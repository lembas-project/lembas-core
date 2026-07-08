"""Lembas manifest handling and pixi.toml synthesis."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import toml
import tomlkit

LEMBAS_DIR = ".lembas"
LEMBAS_MANIFEST = "lembas.toml"
PIXI_MANIFEST = "pixi.toml"


def get_lembas_dir(project_root: Path | None = None) -> Path:
    """Get the .lembas directory path."""
    root = project_root or Path.cwd()
    return root / LEMBAS_DIR


def get_lembas_manifest_path(project_root: Path | None = None) -> Path:
    """Get the lembas.toml path."""
    root = project_root or Path.cwd()
    return root / LEMBAS_MANIFEST


def get_pixi_manifest_path(project_root: Path | None = None) -> Path:
    """Get the synthesized pixi.toml path inside .lembas/."""
    return get_lembas_dir(project_root) / PIXI_MANIFEST


def load_lembas_manifest(project_root: Path | None = None) -> dict[str, Any]:
    """Load and parse lembas.toml."""
    path = get_lembas_manifest_path(project_root)
    if not path.exists():
        raise FileNotFoundError(f"No lembas.toml found at {path}")
    return toml.load(path)


def compute_manifest_hash(manifest: dict[str, Any]) -> str:
    """Compute SHA-256 hash of the relevant manifest sections for staleness check."""
    relevant_sections = ["project", "dependencies", "plugins", "tasks", "environments", "study"]
    relevant = {k: v for k, v in manifest.items() if k in relevant_sections}
    canonical = toml.dumps(relevant)
    return hashlib.sha256(canonical.encode()).hexdigest()


def extract_hash_from_pixi_manifest(pixi_path: Path) -> str | None:
    """Extract the lembas-hash from the synthesized pixi.toml header."""
    if not pixi_path.exists():
        return None
    with pixi_path.open() as f:
        for line in f:
            if line.startswith("# lembas-hash:"):
                return line.split(":", 1)[1].strip()
            if not line.startswith("#"):
                break
    return None


def is_pixi_manifest_stale(project_root: Path | None = None) -> bool:
    """Check if the synthesized pixi.toml is stale relative to lembas.toml."""
    pixi_path = get_pixi_manifest_path(project_root)
    if not pixi_path.exists():
        return True

    manifest = load_lembas_manifest(project_root)
    current_hash = compute_manifest_hash(manifest)
    stored_hash = extract_hash_from_pixi_manifest(pixi_path)

    return current_hash != stored_hash


def synthesize_pixi_manifest(project_root: Path | None = None) -> str:
    """Synthesize pixi.toml content from lembas.toml.

    Synthesis rules:
    - [project] → [workspace] (name, channels, platforms)
    - [plugins] entries → added to [dependencies]
    - [dependencies] → [dependencies]
    - [tasks] → [tasks]
    - [environments] → [environments] (passed through)
    - [platform], [plugin] → stripped (lembas-only)
    """
    manifest = load_lembas_manifest(project_root)
    manifest_hash = compute_manifest_hash(manifest)

    doc = tomlkit.document()

    # Add header comment with hash
    doc.add(tomlkit.comment(f"lembas-hash: {manifest_hash}"))
    doc.add(tomlkit.comment("Auto-generated from lembas.toml - do not edit"))
    doc.add(tomlkit.nl())

    # [workspace] from [project]
    project = manifest.get("project", {})
    workspace = tomlkit.table()
    if name := project.get("name"):
        workspace["name"] = name
    if channels := project.get("channels"):
        workspace["channels"] = channels
    if platforms := project.get("platforms"):
        workspace["platforms"] = platforms
    if workspace:
        doc["workspace"] = workspace

    # [dependencies] - merge regular deps and plugins
    deps = tomlkit.table()

    # Add regular dependencies
    for key, value in manifest.get("dependencies", {}).items():
        deps[key] = value

    # Add plugins as dependencies (plugins are conda packages)
    for key, value in manifest.get("plugins", {}).items():
        deps[key] = value

    if deps:
        doc["dependencies"] = deps

    # [tasks] - pass through, adding cwd=".." so tasks run from project root
    tasks_table = tomlkit.table()

    # Inject _lembas_run task if [study].cases is defined
    study_config = manifest.get("study", {})
    if "cases" in study_config:
        tasks_table["_lembas_run"] = {
            "cmd": "lembas _run-cases",
            "cwd": "..",
        }

    # Add user-defined tasks
    for name, task in manifest.get("tasks", {}).items():
        if isinstance(task, str):
            # Simple string task - convert to dict with cwd
            tasks_table[name] = {"cmd": task, "cwd": ".."}
        elif isinstance(task, dict):
            # Complex task - add cwd if not already set
            task_dict = dict(task)
            if "cwd" not in task_dict:
                task_dict["cwd"] = ".."
            tasks_table[name] = task_dict

    if tasks_table:
        doc["tasks"] = tasks_table

    # [environments] - pass through if present
    if environments := manifest.get("environments"):
        doc["environments"] = environments

    return tomlkit.dumps(doc)


def write_pixi_manifest(project_root: Path | None = None) -> Path:
    """Synthesize and write pixi.toml to .lembas/ directory."""
    lembas_dir = get_lembas_dir(project_root)
    lembas_dir.mkdir(exist_ok=True)

    # Create .gitignore in .lembas/ if it doesn't exist
    gitignore = lembas_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".pixi/\n")

    pixi_path = get_pixi_manifest_path(project_root)
    content = synthesize_pixi_manifest(project_root)
    pixi_path.write_text(content)

    return pixi_path


def ensure_pixi_manifest(project_root: Path | None = None) -> Path:
    """Ensure pixi.toml exists and is up-to-date, regenerating if stale."""
    if is_pixi_manifest_stale(project_root):
        return write_pixi_manifest(project_root)
    return get_pixi_manifest_path(project_root)


def run_pixi(
    args: list[str], project_root: Path | None = None
) -> subprocess.CompletedProcess[bytes]:
    """Run pixi with the synthesized manifest."""
    pixi_path = ensure_pixi_manifest(project_root)
    cmd = ["pixi", "--manifest-path", str(pixi_path), *args]
    return subprocess.run(cmd, check=False)
