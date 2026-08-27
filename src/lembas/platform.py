"""Platform client for communicating with the lembas server."""

from __future__ import annotations

import logging
import os
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import httpx

if TYPE_CHECKING:
    from lembas.case import Case

log = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

CREDENTIALS_PATH = Path.home() / ".lembas" / "credentials"
SERVICE_NAME = "lembas"
ENV_VAR = "LEMBAS_API_TOKEN"


@dataclass
class PlatformConfig:
    """Configuration for platform connection."""

    name: str
    server: str

    @classmethod
    def from_manifest(
        cls, manifest: dict[str, Any], target: str | None = None
    ) -> PlatformConfig | None:
        """Extract platform config from lembas.toml manifest.

        Format:
            [[platform]]
            name = "default"
            url = "https://lembas.example.com"

            [[platform]]
            name = "staging"
            url = "https://staging.lembas.example.com"

        Args:
            manifest: The parsed lembas.toml content.
            target: Name of the platform target to use. If None, uses the first
                one (default). Can also be a URL for ad-hoc targets.

        Returns:
            PlatformConfig or None if no platform is configured.
        """
        platform = manifest.get("platform")

        # Check if target is a URL (ad-hoc platform — no manifest entry needed)
        if target and (target.startswith("http://") or target.startswith("https://")):
            return cls(name="adhoc", server=target)

        if not platform:
            return None

        if not isinstance(platform, list) or not platform:
            return None

        if target:
            # Find target by name
            for p in platform:
                if p.get("name") == target:
                    return cls(name=p["name"], server=p.get("url", ""))
            # Target not found
            available = [p.get("name") for p in platform if p.get("name")]
            raise ValueError(f"Platform target '{target}' not found. Available: {available}")

        # Use first target as default
        first = platform[0]
        return cls(
            name=first.get("name", "default"),
            server=first.get("url", ""),
        )

    @classmethod
    def list_targets(cls, manifest: dict[str, Any]) -> list[PlatformConfig]:
        """List all available platform targets from manifest."""
        platform = manifest.get("platform")
        if not platform or not isinstance(platform, list):
            return []

        return [
            cls(name=p.get("name", f"target-{i}"), server=p.get("url", ""))
            for i, p in enumerate(platform)
            if p.get("url")
        ]


def resolve_server_url(override: str | None = None) -> str | None:
    """Return a server URL from an explicit override or the first [[platform]] in lembas.toml.

    Returns None if no URL can be determined.
    """
    from lembas.manifest import get_lembas_manifest_path
    from lembas.manifest import load_lembas_manifest

    if override:
        return override
    if get_lembas_manifest_path().exists():
        manifest = load_lembas_manifest()
        platforms = manifest.get("platform", [])
        if platforms:
            return platforms[0].get("url")
    return None


def get_stored_token() -> str | None:
    """Retrieve token using the resolution order:

    1. ``LEMBAS_API_TOKEN`` environment variable
    2. System keyring
    3. Fallback credentials file (``~/.lembas/credentials``)
    """
    if token := os.environ.get(ENV_VAR):
        return token

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


class DeviceLoginError(Exception):
    """Raised when device flow login fails."""


def device_login(server: str, token_name: str = "cli") -> str:
    """Run a full device authorization flow against the lembas server.

    Opens the browser automatically. Blocks until approved or expired.
    Stores the resulting token and returns the token name.

    Raises DeviceLoginError on any failure.
    """
    try:
        resp = httpx.get(f"{server}/api/auth/device", timeout=30.0)
        resp.raise_for_status()
    except Exception as e:
        raise DeviceLoginError(f"Could not reach server: {e}") from e

    data = resp.json()
    user_code = data["user_code"]
    device_code = data["device_code"]
    verification_uri = data["verification_uri"]
    interval = data.get("interval", 5)
    expires_in = data.get("expires_in", 300)

    return _poll_device_flow(
        server, device_code, user_code, verification_uri, interval, expires_in, token_name
    )


def _poll_device_flow(
    server: str,
    device_code: str,
    user_code: str,
    verification_uri: str,
    interval: int,
    expires_in: int,
    token_name: str,
) -> str:
    """Display the user code, open the browser, and poll until approved."""
    from rich.console import Console

    console = Console()
    console.print(f"\n  Your code: [bold green]{user_code}[/bold green]")
    console.print(f"  Open:      [link={verification_uri}]{verification_uri}[/link]\n")
    webbrowser.open(verification_uri)

    console.print("Waiting for authorization", end="")
    deadline = time.time() + expires_in

    while time.time() < deadline:
        time.sleep(interval)
        console.print(".", end="", highlight=False)

        try:
            poll_resp = httpx.post(
                f"{server}/api/auth/device/token",
                json={"device_code": device_code, "token_name": token_name},
                timeout=30.0,
            )
        except Exception:
            continue

        if poll_resp.status_code == 201:
            result = poll_resp.json()
            store_token(result["token"])
            console.print()
            return result.get("token_name") or token_name

        if poll_resp.status_code == 200:
            if poll_resp.json().get("error") == "slow_down":
                new_interval = poll_resp.json().get("interval")
                if new_interval:
                    interval = new_interval
            continue

        raise DeviceLoginError(f"Authorization failed: {poll_resp.text}")

    console.print()
    raise DeviceLoginError("Device flow expired. Run 'lembas auth login' again.")


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
                    "id": case.id,
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
