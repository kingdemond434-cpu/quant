"""The live-desk pager: silence, drawdown, pause and release refusal each raise a condition."""
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "scripts" / "check_live_desk_alive.py"
_spec = importlib.util.spec_from_file_location("check_live_desk_alive", _SRC)
assert _spec and _spec.loader
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

WED = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _eval(state=None, **kw):
    args = {"gw_state": {"equity": 650.0}, "gw_mtime": WED.timestamp(), "paused": False,
            "release": {"ok": True}}
    args.update(kw)
    return A.evaluate(WED, state or {}, **args)


def test_market_hours() -> None:
    assert A.gold_is_trading(WED)
    assert not A.gold_is_trading(datetime(2026, 9, 26, 12, tzinfo=UTC))       # Saturday
    assert not A.gold_is_trading(datetime(2026, 9, 25, 21, 30, tzinfo=UTC))   # Friday close
    assert not A.gold_is_trading(datetime(2026, 9, 23, 21, 30, tzinfo=UTC))   # daily break
    assert A.gold_is_trading(datetime(2026, 9, 27, 23, 30, tzinfo=UTC))       # Sunday open


def test_a_healthy_desk_raises_nothing() -> None:
    conds, st = _eval()
    assert conds == [] and st["day_start_equity"] == 650.0


def test_a_silent_gateway_pages_while_gold_trades() -> None:
    conds, _ = _eval(gw_mtime=WED.timestamp() - 45 * 60)
    assert [k for k, _ in conds] == ["silent"]
    conds, _ = _eval(gw_mtime=None)
    assert [k for k, _ in conds] == ["silent"]


def test_silence_on_a_weekend_is_not_an_alert() -> None:
    sat = datetime(2026, 9, 26, 12, tzinfo=UTC)
    conds, _ = A.evaluate(sat, {}, gw_state={"equity": 650.0},
                          gw_mtime=sat.timestamp() - 86400, paused=False, release=None)
    assert conds == []


def test_drawdowns_page() -> None:
    st = {"day": WED.date().isoformat(), "day_start_equity": 700.0, "peak_equity": 800.0}
    conds, _ = _eval(state=st, gw_state={"equity": 660.0})
    assert {k for k, _ in conds} == {"day_drop", "peak_drop"}


def test_pause_and_release_refusal_page() -> None:
    conds, _ = _eval(paused=True, release={"ok": False, "reason": "drift"})
    assert {k for k, _ in conds} == {"paused", "release_refused"}


def test_repeat_suppression() -> None:
    st = {"paged": {"silent": WED.isoformat()}}
    assert not A.due("silent", WED, st)
    assert A.due("silent", datetime(2026, 9, 23, 19, tzinfo=UTC), st)
    assert A.due("paused", WED, st)
