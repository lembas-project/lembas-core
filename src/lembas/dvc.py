"""DVC wrapper for case data synchronization.

Synthesizes DVC configuration and wraps DVC commands for case-level
push/pull operations. DVC is an implementation detail — users interact
through `lembas push/pull`, not DVC directly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from lembas.manifest import get_lembas_dir


def get_dvc_dir(project_root: Path | None = None) -> Path:
    """Get the .lembas/dvc directory path."""
    return get_lembas_dir(project_root) / "dvc"


def get_cases_dir(project_root: Path | None = None) -> Path:
    """Get the cases directory path."""
    root = project_root or Path.cwd()
    return root / "cases"


def init_dvc(project_root: Path | None = None) -> None:
    """Initialize DVC in .lembas/dvc if not already initialized."""
    dvc_dir = get_dvc_dir(project_root)
    if (dvc_dir / "config").exists():
        return

    dvc_dir.mkdir(parents=True, exist_ok=True)

    # Initialize DVC with no SCM (we manage git integration ourselves)
    _run_dvc(["init", "--no-scm"], project_root)


def configure_remote(
    server_url: str,
    study_id: str,
    *,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    project_root: Path | None = None,
) -> None:
    """Configure DVC remote to point to platform storage.

    Args:
        server_url: Platform server URL (e.g. https://lembas.fly.dev)
        study_id: Study ID for scoping storage
        access_key_id: S3 access key (optional, can use env vars)
        secret_access_key: S3 secret key (optional, can use env vars)
        project_root: Project root directory
    """
    init_dvc(project_root)

    # Remote URL points to platform's S3-compatible storage
    # Format: s3://{bucket}/studies/{study_id}
    remote_url = f"{server_url}/storage/{study_id}"

    _run_dvc(["remote", "add", "-f", "platform", remote_url], project_root)
    _run_dvc(["remote", "default", "platform"], project_root)

    if access_key_id:
        _run_dvc(
            ["remote", "modify", "platform", "access_key_id", access_key_id],
            project_root,
        )
    if secret_access_key:
        _run_dvc(
            ["remote", "modify", "platform", "secret_access_key", secret_access_key],
            project_root,
        )


def track_case(case_id: str, project_root: Path | None = None) -> Path:
    """Track a case directory with DVC.

    Creates cases/{case_id}.dvc pointing to cases/{case_id}/.

    Args:
        case_id: The case ID (content hash)
        project_root: Project root directory

    Returns:
        Path to the created .dvc file
    """
    cases_dir = get_cases_dir(project_root)
    case_dir = cases_dir / case_id

    if not case_dir.exists():
        raise FileNotFoundError(f"Case directory not found: {case_dir}")

    dvc_file = cases_dir / f"{case_id}.dvc"

    # If already tracked, update it
    if dvc_file.exists():
        _run_dvc(["add", str(case_dir)], project_root)
    else:
        _run_dvc(["add", str(case_dir)], project_root)

    return dvc_file


def push_case(case_id: str, project_root: Path | None = None) -> None:
    """Push a single case's data to remote storage.

    Args:
        case_id: The case ID to push
        project_root: Project root directory
    """
    cases_dir = get_cases_dir(project_root)
    dvc_file = cases_dir / f"{case_id}.dvc"

    if not dvc_file.exists():
        raise FileNotFoundError(f"Case not tracked: {dvc_file}")

    _run_dvc(["push", str(dvc_file)], project_root)


def pull_case(case_id: str, project_root: Path | None = None) -> None:
    """Pull a single case's data from remote storage.

    Args:
        case_id: The case ID to pull
        project_root: Project root directory
    """
    cases_dir = get_cases_dir(project_root)
    dvc_file = cases_dir / f"{case_id}.dvc"

    if not dvc_file.exists():
        raise FileNotFoundError(f"Case not tracked: {dvc_file}")

    _run_dvc(["pull", str(dvc_file)], project_root)


def push_all(project_root: Path | None = None) -> None:
    """Push all tracked cases to remote storage."""
    _run_dvc(["push"], project_root)


def pull_all(project_root: Path | None = None) -> None:
    """Pull all tracked cases from remote storage."""
    _run_dvc(["pull"], project_root)


def list_tracked_cases(project_root: Path | None = None) -> list[str]:
    """List all case IDs that have .dvc files.

    Returns:
        List of case IDs (without .dvc extension)
    """
    cases_dir = get_cases_dir(project_root)
    if not cases_dir.exists():
        return []

    return [p.stem for p in cases_dir.glob("*.dvc")]


def is_case_cached(case_id: str, project_root: Path | None = None) -> bool:
    """Check if a case's data is available locally.

    Args:
        case_id: The case ID to check
        project_root: Project root directory

    Returns:
        True if the case data exists locally
    """
    cases_dir = get_cases_dir(project_root)
    case_dir = cases_dir / case_id
    return case_dir.exists() and any(case_dir.iterdir())


def _run_dvc(
    args: list[str],
    project_root: Path | None = None,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a DVC command with the synthesized config.

    Args:
        args: DVC command arguments (without 'dvc' prefix)
        project_root: Project root directory
        check: Raise on non-zero exit code

    Returns:
        Completed process result
    """
    dvc_dir = get_dvc_dir(project_root)
    root = project_root or Path.cwd()

    env_override = {
        "DVC_DIR": str(dvc_dir),
    }

    import os

    env = {**os.environ, **env_override}

    cmd = ["dvc", *args]
    return subprocess.run(
        cmd,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )
