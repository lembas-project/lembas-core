from __future__ import annotations

from typing import TYPE_CHECKING

from lembas.main import run

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


def test_run(capsys: CaptureFixture[str]) -> None:
    run()
    assert capsys.readouterr().out.rstrip() == "Hello"
