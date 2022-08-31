from __future__ import annotations

from typing import Any
from typing import Optional

from rich.console import Console
from rich_click import typer

from lembas._version import __version__

console = Console()
app = typer.Typer(add_completion=False)


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
