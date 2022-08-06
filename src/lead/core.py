from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


class Case:
    """Base case for all cases."""

    def __init__(self, **kwargs: Any):
        for name, value in kwargs.items():
            setattr(self, name, value)


def step(condition: Callable[[Any], bool]) -> Any:
    def decorator(f: Callable[[Case], None]) -> Callable[[Case], None]:
        @functools.wraps(f)
        def new_f(self: Case) -> None:
            if condition(self):
                return f(self)
            else:
                return None

        return new_f

    return decorator


class _NoDefault:
    """Used as a sentinel to indicate lack of a default value for an `InputAttribute`."""


_builtin_type = type


class InputAttribute:
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
            self._type = None

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
