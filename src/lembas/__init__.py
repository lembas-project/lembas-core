from lembas._version import __version__
from lembas.case import Case
from lembas.case import CaseList
from lembas.case import step
from lembas.param import InputParameter
from lembas.plugins import load_plugins_from_file
from lembas.plugins import registry
from lembas.results import result

__all__ = [
    "Case",
    "CaseList",
    "InputParameter",
    "load_local_plugins",
    "load_plugins_from_file",
    "registry",
    "result",
    "step",
    "__version__",
]


def load_local_plugins() -> None:
    """Load local plugins defined in [local-plugins] section of lembas.toml.

    Call this at the start of run.py to load any plugins defined locally in the project.
    After calling, case handlers will be available in the registry.

    Example:
        from lembas import load_local_plugins, registry

        load_local_plugins()
        PlaningPlateCase = registry.get("PlaningPlateCase")
    """
    from pathlib import Path

    from lembas.manifest import load_lembas_manifest

    cwd = Path.cwd()
    try:
        manifest = load_lembas_manifest(cwd)
    except FileNotFoundError:
        return

    local_plugins = manifest.get("local-plugins", {})
    for _name, path_str in local_plugins.items():
        plugin_path = cwd / path_str
        if plugin_path.exists():
            load_plugins_from_file(plugin_path)
