from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType

from rich import print

from lembas import Case

registry: dict[str, type[Case]] = {}


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


def load_plugins_from_file(plugin_path: Path) -> None:
    """Load all defined plugins from a module from a filesystem Path.

    Args:
        plugin_path: A path to the `.py` file containing the `Case` subclasses.

    """

    print("Loading plugins")
    plugin_path = plugin_path.resolve()
    mod = _load_module_from_path(plugin_path)

    for name, obj in mod.__dict__.items():
        if inspect.isclass(obj):
            if issubclass(obj, Case) and obj != Case:
                registry[name] = obj
                print(f"Found [bold]{name}[/bold] in {plugin_path}")
