from __future__ import annotations

from typing import Any

import pytest

from lead import Case
from lead import InputParameter


class MyCase(Case):
    my_param = InputParameter(type=float, min=2.0, max=5.0)


@pytest.fixture()
def case() -> MyCase:
    return MyCase(my_param=3.0)


@pytest.mark.parametrize("input_value", [3.0, 3, "3", "3.0"])
def test_case_handler_parameter_type_conversion(case: MyCase, input_value: Any) -> None:
    """The value is coerced to the proper type."""
    assert case.my_param == pytest.approx(3.0)


@pytest.mark.parametrize("input_value", [1.0, 6.0])
def test_case_handler_parameter_bounds_raises_exception(
    case: MyCase, input_value: float
) -> None:
    """An exception is raised when attempting to set the value out of bounds."""
    with pytest.raises(ValueError):
        case.my_param = input_value
