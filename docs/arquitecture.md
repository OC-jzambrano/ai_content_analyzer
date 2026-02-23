# AI Content Analyzer

AI-powered service that analyzes social media content (video + metadata) and returns a structured quality score with breakdowns across multiple dimensions.

---

# 1. Architecture

## High-Level Overview

The system is composed of three main components:

* **API Service (FastAPI + Hypercorn)**
* **Worker Service (ARQ + Redis)**
* **Redis (Task queue + result backend)**

```
Client → API → Redis Queue → Worker → Redis → API → Client
```

## Components

### API

* Receives analysis requests
* Validates payload
* Pushes async job to Redis
* Returns Job ID
* Allows polling for results

### Worker

* Consumes jobs from Redis
* Downloads/processes media
* Extracts frames + audio
* Runs scoring logic
* Stores result in Redis

### Redis

* Queue broker
* Result store
* Lightweight + fast

---

# 2. Data Flow

### Step 1 — Client Sends Request

Client calls:

```
POST /analyze
```

with content metadata and media URL.

---

### Step 2 — API Queues Job

API:

* Validates input
* Pushes job to Redis
* Returns:

```json
{
  "job_id": "b7a9c0e2-8d34-4b1a-9a2f-91aa12f9b123",
  "status": "queued"
}
```

---

### Step 3 — Worker Processes

Worker:

1. Downloads video
2. Extracts audio (ffmpeg)
3. Samples frames
4. Applies scoring logic
5. Saves structured result

---

### Step 4 — Client Fetches Result

```
GET /result/{job_id}
```

Returns final analysis when complete.

---

# 3. API Examples

## Submit Content

### Request

```
POST /analyze
Content-Type: application/json
```

```json
{
  "video_url": "https://example.com/video.mp4",
  "caption": "This product changed my life",
  "hashtags": ["#fitness", "#motivation"],
  "platform": "instagram"
}
```

### Response

```json
{
  "job_id": "b7a9c0e2-8d34-4b1a-9a2f-91aa12f9b123",
  "status": "queued"
}
```

---

## Get Result

```
GET /result/b7a9c0e2-8d34-4b1a-9a2f-91aa12f9b123
```

---

# 4. JSON Response Example

```json
{
  "job_id": "b7a9c0e2-8d34-4b1a-9a2f-91aa12f9b123",
  "status": "completed",
  "scores": {
    "hook_strength": 82,
    "visual_engagement": 74,
    "audio_quality": 68,
    "caption_quality": 91,
    "trend_alignment": 63
  },
  "overall_score": 79,
  "verdict": "High Potential",
  "recommendations": [
    "Improve lighting consistency",
    "Use stronger call-to-action in first 3 seconds",
    "Increase pacing in middle section"
  ],
  "processing_time_seconds": 6.4
}
```

---

# 5. Error Handling Strategy

## Validation Errors (400)

Invalid payload:

```json
{
  "error": "Invalid video_url",
  "details": "URL must be HTTPS"
}
```

---

## Job Not Found (404)

```json
{
  "error": "Job not found"
}
```

---

## Processing Error (500)

```json
{
  "error": "Processing failed",
  "details": "ffmpeg could not decode media"
}
```

---

## Timeout Handling

* Configurable request timeout
* Worker retries configurable
* Safe failure if media download fails
* Logs contain full stack trace

---

# 6. Scoring System Explained

The scoring engine evaluates content across multiple weighted dimensions.

## Dimensions

| Category          | Weight |
| ----------------- | ------ |
| Hook Strength     | 25%    |
| Visual Engagement | 20%    |
| Audio Quality     | 15%    |
| Caption Quality   | 20%    |
| Trend Alignment   | 20%    |

---

## How Overall Score Is Calculated

```
overall_score = Σ(score_i × weight_i)
```

Example:

```
(82 × 0.25) +
(74 × 0.20) +
(68 × 0.15) +
(91 × 0.20) +
(63 × 0.20)
= 79
```

---

## Verdict Mapping

| Score Range | Verdict            |
| ----------- | ------------------ |
| 85–100      | Viral Potential    |
| 70–84       | High Potential     |
| 50–69       | Needs Optimization |
| <50         | Low Impact         |

---

# 7. Performance Considerations

* Frame sampling limits CPU usage
* Async worker architecture prevents API blocking
* Redis ensures horizontal scalability
* Multiple workers can run in parallel

---

# 8. Future Improvements

* ML-based scoring model
* Engagement prediction model
* Platform-specific tuning
* Batch analysis endpoint
* Dashboard UI

---

# License

Internal project.
