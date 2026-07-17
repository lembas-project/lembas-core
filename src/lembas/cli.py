"""Lembas CLI - command line interface for lifecycle engineering analysis."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from lembas._version import __version__
from lembas.manifest import ensure_pixi_manifest
from lembas.manifest import get_lembas_manifest_path
from lembas.manifest import get_pixi_manifest_path
from lembas.manifest import is_pixi_manifest_stale
from lembas.manifest import load_lembas_manifest
from lembas.manifest import write_pixi_manifest
from lembas.plugins import CaseHandlerNotFound
from lembas.plugins import load_plugins_from_file
from lembas.plugins import registry

console = Console()
app = typer.Typer(add_completion=False)

# Subcommand group for case management
cases_app = typer.Typer(help="Manage study cases")
app.add_typer(cases_app, name="cases")


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


def _run_pixi(args: list[str]) -> int:
    """Run pixi with the synthesized manifest, returning exit code."""
    pixi_path = ensure_pixi_manifest()
    # pixi expects: pixi <command> --manifest-path <path> [args]
    # Insert --manifest-path after the first arg (the command)
    if args:
        cmd = ["pixi", args[0], "--manifest-path", str(pixi_path), *args[1:]]
    else:
        cmd = ["pixi", "--manifest-path", str(pixi_path)]
    result = subprocess.run(cmd, check=False)
    return result.returncode


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(None, "--version", help="Show version and exit."),
) -> None:
    """Lembas - Lifecycle Engineering Model-Based Analysis System.

    If no command is given, attempts to run the command as a pixi task.
    """
    if version:
        console.print(f"lembas {__version__}")
        raise typer.Exit()

    # If no subcommand and we have remaining args, try as pixi task
    if ctx.invoked_subcommand is None:
        # Check if lembas.toml exists
        if not get_lembas_manifest_path().exists():
            console.print("No lembas.toml found in current directory.", style="red")
            console.print("Run 'lembas init' to create a new project.")
            raise typer.Exit(1)

        # No args means show help
        if not ctx.args:
            console.print(ctx.get_help())
            raise typer.Exit()

        # Try to run as pixi task
        task_name = ctx.args[0]
        task_args = ctx.args[1:]

        manifest = load_lembas_manifest()
        tasks = manifest.get("tasks", {})

        if task_name not in tasks:
            console.print(f"Unknown command or task: {task_name}", style="red")
            console.print(f"Available tasks: {', '.join(tasks.keys()) or '(none)'}")
            raise typer.Exit(1)

        exit_code = _run_pixi(["run", task_name, *task_args])
        raise typer.Exit(exit_code)


@app.command()
def init(
    name: str | None = typer.Option(None, help="Project name"),
    project_type: str = typer.Option(
        "study", "--type", "-t", help="Project type: study, plugin, workspace"
    ),
) -> None:
    """Initialize a new lembas project."""
    cwd = Path.cwd()
    manifest_path = cwd / "lembas.toml"

    if manifest_path.exists():
        raise Abort("lembas.toml already exists in this directory")

    project_name = name or cwd.name

    if project_type == "study":
        content = f'''[project]
name = "{project_name}"
type = "study"
description = ""
channels = ["conda-forge", "lembas-project"]
platforms = ["linux-64", "osx-arm64"]

[dependencies]
python = ">=3.11"

[plugins]
# Add lembas plugins here, e.g.:
# lembas-planingfsi = ">=0.1.0"

[tasks]
run = "python run.py"
'''
        run_py = cwd / "run.py"
        if not run_py.exists():
            run_py.write_text('''"""Run the parametric study."""

from __future__ import annotations


def main() -> None:
    """Main entry point."""
    print("Hello from lembas!")
    # TODO: Add your study logic here


if __name__ == "__main__":
    main()
''')
            console.print(f"Created {run_py}")

    elif project_type == "plugin":
        content = f'''[project]
name = "{project_name}"
type = "plugin"
version = "0.1.0"
description = ""
channels = ["conda-forge", "lembas-project"]
platforms = ["linux-64", "osx-arm64"]

[dependencies]
python = ">=3.11"
lembas = ">=0.1.0"

[dev-dependencies]
pytest = "*"

[plugin]
entry-point = "{project_name.replace("-", "_")}:Plugin"

[tasks]
test = "pytest tests/ -v"
'''
    else:
        raise Abort(f"Unknown project type: {project_type}")

    manifest_path.write_text(content)
    console.print(f"Created {manifest_path}")

    # Create .gitignore
    gitignore = cwd / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".lembas/\n")
        console.print(f"Created {gitignore}")

    raise Okay(f"Initialized lembas {project_type}: {project_name}")


@app.command()
def install() -> None:
    """Install project dependencies.

    Synthesizes .lembas/pixi.toml from lembas.toml and runs pixi install.
    """
    if not get_lembas_manifest_path().exists():
        raise Abort("No lembas.toml found. Run 'lembas init' first.")

    if is_pixi_manifest_stale():
        console.print("Synthesizing .lembas/pixi.toml...")
        write_pixi_manifest()

    console.print("Installing dependencies...")
    exit_code = _run_pixi(["install"])

    if exit_code == 0:
        raise Okay("Dependencies installed")
    else:
        raise typer.Exit(exit_code)


@app.command()
def shell() -> None:
    """Start a shell with the project environment activated."""
    if not get_lembas_manifest_path().exists():
        raise Abort("No lembas.toml found. Run 'lembas init' first.")

    ensure_pixi_manifest()
    pixi_path = get_pixi_manifest_path()

    # Use exec to replace the current process
    import os

    os.execlp("pixi", "pixi", "--manifest-path", str(pixi_path), "shell")


@app.command("run")
def run_task(
    task: str | None = typer.Argument(None, help="Task name to run, or omit to run cases"),
    args: list[str] | None = typer.Argument(None, help="Additional arguments"),  # noqa: B008
) -> None:
    """Run cases or a task defined in lembas.toml.

    Without arguments, loads and runs all cases from [study].cases.
    With a task name, runs that pixi task.
    """
    if not get_lembas_manifest_path().exists():
        raise Abort("No lembas.toml found. Run 'lembas init' first.")

    # If no task specified, run the study cases
    if task is None:
        _run_study_cases()
        return

    manifest = load_lembas_manifest()
    tasks = manifest.get("tasks", {})

    if task not in tasks:
        console.print(f"Unknown task: {task}", style="red")
        console.print(f"Available tasks: {', '.join(tasks.keys()) or '(none)'}")
        raise typer.Exit(1)

    exit_code = _run_pixi(["run", task, *(args or [])])
    raise typer.Exit(exit_code)


def _run_study_cases() -> None:
    """Run cases via the synthesized _lembas_run pixi task.

    This ensures cases run in the project's pixi environment where
    all dependencies (including those used by local plugins) are available.
    """
    manifest = load_lembas_manifest()
    study_config = manifest.get("study", {})

    if "cases" not in study_config:
        raise Abort("No \\[study].cases defined in lembas.toml")

    # Run via pixi to ensure we're in the correct environment
    exit_code = _run_pixi(["run", "_lembas_run"])
    raise typer.Exit(exit_code)


@app.command()
def status() -> None:
    """Show project status."""
    if not get_lembas_manifest_path().exists():
        raise Abort("No lembas.toml found. Run 'lembas init' first.")

    manifest = load_lembas_manifest()
    project = manifest.get("project", {})

    console.print(f"[bold]Project:[/bold] {project.get('name', '(unnamed)')}")
    console.print(f"[bold]Type:[/bold] {project.get('type', '(unknown)')}")

    if desc := project.get("description"):
        console.print(f"[bold]Description:[/bold] {desc}")

    # Show plugins
    if plugins := manifest.get("plugins"):
        console.print("\n[bold]Plugins:[/bold]")
        for name, version in plugins.items():
            console.print(f"  - {name} {version}")

    # Show tasks
    if tasks := manifest.get("tasks"):
        console.print("\n[bold]Tasks:[/bold]")
        for name, task in tasks.items():
            if isinstance(task, str):
                console.print(f"  - {name}: {task}")
            else:
                console.print(f"  - {name}: {task.get('cmd', '(complex)')}")

    # Check pixi manifest status
    pixi_path = get_pixi_manifest_path()
    if pixi_path.exists():
        if is_pixi_manifest_stale():
            console.print(
                "\n[yellow]⚠ .lembas/pixi.toml is stale. Run 'lembas install' to update.[/yellow]"
            )
        else:
            console.print("\n[green]✓ .lembas/pixi.toml is up to date[/green]")
    else:
        console.print("\n[yellow]⚠ No .lembas/pixi.toml. Run 'lembas install' to create.[/yellow]")


@app.command("_run-cases", hidden=True)
def run_cases_internal() -> None:
    """Internal command to run study cases (called by synthesized pixi task)."""
    from lembas import load_local_plugins
    from lembas.study import load_cases

    load_local_plugins()
    cases = load_cases()

    console.print(f"Running {len(cases)} cases...")
    cases.run_all()

    raise Okay(f"Completed {len(cases)} cases")


# TODO: Merge this into `lembas run --handler <name>` and deprecate this command.
# See: https://github.com/lembas-project/lembas-core/issues/180
@app.command("case", hidden=True)
def run_case(
    case_handler_name: str,
    params: list[str] | None = typer.Argument(None),  # noqa: B008
    *,
    plugin: Path | None = None,
) -> None:
    """Run a single case of a given case handler type (low-level)."""
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


def _print_cases_table(cases: list) -> None:
    """Print a table of cases with styled status and notes."""
    from lembas.index import CaseStatus

    status_styles = {
        CaseStatus.COMPLETE: "[green]complete[/green]",
        CaseStatus.MISSING: "[red]missing[/red]",
        CaseStatus.PENDING: "[yellow]pending[/yellow]",
    }

    table = Table(title="Cases")
    table.add_column("ID", style="cyan")
    table.add_column("HANDLER")
    table.add_column("STATUS")
    table.add_column("PATH")
    table.add_column("NOTES")

    for case in cases:
        styled_status = status_styles.get(case.status, case.status.value)
        styled_notes = f"[yellow]{case.notes}[/yellow]" if case.notes else ""
        table.add_row(case.short_id, case.handler, styled_status, case.path, styled_notes)

    console.print(table)


@cases_app.callback(invoke_without_command=True)
def cases_callback(ctx: typer.Context) -> None:
    """Manage study cases."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@cases_app.command("list")
def cases_list(
    pending: bool = typer.Option(False, "--pending", "-p", help="Show only pending cases"),
    complete: bool = typer.Option(False, "--complete", "-c", help="Show only complete cases"),
) -> None:
    """List all cases (specified and run) with their status.

    By default shows all cases from cases.yaml and any that have been run.
    Use --pending or --complete to filter (mutually exclusive).
    """
    from lembas.index import CaseStatus
    from lembas.index import ensure_index_fresh
    from lembas.index import gather_case_info
    from lembas.index import load_specified_cases

    if pending and complete:
        raise Abort("--pending and --complete are mutually exclusive")

    # Load index, auto-reindex if stale
    index, was_reindexed = ensure_index_fresh()
    if was_reindexed:
        console.print("[dim]Index stale, reindexed.[/dim]")

    # Load specified cases from cases.yaml
    specified_result = load_specified_cases()
    if specified_result.warning:
        console.print(f"[yellow]Warning: {specified_result.warning}[/yellow]\n")

    # Determine filter
    filter_status = None
    if pending:
        filter_status = CaseStatus.PENDING
    elif complete:
        filter_status = CaseStatus.COMPLETE

    # Gather case info
    cases = gather_case_info(index, specified_result.cases, filter_status)

    if not cases and not index and not specified_result.cases:
        console.print("No cases found. Add cases to cases.yaml or run 'lembas run'.")
        return

    _print_cases_table(cases)


@cases_app.command("reindex")
def cases_reindex() -> None:
    """Rebuild index from case.toml files.

    Scans for case.toml files, extracts handler and inputs,
    recomputes case IDs, and rebuilds .lembas/cases.json.
    """
    from lembas.index import CASE_TOML_PATH
    from lembas.index import reindex_cases

    console.print(f"Scanning cases/**/{CASE_TOML_PATH}...")
    index = reindex_cases()
    console.print(f"Found {len(index)} cases, rebuilt index.")


@cases_app.command("clean")
def cases_clean(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Clean up stale index entries and remove duplicate path references.

    Removes index entries where the path no longer exists.
    Shows what will be cleaned and prompts for confirmation unless --force is used.
    """
    from lembas.index import clean_index
    from lembas.index import load_case_index
    from lembas.index import save_case_index

    if not load_case_index():
        console.print("Index is empty, nothing to clean.")
        return

    result = clean_index()

    # Print what will be cleaned
    for short_id, path in result.stale_entries:
        console.print(f"[red]STALE:[/red] {short_id} -> {path} (no existing paths)")
    for short_id, removed in result.pruned_entries:
        console.print(f"[yellow]PRUNE:[/yellow] {short_id} removed {removed} missing path(s)")

    if result.is_clean:
        console.print("[green]Index is clean, no changes needed.[/green]")
        return

    # Prompt for confirmation unless --force
    if not force:
        console.print(f"\nWill remove {len(result.stale_entries)} stale entries.")
        confirm = typer.confirm("Proceed?")
        if not confirm:
            console.print("Aborted.")
            return

    save_case_index(result.cleaned_index)
    console.print(
        f"[green]Cleaned index:[/green] removed {len(result.stale_entries)} stale entries."
    )
