# AI CONTENT ANALYZER
FastAPI aplication with docker, tests and CI for automated moderation and risk intelligence platform for influencer marketing campaigns.

# How to Run Locally

## Requirements

* Docker
* Docker Compose

---

## 1. Clone Repository

```
git clone <repo>
cd ai-content-analyzer
```

---

## 2. Create .env File

```
REDIS_URL=redis://redis:6379/0
MAX_FRAMES_PER_POST=12
FRAME_SAMPLE_FPS=1.0
REQUEST_TIMEOUT=30
MEDIA_ROOT=/mnt/media
```

---

## 3. Start Services

```
docker compose up --build
```

---

## 4. API Available At

```
http://localhost:8000
```

Swagger docs:

```
http://localhost:8000/docs
```

---
