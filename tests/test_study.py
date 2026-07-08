"""Tests for study.py - case loading from YAML files."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from lembas import Case
from lembas import InputParameter
from lembas.plugins import registry
from lembas.study import load_cases

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class DummyCase(Case):
    """Test case handler for study tests."""

    param_a = InputParameter(type=float)
    param_b = InputParameter(type=float, default=1.0)


@pytest.fixture(autouse=True)
def setup_registry() -> None:
    """Register the test case handler."""
    registry.clear()
    registry.add(DummyCase)


@pytest.fixture()
def tmp_project(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """Create a temporary project directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_load_cases_cartesian(tmp_project: Path) -> None:
    """Cartesian expansion creates product of all parameters."""
    cases_yaml = tmp_project / "cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: DummyCase
          expansion: cartesian
          parameters:
            param_a: [1.0, 2.0]
            param_b: [10.0, 20.0]
        """)
    )

    cases = load_cases(cases_yaml)

    assert len(cases) == 4
    params = [(c.param_a, c.param_b) for c in cases]  # type: ignore[attr-defined]
    assert (1.0, 10.0) in params
    assert (1.0, 20.0) in params
    assert (2.0, 10.0) in params
    assert (2.0, 20.0) in params


def test_load_cases_zip(tmp_project: Path) -> None:
    """Zip expansion pairs parameters by index."""
    cases_yaml = tmp_project / "cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: DummyCase
          expansion: zip
          parameters:
            param_a: [1.0, 2.0, 3.0]
            param_b: [10.0, 20.0, 30.0]
        """)
    )

    cases = load_cases(cases_yaml)

    assert len(cases) == 3
    params = [(c.param_a, c.param_b) for c in cases]  # type: ignore[attr-defined]
    assert params == [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)]


def test_load_cases_zip_mismatched_lengths(tmp_project: Path) -> None:
    """Zip expansion raises error if arrays have different lengths."""
    cases_yaml = tmp_project / "cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: DummyCase
          expansion: zip
          parameters:
            param_a: [1.0, 2.0]
            param_b: [10.0, 20.0, 30.0]
        """)
    )

    with pytest.raises(ValueError, match="same length"):
        load_cases(cases_yaml)


def test_load_cases_explicit(tmp_project: Path) -> None:
    """Explicit expansion creates a single case with scalar values."""
    cases_yaml = tmp_project / "cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: DummyCase
          expansion: explicit
          parameters:
            param_a: 1.5
            param_b: 2.5
        """)
    )

    cases = load_cases(cases_yaml)

    assert len(cases) == 1
    assert cases._cases[0].param_a == 1.5  # type: ignore[attr-defined]
    assert cases._cases[0].param_b == 2.5  # type: ignore[attr-defined]


def test_load_cases_multiple_definitions(tmp_project: Path) -> None:
    """Multiple case definitions are combined."""
    cases_yaml = tmp_project / "cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: DummyCase
          expansion: cartesian
          parameters:
            param_a: [1.0, 2.0]
            param_b: [10.0]

        - handler: DummyCase
          expansion: explicit
          parameters:
            param_a: 99.0
        """)
    )

    cases = load_cases(cases_yaml)

    assert len(cases) == 3  # 2 from cartesian + 1 from explicit


def test_load_cases_from_manifest(tmp_project: Path) -> None:
    """Load cases via lembas.toml reference."""
    lembas_toml = tmp_project / "lembas.toml"
    lembas_toml.write_text(
        dedent("""\
        [project]
        name = "test"
        type = "study"

        [study]
        cases = "my_cases.yaml"
        """)
    )

    cases_yaml = tmp_project / "my_cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: DummyCase
          parameters:
            param_a: [1.0, 2.0]
        """)
    )

    cases = load_cases()

    assert len(cases) == 2


def test_load_cases_default_expansion_is_cartesian(tmp_project: Path) -> None:
    """Default expansion strategy is cartesian."""
    cases_yaml = tmp_project / "cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: DummyCase
          parameters:
            param_a: [1.0, 2.0]
            param_b: [10.0, 20.0]
        """)
    )

    cases = load_cases(cases_yaml)

    assert len(cases) == 4  # Cartesian product


def test_load_cases_unknown_expansion(tmp_project: Path) -> None:
    """Unknown expansion strategy raises error."""
    cases_yaml = tmp_project / "cases.yaml"
    cases_yaml.write_text(
        dedent("""\
        - handler: DummyCase
          expansion: unknown
          parameters:
            param_a: [1.0]
        """)
    )

    with pytest.raises(ValueError, match="Unknown expansion strategy"):
        load_cases(cases_yaml)
