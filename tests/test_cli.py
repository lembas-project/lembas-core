from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Callable

import pytest
from typer.testing import CliRunner
from typer.testing import Result

from lembas import __version__
from lembas.cli import app

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
