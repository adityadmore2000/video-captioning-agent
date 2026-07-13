# Context: Dedicated Deployment Setup Script (Fireworks API)

## Goal

A one-time setup script that provisions dedicated (on-demand) Fireworks deployments for both models used in this project, and automatically writes the resulting deployment names into the experiment config file(s) — so deployment IDs never need to be manually copy-pasted.

## Scope

- This is a standalone utility script, not part of the production pipeline (`src/`) or the Docker build. It lives alongside the experiment-tracking harness (e.g. `experiments/setup_deployments.py`).
- It is run manually, deliberately, when the user is ready to actually stand up dedicated capacity — not automatically invoked by `run_experiment.py`, `run_all.py`, or any production code path. Running it starts GPU billing immediately (see Cost note below), so it must never run silently as a side effect of something else.

## What to deploy

Two dedicated deployments, both with **minimal configuration** — no `deploymentShape` (this is what avoids the "throughput"/"fast" presets), no explicit `acceleratorType`/`acceleratorCount` (let Fireworks pick sensible defaults for the model):

1. **CVR / vision model**
   - Base model: `accounts/fireworks/models/qwen2p5-vl-32b-instruct`
   - Desired display name / deployment ID: `qwen2p5-vl-32b-instruct`
2. **Style-generation model**
   - Base model: `accounts/fireworks/models/gpt-oss-20b`
   - Desired display name / deployment ID: `gpt-oss-20b`

Both deployments: `minReplicaCount: 1`, `maxReplicaCount: 1` (single fixed replica, no autoscaling to configure).

## API details

```
POST https://api.fireworks.ai/v1/accounts/{account_id}/deployments
Authorization: Bearer <FIREWORKS_API_KEY>
Content-Type: application/json
```

Request body per deployment:
```json
{
  "displayName": "<desired-name>",
  "deploymentId": "<desired-name>",
  "baseModel": "<base-model-resource-name>",
  "minReplicaCount": 1,
  "maxReplicaCount": 1
}
```

Include `deploymentId` explicitly in the request (not just `displayName`) so the actual inference-time identifier matches the intended name, rather than Fireworks assigning a random ID.

The response includes a `name` field of the form `accounts/{account_id}/deployments/{deployment_id}` — this exact string is what gets used later as the queryable model identifier (appended after `#` when calling the base model, or used directly depending on client setup).

`account_id` and `FIREWORKS_API_KEY` should be read from existing environment variables already used elsewhere in this project (do not hardcode or duplicate credential handling — reuse whatever config/env pattern `src/cvr_client.py` already established).

## What the script must do, end to end

1. **Create the CVR model's deployment** via the API above, using the `qwen2p5-vl-32b-instruct` base model and desired name.
2. **Create the style model's deployment** via the API above, using the `gpt-oss-20b` base model and desired name.
3. **Extract the deployment resource name** (`accounts/{account_id}/deployments/{deployment_id}`) from each creation response.
4. **Write both resulting deployment names into the experiment config YAML** (e.g. `experiments/configs/exp_example.yaml`), specifically into:
   - `cvr_model.name`
   - `style_model.name`
   Use a YAML read/modify/write approach that preserves existing keys, comments, and formatting as much as possible — don't regenerate the whole file from scratch and lose `temperature`/`max_tokens`/other existing fields.
5. **Print both resulting deployment names/IDs to stdout** for confirmation, along with a reminder that these deployments are now live and billing by GPU-second.

## Idempotency / re-run behavior

Running this script again should be safe and useful, not just a duplicate-creation error:
- If a deployment with the same `deploymentId` already exists, handle the resulting API error gracefully — check for an existing deployment first (e.g. via `GET /v1/accounts/{account_id}/deployments/{deployment_id}`) and skip creation (or optionally recreate, behind an explicit `--recreate` flag) rather than crashing.
- The config-writing step (step 4) should still run and update the YAML even if the deployment already existed, so the config is always in sync with whatever deployment currently exists under that name.

## Cost note (must be visible to the user, not just documented here)

Dedicated deployments are billed continuously by GPU-second while replicas are running, regardless of whether inference requests are being sent — unlike the serverless pay-per-token model used elsewhere in this project. The script must print a clear cost-awareness message after successful creation (e.g. "Deployment is now live and billing continuously. Delete it when done via `firectl delete deployment <id>` or the equivalent API call, to stop billing.").

## Explicitly out of scope for this script

- Does not modify `src/cvr_client.py` or any production model-invocation code — the config-swappable kwargs added there already support pointing at a deployment-qualified model string; this script only needs to populate the experiment config with the right value.
- Does not implement deployment deletion/teardown — that can be a separate, later addition if needed.
- Does not touch `minReplicaCount`/scale-to-zero behavior beyond the fixed `1`/`1` specified above — if the user later wants scale-to-zero cost savings, that's a distinct follow-up decision, not part of this script's default behavior.
