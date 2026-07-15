"""CVR-only text generation for all supported caption styles.

Per TASKS.md Decisions and the revised Task 10: this stage always generates captions for
all 4 supported styles unconditionally. It does NOT read or check a task's requested-styles
list; that filtering happens exclusively at result serialization (Task 12). Generation
uses ``gpt-oss-120b`` (hosted on Fireworks) in text-only mode, with the sensitive videos,
frames, and metadata fully isolated from this stage — only the serialized CVR is admitted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, Sequence

import requests

from .contracts import CanonicalVideoReport
from .cvr_client import FIREWORKS_URL
from .styles import SUPPORTED_STYLES


STYLE_MODEL_ID = "accounts/fireworks/models/gpt-oss-120b"
STYLE_TEMPERATURE = 0.2
STYLE_MAX_TOKENS = 256
DEFAULT_STYLE_TIMEOUT_SECONDS = 120.0

STYLE_SYSTEM_PROMPT = """You rewrite Canonical Video Reports as concise captions.
Use only facts stated in the supplied CVR. Do not introduce, remove, or alter factual
claims. Produce one or two readable sentences in the requested style.

Captions are meant for human readers, not a technical report. Write natural, flowing
prose. Do not carry over CVR-internal formatting or labels into the caption: never
include timestamps, frame numbers, "timestamp" labels, or any other artifact of the
CVR's structured timeline field. Instead, convey the order and progression of events
naturally (e.g. "then", "afterwards", "eventually", "by the end"). The caption should
read as a description a viewer would understand, not an annotated log."""


class StyleGenerationError(RuntimeError):
    """Raised when Fireworks returns no usable caption text.

    When the failure is due to a malformed/unexpected response body (rather than a
    transport error), ``raw`` carries the unparsed response text so callers can log
    it for diagnostics (e.g. refusal-adjacent hedging, prose commentary, empty body).
    """

    def __init__(self, message: str, *, raw: str | None = None) -> None:
        super().__init__(message)
        self.raw = raw


@dataclass(frozen=True, slots=True)
class CaptionGenerationFailure:
    """One non-fatal model failure associated with its style.

    ``raw_response`` is the unparsed HTTP body captured on a malformed-response failure
    (``None`` for transport/timeout failures that produced no body). It exists for
    diagnostics only and is never used as a caption.
    """

    style: str
    message: str
    raw_response: str | None = None


@dataclass(frozen=True, slots=True)
class CaptionGenerationResult:
    """All 4 supported-style captions plus isolated per-style failures.

    ``captions`` always contains exactly one entry per supported style: the generated
    caption on success, or the empty string on any failure (timeout, malformed
    response, validation rejection, exception). No key is ever omitted. Task 11
    validates this full 4-key set and Task 12 filters it down to each task's
    requested styles, substituting ``""`` for any requested style absent from the
    validated set.
    """

    captions: dict[str, str]
    failures: tuple[CaptionGenerationFailure, ...]


class StyleCaptionClient(Protocol):
    """The narrow text-only interface used by caption generation."""

    def generate_caption(self, cvr_json: str, style: str) -> str:
        """Generate one caption from one serialized CVR."""


def build_style_request(
    cvr_json: str,
    style: str,
    *,
    system_prompt: str = STYLE_SYSTEM_PROMPT,
    model_id: str = STYLE_MODEL_ID,
    temperature: float = STYLE_TEMPERATURE,
    max_tokens: int = STYLE_MAX_TOKENS,
) -> dict[str, object]:
    """Build a text-only request whose sole factual input is ``cvr_json``.

    Keyword arguments are optional and default to the module constants, so the production
    pipeline continues to call this function positionally and observes identical behavior.
    The experiments harness passes config-driven overrides through these kwargs.
    """

    if style not in SUPPORTED_STYLES:
        raise ValueError(f"Unsupported caption style: {style}")
    return {
        "model": model_id,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
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
    """Fireworks text-only client for CVR rewriting via ``gpt-oss-120b``.

    All model/parameter attributes are optional and default to the module constants;
    passing none of them reproduces the original behavior exactly. The experiments
    harness constructs this client with config-driven overrides via these same kwargs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_STYLE_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
        *,
        system_prompt: str = STYLE_SYSTEM_PROMPT,
        model_id: str | None = None,
        temperature: float = STYLE_TEMPERATURE,
        max_tokens: int = STYLE_MAX_TOKENS,
    ) -> None:
        self._api_key = api_key or os.environ.get("FIREWORKS_API_KEY")
        if not self._api_key:
            raise ValueError("FIREWORKS_API_KEY must be configured")
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._system_prompt = system_prompt
        self._model_id = (
            model_id
            or os.environ.get("FIREWORKS_STYLE_MODEL")
            or STYLE_MODEL_ID
        )
        self._temperature = temperature
        self._max_tokens = max_tokens

    def generate_caption(self, cvr_json: str, style: str) -> str:
        """Submit one text-only rewrite request for a supported style."""

        request_payload = build_style_request(
            cvr_json,
            style,
            system_prompt=self._system_prompt,
            model_id=self._model_id,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )

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
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise StyleGenerationError(
                "Fireworks response did not contain caption text",
                raw=_safe_response_text(response),
            ) from error
        if not isinstance(content, str):
            raise StyleGenerationError(
                "Fireworks caption content must be text",
                raw=_safe_response_text(response),
            )
        return content


def generate_all_captions(
    client: StyleCaptionClient, report: CanonicalVideoReport
) -> CaptionGenerationResult:
    """Generate all 4 supported-style captions from one CVR, isolating per-style failures.

    Always issues exactly ``len(SUPPORTED_STYLES)`` text-only requests (one per supported
    style) regardless of any task's requested-styles list. Each request receives only the
    serialized CVR — never frames, video URLs, or other metadata.

    The returned ``captions`` dict always contains all 4 supported-style keys: the
    generated caption on success, or the empty string on any failure (timeout, HTTP
    error, malformed/empty response, or exception). No key is ever omitted, so a
    failed style is represented as an empty string value (never an absent key) —
    matching the Decision that Task 10 always returns the full 4-style set. The
    structured ``failures`` tuple records the reason (and the raw response body where
    one was produced) for diagnostics without altering the captions dict.
    """

    cvr_json = report.to_json()
    captions: dict[str, str] = {style: "" for style in SUPPORTED_STYLES}
    failures: list[CaptionGenerationFailure] = []
    for style in SUPPORTED_STYLES:
        try:
            captions[style] = client.generate_caption(cvr_json, style)
        except (requests.RequestException, StyleGenerationError) as error:
            failures.append(
                CaptionGenerationFailure(
                    style=style,
                    message=str(error),
                    raw_response=_extract_raw_response(error),
                )
            )
    return CaptionGenerationResult(captions=captions, failures=tuple(failures))


def _extract_raw_response(error: BaseException) -> str | None:
    """Best-effort retrieval of the unparsed HTTP body carried by a style-generation error.

    ``StyleGenerationError.raw`` is set by the client when a response body was present
    but unusable (malformed/empty content). ``requests.HTTPError.response.text`` covers
    non-2xx responses. Transport failures (timeout, connection error) carry no body and
    yield ``None``.
    """

    raw = getattr(error, "raw", None)
    if isinstance(raw, str):
        return raw
    response = getattr(error, "response", None)
    text = getattr(response, "text", None)
    return text if isinstance(text, str) else None


def _safe_response_text(response: object) -> str | None:
    """Return ``response.text`` when it is a real string (guarded for mocks)."""

    text = getattr(response, "text", None)
    return text if isinstance(text, str) else None