import pytest
from unittest.mock import AsyncMock

from src.app.services.moderation_service import ModerationService, SightengineClient


@pytest.mark.asyncio
async def test_visual_partial_failures(tmp_path):
    frame1 = tmp_path / "f1.jpg"
    frame2 = tmp_path / "f2.jpg"
    frame1.write_bytes(b"x")
    frame2.write_bytes(b"x")

    client = SightengineClient.__new__(SightengineClient)
    client.check_image = AsyncMock(side_effect=[
        {"nudity": {"raw": 0.0, "suggestive": 0.0}, "violence": {"prob": 0.0}, "weapon": {"classes": {}}, "gore": {"classes": {}}, "type": {"deepfake": 0.0}},
        RuntimeError("boom"),
    ])

    svc = ModerationService(client=client)
    res = await svc.moderate_visual("p1", [str(frame1), str(frame2)])

    assert res.frame_count == 2
    assert len(res.partial_failures) == 1
    assert any(c.category == "Spoof / Fake Content" for c in res.categories)


@pytest.mark.asyncio
async def test_text_moderation_rules(tmp_path):
    client = SightengineClient.__new__(SightengineClient)
    client.check_text_rules = AsyncMock(return_value={
        "status": "success",
        "profanity": {"matches": [{"type": "insult", "intensity": "low", "match": "stupid", "start": 0, "end": 6}]},
        "extremism": {"matches": []},
    })

    svc = ModerationService(client=client)
    res = await svc.moderate_text("p1", "stupid", lang="en")

    profanity = next(c for c in res.categories if c.category == "Profanity")
    assert profanity.safety_score is not None