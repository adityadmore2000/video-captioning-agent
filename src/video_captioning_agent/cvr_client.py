"""Canonical Video Report prompt construction and Fireworks VLM access."""

from __future__ import annotations

import json
import os
from typing import Any, Sequence

import requests

from .contracts import FrameSample, VideoMetadata


FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
VISION_MODEL_ID = "accounts/fireworks/models/qwen2p5-vl-32b-instruct"
VISION_TEMPERATURE = 0.1
VISION_MAX_TOKENS = 1024
DEFAULT_VISION_TIMEOUT_SECONDS = 120.0

CVR_SYSTEM_PROMPT = """You are a strict, objective video-understanding agent. Your sole purpose is to analyze sequences of video frames and generate a Canonical Video Report (CVR).

Core Directives:
1. OBSERVABLE FACTS ONLY: Describe only what is explicitly visible in the frames.
2. NO SPECULATION: Do not infer emotions, intentions, or off-screen events. If an action is ambiguous, describe the physical motion, not the assumed purpose.
3. NO HUMOR OR STYLE: The CVR must be completely dry, factual, and objective.
4. TEMPORAL AWARENESS: Pay close attention to the chronological order of frames to accurately construct the timeline of events.
5. STRICT JSON: You must output ONLY valid JSON matching the requested schema. Do not wrap the output in markdown code blocks and do not include any conversational text before or after the JSON."""


class CvrGenerationError(RuntimeError):
    """Raised when Fireworks returns no usable CVR text response."""


def build_cvr_request(
    frames: Sequence[FrameSample], metadata: VideoMetadata
) -> dict[str, Any]:
    """Build one multimodal CVR request with chronological frame context."""

    if not frames:
        raise ValueError("At least one frame is required to build a CVR request")

    ordered_frames = sorted(frames, key=lambda frame: frame.frame_index)
    timestamp_lines = "\n".join(
        f"- Frame {ordinal} (source frame {frame.frame_index}): "
        f"{frame.display_timestamp}"
        for ordinal, frame in enumerate(ordered_frames, start=1)
    )
    user_prompt = _build_cvr_user_prompt(
        frame_count=len(ordered_frames),
        metadata=metadata,
        timestamp_lines=timestamp_lines,
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for ordinal, frame in enumerate(ordered_frames, start=1):
        content.extend(
            [
                {
                    "type": "text",
                    "text": (
                        f"Frame {ordinal} (source frame {frame.frame_index}, "
                        f"{frame.display_timestamp})"
                    ),
                },
                {"type": "image_url", "image_url": {"url": frame.image_data_url}},
            ]
        )

    return {
        "model": VISION_MODEL_ID,
        "temperature": VISION_TEMPERATURE,
        "max_tokens": VISION_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": CVR_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    }


def _build_cvr_user_prompt(
    frame_count: int, metadata: VideoMetadata, timestamp_lines: str
) -> str:
    metadata_json = json.dumps(metadata.to_dict(), sort_keys=True)
    return f"""Below are {frame_count} frames sampled from a {metadata.duration_seconds:.1f}-second video, presented in chronological order.

Video Metadata:
{metadata_json}

Frame Timestamps:
{timestamp_lines}

Analyze these frames and generate the Canonical Video Report (CVR).

Return a JSON object with EXACTLY this structure:
{{
  "scene": "Brief description of the location or environment",
  "primary_subjects": ["Entity 1", "Entity 2"],
  "important_objects": ["Object 1", "Object 2"],
  "timeline": [
    "Event 1 at timestamp X",
    "Event 2 at timestamp Y"
  ],
  "overall_summary": "A single, concise sentence summarizing the factual progression of the entire video."
}}

Rules:
- Prioritize semantically important events over exhaustive background details.
- Only include primary subjects and important objects that are clearly visible and relevant to the action.
- If you cannot see something clearly, do not include it."""


class FireworksCvrClient:
    """Client for one factual visual-understanding call per video."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_VISION_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("FIREWORKS_API_KEY")
        if not self._api_key:
            raise ValueError("FIREWORKS_API_KEY must be configured")
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def generate_cvr(self, frames: Sequence[FrameSample], metadata: VideoMetadata) -> str:
        """Submit one vision request and return the raw CVR text for Task 8 parsing."""

        request_payload = build_cvr_request(frames, metadata)
        response = self._session.post(
            FIREWORKS_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            json=request_payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError) as error:
            raise CvrGenerationError("Fireworks response did not contain CVR text") from error
        if not isinstance(content, str):
            raise CvrGenerationError("Fireworks CVR content must be text")
        return content
