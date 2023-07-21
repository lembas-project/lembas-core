from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType

from rich import print

from lembas import Case


class CaseHandlerNotFound(AttributeError):
    pass


class CaseHandlerRegistry:
    """The case handler registry contains all registered case handlers, which are provided by plugins."""

    def __init__(self) -> None:
        self._registry: dict[str, type[Case]] = {}

    def add(self, cls: type[Case]) -> None:
        """Add a new class to the case handler registry."""
        # FIXME: There is no de-duplication by path, so case handlers with the same class
        #       name will clobber each other.
        self._registry[cls.__name__] = cls

    def get(self, name: str) -> type[Case]:
        """Retrieve a case handler by name from the registry.

        Args:
            name: The name of the case handler class.

        """
        try:
            return self._registry[name]
        except KeyError:
            raise CaseHandlerNotFound(
                f"Could not find [bold]{name}[/bold] in the case handler registry"
            )

    def clear(self) -> None:
        """Clear the case handler registry."""
        self._registry.clear()


registry = CaseHandlerRegistry()


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
                registry.add(obj)
                print(f"Found [bold]{name}[/bold] in {plugin_path}")
