from unittest.mock import Mock

import json

from video_captioning_agent.contracts import FrameSample, VideoMetadata
from video_captioning_agent.cvr_client import (
    CVR_SYSTEM_PROMPT,
    CVR_USER_PROMPT_TEMPLATE,
    FIREWORKS_URL,
    VISION_MAX_TOKENS,
    VISION_MODEL_ID,
    VISION_TEMPERATURE,
    FireworksCvrClient,
    build_cvr_request,
)


def _frames() -> list[FrameSample]:
    return [
        FrameSample(9, 1.8, "data:image/jpeg;base64,bGF0ZQ=="),
        FrameSample(0, 0.0, "data:image/jpeg;base64,Zmlyc3Q="),
        FrameSample(
            5,
            None,
            "data:image/jpeg;base64,bWlkZGxl",
            "frame 2 of 3, exact timing unavailable",
        ),
    ]


def _metadata() -> VideoMetadata:
    return VideoMetadata(2.0, 5.0, 10, 32, 24)


def test_cvr_request_contains_ordered_frames_timestamps_metadata_and_schema() -> None:
    request = build_cvr_request(_frames(), _metadata())

    assert request["model"] == VISION_MODEL_ID
    assert request["temperature"] == VISION_TEMPERATURE
    assert request["max_tokens"] == VISION_MAX_TOKENS
    assert "OBSERVABLE FACTS ONLY" in request["messages"][0]["content"]
    assert "NO SPECULATION" in request["messages"][0]["content"]
    assert "STRICT JSON" in request["messages"][0]["content"]

    content = request["messages"][1]["content"]
    prompt = content[0]["text"]
    assert '"frame_count": 10' in prompt
    assert prompt.index("source frame 0): 0.0s") < prompt.index(
        "source frame 5): frame 2 of 3, exact timing unavailable"
    )
    assert prompt.index("source frame 5)") < prompt.index("source frame 9): 1.8s")
    assert '"scene"' in prompt
    assert '"primary_subjects"' in prompt
    assert '"important_objects"' in prompt
    assert '"timeline"' in prompt
    assert '"overall_summary"' in prompt

    image_urls = [block["image_url"]["url"] for block in content if block["type"] == "image_url"]
    assert image_urls == [
        "data:image/jpeg;base64,Zmlyc3Q=",
        "data:image/jpeg;base64,bWlkZGxl",
        "data:image/jpeg;base64,bGF0ZQ==",
    ]


def test_cvr_client_makes_exactly_one_vision_call_per_video() -> None:
    session = Mock()
    response = Mock()
    response.json.return_value = {
        "choices": [{"message": {"content": '{"scene": "Kitchen"}'}}]
    }
    session.post.return_value = response
    client = FireworksCvrClient(api_key="test-key", timeout_seconds=45.0, session=session)

    result = client.generate_cvr(_frames(), _metadata())

    assert result == '{"scene": "Kitchen"}'
    session.post.assert_called_once()
    call_args, call_kwargs = session.post.call_args
    assert call_args == (FIREWORKS_URL,)
    assert call_kwargs["timeout"] == 45.0
    assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert call_kwargs["json"]["model"] == VISION_MODEL_ID
    assert call_kwargs["json"]["temperature"] == 0.1
    assert call_kwargs["json"]["max_tokens"] == 1024
    response.raise_for_status.assert_called_once_with()


def test_default_kwargs_reproduce_constant_based_behavior_exactly() -> None:
    """Passing no kwargs (as pipeline.py does) must yield the same request as before."""

    request = build_cvr_request(_frames(), _metadata())

    metadata_json = json.dumps(_metadata().to_dict(), sort_keys=True)
    timestamp_lines = "\n".join(
        [
            "- Frame 1 (source frame 0): 0.0s",
            "- Frame 2 (source frame 5): frame 2 of 3, exact timing unavailable",
            "- Frame 3 (source frame 9): 1.8s",
        ]
    )

    assert request["model"] == VISION_MODEL_ID
    assert request["temperature"] == VISION_TEMPERATURE
    assert request["max_tokens"] == VISION_MAX_TOKENS
    assert request["messages"][0]["content"] == CVR_SYSTEM_PROMPT
    assert request["messages"][1]["content"][0]["text"] == CVR_USER_PROMPT_TEMPLATE.format(
        frame_count=3,
        duration_seconds=2.0,
        metadata_json=metadata_json,
        timestamp_lines=timestamp_lines,
    )


def test_client_kwargs_override_constants_in_constructed_request() -> None:
    session = Mock()
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
    session.post.return_value = response
    client = FireworksCvrClient(
        api_key="test-key",
        session=session,
        system_prompt="ALT SYSTEM",
        user_prompt_template="ALT USER {frame_count} {duration_seconds:.1f} {metadata_json} {timestamp_lines}",
        model_id="accounts/fireworks/models/alt-model",
        temperature=0.7,
        max_tokens=512,
    )

    client.generate_cvr(_frames(), _metadata())

    request = session.post.call_args.kwargs["json"]
    assert request["model"] == "accounts/fireworks/models/alt-model"
    assert request["temperature"] == 0.7
    assert request["max_tokens"] == 512
    assert request["messages"][0]["content"] == "ALT SYSTEM"
    assert request["messages"][1]["content"][0]["text"].startswith("ALT USER 3 2.0 ")
