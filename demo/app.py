"""Streamlit demo for the Video Captioning Agent.

A single bundled sample video, one "Run demo" button, and the four generated
caption styles printed as output. No configuration knobs — just show the output.

Run locally:
    cd <repo-root>
    streamlit run demo/app.py

Or via Streamlit Community Cloud:
    deploy from this GitHub repo, set the following as secrets (Manage app →
    Settings → Secrets), and main file path = demo/app.py:

        FIREWORKS_API_KEY="fw_..."
        # Option A (automatic provisioning): the demo provisions/reuses a
        # deployment of the base VLM on first run — no dashboard work needed.
        FIREWORKS_VISION_BASE_MODEL="qwen2.5-vl-32b-instruct"
        FIREWORKS_VISION_DEPLOYMENT_NAME="video-captioning-vlm"
        # Option B (pre-deployed): point directly at an existing model id.
        # FIREWORKS_VISION_MODEL="accounts/.../deployments/<your-vision-deployment>"
        STYLE_DEPLOYMENT_ID="accounts/.../deployments/<your-style-deployment>"

Locally, the same values can be set as environment variables instead.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import streamlit as st

_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPOSITORY_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from video_captioning_agent._env import load_env_file
from video_captioning_agent.cvr_client import (
    CvrGenerationError,
    FireworksCvrClient,
    VISION_MODEL_ID,
)
from video_captioning_agent.cvr_parser import parse_cvr_response
from video_captioning_agent.deployment_manager import (
    DEFAULT_MAX_REPLICAS,
    DEFAULT_MIN_REPLICAS,
    DeploymentProvisioningError,
    FireworksDeploymentManager,
)
from video_captioning_agent.frame_sampler import FrameSamplingError, sample_frames
from video_captioning_agent.style_generator import (
    FireworksStyleClient,
    StyleGenerationError,
    STYLE_MODEL_ID,
    generate_all_captions,
)
from video_captioning_agent.video_inspection import inspect_video

load_env_file()

SAMPLE_VIDEO = Path(__file__).resolve().parent / "sample_data" / "001YG.mp4"

STYLE_COLORS = {
    "Formal": "#4FC3F7",
    "Sarcastic": "#FF8A65",
    "Humorous-Tech": "#81C784",
    "Humorous-Non-Tech": "#BA68C8",
}

STYLES = ("Formal", "Sarcastic", "Humorous-Tech", "Humorous-Non-Tech")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _config_value(key: str, fallback: str) -> str:
    """Read a config value from Streamlit secrets, then env, then fallback."""
    try:
        value = st.secrets.get(key)
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(key, fallback)


def _resolve_vision_model() -> str:
    """Resolve the vision model id with auto-provisioning support.

    Precedence (secrets then env at each step):
    1. ``FIREWORKS_VISION_MODEL`` — use a pre-existing model id directly.
    2. ``FIREWORKS_VISION_DEPLOYMENT_NAME`` + ``FIREWORKS_VISION_BASE_MODEL``
       — provision/reuse a deployment via ``FireworksDeploymentManager``.
    3. ``VISION_DEPLOYMENT_ID`` — legacy pre-deployed secret/env (fallback).
    4. ``VISION_MODEL_ID`` constant.
    """
    explicit = _config_value("FIREWORKS_VISION_MODEL", "")
    if explicit:
        return explicit

    deployment_name = _config_value("FIREWORKS_VISION_DEPLOYMENT_NAME", "")
    base_model = _config_value("FIREWORKS_VISION_BASE_MODEL", "")
    if deployment_name and base_model:
        api_key = _config_value("FIREWORKS_API_KEY", "")
        try:
            manager = FireworksDeploymentManager(api_key=api_key or None)
            with st.spinner("Provisioning vision deployment (first run may take several minutes)..."):
                _raw_lt = _config_value("FIREWORKS_VISION_LOAD_TARGET", "")
                _raw_min = _config_value("FIREWORKS_VISION_MIN_REPLICAS", "")
                _raw_max = _config_value("FIREWORKS_VISION_MAX_REPLICAS", "")
                _raw_ac = _config_value("FIREWORKS_VISION_ACCELERATOR_COUNT", "")
                accelerator_type = _config_value("FIREWORKS_VISION_ACCELERATOR_TYPE", "") or None
                accelerator_count = int(_raw_ac) if _raw_ac and accelerator_type else None
                return manager.resolve_vision_model(
                    deployment_name=deployment_name,
                    base_model=base_model,
                    min_replicas=int(_raw_min) if _raw_min else DEFAULT_MIN_REPLICAS,
                    max_replicas=int(_raw_max) if _raw_max else DEFAULT_MAX_REPLICAS,
                    deployment_shape=_config_value("FIREWORKS_VISION_DEPLOYMENT_SHAPE", "") or None,
                    accelerator_type=accelerator_type,
                    accelerator_count=accelerator_count,
                    load_target=float(_raw_lt) if _raw_lt else None,
                )
        except DeploymentProvisioningError as error:
            st.error(f"Vision deployment provisioning failed: {error}")
            raise

    return _config_value("VISION_DEPLOYMENT_ID", VISION_MODEL_ID)


def main() -> None:
    st.set_page_config(
        page_title="Video Captioning Agent",
        page_icon=":movie_camera:",
        layout="centered",
    )
    st.title("Video Captioning Agent")
    st.markdown(
        "Click **Run demo** to caption the sample video below in all four styles."
    )

    if not os.environ.get("FIREWORKS_API_KEY"):
        st.error(
            "**FIREWORKS_API_KEY is not set.** The demo cannot run without it. "
            "Set it in your environment or pass `-e FIREWORKS_API_KEY=...` to Docker."
        )
        return

    if not SAMPLE_VIDEO.is_file():
        st.error("Sample video file not found in the image.")
        return

    st.video(str(SAMPLE_VIDEO))

    if not st.button("Run demo", type="primary", use_container_width=True):
        return

    _run_pipeline(SAMPLE_VIDEO)


def _run_pipeline(video_path: Path) -> None:
    """Run the full two-stage pipeline and print the four captions."""

    start = time.perf_counter()

    with st.spinner("Sampling frames..."):
        inspection = inspect_video("demo", video_path)
        if not inspection.succeeded or inspection.metadata is None:
            st.error(f"Video inspection failed: {inspection.failure}")
            return
        try:
            frames = sample_frames(video_path, inspection.metadata)
        except FrameSamplingError as error:
            st.error(f"Frame sampling failed: {error}")
            return

    style_id = _config_value("STYLE_DEPLOYMENT_ID", STYLE_MODEL_ID)

    try:
        vision_id = _resolve_vision_model()
    except DeploymentProvisioningError:
        return

    with st.spinner("Generating Canonical Video Report (vision model)..."):
        try:
            vision_client = FireworksCvrClient(model_id=vision_id)
            raw_cvr = vision_client.generate_cvr(frames, inspection.metadata)
        except CvrGenerationError as error:
            st.error(f"Vision model call failed: {error}")
            return

        parsed = parse_cvr_response("demo", raw_cvr)
        if not parsed.succeeded or parsed.report is None:
            st.error(f"CVR parsing failed: {parsed.failure}")
            return

    with st.spinner("Generating captions in all 4 styles..."):
        try:
            style_client = FireworksStyleClient(model_id=style_id)
            result = generate_all_captions(style_client, parsed.report)
        except StyleGenerationError as error:
            st.error(f"Style generation failed: {error}")
            return

    elapsed = time.perf_counter() - start

    st.divider()
    st.markdown(f"**Captions** &nbsp; (pipeline took {elapsed:.1f}s)")
    st.divider()

    for style in STYLES:
        caption = result.captions.get(style, "")
        color = STYLE_COLORS[style]
        st.markdown(
            f"<div style='border-left:4px solid {color}; padding:8px 16px; "
            f"margin-bottom:12px;'>"
            f"<b style='color:{color};'>{style}</b><br>"
            f"<span style='color:#FAFAFA; font-size:1.1rem;'>"
            f"{caption or '(generation failed)'}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()