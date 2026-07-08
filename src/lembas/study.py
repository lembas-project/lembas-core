"""Study configuration and case loading from YAML files."""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import yaml

from lembas.case import CaseList
from lembas.manifest import get_lembas_manifest_path
from lembas.manifest import load_lembas_manifest
from lembas.plugins import registry

if TYPE_CHECKING:
    from lembas.case import Case

__all__ = ["load_cases"]


def load_cases(
    cases_path: Path | str | None = None,
    project_root: Path | None = None,
) -> CaseList[Case]:
    """Load case definitions from a YAML file.

    If no path is provided, reads `[study].cases` from lembas.toml to find the cases file.

    Args:
        cases_path: Path to a YAML file containing case definitions. If None, reads
            from lembas.toml's [study].cases setting.
        project_root: Project root directory containing lembas.toml. Defaults to cwd.

    Returns:
        A CaseList populated with the case instances.

    The YAML file should contain a list of case definitions:

    ```yaml
    - handler: PlaningPlateCase
      expansion: cartesian
      parameters:
        froude_num: [0.5, 1.0, 1.5, 2.0]
        angle_of_attack: [5.0, 7.5, 10.0]

    - handler: AnotherCase
      expansion: zip
      parameters:
        param_a: [1, 2, 3]
        param_b: [4, 5, 6]
    ```

    Expansion strategies:
    - "cartesian": Cartesian product of all parameter arrays (default)
    - "zip": Pair parameters by index (all arrays must have same length)
    - "explicit": Single case with scalar parameter values

    """
    if cases_path is None:
        manifest_path = get_lembas_manifest_path(project_root)
        manifest = load_lembas_manifest(project_root)
        study_config = manifest.get("study", {})
        cases_file = study_config.get("cases")

        if cases_file is None:
            return CaseList()

        resolved_path = manifest_path.parent / cases_file
    else:
        resolved_path = Path(cases_path)

    with resolved_path.open() as f:
        cases_config = yaml.safe_load(f) or []

    return _expand_cases(cases_config)


def _expand_cases(cases_config: list[dict[str, Any]]) -> CaseList[Case]:
    """Expand case definitions into a CaseList."""
    cases: CaseList[Case] = CaseList()

    for case_def in cases_config:
        handler_name = case_def["handler"]
        expansion = case_def.get("expansion", "cartesian")
        parameters = case_def.get("parameters", {})

        handler_cls = registry.get(handler_name)

        if expansion == "cartesian":
            _expand_cartesian(cases, handler_cls, parameters)
        elif expansion == "zip":
            _expand_zip(cases, handler_cls, parameters)
        elif expansion == "explicit":
            cases.add(handler_cls(**parameters))
        else:
            raise ValueError(f"Unknown expansion strategy: {expansion}")

    return cases


def _expand_cartesian(
    cases: CaseList[Case],
    handler_cls: type[Case],
    parameters: dict[str, Any],
) -> None:
    """Expand parameters using Cartesian product."""
    param_names = list(parameters.keys())
    param_values = [v if isinstance(v, list) else [v] for v in parameters.values()]

    for combo in product(*param_values):
        params = dict(zip(param_names, combo, strict=True))
        cases.add(handler_cls(**params))


def _expand_zip(
    cases: CaseList[Case],
    handler_cls: type[Case],
    parameters: dict[str, Any],
) -> None:
    """Expand parameters by zipping arrays together."""
    param_names = list(parameters.keys())
    param_values = list(parameters.values())
    lengths = [len(v) if isinstance(v, list) else 1 for v in param_values]

    if len(set(lengths)) > 1:
        raise ValueError(
            f"All parameter arrays must have same length for 'zip' expansion. "
            f"Got lengths: {dict(zip(param_names, lengths, strict=True))}"
        )

    param_values = [v if isinstance(v, list) else [v] for v in param_values]
    for values in zip(*param_values, strict=True):
        params = dict(zip(param_names, values, strict=True))
        cases.add(handler_cls(**params))
