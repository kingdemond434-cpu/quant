"""libs/ops/safe_append.append_line: a log line never raises (box 2026-10-29, fusion_deadman).

Also pins the shared-log writer it was introduced for: mt5desk/gateway.py `log()`, which the
gateway resident, the hourly chain's regime leg and MT5-RegimeMonitor all call on one file.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.ops import safe_append
from libs.ops.safe_append import append_line

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(safe_append.time, "sleep", lambda _s: None)


def test_appends_and_creates_the_parent(tmp_path: Path) -> None:
    p = tmp_path / "logs" / "x.log"
    assert append_line(p, "one") and append_line(p, "two")
    assert p.read_text("utf-8") == "one\ntwo\n"


def test_an_unwritable_target_returns_false_and_goes_to_stderr(tmp_path, capsys) -> None:
    p = tmp_path / "x.log"
    p.mkdir()                                   # opening a directory for append raises OSError
    assert append_line(p, "lost line") is False
    err = capsys.readouterr().err
    assert "log write to x.log failed" in err and "lost line" in err


def test_a_transient_refusal_is_retried(tmp_path, monkeypatch) -> None:
    real_open = Path.open
    left = {"n": 2}

    def flaky(self, *a, **kw):
        if self.name == "x.log" and left["n"]:
            left["n"] -= 1
            raise PermissionError(13, "sharing violation")
        return real_open(self, *a, **kw)

    monkeypatch.setattr(Path, "open", flaky)
    assert append_line(tmp_path / "x.log", "third time", attempts=3)
    assert (tmp_path / "x.log").read_text("utf-8") == "third time\n"


def test_every_attempt_refused_is_false_not_a_raise(tmp_path, monkeypatch) -> None:
    target = tmp_path / "x.log"
    real_open = Path.open

    def refuse(self, *a, **kw):
        if self == target:
            raise PermissionError(13, "sharing violation")
        return real_open(self, *a, **kw)

    monkeypatch.setattr(Path, "open", refuse)
    assert append_line(target, "never", attempts=4) is False


def test_the_gateway_log_goes_through_the_never_raise_helper() -> None:
    src = (ROOT / "desks" / "mt5" / "mt5desk" / "gateway.py").read_text("utf-8")
    body = src[src.index("def log(msg: str) -> None:"):]
    body = body[:body.index("\ndef ")]
    assert "append_line(LOG, line)" in body
    assert '.open("a"' not in body
