from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Optional

import typer
from rich.console import Console

from lembas._version import __version__
from lembas.plugins import _load_module_from_path

console = Console()
app = typer.Typer(add_completion=False)
print = console.print


class Okay(typer.Exit):
    """Simply prints "OK" and an optional message, to the console, before cleanly exiting.

    Provides a standard way to end/confirm a successful command.

    """

    def __init__(self, msg: str = "", *args: Any, **kwargs: Any):
        print(f"OK. {msg}".rstrip(), style="green")
        super().__init__(*args, **kwargs)


class Abort(typer.Abort):
    """Abort with a consistent error message."""

    def __init__(self, msg: str, *args: Any, **kwargs: Any):
        console.print(msg, style="red")
        super().__init__(*args, **kwargs)


@app.callback(invoke_without_command=True, no_args_is_help=True)
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", help="Show project version and exit."
    )
) -> None:
    """Command Line Interface for Lembas."""
    if version:
        console.print(f"Lembas version: {__version__}", style="bold green")
        raise typer.Exit()


@app.command()
def run(
    case_handler_name: str,
    *,
    plugin: Optional[str] = None,
    params: Optional[list[str]] = None,
) -> None:
    if plugin is None:
        raise Abort("We must currently specify a plugin")

    print("Attempting to load plugins")
    plugin_path = Path(plugin).resolve()
    mod = _load_module_from_path(plugin_path)

    try:
        class_ = getattr(mod, case_handler_name)
    except AttributeError:
        raise Abort(f"Could not find [bold]{case_handler_name}[/bold] in {plugin_path}")
    else:
        print(f"Found [bold]{case_handler_name}[/bold] in {plugin_path}")

    data = {}
    for param in params or []:
        key, value = param.split("=")
        data[key] = value
    print(f"Case data: {data}")

    print("Running the case")
    case = class_(**data)
    case.run()
    raise Okay("Case complete")
