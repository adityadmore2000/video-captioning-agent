# Context: Experiment Tracking Harness for Prompt/Sampling Iteration (MLflow-backed)

## Goal

Build a lightweight experiment-tracking tool that lets me quickly iterate on:
- `SYSTEM_PROMPT` (the CVR system prompt from DESIGN.md §4.1)
- `USER_PROMPT` (the CVR user prompt template from DESIGN.md §4.2)
- Frame-sampling parameters (`num_frames`, `max_resolution`, `fallback_fps`)
- Model choice / generation parameters (`model_name`, `temperature`, `max_tokens`)
- `video_path`

...and run each variation against a real local sample video, with every run's exact configuration and resulting CVR persisted together — so I can see, in a spreadsheet-style table, which configuration produced which CVR, and compare runs side by side.

## Tracking backend: MLflow

Use **MLflow's experiment tracking** (`mlflow` Python package) as the backend, instead of hand-rolled JSONL/CSV files. Rationale: MLflow's runs table is natively a spreadsheet view (one row per run, params/metrics as columns), it's a single `pip install`, requires no additional infra (Postgres/ClickHouse/etc.), and it directly gives us param logging, artifact storage, and a built-in run-comparison UI — the exact combination of features this tool needs.

- Set up a local MLflow tracking server: `mlflow server --backend-store-uri sqlite:///experiments/mlflow.db --default-artifact-root ./experiments/mlruns --host 0.0.0.0 --port 5000` (or `mlflow ui` for a simpler local-only setup if a full server isn't needed).
- Use a dedicated MLflow experiment named `video_captioning_cvr_experiments` so these runs are grouped separately from anything else.

## Scope boundaries (important)

- This is **dev-only tooling** — it does not ship in the production Docker image (Task 14 in TASKS.md) and does not touch the `/input` → `/output` contract.
- It should live in its own directory (e.g. `experiments/`), separate from `src/` (the production pipeline).
- It must **reuse the existing production components** (frame sampler from Task 6, VLM client from Task 7) rather than reimplementing them — the point is to test the real pipeline's building blocks with swappable config, not build a parallel implementation.
- `mlflow` is the one new dependency this introduces — add it to the dev/experiments dependency group, not the production runtime dependencies used by the Docker image (Task 14).

## What to build

### 1. Config-driven experiment definition
A YAML (or JSON) config file per experiment, e.g. `experiments/configs/exp_001.yaml`:

```yaml
name: exp_001_baseline
video_path: /home/aditya/dev-work/video-captioning-agent/Data/Charades_v1_480/Charades_v1_480/001YG.mp4
system_prompt: |
  You are a strict, objective video-understanding agent...
user_prompt_template: |
  Below are {num_frames} frames sampled from a {duration:.1f}-second video...
frame_sampling:
  num_frames: 16
  max_resolution: 768
  fallback_fps: 1
model:
  name: accounts/fireworks/models/qwen2p5-vl-32b-instruct
  temperature: 0.1
  max_tokens: 1024
```

`system_prompt` and `user_prompt_template` adds a path to a separate `.md` file for easier editing of long prompts.

### 2. CLI runner
```bash
python experiments/run_experiment.py --config experiments/configs/exp_001.yaml
```
Optional override flags (e.g. `--video-path`, `--num-frames`) so I can quickly test one-off variations without editing the YAML.

The runner should, inside a single `with mlflow.start_run(run_name=...)` block (so config and output are atomically linked to one `run_id`):

1. Load the config.
2. Log the run's configuration via `mlflow.log_params(...)`:
   - `num_frames`, `max_resolution`, `fallback_fps`
   - `model_name`, `temperature`, `max_tokens`
   - `video_path`
3. Log `system_prompt` and `user_prompt_template` via `mlflow.log_text(...)` as artifacts (`system_prompt.txt`, `user_prompt_template.txt`) — these are logged as artifacts, not params, since MLflow params have a length limit unsuited to full prompt text.
4. Call the existing frame sampler (Task 6 code) with the config's sampling params, timing the call.
5. Call the existing VLM client (Task 7 code) with the config's prompts and model params, timing the call.
6. Log the resulting CVR via `mlflow.log_dict(cvr, "cvr_output.json")`.
7. Log `latency_seconds` (and token usage, if available in the API response) via `mlflow.log_metric(...)`.
8. Print the resulting CVR to stdout as well, for immediate feedback.

### 3. Viewing and comparing runs
No separate comparison script needs to be built — this is native to MLflow:
- **Runs table** in the MLflow UI (`http://localhost:5000`) shows one row per run, with every logged param/metric as a toggleable column — this is the spreadsheet view.
- **Click into a run** to view its `system_prompt.txt`, `user_prompt_template.txt`, and `cvr_output.json` artifacts directly in the browser — this answers "which config led to which CVR" per run.
- **Select multiple runs → Compare** shows a side-by-side table highlighting which params differ, alongside their metrics, for direct comparisons (e.g. `num_frames=8` vs. `num_frames=16` on the same video).
- **Export to CSV** is a built-in button on the runs table — no custom export script needed.

If a fuller written report is ever needed beyond browsing the UI, it can be generated programmatically:
```python
import mlflow
runs_df = mlflow.search_runs(experiment_names=["video_captioning_cvr_experiments"])
runs_df.to_csv("experiment_report.csv", index=False)
```

## Acceptance criteria

- I can change `SYSTEM_PROMPT` or `USER_PROMPT` purely via config/file edit, with no code changes needed.
- I can change frame count, resolution, or fallback fps purely via config.
- I can point at the local sample video (or any other video path) via config or CLI flag.
- Every run's config, prompts, CVR output, and latency are logged to MLflow under a single `run_id`, viewable and comparable in the MLflow UI without any custom export script.
- The harness calls the real frame-sampling and VLM-client code from `src/` — it does not duplicate that logic.
- Running this tool has no effect on the production pipeline, its tests, or the Docker build.
- `mlflow` is only a dependency of the experiments tooling, not of the production Docker image.

## Open decisions coding-agent should ask me about, not assume

- Whether to also track style-generation (Task 10) experiments in the same MLflow experiment, or keep this scoped to CVR generation only for now.
- Whether to run a persistent local MLflow server (`mlflow server`, SQLite backend) or use the simpler file-based `mlflow ui` pointed at a local `mlruns/` directory — the former supports concurrent runs better, the latter needs zero setup.
