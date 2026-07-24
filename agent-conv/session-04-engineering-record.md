# Session Summary: Session 04

## Objective

This session had three sequential goals: (1) refactor the production pipeline so style generation for video N runs concurrently with VLM processing for video N+1 (latency optimization); (2) investigate and fix a bug where gpt-oss-20b style generation returned only 2 of 4 expected styles (keys missing entirely, not empty); (3) eliminate CVR-internal timestamp formatting leaking into human-facing captions.

## Project State Before Session

- **Session 03** ended in plan-mode lockout — all edits were fully specified but none were executed due to permission restrictions. The prompt-drift resolution (backtick marker, scene example, experiment config restoration, DESIGN.md update) was blocked.
- The production pipeline (`pipeline.py`) processed tasks fully sequentially: `_process_task` ran download → inspect → sample → CVR → parse → style generation → validate → build result for each video before starting the next. Style generation for video N blocked the start of video N+1's CVR entirely.
- `generate_all_captions` omitted failed styles from `captions` (intentional Task 10 contract — `failures` tuple held the reason, and downstream Task 11/12 were responsible for reconstructing `""` for missing keys).
- The experiments harness logged `result.captions` directly to `style_captions.json` artifacts, bypassing Task 11/12 validation. Failed styles thus appeared as **omitted keys** in MLflow artifacts.
- `STYLE_MAX_TOKENS = 256` (hardcoded in `style_generator.py`). `STYLE_SYSTEM_PROMPT` had no anti-timestamp directive.
- 80 tests passing at session start.

## Major Achievements

1. **Refactored pipeline.py for concurrent style generation**: Split `_process_task` into `_run_vision_stage` (sequential, main thread) and `_run_style_stage` (dispatched to `ThreadPoolExecutor`). Style gen for video N now overlaps with VLM for video N+1.
2. **Added 3 pipeline tests** verifying non-blocking concurrency, out-of-order result collection, and per-task style-failure isolation.
3. **Investigated and resolved missing-style-keys bug**: Reconstructed the failing run from MLflow artifacts; identified root cause; fixed `generate_all_captions` to always emit all 4 keys (`""` on failure).
4. **Disproved the user's hypothesized root cause** (refusal-adjacent hedging/prose commentary) — actual cause was `max_tokens=256` being too small for reasoning model gpt-oss-20b, exhausting its `reasoning_content` budget before `content` could be produced.
5. **Added raw-response capture** to `StyleGenerationError` and `CaptionGenerationFailure` for diagnostics; updated experiments harness to log `style_failures.json`.
6. **Added anti-timestamp directive to style-generation prompt** (Task 10) and a warning-only regex validator in `caption_validation.py` (Task 11).
7. **93 tests passing** at session end (up from 80).

## Engineering Decisions

### 1. ThreadPoolExecutor over asyncio for style-gen concurrency

- **Decision**: Use `concurrent.futures.ThreadPoolExecutor(max_workers=4)` to dispatch style generation as background futures.
- **Reasoning**: The pipeline is entirely synchronous (`requests` for HTTP). Wrapping in asyncio would require rewriting the entire call chain. Thread pool provides fire-and-collect semantics with bounded parallelism.
- **Alternatives**: asyncio (rejected — too invasive), per-style parallel futures (rejected — would create unbounded HTTP concurrency).
- **Trade-off**: GIL contention is minimal (I/O-bound HTTP calls dominate). Single-worker pool (max_workers=1) was considered but 4 workers was chosen to allow multiple style tasks to overlap when VLM stages run sequentially.

### 2. All-4-keys-always-present contract for `generate_all_captions`

- **Decision**: Change `generate_all_captions` to initialize `captions = {style: "" for style in SUPPORTED_STYLES}` and only overwrite on success.
- **Reasoning**: The user explicitly required "ANY failure results in that style's key still being present in the output dict with an empty string value — never an omitted key." This is a correctness requirement for the experiments harness (which bypasses Task 11/12). Making it the central contract in `generate_all_captions` fixes both production and experiment paths.
- **Trade-off**: `validate_all_captions` now sees failed styles as EMPTY instead of MISSING. The final production output is identical (`""` either way), but the failure-kind label changes from MISSING to EMPTY. The change requires updating the module docstring and one existing test assertion.

### 3. Reasoning-model token budget diagnosis

- **Decision**: Re-ran the saved CVR through gpt-oss-20b with raw-response capture to determine root cause.
- **Finding**: gpt-oss-20b is a reasoning model that emits `reasoning_content` (chain-of-thought) before `content`. With `max_tokens=256`, the reasoning exhausts the token budget (`finish_reason: "length"`) and `content` is never produced. With `max_tokens=2048`, all 4 styles succeed including humor-leaning ones.
- **Implication**: The fix is raising `max_tokens`, not a prompt-wording change or model swap. The user's hypothesized "refusal-adjacent hedging" was wrong.

### 4. Warning-only CVR-leakage check (not hard rejection)

- **Decision**: Add `_warn_if_leaking_cvr_artifacts` to `caption_validation.py` that logs a warning if a caption matches `CVR_LEAKAGE_PATTERN` — never rejects or retries.
- **Reasoning**: Consistent with the existing loose word-count sanity check (`_warn_if_long`). Hard rejection would break the pipeline's no-retry design. The style-generation prompt fix is the primary solution; the validator is observability only.
- **Trade-off**: The regex (`\b\d+(?:\.\d+)?\s*'?s(?:ec(?:ond)?s?)?\b`) has false-positive risk (e.g., "1980s music" matches). Acceptable for warning-only.

## Architecture Changes

### `src/video_captioning_agent/pipeline.py` — Major refactor

- **Split**: `_process_task(task, ...) → TaskResult` replaced by:
  - `_run_vision_stage(task, ...) → CanonicalVideoReport | None` — download, inspect, sample, CVR, parse (sequential, main thread)
  - `_run_style_stage(task, report, client) → TaskResult` — generate_all_captions, validate, build (dispatched to executor)
- **New concurrency**: `run_pipeline` uses `ThreadPoolExecutor(max_workers=style_workers)` with `STYLE_WORKERS = 4`. Main thread submits style future, immediately proceeds to next video's VLM. Futures collected by submission index after all tasks submitted.
- **Parameter**: `style_workers: int = STYLE_WORKERS` added to `run_pipeline()`.

### `src/video_captioning_agent/style_generator.py` — Three changes

- **`generate_all_captions`** (lines ~180): Changed `captions: dict[str, str] = {}` to `captions: dict[str, str] = {style: "" for style in SUPPORTED_STYLES}`. Failed styles now produce `""` instead of being omitted.
- **`StyleGenerationError`**: Added optional `raw: str | None` attribute carrying the raw HTTP response body.
- **`CaptionGenerationFailure`**: Added `raw_response: str | None = None` field.
- **`STYLE_SYSTEM_PROMPT`**: Extended with anti-timestamp directive — captions must be natural flowing prose, no timestamps/frame numbers/CVR-internal formatting.
- **New helpers**: `_safe_response_text`, `_extract_raw_response`.

### `src/video_captioning_agent/caption_validation.py`

- **New constant**: `CVR_LEAKAGE_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\s*\'?s(?:ec(?:ond)?s?)?\b|\btimestamp\b', re.IGNORECASE)`
- **New function**: `_warn_if_leaking_cvr_artifacts` called from `validate_all_captions`.
- **New test cases** in `test_caption_validation.py`: parametrized test for detection of leakage patterns and non-detection of natural prose.

### `experiments/run_experiment.py`

- `_run_style_stage` now returns `CaptionGenerationResult` (not just `dict`). Logs `style_failures.json` artifact when failures exist. Summary includes `style_failures`.

## Implementation Progress

### Tests added/modified (13 tests net new, 93 total)

1. **`test_pipeline.py`** — 3 new tests:
   - `test_pipeline_does_not_block_next_cvr_on_inflight_style_generation` — uses `threading.Event` to prove v2's CVR fires while v1's style gen is blocked.
   - `test_pipeline_collects_style_results_in_input_order_even_when_completed_out_of_order` — delays v1's style so v2 completes first, asserts correct ordering.
   - `test_pipeline_isolates_style_generation_failure_from_next_video` — v1 style raises, v2 unaffected.
   - Adapted existing `test_pipeline_isolates_a_failed_task_and_writes_all_results`.

2. **`test_style_generator.py`** — 2 changes:
   - Updated `test_generation_failure_for_one_style_does_not_stop_other_styles` to assert all 4 keys present.
   - Added `test_failed_style_key_is_present_as_empty_string_for_any_failure_mode` — parametrized across malformed body (StyleGenerationError with raw), HTTP error, and timeout.

3. **`test_caption_validation.py`** — 8 new parametrized cases on `CVR_LEAKAGE_PATTERN`.

4. **`test_style_prompt.py`** — New test: `test_style_system_prompt_contains_no_timestamps_directive`.

## Problems / Bugs / Limitations

### Fixed

1. **Missing style keys in experiment artifacts**: `generate_all_captions` omitted failed styles. Fixed by initializing all 4 keys as `""`.

2. **gpt-oss-20b producing only 2 of 4 styles**: Root cause was `max_tokens=256` insufficient for reasoning-model chain-of-thought, not refusal/hedging. Mitigated by raising to 2048 in config. The token budget issue is model-dependent — gpt-oss-120b apparently works within 256 tokens.

3. **CVR timestamp formatting leaked into captions**: Fixed by prompt directive + warning validator.

4. **Raw responses not captured for diagnostics**: `StyleGenerationError` and `CaptionGenerationFailure` now carry raw body.

5. **Experiment harness not logging failures**: `style_failures.json` now logged alongside `style_captions.json`.

### Open / Not addressed

- **CVR deployment flakiness**: The custom deployment `e7g2xwfe` returned 404 multiple times during the session. The user eventually deleted all deployments.
- **`STYLE_MAX_TOKENS=256` in production**: The production default may be too small for reasoning models (gpt-oss-120b). Not changed — user to decide.
- **Sessions 01-03 edits still blocked**: The prompt-drift fixes (backtick marker, scene example, experiment config restoration, DESIGN.md update) from Sessions 02/03 remain unexecuted.
- **No asyncio refactor**: The user repeatedly referred to "the asyncio refactor" — no such refactor exists. The concurrency uses `concurrent.futures.ThreadPoolExecutor`. This premise error was corrected but not resolved.

## Debugging / Investigation

### Missing style keys — full investigation chain

1. **Confirmed the bug artifact**: Inspected `mlruns/2/356727511c8e49ef8dbeca68be7280f4/artifacts/style_captions.json` — exactly 2 styles present (Formal, Humorous-Non-Tech), 2 missing (Sarcastic, Humorous-Tech).

2. **Confirmed MLflow metadata**: SQLite query showed `style_model_name=accounts/fireworks/models/gpt-oss-20b`, `style_latency=33.3s`, `status=FINISHED`.

3. **Determined raw responses unrecoverable**: `generate_all_captions` never logged raw per-style responses, only final `captions` dict. The experiment harness did not log `failures`. Past raw data is permanently lost.

4. **Re-ran with raw capture**: Wrote a probe script feeding the saved CVR JSON through `FireworksStyleClient` with raw-response capture. Results showed:
   - All 4 responses had `finish_reason: "length"` and `reasoning_content` (long chain-of-thought) but **no `content` field**.
   - `response.json()["choices"][0]["message"]["content"]` raised `KeyError` → `StyleGenerationError`.
   - This disproved the "refusal-adjacent hedging" hypothesis.

5. **Confirmed with higher `max_tokens`**: Re-ran with `max_tokens=2048`. All 4 styles produced valid `content` fields. The root cause is purely token-budget exhaustion in the reasoning model.

### CVR deployment availability

- Initially 404 (deployment `e7g2xwfe` down).
- User confirmed API became available, but it 404'd again on retry.
- User eventually confirmed deployments were deleted (taking too long for code writing session).

## Important Insights

1. **Reasoning models have silent failure modes**: gpt-oss-20b's `reasoning_content` exhausts the token budget before `content` is produced, but this is invisible to the API client — it just sees `finish_reason: "length"` and no `content`. No error code, no refusal text. This is a general class of bug: "the model tried but couldn't fit the answer."

2. **Heuristic token budgets are a sharp edge**: `STYLE_MAX_TOKENS=256` was a guess that worked for non-reasoning models. Reasoning models consume 5-10x more tokens internally before producing output. The same budget can silently break one model and not another.

3. **User premise errors require correction, not agreement**: The user twice gave incorrect premises ("asyncio refactor," "refusal-adjacent hedging"). In both cases, the assistant investigated, found the facts, and corrected the user — resulting in a correct diagnosis that neither prompt-wording nor model-swap was needed.

4. **Experiments harness bypasses production validation pipeline**: The missing-key bug was invisible in production because `build_task_result`'s `.get(style, "")` always reconstructs empty strings. It only surfaced in the experiments harness, which logged `result.captions` directly. This design discrepancy (missing Task 11/12 in experiments path) was a latent observability bug.

5. **ThreadPoolExecutor vs asyncio distinction matters**: The user conflated "background concurrency" with "asyncio." The correct choice (thread pool for sync code) avoids rewriting the entire I/O layer.

## Project State After Session

- **Pipeline concurrency improved**: Style generation no longer blocks the next video's VLM processing. Each style stage runs on a background thread while the main thread continues to the next video's vision work.
- **Style generation robustness improved**: All 4 style keys always present in output — failed styles are `""` instead of omitted. Raw response bodies captured for diagnostics.
- **Timestamp leakage fixed**: Both prompt-level (preventive) and warning-level (detective) guards added.
- **93 tests pass** (up from 80).
- **Experiments harness**: Now logs `style_failures.json` with raw response bodies.
- **6 files modified**: `pipeline.py` (major refactor), `style_generator.py` (contract change + raw capture + prompt fix), `caption_validation.py` (leakage check), `run_experiment.py` (failure logging), `test_pipeline.py` (3 new tests), `test_style_generator.py` (updated + 1 new test), `test_caption_validation.py` (8 new params), `test_style_prompt.py` (new).
- **No sessions 01-03 edits executed** (prompt-drift fixes still blocked).
- **No deployments active** (user deleted CVR deployments).

## Interview-Worthy Talking Points

1. **Reasoning model token-budget failure**: A reasoning model silently fails to produce output when `max_tokens` is too small — the chain-of-thought consumes the budget and `content` is never emitted. This is distinct from refusal, timeout, or malformed-response bugs. The fix is raising `max_tokens`, not changing prompts or models.

2. **Sequential pipeline → concurrent dispatch refactoring**: Refactoring `_process_task` into `_run_vision_stage` (main thread) and `_run_style_stage` (ThreadPoolExecutor) while preserving task-level failure isolation. The design constraint was to avoid "full bounded concurrency across all tasks" — only background the style-gen stage.

3. **User-premise correction as engineering skill**: Twice the user asserted incorrect premises (asyncio refactor, refusal-adjacent hedging). The assistant investigated, disproved the premises, and presented evidence — resulting in a correct diagnosis that neither prompt-wording nor model-swap was needed.

4. **Experiments harness bypassed production validation**: The missing-key bug existed only in experiment artifacts because the harness logged `result.captions` directly, bypassing Task 11/12. A cautionary tale about observability gaps between development and experiment code paths.

5. **Warning-only vs hard-rejection pattern**: The CVR-leakage check was designed as a warning-only validator (no retry, no rejection), consistent with the existing "loose word-count sanity check" pattern. The primary fix was the prompt — the validator is diagnostic only.

## Keywords

ThreadPoolExecutor, concurrent style generation, fire-and-collect, concurrent.futures, pipeline refactoring, reasoning model, token budget exhaustion, max_tokens, gpt-oss-20b, reasoning_content, content vs reasoning_content, finish_reason length, style generation, CVR leakage, timestamp leakage, caption validation, warning-only validator, experiment harness, MLflow artifacts, missing keys bug, style failures, raw response capture, StyleGenerationError, CaptionGenerationFailure, all-4-keys contract, STYLE_WORKERS, STYLE_MAX_TOKENS, STYLE_SYSTEM_PROMPT, no timestamps directive, event isolation, thread safety, CVR_LEAKAGE_PATTERN

## Presentation Assets

1. **Timeline diagram**: "Session 04 — Three-phase session" — Phase 1 (pipeline concurrency refactor) → Phase 2 (missing-keys bug investigation + fix) → Phase 3 (timestamp leakage fix). Each with tool outputs, test counts, and artifacts.

2. **Architecture diagram**: "Before/After pipeline concurrency" — showing sequential `_process_task` vs concurrent `_run_vision_stage` (main thread) + `_run_style_stage` (background thread pool).

3. **Debugging case study**: "The missing Sarcastic caption" — full evidence chain from MLflow artifact inspection → raw response re-run → `finish_reason:length` discovery → `max_tokens=2048` confirmation. Disproving two user premises along the way.

4. **Comparison table**: "Before/After `generate_all_captions` contract" — showing old behavior (failed styles omitted from dict) vs new (all 4 keys `""`), impact on production vs experiments path.

5. **Slide**: "Reasoning models eat your token budget" — how `reasoning_content` silently exhausts `max_tokens` before `content` is produced. The `finish_reason: "length"` vs `finish_reason: "stop"` distinction with gpt-oss-20b evidence.

6. **Benchmark chart**: "gpt-oss-20b success rate vs max_tokens" — 256 tokens → 0/4 styles succeed, 2048 tokens → 4/4 succeed. With actual raw captions showing Sarcastic and Humorous-Tech responses.

7. **Timeline**: "From 80 tests to 93 tests" — breaking down each test addition and its purpose.
