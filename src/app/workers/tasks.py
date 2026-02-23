from __future__ import annotations

from typing import Any, Dict, List

from src.app.api.v1.jobs import JobStatusResponse
from src.app.schemas.moderation import TextModerationResult, VisualModerationResult
from src.app.schemas.summarization import SummarizationResult
from src.app.services.aggregation_service import AggregationService
from src.app.services.ingestion_service import IngestionService
from src.app.services.media_service import MediaService
from src.app.services.moderation_service import ModerationService
from src.app.services.report_store import ReportStore
from src.app.services.transcription_service import TranscriptionService
from src.app.services.summarization_service import SummarizationService
from src.app.services.job_store import JobStore


async def _set_stage(job_store: JobStore, job_id: str, campaign_id: str, status: str, stage: str, error: str | None = None):
    await job_store.set(
        JobStatusResponse(
            job_id=job_id,
            campaign_id=campaign_id,
            status=status,   # queued | processing | completed | failed
            stage=stage,
            error=error,
        )
    )


async def process_campaign(ctx, job_id: str, campaign_id: str, campaign_payload: Dict[str, Any]) -> dict:
    """
    ctx dependencies are injected by the worker bootstrap.
    campaign_payload is the validated campaign input from the route (posts list, etc.).
    """

    job_store: JobStore = ctx["job_store"]
    report_store: ReportStore = ctx["report_store"]

    ingestion_svc: IngestionService = ctx["ingestion_service"]
    media_svc: MediaService = ctx["media_service"]
    transcription_svc: TranscriptionService = ctx["transcription_service"]
    moderation_svc: ModerationService = ctx["moderation_service"]
    summarization_svc: SummarizationService = ctx["summarization_service"]
    aggregation_svc: AggregationService = ctx["aggregation_service"]

    await _set_stage(job_store, job_id, campaign_id, status="processing", stage="ingestion")

    try:
        posts_payload = campaign_payload.get("posts") or []
        ingestion = await ingestion_svc.ingest(campaign_id=campaign_id, posts_payload=posts_payload)

        if not ingestion.posts:
            raise RuntimeError("No posts found in campaign payload")

        visual_results: List[VisualModerationResult] = []
        text_results: List[TextModerationResult] = []
        summaries: List[SummarizationResult] = []
        post_results = []

        # Process posts sequentially first (simple + safe). Optimize later with concurrency.
        for idx, post in enumerate(ingestion.posts, start=1):
            post_id = post.post_id
            caption = post.caption or ""
            media_url = post.media_urls[0] if post.media_urls else None

            await _set_stage(
                job_store,
                job_id,
                campaign_id,
                status="processing",
                stage=f"post:{idx}/{len(ingestion.posts)}:media",
            )

            # Per-post try/except to allow partial completion
            try:
                await _set_stage(
                    job_store,
                    job_id,
                    campaign_id,
                    "processing",
                    f"post:{idx}/{len(ingestion.posts)}:media",
                )

                media = await media_svc.prepare_post_media(
                    post_id=post_id,
                    media_url=str(media_url) if media_url else None,
                    extract_audio_enabled=True,
                    sample_frames_enabled=True,
                )

                await _set_stage(job_store, job_id, campaign_id, "processing", "moderation")

                vres = await moderation_svc.moderate_visual(
                    post_id=post_id,
                    frame_paths=[f.path for f in media.frames],
                )
                visual_results.append(vres)

                transcript_text = ""
                if media.audio_path:
                    await _set_stage(job_store, job_id, campaign_id, "processing", "transcription")
                    t = await transcription_svc.transcribe(post_id=post_id, audio_path=media.audio_path)
                    transcript_text = t.transcript_text

                await _set_stage(job_store, job_id, campaign_id, "processing", "text_moderation")

                tres = await moderation_svc.moderate_text(
                    post_id=post_id,
                    text=(caption + "\n" + transcript_text).strip(),
                    lang="en",
                )
                text_results.append(tres)

                await _set_stage(job_store, job_id, campaign_id, "processing", "summarization")

                sres = await summarization_svc.summarize(
                    post_id=post_id,
                    caption=caption,
                    transcript_text=transcript_text,
                    visual_findings={
                        "visual_categories": [
                            {"category": c.category, "score": c.safety_score, "status": c.status}
                            for c in vres.categories
                        ]
                    },
                )
                summaries.append(sres)

                post_results.append(
                    {
                        "post_id": post_id,
                        "success": True,
                        "error_stage": None,
                        "error_message": None,
                    }
                )

            except Exception as e:
                post_results.append(
                    {
                        "post_id": post_id,
                        "success": False,
                        "error_stage": "post_pipeline",
                        "error_message": str(e),
                    }
                )
                continue

        await _set_stage(job_store, job_id, campaign_id, "processing", "aggregation")

        report = aggregation_svc.aggregate(
        campaign_id=campaign_id,
        visual_results=visual_results,
        text_results=text_results,
        summaries=summaries,
        post_results=post_results,
    )

        await report_store.set(report)

        await _set_stage(job_store, job_id, campaign_id, status="completed", stage="done")
        return {"ok": True, "job_id": job_id, "campaign_id": campaign_id}

    except Exception as e:
        await _set_stage(job_store, job_id, campaign_id, status="failed", stage="error", error=str(e))
        raise