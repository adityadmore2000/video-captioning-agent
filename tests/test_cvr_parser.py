import json

import pytest

from video_captioning_agent.cvr_parser import (
    CvrParseFailureKind,
    parse_cvr_response,
)


def _valid_cvr() -> dict[str, object]:
    return {
        "scene": "Kitchen",
        "primary_subjects": ["A person"],
        "important_objects": ["A bowl"],
        "timeline": ["0.0s: A person holds a bowl."],
        "overall_summary": "A person holds a bowl in a kitchen.",
    }


def test_parse_cvr_response_accepts_valid_json_matching_the_contract() -> None:
    result = parse_cvr_response("v1", json.dumps(_valid_cvr()))

    assert result.succeeded
    assert result.report is not None
    assert result.report.scene == "Kitchen"
    assert result.report.timeline == ("0.0s: A person holds a bowl.",)


@pytest.mark.parametrize(
    "raw_response",
    [
        "```json\n" + json.dumps(_valid_cvr()) + "\n```",
        "Here is the CVR: " + json.dumps(_valid_cvr()),
        '{"scene": "Kitchen",',
    ],
)
def test_parse_cvr_response_rejects_markdown_prose_and_malformed_json(
    raw_response: str,
) -> None:
    result = parse_cvr_response("v1", raw_response)

    assert not result.succeeded
    assert result.report is None
    assert result.failure is not None
    assert result.failure.kind is CvrParseFailureKind.INVALID_JSON


@pytest.mark.parametrize(
    "payload",
    [
        {
            "scene": "Kitchen",
            "primary_subjects": ["A person"],
            "important_objects": ["A bowl"],
            "overall_summary": "A person holds a bowl in a kitchen.",
        },
        {
            "scene": "Kitchen",
            "primary_subjects": "A person",
            "important_objects": ["A bowl"],
            "timeline": ["0.0s: A person holds a bowl."],
            "overall_summary": "A person holds a bowl in a kitchen.",
        },
    ],
)
def test_parse_cvr_response_rejects_missing_or_invalid_contract_fields(
    payload: dict[str, object],
) -> None:
    result = parse_cvr_response("v1", json.dumps(payload))

    assert not result.succeeded
    assert result.report is None
    assert result.failure is not None
    assert result.failure.kind is CvrParseFailureKind.INVALID_CONTRACT
