"""Tests for case directory convention: case.id, case_dir, index file handling."""

from __future__ import annotations

import json
from pathlib import Path

import toml

from lembas import Case
from lembas import InputParameter
from lembas.index import compute_case_id
from lembas.index import get_case_dir_from_index
from lembas.index import load_case_index
from lembas.index import reindex_cases
from lembas.index import save_case_index
from lembas.index import update_case_index


class SimpleCase(Case):
    """A simple case with two parameters."""

    alpha = InputParameter(type=float)
    beta = InputParameter(type=int)


class CaseWithShortNames(Case):
    """A case with short names for directory paths."""

    froude_number = InputParameter(type=float, short_name="Fr")
    angle_of_attack = InputParameter(type=float, short_name="AOA")


class CaseWithPathFormat(Case):
    """A case with custom path formatting."""

    value = InputParameter(type=float, path_format=".2f")
    count = InputParameter(type=int, path_format="03d")


class CaseWithManyParams(Case):
    """A case with more than 3 parameters to test nesting depth limit."""

    param_a = InputParameter(type=float)
    param_b = InputParameter(type=float)
    param_c = InputParameter(type=float)
    param_d = InputParameter(type=float)
    param_e = InputParameter(type=float)


class CaseWithControl(Case):
    """A case with a control parameter (excluded from inputs)."""

    value = InputParameter(type=float)
    debug = InputParameter(default=False, control=True)


class TestInputParameterPathFormatting:
    """Tests for InputParameter path_format and short_name."""

    def test_path_name_uses_short_name(self) -> None:
        param = InputParameter(type=float, short_name="Fr")
        param._name = "froude_number"
        assert param.path_name == "Fr"

    def test_path_name_uses_full_name_when_no_short_name(self) -> None:
        param = InputParameter(type=float)
        param._name = "froude_number"
        assert param.path_name == "froude_number"

    def test_format_for_path_uses_custom_format(self) -> None:
        param = InputParameter(type=float, path_format=".2f")
        param._name = "value"
        assert param.format_for_path(3.14159) == "3.14"

    def test_format_for_path_default_float_uses_6g(self) -> None:
        param = InputParameter(type=float)
        param._name = "value"
        assert param.format_for_path(3.14159265) == "3.14159"
        assert param.format_for_path(0.5) == "0.5"
        assert param.format_for_path(1000000.0) == "1e+06"

    def test_format_for_path_int_uses_str(self) -> None:
        param = InputParameter(type=int)
        param._name = "count"
        assert param.format_for_path(42) == "42"

    def test_format_for_path_string_uses_str(self) -> None:
        param = InputParameter(type=str)
        param._name = "name"
        assert param.format_for_path("hello") == "hello"

    def test_format_for_path_int_with_custom_format(self) -> None:
        param = InputParameter(type=int, path_format="05d")
        param._name = "count"
        assert param.format_for_path(42) == "00042"


class TestCaseId:
    """Tests for case.id generation."""

    def test_id_is_full_sha256(self) -> None:
        case = SimpleCase(alpha=1.0, beta=2)
        assert len(case.id) == 64
        assert all(c in "0123456789abcdef" for c in case.id)

    def test_short_id_is_8_chars(self) -> None:
        case = SimpleCase(alpha=1.0, beta=2)
        assert len(case.short_id) == 8
        assert case.short_id == case.id[:8]

    def test_id_is_deterministic(self) -> None:
        case1 = SimpleCase(alpha=1.0, beta=2)
        case2 = SimpleCase(alpha=1.0, beta=2)
        assert case1.id == case2.id

    def test_id_differs_for_different_inputs(self) -> None:
        case1 = SimpleCase(alpha=1.0, beta=2)
        case2 = SimpleCase(alpha=1.0, beta=3)
        assert case1.id != case2.id

    def test_id_is_alphabetically_sorted(self) -> None:
        # Create cases with params in different order but same values
        case1 = SimpleCase(alpha=1.0, beta=2)
        case2 = SimpleCase(beta=2, alpha=1.0)
        # Both should produce the same id because inputs are sorted alphabetically
        assert case1.id == case2.id

    def test_id_excludes_control_params(self) -> None:
        case1 = CaseWithControl(value=1.0)
        case2 = CaseWithControl(value=1.0, debug=True)
        # Control params are excluded from inputs, so id should be the same
        assert case1.id == case2.id


class TestCaseDir:
    """Tests for default case_dir generation."""

    def test_case_dir_nests_by_declaration_order(self) -> None:
        case = SimpleCase(alpha=1.5, beta=10)
        # Should use declaration order: alpha, beta
        expected_suffix = Path("cases") / "alpha=1.5" / "beta=10"
        assert case.case_dir.parts[-3:] == expected_suffix.parts

    def test_case_dir_uses_short_names(self) -> None:
        case = CaseWithShortNames(froude_number=0.5, angle_of_attack=5.0)
        expected_suffix = Path("cases") / "Fr=0.5" / "AOA=5"
        assert case.case_dir.parts[-3:] == expected_suffix.parts

    def test_case_dir_uses_path_format(self) -> None:
        case = CaseWithPathFormat(value=3.14159, count=7)
        expected_suffix = Path("cases") / "value=3.14" / "count=007"
        assert case.case_dir.parts[-3:] == expected_suffix.parts

    def test_case_dir_limits_nesting_to_3_params(self) -> None:
        case = CaseWithManyParams(param_a=1.0, param_b=2.0, param_c=3.0, param_d=4.0, param_e=5.0)
        # Only first 3 params should be in path
        expected_suffix = Path("cases") / "param_a=1" / "param_b=2" / "param_c=3"
        assert case.case_dir.parts[-4:] == expected_suffix.parts

    def test_case_dir_excludes_control_params(self) -> None:
        case = CaseWithControl(value=1.5, debug=True)
        # Only non-control param should be in path
        expected_suffix = Path("cases") / "value=1.5"
        assert case.case_dir.parts[-2:] == expected_suffix.parts

    def test_case_dir_is_absolute(self) -> None:
        case = SimpleCase(alpha=1.0, beta=2)
        assert case.case_dir.is_absolute()

    def test_relative_case_dir_is_relative(self) -> None:
        case = SimpleCase(alpha=1.0, beta=2)
        # Default case_dir is under cwd, so relative_case_dir should be relative
        assert not case.relative_case_dir.is_absolute()
        assert case.relative_case_dir.parts[0] == "cases"


class TestCaseIndex:
    """Tests for case index file handling."""

    def test_load_empty_index(self, tmp_path: Path) -> None:
        index = load_case_index(tmp_path)
        assert index == {}

    def test_save_and_load_index(self, tmp_path: Path) -> None:
        index = {
            "abc123": {
                "path": "cases/alpha=1/beta=2",
                "handler": "Case1",
                "all_paths": ["cases/alpha=1/beta=2"],
            },
            "def456": {
                "path": "cases/alpha=3/beta=4",
                "handler": "Case2",
                "all_paths": ["cases/alpha=3/beta=4"],
            },
        }
        save_case_index(index, tmp_path)

        loaded = load_case_index(tmp_path)
        assert loaded == index

    def test_save_creates_lembas_dir(self, tmp_path: Path) -> None:
        index = {"abc123": {"path": "cases/test", "handler": "Case", "all_paths": ["cases/test"]}}
        save_case_index(index, tmp_path)
        assert (tmp_path / ".lembas").exists()
        assert (tmp_path / ".lembas" / "cases.json").exists()

    def test_update_case_index(self, tmp_path: Path) -> None:
        # Start with empty index
        update_case_index("abc123", tmp_path / "cases" / "test1", "Handler1", tmp_path)
        update_case_index("def456", tmp_path / "cases" / "test2", "Handler2", tmp_path)

        index = load_case_index(tmp_path)
        assert index["abc123"]["path"] == "cases/test1"
        assert index["abc123"]["handler"] == "Handler1"
        assert index["def456"]["path"] == "cases/test2"
        assert index["def456"]["handler"] == "Handler2"

    def test_get_case_dir_from_index_found(self, tmp_path: Path) -> None:
        # Create a case directory
        case_dir = tmp_path / "cases" / "test"
        case_dir.mkdir(parents=True)

        save_case_index(
            {"abc123": {"path": "cases/test", "handler": "Case", "all_paths": ["cases/test"]}},
            tmp_path,
        )

        result = get_case_dir_from_index("abc123", tmp_path)
        assert result == case_dir

    def test_get_case_dir_from_index_not_found(self, tmp_path: Path) -> None:
        result = get_case_dir_from_index("nonexistent", tmp_path)
        assert result is None

    def test_get_case_dir_from_index_missing_directory(self, tmp_path: Path) -> None:
        # Index points to non-existent directory
        save_case_index(
            {
                "abc123": {
                    "path": "cases/missing",
                    "handler": "Case",
                    "all_paths": ["cases/missing"],
                }
            },
            tmp_path,
        )

        result = get_case_dir_from_index("abc123", tmp_path)
        assert result is None


class TestComputeCaseId:
    """Tests for compute_case_id function."""

    def test_compute_case_id_matches_case_property(self) -> None:
        case = SimpleCase(alpha=1.0, beta=2)
        computed = compute_case_id(case.fully_resolved_name, case.inputs)
        assert computed == case.id

    def test_compute_case_id_alphabetical_order(self) -> None:
        # Order of keys in inputs dict shouldn't matter
        id1 = compute_case_id("test.Case", {"alpha": 1.0, "beta": 2})
        id2 = compute_case_id("test.Case", {"beta": 2, "alpha": 1.0})
        assert id1 == id2


class TestReindexCases:
    """Tests for reindex_cases function."""

    def test_reindex_empty_directory(self, tmp_path: Path) -> None:
        index = reindex_cases(tmp_path / "cases", tmp_path)
        assert index == {}

    def test_reindex_finds_case_toml_files(self, tmp_path: Path) -> None:
        # Create a case directory with case.toml
        case_dir = tmp_path / "cases" / "alpha=1" / "beta=2"
        lembas_dir = case_dir / "lembas"
        lembas_dir.mkdir(parents=True)

        case_toml = lembas_dir / "case.toml"
        case_toml.write_text(
            toml.dumps(
                {
                    "lembas": {
                        "case-handler": "test.SimpleCase",
                        "inputs": {"alpha": 1.0, "beta": 2},
                    }
                }
            )
        )

        index = reindex_cases(tmp_path / "cases", tmp_path)

        expected_id = compute_case_id("test.SimpleCase", {"alpha": 1.0, "beta": 2})
        assert expected_id in index
        assert index[expected_id]["path"] == "cases/alpha=1/beta=2"
        assert index[expected_id]["handler"] == "SimpleCase"

    def test_reindex_multiple_cases(self, tmp_path: Path) -> None:
        # Create multiple case directories
        for i in range(3):
            case_dir = tmp_path / "cases" / f"value={i}"
            lembas_dir = case_dir / "lembas"
            lembas_dir.mkdir(parents=True)

            case_toml = lembas_dir / "case.toml"
            case_toml.write_text(
                toml.dumps(
                    {
                        "lembas": {
                            "case-handler": "test.Case",
                            "inputs": {"value": i},
                        }
                    }
                )
            )

        index = reindex_cases(tmp_path / "cases", tmp_path)
        assert len(index) == 3

    def test_reindex_skips_invalid_toml(self, tmp_path: Path) -> None:
        # Create a case with invalid toml
        case_dir = tmp_path / "cases" / "bad"
        lembas_dir = case_dir / "lembas"
        lembas_dir.mkdir(parents=True)

        case_toml = lembas_dir / "case.toml"
        case_toml.write_text("not valid toml [[[")

        # Create a valid case too
        good_dir = tmp_path / "cases" / "good"
        good_lembas = good_dir / "lembas"
        good_lembas.mkdir(parents=True)
        good_toml = good_lembas / "case.toml"
        good_toml.write_text(
            toml.dumps(
                {
                    "lembas": {
                        "case-handler": "test.Case",
                        "inputs": {"value": 1},
                    }
                }
            )
        )

        index = reindex_cases(tmp_path / "cases", tmp_path)
        # Should only have the good case
        assert len(index) == 1

    def test_reindex_saves_index_file(self, tmp_path: Path) -> None:
        # Create a case
        case_dir = tmp_path / "cases" / "test"
        lembas_dir = case_dir / "lembas"
        lembas_dir.mkdir(parents=True)

        case_toml = lembas_dir / "case.toml"
        case_toml.write_text(
            toml.dumps(
                {
                    "lembas": {
                        "case-handler": "test.Case",
                        "inputs": {"value": 1},
                    }
                }
            )
        )

        reindex_cases(tmp_path / "cases", tmp_path)

        # Index file should be created
        index_file = tmp_path / ".lembas" / "cases.json"
        assert index_file.exists()

        # And contain the case
        saved_index = json.loads(index_file.read_text())
        assert len(saved_index) == 1
