"""Tier S organ functions (desks/mt5/research/tier_s.py): the joins and consumers the layers claim.

Each test pins one claim the independent verifier found unconsumed or untested on 2026-09-30:
cross-science hits are tested as their own mechanism (never relabelled range_reversion), broken
relationships are tested as RESIDUALS, the falsify_order gene changes what a genome emits, the
self-model's docket reaches the implementer, and one sleeve's five spellings resolve to one key.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
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

from libs.research import alpha_grammar as ag  # noqa: E402

LABS = {
    "signal": {"lab": "signal", "period": 14.0},
    "control": {"lab": "control", "ac": 0.2},
    "queueing": {"lab": "queueing"},
    "ecology": {"lab": "ecology", "coupling": -0.3},
    "dynamical": {"lab": "dynamical"},
    "bayesian": {"lab": "bayesian", "posterior": {"mean": -0.1}},
}


@pytest.mark.parametrize("lab", sorted(LABS))
def test_every_single_symbol_lab_is_a_valid_grammar_expression(lab: str) -> None:
    text = ts.xsci_expression(LABS[lab])
    assert text is not None
    assert ag.is_valid(ag.from_str(text)), text


def test_signs_follow_the_measured_statistic() -> None:
    assert ts.xsci_expression({"lab": "control", "ac": -0.2}).startswith("neg(")
    assert not ts.xsci_expression({"lab": "control", "ac": 0.2}).startswith("neg(")
    assert ts.xsci_expression({"lab": "bayesian", "posterior": {"mean": 0.1}}) == "mean(ret, 2)"
    assert ts.xsci_expression({"lab": "information"}) is None     # cross-instrument: compiler


def test_science_rows_test_each_hit_as_its_own_mechanism(monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "_may_hypothesise", lambda s: s != "AAPL")
    resid = [{"target": "EURUSD", "driver": "DXY", "claim": "c", "residual_z": 3.0},
             {"target": "AAPL", "driver": "US500", "claim": "c", "residual_z": 3.0}]
    labs = {"information": [{"lab": "information", "symbols": ["GBPUSD", "EURUSD"],
                             "driver": "EURUSD", "target": "GBPUSD", "claim": "te"}],
            "network": [{"lab": "network", "symbols": ["AUDUSD", "XAUUSD"], "hub": "XAUUSD",
                         "corr": -0.2, "claim": "hub"}],
            "signal": [{"lab": "signal", "symbols": ["USDJPY"], "period": 24.0, "claim": "cyc"}]}
    rows, exprs = ts.science_rows(labs, resid)
    fams = Counter(r["family"] for r in rows)
    assert "range_reversion" not in fams
    res = [r for r in rows if r["family"] == "cross_asset_residual"]
    assert len(res) == 1, "a single-name equity target is never hypothesised"
    assert res[0]["symbols"] == ["EURUSD"]
    assert res[0]["params"]["factor_symbols"] == ["DXY"]
    ll = [r for r in rows if r["family"] == "lead_lag"]
    te = [r for r in ll if r["symbols"] == ["GBPUSD"]]
    assert {r["params"]["direction"] for r in te} == {"same", "opposite"}, "TE has no sign"
    hub = [r for r in ll if r["symbols"] == ["AUDUSD"]]
    assert [r["params"]["direction"] for r in hub] == ["opposite"]
    assert hub[0]["params"]["driver_symbol"] == "XAUUSD"
    assert exprs == [dict(exprs[0], symbol="USDJPY", lab="signal",
                          generator="cross_science:signal")]
    assert ag.is_valid(ag.from_str(exprs[0]["expr"]))


def test_enqueue_dedupes_and_caps(tmp_path: Path) -> None:
    q = tmp_path / "q.json"
    row = {"symbol": "EURUSD", "expr": "mean(ret, 2)", "lab": "bayesian"}
    assert ts.enqueue_xsci([row, dict(row)], q) == 1
    assert ts.enqueue_xsci([row], q) == 0
    assert len(json.loads(q.read_text("utf-8"))) == 1


def test_expression_factory_drains_the_queue_as_its_own_generator(tmp_path: Path) -> None:
    import expression_factory as ef
    q = tmp_path / "data" / "tier_s" / "xsci_expressions.json"
    q.parent.mkdir(parents=True)
    q.write_text(json.dumps([
        {"symbol": "NOTHERE", "expr": "mean(ret, 2)", "generator": "cross_science:bayesian"},
        {"symbol": "EURUSD", "expr": "neg(delta(close, 8))", "generator": "cross_science:signal"},
    ]), "utf-8")
    idx = pd.date_range("2026-01-01", periods=50, freq="h")
    close = pd.Series(np.linspace(1.0, 1.1, 50), index=idx)
    frames = {"close": close, "ret": close.pct_change()}
    world = SimpleNamespace(frames=frames, asset_class="FX")
    fake = SimpleNamespace(paths=SimpleNamespace(desk=tmp_path),
                           lake=SimpleNamespace(worlds={"EURUSD": world}), dry_run=False,
                           xsci_cells={}, rng=np.random.default_rng(0))
    cell = ef.Factory._xsci_cell(fake)                       # type: ignore[arg-type]
    assert cell is not None
    assert cell.symbol == "EURUSD" and cell.generator == "cross_science:signal"
    assert cell.origin == "invention"
    left = json.loads(q.read_text("utf-8"))
    assert [r["symbol"] for r in left] == ["NOTHERE"], "drained, and only the one it used"
    assert fake.xsci_cells == {"cross_science:signal": 1}
    assert ef.Factory._xsci_cell(fake) is None              # type: ignore[arg-type]


def test_falsify_order_changes_the_ranking() -> None:
    ledger = ([{"family": "a", "passed": False, "terminal_gate": "stress_costs"}] * 8
              + [{"family": "a", "passed": False, "terminal_gate": "deflated_sharpe"}] * 2
              + [{"family": "b", "passed": False, "terminal_gate": "deflated_sharpe"}] * 8
              + [{"family": "b", "passed": False, "terminal_gate": "stress_costs"}] * 2)
    kills = ts._family_gate_kills(ledger)
    assert ts.falsify_rank("a", "cost_first", kills) == pytest.approx(0.8)
    assert ts.falsify_rank("b", "cost_first", kills) == pytest.approx(0.2)
    assert ts.falsify_rank("a", "dsr_first", kills) < ts.falsify_rank("b", "dsr_first", kills)
    assert ts.falsify_rank("unjudged", "cost_first", kills) == 0.5
    assert set(ts.FALSIFY_GATES) == {"cost_first", "lookahead_first", "stability_first",
                                     "dsr_first"}


def test_every_falsify_allele_the_gene_can_take_has_gates() -> None:
    from libs.tiers import evolution
    gene = next(g for g in evolution.RESEARCHER_GENES if g.name == "falsify_order")
    assert set(gene.choices) == set(ts.FALSIFY_GATES)


def test_self_model_docket_reaches_the_implementer(tmp_path: Path) -> None:
    import implementer
    d = tmp_path / "desks" / "mt5" / "data" / "tier_s"
    d.mkdir(parents=True)
    (d / "SELF_MODEL_DOCKET.json").write_text(json.dumps({"tasks": [
        {"task": "Tier S deficiency: validation.power", "why": "power 0.31",
         "expected_improvement": 0.4, "gain": "ALPHA_DISCOVERY"}]}), "utf-8")
    rows = implementer._self_model_rows(tmp_path)
    assert len(rows) == 1 and rows[0]["source"] == "tier_s_self_model"
    assert "validation.power" in rows[0]["summary"]
    assert "0.31" not in rows[0]["summary"], "an hourly number would mint a row per read"
    assert implementer._self_model_rows(tmp_path / "absent") == []


def test_one_sleeve_five_spellings_one_key(monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "registry", lambda: {
        "EURZAR.overnight_gap_decay.asia": {"identity": {"symbol": "EURZAR",
                                                         "family": "overnight_gap_decay",
                                                         "selector": "asia"}}})
    monkeypatch.setattr(ts, "survivors", dict)
    monkeypatch.setattr(ts, "_read", lambda p: {})
    monkeypatch.setattr(ts, "_jsonl", lambda p, limit=0: [{"ticket": "77", "sleeve": "gold_asia"}])
    nm = ts.Names()
    assert nm.key("EURZAR.overnight_gap_decay.asia") == "EURZAR.overnight_gap_decay.asia"
    assert nm.key("EURZAR_overnight_gap_decay_asia") == "EURZAR.overnight_gap_decay.asia"
    assert nm.group("gold_asia") == "XAUUSD.asia"
    assert nm.fill_sleeve({"entry_order": 77, "sleeve": "[tp 4360.71]"}) == "gold_asia"
    assert nm.fill_sleeve({"sleeve": "[sl 1.0]"}) == ""
    assert nm.triple("") is None


def test_producers_and_epistemologies() -> None:
    assert ts._producer("miner:deep_forest:zhihu") == "miner:deep_forest"
    assert ts._producer("kimi:discoveries") == "kimi"
    assert ts._producer(None) == "unattributed"
    assert ts._epistemology("tier_s:cross_science") == "structural_model"
    assert ts._epistemology("miner:deep_forest") == "practitioner_story"
    assert ts._epistemology("something_new") == "empirical_mining"


def test_world_and_science_is_unmeasured_without_bars(monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "_returns_panel", lambda: ({}, {}, {}))
    out = ts.organ_world_and_science()
    assert out["status"] == "UNMEASURED" and out["metric"]["hypotheses"] == 0
