import os

import pytest

from lembas import Case
from lembas import CaseNotRunError
from lembas import result


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
def case(tmp_path: pytest.TempPathFactory) -> MyCase:  # type: ignore[misc]
    # Change to temp directory so case_dir is writable
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    c = MyCase()
    yield c
    os.chdir(old_cwd)


@pytest.fixture()
def run_case(case: MyCase) -> MyCase:
    """Fixture that provides a case that has been run."""
    case.run()
    return case


def test_case_results_parent(case: MyCase) -> None:
    assert case.results.parent is case


def test_case_results_raises_before_run(case: MyCase) -> None:
    """Accessing results before run() raises CaseNotRunError."""
    with pytest.raises(CaseNotRunError) as exc_info:
        _ = case.results.some_result
    assert "has not been run" in str(exc_info.value)
    assert "some_result" in str(exc_info.value)


def test_case_results_get_attr_no_args(run_case: MyCase) -> None:
    assert run_case.results.some_result == "some_result_value"


def test_cas_results_get_attr_with_args_single(run_case: MyCase) -> None:
    assert run_case.results.single_result == "single_result_value"


def test_case_results_get_attr_multiple(run_case: MyCase) -> None:
    assert run_case.results.first_result == "first_result_value"
    assert run_case.results.get("second_result") == "second_result_value"


def test_case_results_incorrect_number_of_results(run_case: MyCase) -> None:
    with pytest.raises(ValueError):
        _ = run_case.results.first_result_expected


def test_case_results_undefined(run_case: MyCase) -> None:
    with pytest.raises(AttributeError):
        _ = run_case.results.nonexistent_result


def test_case_results_method_provides_results(case: MyCase) -> None:
    assert MyCase.some_result._provides_results == ("some_result",)  # type: ignore


def test_case_has_run_property(case: MyCase) -> None:
    """has_run is False before run(), True after."""
    assert case.has_run is False
    case.run()
    assert case.has_run is True
