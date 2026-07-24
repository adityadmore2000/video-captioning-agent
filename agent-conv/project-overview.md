# Project Overview

This project is a **Video Captioning Agent** — an AI pipeline that watches a video, understands what happens in it, and generates captions in four distinct writing styles: Formal, Sarcastic, Humorous-Tech, and Humorous-Non-Tech.

It was built for a hackathon with strict rules: everything must finish within 10 minutes, the Docker image must fit under 10 GB, and the output must be valid JSON. The constraint shaped nearly every decision in the project.

The core idea is simple but powerful: **separate video understanding from language generation.** First, a vision-language model watches the video and writes a dry, factual report called the Canonical Video Report (CVR). Then a text model rewrites that report into each style. The text model never sees the video — it can only manipulate the CVR text. This prevents it from hallucinating events, emotions, or objects that weren't actually there.

---

# The Engineering Journey

The project evolved through several distinct phases, each driven by a problem discovered in the previous phase.

## Phase 1: Getting the prototype working

The team started with a clear design on paper: download a video, sample frames from it, feed the frames to a vision model, produce a factual report, rewrite it into four styles. The first implementation got this working end-to-end, but it was purely sequential — each video had to finish completely before the next one started. The vision stage, which is the slowest part, became a bottleneck.

At this stage the project used Fireworks AI as the model provider. The vision model was Qwen2.5-VL 32B and the text model was gpt-oss-120b. A key early discovery was that Fireworks' API didn't support native video upload — it only accepted images. The team settled on frame sampling: extract 16 evenly-spaced frames from each video, encode them as base64 JPEGs, and send those to the vision model instead.

## Phase 2: Making iteration systematic

After the prototype worked, the team needed a way to systematically experiment with different frame counts, prompts, temperatures, and models. They built an experiment tracking harness on top of MLflow. This turned out to be harder than expected — mid-build, MLflow 3.x deprecated its filesystem backend, forcing a migration to SQLite. The team chose the migration path rather than the workaround, reasoning that forward compatibility was worth the effort.

The harness was designed to reuse the production pipeline modules directly rather than reimplementing them — a conscious choice to avoid code duplication between production and experimentation paths.

## Phase 3: The concurrency refactor

The sequential pipeline was slow. Style generation for video N blocked everything — including the VLM work for video N+1. The solution was to split the pipeline into two stages that run concurrently: the main thread processes videos sequentially through the vision stage, but dispatches each video's style generation to a thread pool. This means while video 1's captions are being written, video 2 is already being analyzed by the VLM.

The team chose `ThreadPoolExecutor` over asyncio. The code was synchronous throughout (using `requests` for HTTP), and rewriting the entire I/O layer for asyncio would have been too invasive for the benefit.

## Phase 4: Infrastructure growing pains

As the project matured, it needed to run in Docker and on Streamlit Cloud. This surfaced a series of infrastructure problems: Docker volume mount paths didn't match what the code expected, Fireworks' serverless API didn't support the vision model at all (it needed a dedicated GPU deployment), and the auto-provisioning system that was built to manage deployments kept hitting API quirks — accelerator type names that didn't match the documented format, deployment names that couldn't be reused for 7 days after deletion, and auth mechanisms that worked differently in containers than on the developer's machine.

The team built a full deployment lifecycle manager, then ultimately removed it. The auto-provisioning system was ~500 lines of code handling deployment creation, polling, caching, and teardown. It worked, but it added operational complexity for something that should be "set once and forget." The final design is simpler: model IDs come from environment variables. If they're missing, the system fails fast with a clear error. Users manage their own Fireworks deployments through the dashboard.

## Phase 5: Debugging the silent failures

The project's most interesting engineering work happened during debugging. Two bugs stood out:

**The missing captions bug.** Experiment results showed only 2 of 4 styles appearing in output files. The initial hypothesis was that the model was refusing to generate certain styles (Sarcastic and Humorous-Tech). Investigation proved this wrong. The real cause was that `gpt-oss-20b` is a reasoning model — it emits chain-of-thought tokens internally before producing output text. With `max_tokens=256`, the reasoning consumed the entire budget, leaving no tokens for the actual caption. Raising to 2048 fixed it completely. The lesson: reasoning models have a silent failure mode where they "try" but can't fit the answer.

**The empty results.json bug.** The pipeline was producing `{"captions": {}}` — empty results with no errors. The input JSON had styles like `"humorous_tech"` (underscores, lowercase), but the code matched against `"Humorous-Tech"` (title case, hyphens). Case-sensitive exact matching silently rejected all four styles. The pipeline reported success. The fix was style name normalization.

In both cases, the pipeline's "graceful degradation" design — don't crash, produce well-formed output even on failure — masked the actual problems. This became a recurring theme: graceful degradation is good, but too much silence hides bugs.

---

# Final Architecture (High Level)

The system has a clear separation of concerns across three layers:

## The Core Pipeline

1. **Input loading** reads `/input/tasks.json` — a list of task objects, each with a video URL and requested caption styles.
2. **Video download** fetches the video file from a URL.
3. **Frame sampling** extracts 16 uniformly-spaced frames at 768px resolution using OpenCV. If the video's metadata is corrupted (a surprisingly common problem), it falls back to reading frames sequentially at 1 fps.
4. **CVR generation** sends the frames to Qwen2.5-VL 32B, which produces a Canonical Video Report — a structured JSON document describing the scene, subjects, objects, timeline of events, and an overall factual summary.
5. **Style generation** takes the CVR and the requested styles, sends them to a text model (gpt-oss-120b or similar), and produces one caption per style. This runs on a background thread pool so it doesn't block the next video's VLM work.
6. **Result writing** outputs `/output/results.json` with all generated captions.

## Concurrent Execution Model

```
Video 1: [Download → Sample → CVR] ──► [Style Gen ────────────]
                                        (background thread)
Video 2:                                    [Download → Sample → CVR] ──► [Style Gen]
```

The main thread never waits for style generation to finish before starting the next video's vision work. Failed styles produce empty strings rather than missing keys, and per-task failures are isolated — one broken video doesn't affect the next.

## Deployment Model

The system targets Docker. The container expects `/input` and `/output` as mount points (independent of the internal `/app` workdir). Model IDs come from `FIREWORKS_VISION_MODEL_ID` and `FIREWORKS_STYLE_MODEL_ID` environment variables. No auto-provisioning — deployments are managed externally through the Fireworks dashboard.

A separate Streamlit demo app provides a web UI, and an MLflow-based experiment harness in `experiments/` supports systematic evaluation of prompts, frame counts, and model parameters.

---

# Major Engineering Decisions

## Decision 1: Two-stage architecture (VLM → CVR → Text LLM)

**Problem:** If the language model can see the video, it can hallucinate details during style generation. There's no way to guarantee factual consistency.

**Why this solution:** The CVR acts as a firewall. The text model receives only the CVR's text — it cannot invent visual observations because it literally cannot see the video. Each stage can use a different model optimized for its task: low-temperature for factual VLM output, higher temperature for creative style generation.

**Alternatives considered:** A single model handling both vision and style generation. Rejected because it can't guarantee the text model won't modify facts.

**Trade-off:** Two API calls per video instead of one (higher cost and latency). But the concurrency refactor mitigates the latency by overlapping VLM and style work across videos.

## Decision 2: Frame sampling instead of native video upload

**Problem:** Fireworks' API only accepts image content, not video files. The theoretical ideal of "send the video file and let the model handle it" wasn't available.

**Why this solution:** Extract 16 evenly-spaced frames at 768px, encode as base64 JPEGs. This gives deterministic control over token budget (~33k tokens for 16 frames, well under the 128k context limit) and temporal coverage (1.87s to 7.5s between frames depending on video length).

**Alternatives considered:** Reducing frame count (loses temporal coverage), reducing resolution (loses spatial detail), or switching providers (disruptive). The frame count was investigated analytically and validated experimentally — 16 frames was the sweet spot for 30-120s videos.

**Trade-off:** Frame sampling misses what happens between frames. A 7.5s gap in a 120s video could miss a quick action. The team mitigated this by making frame count configurable so operators could increase to 24 frames for longer videos.

## Decision 3: ThreadPoolExecutor over asyncio for concurrency

**Problem:** The sequential pipeline was slow. Style generation for video N blocked VLM work for video N+1.

**Why this solution:** The code was synchronous throughout. Rewriting the entire I/O layer for asyncio would touch every module. A thread pool provides fire-and-collect semantics with bounded parallelism (`max_workers=4`) and requires minimal code changes.

**Alternatives considered:** asyncio (too invasive), per-style parallel threads (unbounded concurrency risk).

**Trade-off:** GIL contention is minimal because the work is I/O-bound (HTTP calls to Fireworks). The main limitation is that VLM work remains sequential — only the style stage benefits from concurrency.

## Decision 4: Remove auto-provisioning

**Problem:** The project had built an elaborate deployment lifecycle manager (~500 lines) that created, polled, and tore down Fireworks GPU deployments. But it added operational surface area — accelerator type normalization, 7-day purge queue handling, auth mechanism differences between container and desktop.

**Why this solution:** Most users create a deployment once and reuse it. The model ID doesn't change between runs. Fail-fast (raise `ValueError` if env var is missing) is simpler and more debuggable than a provisioning system that can fail in a dozen different ways.

**Alternatives considered:** Fixing the provisioning system's bugs. Rejected because the bugs weren't the problem — the concept of provisioning-at-runtime was wrong for the steady-state use case.

**Trade-off:** Users must manage deployments through the Fireworks dashboard. Startup becomes one step longer on first run. But operational simplicity, reduced code surface, and clear failure modes outweigh this.

## Decision 5: Model selection — Qwen2.5-VL 32B over InternVL3-8B

**Problem:** The vision model needs enough context window to process 16+ high-resolution frames. InternVL3-8B's 16k context window forces a choice between frame count and resolution — you can have good temporal coverage or good spatial detail, not both.

**Why this solution:** Qwen2.5-VL 32B has a 128k context window. 16 frames at 768px consume ~33k tokens — only 26% of the budget, leaving ~94k tokens of headroom. This removed the context window as a binding constraint entirely.

**Alternatives considered:** InternVL3-8B with fewer frames or lower resolution (both degrade video understanding quality). InternVL3-8B is open-source and self-hostable, which is a legitimate advantage, but the 16k context window was an architectural dead end.

**Trade-off:** Cloud API dependency. Self-hosting InternVL3 would provide full operational control and zero API cost. But the hackathon timeline made self-hosting infeasible, and the 128k context gain justified the dependency.

---

# Biggest Challenges

## The reasoning model that ran out of tokens before it could answer

This was the most surprising bug. Experiment results showed gpt-oss-20b producing only 2 of 4 captions — Sarcastic and Humorous-Tech were missing entirely. The working hypothesis was "refusal-adjacent hedging" — the model refusing to generate humor-based styles.

The investigation proved this wrong. The raw API responses showed that all four responses had `finish_reason: "length"` and contained `reasoning_content` (chain-of-thought) but no `content` field at all. The model was doing its reasoning — thinking about how to write the captions — and exhausteding the token budget before it could produce the actual output text.

Raising `max_tokens` from 256 to 2048 fixed all four styles. The model wasn't refusing anything. It was running out of budget mid-thought. The lesson: **reasoning models need 5-10x more tokens than non-reasoning models**, and when they don't get them, they fail silently — no error code, no refusal text, just a missing `content` field.

## The empty results that reported success

The pipeline produced `{"captions": {}}` — valid JSON, exit code 0, no errors logged. The input had `styles: ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]`. The code checked against `("Formal", "Sarcastic", "Humorous-Tech", "Humorous-Non-Tech")`. Zero matches, so the pipeline skipped all video processing and wrote the empty result.

The `filter_supported_styles()` function performed case-sensitive exact matching with no normalization. All four style names were silently ignored. The pipeline's graceful degradation design — "don't crash, produce well-formed output even on failure" — made this invisible.

After fixing the style matching, the team discovered a second bug masked by the first: the `video_url` in the input was a local filesystem path, but the downloader only handled HTTP URLs. Fixing one bug would expose another. This layering of bugs — where one hides the next — became a lesson in investigation methodology.

## Container contract mismatch

The Docker image had `WORKDIR /app`, but the application code hardcoded `/app/input/tasks.json` and `/app/output/results.json`. The README's `docker run` example correctly showed `-v "$(pwd)/input:/input"` — mounting at the root. The container would start, try to read from `/app/input/` (which had nothing mounted there), find no file, and silently produce empty output.

The documentation was ahead of the code. Somewhere in the project's history, the paths were changed from root to `/app/`-prefixed without updating the Docker UX. The fix was two lines — change the constants to `/input/tasks.json` and `/output/results.json` — but the mismatch had persisted through multiple sessions because nobody verified the code against the documentation.

## Fireworks API quirks

The Fireworks API had several undocumented behaviors that caused significant debugging effort:

- **Accelerator type names** used PascalCase enums (`NVIDIA_H200_141GB`) while the scripts used lowercase (`h200-141gb`). The normalization fix required reverse-engineering the enum values from API error messages.
- **7-day purge queue** meant deleted deployment names couldn't be reused for a week. The auto-provisioning system had to handle 409 Conflict responses by falling back to direct GET lookups.
- **Authentication** worked differently in containers. The `firectl` CLI used OIDC tokens from `~/.fireworks/auth.ini` on the developer's machine, but in Docker, only the `--api-key` flag worked. The `~/.firectl.yaml` file the team had been writing to was never read by firectl at all.
- **Shell pipeline footgun**: `firectl ... 2>&1 | sed ...` masked firectl's exit status because without `pipefail`, the pipeline returns the last command's exit code (`sed`, which always succeeds). The error handler never fired even when firectl failed.

---

# Performance & Reliability

## Measured performance

From MLflow experiment tracking data (Session 12):

- **CVR latency scales approximately linearly with frame count**: 3.2s for 1 frame, 7.3s for 8 frames, 11.4s for 16 frames.
- **Style generation latency varies with token budget**: gpt-oss-20b took 33.3s at `max_tokens=256` and 50.0s at `max_tokens=2048` — roughly a 50% increase for an 8x token budget increase, suggesting significant fixed overhead.
- **End-to-end pipeline** was measured at 4-5 minutes for 10 tasks, well under the 10-minute hackathon constraint.

Note: Some of these numbers come from design estimates rather than committed benchmark artifacts. The project's Task 15 (benchmarking) is the least-evidenced area — no reproducible benchmark results are committed to the repository.

## Reliability design choices

- **Style key contract**: All four style keys are always present in output. Failed styles produce empty strings, never missing keys. This prevents downstream consumers from crashing on key lookups.
- **Per-task failure isolation**: If video 3's download fails, videos 1, 2, 4, and 5 are unaffected.
- **Frame sampler fallback**: Videos with corrupted metadata (a real problem — `cv2.VideoCapture` returns 0 frames for some files) fall back to sequential reading at 1 fps instead of crashing.
- **CVR leakage prevention**: A prompt directive tells the style model not to include timestamps in captions. A regex-based warning validator catches leaks if they still happen. The primary defense is the prompt fix; the validator is diagnostic only.
- **CVR parse failure aborts the run** for that video (prerequisite for all style generation), while style generation failures produce partial results. This is asymmetric: an unparseable CVR means nothing downstream can proceed, but a single failed style shouldn't block the other three.

## Known reliability gaps

The EEM documents these gaps explicitly:

- **No retry or backoff logic** exists at the vision or style client layer. A single failed `requests.post` call (120s timeout) results in an empty caption with no retry.
- **No CI/CD pipeline** exists. Tests run locally. There's no coverage gate or lint enforcement.
- **The pipeline depends entirely on a paid external API** (Fireworks). No offline or fallback path exists. If Fireworks is down, the pipeline produces empty results.
- **Hardcoded configuration** throughout. Frame count, resolution, model temperatures, and other pipeline parameters are module-level constants — only overridable through the experiment harness, not through environment variables or config files.

---

# Lessons Learned

These are the insights the team would pass on to someone building a similar system:

1. **Reasoning models eat your token budget silently.** When `max_tokens` is too small for a reasoning model, it exhausts the budget on chain-of-thought before producing output. No error, no refusal, just a missing `content` field. Always budget 5-10x more tokens for reasoning models than you think you need.

2. **Graceful degradation without observability is a bug, not a feature.** The pipeline's pattern of "don't crash, produce well-formed output" was correct in principle, but the absence of logging for silent failures (style mismatches, empty task lists) turned correct behavior into undebuggable behavior. Every "continue without error" path needs a log statement.

3. **Design documents lag reality, and that's sometimes worse than having no design document at all.** The `{metadata_json}` block in the CVR prompt was a legitimate improvement that was never documented in DESIGN.md. The design doc became a source of false confidence — it described a prompt that didn't exist in the actual code. Trust what the code actually does over what the documentation says it does.

4. **Verify user assertions against the code, even when the user is confident.** Twice during development, the user reported problems based on incorrect premises: claiming the asyncio refactor existed (it didn't), and claiming safety clauses were missing from the production prompt (they weren't — they were missing from the experiment config). Investigating rather than complying with the user's framing led to correct fixes both times.

5. **"No-op overrides" are a sharp edge.** The experiment config's system prompt was supposed to be a byte-for-byte copy of the production prompt — a no-op override that demonstrates the config format. Instead, it truncated three safety clauses. Any experiment run with that config used degraded prompts. A config file that defaults to "no change" must actually be identical to the production default.

6. **Docker bind-mount behavior is a persistent footgun.** Mounting a non-existent host file with `-v` creates an empty directory at the mount target instead of the file you expected. This silently broke input loading. Detect this early by verifying that mount targets are actual files before the application logic runs.

7. **Shell pipelines without `pipefail` mask errors.** `command | sed` returns sed's exit status (always 0), not command's. The error handler never fires. Either use `set -o pipefail` or capture output to a file first and check the exit status separately.

8. **Remove subsystems you're not using.** The auto-provisioning deployer was a working 500-line system with tests, but it addressed a transient concern (first-time deployment setup) that was better solved with documentation and environment variables. Removing it reduced the failure surface and made the steady-state path clearer.

---

# Current Project State

Based on the evidence in all 12 session records:

The core pipeline is functional and tested (114 tests passing across production and experiment suites). It reads tasks from `/input/tasks.json`, processes videos through the two-stage CVR-to-style pipeline with concurrent style generation, and writes results to `/output/results.json`.

The Docker container builds and runs. The container contract (`/input` → `/output`) is aligned between code and documentation. Streamlit Cloud deployment was demonstrated to build successfully after an apt dependency fix.

The experiment harness provides systematic evaluation with MLflow tracking (SQLite backend for metrics, filesystem for artifacts). It reuses production modules without duplication and supports config-driven experiments with YAML config files.

The project has been through a simplification pass: auto-provisioning was removed, model IDs are now explicit environment variables, and the `.env` file requires only three variables (API key + two model IDs).

## Gaps identified but not addressed

- **No CI/CD** — tests run locally only. No `.github/` directory exists.
- **No measured test coverage** — pytest exists but no coverage report is configured.
- **No retry/backoff** at the HTTP client layer.
- **Hardcoded pipeline parameters** — config externalization exists in the experiment harness but not in production.
- **Audio is out of scope** — the system is visual-only by design.
- **Fine-tuning capability** — the Charades dataset exists in `Data/` but is only used for manual integration testing. The EEM identifies supervised fine-tuning of the vision model as a planned future workstream.
- **Benchmarking is unverified** — runtime claims (4-5 minutes for 10 tasks, <1 GB image size) come from design estimates, not committed benchmarks.

---

# Reading Guide

If you want more detail, start with these files in the repository:

1. **`EVIDENCE_MAP_SPEC.md`** — The universal specification for engineering evidence maps. Not project-specific, but explains the structure this project's knowledge is organized around.

2. **`DESIGN.md`** — The canonical technical design document. Sections 3 and 4 cover the architecture and prompt design. Section 5 has the token budget analysis. Be aware that some prompts have drifted from what's documented here (the `{metadata_json}` block, for instance, exists in the code but was added after DESIGN.md was written).

3. **`video_captioning_agent_spec.md`** — The original product specification with functional requirements, constraints, edge cases, and acceptance criteria. Useful for understanding the "what" before diving into the "how."

4. **`EXPERIMENT_TRACKING.md`** — Design for the experiment harness. Covers the config format, MLflow integration, and the reuse contract with the production pipeline.

5. **Agent conversation records** (`agent-conv/session-*-engineering-record.md`):
   - **Session 01** — How the project was scaffolded and AGENTS.md was created.
   - **Session 04** — The concurrency refactor and the reasoning-model token budget investigation.
   - **Session 05** — Fireworks deployment infrastructure and the shell pipeline footgun.
   - **Session 08** — Auto-provisioning architecture and accelerator type normalization.
   - **Session 10** — The empty results.json debugging investigation.
   - **Session 11** — The refactor that removed auto-provisioning.
   - **Session 12** — Latency benchmarking and MLflow data archaeology.
