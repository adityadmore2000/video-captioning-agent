import json
from unittest.mock import Mock

from video_captioning_agent.contracts import CanonicalVideoReport
from video_captioning_agent.style_generator import (
    STYLE_TEMPERATURE,
    FireworksStyleClient,
    StyleGenerationError,
    build_style_request,
    generate_requested_captions,
)


def _report() -> CanonicalVideoReport:
    return CanonicalVideoReport(
        scene="Kitchen",
        primary_subjects=("A person",),
        important_objects=("A bowl",),
        timeline=("0.0s: A person holds a bowl.",),
        overall_summary="A person holds a bowl in a kitchen.",
    )


def test_requested_supported_styles_each_use_the_same_cvr_and_no_visual_input() -> None:
    session = Mock()
    first_response = Mock()
    first_response.json.return_value = {"choices": [{"message": {"content": "Formal caption."}}]}
    second_response = Mock()
    second_response.json.return_value = {"choices": [{"message": {"content": "Tech caption."}}]}
    session.post.side_effect = [first_response, second_response]
    client = FireworksStyleClient(api_key="test-key", session=session)

    result = generate_requested_captions(
        client,
        _report(),
        ("Formal", "Unsupported", "Humorous-Tech"),
    )

    assert result.captions == {"Formal": "Formal caption.", "Humorous-Tech": "Tech caption."}
    assert result.failures == ()
    assert session.post.call_count == 2
    expected_cvr_json = _report().to_json()
    for call in session.post.call_args_list:
        request = call.kwargs["json"]
        serialized_request = json.dumps(request)
        assert request["temperature"] == STYLE_TEMPERATURE
        assert expected_cvr_json in request["messages"][1]["content"]
        assert "data:image" not in serialized_request
        assert "image_url" not in serialized_request
        assert "video_url" not in serialized_request
        assert "frame_index" not in serialized_request

    assert "Target style: Formal" in session.post.call_args_list[0].kwargs["json"]["messages"][1]["content"]
    assert "Target style: Humorous-Tech" in session.post.call_args_list[1].kwargs["json"]["messages"][1]["content"]


def test_generation_failure_for_one_style_does_not_stop_other_styles() -> None:
    client = Mock()
    client.generate_caption.side_effect = [
        StyleGenerationError("model unavailable"),
        "Tech caption.",
    ]

    result = generate_requested_captions(client, _report(), ("Formal", "Humorous-Tech"))

    assert result.captions == {"Humorous-Tech": "Tech caption."}
    assert len(result.failures) == 1
    assert result.failures[0].style == "Formal"


def test_style_request_construction_is_deterministic() -> None:
    cvr_json = _report().to_json()

    assert build_style_request(cvr_json, "Formal") == build_style_request(cvr_json, "Formal")
