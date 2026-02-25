from __future__ import annotations

import asyncio
import yt_dlp
from aiohttp import ClientError
from pathlib import Path
from typing import Optional
import aiohttp
from app.utils.retry import run_with_retry
from app.utils.ffmpeg import FFmpegError, extract_audio, sample_frames
import logging

logger = logging.getLogger(__name__)

from src.app.core.config import settings
from src.app.schemas.media import MediaResult, SampledFrame
from src.app.utils.files import ensure_dir, new_work_dir, safe_ext_from_url
from src.app.utils.ffmpeg import extract_audio, sample_frames
from typing import Optional, Tuple, Dict


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

    def _is_social_url(self, url: str) -> bool:
        url = str(url).lower()
        return "tiktok.com" in url or "instagram.com" in url

    def _download_social_video(self, url: str, output_path: Path) -> Path:
        ydl_opts = {
            "outtmpl": str(output_path),
            "format": "bestvideo+bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "merge_output_format": "mp4",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not output_path.exists():
            raise RuntimeError("yt-dlp download failed")

        return output_path

    async def _resolve_media_url(self, media_url: str) -> Tuple[str, Dict[str, str]]:
        media_url = str(media_url)
        if self._is_social_url(media_url):
            return await asyncio.to_thread(self._extract_direct_media_url, media_url)
        return media_url, {}

    async def _download(self, url: str, dest_path: Path, headers: Optional[Dict[str, str]] = None) -> Path:
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.read()
                dest_path.write_bytes(data)
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

        if local_video_path:
            video_path = Path(local_video_path)
        elif media_url:
            media_url = str(media_url)
            if self._is_social_url(media_url):
                video_path = work_dir / "video.mp4"
                await run_with_retry(
                    asyncio.to_thread,
                    self._download_social_video,
                    media_url,
                    video_path,
                    max_attempts=2,
                    timeout=settings.REQUEST_TIMEOUT,
                    retryable_exceptions=(Exception,),
                )
            else:
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