from __future__ import annotations

from arq.connections import RedisSettings

from src.app.core.config import settings
from src.app.services.ingestion_service import IngestionService
from src.app.services.job_store import JobStore
from src.app.services.media_service import MediaService
from src.app.services.moderation_service import ModerationService
from src.app.services.report_store import ReportStore
from src.app.services.summarization_service import SummarizationService
from src.app.services.transcription_service import TranscriptionService
from src.app.services.post_store import PostResultStore


async def startup(ctx):
    # Lazy import to avoid circular import issues
    from src.app.services.aggregation_service import AggregationService

    ctx["job_store"] = JobStore(settings.REDIS_URL)
    ctx["report_store"] = ReportStore(settings.REDIS_URL)

    ctx["ingestion_service"] = IngestionService()
    ctx["media_service"] = MediaService()
    ctx["transcription_service"] = TranscriptionService()
    ctx["moderation_service"] = ModerationService()
    ctx["summarization_service"] = SummarizationService()
    ctx["aggregation_service"] = AggregationService()
    ctx["post_store"] = PostResultStore(settings.REDIS_URL)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = ["src.app.workers.tasks.process_campaign"]
    on_startup = startup