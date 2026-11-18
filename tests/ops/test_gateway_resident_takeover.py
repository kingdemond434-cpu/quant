"""A gateway resident that holds the slot but stopped passing is replaced; a paused one is not."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))

import gateway_resident as gr  # noqa: E402

NOW = datetime(2026, 11, 18, 3, 0, tzinfo=UTC)


def _stamp(tmp_path: Path, **doc: object) -> Path:
    p = tmp_path / "GATEWAY_LOADED.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_a_fresh_pass_is_not_stuck_even_when_gateway_state_is_old(tmp_path: Path) -> None:
    # A PAUSED gateway writes no gateway_state.json but still stamps every pass.
    p = _stamp(tmp_path, pid=42, last_pass_at=(NOW - timedelta(minutes=2)).isoformat())
    stuck, pid, _ = gr.holder_stuck(NOW, p, 1800)
    assert (stuck, pid) == (False, 42)


def test_a_holder_with_no_pass_for_half_an_hour_is_stuck(tmp_path: Path) -> None:
    p = _stamp(tmp_path, pid=42, started_at=(NOW - timedelta(days=18)).isoformat(),
               last_pass_at=(NOW - timedelta(minutes=31)).isoformat())
    stuck, pid, why = gr.holder_stuck(NOW, p, 1800)
    assert (stuck, pid) == (True, 42) and "last pass" in why


def test_a_holder_that_never_passed_is_judged_on_its_start(tmp_path: Path) -> None:
    p = _stamp(tmp_path, pid=7, started_at=(NOW - timedelta(hours=2)).isoformat(),
               last_pass_at=None)
    assert gr.holder_stuck(NOW, p, 1800)[0] is True


@pytest.mark.parametrize("body", ["not json", "[]", json.dumps({"last_pass_at": "x"})])
def test_no_usable_stamp_ends_nothing(tmp_path: Path, body: str) -> None:
    p = tmp_path / "GATEWAY_LOADED.json"
    p.write_text(body, encoding="utf-8")
    assert gr.holder_stuck(NOW, p, 1800)[:2] == (False, None)


def test_healthy_holder_exits_zero_and_ends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    ended: list[int] = []
    monkeypatch.setattr(gr, "_claim_singleton", lambda: None)
    monkeypatch.setattr(gr, "holder_stuck", lambda: (False, 42, "fresh"))
    monkeypatch.setattr(gr, "_take_over", lambda pid: (ended.append(pid), (True, ""))[1])
    assert gr.claim_or_take_over() == (None, 0)
    assert ended == []


def test_stuck_holder_is_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = iter([None, "HANDLE"])
    monkeypatch.setattr(gr, "_claim_singleton", lambda: next(claims))
    monkeypatch.setattr(gr, "holder_stuck", lambda: (True, 42, "stuck"))
    monkeypatch.setattr(gr, "_take_over", lambda pid: (True, f"pid {pid} ended"))
    monkeypatch.setattr(gr, "_log", lambda msg: None)
    assert gr.claim_or_take_over() == ("HANDLE", 0)


def test_stuck_holder_that_cannot_be_ended_fails_the_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gr, "_claim_singleton", lambda: None)
    monkeypatch.setattr(gr, "holder_stuck", lambda: (True, 42, "stuck"))
    monkeypatch.setattr(gr, "_take_over", lambda pid: (False, "not a gateway resident"))
    monkeypatch.setattr(gr, "_log", lambda msg: None)
    assert gr.claim_or_take_over() == (None, gr.EXIT_STUCK)


def test_take_over_refuses_a_pid_that_is_not_a_resident() -> None:
    import os
    ok, why = gr._take_over(os.getpid())
    assert ok is False and "not a gateway resident" in why
