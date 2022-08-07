from __future__ import annotations

from typing import Any

import pytest

from lead import Case
from lead import InputParameter
from lead import step


class MyCase(Case):
    my_param = InputParameter(type=float, min=2.0, max=5.0)
    param_with_default = InputParameter(default=10.0)
    required_param = InputParameter()

    @step(condition=lambda self: self.my_param > 4)
    def change_param_with_default(self) -> None:
        self.param_with_default = 5.0


@pytest.fixture()
def case() -> MyCase:
    return MyCase(my_param=3.0)


def test_case_parameter_default(case: MyCase) -> None:
    assert case.param_with_default == pytest.approx(10.0)


def test_case_parameter_required_raises_exception(case: MyCase) -> None:
    """A parameter with no default that is not set raises an exception when accessed."""
    with pytest.raises(AttributeError):
        _ = case.required_param


@pytest.mark.parametrize("input_value", [3.0, 3, "3", "3.0"])
def test_case_parameter_type_conversion(case: MyCase, input_value: Any) -> None:
    """The value is coerced to the proper type."""
    assert case.my_param == pytest.approx(3.0)


@pytest.mark.parametrize("input_value", [1.0, 6.0])
def test_case_parameter_bounds_raises_exception(
    case: MyCase, input_value: float
) -> None:
    """An exception is raised when attempting to set the value out of bounds."""
    with pytest.raises(ValueError):
        case.my_param = input_value


def test_case_step_condition_is_not_met(case: MyCase) -> None:
    """If we don't set the case.my_param, the step shouldn't run."""
    case.change_param_with_default()
    assert case.param_with_default == pytest.approx(10.0)


def test_case_step_condition_is_met(case: MyCase) -> None:
    """If we do set the case.my_param explicitly, the step should run."""
    case.my_param = 5.0
    case.change_param_with_default()
    assert case.param_with_default == pytest.approx(5.0)
