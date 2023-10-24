from __future__ import annotations

import weakref
from functools import cached_property
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import TypeVar

if TYPE_CHECKING:
    from lembas.case import Case


TCase = TypeVar("TCase", bound="Case")
RawCaseMethod = Callable[[TCase], Any]


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

    def __getattr__(self, item: str) -> Any:
        if item in self.__dict__:
            return self.__dict__[item]

        # During attribute access, we search the class for methods to which have been
        # attached a "_provides_results" tuple. If we find that, and the requested
        # result is in that tuple, we call the method (once) and cache the results in
        # the self.__dict__ for later, faster retrieval.
        cls = self.parent.__class__
        for method_name, method_func in cls.__dict__.items():
            try:
                provides_results = getattr(method_func, "_provides_results")
            except AttributeError:
                continue  # to next method

            provides_results = provides_results or tuple()
            if item not in provides_results:
                continue

            results = method_func(self.parent)
            if not isinstance(results, tuple):
                results = (results,)

            num_expected_results = len(provides_results)
            num_results = len(results)
            if num_expected_results != num_results:
                raise ValueError(
                    f"Results method {method_name} returns {num_results} items, "
                    f"only {num_expected_results} results are declared in the @result "
                    "decorator."
                )

            for n, r in zip(provides_results, results):
                setattr(self, n, r)

        try:
            return self.__dict__[item]
        except KeyError:
            raise AttributeError(f"Result '{item}' is not defined")


def result(
    *func_or_names: Callable[[TCase], Any] | str
) -> RawCaseMethod | Callable[[RawCaseMethod], RawCaseMethod]:
    """A decorator to annotate a method that provides result(s).

    The decorator accepts a variadic list of names for the provided result(s). The method
    can return a single object or a tuple of objects, which must map to the number of names
    provided. The results are then available from within other case handler methods like
    self.results.result_name.

    """

    if any(callable(fn) for fn in func_or_names):
        # This case captures the non-argument form, i.e. @result
        # In this case, there should only be one argument, which is
        # the decorated method.
        try:
            (method,) = func_or_names
        except ValueError:
            raise ValueError("Must only provide a single callable")
        names = (method.__name__,)  # type: ignore
        method._provides_results = names  # type: ignore
        return method  # type: ignore

    # We now handle the case with arguments, i.e. @result("name1", "name2")
    names = func_or_names  # type: ignore

    def decorator(m: RawCaseMethod) -> RawCaseMethod:
        # Here, we attach the tuple of names to the method function object. We have to do
        # this because we do not have access to the class object at the time when the
        # decorator is called. The actual discovery of the name mapping is performed
        # during attribute access on the case.results object, which does a search across
        # the methods attached to the class at runtime.
        m._provides_results = names  # type: ignore
        return m

    return decorator
