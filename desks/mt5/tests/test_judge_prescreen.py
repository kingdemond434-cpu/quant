"""The judge's pre-build screen: shadow by default, charged exactly once, canon only as code.

python -m pytest desks/mt5/tests/test_judge_prescreen.py -q
"""

from __future__ import annotations

import json
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
    assert rp["at_risk_true_survivors"] == 1
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
    assert rp["at_risk_true_survivors"] == 0
    assert rp["canon_k"] is None and rp["canon_ready"] is False


def _at_risk_world(late_victim: bool) -> list[dict]:
    rows = []
    # eight at-risk survivors: each the FIRST verdict of its own fresh bucket (named 0 < K)
    for i in range(8):
        rows.append(_row(f"W{i}.carry.p=win", "", True))
        rows += [_row(f"D{i}.carry.p={j}", "in_sample_screen") for j in range(12)]
    if late_victim:  # a late survivor arriving in a bucket with 6 prior failures: K=5 kills it
        rows += [_row(f"LATE.carry.p={j}", "in_sample_screen") for j in range(6)]
        rows.append(_row("LATE.carry.p=win", "", True))
    return rows


def test_select_on_the_earlier_half_confirm_on_the_later(monkeypatch) -> None:
    monkeypatch.setattr(jp, "MIN_AT_RISK_PER_HALF", 4)
    clean = jp.replay(_at_risk_world(False), k_grid=(5, 10))
    assert clean["at_risk_true_survivors_by_half"] == {"select": 4, "confirm": 4}
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
    assert jp.lifetime_kills() == (0, {})  # the judge's fate carries the single trial
    assert EV in {x["_cell"] for x in out}
    _run(t, r, canon=True, ruled=set())  # even if the ruled set later misses it: never re-killed
    assert jp.lifetime_kills() == (0, {}) and jp.fold_ledger()[EV]["judged"] is True


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


# ------------------------------------------------------------------ M1: fail closed
def test_a_truncated_tail_raises(paths) -> None:
    jp.VERDICTS.write_text(
        json.dumps({"event": "KILL", "cell": "a", "family": "jump"})
        + "\n"
        + '{"event": "KILL", "cell": "b", "fam'
    )
    with pytest.raises(jp.KillLedgerCorrupt):
        jp.lifetime_kills()


def test_conflict_markers_raise(paths) -> None:
    good = json.dumps({"event": "KILL", "cell": "a", "family": "jump"})
    jp.VERDICTS.write_text(f"<<<<<<< HEAD\n{good}\n=======\n{good}\n>>>>>>> other\n")
    with pytest.raises(jp.KillLedgerCorrupt):
        jp.lifetime_kills()


def test_a_foreign_row_raises(paths) -> None:
    jp.VERDICTS.write_text(json.dumps({"cell": "a"}) + "\n")
    with pytest.raises(jp.KillLedgerCorrupt):
        jp.lifetime_kills()


def test_experiment_ledger_charges_once_and_fails_closed(paths) -> None:
    from libs.research import experiment_ledger as el

    jp.VERDICTS.write_text(
        "\n".join(
            json.dumps(x)
            for x in (
                {"event": "KILL", "cell": "a", "family": "jump"},
                {"event": "KILL", "cell": "b", "family": "jump"},
                {"event": "READMIT", "cell": "b", "family": "jump"},
                {"event": "KILL", "cell": "c", "family": "jump"},
                {"event": "JUDGED", "cell": "c", "family": "jump"},
            )
        )
        + "\n"
    )
    assert el._prescreen_counts() == (2, {"jump": 2})
    with jp.VERDICTS.open("a") as fh:
        fh.write("<<<<<<< HEAD\n")
    with pytest.raises(ValueError):
        el._prescreen_counts()


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
