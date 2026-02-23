import pytest
from unittest.mock import AsyncMock

from src.app.services.summarization_service import SummarizationService, ClaudeClient


@pytest.mark.asyncio
async def test_summarization_parses_json():
    client = ClaudeClient("dummy")
    client.create_message = AsyncMock(return_value={
        "content": [{
            "type": "text",
            "text": """{
              "summary":"Creator explains a skincare routine.",
              "key_points":["Routine steps","Mentions a product"],
              "signals":[
                {"category":"Brand Mentions","safety_score":80,"explanation":"Explicit product mention.","recommendation":"Add disclosure if sponsored."},
                {"category":"Disclosure Compliance","safety_score":60,"explanation":"No #ad or sponsorship disclosure.","recommendation":"Add #ad/#sponsored."},
                {"category":"Misinformation","safety_score":90,"explanation":"No strong false claims.","recommendation":null},
                {"category":"Political Content","safety_score":95,"explanation":"No political content.","recommendation":null}
              ]
            }"""
        }]
    })

    svc = SummarizationService(client=client)
    res = await svc.summarize("p1", caption="test", transcript_text="test")

    assert res.post_id == "p1"
    assert res.summary
    assert any(s.category == "Disclosure Compliance" for s in res.signals)