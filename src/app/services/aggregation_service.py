from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from src.app.schemas.moderation import VisualModerationResult, TextModerationResult
from src.app.schemas.summarization import SummarizationResult
from src.app.schemas.report import CampaignReport, CategoryAggregate, OverallScore

SAFE = "Safe"
WARNING = "Warning"
UNSAFE = "Unsafe"


VISUAL_WEIGHTS = {
    "Adult Content": 2.0,
    "Violence / Weapons": 2.0,
    "Racy Content": 1.0,
    "Medical / Gore": 1.0,
    "Spoof / Fake Content": 1.5,
}

TEXT_WEIGHTS = {
    "Profanity": 1.0,
    "Hate Speech": 2.0,
    "Misinformation": 2.0,
    "Brand Mentions": 1.0,
    "Disclosure Compliance": 1.0,
    "Political Content": 1.0,
}


def _status_visual(score: float) -> str:
    if score >= 90:
        return SAFE
    if score >= 70:
        return WARNING
    return UNSAFE


def _status_text(score: float) -> str:
    if score >= 85:
        return SAFE
    if score >= 70:
        return WARNING
    return UNSAFE


class AggregationService:
    """
    Responsibility:
    - Aggregate post-level moderation & summarization
    - Compute weighted campaign-level scores
    - Return structured CampaignReport
    """

    def aggregate(
        self,
        campaign_id: str,
        visual_results: List[VisualModerationResult],
        text_results: List[TextModerationResult],
        summaries: List[SummarizationResult],
        post_results: List[dict],
    ) -> CampaignReport:

        visual_scores = defaultdict(list)
        text_scores = defaultdict(list)

        # ---- Collect per-post scores ----
        for vr in visual_results:
            for cat in vr.categories:
                if cat.safety_score is not None:
                    visual_scores[cat.category].append(cat.safety_score)

        for tr in text_results:
            for cat in tr.categories:
                if cat.safety_score is not None:
                    text_scores[cat.category].append(cat.safety_score)

        for sr in summaries:
            for sig in sr.signals:
                if sig.safety_score is not None:
                    text_scores[sig.category].append(sig.safety_score)

        # ---- Average per category ----
        visual_aggregates: List[CategoryAggregate] = []
        for cat, scores in visual_scores.items():
            avg = sum(scores) / len(scores)
            visual_aggregates.append(
                CategoryAggregate(
                    category=cat,
                    average_safety_score=round(avg, 2),
                    status=_status_visual(avg),
                )
            )

        text_aggregates: List[CategoryAggregate] = []
        for cat, scores in text_scores.items():
            avg = sum(scores) / len(scores)
            text_aggregates.append(
                CategoryAggregate(
                    category=cat,
                    average_safety_score=round(avg, 2),
                    status=_status_text(avg),
                )
            )

        # ---- Weighted Overall Visual ----
        visual_weighted_sum = 0.0
        visual_weight_total = 0.0

        for cat in visual_aggregates:
            weight = VISUAL_WEIGHTS.get(cat.category, 1.0)
            visual_weighted_sum += cat.average_safety_score * weight
            visual_weight_total += weight

        overall_visual_score = (
            visual_weighted_sum / visual_weight_total if visual_weight_total else 100.0
        )

        # ---- Weighted Overall Text ----
        text_weighted_sum = 0.0
        text_weight_total = 0.0

        for cat in text_aggregates:
            weight = TEXT_WEIGHTS.get(cat.category, 1.0)
            text_weighted_sum += cat.average_safety_score * weight
            text_weight_total += weight

        overall_text_score = (
            text_weighted_sum / text_weight_total if text_weight_total else 100.0
        )

        overall_visual = OverallScore(
            score=round(overall_visual_score, 2),
            status=_status_visual(overall_visual_score),
        )

        overall_text = OverallScore(
            score=round(overall_text_score, 2),
            status=_status_text(overall_text_score),
        )

        # ---- Human Summary ----
        summary = (
            f"Campaign {campaign_id} analyzed across {len(visual_results)} posts. "
            f"Overall visual safety: {overall_visual.score}% ({overall_visual.status}). "
            f"Overall text safety: {overall_text.score}% ({overall_text.status})."
        )

        partial_failures = [p for p in post_results if not p["success"]]

        return CampaignReport(
            campaign_id=campaign_id,
            visual_categories=visual_aggregates,
            text_categories=text_aggregates,
            overall_visual=overall_visual,
            overall_text=overall_text,
            summary=summary,
            posts=post_results,
            partial_failure_count=len(partial_failures),
        )