# Session Summary

## Objective
Investigate the `mlruns/` directory to extract and compare latency achieved by two Fireworks-hosted models (`gpt-oss-20b` and `qwen-2.5-vl-32b`) across experiment runs.

## Project State Before Session
- The project had a functioning MLflow experiment tracking pipeline (`experiments/run_experiment.py`) that logged CVR and style generation latency as metrics.
- Two experiments existed: `video_captioning_cvr_experiments` (exp 1) and `video_captioning_cvr_experiments_v2` (exp 2), the latter later subdivided into named sub-experiments like `exp_qwen_x_gpt_oss_20b`.
- Multiple custom Fireworks deployments had been created (e.g. `ynb0xtxw`, `j8n04pmq`, `e7g2xwfe`, `ks6i10e2`, `gby0ppfz`, `wg7je874`, `svfxk7pz`) with no in-repo documentation of which base model each maps to.
- Artifacts were stored in `mlruns/` (local directory tree), while metrics/params/tags were stored in a SQLite backend (`experiments/mlflow.db`).
- Git history showed an evolution: the earliest example config used public Fireworks model endpoints; later commits replaced them with opaque custom deployment IDs.

## Major Achievements
- Discovered that MLflow metrics lived in SQLite, not in the `mlruns/` file tree (which only held artifacts).
- Queried the SQLite database to extract all 8 runs that had latency data.
- Identified that Experiment 1 logged no latency metrics at all (only artifacts), making it impossible to compare directly with Experiment 2.
- For explicitly-identified `gpt-oss-20b` style model runs: style latency was 33.34s (max_tokens=256) and 50.04s (max_tokens=2048).
- For custom CVR deployments in the `exp_qwen_x_gpt_oss_20b` experiment (implied to be Qwen-based): CVR latencies ranged from 6.58s to 8.34s at 8 frames, 768 max resolution.
- Documented the opacity problem: deployment IDs have no in-repo mapping to base model names.

## Engineering Decisions
- **SQLite backend for metrics** (already in place): Metrics were stored in a SQLite DB rather than the local filesystem `mlruns/` tree. This was not a visible decision but was discovered during investigation as a consequence of how `mlflow.log_metric()` was configured.
- **Use of custom Fireworks deployments**: The project moved from using public model endpoints (e.g. `accounts/fireworks/models/qwen2p5-vl-32b-instruct`) to custom deployment IDs. This adds flexibility for fine-tuned or custom-configured models but makes experiment results opaque without external documentation.

## Architecture Changes
None. This session was purely investigative.

## Implementation Progress
No code was written. The investigation produced a latency comparison table and surfaced the lack of deployment-to-model mapping documentation.

## Problems / Bugs / Limitations
- **Missing latency data in Experiment 1**: Runs using explicit public model IDs (`qwen2p5-vl-32b-instruct`, `gpt-oss-120b`) have no latency metrics logged, only artifacts. This is likely because those runs predate the addition of `mlflow.log_metric("cvr_latency_seconds", ...)` to the experiment harness.
- **Opaque deployment IDs**: Custom Fireworks deployment IDs (`e7g2xwfe`, `ks6i10e2`, `ynb0xtxw`, `j8n04pmq`, etc.) cannot be mapped to base model names from the repository alone. The experiment name `exp_qwen_x_gpt_oss_20b` provides hints, but it's not authoritative.
- **Model naming inconsistency**: Within the same experiment, style model is sometimes explicit (`accounts/fireworks/models/gpt-oss-20b`) and sometimes a custom deployment ID. This makes cross-run comparison unreliable.

## Debugging / Investigation
- Explored the `mlruns/` directory tree (found artifacts: `cvr_raw.txt`, `cvr_output.json`, `cvr_parse_failure.json`, `style_captions.json`, system prompts).
- Found no `meta.yaml`, `metrics/`, `params/`, or `tags/` directories in the file tree.
- Used `grep` to find `mlflow.log_metric` in `run_experiment.py`, confirming metrics were being logged.
- Discovered the SQLite database `experiments/mlflow.db` and queried it with `sqlite3` to extract: experiments, params, metrics, and tags.
- Used `git log` and `git show` on recent commits to trace the evolution from public model endpoints to custom deployment IDs.
- Cross-referenced the example config (in various git revisions) with DB data to infer which deployments might be which model.

## Important Insights
- **MLflow dual storage**: When using a SQLite tracking URI, metrics/params/tags go into the database, while artifacts go into the `mlruns/` directory. Inspecting only the file tree gives an incomplete picture.
- **Experiment naming as weak documentation**: The experiment name `exp_qwen_x_gpt_oss_20b` is the only clue linking custom deployments to base models. This is fragile and should be replaced with explicit tags or a config file.
- **Latency varies significantly with max_tokens for style generation**: 33.34s at max_tokens=256 vs 50.04s at max_tokens=2048 for gpt-oss-20b — a ~50% increase.
- **CVR latency scales with frame count**: 3.23s (1 frame) → 7.29s (8 frames) → 11.44s (16 frames) for the same (unknown) CVR model.

## Project State After Session
No files were modified. A manual understanding of the latency landscape was produced. The project gained visibility into a data quality issue: experiment 1 is missing metric data, and custom deployment IDs are undocumented.

## Interview-Worthy Talking Points
- Migrating from public model endpoints to custom deployments: tracing the impact on experiment reproducibility.
- MLflow dual-storage pitfall: file tree inspection alone misses metrics when SQLite backend is used.
- The importance of logging experiment metadata (model name, deployment ID, config) as tags so experiments remain interpretable without external docs.
- Latency vs. token budget: max_tokens doubling (256→2048) drove style latency up ~50%, not the ~8x a naive model would suggest — what does this imply about generation overhead?
- Using `git log` and `git show` as an investigative tool to trace when and why deployment choices changed.

## Keywords
MLflow, SQLite, experiment tracking, latency benchmarking, Fireworks AI, gpt-oss-20b, qwen-2.5-vl-32b, custom deployment, opaque deployment IDs, mlruns, CVR pipeline, style generation, frame sampling, max_tokens, artifacts, metrics logging, experiment reproducibility, `sqlite3`, git archaeology

## Presentation Assets
- **Comparison table** — 8 runs with latency, model IDs, max_tokens, and frame count — could be a slide summarizing CVR vs style latency across configurations.
- **Bar chart** — CVR latency by frame count (1, 8, 16 frames) showing linear-ish scaling.
- **Architecture diagram** — MLflow dual-storage layout: SQLite (metrics/params/tags) vs filesystem (artifacts) — useful for onboarding.
- **Timeline** — Git history showing the evolution from public endpoints to custom deployments, annotated with which experiment configs were used when.
- **Debugging case study** — "Why does Experiment 1 have no latency data?" — the process of ruling out file tree inspection, finding SQLite, and discovering that the metric logging code was added later.
