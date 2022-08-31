from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from typing import Callable

import pytest
from typer.testing import CliRunner
from typer.testing import Result

from lembas import Case
from lembas import __version__
from lembas.cli import app
from lembas.plugins import _load_module_from_path

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from mypy_extensions import VarArg

    CLIInvoker = Callable[[VarArg(str)], Result]


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
    assert f"Lembas version: {__version__}" in result.stdout


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
