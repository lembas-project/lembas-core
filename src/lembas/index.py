"""Case index management for mapping case IDs to directory paths."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import toml

__all__ = [
    "load_case_index",
    "save_case_index",
    "get_case_dir_from_index",
    "update_case_index",
    "reindex_cases",
    "ensure_index_fresh",
    "gather_case_info",
    "load_specified_cases",
    "clean_index",
    "CaseInfo",
    "CaseStatus",
    "CleanResult",
    "SpecifiedCasesResult",
    "CASE_TOML_PATH",
]

LEMBAS_DIR = Path(".lembas")
CASES_INDEX_FILE = LEMBAS_DIR / "cases.json"
CASE_TOML_PATH = Path("lembas") / "case.toml"
STATUS_FILE_PATH = Path("lembas") / "status.json"


def _get_case_status(case_dir: Path) -> CaseStatus:
    """Determine case status from filesystem.

    A case is COMPLETE if status.json exists and has completed_at set.
    A case is PENDING if it has case.toml or status.json but isn't complete.
    A case is MISSING if the directory doesn't exist.
    """
    if not case_dir.exists():
        return CaseStatus.MISSING

    status_file = case_dir / STATUS_FILE_PATH
    if status_file.exists():
        try:
            status = json.loads(status_file.read_text())
            if status.get("completed_at"):
                return CaseStatus.COMPLETE
        except (json.JSONDecodeError, OSError):
            pass
        return CaseStatus.PENDING

    case_toml = case_dir / CASE_TOML_PATH
    if case_toml.exists():
        return CaseStatus.PENDING

    return CaseStatus.MISSING


class CaseStatus(Enum):
    """Status of a case."""

    COMPLETE = "complete"
    MISSING = "missing"
    PENDING = "pending"


@dataclass
class CaseInfo:
    """Information about a case for display purposes."""

    id: str
    short_id: str
    handler: str
    path: str
    status: CaseStatus
    notes: str


def load_case_index(project_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load case index from .lembas/cases.json.

    Args:
        project_root: Project root directory. Defaults to current working directory.

    Returns:
        Dictionary mapping case_id to {path, handler, duplicates?}.
        For backwards compatibility, also handles old format (case_id -> path string).
    """
    root = project_root or Path.cwd()
    index_file = root / CASES_INDEX_FILE
    if not index_file.exists():
        return {}
    raw = json.loads(index_file.read_text())
    # Handle old format: case_id -> path string
    if raw and isinstance(next(iter(raw.values())), str):
        return {k: {"path": v, "handler": ""} for k, v in raw.items()}
    return raw


def save_case_index(index: dict[str, dict[str, Any]], project_root: Path | None = None) -> None:
    """Save case index to .lembas/cases.json.

    Args:
        index: Dictionary mapping case_id to {path, handler, duplicates?}.
        project_root: Project root directory. Defaults to current working directory.
    """
    root = project_root or Path.cwd()
    index_file = root / CASES_INDEX_FILE
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")


def get_case_dir_from_index(case_id: str, project_root: Path | None = None) -> Path | None:
    """Look up case directory from index, verify it exists.

    Args:
        case_id: The content-addressed case identifier.
        project_root: Project root directory. Defaults to current working directory.

    Returns:
        Path to the case directory if found and exists, None otherwise.
    """
    root = project_root or Path.cwd()
    index = load_case_index(root)
    if case_id in index:
        entry = index[case_id]
        path = root / entry["path"]
        if path.exists():
            return path
    return None


def update_case_index(
    case_id: str,
    case_dir: Path,
    handler: str = "",
    project_root: Path | None = None,
) -> None:
    """Add or update a case in the index.

    Args:
        case_id: The content-addressed case identifier.
        case_dir: Path to the case directory.
        handler: Handler class name.
        project_root: Project root directory. Defaults to current working directory.
    """
    root = project_root or Path.cwd()
    index = load_case_index(root)
    try:
        relative_path = str(case_dir.relative_to(root))
    except ValueError:
        relative_path = str(case_dir)

    if case_id in index:
        # Update path, keep track of all paths
        entry = index[case_id]
        entry["path"] = relative_path
        if relative_path not in entry.get("all_paths", []):
            entry.setdefault("all_paths", []).append(relative_path)
    else:
        index[case_id] = {
            "path": relative_path,
            "handler": handler,
            "all_paths": [relative_path],
        }
    save_case_index(index, root)


def compute_case_id(handler_fqn: str, inputs: dict) -> str:
    """Compute case ID from handler name and inputs.

    Args:
        handler_fqn: Fully qualified name of the case handler.
        inputs: Dictionary of input parameter values.

    Returns:
        Full 64-character hex string (SHA-256).
    """
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    content = f"{handler_fqn}:{canonical}"
    return hashlib.sha256(content.encode()).hexdigest()


def reindex_cases(
    cases_root: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Scan case.toml files and rebuild the index.

    Searches for lembas/case.toml files under the cases directory, extracts
    the handler and inputs from each, recomputes the case ID, and rebuilds
    the index file.

    Args:
        cases_root: Root directory to scan for cases. Defaults to "cases" under project_root.
        project_root: Project root directory. Defaults to current working directory.

    Returns:
        The rebuilt index mapping case_id to {path, handler, all_paths}.
    """
    root = project_root or Path.cwd()
    cases_dir = cases_root or (root / "cases")

    index: dict[str, dict[str, Any]] = {}

    if not cases_dir.exists():
        save_case_index(index, root)
        return index

    for case_toml in cases_dir.rglob(str(CASE_TOML_PATH)):
        case_dir = case_toml.parent.parent
        try:
            data = toml.loads(case_toml.read_text())
            handler_fqn = data["lembas"]["case-handler"]
            inputs = data["lembas"]["inputs"]
            case_id = compute_case_id(handler_fqn, inputs)
            try:
                relative_path = str(case_dir.relative_to(root))
            except ValueError:
                relative_path = str(case_dir)

            handler_name = handler_fqn.split(".")[-1]

            if case_id in index:
                # Track all paths for this case_id
                index[case_id]["all_paths"].append(relative_path)
            else:
                index[case_id] = {
                    "path": relative_path,
                    "handler": handler_name,
                    "all_paths": [relative_path],
                }
        except (KeyError, toml.TomlDecodeError):
            continue

    save_case_index(index, root)
    return index


def ensure_index_fresh(project_root: Path | None = None) -> tuple[dict[str, dict[str, Any]], bool]:
    """Load index, auto-reindexing if stale.

    Args:
        project_root: Project root directory. Defaults to current working directory.

    Returns:
        Tuple of (index, was_reindexed).
    """
    root = project_root or Path.cwd()
    cases_dir = root / "cases"
    index = load_case_index(root)

    if not index:
        if cases_dir.exists() and any(cases_dir.rglob(str(CASE_TOML_PATH))):
            return reindex_cases(project_root=root), True
        return index, False

    if cases_dir.exists():
        disk_count = sum(1 for _ in cases_dir.rglob(str(CASE_TOML_PATH)))
        index_path_count = sum(len(e.get("all_paths", [e["path"]])) for e in index.values())
        if disk_count != index_path_count:
            return reindex_cases(project_root=root), True

    return index, False


def gather_case_info(
    index: dict[str, dict[str, Any]],
    specified_cases: dict[str, tuple[str, str]] | None = None,
    filter_status: CaseStatus | None = None,
) -> list[CaseInfo]:
    """Gather case information from index and specified cases.

    Args:
        index: The case index mapping id to {path, handler, all_paths}.
        specified_cases: Optional dict of id -> (handler, expected_path) from cases.yaml.
        filter_status: Optional status to filter by.

    Returns:
        List of CaseInfo objects sorted by path.
    """
    specified = specified_cases or {}
    all_ids = set(index.keys()) | set(specified.keys())
    cases: list[CaseInfo] = []

    for case_id in all_ids:
        if case_id in index:
            entry = index[case_id]
            path = entry["path"]
            handler = entry.get("handler", "")
            all_paths = entry.get("all_paths", [path])

            # Check for duplicates
            notes = ""
            if len(all_paths) > 1:
                notes = f"+{len(all_paths) - 1} duplicate(s)"

            # Check if matches specified case
            if case_id in specified:
                specified_handler, specified_path = specified[case_id]
                handler = handler or specified_handler
                if path != specified_path:
                    notes = f"expected: {specified_path}"

            status = _get_case_status(Path(path))
            if not handler:
                handler = "-"
        else:
            # In specified but not run
            handler, path = specified[case_id]
            status = CaseStatus.PENDING
            notes = ""

        if filter_status and status != filter_status:
            continue

        cases.append(
            CaseInfo(
                id=case_id,
                short_id=case_id[:8],
                handler=handler,
                path=path,
                status=status,
                notes=notes,
            )
        )

    cases.sort(key=lambda c: c.path)
    return cases


@dataclass
class SpecifiedCasesResult:
    """Result of loading specified cases from cases.yaml."""

    cases: dict[str, tuple[str, str]]  # id -> (handler_name, expected_path)
    warning: str | None  # Warning message if loading failed partially


def load_specified_cases() -> SpecifiedCasesResult:
    """Load specified cases from cases.yaml.

    Returns:
        SpecifiedCasesResult with cases dict and optional warning.
    """
    from lembas.manifest import load_lembas_manifest

    specified: dict[str, tuple[str, str]] = {}
    warning: str | None = None

    try:
        manifest = load_lembas_manifest()
        if "study" in manifest and "cases" in manifest["study"]:
            from lembas import load_local_plugins
            from lembas.study import load_cases

            load_local_plugins()
            case_list = load_cases()
            for case in case_list:
                specified[case.id] = (
                    case.fully_resolved_name.split(".")[-1],
                    str(case.relative_case_dir),
                )
    except FileNotFoundError:
        pass
    except (ImportError, ModuleNotFoundError) as e:
        warning = (
            f"Could not load cases.yaml (missing dependency: {e.name}). Showing only run cases."
        )

    return SpecifiedCasesResult(cases=specified, warning=warning)


@dataclass
class CleanResult:
    """Result of cleaning the index."""

    stale_entries: list[tuple[str, str]]  # (short_id, path)
    pruned_entries: list[tuple[str, int]]  # (short_id, num_removed)
    cleaned_index: dict[str, dict[str, Any]]
    is_clean: bool


def clean_index(project_root: Path | None = None) -> CleanResult:
    """Analyze index and prepare cleaned version.

    Does not save the index — caller decides whether to apply.

    Args:
        project_root: Project root directory. Defaults to current working directory.

    Returns:
        CleanResult with stale/pruned entries and the cleaned index.
    """
    root = project_root or Path.cwd()
    index = load_case_index(root)

    stale_entries: list[tuple[str, str]] = []
    pruned_entries: list[tuple[str, int]] = []
    cleaned_index: dict[str, dict[str, Any]] = {}

    for case_id, entry in index.items():
        path = entry["path"]
        all_paths = entry.get("all_paths", [path])
        existing_paths = [p for p in all_paths if Path(p).exists()]

        short_id = case_id[:8]
        if not existing_paths:
            stale_entries.append((short_id, path))
        else:
            cleaned_entry = {
                "path": existing_paths[0],
                "handler": entry.get("handler", ""),
                "all_paths": existing_paths,
            }
            if len(existing_paths) < len(all_paths):
                pruned_entries.append((short_id, len(all_paths) - len(existing_paths)))
            cleaned_index[case_id] = cleaned_entry

    is_clean = not stale_entries and cleaned_index == index

    return CleanResult(
        stale_entries=stale_entries,
        pruned_entries=pruned_entries,
        cleaned_index=cleaned_index,
        is_clean=is_clean,
    )
