from __future__ import annotations

import weakref
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lembas.case import Case


class Results:
    """A generic container for results of a case.

    Implements lazy loading of results, where the result accessors are specified by @result
    decorator.

    """

    def __init__(self, parent: Case):
        self._parent = weakref.ref(parent)

    @cached_property
    def parent(self) -> Case:
        """A reference to the parent case with which these results are associated."""
        parent = self._parent()
        if parent is None:
            raise ValueError(
                "The parent has been de-referenced. This shouldn't happen."
            )
        return parent
