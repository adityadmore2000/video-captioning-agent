# Codebase Architecture Model: Video Captioning Agent

## Project Purpose

The system produces multi-style captions for short-form video clips. It accepts a batch of tasks -- each specifying a video URL and a set of desired caption styles -- and writes per-task captions to a structured JSON output. The core design constraint is factual fidelity: captions must describe only what is visible in the video without hallucination.

---

## High-Level Architecture

The system is organized as a **two-stage pipeline** connected by a single intermediate data structure: the **Canonical Video Report (CVR)**.

### Stage 1: Visual Understanding (Vision Stage)

- **Responsibility**: Download a video, validate it, sample representative frames, and send them to a Vision-Language Model (VLM) to produce a CVR.
- **Input**: A `VideoTask` containing a `video_url` and requested `styles`.
- **Output**: A parsed `CanonicalVideoReport` (five-field JSON) or a silent failure for that task.
- **Dependencies**: HTTP download client, OpenCV, the Fireworks inference API (Qwen2.5-VL 32B Instruct).

### Stage 2: Language Generation (Style Stage)

- **Responsibility**: Rewrite a CVR into 1--2 sentence captions in each of four supported styles (`Formal`, `Sarcastic`, `Humorous-Tech`, `Humorous-Non-Tech`), validate them, and filter output to only the styles the task requested.
- **Input**: A `CanonicalVideoReport` (serialized JSON text only -- no frames, no URLs, no metadata).
- **Output**: A `TaskResult` with a `captions` mapping keyed by style.
- **Dependencies**: The Fireworks inference API (gpt-oss-120b, text-only mode).

These two stages are completely isolated: the style stage never sees the original video or frames. It can only rewrite the CVR text. This is the primary guardrail against hallucination.

### Supporting Subsystems

| Subsystem | Responsibility |
|---|---|
| **Input Loader** | Read and structurally validate `/input/tasks.json`. |
| **Style Validation** | Confirm requested styles are among the four supported styles. |
| **Video Downloader** | Fetch a video over HTTP with a bounded timeout; isolate per-task failures. |
| **Video Inspector** | Check OpenCV readability and collect metadata (fps, frame count, resolution). |
| **Frame Sampler** | Extract uniformly-spaced frames, resize to max 768px, encode as JPEG base64 data URLs. |
| **CVR Client** | Build a multimodal chat-completions request and call the Fireworks VLM. |
| **CVR Parser** | Strictly parse and validate the VLM's JSON response against the CVR contract. |
| **Style Generator** | Issue one text-only call per supported style, always all four. |
| **Caption Validator** | Check captions are non-empty, warn on excessive length or CVR-leaked artifacts. |
| **Result Writer** | Filter captions to task-requested styles and atomically write `/output/results.json`. |
| **Deployment Manager** | Optionally provision a Fireworks VLM deployment at startup. |
| **Environment Loader** | Best-effort `.env` loading at process start. |

---

## System Pipeline

```
/input/tasks.json
    |
    v
[Input Loader] --- structural validation, duplicate ID detection
    |
    v
[Style Filter] --- classify each task as ELIGIBLE or NO_SUPPORTED_STYLES
    |
    v  (per task, sequentially on calling thread)
[Video Downloader] --- HTTP GET with 30s timeout, per-task failure return
    |
    v
[Video Inspector] --- OpenCV readability + metadata extraction
    |
    v
[Frame Sampler] --- 16 uniform frames @ 768px, JPEG base64, 1fps fallback path
    |
    v
[CVR Client] --- multimodal request to Qwen2.5-VL 32B (temperature 0.1)
    |
    v
[CVR Parser] --- strict JSON parsing, exact-field validation
    |
    v  (dispatched as fire-and-collect background Future)
[Style Generator] --- 4 text-only calls to gpt-oss-120b (temperature 0.2)
    |
    v
[Caption Validator] --- non-empty check, ~100-word soft warning, CVR-leakage detection
    |
    v
[Result Writer] --- filter to task-requested styles, atomic write
    |
    v
/output/results.json
```

The pipeline processes tasks **sequentially** for the vision stage but **concurrently** for style generation. After a video's CVR is parsed, style generation for that video is dispatched to a bounded `ThreadPoolExecutor` (4 workers). This allows the next video's download/sample/CVR work to overlap with the previous video's style generation.

---

## Core Domain Concepts

| Concept | Role |
|---|---|
| **VideoTask** | A single unit of work: a task ID, a video URL, and a list of requested caption styles. Immutable, validated on construction. |
| **VideoMetadata** | Inspection data from a downloaded video: duration, fps, frame count, width, height. |
| **FrameSample** | A timestamped, downscaled-to-768px JPEG frame encoded as a base64 data URL. Carries a frame index and a display timestamp for VLM prompt construction. |
| **CanonicalVideoReport (CVR)** | The five-field factual interface between vision and language stages: `scene`, `primary_subjects`, `important_objects`, `timeline`, `overall_summary`. All fields are non-empty strings or string lists. No field may be absent or extra. |
| **TaskResult** | The public output for one task: a `task_id` and a dictionary of `captions` keyed by snake_case style keys (only styles the task actually requested). |
| **Style** | One of four fixed caption styles: `Formal`, `Sarcastic`, `Humorous-Tech`, `Humorous-Non-Tech`. The full set is always generated; output filtering selects only task-requested keys. |
| **Deployment** | A Fireworks-hosted model inference endpoint. Managed automatically via the Fireworks Management API: create, poll-until-ready, reuse on restart, optional teardown. |

---

## Architectural Patterns

### Pipeline (Two-Stage with Intermediate Canonical Form)

The system is organized as a sequential pipeline where each stage's output becomes the next stage's input. The CVR is the **canonical intermediate representation** -- the single source of truth that isolates visual facts from stylistic rewriting.

### Fire-and-Collect Concurrency

Style generation runs as background futures dispatched concurrently while the next task's vision stage proceeds on the calling thread. Results are collected by submission index and matched back to the originating task before final serialization. This is a bounded form of task-level parallelism that does not require restructuring the entire pipeline into an async architecture.

### Failure Isolation (Error-Kernel Pattern)

Every stage returns a result-or-failure discriminated union rather than raising exceptions. A video that fails to download, a corrupt frame, a malformed VLM response, or a failed style call produces an empty-string caption for that task while all other tasks proceed normally. The pipeline always writes a valid `/output/results.json` array equal in length to the input tasks.

### Strategy/Provider Abstraction

The pipeline accepts injectable callables for download, inspection, and sampling. The style generation client is defined by a `Protocol` interface (`StyleCaptionClient`), allowing any text-generation backend to satisfy the contract. Both the CVR client and style client accept keyword overrides for model ID, temperature, max tokens, and prompts -- enabling the experiments harness to swap configurations without reimplementing request construction.

### Idempotent Initialization

Deployment provisioning is idempotent across process restarts: an existing `READY` deployment with the configured name is reused rather than duplicated. The resolved deployment name is cached in-process so subsequent lookups are free.

---

## Major Components

### Production Pipeline (`pipeline.py`)

The orchestrator. Loads tasks, provisions a vision deployment if configured, iterates tasks sequentially for the vision stage, dispatches style generation as futures, collects results, and writes output. All injectable dependencies default to the production implementations but can be overridden for testing.

**Concurrency model**: Vision is sequential on the calling thread. Style is dispatched on a `ThreadPoolExecutor` (4 workers). Results are matched back by submission index.

**Notable choice**: The pipeline always returns exit code 0, even when all tasks fail. Fatal errors only occur during provisioning (infrastructure failure) or input loading (file not found / invalid JSON root type).

### Frame Sampler

Two sampling strategies are implemented:
1. **Uniform sampling** -- when reliable frame-count metadata exists. Computes evenly-spaced frame indices across the timeline, seeks to each via `CAP_PROP_POS_FRAMES`, reads, encodes.
2. **Sequential fallback** -- when frame-count metadata is zero or corrupt. Reads the video linearly, collecting one frame per second (or every frame if fps is unknown), then applies the same uniform-index selection to the collected candidates.

Both paths output a list of `FrameSample` objects with base64 JPEG data URLs (quality 85). Neither path duplicates frames to pad to `target_frames`.

### CVR Client

Builds a multimodal OpenAI-compatible chat request: a system prompt, a user prompt with video metadata and timestamp annotations, and each frame as a separate `image_url` content block preceded by a text label identifying it. Calls the Fireworks `/chat/completions` endpoint. The client is constructed with keyword-overridable model/prompt/parameter defaults so the experiments harness can swap prompts without reimplementing request construction.

### CVR Parser

Accepts only a strict JSON object with exactly five named fields. Rejects duplicate keys and non-standard JSON constants (NaN, Infinity). No field-level defaulting, no field removal -- if the VLM omits a required field or adds an extra one, the response is rejected and the entire task fails the vision stage.

### Style Generator

Issues exactly four text-only calls to `gpt-oss-120b` -- one per supported style -- regardless of which styles a task requested. Each call receives only the serialized CVR JSON and the target style name. The system prompt mandates concise natural prose and explicitly forbids carrying over CVR-internal artifacts (timestamps, frame numbers, structured field labels). Failed styles are recorded as empty strings with a structured failure entry for diagnostics; the full four-key captions dict is always returned.

### Caption Validator

Performs three checks on each of the four generated captions:
- **Missing key** in the captions dict (hard rejection -- empty string).
- **Empty/blank value** (hard rejection -- empty string).
- **Length > ~100 words** (soft warning only -- caption is still accepted).
- **CVR leakage** -- regex match for timestamp labels or numeric-with-seconds patterns (soft warning only -- caption is still accepted).

### Result Writer

The sole place where task-requested styles are applied as a filter. Receives the full four-style validated captions set and selects only the keys matching the task's `styles` field. Output keys are snake_case (`formal`, `sarcastic`, `humorous_tech`, `humorous_non_tech`). Writes atomically via `mkstemp` + `os.replace` + `fsync` to guard against partial writes or power loss.

### Deployment Manager

Optional subsystem for auto-provisioning Fireworks VLM deployments. Resolves the vision model ID with three-tier precedence:
1. `FIREWORKS_VISION_MODEL` env var -- use a pre-existing model directly.
2. `FIREWORKS_VISION_DEPLOYMENT_NAME` + `FIREWORKS_VISION_BASE_MODEL` -- provision/reuse a deployment.
3. Neither -- fall back to the hardcoded serverless model ID.

Supports configurable replica counts, accelerator types, deployment shapes, and autoscaling load targets. Includes a best-effort teardown path for ephemeral deployments.

### Experiments Harness

A dev-only subsystem that reuses production pipeline components (`sample_frames`, `FireworksCvrClient`, `FireworksStyleClient`, `generate_all_captions`) with YAML-driven configuration. Each experiment config can override CVR prompts (inline or from external files), model IDs, temperatures, max tokens, and frame sampling parameters. Runs are tracked in MLflow (SQLite backend + file artifacts). A batch runner (`run_all.py`) iterates over all YAML configs in a directory.

### Streamlit Demo

A minimal web UI that bundles a sample video, provisions a deployment on first run, executes the full two-stage pipeline, and displays all four style captions with color-coded formatting. Accepts configuration from Streamlit secrets first, then environment variables, then hardcoded fallbacks.

---

## External Dependencies

| System | Role | Integration Point |
|---|---|---|
| **Fireworks Inference API** | Hosts both models (Qwen2.5-VL 32B for vision, gpt-oss-120b for text) | OpenAI-compatible `/chat/completions` endpoint; Bearer auth via `FIREWORKS_API_KEY` |
| **Fireworks Management API** | Deploy model instances for the vision stage | REST API (`/accounts`, `/deployments`); Bearer auth; used by `FireworksDeploymentManager` |
| **OpenCV** (`cv2`) | Video file I/O, frame decoding, resize, color conversion | Used by `video_inspection` and `frame_sampler` |
| **Pillow** | JPEG encoding from numpy arrays | Used by `_encode_frame` in the frame sampler |
| **requests** | All HTTP calls (downloads, inference, management API) | Shared `requests.Session` instances in both clients |
| **python-dotenv** | `.env` file loading | Best-effort at process start; missing package is a silent no-op |
| **MLflow** | Experiment tracking (dev-only) | SQLite database + file artifacts under `experiments/mlruns` |
| **Streamlit** | Demo UI (dev-only) | Bundled under `demo/` |
| **Docker** | Containerized production deployment | Python 3.12-slim base; `ENTRYPOINT` runs the pipeline |

---

## Configuration

The system uses a three-tier configuration model:

1. **Environment file** (`.env`): Loaded at startup via `python-dotenv` with `override=False`. The `.env` file fills in anything not already set. Missing `python-dotenv` or a missing file is silently tolerated.

2. **Environment variables** (shell/Docker `-e`): Always take precedence over `.env`. Key variables:
   - `FIREWORKS_API_KEY` (required)
   - `FIREWORKS_VISION_MODEL` (optional -- explicit model ID)
   - `FIREWORKS_VISION_DEPLOYMENT_NAME` + `FIREWORKS_VISION_BASE_MODEL` (optional -- auto-provision)
   - `FIREWORKS_VISION_TEARDOWN` (optional -- if set, deployment is deleted after the run)
   - `DOTENV_PATH` (optional -- alternate `.env` file location)
   - Various `FIREWORKS_VISION_*` provisioning knobs (accelerator type, replica counts, load targets)

3. **Hardcoded module constants**: Final fallbacks for model IDs, temperatures, max tokens, timeouts, frame sampling parameters, supported styles, and output paths. These are public module-level constants that both the production pipeline and experiments harness reference.

Client classes (`FireworksCvrClient`, `FireworksStyleClient`) accept constructor kwargs for all configurable parameters, enabling the experiments harness to override them without mutation or environment variable manipulation.

---

## Current Engineering Decisions Visible in Code

### CVR as Factual Firewall

The most significant architectural decision: the style generator receives **only** the serialized CVR JSON string. It has no access to frames, video URLs, metadata, or task definitions. This is enforced at the `generate_all_captions` level (which calls `report.to_json()` and passes only that string) and at the `build_style_request` level (which embeds the CVR JSON into a user prompt that explicitly labels it as the sole factual source).

### Generation-Always, Filter-Later

All four supported style captions are generated for every video unconditionally. Filtering to task-requested styles happens only at `build_task_result` (result writer). This avoids conditional branching in the style generation code path at the cost of up to three unused caption generations per task.

### Sequential Vision, Concurrent Style

The vision stage processes one video at a time on the calling thread to avoid saturating the VLM deployment with concurrent multimodal requests. Style generation is dispatched on a bounded thread pool to overlap with the next video's CVR work. This is a pragmatic compromise: full task-level parallelism would require managing multiple VLM contexts simultaneously; sequential vision keeps resource usage predictable while concurrent style recovers some wall-clock time.

### Failure Isolation via Discriminated Unions

Every stage that can fail returns a result type with explicit success/failure fields rather than raising exceptions. The pipeline converts any raised exceptions at stage boundaries into empty results for the affected task. This guarantees that a corrupt video, network timeout, or malformed model response cannot abort the batch.

### Atomic Output

`/output/results.json` is written via `mkstemp` + `os.replace` + `os.fsync`, ensuring the file is never observed in a partially-written state even during a crash. The file is created at the final step, not incrementally appended.

### Strict CVR Parsing

The CVR parser rejects any JSON with: missing required fields, unexpected extra fields, duplicate object keys, or non-standard JSON constants (`NaN`, `Infinity`). There is no partial CVR recovery, no field-level defaulting, and no retry. A VLM that fails to produce a contract-compliant response fails the task -- the system does not fabricate facts to fill gaps.

### Config-Swappable Prompts

Both `build_cvr_request` and `build_style_request` accept all prompt/model/parameter values as keyword arguments that default to module constants. The production pipeline calls these functions with only positional arguments, but the experiments harness passes config-driven overrides through the same kwargs interface. This means prompt engineering experiments require no changes to request construction logic.

### Idempotent Deployment Lifecycle

Deployments are created with a caller-chosen name, discovered via a paginated list endpoint, and reused if already `READY`. The deployment lifecycle is scoped to the process lifetime: deployment is created/resolved at pipeline start and optionally torn down in a `finally` block. If teardown fails or the process exits uncleanly, the deployment persists for reuse on the next run.

### Container-Native Input/Output Contract

The production pipeline reads from `/input/tasks.json` and writes to `/output/results.json`. These paths are hardcoded and correspond to Docker mount points. The container entrypoint runs the pipeline module directly with no CLI argument parsing.

---

## Extension Points

### Interchangeable Models

Both the CVR client and style client accept `model_id` at construction time, defaulting to the production models but overridable via environment variable or constructor argument. The experiments harness exercises this to benchmark different models.

### Pluggable Prompt Templates

The CVR system prompt and user prompt template are module constants that can be overridden when constructing `FireworksCvrClient` or calling `build_cvr_request`/`build_style_request`. The experiments harness supports loading prompts from external files, enabling prompt engineering without code changes.

### Injectable Pipeline Stages

`run_pipeline` accepts `downloader`, `inspector`, and `sampler` as callable arguments. Tests inject mock functions; future extensions could inject alternative implementations (e.g., a cloud-storage-backed downloader) without modifying the orchestrator.

### Style Client Protocol

`StyleCaptionClient` is a `Protocol` requiring only `generate_caption(cvr_json, style) -> str`. Any text-generation backend can satisfy this interface. The production implementation uses Fireworks, but a local model or a different provider could be substituted.

### Deployment Shape Configuration

`FireworksDeploymentManager.resolve_vision_model` accepts `deployment_shape`, `accelerator_type`, `accelerator_count`, and `load_target` parameters driven by environment variables, enabling cost/performance tuning without code changes.

### Experiments Config Schema

The YAML-driven experiments system supports configurable frame sampling parameters, prompt text (inline or file-referenced), and model parameters for both the CVR and style stages. New experiments are added by creating a new YAML file; no code changes are required.

---

## Current Limitations

### No Retry Logic

The pipeline makes exactly one attempt per stage per task. A transient HTTP error or a single malformed VLM response fails the task permanently. There is no exponential backoff, no retry budget, and no circuit breaker.

### No Streaming or Incremental Output

Results are written only after all tasks complete. For large batches approaching the 10-minute runtime limit, a crash near the end loses all progress. Intermediate checkpoints are not written.

### No Context-Budget Enforcement

The frame sampler is configured for 16 frames at 768px, which fits within the 128k context window with ~94k tokens of headroom. However, there is no programmatic token counting or context-budget enforcement. If the number of frames or resolution were increased beyond safe limits, the system would silently send requests that the VLM might truncate.

### No Programmatic Factuality Verification

Caption factuality relies entirely on prompt design (CVR-only input isolation) and the CVR parser's strict schema enforcement. There is no post-generation comparison between captions and the CVR, no embedding-based similarity check, and no programmatic verification that captions do not introduce facts absent from the CVR.

### Single-Model Dependency

Both stages depend on Fireworks-hosted models. There is no fallback model provider, no multi-model voting, and no local inference path. If Fireworks is unreachable, the entire pipeline fails.

### No Incremental Frame Sampling

The sampler reads all target frames into memory. For very long videos or very high target frame counts, this could exhaust available memory. There is no support for streaming frame-by-frame encoding to disk or progressive frame submission.

### No Audio Processing

The system is visual-only by design decision. Videos with critical audio context (dialogue, sound cues) will produce captions missing that information.

### Vision-Stage Sequential Bottleneck

Processing one video's CVR at a time limits throughput. For videos with similar duration, the pipeline cannot parallelize the most time-consuming stage. The concurrent style stage partially mitigates this, but the vision stage remains the bottleneck.

### No Per-Task Timeout Aggregation

Each stage has individual timeouts (download 30s, vision 120s, style 120s), but there is no aggregate per-task watchdog. A task could theoretically consume up to several minutes across all stages, though in practice this is bounded by the individual timeouts.

---

## Implementation Summary

The video captioning agent is a two-stage pipeline that processes a batch of video URLs into stylized captions. The vision stage downloads each video, samples uniform frames, and calls Qwen2.5-VL 32B to generate a strictly-structured Canonical Video Report. The language stage rewrites that report into four preset caption styles using gpt-oss-120b, then filters output to only the styles each task requested. The two stages are separated by design: the style model cannot see the original video, only the CVR text.

The pipeline is orchestrated sequentially for the vision stage (one video at a time) but dispatches style generation as concurrent background tasks to overlap with the next video's processing. Every stage implements failure isolation: a problem with one task never aborts the batch, and the system always produces a complete, valid JSON output array. Deployment of the vision model to Fireworks is handled automatically at startup, with idempotent reuse across restarts.

A dev-only experiments harness reuses the same production components with YAML-configurable prompts, models, and parameters, logging results to MLflow. A minimal Streamlit demo provides a one-click interface on a bundled sample video.
