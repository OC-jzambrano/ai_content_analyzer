from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientError
from app.utils.retry import run_with_retry

from src.app.core.config import settings
from src.app.schemas.moderation import (
    CategoryScore,
    TextModerationResult,
    VisualModerationResult,
)

SAFE = "Safe"
WARNING = "Warning"
UNSAFE = "Unsafe"


def _status_from_thresholds(score: float, safe_min: float, warn_min: float) -> str:
    # score is "safety %" (higher = safer)
    if score >= safe_min:
        return SAFE
    if score >= warn_min:
        return WARNING
    return UNSAFE


def _risk_to_safety_pct(risk: float) -> float:
    # risk is 0..1 where higher = more risky
    risk = max(0.0, min(1.0, risk))
    return (1.0 - risk) * 100.0


@dataclass(frozen=True)
class SightengineCreds:
    api_user: str
    api_secret: str


class SightengineClient:
    """
    One responsibility:
    - Make HTTP calls to Sightengine endpoints.
    """

    def __init__(self, creds: SightengineCreds) -> None:
        self._creds = creds
        self._base = "https://api.sightengine.com/1.0"

    async def check_image(self, image_path: str, models: str) -> Dict[str, Any]:
        # POST multipart to /check.json :contentReference[oaicite:3]{index=3}
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        data = aiohttp.FormData()
        data.add_field("media", open(image_path, "rb"), filename=Path(image_path).name)
        data.add_field("models", models)
        data.add_field("api_user", self._creds.api_user)
        data.add_field("api_secret", self._creds.api_secret)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self._base}/check.json", data=data) as resp:
                txt = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f"Sightengine image check failed ({resp.status}): {txt[:500]}")
                return await resp.json()

    async def check_text_rules(
        self,
        text: str,
        lang: str,
        categories: str,
    ) -> Dict[str, Any]:
        # POST form to /text/check.json (mode=rules) :contentReference[oaicite:4]{index=4}
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        payload = {
            "text": text,
            "lang": lang,
            "categories": categories,
            "mode": "rules",
            "api_user": self._creds.api_user,
            "api_secret": self._creds.api_secret,
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self._base}/text/check.json", data=payload) as resp:
                txt = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f"Sightengine text check failed ({resp.status}): {txt[:500]}")
                return await resp.json()


class ModerationService:
    """
    Responsibility:
    - Visual moderation of frames (Sightengine /check.json)
    - Text moderation (Sightengine /text/check.json)
    - Convert raw outputs into your required categories, scores, statuses
    - Never raises for single-frame failure: returns partial results
    """

    def __init__(self, client: Optional[SightengineClient] = None) -> None:
        creds = SightengineCreds(
            api_user=settings.SIGHTENGINE_API_USER,
            api_secret=settings.SIGHTENGINE_API_SECRET,
        )
        self._client = client or SightengineClient(creds)

    async def moderate_visual(self, post_id: str, frame_paths: List[str]) -> VisualModerationResult:
        # Models mapped to your requirements:
        # - Adult/Racy: nudity & suggestive (we use nudity-2.1)
        # - Violence/Weapons: violence + weapon
        # - Medical/Gore: gore-2.0
        # - Spoof/Fake: deepfake (proxy for face-swap manipulation) :contentReference[oaicite:5]{index=5}
        #
        # Note: all are run per-frame. Aggregation across posts belongs to aggregation_service.
        models = "nudity-2.1,violence,weapon,gore-2.0,deepfake"

        partial_failures: List[str] = []
        raw_per_frame: List[Dict[str, Any]] = []

        # best-effort, no blocking on one bad frame
        for fp in frame_paths:
            try:
                raw = await run_with_retry(
                self._client.check_image,
                fp,
                models,
                max_attempts=settings.RETRY_ATTEMPTS,
                timeout=settings.REQUEST_TIMEOUT,
                retryable_exceptions=(ClientError, asyncio.TimeoutError),
            )
                raw_per_frame.append(raw)
            except Exception:
                partial_failures.append(fp)

        # If everything failed, return warnings with no scores
        if not raw_per_frame:
            cats = [
                CategoryScore(category="Adult Content", safety_score=None, status=WARNING, error="all_frames_failed"),
                CategoryScore(category="Racy Content", safety_score=None, status=WARNING, error="all_frames_failed"),
                CategoryScore(category="Violence / Weapons", safety_score=None, status=WARNING, error="all_frames_failed"),
                CategoryScore(category="Medical / Gore", safety_score=None, status=WARNING, error="all_frames_failed"),
                CategoryScore(category="Spoof / Fake Content", safety_score=None, status=WARNING, error="all_frames_failed"),
            ]
            return VisualModerationResult(
                post_id=post_id,
                categories=cats,
                frame_count=len(frame_paths),
                partial_failures=partial_failures,
            )

        # Convert per-frame raw to per-category "worst safety" across frames
        # (worst safety = minimum safety score)
        adult_safety: List[float] = []
        racy_safety: List[float] = []
        violence_weapon_safety: List[float] = []
        gore_safety: List[float] = []
        spoof_safety: List[float] = []

        for raw in raw_per_frame:
            # nudity-2.1 usually returns "nudity" object; fields can vary by model version.
            nud = raw.get("nudity") or {}
            # "raw" and "suggestive" are common; treat them as risk.
            adult_risk = float(nud.get("raw", 0.0))
            racy_risk = float(nud.get("suggestive", 0.0))

            adult_safety.append(_risk_to_safety_pct(adult_risk))
            racy_safety.append(_risk_to_safety_pct(racy_risk))

            vio = raw.get("violence") or {}
            weapon = raw.get("weapon") or {}

            # violence.prob is defined as an overall probability :contentReference[oaicite:6]{index=6}
            violence_risk = float(vio.get("prob", 0.0))

            # weapon model exposes classes.* (firearm/knife/etc.) :contentReference[oaicite:7]{index=7}
            w_classes = (weapon.get("classes") or {}) if isinstance(weapon, dict) else {}
            weapon_risk = max(
                float(w_classes.get("firearm", 0.0)),
                float(w_classes.get("knife", 0.0)),
                float(w_classes.get("firearm_gesture", 0.0)),
                float(w_classes.get("firearm_toy", 0.0)),
                0.0,
            )

            violence_weapon_risk = max(violence_risk, weapon_risk)
            violence_weapon_safety.append(_risk_to_safety_pct(violence_weapon_risk))

            gore = raw.get("gore") or {}
            # gore-2.0 returns multiple classes; treat max class prob as risk :contentReference[oaicite:8]{index=8}
            g_classes = (gore.get("classes") or {}) if isinstance(gore, dict) else {}
            gore_risk = max([float(v) for v in g_classes.values()], default=0.0)
            gore_safety.append(_risk_to_safety_pct(gore_risk))

            # deepfake model returns type.deepfake 0..1 :contentReference[oaicite:9]{index=9}
            deepfake_obj = raw.get("type") or {}
            deepfake_risk = float(deepfake_obj.get("deepfake", 0.0))
            spoof_safety.append(_risk_to_safety_pct(deepfake_risk))

        def worst(scores: List[float]) -> float:
            return min(scores) if scores else 100.0

        adult = worst(adult_safety)
        racy = worst(racy_safety)
        vio_weap = worst(violence_weapon_safety)
        gore = worst(gore_safety)
        spoof = worst(spoof_safety)

        # Visual thresholds per your spec:
        # Safe >= 90, Warning 70-89, Unsafe < 70
        adult_status = _status_from_thresholds(adult, safe_min=90, warn_min=70)
        racy_status = _status_from_thresholds(racy, safe_min=90, warn_min=70)
        vw_status = _status_from_thresholds(vio_weap, safe_min=90, warn_min=70)
        gore_status = _status_from_thresholds(gore, safe_min=90, warn_min=70)

        # Spoof/Fake special rule: flag below 90 even if others safe
        spoof_status = SAFE if spoof >= 90 else WARNING

        cats = [
            CategoryScore(category="Adult Content", safety_score=round(adult, 2), status=adult_status),
            CategoryScore(category="Violence / Weapons", safety_score=round(vio_weap, 2), status=vw_status),
            CategoryScore(category="Racy Content", safety_score=round(racy, 2), status=racy_status),
            CategoryScore(category="Medical / Gore", safety_score=round(gore, 2), status=gore_status),
            CategoryScore(category="Spoof / Fake Content", safety_score=round(spoof, 2), status=spoof_status),
        ]

        return VisualModerationResult(
            post_id=post_id,
            categories=cats,
            frame_count=len(frame_paths),
            partial_failures=partial_failures,
        )

    async def moderate_text(self, post_id: str, text: str, lang: str = "en") -> TextModerationResult:
        # Rule-based categories available include profanity, violence, extremism, weapon, etc. :contentReference[oaicite:10]{index=10}
        categories = "profanity,violence,extremism,weapon"
        raw: Optional[Dict[str, Any]] = None
        try:
            raw = await run_with_retry(
            self._client.check_text_rules,
            text,
            lang,
            categories,
            max_attempts=settings.RETRY_ATTEMPTS,
            timeout=settings.REQUEST_TIMEOUT,
            retryable_exceptions=(ClientError, asyncio.TimeoutError),)
        except Exception as e:
            # full failure: return warnings with no scores
            return TextModerationResult(
                post_id=post_id,
                language=lang,
                categories=[
                    CategoryScore(category="Profanity", safety_score=None, status=WARNING, error=str(e)),
                    CategoryScore(category="Hate Speech", safety_score=None, status=WARNING, error=str(e)),
                    CategoryScore(category="Political Content", safety_score=None, status=WARNING, error=str(e)),
                    CategoryScore(category="Misinformation", safety_score=None, status=WARNING, error="not_evaluated_by_sightengine"),
                    CategoryScore(category="Brand Mentions", safety_score=None, status=WARNING, error="not_evaluated_by_sightengine"),
                    CategoryScore(category="Disclosure Compliance", safety_score=None, status=WARNING, error="not_evaluated_by_sightengine"),
                ],
            )

        # Profanity: if any matches exist => reduce safety
        prof_matches = ((raw.get("profanity") or {}).get("matches") or [])
        profanity_risk = 0.0
        if prof_matches:
            # crude risk: more matches and higher intensity increases risk
            intensity_weight = {"low": 0.25, "medium": 0.5, "high": 0.8}
            profanity_risk = min(
                1.0,
                sum(intensity_weight.get(m.get("intensity", "low"), 0.25) for m in prof_matches) / 3.0,
            )
        profanity_safety = _risk_to_safety_pct(profanity_risk)

        # Hate Speech (best-effort): use discriminatory items detected inside profanity matches (Sightengine rules describe discriminatory under profanity) :contentReference[oaicite:11]{index=11}
        hate_risk = 0.0
        if prof_matches:
            discriminatory = [m for m in prof_matches if m.get("type") in ("discriminatory", "racist", "hate")]
            if discriminatory:
                hate_risk = min(1.0, 0.7 + 0.1 * len(discriminatory))
        hate_safety = _risk_to_safety_pct(hate_risk)

        # Political Content (best-effort proxy): extremism matches ≠ politics, but it’s the closest rules-based signal available.
        # We label it but don’t block unless < 70 (your spec).
        extremism_matches = ((raw.get("extremism") or {}).get("matches") or [])
        political_risk = 0.0 if not extremism_matches else min(1.0, 0.6 + 0.1 * len(extremism_matches))
        political_safety = _risk_to_safety_pct(political_risk)

        # Text thresholds:
        # Safe >= 85, Warning 70-84, Unsafe < 70
        profanity_status = _status_from_thresholds(profanity_safety, safe_min=85, warn_min=70)

        # strict categories: Hate Speech and Violence-related always strictest thresholds
        # Apply safe>=90, warn>=70 for hate + violence-like signals
        hate_status = _status_from_thresholds(hate_safety, safe_min=90, warn_min=70)

        political_status = SAFE if political_safety >= 85 else (WARNING if political_safety >= 70 else UNSAFE)

        cats = [
            CategoryScore(category="Profanity", safety_score=round(profanity_safety, 2), status=profanity_status, raw={"profanity": raw.get("profanity")}),
            CategoryScore(category="Hate Speech", safety_score=round(hate_safety, 2), status=hate_status, raw={"profanity": raw.get("profanity")}),
            CategoryScore(category="Political Content", safety_score=round(political_safety, 2), status=political_status, raw={"extremism": raw.get("extremism")}),
            # Not natively supported by Sightengine text models; handled in summarization stage or a dedicated NLP stage
            CategoryScore(category="Misinformation", safety_score=None, status=WARNING, error="not_evaluated_by_sightengine"),
            CategoryScore(category="Brand Mentions", safety_score=None, status=WARNING, explanation="Evaluate via entity/brand detection in summarization stage.", error="not_evaluated_by_sightengine"),
            CategoryScore(category="Disclosure Compliance", safety_score=None, status=WARNING, explanation="Evaluate via caption keywords (#ad/#sponsored) + heuristics in summarization stage.", error="not_evaluated_by_sightengine"),
        ]

        return TextModerationResult(post_id=post_id, language=lang, categories=cats)