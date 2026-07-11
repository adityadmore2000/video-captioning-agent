"""Conservative parsing and validation of raw CVR model responses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

from .contracts import CanonicalVideoReport, ContractValidationError


class CvrParseFailureKind(str, Enum):
    """Categories of a non-fatal task-level CVR parsing failure."""

    INVALID_JSON = "invalid_json"
    INVALID_CONTRACT = "invalid_contract"


@dataclass(frozen=True, slots=True)
class CvrParseFailure:
    """Details of a rejected CVR response without inventing replacement facts."""

    task_id: str
    kind: CvrParseFailureKind
    message: str


@dataclass(frozen=True, slots=True)
class CvrParseResult:
    """A validated CVR or a structured per-task parse failure."""

    task_id: str
    report: CanonicalVideoReport | None = None
    failure: CvrParseFailure | None = None

    @property
    def succeeded(self) -> bool:
        return self.report is not None and self.failure is None


def parse_cvr_response(task_id: str, raw_response: object) -> CvrParseResult:
    """Accept only a single strict JSON object matching the CVR contract."""

    if not isinstance(raw_response, str):
        return _failure(
            task_id,
            CvrParseFailureKind.INVALID_JSON,
            "CVR response must be JSON text",
        )
    try:
        payload = json.loads(
            raw_response,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_standard_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as error:
        return _failure(task_id, CvrParseFailureKind.INVALID_JSON, str(error))

    try:
        report = CanonicalVideoReport.from_dict(payload)
    except ContractValidationError as error:
        return _failure(task_id, CvrParseFailureKind.INVALID_CONTRACT, str(error))
    return CvrParseResult(task_id=task_id, report=report)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_standard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _failure(
    task_id: str, kind: CvrParseFailureKind, reason: str
) -> CvrParseResult:
    return CvrParseResult(
        task_id=task_id,
        failure=CvrParseFailure(
            task_id=task_id,
            kind=kind,
            message=f"Rejected CVR for task {task_id}: {reason}",
        ),
    )
