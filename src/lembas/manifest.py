"""Lembas manifest (lembas.toml) parsing and validation."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

__all__ = [
    "LembasManifest",
    "ProjectConfig",
    "PlatformConfig",
    "PluginConfig",
    "TaskConfig",
    "WorkspaceConfig",
]


class ProjectConfig(BaseModel):
    """The [project] section of lembas.toml."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    type: Literal["study", "plugin", "workspace"] = "study"
    version: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=lambda: ["conda-forge"])
    platforms: list[str] = Field(default_factory=lambda: ["linux-64", "osx-arm64"])
    publish_to: Annotated[str | None, Field(alias="publish-to")] = None


class PlatformConfig(BaseModel):
    """The [platform] section of lembas.toml."""

    server: str | None = None
    project: str | None = None


class PluginConfig(BaseModel):
    """The [plugin] section of lembas.toml (for type=plugin projects)."""

    model_config = ConfigDict(populate_by_name=True)

    entry_point: Annotated[str | None, Field(alias="entry-point")] = None
    environment: Literal["conda", "docker"] = "conda"
    handlers: list[str] = Field(default_factory=list)


class TaskConfig(BaseModel):
    """A single task definition."""

    model_config = ConfigDict(populate_by_name=True)

    cmd: str
    description: str | None = None
    depends_on: Annotated[list[str], Field(alias="depends-on")] = Field(default_factory=list)


class WorkspaceConfig(BaseModel):
    """The [workspace] section of lembas.toml (for type=workspace projects)."""

    members: list[str] = Field(default_factory=list)


def _parse_task(value: str | dict[str, Any]) -> TaskConfig:
    """Parse a task value which can be a string (cmd) or a dict."""
    if isinstance(value, str):
        return TaskConfig(cmd=value)
    return TaskConfig.model_validate(value)


class LembasManifest(BaseModel):
    """The complete lembas.toml manifest."""

    model_config = ConfigDict(populate_by_name=True)

    project: ProjectConfig
    plugins: dict[str, str] = Field(default_factory=dict)
    dependencies: dict[str, str] = Field(default_factory=dict)
    dev_dependencies: Annotated[dict[str, str], Field(alias="dev-dependencies")] = Field(
        default_factory=dict
    )
    platform: PlatformConfig | None = None
    plugin: PluginConfig | None = None
    tasks: dict[str, TaskConfig] = Field(default_factory=dict)
    workspace: WorkspaceConfig | None = None
    environments: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_path(cls, path: Path) -> LembasManifest:
        """Load a manifest from a lembas.toml file."""
        with path.open("rb") as f:
            data = tomllib.load(f)

        # Parse tasks specially since they can be strings or dicts
        if "tasks" in data:
            data["tasks"] = {name: _parse_task(value) for name, value in data["tasks"].items()}

        return cls.model_validate(data)

    @classmethod
    def find_and_load(cls, start_dir: Path | None = None) -> tuple[LembasManifest, Path]:
        """Find lembas.toml in start_dir or ancestors, and load it.

        Returns:
            Tuple of (manifest, path to lembas.toml)

        Raises:
            FileNotFoundError: If no lembas.toml is found.
        """
        search_dir = (start_dir or Path.cwd()).resolve()
        for parent in [search_dir, *search_dir.parents]:
            manifest_path = parent / "lembas.toml"
            if manifest_path.exists():
                return cls.from_path(manifest_path), manifest_path
        raise FileNotFoundError("No lembas.toml found in current directory or parents")

    def sections_hash(self) -> str:
        """Compute SHA-256 hash of sections relevant to pixi.toml synthesis.

        Used for staleness checking of .lembas/pixi.toml.
        """
        relevant: dict[str, Any] = {
            "project": self.project.model_dump(by_alias=True),
            "plugins": self.plugins,
            "dependencies": self.dependencies,
            "dev_dependencies": self.dev_dependencies,
            "tasks": {k: v.model_dump(by_alias=True) for k, v in self.tasks.items()},
            "environments": self.environments,
        }
        if self.workspace:
            relevant["workspace"] = self.workspace.model_dump(by_alias=True)

        content = json.dumps(relevant, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()
