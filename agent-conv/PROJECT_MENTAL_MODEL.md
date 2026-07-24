# Project Mental Model: Video Captioning Agent

---

## 1. Project Purpose

The Video Captioning Agent is a multimodal AI pipeline that watches short video clips (30–120 seconds) and produces captions in four distinct writing styles: Formal, Sarcastic, Humorous-Tech, and Humorous-Non-Tech. The system was built for a hackathon with strict runtime (≤10 minutes) and container-size (≤10 GB) constraints.

The central problem it solves is **factual fidelity across style transformations**. Rewriting a video description in a sarcastic or humorous tone risks introducing hallucinated details — invented objects, actions, or emotions. The system prevents this by physically isolating the style-generation model from the video frames. The text model that writes styled captions receives only a pre-written factual report, never the visual input. This makes factual hallucination architecturally impossible rather than statistically improbable.

The system is built for a competition evaluation where hidden videos from diverse domains are scored on factual accuracy, style quality, and output validity. The project is a working prototype, not a production service.

---

## 2. Core Constraints

Every major architectural choice in this project was shaped by one of three binding constraints.

### Hackathon Runtime Budget (≤10 minutes)

The pipeline must complete all tasks — download, frame sampling, vision model inference, and style text generation — within 600 seconds. This ruled out exhaustive frame-by-frame analysis, multi-model voting, and any approach requiring more than one vision-model call per video. It also drove the project toward a concurrent execution model: while one video's style captions are being generated, the next video's vision analysis begins on the main thread.

### Fireworks API: Images-Only for Vision Models

The hosting provider's OpenAI-compatible chat completions endpoint accepts images (base64 data URLs) but does not support native video file upload. This forced the pipeline to adopt **uniform frame sampling** as the canonical video ingestion method — extracting N evenly-spaced JPEG frames and sending them as individual image content blocks. This constraint turned frame selection from an implementation detail into the most critical quality lever in the system.

### Factual Fidelity as the Primary Quality Requirement

The spec requires that captions accurately summarize entire videos without introducing hallucinated facts. The architecture enforces this by strictly separating visual understanding (which produces a Canonical Video Report) from language generation (which rewrites the CVR into styled captions). The language model is prohibited from seeing frames, video URLs, or metadata. This constraint is implemented as a **hard architectural boundary**, not a prompt guideline.

Secondary constraints (Docker image ≤10 GB, output must be valid JSON, exit code must be 0 even on task failures) influenced implementation details like image base size, error-handling patterns, and the discriminated-union result model — but did not define the architecture.

---

## 3. Core Concepts

### VideoTask

A unit of work: a task ID, a video URL, and a list of requested caption styles. Immutable and validated on construction. Each task in the input batch produces exactly one result in the output, in input order.

**Why it exists**: The system processes batches, not single videos. Each task carries its own desired output shape. The concept isolates per-video concerns — a bad URL for task 3 must not affect task 4.

### FrameSample

A timestamped, downscaled-to-768px JPEG frame encoded as a base64 data URL. Carries a frame index and a display timestamp used in VLM prompt construction.

**Why it exists**: The Fireworks API cannot accept video files. Frames are the unit of visual information the vision model actually receives. The choice of how many frames to sample and at what resolution directly determines how much of the video's temporal and spatial information reaches the model.

### Frame Selection (as distinct from Frame Extraction)

Frame extraction is a mechanical video processing step (decoding MP4 bytes into pixel arrays). Frame selection is an engineering decision: which of those decoded frames should be sent to the vision model. The project uses uniform sampling — compute evenly-spaced frame indices across the timeline and extract those. A fallback path reads frames sequentially at 1 fps when video metadata is corrupt.

**Why it exists**: Not every frame carries equal information. Sending all 1,800 frames of a 60-second video would be wasteful and would exhaust the VLM's context window. Selecting the right frames is the single most influential quality lever in the vision stage. This concept emerged from the recognition (ELL Session 7) that frame extraction and frame selection are separable problems.

### Canonical Video Report (CVR)

The five-field factual interface between the vision and language stages: `scene`, `primary_subjects`, `important_objects`, `timeline`, and `overall_summary`. The CVR is a strictly-structured JSON document that may contain only observable facts — no speculation, no humor, no inferred emotions, no off-screen events. The CVR parser rejects any JSON with missing or extra fields, duplicate keys, or non-standard JSON constants. There is no partial recovery: a malformed CVR response fails the entire task.

**Why it exists**: The CVR is the structural center of the system's architecture. It is the single source of truth from which all four styled captions are derived. It physically enforces the separation between visual understanding and language generation: the style model cannot see the video and can only rewrite the CVR's text. The CVR also serves as a debugging artifact — if a caption is factually wrong, inspecting the CVR reveals whether the problem originated in visual understanding (bad CVR) or stylistic rewriting (good CVR, bad caption). The CVR is never included in the final output.

### Style

One of four fixed caption writing styles: `Formal`, `Sarcastic`, `Humorous-Tech`, `Humorous-Non-Tech`. This set is exhaustive. The system always generates all four captions for every video regardless of which styles the input task actually requested; filtering to task-requested styles happens only at result serialization.

**Why it exists**: The four styles were specified by the hackathon requirements. The "generate always, filter later" pattern avoids conditional branching in the style generation code path — one code path, four parallel calls, no awareness of the task's requested subset. The trade-off is up to three unused caption generations per task when fewer than four styles are requested. This was accepted because short text generation is cheap relative to vision model inference.

### TaskResult

The public output for one task: a `task_id` and a `captions` dictionary keyed by snake_case style keys (e.g., `"humorous_tech"`, `"sarcastic"`). Only styles the task actually requested appear in the dict. A requested-but-failed caption is represented as an empty string, never as a missing key. This contract guarantees downstream consumers never crash on missing-key lookups.

### Deployment

A Fireworks-hosted model inference endpoint for the vision model (`Qwen2.5-VL 32B Instruct`). The production pipeline resolves the model ID from environment variables; there is no runtime provisioning. The project experimented with an auto-provisioning system but removed it — the incurred operational complexity outweighed the benefit of one-time setup convenience.

---

## 4. System Mental Model

Think of the system as a factory with two departments connected by a single conveyor belt carrying a single document.

**Department One (Vision Stage)** receives video URLs. For each one, it downloads the file, inspects it with OpenCV to verify readability and extract metadata, selects 16 evenly-spaced frames, encodes them as JPEG base64 data URLs, and sends them — along with a system prompt that mandates strict factual reporting — to a vision-language model (`Qwen2.5-VL 32B`). The VLM returns a JSON document called the Canonical Video Report (CVR). Department One either produces a valid CVR or declares the task failed for that video.

**The Conveyor Belt** carries only the CVR — serialized JSON text. No frames, no video URLs, no metadata, no task identifiers cross this boundary.

**Department Two (Style Stage)** receives CVRs from the belt. For each CVR, it issues exactly four text-only API calls — one per supported style — to a language model (`gpt-oss-120b`). Each call receives only the CVR text and the target style name. The model rewrites the factual report into 1–2 sentences matching the requested tone. Failed style calls produce empty strings. Validators check that captions are non-empty, warn if a caption exceeds ~100 words, and warn if CVR-internal artifacts (timestamps, frame numbers) have leaked into human-facing text. The full four-style caption set is then filtered down to only the styles the original task actually requested.

**The Order Desk** serializes all task results atomically to `/output/results.json`, always producing a complete, valid JSON array equal in length to the input tasks.

**Departments operate concurrently, not sequentially.** While Department Two transforms CVR-1 into captions on background threads, Department One has already started downloading and analyzing video-2. The main thread never waits for style generation to finish before moving to the next video's vision work.

**If something breaks**: A video that fails to download, a corrupt frame, a VLM that returns malformed JSON, or a failed style-generation call all produce empty captions for that specific task. All other tasks proceed normally. The system always writes a valid output file and exits with code 0. Only infrastructure failures (missing input file, unreachable Fireworks API on all attempts, unwritable output directory) prevent the pipeline from completing.

---

## 5. Architecture Through Decisions

### Decision 1: Two-Stage Architecture with CVR as Firewall

**The problem**: If the language model can see the video frames during style generation, there is no guarantee it won't hallucinate new visual details when phrasing captions humorously or sarcastically. A prompt-level instruction ("don't make things up") is not a reliable safeguard.

**The chosen approach**: Physically separate visual understanding (Stage 1, VLM) from language generation (Stage 2, text LLM). Connect them through the CVR — a single JSON document that the text model rewrites without ever seeing the source video. This is enforced in code: the style generator receives only `report.to_json()`, a plain string.

**Why this approach**: It makes factual hallucination architecturally impossible rather than statistically improbable. The text model literally cannot invent visual observations because it receives no visual input. Each stage can also use a different model optimized for its task: low-temperature (0.1) for factual VLM output, higher temperature (0.2) for creative style generation.

**Trade-off**: Two API calls per video instead of one (higher cost and latency). Mitigated by the concurrent dispatch model that overlaps VLM work on the next video with style generation on the current one.

### Decision 2: Uniform Frame Sampling (16 frames, 768px)

**The problem**: Fireworks' API only accepts image content, not video files. The system must convert video to a format the VLM can consume.

**The chosen approach**: Extract 16 evenly-spaced frames, downscale the maximum dimension to 768px, encode as JPEG base64 (quality 85), and send as individual image content blocks with timestamp annotations.

**Why this approach**: This was not initially a "decision" — it was discovered as a platform constraint (the API doesn't support native video upload) and adopted as the canonical ingestion method. The specific parameters (16 frames, 768px) were determined by analytical token-budget modeling: 16 frames at 768px consume ~33k tokens in Qwen2.5-VL's 128k context window, leaving ~94k tokens of headroom. This enables increasing to 24 frames for longer videos without risking context truncation.

**Trade-off**: Uniform sampling misses what happens between frames. A ~7.5s inter-frame gap on a 120-second video could skip a quick action. Non-uniform sampling strategies (scene-change detection, motion-aware sampling) were identified in early investigation but the project chose uniform sampling for its simplicity and deterministic behavior. Frame count is configurable via the experiments harness and could be increased if temporal coverage proves insufficient.

**Two sampling strategies** are implemented: uniform (when reliable frame-count metadata exists) and sequential fallback (when metadata is corrupt — reads linearly at 1 fps, then applies uniform-index selection to the collected candidates). Neither path duplicates frames to pad to the target count.

### Decision 3: Sequential Vision, Concurrent Style Execution

**The problem**: The vision stage is the slowest part of the pipeline (~11 seconds per video for the VLM call). Processing everything fully sequentially meant style generation for video N blocked the VLM call for video N+1, wasting wall-clock time.

**The chosen approach**: The main thread processes videos sequentially through the vision stage (download → sample → CVR) but dispatches each video's style generation as a fire-and-collect background `Future` on a bounded `ThreadPoolExecutor` (4 workers). Results are matched back to their originating task by submission index.

**Why this approach**: Thread-based concurrency (`concurrent.futures`) works with the existing synchronous I/O layer (`requests`). Switching to `asyncio` would have required rewriting every HTTP call across the entire pipeline — too invasive for the benefit. The GIL contention is minimal because the work is I/O-bound (HTTP calls to Fireworks). Bounded at 4 workers to prevent unbounded HTTP concurrency.

**Trade-off**: Vision work remains sequential — the system cannot analyze two videos' frames simultaneously. Only the style-generation stage benefits from concurrency. This is the pragmatic compromise: the vision stage is the bottleneck, but full multi-video parallelism would require managing multiple VLM inference contexts simultaneously, which was out of scope.

### Decision 4: Generation-Always, Filter-Later for Styles

**The problem**: Tasks may request any subset of the four supported styles. Generating only the requested subset requires conditional logic in the style generation code path.

**The chosen approach**: Always generate all four captions for every video, unconditionally. Filter to task-requested styles only at result serialization.

**Why this approach**: Simplifies the style generation code path — one code path, no branching per requested style. All four calls share the same CVR input and can be dispatched concurrently. The cost of unused generations (up to 3 per task at ~2 seconds each for text generation) is dwarfed by the vision stage's ~11-second VLM call.

### Decision 5: Failure Isolation via Discriminated Unions

**The problem**: A corrupt video, network timeout, or malformed VLM response for task 3 of 10 should not abort the entire batch. The spec requires the system to always produce valid output JSON and exit code 0.

**The chosen approach**: Every pipeline stage that can fail returns a result type with explicit success/failure fields rather than raising exceptions. The pipeline converts any raised exceptions at stage boundaries into empty results for the affected task. Failed tasks produce empty-string captions in the output; successful tasks are unaffected.

**Why this approach**: This is the Error-Kernel pattern — isolate failure to the smallest unit of work (a single task) and prevent it from propagating. Combined with atomic output writing (mkstemp + os.replace + fsync), this guarantees that any batch produces a complete, valid JSON output regardless of how many individual tasks fail.

**A known tension**: Graceful degradation without observability masked two significant bugs during development — silent style-name mismatches and empty result sets that reported success. Every "continue without error" path needs a log statement for debuggability.

### Decision 6: Strict CVR Parsing, No Recovery

**The problem**: The VLM may return malformed JSON, prose-wrapped JSON, missing fields, extra fields, or nonstandard JSON constants.

**The chosen approach**: The CVR parser rejects any JSON with missing required fields, unexpected extra fields, duplicate object keys, or non-standard JSON constants (`NaN`, `Infinity`). There is no partial recovery — a VLM that fails to produce a contract-compliant response fails the entire task.

**Why this approach**: Partial CVR recovery would require the system to fabricate facts to fill missing fields, which contradicts the core requirement of factual fidelity. A rejected CVR is worse than no CVR — silent factual gaps are harder to detect and debug than explicit task failures. The system does not retry; it makes exactly one attempt per stage per task.

### Decision 7: Separate Models for Vision and Language

**The problem**: The vision model needs multimodal input (images + text) and high context capacity. The language model needs only text input and should be optimized for creative rewriting.

**The chosen approach**: `Qwen2.5-VL 32B Instruct` for the vision stage (multimodal, 128k context window for 16+ frames). `gpt-oss-120b` for the style stage (text-only, separate from the vision model).

**Why this approach**: The 128k context window was the decisive factor in model selection. The alternative, `InternVL3-8B`, had a 16k context window that would have forced a choice between frame count and resolution — the project would have had to sacrifice either temporal coverage or spatial detail. Qwen2.5-VL's 8x larger context window eliminated this trade-off entirely. Using a different text model for style generation was a later decision: the early plan to reuse the vision model in text-only mode was abandoned in favor of a model better suited for creative text generation.

**Trade-off**: Cloud API dependency on Fireworks for both models. No self-hosting fallback. No multi-model voting or ensemble.

---

## 6. Quality Levers

These are the parts of the system where engineering choices have the greatest influence on output quality. They are listed in order of impact.

### Frame Count and Resolution

The number of frames and their resolution determine how much of the video's spatiotemporal information reaches the vision model. At the current default of 16 frames at 768px, the inter-frame gap ranges from ~1.87s (30s video) to ~7.5s (120s video). Increasing frame count to 24 would improve temporal coverage for longer videos while remaining within the token budget. This is the most impactful quality lever because every subsequent stage depends on the CVR, and the CVR depends on what the model sees.

### CVR Prompt Engineering

The system prompt that instructs the VLM controls the factual quality of the CVR. Key elements: explicit directives to describe only observable facts, to preserve chronological order, to prioritize semantically important events over exhaustive background detail, and to return only valid JSON in an exact schema. The CVR prompt was designed to exploit Qwen2.5-VL's strong instruction-following on structured directives. Poor CVR prompts produce factually sparse or hallucinated reports that propagate errors into every downstream caption.

### Style Prompt Engineering

The style system prompt controls whether the text model produces natural, readable captions that match the requested tone without leaking CVR-internal artifacts (timestamps, frame numbers, field labels). A key addition was the anti-timestamp directive — explicit instruction not to carry over structured formatting from the CVR into human-readable text. This lever is secondary to CVR quality but critical for output polish.

### Model Selection

The vision model's context window size is the binding constraint for frame capacity. Model quality differences (e.g., 8B vs 32B vs 72B parameter models) are secondary to context-window adequacy. Qwen2.5-VL 32B was selected primarily for its 128k context window, not its parameter count. The text model choice (`gpt-oss-120b`) was influenced by the discovery that the initially-tested `gpt-oss-20b` was a reasoning model whose chain-of-thought token consumption silently exhausted the output budget — a failure mode specific to reasoning models that required investigation to diagnose.

### Frame Sampling Strategy

Uniform sampling is simple and deterministic but can miss fast actions or scene transitions between sampled frames. Non-uniform strategies (scene-change detection, motion-aware sampling) could improve temporal coverage at the same frame count but introduce complexity and edge cases. The current implementation uses uniform sampling exclusively. The sampling strategy was identified early as a primary quality lever (ELL Session 7) but the project committed to uniform sampling for simplicity within the hackathon timeline.

### Temperature Settings

CVR generation uses `temperature=0.1` for factual determinism — the model should produce the same structured report for the same input. Style generation uses `temperature=0.2` — a balance between creative phrasing variety and output consistency. The spec's determinism requirement was the reason `temperature` was lowered from the original DESIGN.md value of `0.7` for style generation.

---

## 7. Evolution of Understanding

The following conceptual shifts materially changed the project's architecture or engineering approach.

### Shift 1: Video Models Don't Consume Video Files

**Initial assumption**: Send a video file to the VLM API and let the model handle encoding internally.

**Correction** (ELL Session 7): Modern Video VLMs like InternVL3 and Qwen2.5-VL do not process video files natively. They operate on ordered sequences of pre-extracted image frames. Frame extraction is an external preprocessing responsibility — not something the model handles automatically.

**Impact**: This discovery transformed frame selection from an implementation detail into the most important engineering decision in the pipeline. It also established that the system (not the model) is responsible for temporal coverage. Frame count, resolution, and sampling strategy are pipeline parameters that must be chosen explicitly.

### Shift 2: The Project Evaluates Video Understanding, Not Caption Generation

**Initial assumption**: The project's goal is to produce "better captions." Model selection should optimize for caption quality on benchmark leaderboards.

**Correction** (ELL Session 8): The system evaluates structured video understanding, not caption generation. The CVR is the project's most important artifact — every downstream caption depends entirely on the information it contains. The correct evaluation target is CVR accuracy (factual completeness, temporal reasoning, absence of hallucination), not caption style quality.

**Impact**: This reframed model selection, prompt engineering, and evaluation methodology. Structured CVR evaluation replaced benchmark leaderboard comparison. The experiment tracking harness was designed around comparing CVR quality across configurations. Manual inspection of CVRs became an accepted evaluation method because factual correctness, not stylistic flair, is the primary objective.

### Shift 3: Reasoning Models Have a Silent Failure Mode

**Initial assumption**: If a model call succeeds (no HTTP error, no timeout), it produced usable output.

**Correction** (Session 4, project-overview): A reasoning model like `gpt-oss-20b` emits chain-of-thought tokens (`reasoning_content`) before producing output text (`content`). With `max_tokens=256`, the reasoning exhausted the entire budget, the output was never produced, and the API returned `finish_reason: "length"` with no `content` field — but no error.

**Impact**: This bug was invisible to the pipeline because the API call technically succeeded. The fix (raising `max_tokens` to 2048) was simple, but the diagnosis required capturing raw API responses and discovering that reasoning models need 5–10x more token budget than non-reasoning models. The lesson generalized: token budgets that work for one model can silently fail for another, and reasoning models have a failure mode with no error signal.

### Shift 4: Auto-Provisioning Was the Wrong Solution for a Steady-State Problem

**Initial assumption**: The pipeline should automatically create and manage Fireworks GPU deployments at runtime. This is "set once and forget."

**Correction** (Phase 4, project-overview): Most users create a deployment once and reuse it indefinitely. The auto-provisioning system (~500 lines) handled deployment creation, polling, caching, and teardown but introduced operational surface area — accelerator type normalization mismatches, 7-day purge queue for deleted deployment names, and auth mechanism differences between container and desktop environments. The concept of provisioning-at-runtime was wrong for the steady-state use case.

**Impact**: The deployment system was removed. Model IDs are now environment variables that must be explicitly set. The system fails fast with a clear error if they're missing. This reduced code surface, simplified debugging, and eliminated a class of bugs related to API quirks and container/desktop auth differences.

### Shift 5: Graceful Degradation Without Observability Is a Bug

**Initial insight** (Session 10, project-overview): The pipeline's design pattern — "don't crash, produce well-formed output even on failure" — was correct in principle. But two significant bugs were masked by silent failure paths:

1. **Silent style-name mismatch**: Input styles used snake_case (`humorous_tech`) while the code matched against Title-Case-with-hyphens (`Humorous-Tech`). Case-sensitive exact matching rejected all four styles, producing `{"captions": {}}` with exit code 0 and no errors.
2. **Documentation lag**: A Docker bind-mount path mismatch — docs said `/input`, code said `/app/input` — caused silent empty output because bind mounts create empty directories when the host path doesn't exist.

**Impact**: The lesson — "every continue-without-error path needs a log statement" — was retroactively applied but the deeper realization is that the error-kernel pattern's correctness depends on observability at every failure boundary. Silent success is more dangerous than a crash because it produces output that looks valid but contains no useful information.

---

## 8. Current Architecture

The system is organized as a **two-stage pipeline** with a **fire-and-collect concurrency model** for the second stage. All components are implemented in Python under `src/video_captioning_agent/`.

### Pipeline Flow

```
/input/tasks.json
  → Input Loader (parse, structural validation, duplicate ID detection)
  → Style Filter (classify each task as ELIGIBLE / NO_SUPPORTED_STYLES)
  → For each eligible task (sequential, main thread):
      → Video Downloader (HTTP GET, 30s timeout, per-task isolation)
      → Video Inspector (OpenCV readability + metadata extraction)
      → Frame Sampler (16 uniform frames @ 768px; 1fps fallback path)
      → CVR Client (multimodal request → Qwen2.5-VL 32B, temperature 0.1)
      → CVR Parser (strict JSON validation, exact 5-field schema)
      → Dispatch Style Generation (background Future, 4-worker thread pool)
  → Collect style futures in submission order
  → For each completed style result:
      → Caption Validator (non-empty check, ~100-word soft warning, CVR-leakage detection)
      → Result Writer (filter to task-requested styles, atomic write)
  → Write /output/results.json (mkstemp + os.replace + fsync)
  → Exit 0
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| **Input Loader** | Parse `/input/tasks.json`, validate structure, detect duplicate task IDs |
| **Style Filter** | Validate requested styles against the four supported styles; classify task eligibility |
| **Video Downloader** | Fetch video via HTTP with bounded timeout; isolate per-task failures |
| **Video Inspector** | Verify OpenCV readability; collect fps, frame count, resolution |
| **Frame Sampler** | Extract 16 uniform frames at 768px; encode as JPEG base64; fallback to sequential 1fps |
| **CVR Client** | Build multimodal chat request; call Fireworks VLM; accept keyword overrides for model/prompt/params |
| **CVR Parser** | Strictly validate 5-field CVR JSON; reject missing/extra fields, duplicate keys, NaN/Infinity |
| **Style Generator** | Issue 4 text-only calls to gpt-oss-120b (always all 4 styles); all-keys-always-present contract |
| **Caption Validator** | Non-empty check, ~100-word soft warning, regex-based CVR-leakage detection |
| **Result Writer** | Filter 4-style output to task-requested styles; atomic write via mkstemp+os.replace |
| **Deployment Manager** | Resolve vision model ID from env vars; fail-fast if missing (no runtime provisioning) |

### Concurrency Model

- **Vision stage**: Sequential on the calling thread. One video at a time.
- **Style stage**: Dispatched as `Future` on `ThreadPoolExecutor(max_workers=4)`. Results collected by submission index after all tasks submitted.
- **Failure isolation**: Both stages implement per-task failure isolation. A vision-stage failure or style-stage failure for task N never affects task N+1.
- **Output contract**: Always produces a results array equal in length to input tasks. Failed tasks produce empty-string captions.

### Configuration Model

Three tiers: (1) environment variables (always take precedence), (2) `.env` file (best-effort load at startup, fills in only what's not already set), (3) hardcoded module constants (final fallback). Key variables: `FIREWORKS_API_KEY` (required), `FIREWORKS_VISION_MODEL_ID` and `FIREWORKS_STYLE_MODEL_ID` (optional — hardcoded module constants provide defaults), `DOTENV_PATH` (optional alternate `.env` location).

Client classes accept constructor keyword arguments for all configurable parameters (model ID, temperature, max tokens, prompts), enabling the experiments harness to override them without mutation.

### Supporting Systems

- **Experiments Harness** (dev-only, `experiments/`): Reuses production pipeline components with YAML-configurable prompts, models, and parameters. Tracks runs in MLflow (SQLite backend for metrics, filesystem for artifacts). Batch runner iterates over all YAML configs in a directory. Not part of the Docker image.
- **Streamlit Demo** (dev-only, `demo/`): Minimal web UI bundling a sample video; provisions a deployment on first run; displays all four style captions.
- **Manual Test Scripts** (`fireworks_test_deployment.py`): Two lightweight checks against the deployed VLM — image-sanity mode for auth/health, video mode for frame sampling + understanding.

---

## 9. Known Limitations

### Implementation Limitations

- **No retry or backoff**: The pipeline makes exactly one attempt per stage per task. A transient HTTP error or a single malformed VLM response fails the task permanently. No exponential backoff, no retry budget, no circuit breaker.
- **No streaming or incremental output**: Results are written only after all tasks complete. For large batches approaching the 10-minute runtime limit, a crash near the end loses all progress.
- **No programmatic factuality verification**: Caption factuality relies entirely on prompt design (CVR-only input isolation) and the CVR parser's schema enforcement. There is no post-generation comparison between captions and the CVR, no embedding-based similarity check, and no LLM-as-judge pass. This is explicitly deferred to future scope (TASKS.md).
- **No context-budget enforcement**: The frame sampler is configured for 16 frames at 768px, which empirically fits within the 128k context window, but there is no programmatic token counting. Parameters changed outside the tested range could silently produce truncated responses.
- **No incremental frame sampling**: The sampler reads all target frames into memory. For very long videos or very high target frame counts, this could exhaust available memory.
- **Hardcoded pipeline parameters in production**: Frame count, resolution, model temperatures, and timeouts are module-level constants — only overridable through the experiments harness, not through environment variables or config files in production.

### Design Limitations

- **Audio is out of scope**: The system is visual-only by design. Videos with critical audio context (dialogue, sound cues) will produce captions missing that information.
- **Vision-stage sequential bottleneck**: Processing one video's CVR at a time limits throughput. The concurrent style stage partially mitigates this by overlapping with the next video's vision work, but the vision stage remains the serial bottleneck.
- **Single-model dependency**: Both stages depend on Fireworks-hosted models. There is no fallback model provider, no multi-model voting, and no local inference path. If Fireworks is unreachable, the pipeline produces empty results.
- **No per-task timeout aggregation**: Each stage has individual timeouts, but there is no aggregate per-task watchdog. A task could theoretically consume up to several minutes cumulatively, though this is bounded by individual stage timeouts in practice.
- **Uniform sampling only**: Non-uniform strategies were identified as potential quality improvements but not implemented.

### Unresolved Engineering Questions

- **What frame count is optimal for 120-second videos?** The analytical model suggests 24 frames would improve temporal coverage while staying within the token budget, but this has not been empirically validated.
- **How much does prompt quality transfer across model families?** The CVR prompt was designed for Qwen2.5-VL. If the vision model is changed, prompt effectiveness may need re-evaluation.
- **Would a dedicated fact-consistency verifier improve output quality?** The project deferred this (TASKS.md → Future Scope). The question is whether a post-generation verifier would catch failures the current CVR-only isolation pattern misses.
- **Is the no-retry design acceptable for production use?** A single transient network failure fails a task permanently. For batch processing this is acceptable but for production services it would degrade reliability.

---

## 10. Mental Checklist

Before making changes to this project, understand the following:

**The CVR is the center of gravity.** Every downstream caption depends on it. Any change to frame sampling, the VLM prompt, or the CVR schema affects every output. The CVR parser enforces an exact 5-field contract — changing the schema requires changes in the parser, the prompt, and all tests that validate against the contract.

**The two stages are physically isolated.** The style generator receives only `report.to_json()` — a plain string. Do not pass frames, video URLs, metadata, or task IDs to the style stage. This isolation is the primary defense against hallucination. If you need the style model to know something about the video, it must come through the CVR.

**The system does not retry.** Every stage has exactly one attempt. A transient failure produces empty captions for that task. Before adding retry logic, consider where retry budget should be tracked (per-stage? per-task?) and whether retries could push the pipeline past the runtime constraint.

**Graceful degradation needs observability.** The pipeline is designed to never crash on per-task failures — it produces empty captions and continues. This pattern is correct but every silent-failure path needs logging. An empty result with no accompanying diagnostic is a debugging dead end.

**Generation always precedes filtering.** All four style captions are generated unconditionally. Filtering to task-requested styles happens only at result serialization (`build_task_result`). Do not add conditional branching in `generate_all_captions` based on which styles a task requested.

**The style generation contract is all-four-keys-always-present.** `generate_all_captions` returns a dict with all four supported style keys, using empty strings for failures. Never omit a key — this contract is relied upon by both the production result writer and the experiments harness.

**Frame selection is the primary quality lever.** Changes to frame count, resolution, or sampling strategy affect everything downstream. The current default of 16 frames at 768px was chosen analytically (token budget modeling), not experimentally validated against real video. If quality is insufficient, this is the first lever to adjust.

**The vision model context window (128k tokens) is the binding constraint on frame capacity.** At 16 frames, ~26% of the budget is consumed. You can increase frame count substantially before hitting the limit — but there is no programmatic token counting to warn you when you've exceeded it.

**Model IDs come from environment variables. There is no runtime provisioning.** If `FIREWORKS_VISION_MODEL_ID` or `FIREWORKS_STYLE_MODEL_ID` is unset, the system falls back to hardcoded module constants. If those are wrong, the pipeline fails at inference time, not startup. The old auto-provisioning system was removed — do not re-add it without reconsidering the operational complexity it introduces.

**The experiments harness shares production code but not production validation.** Experiment artifacts were not validated through the same path as production output, which historically masked bugs (the missing-keys problem). Any change to the production pipeline's validation or output contract should be verified against the experiments path as well.

**The spec requires exit code 0 even when all tasks fail.** Only infrastructure failures (missing input file, unreachable API, unwritable output directory) cause non-zero exit codes. Task-level failures — even when every task in the batch fails — must produce valid output JSON and exit successfully.

**Audio doesn't exist in this system.** Do not design features that depend on audio data without first adding an audio ingestion pipeline. The system is visual-only by design.

**The hackathon constraints (10 min runtime, 10 GB image) are resolved but still bound the architecture.** The pipeline operates within these constraints under the tested workload (10 tasks, 30–120s videos). Scaling beyond this workload may push against the runtime constraint because the vision stage (the bottleneck) is sequential.
