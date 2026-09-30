"""Tier S layers that used to end in a report now act on a real path:

  S04  runtime blinding: the proposer doors (deepseek cold context, proposer_common.donate, the
       hypothesis compiler's read of data/intelligence/**) strip held-out / lockbox / forward /
       gate outcomes, count them per seat in a published ledger, and organ_market withholds a
       seat whose OUTPUT carried them from the independent-discovery count.
  S09  a kind that fools the certifier earns a defender rule in the pre-judge screen once its
       challenger survives the sealed trap suite.
  S21  an invented test proposed on one suite and confirmed on another is ratified by the
       machine into test_ratifications.jsonl and RUNS on candidates in the pre-judge screen.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.tiers import blinding, researcher_market  # noqa: E402
from libs.tiers import meta_benchmark as mb  # noqa: E402
from libs.tiers import prejudge_screen as pj  # noqa: E402
from libs.tiers import red_queen as rq  # noqa: E402
from libs.tiers import test_invention as ti  # noqa: E402

SMALL_SEALED = mb.Suite(per_kind=2, base_seed=5150, n=1200)


# ================================================================== S04 runtime blinding
def test_outcome_keys_are_stripped_at_any_depth_and_facts_kept() -> None:
    row = {"symbol": "EURUSD", "family": "carry", "t_stat": 3.1, "win_rate": 0.6,
           "survivor_metrics": {"sharpe": 1.2, "holdout_sharpe": 0.9},
           "evidence": [{"forward_exp_r": 0.2, "n": 40}, {"lockbox_result": "PASS"}],
           "gate_verdict": "passed", "forwardExpR": 1.0, "forward_guidance": "hawkish"}
    clean, gone = blinding.strip_outcomes(row)
    assert clean["survivor_metrics"] == {"sharpe": 1.2}
    assert clean["evidence"] == [{"n": 40}, {}]
    for k in ("gate_verdict", "forwardExpR"):
        assert k not in clean
    for k in ("symbol", "family", "t_stat", "win_rate", "forward_guidance"):
        assert k in clean                       # a source's own claims are facts
    assert len(gone) == 5 and "survivor_metrics.holdout_sharpe" in gone
    assert "holdout_sharpe" in row["survivor_metrics"]       # never mutates the input


def test_counter_counts_violations_per_seat_and_appends_the_ledger(tmp_path: Path) -> None:
    c = blinding.RuntimeCounter("compiler_read")
    c.filter("kimi", {"title": "x", "oos_sharpe": 1.0})
    c.filter("kimi", {"title": "y"})
    c.filter("cot", {"title": "z"})
    rep = c.publish(tmp_path, "tier_s/blinding_runtime.jsonl")
    assert rep["violations"] == 1 and rep["seats"]["kimi"]["rows_with_outcomes"] == 1
    assert rep["seats"]["kimi"]["keys"] == {"oos_sharpe": 1}
    lines = (tmp_path / "tier_s" / "blinding_runtime.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["stage"] == "compiler_read"


def test_the_compiler_reads_every_seat_row_blind(tmp_path: Path, monkeypatch: Any) -> None:
    import miner_candidate_compiler as mcc
    intel = tmp_path / "data" / "intelligence"
    (intel / "kimi").mkdir(parents=True)
    (intel / "kimi" / "discoveries_1.json").write_text(json.dumps({"discoveries": [
        {"title": "carry on EURUSD", "symbols": ["EURUSD"], "family": "carry",
         "forward_exp_r": 0.4, "evidence": {"holdout_t": 3.0, "in_sample_t": 2.5}}]}))
    monkeypatch.setattr(mcc, "INTEL_ROOTS", (intel,))
    monkeypatch.setattr(mcc, "CURSOR", tmp_path / "cursor.json")
    rows = mcc.recent_rows(datetime.now(UTC))
    assert rows, "the seat row must still be read (blinding strips, never drops)"
    _src, row = rows[0]
    assert "forward_exp_r" not in row and row["evidence"] == {"in_sample_t": 2.5}
    rep = mcc._BLIND.report()
    assert rep["seats"]["kimi"]["rows_with_outcomes"] == 1 and rep["violations"] == 1


def test_the_donate_door_strips_and_records_an_output_violation(tmp_path: Path,
                                                                monkeypatch: Any) -> None:
    import proposer_common as pc
    monkeypatch.setattr(pc, "INTEL", tmp_path / "data" / "intelligence")
    clean, note = pc._blinded("seat_x", [{"symbol": "XAUUSD", "family": "carry",
                                          "params": {}, "forward_n": 12, "t": 2.4}])
    assert clean == [{"symbol": "XAUUSD", "family": "carry", "params": {}, "t": 2.4}]
    assert note["violations"] == 1
    led = [json.loads(x) for x in (tmp_path / "data" / "tier_s" / "blinding_runtime.jsonl")
           .read_text().splitlines()]
    assert led[0]["stage"] == "output" and led[0]["seats"]["seat_x"]["rows_with_outcomes"] == 1


def test_the_llm_cold_context_is_blind_to_held_out_outcomes() -> None:
    from libs.ops.deepseek_cycle import cold_context
    out = cold_context({"survivor_metrics": {"sharpe": 1.2, "oos_sharpe": 0.4},
                        "lockbox_results": [1, 2], "portfolio_state": {}})
    assert out["cold_context"] == {"survivor_metrics": {"sharpe": 1.2}, "portfolio_state": {}}
    assert sorted(out["blinded_fields"]) == ["lockbox_results", "survivor_metrics.oos_sharpe"]


def test_market_withholds_a_seat_whose_output_carried_outcomes(tmp_path: Path,
                                                               monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    now = datetime.now(UTC)
    rows = [
        {"at": now.isoformat(), "stage": "output", "rows": 3, "violations": 1,
         "fields_stripped": 2, "seats": {"kimi": {"rows": 3, "rows_with_outcomes": 1}}},
        {"at": now.isoformat(), "stage": "context", "rows": 1, "violations": 1,
         "fields_stripped": 1, "seats": {"deepseek": {"rows": 1, "rows_with_outcomes": 1}}},
        # outside the window: forgotten
        {"at": (now - timedelta(hours=48)).isoformat(), "stage": "compiler_read", "rows": 1,
         "violations": 1, "seats": {"cot": {"rows": 1, "rows_with_outcomes": 1}}},
    ]
    (tmp_path / "blinding_runtime.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    rt = ts._runtime_blinding()
    assert rt["status"] == "MEASURED" and rt["violations"] == 2
    assert rt["output_violators"] == ["kimi"]          # a stripped CONTEXT is enforcement
    cohort = ts._epistemology("miner:kimi")
    assert sorted([cohort, "*"]) in rt["contaminated_pairs"]
    sight = [("kimi", "carry|fx"), ("cot_miner", "carry|fx")]
    cohorts = {"kimi": cohort, "cot_miner": "flow_positioning"}
    free = researcher_market.independent_discoveries(sight, cohorts, [])
    held = researcher_market.independent_discoveries(sight, cohorts, rt["contaminated_pairs"])
    assert free["independently_discovered"] == 1
    assert held["independently_discovered"] == 0 and held["withheld_by_blinding"] == 1


def test_no_ledger_is_unmeasured_not_clean(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    rt = ts._runtime_blinding()
    assert rt["status"].startswith("UNMEASURED") and rt["contaminated_pairs"] == []


# ================================================================== the pre-judge screen
def _walk(n: int = 400, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"close": 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))}, index=idx)


class _Trade:
    def __init__(self, a: pd.Timestamp, b: pd.Timestamp, side: int) -> None:
        self.entry_time, self.exit_time, self.side = a, b, side


def test_candidate_features_use_the_benchmarks_own_definition() -> None:
    df = _walk()
    idx = df.index
    pos = pj.positions_from_trades(idx, [_Trade(idx[10], idx[20], 1), _Trade(idx[50], idx[55], -1)])
    assert pos[9] == 1 and pos[18] == 1 and pos[19] == 0 and pos[49] == -1 and pos[54] == 0
    f = pj.candidate_features(df["close"].to_numpy(), pos)
    assert f is not None and set(f) == set(pj.SCREEN_FEATURES)
    assert pj.candidate_features([1.0, 2.0], [0, 0]) is None        # too short: UNMEASURED


def test_demotion_keeps_every_row_and_every_family_slot() -> None:
    rows = [{"symbol": "A", "family": "f", "params": {"k": i}} for i in range(3)]
    rows.insert(1, {"symbol": "B", "family": "g", "params": {}})
    flagged = pj.identity(rows[0])
    out, rep = pj.demote_flagged([dict(r) for r in rows], {flagged: {"flags": ["rq:x"]}})
    assert [r["family"] for r in out] == ["f", "g", "f", "f"]       # slots unchanged
    assert [r["params"] for r in out if r["family"] == "f"] == [{"k": 1}, {"k": 2}, {"k": 0}]
    assert rep["flagged"] == 1 and rep["withheld"] == 0 and len(out) == len(rows)
    assert out[3]["prejudge"]["flags"] == ["rq:x"]


def test_run_external_backtest_tags_a_candidate_with_the_rules_it_trips(
        tmp_path: Path, monkeypatch: Any) -> None:
    sys.path.insert(0, str(DESK / "side_channels"))
    import run_external_backtest as reb
    rules = tmp_path / "PREJUDGE_RULES.json"
    pj.save_rules({"rules": [
        {"id": "rq:leakage:sr>0.01", "source": "red_queen", "check": ["sr", ">", 0.01],
         "status": "ADOPTED"},
        {"id": "ti:turnover>5", "source": "test_invention", "check": ["turnover", ">", 5.0],
         "status": "ADOPTED"}]}, rules)
    monkeypatch.setattr(reb._prejudge, "RULES", rules)
    reb._prejudge_rules_cache.clear()
    df = _walk()
    # a long position over a rising stretch: per-bar Sharpe far above the rule's bar
    df.loc[df.index[100:200], "close"] = np.linspace(100, 130, 100)
    v = reb.prejudge_verdict(df, [_Trade(df.index[101], df.index[199], 1)])
    assert v is not None and v["status"] == "SCREENED"
    assert v["flags"] == ["rq:leakage:sr>0.01"] and v["rules_hash"]
    monkeypatch.setattr(reb._prejudge, "RULES", tmp_path / "absent.json")
    reb._prejudge_rules_cache.clear()
    assert reb.prejudge_verdict(df, []) is None                     # no rules: no tag


# ================================================================== S09 defenders
def test_a_fooling_kind_earns_a_defender_that_survives_the_sealed_suite() -> None:
    sealed = list(SMALL_SEALED.cases())
    out = rq.defender_rule("leakage", mb.ValidatorConfig(), sealed, seed=3)
    assert out["status"] == "ADOPTABLE", out
    assert out["check"][0] in pj.SCREEN_FEATURES
    s = out["sealed"]
    assert s["survives"] and s["challenger"]["power"] >= s["incumbent"]["power"]
    assert s["challenger"]["immune"] >= s["incumbent"]["immune"]
    assert out["proposal"]["d_immune"] > 0 and out["confirmation"]["d_immune"] > 0


def test_red_queen_writes_the_defender_into_the_screen_once(tmp_path: Path,
                                                            monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    calls: list[str] = []

    def fake(kind: str, *a: Any, **k: Any) -> dict[str, Any]:
        calls.append(kind)
        if kind == "cost_fake":
            return {"kind": kind, "status": "FAILED_SEALED_SUITE"}
        return {"kind": kind, "status": "ADOPTABLE", "check": ["sr", ">", 0.4],
                "sealed": {"survives": True}}

    monkeypatch.setattr(ts.red_queen, "defender_rule", fake)
    res = {"blind_spots": {"cost_fake": 0.5},
           "elite_attacks": [{"attack": {"kind": "leakage", "subtlety": 0.7}}]}
    real = {"status": "MEASURED", "leaks": [{"kind": "leakage"}]}
    out = ts._adopt_defenders(res, real, 5, [])
    assert calls == ["leakage", "cost_fake"]           # the production certifier's leak first
    assert out["adopted_now"] == 1 and out["adopted_total"] == 1
    doc = pj.load_rules(tmp_path / "PREJUDGE_RULES.json")
    (rule,) = pj.active(doc)
    assert rule["kind"] == "leakage" and rule["certifier"] == "production_gauntlet"
    assert "sealed trap suite" in rule["adoption"]
    calls.clear()
    again = ts._adopt_defenders(res, real, 6, [])        # adopted: never re-searched;
    assert calls == [] and again["adopted_now"] == 0     # the failed kind waits its retry
    ts._adopt_defenders(res, real, 5 + ts.DEFENDER_RETRY_GENS, [])
    assert calls == ["cost_fake"]


# ================================================================== S21 machine ratification
def _gate(check: list[Any], **kw: Any) -> dict[str, Any]:
    return {"check": check, "d_immune": 0.3, "d_power": 0.0, "confirm_d_immune": 0.2,
            "confirm_d_power": 0.0, "status": "CANDIDATE_GATE", "confirmations": 2, **kw}


def test_ratifiable_needs_both_suites_and_a_screenable_feature() -> None:
    assert ti.ratifiable(_gate(["sr", ">", 0.4]), pj.SCREEN_FEATURES) is None
    assert "certificate" in str(ti.ratifiable(_gate(["pbo.value", ">", 0.2]),
                                              pj.SCREEN_FEATURES))
    assert ti.ratifiable(_gate(["variants", ">", 3]), pj.SCREEN_FEATURES)
    assert ti.ratifiable(_gate(["sr", ">", 0.4], confirm_d_immune=0.0), pj.SCREEN_FEATURES)
    real = {"check": ["decay", ">", 0.1], "status": "CANDIDATE_GATE",
            "proposal": {"d_immune": 0.5}, "confirmation": {"d_immune": 0.25}}
    assert ti.ratifiable(real, pj.SCREEN_FEATURES) is None


def test_the_machine_ratifies_records_evidence_and_the_test_runs_on_candidates(
        tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "RATIFY_SUITE", SMALL_SEALED)
    good = _gate(["sr", ">", 0.438408])
    cert = _gate(["pbo.value", ">", 0.2])
    reg = {json.dumps(good["check"]): good, json.dumps(cert["check"]): cert}
    out = ts._ratify_invented(reg)
    assert out["ratified_now"] == 1 and out["ratified_total"] == 1
    assert good["ratification"] == "RATIFIED"
    assert cert["ratification"].startswith("NOT_RATIFIABLE")
    (row,) = [json.loads(x) for x in (tmp_path / "test_ratifications.jsonl")
              .read_text().splitlines()]
    assert row["by"] == ti.RATIFIED_BY and row["check"] == good["check"]
    ev = row["evidence"]
    assert ev["proposal"]["d_immune"] > 0 and ev["confirmation"]["d_immune"] > 0
    assert ev["sealed_suite"]["survives"] and ev["sealed_suite"]["seal"]
    # it is a rule of the pre-judge screen now, and it fires on a candidate that trips it
    rules = pj.active(pj.load_rules(tmp_path / "PREJUDGE_RULES.json"))
    assert [r["id"] for r in rules] == [row["rule_id"]]
    hit = pj.screen(dict.fromkeys(pj.SCREEN_FEATURES, 0.0) | {"sr": 0.9}, rules)
    miss = pj.screen(dict.fromkeys(pj.SCREEN_FEATURES, 0.0) | {"sr": 0.1}, rules)
    assert hit["flags"] == [row["rule_id"]] and miss["flags"] == []
    # idempotent: a second pass ratifies nothing new and writes no second row
    again = ts._ratify_invented(reg)
    assert again["ratified_now"] == 0 and again["ratified_total"] == 1
    assert len((tmp_path / "test_ratifications.jsonl").read_text().splitlines()) == 1


def test_a_lost_rules_file_is_refilled_from_the_ratification_ledger(
        tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "RATIFY_SUITE", SMALL_SEALED)
    good = _gate(["sr", ">", 0.438408])
    reg = {json.dumps(good["check"]): good}
    ts._ratify_invented(reg)
    (tmp_path / "PREJUDGE_RULES.json").unlink()
    out = ts._ratify_invented(reg)
    assert out["restored_to_screen"] == 1
    assert pj.active(pj.load_rules(tmp_path / "PREJUDGE_RULES.json"))


def test_a_gate_that_costs_a_genuine_edge_on_the_sealed_suite_is_not_ratified(
        tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "RATIFY_SUITE", SMALL_SEALED)
    greedy = _gate(["sr", ">", -1.0])           # rejects everything, genuine edges included
    out = ts._ratify_invented({json.dumps(greedy["check"]): greedy})
    assert out["ratified_now"] == 0 and greedy["ratification"] == "FAILED_SEALED_SUITE"
    assert not (tmp_path / "test_ratifications.jsonl").exists()


def test_the_constitutional_ledger_is_never_written_by_the_machine() -> None:
    assert ts._test_ratifications() != ts.RATIFICATIONS
    assert ts._test_ratifications().name == "test_ratifications.jsonl"


@pytest.mark.parametrize("kind", ["regime_break"])
def test_defender_search_is_deterministic(kind: str) -> None:
    sealed = list(SMALL_SEALED.cases())
    a = rq.defender_rule(kind, mb.ValidatorConfig(), sealed, seed=7)
    b = rq.defender_rule(kind, mb.ValidatorConfig(), sealed, seed=7)
    assert a.get("check") == b.get("check") and a["status"] == b["status"]
