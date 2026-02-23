from __future__ import annotations

import asyncio
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


async def run_ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise FFmpegError((err or out).decode(errors="ignore")[:2000])


async def extract_audio(video_path: str, audio_path: str) -> None:
    # -vn: no video; 16k mono wav is common for ASR
    await run_ffmpeg([
        "-y",
        "-i", video_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        audio_path,
    ])


async def sample_frames(video_path: str, out_dir: str, fps: float, max_frames: int) -> list[Path]:
    # Output files: frame_0001.jpg ...
    pattern = str(Path(out_dir) / "frame_%04d.jpg")

    # ffmpeg option: -vf fps=<fps> and -vframes <max_frames>
    await run_ffmpeg([
        "-y",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-vframes", str(max_frames),
        pattern,
    ])

    return sorted(Path(out_dir).glob("frame_*.jpg"))