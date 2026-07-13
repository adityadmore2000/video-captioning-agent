"""Streamlit demo for the Video Captioning Agent.

A single bundled sample video, one "Run demo" button, and the four generated
caption styles printed as output. No configuration knobs — just show the output.

Run locally:
    cd <repo-root>
    streamlit run demo/app.py

Or via Streamlit Community Cloud:
    deploy from this GitHub repo, set FIREWORKS_API_KEY as a secret, main
    file path = demo/app.py.
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

from video_captioning_agent.cvr_client import CvrGenerationError, FireworksCvrClient
from video_captioning_agent.cvr_parser import parse_cvr_response
from video_captioning_agent.frame_sampler import FrameSamplingError, sample_frames
from video_captioning_agent.style_generator import (
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

STYLES = ("Formal", "Sarcastic", "Humorous-Tech", "Humorous-Non-Tech")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


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

    with st.spinner("Generating Canonical Video Report (vision model)..."):
        try:
            vision_client = FireworksCvrClient()
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
            style_client = FireworksStyleClient()
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