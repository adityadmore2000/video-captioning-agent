"""Automatic Fireworks deployment provisioning for the vision stage.

The vision (CVR) stage requires a deployed VLM that the calling Fireworks
account can access. This module eliminates the manual prerequisite of
pre-deploying a model in the Fireworks dashboard: when the pipeline starts,
it resolves the vision model identifier using one of three precedence rules
(see ``resolve_vision_model_id``):

1. ``FIREWORKS_VISION_MODEL`` set — use a pre-existing deployed/serverless
   model directly. No provisioning is performed.
2. ``FIREWORKS_VISION_DEPLOYMENT_NAME`` + ``FIREWORKS_VISION_BASE_MODEL`` set
   — provision (or reuse) a deployment of that base model and return the
   deployment resource name, which is the value accepted by the
   ``/inference/v1/chat/completions`` ``model`` field.
3. Neither set — fall back to the hardcoded ``VISION_MODEL_ID`` constant,
   preserving the original behavior.

The Deployment Management API surface used here (all Bearer-auth, base
``https://api.fireworks.ai/v1``):

* ``GET /accounts`` — list accounts accessible to the API key; the first
  account's resource name (``accounts/<id>``) provides the ``account_id``
  path segment for every subsequent call. No ``FIREWORKS_ACCOUNT_ID`` env
  var is required.
* ``GET /accounts/{account_id}/deployments`` — paginated list; the
  ``name`` field of each deployment has the form
  ``accounts/<account>/deployments/<deployment_id>``.
* ``GET /accounts/{account_id}/deployments/{deployment_id}`` — fetch one
  deployment's ``state`` (``CREATING``/``READY``/``FAILED``/...) for
  readiness polling.
* ``POST /accounts/{account_id}/deployments?deploymentId={name}`` — create
  a new deployment with a caller-chosen id; the body's required ``baseModel``
  field is the fully-qualified Fireworks base model resource name
  (``accounts/fireworks/models/<id>``). ``deploymentShape`` may be supplied
  instead of explicit replica counts when a shape is wanted.

The returned deployment ``name`` *is* the model id passed to inference. No
separate "resolve model id" step exists. Deployment creation/reuse is
idempotent across process restarts: an existing ``READY`` deployment with
the configured name is reused rather than duplicated.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from .cvr_client import VISION_MODEL_ID


LOGGER = logging.getLogger(__name__)

FIREWORKS_MGMT_BASE_URL = "https://api.fireworks.ai/v1"
FIREWORKS_BASE_MODEL_PREFIX = "accounts/fireworks/models/"

DEFAULT_PROVISION_TIMEOUT_SECONDS = 1200.0
DEFAULT_PROVISION_POLL_INTERVAL_SECONDS = 15.0
DEFAULT_MIN_REPLICAS = 0
DEFAULT_MAX_REPLICAS = 1

_DEPLOYMENT_NAME_PREFIX = "deployments/"
_TERMINAL_FAILURE_STATES = frozenset({"FAILED", "DELETED"})
_PROVISIONING_STATES = frozenset({"CREATING", "UPDATING", "STATE_UNSPECIFIED"})

_ACCELERATOR_TYPE_MAP: dict[str, str] = {
    "h200-141gb": "NVIDIA_H200_141GB",
    "h100-80gb": "NVIDIA_H100_80GB",
    "l4": "NVIDIA_L4_24GB",
    "a100-80gb": "NVIDIA_A100_80GB",
}


class DeploymentProvisioningError(RuntimeError):
    """Raised when a deployment cannot be created or reach the READY state.

    The ``gateway_code`` field carries the Fireworks ``gatewayCode`` string
    when one was surfaced by the API (e.g. ``ALREADY_EXISTS``,
    ``PERMISSION_DENIED``); it is ``None`` for transport-level failures.
    """


@dataclass(frozen=True, slots=True)
class DeploymentRef:
    """Resolved deployment reference. Cached for the process lifetime."""

    name: str
    base_model: str
    state: str


class FireworksDeploymentManager:
    """Manage one Fireworks VLM deployment's lifecycle for a single process.

    A single instance resolves the account id from the API key on first use,
    then lists/creates/polls deployments. The resolved deployment name is
    cached on the instance so subsequent ``resolve_vision_model`` calls do
    not re-provision.
    """

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        *,
        account_id: str | None = None,
        base_url: str = FIREWORKS_MGMT_BASE_URL,
        timeout_seconds: float = 30.0,
        provision_timeout_seconds: float = DEFAULT_PROVISION_TIMEOUT_SECONDS,
        poll_interval_seconds: float = DEFAULT_PROVISION_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._api_key = api_key or os.environ.get("FIREWORKS_API_KEY")
        if not self._api_key:
            raise ValueError("FIREWORKS_API_KEY must be configured")
        self._session = session or requests.Session()
        self._account_id: str | None = account_id
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._provision_timeout_seconds = provision_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._cache: dict[str, DeploymentRef] = {}

    def resolve_vision_model(
        self,
        *,
        deployment_name: str,
        base_model: str,
        min_replicas: int = DEFAULT_MIN_REPLICAS,
        max_replicas: int = DEFAULT_MAX_REPLICAS,
        deployment_shape: str | None = None,
        accelerator_type: str | None = None,
        accelerator_count: int | None = None,
        load_target: float | None = None,
    ) -> str:
        """Return a READY deployment ``name`` for the configured base model.

        Reuses an existing READY deployment with ``deployment_name`` when one
        exists; otherwise creates one and polls until READY. Raises
        ``DeploymentProvisioningError`` if creation or provisioning fails.
        """
        accelerator_type = _normalize_accelerator_type(accelerator_type)

        cached = self._cache.get(deployment_name)
        if cached is not None:
            return cached.name

        account_id = self._require_account_id()
        normalized_base = _normalize_base_model(base_model)
        existing = self._find_deployment(account_id, deployment_name)
        if existing is not None:
            ref = self._wait_for_ready(account_id, deployment_name, existing)
            self._cache[deployment_name] = ref
            return ref.name

        created = self._create_deployment(
            account_id,
            deployment_name=deployment_name,
            base_model=normalized_base,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            deployment_shape=deployment_shape,
            accelerator_type=accelerator_type,
            accelerator_count=accelerator_count,
            load_target=load_target,
        )
        ref = self._wait_for_ready(account_id, deployment_name, created)
        self._cache[deployment_name] = ref
        return ref.name

    def teardown(self, deployment_name: str) -> None:
        """Best-effort soft-delete of a deployment. Never raises.

        Called from the pipeline ``finally`` block when
        ``FIREWORKS_VISION_TEARDOWN`` is enabled.
        """
        cache_key = deployment_name
        ref = self._cache.get(cache_key)
        if ref is None:
            return
        try:
            account_id = self._account_id or self._resolve_account_id()
        except DeploymentProvisioningError:
            return
        url = f"{self._base_url}/accounts/{account_id}/deployments/{deployment_name}"
        try:
            response = self._session.delete(
                url,
                headers=self._auth_headers(),
                timeout=self._timeout_seconds,
            )
            if response.status_code not in (200, 204, 404):
                LOGGER.warning(
                    "Teardown of deployment %s returned HTTP %s: %s",
                    deployment_name,
                    response.status_code,
                    _safe_text(response),
                )
        except requests.RequestException as error:
            LOGGER.warning("Teardown of deployment %s failed: %s", deployment_name, error)

    def _require_account_id(self) -> str:
        if self._account_id is None:
            self._account_id = self._resolve_account_id()
        return self._account_id

    def _resolve_account_id(self) -> str:
        url = f"{self._base_url}/accounts"
        response = self._request("GET", url)
        payload = response.json()
        accounts = payload.get("accounts") if isinstance(payload, dict) else None
        if not accounts:
            raise DeploymentProvisioningError(
                "No Fireworks accounts are accessible to this API key; "
                "verify FIREWORKS_API_KEY"
            )
        first = accounts[0]
        name = first.get("name") if isinstance(first, dict) else None
        if not isinstance(name, str) or not name.startswith("accounts/"):
            raise DeploymentProvisioningError(
                f"Fireworks /accounts response did not contain a valid account name: {payload!r}"
            )
        return name.split("accounts/", 1)[1]

    def _find_deployment(self, account_id: str, deployment_name: str) -> dict[str, Any] | None:
        url = f"{self._base_url}/accounts/{account_id}/deployments"
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": 200}
            if page_token:
                params["pageToken"] = page_token
            response = self._request("GET", url, params=params)
            payload = response.json()
            for deployment in payload.get("deployments", []) or ():
                name = deployment.get("name") if isinstance(deployment, dict) else None
                if isinstance(name, str) and name.endswith(f"/{_DEPLOYMENT_NAME_PREFIX}{deployment_name}"):
                    return deployment
            page_token = payload.get("nextPageToken") if isinstance(payload, dict) else None
            if not page_token:
                return None

    def _create_deployment(
        self,
        account_id: str,
        *,
        deployment_name: str,
        base_model: str,
        min_replicas: int,
        max_replicas: int,
        deployment_shape: str | None,
        accelerator_type: str | None,
        accelerator_count: int | None,
        load_target: float | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/accounts/{account_id}/deployments"
        body: dict[str, Any] = {"baseModel": base_model}
        if deployment_shape:
            body["deploymentShape"] = deployment_shape
        else:
            body["minReplicaCount"] = min_replicas
            body["maxReplicaCount"] = max_replicas
        if accelerator_type:
            body["acceleratorType"] = accelerator_type
        if accelerator_count is not None:
            body["acceleratorCount"] = accelerator_count
        if load_target is not None:
            body["autoscalingPolicy"] = {
                "loadTargets": {"default": load_target}
            }
        try:
            response = self._session.request(
                "POST",
                url,
                headers=self._auth_headers(),
                params={"deploymentId": deployment_name},
                json=body,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as error:
            raise DeploymentProvisioningError(
                f"Failed to create deployment {deployment_name}: {error}"
            ) from error
        if response.status_code == 409:
            existing = self._find_deployment(account_id, deployment_name)
            if existing is not None:
                return existing
            raise DeploymentProvisioningError(
                f"Fireworks reported {deployment_name} already exists but it is not listable"
            )
        if response.status_code >= 400:
            raise _provisioning_error_from_response(
                f"Create deployment {deployment_name} failed",
                response,
            )
        try:
            return response.json()
        except ValueError as error:
            raise DeploymentProvisioningError(
                f"Create deployment {deployment_name} returned non-JSON: {_safe_text(response)}"
            ) from error

    def _wait_for_ready(
        self,
        account_id: str,
        deployment_name: str,
        current: dict[str, Any],
    ) -> DeploymentRef:
        state = current.get("state") if isinstance(current, dict) else None
        name = current.get("name") if isinstance(current, dict) else None
        base_model = current.get("baseModel") if isinstance(current, dict) else None
        if not isinstance(name, str) or not isinstance(base_model, str):
            raise DeploymentProvisioningError(
                f"Deployment {deployment_name} response missing name/baseModel: {current!r}"
            )
        if state == "READY":
            return DeploymentRef(name=name, base_model=base_model, state=state)
        if state in _TERMINAL_FAILURE_STATES:
            raise DeploymentProvisioningError(
                f"Deployment {deployment_name} is in terminal state {state}"
            )

        deadline = time.monotonic() + self._provision_timeout_seconds
        while time.monotonic() < deadline:
            time.sleep(self._poll_interval_seconds)
            ref = self._get_deployment(account_id, deployment_name)
            if ref.state == "READY":
                return ref
            if ref.state in _TERMINAL_FAILURE_STATES:
                raise DeploymentProvisioningError(
                    f"Deployment {deployment_name} entered terminal state {ref.state}"
                )
        raise DeploymentProvisioningError(
            f"Deployment {deployment_name} did not reach READY within "
            f"{self._provision_timeout_seconds:.0f}s (last state: {state})"
        )

    def _get_deployment(self, account_id: str, deployment_name: str) -> DeploymentRef:
        url = f"{self._base_url}/accounts/{account_id}/deployments/{deployment_name}"
        response = self._request("GET", url)
        payload = response.json()
        name = payload.get("name")
        base_model = payload.get("baseModel")
        state = payload.get("state")
        if not (isinstance(name, str) and isinstance(base_model, str) and isinstance(state, str)):
            raise DeploymentProvisioningError(
                f"Get deployment {deployment_name} returned malformed payload: {payload!r}"
            )
        return DeploymentRef(name=name, base_model=base_model, state=state)

    def _request(self, method: str, url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
        try:
            response = self._session.request(
                method,
                url,
                headers=self._auth_headers(),
                params=params,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as error:
            raise DeploymentProvisioningError(f"Fireworks {method} {url} failed: {error}") from error
        if response.status_code >= 400:
            raise _provisioning_error_from_response(f"Fireworks {method} {url} failed", response)
        return response

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }


def resolve_vision_model_id(
    *,
    vision_client_model_id: str | None = None,
    manager: FireworksDeploymentManager | None = None,
) -> str:
    """Resolve the vision model id used for ``FireworksCvrClient.model_id``.

    Precedence (env-driven, no code changes needed at the call sites):
    1. An explicit ``vision_client_model_id`` (passed by callers/tests) wins.
    2. ``FIREWORKS_VISION_MODEL`` env var → use a pre-existing model directly,
       no provisioning performed.
    3. ``FIREWORKS_VISION_DEPLOYMENT_NAME`` + ``FIREWORKS_VISION_BASE_MODEL``
       env vars → provision/reuse a deployment via ``FireworksDeploymentManager``
       and return the deployment resource name.
    4. Neither set → fall back to the ``VISION_MODEL_ID`` module constant.
    """
    if vision_client_model_id is not None:
        return vision_client_model_id

    explicit = os.environ.get("FIREWORKS_VISION_MODEL")
    if explicit:
        return explicit

    deployment_name = os.environ.get("FIREWORKS_VISION_DEPLOYMENT_NAME")
    base_model = os.environ.get("FIREWORKS_VISION_BASE_MODEL")
    if deployment_name and base_model:
        client = manager or FireworksDeploymentManager()
        accelerator_type = _normalize_accelerator_type(
            os.environ.get("FIREWORKS_VISION_ACCELERATOR_TYPE") or None
        )
        accelerator_count = None
        accelerator_count_raw = os.environ.get("FIREWORKS_VISION_ACCELERATOR_COUNT")
        if accelerator_type and accelerator_count_raw:
            accelerator_count = _env_int("FIREWORKS_VISION_ACCELERATOR_COUNT", -1)
        load_target_raw = os.environ.get("FIREWORKS_VISION_LOAD_TARGET")
        return client.resolve_vision_model(
            deployment_name=deployment_name,
            base_model=base_model,
            min_replicas=_env_int("FIREWORKS_VISION_MIN_REPLICAS", DEFAULT_MIN_REPLICAS),
            max_replicas=_env_int("FIREWORKS_VISION_MAX_REPLICAS", DEFAULT_MAX_REPLICAS),
            deployment_shape=os.environ.get("FIREWORKS_VISION_DEPLOYMENT_SHAPE") or None,
            accelerator_type=accelerator_type,
            accelerator_count=accelerator_count,
            load_target=_env_float("FIREWORKS_VISION_LOAD_TARGET", None) if load_target_raw else None,
        )

    return VISION_MODEL_ID


def _normalize_base_model(base_model: str) -> str:
    """Accept a bare id or a full ``accounts/fireworks/models/<id>`` name."""
    if not base_model:
        raise DeploymentProvisioningError("FIREWORKS_VISION_BASE_MODEL must not be empty")
    if base_model.startswith("accounts/"):
        return base_model
    return f"{FIREWORKS_BASE_MODEL_PREFIX}{base_model}"


def _normalize_accelerator_type(value: str | None) -> str | None:
    if value is None:
        return None
    canonical = _ACCELERATOR_TYPE_MAP.get(value.lower())
    if canonical is not None:
        return canonical
    if value.lower().startswith("nvidia_"):
        return value.upper()
    raise DeploymentProvisioningError(
        f"Unrecognized accelerator type: {value!r}. "
        f"Supported aliases: {', '.join(sorted(_ACCELERATOR_TYPE_MAP))}. "
        f"Or use a raw Fireworks enum value like NVIDIA_H200_141GB."
    )


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise DeploymentProvisioningError(
            f"{name} must be an integer, got {raw!r}"
        ) from error


def _env_float(name: str, default: float | None = None) -> float | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise DeploymentProvisioningError(
            f"{name} must be a number, got {raw!r}"
        ) from error


def _provisioning_error_from_response(prefix: str, response: requests.Response) -> DeploymentProvisioningError:
    code: str | None = None
    message = _safe_text(response)
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                code = error.get("code") if isinstance(error.get("code"), str) else None
                msg = error.get("message") if isinstance(error.get("message"), str) else None
                if msg:
                    message = msg
    except ValueError:
        pass
    suffix = f" [gatewayCode={code}]" if code else ""
    return DeploymentProvisioningError(f"{prefix}: HTTP {response.status_code} {message}{suffix}")


def _safe_text(response: requests.Response) -> str:
    try:
        return response.text
    except Exception:
        return ""