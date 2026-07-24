# README run instructions from implementation progress

**Session ID:** ses_0a8a41c5effehugH2XriXSEe2E
**Created:** 7/12/2026, 10:54:27 PM
**Updated:** 7/13/2026, 4:01:08 AM

---

## Assistant

61 passed (was 59 — +2 new cvr_client tests). Now let me check if `test_cvr_prompt.py` already covers prompt directives (it should still pass since I didn't change the default promptcontent).

**Tool: read**

---

## Assistant

Good — `test_cvr_prompt.py` still passes (the default user prompt content is unchanged; it just lives in a named constant now).

The Task 7 additive edit is done. Now starting **item 2** — the experimentsharness.

**Tool: todowrite**

---

## Assistant

Let me check what Python tooling's available (mlflow, yaml) and the existing `.gitignore` to respect it.

**Tool: bash**

**Tool: read**

---

## Assistant

mlflow isn't installed. I'll need to install it to actually run the harness tests. Per `EXPERIMENT_TRACKING.md`: *"`mlflow` is the one new dependency this introduces — add it to the dev/experiments dependency group, not the production runtime dependencies used by the Dockerimage."* So I'll add `experiments/requirements.txt` (separate from the production `requirements.txt`), and install mlflow into the venv.

**Tool: bash**

---

## Assistant

mlflow installed. Now let me look at the specs from `EXPERIMENT_TRACKING.md` once more for the exact config schema + runner steps, then design theharness.

Key design decisions I'm making (per EXPERIMENT_TRACKING.md and your instructions):

1. **Both CVR (Task 7) and style-gen (Task 10) tracked** in the same MLflow experiment `video_captioning_cvr_experiments` — per your message.
2. **File-based MLflow tracking** (`mlflow.set_tracking_uri("file:./experiments/mlruns")`) — no server. UI via `mlflow ui --backend-store-uri ./experiments/mlruns`.
3. **One config = one MLflow run**, atomic via `with mlflow.start_run(run_name=...)`. Config drives both CVR generation and style generation. The CVR's output is logged as an artifact and **fed directly into style generation** (so one run captures the full CVR→4-caption flow).
4. **Reuse `src/`** — `sample_frames`, `inspect_video`, `FireworksCvrClient` (with new kwargs), `FireworksStyleClient`, `generate_all_captions`. No reimplementation.
5. **`experiments/` directory** separate from `src/`; not in Docker image.
6. **`experiments/requirements.txt`** holds `mlflow` and `pyyaml` (dev-only deps).
7. `.gitignore` gets `experiments/mlruns/` so tracked runs don't get committed.
8. Tests in `experiments/tests/` (mocked MLflow + mocked model clients) per AGENTS.md "tests use pytest with mocked network/model calls."

Let me first inspect `inspect_video` and `sample_frames` signatures to call them correctly fromthe harness.

**Tool: grep**

---

## Assistant

Now let me create the experiments directory structure andfiles.

**Tool: bash**

---

## Assistant

**Tool: write**

---

## Assistant

**Tool: write**

---

## Assistant

Now the single-run CLI runner. It reuses `src/`'s `inspect_video`, `sample_frames`, `FireworksCvrClient` (with config kwargs), `FireworksStyleClient` + `generate_all_captions`, all inside one `mlflow.start_run`.

**Tool: write**

---

## Assistant

_Thinking:_

I made a mistake in the `_run_style_stage` — I'm passing `model_id_override`, `temperature_override`, `max_tokens_override` to `FireworksStyleClient`, but I haven't added those kwargs to `FireworksStyleClient.__init__()`. The style generator currently uses module constants (`STYLE_MODEL_ID`, `STYLE_TEMPERATURE`, `STYLE_MAX_TOKENS`) hard-coded in `build_style_request`.

I need to make the same additive-kwarg change to `FireworksStyleClient.__init__()` and `build_style_request()` in `src/video_captioning_agent/style_generator.py` so the experiments harness can swap the model/temperature/max_tokens for style generation too. Per EXPERIMENT_TRACKING.md, the harness must allow iterating on `model_name`, `temperature`, `max_tokens` for style generation.

Let me fix this by adding the same additive optional kwargs to `style_generator.py`. This is consistent with the approach the user approved for `cvr_client.py`.

I need to add the same additive-kwarg pattern to `FireworksStyleClient` so the style-gen stage is also config-swappable. Let me fix `style_generator.py`first.

**Tool: read**

---

## Assistant

**Tool: edit**

---

## Assistant

Now let me check the rest of `generate_caption` to make sure the request_payload is consumed correctly (it currently calls `build_style_request` inline, which I've moved). Let me read it.

**Tool: read**

---

## Assistant

There's a duplicate `build_style_request` call on line 151 — the old inline call still exists in the `json=` field. Need to fix that to use `request_payload`.

**Tool: edit**

---

## Assistant

Now fixing the experiments runner's `_run_style_stage` to use the new kwargs correctly:

**Tool: edit**

---

## Assistant

_Thinking:_

I've referenced `config.style_system_prompt` which doesn't exist in `ExperimentConfig`. Per `EXPERIMENT_TRACKING.md`, the style generation inputs to vary are `model_name`, `temperature`, `max_tokens` (and CVR). The system prompt for style generation isn't listed as a configurable per EXPERIMENT_TRACKING.md's "What to build" — only CVR-related `SYSTEM_PROMPT` and `USER_PROMPT` are configurable.

Let me re-read EXPERIMENT_TRACKING.md's config schema to confirm: the config shows `system_prompt`, `user_prompt_template` (for CVR), `frame_sampling`, `model` (with `name`, `temperature`, `max_tokens`). The Go says to iterate on:
- `SYSTEM_PROMPT` (CVR)
- `USER_PROMPT` (CVR)
- Frame-sampling params
- Model choice / generation params (`model_name`, `temperature`, `max_tokens`)
- `video_path`

So the "model" section in the original config example was for CVR. But since we're now also tracking style-gen experiments with configurable model/temperature/max_tokens, I added `cvr_model` and `style_model` sections in `harness.py`.

For the style system prompt — `STYLE_SYSTEM_PROMPT` is a constant, and EXPERIMENT_TRACKING.md doesn't list it as a configurable. Per the spec, style-gen uses a fixed system prompt. So I should NOT make `style_system_prompt` a config field. I should just pass nothing for `system_prompt` to `FireworksStyleClient`, letting it use the `STYLE_SYSTEM_PROMPT` default.

Let me fix `_run_style_stage` to not pass `system_prompt` (use default), and remove the nonexistent `config.style_system_prompt`reference.

The style system prompt isn't a configurable per `EXPERIMENT_TRACKING.md` (only CVR's `SYSTEM_PROMPT`/`USER_PROMPT` and model params are). Let me fix `_run_style_stage` to use the default `STYLE_SYSTEM_PROMPT`.

**Tool: edit**

---

## Assistant

Now let me verify the style_generator changes didn't break existing tests, and run the fullsuite.

**Tool: bash**

---

## Assistant

Now let me write the batch runner `run_all.py`, an example config, the `.gitignore` addition, a conftest for the experiments tests, and the actual tests.

**Tool: write**

---

## Assistant

Now an example config file demonstrating the schema:

**Tool: write**

---

## Assistant

Now update `.gitignore` to exclude `mlruns/` and add the experiments tests' conftest +tests.

**Tool: edit**

---

## Assistant

**Tool: write**

---

## Assistant

Now the tests for the experiments harness. I'll cover: config loading (inline + file-backed prompts + overrides), MLflow setup (file-based, experiment name), `run_one_experiment` end-to-end with **mocked** vision + style clients (no network, no real video — use a tiny generated fixture video so `inspect_video`/`sample_frames` actually run), and `run_all`'s discovery + per-config failure isolation.

**Tool: write**

---

## Assistant

Now the test for `run_one_experiment` end-to-end with mocked model clients + a tiny real video fixture (so `inspect_video`/`sample_frames` actually exercise the reuse path). This is the key test proving the harness reuses `src/` rather than reimplementing it.

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

OpenCV can write tiny mp4 fixtures. Now writing the `run_experiment` end-to-end test: it builds a tiny video fixture,monkeypatches `inspect_video`/`sample_frames`-or-reuses-them-real + mocks the VLM/style HTTP layer via `requests.Session`, asserts MLflow artifacts + metrics getlogged.

**Tool: write**

---

## Assistant

Now the test for `run_all.py` — config discovery + per-config failure isolation.

**Tool: write**

---

## Assistant

Now let me run the experiments tests.

**Tool: bash**

---

## Assistant

_Thinking:_

MLflow 3.14 disabled the file-based store by default and requires `MLFLOW_ALLOW_FILE_STORE=true`. This is an environment-config decision. Per EXPERIMENT_TRACKING.md, the user explicitly chose file-based MLflow (`mlflow ui` pointed at a local `mlruns/` directory), and your instructions confirmed "Use file-based MLflow tracking (`mlflow ui` pointed at a local `mlruns/`) — no MLflow server process needed."

So I need to set `MLFLOW_ALLOW_FILE_STORE=true` in the environment for both the harness and the tests. The cleanest way that respects AGENTS.md ("read credentials from environment") is to set this env var in `setup_mlflow()` before importing/using mlflow, so the harness works out of the box for the user without them needing to set it manually. But that's slightlyhacky—setting an env var from library code.

Better approach: set it in the experiments tests' `conftest.py` (so tests work) AND document it in `run_experiment.py`'s docstring/README that the user needs `MLFLOW_ALLOW_FILE_STORE=true`. Actually, the cleanest is to set it in `setup_mlflow()` since that's the single entry point — it's a known MLflow 3.x requirement for file-based tracking, exactly the use case we're enabling. Setting `os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")` in `setup_mlflow()` is the right call: it makes the documented file-based mode actually work without forcing the user to read MLflow's deprecation notices, while still letting them override to a DB backend if they want.

Let me update `setup_mlflow()` to set this env var, and verify.

MLflow 3.x requires `MLFLOW_ALLOW_FILE_STORE=true` to use the file-based backend (which is what `EXPERIMENT_TRACKING.md` specifies). Setting it inside `setup_mlflow()` so the harness works out of thebox.

**Tool: edit**

---

## Assistant

_Thinking:_

Now the `test_run_all.py` failure is because `run_all_function` calls `setup_mlflow()` from `harness`, but I'm monkeypatching `run_all.setup_mlflow`. Let me check — actually `run_all.py` imports `setup_mlflow` from `harness` into its own namespace, so `run_all.setup_mlflow` is the right target. But the test failure shows the file store error came from a real `setup_mlflow` call. Let me look — the test monkeypatches `run_all.setup_mlflow`, which should prevent the real call. Let me re-run to see.

Actually wait — the test failure for `test_run_all_isolates_per_config_failures_and_continues` may have been from BEFORE my edit (the test run was before the env var fix). Let me re-run the suite now.

**Tool: bash**

---

## Assistant

_Thinking:_

Now 14 pass, 2 fail. Let me look at the two failures:

1. `test_run_all_isolates_per_config_failures_and_continues` — let me see the actual error. The tail shows the `test_run_one_experiment_logs...` error (run not found when listing artifacts). Let me run with more context.

2. `test_run_one_experiment_logs_cvr_and_style_artifacts_to_one_mlflow_run` — the artifact listing fails with "Run not found". This is because I create the MlflowClient with `tracking_uri=tracking_uri`, but mlflow's fluent API (`mlflow.start_run`) uses the global tracking URI. The run was created under the global tracking URI set by `setup_mlflow()`, but `mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)` creates a client that may resolve to a different path.

Actually, looking more carefully: `tracking_uri = f"file:{tmp_path / 'mlruns'}"`. When I do `mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)`, and `tracking_uri` is `file:/tmp/pytest-of-aditya/pytest-5/.../mlruns`, the run should be findable. But the error says run not found.

Wait — in the test I call `setup_mlflow(tracking_uri)` which sets the global tracking URI. Then `run_experiment.run_one_experiment(config)` internally calls `setup_mlflow()` AGAIN with the DEFAULT tracking URI (`file:./experiments/mlruns`), which is a DIFFERENT path! That overwrites the global tracking URI. So the run gets created under `./experiments/mlruns` (in the cwd), not under my tmp_path.

That's the bug: `run_one_experiment` calls `setup_mlflow()` with no args, using the default. I need `run_one_experiment` to accept a tracking_uri parameter, OR I should not call `setup_mlflow()` inside `run_one_experiment` and instead require the caller to set it up.

Actually, looking at the spec more carefully — `run_one_experiment` calls `setup_mlflow()` to be self-contained. But for testing (and for `run_all`), I want to control the tracking URI. The cleanest fix: add an optional `tracking_uri` parameter to `run_one_experiment` that defaults to `DEFAULT_TRACKING_URI`, passed through to `setup_mlflow`.

Let me also check the `run_all` failure — likely the same issue: `run_one_experiment` is called with config only, and it internally calls `setup_mlflow()` with default URI, but the test already set up mlflow differently. Actually in `test_run_all_isolates_per_config_failures_and_continues`, I monkeypatch `run_all.setup_mlflow` but `run_one_experiment` (the real one, not monkeypatched) calls `setup_mlflow` from its own module namespace (`run_experiment.setup_mlflow`). Since I monkeypatch `run_all.run_one_experiment` entirely with a fake function, the real `setup_mlflow` shouldn't be called from within `run_all`. But `run_all_function` calls `setup_mlflow()` at the top — and I monkeypatched `run_all.setup_mlflow` to be a lambda. So that should be fine.

Wait, let me re-read the `run_all` test failure. Let me run just that test with more verbose output.

**Tool: bash**

---

## Assistant

_Thinking:_

The `run_all` test is failing because my fake `run_one_experiment` is being set on the `run_all` module, but `run_all_function` calls `run_one_experiment` from the `run_all` module's namespace. However, inside `run_all_function`, the code does:

```python
from run_experiment import run_one_experiment
...
summary = run_one_experiment(config)
```

Wait no — `run_all.py` imports `run_one_experiment` at the top: `from run_experiment import run_one_experiment`. So `run_all.run_one_experiment` is the name in `run_all`'s namespace. When I `monkeypatch.setattr(run_all, "run_one_experiment", fake_run_one)`, that should replace it.

But the error says "Experiment config must have a non-empty 'video_path'" — that's from `load_config`! Looking at `run_all_function`:

```python
config = load_config(config_path)
summary = run_one_experiment(config)
```

It calls `load_config(config_path)` BEFORE calling `run_one_experiment`. My fake `run_one_experiment` never gets to run because `load_config` fails first (the test yaml files only have `name: ok`, no `video_path`).

I need to either:
1. Make the test yaml files valid (add `video_path` and prompts), OR
2. Monkeypatch `load_config` too, OR
3. Have the fake `run_one_experiment` accept a path instead of a config

The cleanest: monkeypatch both `load_config` and `run_one_experiment` in `run_all`, returning a simple object with a `.name` attribute.

The `run_all` test fails because `run_all_function` calls `load_config()` before `run_one_experiment()`, and my minimal YAML configs lack `video_path`. I need to also stub `load_config`. Fixing:

**Tool: edit**

---

## Assistant

Now fix the `run_one_experiment` test — the issue is `run_one_experiment` calls `setup_mlflow()` with the default URI, overriding the test's tracking URI. I need to add a `tracking_uri` param to `run_one_experiment`:

**Tool: edit**

---

## Assistant

Also update `run_all.py` to pass `tracking_uri` through to `run_one_experiment`:

**Tool: edit**

---

## Assistant

Now update the end-to-end test to pass `tracking_uri` to `run_one_experiment`:

**Tool: edit**

---

## Assistant

**Tool: grep**

---

## Assistant

The other two calls also need the tracking_uri. Let me updatethem:

**Tool: read**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

The fake `run_one` needs to accept the `tracking_uri` kwarg now that `run_all` passes it. Fixing:

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

All 16 experiments tests pass. Now let me run the **entire** test suite (production + experiments) together to confirm nothing is broken across the board.

**Tool: bash**

---

## Assistant

**77 tests passed** (61 production + 16 experiments), zero failures. Let me also verify the Dockerfile still builds correctly (no experiments code leaking into the image) and check `.dockerignore`:

**Tool: read**

---

## Assistant

The Dockerfile only copies `src/` and `requirements.txt` — and `.dockerignore` doesn't need `experiments/` added because the `COPY src ./src` in the Dockerfile only copies the `src/` directory. But to be safe and explicit per EXPERIMENT_TRACKING.md ("does not ship in the production Docker image"), let me add `experiments/` to `.dockerignore`:

**Tool: edit**

---

## Assistant

Finally, let me update the README to document the experiments harness — your instructions and EXPERIMENT_TRACKING.md's acceptance criteria require that running the tool isdocumented.

**Tool: read**

---

## Assistant

**Tool: edit**

---

## Assistant

Final full-suite run to confirm everything green:

**Tool: bash**

---

## Assistant

**Tool: todowrite**

---

## Assistant

## ✅ Item 2 complete — check-in summary

Built the experiment-tracking harness from scratch under `experiments/`, independent of the production pipeline. Full test suite (production + experiments) green at **77 passed**.

### Files created

- **`experiments/harness.py`** — config loading + MLflow setup. Defines `ExperimentConfig`/`FrameSamplingConfig`/`ModelConfig`, `load_config()` (YAML, inline or file-backed prompts, defaults to production constants for omitted sections), `apply_overrides()` (CLI overrides), `setup_mlflow()` (file-based tracking, sets `MLFLOW_ALLOW_FILE_STORE=true` for MLflow 3.x compat, creates the `video_captioning_cvr_experiments` experiment).
- **`experiments/run_experiment.py`** — single-run CLI. Runs one config inside one `mlflow.start_run`: logs params (model names, temperatures, max_tokens, num_frames, max_resolution, fallback_fps, video_path), logs prompt text as artifacts (`system_prompt.txt`, `user_prompt_template.txt`), reuses Task 6 (`inspect_video` + `sample_frames`) + Task 7 (`FireworksCvrClient` with config kwargs) + Task 8 (`parse_cvr_response`) + Task 10 (`FireworksStyleClient` + `generate_all_captions`), logs `cvr_latency_seconds`/`style_latency_seconds` metrics + `cvr_raw.txt`/`cvr_output.json`/`style_captions.json` artifacts, prints summary to stdout. CVR parse failure aborts; style-gen failure logs partial captions. CLI: `--config`, `--tracking-uri`, `--video-path`, `--num-frames`, `--max-resolution`, `--fallback-fps`.
- **`experiments/run_all.py`** — batch runner. Discovers `*.yaml`/`*.yml` in `experiments/configs/`, runs each sequentially as its own MLflow run, isolates per-config failures (one fails → logged + next continues), returns summary with pass/fail counts. CLI exit code is 1 if any config failed.
- **`experiments/configs/exp_example.yaml`** — fully-annotated example config.
- **`experiments/requirements.txt`** — `mlflow>=2.9,<4`, `pyyaml>=6,<7` (dev-only; not in production `requirements.txt`).
- **`experiments/tests/conftest.py`** — puts `src/` + `experiments/` on `sys.path`.
- **`experiments/tests/test_harness.py`** (9 tests) — config loading (inline/file-backed/both/missing/overrides), `apply_overrides`, `setup_mlflow` file-based + experiment creation + non-file URI rejection.
- **`experiments/tests/test_run_experiment.py`** (3 tests) — end-to-end with **real** `inspect_video`/`sample_frames` against a tiny synthetic mp4 fixture (proving the reuse contract) + **mocked** Fireworks HTTP via `requests.Session`; asserts MLflow params/metrics/artifacts are logged to one run_id, both CVR + 4 style calls happen (5 posts), CVR-parse-failure aborts before style stage, missing video raises.
- **`experiments/tests/test_run_all.py`** (4 tests) — config discovery (sorted, filtered), per-config failure isolation + pass/fail accounting, empty dir handling.

### Files changed

- **`src/video_captioning_agent/cvr_client.py`** — additive optional kwargs (`system_prompt`, `user_prompt_template`, `model_id`, `temperature`, `max_tokens`) on `build_cvr_request()` and `FireworksCvrClient.__init__()`, all defaulting to current constants. Zero behavior change when called with no kwargs (as `pipeline.py` does). Extracted `CVR_USER_PROMPT_TEMPLATE` as a named module constant (previously inline). Exported via `__init__.py`.
- **`src/video_captioning_agent/style_generator.py`** — same additive-kwarg pattern on `build_style_request()` and `FireworksStyleClient.__init__()` (`system_prompt`, `model_id`, `temperature`, `max_tokens`), so the style stage is also config-swappable per `EXPERIMENT_TRACKING.md`. Defaults preserve production behavior.
- **`tests/test_cvr_client.py`** — +2 tests confirming (a) default kwargs reproduce constant-based behavior byte-for-byte, (b) each kwarg overrides its constant in the constructed request.
- **`.gitignore`** — added `experiments/mlruns/` (tracked runs not committed).
- **`.dockerignore`** — added `experiments/` (dev tooling not in Docker image, per EXPERIMENT_TRACKING.md scope).
- **`README.md`** — added "Experiment tracking (dev-only)" section + updated project layout + updated test commands (`PYTHONPATH=src:experiments` for experiments tests).

### Test results
- Production suite: **61 passed** (includes the 2 new cvr_client additive-kwarg tests)
- Experiments suite: **16 passed**
- **Combined: 77 passed**, zero failures, zero skips

### Reuse verification (per EXPERIMENT_TRACKING.md acceptance criteria)
The experiments harness imports and calls directly from `src/`:
- `video_captioning_agent.video_inspection.inspect_video`
- `video_captioning_agent.frame_sampler.sample_frames`
- `video_captioning_agent.cvr_client.FireworksCvrClient` (with config-driven kwargs)
- `video_captioning_agent.cvr_parser.parse_cvr_response`
- `video_captioning_agent.style_generator.FireworksStyleClient` + `generate_all_captions`

No frame-sampling, request-construction, or CVR-parsing logic is reimplemented in `experiments/`. The production pipeline, `/input`→`/output` contract, `requirements.txt`, and `Dockerfile` are untouched.

### Open decisions resolved per your instructions
- **Both CVR (Task 7) and style-gen (Task 10)** tracked in the same MLflow experiment (`video_captioning_cvr_experiments`) — per your message.
- **File-based MLflow** (`file:./experiments/mlruns`) via `mlflow ui` — no server — per your message. `MLFLOW_ALLOW_FILE_STORE=true` is set inside `setup_mlflow()` to work around MLflow 3.x's maintenance-mode gate on the file store.

Both work items (1 and 2) are complete. Let me know if you'd like me to commit, or if there's anything you'd like adjusted.

---

## User

MLflow's plain filesystem tracking backend ('./mlruns') is now in maintenance
mode in the installed MLflow version and raises MlflowException on startup
unless a database backend is used instead. Update the experiment-tracking
harness accordingly:

1. Switch the tracking backend from plain filesystem to SQLite. Use
   `sqlite:///experiments/mlflow.db` as the backend store URI, with
   `./experiments/mlruns` as the artifact root (artifacts — the logged
   prompts and CVR JSON — still live as local files; only the tracking
   metadata moves into SQLite).
2. Update any documentation/comments in experiments/ that reference plain
   filesystem tracking to reflect this SQLite requirement.
3. Update the startup command (README or comments) to:
   mlflow ui --backend-store-uri sqlite:///experiments/mlflow.db --default-artifact-root ./experiments/mlruns
   This is still a lightweight, single-command local setup — it does not
   require running `mlflow server` as a background process; `mlflow ui` with
   a SQLite backend is sufficient for this project's sequential, single-user
   use case.
4. Confirm run_experiment.py and run_all.py set MLFLOW_TRACKING_URI (or the
   equivalent mlflow.set_tracking_uri() call) to this same SQLite URI, so runs
   logged via the CLI land in the same place the UI reads from.
5. Do not set MLFLOW_ALLOW_FILE_STORE=true as a workaround — follow MLflow's
   own recommended path (database backend) rather than opting out of it,
   since we want this to keep working on future MLflow versions too.

Run a test experiment end-to-end after this change to confirm the UI starts
cleanly and shows the run. 

---

## Assistant

I'll trace through all the places the file-based tracking URI is referenced and convert them to SQLite, then verify end-to-end.

**Tool: grep**

**Tool: grep**

---

## Assistant

I have a clear picture of all the touchpoints. Let me make all the edits:

1. `harness.py` — switch `DEFAULT_TRACKING_URI` to SQLite, update `setup_mlflow()` validation (require `sqlite:` scheme; drop `MLFLOW_ALLOW_FILE_STORE`), add artifact root handling.
2. Test files — switch URIs from `file:` to `sqlite:`.
3. Comments/docs in `run_experiment.py`, `run_all.py`, `README.md`.
4. `.gitignore` — add `experiments/mlflow.db`.

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

Now updating `run_experiment.py` help text:

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

Now the tests — switch all `file:` URIs to `sqlite:` and update the validation-errortest:

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

The fragment I copied includes a line marker. Let me use straightforward replacements:

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

Now update `.gitignore` to also exclude `experiments/mlflow.db`:

**Tool: edit**

---

## Assistant

Now update the README's "View runs in the MLflow UI"section:

**Tool: edit**

---

## Assistant

Let me also update the "Experiment tracking" section header description that says "MLflow-backed" to be consistent, and the harness output. Let me check if there's a stray "File-based tracking" reference in theREADME:

**Tool: grep**

---

## Assistant

Good — the remaining `file:` references in README are gone (the README section was updated). `experiment_tracking.md`'s "Open decisions" section still mentions the file-based option as an open question, but per your instruction #2 ("Update any documentation/comments in `experiments/`"), that's outside `experiments/` and is the original spec doc — I'll leave it since it's the source-of-truth spec you wrote. Now let me run the experiments tests toconfirm the SQLite switchworks:

**Tool: bash**

---

## Assistant

All 16 tests pass with SQLite. Now the end-to-end manual test: I'll run an actual experiment against the local Charades sample clip using `run_experiment.py` with the SQLite backend, then start `mlflow ui` and verify the run shows up.

First, let me check the sample clip exists and clean any prior `mlruns`/`mlflow.db`:

**Tool: bash**

---

## Assistant

The sample clip is present, but `FIREWORKS_API_KEY` is not set in this shell, so an actual end-to-end run against Fireworks will fail at the VLM call. Let me check whether a `.env` file exists that I couldsource:

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

Now let me first clean up any prior `mlruns/` / `mlflow.db` from earlier test runs and create a real config pointing at the sample clip, then run the experimentend-to-end:

**Tool: bash**

---

## Assistant

**Tool: write**

---

## Assistant

Now run the single-experiment CLI end-to-end with the SQLite backend (using `--num-frames 4` to keep the VLM call small/fast):

**Tool: bash**

---

## Assistant

The SQLite side worked perfectly (it created the DB + experiment). The failure is a 404 from Fireworks on the VLM call — likely because `accounts/fireworks/models/qwen2p5-vl-32b-instruct` isn't deployed under this account, or the model ID needs adjustment. This isn't a tracking-harness issue — the harness itselfinitialized SQLite and logged the run attempt.

Let me check what model ID the existing `fireworks_test_deployment.py` uses (since that's the script that's known to work per `AGENTS.md`), and also verify the SQLite DB has a run recorded even though the VLM call failed (which validates tracking works end-to-end):

**Tool: bash**

---

## Assistant

The SQLite backend is working: the `video_captioning_cvr_experiments` experiment was created and a run was recorded (the run that errored out is still logged — that's MLflow's behavior since `setup_mlflow` + `start_run` happened before the VLM call). But notice `experiments/mlruns/` doesn't exist — because the run failed before any artifact was logged, the artifact directory wasn't created. That's fine.

Now for the VLM 404 — let me check the working modeldeployment ID:

**Tool: read**

---

## User

only access current working directory and do work in current working directory

---

## Assistant

Understood — staying within the current working directory. The 404 from Fireworks is on the model-id (`accounts/fireworks/models/qwen2p5-vl-32b-instruct`) which is a downstream Fireworks deployment issue, not a tracking-harness issue.

The key thing I need to confirm per your instruction #4 is that the **harness sets `MLFLOW_TRACKING_URI` / calls `mlflow.set_tracking_uri()` to the same SQLite URI** the UI reads from. Let me verify that's the case end-to-end — confirm runs logged via the CLI land in `sqlite:///experiments/mlflow.db`, and that `mlflow ui` with that same backend reads them.

**Tool: grep**

---

## Assistant

Confirmed: `run_experiment.py` (line 57, 165) and `run_all.py` (line 43, 63) both default to `DEFAULT_TRACKING_URI = "sqlite:///experiments/mlflow.db"`, and `setup_mlflow()` calls `mlflow.set_tracking_uri(tracking_uri)` (line 197). This matches the README's `mlflow ui --backend-store-uri sqlite:///experiments/mlflow.db ...` command exactly.

Now let me verify the UI starts cleanly against this SQLite DB and shows the run. I'll start `mlflow ui` in the background, hit the REST API to confirm it returns the experiment + run, then shut itdown.

**Tool: bash**

---

## Assistant

The UI starts cleanly (HTTP 200) and reads the run from the SQLite backend. The earlier experimentlist came back empty due to the default `search` filtering (MLflow excludes the `Default` experiment from the top-level list view by default and the active-view filter), but the targeted query to `video_captioning_cvr_experiments` (experiment_id=1) returns the run we logged via the CLI — `exp_001_sqlite_e2e` with status `FAILED` (expected, since the Fireworks model-id 404'd). This confirms:

**The harness and the UI read from the same SQLite DB.** Runs logged via `run_experiment.py` / `run_all.py` (which call `mlflow.set_tracking_uri("sqlite:///experiments/mlflow.db")` via `setup_mlflow()`) are visible in `mlflow ui --backend-store-uri sqlite:///experiments/mlflow.db ...`.

Let me also run the full test suite one more time to confirm everything is green after the SQLite switch, and clean up the testartifacts:

**Tool: bash**

---

## Assistant

All **77 tests pass** (61 production + 16 experiments, now using SQLite).

## Summary of changes

Switched the experiment-tracking harness from MLflow's maintenance-mode filesystem backend to a SQLite database backend per your instructions. The harness now follows MLflow's recommended path instead of opting out of it.

### What changed

**`experiments/harness.py`** — Core change:
- `DEFAULT_TRACKING_URI` is now `"sqlite:///experiments/mlflow.db"` (was `file:./experiments/mlruns`).
- Added `DEFAULT_ARTIFACT_ROOT = "./experiments/mlruns"` — artifacts (logged prompts, CVR JSON) still live as local files; only tracking metadata moved to SQLite.
- `setup_mlflow()` now requires `sqlite:` URI scheme (was `file:`); removed `os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")` entirely — no workaround, following the database-backend recommendation for forward compatibility. Added `mlflow.set_registry_uri()` for completeness.
- Docstring rewritten to explain the SQLite + artifact-root split and why `mlflow ui` (not `mlflow server`) is sufficient.

**`experiments/run_experiment.py`** — Updated `--tracking-uri` help text to reflect `sqlite:` scheme and default `sqlite:///experiments/mlflow.db`.

**`experiments/run_all.py`** — Updated usage example + `--tracking-uri` help text to `sqlite:`.

**`experiments/tests/test_harness.py`** — Test renamed: `test_setup_mlflow_uses_sqlite_tracking_and_creates_experiment`; URI strings switched to `sqlite:///{tmp}/mlflow.db`; rejection test now checks for `"SQLite MLflow backend"` error and uses a `file:` URI as the rejected input.

**`experiments/tests/test_run_experiment.py`** (3 tests) — All `tracking_uri` literals switched from `file:{...}/mlruns` to `sqlite:///{...}/mlflow.db`.

**`experiments/tests/test_run_all.py`** (2 tests) — Mocked `setup_mlflow` and `run_all_function` URIs switched from `file:./mlruns` to `sqlite:///mlruns`.

**`README.md`** — "View runs in the MLflow UI" section rewritten: startup command is now `mlflow ui --backend-store-uri sqlite:///experiments/mlflow.db --default-artifact-root ./experiments/mlruns`; explains tracking metadata in SQLite, artifacts as files, no server process needed.

**`.gitignore`** — Added `experiments/mlflow.db` alongside `experiments/mlruns/`.

### End-to-end verification
1. **CLI run**: `python experiments/run_experiment.py --config ...` — created `experiments/mlflow.db` (SQLite tables initialized by MLflow), created the `video_captioning_cvr_experiments` experiment, and recorded a run. (The run's VLM call 404'd on Fireworks' side due to the model deployment ID — not a harness issue.)
2. **UI verification**: started `mlflow ui --backend-store-uri sqlite:///experiments/mlflow.db --default-artifact-root ./experiments/mlruns --port 5050` — started cleanly (HTTP 200), the REST API confirmed the run logged via the CLI is visible in the UI under the correct experiment.
3. **Test suite**: 77 passed.

The harness (`run_experiment.py` / `run_all.py`) calls `mlflow.set_tracking_uri("sqlite:///experiments/mlflow.db")` via `setup_mlflow()`, which is the exact URI the README's `mlflow ui` command reads from — confirmed end-to-end.

---

## User

(.venv) aditya@pop-os:~/dev-work/video-captioning-agent$ python3 experiments/run_experiment.py --config experiments/configs/exp_example.yaml
Traceback (most recent call last):
  File "/home/aditya/dev-work/video-captioning-agent/experiments/run_experiment.py", line 26, in <module>
    from video_captioning_agent.contracts import CanonicalVideoReport
ModuleNotFoundError: No module named 'video_captioning_agent' 

---

## Assistant

_Thinking:_

The error is because `experiments/run_experiment.py` imports from `video_captioning_agent` (which lives in `src/`), but the user ran `python3 experiments/run_experiment.py` without setting `PYTHONPATH=src`. The script needs to make `src/` importable on its own without requiring the user to set `PYTHONPATH`.

The cleanest fix: make the experiments scripts add `src/` to `sys.path` themselves at the top, so the user can run them directly without needing `PYTHONPATH=src`. This is a common pattern for dev scripts that live alongside but outside a `src/` package.

Let me check both `run_experiment.py` and `run_all.py` imports and add a small bootstrap at the top of each that inserts `src/` (relative to the script's own location) onto `sys.path`. The experiments tests have a `conftest.py` that does this already — I should mirror that pattern in the scripts themselves.

Let me look at the current top of both files to editthem.

The script needs `src/` on `sys.path` but doesn't add it itself — you'd have to manually prefix `PYTHONPATH=src:experiments`. The fix is to make the scripts bootstrap themselves by inserting `src/` onto `sys.path` (same pattern the experiments `conftest.py` already uses fortests).

**Tool: read**

---

## Assistant

**Tool: read**

---

## Assistant

I'll add a small `_bootstrap_sys_path()` helper to both scripts that inserts the repo's `src/` and the `experiments/` dir onto `sys.path`, computed relative to the script's own location (so it works regardless of the current working directory). Then `run_all.py` can drop the separate `experiments/` insert since importing `run_experiment` will have already donethat.

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

Now let me verify it works without `PYTHONPATH` set — running the CLI exactly as you did (no env prefix):

**Tool: bash**

---

## Assistant

Imports resolved cleanly with no `PYTHONPATH`. Let me confirm `run_all.py` also bootstraps and the full test suite still passes:

**Tool: bash**

---

## Assistant

Fixed. Both `experiments/run_experiment.py` and `experiments/run_all.py` now bootstrap `sys.path` themselves (inserting the repo's `src/` and `experiments/` dirs, resolved relative to each script's own location), so you can run them directly without `PYTHONPATH`:

```bash
python3 experiments/run_experiment.py --config experiments/configs/exp_example.yaml
python3 experiments/run_all.py
```

All 77 tests still pass.

---

## User

don't read the FIREWORKS_API_KEY, actually it's present in .env, its sensitive so i dont want you to read it. use load_dotenv() from dotenv module and then use that in run_experiment.py

---

## Assistant

_Thinking:_

The user wants me to use `load_dotenv()` from the `python-dotenv` module to load the `.env` file containing `FIREWORKS_API_KEY`, rather than me reading the `.env` file (which I never did - I only checked that it existed). They want this integrated into `run_experiment.py`.

Let me check if `python-dotenv` is available in the venv and if it's already in requirements. The AGENTS.md mentions `pip install python-dotenv` as an example dependency, so it's a known dependency. But it's not in the experiments `requirements.txt`. Since this is experiments tooling, I should add `python-dotenv` to `experiments/requirements.txt`.

Let me check if python-dotenv is installed.

**Tool: bash**

---

## Assistant

_Thinking:_

Good, `python-dotenv` is available. Now I need to:

1. Add `load_dotenv()` at the top of `run_experiment.py` (after the `_bootstrap_sys_path()` call but before the Fireworks clients are imported — since `FireworksCvrClient.__init__` reads `os.environ.get("FIREWORKS_API_KEY")` at construction time, not import time, so loading dotenv before constructing the clients is sufficient — but it's cleanest to load it as early as possible).

2. Add `python-dotenv` to `experiments/requirements.txt`.

The `load_dotenv()` call should happen before any code that reads `FIREWORKS_API_KEY` from the environment. The `FireworksCvrClient` and `FireworksStyleClient` constructors read it via `os.environ.get("FIREWORKS_API_KEY")` at construction time (in `_run_cvr_stage` and `_run_style_stage`), so loading dotenv at the start of `main()` or right after bootstrap would be fine. But it's cleanest to put it right after the bootstrap, before any imports that might need it.

Actually, looking more carefully: the Fireworks clients are imported at module level but their constructors are called inside functions. So as long as `load_dotenv()` runs before those functions are called, it works. The cleanest place is right after `_bootstrap_sys_path()` at module level, or at the start of `main()`. I'll put it right after bootstrap so the env is loaded before anything that might probe it.

Let me also check: should I add this to `run_all.py` too? `run_all.py` doesn't directly create any Fireworks clients — it calls `run_one_experiment` which does. And `run_experiment.py`'s `run_one_experiment` creates the clients. So if `load_dotenv()` is called in `run_experiment.py`, it'll be active when `run_all.py` imports `run_experiment` and calls `run_one_experiment`. But to be safe, I should add it to `run_all.py` too, in case someone runs `run_all.py` directly.

Actually, `run_all.py` imports `run_experiment` which at module level calls `load_dotenv()` — so by the time `run_all.py`'s code runs, dotenv is already loaded. But that's implicit. Better to explicitly add `load_dotenv()` in `run_all.py` too, right after its own `_bootstrap_sys_path()`.

Wait — but `run_all.py`'s `_bootstrap_sys_path` inserts paths, then it imports from `run_experiment`. If `run_experiment` calls `load_dotenv()` at module level (after its own `_bootstrap_sys_path()`), then by the time `run_all.py` finishes importing `run_experiment`, dotenv has already been loaded. So `run_all.py` doesn't strictly need its own `load_dotenv()`. But for clarity and robustness (e.g., if someone changes the import structure), I'll add it to both.

Actually, let me keep it simple: add `load_dotenv()` only in `run_experiment.py` since that's where the Fireworks clients are constructed. `run_all.py` imports from `run_experiment`, so the env will already be loaded. But the user specifically said "use that in run_experiment.py", so I'll put it there.

Let me put `load_dotenv()` right after `_bootstrap_sys_path()` in `run_experiment.py`. I need to import `load_dotenv` from `dotenv`. Since `python-dotenv` might not be in the experiments requirements, I'll add it.

Also note: `load_dotenv()` by default looks for `.env` in the current working directory. Since the user runs from the repo root, `.env` is there. That should work fine. I could also use `load_dotenv(Path(__file__).resolve().parent.parent / ".env")` to be explicit, but `load_dotenv()` with no args searches CWD and parent dirs, which is the standard behavior and should work fine here.

Let me keep it simple and just call `load_dotenv()` after bootstrap.

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

`run_experiment.py` now calls `load_dotenv()` right after bootstrapping `sys.path`, so `FIREWORKS_API_KEY` is loaded from `.env` automatically before the Fireworks clients are constructed. Added `python-dotenv>=1,<2` to `experiments/requirements.txt`. 77 tests still pass.

---

## User

let's say i want to edit some config and then run the experiment, then how can i change experiment name and then run it?

---

## Assistant

_Thinking:_

The user is asking how to change the experiment name and run it. Let me look at the config to understand how the `name` field works, and explain how to change it.

The `name` field in the YAML config becomes the MLflow `run_name` (passed to `mlflow.start_run(run_name=config.name)`). It's also logged as the `name` param.

But wait — there's a distinction here: the MLflow *experiment* name (`video_captioning_cvr_experiments`) is fixed in `harness.py` (`EXPERIMENT_NAME`), while the *run* name comes from `config.name`. The user is asking about changing the experiment name, which could mean either:
1. The run name (config's `name` field) — easy, just edit the YAML's `name:` line
2. The MLflow experiment name — currently hardcoded as `EXPERIMENT_NAME` in harness.py

Let me check if there's a CLI override for the run name... looking at the arg parser, there's `--video-path`, `--num-frames`, etc., but no `--name` override. So to change the run name, the user would edit the YAML's `name:` field.

Let me just answer concisely — edit the `name:` field in the YAML config.

Edit the `name:` field at the top of your config YAML — it becomes the MLflow run name:

```yaml
# experiments/configs/exp_example.yaml
name: my_new_experiment_name      # <- change this
video_path: ...
```

Then run:

```bash
python3 experiments/run_experiment.py --config experiments/configs/exp_example.yaml
```

Or copy the example to a new file and edit it:

```bash
cp experiments/configs/exp_example.yaml experiments/configs/exp_my_test.yaml
# edit experiments/configs/exp_my_test.yaml — change `name:` and any other fields
python3 experiments/run_experiment.py --config experiments/configs/exp_my_test.yaml
```

Note: the `name` field sets the **run name** (one row per run in the MLflow UI). All runs group under the single MLflow **experiment** `video_captioning_cvr_experiments` (fixed in `experiments/harness.py:14`), so different configs/runs are comparable side-by-side in that one experiment.

---

## User

Did you intentionally modify the system/user prompts from DESIGN.md §4.1/§4.2, or did these drift during implementation? Specifically: the "describe physical motion, not assumed purpose" clause and the "no markdown-wrapping" instruction are missing from the system prompt, and a new {metadata_json} block was added to the user prompt that wasn't in the original design. Restore the two missing system-prompt clauses exactly as written in DESIGN.md — those are safety-relevant, not stylistic. For the added metadata block, tell me why it was added; if it was a deliberate improvement, I'll decide whether to keep it, but it shouldn't have been added silently. 

---

## Assistant

_Thinking:_

The user is asking me to investigate whether I intentionally modified the system/user prompts from DESIGN.md, and clarify the situation. I'm in plan mode (read-only), so I should investigate by reading DESIGN.md §4.1/§4.2 and comparing to the current implementation. I must NOT edit anything — just analyze and report.

Let me read DESIGN.md to find §4.1 and §4.2, and compare with the current prompts in `src/video_captioning_agent/cvr_client.py`.

I'm in plan mode — I'll investigate without editing. Let me read DESIGN.md §4.1/§4.2 and compare against the current implementation.

**Tool: grep**

**Tool: read**

---

## Assistant

_Thinking:_

Wait — let me re-read the current `CVR_SYSTEM_PROMPT` carefully. Looking at lines 20-27:

```
CVR_SYSTEM_PROMPT = """You are a strict, objective video-understanding agent. Your sole purpose is to analyze sequences of video frames and generate a Canonical Video Report (CVR).

Core Directives:
1. OBSERVABLE FACTS ONLY: Describe only what is explicitly visible in the frames.
2. NO SPECULATION: Do not infer emotions, intentions, or off-screen events. If an action is ambiguous, describe the physical motion, not the assumed purpose.
3. NO HUMOR OR STYLE: The CVR must be completely dry, factual, and objective.
4. TEMPORAL AWARENESS: Pay close attention to the chronological order of frames to accurately construct the timeline of events.
5. STRICT JSON: You must output ONLY valid JSON matching the requested schema. Do not wrap the output in markdown code blocks and do not include any conversational text before or after the JSON."""
```

Hmm — actually both clauses ARE present:
- "describe the physical motion, not the assumed purpose" — IS present in clause #2
- "Do not wrap the output in markdown code blocks" — IS present in clause #5

So the user's claim that these are missing appears to be *incorrect* based on my reading of the current file. Let me double-check by reading DESIGN.md §4.1 to verify what the original design says, and compare carefully.

Let me read DESIGN.md §4.1 and §4.2.

Let me read DESIGN.md §4.1/§4.2 to compare against the current implementation (I'm in read-only planmode).

**Tool: read**

---

## Assistant

_Thinking:_

Now I have a clear picture. Let me carefully compare:

**DESIGN.md §4.1 (System Prompt):**
```
1. OBSERVABLE FACTS ONLY: Describe only what is explicitly visible in the frames. 
2. NO SPECULATION: Do not infer emotions, intentions, or off-screen events. If an action is ambiguous, describe the physical motion, not the assumed purpose.
3. NO HUMOR OR STYLE: The CVR must be completely dry, factual, and objective.
4. TEMPORAL AWARENESS: Pay close attention to the chronological order of frames to accurately construct the timeline of events.
5. STRICT JSON: You must output ONLY valid JSON matching the requested schema. Do not wrap the output in markdown code blocks (```) and do not include any conversational text before or after the JSON.
```

**Current implementation in `cvr_client.py` (lines 20-27):**
```
1. OBSERVABLE FACTS ONLY: Describe only what is explicitly visible in the frames.
2. NO SPECULATION: Do not infer emotions, intentions, or off-screen events. If an action is ambiguous, describe the physical motion, not the assumed purpose.
3. NO HUMOR OR STYLE: The CVR must be completely dry, factual, and objective.
4. TEMPORAL AWARENESS: Pay close attention to the chronological order of frames to accurately construct the timeline of events.
5. STRICT JSON: You must output ONLY valid JSON matching the requested schema. Do not wrap the output in markdown code blocks and do not include any conversational text before or after the JSON.
```

**The user's claim:** "the 'describe physical motion, not assumed purpose' clause and the 'no markdown-wrapping' instruction are missing from the system prompt"

**Reality based on the actual file content:**
- "describe the physical motion, not the assumed purpose" — IS present (clause #2, line 24)
- "Do not wrap the output in markdown code blocks" — IS present (clause #5, line 27)

So the user's premise is **factually incorrect**. Both clauses ARE present in the current implementation. The user is mistaken about this.

However, there IS one tiny difference in the system prompt: DESIGN.md §4.1 clause 5 says `"Do not wrap the output in markdown code blocks (\`\`\`) and do not include..."` with the literal ` ``` ` example, while the implementation says `"Do not wrap the output in markdown code blocks and do not include..."` — missing the literal ` ``` ` example. This is a *very minor* stylistic difference (the implementation dropped the literal triple-backtick example). That's a real but minor drift. The core instruction "do not markdown-wrap" is present.

Also clause #1 in DESIGN.md has a trailing space: "Describe only what is explicitly visible in the frames. " (trailing space) — the implementation doesn't have the trailing space. Trivial whitespace difference.

**Now for the User Prompt — this is where the real drift is:**

**DESIGN.md §4.2:**
```
Below are {num_frames} frames sampled from a {duration:.1f}-second video, presented in chronological order.

Frame Timestamps:
{frame_timestamps}

Analyze these frames and generate the Canonical Video Report (CVR). 

Return a JSON object with EXACTLY this structure:
{
  "scene": "Brief description of the location or environment (e.g., Kitchen, Outdoor street)",
  ...
}
```

**Current implementation:**
```
Below are {frame_count} frames sampled from a {duration_seconds:.1f}-second video, presented in chronological order.

Video Metadata:
{metadata_json}

Frame Timestamps:
{timestamp_lines}

Analyze these frames and generate the Canonical Video Report (CVR).

Return a JSON object with EXACTLY this structure:
{{
  "scene": "Brief description of the location or environment",
  ...
}}
```

Differences in the user prompt:
1. **Added `Video Metadata:\n{metadata_json}` block** — NOT in DESIGN.md §4.2. This is the "added metadata block" the user is asking about.
2. Placeholder renames (cosmetic, for `.format()`): `{num_frames}` → `{frame_count}`, `{duration:.1f}` → `{duration_seconds:.1f}`, `{frame_timestamps}` → `{timestamp_lines}`. Also `{{` / `}}` escaping for the JSON braces since `.format()` is used. These are mechanical, not semantic.
3. **Removed `(e.g., Kitchen, Outdoor street)` example** from the `scene` field description — DESIGN.md has it, implementation doesn't.

Now, regarding the "describe physical motion" and "no markdown-wrapping" claims — I need to honestly tell the user that those clauses ARE actually present in the current implementation. I shouldn't just agree with a false premise. I should show them the actual current content and tell them their premise is mistaken, then address the real drifts:
- The minor one: literal ` ``` ` example dropped from clause #5 (cosmetic — the instruction itself is present)
- The `Video Metadata:\n{metadata_json}` block added to the user prompt (a real addition)
- The `(e.g., Kitchen, Outdoor street)` example removed from the scene field description (a real removal)

I cannot edit in plan mode anyway. I need to:
1. Correct the user's premise factually (both clauses are present) — and point out where they can verify
2. Explain the actual differences I found
3. For the metadata block: explain why it was added (I need to check the git history / blame to see if this was an intentional addition or pre-existing). Since I'm in plan mode, I can use git blame to investigate without editing.

Let me be honest: I added the `CVR_USER_PROMPT_TEMPLATE` constant as a named module constant when making the additive-kwargs change for the experiments harness. But before that, the same user-prompt text (including the `Video Metadata:\n{metadata_json}` block) was already inline in `_build_cvr_user_prompt()` — I just extracted it verbatim into the constant. So the metadata block was NOT added by me; it was already in the existing Task 7 implementation that

---

