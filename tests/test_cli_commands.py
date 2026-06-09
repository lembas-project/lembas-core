"""Tests for the new lembas CLI commands."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lembas.cli import app

if TYPE_CHECKING:
    from unittest.mock import MagicMock


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a project with lembas.toml and cd into it."""
    manifest = dedent("""\
        [project]
        name = "test-project"
        type = "study"
        channels = ["conda-forge"]
        platforms = ["linux-64", "osx-arm64"]

        [dependencies]
        python = ">=3.11"

        [tasks]
        run = "python run.py"
        test = "pytest tests/"
    """)
    (tmp_path / "lembas.toml").write_text(manifest)
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestStatusCommand:
    def test_status_shows_project_info(self, runner: CliRunner, project_dir: Path) -> None:
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "test-project" in result.output
        assert "study" in result.output

    def test_status_shows_tasks(self, runner: CliRunner, project_dir: Path) -> None:
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "run" in result.output
        assert "test" in result.output

    def test_status_no_manifest(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 3
        assert "No lembas.toml found" in result.output

    def test_status_shows_plugins(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest = dedent("""\
            [project]
            name = "test-project"

            [plugins]
            lembas-reef3d = ">=0.1.0"
        """)
        (tmp_path / "lembas.toml").write_text(manifest)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "lembas-reef3d" in result.output
        assert ">=0.1.0" in result.output


class TestRunCommand:
    def test_run_missing_task(self, runner: CliRunner, project_dir: Path) -> None:
        result = runner.invoke(app, ["run", "nonexistent"])

        assert result.exit_code == 2
        assert "Task 'nonexistent' not found" in result.output
        assert "Available tasks:" in result.output

    def test_run_no_manifest(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["run"])

        assert result.exit_code == 3
        assert "No lembas.toml found" in result.output

    @patch("lembas.cli._run_pixi")
    def test_run_invokes_pixi(
        self, mock_run_pixi: MagicMock, runner: CliRunner, project_dir: Path
    ) -> None:
        mock_run_pixi.return_value = 0

        result = runner.invoke(app, ["run", "test"])

        assert result.exit_code == 0
        mock_run_pixi.assert_called_once()
        args = mock_run_pixi.call_args[0][0]
        assert args == ["run", "test"]


class TestInstallCommand:
    def test_install_no_manifest(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["install"])

        assert result.exit_code == 3
        assert "No lembas.toml found" in result.output

    @patch("lembas.cli._run_pixi")
    def test_install_invokes_pixi(
        self, mock_run_pixi: MagicMock, runner: CliRunner, project_dir: Path
    ) -> None:
        mock_run_pixi.return_value = 0

        result = runner.invoke(app, ["install"])

        assert result.exit_code == 0
        mock_run_pixi.assert_called_once()
        args = mock_run_pixi.call_args[0][0]
        assert args == ["install"]
        assert "Environment installed successfully" in result.output


class TestShellCommand:
    def test_shell_no_manifest(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["shell"])

        assert result.exit_code == 3
        assert "No lembas.toml found" in result.output


class TestSynthesisIntegration:
    def test_synthesis_creates_lembas_dir(self, runner: CliRunner, project_dir: Path) -> None:
        lembas_dir = project_dir / ".lembas"
        assert not lembas_dir.exists()

        with patch("lembas.cli._find_pixi") as mock_find:
            mock_find.return_value = Path("/usr/bin/pixi")
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                runner.invoke(app, ["install"])

        assert lembas_dir.exists()
        assert (lembas_dir / "pixi.toml").exists()

    def test_synthesized_pixi_toml_has_correct_content(
        self, runner: CliRunner, project_dir: Path
    ) -> None:
        with patch("lembas.cli._find_pixi") as mock_find:
            mock_find.return_value = Path("/usr/bin/pixi")
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                runner.invoke(app, ["install"])

        pixi_toml = (project_dir / ".lembas" / "pixi.toml").read_text()
        assert "test-project" in pixi_toml
        assert "python" in pixi_toml
        assert "conda-forge" in pixi_toml


class TestVersionFlag:
    def test_version_output(self, runner: CliRunner) -> None:
        from lembas import __version__

        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert f"lembas {__version__}" in result.output
