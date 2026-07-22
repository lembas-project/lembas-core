"""Platform client for communicating with the lembas server."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import httpx

if TYPE_CHECKING:
    from lembas.case import Case

log = logging.getLogger(__name__)

CREDENTIALS_PATH = Path.home() / ".lembas" / "credentials"
SERVICE_NAME = "lembas"


@dataclass
class PlatformConfig:
    """Configuration for platform connection."""

    server: str

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> PlatformConfig | None:
        """Extract platform config from lembas.toml manifest."""
        platform = manifest.get("platform")
        if not platform:
            return None
        server = platform.get("server")
        if not server:
            return None
        return cls(server=server)


def get_stored_token() -> str | None:
    """Retrieve stored token from keyring or fallback file."""
    try:
        import keyring

        token = keyring.get_password(SERVICE_NAME, "token")
        if token:
            return token
    except Exception:
        pass

    if CREDENTIALS_PATH.exists():
        return CREDENTIALS_PATH.read_text().strip()

    return None


def store_token(token: str) -> None:
    """Store token in keyring or fallback file."""
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, "token", token)
        return
    except Exception:
        pass

    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(token)
    CREDENTIALS_PATH.chmod(0o600)


def clear_token() -> None:
    """Clear stored token."""
    try:
        import keyring

        keyring.delete_password(SERVICE_NAME, "token")
    except Exception:
        pass

    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()


class PlatformClient:
    """Client for interacting with the lembas platform server."""

    def __init__(self, config: PlatformConfig, token: str | None = None):
        self.config = config
        self.token = token or get_stored_token()
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.Client(
                base_url=self.config.server,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> PlatformClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def register_study(
        self,
        name: str,
        cases: list[Case],
        *,
        description: str | None = None,
        tags: list[str] | None = None,
        plugins_declared: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register a study with its cases on the platform."""
        payload = {
            "name": name,
            "description": description,
            "tags": tags or [],
            "plugins_declared": plugins_declared or [],
            "cases": [
                {
                    "case_id": case.id,
                    "handler_fqn": f"{case.__class__.__module__}.{case.__class__.__name__}",
                    "inputs": case.inputs,
                }
                for case in cases
            ],
        }
        response = self.client.post("/api/studies", json=payload)
        response.raise_for_status()
        return response.json()

    def update_case_status(
        self,
        study_id: str,
        case_id: str,
        status: str,
        *,
        duration_seconds: float | None = None,
        results: dict[str, Any] | None = None,
        environment: dict[str, str] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Update the status of a case within a study."""
        payload: dict[str, Any] = {"status": status}
        if duration_seconds is not None:
            payload["duration_seconds"] = duration_seconds
        if results is not None:
            payload["results"] = results
        if environment is not None:
            payload["environment"] = environment
        if error_message is not None:
            payload["error_message"] = error_message
        response = self.client.patch(
            f"/api/studies/{study_id}/cases/{case_id}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def get_study(self, study_id: str) -> dict[str, Any]:
        """Fetch a study by ID."""
        response = self.client.get(f"/api/studies/{study_id}")
        response.raise_for_status()
        return response.json()

    def health_check(self) -> bool:
        """Check if the server is reachable."""
        try:
            response = self.client.get("/api/healthz")
            return response.status_code == 200
        except httpx.RequestError:
            return False
