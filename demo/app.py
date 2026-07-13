"""Streamlit demo for the Video Captioning Agent.

Reuses the real production pipeline components from ``src/`` — frame sampler,
CVR client, CVR parser, and style generator — to show the full two-stage
pipeline end-to-end on a single video.

Run locally:
    cd <repo-root>
    streamlit run demo/app.py

Or via Docker:
    docker run -p 8501:8501 -e FIREWORKS_API_KEY=... \
        ghcr.io/adityadmore2000/video-captioning-agent-demo:latest
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
import time
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from video_captioning_agent.contracts import CanonicalVideoReport
from video_captioning_agent.cvr_client import CvrGenerationError, FireworksCvrClient
from video_captioning_agent.cvr_parser import parse_cvr_response
from video_captioning_agent.frame_sampler import FrameSamplingError, sample_frames
from video_captioning_agent.style_generator import (
    CaptionGenerationResult,
    FireworksStyleClient,
    StyleGenerationError,
    generate_all_captions,
)
from video_captioning_agent.video_inspection import inspect_video


SAMPLE_VIDEO = Path(__file__).resolve().parent / "sample_data" / "001YG.mp4"

STYLE_COLORS = {
    "Formal": "#4FC3F7",
    "Sarcastic": "#FF8A65",
    "Humorous-Tech": "#81C784",
    "Humorous-Non-Tech": "#BA68C8",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger("demo")


def _status_icon(ok: bool) -> str:
    return "done" if ok else "error"


def _step_header(step: int, title: str, elapsed: float | None = None) -> None:
    timing = f" &nbsp;({elapsed:.1f}s)" if elapsed is not None else ""
    st.markdown(f"### Step {step}: {title}{timing}")


def main() -> None:
    st.set_page_config(
        page_title="Video Captioning Agent",
        page_icon=":movie_camera:",
        layout="wide",
    )
    st.title("Video Captioning Agent")
    st.markdown(
        "A multimodal pipeline that produces a **Canonical Video Report (CVR)** "
        "from sampled video frames, then rewrites it into four distinct writing styles."
    )

    api_key_configured = bool(__get_api_key())
    if not api_key_configured:
        st.error(
            "**FIREWORKS_API_KEY is not set.** The demo needs it to call the vision "
            "and style models. Set it in your environment or pass `-e FIREWORKS_API_KEY=...` "
            "when running the Docker container."
        )

    st.divider()

    left_col, right_col = st.columns([1, 2])

    with left_col:
        st.markdown("### Configuration")
        source = st.radio(
            "Video source",
            ["Sample clip (Charades 001YG)", "Upload your own"],
            disabled=not api_key_configured,
        )
        num_frames = st.slider(
            "Frame count",
            min_value=2,
            max_value=24,
            value=8,
            step=1,
            help="How many chronological frames to sample from the video.",
            disabled=not api_key_configured,
        )
        max_resolution = st.slider(
            "Max resolution (px)",
            min_value=256,
            max_value=1024,
            value=768,
            step=64,
            disabled=not api_key_configured,
        )
        run_button = st.button(
            "Run pipeline",
            type="primary",
            disabled=not api_key_configured,
            use_container_width=True,
        )

    with right_col:
        st.markdown("### Video")
        video_path: Path | None = None
        if source.startswith("Sample"):
            if SAMPLE_VIDEO.is_file():
                st.video(str(SAMPLE_VIDEO))
                video_path = SAMPLE_VIDEO
            else:
                st.warning("Sample clip not found in the image.")
        else:
            uploaded = st.file_uploader(
                "Upload a short video (mp4, mov, avi)",
                type=["mp4", "mov", "avi"],
                disabled=not api_key_configured,
            )
            if uploaded is not None:
                tmp = tempfile.NamedTemporaryFile(
                    suffix=f".{uploaded.name.split('.')[-1]}", delete=False
                )
                tmp.write(uploaded.read())
                tmp.close()
                video_path = Path(tmp.name)
                st.video(str(video_path))

    if not run_button or video_path is None:
        st.divider()
        st.markdown(
            "**How it works:**\n"
            "1. Sample chronological frames from the video (OpenCV).\n"
            "2. Send frames to **Qwen2.5-VL 32B Instruct** (vision) → Canonical Video Report.\n"
            "3. Rewrite the CVR into 4 styles using **gpt-oss-120b** (text-only).\n\n"
            "Configure the options on the left and click **Run pipeline** to see it live."
        )
        return

    st.divider()

    full_start = time.perf_counter()

    # ---- Step 1: inspect + sample frames ---------------------------------
    _step_header(1, "Video inspection & frame sampling")
    with st.spinner("Inspecting video and sampling frames..."):
        t0 = time.perf_counter()
        try:
            inspection = inspect_video("demo", video_path)
            if not inspection.succeeded or inspection.metadata is None:
                st.error(f"Video inspection failed: {inspection.failure}")
                return
            frames = sample_frames(
                video_path, inspection.metadata,
                target_frames=num_frames, max_resolution=max_resolution,
            )
        except (FrameSamplingError, Exception) as error:
            st.error(f"Frame sampling failed: {error}")
            return
        t1 = time.perf_counter()

    meta = inspection.metadata
    st.success(
        f"Inspected OK: {meta.width}x{meta.height}, {meta.fps:.1f} fps, "
        f"{meta.duration_seconds:.1f}s"
    )

    cols = st.columns(min(len(frames), 4))
    for idx, frame in enumerate(frames):
        with cols[idx % len(cols)]:
            st.image(frame.image_data_url, caption=f"Frame {idx + 1}: {frame.display_timestamp}")
    if len(frames) > 4:
        with st.expander(f"Show all {len(frames)} frames"):
            cols2 = st.columns(4)
            for idx, frame in enumerate(frames[4:], start=5):
                with cols2[(idx - 5) % 4]:
                    st.image(frame.image_data_url, caption=f"Frame {idx}: {frame.display_timestamp}")

    # ---- Step 2: CVR generation (vision) ---------------------------------
    _step_header(2, "CVR generation (Qwen2.5-VL 32B Instruct)")
    with st.spinner("Calling vision model..."):
        try:
            vision_client = FireworksCvrClient()
            t2 = time.perf_counter()
            raw_cvr = vision_client.generate_cvr(frames, meta)
            t3 = time.perf_counter()
        except (CvrGenerationError, Exception) as error:
            st.error(f"Vision model call failed: {error}")
            return

    parsed = parse_cvr_response("demo", raw_cvr)
    if not parsed.succeeded or parsed.report is None:
        st.error(f"CVR parsing failed: {parsed.failure}")
        with st.expander("Raw response"):
            st.code(raw_cvr, language="json")
        return

    report = parsed.report
    st.success(f"CVR generated in {t3 - t2:.1f}s")

    cvr_col1, cvr_col2 = st.columns([1, 1])
    with cvr_col1:
        st.json(report.to_dict())
    with cvr_col2:
        st.markdown("**Scene:**")
        st.write(report.scene)
        st.markdown("**Primary subjects:**")
        st.write(", ".join(report.primary_subjects))
        st.markdown("**Important objects:**")
        st.write(", ".join(report.important_objects))
        st.markdown("**Timeline:**")
        for event in report.timeline:
            st.markdown(f"- {event}")
        st.markdown("**Overall summary:**")
        st.write(report.overall_summary)

    # ---- Step 3: Style generation (text) ---------------------------------
    _step_header(3, "Style generation (gpt-oss-120b)")
    with st.spinner("Generating captions in all 4 styles..."):
        try:
            style_client = FireworksStyleClient()
            t4 = time.perf_counter()
            result = generate_all_captions(style_client, report)
            t5 = time.perf_counter()
        except (StyleGenerationError, Exception) as error:
            st.error(f"Style generation failed: {error}")
            return
        else:
            pass

    st.success(f"All 4 captions generated in {t5 - t4:.1f}s")

    cards = st.columns(4)
    for card, style in zip(cards, ["Formal", "Sarcastic", "Humorous-Tech", "Humorous-Non-Tech"]):
        caption = result.captions.get(style, "")
        with card:
            color = STYLE_COLORS.get(style, "#FFFFFF")
            st.markdown(
                f"<div style='border:2px solid {color}; border-radius:10px; "
                f"padding:16px; height:100%;'>"
                f"<h4 style='color:{color}; margin-top:0;'>{style}</h4>"
                f"<p style='color:#FAFAFA;'>{caption or '(generation failed)'}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if result.failures:
        with st.expander("Generation failures"):
            for failure in result.failures:
                st.warning(f"**{failure.style}**: {failure.message}")

    # ---- Summary ---------------------------------------------------------
    total_elapsed = time.perf_counter() - full_start
    st.divider()
    st.markdown(f"### Pipeline complete in {total_elapsed:.1f}s")
    st.caption(
        "Vision understanding ran exactly once. The style generator never saw "
        "the video — only the CVR text. This isolation is the primary safeguard "
        "against factual fabrication."
    )


def __get_api_key() -> str | None:
    import os
    return os.environ.get("FIREWORKS_API_KEY")


if __name__ == "__main__":
    main()