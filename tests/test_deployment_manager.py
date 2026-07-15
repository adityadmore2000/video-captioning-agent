"""Mocked-HTTP tests for the Fireworks deployment provisioner.

Covers account resolution, list/get/create/poll, the 409 race, base-model
normalization, process-lifetime caching, and best-effort teardown. Mirrors the
``Mock`` session pattern of ``tests/test_cvr_client.py``.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
import requests

from video_captioning_agent.deployment_manager import (
    DEFAULT_MAX_REPLICAS,
    DEFAULT_MIN_REPLICAS,
    DeploymentProvisioningError,
    FireworksDeploymentManager,
    _normalize_accelerator_type,
    _normalize_base_model,
    resolve_vision_model_id,
)
from video_captioning_agent.cvr_client import VISION_MODEL_ID


ACCOUNT_ID = "adityadmore2000-x698"
ACCOUNT_NAME = f"accounts/{ACCOUNT_ID}"
DEPLOYMENT_NAME = "video-captioning-vlm"
DEPLOYMENT_FULL_NAME = f"{ACCOUNT_NAME}/deployments/{DEPLOYMENT_NAME}"
BASE_MODEL_BARE = "qwen2.5-vl-32b-instruct"
BASE_MODEL_FULL = "accounts/fireworks/models/qwen2.5-vl-32b-instruct"


class MockResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no payload")
        return self._payload


def _build_manager(session: Mock, **kwargs) -> FireworksDeploymentManager:
    kwargs.setdefault("account_id", ACCOUNT_ID)
    return FireworksDeploymentManager(
        api_key="fw-test-key",
        session=session,
        poll_interval_seconds=0,
        provision_timeout_seconds=5,
        **kwargs,
    )


def _accounts_response() -> MockResponse:
    return MockResponse(200, {"accounts": [{"name": ACCOUNT_NAME}]})


def _deployment_payload(state: str, base_model: str = BASE_MODEL_FULL) -> dict:
    return {"name": DEPLOYMENT_FULL_NAME, "baseModel": base_model, "state": state}


def test_resolve_vision_model_id_explicit_wins() -> None:
    assert resolve_vision_model_id(vision_client_model_id="direct-id") == "direct-id"


def test_resolve_vision_model_id_env_model_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREWORKS_VISION_MODEL", "accounts/.../deployments/existing")
    monkeypatch.delenv("FIREWORKS_VISION_DEPLOYMENT_NAME", raising=False)
    monkeypatch.delenv("FIREWORKS_VISION_BASE_MODEL", raising=False)
    assert resolve_vision_model_id() == "accounts/.../deployments/existing"


def test_resolve_vision_model_id_falls_back_to_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FIREWORKS_VISION_MODEL", raising=False)
    monkeypatch.delenv("FIREWORKS_VISION_DEPLOYMENT_NAME", raising=False)
    monkeypatch.delenv("FIREWORKS_VISION_BASE_MODEL", raising=False)
    assert resolve_vision_model_id() == VISION_MODEL_ID


def test_normalize_base_model_accepts_bare_and_full() -> None:
    assert _normalize_base_model(BASE_MODEL_BARE) == BASE_MODEL_FULL
    assert _normalize_base_model(BASE_MODEL_FULL) == BASE_MODEL_FULL


def test_normalize_base_model_rejects_empty() -> None:
    with pytest.raises(DeploymentProvisioningError):
        _normalize_base_model("")


def test_account_resolution_uses_first_account() -> None:
    session = Mock()
    session.request.return_value = _accounts_response()
    manager = _build_manager(session, account_id=None)
    assert manager._require_account_id() == ACCOUNT_ID
    call = session.request.call_args
    assert call.args == ("GET", "https://api.fireworks.ai/v1/accounts")


def test_account_resolution_raises_when_no_accounts() -> None:
    session = Mock()
    session.request.return_value = MockResponse(200, {"accounts": []})
    manager = _build_manager(session, account_id=None)
    with pytest.raises(DeploymentProvisioningError, match="No Fireworks accounts"):
        manager._require_account_id()


def test_resolve_reuses_existing_ready_deployment() -> None:
    session = Mock()
    session.request.return_value = MockResponse(
        200,
        {"deployments": [_deployment_payload("READY")], "nextPageToken": ""},
    )
    manager = _build_manager(session)

    name = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    assert name == DEPLOYMENT_FULL_NAME
    # Only the list call should have happened; no POST create.
    assert session.request.call_count == 1
    method, url = session.request.call_args.args
    assert method == "GET" and url.endswith(f"/accounts/{ACCOUNT_ID}/deployments")


def test_resolve_polls_creating_then_ready() -> None:
    session = Mock()
    session.request.side_effect = [
        MockResponse(200, {"deployments": [_deployment_payload("CREATING")], "nextPageToken": ""}),
        MockResponse(200, _deployment_payload("CREATING")),
        MockResponse(200, _deployment_payload("READY")),
    ]
    manager = _build_manager(session)

    name = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    assert name == DEPLOYMENT_FULL_NAME
    calls = session.request.call_args_list
    # 1=list (found CREATING), 2,3 = poll get
    assert len(calls) == 3
    assert calls[0].args == ("GET", f"https://api.fireworks.ai/v1/accounts/{ACCOUNT_ID}/deployments")
    assert calls[1].args == ("GET", f"https://api.fireworks.ai/v1/accounts/{ACCOUNT_ID}/deployments/{DEPLOYMENT_NAME}")
    assert calls[2].args == calls[1].args


def test_resolve_raises_on_existing_failed_state() -> None:
    session = Mock()
    session.request.side_effect = [
        MockResponse(200, {"deployments": [_deployment_payload("FAILED")], "nextPageToken": ""}),
    ]
    manager = _build_manager(session)

    with pytest.raises(DeploymentProvisioningError, match="terminal state FAILED"):
        manager.resolve_vision_model(
            deployment_name=DEPLOYMENT_NAME,
            base_model=BASE_MODEL_BARE,
        )


def test_resolve_creates_when_not_found_then_polls_to_ready() -> None:
    session = Mock()
    session.request.side_effect = [
        MockResponse(200, {"deployments": [], "nextPageToken": ""}),
        MockResponse(200, _deployment_payload("CREATING")),
        MockResponse(200, _deployment_payload("READY")),
    ]
    manager = _build_manager(session)

    name = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    assert name == DEPLOYMENT_FULL_NAME
    calls = session.request.call_args_list
    # 1=list, 2=create POST, 3=poll get
    assert len(calls) == 3
    create_method, create_url = calls[1].args
    assert create_method == "POST"
    assert create_url == f"https://api.fireworks.ai/v1/accounts/{ACCOUNT_ID}/deployments"
    create_kwargs = calls[1].kwargs
    assert create_kwargs["params"] == {"deploymentId": DEPLOYMENT_NAME}
    body = create_kwargs["json"]
    assert body["baseModel"] == BASE_MODEL_FULL
    assert body["minReplicaCount"] == 0
    assert body["maxReplicaCount"] == 1


def test_resolve_uses_deployment_shape_when_provided() -> None:
    session = Mock()
    shape = "accounts/fireworks/deploymentShapes/qwen2.5-vl-minimal"
    session.request.side_effect = [
        MockResponse(200, {"deployments": [], "nextPageToken": ""}),
        MockResponse(200, _deployment_payload("READY")),
    ]
    manager = _build_manager(session)

    name = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_FULL,
        deployment_shape=shape,
    )

    assert name == DEPLOYMENT_FULL_NAME
    create_kwargs = session.request.call_args_list[1].kwargs
    body = create_kwargs["json"]
    assert body["deploymentShape"] == shape
    assert "minReplicaCount" not in body
    assert "maxReplicaCount" not in body


def test_create_409_race_relists_and_polls() -> None:
    session = Mock()
    session.request.side_effect = [
        MockResponse(200, {"deployments": [], "nextPageToken": ""}),
        MockResponse(409, {"error": {"code": "ALREADY_EXISTS", "message": "exists"}}),
        MockResponse(200, {"deployments": [_deployment_payload("CREATING")], "nextPageToken": ""}),
        MockResponse(200, _deployment_payload("READY")),
    ]
    manager = _build_manager(session)

    name = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    assert name == DEPLOYMENT_FULL_NAME
    calls = session.request.call_args_list
    # 1=list(not found), 2=POST(409), 3=relist(found CREATING), 4=poll get
    assert len(calls) == 4
    assert calls[1].args[0] == "POST"  # the 409


def test_create_409_with_no_listable_deployment_raises() -> None:
    session = Mock()
    session.request.side_effect = [
        MockResponse(200, {"deployments": [], "nextPageToken": ""}),
        MockResponse(409, {"error": {"code": "ALREADY_EXISTS", "message": "exists"}}),
        MockResponse(200, {"deployments": [], "nextPageToken": ""}),
        MockResponse(404, {"error": {"code": "NOT_FOUND", "message": "deployment not found"}}),
    ]
    manager = _build_manager(session)

    with pytest.raises(DeploymentProvisioningError, match="not listable or fetchable"):
        manager.resolve_vision_model(
            deployment_name=DEPLOYMENT_NAME,
            base_model=BASE_MODEL_BARE,
        )


def test_create_non_409_error_raises_with_gateway_code() -> None:
    session = Mock()
    session.request.side_effect = [
        MockResponse(200, {"deployments": [], "nextPageToken": ""}),
        MockResponse(403, {"error": {"code": "PERMISSION_DENIED", "message": "no access"}}),
    ]
    manager = _build_manager(session)

    with pytest.raises(DeploymentProvisioningError, match="gatewayCode=PERMISSION_DENIED"):
        manager.resolve_vision_model(
            deployment_name=DEPLOYMENT_NAME,
            base_model=BASE_MODEL_BARE,
        )


def test_provisioning_times_out_when_never_ready() -> None:
    session = Mock()
    # An infinite stream of CREATING responses: the first call is the list
    # (deployment found in CREATING), every subsequent call is a Get poll that
    # also stays CREATING. The manager must give up after the timeout.
    def always_creating(*args: object, **kwargs: object) -> MockResponse:
        url = args[1] if len(args) > 1 else str(kwargs.get("url", ""))
        if url.endswith(f"/deployments/{DEPLOYMENT_NAME}"):
            return MockResponse(200, _deployment_payload("CREATING"))
        return MockResponse(
            200,
            {"deployments": [_deployment_payload("CREATING")], "nextPageToken": ""},
        )

    session.request.side_effect = always_creating
    manager = FireworksDeploymentManager(
        api_key="fw-test-key",
        session=session,
        account_id=ACCOUNT_ID,
        poll_interval_seconds=0,
        provision_timeout_seconds=0.01,
    )

    with pytest.raises(DeploymentProvisioningError, match="did not reach READY"):
        manager.resolve_vision_model(
            deployment_name=DEPLOYMENT_NAME,
            base_model=BASE_MODEL_BARE,
        )


def test_resolved_deployment_is_cached_for_process_lifetime() -> None:
    session = Mock()
    session.request.return_value = MockResponse(
        200,
        {"deployments": [_deployment_payload("READY")], "nextPageToken": ""},
    )
    manager = _build_manager(session)

    first = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )
    second = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    assert first == second == DEPLOYMENT_FULL_NAME
    assert session.request.call_count == 1, "second resolve must hit the cache, no HTTP"


def test_teardown_issues_delete_when_cached() -> None:
    session = Mock()
    session.request.return_value = MockResponse(
        200,
        {"deployments": [_deployment_payload("READY")], "nextPageToken": ""},
    )
    delete_response = MockResponse(200)
    session.delete.return_value = delete_response
    manager = _build_manager(session)
    manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    manager.teardown(DEPLOYMENT_NAME)

    session.delete.assert_called_once()
    call = session.delete.call_args
    assert call.args[0] == (
        f"https://api.fireworks.ai/v1/accounts/{ACCOUNT_ID}/deployments/{DEPLOYMENT_NAME}"
    )


def test_teardown_is_best_effort_and_never_raises() -> None:
    session = Mock()
    session.request.return_value = MockResponse(
        200,
        {"deployments": [_deployment_payload("READY")], "nextPageToken": ""},
    )
    session.delete.side_effect = requests.RequestException("network down")
    manager = _build_manager(session)
    manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    # Must not raise.
    manager.teardown(DEPLOYMENT_NAME)


def test_teardown_noops_when_never_provisioned() -> None:
    session = Mock()
    manager = _build_manager(session)
    manager.teardown(DEPLOYMENT_NAME)
    session.delete.assert_not_called()


def test_pagination_traverses_next_page_token() -> None:
    session = Mock()
    other = {
        "name": f"{ACCOUNT_NAME}/deployments/some-other",
        "baseModel": BASE_MODEL_FULL,
        "state": "READY",
    }
    session.request.side_effect = [
        MockResponse(200, {"deployments": [other], "nextPageToken": "page2"}),
        MockResponse(
            200,
            {"deployments": [_deployment_payload("READY")], "nextPageToken": ""},
        ),
    ]
    manager = _build_manager(session)

    name = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    assert name == DEPLOYMENT_FULL_NAME
    calls = session.request.call_args_list
    # Both list pages must have been fetched before finding the deployment.
    assert len(calls) == 2
    assert calls[0].kwargs["params"] == {"pageSize": 200}
    assert calls[1].kwargs["params"] == {"pageSize": 200, "pageToken": "page2"}


def test_resolve_via_env_when_provisioning_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIREWORKS_VISION_MODEL", raising=False)
    monkeypatch.setenv("FIREWORKS_VISION_DEPLOYMENT_NAME", DEPLOYMENT_NAME)
    monkeypatch.setenv("FIREWORKS_VISION_BASE_MODEL", BASE_MODEL_BARE)
    session = Mock()
    session.request.side_effect = [
        _accounts_response(),
        MockResponse(200, {"deployments": [_deployment_payload("READY")], "nextPageToken": ""}),
    ]

    manager = FireworksDeploymentManager(
        api_key="fw-test-key",
        session=session,
        poll_interval_seconds=0,
        provision_timeout_seconds=5,
    )
    name = resolve_vision_model_id(manager=manager)
    assert name == DEPLOYMENT_FULL_NAME


def test_create_deployment_with_load_target() -> None:
    session = Mock()
    session.request.side_effect = [
        MockResponse(200, {"deployments": [], "nextPageToken": ""}),
        MockResponse(200, _deployment_payload("CREATING")),
        MockResponse(200, _deployment_payload("READY")),
    ]
    manager = _build_manager(session)

    name = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
        load_target=0.8,
    )

    assert name == DEPLOYMENT_FULL_NAME
    create_kwargs = session.request.call_args_list[1].kwargs
    body = create_kwargs["json"]
    assert body["autoscalingPolicy"] == {"loadTargets": {"default": 0.8}}


def test_create_deployment_without_load_target() -> None:
    session = Mock()
    session.request.side_effect = [
        MockResponse(200, {"deployments": [], "nextPageToken": ""}),
        MockResponse(200, _deployment_payload("CREATING")),
        MockResponse(200, _deployment_payload("READY")),
    ]
    manager = _build_manager(session)

    name = manager.resolve_vision_model(
        deployment_name=DEPLOYMENT_NAME,
        base_model=BASE_MODEL_BARE,
    )

    assert name == DEPLOYMENT_FULL_NAME
    create_kwargs = session.request.call_args_list[1].kwargs
    body = create_kwargs["json"]
    assert "autoscalingPolicy" not in body


def test_normalize_accelerator_type_none() -> None:
    assert _normalize_accelerator_type(None) is None


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("h200-141gb", "NVIDIA_H200_141GB"),
        ("h100-80gb", "NVIDIA_H100_80GB"),
        ("l4", "NVIDIA_L4_24GB"),
        ("a100-80gb", "NVIDIA_A100_80GB"),
    ],
)
def test_normalize_accelerator_type_known_aliases(alias: str, expected: str) -> None:
    assert _normalize_accelerator_type(alias) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "NVIDIA_H200_141GB",
        "nvidia_h200_141gb",
        "nViDiA_h200_141gb",
        "Nvidia_H200_141GB",
    ],
)
def test_normalize_accelerator_type_canonical_case_insensitive(raw: str) -> None:
    assert _normalize_accelerator_type(raw) == "NVIDIA_H200_141GB"


def test_normalize_accelerator_type_rejects_unknown() -> None:
    with pytest.raises(DeploymentProvisioningError, match="Unrecognized accelerator"):
        _normalize_accelerator_type("foo")