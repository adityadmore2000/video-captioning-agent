import json

import pytest

from video_captioning_agent.contracts import (
    CanonicalVideoReport,
    ContractValidationError,
    FrameSample,
    TaskResult,
    VideoMetadata,
    VideoTask,
)


def test_contracts_serialize_to_json_compatible_data() -> None:
    task = VideoTask("v1", "https://example.test/video.mp4", ("Formal", "Sarcastic"))
    frame = FrameSample(3, 1.5, "data:image/jpeg;base64,ZmFrZQ==")
    metadata = VideoMetadata(12.5, 24.0, 300, 1280, 720)
    report = CanonicalVideoReport(
        scene="A kitchen",
        primary_subjects=("A person",),
        important_objects=("A pan",),
        timeline=("0.0s: A person enters the kitchen.",),
        overall_summary="A person enters a kitchen while carrying a pan.",
    )
    result = TaskResult("v1", {"formal": "A person enters a kitchen."})

    serialized = json.dumps(
        {
            "task": task.to_dict(),
            "frame": frame.to_dict(),
            "metadata": metadata.to_dict(),
            "report": report.to_dict(),
            "result": result.to_dict(),
        }
    )

    assert json.loads(serialized)["report"] == {
        "scene": "A kitchen",
        "primary_subjects": ["A person"],
        "important_objects": ["A pan"],
        "timeline": ["0.0s: A person enters the kitchen."],
        "overall_summary": "A person enters a kitchen while carrying a pan.",
    }


def test_cvr_round_trips_through_json() -> None:
    payload = {
        "scene": "Outdoor path",
        "primary_subjects": ["A cyclist"],
        "important_objects": ["A bicycle"],
        "timeline": ["0.0s: The cyclist rides along the path."],
        "overall_summary": "A cyclist rides a bicycle along an outdoor path.",
    }

    report = CanonicalVideoReport.from_json(json.dumps(payload))

    assert json.loads(report.to_json()) == payload


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "scene": "Kitchen",
            "primary_subjects": [],
            "important_objects": [],
            "timeline": [],
            "overall_summary": "A still kitchen is shown.",
            "key_actions": [],
        },
        {
            "scene": "Kitchen",
            "primary_subjects": "A person",
            "important_objects": [],
            "timeline": [],
            "overall_summary": "A person is in a kitchen.",
        },
        {
            "scene": "Kitchen",
            "primary_subjects": [],
            "important_objects": [],
            "timeline": [123],
            "overall_summary": "A person is in a kitchen.",
        },
    ],
)
def test_cvr_rejects_malformed_data(payload: object) -> None:
    with pytest.raises(ContractValidationError):
        CanonicalVideoReport.from_dict(payload)


def test_cvr_rejects_invalid_json() -> None:
    with pytest.raises(ContractValidationError):
        CanonicalVideoReport.from_json("not json")
