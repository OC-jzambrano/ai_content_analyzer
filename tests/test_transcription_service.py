import pytest
from unittest.mock import AsyncMock

from src.app.services.transcription_service import TranscriptionService, AssemblyAIClient


@pytest.mark.asyncio
async def test_transcription_service_maps_result(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"x")

    client = AssemblyAIClient("dummy")
    client.upload = AsyncMock(return_value="upload_url")
    client.create_transcript = AsyncMock(return_value="tid123")
    client.get_transcript = AsyncMock(return_value={"status": "completed", "text": "hello", "words": []})

    svc = TranscriptionService(client=client)
    res = await svc.transcribe(post_id="p1", audio_path=str(audio))

    assert res.post_id == "p1"
    assert res.transcript_text == "hello"
    assert res.provider_job_id == "tid123"