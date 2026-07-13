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
#   FIREWORKS_API_KEY   Fireworks API key (read by firectl from ~/.firectl.yaml)
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

# firectl reads its key from ~/.firectl.yaml; write a minimal config so the
# CLI authenticates without any interactive login step.
mkdir -p "${HOME}"
cat > "${HOME}/.firectl.yaml" <<EOF
api_key: ${FIREWORKS_API_KEY}
account: ${ACCOUNT_ID}
EOF

VISION_BASE_MODEL="accounts/fireworks/models/qwen2p5-vl-32b-instruct"
STYLE_BASE_MODEL="accounts/fireworks/models/gpt-oss-120b"
VISION_DISPLAY_NAME="vca-demo-vision"
STYLE_DISPLAY_NAME="vca-demo-style"

ACCELERATOR_TYPE="NVIDIA_H200_141GB"
ACCELERATOR_COUNT="1"
MIN_REPLICAS="0"
MAX_REPLICAS="1"
LOAD_TARGET="gpu_cache_usage_pct=0.8"

deployments="${VISION_DISPLAY_NAME} ${STYLE_DISPLAY_NAME}"

# Cleanup trap: ensure teardown runs even if the script is interrupted (SIGINT /
# SIGTERM), so GPU billing never leaks past container exit.
cleanup() {
    trap '' INT TERM
    echo ""
    echo "=== Tearing down deployments ==="
    for display_name in ${deployments}; do
        echo "Deleting deployment: ${display_name}"
        firectl delete deployment "${display_name}" >/tmp/firectl-delete.log 2>&1 \
            && echo "  deleted" \
            || echo "  delete failed (probably already gone): $(cat /tmp/firectl-delete.log | head -1)"
    done
    echo "=== Teardown complete ==="
}
trap cleanup INT TERM EXIT

echo "==========================================================="
echo "Fireworks Deployment Lifecycle"
echo "  account:           ${ACCOUNT_ID}"
echo "  duration:          ${DURATION_S}s"
echo "  accelerator:       ${ACCELERATOR_TYPE} x${ACCELERATOR_COUNT}"
echo "  replicas:          min=${MIN_REPLICAS}  max=${MAX_REPLICAS}"
echo "  autoscale target:  ${LOAD_TARGET} (80%)"
echo "  models:            ${VISION_DISPLAY_NAME} (vision), ${STYLE_DISPLAY_NAME} (style)"
echo "  scale-to-zero:     default window 1h (no inference -> 0 replicas -> 0 billing)"
echo "==========================================================="
echo ""

# --- Create deployments ----------------------------------------------------
# --wait blocks until each deployment reaches READY; failures abort the script
# and trigger cleanup.

echo "[1/3] Creating CVR/vision deployment..."
/usr/bin/time -f "  duration: %es" \
    firectl create deployment "${VISION_BASE_MODEL}" \
    --display-name "${VISION_DISPLAY_NAME}" \
    --deployment-id "${VISION_DISPLAY_NAME}" \
    --accelerator-type "${ACCELERATOR_TYPE}" \
    --accelerator-count "${ACCELERATOR_COUNT}" \
    --min-replica-count "${MIN_REPLICAS}" \
    --max-replica-count "${MAX_REPLICAS}" \
    --load-targets "${LOAD_TARGET}" \
    --wait 2>&1 | sed 's/^/  /' || {
        echo "ERROR: vision deployment creation failed; aborting." >&2
        exit 1
    }

echo ""
echo "[2/3] Creating style deployment..."
/usr/bin/time -f "  duration: %es" \
    firectl create deployment "${STYLE_BASE_MODEL}" \
    --display-name "${STYLE_DISPLAY_NAME}" \
    --deployment-id "${STYLE_DISPLAY_NAME}" \
    --accelerator-type "${ACCELERATOR_TYPE}" \
    --accelerator-count "${ACCELERATOR_COUNT}" \
    --min-replica-count "${MIN_REPLICAS}" \
    --max-replica-count "${MAX_REPLICAS}" \
    --load-targets "${LOAD_TARGET}" \
    --wait 2>&1 | sed 's/^/  /' || {
        echo "ERROR: style deployment creation failed; aborting." >&2
        exit 1
    }

echo ""
echo "=== Deployments READY ==="
echo "Vision: accounts/${ACCOUNT_ID}/deployments/${VISION_DISPLAY_NAME}"
echo "Style:  accounts/${ACCOUNT_ID}/deployments/${STYLE_DISPLAY_NAME}"
echo ""
echo "To point the demo at these deployments, set in Streamlit secrets:"
echo "  vision_deployment_id=accounts/${ACCOUNT_ID}/deployments/${VISION_DISPLAY_NAME}"
echo "  style_deployment_id=accounts/${ACCOUNT_ID}/deployments/${STYLE_DISPLAY_NAME}"
echo ""

# --- Hold deployments alive ------------------------------------------------
HOLD_SECONDS=$((DURATION_S))
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