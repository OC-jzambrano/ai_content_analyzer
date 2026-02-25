import pytest
from unittest.mock import AsyncMock

from src.app.services.media_service import MediaService


@pytest.mark.asyncio
async def test_prepare_post_media_returns_paths(monkeypatch, tmp_path):
    svc = MediaService(media_root=str(tmp_path))

    # Mock download + ffmpeg helpers
    monkeypatch.setattr(svc, "_download", AsyncMock(side_effect=lambda url, dest: dest))
    monkeypatch.setattr("src.app.services.media_service.extract_audio", AsyncMock())
    monkeypatch.setattr(
        "src.app.services.media_service.sample_frames",
        AsyncMock(return_value=[tmp_path / "f1.jpg", tmp_path / "f2.jpg"]),
    )

    # also mock existence check by creating a local file path
    video_file = tmp_path / "video.mp4"
    video_file.write_bytes(b"x")

    res = await svc.prepare_post_media(
        post_id="p1",
        local_video_path=str(video_file),
        extract_audio_enabled=True,
        sample_frames_enabled=True,
    )

    assert res.post_id == "p1"
    assert res.video_path is not None
    assert len(res.frames) == 2


@pytest.mark.asyncio
async def test_prepare_post_media_social_url_resolves_and_downloads(monkeypatch, tmp_path):
    svc = MediaService(media_root=str(tmp_path))

    # Resolve social URL to direct media URL
    monkeypatch.setattr(svc, "_resolve_media_url", AsyncMock(return_value="https://cdn.example.com/v.mp4"))

    async def _fake_download(url, dest):
        dest.write_bytes(b"x")
        return dest

    monkeypatch.setattr(svc, "_download", AsyncMock(side_effect=_fake_download))
    monkeypatch.setattr("src.app.services.media_service.extract_audio", AsyncMock())
    monkeypatch.setattr(
        "src.app.services.media_service.sample_frames",
        AsyncMock(return_value=[tmp_path / "f1.jpg"]),
    )

    res = await svc.prepare_post_media(
        post_id="p2",
        media_url="https://www.tiktok.com/@user/video/123",
        extract_audio_enabled=True,
        sample_frames_enabled=True,
    )

    assert res.post_id == "p2"
    assert res.video_path is not None
    assert len(res.frames) == 1