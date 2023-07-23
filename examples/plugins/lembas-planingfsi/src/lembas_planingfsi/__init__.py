from __future__ import annotations

from collections.abc import Iterator

from lembas import Case
from lembas.plugins import register

from lembas_planingfsi.filled_dam import HydrostaticDamCase
from lembas_planingfsi.flat_plate import PlaningPlateCase


@register
def lembas_case_handlers() -> Iterator[type[Case]]:
    yield PlaningPlateCase
    yield HydrostaticDamCase
