from __future__ import annotations

import logging

from typing import Iterable, List

from src.app.schemas.ingestion import IngestedPost, IngestionResult

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Responsibility:
    - Normalize campaign input into a clean list of posts + media URLs.
    - No downloading, no AI, no media processing.
    """

    async def ingest(self, campaign_id: str, posts_payload: Iterable[dict]) -> IngestionResult:
        posts: List[IngestedPost] = []

        for p in posts_payload:
            # Normalize post_id
            post_id = str(
                p.get("post_id")
                or p.get("id")
                or p.get("platform_post_id")
                or ""
            ).strip()

            if not post_id:
                logger.warning("Skipping post without id: %s", p)
                continue

            caption = p.get("caption") or p.get("text") or ""

            media_urls = p.get("media_urls") or []

            # Accept single media_url
            if not media_urls and p.get("media_url"):
                media_urls = [p["media_url"]]

            # Accept single url (new payload)
            if not media_urls and p.get("url"):
                media_urls = [p["url"]]

            if not media_urls:
                logger.warning("Post %s has no media URLs", post_id)
                continue

            posts.append(
                IngestedPost(
                    post_id=post_id,
                    url=p.get("url"),
                    caption=caption,
                    media_urls=media_urls,
                )
            )

        return IngestionResult(
            campaign_id=campaign_id,
            posts=posts,
        )