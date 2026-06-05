"""Tests for pixi.toml synthesis from lembas.toml."""

from pathlib import Path
from textwrap import dedent

import tomlkit

from lembas.manifest import LembasManifest
from lembas.synthesis import LEMBAS_DIR
from lembas.synthesis import PIXI_TOML_NAME
from lembas.synthesis import is_synthesis_stale
from lembas.synthesis import synthesize_pixi_toml


def create_manifest(tmp_path: Path, content: str) -> tuple[LembasManifest, Path]:
    """Helper to create a lembas.toml and load it."""
    manifest_path = tmp_path / "lembas.toml"
    manifest_path.write_text(dedent(content))
    manifest = LembasManifest.from_path(manifest_path)
    return manifest, tmp_path


class TestSynthesizePixiToml:
    def test_minimal_study(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            channels = ["conda-forge"]
            platforms = ["linux-64", "osx-arm64"]
            """,
        )

        pixi_path = synthesize_pixi_toml(manifest, project_root)

        assert pixi_path == tmp_path / LEMBAS_DIR / PIXI_TOML_NAME
        assert pixi_path.exists()

        content = pixi_path.read_text()
        assert "lembas-hash:" in content
        assert "Auto-generated" in content

        doc = tomlkit.loads(content)
        assert doc["workspace"]["name"] == "my-study"
        assert doc["workspace"]["channels"] == ["conda-forge"]
        assert doc["workspace"]["platforms"] == ["linux-64", "osx-arm64"]

    def test_with_dependencies(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"

            [dependencies]
            python = ">=3.11"
            numpy = ">=1.24"

            [dev-dependencies]
            pytest = "*"
            """,
        )

        pixi_path = synthesize_pixi_toml(manifest, project_root)
        doc = tomlkit.loads(pixi_path.read_text())

        # All deps merged together, sorted alphabetically
        assert "numpy" in doc["dependencies"]
        assert "python" in doc["dependencies"]
        assert "pytest" in doc["dependencies"]

    def test_with_plugins(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"

            [plugins]
            lembas-reef3d = ">=0.1.0"
            """,
        )

        pixi_path = synthesize_pixi_toml(manifest, project_root)
        doc = tomlkit.loads(pixi_path.read_text())

        # Plugins become dependencies
        assert doc["dependencies"]["lembas-reef3d"] == ">=0.1.0"

    def test_with_tasks(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"

            [tasks]
            run = "python run.py"
            test = "pytest tests/"
            """,
        )

        pixi_path = synthesize_pixi_toml(manifest, project_root)
        doc = tomlkit.loads(pixi_path.read_text())

        assert doc["tasks"]["run"] == "python run.py"
        assert doc["tasks"]["test"] == "pytest tests/"

    def test_task_with_depends_on(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"

            [tasks]
            run = "python run.py"

            [tasks.report]
            cmd = "python report.py"
            depends-on = ["run"]
            """,
        )

        pixi_path = synthesize_pixi_toml(manifest, project_root)
        doc = tomlkit.loads(pixi_path.read_text())

        assert doc["tasks"]["run"] == "python run.py"
        assert doc["tasks"]["report"]["cmd"] == "python report.py"
        assert doc["tasks"]["report"]["depends-on"] == ["run"]

    def test_channel_expansion(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            channels = ["conda-forge", "my-org/plugins"]

            [platform]
            server = "https://lembas.example.com"
            """,
        )

        pixi_path = synthesize_pixi_toml(manifest, project_root)
        doc = tomlkit.loads(pixi_path.read_text())

        channels = doc["workspace"]["channels"]
        assert channels[0] == "conda-forge"
        assert channels[1] == "https://lembas.example.com/channels/my-org/plugins"

    def test_channel_no_server(self, tmp_path: Path) -> None:
        """Channel shorthand without server stays as-is."""
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            channels = ["conda-forge", "my-org/plugins"]
            """,
        )

        pixi_path = synthesize_pixi_toml(manifest, project_root)
        doc = tomlkit.loads(pixi_path.read_text())

        channels = doc["workspace"]["channels"]
        assert channels[1] == "my-org/plugins"  # Not expanded

    def test_creates_lembas_dir(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            """,
        )

        lembas_dir = tmp_path / LEMBAS_DIR
        assert not lembas_dir.exists()

        synthesize_pixi_toml(manifest, project_root)

        assert lembas_dir.exists()
        assert (lembas_dir / PIXI_TOML_NAME).exists()
        assert (lembas_dir / ".gitignore").exists()

    def test_gitignore_content(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            """,
        )

        synthesize_pixi_toml(manifest, project_root)

        gitignore = (tmp_path / LEMBAS_DIR / ".gitignore").read_text()
        assert "*" in gitignore


class TestIsSynthesisStale:
    def test_no_pixi_toml(self, tmp_path: Path) -> None:
        manifest, _ = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            """,
        )

        lembas_dir = tmp_path / LEMBAS_DIR
        lembas_dir.mkdir()

        assert is_synthesis_stale(manifest, lembas_dir) is True

    def test_pixi_toml_no_hash(self, tmp_path: Path) -> None:
        manifest, _ = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            """,
        )

        lembas_dir = tmp_path / LEMBAS_DIR
        lembas_dir.mkdir()
        (lembas_dir / PIXI_TOML_NAME).write_text("[workspace]\nname = 'test'\n")

        assert is_synthesis_stale(manifest, lembas_dir) is True

    def test_pixi_toml_matching_hash(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            """,
        )

        # Generate pixi.toml with correct hash
        synthesize_pixi_toml(manifest, project_root)
        lembas_dir = project_root / LEMBAS_DIR

        assert is_synthesis_stale(manifest, lembas_dir) is False

    def test_pixi_toml_stale_hash(self, tmp_path: Path) -> None:
        manifest, project_root = create_manifest(
            tmp_path,
            """\
            [project]
            name = "my-study"
            """,
        )

        # Generate pixi.toml
        synthesize_pixi_toml(manifest, project_root)
        lembas_dir = project_root / LEMBAS_DIR

        # Modify manifest
        manifest_path = tmp_path / "lembas.toml"
        manifest_path.write_text(
            dedent("""\
            [project]
            name = "my-study"

            [plugins]
            lembas-reef3d = ">=0.1.0"
        """)
        )
        new_manifest = LembasManifest.from_path(manifest_path)

        assert is_synthesis_stale(new_manifest, lembas_dir) is True
