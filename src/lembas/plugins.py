from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module_from_path(mod_path: Path) -> ModuleType:
    """Load a module from a filesystem Path.

    Args:
        mod_path: A path to the `.py` file.

    Returns:
        The imported module object.

    """
    mod_name = mod_path.stem
    spec = importlib.util.spec_from_file_location(mod_name, mod_path)
    if spec is None:
        raise LookupError(f"Cannot load module {mod_path}")
    if spec.loader is None:
        raise ValueError(f"Invalid spec loader while loading {mod_path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod
