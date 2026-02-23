from __future__ import annotations

import asyncio
import time
import aiohttp

from typing import Any, Dict, List, Optional

from aiohttp import ClientError
from app.utils.retry import run_with_retry, RetryError
from app.core.metrics import AI_LATENCY, AI_FAILURES
from src.app.core.config import settings
from src.app.schemas.moderation import (
    CategoryScore,
    TextModerationResult,
    VisualModerationResult,
)


class ModerationError(RuntimeError):
    pass


class SightEngineClient:
    """
    SightEngine API client for visual + text moderation.
    https://sightengine.com/docs
    """

    def __init__(self, api_user: str, api_secret: str) -> None:
        self._api_user = api_user
        self._api_secret = api_secret
        self._base = "https://api.sightengine.com/1.0"

    async def check_image(self, image_path: str) -> Dict[str, Any]:
        """
        Check a single image for adult, racy, gore, violence, etc.
        Returns raw SightEngine response.
        """
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            with open(image_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("media", f)
                data.add_field("models", "all")
                data.add_field("api_user", self._api_user)
                data.add_field("api_secret", self._api_secret)

                async with session.post(f"{self._base}/check", data=data) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        raise ModerationError(f"SightEngine image check failed ({resp.status}): {text[:500]}")
                    return await resp.json()

    async def check_text(self, text_content: str) -> Dict[str, Any]:
        """
        Check text for profanity, hate speech, etc.
        Returns raw SightEngine response.
        """
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                "text": text_content,
                "models": "text-prop",
                "api_user": self._api_user,
                "api_secret": self._api_secret,
            }
            async with session.post(f"{self._base}/check", data=payload) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise ModerationError(f"SightEngine text check failed ({resp.status}): {text[:500]}")
                return await resp.json()


def _risk_to_safety_pct(risk: float) -> float:
    """Convert SightEngine risk score (0-1) to safety percentage (0-100)."""
    risk = max(0.0, min(1.0, float(risk)))
    return (1.0 - risk) * 100.0


class ModerationService:
    """
    Responsibility:
    - Moderate visual content (images) via SightEngine
    - Moderate text content (captions + transcripts) via SightEngine
    - Track latency and failures via Prometheus metrics
    - Return structured VisualModerationResult and TextModerationResult
    """

    def __init__(self, client: Optional[SightEngineClient] = None) -> None:
        self._client = client or SightEngineClient(
            settings.SIGHTENGINE_API_USER,
            settings.SIGHTENGINE_API_SECRET,
        )

    async def moderate_visual(self, post_id: str, frame_paths: List[str]) -> VisualModerationResult:
        """
        Moderate visual content (frames).
        """
        if not frame_paths:
            return VisualModerationResult(
                post_id=post_id,
                categories=[],
                frame_count=0,
                partial_failures=[],
            )

        adult_safety = []
        racy_safety = []
        violence_weapon_safety = []
        gore_safety = []
        spoof_safety = []
        partial_failures = []

        for frame_path in frame_paths:
            try:
                # ---- IMAGE CHECK STAGE ----
                start = time.perf_counter()
                try:
                    raw = await run_with_retry(
                        self._client.check_image,
                        frame_path,
                        max_attempts=settings.RETRY_ATTEMPTS,
                        timeout=settings.REQUEST_TIMEOUT,
                        retryable_exceptions=(ClientError, asyncio.TimeoutError),
                    )
                    duration = time.perf_counter() - start
                    AI_LATENCY.labels(provider="sightengine", operation="image_check").observe(duration)
                except Exception as e:
                    AI_FAILURES.labels(provider="sightengine", operation="image_check").inc()
                    partial_failures.append({"frame": frame_path, "error": str(e)})
                    continue

                # Parse adult content
                a_classes = raw.get("classes", {}).get("adult", {})
                adult_risk = max([float(v) for v in a_classes.values()], default=0.0)
                adult_safety.append(_risk_to_safety_pct(adult_risk))

                # Parse racy content
                r_classes = raw.get("classes", {}).get("racy", {})
                racy_risk = max([float(v) for v in r_classes.values()], default=0.0)
                racy_safety.append(_risk_to_safety_pct(racy_risk))

                # Parse violence + weapons
                vw_classes = raw.get("classes", {}).get("violence", {})
                violence_risk = max([float(v) for v in vw_classes.values()], default=0.0)
                violence_weapon_safety.append(_risk_to_safety_pct(violence_risk))

                # Parse gore
                g_classes = raw.get("classes", {}).get("gore", {})
                gore_risk = max([float(v) for v in g_classes.values()], default=0.0)
                gore_safety.append(_risk_to_safety_pct(gore_risk))

                # Parse deepfake/spoof
                deepfake_obj = raw.get("type") or {}
                deepfake_risk = float(deepfake_obj.get("deepfake", 0.0))
                spoof_safety.append(_risk_to_safety_pct(deepfake_risk))

            except Exception as e:
                partial_failures.append({"frame": frame_path, "error": str(e)})
                continue

        def worst(scores: List[float]) -> float:
            return min(scores) if scores else 100.0

        from app.utils.scoring import visual_status

        adult = worst(adult_safety)
        racy = worst(racy_safety)
        vio_weap = worst(violence_weapon_safety)
        gore = worst(gore_safety)
        spoof = worst(spoof_safety)

        cats = [
            CategoryScore(
                category="Adult Content",
                safety_score=round(adult, 2),
                status=visual_status("Adult Content", adult),
            ),
            CategoryScore(
                category="Violence / Weapons",
                safety_score=round(vio_weap, 2),
                status=visual_status("Violence / Weapons", vio_weap),
            ),
            CategoryScore(
                category="Racy Content",
                safety_score=round(racy, 2),
                status=visual_status("Racy Content", racy),
            ),
            CategoryScore(
                category="Medical / Gore",
                safety_score=round(gore, 2),
                status=visual_status("Medical / Gore", gore),
            ),
            CategoryScore(
                category="Spoof / Fake Content",
                safety_score=round(spoof, 2),
                status=visual_status("Spoof / Fake Content", spoof),
            ),
        ]

        return VisualModerationResult(
            post_id=post_id,
            categories=cats,
            frame_count=len(frame_paths),
            partial_failures=partial_failures,
        )

    async def moderate_text(self, post_id: str, text: str, lang: str = "en") -> TextModerationResult:
        """
        Moderate text content (caption + transcript).
        """
        if not text.strip():
            return TextModerationResult(
                post_id=post_id,
                language=lang,
                categories=[],
            )

        try:
            # ---- TEXT CHECK STAGE ----
            start = time.perf_counter()
            try:
                raw = await run_with_retry(
                    self._client.check_text,
                    text,
                    max_attempts=settings.RETRY_ATTEMPTS,
                    timeout=settings.REQUEST_TIMEOUT,
                    retryable_exceptions=(ClientError, asyncio.TimeoutError),
                )
                duration = time.perf_counter() - start
                AI_LATENCY.labels(provider="sightengine", operation="text_check").observe(duration)
            except Exception as e:
                AI_FAILURES.labels(provider="sightengine", operation="text_check").inc()
                raise

            from app.utils.scoring import text_status

            # Parse profanity
            profanity_data = raw.get("profanity", {})
            profanity_risk = float(profanity_data.get("matches", 0)) / max(len(text.split()), 1)
            profanity_risk = min(profanity_risk, 1.0)
            profanity_safety = _risk_to_safety_pct(profanity_risk)

            # Parse hate speech
            extremism_data = raw.get("extremism", {})
            hate_risk = float(extremism_data.get("confidence", 0.0))
            hate_safety = _risk_to_safety_pct(hate_risk)

            # Parse political content (not explicitly in SightEngine; use extremism as proxy)
            political_safety = _risk_to_safety_pct(hate_risk * 0.5)  # Lower weight

            cats = [
                CategoryScore(
                    category="Profanity",
                    safety_score=round(profanity_safety, 2),
                    status=text_status("Profanity", profanity_safety),
                    raw={"profanity": profanity_data},
                ),
                CategoryScore(
                    category="Hate Speech",
                    safety_score=round(hate_safety, 2),
                    status=text_status("Hate Speech", hate_safety),
                    raw={"extremism": extremism_data},
                ),
                CategoryScore(
                    category="Political Content",
                    safety_score=round(political_safety, 2),
                    status=text_status("Political Content", political_safety),
                    raw={"proxy": "extremism"},
                ),
                CategoryScore(
                    category="Misinformation",
                    safety_score=None,
                    status="Warning",
                    error="not_evaluated_by_sightengine",
                ),
                CategoryScore(
                    category="Brand Mentions",
                    safety_score=None,
                    status="Warning",
                    error="not_evaluated_by_sightengine",
                    explanation="Evaluate via entity/brand detection in summarization stage.",
                ),
                CategoryScore(
                    category="Disclosure Compliance",
                    safety_score=None,
                    status="Warning",
                    error="not_evaluated_by_sightengine",
                    explanation="Evaluate via caption keywords (#ad/#sponsored) in summarization stage.",
                ),
            ]

            return TextModerationResult(post_id=post_id, language=lang, categories=cats)

        except Exception as e:
            raise ModerationError(f"Text moderation failed: {str(e)}")