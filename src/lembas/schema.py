"""JSON Schema extraction for Case handlers.

Generates JSON Schema representations of Case handlers for the schema registry.
Schemas are content-addressed by fingerprint (SHA-256 of canonical JSON).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from lembas.case import Case

SCHEMA_VERSION = "v1"
SCHEMA_BASE_URL = "https://lembas.fly.dev/schemas"


def get_git_ref() -> dict[str, Any] | None:
    """Get git reference for current working directory.

    Returns:
        Dict with git_ref and dirty flag, or None if not in a git repo.
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        return {
            "git_ref": commit,
            "dirty": bool(status),
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _python_type_to_json_schema(python_type: type | None) -> dict[str, Any]:
    """Convert a Python type to JSON Schema type."""
    if python_type is None:
        return {"type": "string"}

    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }

    return type_map.get(python_type, {"type": "string"})


def extract_input_schema(case_cls: type[Case]) -> dict[str, Any]:
    """Extract JSON Schema for a Case handler's inputs.

    Returns a valid JSON Schema object for the inputs.
    """
    from lembas.param import InputParameter
    from lembas.param import _NoDefault

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, value in case_cls.__dict__.items():
        if isinstance(value, InputParameter):
            prop_schema = _python_type_to_json_schema(value._type)

            if value._min_value is not None:
                prop_schema["minimum"] = value._min_value
            if value._max_value is not None:
                prop_schema["maximum"] = value._max_value
            if value._default != _NoDefault:
                prop_schema["default"] = value._default
            if value._short_name:
                prop_schema["x-lembas-short-name"] = value._short_name

            properties[name] = prop_schema

            if value._default == _NoDefault:
                required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": sorted(required),
    }


def extract_result_schema(case_cls: type[Case]) -> dict[str, Any]:
    """Extract JSON Schema for a Case handler's results.

    Returns a valid JSON Schema object for the results.
    """
    properties: dict[str, Any] = {}

    for _method_name, method_func in case_cls.__dict__.items():
        provides = getattr(method_func, "_provides_results", None)
        if not provides:
            continue

        # Each name in provides is a result field
        for name in provides:
            # Default to number type for results
            # Could be enhanced to introspect return type annotations
            properties[name] = {
                "type": "number",
            }

    return {
        "type": "object",
        "properties": properties,
    }


def extract_steps_schema(case_cls: type[Case]) -> list[dict[str, Any]]:
    """Extract step definitions for a Case handler.

    Returns a list of step objects with name, requires, condition info, and order.
    Steps are returned in definition order, which is the implicit execution order
    when no explicit `requires=` dependencies are specified.
    """
    from lembas.case import CaseStep

    steps: list[dict[str, Any]] = []
    order = 0

    for name, value in case_cls.__dict__.items():
        if isinstance(value, CaseStep):
            step_info: dict[str, Any] = {
                "name": name,
                "requires": value.requires if value.requires else [],
                "order": order,
            }
            order += 1

            # Get docstring if available
            if value._func.__doc__:
                step_info["description"] = value._func.__doc__.strip().split("\n")[0]

            # Check if there's a condition (we can't serialize lambdas, but we can flag it)
            # The condition is stored as a callable, check if it's not the default "always true"
            if value._condition is not None:
                # Check if it's not the default lambda that always returns True
                # We do this by checking if the condition function is different from the default
                try:
                    # Try to detect if there's a real condition by checking if it's a closure
                    if hasattr(value._condition, "__closure__") and value._condition.__closure__:
                        step_info["has_condition"] = True
                except Exception:
                    pass

            steps.append(step_info)

    return steps


def extract_handler_schema(
    case_cls: type[Case],
    *,
    base_url: str = SCHEMA_BASE_URL,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract full JSON Schema for a Case handler.

    Args:
        case_cls: The Case subclass to extract schema from.
        base_url: Base URL for schema references.
        source: Source metadata (git_ref, plugin version, etc.)

    Returns:
        Complete JSON Schema with inputs, results, steps, and metadata.
    """
    inputs_schema = extract_input_schema(case_cls)
    results_schema = extract_result_schema(case_cls)
    steps_schema = extract_steps_schema(case_cls)

    # Build the schema without fingerprint first
    handler_name = case_cls.__name__

    # Get description from docstring
    description = None
    if case_cls.__doc__:
        description = case_cls.__doc__.strip().split("\n")[0]

    schema: dict[str, Any] = {
        "title": handler_name,
        "inputs": inputs_schema,
        "results": results_schema,
        "steps": steps_schema,
    }

    if description:
        schema["description"] = description

    # Compute fingerprint from canonical schema (without metadata)
    fingerprint = compute_fingerprint(schema)

    # Now build the full schema with all metadata
    full_schema: dict[str, Any] = {
        "$schema": f"{base_url}/case-handler/{SCHEMA_VERSION}",
        "$id": f"{base_url}/handlers/{handler_name}/{fingerprint}",
        "title": handler_name,
        "x-lembas-fingerprint": fingerprint,
    }

    if description:
        full_schema["description"] = description

    if source:
        full_schema["x-lembas-source"] = source

    full_schema["inputs"] = inputs_schema
    full_schema["results"] = results_schema
    full_schema["steps"] = steps_schema

    return full_schema


def compute_fingerprint(schema: dict[str, Any]) -> str:
    """Compute content-addressable fingerprint for a schema.

    Uses SHA-256 of canonical JSON (sorted keys, no whitespace).
    Returns first 16 hex characters.
    """
    # Only hash the semantic content (inputs + results + steps), not metadata
    content = {
        "title": schema.get("title"),
        "inputs": schema.get("inputs"),
        "results": schema.get("results"),
        "steps": schema.get("steps"),
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def extract_all_handler_schemas(
    case_classes: list[type[Case]],
    *,
    base_url: str = SCHEMA_BASE_URL,
) -> list[dict[str, Any]]:
    """Extract schemas from multiple Case handlers.

    Automatically detects git ref for local plugins.
    """
    source = get_git_ref()

    schemas = []
    for case_cls in case_classes:
        schema = extract_handler_schema(case_cls, base_url=base_url, source=source)
        schemas.append(schema)

    return schemas
