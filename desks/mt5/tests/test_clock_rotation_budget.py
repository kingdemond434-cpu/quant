"""Invariant I1 (principal 2026-11-25): every certified survivor on a fresh forward clock.

The production forward pass is BUDGETED and ROTATES: it stops cleanly when its wall-clock budget
is spent (so the state is written and the promoter still runs in the slot), it visits the stalest
symbol first with never-evaluated clocks first of all and ties broken by the forward slot
ranker's published rank, and `last_attempt_at` is the cursor that makes successive passes cover
every clock. Exotic certificates are a named exclusion (no new clock, nothing deleted). The
per-clock freshness table is published for the health board. These pin each property.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "tests"))

import shadow_forward  # noqa: E402
from test_shadow_forward_checkpoints import _bars, _wire  # noqa: E402


def _state(shadow_dir: Path) -> dict:
    return json.loads((shadow_dir / "shadow_state.json").read_text("utf-8"))


def _fresh(shadow_dir: Path) -> dict:
    return json.loads((shadow_dir / "CLOCK_FRESHNESS.json").read_text("utf-8"))


def test_a_spent_budget_stops_cleanly_and_the_next_pass_resumes_at_the_cursor(
        tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []
    slow = {"on": True}

    def fetch(sym: str, timeframe: str = "H1"):
        calls.append(sym)
        if slow["on"]:
            time.sleep(0.3)
        return _bars()

    shadow_dir = _wire(monkeypatch, tmp_path, ["AUDUSD", "EURUSD", "GBPUSD"], fetch)
    shadow_forward.main(budget_s=0.45)
    st = _state(shadow_dir)
    assert calls == ["AUDUSD", "EURUSD"], f"the budget did not stop the pass: {calls}"
    assert st["engine_pass"]["complete"] is False and st["engine_pass"]["budget_exhausted"]
    assert st["engine_pass"]["rows_reached"] == 2
    assert "last_attempt_at" not in st.get("GBPUSD.asia", {}), "an unreached row was stamped"
    fresh = _fresh(shadow_dir)
    assert fresh["summary"]["next_cursor_symbol"] == "GBPUSD"
    assert fresh["summary"]["never_evaluated"] == 1
    assert fresh["clocks"]["GBPUSD.asia"]["reached_this_pass"] is False

    calls.clear()
    slow["on"] = False
    shadow_forward.main(budget_s=600)
    assert calls[0] == "GBPUSD", f"the next pass did not resume at the cursor: {calls}"
    assert _state(shadow_dir)["engine_pass"]["complete"] is True
    assert _fresh(shadow_dir)["summary"]["never_evaluated"] == 0


def test_a_never_evaluated_tie_is_broken_by_the_slot_rankers_rank(
        tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fetch(sym: str, timeframe: str = "H1"):
        calls.append(sym)
        return _bars()

    shadow_dir = _wire(monkeypatch, tmp_path, ["AUDUSD", "EURUSD", "GBPUSD"], fetch)
    (shadow_dir.parent / "FORWARD_SLOT_RANKER.json").write_text(json.dumps({
        "at": "2026-11-25T00:00:00+00:00",
        "running": [{"clock": "GBPUSD.asia"}, {"clock": "AUDUSD.asia"}]}), "utf-8")
    shadow_forward.main()
    assert calls == ["GBPUSD", "AUDUSD", "EURUSD"], calls
    summ = _fresh(shadow_dir)["summary"]
    assert "FORWARD_SLOT_RANKER.json" in summ["priority_source"]
    assert _fresh(shadow_dir)["clocks"]["GBPUSD.asia"]["slot_rank"] == 0


def test_without_a_ranking_the_order_is_the_old_one_and_says_unmeasured(
        tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fetch(sym: str, timeframe: str = "H1"):
        calls.append(sym)
        return _bars()

    shadow_dir = _wire(monkeypatch, tmp_path, ["AUDUSD", "EURUSD"], fetch)
    shadow_forward.main()
    assert calls == ["AUDUSD", "EURUSD"]
    assert _fresh(shadow_dir)["summary"]["priority_source"].startswith("UNMEASURED")


def test_an_exotic_certificate_is_a_named_exclusion_and_nothing_is_deleted(
        tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fetch(sym: str, timeframe: str = "H1"):
        calls.append(sym)
        return _bars()

    shadow_dir = _wire(monkeypatch, tmp_path, ["EURUSD", "EURZAR", "USDNOK"], fetch)
    (shadow_dir / "shadow_state.json").write_text(json.dumps({
        "USDNOK.asia": {"status": "PROMOTION CANDIDATE", "n": 40}}), "utf-8")
    shadow_forward.main()
    st = _state(shadow_dir)
    assert calls == ["EURUSD"], f"an exotic was judged: {calls}"
    assert "EURZAR.asia" not in st, "an exotic certificate was given a new clock"
    assert st["USDNOK.asia"]["status"] == "PROMOTION CANDIDATE" and st["USDNOK.asia"]["n"] == 40
    assert st["USDNOK.asia"]["forward_evidence"]["status"] == "UNMEASURED"
    exc = _fresh(shadow_dir)["summary"]["excluded"]["exotic"]
    assert exc["n"] == 2 and "exotic" in exc["why"]


def test_a_caller_with_its_own_rows_keeps_the_unbudgeted_unfiltered_pass(
        tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fetch(sym: str, timeframe: str = "H1"):
        calls.append(sym)
        return _bars()

    shadow_dir = _wire(monkeypatch, tmp_path, ["EURUSD"], fetch)
    shadow_forward.main(rows=[("EURZAR", "asia", {}, "session_range_breakout", "LONG")],
                        ledger="precert_state.json")
    assert calls == ["EURZAR"]
    assert not (shadow_dir / "CLOCK_FRESHNESS.json").exists()
