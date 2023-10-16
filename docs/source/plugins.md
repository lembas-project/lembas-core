# Writing a third-party plugin to provide case handlers


A case handler can be registered to `lembas` via the plugin mechanism.
An example package is provided in `examples/plugins/lembas-planingfsi`.

Assuming the case handler is defined as follows:

```python
from lembas import Case
from lembas import InputParameter


class MyPluginProvidedCase(Case):
    some_variable = InputParameter(type=float)
```

there are two ways to register.

Using `setuptools`, the following entry to `pyproject.toml` will define the `lembas_planingfsi` module as the location of the plugins.

```toml
[project.entry-points.lembas]
_ = "lembas_planingfsi"
```

First, as long as the case handler is imported in the namespace specified in the plugin, all subclasses of `Case` are automatically registered.

Alternately, a more explicit approach may be used:

```python
# contents of lembas_planingfsi.py

from collections.abc import Iterator

from lembas import Case
from lembas.plugins import register

from lembas_planingfsi.filled_dam import HydrostaticDamCase
from lembas_planingfsi.flat_plate import PlaningPlateCase


@register
def lembas_case_handlers() -> Iterator[type[Case]]:
    """Yield any number of case handler classes to be registered with lembas.

    As long as these are available in this module, and this module is the one listed in the `pyproject.toml`,
    they will be available to use by lembas.

    """
    yield PlaningPlateCase
    yield HydrostaticDamCase

```
