from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from lembas._version import __version__
from lembas.plugins import CaseHandlerNotFound
from lembas.plugins import load_plugins_from_file
from lembas.plugins import registry

console = Console()
app = typer.Typer(add_completion=False)


class Okay(typer.Exit):
    """Prints an optional message to the console, before cleanly exiting.

    Provides a standard way to end/confirm a successful command.

    """

    def __init__(self, msg: str = "", *args: Any, **kwargs: Any):
        if m := msg.strip():
            console.print(m, style="green")
        super().__init__(*args, **kwargs)


class Abort(typer.Abort):
    """Prints an optional message to the console, before aborting with non-zero exit code."""

    def __init__(self, msg: str = "", *args: Any, **kwargs: Any):
        if m := msg.strip():
            console.print(m, style="red")
        super().__init__(*args, **kwargs)


@app.callback(invoke_without_command=True, no_args_is_help=True)
def main(
    version: bool | None = typer.Option(None, "--version", help="Show project version and exit."),
) -> None:
    """Command Line Interface for Lembas."""
    if version:
        console.print(f"Lembas version: {__version__}", style="bold green")
        raise typer.Exit()


@app.command()
def run(
    case_handler_name: str,
    params: list[str] | None = typer.Argument(None),  # noqa: B008
    *,
    plugin: Path | None = None,
) -> None:
    """Run a single case of a given case handler type."""
    if plugin is not None:
        load_plugins_from_file(plugin)

    try:
        class_ = registry.get(case_handler_name)
    except CaseHandlerNotFound as e:
        raise Abort(str(e)) from e

    data = {}
    for param in params or []:
        key, value = param.split("=")
        data[key] = value

    case = class_(**data)
    console.print(case)

    case.run()

    raise Okay("Case complete")
