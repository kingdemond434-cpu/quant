"""The judge's pre-build screen: shadow by default, trial-honest, canon only on measured evidence.

    python -m pytest desks/mt5/tests/test_judge_prescreen.py -q
"""
from __future__ import annotations

import json
import sys
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
    return tmp_path


def _row(cell: str, gate: str, passed: bool | None = False, ds: str | None = None) -> dict:
    return {"cell": cell, "terminal_gate": gate, "passed": passed, "downstream_status": ds}


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


def test_replay_screens_each_cell_on_the_evidence_before_its_first_verdict() -> None:
    dead = [_row(f"EURUSD.carry.p={i:04d}", "in_sample_screen") for i in range(6)]
    # judged after six in-sample failures: a K=5 screen kills it, and it later PASSES
    late = [_row("EURUSD.carry.p=late", "UNKNOWN", None), _row("EURUSD.carry.p=late", "", True)]
    rp = jp.replay([*dead, *late], k_grid=(5, 10))
    k5 = rp["by_k"]["5"]
    # the sixth failure (5 named before it) and the late survivor are both killed at K=5
    assert k5["killed"] == 2 and k5["killed_by_tier"]["true_survivor"] == 1
    assert k5["killed_by_tier"]["in_sample_fail"] == 1
    assert rp["by_k"]["10"]["killed"] == 0
    # one true survivor is below MIN_TRUE_SURVIVORS: no K can be called safe
    assert rp["canon_k"] is None and rp["canon_ready"] is False
    # the bucket cleared once the survivor landed, so it is not dead any more
    assert "EURUSD|H1|carry" not in rp["dead_buckets"]


def test_a_bucket_that_ever_cleared_in_sample_is_never_dead() -> None:
    rows = [_row("GBPUSD.carry.p=x", "deflated_sharpe")]
    rows += [_row(f"GBPUSD.carry.p={i}", "in_sample_screen") for i in range(50)]
    rows += [_row("GBPUSD.carry.p=new", "in_sample_screen")]
    rp = jp.replay(rows, k_grid=(5,))
    assert rp["by_k"]["5"]["killed"] == 0


def test_protected_buckets_are_never_killed() -> None:
    rows = [_row(f"XAUUSD.session_range_breakout.p={i}", "in_sample_screen") for i in range(30)]
    rp = jp.replay(rows, k_grid=(5,), protected={"XAUUSD|H1|session_range_breakout"})
    assert rp["by_k"]["5"]["killed"] == 0 and not rp["dead_buckets"]


def test_canon_k_needs_zero_true_survivor_kills_in_both_halves(monkeypatch) -> None:
    monkeypatch.setattr(jp, "MIN_TRUE_SURVIVORS", 2)
    rows = []
    for b in range(4):   # four buckets each with a survivor first, so none is ever dead
        rows.append(_row(f"S{b}.carry.p=win", "", True))
        rows += [_row(f"S{b}.carry.p={i}", "in_sample_screen") for i in range(12)]
    rows += [_row(f"DEAD.carry.p={i}", "in_sample_screen") for i in range(30)]
    rp = jp.replay(rows, k_grid=(5, 10))
    assert rp["population_by_tier"]["true_survivor"] == 4
    assert rp["canon_k"] == 5
    assert rp["by_k"]["5"]["killed_by_tier"]["true_survivor"] == 0
    assert rp["by_k"]["5"]["killed"] == 25


def test_chart_short_is_a_proof_with_a_clock_margin() -> None:
    assert jp.chart_is_short({"utc_days": 29, "span_days": 400})       # 2 x 29 = 58 < 60
    assert not jp.chart_is_short({"utc_days": 30, "span_days": 400})   # 60 dates possible
    assert jp.chart_is_short({"utc_days": 200, "span_days": 50})       # span 50 + 2 < 60
    assert not jp.chart_is_short(None)                                  # unknown escalates
    assert not jp.chart_is_short({"utc_days": "x"})


def test_rule_classes_match_the_separability_harness() -> None:
    # test_fire_prescreen_not_separable: only an empty series is separable
    assert jp.RULES["needs_data"]["canon_eligible"] is True
    assert jp.RULES["chart_short"]["canon_eligible"] is False
    assert jp.RULES["sibling_dead"]["class"] == "STATISTICAL"


def _tables(dead=None, charts=None) -> dict:
    return {"charts": charts or {"EURUSD|H1": {"utc_days": 2000, "span_days": 2900},
                                 "XAUUSD|M1": {"utc_days": 20, "span_days": 25}},
            "dead_buckets": dead or {}, "protected_buckets": []}


def _report(canon_k=None, ready=False, age_h=0.0) -> dict:
    at = (datetime.now(UTC) - timedelta(hours=age_h)).isoformat(timespec="seconds")
    return {"generated_at": at, "sibling_dead": {"canon_k": canon_k, "canon_ready": ready}}


def _docket() -> list[dict]:
    return [
        {"_cell": "EURUSD.carry.p=1", "symbol": "EURUSD", "family": "carry", "params": {}},
        {"_cell": "EURUSD.event_reaction.p=2", "symbol": "EURUSD", "family": "event_reaction",
         "params": {}},
        {"_cell": "XAUUSD@M1.formula.p=3", "symbol": "XAUUSD", "family": "formula",
         "params": {"timeframe": "M1"}},
        {"_cell": "EURUSD.jump.p=4", "symbol": "EURUSD", "family": "jump", "params": {}},
    ]


def _probe(sym, fam):
    return {"status": "NEEDS_DATA", "missing_input": "bar_clock"} if fam == "event_reaction" \
        else {"status": "UNMEASURED"}


def _write(tmp: Path, tables: dict, report: dict, canon: bool) -> tuple[Path, Path, Path]:
    t, r, s = tmp / "tables.json", tmp / "report.json", tmp / "switch.json"
    t.write_text(json.dumps(tables))
    r.write_text(json.dumps(report))
    s.write_text(json.dumps({"enabled": canon}))
    return t, r, s


def test_shadow_returns_every_row_and_counts_what_it_would_kill(paths) -> None:
    t, r, s = _write(paths, _tables(dead={"EURUSD|H1|jump": 50}), _report(), canon=False)
    rows = _docket()
    out, doc = jp.intake(rows, cell_of=lambda x: x["_cell"], probe=_probe,
                         tables_path=t, report_path=r, switch=s)
    assert out is rows and len(out) == 4
    assert doc["mode"] == "SHADOW" and doc["removed_from_docket"] == 0
    assert doc["would_kill"] == {"needs_data": 1, "chart_short": 1, "sibling_dead": 1}
    # with no canon K yet, shadow counts at the most aggressive K and reports every K
    assert doc["sibling_k"] == min(jp.K_GRID)
    assert doc["sibling_would_kill_by_k"] == {"5": 1, "10": 1, "20": 1, "40": 1, "80": 0}
    assert not jp.VERDICTS.exists()                         # shadow writes no trial
    assert jp.lifetime_kills() == (0, {})


def test_canon_removes_only_ready_rules_and_records_each_kill_as_one_trial(paths) -> None:
    t, r, s = _write(paths, _tables(dead={"EURUSD|H1|jump": 50}),
                     _report(canon_k=40, ready=True), canon=True)
    out, doc = jp.intake(_docket(), cell_of=lambda x: x["_cell"], probe=_probe,
                         tables_path=t, report_path=r, switch=s)
    kept = {x["_cell"] for x in out}
    # needs_data (proven) and sibling_dead (canon-ready) leave; chart_short NEVER does
    assert kept == {"EURUSD.carry.p=1", "XAUUSD@M1.formula.p=3"}
    assert doc["rule_acts"] == {"needs_data": True, "chart_short": False, "sibling_dead": True}
    n, fam = jp.lifetime_kills()
    assert n == 2 and fam == {"event_reaction": 1, "jump": 1}
    rows = [json.loads(x) for x in jp.VERDICTS.read_text().splitlines()]
    assert {x["verdict"] for x in rows} == {"PRESCREEN_UNKNOWN", "PRESCREEN_REJECT"}
    assert all(x["event"] == "KILL" and x["evidence"] for x in rows)
    # a second identical pass appends nothing (one trial per cell, never two)
    jp.intake(_docket(), cell_of=lambda x: x["_cell"], probe=_probe,
              tables_path=t, report_path=r, switch=s)
    assert len(jp.VERDICTS.read_text().splitlines()) == 2
    # the bucket clears: the cell is READMITTED and stops counting, the judge's fate replaces it
    t.write_text(json.dumps(_tables(dead={})))
    out2, doc2 = jp.intake(_docket(), cell_of=lambda x: x["_cell"], probe=_probe,
                           tables_path=t, report_path=r, switch=s)
    assert "EURUSD.jump.p=4" in {x["_cell"] for x in out2}
    assert doc2["ledger"]["readmitted"] == 1
    assert jp.lifetime_kills() == (1, {"event_reaction": 1})


def test_sibling_rule_never_acts_on_a_stale_or_unready_report(paths) -> None:
    for rep in (_report(canon_k=None, ready=False), _report(canon_k=40, ready=True, age_h=7)):
        t, r, s = _write(paths, _tables(dead={"EURUSD|H1|jump": 500}), rep, canon=True)
        out, doc = jp.intake(_docket(), cell_of=lambda x: x["_cell"], probe=None,
                             tables_path=t, report_path=r, switch=s)
        assert "EURUSD.jump.p=4" in {x["_cell"] for x in out}
        assert doc["rule_acts"]["sibling_dead"] is False


def test_needs_data_needs_bars_on_the_chart(paths) -> None:
    # no bars: the judge's build fails BY NAME and asks for them (judge_coverage keeps it live)
    t, r, s = _write(paths, _tables(charts={"XAUUSD|M1": {"utc_days": 20, "span_days": 25}}),
                     _report(), canon=True)
    out, doc = jp.intake(_docket(), cell_of=lambda x: x["_cell"], probe=_probe,
                         tables_path=t, report_path=r, switch=s)
    assert doc["would_kill"]["needs_data"] == 0
    assert "EURUSD.event_reaction.p=2" in {x["_cell"] for x in out}


def test_intake_fails_open(paths) -> None:
    rows = _docket()

    def boom(_):
        raise RuntimeError("x")
    out, doc = jp.intake(rows, cell_of=boom, probe=None, tables_path=paths / "none.json",
                         report_path=paths / "none2.json", switch=paths / "none3.json")
    assert out is rows and doc["removed_from_docket"] == 0


def test_an_unreadable_kill_ledger_is_never_counted_as_zero(paths) -> None:
    jp.VERDICTS.mkdir()          # exists, cannot be read as a file
    with pytest.raises(OSError):
        jp.lifetime_kills()


def test_experiment_ledger_charges_each_standing_kill_once(paths, monkeypatch) -> None:
    from libs.research import experiment_ledger as el
    jp.VERDICTS.write_text("\n".join(json.dumps(x) for x in (
        {"event": "KILL", "cell": "a", "family": "jump"},
        {"event": "KILL", "cell": "b", "family": "jump"},
        {"event": "READMIT", "cell": "b", "family": "jump"})) + "\n")
    assert el._prescreen_counts() == (1, {"jump": 1})


def test_the_screen_is_wired_and_scheduled() -> None:
    cyc = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("judge_prescreen"' in cyc and '"judge_prescreen": 600' in cyc
    assert '"judge_prescreen":' in (ROOT / "libs" / "research" / "layers.py").read_text("utf-8")
    cov = (DESK / "research" / "judge_coverage.py").read_text("utf-8")
    assert "rows, doc[\"prescreen\"] = _prescreen(rows, publish=publish)" in cov
    led = (ROOT / "libs" / "research" / "experiment_ledger.py").read_text("utf-8")
    assert "_prescreen_counts()" in led


def test_no_sealed_file_imports_or_names_the_screen() -> None:
    manifest = json.loads((DESK / "data" / "IMMUTABLE_MANIFEST.json").read_text("utf-8"))
    for rel in manifest["files"]:
        p = ROOT / rel
        if p.exists():
            assert "judge_prescreen" not in p.read_text("utf-8", errors="replace"), rel
