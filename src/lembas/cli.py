from __future__ import annotations

from typing import Any
from typing import Optional

from rich.console import Console
from rich_click import typer

from lembas._version import __version__

console = Console()
app = typer.Typer(add_completion=False)
print = console.print


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
    plugins: Optional[str] = None,
    params: Optional[list[str]] = None,
) -> None:
    print(f"Preparing to run case handler: {case_handler_name}")
    print(f"Will load plugins from {plugins}")

    data = {}
    params = params or []
    for param in params:
        print(param)
        key, value = param.split("=")
        data[key] = value

    import sys
    from pathlib import Path

    mod_dir = Path(__file__).parents[2] / "examples" / "planingfsi" / "flat_plate"
    sys.path.insert(0, mod_dir.resolve().as_posix())
    import importlib

    mod = importlib.import_module("run_flat_plate_cases")
    class_ = getattr(mod, case_handler_name)
    case = class_(**data)
    case.run()
