"""Gate -2 and the no-limbo cell state ledger (research/cell_state.py).

Gate -2 may only ROUTE: every row stays, in a family-preserving order, and every waiting cell
names its dependency and repair owner. These tests pin each check on a synthetic host, the
UNMEASURED path, the ledger's transitions and KPIs, and the refresh_bars hand-off.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data.pit import stamp as pit_stamp  # noqa: E402
from libs.tiers import prejudge_screen as pj  # noqa: E402
from research import cell_state as cs  # noqa: E402

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
COSTS = {"tick_size": 1e-5, "tick_value": 1.0, "median_spread_pts": 1.0}


def _bars(path: Path, days: int, per_day: int = 24) -> None:
    idx = pd.date_range("2024-01-01", periods=days * per_day, freq=f"{24 // per_day}h", tz="UTC",
                        name="time")
    pd.DataFrame({"close": 1.0}, index=idx).to_parquet(path)


@pytest.fixture()
def host(tmp_path: Path) -> Path:
    uni = tmp_path / "universe"
    uni.mkdir()
    reg = {s: {"symbol": s, **COSTS} for s in ("EURUSD", "GBPUSD", "XAUUSD", "SHORTY", "WTI")}
    reg["BADCOST"] = {"symbol": "BADCOST", "tick_size": 0.0, "tick_value": 1.0,
                      "median_spread_pts": 1.0}
    (uni / "universe.json").write_text(json.dumps(reg), "utf-8")
    for s in ("EURUSD", "GBPUSD", "XAUUSD", "BADCOST"):
        _bars(uni / f"{s}_H1.parquet", 400)
    _bars(uni / "SHORTY_H1.parquet", 20)
    (uni / "bar_coverage_skips.json").write_text(json.dumps(
        {"reasons": {"WTI": {"reason": "NOT_OFFERED"}}}), "utf-8")
    return uni


def _ctx(host: Path, *, judged: dict[str, bool] | None = None,
         families: tuple[str, ...] = ("trend", "relative_value")) -> cs.Context:
    return cs.Context(now=NOW, universe=host, live_families=families, judged=judged or {})


def _row(sym: str = "EURUSD", fam: str = "trend", tf: str = "H1", **params: object) -> dict:
    body = {"symbol": sym, "family": fam, "params": {"timeframe": tf, **params}}
    return pit_stamp(body, "test", now=NOW - timedelta(hours=1))


def _checks(row: dict, ctx: cs.Context) -> set[str]:
    return {v["check"] for v in cs.gate_minus2(row, ctx, seen={}, genomes={},
                                               cell=cs.cell_of(row))}


def test_constants_are_the_organs_own() -> None:
    from research import hourly_cycle as hc
    from research import judge_coverage as jc
    assert cs.CPCV_MIN_DAYS == jc.CPCV_MIN_DAYS
    assert cs.BARS_PER_HOUR == hc.BARS_WANTED_PER_HOUR
    assert set(cs.STATES) == set(cs.TRANSITIONS)


def test_no_absorbing_state_except_judged() -> None:
    """No cell ever ends untestable: every state but a JUDGED verdict has an edge OUT."""
    assert set(cs.TERMINALS) == {cs.JUDGED_PASS, cs.JUDGED_FAIL}
    for state, edges in cs.TRANSITIONS.items():
        leaves = edges - {state} - set(cs.TERMINALS if state in cs.TERMINALS else ())
        if state in cs.TERMINALS:
            assert edges <= set(cs.TERMINALS), f"{state} must stay judged"
            continue
        assert leaves, f"{state} is absorbing; only a JUDGED verdict may be"
    for would_be in cs.CONVERT_FROM:
        assert would_be not in cs.STATES, f"{would_be} must be a convert_from, not a state"
    assert cs.READY in cs.TRANSITIONS[cs.CONVERT]


def test_a_clean_row_is_ready_and_unflagged(host: Path) -> None:
    rows, summ = cs.stamp([_row()], _ctx(host, judged={"other.cell": False}))
    assert rows[0]["cell_state"]["state"] == cs.READY
    assert "prejudge" not in rows[0]
    assert summ["flagged"] == 0 and summ["unmeasured_checks"] == []


@pytest.mark.parametrize(("row", "check", "state", "convert_from"), [
    (_row(tf="M15"), "bars", cs.BLOCKED, None),
    (_row("WTI"), "bars", cs.CONVERT, cs.NO_SOURCE),
    (_row("SHORTY"), "observations", cs.CONVERT, cs.NO_HISTORY),
    (_row("NOPE"), "asset_mapping", cs.CONVERT, cs.NOT_MT5),
    (_row(fam="ghost"), "family", cs.CONVERT, cs.IMPOSSIBLE),
    (_row(fam="relative_value"), "inputs", cs.BLOCKED, None),
    (_row("EURUSD", "relative_value", peer_symbol="NOPE"), "asset_mapping", cs.CONVERT,
     cs.NOT_MT5),
    (_row("BADCOST"), "costs", cs.BLOCKED, None),
    ({"symbol": "EURUSD", "family": "trend", "params": {"timeframe": "H1"}}, "pit", cs.BLOCKED,
     None),
])
def test_each_check_routes_with_a_named_owner(host: Path, row: dict, check: str,
                                              state: str, convert_from: str | None) -> None:
    ctx = _ctx(host)
    assert check in _checks(row, ctx)
    rows, _ = cs.stamp([dict(row)], ctx)
    st = rows[0]["cell_state"]
    assert st["state"] == state
    assert st["owner"] in cs.OWNERS
    assert st["reopen_conditions"] and st["next_action"]
    assert st["dependency"], "every waiting cell names its dependency"
    assert st.get("convert_from") == convert_from
    if state == cs.CONVERT:
        assert st["conversion_reason"] in cs.CONVERSIONS
        assert st["owner"] == cs.CONVERTER_OWNER
    assert f"{cs.FLAG_PREFIX}{st['check']}" in rows[0]["prejudge"]["flags"]


def test_cost_dead_and_future_pit_hold(host: Path) -> None:
    dead = {**_row(), "net_verdict": "COST_DEAD"}
    assert "costs" in _checks(dead, _ctx(host))
    unconfirmed = {**_row(), "net_verdict": "COST_DEAD_UNCONFIRMED"}
    assert "costs" not in _checks(unconfirmed, _ctx(host))
    future = pit_stamp({"symbol": "EURUSD", "family": "trend", "params": {"timeframe": "H1"}},
                       "t", now=NOW + timedelta(days=1))
    future["available_time"] = (NOW + timedelta(days=1)).isoformat()
    assert "pit" in _checks(future, _ctx(host))


def test_twins_and_already_judged(host: Path) -> None:
    a, b = _row(), _row()
    g1 = {**_row("GBPUSD"), "genome_id": "g"}
    g2 = {**_row("XAUUSD"), "genome_id": "g"}
    judged_row = _row("EURUSD", lookback=5)
    ctx = _ctx(host, judged={cs.cell_of(judged_row): True})
    rows, summ = cs.stamp([a, b, g1, g2, judged_row], ctx)
    states = [r["cell_state"]["state"] for r in rows]
    assert states == [cs.READY, cs.BLOCKED, cs.READY, cs.BLOCKED, cs.JUDGED_PASS]
    assert rows[1]["cell_state"]["dependency"].startswith("twin:")
    assert "prejudge" not in rows[4], "a judged row is not re-flagged; coverage orders it"
    assert summ["by_check"]["duplicate"] == 2


def test_unmeasured_inputs_never_flag(tmp_path: Path) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()
    ctx = cs.Context(now=NOW, universe=empty, live_families=(), judged={})
    rows, summ = cs.stamp([_row(tf="M15"), _row("NOPE", "ghost")], ctx)
    assert all(r["cell_state"]["state"] == cs.READY for r in rows)
    assert {"bars", "observations", "asset_mapping", "family"} <= set(summ["unmeasured_checks"])


def test_existing_flags_are_kept_and_demotion_is_in_family_only(host: Path) -> None:
    rows = [_row(tf="M15"), _row("GBPUSD"), _row(fam="relative_value"),
            _row("XAUUSD", lookback=3)]
    rows[3]["prejudge"] = {"flags": ["redqueen:x"], "rules_hash": "h"}
    stamped, _ = cs.stamp(rows, _ctx(host))
    assert stamped[3]["prejudge"]["flags"] == ["redqueen:x"]
    out, rep = pj.demote_flagged(stamped, {})
    assert len(out) == 4 and rep["withheld"] == 0
    assert [r["family"] for r in out] == [r["family"] for r in rows]
    assert out[0]["symbol"] == "GBPUSD", "the clean trend row moves ahead of the held one"


def test_ledger_kpis_transitions_and_unlock_value(host: Path, tmp_path: Path) -> None:
    ctx = _ctx(host)
    rows, g2 = cs.stamp([_row(tf="M15"), _row("GBPUSD", tf="M15"), _row("XAUUSD")], ctx)
    bank = {"XAUUSD@M5.trend.p=1": {"reason": "data_missing", "sym": "XAUUSD", "tf": "M5",
                                    "family": "trend", "parked_at": "2026-10-01T00:00:00+00:00"},
            "EURUSD.trend.p=2": {"reason": "never_fires", "sym": "EURUSD", "tf": "H1"},
            "EURUSD.trend.p=3": {"reason": "mystery"}}
    lp, rp = tmp_path / "ledger.json", tmp_path / "CELL_STATE.json"
    k1 = cs.publish(rows, ledger_path=lp, report_path=rp, bank=bank, now=NOW, gate2=g2)
    assert k1["unexplained_waiting_cells"] == 1, "the unnamed bank reason is counted, by name"
    assert k1["oldest_blocked"]["cell"] == "XAUUSD@M5.trend.p=1"
    doc = json.loads(rp.read_text("utf-8"))
    assert rp.stat().st_size < 4 * 1024 * 1024
    kinds = {q["dependency"]: q for q in doc["dependency_queue"]}
    assert kinds["bars:EURUSD_M15"]["unlock_value"] == 1.0
    assert doc["states"][cs.REPAIRING] >= 3, "the bars head is being worked this hour"
    # next pass: the EURUSD chart landed, so its cell is READY -- one unlock
    (host / "EURUSD_M15.parquet").write_bytes((host / "EURUSD_H1.parquet").read_bytes())
    rows2, _ = cs.stamp([_row(tf="M15"), _row("GBPUSD", tf="M15"), _row("XAUUSD")], _ctx(host))
    k2 = cs.publish(rows2, ledger_path=lp, report_path=rp, bank=bank,
                    now=NOW + timedelta(hours=1))
    assert k2["unlocked_last_pass"] == 1 and k2["unlocked_per_hour"] == 1.0
    doc2 = json.loads(rp.read_text("utf-8"))
    assert doc2["kpi"]["oldest_blocked"]["since"] == "2026-10-01T00:00:00+00:00"
    assert len(doc2["history"]) == 2


def test_capacity_prefix_is_judging(host: Path) -> None:
    rows, _ = cs.stamp([_row(), _row("GBPUSD"), _row("XAUUSD")], _ctx(host))
    _, rep = cs.build(rows, bank={}, prior=None, capacity=2, now=NOW)
    assert rep["states"][cs.JUDGING] == 2 and rep["states"][cs.READY] == 1


def test_refresh_bars_prefers_the_queue_and_falls_back(tmp_path: Path) -> None:
    from research import hourly_cycle as hc
    cov = tmp_path / "JUDGE_COVERAGE.json"
    cov.write_text(json.dumps({"bars_wanted": {"AUDCAD_M15": 9}}), "utf-8")
    assert hc.bars_wanted_symbols(cov) == ["AUDCAD"]
    led = tmp_path / "CELL_STATE.json"
    led.write_text(json.dumps({"at": datetime.now(UTC).isoformat(), "dependency_queue": [
        {"kind": "bars", "key": "EURUSD_M5", "unlock_value": 3.0},
        {"kind": "history", "key": "XAUUSD_H1", "unlock_value": 99.0},
        {"kind": "bars", "key": "GBPUSD_M15", "unlock_value": 5.0},
        {"kind": "bars", "key": "EURUSD_M15", "unlock_value": 3.0}]}), "utf-8")
    assert hc.bars_wanted_symbols(cov) == ["EURUSD", "GBPUSD"]
    led.write_text(json.dumps({"at": "2020-01-01T00:00:00+00:00", "dependency_queue": [
        {"kind": "bars", "key": "EURUSD_M5", "unlock_value": 3.0}]}), "utf-8")
    assert hc.bars_wanted_symbols(cov) == ["AUDCAD"], "a stale ledger steers nothing"


def test_parked_cells_convert_and_the_queue_is_handed_off(host: Path, tmp_path: Path) -> None:
    rows, _ = cs.stamp([_row("WTI"), _row()], _ctx(host))
    bank = {"EURUSD.trend.p=9": {"reason": "never_fires", "sym": "EURUSD", "tf": "H1",
                                 "family": "trend", "parked_at": "2026-01-01T00:00:00+00:00"},
            "EURUSD.trend.p=8": {"reason": "build_failed", "sym": "EURUSD", "tf": "H1",
                                 "family": "trend"}}
    lp, rp = tmp_path / "cell_state_ledger.json", tmp_path / "CELL_STATE.json"
    k = cs.publish(rows, ledger_path=lp, report_path=rp, bank=bank, now=NOW)
    assert k["convert"] == 2 and k["convert_stale"] == 0, "the convert clock starts at hand-off"
    q = json.loads((tmp_path / cs.CONVERT_QUEUE.name).read_text("utf-8"))
    assert q["status"] == "UNMEASURED_UNTIL_CONSUMED" and q["rows_total"] == 2
    by_cell = {r["cell"]: r for r in q["rows"]}
    assert by_cell["EURUSD.trend.p=9"]["conversion_reason"] == "coarser_timeframe"
    assert by_cell["EURUSD.trend.p=9"]["convert_from"] == "PARKED_UNRUNNABLE"
    assert all(r["conversion_reason"] in cs.CONVERSIONS for r in q["rows"])
    doc = json.loads(rp.read_text("utf-8"))
    assert doc["states"][cs.BLOCKED] == 1, "a build fault stays a repairable HOLD"
    assert cs.fence(doc) == []
    # the consumer acks: status flips
    (tmp_path / cs.CONVERT_ACKS.name).write_text(json.dumps(
        {"consumed_at": (NOW + timedelta(hours=1)).isoformat(), "cells": []}), "utf-8")
    cs.publish(rows, ledger_path=lp, report_path=rp, bank=bank, now=NOW + timedelta(hours=2))
    assert json.loads(rp.read_text("utf-8"))["convert"]["consumer"] == "CONSUMING"


def test_the_fence_fails_on_a_stale_conversion(host: Path, tmp_path: Path) -> None:
    rows, _ = cs.stamp([_row("WTI")], _ctx(host))
    lp, rp = tmp_path / "cell_state_ledger.json", tmp_path / "CELL_STATE.json"
    cs.publish(rows, ledger_path=lp, report_path=rp, bank={}, now=NOW)
    later = NOW + timedelta(hours=cs.CONVERT_STALE_H + 1)
    k = cs.publish(rows, ledger_path=lp, report_path=rp, bank={}, now=later)
    assert k["convert_stale"] == 1
    doc = json.loads(rp.read_text("utf-8"))
    assert doc["convert"]["fence"] == "FAIL"
    problems = cs.fence(doc)
    assert problems and "CONVERT" in problems[0]
    assert cs.fence(None) == [], "an absent report is UNMEASURED, not a breach"
