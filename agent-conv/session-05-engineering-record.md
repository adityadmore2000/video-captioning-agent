# Session Summary

## Objective
Get the Streamlit Cloud demo app running end-to-end by resolving the Fireworks vision model 404 error and building a deployment lifecycle orchestrator for dedicated GPU deployments.

## Project State Before Session
- Streamlit Cloud app deployed but immediately failed at build time due to broken apt dependencies (`libglib2.0-0` from Debian 11 bullseye on a Debian 13 trixie host)
- A `packages.txt` existed with problematic apt packages
- The demo app hardcoded serverless Fireworks model IDs; the vision model (`qwen2p5-vl-32b-instruct`) returned 404 in serverless mode
- A `firectl` binary was already present in the repo for Fireworks CLI operations
- A `.dockerignore` excluded `firectl` from Docker build contexts

## Major Achievements
1. **Fixed Streamlit Cloud build failure** — removed `libglib2.0-0` from `packages.txt` (OpenCV headless wheel bundles its own libs)
2. **Discovered vision model unavailability** — probed Fireworks serverless API confirmed `qwen2p5-vl-32b-instruct` returns 404 while `gpt-oss-120b` works serverless; vision requires a dedicated deployment
3. **Built and published a deployer container** — `ghcr.io/adityadmore2000/video-captioning-agent-demo-deployer:latest` (117 MB, Alpine + static `firectl`) that orchestrates: create two minimal 1×H200 deployments → poll READY → hold 10 min → auto-delete with cleanup trap
4. **Wired demo app for dynamic deployment IDs** — `demo/app.py` now reads `VISION_DEPLOYMENT_ID` and `STYLE_DEPLOYMENT_ID` from Streamlit secrets (with env var and serverless fallbacks)
5. **Fixed lifecycle script control-flow bug** — pipeline `firectl ... 2>&1 | sed ...` masked firectl's exit status because `set -e` without `pipefail` evaluates the last command (`sed`), which always returns 0. Restructured to capture output to a file first, then check exit status.
6. **Fixed firectl auth mechanism** — script was writing `~/.firectl.yaml` but firectl reads `~/.fireworks/auth.ini` for OIDC credentials; switched to `firectl --api-key <KEY>` global flag (confirmed working for both create and delete)
7. **Resolved deployment name collision** — Fireworks retains DELETED deployments in a 7-day purge queue, so static deployment IDs fail on re-run with `AlreadyExists`. Added `RUN_SUFFIX` (4-char hex from `/dev/urandom`) for unique-per-invocation IDs.
8. **Discovered correct load-target key** — `gpu_cache_usage_pct` is not supported; corrected to `default=0.8` per firectl warning

## Engineering Decisions

### Decision: Remove `libglib2.0-0` from packages.txt instead of pinning a compatible version
- **Reasoning**: `opencv-python-headless` wheel bundles its own shared libraries; system-level `libglib2.0-0` is unnecessary and conflicts with the Debian trixie host environment. Simpler to drop it entirely.
- **Alternative**: Pin `libglib2.0-0t64` (the trixie-versioned package), but the risk of future version drift on Streamlit Cloud's base image makes removal safer.
- **Trade-off**: If the OpenCV version changes and no longer bundles `libglib`, this fix would regress. Low probability for a demo app.

### Decision: Build a Docker container (deployer) rather than a standalone Python script for deployment lifecycle
- **Reasoning**: The firectl binary (73 MB, static Go) handles the Fireworks API with correct field names and auth, avoiding protobuf field-mapping issues encountered when using REST directly. Bundling it in a container is the most reliable path.
- **Alternative**: Pure Python script with REST calls (attempted but `loadTargets` field rejected at create; accepted only via PATCH which complicates the script).
- **Trade-off**: Container depends on local `firectl` binary not checked into git (gitignored). Reproducible only on machines that have the binary. Acceptable for a utility container.

### Decision: Use `--api-key` global flag instead of writing `.firectl.yaml`
- **Reasoning**: Investigation revealed firectl reads `~/.fireworks/auth.ini` (OIDC tokens), NOT `~/.firectl.yaml`. The user's host used Google OIDC sign-in. Inside the container, API key authentication via the `--api-key` flag was the only non-interactive option that worked.
- **Discovery**: The user's `~/.fireworks/auth.ini` had `api_key = ` empty (OIDC-only auth). `firectl set-api-key` writes to `~/.fireworks/auth.ini`. Verified `--api-key` works for both `create` and `delete deployment`.

### Decision: Unique random suffix for deployment IDs per run
- **Reasoning**: Fireworks keeps DELETED deployments in a 7-day purge queue with `AlreadyExists` errors on name reuse. A 4-char random hex suffix per invocation avoids collision.
- **Trade-off**: The user must copy-paste new deployment IDs into Streamlit secrets each run. Acceptable for a demo workflow.

### Decision: Capture firectl output to file before sed rather than piping
- **Reasoning**: Shell pipelines without `pipefail` return the exit status of the last command (`sed` = 0). The `||` error handler never fired even when `firectl` failed. Restructured to `if ! firectl ... > /tmp/log 2>&1; then ... fi; cat /tmp/log | sed`.
- **Alternative**: `set -o pipefail` — but busybox `ash` (used in Alpine) may not support it. File-based approach is POSIX-compatible.

## Architecture Changes
- **`demo/lifecycle.sh`** — new shell-script orchestrator for Fireworks deployment lifecycle
- **`demo/deployer.Dockerfile`** — new minimal Alpine-based Docker image bundling `firectl` and `lifecycle.sh`
- **`demo/app.py`** — updated to read `VISION_DEPLOYMENT_ID` / `STYLE_DEPLOYMENT_ID` from Streamlit secrets with env var fallback; passes `model_id` to both Fireworks clients
- **`packages.txt`** — reduced from 4 packages to 3 (removed `libglib2.0-0`)
- **`.dockerignore`** — added `!firectl` exception for deployer builds

## Implementation Progress
- Demo app now supports deployment IDs via `_config_value()` helper (secrets → env → serverless fallback)
- Deployer container published to GHCR with both `:latest` and `:sha-<git-sha>` tags
- Script includes: auth sanity check (`firectl deployment list`) before deployment creation; `--wait` blocks until READY; cleanup `trap` on INT/TERM/EXIT; idempotent delete

## Problems / Bugs / Limitations
1. **Serverless vision model unavailable** — `qwen2p5-vl-32b-instruct` returns 404 on serverless endpoint. Root cause: needs a dedicated deployment (GPU).
2. **7-day purge queue** — Fireworks retains DELETED deployments for 7 days, preventing immediate re-deployment with the same name.
3. **Container signal propagation** — Docker's SIGTERM → PID1 (shell) propagation is unreliable for trap-based cleanup when the container is killed by `timeout`/`docker stop`. The EXIT trap triggers on normal completion; graceful interruption may leave orphaned deployments with GPU billing.
4. **`--load-targets` replaces default** — Setting `--load-targets` removes Fireworks' default autoscaling metrics; must explicitly include `default=<value>`.

## Debugging / Investigation
- **Streamlit Cloud build failure**: Inspected downloaded Cloud logs showing `libglib2.0-0` → `libffi7` dependency chain incompatible with Debian trixie. Fixed by removing the package.
- **Vision model 404**: Tested both serverless models via REST. `gpt-oss-120b` → HTTP 200, `qwen2p5-vl-32b-instruct` → HTTP 404. Confirmed serverless not available for the vision model.
- **firectl auth**: Investigated firectl's authentication pathways by inspecting host's `~/.fireworks/auth.ini` (contained OIDC `id_token`, `refresh_token`, empty `api_key`). Discovered `.firectl.yaml` is not read by firectl — authentication credentials come from `~/.fireworks/auth.ini` (for OIDC) or the `--api-key` CLI flag.
- **`loadTargets` field name**: Probed Fireworks REST API with both `loadTargets` and `load_targets` — both rejected at create time. Only settable via PATCH (Update). Used firectl `--load-targets` CLI flag instead, which handles the internal API correctly.
- **Supported load-target keys**: Extracted from firectl error message: `concurrent_requests`, `vllm_concurrent_requests`, `serverless_uncached_input_capacity_utilization`, `default`, `generation_latency_per_token_ms`, `prompt_tokens_per_second`, `serverless_generated_capacity_utilization`, `tokens_generated_per_second`, `requests_per_second`.

## Important Insights
- **OpenCV headless wheel is self-contained** — doesn't need system-level `libglib2.0-0` on Streamlit Cloud's Debian host, debunking the assumption made in the initial `packages.txt`.
- **Fireworks dedicated deployments have a 7-day retention** after deletion before names can be reused — important lifecycle consideration for ephemeral demo deployments.
- **`firectl --api-key` bypasses OIDC entirely** — the user's environment uses Google OIDC sign-in, but the API key flag works independently for non-interactive scripts.
- **Deployment creation latency is significant** — qwen2p5-vl-32b-instruct (BF16, ~36GB) takes several minutes to reach READY state. The `--wait` flag blocks accordingly.
- **With `minReplicaCount=0`**, no GPU replica is allocated until the first inference request; billing is GPU-second-based. This means the deployment itself costs nothing until traffic flows.

## Project State After Session
- Streamlit Cloud app builds and runs but still returns 404 on vision model calls (waiting for user to run deployer + set secrets)
- A deployer container is built, tested (with auth and control-flow bugs fixed), and published to GHCR with both `:latest` and `:sha-*` tags
- The demo app accepts deployment IDs from secrets/env with serverless fallback
- Remaining gap: the user needs to (a) run the deployer, (b) paste the printed deployment IDs into Streamlit Cloud secrets, (c) click "Run demo" within the 10-minute window

## Interview-Worthy Talking Points
1. **Shell pipefail footgun** — how `firectl ... | sed` masked a non-zero exit and the script silently "succeeded". Illustrates the danger of pipelines in error-handling context. The fix (file-capture before processing) is POSIX-compatible and more explicit than `set -o pipefail`.
2. **Protobuf field discovery via binary strings** — using `strings firectl` to reverse-engineer the REST API field name (`load_targets`) when documentation was incomplete. Real-world binary archaeology for debugging undocumented protobuf APIs.
3. **OIDC vs API key authentication** — debugging why firectl failed auth in the container despite having the API key, discovering that firectl uses OIDC tokens (not API key) stored in `~/.fireworks/auth.ini` for `create deployment`, and that the `--api-key` global flag uses a separate auth pathway.
4. **Auto-scaling GPU deployments with zero idle-cost** — designing an ephemeral demo infrastructure where `minReplicaCount=0` means zero GPU billing during idle, but billing spikes when inference arrives. The scale-to-zero window trade-off.
5. **Cross-distribution apt dependency conflicts** — Debian bullseye vs trixie package version mix caused by Streamlit Cloud's multi-distribution build environment.

## Keywords
Fireworks AI, Streamlit Cloud, Debian trixie, apt dependencies, opencv-python-headless, dedicated GPU deployment, firectl CLI, deployment lifecycle, autoscaling, scale-to-zero, load targets, protobuf, OIDC authentication, API key, NVIDIA_H200_141GB, pipeline exit status, shell pipefail, 7-day purge retention, GPU billing, ephemeral demo infrastructure, video captioning, qwen2p5-vl-32b-instruct, gpt-oss-120b, GHCR, Docker, Streamlit secrets

## Presentation Assets
- **Debugging case study**: Shell pipeline exit status masking (before/after of lifecycle.sh control flow)
- **Comparison table**: Authentication methods tested (`.firectl.yaml`, `~/.fireworks/auth.ini`, `--api-key` global flag) with success/failure per operation
- **Architecture diagram**: Deployer container lifecycle (container start → auth check → create vision dep → create style dep → hold 10 min → auto-delete)
- **Timeline**: Session events (build fix → vision 404 discovery → deployer build → auth fix → control flow fix → deployment name collision fix)
- **Billing model chart**: `minReplicaCount=0` vs `minReplicaCount=1` billing implications
