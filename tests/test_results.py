import pytest

from lembas import Case


class MyCase(Case):
    ...


@pytest.fixture()
def case() -> MyCase:
    return MyCase()


def test_case_results_parent(case: MyCase) -> None:
    assert case.results.parent is case
