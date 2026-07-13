"""Tests for Task 10: CVR-only generation of all 4 supported styles unconditionally.

Per the revised Task 10 (see TASKS.md): this stage takes a CVR and the text-only model
client, generates one caption per supported style (always all 4), and never inspects any
task's requested-styles list. It uses ``gpt-oss-120b`` on Fireworks.
"""

import json
from unittest.mock import Mock

from video_captioning_agent.contracts import CanonicalVideoReport
from video_captioning_agent.styles import SUPPORTED_STYLES
from video_captioning_agent.style_generator import (
    STYLE_MODEL_ID,
    STYLE_TEMPERATURE,
    FireworksStyleClient,
    StyleGenerationError,
    build_style_request,
    generate_all_captions,
)


def _report() -> CanonicalVideoReport:
    return CanonicalVideoReport(
        scene="Kitchen",
        primary_subjects=("A person",),
        important_objects=("A bowl",),
        timeline=("0.0s: A person holds a bowl.",),
        overall_summary="A person holds a bowl in a kitchen.",
    )


def _client_returning(captions_by_style: dict[str, str]) -> FireworksStyleClient:
    session = Mock()
    responses = []
    for style in SUPPORTED_STYLES:
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": captions_by_style.get(style, f"{style} caption.")}}]
        }
        responses.append(response)
    session.post.side_effect = responses
    return FireworksStyleClient(api_key="test-key", session=session)


def test_generates_exactly_four_requests_one_per_supported_style() -> None:
    client = _client_returning({})

    result = generate_all_captions(client, _report())

    assert client._session.post.call_count == len(SUPPORTED_STYLES)
    requested_styles = [
        call.kwargs["json"]["messages"][1]["content"].splitlines()[0].removeprefix("Target style: ")
        for call in client._session.post.call_args_list
    ]
    assert sorted(requested_styles) == sorted(SUPPORTED_STYLES)
    assert set(result.captions) == set(SUPPORTED_STYLES)
    assert result.failures == ()


def test_all_four_requests_use_the_same_cvr_and_carry_no_visual_input() -> None:
    client = _client_returning({})

    generate_all_captions(client, _report())

    expected_cvr_json = _report().to_json()
    for call in client._session.post.call_args_list:
        request = call.kwargs["json"]
        serialized_request = json.dumps(request)
        assert request["temperature"] == STYLE_TEMPERATURE
        assert request["model"] == STYLE_MODEL_ID
        assert expected_cvr_json in request["messages"][1]["content"]
        assert "data:image" not in serialized_request
        assert "image_url" not in serialized_request
        assert "video_url" not in serialized_request
        assert "frame_index" not in serialized_request


def test_generation_failure_for_one_style_does_not_stop_other_styles() -> None:
    session = Mock()
    responses = []
    for style in SUPPORTED_STYLES:
        if style == "Sarcastic":
            bad_response = Mock()
            bad_response.json.side_effect = StyleGenerationError("model unavailable")
            responses.append(bad_response)
        else:
            response = Mock()
            response.json.return_value = {"choices": [{"message": {"content": f"{style} caption."}}]}
            responses.append(response)
    session.post.side_effect = responses
    client = FireworksStyleClient(api_key="test-key", session=session)

    result = generate_all_captions(client, _report())

    assert set(result.captions) == set(SUPPORTED_STYLES)
    assert result.captions["Sarcastic"] == ""
    successful = {s: f"{s} caption." for s in SUPPORTED_STYLES if s != "Sarcastic"}
    assert {s: result.captions[s] for s in successful} == successful
    assert [failure.style for failure in result.failures] == ["Sarcastic"]


def test_failed_style_key_is_present_as_empty_string_for_any_failure_mode() -> None:
    """A failure in one of the 4 style calls never omits its key.

    Covers the failure modes that can take down a single style call: a
    ``StyleGenerationError`` (malformed/empty body, with a captured raw body),
    a transport-level ``requests`` exception (timeout), and an HTTP error raised
    by ``raise_for_status`` (with a response body). In every case the failed
    style's key remains present in the output dict with an empty-string value,
    and all 4 supported styles are always represented.
    """

    import requests

    raw_sarcastic_body = (
        "I'm sorry, but I can't generate a sarcastic caption for this content."
    )
    raw_http_body = '{"error":"internal server error"}'

    session = Mock()
    responses: list[Mock] = []

    # Iteration order matches SUPPORTED_STYLES: Formal, Sarcastic, Humorous-Tech,
    # Humorous-Non-Tech. Build the side_effect list in that same order.
    formal_response = Mock()
    formal_response.raise_for_status = Mock()
    formal_response.json.return_value = {
        "choices": [{"message": {"content": "Formal caption."}}]
    }
    responses.append(formal_response)

    sarcastic_response = Mock()
    sarcastic_response.raise_for_status = Mock()
    sarcastic_response.json.return_value = {
        "choices": [{"message": {"content": 42}}]
    }
    sarcastic_response.text = raw_sarcastic_body
    responses.append(sarcastic_response)

    tech_response = Mock()
    tech_response.raise_for_status.side_effect = requests.HTTPError(
        "500 Server Error", response=Mock(text=raw_http_body)
    )
    responses.append(tech_response)

    non_tech_response = Mock()
    non_tech_response.raise_for_status.side_effect = requests.Timeout(
        "read timed out"
    )
    responses.append(non_tech_response)

    session.post.side_effect = responses
    client = FireworksStyleClient(api_key="test-key", session=session)

    result = generate_all_captions(client, _report())

    assert set(result.captions) == set(SUPPORTED_STYLES)
    assert result.captions["Formal"] == "Formal caption."
    assert result.captions["Sarcastic"] == ""
    assert result.captions["Humorous-Tech"] == ""
    assert result.captions["Humorous-Non-Tech"] == ""
    failed_styles = sorted(failure.style for failure in result.failures)
    assert failed_styles == ["Humorous-Non-Tech", "Humorous-Tech", "Sarcastic"]
    sarcastic_failure = next(f for f in result.failures if f.style == "Sarcastic")
    assert sarcastic_failure.raw_response == raw_sarcastic_body
    tech_failure = next(f for f in result.failures if f.style == "Humorous-Tech")
    assert tech_failure.raw_response == raw_http_body
    non_tech_failure = next(
        f for f in result.failures if f.style == "Humorous-Non-Tech"
    )
    assert non_tech_failure.raw_response is None


def test_style_request_construction_is_deterministic() -> None:
    cvr_json = _report().to_json()

    assert build_style_request(cvr_json, "Formal") == build_style_request(cvr_json, "Formal")


def test_style_request_uses_gpt_oss_120b_model_id() -> None:
    request = build_style_request(_report().to_json(), "Sarcastic")

    assert request["model"] == STYLE_MODEL_ID
    assert request["model"] == "accounts/fireworks/models/gpt-oss-120b"