"""Serializable data contracts shared by the captioning pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping


class ContractValidationError(ValueError):
    """Raised when external or model data does not satisfy a contract."""


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")
    return value


def _require_non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractValidationError(f"{field_name} must be a non-negative integer")
    return value


def _require_non_negative_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ContractValidationError(f"{field_name} must be a non-negative number")
    return float(value)


def _require_string_list(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ContractValidationError(f"{field_name} must be a list of non-empty strings")
    return tuple(_require_string(item, f"{field_name}[{index}]") for index, item in enumerate(value))


def _require_mapping(value: object, contract_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{contract_name} must be a JSON object")
    return value


def _require_exact_fields(
    payload: Mapping[str, Any], expected_fields: set[str], contract_name: str
) -> None:
    actual_fields = set(payload)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        unexpected = sorted(actual_fields - expected_fields)
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected fields: {', '.join(unexpected)}")
        raise ContractValidationError(f"{contract_name} has {'; '.join(details)}")


@dataclass(frozen=True, slots=True)
class VideoTask:
    """A single captioning request read from ``tasks.json``."""

    task_id: str
    video_url: str
    styles: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_string(self.task_id, "task_id")
        _require_string(self.video_url, "video_url")
        _require_string_list(self.styles, "styles")

    @classmethod
    def from_dict(cls, payload: object) -> "VideoTask":
        data = _require_mapping(payload, "VideoTask")
        required_fields = {"task_id", "video_url", "styles"}
        missing = required_fields - set(data)
        if missing:
            raise ContractValidationError(
                f"VideoTask missing fields: {', '.join(sorted(missing))}"
            )
        return cls(
            task_id=_require_string(data["task_id"], "task_id"),
            video_url=_require_string(data["video_url"], "video_url"),
            styles=_require_string_list(data["styles"], "styles"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "video_url": self.video_url,
            "styles": list(self.styles),
        }


@dataclass(frozen=True, slots=True)
class FrameSample:
    """A timestamped JPEG frame supplied to the vision model."""

    frame_index: int
    timestamp_seconds: float | None
    image_data_url: str
    timestamp_label: str | None = None

    def __post_init__(self) -> None:
        _require_non_negative_int(self.frame_index, "frame_index")
        if self.timestamp_seconds is None:
            _require_string(self.timestamp_label, "timestamp_label")
        else:
            _require_non_negative_number(self.timestamp_seconds, "timestamp_seconds")
            if self.timestamp_label is not None:
                _require_string(self.timestamp_label, "timestamp_label")
        _require_string(self.image_data_url, "image_data_url")

    @property
    def display_timestamp(self) -> str:
        """Return an honest label for downstream CVR prompt construction."""

        if self.timestamp_label is not None:
            return self.timestamp_label
        return f"{self.timestamp_seconds:.1f}s"

    def to_dict(self) -> dict[str, object]:
        return {
            "frame_index": self.frame_index,
            "timestamp_seconds": self.timestamp_seconds,
            "image_data_url": self.image_data_url,
            "timestamp_label": self.timestamp_label,
        }


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Inspection metadata for a readable local video."""

    duration_seconds: float
    fps: float
    frame_count: int
    width: int
    height: int

    def __post_init__(self) -> None:
        _require_non_negative_number(self.duration_seconds, "duration_seconds")
        _require_non_negative_number(self.fps, "fps")
        _require_non_negative_int(self.frame_count, "frame_count")
        _require_non_negative_int(self.width, "width")
        _require_non_negative_int(self.height, "height")

    def to_dict(self) -> dict[str, object]:
        return {
            "duration_seconds": self.duration_seconds,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True, slots=True)
class CanonicalVideoReport:
    """The five-field factual interface between vision and style generation."""

    scene: str
    primary_subjects: tuple[str, ...]
    important_objects: tuple[str, ...]
    timeline: tuple[str, ...]
    overall_summary: str

    def __post_init__(self) -> None:
        _require_string(self.scene, "scene")
        _require_string_list(self.primary_subjects, "primary_subjects")
        _require_string_list(self.important_objects, "important_objects")
        _require_string_list(self.timeline, "timeline")
        _require_string(self.overall_summary, "overall_summary")

    @classmethod
    def from_dict(cls, payload: object) -> "CanonicalVideoReport":
        data = _require_mapping(payload, "CanonicalVideoReport")
        _require_exact_fields(
            data,
            {
                "scene",
                "primary_subjects",
                "important_objects",
                "timeline",
                "overall_summary",
            },
            "CanonicalVideoReport",
        )
        return cls(
            scene=_require_string(data["scene"], "scene"),
            primary_subjects=_require_string_list(
                data["primary_subjects"], "primary_subjects"
            ),
            important_objects=_require_string_list(
                data["important_objects"], "important_objects"
            ),
            timeline=_require_string_list(data["timeline"], "timeline"),
            overall_summary=_require_string(data["overall_summary"], "overall_summary"),
        )

    @classmethod
    def from_json(cls, serialized: str) -> "CanonicalVideoReport":
        try:
            payload = json.loads(serialized)
        except json.JSONDecodeError as error:
            raise ContractValidationError("CanonicalVideoReport must be valid JSON") from error
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, object]:
        return {
            "scene": self.scene,
            "primary_subjects": list(self.primary_subjects),
            "important_objects": list(self.important_objects),
            "timeline": list(self.timeline),
            "overall_summary": self.overall_summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True, slots=True)
class TaskResult:
    """Captions produced for a task, excluding its internal CVR."""

    task_id: str
    captions: Mapping[str, str]

    def __post_init__(self) -> None:
        _require_string(self.task_id, "task_id")
        if not isinstance(self.captions, Mapping):
            raise ContractValidationError("captions must be a mapping of styles to strings")
        for style, caption in self.captions.items():
            _require_string(style, "captions style")
            _require_string(caption, f"captions[{style}]")

    def to_dict(self) -> dict[str, object]:
        return {"task_id": self.task_id, "captions": dict(self.captions)}
