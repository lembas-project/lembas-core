"""Tests for the platform client and token resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lembas.platform import ENV_VAR
from lembas.platform import PlatformConfig
from lembas.platform import get_stored_token

# --- Token resolution ---


def test_get_stored_token_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEMBAS_API_TOKEN env var takes highest priority."""
    monkeypatch.setenv(ENV_VAR, "lb_v1_env_token")
    assert get_stored_token() == "lb_v1_env_token"


def test_get_stored_token_env_var_overrides_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env var takes priority over keyring."""
    monkeypatch.setenv(ENV_VAR, "lb_v1_env_token")
    with patch("keyring.get_password", return_value="lb_v1_keyring_token"):
        assert get_stored_token() == "lb_v1_env_token"


def test_get_stored_token_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falls back to keyring when env var not set."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    with patch("keyring.get_password", return_value="lb_v1_keyring_token"):
        assert get_stored_token() == "lb_v1_keyring_token"


def test_get_stored_token_file_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Falls back to credentials file when keyring unavailable."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    creds = tmp_path / "credentials"
    creds.write_text("lb_v1_file_token\n")

    with (
        patch("lembas.platform.CREDENTIALS_PATH", creds),
        patch("keyring.get_password", side_effect=Exception("no keyring")),
    ):
        assert get_stored_token() == "lb_v1_file_token"


def test_get_stored_token_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Returns None when no token available."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    with (
        patch("lembas.platform.CREDENTIALS_PATH", tmp_path / "credentials"),
        patch("keyring.get_password", side_effect=Exception("no keyring")),
    ):
        assert get_stored_token() is None


# --- PlatformConfig ---


def test_platform_config_from_manifest_default() -> None:
    manifest = {
        "platform": [
            {"name": "default", "url": "https://lembas.fly.dev"},
            {"name": "staging", "url": "https://staging.lembas.fly.dev"},
        ]
    }
    config = PlatformConfig.from_manifest(manifest)
    assert config is not None
    assert config.name == "default"
    assert config.server == "https://lembas.fly.dev"


def test_platform_config_from_manifest_named_target() -> None:
    manifest = {
        "platform": [
            {"name": "default", "url": "https://lembas.fly.dev"},
            {"name": "staging", "url": "https://staging.lembas.fly.dev"},
        ]
    }
    config = PlatformConfig.from_manifest(manifest, target="staging")
    assert config is not None
    assert config.server == "https://staging.lembas.fly.dev"


def test_platform_config_from_manifest_url_target() -> None:
    manifest: dict = {}
    config = PlatformConfig.from_manifest(manifest, target="http://localhost:8001")
    assert config is not None
    assert config.server == "http://localhost:8001"
    assert config.name == "adhoc"


def test_platform_config_from_manifest_missing_target() -> None:
    manifest = {"platform": [{"name": "default", "url": "https://lembas.fly.dev"}]}
    with pytest.raises(ValueError, match="not found"):
        PlatformConfig.from_manifest(manifest, target="nonexistent")


def test_platform_config_from_manifest_no_platform() -> None:
    assert PlatformConfig.from_manifest({}) is None


# --- register_study payload ---


def test_register_study_payload() -> None:
    """Verify that register_study sends 'id' not 'case_id' in the payload."""
    from lembas.platform import PlatformClient

    config = PlatformConfig(name="test", server="http://localhost")
    client = PlatformClient(config, token="lb_v1_test")

    mock_case = MagicMock()
    mock_case.id = "abc123"
    mock_case.__class__.__module__ = "my_plugin"
    mock_case.__class__.__name__ = "MyCase"
    mock_case.inputs = {"x": 1.0}

    captured: list[dict] = []

    def mock_post(url: str, **kwargs: object) -> MagicMock:
        captured.append(kwargs.get("json", {}))  # type: ignore[arg-type]
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"id": "study-uuid"}
        return resp

    with patch.object(client.client, "post", side_effect=mock_post):
        client.register_study("my-study", [mock_case])

    assert len(captured) == 1
    case_payload = captured[0]["cases"][0]
    assert "id" in case_payload
    assert case_payload["id"] == "abc123"
    assert "case_id" not in case_payload
