import pytest
from src.app.services.ingestion_service import IngestionService


@pytest.mark.asyncio
async def test_ingestion_normalizes_posts():
    svc = IngestionService()

    res = await svc.ingest(
        campaign_id="c1",
        posts_payload=[
            {"id": "p1", "caption": "hi", "media_url": "https://example.com/a.mp4"},
            {"post_id": "p2", "text": "yo", "media_urls": ["https://example.com/b.mp4"]},
        ],
    )

    assert res.campaign_id == "c1"
    assert len(res.posts) == 2
    assert res.posts[0].post_id == "p1"
    assert len(res.posts[0].media_urls) == 1
    assert res.posts[1].post_id == "p2"