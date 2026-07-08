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
