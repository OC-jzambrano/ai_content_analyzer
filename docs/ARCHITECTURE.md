# AI Content Analyzer — Architecture Document (Completed)

AI-powered service that analyzes social media campaign content (video + metadata) and returns structured moderation + risk intelligence outputs with quality/safety scores and category breakdowns.

---

## 1. Scoring System Explained

### Outputs Produced

At minimum:

* **Per-post results**
  * Visual moderation categories + scores
  * Text moderation categories + scores (caption + transcript)
  * Risk flags
  * Narrative summary
  * Post-level overall score and status

* **Campaign report**
  * Aggregated overall visual + text scores
  * Category breakdown averages
  * Status label (Safe / Review / Unsafe)
  * Summary narrative (optional)

### Score Normalization

Providers return different formats; internal scoring should normalize to a common scale:

* Use a 0–100 scale where **100 = safest / best**
* If a provider returns "probability of violation", invert:
  * `safety_score = 100 * (1 - violation_prob)`
* If a provider returns "confidence of safe", use directly:
  * `safety_score = 100 * safe_confidence`

### Post-Level Score Calculation (Suggested)

For each post:

* `visual_score` = aggregate of frame-level category scores
* `text_score` = moderation score over (caption + transcript)

Then:

* `post_overall = wv * visual_score + wt * text_score`

Default weights (tunable):

* `wv = 0.5`
* `wt = 0.5`

If there's no audio/transcript:

* redistribute weight to available signals (e.g., all visual + caption text)

### Category Status Thresholds (Example)

Define thresholds:

* `Safe`: score >= 85
* `Review`: 60–84
* `Unsafe`: < 60

These thresholds should be configurable (env or config file) because different brands/campaigns will want different strictness.

### Campaign-Level Aggregation (Suggested)

For campaign:

* `overall_visual` = average (or weighted average) of post visual scores
* `overall_text` = average of post text scores
* `overall_campaign` = weighted average of overall_visual + overall_text

Also compute:

* category-level averages (e.g., Adult Content, Violence, Hate, Drugs)
* top risk posts list (lowest scores)
* counts by status (Safe/Review/Unsafe)

### Why this structure works

* Easy to explain to non-technical stakeholders
* Tunable per client
* Stable against outliers (optionally use median or trimmed mean)

---

## 2. Deployment & CI/CD

### Docker Compose (local + simple prod)

Services:

* `api`
* `worker`
* `redis`

Optional:

* `redis-commander`
* `prometheus`
* `grafana`

### CI (Recommended baseline)

Pipeline stages:

1. Lint: `black --check`, `flake8`, `mypy`
2. Test: `pytest` + coverage gate
3. Build: Docker image build
4. Security: dependency audit (pip-audit) + image scan (Trivy)
5. Push: registry
6. Deploy: environment-based

### Releases

* Tag images with git SHA + semver
* Promote artifacts between dev → staging → prod

---

## 4. Answers to the Questions

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

## 3. Future Improvements (Updated)

* PostgreSQL persistence for historical reports + billing
* Multi-tenant support (client/org separation, per-tenant thresholds)
* Policy engine (brand rules: forbidden topics, stricter categories)
* Batch endpoints + webhooks (push results instead of polling)
* Model/provider fallback routing (resilience during outages)
* UI dashboard for campaign review and audit trail
* Engagement prediction (separate service) once moderation is stable

---

## License

Internal project. All rights reserved.
