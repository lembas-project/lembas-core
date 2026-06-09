"""Tests for lembas.toml manifest parsing."""

from pathlib import Path
from textwrap import dedent

import pytest

from lembas.manifest import LembasManifest
from lembas.manifest import ProjectConfig
from lembas.manifest import TaskConfig


class TestProjectConfig:
    def test_minimal(self) -> None:
        config = ProjectConfig(name="my-project")
        assert config.name == "my-project"
        assert config.type == "study"
        assert config.channels == ["conda-forge"]
        assert config.platforms == ["linux-64", "osx-arm64"]

    def test_plugin_type(self) -> None:
        config = ProjectConfig(name="my-plugin", type="plugin", version="1.0.0")
        assert config.type == "plugin"
        assert config.version == "1.0.0"

    def test_publish_to_alias(self) -> None:
        data = {"name": "my-plugin", "publish-to": "my-org/channel"}
        config = ProjectConfig.model_validate(data)
        assert config.publish_to == "my-org/channel"


class TestTaskConfig:
    def test_simple_cmd(self) -> None:
        config = TaskConfig(cmd="pytest tests/")
        assert config.cmd == "pytest tests/"
        assert config.depends_on == []

    def test_with_depends_on(self) -> None:
        data = {"cmd": "python report.py", "depends-on": ["run", "test"]}
        config = TaskConfig.model_validate(data)
        assert config.depends_on == ["run", "test"]


class TestLembasManifest:
    def test_minimal_study(self, tmp_path: Path) -> None:
        toml_content = dedent("""\
            [project]
            name = "my-study"
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        manifest = LembasManifest.from_path(manifest_path)

        assert manifest.project.name == "my-study"
        assert manifest.project.type == "study"
        assert manifest.plugins == {}
        assert manifest.tasks == {}

    def test_study_with_plugins(self, tmp_path: Path) -> None:
        toml_content = dedent("""\
            [project]
            name = "my-study"
            type = "study"

            [plugins]
            lembas-reef3d = ">=0.1.0"
            lembas-planing = "==1.0.0"
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        manifest = LembasManifest.from_path(manifest_path)

        assert manifest.plugins == {
            "lembas-reef3d": ">=0.1.0",
            "lembas-planing": "==1.0.0",
        }

    def test_tasks_string_form(self, tmp_path: Path) -> None:
        toml_content = dedent("""\
            [project]
            name = "my-study"

            [tasks]
            run = "python run.py"
            test = "pytest tests/"
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        manifest = LembasManifest.from_path(manifest_path)

        assert manifest.tasks["run"].cmd == "python run.py"
        assert manifest.tasks["test"].cmd == "pytest tests/"

    def test_tasks_dict_form(self, tmp_path: Path) -> None:
        toml_content = dedent("""\
            [project]
            name = "my-study"

            [tasks.report]
            cmd = "python report.py"
            description = "Generate report"
            depends-on = ["run"]
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        manifest = LembasManifest.from_path(manifest_path)

        assert manifest.tasks["report"].cmd == "python report.py"
        assert manifest.tasks["report"].description == "Generate report"
        assert manifest.tasks["report"].depends_on == ["run"]

    def test_plugin_manifest(self, tmp_path: Path) -> None:
        toml_content = dedent("""\
            [project]
            name = "lembas-reef3d"
            type = "plugin"
            version = "0.3.1"
            publish-to = "my-org/solvers"

            [dependencies]
            python = ">=3.11"
            reef3d = "==2.3.0"

            [dev-dependencies]
            pytest = "*"

            [plugin]
            entry-point = "lembas_reef3d:Plugin"
            environment = "conda"
            handlers = ["Reef3DWaveCase"]
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        manifest = LembasManifest.from_path(manifest_path)

        assert manifest.project.type == "plugin"
        assert manifest.project.version == "0.3.1"
        assert manifest.project.publish_to == "my-org/solvers"
        assert manifest.dependencies == {"python": ">=3.11", "reef3d": "==2.3.0"}
        assert manifest.dev_dependencies == {"pytest": "*"}
        assert manifest.plugin is not None
        assert manifest.plugin.entry_point == "lembas_reef3d:Plugin"
        assert manifest.plugin.handlers == ["Reef3DWaveCase"]

    def test_platform_section(self, tmp_path: Path) -> None:
        toml_content = dedent("""\
            [project]
            name = "my-study"

            [platform]
            server = "https://lembas.example.com"
            project = "hull-design-2026"
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        manifest = LembasManifest.from_path(manifest_path)

        assert manifest.platform is not None
        assert manifest.platform.server == "https://lembas.example.com"
        assert manifest.platform.project == "hull-design-2026"

    def test_find_and_load_current_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toml_content = dedent("""\
            [project]
            name = "found-project"
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        monkeypatch.chdir(tmp_path)
        manifest, path = LembasManifest.find_and_load()

        assert manifest.project.name == "found-project"
        assert path == manifest_path

    def test_find_and_load_parent_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toml_content = dedent("""\
            [project]
            name = "parent-project"
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        subdir = tmp_path / "src" / "pkg"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        manifest, path = LembasManifest.find_and_load()

        assert manifest.project.name == "parent-project"
        assert path == manifest_path

    def test_find_and_load_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError, match="No lembas.toml found"):
            LembasManifest.find_and_load()

    def test_sections_hash_deterministic(self, tmp_path: Path) -> None:
        toml_content = dedent("""\
            [project]
            name = "my-study"

            [plugins]
            lembas-reef3d = ">=0.1.0"

            [tasks]
            run = "python run.py"
        """)
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(toml_content)

        manifest = LembasManifest.from_path(manifest_path)
        hash1 = manifest.sections_hash()
        hash2 = manifest.sections_hash()

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_sections_hash_changes_with_content(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "lembas.toml"

        manifest_path.write_text(
            dedent("""\
            [project]
            name = "my-study"
        """)
        )
        manifest1 = LembasManifest.from_path(manifest_path)
        hash1 = manifest1.sections_hash()

        manifest_path.write_text(
            dedent("""\
            [project]
            name = "my-study"

            [plugins]
            lembas-reef3d = ">=0.1.0"
        """)
        )
        manifest2 = LembasManifest.from_path(manifest_path)
        hash2 = manifest2.sections_hash()

        assert hash1 != hash2
