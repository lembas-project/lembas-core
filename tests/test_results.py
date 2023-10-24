import pytest

from lembas import Case
from lembas.results import result


class MyCase(Case):
    @result
    def some_result(self) -> str:
        return "some_result_value"

    @result("single_result")
    def single_result_name_ignored(self) -> str:
        return "single_result_value"

    @result("first_result", "second_result")
    def multiple_result_name_ignored(self) -> tuple[str, str]:
        return "first_result_value", "second_result_value"

    @result("first_result_expected", "second_result_expected")
    def incorrect_number_of_results(self) -> str:
        return "this_should_raise_an_error"


@pytest.fixture()
def case() -> MyCase:
    return MyCase()


def test_case_results_parent(case: MyCase) -> None:
    assert case.results.parent is case


def test_case_results_get_attr_no_args(case: MyCase) -> None:
    assert case.results.some_result == "some_result_value"


def test_cas_results_get_attr_with_args_single(case: MyCase) -> None:
    assert case.results.single_result == "single_result_value"


def test_case_results_get_attr_multiple(case: MyCase) -> None:
    assert case.results.first_result == "first_result_value"
    assert case.results.second_result == "second_result_value"


def test_case_results_incorrect_number_of_results(case: MyCase) -> None:
    with pytest.raises(ValueError):
        _ = case.results.first_result_expected


def test_case_results_undefined(case: MyCase) -> None:
    with pytest.raises(AttributeError):
        _ = case.results.nonexistent_result


def test_case_results_method_provides_results(case: MyCase) -> None:
    assert MyCase.some_result._provides_results == ("some_result",)  # type: ignore
