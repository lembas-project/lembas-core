"""Tests for JSON Schema extraction from Case handlers."""

from __future__ import annotations

import json

from lembas import Case
from lembas import InputParameter
from lembas import step
from lembas.results import result
from lembas.schema import compute_fingerprint
from lembas.schema import extract_handler_schema
from lembas.schema import extract_input_schema
from lembas.schema import extract_result_schema
from lembas.schema import extract_steps_schema


class SimpleCase(Case):
    """A simple case for testing schema extraction."""

    velocity: float = InputParameter(type=float, min=0.0, max=100.0)
    angle: float = InputParameter(type=float, default=45.0)
    name: str = InputParameter(type=str, default="test")
    count: int = InputParameter(type=int, default=1)
    enabled: bool = InputParameter(type=bool, default=True)

    @step
    def prepare(self) -> None:
        """Prepare the simulation."""
        pass

    @step(requires="prepare")
    def solve(self) -> None:
        """Run the solver."""
        pass

    @step(requires="solve")
    def post_process(self) -> None:
        pass

    @result("force", "moment")
    def compute_loads(self) -> tuple[float, float]:
        return 1.0, 2.0


class TestExtractInputSchema:
    def test_extracts_all_parameters(self) -> None:
        schema = extract_input_schema(SimpleCase)
        assert schema["type"] == "object"
        assert set(schema["properties"].keys()) == {
            "velocity",
            "angle",
            "name",
            "count",
            "enabled",
        }

    def test_required_parameters(self) -> None:
        schema = extract_input_schema(SimpleCase)
        assert schema["required"] == ["velocity"]

    def test_float_parameter_schema(self) -> None:
        schema = extract_input_schema(SimpleCase)
        velocity = schema["properties"]["velocity"]
        assert velocity["type"] == "number"
        assert velocity["minimum"] == 0.0
        assert velocity["maximum"] == 100.0
        assert "default" not in velocity

    def test_float_with_default_schema(self) -> None:
        schema = extract_input_schema(SimpleCase)
        angle = schema["properties"]["angle"]
        assert angle["type"] == "number"
        assert angle["default"] == 45.0

    def test_string_parameter_schema(self) -> None:
        schema = extract_input_schema(SimpleCase)
        name = schema["properties"]["name"]
        assert name["type"] == "string"
        assert name["default"] == "test"

    def test_int_parameter_schema(self) -> None:
        schema = extract_input_schema(SimpleCase)
        count = schema["properties"]["count"]
        assert count["type"] == "integer"
        assert count["default"] == 1

    def test_bool_parameter_schema(self) -> None:
        schema = extract_input_schema(SimpleCase)
        enabled = schema["properties"]["enabled"]
        assert enabled["type"] == "boolean"
        assert enabled["default"] is True


class TestExtractResultSchema:
    def test_extracts_result_fields(self) -> None:
        schema = extract_result_schema(SimpleCase)
        assert schema["type"] == "object"
        assert "force" in schema["properties"]
        assert "moment" in schema["properties"]

    def test_result_default_type(self) -> None:
        schema = extract_result_schema(SimpleCase)
        assert schema["properties"]["force"]["type"] == "number"
        assert schema["properties"]["moment"]["type"] == "number"


class TestExtractStepsSchema:
    def test_extracts_all_steps(self) -> None:
        steps = extract_steps_schema(SimpleCase)
        step_names = {s["name"] for s in steps}
        assert step_names == {"prepare", "solve", "post_process"}

    def test_step_requires(self) -> None:
        steps = extract_steps_schema(SimpleCase)
        steps_by_name = {s["name"]: s for s in steps}

        assert steps_by_name["prepare"]["requires"] == []
        assert steps_by_name["solve"]["requires"] == ["prepare"]
        assert steps_by_name["post_process"]["requires"] == ["solve"]

    def test_step_description_from_docstring(self) -> None:
        steps = extract_steps_schema(SimpleCase)
        steps_by_name = {s["name"]: s for s in steps}

        assert steps_by_name["prepare"]["description"] == "Prepare the simulation."
        assert steps_by_name["solve"]["description"] == "Run the solver."
        assert "description" not in steps_by_name["post_process"]


class TestExtractHandlerSchema:
    def test_full_schema_structure(self) -> None:
        schema = extract_handler_schema(SimpleCase)

        assert "$schema" in schema
        assert "$id" in schema
        assert schema["title"] == "SimpleCase"
        assert schema["description"] == "A simple case for testing schema extraction."
        assert "x-lembas-fingerprint" in schema
        assert "inputs" in schema
        assert "results" in schema
        assert "steps" in schema

    def test_schema_id_contains_fingerprint(self) -> None:
        schema = extract_handler_schema(SimpleCase)
        fingerprint = schema["x-lembas-fingerprint"]
        assert fingerprint in schema["$id"]

    def test_custom_base_url(self) -> None:
        schema = extract_handler_schema(SimpleCase, base_url="https://example.com")
        assert schema["$schema"].startswith("https://example.com")
        assert schema["$id"].startswith("https://example.com")

    def test_source_metadata(self) -> None:
        source = {"git_ref": "abc123", "dirty": False}
        schema = extract_handler_schema(SimpleCase, source=source)
        assert schema["x-lembas-source"] == source


class TestComputeFingerprint:
    def test_fingerprint_is_16_hex_chars(self) -> None:
        schema = extract_handler_schema(SimpleCase)
        fingerprint = schema["x-lembas-fingerprint"]
        assert len(fingerprint) == 16
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_fingerprint_is_deterministic(self) -> None:
        fp1 = compute_fingerprint(extract_handler_schema(SimpleCase))
        fp2 = compute_fingerprint(extract_handler_schema(SimpleCase))
        assert fp1 == fp2

    def test_fingerprint_changes_with_schema(self) -> None:
        class AnotherCase(Case):
            x: float = InputParameter(type=float)

        fp1 = compute_fingerprint(extract_handler_schema(SimpleCase))
        fp2 = compute_fingerprint(extract_handler_schema(AnotherCase))
        assert fp1 != fp2

    def test_fingerprint_ignores_metadata(self) -> None:
        schema1 = extract_handler_schema(SimpleCase, source={"git_ref": "abc"})
        schema2 = extract_handler_schema(SimpleCase, source={"git_ref": "xyz"})
        assert schema1["x-lembas-fingerprint"] == schema2["x-lembas-fingerprint"]


class TestSchemaJsonSerialization:
    def test_schema_is_json_serializable(self) -> None:
        schema = extract_handler_schema(SimpleCase)
        json_str = json.dumps(schema)
        roundtrip = json.loads(json_str)
        assert roundtrip == schema
