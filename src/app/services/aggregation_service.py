from __future__ import annotations

from typing import List, Optional

from src.app.schemas.moderation import TextModerationResult, VisualModerationResult
from src.app.schemas.summarization import SummarizationResult
from src.app.schemas.report import CampaignReport, CategoryAggregate, OverallScore, PostProcessingResult


class AggregationService:
    """
    Aggregates per-post moderation and summarization results into a campaign-level report.
    """

    def aggregate(
        self,
        campaign_id: str,
        visual_results: List[VisualModerationResult],
        text_results: List[TextModerationResult],
        summaries: List[SummarizationResult],
        post_results: List[dict],
    ) -> CampaignReport:
        """
        Aggregate per-post results into campaign-level statistics and thresholds.

        Args:
            campaign_id: Campaign identifier
            visual_results: List of visual moderation results
            text_results: List of text moderation results
            summaries: List of summarization results
            post_results: List of per-post metadata (success flags, errors)

        Returns:
            CampaignReport with aggregated scores and status
        """
        
        # Compute visual score aggregate
        visual_scores = []
        for r in visual_results:
            if r and r.categories:
                scores = [cat.safety_score for cat in r.categories if cat.safety_score is not None]
                if scores:
                    visual_scores.append(sum(scores) / len(scores))
        overall_visual_score = sum(visual_scores) / len(visual_scores) if visual_scores else 0

        # Compute text score aggregate
        text_scores = []
        for r in text_results:
            if r and r.categories:
                scores = [cat.safety_score for cat in r.categories if cat.safety_score is not None]
                if scores:
                    text_scores.append(sum(scores) / len(scores))
        overall_text_score = sum(text_scores) / len(text_scores) if text_scores else 0

        # Build category averages
        visual_categories = self._compute_category_aggregates(visual_results)
        text_categories = self._compute_category_aggregates(text_results)

        # Convert post results to PostProcessingResult
        posts = [
            PostProcessingResult(
                post_id=p.get("post_id", "unknown"),
                success=p.get("success", False),
                error_stage=p.get("error_stage"),
                error_message=p.get("error_message"),
            )
            for p in post_results
        ]

        # Count partial failures
        partial_failure_count = sum(1 for p in post_results if not p.get("success"))

        return CampaignReport(
            campaign_id=campaign_id,
            visual_categories=visual_categories,
            text_categories=text_categories,
            overall_visual=OverallScore(
                score=overall_visual_score,
                status=self._get_status(overall_visual_score),
            ),
            overall_text=OverallScore(
                score=overall_text_score,
                status=self._get_status(overall_text_score),
            ),
            summary=f"Campaign {campaign_id} analyzed: {len(posts)} posts, {partial_failure_count} failures",
            posts=posts,
            partial_failure_count=partial_failure_count,
        )

    def _compute_category_aggregates(
        self, results: List[VisualModerationResult] | List[TextModerationResult]
    ) -> List[CategoryAggregate]:
        """Compute average score per category."""
        category_scores = {}

        for result in results:
            if result:
                for cat in result.categories:
                    if cat.category not in category_scores:
                        category_scores[cat.category] = []
                    if cat.safety_score is not None:
                        category_scores[cat.category].append(cat.safety_score)

        return [
            CategoryAggregate(
                category=cat,
                average_safety_score=sum(scores) / len(scores) if scores else 0,
                status=self._get_status(sum(scores) / len(scores) if scores else 0),
            )
            for cat, scores in category_scores.items()
        ]

    def _get_status(self, score: float) -> str:
        """Determine status label from score."""
        if score >= 85:
            return "safe"
        elif score >= 60:
            return "review"
        else:
            return "unsafe"