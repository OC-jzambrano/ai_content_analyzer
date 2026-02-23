from __future__ import annotations

import asyncio
import time
import aiohttp

from pathlib import Path
from typing import Optional
from aiohttp import ClientError
from app.utils.retry import run_with_retry, RetryError
from app.core.metrics import AI_LATENCY, AI_FAILURES
from src.app.core.config import settings
from src.app.schemas.transcript import TranscriptionResult, TranscriptSegment


class TranscriptionError(RuntimeError):
    pass


class AssemblyAIClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base = "https://api.assemblyai.com/v2"
        self._headers = {
            "authorization": self._api_key,
            "content-type": "application/json",
        }

    async def upload(self, audio_path: str) -> str:
        # AssemblyAI upload uses raw bytes stream
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout, headers={"authorization": self._api_key}) as session:
            with open(audio_path, "rb") as f:
                async with session.post(f"{self._base}/upload", data=f) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        raise TranscriptionError(f"AssemblyAI upload failed ({resp.status}): {text[:500]}")
                    data = await resp.json()
                    return data["upload_url"]

    async def create_transcript(self, upload_url: str) -> str:
        payload = {
            "audio_url": upload_url,
            "punctuate": True,
            "format_text": True,
        }
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout, headers=self._headers) as session:
            async with session.post(f"{self._base}/transcript", json=payload) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise TranscriptionError(f"AssemblyAI create failed ({resp.status}): {text[:500]}")
                data = await resp.json()
                return data["id"]

    async def get_transcript(self, transcript_id: str) -> dict:
        timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout, headers=self._headers) as session:
            async with session.get(f"{self._base}/transcript/{transcript_id}") as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise TranscriptionError(f"AssemblyAI get failed ({resp.status}): {text[:500]}")
                return await resp.json()


class TranscriptionService:
    """
    Responsibility:
    - Turn an audio file into a transcript using AssemblyAI.
    - Includes provider polling (still same stage).
    - Returns TranscriptionResult.
    - Tracks latency and failures via Prometheus metrics.
    """

    def __init__(self, client: Optional[AssemblyAIClient] = None) -> None:
        self._client = client or AssemblyAIClient(settings.ASSEMBLYAI_API_KEY)

    async def transcribe(self, post_id: str, audio_path: str) -> TranscriptionResult:
        ap = Path(audio_path)
        if not ap.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        # Basic retry loop for transient failures
        last_err: Optional[Exception] = None
        for attempt in range(1, settings.RETRY_ATTEMPTS + 1):
            try:
                # ---- UPLOAD STAGE ----
                start = time.perf_counter()
                try:
                    upload_url = await run_with_retry(
                        self._client.upload,
                        str(ap),
                        max_attempts=settings.RETRY_ATTEMPTS,
                        timeout=settings.REQUEST_TIMEOUT,
                        retryable_exceptions=(ClientError, asyncio.TimeoutError),
                    )
                    duration = time.perf_counter() - start
                    AI_LATENCY.labels(provider="assemblyai", operation="upload").observe(duration)
                except Exception as e:
                    AI_FAILURES.labels(provider="assemblyai", operation="upload").inc()
                    raise

                # ---- CREATE TRANSCRIPT STAGE ----
                start = time.perf_counter()
                try:
                    provider_job_id = await run_with_retry(
                        self._client.create_transcript,
                        upload_url,
                        max_attempts=settings.RETRY_ATTEMPTS,
                        timeout=settings.REQUEST_TIMEOUT,
                        retryable_exceptions=(ClientError, asyncio.TimeoutError),
                    )
                    duration = time.perf_counter() - start
                    AI_LATENCY.labels(provider="assemblyai", operation="create_transcript").observe(duration)
                except Exception as e:
                    AI_FAILURES.labels(provider="assemblyai", operation="create_transcript").inc()
                    raise

                # Poll until completed/failed
                poll_attempt = 0
                for poll_attempt in range(settings.TRANSCRIPTION_MAX_POLLS):
                    # ---- GET TRANSCRIPT STAGE (polling) ----
                    start = time.perf_counter()
                    try:
                        data = await run_with_retry(
                            self._client.get_transcript,
                            provider_job_id,
                            max_attempts=settings.RETRY_ATTEMPTS,
                            timeout=settings.REQUEST_TIMEOUT,
                            retryable_exceptions=(ClientError, asyncio.TimeoutError),
                        )
                        duration = time.perf_counter() - start
                        AI_LATENCY.labels(provider="assemblyai", operation="get_transcript").observe(duration)
                    except Exception as e:
                        AI_FAILURES.labels(provider="assemblyai", operation="get_transcript").inc()
                        raise

                    status = data.get("status")

                    if status == "completed":
                        text = data.get("text") or ""
                        words = data.get("words") or []

                        segments = []
                        # Build coarse segments from words (optional)
                        # If provider returns utterances/segments in your plan, map those here instead.
                        for w in words:
                            if "start" in w and "end" in w and "text" in w:
                                segments.append(
                                    TranscriptSegment(
                                        start_ms=int(w["start"]),
                                        end_ms=int(w["end"]),
                                        text=str(w["text"]),
                                    )
                                )

                        return TranscriptionResult(
                            post_id=post_id,
                            transcript_text=text,
                            segments=segments,
                            provider="assemblyai",
                            provider_job_id=provider_job_id,
                            confidence=data.get("confidence"),
                        )

                    if status == "error":
                        AI_FAILURES.labels(provider="assemblyai", operation="transcription_failed").inc()
                        raise TranscriptionError(f"AssemblyAI transcription error: {data.get('error')}")

                    await asyncio.sleep(settings.TRANSCRIPTION_POLL_SECONDS)

                raise TranscriptionError("AssemblyAI transcription timed out (max polls reached)")

            except Exception as e:
                last_err = e
                if attempt < settings.RETRY_ATTEMPTS:
                    # small backoff
                    await asyncio.sleep(min(2 ** attempt, 10))
                    continue
                raise

        # should never hit
        raise TranscriptionError(str(last_err) if last_err else "Unknown transcription error")