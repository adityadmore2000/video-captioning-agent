# New session - 2026-07-20T11:09:29.774Z

**Session ID:** ses_080c886d1ffeQ2ZTfH0G8AvEJl
**Created:** 7/20/2026, 4:39:29 PM
**Updated:** 7/20/2026, 4:44:05 PM

---

## User

can you inspect mlruns folder and explain to me how much latency i have achieved with gpt-oss-20b and qwen-2.5-vl-32b model?

---

## Assistant

_Thinking:_

The user wants me to inspect the `mlruns` folder to analyze latency data for two models: `gpt-oss-20b` and `qwen-2.5-vl-32b`. Let me first explore the `mlruns` directory structure to understand what's there.

I'm in plan mode, so I can only read and inspect files - no modifications.

**Tool: read**

---

## Assistant

_Thinking:_

There are two subdirectories `1/` and `2/`. Let me explore further to understand the structure.

**Tool: bash**

**Tool: read**

**Tool: read**

---

## Assistant

_Thinking:_

This is MLflow tracking data. Each experiment has runs under it. Let me look at the MLflow metadata files to understand which experiment corresponds to which model. MLflow stores experiment metadata in the `mlruns` directory. Let me look at the experiment metadata and run tags/data.

**Tool: glob**

**Tool: glob**

---

## Assistant

_Thinking:_

No meta.yaml files found. Let me check what files exist under the individual run directories.

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

MLflow typically stores metadata in format-specific files. Let me look deeper - sometimes MLflow uses `MLproject` files or the data is stored within the run directories. Let me check the full file listing more thoroughly and also look at the content of the artifacts to understand what model each run was using.

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

I see a lot of artifact files. Let me look at the system prompts and some cvr_output files to understand which model each run used, and find timing/latency information. Let me also look for any MLflow metadata that tells us about experiments.

Let me check the system prompts first - they might reference the model.

**Tool: task**

---

## Assistant

_Thinking:_

The task seems to have completed but returned no output. Let me check the content directly myself.

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

_Thinking:_

The cvr_output.json files don't contain latency data - they contain the model output (scene descriptions). The system prompts also don't indicate which model. Let me look for MLflow's internal data files - MLflow stores metrics, params, and tags in a specific format. Let me check if there are hidden files or files in the run directories that have this data.

MLflow stores data as:
- metrics: mlruns/<experiment_id>/<run_id>/metrics/*
- params: mlruns/<experiment_id>/<run_id>/params/*
- tags: mlruns/<experiment_id>/<run_id>/tags/*

Let me search for these directories properly.

**Tool: bash**

---

## Assistant

_Thinking:_

No metrics/params/tags directories. This is unusual for MLflow. Let me check if there are any hidden files/directories.

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

So there are no standard MLflow metadata files (meta.yaml, metrics, params, tags) - each run only has an `artifacts/` directory. This means the latency data might be stored inside the artifacts themselves. Let me check the `cvr_raw.txt` files - they might contain the raw LLM response with timing info, or maybe check the `style_captions.json` or the `cvr_parse_failure.json` files.

Let me also look for any Python script that uses MLflow to see how data is logged.

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: grep**

---

## Assistant

_Thinking:_

Now I have a much clearer picture. The key file is `experiments/run_experiment.py`. Let me look at it more closely to understand the experiment config and see where model names are configured. The latency data is logged via `mlflow.log_metric("cvr_latency_seconds", cvr_latency)` - so the metrics are stored in a SQLite database (`experiments/mlflow.db`), not in the `mlruns` directory directly. Let me check the experiment configs and then query the MLflow DB.

**Tool: read**

**Tool: glob**

**Tool: glob**

**Tool: glob**

---

## Assistant

_Thinking:_

The latency data is in the SQLite DB at `experiments/mlflow.db`, not in the `mlruns` directory (the `mlruns` directory is just a local file store for artifacts). The metrics are stored in the SQLite DB. Let me read the experiment config and query the SQLite DB to extract latency data.

**Tool: read**

**Tool: bash**

---

## Assistant

_Thinking:_

The SQLite DB has the standard MLflow schema. Let me query the experiments, params, and metrics tables.

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

Now I need to figure out which deployment IDs correspond to which models. Let me look at the experiment tags and also get the full picture on the deployments. Let me match the deployment names from the example config to understand which deployment is which model.

From the example config:
- `cvr_model.name: accounts/adityadmore2000-x698/deployments/ynb0xtxw` 
- `style_model.name: accounts/adityadmore2000-x698/deployments/j8n04pmq`

And I can see from the run data:
- `accounts/fireworks/models/qwen2p5-vl-32b-instruct` - Qwen 2.5 VL 32B (official Fireworks model)
- `accounts/fireworks/models/gpt-oss-120b` - GPT-OSS-120b
- `accounts/fireworks/models/gpt-oss-20b` - GPT-OSS-20b
- `accounts/adityadmore2000-x698/deployments/ynb0xtxw` - custom deployment (from example, this looks like it could be for Qwen)
- `accounts/adityadmore2000-x698/deployments/j8n04pmq` - custom deployment (from example, this looks like for gpt-oss-20b)

Now I need to understand what models correspond to the exp_qwen_x_gpt_oss_20b runs. Let me build a more comprehensive query.

Looking at the data:
- Experiment 1 (video_captioning_cvr_experiments): qwen2p5-vl-32b-instruct and gpt-oss-120b
- Experiment 2 (video_captioning_cvr_experiments_v2): multiple models.

For "gpt-oss-20b" specifically:
- Style model: `accounts/fireworks/models/gpt-oss-20b`
- But the CVR model is custom deployments

For "qwen-2.5-vl-32b" specifically:
- `accounts/fireworks/models/qwen2p5-vl-32b-instruct`
- Also custom deployments of it

Let me get the full picture by querying all the deployment mappings, the experiment names, and understanding which runs belong to which experiment + model combination.

Let me check the experiment_tags for the experiment names and also look at the full runs data.

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

Now I need to figure out what these deployment IDs map to. Let me look at the example config and understand the deployments. The example config shows:
- `accounts/adityadmore2000-x698/deployments/ynb0xtxw` for `cvr_model`
- `accounts/adityadmore2000-x698/deployments/j8n04pmq` for `style_model`

And the comments say Qwen2.5-VL 32B for CVR, gpt-oss-120b for style generation.

Let me check the run_experiment.py harness to see how the config handles model names, and also look at the upload_model_to_fireworks.py to understand what model was uploaded with what deployment name.

Actually, let me also check if there's any additional mapping in the configs or in the experiment artifacts.

**Tool: grep**

**Tool: grep**

---

## Assistant

_Thinking:_

The deployment IDs aren't directly mapped in code. Let me check the `upload_model_to_fireworks.py` to see if there are any deployment names mentioned.

**Tool: read**

**Tool: read**

---

## Assistant

_Thinking:_

Now I have a better picture. The configuration has deployment IDs that are opaque - but I can infer some of them from the data. Let me check the tags table to see if there's any additional metadata about which deployment maps to which model.

Actually, the key insight is: the `cvr_model_name` and `style_model_name` params have the actual model IDs. Let me run a comprehensive query that groups all runs by experiment and model type and gives the latency stats. The ones the user cares about are:

1. **gpt-oss-20b** - seen in style_model as `accounts/fireworks/models/gpt-oss-20b`
2. **qwen-2.5-vl-32b** - seen as `accounts/fireworks/models/qwen2p5-vl-32b-instruct`

From the metrics table, I need to match runs to model names. Let me get a full clean query.

**Tool: bash**

---

## Assistant

_Thinking:_

OK, so the issue is that many custom deployment names aren't mapped to model names. The ones that are explicitly `accounts/fireworks/models/qwen2p5-vl-32b-instruct` or `accounts/fireworks/models/gpt-oss-20b` are clearly identifiable.

But many custom deployments (like `e7g2xwfe`, `gby0ppfz`, `ks6i10e2`, etc.) are not identifiable from the code alone.

From the example config:
- `ynb0xtxw` is the CVR model (default Qwen2.5-VL 32B)
- `j8n04pmq` is the style model (default gpt-oss-120b)

But those are just defaults. The custom deployments don't tell us what model they are.

However, looking at the `exp_qwen_x_gpt_oss_20b` runs, many of them have `style_model_name = gpt-oss-20b` for the style model. For example:
- Run `356727511...`: cvr=custom/`e7g2xwfe`, style=**gpt-oss-20b**, cvr_latency=6.58s, style_latency=33.34s
- Run `ce3bb8ee...`: cvr=custom/`ks6i10e2`, style=**gpt-oss-20b**, cvr_latency=8.34s, style_latency=50.04s

But there are also runs like:
- Run `4a12d4de...`: cvr=custom/`wg7je874`, style=custom/`wg7je874`, cvr_latency=11.44s, style_latency=6.01s
- Run `70b132bd...`: cvr=custom/`gby0ppfz`, style=custom/`gby0ppfz`, cvr_latency=3.23s, style_latency=4.47s

The question is about "gpt-oss-20b" and "qwen-2.5-vl-32b". Let me filter to runs where these are clearly identifiable.

For **qwen-2.5-vl-32b** (as CVR model):
- `accounts/fireworks/models/qwen2p5-vl-32b-instruct` - but these runs don't have latency data recorded.

For **gpt-oss-20b** (as style model):
- `accounts/fireworks/models/gpt-oss-20b` - these have style_latency data.

Wait, some custom deployments might be the same model but with different configurations. Let me look at the setup more carefully. Perhaps the answer here is simpler - let me look at the runs that have metrics logged (many runs don't have latency metrics at all, only artifacts).

Let me do a comprehensive query to get ALL runs that have both model info and latency info.

**Tool: bash**

---

## Assistant

_Thinking:_

OK, so 8 runs have latency data. Now let me try to map the custom deployments to actual model names. Let me look at the tags for these runs - MLflow should have some tags.

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

OK, let me now think about which deployments map to which models.

Looking at the example config (`exp_example.yaml`):
- `cvr_model.name: accounts/adityadmore2000-x698/deployments/ynb0xtxw` - this is a custom deployment of Qwen2.5-VL-32B (the comment says the default for CVR is Qwen2.5-VL 32B)
- `style_model.name: accounts/adityadmore2000-x698/deployments/j8n04pmq` - this is a custom deployment of gpt-oss-120b (or gpt-oss-20b)

The run `c8156dfc88fb4a599635bf1fa742beb6` uses `ynb0xtxw` for CVR and `j8n04pmq` for style, matching the example config. This is likely Qwen2.5-VL-32B for CVR and gpt-oss-20b for style.

Now for the exp_qwen_x_gpt_oss_20b runs specifically:
- Run `356727511...`: cvr=`e7g2xwfe`, style=`gpt-oss-20b` → We know style is gpt-oss-20b. CVR is a custom deployment.
- Run `ce3bb8ee...`: cvr=`ks6i10e2`, style=`gpt-oss-20b` → Same, style is gpt-oss-20b.

These are probably testing different CVR models (custom deployments) with GPT-OSS-20b as the style model.

For the runs where both models are the same deployment (wg7je874, gby0ppfz, svfxk7pz), these are probably using the same model for both CVR and style generation.

Let me now look at the git commit history and the run files to better understand. Actually, let me just look at what the user is asking. They said "gpt-oss-20b" and "qwen-2.5-vl-32b". 

From the data I can see:
1. **qwen2.5-vl-32b** explicitly used as CVR model: Runs in experiment 1 (but no latency data recorded for those).
2. **gpt-oss-20b** explicitly used as style model: Runs `356727511...` and `ce3bb8ee...` in experiment 2.

But also, the custom deployments could be Qwen or gpt-oss models uploaded to Fireworks. Let me check if there's any documentation about this.

Let me also check the docs/ folder for relevant notes.

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

Now I have a much clearer picture. Let me look at the docs to see if there's any explanation linking the deployments to models.

**Tool: read**

**Tool: read**

---

## Assistant

_Thinking:_

Those docs aren't helpful for the deployment mapping. Let me look at the example config comment more carefully - it says:

> "All sections except `name` and `video_path` are optional and default to the production constants from `src/` (Qwen2.5-VL 32B Instruct for CVR, gpt-oss-120b for style generation)."

So the default for CVR is Qwen2.5-VL 32B. And the default for style model is gpt-oss-120b.

But in the example config, `ynb0xtxw` is listed as the CVR model and `j8n04pmq` as the style model. These are custom deployments.

Now for the `exp_qwen_x_gpt_oss_20b` runs, the name suggests "qwen x gpt-oss-20b", meaning Qwen for CVR and GPT-OSS-20B for style.

Looking specifically at runs where `style_model = gpt-oss-20b`:
- `356727511...`: cvr=`e7g2xwfe` (unknown custom), style=`gpt-oss-20b` → cvr_latency=6.58s, style_latency=33.34s (style_max_tokens=256)
- `ce3bb8ee...`: cvr=`ks6i10e2` (unknown custom), style=`gpt-oss-20b` → cvr_latency=8.34s, style_latency=50.04s (style_max_tokens=2048)

The difference in style latency (33s vs 50s) is likely due to different max_tokens settings (256 vs 2048).

For the runs where both models are custom and may or may not be the models the user asked about:
- `ynb0xtxw` (CVR) and `j8n04pmq` (style) - used by runs `c8156dfc...` and `9770dda7...` - these look like they match the example config (Qwen for CVR, gpt-oss for style). CVR latency ~7.6s, style latency ~11.7-15.8s.

Without knowing exactly what each custom deployment maps to, I should present the data as it is and note what's identifiable.

Let me do one more check - look at the commit history to see if there's any context about what the different deployment IDs are.

**Tool: bash**

---

## Assistant

_Thinking:_

Interesting - commit `c544771` says "feat(deployment): add dedicated setup script for Fireworks deployments and update experiment config" and `6b2f7a3` says "feat(pipeline): enhance task orchestration with concurrent style generation and failure isolation".

Let me check that commit for deployment mappings.

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

Let me check the config changes in those commits to see what deployments were set.

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

So there are lots of different custom deployments that were created for different experiments with different configurations. Without explicit mapping documentation, it's hard to know exactly which base model each deployment maps to.

However, looking at this more carefully:
- The example config in its EARLIEST form (commit `bb965e9`) used `accounts/fireworks/models/qwen2p5-vl-32b-instruct` for CVR and `accounts/fireworks/models/gpt-oss-120b` for style.
- Later commits swapped to custom deployment IDs.

For the `exp_qwen_x_gpt_oss_20b` experiments, the style model is explicitly `accounts/fireworks/models/gpt-oss-20b`. The CVR models are various custom deployments that were likely qwen2.5-vl-32b (as the name implies "qwen x gpt-oss-20b").

Let me look at the latest version of the example config and see what the actual configs used were. Also, let me check the harness to see the experiment name logic.

**Tool: bash**

**Tool: read**

---

## Assistant

_Thinking:_

Now I see that the latest version of the config (commit `093495a`) has CVR model `accounts/adityadmore2000-x698/deployments/lf5r25lg` and style model `accounts/adityadmore2000-x698/deployments/v575ufos`. These deployments are not directly identifiable from the code.

However, looking at the DB data, the runs use many different deployment IDs. Without a deployment-to-model-name mapping, I can only report on runs where the model name is explicitly identifiable (like `accounts/fireworks/models/gpt-oss-20b` or `accounts/fireworks/models/qwen2p5-vl-32b-instruct`).

Let me summarize what I can determine:

**For gpt-oss-20b (as style model, explicitly identified):**
Run `356727511...`: style_latency = 33.34s (with style_max_tokens=256)
Run `ce3bb8ee...`: style_latency = 50.04s (with style_max_tokens=2048)

**For qwen2.5-vl-32b (explicitly identified as CVR model):**
Runs in experiment 1 but NO latency data was recorded for these runs.

Wait, that can't be right. Let me re-examine.

There are runs in experiment 1 (`bfd66aff`, `e6ec592`, `77f2f613`) and experiment 2 (`cb83d02d`, `9fda2f4d`) that use the explicit `accounts/fireworks/models/qwen2p5-vl-32b-instruct` model. But none of these have metrics/latency data - they only have artifacts.

The runs with latency data use custom deployments. So maybe those custom deployments are Qwen2.5-VL-32B and gpt-oss-20b, but deployed via the Fireworks deployment mechanism rather than using the public model endpoints.

Let me look at the data from `exp_qwen_x_gpt_oss_20b` runs: the experiment name explicitly mentions "qwen" and "gpt-oss-20b", strongly suggesting the CVR model is qwen2.5-vl-32b and the style model is gpt-oss-20b.

For the runs where `style_model_name` is `accounts/fireworks/models/gpt-oss-20b`:
- Run `356727511...`: cvr=`e7g2xwfe` (qwen2.5-vl-32b custom deployment?), style=`gpt-oss-20b`, cvr_latency=6.58s, style_latency=33.34s
- Run `ce3bb8ee...`: cvr=`ks6i10e2` (qwen2.5-vl-32b custom deployment?), style=`gpt-oss-20b`, cvr_latency=8.34s, style_latency=50.04s

But there are more. Let me check all runs for the exp_qwen_x_gpt_oss_20b experiment that have metrics:

**Tool: bash**

**Tool: bash**

---

## Assistant

_Thinking:_

Now I have a clear picture. The experiment named `exp_qwen_x_gpt_oss_20b` has runs that test different custom deployments. Some of them use `gpt-oss-20b` explicitly as the style model. For those runs:

1. `e7g2xwfe` (CVR custom dep.) + `gpt-oss-20b` (style): cvr=6.58s, style=33.34s (max_tokens=256)
2. `ks6i10e2` (CVR custom dep.) + `gpt-oss-20b` (style): cvr=8.34s, style=50.04s (max_tokens=2048)

Other runs use custom deployments for both models. The experiment name suggests both are "qwen" and "gpt-oss-20b" variants.

For the question about "qwen-2.5-vl-32b" specifically, I need to point out that:
- When used as `accounts/fireworks/models/qwen2p5-vl-32b-instruct` (public endpoint), no latency data was recorded
- Custom deployments likely based on qwen2.5-vl-32b have latency data ranging from ~3.23s to ~11.44s for CVR

For "gpt-oss-20b" specifically:
- Runs explicitly using `accounts/fireworks/models/gpt-oss-20b` for style generation: 33.34s and 50.04s

Let me also note that some custom deployments (like `gby0ppfz`, `wg7je874`, `svfxk7pz`) don't specify which base model they use - they could be qwen, gpt-oss-20b, or something else entirely (like InternVL3-78B).

Let me present this analysis to the user.

Here's a summary of the latency data from the MLflow tracking database (`experiments/mlflow.db`).

## Experiments Overview

- **Experiment 1** (`video_captioning_cvr_experiments`): Used explicit `qwen2p5-vl-32b-instruct` + `gpt-oss-120b` -- but **no latency metrics** were logged; only artifacts exist.
- **Experiment 2** (`video_captioning_cvr_experiments_v2`): Used various custom Fireworks deployments + explicit model IDs. Latency data exists here.

## Runs with Latency Data

| Run Name | CVR Model | Style Model | CVR Latency (s) | Style Latency (s) | Notes |
|---|---|---|---|---|---|
| `exp_example_baseline` | custom dep. `wg7je874` | same | **11.44** | 6.01 | 16 frames |
| `exp_8_frames_sampling` | custom dep. `svfxk7pz` | same | **7.29** | 6.82 | 8 frames |
| `exp_num_frames_1` | custom dep. `gby0ppfz` | same | **3.23** | 4.47 | 1 frame |
| `exp_qwen_x_gpt_oss_20b` | custom `e7g2xwfe` | **gpt-oss-20b** | **6.58** | **33.34** | style_max_tokens=256 |
| `exp_qwen_x_gpt_oss_20b` | custom `ks6i10e2` | **gpt-oss-20b** | **8.34** | **50.04** | style_max_tokens=2048 |
| `exp_qwen_x_gpt_oss_20b` | custom `x5x3h9hz` | custom `hygjjnsr` | **6.67** | 11.42 | — |
| `exp_qwen_x_gpt_oss_20b` | custom `ynb0xtxw` | custom `j8n04pmq` | **7.57** | 15.76 | — |
| `exp_qwen_x_gpt_oss_20b` | custom `ynb0xtxw` | custom `j8n04pmq` | **7.61** | 11.69 | — |

## Key Findings

**gpt-oss-20b (style model, explicitly identified):**
- Style generation latency ranged from **33.34s** (max_tokens=256) to **50.04s** (max_tokens=2048)

**qwen-2.5-vl-32b (CVR model):**
- When called via the public Fireworks endpoint (`accounts/fireworks/models/qwen2p5-vl-32b-instruct`), no latency was logged
- The `exp_qwen_x_gpt_oss_20b` runs use custom deployments that the experiment name implies are Qwen-based for CVR. Those CVR latencies range from **6.58s to 8.34s** (all with 8 frames, 768 max resolution)

**Custom deployments are opaque** -- the deployment IDs (`e7g2xwfe`, `ks6i10e2`, `ynb0xtxw`, etc.) don't map to base model names in the code. The only way to know what model they are is from the Fireworks deployment dashboard or environment configuration.

---

