from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp import ClientError
from app.utils.retry import run_with_retry
from app.utils.ffmpeg import FFmpegError, extract_audio, sample_frames

from src.app.core.config import settings
from src.app.schemas.media import MediaResult, SampledFrame
from src.app.utils.files import ensure_dir, new_work_dir, safe_ext_from_url
from src.app.utils.ffmpeg import extract_audio, sample_frames


class MediaService:
    """
    Responsibility:
    - Download media (if URL) to local work dir
    - Extract audio
    - Sample frames
    - Return MediaResult
    """

    def __init__(self, media_root: Optional[str] = None) -> None:
        self._media_root = media_root or settings.MEDIA_ROOT

    async def _download(self, url: str, dest_path: Path) -> Path:
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with dest_path.open("wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 256):
                        f.write(chunk)
        return dest_path

    async def prepare_post_media(
        self,
        post_id: str,
        media_url: Optional[str] = None,
        local_video_path: Optional[str] = None,
        extract_audio_enabled: bool = True,
        sample_frames_enabled: bool = True,
    ) -> MediaResult:
        work_dir = new_work_dir(self._media_root, prefix=f"post_{post_id}")
        frames_dir = ensure_dir(work_dir / "frames")

        video_path: Optional[Path] = None
        audio_path: Optional[Path] = None

        # 1) Resolve video path
        if local_video_path:
            video_path = Path(local_video_path)
        elif media_url:
            ext = safe_ext_from_url(media_url)
            video_path = work_dir / f"video{ext}"
            await run_with_retry(
            self._download,
            media_url,
            video_path,
            max_attempts=settings.RETRY_ATTEMPTS,
            timeout=settings.REQUEST_TIMEOUT,
            retryable_exceptions=(ClientError, asyncio.TimeoutError),
        )

        # If no video, return empty MediaResult (service stays strict: no guessing)
        if not video_path or not video_path.exists():
            return MediaResult(post_id=post_id, video_path=None, audio_path=None, frames=[])

        # 2) Extract audio
        if extract_audio_enabled:
            audio_path = work_dir / "audio.wav"
            await run_with_retry(
            extract_audio,
            str(video_path),
            str(audio_path),
            max_attempts=2,
            timeout=settings.REQUEST_TIMEOUT,
            retryable_exceptions=(FFmpegError,),
        )

        # 3) Sample frames
        frames: list[SampledFrame] = []
        if sample_frames_enabled:
            frame_files = await run_with_retry(
            sample_frames,
            str(video_path),
            str(frames_dir),
            settings.FRAME_SAMPLE_FPS,
            settings.MAX_FRAMES_PER_POST,
            max_attempts=2,
            timeout=settings.REQUEST_TIMEOUT,
            retryable_exceptions=(FFmpegError,),
        )
            # We don't have true timestamps from filenames; approximate:
            # timestamp = index / fps
            fps = max(settings.FRAME_SAMPLE_FPS, 0.0001)
            for i, f in enumerate(frame_files):
                frames.append(
                    SampledFrame(
                        index=i,
                        timestamp_sec=round(i / fps, 3),
                        path=str(f),
                    )
                )

        return MediaResult(
            post_id=post_id,
            video_path=str(video_path),
            audio_path=str(audio_path) if audio_path else None,
            frames=frames,
        )