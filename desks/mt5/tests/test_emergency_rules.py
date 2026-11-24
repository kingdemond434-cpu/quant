"""Emergency kill rules: closes only, near a firm floor, duplicates, stop-less positions."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import emergency_rules as er  # noqa: E402

DESKM = (341956, 341955)
T0 = 1_800_000_000.0


def _p(ticket, sym="EURUSD", typ=0, magic=341956, comment="FX12", sl=1.0, t=T0 - 600):
    return SimpleNamespace(ticket=ticket, symbol=sym, type=typ, magic=magic, comment=comment,
                           sl=sl, time=t, volume=0.1)


def _a(ps, equity=100_000.0, start=100_000.0):
    return er.assess(ps, desk_magics=DESKM, now_epoch=T0, equity=equity, day_start=start,
                     initial=100_000.0, daily_frac=0.05, max_frac=0.10)


def test_within_limits_closes_nothing() -> None:
    res = _a([_p(1), _p(2, sym="GBPUSD")])
    assert res.closes == [] and not res.flatten and not res.stand_down


def test_near_the_daily_floor_flattens_every_desk_position_and_stands_down() -> None:
    # daily limit 5,000 from 100,000: floor 95,000; 20% room = 1,000 -> flatten at <= 96,000
    ps = [_p(1), _p(2, magic=341955, sym="XAUUSD"), _p(3, magic=999)]
    res = _a(ps, equity=96_000.0)
    assert res.flatten and res.stand_down and res.rule == er.NEAR_DAILY_LIMIT
    assert sorted(t for t, _, _ in res.closes) == [1, 2]   # never a position that is not ours
    assert not _a(ps, equity=96_001.0).flatten


def test_near_the_max_loss_floor_flattens() -> None:
    # static floor 90,000; 20% of 10,000 = 2,000 -> flatten at <= 92,000 even on a fresh day
    res = _a([_p(1)], equity=92_000.0, start=92_000.0)
    assert res.rule == er.NEAR_MAX_LOSS and res.flatten


def test_unreadable_inputs_never_flatten_on_a_guess() -> None:
    res = _a([_p(1)], equity=None)
    assert not res.flatten and res.notes
    res = _a([_p(1)], equity=96_000.0, start=None)
    assert not res.flatten and any("daily rule skipped" in n for n in res.notes)


def test_a_duplicate_send_keeps_the_oldest_only() -> None:
    ps = [_p(5, t=T0 - 100), _p(4, t=T0 - 200), _p(6, t=T0 - 50, typ=1)]
    res = _a(ps)
    assert [(t, r) for t, r, _ in res.closes] == [(5, er.DUPLICATE)]


def test_a_stopless_position_is_closed_after_the_grace() -> None:
    res = _a([_p(1, sl=0.0, t=T0 - 600), _p(2, sym="GBPUSD", sl=0.0, t=T0 - 30)])
    assert [(t, r) for t, r, _ in res.closes] == [(1, er.UNPROTECTED)]


def test_no_server_clock_never_closes_for_a_missing_stop() -> None:
    res = er.assess([_p(1, sl=0.0)], desk_magics=DESKM, now_epoch=0.0, equity=100_000.0,
                    day_start=100_000.0, initial=100_000.0, daily_frac=0.05, max_frac=0.10)
    assert res.closes == []


def test_every_close_is_logged(tmp_path) -> None:
    log = tmp_path / "e.jsonl"
    er.log_close(account="ftmo", ticket=1, symbol="EURUSD", rule=er.DUPLICATE, why="x",
                 ok=True, armed=True, path=log)
    row = json.loads(log.read_text().splitlines()[0])
    assert row["rule"] == er.DUPLICATE and row["ok"] and row["account"] == "ftmo"


def test_the_rules_never_open_or_add() -> None:
    src = (DESK / "prop" / "emergency_rules.py").read_text("utf-8")
    for banned in ("order_send", "TRADE_ACTION", "ORDER_TYPE"):
        assert banned not in src


def test_the_ftmo_executor_runs_the_rules_every_pass_and_honours_the_stand_down() -> None:
    src = (DESK / "prop" / "ftmo_executor.py").read_text("utf-8")
    body = src[src.index("def run("):]
    assert "emergency(mt5, st, doc, decl" in body
    assert body.index("emergency(mt5") < body.index("_entries(mt5")
    assert body.index('"EMERGENCY_STAND_DOWN"') < body.index("_entries(mt5")
