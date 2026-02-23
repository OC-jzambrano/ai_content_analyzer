from __future__ import annotations

from prometheus_client import Counter, Histogram, REGISTRY


def _get_registered_collector(name: str):
    """Return an already-registered collector by metric name, if present.

    prometheus_client registers collectors into a global REGISTRY. In some
    runtime setups (workers, reloaders, multiple imports), the same module can
    be imported more than once in the same process, which would otherwise raise:

        ValueError: Duplicated timeseries in CollectorRegistry

    This helper makes metric creation idempotent by reusing existing collectors.
    """
    # prometheus_client keeps a mapping of metric names to collectors.
    # This is an internal attribute but is the most reliable way to ensure
    # idempotent registration across repeated imports in the same process.
    return getattr(REGISTRY, "_names_to_collectors", {}).get(name)


def get_or_create_histogram(
    name: str,
    documentation: str,
    labelnames: list[str] | tuple[str, ...] | None = None,
    **kwargs,
) -> Histogram:
    existing = _get_registered_collector(name)
    if existing is not None:
        return existing  # type: ignore[return-value]
    return Histogram(name, documentation, labelnames=labelnames or (), **kwargs)


def get_or_create_counter(
    name: str,
    documentation: str,
    labelnames: list[str] | tuple[str, ...] | None = None,
    **kwargs,
) -> Counter:
    existing = _get_registered_collector(name)
    if existing is not None:
        return existing  # type: ignore[return-value]
    return Counter(name, documentation, labelnames=labelnames or (), **kwargs)


# -----------------------------
# AI Metrics
# -----------------------------

AI_LATENCY = get_or_create_histogram(
    "ai_request_latency_seconds",
    "Latency of AI external calls",
    labelnames=["provider", "operation"],
)

AI_FAILURES = get_or_create_counter(
    "ai_failures_total",
    "Total number of AI failures",
    labelnames=["provider", "operation"],
)

# -----------------------------
# Job Metrics
# -----------------------------

if "job_processing_time_seconds" not in REGISTRY._names_to_collectors:
    JOB_PROCESSING_TIME = Histogram(
        "job_processing_time_seconds",
        "Time spent processing a job",
        ["stage"],
    )
else:
    JOB_PROCESSING_TIME = REGISTRY._names_to_collectors["job_processing_time_seconds"]

if "job_failures" not in REGISTRY._names_to_collectors:
    JOB_FAILURES = Counter(
        "job_failures",
        "Number of failed jobs",
        ["error_stage"],
    )
else:
    JOB_FAILURES = REGISTRY._names_to_collectors["job_failures"]