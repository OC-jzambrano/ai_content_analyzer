# AI Content Analyzer

FastAPI application with Docker, tests, and CI for automated moderation and risk intelligence platform for influencer marketing campaigns.

**Status**: Production-ready | **License**: Internal

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Usage](#api-usage)
- [Testing](#testing)
- [Monitoring & Metrics](#monitoring--metrics)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

```bash
# Clone repository
git clone <repo>
cd ai-content-analyzer

# Create environment file
cp .env.example .env

# Start all services
docker compose up --build

# API is now available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Environment Variables

Create `.env` file in project root:

```bash
# --- Environment ---
ENVIRONMENT=development  # development | production
DEBUG=True
LOG_LEVEL=DEBUG         # DEBUG | INFO | WARNING | ERROR

# --- Application ---
APP_NAME=ai-content-analyzer
REDIS_URL=redis://redis:6379/0

# --- AI Provider Keys ---
ASSEMBLYAI_API_KEY=your_key_here
SIGHTENGINE_API_USER=your_user
SIGHTENGINE_API_SECRET=your_secret
CLAUDE_API_KEY=your_key_here

# --- Processing Parameters ---
MAX_FRAMES_PER_POST=30          # Max frames to sample per video
FRAME_SAMPLE_FPS=0.2            # Frames per second to sample
TRANSCRIPTION_MAX_POLLS=120     # Max polling attempts
TRANSCRIPTION_POLL_SECONDS=5    # Seconds between polls

# --- Reliability ---
RETRY_ATTEMPTS=3                # Retry failed API calls
REQUEST_TIMEOUT=20              # HTTP request timeout (seconds)

# --- Storage ---
MEDIA_ROOT=/mnt/media           # Path for temporary media files
```

### Configuration Priority

1. Environment variables (`.env` file)
2. `.env.example` (defaults)
3. Hardcoded in `src/app/core/config.py`

---

## 🏗️ Architecture

### System Design

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│   FastAPI (8000)    │  ◄─── Receives requests
│   - /analyze        │       Returns job_id
│   - /result/{id}    │       Polls status
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Redis (6379)       │  ◄─── Task queue
│  - Job queue        │       Result backend
│  - Post-level store │       Campaign reports
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  ARQ Worker(s)      │  ◄─── Processes jobs
│  - Media extraction │       Multi-stage pipeline
│  - Moderation       │       Metrics tracking
│  - Analysis         │
└─────────────────────┘
```

### Data Flow

**Step 1: Client Submits Content**
```
POST /campaigns/{campaign_id}/analyze
{
  "posts": [
    {
      "id": "post_123",
      "caption": "Check this out!",
      "media_url": "https://example.com/video.mp4",
      "language": "en"
    }
  ]
}
```

**Step 2: API Validates & Queues**
- Validates payload
- Creates job record
- Pushes to Redis queue
- Returns `job_id`

**Step 3: Worker Processes**
```
Media Extraction
    ↓
Visual Moderation (SightEngine)
    ↓
Transcription (AssemblyAI)
    ↓
Text Moderation (SightEngine)
    ↓
Summarization (Claude)
    ↓
Aggregation & Report
    ↓
Store in Redis
```

**Step 4: Client Fetches Results**
```
GET /campaigns/{campaign_id}/reports
```

### Component Responsibilities

| Component | Purpose |
|-----------|---------|
| **API** | Request validation, job queuing, result polling |
| **Worker** | Media processing, AI provider calls, metrics |
| **Redis** | Distributed task queue, result caching |
| **PostgreSQL** (future) | Persistent storage for historical reports |

---

## 📦 Installation

### Prerequisites

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **Python** 3.11+ (for local development)
- **FFmpeg** (included in Docker image)

### System Requirements

| Component | Memory | CPU |
|-----------|--------|-----|
| API | 512MB | 1 core |
| Worker | 1GB | 2 cores |
| Redis | 256MB | 1 core |
| **Total** | **~2GB** | **4 cores** |

### Install Locally (Development)

```bash
# Clone repository
git clone <repo>
cd ai-content-analyzer

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install ffmpeg (if not on Docker)
# macOS with Homebrew
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install ffmpeg

# Windows with Chocolatey
choco install ffmpeg
```

---

## ⚙️ Configuration

## 🎯 Running the Application

### Option 1: Docker Compose (Recommended)

```bash
# Start all services
docker compose up --build

# View logs
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f redis

# Stop services
docker compose down

# Remove volumes (clean slate)
docker compose down -v
```

### Option 2: Local Development (Without Docker)

```bash
# Terminal 1: Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: Start API
python -m uvicorn src.app.main:app --reload --port 8000

# Terminal 3: Start Worker
python -m arq src.app.workers.worker.WorkerSettings

# API available at http://localhost:8000
```

### Services Availability

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | Main API |
| Swagger UI | http://localhost:8000/docs | Interactive API docs |
| ReDoc | http://localhost:8000/redoc | API documentation |
| Redis | localhost:6379 | Task queue |
| Redis Commander | http://localhost:8081 | Redis GUI (optional) |

### Verify Setup

```bash
# Check API health
curl http://localhost:8000/health

# Check Swagger docs
open http://localhost:8000/docs
```

---

## 📡 API Usage

### Submit Content for Analysis

```bash
curl -X POST http://localhost:8000/v1/campaigns/campaign_123/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "tiktok",
    "creator_handle": "creator_1",
    "posts": [
      {
        "platform_post_id": "post_1",
        "url": "https://example.com/video.mp4",
        "weight": 1.0
      }
    ]
  }'
```

**Response:**
```json
{
  "job_id": "b7a9c0e2-8d34-4b1a-9a2f-91aa12f9b123",
  "campaign_id": "campaign_123",
  "status": "queued"
}
```

### Poll Job Status

```bash
curl http://localhost:8000/v1/campaigns/campaign_123/jobs/b7a9c0e2-8d34-4b1a-9a2f-91aa12f9b123
```

**Response:**
```json
{
  "job_id": "b7a9c0e2-8d34-4b1a-9a2f-91aa12f9b123",
  "status": "processing",
  "stage": "post:1/5:transcription",
  "processed_posts": 2,
  "total_posts": 5
}
```

### Fetch Campaign Report

```bash
curl http://localhost:8000/v1/campaigns/campaign_123/reports
```

**Response:**
```json
{
  "campaign_id": "campaign_123",
  "overall_visual": {
    "score": 87.5,
    "status": "Safe"
  },
  "overall_text": {
    "score": 92.1,
    "status": "Safe"
  },
  "visual_categories": [
    {
      "category": "Adult Content",
      "average_safety_score": 95.2,
      "status": "Safe"
    }
  ],
  "posts": 5,
  "summary": "Campaign analyzed successfully"
}
```
## Answers to the Questions

### How to reduce latency (practical changes)

1. **Parallelize per-post stages**
   * Process posts concurrently up to a configured limit (worker concurrency).
   * Within a post: run frame extraction and audio extraction in parallel.

2. **Reduce transcription wall time**
   * Use shorter polling interval only until the job is "started", then back off (adaptive polling).
   * Skip transcription for posts where audio is absent or negligible (detect audio track + RMS threshold).

3. **Smarter frame sampling**
   * Replace uniform sampling with "scene-change" or keyframe-based sampling:
     * fewer frames, higher signal.

4. **Batch provider calls**
   * Where supported, submit multiple frames/text blocks in a single request to reduce round trips.

5. **Cache by media hash**
   * If the same media_url appears again, reuse results (content-addressed caching).

6. **Fail fast**
   * If media download/ffmpeg fails, stop early and mark post failed instead of burning time.

### How to control AI-related costs

1. **Gated pipeline**
   * Run cheapest checks first:
     * caption text moderation (cheap) → if hard fail, skip transcription + summarization.

2. **Budget-aware execution**
   * Per-campaign budget:
     * cap frames analyzed
     * cap transcription duration
     * cap summary token length

3. **Adaptive sampling**
   * Short videos: more frames; long videos: fixed max frames.
   * Use keyframes to reduce frames while maintaining coverage.

4. **Dedup + caching**
   * Hash media + caption + language and store results:
     * avoids repeat charges on re-runs.

5. **Provider routing**
   * Use "good enough" model/provider by default; escalate only when:
     * score is borderline
     * brand requires higher confidence

6. **Summarization control**
   * Make summaries optional or "only on Review/Unsafe".
   * Keep prompts small and enforce max output tokens.

### What to improve next (highest ROI)

1. **PostgreSQL persistence + analytics**
   * Historical reporting, audits, client dashboards, cost tracking, trend detection.

2. **SSRF hardening + auth**
   * This is critical for production if media_url is user-controlled.

3. **Queue health + autoscaling**
   * Export queue depth, autoscale workers based on backlog and provider latency.

4. **Better scoring transparency**
   * Add "why" fields per category:
     * top offending timestamps/frames
     * excerpted transcript segments (redacted)

5. **Idempotency + dedup**
   * Avoid charging multiple times for same campaign content.

6. **Tracing (OpenTelemetry)**
   * Fast root-cause analysis when latency spikes or a provider degrades.

---

## 🧪 Testing

### Unit Tests with Pytest

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-httpx

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_moderation_service.py -v

# Run with coverage
pytest --cov=src tests/

# Run only fast tests
pytest -m "not slow" -v
```

### Integration Tests with Chromatic (E2E Testing)

Chromatic provides visual regression testing and component testing.

#### Setup Chromatic Testing

```bash
# Install dependencies
pip install chromatic-api

# Run Chromatic tests
chromatic test --project-token your_token
```

#### E2E Testing with Playwright

```bash
# Install Playwright
pip install pytest-playwright

# Run E2E tests
pytest tests/e2e/ --headed  # Shows browser

# Run headless (CI/CD mode)
pytest tests/e2e/ --headless
```

**Example E2E Test:**
```python
# tests/e2e/test_campaign_flow.py
async def test_submit_and_retrieve_campaign(playwright):
    """Test complete campaign submission and result retrieval flow"""
    page = await browser.new_page()
    
    # Submit campaign
    await page.goto("http://localhost:8000/docs")
    await page.click("text=POST /campaigns/{campaign_id}/analyze")
    
    # Verify job created
    assert "job_id" in await page.content()
    
    # Poll results
    job_id = await page.text_content("[data-testid=job_id]")
    await page.goto(f"http://localhost:8000/campaigns/test/jobs/{job_id}")
    
    # Verify report generated
    assert "overall_visual" in await page.content()
```

### Load Testing with Locust

```bash
# Install Locust
pip install locust

# Create locustfile.py
cat > locustfile.py << 'EOF'
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def analyze_campaign(self):
        self.client.post(
            "/campaigns/test/analyze",
            json={"posts": [{"id": "1", "caption": "Test"}]}
        )
    
    @task
    def get_report(self):
        self.client.get("/campaigns/test/reports")
EOF

# Run load test
locust -f locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10
```

### Manual API Testing

```bash
# Test submission
curl -X POST http://localhost:8000/campaigns/test/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "posts": [{
      "id": "post_1",
      "caption": "Test post",
      "media_url": "https://example.com/video.mp4"
    }]
  }' | jq .

# Extract job_id and poll
JOB_ID="<job_id_from_response>"
curl http://localhost:8000/campaigns/test/jobs/$JOB_ID | jq .

# Get final report
curl http://localhost:8000/campaigns/test/reports | jq .
```

---

## 📊 Monitoring & Metrics

### Prometheus Metrics

Metrics are exposed at `/metrics`:

```bash
curl http://localhost:8000/metrics
```

**Key Metrics:**
- `job_processing_time_seconds` - Campaign processing duration
- `ai_latency_seconds` - AI provider response times
- `ai_failures_total` - Failed API calls
- `stage_duration_seconds` - Per-stage timing

### Grafana Dashboard (Optional)

```bash
# Add Prometheus data source
# http://prometheus:9090

# Import dashboard JSON from docs/grafana-dashboard.json
```

### Log Aggregation

```bash
# View application logs
docker compose logs -f api

# View worker logs
docker compose logs -f worker

# Search logs
docker compose logs api | grep "ERROR"
```

---

## 👨‍💻 Development

### Project Structure

```
ai-content-analyzer/
├── src/app/
│   ├── main.py              # FastAPI app entry
│   ├── core/
│   │   ├── config.py        # Environment config
│   │   ├── metrics.py       # Prometheus metrics
│   │   └── storage.py       # Redis stores
│   ├── services/
│   │   ├── moderation_service.py
│   │   ├── transcription_service.py
│   │   ├── summarization_service.py
│   │   └── aggregation_service.py
│   ├── workers/
│   │   ├── worker.py        # ARQ worker config
│   │   └── tasks.py         # Job processing
│   ├── schemas/
│   │   └── *.py             # Pydantic models
│   └── utils/
│       ├── retry.py         # Retry logic
│       ├── scoring.py       # Centralized scoring
│       └── stage_logger.py  # Performance logging
├── tests/                   # Unit & integration tests
├── docs/
│   ├── architecture.md      # System design
│   └── api.md              # API reference
├── docker-compose.yml       # Service orchestration
├── Dockerfile              # Container image
└── README.md               # This file
```

### Running Tests Locally

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest --cov=src --cov-report=html

# Open coverage report
open htmlcov/index.html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/

# All checks
black . && flake8 . && mypy src/ && pytest
```

---

## 🔧 Troubleshooting

### Issue: "Connection refused" to Redis

```bash
# Check Redis is running
docker ps | grep redis

# Restart Redis
docker compose restart redis

# Check Redis connection
redis-cli -h localhost -p 6379 ping
```

### Issue: Media files not found

```bash
# Check media volume is mounted
docker volume ls | grep media

# Verify permissions
ls -la /mnt/media

# Create if missing
mkdir -p /mnt/media && chmod 777 /mnt/media
```

### Issue: Worker not processing jobs

```bash
# Check worker logs
docker compose logs worker -f

# Verify connection to Redis
docker exec ai-content-analyzer-worker redis-cli -h redis ping

# Restart worker
docker compose restart worker
```

### Issue: API returns 503

```bash
# Check all services running
docker compose ps

# Check API logs
docker compose logs api -f

# Restart stack
docker compose restart
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export DEBUG=True

# Attach debugger
python -m pdb -c continue src/app/main.py
```
