"""Synthesize .lembas/pixi.toml from lembas.toml."""

from __future__ import annotations

import re
from pathlib import Path

import tomlkit
from tomlkit import TOMLDocument

from lembas.manifest import LembasManifest

__all__ = ["synthesize_pixi_toml", "is_synthesis_stale", "LEMBAS_DIR", "PIXI_TOML_NAME"]

LEMBAS_DIR = ".lembas"
PIXI_TOML_NAME = "pixi.toml"
HASH_COMMENT_PATTERN = re.compile(r"^# lembas-hash: ([a-f0-9]{64})$", re.MULTILINE)


def _extract_hash_from_pixi_toml(path: Path) -> str | None:
    """Extract the lembas-hash comment from a pixi.toml file."""
    if not path.exists():
        return None
    content = path.read_text()
    match = HASH_COMMENT_PATTERN.search(content)
    return match.group(1) if match else None


def is_synthesis_stale(manifest: LembasManifest, lembas_dir: Path) -> bool:
    """Check if .lembas/pixi.toml needs to be regenerated.

    Returns True if:
    - pixi.toml doesn't exist
    - pixi.toml has no hash comment
    - hash doesn't match current manifest sections
    """
    pixi_path = lembas_dir / PIXI_TOML_NAME
    stored_hash = _extract_hash_from_pixi_toml(pixi_path)
    if stored_hash is None:
        return True
    return stored_hash != manifest.sections_hash()


def _expand_channel_url(channel: str, platform_server: str | None) -> str:
    """Expand channel shorthand to full URL.

    - "conda-forge" stays as-is
    - "my-org/plugins" expands to "{server}/channels/my-org/plugins"
    """
    if "/" in channel and not channel.startswith("http") and platform_server:
        server = platform_server.rstrip("/")
        return f"{server}/channels/{channel}"
    return channel


def synthesize_pixi_toml(manifest: LembasManifest, project_root: Path) -> Path:
    """Generate .lembas/pixi.toml from lembas.toml manifest.

    Args:
        manifest: Parsed lembas.toml
        project_root: Directory containing lembas.toml

    Returns:
        Path to the generated pixi.toml
    """
    lembas_dir = project_root / LEMBAS_DIR
    lembas_dir.mkdir(exist_ok=True)

    doc = TOMLDocument()

    # Add hash comment at top
    manifest_hash = manifest.sections_hash()
    doc.add(tomlkit.comment(f"lembas-hash: {manifest_hash}"))
    doc.add(tomlkit.comment("Auto-generated from lembas.toml - do not edit"))
    doc.add(tomlkit.nl())

    # [workspace] section
    workspace = tomlkit.table()
    workspace["name"] = manifest.project.name

    # Expand channel URLs
    platform_server = manifest.platform.server if manifest.platform else None
    channels = [_expand_channel_url(ch, platform_server) for ch in manifest.project.channels]
    workspace["channels"] = channels
    workspace["platforms"] = manifest.project.platforms
    doc["workspace"] = workspace

    # [dependencies] - merge plugins (resolved to package names), dependencies, and dev-dependencies
    all_deps: dict[str, str] = {}

    # Plugins become dependencies (for now, just use the plugin name as the package name)
    # TODO: resolve plugin names to actual conda package names via registry
    for plugin_name, version_spec in manifest.plugins.items():
        all_deps[plugin_name] = version_spec

    # Regular dependencies
    all_deps.update(manifest.dependencies)

    # Dev dependencies (merged in for now - pixi features could separate them later)
    all_deps.update(manifest.dev_dependencies)

    if all_deps:
        deps = tomlkit.table()
        for name, spec in sorted(all_deps.items()):
            deps[name] = spec
        doc["dependencies"] = deps

    # [tasks] section
    if manifest.tasks:
        tasks = tomlkit.table()
        for task_name, task_config in manifest.tasks.items():
            if task_config.depends_on:
                # Use inline table for tasks with depends-on
                task_table = tomlkit.inline_table()
                task_table["cmd"] = task_config.cmd
                task_table["depends-on"] = task_config.depends_on
                tasks[task_name] = task_table
            else:
                # Simple string form
                tasks[task_name] = task_config.cmd
        doc["tasks"] = tasks

    # [environments] passthrough
    if manifest.environments:
        doc["environments"] = manifest.environments

    # Write the file
    pixi_path = lembas_dir / PIXI_TOML_NAME
    pixi_path.write_text(tomlkit.dumps(doc))

    # Write .gitignore if it doesn't exist
    gitignore_path = lembas_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text("# Auto-generated\n*\n")

    return pixi_path
