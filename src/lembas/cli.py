from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from typing import Optional

from rich.console import Console
from rich_click import typer

from lembas._version import __version__

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


def _load_module_from_path(mod_path: Path) -> ModuleType:
    """Load a module from a filesystem Path.

    Args:
        mod_path: A path to the `.py` file.

    Returns:
        The imported module object.

    """
    mod_name = mod_path.stem
    spec = importlib.util.spec_from_file_location(mod_name, mod_path.as_posix())
    if spec is None:
        raise LookupError(f"Cannot load module {mod_path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


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
