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
from lembas.manifest import get_lembas_dir
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

# Subcommand group for auth
auth_app = typer.Typer(help="Platform authentication")
app.add_typer(auth_app, name="auth")


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


# --- Auth Commands ---


@auth_app.callback(invoke_without_command=True)
def auth_callback(ctx: typer.Context) -> None:
    """Platform authentication commands."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@auth_app.command("login")
def auth_login(
    token: str | None = typer.Option(None, "--token", "-t", help="API token"),
) -> None:
    """Authenticate with the lembas platform.

    If --token is provided, stores it directly.
    Otherwise, prompts for interactive login (not yet implemented).
    """
    from lembas.platform import store_token

    if token:
        store_token(token)
        raise Okay("Token stored successfully")

    raise Abort("Interactive login not yet implemented. Use --token to provide an API token.")


@auth_app.command("logout")
def auth_logout() -> None:
    """Clear stored authentication credentials."""
    from lembas.platform import clear_token

    clear_token()
    raise Okay("Logged out")


@auth_app.command("status")
def auth_status() -> None:
    """Show current authentication status."""
    from lembas.platform import PlatformClient
    from lembas.platform import PlatformConfig
    from lembas.platform import get_stored_token

    token = get_stored_token()
    if not token:
        console.print("[yellow]Not logged in[/yellow]")
        console.print("Run 'lembas auth login --token <token>' to authenticate.")
        return

    console.print("[green]Logged in[/green] (token stored)")

    # Try to check server connectivity if manifest has platform config
    try:
        manifest = load_lembas_manifest()
        config = PlatformConfig.from_manifest(manifest)
        if config:
            console.print(f"Server: {config.server}")
            with PlatformClient(config, token) as client:
                if client.health_check():
                    console.print("[green]Server reachable[/green]")
                else:
                    console.print("[yellow]Server unreachable[/yellow]")
    except FileNotFoundError:
        pass


@app.command()
def push(
    force: bool = typer.Option(False, "--force", "-f", help="Create new study even if one exists"),
    data: bool = typer.Option(True, "--data/--no-data", help="Push case data (not just metadata)"),
) -> None:
    """Push study state to the platform.

    Reads the local case index and status files, then registers the study
    with all cases and their current status on the configured platform server.

    If a study was previously pushed, updates the existing study. Use --force
    to create a new study instead.

    By default, also pushes case data (output files). Use --no-data
    to push only metadata.
    """
    import json
    import logging
    from datetime import UTC
    from datetime import datetime
    from pathlib import Path

    from lembas import load_local_plugins
    from lembas.index import load_case_index
    from lembas.platform import PlatformClient
    from lembas.platform import PlatformConfig
    from lembas.schema import extract_handler_schema
    from lembas.schema import get_git_ref

    # Suppress verbose httpx request logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    from lembas.study import load_cases
    from lembas.sync import push_case as sync_push_case

    if not get_lembas_manifest_path().exists():
        raise Abort("No lembas.toml found. Run 'lembas init' first.")

    manifest = load_lembas_manifest()
    config = PlatformConfig.from_manifest(manifest)
    if not config:
        raise Abort("No [platform] section in lembas.toml. Add server URL to push.")

    project = manifest.get("project", {})
    study_name = project.get("name", "unnamed-study")
    description = project.get("description")
    tags = project.get("tags", [])
    plugins_declared = list(manifest.get("plugins", {}).keys())

    # Load local plugins and cases
    load_local_plugins()
    cases = load_cases()

    console.print(f"Pushing study [bold]{study_name}[/bold] to {config.server}")
    console.print(f"  {len(cases)} cases")

    # Extract handler schemas
    handler_classes: dict[str, type] = {}
    for case in cases:
        handler_name = case.__class__.__name__
        if handler_name not in handler_classes:
            handler_classes[handler_name] = case.__class__

    git_source = get_git_ref()
    handler_schemas = []
    for handler_cls in handler_classes.values():
        schema = extract_handler_schema(
            handler_cls,
            base_url=f"{config.server}/schemas",
            source=git_source,
        )
        handler_schemas.append(schema)

    # Build case data with status and results
    case_data = []
    index = load_case_index()

    for case in cases:
        case_id = case.id
        handler_fqn = f"{case.__class__.__module__}.{case.__class__.__name__}"

        # Find case path from index
        case_info = index.get(case_id, {})
        case_path = case_info.get("path")

        status = "pending"
        duration_seconds = None
        results_dict = {}

        if case_path:
            status_file = Path(case_path) / ".lembas" / "status.json"
            if status_file.exists():
                with status_file.open() as f:
                    status_data = json.load(f)
                if status_data.get("completed_at"):
                    status = "complete"
                    # Calculate duration
                    started = status_data.get("started_at")
                    completed = status_data.get("completed_at")
                    if started and completed:
                        start_dt = datetime.fromisoformat(started)
                        end_dt = datetime.fromisoformat(completed)
                        duration_seconds = (end_dt - start_dt).total_seconds()

                    # Load results from status.json (saved during run)
                    results_dict = status_data.get("results", {})
            else:
                status = "pending"

        case_data.append(
            {
                "case_id": case_id,
                "handler_fqn": handler_fqn,
                "inputs": case.inputs,
                "status": status,
                "duration_seconds": duration_seconds,
                "results": results_dict,
            }
        )

    # Push to platform
    lembas_dir = get_lembas_dir()
    study_state_path = lembas_dir / "study.json"

    with PlatformClient(config) as client:
        if not client.health_check():
            raise Abort(f"Cannot reach server at {config.server}")

        # Build payload
        payload = {
            "name": study_name,
            "description": description,
            "tags": tags,
            "plugins_declared": plugins_declared,
            "handlers": [
                {
                    "name": s["title"],
                    "schema_fingerprint": s["x-lembas-fingerprint"],
                    "schema": s,
                }
                for s in handler_schemas
            ],
            "cases": [
                {
                    "case_id": c["case_id"],
                    "handler_fqn": c["handler_fqn"],
                    "inputs": c["inputs"],
                }
                for c in case_data
            ],
        }

        # Check for existing study state
        existing_study_id = None
        if not force and study_state_path.exists():
            try:
                state = json.loads(study_state_path.read_text())
                if state.get("server") == config.server:
                    existing_study_id = state.get("id")
            except (json.JSONDecodeError, KeyError):
                pass

        if existing_study_id:
            # Try to update existing study
            response = client.client.put(f"/api/studies/{existing_study_id}", json=payload)
            if response.status_code == 404:
                # Study deleted on server - create new one
                console.print(
                    "  [yellow]Study no longer exists on server, creating new one[/yellow]"
                )
                response = client.client.post("/api/studies", json=payload)
                response.raise_for_status()
                study = response.json()
                study_id = study["id"]
                console.print(f"  Created study: {study_id}")
            else:
                response.raise_for_status()
                study = response.json()
                study_id = study["id"]
                console.print(f"  Updated study: {study_id}")
        else:
            # Create new study
            response = client.client.post("/api/studies", json=payload)
            response.raise_for_status()
            study = response.json()
            study_id = study["id"]
            console.print(f"  Created study: {study_id}")

        # Save study state locally
        study_state = {
            "id": study_id,
            "server": config.server,
            "pushed_at": datetime.now(UTC).isoformat(),
            "name": study_name,
        }
        study_state_path.write_text(json.dumps(study_state, indent=2))

        # Update each case with status and results
        complete_count = 0
        for c in case_data:
            if c["status"] == "complete":
                dur = c["duration_seconds"]
                res = c["results"]
                client.update_case_status(
                    study_id,
                    str(c["case_id"]),
                    "complete",
                    duration_seconds=float(dur) if isinstance(dur, (int, float)) else None,
                    results=res if isinstance(res, dict) else None,
                )
                complete_count += 1

        console.print(f"  Updated {complete_count} complete cases with results")

        # Push case data
        if data and complete_count > 0:
            console.print("  Syncing case data...")

            total_files = 0
            total_uploaded = 0
            total_bytes = 0
            synced_count = 0
            skipped_count = 0

            for c in case_data:
                if c["status"] == "complete":
                    cid = str(c["case_id"])
                    case_info = index.get(cid, {})
                    case_path = case_info.get("path")
                    if case_path and Path(case_path).exists():
                        try:
                            stats = sync_push_case(
                                client.client,
                                study_id,
                                cid,
                                Path(case_path),
                            )
                            total_files += stats["files"]
                            total_uploaded += stats["uploaded"]
                            total_bytes += stats["bytes"]
                            if stats["uploaded"] > 0:
                                synced_count += 1
                            else:
                                skipped_count += 1
                        except Exception as e:
                            console.print(f"  [yellow]Could not sync case {cid[:8]}: {e}[/yellow]")

            if total_uploaded > 0:
                mb = total_bytes / (1024 * 1024)
                console.print(
                    f"  Uploaded {total_uploaded} files ({mb:.1f} MB) from {synced_count} cases"
                )
            if skipped_count > 0:
                console.print(f"  {skipped_count} cases already synced")

    raise Okay(f"Pushed to {config.server}/studies/{study_id}")


@app.command()
def pull(
    case_id: str | None = typer.Option(None, "--case", "-c", help="Pull a specific case by ID"),
) -> None:
    """Pull case data from the platform.

    Downloads case output files from the platform storage.
    Use --case to pull a specific case, otherwise pulls all cases.
    """
    import json
    import logging
    from pathlib import Path

    from lembas.index import load_case_index
    from lembas.platform import PlatformClient
    from lembas.platform import PlatformConfig
    from lembas.sync import pull_case as sync_pull_case

    # Suppress verbose httpx request logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if not get_lembas_manifest_path().exists():
        raise Abort("No lembas.toml found. Run 'lembas init' first.")

    manifest = load_lembas_manifest()
    config = PlatformConfig.from_manifest(manifest)
    if not config:
        raise Abort("No [platform] section in lembas.toml.")

    # Get study ID from local state
    lembas_dir = get_lembas_dir()
    study_state_path = lembas_dir / "study.json"

    if not study_state_path.exists():
        raise Abort("No local study state. Run 'lembas push' first or clone from platform.")

    state = json.loads(study_state_path.read_text())
    study_id = state.get("id")
    if not study_id:
        raise Abort("Invalid study state - missing ID.")

    index = load_case_index()

    with PlatformClient(config) as client:
        if case_id:
            # Pull specific case
            case_info = index.get(case_id, {})
            case_path = case_info.get("path")
            if not case_path:
                raise Abort(f"Case {case_id[:8]} not found in local index")

            console.print(f"Pulling case {case_id[:8]}...")
            try:
                stats = sync_pull_case(client.client, study_id, case_id, Path(case_path))
                mb = stats["bytes"] / (1024 * 1024)
                raise Okay(f"Pulled {stats['downloaded']} files ({mb:.1f} MB)")
            except Exception as e:
                raise Abort(f"Pull failed: {e}") from e

        else:
            # Pull all cases
            console.print("Pulling all cases...")
            total_files = 0
            total_downloaded = 0
            total_bytes = 0
            synced_count = 0
            skipped_count = 0

            for cid, case_info in index.items():
                case_path = case_info.get("path")
                if not case_path:
                    continue
                try:
                    stats = sync_pull_case(client.client, study_id, cid, Path(case_path))
                    total_files += stats["files"]
                    total_downloaded += stats["downloaded"]
                    total_bytes += stats["bytes"]
                    if stats["downloaded"] > 0:
                        synced_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    console.print(f"  [yellow]Failed to pull {cid[:8]}: {e}[/yellow]")

            if total_downloaded > 0:
                mb = total_bytes / (1024 * 1024)
                console.print(
                    f"  Downloaded {total_downloaded} files ({mb:.1f} MB) for {synced_count} cases"
                )
            if skipped_count > 0:
                console.print(f"  {skipped_count} cases already up to date")
            if total_downloaded == 0 and skipped_count > 0:
                raise Okay("All cases already up to date")
            raise Okay("Pull complete")
