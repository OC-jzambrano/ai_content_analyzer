from __future__ import annotations

from typing import List, Optional

from src.app.schemas.moderation import TextModerationResult, VisualModerationResult
from src.app.schemas.summarization import SummarizationResult
from src.app.schemas.report import CampaignReport


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
        visual_scores = [r.overall_score for r in visual_results if r]
        overall_visual = sum(visual_scores) / len(visual_scores) if visual_scores else 0

        # Compute text score aggregate
        text_scores = [r.overall_score for r in text_results if r]
        overall_text = sum(text_scores) / len(text_scores) if text_scores else 0

        # Compute campaign-level overall score
        overall_campaign = (overall_visual + overall_text) / 2

        # Determine status based on score
        status = self._get_status(overall_campaign)

        # Build category averages
        category_averages = self._compute_category_averages(visual_results, text_results)

        # Count posts by status
        status_counts = self._count_post_statuses(post_results)

        # Extract top risk posts
        top_risk_posts = self._get_top_risk_posts(post_results, limit=5)

        return CampaignReport(
            campaign_id=campaign_id,
            overall_visual_score=overall_visual,
            overall_text_score=overall_text,
            overall_campaign_score=overall_campaign,
            status=status,
            category_averages=category_averages,
            status_counts=status_counts,
            top_risk_posts=top_risk_posts,
            total_posts=len(post_results),
            successful_posts=sum(1 for p in post_results if p.get("success")),
        )

    def _get_status(self, score: float) -> str:
        """Determine status label from score."""
        if score >= 85:
            return "safe"
        elif score >= 60:
            return "review"
        else:
            return "unsafe"

    def _compute_category_averages(
        self,
        visual_results: List[VisualModerationResult],
        text_results: List[TextModerationResult],
    ) -> dict:
        """Compute average score per category across all posts."""
        category_scores = {}

        # Aggregate visual categories
        for vresult in visual_results:
            if vresult:
                for cat in vresult.categories:
                    if cat.category not in category_scores:
                        category_scores[cat.category] = []
                    category_scores[cat.category].append(cat.safety_score)

        # Aggregate text categories
        for tresult in text_results:
            if tresult:
                for cat in tresult.categories:
                    if cat.category not in category_scores:
                        category_scores[cat.category] = []
                    category_scores[cat.category].append(cat.safety_score)

        # Compute averages
        return {
            cat: sum(scores) / len(scores)
            for cat, scores in category_scores.items()
        }

    def _count_post_statuses(self, post_results: List[dict]) -> dict:
        """Count posts by success status."""
        safe_count = 0
        review_count = 0
        unsafe_count = 0

        for post in post_results:
            if not post.get("success"):
                continue
            # You may want to infer status from error_message or stored scores
            # For now, default to "safe" if no explicit status is stored
            safe_count += 1

        return {
            "safe": safe_count,
            "review": review_count,
            "unsafe": unsafe_count,
        }

    def _get_top_risk_posts(self, post_results: List[dict], limit: int = 5) -> List[dict]:
        """Extract posts with lowest scores (highest risk)."""
        # Sort by success descending, then filter or rank by error presence
        at_risk = [p for p in post_results if not p.get("success") or p.get("partial_failure")]
        return at_risk[:limit]