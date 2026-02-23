from __future__ import annotations

from typing import Iterable, List

from src.app.schemas.ingestion import IngestedPost, IngestionResult


class IngestionService:
    """
    Responsibility:
    - Normalize campaign input into a clean list of posts + media URLs.
    - No downloading, no AI, no media processing.
    """

    async def ingest(self, campaign_id: str, posts_payload: Iterable[dict]) -> IngestionResult:
        posts: List[IngestedPost] = []

        for p in posts_payload:
            # Expecting upstream schema validation already happened in routes.
            # This service just normalizes fields safely.
            post_id = str(p.get("post_id") or p.get("id"))
            caption = p.get("caption") or p.get("text")

            media_urls = p.get("media_urls") or []
            # allow single field "media_url"
            if not media_urls and p.get("media_url"):
                media_urls = [p["media_url"]]

            posts.append(
                IngestedPost(
                    post_id=post_id,
                    url=p.get("url"),
                    caption=caption,
                    media_urls=media_urls,
                )
            )

        return IngestionResult(campaign_id=campaign_id, posts=posts)