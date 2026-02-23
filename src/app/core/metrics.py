from prometheus_client import Counter, Histogram

# -----------------------------
# AI Metrics
# -----------------------------

AI_LATENCY = Histogram(
    "ai_request_latency_seconds",
    "Latency of AI external calls",
    ["provider", "operation"],
)

AI_FAILURES = Counter(
    "ai_failures_total",
    "Total number of AI failures",
    ["provider", "operation"],
)

# -----------------------------
# Job Metrics
# -----------------------------

JOB_PROCESSING_TIME = Histogram(
    "job_processing_seconds",
    "Total job processing time",
)

JOB_FAILURES = Counter(
    "job_failures_total",
    "Total job failures",
)