# Session Summary: Session 02

## Objective

Build an experiment-tracking harness under `experiments/` for systematic iteration on CVR prompts, frame-sampling parameters, and model selection (both vision and style-generation). The harness must reuse `src/` code without reimplementation and log all runs to MLflow for side-by-side comparison.

## Project State Before Session

- Task 7 (`FireworksCvrClient` additive kwargs) was just completed: 61 tests passed (59 existing + 2 new cvr_client tests).
- Production pipeline existed under `src/video_captioning_agent/` with `pipeline.py`, `cvr_client.py`, `cvr_parser.py`, `frame_sampler.py`, `style_generator.py`, `video_inspection.py`, `contracts.py`.
- `EXPERIMENT_TRACKING.md` specified the experiment-tracking design and acceptance criteria.
- `AGENTS.md` established project conventions. `DESIGN.md` §4.1/§4.2 specified system/user prompts for the CVR.
- MLflow was not installed in the venv. No `experiments/` directory existed.
- `FIREWORKS_API_KEY` lived in `.env` but was not loaded via `python-dotenv` anywhere in the codebase.
- The `style_generator.py` module used hardcoded module-level constants (`STYLE_MODEL_ID`, `STYLE_TEMPERATURE`, `STYLE_MAX_TOKENS`) with no mechanism for runtime overrides — unlike `cvr_client.py`, which had just been made overridable.

## Major Achievements

1. **Built `experiments/` from scratch**: harness config system, single-run CLI, batch runner, example config, test suite (16 tests).
2. **Added additive kwargs to `FireworksStyleClient`** matching the pattern in `FireworksCvrClient` (model_id, temperature, max_tokens, system_prompt).
3. **Discovered and fixed a duplicate `build_style_request` call bug** in `style_generator.py` that would have sent a malformed payload to the API.
4. **Migrated from MLflow file-based to SQLite backend** after discovering MLflow 3.x deprecated the file store.
5. **Made experiments scripts self-bootstrapping** (add `src/` and `experiments/` to `sys.path` automatically) so they run without `PYTHONPATH`.
6. **Integrated `python-dotenv`** so `FIREWORKS_API_KEY` is loaded from `.env` at runtime without manual sourcing.
7. **Investigated prompt drift** between `DESIGN.md` §4.1/§4.2 and the implementation, discovering that the user's claim of missing clauses was incorrect but identifying real (minor) drift.
8. **77 tests passed** (61 production + 16 experiments) at session end.

## Engineering Decisions

### 1. Additive kwargs on `FireworksStyleClient` (same pattern as `FireworksCvrClient`)
- **Decision**: Add `model_id`, `temperature`, `max_tokens`, `system_prompt` as optional kwargs to `FireworksStyleClient.__init__()` and `build_style_request()`, all defaulting to the existing module constants.
- **Reasoning**: The experiments harness must iterate on model/temperature/max_tokens for style generation. The additive-kwarg pattern was already approved for `cvr_client.py` in Task 7. Consistency across both clients.
- **Alternatives**: Refactor to a factory pattern. Rejected — too invasive for the scope.
- **Trade-off**: Zero behavior change when called with no kwargs (production `pipeline.py` unaffected), but adds API surface.

### 2. Single MLflow experiment for both CVR and style-gen
- **Decision**: Both CVR (Task 7) and style-gen (Task 10) tracked under the same MLflow experiment `video_captioning_cvr_experiments`.
- **Reasoning**: User explicitly confirmed this design. A single config drives both stages, so a single run should capture the full CVR→4-caption flow.
- **Trade-off**: Simpler traceability (one run per config), but mixes metrics from two distinct pipeline stages in one namespace.

### 3. File-based MLflow → SQLite migration
- **Decision**: Switched `DEFAULT_TRACKING_URI` from `file:./experiments/mlruns` to `sqlite:///experiments/mlflow.db`, with artifacts still on filesystem under `./experiments/mlruns`.
- **Reasoning**: User discovered MLflow 3.x deprecated the plain filesystem backend. The user explicitly asked to follow MLflow's recommended path rather than set `MLFLOW_ALLOW_FILE_STORE=true` as a workaround.
- **Alternatives**: Setting `MLFLOW_ALLOW_FILE_STORE=true` (initially implemented, then removed). Sticking with file-based + workaround. Rejected because it breaks on future MLflow versions.
- **Trade-off**: Slightly heavier setup (SQLite dependency, schema creation), but forward-compatible.

### 4. `_bootstrap_sys_path()` self-bootstrapping
- **Decision**: `run_experiment.py` and `run_all.py` insert `src/` and `experiments/` onto `sys.path` themselves, resolved relative to the script's own location.
- **Reasoning**: User ran the script directly and got `ModuleNotFoundError`. Relying on `PYTHONPATH` is fragile and user-unfriendly. Tests already did this via `conftest.py` — scripts should too.
- **Trade-off**: Slightly non-standard (modifying `sys.path` in application code), but standard practice for dev scripts that live outside the package tree.

### 5. `load_dotenv()` in `run_experiment.py`
- **Decision**: Call `load_dotenv()` at module level in `run_experiment.py` (after `_bootstrap_sys_path`), added `python-dotenv>=1,<2` to `experiments/requirements.txt`.
- **Reasoning**: User explicitly asked to use `load_dotenv()` rather than the assistant reading `.env` directly. Keeps FIREWORKS_API_KEY out of session logs.
- **Trade-off**: Another dependency for the experiments suite (dev-only, not in production requirements).

### 6. CVR parse failure → abort; style-gen failure → partial results
- **Decision**: If CVR parsing fails, the run aborts with an error. If style-generation fails on some styles, it logs partial captions and the failures.
- **Reasoning**: CVR is prerequisite for all style generation; no point continuing. Style failures can be partial (e.g., one of 4 styles times out).
- **Trade-off**: Adds complexity to the summary output (need to track per-style failures), but preserves maximal information.

## Architecture Changes

### New `experiments/` package structure:

```
experiments/
  harness.py              # ExperimentConfig dataclass, YAML config loader, MLflow setup
  run_experiment.py       # Single-run CLI (reuses src/ entirely)
  run_all.py              # Batch runner over configs/ directory
  configs/
    exp_example.yaml      # Annotated example config
  requirements.txt        # mlflow, pyyaml, python-dotenv (dev-only)
  tests/
    conftest.py           # sys.path bootstrap
    test_harness.py       # 9 tests: config loading, overrides, MLflow setup
    test_run_experiment.py # 3 tests: end-to-end with mocked HTTP + tiny video fixture
    test_run_all.py       # 4 tests: batch discovery, failure isolation, empty dir
```

### Modified files:
- `src/video_captioning_agent/cvr_client.py` — additive kwargs (done in prior session, finalized here)
- `src/video_captioning_agent/style_generator.py` — additive kwargs + fixed duplicate `build_style_request` call
- `tests/test_cvr_client.py` — +2 tests for additive kwargs
- `.gitignore` — added `experiments/mlruns/`, `experiments/mlflow.db`
- `.dockerignore` — added `experiments/`
- `README.md` — added experiment-tracking section, updated test commands

### Design distinction:
The harness architecture cleanly separates **config** (`harness.py` — no heavy imports) from **execution** (`run_experiment.py` — imports everything). This allows unit-testing config loading in isolation.

### Prompt drift discovered:
- `DESIGN.md` §4.2 user prompt does **not** contain a `Video Metadata:\n{metadata_json}` block, but the implementation does — this was added in an earlier session (not this one) and predates the assistant's involvement.
- The literal triple-backtick `\`\`\`` example in the "no markdown" clause was dropped from the system prompt (cosmetic).
- The `(e.g., Kitchen, Outdoor street)` examples were removed from the `scene` field description in the user prompt.

## Implementation Progress

### Phase 1 — Experiments harness skeleton
- Created `experiments/` directory structure, `requirements.txt`, `conftest.py`.
- Implemented `ExperimentConfig`, `FrameSamplingConfig`, `ModelConfig` frozen dataclasses.
- Implemented `load_config()` with inline/file-backed prompt loading (mutually exclusive), defaults to production constants for omitted sections.
- Implemented `apply_overrides()` for CLI overrides.
- Implemented `setup_mlflow()` with file-based tracking, experiment creation.

### Phase 2 — style_generator additive kwargs
- Added `system_prompt`, `model_id`, `temperature`, `max_tokens` kwargs to `FireworksStyleClient.__init__()` and `build_style_request()`.
- Discovered and fixed: `generate_caption()` had a stale inline `build_style_request()` call on line 151 that was still using hardcoded constants, bypassing the new kwargs. The same function had already been refactored to compute `request_payload` at the top, but the old `json=build_style_request(...)` call on line 151 was never removed — would have sent a request with wrong params.

### Phase 3 — Single-run and batch CLIs
- `run_experiment.py`: Argparse CLI with `--config`, `--tracking-uri`, `--video-path`, `--num-frames`, `--max-resolution`, `--fallback-fps`.
- `run_one_experiment()`: Full pipeline inside `mlflow.start_run` — `inspect_video` → `sample_frames` → `FireworksCvrClient` → `parse_cvr_response` → `FireworksStyleClient` → `generate_all_captions`. Logs params, prompt artifacts, latency metrics, CVR output, style captions, and per-style failures.
- `run_all.py`: Glob discovery of `*.yaml`/`*.yml` in `experiments/configs/`, sequential execution with per-config failure isolation, pass/fail accounting, exit code 1 on any failure.

### Phase 4 — SQLite migration
- Changed `DEFAULT_TRACKING_URI` to `sqlite:///experiments/mlflow.db`.
- Added `DEFAULT_ARTIFACT_ROOT = "./experiments/mlruns"`.
- Removed `MLFLOW_ALLOW_FILE_STORE=true` workaround entirely.
- Added scheme validation (`sqlite:` only) in `setup_mlflow()`.
- Updated all test URIs, `.gitignore`, `README.md`, CLI help text.

### Phase 5 — Self-bootstrapping + dotenv
- Added `_bootstrap_sys_path()` to `run_experiment.py` and `run_all.py`.
- Added `load_dotenv()` call in `run_experiment.py`, `python-dotenv` to requirements.

## Problems / Bugs / Limitations

### Fixed

1. **Duplicate `build_style_request` call in `style_generator.py:151`**: After refactoring to support kwargs, the old inline call `json=build_style_request(cvr, ...)` was not removed, leaving dead code that would have been ignored by Python (the later `json=request_payload` would win) but still confusing. Fixed.

2. **MLflow 3.x file-store deprecation**: MLflow 3.14 disabled `file:` backend by default. Initial fix was `MLFLOW_ALLOW_FILE_STORE=true` baked into `setup_mlflow()`. User rejected this approach, requiring a full migration to SQLite.

3. **`run_one_experiment` tracking URI isolation**: Tests set a tmp `tracking_uri`, but `run_one_experiment()` called `setup_mlflow()` with the hardcoded `DEFAULT_TRACKING_URI`, overwriting the test's URI. Fixed by adding an optional `tracking_uri` parameter threaded through to `setup_mlflow()`.

4. **`run_all` test failure**: The fake `run_one_experiment` was correctly monkeypatched, but `run_all_function` called `load_config()` *before* `run_one_experiment()`. The test's minimal YAML configs lacked `video_path`, causing `load_config()` to raise before the patched `run_one_experiment` could run. Fixed by also stubbing `load_config`.

5. **`ModuleNotFoundError: No module named 'video_captioning_agent'`**: User ran `python3 experiments/run_experiment.py` without `PYTHONPATH=src`. Fixed via self-bootstrapping `_bootstrap_sys_path()`.

6. **MLflow artifact listing fail in test**: `MlflowClient(tracking_uri=tracking_uri)` used a different tracking URI than the global one set by `setup_mlflow()`. Fixed by threading `tracking_uri` through consistently.

### Open / Not addressed

- **Fireworks model deployment issue**: The 404 on `accounts/fireworks/models/qwen2p5-vl-32b-instruct` may indicate the model ID changed or wasn't deployed under the account. Not investigated (user redirected to CWD-only work).
- **Prompt drift from DESIGN.md**: Assistant investigated but conversation ends before any resolution. The `{metadata_json}` block in the user prompt (absent from DESIGN.md §4.2) was pre-existing in the implementation, not introduced by the assistant. The user said they'd decide whether to keep it.

## Debugging / Investigation

### MLflow file-store failure
- Symptom: `MlflowException: The configured tracking URI is a local path... plain filesystem tracking is in maintenance mode.`
- Root cause: MLflow 3.14 disabled `file:` backend by default, requiring `MLFLOW_ALLOW_FILE_STORE=true` or a database backend.
- Initial resolution: Set `MLFLOW_ALLOW_FILE_STORE=true` in `setup_mlflow()`.
- Final resolution: Full migration to SQLite per user request.

### `run_all` test mystery
- Symptom: Test failed with "Experiment config must have a non-empty 'video_path'" despite `run_one_experiment` being monkeypatched.
- Root cause: `run_all_function` calls `load_config()` before `run_one_experiment()`. The mock YAML lacked `video_path`, so `load_config` raised.
- Fix: Monkeypatch `load_config` in addition to `run_one_experiment`.

### Prompt drift investigation
- User claimed two clauses were missing from the system prompt ("describe physical motion, not assumed purpose" and "no markdown-wrapping").
- Investigation revealed both clauses **are present** in the implementation. User's premise was factually incorrect.
- Real drift found: `Video Metadata:\n{metadata_json}` block in user prompt (not in DESIGN.md), `(e.g., Kitchen, Outdoor street)` examples removed from `scene` field.

## Important Insights

1. **MLflow version sensitivity**: MLflow 3.x breaking changes (file-store deprecation) directly affected the project. The lesson: pin MLflow version and test the tracking backend during CI, not just at experiment time.

2. **Prompt drift accumulates silently**: The `{metadata_json}` block in the user prompt was added "silently" (per the user) — it was never documented in DESIGN.md. This highlights the risk of prompt changes made for implementation convenience diverging from the canonical design document.

3. **Monkeypatching in tests has subtle failure modes**: The `run_all` test bug (where `load_config` raised before the patched `run_one_experiment` ran) is a classic monkeypatching pitfall — you must patch all intermediate calls in the call chain, not just the final target.

4. **Self-bootstrapping scripts vs. PYTHONPATH**: Dev scripts that import from a sibling `src/` package failed when run directly. The `_bootstrap_sys_path()` pattern solves this but is non-standard — it's a pragmatic compromise for a project without a proper installable package.

## Project State After Session

- **`experiments/` directory exists** with full experiment-tracking infrastructure.
- **MLflow tracking via SQLite** (`experiments/mlflow.db`), artifacts in `experiments/mlruns/`.
- **`FireworksStyleClient` supports runtime overrides** for model_id, temperature, max_tokens, system_prompt.
- **Bug fixed**: Duplicate `build_style_request` call that would have caused incorrect API payloads.
- **Scripts are self-bootstrapping**: `run_experiment.py` and `run_all.py` work without `PYTHONPATH`.
- **`.env` loaded automatically** via `python-dotenv` in `run_experiment.py`.
- **Experiment name changed** from `video_captioning_cvr_experiments` to `video_captioning_cvr_experiments_v2` (visible in harness.py; the `_v2` suffix may have been added during the SQLite migration to avoid conflicts with prior file-based runs).
- **Production pipeline untouched**: Dockerfile, requirements.txt, /input→/output contract unchanged.
- **77 tests passing** (61 production + 16 experiments).
- **Prompt drift identified**: `{metadata_json}` block in user prompt is an undocumented addition; user to decide whether to keep it.

## Interview-Worthy Talking Points

1. **MLflow 3.x file-store deprecation**: Hard-to-anticipate upstream breaking change mid-sprint. The decision tree — workaround vs. migration — and why the user chose migration (forward compatibility over expedience).
2. **Dual-client kwargs design**: Adding runtime overrides to both `FireworksCvrClient` and `FireworksStyleClient` via the same additive-kwargs pattern, keeping zero-args backward compatibility. A case study in minimal API surface extension.
3. **Prompt drift vs. DESIGN.md**: A real-world example of an implementation diverging from a canonical design document. The assistant was accused of introducing undocumented changes but investigation showed the drift predated its involvement. Good lesson in evidence-based debugging of process issues.
4. **Monkeypatching test failure isolation**: The `run_all` test bug is a textbook example of why you need to understand the full call chain when mocking. The lesson: when stubbing a function, verify no intermediate function raises first.
5. **Experiment harness reuse contract**: The harness reuses 5 `src/` modules directly without reimplementation, verified by end-to-end tests with a tiny synthetic video fixture. A clean example of the composition-over-reimplementation principle.
6. **`_bootstrap_sys_path()` pattern**: Making dev scripts self-contained is a trade-off — convenient for the user, but violates the "imports are pure" principle. Worth discussing when this pattern is justified.

## Keywords

experiment tracking, MLflow, SQLite, CVR, video captioning, Fireworks AI, style generation, config-driven experiments, YAML config, harness architecture, additive kwargs, sys.path bootstrap, python-dotenv, prompt drift, DESIGN.md, Monkeypatching, test isolation, MLflow UI, batch runner, frame sampling, Qwen2.5-VL, failure isolation, artifact logging, metric logging, run_all, backward compatibility, MLflow 3.x file store deprecation

## Presentation Assets

1. **Architecture diagram**: "Experiment harness reuse contract" — a diagram showing how `experiments/run_experiment.py` calls 5 `src/` modules (inspect_video, sample_frames, FireworksCvrClient, parse_cvr_response, FireworksStyleClient/generate_all_captions) without reimplementing any of them.
2. **Slide**: "MLflow 3.x File-Store Deprecation: Workaround vs. Migration" — decision tree showing the initial `MLFLOW_ALLOW_FILE_STORE=true` workaround, the user's rejection, and the final SQLite migration.
3. **Debugging case study**: "The `run_all` test mystery" — timeline of the monkeypatching bug where `load_config` raised before the patched `run_one_experiment` ran.
4. **Comparison table**: "Prompt drift between DESIGN.md §4.1/§4.2 and implementation" — three-column table (DESIGN.md text, implementation text, drift description).
5. **Timeline**: "Session 02: From Task 7 completion to experiments harness to prompt drift investigation" — multi-phase session sequence.
6. **Benchmark chart**: Not applicable (no performance measurements taken).
