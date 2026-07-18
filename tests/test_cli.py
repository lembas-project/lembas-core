from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner
from typer.testing import Result

from lembas import Case
from lembas import __version__
from lembas.cli import app
from lembas.plugins import _load_module_from_path
from lembas.plugins import registry

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from mypy_extensions import VarArg

    CLIInvoker = Callable[[VarArg(str)], Result]


@pytest.fixture(autouse=True)
def clean_case_handler_registry() -> None:
    """Ensure the case handler registry global is cleared before every test."""
    registry.clear()


@pytest.fixture()
def run_path(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """Create a temporary directory and change the working directory to it, returning the path."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def invoke_cli(run_path: Path) -> CLIInvoker:
    """Returns a function, which can be used to call the CLI from within a temporary directory."""
    runner = CliRunner()

    def f(*args: str) -> Result:
        return runner.invoke(app, args)

    return f


def test_version(invoke_cli: CLIInvoker) -> None:
    """A basic smoke-test to check that the CLI can print out the version."""
    result = invoke_cli("--version")
    assert result.exit_code == 0
    assert f"lembas {__version__}" in result.stdout


@pytest.fixture()
def plugin_module_path(run_path: Path) -> Path:
    """Generate a plugin module containing a case handler, returning the path."""
    code = """\
        import json
        from lembas import Case, InputParameter, step

        class MyCase(Case):
            my_param = InputParameter(type=float, min=2.0, max=5.0)
            has_been_run = InputParameter(default=False)

            @step
            def set_has_been_run(self) -> None:
                self.has_been_run = True

            @step
            def write_results(self) -> None:
                with open("results.json", "w") as fp:
                    json.dump({"has_been_run": self.has_been_run}, fp)
    """
    mod_path = run_path / "my_mod.py"
    with mod_path.open("w") as fp:
        fp.write(dedent(code))
    return mod_path


def test_plugin_file_exists(plugin_module_path: Path) -> None:
    """The file exists and is not empty (test fixture itself)."""
    assert plugin_module_path.exists()
    with plugin_module_path.open() as fp:
        assert "MyCase" in fp.read()


def test_load_plugin_module(plugin_module_path: Path) -> None:
    """We can load the module and the class inside it."""
    module = _load_module_from_path(plugin_module_path)
    assert hasattr(module, "MyCase")
    assert issubclass(module.MyCase, Case)


def test_run_case_success(invoke_cli: CLIInvoker, plugin_module_path: Path) -> None:
    """A successful run must specify the case handler name, plugin path, and parameters without a default value."""
    my_param_value = 3.5
    result = invoke_cli(
        "case",
        "MyCase",
        "--plugin",
        str(plugin_module_path),
        f"my_param={my_param_value}",
    )

    assert result.exit_code == 0, result.stdout
    assert "MyCase:" in result.stdout
    assert f"- my_param: {my_param_value}" in result.stdout
    assert "- has_been_run: False" in result.stdout


def test_run_case_missing_case_handler(invoke_cli: CLIInvoker) -> None:
    """If the case handler is not in the registry, execution is aborted."""
    result = invoke_cli("case", "NonExistentCase")
    assert result.exit_code == 1, result.stdout
    assert "Could not find NonExistentCase in the case handler registry" in result.stdout


@pytest.mark.skip(reason="Requires full pixi integration with lembas published")
def test_run_without_args_runs_study_cases(
    invoke_cli: CLIInvoker, run_path: Path, plugin_module_path: Path
) -> None:
    """Running `lembas run` without args loads and runs cases from [study].cases."""
    # Create lembas.toml with study config
    lembas_toml = run_path / "lembas.toml"
    lembas_toml.write_text(
        dedent(f"""\
        [project]
        name = "test-study"
        type = "study"
        channels = ["conda-forge"]
        platforms = ["linux-64", "osx-arm64"]

        [dependencies]
        python = ">=3.11"
        lembas = "*"

        [local-plugins]
        my_mod = "{plugin_module_path.name}"

        [study]
        cases = "cases.yaml"
        """)
    )

    # Create cases.yaml
    cases_yaml = run_path / "cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: MyCase
          expansion: explicit
          parameters:
            my_param: 3.0
        """)
    )

    result = invoke_cli("run")

    # Exit code 0 means cases ran successfully via pixi _lembas_run task
    assert result.exit_code == 0, result.output


def test_run_without_args_no_study_cases_errors(invoke_cli: CLIInvoker, run_path: Path) -> None:
    """Running `lembas run` without [study].cases shows an error."""
    # Create lembas.toml without study.cases
    lembas_toml = run_path / "lembas.toml"
    lembas_toml.write_text(
        dedent("""\
        [project]
        name = "test-study"
        type = "study"
        """)
    )

    result = invoke_cli("run")

    assert result.exit_code == 1, result.stdout
    assert "[study].cases" in result.stdout


def test_run_with_task_runs_pixi_task(invoke_cli: CLIInvoker, run_path: Path) -> None:
    """Running `lembas run <task>` still runs a pixi task."""
    # Create lembas.toml with a task
    lembas_toml = run_path / "lembas.toml"
    lembas_toml.write_text(
        dedent("""\
        [project]
        name = "test-study"
        type = "study"
        channels = ["conda-forge"]
        platforms = ["linux-64", "osx-arm64"]

        [tasks]
        hello = "echo hello"
        """)
    )

    result = invoke_cli("run", "nonexistent")

    # Task doesn't exist, so we get an error
    assert result.exit_code == 1
    assert "Unknown task: nonexistent" in result.stdout


class TestCasesListCommand:
    """Tests for `lembas cases list` command."""

    def test_cases_list_empty(self, invoke_cli: CLIInvoker) -> None:
        """With no index file, shows no cases message."""
        result = invoke_cli("cases", "list")
        assert result.exit_code == 0
        assert "No cases found" in result.stdout

    def test_cases_list_with_index(self, invoke_cli: CLIInvoker, run_path: Path) -> None:
        """With an index file, shows cases in a table."""
        import json

        # Create index file
        lembas_dir = run_path / ".lembas"
        lembas_dir.mkdir()
        index_file = lembas_dir / "cases.json"
        # Full 64-char case IDs
        case_id_1 = "abc12345" + "0" * 56
        case_id_2 = "def67890" + "0" * 56
        index_file.write_text(
            json.dumps(
                {
                    case_id_1: "cases/alpha=1/beta=2",
                    case_id_2: "cases/alpha=3/beta=4",
                }
            )
        )

        result = invoke_cli("cases", "list")
        assert result.exit_code == 0
        # Display shows short IDs (first 8 chars)
        assert "abc12345" in result.stdout
        assert "def67890" in result.stdout
        assert "cases/alpha=1/beta=2" in result.stdout

    def test_cases_list_shows_missing_status(self, invoke_cli: CLIInvoker, run_path: Path) -> None:
        """Directories that don't exist are marked as missing."""
        import json

        lembas_dir = run_path / ".lembas"
        lembas_dir.mkdir()
        index_file = lembas_dir / "cases.json"
        case_id = "abc12345" + "0" * 56
        index_file.write_text(json.dumps({case_id: "cases/nonexistent"}))

        result = invoke_cli("cases", "list")
        assert result.exit_code == 0
        assert "missing" in result.stdout

    def test_cases_list_shows_complete_status(self, invoke_cli: CLIInvoker, run_path: Path) -> None:
        """Cases with completed status.json are marked as complete."""
        import json

        import toml

        # Create the case directory with a case.toml
        case_dir = run_path / "cases" / "test"
        lembas_case_dir = case_dir / "lembas"
        lembas_case_dir.mkdir(parents=True)
        case_toml = lembas_case_dir / "case.toml"
        case_toml.write_text(
            toml.dumps({"lembas": {"case-handler": "test.Case", "inputs": {"value": 1}}})
        )

        # Create status.json with completed_at to mark as complete
        status_file = lembas_case_dir / "status.json"
        status_file.write_text(json.dumps({"completed_at": "2026-07-17T12:00:00Z", "steps": {}}))

        # Create index with rich format (full 64-char case ID)
        lembas_dir = run_path / ".lembas"
        lembas_dir.mkdir()
        index_file = lembas_dir / "cases.json"
        case_id = "abc12345" + "0" * 56
        index_file.write_text(
            json.dumps(
                {
                    case_id: {
                        "path": "cases/test",
                        "handler": "Case",
                        "all_paths": ["cases/test"],
                    }
                }
            )
        )

        result = invoke_cli("cases", "list")
        assert result.exit_code == 0
        assert "complete" in result.stdout

    def test_cases_list_auto_reindexes(self, invoke_cli: CLIInvoker, run_path: Path) -> None:
        """When index is empty but case.toml files exist, auto-reindex."""
        import toml

        # Create a case directory with case.toml but NO index file
        case_dir = run_path / "cases" / "value=1"
        lembas_dir = case_dir / "lembas"
        lembas_dir.mkdir(parents=True)

        case_toml = lembas_dir / "case.toml"
        case_toml.write_text(
            toml.dumps(
                {
                    "lembas": {
                        "case-handler": "test.Case",
                        "inputs": {"value": 1},
                    }
                }
            )
        )

        # No .lembas/cases.json exists
        result = invoke_cli("cases", "list")
        assert result.exit_code == 0
        # Should find the case via auto-reindex
        assert "cases/value=1" in result.stdout


class TestCasesReindexCommand:
    """Tests for `lembas cases reindex` command."""

    def test_cases_reindex_empty(self, invoke_cli: CLIInvoker) -> None:
        """With no cases, reindex shows 0 cases."""
        result = invoke_cli("cases", "reindex")
        assert result.exit_code == 0
        assert "Found 0 cases" in result.stdout

    def test_cases_reindex_finds_cases(self, invoke_cli: CLIInvoker, run_path: Path) -> None:
        """Reindex finds case.toml files and rebuilds index."""
        import toml

        # Create a case directory with case.toml
        case_dir = run_path / "cases" / "value=1"
        lembas_dir = case_dir / "lembas"
        lembas_dir.mkdir(parents=True)

        case_toml = lembas_dir / "case.toml"
        case_toml.write_text(
            toml.dumps(
                {
                    "lembas": {
                        "case-handler": "test.Case",
                        "inputs": {"value": 1},
                    }
                }
            )
        )

        result = invoke_cli("cases", "reindex")
        assert result.exit_code == 0
        assert "Found 1 cases" in result.stdout

        # Verify index file was created
        index_file = run_path / ".lembas" / "cases.json"
        assert index_file.exists()
