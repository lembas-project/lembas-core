from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lembas.case import Case


class Results:
    """A generic container for results of a case.

    Implements lazy loading of results, where the result accessors are specified by @result
    decorator.

    """

    def __init__(self, parent: Case):
        self._parent = parent

    @property
    def parent(self) -> Case:
        # TODO: Replace with a weakref to remove memory leak
        return self._parent
