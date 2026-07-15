#!/usr/bin/env sh
# Lifecycle orchestrator: deploy dedicated Fireworks deployments (minimal 1-GPU,
# scale-to-zero autoscaling @ 80% load), keep them alive for 10 minutes, then
# delete them to release GPU billing.
#
# Stands up the two deployments the demo needs:
#   1. CVR / vision model: qwen2p5-vl-32b-instruct
#   2. Style-generation model: gpt-oss-120b
#
# With --min-replica-count 0, no GPU replica spins up until the first inference
# request arrives, and the deployment scales back to zero after Fireworks'
# default scale-to-zero idle window (1h) — so idle billing is zero.
#
# Required env:
#   FIREWORKS_API_KEY   Fireworks API key (passed to firectl via --api-key)
#
# Optional env (defaults shown):
#   FIREWORKS_ACCOUNT_ID=adityadmore2000-x698
#   LIFECYCLE_DURATION_SECONDS=600   how long to keep deployments up before teardown
#
# Usage:
#   docker run --rm \
#     -e FIREWORKS_API_KEY=... \
#     [-e FIREWORKS_ACCOUNT_ID=...] \
#     [-e LIFECYCLE_DURATION_SECONDS=600] \
#     ghcr.io/adityadmore2000/video-captioning-agent-demo-deployer:latest
#
# WARNING: setting --min-replica-count to 0 means zero idle GPU billing, but
# any inference traffic through these deployments (e.g. the Streamlit demo
# pointed at them) will allocate replicas billed by GPU-second until they
# scale back to zero after the idle window.

set -eu

ACCOUNT_ID="${FIREWORKS_ACCOUNT_ID:-adityadmore2000-x698}"
DURATION_S="${LIFECYCLE_DURATION_SECONDS:-600}"

if [ -z "${FIREWORKS_API_KEY:-}" ]; then
    echo "ERROR: FIREWORKS_API_KEY is required." >&2
    exit 1
fi

VISION_BASE_MODEL="accounts/fireworks/models/qwen2p5-vl-32b-instruct"
STYLE_BASE_MODEL="accounts/fireworks/models/gpt-oss-120b"
# Unique-per-run suffix: Fireworks retains DELETED deployments in a 7-day
# purge queue, so reusing a static deployment name on a second run fails with
# `AlreadyExists`. A short random suffix makes each invocation create fresh,
# immediately-usable IDs. The actual deployment IDs are printed to stdout at
# the end so they can be pasted into the demo's Streamlit secrets.
RUN_SUFFIX=$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 4)
VISION_DEPLOYMENT_ID="vca-demo-vision-${RUN_SUFFIX}"
STYLE_DEPLOYMENT_ID="vca-demo-style-${RUN_SUFFIX}"

ACCELERATOR_TYPE="NVIDIA_H200_141GB"
ACCELERATOR_COUNT="1"
MIN_REPLICAS="0"
MAX_REPLICAS="1"
LOAD_TARGET="default=0.8"

# Track which deployments we actually created so cleanup only tries to delete
# those (avoids noisy "not found" errors from a never-created deployment).
CREATED_DEPLOYMENTS=""

# Cleanup trap: ensure teardown runs even if the script is interrupted (SIGINT /
# SIGTERM) or exits normally, so GPU billing never leaks past container exit.
cleanup() {
    trap '' INT TERM
    echo ""
    echo "=== Tearing down deployments ==="
    if [ -z "${CREATED_DEPLOYMENTS}" ]; then
        echo "  (no deployments were created — nothing to delete)"
    else
        for dep_id in ${CREATED_DEPLOYMENTS}; do
            echo "Deleting deployment: ${dep_id}"
            if firectl --api-key "${FIREWORKS_API_KEY}" -a "${ACCOUNT_ID}" \
                    delete deployment "${dep_id}" >/tmp/firectl-delete.log 2>&1; then
                echo "  deleted"
            else
                echo "  delete failed (probably already gone): $(head -1 /tmp/firectl-delete.log)"
            fi
        done
    fi
    echo "=== Teardown complete ==="
}
trap cleanup INT TERM EXIT

# Helper: create one deployment, capturing output to a log file so we can
# distinguish firectl's exit status from sed's (the previous version piped
# through sed, which masked firectl failures and let the script continue).
create_deployment() {
    base_model="$1"
    dep_id="$2"
    log_file="/tmp/firectl-create-${dep_id}.log"

    if firectl --api-key "${FIREWORKS_API_KEY}" -a "${ACCOUNT_ID}" \
            create deployment "${base_model}" \
            --display-name "${dep_id}" \
            --deployment-id "${dep_id}" \
            --accelerator-type "${ACCELERATOR_TYPE}" \
            --accelerator-count "${ACCELERATOR_COUNT}" \
            --min-replica-count "${MIN_REPLICAS}" \
            --max-replica-count "${MAX_REPLICAS}" \
            --load-targets "${LOAD_TARGET}" \
            --wait >"${log_file}" 2>&1; then
        sed 's/^/  /' "${log_file}"
        return 0
    fi
    echo "  firectl output:" >&2
    sed 's/^/    /' "${log_file}" >&2
    return 1
}

echo "==========================================================="
echo "Fireworks Deployment Lifecycle"
echo "  account:           ${ACCOUNT_ID}"
echo "  duration:          ${DURATION_S}s"
echo "  accelerator:       ${ACCELERATOR_TYPE} x${ACCELERATOR_COUNT}"
echo "  replicas:          min=${MIN_REPLICAS}  max=${MAX_REPLICAS}"
echo "  autoscale target:  ${LOAD_TARGET} (default metric @ 80%)"
echo "  models:            ${VISION_DEPLOYMENT_ID} (vision), ${STYLE_DEPLOYMENT_ID} (style)"
echo "  scale-to-zero:     default window 1h (no inference -> 0 replicas -> 0 billing)"
echo "==========================================================="
echo ""

# --- Auth sanity check -----------------------------------------------------
# Run a trivial read-only command so we fail fast with a clear message if the
# API key is invalid, instead of failing mid-way through deployment creation.

echo "[0/3] Verifying Fireworks API key..."
if ! firectl --api-key "${FIREWORKS_API_KEY}" -a "${ACCOUNT_ID}" \
        deployment list >/tmp/firectl-auth.log 2>&1; then
    echo "ERROR: Fireworks authentication failed. Check FIREWORKS_API_KEY." >&2
    echo "  firectl output:" >&2
    sed 's/^/    /' /tmp/firectl-auth.log >&2
    exit 1
fi
echo "  auth OK"

# --- Create deployments ----------------------------------------------------
# Fail-fast: ANY deployment creation failure aborts the entire lifecycle.
# Cleanup runs via the EXIT trap, deleting only deployments actually created.

echo ""
echo "[1/3] Creating CVR/vision deployment..."
if ! create_deployment "${VISION_BASE_MODEL}" "${VISION_DEPLOYMENT_ID}"; then
    echo "ERROR: vision deployment creation failed; aborting." >&2
    exit 1
fi
CREATED_DEPLOYMENTS="${CREATED_DEPLOYMENTS} ${VISION_DEPLOYMENT_ID}"

echo ""
echo "[2/3] Creating style deployment..."
if ! create_deployment "${STYLE_BASE_MODEL}" "${STYLE_DEPLOYMENT_ID}"; then
    echo "ERROR: style deployment creation failed; aborting." >&2
    exit 1
fi
CREATED_DEPLOYMENTS="${CREATED_DEPLOYMENTS} ${STYLE_DEPLOYMENT_ID}"

echo ""
echo "=== Deployments READY ==="
echo "Vision: accounts/${ACCOUNT_ID}/deployments/${VISION_DEPLOYMENT_ID}"
echo "Style:  accounts/${ACCOUNT_ID}/deployments/${STYLE_DEPLOYMENT_ID}"
echo ""
echo "To point the demo at these deployments, set in Streamlit secrets:"
echo "  VISION_DEPLOYMENT_ID=accounts/${ACCOUNT_ID}/deployments/${VISION_DEPLOYMENT_ID}"
echo "  STYLE_DEPLOYMENT_ID=accounts/${ACCOUNT_ID}/deployments/${STYLE_DEPLOYMENT_ID}"
echo ""

# --- Hold deployments alive ------------------------------------------------
HOLD_SECONDS=${DURATION_S}
END=$(( $(date +%s) + HOLD_SECONDS ))
echo "[3/3] Holding deployments alive for ${HOLD_SECONDS}s."
echo "      Will auto-delete at $(date -d "@${END}" -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo "epoch+${END}")."
echo "      Press Ctrl-C to tear down early (cleanup is safe to interrupt)."

while [ "$(date +%s)" -lt "${END}" ]; do
    remaining=$(( END - $(date +%s) ))
    printf "\r  remaining: %4ss / ${HOLD_SECONDS}s   " "${remaining}"
    sleep 10
done
echo ""

# cleanup runs via the EXIT trap regardless of how we got here.
echo "Hold window elapsed."