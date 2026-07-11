"""CVR-only text generation for requested caption styles."""

from __future__ import annotations

import os
from typing import Protocol, Sequence

import requests

from .contracts import CanonicalVideoReport
from .cvr_client import FIREWORKS_URL, VISION_MODEL_ID
from .styles import SUPPORTED_STYLES, filter_supported_styles


STYLE_TEMPERATURE = 0.2
STYLE_MAX_TOKENS = 256
DEFAULT_STYLE_TIMEOUT_SECONDS = 120.0

STYLE_SYSTEM_PROMPT = """You rewrite Canonical Video Reports as concise captions.
Use only facts stated in the supplied CVR. Do not introduce, remove, or alter factual
claims. Produce one or two readable sentences in the requested style."""


class StyleGenerationError(RuntimeError):
    """Raised when Fireworks returns no usable caption text."""


class StyleCaptionClient(Protocol):
    """The narrow text-only interface used by caption generation."""

    def generate_caption(self, cvr_json: str, style: str) -> str:
        """Generate one caption from one serialized CVR."""


def build_style_request(cvr_json: str, style: str) -> dict[str, object]:
    """Build a text-only request whose sole factual input is ``cvr_json``."""

    if style not in SUPPORTED_STYLES:
        raise ValueError(f"Unsupported caption style: {style}")
    return {
        "model": VISION_MODEL_ID,
        "temperature": STYLE_TEMPERATURE,
        "max_tokens": STYLE_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": STYLE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Target style: {style}\n\n"
                    "Canonical Video Report (the only factual source):\n"
                    f"{cvr_json}\n\n"
                    "Write only the caption."
                ),
            },
        ],
    }


class FireworksStyleClient:
    """Fireworks client for text-only CVR rewriting."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_STYLE_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("FIREWORKS_API_KEY")
        if not self._api_key:
            raise ValueError("FIREWORKS_API_KEY must be configured")
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def generate_caption(self, cvr_json: str, style: str) -> str:
        """Submit one text-only rewrite request for a supported style."""

        response = self._session.post(
            FIREWORKS_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            json=build_style_request(cvr_json, style),
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError) as error:
            raise StyleGenerationError("Fireworks response did not contain caption text") from error
        if not isinstance(content, str):
            raise StyleGenerationError("Fireworks caption content must be text")
        return content


def generate_requested_captions(
    client: StyleCaptionClient,
    report: CanonicalVideoReport,
    requested_styles: Sequence[str],
) -> dict[str, str]:
    """Generate one caption for each requested supported style from one CVR."""

    supported_styles, _ = filter_supported_styles(requested_styles)
    cvr_json = report.to_json()
    return {
        style: client.generate_caption(cvr_json, style)
        for style in supported_styles
    }
