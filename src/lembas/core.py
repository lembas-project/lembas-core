from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


class _NoDefault:
    """Used as a sentinel to indicate lack of a default value for an `InputAttribute`."""


_builtin_type = type


class InputParameter:
    _name: str
    _type: type | None
    _min_value: float | None
    _max_value: float | None

    def __init__(
        self,
        *,
        type: type | None = None,
        default: Any = _NoDefault,
        min: float | None = None,
        max: float | None = None,
    ):
        if type is not None:
            self._type = type
        elif default != _NoDefault:
            self._type = _builtin_type(default)
        else:
            raise TypeError(
                "An 'InputParameter' must either explicitly set the type, or have a default value to infer it from."
            )

        self._default = default
        self._min_value = min
        self._max_value = max

    def __set_name__(self, owner: type[Case], name: str) -> None:
        self._name = name

    def __set__(self, instance: object, value: Any) -> None:
        if self._type is not None:
            value = self._type(value)

        if self._min_value is not None and value < self._min_value:
            raise ValueError(
                "Specified value less than minimum for attribute "
                f"'{self._name}': ({value} < {self._min_value})"
            )

        if self._max_value is not None and value > self._max_value:
            raise ValueError(
                "Specified value exceeds maximum for attribute "
                f"'{self._name}': ({value} > {self._max_value})"
            )

        instance.__dict__[self._name] = value

    def __get__(self, instance: Case, owner: type[Case]) -> Any:
        """Retrieve the attribute from the instance dictionary.

        If the value hasn't been set, we attempt to return a default, unless there is no default,
        in which case we raise an AttributeError.

        """
        try:
            return instance.__dict__[self._name]
        except KeyError:
            if self._default == _NoDefault:
                raise AttributeError(
                    f"'{self._name}' attribute of '{owner.__name__}' class "
                    "has no default value and must be specified explicitly"
                )
            return self._default


# TODO: I can't figure out how to properly resolve type errors when the argument is `Case`
#       in the decorator definition for condition


def step(condition: Callable[[Any], bool] | None = None) -> Any:
    """A decorator to define steps to be performed when running a `Case`.

    The step should not return a value.

    Args:
        condition: an optional callable which can be used to determine whether the step should run.
            It will receive the `Case` instance as its only argument, and must return a boolean
            which, if True, the step will run. Otherwise, it will be skipped.

    Usage:
        ```
        class MyCase(Case):
            @step(condition=lambda case: case.case_dir.exists())
            def some_analysis_step(self):
                # do something
        ```

    """

    def decorator(f: Callable[[Case], None]) -> Callable[[Case], None]:
        @functools.wraps(f)
        def new_f(self: Case) -> None:
            if condition is not None and condition(self):
                return f(self)
            else:
                return None

        return new_f

    return decorator


class Case:
    """Base case for all cases."""

    def __init__(self, **kwargs: Any):
        for name, value in kwargs.items():
            setattr(self, name, value)
