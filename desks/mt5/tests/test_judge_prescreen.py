"""The judge's pre-build screen: shadow by default, charged exactly once, canon only as code.

python -m pytest desks/mt5/tests/test_judge_prescreen.py -q
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for p in (DESK, DESK / "research", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from research import judge_prescreen as jp  # noqa: E402


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(jp, "INTAKE_REPORT", tmp_path / "intake.json")
    monkeypatch.setattr(jp, "VERDICTS", tmp_path / "prescreen_verdicts.jsonl")
    monkeypatch.setattr(jp, "KILLED", tmp_path / "prescreen_killed.json")
    monkeypatch.setattr(jp, "LOCK", tmp_path / "prescreen_verdicts.lock")
    monkeypatch.setattr(jp, "LEDGER", tmp_path / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(jp, "GRAPH", tmp_path / "hypothesis_graph.jsonl")
    monkeypatch.setattr(jp, "SOURCES_STATE", tmp_path / "sources_state.json")
    from libs.ops import events

    monkeypatch.setattr(events, "PATH", tmp_path / "events.jsonl")
    return tmp_path


def _row(cell, gate, passed=False, ds=None, at="2026-10-01T00:00:00+00:00"):
    return {
        "cell": cell,
        "terminal_gate": gate,
        "passed": passed,
        "downstream_status": ds,
        "at": at,
    }


# ------------------------------------------------------------------ identity and tiers
def test_bucket_of_reads_the_judges_cell_ids() -> None:
    assert jp.bucket_of("AUDCAD@M15.adx_channel_hybrid.p=1b57") == "AUDCAD|M15|adx_channel_hybrid"
    assert jp.bucket_of("3M.carry.p=3648") == "3M|H1|carry"
    assert jp.bucket_of("garbage") is None


def test_tier_skips_rows_that_are_not_series_judgements() -> None:
    assert jp.tier_of(_row("a", "economic_prior")) is None
    assert jp.tier_of(_row("a", "symbol_eligibility")) is None
    assert jp.tier_of(_row("a", "", None, "NOT_RUN_BUILD_BUDGET_DEFERRED")) is None
    assert jp.tier_of(_row("a", "UNKNOWN", None)) == jp.UNKNOWN_T
    assert jp.tier_of(_row("a", "in_sample_screen")) == jp.IS_FAIL_T
    assert jp.tier_of(_row("a", "deflated_sharpe")) == jp.CLEARED_IS_T
    assert jp.tier_of(_row("a", "", True)) == jp.PASSED_T


# ------------------------------------------------------------------ M5: canon is code
def test_canon_is_a_code_constant_and_sibling_dead_is_not_eligible() -> None:
    assert jp.CANON is False
    assert jp.RULES["needs_data"]["canon_eligible"] is True
    assert jp.RULES["chart_short"]["canon_eligible"] is False
    assert jp.RULES["sibling_dead"]["canon_eligible"] is False
    src = (DESK / "research" / "judge_prescreen.py").read_text("utf-8")
    assert "JUDGE_PRESCREEN_CANON.json" not in src  # no box-state switch


# ------------------------------------------------------------------ M4: the replay
def test_replay_screens_on_the_evidence_before_the_first_verdict() -> None:
    dead = [_row(f"EURUSD.carry.p={i:04d}", "in_sample_screen") for i in range(6)]
    late = [_row("EURUSD.carry.p=late", "UNKNOWN", None), _row("EURUSD.carry.p=late", "", True)]
    rp = jp.replay([*dead, *late], k_grid=(5, 10))
    k5 = rp["by_k"]["5"]
    assert k5["killed"] == 2 and k5["killed_by_tier"]["true_survivor"] == 1
    assert rp["by_k"]["10"]["killed"] == 0
    assert rp["true_survivors_reached_by_k"]["5"]["reached"] == 1
    assert rp["true_survivors_reached_by_k"]["5"]["exposed_uncleared"] == 1
    assert rp["true_survivors_reached_by_k"]["10"]["reached"] == 0
    assert rp["canon_k"] is None  # far below the per-half floor
    assert "EURUSD|H1|carry" not in rp["dead_buckets"]


def test_protection_only_counts_when_dated_before_the_verdict() -> None:
    rows = [
        _row(f"XAU.srb.p={i}", "in_sample_screen", at="2026-10-01T00:00:00+00:00")
        for i in range(30)
    ]
    future = jp.replay(rows, k_grid=(5,), protected={"XAU|H1|srb": "2026-10-20T00:00:00+00:00"})
    undated = jp.replay(rows, k_grid=(5,), protected={"XAU|H1|srb": None})
    past = jp.replay(rows, k_grid=(5,), protected={"XAU|H1|srb": "2026-09-01T00:00:00+00:00"})
    assert future["by_k"]["5"]["killed"] == 25  # no look-ahead: a later cert protects nothing
    assert undated["by_k"]["5"]["killed"] == 25  # an undated cert protects nothing in replay
    assert past["by_k"]["5"]["killed"] == 0
    # the LIVE table never lists a protected bucket as dead, dated or not
    assert not future["dead_buckets"] and not undated["dead_buckets"]


def test_survivors_never_at_risk_cannot_satisfy_the_floor(monkeypatch) -> None:
    monkeypatch.setattr(jp, "MIN_AT_RISK_PER_HALF", 2)
    rows = []
    for b in range(6):  # each bucket clears first, so its survivors were never at risk
        rows.append(_row(f"S{b}.carry.p=clear", "deflated_sharpe"))
        rows.append(_row(f"S{b}.carry.p=win", "", True))
    rows += [_row(f"DEAD.carry.p={i}", "in_sample_screen") for i in range(30)]
    rp = jp.replay(rows, k_grid=(5, 10))
    assert rp["population_by_tier"]["true_survivor"] == 6
    assert rp["true_survivors_reached_by_k"]["5"]["reached"] == 0  # 1 named sibling < K
    assert rp["canon_k"] is None and rp["canon_ready"] is False


def _fresh_bucket_survivors(interleave: bool) -> list[dict]:
    """The auditor's P7 / P7b: 40 survivors, each the FIRST verdict of its own fresh bucket,
    beside plenty of dead buckets. No K can ever reach a survivor here."""
    rows: list[dict] = []
    dead = [
        [_row(f"DEAD{b}.carry.p={j}", "in_sample_screen") for j in range(30)] for b in range(10)
    ]
    wins = [_row(f"FRESH{i}.carry.p=win", "", True) for i in range(40)]
    if interleave:  # P7b: survivors spread through time between the dead buckets' verdicts
        for i, w in enumerate(wins):
            rows.append(w)
            rows += dead[i % 10][(i // 10) * 7 : (i // 10) * 7 + 7]
    else:  # P7: all survivors first, the dead buckets after
        rows = wins + [r for d in dead for r in d]
    return rows


@pytest.mark.parametrize("interleave", [False, True], ids=["P7", "P7b"])
def test_fresh_bucket_survivors_never_satisfy_the_floor(interleave) -> None:
    rp = jp.replay(_fresh_bucket_survivors(interleave))
    assert rp["population_by_tier"]["true_survivor"] == 40
    assert all(v["reached"] == 0 for v in rp["true_survivors_reached_by_k"].values())
    assert rp["by_k"]["5"]["killed"] > 0  # the rule does kill dead-bucket cells...
    assert rp["canon_k"] is None and rp["canon_ready"] is False  # ...but proves nothing safe


def _at_risk_world(late_victim: bool) -> list[dict]:
    rows = []
    # eight REACHED survivors: each arrives in a bucket already holding 11 named siblings, one
    # of which cleared in_sample -- the rule reaches them at K=5 and K=10 and rightly spares them
    for i in range(8):
        rows.append(_row(f"W{i}.carry.p=clear", "deflated_sharpe"))
        rows += [_row(f"W{i}.carry.p={j}", "in_sample_screen") for j in range(10)]
        rows.append(_row(f"W{i}.carry.p=win", "", True))
    if late_victim:  # a late survivor arriving in a bucket with 6 prior failures: K=5 kills it
        rows += [_row(f"LATE.carry.p={j}", "in_sample_screen") for j in range(6)]
        rows.append(_row("LATE.carry.p=win", "", True))
    return rows


def test_select_on_the_earlier_half_confirm_on_the_later(monkeypatch) -> None:
    monkeypatch.setattr(jp, "MIN_AT_RISK_PER_HALF", 4)
    clean = jp.replay(_at_risk_world(False), k_grid=(5, 10))
    reach5 = clean["true_survivors_reached_by_k"]["5"]
    assert reach5["reached_by_half"] == {"select": 4, "confirm": 4}
    assert reach5["exposed_uncleared"] == 0 and reach5["floor_met"] is True
    assert clean["selected_k_on_select_half"] == 5 and clean["canon_k"] == 5
    dirty = jp.replay(_at_risk_world(True), k_grid=(5, 10))
    # K=5 is clean on the select half but kills the late survivor on the confirm half
    assert dirty["selected_k_on_select_half"] == 5
    assert dirty["by_k"]["5"]["killed_by_tier_confirm_half"]["true_survivor"] == 1
    assert dirty["canon_k"] is None


def test_holdout_is_deterministic_and_about_one_in_twenty() -> None:
    cells = [f"EURUSD.carry.p={i:06d}" for i in range(4000)]
    hits = sum(jp.is_holdout(c) for c in cells)
    assert 140 <= hits <= 260
    assert [jp.is_holdout(c) for c in cells[:50]] == [jp.is_holdout(c) for c in cells[:50]]


def test_chart_short_is_a_proof_with_a_clock_margin() -> None:
    assert jp.chart_is_short({"utc_days": 29, "span_days": 400})
    assert not jp.chart_is_short({"utc_days": 30, "span_days": 400})
    assert jp.chart_is_short({"utc_days": 200, "span_days": 50})
    assert not jp.chart_is_short(None)
    assert not jp.chart_is_short({"utc_days": "x"})


# ------------------------------------------------------------------ intake
def _tables(dead=None, charts=None) -> dict:
    return {
        "charts": charts
        or {
            "EURUSD|H1": {"utc_days": 2000, "span_days": 2900},
            "XAUUSD|M1": {"utc_days": 20, "span_days": 25},
        },
        "dead_buckets": dead or {},
        "protected_buckets": [],
    }


def _report(canon_k=None, ready=False, age_h=0.0) -> dict:
    at = (datetime.now(UTC) - timedelta(hours=age_h)).isoformat(timespec="seconds")
    return {"generated_at": at, "sibling_dead": {"canon_k": canon_k, "canon_ready": ready}}


def _non_holdout(prefix: str) -> str:
    i = 0
    while jp.is_holdout(f"{prefix}{i}"):
        i += 1
    return f"{prefix}{i}"


def _holdout(prefix: str) -> str:
    i = 0
    while not jp.is_holdout(f"{prefix}{i}"):
        i += 1
    return f"{prefix}{i}"


EV = _non_holdout("EURUSD.event_reaction.p=")


def _docket(ev_cell: str = EV) -> list[dict]:
    return [
        {"_cell": "EURUSD.carry.p=1", "symbol": "EURUSD", "family": "carry", "params": {}},
        {"_cell": ev_cell, "symbol": "EURUSD", "family": "event_reaction", "params": {}},
        {
            "_cell": "XAUUSD@M1.formula.p=3",
            "symbol": "XAUUSD",
            "family": "formula",
            "params": {"timeframe": "M1"},
        },
        {"_cell": "EURUSD.jump.p=4", "symbol": "EURUSD", "family": "jump", "params": {}},
    ]


def _probe(sym, fam):
    if fam == "event_reaction":
        return {"status": "NEEDS_DATA", "missing_input": "bar_clock"}
    return {"status": "UNMEASURED"}


def _graph(tmp: Path, *rows: dict) -> None:
    with (tmp / "hypothesis_graph.jsonl").open("a") as fh:
        for r in rows:
            fh.write(json.dumps({"id": r["id"], "region": "x", "params": {}, "source": "t", **r}))
            fh.write("\n")


def _files(tmp: Path, tables: dict, report: dict) -> tuple[Path, Path]:
    t, r = tmp / "tables.json", tmp / "report.json"
    t.write_text(json.dumps(tables))
    r.write_text(json.dumps(report))
    return t, r


def _run(t, r, *, canon, ruled=frozenset(), docket=None, probe=_probe, spc=2.0):
    return jp.intake(
        docket or _docket(),
        cell_of=lambda x: x["_cell"],
        probe=probe,
        tables_path=t,
        report_path=r,
        ruled=None if ruled is None else set(ruled),
        seconds_per_cell=spc,
        canon=canon,
    )


def test_shadow_returns_every_row_writes_no_trial_and_carries_missed_growth(paths) -> None:
    t, r = _files(paths, _tables(dead={"EURUSD|H1|jump": 50}), _report())
    rows = _docket()
    out, doc = jp.intake(
        rows,
        cell_of=lambda x: x["_cell"],
        probe=_probe,
        tables_path=t,
        report_path=r,
        ruled=set(),
        seconds_per_cell=2.0,
    )  # default = CANON
    assert out is rows and doc["mode"] == "SHADOW" and doc["removed_from_docket"] == 0
    assert doc["would_kill"] == {"needs_data": 1, "chart_short": 1, "sibling_dead": 1}
    assert doc["sibling_would_kill_by_k"] == {"5": 1, "10": 1, "20": 1, "40": 1, "80": 0}
    assert not jp.VERDICTS.exists() and jp.lifetime_kills() == (0, {})
    cost, gain = doc["missed_growth"]
    assert cost["side"] == "cost" and cost["e_log_w"] == "UNMEASURED"
    assert gain["side"] == "gain" and gain["rows_removed"] == 0 and gain["value"] == 0.0
    assert gain["would_free_seconds_if_all_rules_acted"] == 6.0


def test_canon_kills_only_needs_data_even_when_sibling_is_ready(paths) -> None:
    t, r = _files(paths, _tables(dead={"EURUSD|H1|jump": 50}), _report(40, True))
    out, doc = _run(t, r, canon=True)
    assert {x["_cell"] for x in out} == {
        "EURUSD.carry.p=1",
        "XAUUSD@M1.formula.p=3",
        "EURUSD.jump.p=4",
    }
    assert doc["rule_acts"] == {"needs_data": True, "chart_short": False, "sibling_dead": False}
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})
    assert doc["missed_growth"][1]["value"] == 2.0  # one build freed at 2 s/cell


def test_canon_holdout_still_goes_to_the_judge(paths) -> None:
    t, r = _files(paths, _tables(), _report())
    hold = _holdout("EURUSD.event_reaction.p=")
    out, doc = _run(t, r, canon=True, docket=_docket(hold))
    assert hold in {x["_cell"] for x in out}
    assert doc["holdout_sent_to_judge"] == 1 and jp.lifetime_kills() == (0, {})


def test_a_row_the_judge_already_ruled_is_never_screened_or_killed(paths) -> None:
    t, r = _files(paths, _tables(), _report())
    out, doc = _run(t, r, canon=True, ruled={EV})
    assert EV in {x["_cell"] for x in out}
    assert doc["rows_already_ruled_not_screened"] == 1 and jp.lifetime_kills() == (0, {})


def test_canon_without_the_ruled_set_kills_nothing(paths) -> None:
    t, r = _files(paths, _tables(), _report())
    out, doc = _run(t, r, canon=True, ruled=None)
    assert len(out) == 4 and "refused" in doc["ledger"] and not jp.VERDICTS.exists()


# ------------------------------------------------------------------ M3: exactly once
def test_kill_readmit_without_judgement_stays_one_trial(paths) -> None:
    t, r = _files(paths, _tables(), _report())
    _run(t, r, canon=True)
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})
    _run(t, r, canon=True, probe=lambda s, f: {"status": "PRESENT"})  # input appeared
    assert jp.fold_ledger()[EV]["killed"] is False
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})  # still one, not zero
    _run(t, r, canon=True)  # re-kill after readmit: still one, never two
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})


def test_readmit_then_judged_hands_the_one_trial_to_the_judge(paths) -> None:
    t, r = _files(paths, _tables(), _report())
    _run(t, r, canon=True)
    _run(t, r, canon=True, probe=lambda s, f: {"status": "PRESENT"})
    out, doc = _run(t, r, canon=True, ruled={EV})  # the judge has now ruled it
    assert doc["ledger"]["handed_to_judge"] == 1
    assert EV in {x["_cell"] for x in out}
    # the JUDGED handoff alone moves no charge: the graph holds no fate for it yet (no_spec)
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})
    gid = jp.fold_ledger()[EV]["graph_id"]
    assert gid  # the KILL row carries the graph's own id
    _graph(paths, {"id": gid, "fate": "FAILED"})
    assert jp.lifetime_kills() == (0, {})  # the graph's fate carries the single trial
    _run(t, r, canon=True, ruled=set())  # even if the ruled set later misses it: never re-killed
    assert jp.lifetime_kills() == (0, {}) and jp.fold_ledger()[EV]["judged"] is True


def test_a_killed_cell_parked_as_fail_to_build_stays_charged_exactly_once(paths) -> None:
    """v1.6 (rebase onto #424). A fail-to-build cell is parked by `judge_coverage`'s unrunnable
    filter BEFORE the screen runs, so the screen never sees it: a killed cell that is later
    parked is simply absent from the docket the screen reads -- no READMIT (it is not `present`),
    the KILL charge stands. Its NOT_RUN_BUILD_FAILED gate row is not a ruling (`_LedgerScan`
    skips every NOT_RUN row and `record_gauntlet_verdicts` writes no graph fate for it), so the
    charge is neither handed over nor joined away: one trial, never zero, never two. When the
    bank releases it and the judge rules it, the graph's fate carries that one trial instead."""
    from research import judge_coverage as jc

    t, r = _files(paths, _tables(), _report())
    _run(t, r, canon=True)                                     # KILL: one trial
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})
    parked_out = [x for x in _docket() if x["_cell"] != EV]    # the bank filtered it upstream
    gate = paths / "gate_verdict_ledger.jsonl"
    gate.write_text(json.dumps(_row(EV, "", ds="NOT_RUN_BUILD_FAILED")) + "\n")
    scan = jc._LedgerScan(gate)
    assert EV not in scan.cell_ruled                           # a NOT_RUN row is no ruling
    out, doc = _run(t, r, canon=True, docket=parked_out, ruled=scan.cell_ruled)
    assert doc["ledger"]["readmitted"] == 0 and doc["ledger"]["handed_to_judge"] == 0
    assert jp.fold_ledger()[EV]["killed"] is True
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})   # not zero
    # released by the bank and the input now present: READMIT, still one
    _run(t, r, canon=True, probe=lambda s, f: {"status": "PRESENT"}, ruled=scan.cell_ruled)
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})   # not two
    # the judge rules it: the graph's fate carries the single trial
    with gate.open("a") as fh:
        fh.write(json.dumps(_row(EV, "in_sample_screen")) + "\n")
    assert EV in jc._LedgerScan(gate).cell_ruled
    _run(t, r, canon=True, ruled=jc._LedgerScan(gate).cell_ruled)
    _graph(paths, {"id": jp.fold_ledger()[EV]["graph_id"], "fate": "FAILED"})
    assert jp.lifetime_kills() == (0, {})


# ------------------------------------------------------------------ M2: one source of truth
def test_a_lost_ledger_never_leaves_a_cell_out_uncharged(paths) -> None:
    t, r = _files(paths, _tables(), _report())
    _run(t, r, canon=True)
    jp.VERDICTS.unlink()  # the ledger is lost; the cache still lists the cell
    assert jp.KILLED.exists()
    out, _ = _run(t, r, canon=True)
    assert EV not in {x["_cell"] for x in out}
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})  # re-killed AND re-charged


def test_the_cache_is_never_an_authority(paths) -> None:
    t, r = _files(paths, _tables(), _report())
    jp.KILLED.write_text(json.dumps({"cells": {"EURUSD.jump.p=4": {"family": "jump"}}}))
    out, _ = _run(t, r, canon=True)
    assert "EURUSD.jump.p=4" in {x["_cell"] for x in out}
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})


def test_an_unwritable_ledger_removes_nothing(paths, monkeypatch) -> None:
    t, r = _files(paths, _tables(), _report())

    def boom(_rows):
        raise OSError("disk full")

    monkeypatch.setattr(jp, "_append_durable", boom)
    out, doc = _run(t, r, canon=True)
    assert len(out) == 4 and doc["removed_from_docket"] == 0


def test_concurrent_writers_charge_one_trial(paths) -> None:
    kill = {EV: {"rule": "needs_data", "row": _docket()[1], "evidence": {"x": 1}}}
    errs: list[BaseException] = []

    def go():
        try:
            jp.reconcile_and_kill(dict(kill), {EV}, set())
        except BaseException as exc:  # pragma: no cover - surfaced below
            errs.append(exc)

    ts = [threading.Thread(target=go) for _ in range(6)]
    for th in ts:
        th.start()
    for th in ts:
        th.join()
    assert not errs
    rows = [json.loads(x) for x in jp.VERDICTS.read_text().splitlines()]
    assert sum(1 for x in rows if x["event"] == "KILL") == 1
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})


# ------------------------------------------------------------------ M1: corrupt -> quarantine
def test_fold_itself_refuses_a_corrupt_ledger(paths) -> None:
    good = json.dumps({"event": "KILL", "cell": "a", "family": "jump"})
    for bad in ('{"event": "KILL", "cell": "b", "fam', "<<<<<<< HEAD", json.dumps({"cell": "a"})):
        jp.VERDICTS.write_text(f"{good}\n{bad}\n")
        with pytest.raises(jp.KillLedgerCorrupt):
            jp.fold_ledger()


def _quarantined(paths) -> list[Path]:
    return sorted(paths.glob("prescreen_verdicts.corrupt-*.jsonl"))


def _defects(paths) -> list[dict]:
    p = paths / "events.jsonl"
    rows = [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
    return [r for r in rows if r.get("kind") == "PLUMBING_DEFECT"]


def test_a_truncated_tail_is_quarantined_and_charged_as_an_upper_bound(paths) -> None:
    original = (
        json.dumps({"event": "KILL", "cell": "a", "family": "jump"})
        + "\n"
        + '{"event": "KILL", "cell": "b", "fam'
    )
    jp.VERDICTS.write_text(original)
    n, fam = jp.lifetime_kills()
    assert n == 2  # a + the unreadable line (it names b): never 1, never a silent 0
    (q,) = _quarantined(paths)
    assert q.read_text() == original  # kept byte-for-byte
    assert jp.fold_ledger()["b"]["charged"] is True and jp.fold_ledger()["b"]["killed"] is False
    (d,) = _defects(paths)
    assert d["producer"] == "judge_prescreen" and d["evidence"]["unreadable_lines_charged"] == 1
    assert jp.lifetime_kills() == (n, fam)  # stable: the rebuilt ledger reads clean


def test_a_garbled_line_naming_no_cell_is_still_one_trial(paths) -> None:
    good = json.dumps({"event": "KILL", "cell": "a", "family": "jump"})
    jp.VERDICTS.write_text(f"{good}\n\x00\x00garbage\n")
    assert jp.lifetime_kills()[0] == 2


def test_conflict_markers_are_dropped_and_both_sides_kept(paths) -> None:
    a = json.dumps({"event": "KILL", "cell": "a", "family": "jump"})
    b = json.dumps({"event": "KILL", "cell": "b", "family": "jump"})
    jp.VERDICTS.write_text(f"<<<<<<< HEAD\n{a}\n=======\n{b}\n>>>>>>> other\n")
    assert jp.lifetime_kills() == (2, {"jump": 2})
    assert (
        len(_quarantined(paths)) == 1
        and _defects(paths)[0]["evidence"]["conflict_marker_lines"] == 3
    )


def test_a_foreign_row_is_charged_not_dropped(paths) -> None:
    jp.VERDICTS.write_text(json.dumps({"cell": "a"}) + "\n")
    assert jp.lifetime_kills()[0] == 1


def test_a_writer_mid_append_is_not_quarantined(paths, monkeypatch) -> None:
    good = json.dumps({"event": "KILL", "cell": "a", "family": "jump"})
    jp.VERDICTS.write_text(good + "\n" + '{"event": "KI')
    real = jp._fold_or_quarantine_locked

    def writer_finished(p):  # the lock is taken only after the writer completes its line
        p.write_text(good + "\n" + json.dumps({"event": "KILL", "cell": "b"}) + "\n")
        return real(p)

    monkeypatch.setattr(jp, "_fold_or_quarantine_locked", writer_finished)
    assert jp.lifetime_kills()[0] == 2 and not _quarantined(paths) and not _defects(paths)


def test_a_failed_quarantine_raises_never_counts_zero(paths, monkeypatch) -> None:
    jp.VERDICTS.write_text('{"event": "KILL", "cell": "b", "fam')

    def boom(*_a, **_k):
        raise OSError("read-only")

    monkeypatch.setattr(jp, "quarantine", boom)
    with pytest.raises(OSError):
        jp.lifetime_kills()


def test_read_time_join_is_against_the_graph_experiment_ledger_counts(paths) -> None:
    jp.VERDICTS.write_text(
        "\n".join(
            json.dumps(x)
            for x in (
                {"event": "KILL", "cell": "a", "family": "jump"},
                {"event": "READMIT", "cell": "a", "family": "jump"},
                {"event": "KILL", "cell": "z", "family": "jump"},
                {"event": "KILL", "cell": "n", "family": "jump"},
                {"event": "READMIT", "cell": "n", "family": "jump"},
            )
        )
        + "\n"
    )
    assert jp.lifetime_kills() == (3, {"jump": 3})
    jp.LEDGER.write_text(
        "\n".join(
            json.dumps(x)
            for x in (
                # `a` judged and in the graph; `n` judged with no joinable spec (no graph id);
                # `z` only a NOT_RUN gate-1 reject -- which the graph recorded as FAILED
                {"cell": "a", "graph_id": "ga", "terminal_gate": "in_sample_screen"},
                {"cell": "n", "graph_id": "", "terminal_gate": "in_sample_screen"},
                {"cell": "z", "graph_id": "gz", "passed": None, "downstream_status": "NOT_RUN_G1"},
            )
        )
        + "\n"
    )
    _graph(paths, {"id": "ga", "fate": "BORN"}, {"id": "ga", "fate": "FAILED"})
    _graph(paths, {"id": "gz", "fate": "FAILED"})
    # a: graph counts it -> 0 here, at once, before any intake writes JUDGED
    # n: ruled in the gate ledger but no graph fate -> STILL charged (a gate join would deflate)
    # z: NOT_RUN-only yet the graph counts it -> NOT charged (a gate join would inflate)
    assert jp.lifetime_kills() == (1, {"jump": 1})
    assert jp.judge_ruled({"a", "z", "n", "q"}) == {"a", "n"}
    _graph(paths, {"id": "ga", "fate": ""})  # the latest row wins, as in experiment_ledger
    assert jp.lifetime_kills() == (2, {"jump": 2})


def test_an_unreadable_graph_leaves_every_charge_standing(paths) -> None:
    jp.VERDICTS.write_text(json.dumps({"event": "KILL", "cell": "a", "graph_id": "ga"}) + "\n")
    jp.GRAPH.mkdir()  # reading a directory raises
    assert jp.lifetime_kills()[0] == 1


def test_the_counted_fates_are_experiment_ledgers_own() -> None:
    from libs.research import experiment_ledger as el

    assert jp.GRAPH_COUNTED_FATES == el.GRAPH_COUNTED_FATES


def test_graph_fates_slices_rows_and_parses_others(paths) -> None:
    _graph(paths, {"id": "a1", "fate": "FAILED", "params": {"fate": "decoy"}})
    with jp.GRAPH.open("a") as fh:
        fh.write(json.dumps({"fate": "CERTIFIED", "id": "b2"}) + "\n")
    assert jp.graph_fates() == {"a1": "FAILED", "b2": "CERTIFIED"}
    assert jp.graph_fates({"b2"}) == {"b2": "CERTIFIED"}


def test_the_report_measures_how_far_the_two_sources_disagree(paths) -> None:
    jp.LEDGER.write_text(
        "\n".join(
            json.dumps(x)
            for x in (
                {"cell": "a", "graph_id": "ga", "terminal_gate": "in_sample_screen"},
                {"cell": "n", "graph_id": "", "terminal_gate": "in_sample_screen"},
                {"cell": "z", "graph_id": "gz", "passed": None, "downstream_status": "NOT_RUN_G1"},
                {"cell": "w", "graph_id": "gw", "passed": None, "downstream_status": "NOT_RUN_X"},
            )
        )
        + "\n"
    )
    _graph(paths, {"id": "ga", "fate": "FAILED"}, {"id": "gz", "fate": "FAILED"})
    cmp = jp.trial_source_comparison()
    assert cmp["status"] == "MEASURED" and cmp["cells"] == 4 and cmp["pending_graph_read"] == 0
    assert cmp["both"] == 1 and cmp["gate_ruled_not_graph_counted"] == 1
    assert cmp["graph_counted_not_gate_ruled"] == 1 and cmp["neither"] == 1
    assert cmp["sample_gate_only"] == ["n"] and cmp["sample_graph_only"] == ["z"]
    assert cmp["cells_without_graph_id"] == 1


# ------------------------------------------------------------------ v1.3 must-fix: nested fates
def _decoys(paths) -> None:
    # the auditor's two rows: a params decoy over a real BORN, and a null top-level fate with a
    # nested FAILED in gates -- experiment_ledger reads BORN and "" for them: neither is counted
    _graph(
        paths,
        {"id": "gp", "params": {"source": "x", "fate": "CERTIFIED"}, "fate": "BORN"},
        {"id": "gn", "fate": None, "gates": {"g1": {"passed": False, "fate": "FAILED"}}},
    )


def test_graph_fates_read_only_the_top_level_fate(paths) -> None:
    _decoys(paths)
    assert jp.graph_fates({"gp", "gn"}) == {"gp": "BORN", "gn": ""}
    assert jp.graph_fates() == {"gp": "BORN", "gn": ""}


def test_nested_fates_never_uncharge_a_cell(paths) -> None:
    _decoys(paths)
    jp.VERDICTS.write_text(
        json.dumps({"event": "KILL", "cell": "p", "family": "jump", "graph_id": "gp"})
        + "\n"
        + json.dumps({"event": "KILL", "cell": "n", "family": "jump", "graph_id": "gn"})
        + "\n"
    )
    assert jp.lifetime_kills() == (2, {"jump": 2})  # both stay charged


def test_graph_fates_match_experiment_ledgers_reading(paths, monkeypatch) -> None:
    from libs.research import experiment_ledger as el
    from libs.research import hypothesis_graph as hg

    _decoys(paths)
    _graph(paths, {"id": "gf", "fate": "FAILED"}, {"id": "gc", "fate": "CERTIFIED"})
    monkeypatch.setattr(hg, "LEDGER", jp.GRAPH)
    monkeypatch.setattr(el, "DESK", paths)  # its count cache lands in tmp
    total, _ = el._graph_counts()
    fates = jp.graph_fates()
    assert total == sum(1 for f in fates.values() if f in jp.GRAPH_COUNTED_FATES) == 2


# ------------------------------------------------------------------ v1.3 watch: bounded sources
def _sources_world(paths) -> None:
    jp.LEDGER.write_text(
        "\n".join(
            json.dumps(x)
            for x in (
                {"cell": "a", "graph_id": "ga", "terminal_gate": "in_sample_screen"},
                {"cell": "n", "graph_id": "", "terminal_gate": "in_sample_screen"},
                {"cell": "z", "graph_id": "gz", "passed": None, "downstream_status": "NOT_RUN_G1"},
                {"cell": "w", "graph_id": "gw", "passed": None, "downstream_status": "NOT_RUN_X"},
            )
        )
        + "\n"
    )
    _graph(paths, {"id": "ga", "fate": "FAILED"}, {"id": "gz", "fate": "FAILED"})


_COUNTS = ("cells", "both", "gate_ruled_not_graph_counted", "graph_counted_not_gate_ruled")


def test_sources_converge_under_a_tiny_budget_and_never_read_partial_as_zero(paths) -> None:
    _sources_world(paths)
    full = jp.trial_source_comparison(state_path=paths / "full.json")
    assert full["status"] == "MEASURED" and full["provisional"] is False
    seen = []
    for _ in range(12):
        r = jp.trial_source_comparison(max_lines=1)
        seen.append(r)
        if r["status"] == "MEASURED":
            break
    assert seen[0]["status"] == "PARTIAL" and seen[0]["provisional"] is True
    assert seen[0]["coverage"]["gate_bytes_read"] < seen[0]["coverage"]["gate_bytes"]
    assert seen[-1]["status"] == "MEASURED"
    assert {k: seen[-1][k] for k in _COUNTS} == {k: full[k] for k in _COUNTS}
    assert all("seconds" in r and "coverage" in r for r in seen)


def test_a_zero_budget_reports_partial_coverage_honestly(paths) -> None:
    _sources_world(paths)
    jp.trial_source_comparison(max_lines=4)  # the gate ledger only; no graph line read yet
    r = jp.trial_source_comparison(budget_s=0.0, max_lines=0)
    assert r["status"] == "PARTIAL"
    assert r["coverage"]["graph_bytes_read"] == 0 < r["coverage"]["graph_bytes"]
    # with no graph row read, every cell holding a graph id is PENDING -- not a gap, not a 0;
    # only `n` (no graph id at all) is already knowable as a deflation case
    assert r["pending_graph_read"] == 3 and r["gate_ruled_not_graph_counted"] == 1
    assert r["both"] == 0 and r["graph_counted_not_gate_ruled"] == 0 and r["provisional"] is True
    for _ in range(12):  # each partial pass is a subset of the truth, never a contradiction
        r = jp.trial_source_comparison(max_lines=1)
        assert r["gate_ruled_not_graph_counted"] <= 1 and r["graph_counted_not_gate_ruled"] <= 1


def test_sources_read_only_deltas_and_backfill_ids_seen_late(paths) -> None:
    _sources_world(paths)
    first = jp.trial_source_comparison()
    assert first["status"] == "MEASURED" and first["both"] == 1
    # a NEW gate row names `gb`, whose graph row was already passed (before the checkpoint),
    # and `ga` gets a newer non-counted fate in the graph delta
    with jp.LEDGER.open("a") as fh:
        fh.write(json.dumps({"cell": "b", "graph_id": "gb", "terminal_gate": "UNKNOWN"}) + "\n")
    lines = jp.GRAPH.read_text().splitlines()
    jp.GRAPH.write_text(
        "\n".join([json.dumps({"id": "gb", "fate": "JUDGED"}), *lines]) + "\n"
    )  # rewritten head: a full re-read, still correct
    again = jp.trial_source_comparison()
    assert "graph" in again["coverage"]["reset_this_pass"] and again["both"] == 2
    _graph(paths, {"id": "gb2", "fate": "FAILED"})  # appended: read as a delta, head unchanged
    with jp.LEDGER.open("a") as fh:
        fh.write(json.dumps({"cell": "c", "graph_id": "gb2", "terminal_gate": "UNKNOWN"}) + "\n")
    with jp.LEDGER.open("a") as fh:
        fh.write(json.dumps({"cell": "d", "graph_id": "gz", "terminal_gate": "UNKNOWN"}) + "\n")
    delta = jp.trial_source_comparison()
    assert delta["coverage"]["reset_this_pass"] == []
    assert delta["status"] == "MEASURED" and delta["both"] == 4  # a, b, c (backfilled), d


def test_a_newer_delta_fate_beats_the_backfill(paths) -> None:
    _sources_world(paths)
    jp.trial_source_comparison()
    with jp.LEDGER.open("a") as fh:  # `gq` is seen late; its OLD row says FAILED...
        fh.write(json.dumps({"cell": "q", "graph_id": "gq", "terminal_gate": "UNKNOWN"}) + "\n")
    lines = jp.GRAPH.read_text().splitlines()
    head, rest = lines[0], lines[1:]
    # gq's old row goes into the already-read prefix; the checkpoint is faked to match below
    jp.GRAPH.write_text("\n".join([head, json.dumps({"id": "gq", "fate": "FAILED"}), *rest]) + "\n")
    st = json.loads(jp.SOURCES_STATE.read_text())
    st["graph"] = jp._part_stamp(jp.GRAPH, jp.GRAPH.stat().st_size)  # as if all of it was read
    jp.SOURCES_STATE.write_text(json.dumps(st))
    started = jp.trial_source_comparison(max_lines=1)  # reads q, opens the backfill, no more
    assert started["status"] == "PARTIAL" and started["pending_graph_read"] == 1
    assert json.loads(jp.SOURCES_STATE.read_text())["backfill"]["ids"] == ["gq"]
    _graph(paths, {"id": "gq", "fate": "BORN"})  # ...and a NEWER delta row says BORN
    r = jp.trial_source_comparison()
    assert r["status"] == "MEASURED"
    st = json.loads(jp.SOURCES_STATE.read_text())
    assert st["fates"]["gq"] == "BORN"  # the backfill's older FAILED never overwrote it


def _big_gate(n: int = 300) -> list[str]:
    """A gate ledger well past the 4 KiB head, so a change beyond it is not a head change."""
    return [
        json.dumps({"cell": f"c{i:04d}", "graph_id": f"g{i:04d}", "terminal_gate": "UNKNOWN"})
        for i in range(n)
    ]


def test_a_same_size_rewrite_beyond_the_head_rereads_from_zero(paths) -> None:
    lines = _big_gate()
    jp.LEDGER.write_text("\n".join(lines) + "\n")
    _graph(paths, {"id": "g0250", "fate": "FAILED"})
    first = jp.trial_source_comparison()
    assert first["status"] == "MEASURED" and first["both"] == 1
    before = jp.LEDGER.stat()
    # rewrite row 250 IN PLACE, same length: its graph id now names no graph node
    lines[250] = lines[250].replace('"g0250"', '"h0250"')
    jp.LEDGER.write_text("\n".join(lines) + "\n")
    os.utime(jp.LEDGER, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
    assert jp.LEDGER.stat().st_size == before.st_size
    again = jp.trial_source_comparison()
    assert "gate" in again["coverage"]["reset_this_pass"]
    assert again["status"] == "MEASURED" and again["both"] == 0  # the stale fate is gone


def test_a_truncate_then_grow_past_the_old_offset_rereads_from_zero(paths) -> None:
    lines = _big_gate()
    jp.LEDGER.write_text("\n".join(lines) + "\n")
    _graph(paths, {"id": "g0250", "fate": "FAILED"}, {"id": "g9999", "fate": "FAILED"})
    assert jp.trial_source_comparison()["both"] == 1
    # truncate to 200 rows (the head is unchanged), then grow PAST the old offset with others
    new = lines[:200] + [
        json.dumps({"cell": f"x{i:04d}", "graph_id": "g9999", "terminal_gate": "UNKNOWN"})
        for i in range(150)
    ]
    jp.LEDGER.write_text("\n".join(new) + "\n")
    again = jp.trial_source_comparison()
    assert "gate" in again["coverage"]["reset_this_pass"]
    assert again["cells"] == 350 and again["both"] == 150  # c0250 is gone; the x rows count


def test_an_append_alone_is_never_a_reset(paths) -> None:
    jp.LEDGER.write_text("\n".join(_big_gate()) + "\n")
    _graph(paths, {"id": "g0001", "fate": "FAILED"})
    jp.trial_source_comparison()
    with jp.LEDGER.open("a") as fh:
        fh.write(
            json.dumps({"cell": "new", "graph_id": "g0001", "terminal_gate": "UNKNOWN"}) + "\n"
        )
    _graph(paths, {"id": "g0002", "fate": "FAILED"})
    r = jp.trial_source_comparison()
    assert r["coverage"]["reset_this_pass"] == [] and r["both"] == 3


@pytest.mark.parametrize(
    "bad",
    [
        {"cells": []},
        {"gate_offset": "x"},
        {"fates": {"a": 1}},
        {"pending": "x"},
        {"backfill": {"ids": ["a"], "cursor": "x", "end": 0, "found": {}, "newer": []}},
        {"cell_entry": ["bad"]},
        "not a dict",
    ],
)
def test_a_checkpoint_with_bad_types_is_discarded_never_raised(paths, bad) -> None:
    _sources_world(paths)
    jp.trial_source_comparison()
    st = json.loads(jp.SOURCES_STATE.read_text())
    if bad == "not a dict":
        st = [1, 2]
    elif "gate_offset" in bad:
        st["gate"]["offset"] = "x"
    elif "cell_entry" in bad:
        st["cells"]["a"] = bad["cell_entry"]
    else:
        st.update(bad)
    jp.SOURCES_STATE.write_text(json.dumps(st))
    r = jp.trial_source_comparison()
    assert r["coverage"]["reset_this_pass"][0] == "invalid_checkpoint"
    assert r["status"] == "MEASURED" and r["both"] == 1


def test_run_once_never_fails_the_leg_on_the_sources_measurement(paths, tmp_path, monkeypatch):
    led = tmp_path / "ledger.jsonl"
    led.write_text(json.dumps(_row("E.carry.p=1", "in_sample_screen")) + "\n")
    monkeypatch.setattr(jp, "_probe_fn", lambda: None)

    def boom(*_a, **_k):
        raise TypeError("list indices must be integers")

    monkeypatch.setattr(jp, "trial_source_comparison", boom)
    doc = jp.run_once(led, tmp_path / "out", tmp_path / "no_universe")
    src = doc["trials"]["sources"]
    assert src["status"] == "UNMEASURED" and "TypeError" in src["why"]


def test_an_unreadable_source_is_unmeasured_not_zero(paths) -> None:
    r = jp.trial_source_comparison()
    assert r["status"] == "UNMEASURED" and "both" not in r


# ------------------------------------------------------------------ v1.2 should-fix: no silent 0
def test_a_failed_rebuild_leaves_the_original_ledger_in_place(paths) -> None:
    original = '{"event": "KILL", "cell": "b", "fam'
    jp.VERDICTS.write_text(original)
    (paths / "prescreen_verdicts.jsonl.tmp").mkdir()  # the rebuild cannot be written
    with pytest.raises(OSError):
        jp.lifetime_kills()
    assert jp.VERDICTS.read_text() == original and not _quarantined(paths)
    with pytest.raises(OSError):  # the next read refuses again -- never (0, {})
        jp.lifetime_kills()
    (paths / "prescreen_verdicts.jsonl.tmp").rmdir()
    assert jp.lifetime_kills()[0] == 1 and len(_quarantined(paths)) == 1


def test_an_absent_ledger_beside_a_quarantined_copy_refuses_and_alerts(paths) -> None:
    (paths / "prescreen_verdicts.corrupt-20261028T000000Z.jsonl").write_text("garbage\n")
    with pytest.raises(jp.KillLedgerLost):
        jp.lifetime_kills()
    assert _defects(paths)[-1]["evidence"]["defect"].startswith("kill ledger absent")
    kill = {EV: {"rule": "needs_data", "row": _docket()[1], "evidence": {}}}
    with pytest.raises(jp.KillLedgerLost):  # the writer refuses too: intake then fails open
        jp.reconcile_and_kill(kill, {EV}, set())


def test_experiment_ledger_charges_once_and_never_deflates(paths) -> None:
    from libs.research import experiment_ledger as el

    jp.VERDICTS.write_text(
        "\n".join(
            json.dumps(x)
            for x in (
                {"event": "KILL", "cell": "a", "family": "jump"},
                {"event": "KILL", "cell": "b", "family": "jump"},
                {"event": "READMIT", "cell": "b", "family": "jump"},
                {"event": "KILL", "cell": "c", "family": "jump", "graph_id": "gc"},
                {"event": "JUDGED", "cell": "c", "family": "jump"},
            )
        )
        + "\n"
    )
    assert el._prescreen_counts() == (3, {"jump": 3})  # c judged, but no graph fate yet
    _graph(paths, {"id": "gc", "fate": "JUDGED"})
    assert el._prescreen_counts() == (2, {"jump": 2})
    with jp.VERDICTS.open("a") as fh:
        fh.write("<<<<<<< HEAD\n")
    assert el._prescreen_counts() == (2, {"jump": 2})  # quarantined: same count, not 0
    assert len(_quarantined(paths)) == 1


# ------------------------------------------------------------------ fail open, priority, wiring
def test_intake_fails_open_even_on_systemexit(paths) -> None:
    t, r = _files(paths, _tables(), _report())

    def leave(_s, _f):
        raise SystemExit(3)

    rows = _docket()
    out, doc = jp.intake(
        rows,
        cell_of=lambda x: x["_cell"],
        probe=leave,
        tables_path=t,
        report_path=r,
        ruled=set(),
        canon=True,
    )
    assert out is rows and doc["mode"] == "UNMEASURED"


def test_below_normal_says_whether_it_took() -> None:
    got = jp._below_normal()
    assert isinstance(got.get("applied"), bool) and got.get("how")


def test_report_carries_priority_trials_and_a_two_sided_missed_growth_line(
    paths, tmp_path, monkeypatch
) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text(
        "\n".join(json.dumps(_row(f"E.carry.p={i}", "in_sample_screen")) for i in range(8)) + "\n"
    )
    monkeypatch.setattr(jp, "_probe_fn", lambda: None)
    out = tmp_path / "out"
    doc = jp.run_once(led, out, tmp_path / "no_universe", priority={"applied": True})
    assert doc["mode"] == "SHADOW" and doc["priority"] == {"applied": True}
    assert [x["side"] for x in doc["missed_growth"]] == ["cost", "gain"]
    assert doc["missed_growth"][0]["would_act_sibling_dead"]["true_survivors_killed"] == 0
    assert doc["sibling_dead"]["canon_eligible_in_code"] is False
    assert (out / "JUDGE_PRESCREEN.json").exists()


def test_the_screen_is_wired_and_scheduled() -> None:
    cyc = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("judge_prescreen"' in cyc and '"judge_prescreen": 600' in cyc
    assert '"judge_prescreen":' in (ROOT / "libs" / "research" / "layers.py").read_text("utf-8")
    cov = (DESK / "research" / "judge_coverage.py").read_text("utf-8")
    assert 'rows, doc["prescreen"] = _prescreen(' in cov and "ruled=ruled" in cov
    assert "except (Exception, SystemExit) as exc:" in cov
    led = (ROOT / "libs" / "research" / "experiment_ledger.py").read_text("utf-8")
    assert "_prescreen_counts()" in led
    gi = (ROOT / ".gitignore").read_text("utf-8")
    assert "!desks/mt5/reports/JUDGE_PRESCREEN.json" in gi
    assert "!desks/mt5/reports/JUDGE_PRESCREEN_INTAKE.json" in gi
    ps1 = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/reports/JUDGE_PRESCREEN.json"' in ps1


def test_no_sealed_file_imports_or_names_the_screen() -> None:
    manifest = json.loads((DESK / "data" / "IMMUTABLE_MANIFEST.json").read_text("utf-8"))
    for rel in manifest["files"]:
        p = ROOT / rel
        if p.exists():
            assert "judge_prescreen" not in p.read_text("utf-8", errors="replace"), rel
