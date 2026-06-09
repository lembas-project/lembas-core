"""Lembas CLI - command line interface for lembas projects."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Annotated
from typing import Any

import typer
from rich.console import Console

from lembas._version import __version__
from lembas.manifest import LembasManifest
from lembas.plugins import CaseHandlerNotFound
from lembas.plugins import load_plugins_from_file
from lembas.plugins import registry
from lembas.synthesis import LEMBAS_DIR
from lembas.synthesis import PIXI_TOML_NAME
from lembas.synthesis import is_synthesis_stale
from lembas.synthesis import synthesize_pixi_toml

console = Console()
err_console = Console(stderr=True)
app = typer.Typer(add_completion=False, no_args_is_help=True)


class Okay(typer.Exit):
    """Prints an optional message to the console, before cleanly exiting."""

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


def _find_pixi() -> Path:
    """Find the pixi executable."""
    pixi = shutil.which("pixi")
    if pixi is None:
        err_console.print("[red]Error:[/red] pixi not found. Install from https://pixi.sh")
        raise typer.Exit(1)
    return Path(pixi)


def _ensure_synthesis(project_root: Path) -> Path:
    """Ensure .lembas/pixi.toml is up to date, regenerating if stale.

    Returns the path to the pixi.toml file.
    """
    try:
        manifest = LembasManifest.from_path(project_root / "lembas.toml")
    except FileNotFoundError:
        err_console.print("[red]Error:[/red] No lembas.toml found")
        raise typer.Exit(3) from None

    lembas_dir = project_root / LEMBAS_DIR

    if is_synthesis_stale(manifest, lembas_dir):
        console.print("[dim]Synthesizing .lembas/pixi.toml...[/dim]")
        synthesize_pixi_toml(manifest, project_root)

    return lembas_dir / PIXI_TOML_NAME


def _run_pixi(args: list[str], project_root: Path) -> int:
    """Run pixi with the synthesized manifest."""
    pixi = _find_pixi()
    pixi_toml = _ensure_synthesis(project_root)

    # pixi wants: pixi <subcommand> --manifest-path <path> [args...]
    # So we insert --manifest-path after the first arg (the subcommand)
    if args:
        cmd = [str(pixi), args[0], "--manifest-path", str(pixi_toml), *args[1:]]
    else:
        cmd = [str(pixi), "--manifest-path", str(pixi_toml)]
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool | None, typer.Option("--version", help="Show version and exit.")
    ] = None,
) -> None:
    """Lembas - lifecycle engineering analysis framework."""
    if version:
        console.print(f"lembas {__version__}")
        raise typer.Exit()

    # If no subcommand given and we have extra args, try to run as pixi task
    if ctx.invoked_subcommand is None and ctx.args:
        # This handles: lembas <task> [args...]
        _run_task_or_proxy(ctx.args)


def _run_task_or_proxy(args: list[str]) -> None:
    """Run a task from lembas.toml or proxy to pixi."""
    project_root = Path.cwd()
    try:
        manifest, manifest_path = LembasManifest.find_and_load(project_root)
        project_root = manifest_path.parent
    except FileNotFoundError:
        err_console.print("[red]Error:[/red] No lembas.toml found")
        raise typer.Exit(3) from None

    task_name = args[0]
    task_args = args[1:]

    # Check if it's a defined task
    if task_name in manifest.tasks:
        # Run via pixi
        pixi_args = ["run", task_name, *task_args]
        returncode = _run_pixi(pixi_args, project_root)
        raise typer.Exit(returncode)

    # Not a known task - error
    available = list(manifest.tasks.keys())
    err_console.print(f"[red]Error:[/red] Unknown command '{task_name}'")
    if available:
        err_console.print(f"Available tasks: {', '.join(available)}")
    raise typer.Exit(2)


@app.command()
def install() -> None:
    """Install the project environment via pixi."""
    project_root = Path.cwd()
    try:
        _, manifest_path = LembasManifest.find_and_load(project_root)
        project_root = manifest_path.parent
    except FileNotFoundError:
        err_console.print("[red]Error:[/red] No lembas.toml found")
        raise typer.Exit(3) from None

    returncode = _run_pixi(["install"], project_root)
    if returncode == 0:
        console.print("[green]Environment installed successfully[/green]")
    raise typer.Exit(returncode)


@app.command()
def shell() -> None:
    """Start a shell with the project environment activated."""
    project_root = Path.cwd()
    try:
        _, manifest_path = LembasManifest.find_and_load(project_root)
        project_root = manifest_path.parent
    except FileNotFoundError:
        err_console.print("[red]Error:[/red] No lembas.toml found")
        raise typer.Exit(3) from None

    pixi = _find_pixi()
    pixi_toml = _ensure_synthesis(project_root)

    # Use exec to replace the process with the shell
    import os

    os.execlp(str(pixi), "pixi", "--manifest-path", str(pixi_toml), "shell")


@app.command("run")
def run_task(
    task: Annotated[str, typer.Argument(help="Task name from [tasks] section")] = "run",
    args: Annotated[
        list[str] | None, typer.Argument(help="Additional arguments to pass to the task")
    ] = None,
) -> None:
    """Run a task defined in lembas.toml."""
    project_root = Path.cwd()
    try:
        manifest, manifest_path = LembasManifest.find_and_load(project_root)
        project_root = manifest_path.parent
    except FileNotFoundError:
        err_console.print("[red]Error:[/red] No lembas.toml found")
        raise typer.Exit(3) from None

    if task not in manifest.tasks:
        available = list(manifest.tasks.keys())
        err_console.print(f"[red]Error:[/red] Task '{task}' not found")
        if available:
            err_console.print(f"Available tasks: {', '.join(available)}")
        raise typer.Exit(2)

    pixi_args = ["run", task]
    if args:
        pixi_args.extend(args)

    returncode = _run_pixi(pixi_args, project_root)
    raise typer.Exit(returncode)


@app.command()
def status() -> None:
    """Show project status and available tasks."""
    project_root = Path.cwd()
    try:
        manifest, manifest_path = LembasManifest.find_and_load(project_root)
    except FileNotFoundError:
        err_console.print("[red]Error:[/red] No lembas.toml found")
        raise typer.Exit(3) from None

    console.print(f"[bold]{manifest.project.name}[/bold]")
    console.print(f"  Type: {manifest.project.type}")
    if manifest.project.description:
        console.print(f"  Description: {manifest.project.description}")
    console.print(f"  Location: {manifest_path.parent}")

    if manifest.plugins:
        console.print("\n[bold]Plugins:[/bold]")
        for name, version in manifest.plugins.items():
            console.print(f"  {name} {version}")

    if manifest.tasks:
        console.print("\n[bold]Tasks:[/bold]")
        for name, task in manifest.tasks.items():
            desc = f" - {task.description}" if task.description else ""
            console.print(f"  {name}{desc}")


# Legacy command for running case handlers directly (kept for backwards compatibility)
@app.command("case", hidden=True)
def run_case(
    case_handler_name: str,
    params: list[str] | None = typer.Argument(None),  # noqa: B008
    *,
    plugin: Path | None = None,
) -> None:
    """Run a single case of a given case handler type (legacy)."""
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


if __name__ == "__main__":
    app()
