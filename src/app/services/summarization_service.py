from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientError
from app.utils.retry import run_with_retry

from app.utils.scoring import text_status

from src.app.core.config import settings
from src.app.schemas.summarization import PolicySignal, SummarizationResult

SAFE = "Safe"
WARNING = "Warning"
UNSAFE = "Unsafe"


class ClaudeError(RuntimeError):
    pass


class ClaudeClient:
    """
    One responsibility:
    - Call Anthropic Messages API (POST /v1/messages).
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base = "https://api.anthropic.com/v1/messages"

    async def create_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(self._base, json=payload) as resp:
                txt = await resp.text()
                if resp.status >= 400:
                    raise ClaudeError(f"Claude API error ({resp.status}): {txt[:800]}")
                return await resp.json()


class SummarizationService:
    """
    Responsibility:
    - Generate a concise human summary
    - Extract structured policy signals:
        - Brand Mentions
        - Disclosure Compliance
        - Misinformation
        - Political Content (labeling + risk)
    - No aggregation across posts (that’s Step 6.8 aggregation_service)
    """

    def __init__(self, client: Optional[ClaudeClient] = None) -> None:
        self._client = client or ClaudeClient(settings.CLAUDE_API_KEY)

    async def summarize(
        self,
        post_id: str,
        caption: str | None,
        transcript_text: str | None,
        visual_findings: Dict[str, Any] | None = None,
    ) -> SummarizationResult:
        caption = caption or ""
        transcript_text = transcript_text or ""

        # Keep the prompt deterministic and JSON-first.
        system = (
            "You are a content safety and marketing compliance analyst. "
            "Return STRICT JSON only, no markdown, no extra text. "
            "Scores are safety percentages 0-100 where higher means safer."
        )

        user = {
            "post_id": post_id,
            "caption": caption,
            "transcript": transcript_text,
            "visual_findings_hint": visual_findings or {},
            "required": {
                "summary": "1-3 short paragraphs max",
                "key_points": "3-7 bullets",
                "signals": [
                    {
                        "category": "Brand Mentions",
                        "safety_score": "0-100 or null",
                        "explanation": "short",
                        "recommendation": "short if Warning/Unsafe else null",
                    },
                    {
                        "category": "Disclosure Compliance",
                        "safety_score": "0-100 or null",
                        "explanation": "short",
                        "recommendation": "short if Warning/Unsafe else null",
                    },
                    {
                        "category": "Misinformation",
                        "safety_score": "0-100 or null",
                        "explanation": "short",
                        "recommendation": "short if Warning/Unsafe else null",
                    },
                    {
                        "category": "Political Content",
                        "safety_score": "0-100 or null",
                        "explanation": "short",
                        "recommendation": "short if <70 else null",
                    },
                ],
            },
            "scoring_rules": {
                "Brand Mentions": "Warning below 85",
                "Disclosure Compliance": "Warning below 85",
                "Political Content": "Label always; do not block unless <70",
            },
            "hints": {
                "disclosure_keywords": ["#ad", "#sponsored", "#paidpartnership", "paid partnership", "sponsored"],
                "brand_mentions_definition": "explicit brand/product/company mentions or obvious sponsorship cues",
                "misinformation_definition": "claims presented as facts that are likely false or misleading (health/finance especially)",
                "political_definition": "politicians, elections, parties, activism, policy debates",
            },
        }

        payload = {
            "model": settings.CLAUDE_MODEL,
            "max_tokens": settings.CLAUDE_MAX_TOKENS,
            "temperature": settings.CLAUDE_TEMPERATURE,
            "system": system,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": json.dumps(user)}]},
            ],
        }

        data = await run_with_retry(
        self._client.create_message,
        payload,
        max_attempts=settings.RETRY_ATTEMPTS,
        timeout=settings.REQUEST_TIMEOUT,
        retryable_exceptions=(ClientError, asyncio.TimeoutError),
    )

        # Anthropic responses return content blocks; we expect the first text block to be JSON. :contentReference[oaicite:1]{index=1}
        content = data.get("content") or []
        text_blocks = [c.get("text") for c in content if c.get("type") == "text"]
        if not text_blocks:
            raise ClaudeError("Claude response missing text content")

        raw_json = text_blocks[0].strip()
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ClaudeError(f"Claude returned non-JSON: {raw_json[:400]}") from e

        # Map to schema + enforce your threshold logic here (don’t trust the model to set status)
        summary = str(parsed.get("summary") or "")
        key_points = parsed.get("key_points") or []
        if not isinstance(key_points, list):
            key_points = []

        signals_out: List[PolicySignal] = []
        for s in (parsed.get("signals") or []):
            if not isinstance(s, dict):
                continue
            cat = str(s.get("category") or "").strip()
            score = s.get("safety_score")
            score_f: Optional[float] = None
            if isinstance(score, (int, float)):
                score_f = float(score)

            explanation = s.get("explanation")
            recommendation = s.get("recommendation")

            # Apply required status rules:
            status = WARNING
            if score_f is not None:
                status = text_status(cat, score_f)

                # Brand + Disclosure: Warning below 85 (already in _status_text), but ensure recommendation present.
                if cat in ("Brand Mentions", "Disclosure Compliance") and score_f < 85 and not recommendation:
                    recommendation = "Add clear disclosure (e.g., #ad/#sponsored) and clarify brand relationship."

                # Political: label always; don’t block unless <70 (status will become Unsafe below 70).
                # If between 70-84 => Warning label only.

            signals_out.append(
                PolicySignal(
                    category=cat,
                    safety_score=round(score_f, 2) if score_f is not None else None,
                    status=status,
                    explanation=str(explanation) if explanation else None,
                    recommendation=str(recommendation) if recommendation else None,
                )
            )

        return SummarizationResult(
            post_id=post_id,
            summary=summary,
            key_points=[str(x) for x in key_points][:10],
            signals=signals_out,
        )

    async def _with_retries(self, fn, *args):
        last: Optional[Exception] = None
        for attempt in range(1, settings.RETRY_ATTEMPTS + 1):
            try:
                return await fn(*args)
            except Exception as e:
                last = e
                if attempt < settings.RETRY_ATTEMPTS:
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue
                raise last