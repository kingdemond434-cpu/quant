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
for p in (str(ROOT), str(ROOT / "scripts"), str(DESK / "research"), str(DESK)):
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


def test_matched_fills_resolver_reads_evidence_that_exists() -> None:
    from libs.tiers import review_panel as rp
    res = rp.RESOLVERS["matched_fills_10"]
    assert res({"execution": {"matched_fills": 9, "live_mean_r": 1.0}}) is None
    # the old defect: ten fills and no `capture` field resolved AGAINST
    assert res({"execution": {"matched_fills": 12}}) is None
    assert res({"execution": {"matched_fills": 12, "live_mean_r": 0.2}}) is True
    assert res({"execution": {"matched_fills": 12, "live_mean_r": -0.2}}) is False
    assert res({"execution": {"matched_fills": 12, "capture": 0.8}}) is True
    ev = ts._execution_evidence(12, [0.1, 0.3], 0.4)
    assert ev == {"matched_fills": 12, "live_mean_r": 0.2, "capture": 0.5}
    assert "capture" not in ts._execution_evidence(12, [0.1], -0.2)
    assert ts._execution_evidence(0, None, None) == {"matched_fills": 0}


def test_rejected_organ_loses_steering_never_emission(tmp_path: Path) -> None:
    from libs.tiers import authority
    ledger = {"layers": [{"id": "S08", "contract": {"organ": "market"}},
                         {"id": "S40", "contract": {"organ": "market"}},
                         {"id": "S22", "contract": {"organ": "grammar"}},
                         {"id": "S44", "contract": {"organ": "grammar"}}]}
    doc = authority.compute(ledger, {"S08": {"verdict": "REJECTED"},
                                     "S40": {"verdict": "REJECTED"},
                                     "S22": {"verdict": "REJECTED"},
                                     "S44": {"verdict": "ADMITTED"}})
    assert doc["suspended"] == ["market"], "suspended only when EVERY layer is REJECTED"
    p = tmp_path / "AUTHORITY.json"
    p.write_text(json.dumps(doc), "utf-8")
    assert authority.suspended("market", p) and not authority.suspended("grammar", p)
    old = dict(doc, generated_utc="2020-01-01T00:00:00+00:00")
    p.write_text(json.dumps(old), "utf-8")
    assert not authority.suspended("market", p), "a stale verdict lapses"
    assert not authority.suspended("market", tmp_path / "absent.json")


def test_contract_verdicts_carry_their_baseline() -> None:
    from libs.tiers import contracts
    c = contracts.Contract.parse({"gain": "ALPHA_DISCOVERY", "metric": "m", "better": "down"})
    ev = contracts.evaluate(c, [4.0, 4.0, 2.0, 1.0])
    assert ev["baseline"] == 4.0 and ev["delta_vs_baseline"] == 3.0
    assert contracts.evaluate(c, [])["baseline"] is None


def test_every_new_hourly_leg_has_a_contract() -> None:
    import check_tier_s_program as chk
    ledger = json.loads(chk.LEDGER.read_text("utf-8"))
    problems, _ = chk.check(ledger, chk.ROOT)
    assert not problems, problems
    ledger["leg_contracts"] = [r for r in ledger["leg_contracts"] if r["leg"] != "frontier_map"]
    problems, _ = chk.check(ledger, chk.ROOT)
    assert any("frontier_map" in p for p in problems)


# ------------------------------------------------------------------ self-grading, batch 3
def test_every_kind_generates_and_new_placebos_behave() -> None:
    from libs.tiers import traps
    for kind in traps.ALL_KINDS:
        case, truth = traps.generate(kind, 11, 300)
        assert truth.genuine == (kind in traps.TRUE_KINDS)
        assert len(case.prices) == 301
        assert np.isfinite(case.signal_fn(case.prices, 100))
    assert {"information_delay", "timestamp_scramble", "sign_reversal", "spread_perturbation",
            "label_randomization"} <= set(traps.TRAP_KINDS)
    assert "true_strong_signal" in traps.TRUE_KINDS
    assert traps.LATE_INFORMATION_KINDS.issubset(traps.TRAP_KINDS)
    assert traps.INEXPRESSIBLE_TO_GAUNTLET.issubset(traps.TRAP_KINDS)


def test_label_randomization_is_causal() -> None:
    """The overfit trap must fool by FITTING, not by leaking: changing the future cannot move
    today's position."""
    from libs.tiers import traps
    case, _t = traps.generate("label_randomization", 3, 400)
    px = case.prices.copy()
    before = [case.signal_fn(px, t) for t in range(10, 200)]
    px[201:] *= 1.5
    assert [case.signal_fn(px, t) for t in range(10, 200)] == before


def test_production_immune_is_blind_and_honestly_stamped(monkeypatch: Any,
                                                        tmp_path: Path) -> None:
    import adversary

    from libs.tiers import traps
    seen: list[dict[str, Any]] = []

    class G:
        @staticmethod
        def run_gauntlet(cells: list[dict[str, Any]], _n: str, _m: Any) -> dict[str, Any]:
            seen.extend(cells)
            return {"verdicts": [{"family": c["family"], "passed": False, "stages": {}}
                                 for c in cells]}

    stamps: dict[str, int] = {}

    def cell(name: str, sig: Any, fwd: Any, stamp_offset: int = 0, **_k: Any) -> dict:
        stamps[name] = stamp_offset
        return {"family": f"canary_{name}"}

    monkeypatch.setattr(adversary, "real_gate", lambda: (SimpleNamespace(_gauntlet=G), None))
    monkeypatch.setattr(adversary, "docket_cell", cell)
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "PROD_SUITE", ts.meta_benchmark.Suite(per_kind=2, n=120))
    out = ts.production_immune(budget_s=60)
    expressible = [k for k in traps.ALL_KINDS if k not in traps.INEXPRESSIBLE_TO_GAUNTLET]
    assert out["judged_total"] == 2 * len(expressible)
    assert out["immune_score"] == 1.0 and out["power"] == 0.0
    for c in seen:                      # the certifier is told nothing about the kind
        assert not any(k in c["family"] for k in traps.ALL_KINDS)
    state = json.loads((tmp_path / "immune_prod.json").read_text("utf-8"))
    by_name = {"im" + ts.truth_kernel.sha256(f"{v['kind']}|{k.split('|')[1]}|"
                                            f"{state['code']}")[:12]: v["kind"]
               for k, v in state["verdicts"].items()}
    for name, kind in by_name.items():
        assert stamps[name] == (1 if kind in traps.LATE_INFORMATION_KINDS else 0), kind
    # verdicts are kept until the certifier's code changes: a second hour judges nothing new
    assert ts.production_immune(budget_s=60)["judged_now"] == 0


def test_case_series_keeps_the_edge_to_cost_ratio() -> None:
    from libs.tiers import traps
    cheap, _ = traps.generate("true_signal", 5, 200)
    dear, _ = traps.generate("cost_fake", 5, 200)
    _s, f1 = ts._case_series(cheap)
    _s, f2 = ts._case_series(dear)
    assert np.std(f2) < np.std(f1) / 10, "a sub-cost edge is shrunk against the docket's cost"


def test_red_queen_generation_evolves_and_scores() -> None:
    from libs.tiers import meta_benchmark as mb
    from libs.tiers import red_queen
    sealed = list(mb.Suite(per_kind=2, base_seed=5150, n=400).cases())
    res = red_queen.generation([], mb.ValidatorConfig(), sealed, seed=1, pop=4, defenders=2,
                               attack_seeds=1)
    assert len(res["next_attackers"]) == 4
    assert 0.0 <= res["attack_success"] <= 1.0
    assert res["best_defender"]["balanced"] is not None


def test_invent_from_needs_cases() -> None:
    from libs.tiers import meta_benchmark as mb
    from libs.tiers import test_invention
    out = test_invention.invent_from(mb.ValidatorConfig(), [], [])
    assert out["candidate_gates"] == [] and out["n_tried"] == 0


# ------------------------------------------------------------------ the promotion door
def test_promotion_authority_withholds_on_evidence_only(monkeypatch: Any, tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from libs.tiers import promotion_authority as pa
    now = datetime.now(UTC).isoformat()
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    for attr in ("REPLICATION", "FDR_ROWS", "FREEZE", "LEDGER"):
        monkeypatch.setattr(pa, attr, tmp_path / "reports" / f"{attr}.json")
    (tmp_path / "reports").mkdir()
    assert pa.block("EURUSD.x.asia") is None, "absent verdicts withhold nothing"
    pa.REPLICATION.write_text(json.dumps({"verdicts": [
        {"key": "external.EURUSD.x.asia", "verdict": "MISMATCH"}]}), "utf-8")
    assert str(pa.block("EURUSD.x.asia")).startswith("REPLICATION_MISMATCH")
    pa.REPLICATION.write_text("{}", "utf-8")
    pa.FDR_ROWS.write_text(json.dumps({"generated_utc": now, "certified": [
        {"test_id": "GBPUSD.y.ny", "over_budget": True, "p": 0.04}]}), "utf-8")
    assert str(pa.block("GBPUSD.y.ny")).startswith("ONLINE_FDR_OVER_BUDGET")
    pa.FDR_ROWS.write_text("{}", "utf-8")
    # a freeze counts only when the PRODUCTION certifier's score DROPPED
    pa.FREEZE.write_text(json.dumps({"at": now, "verdict": "FREEZE", "judge":
                                     "reference_validator", "why": "immune score fell"}), "utf-8")
    assert pa.block("A") is None
    pa.FREEZE.write_text(json.dumps({"at": now, "verdict": "FREEZE", "judge": "production:ab",
                                     "why": "immune score 0.8 below the floor 0.9"}), "utf-8")
    assert pa.block("A") is None
    pa.FREEZE.write_text(json.dumps({"at": now, "verdict": "FREEZE", "judge": "production:ab",
                                     "why": "immune score fell 0.99 -> 0.90"}), "utf-8")
    assert str(pa.block("A")).startswith("IMMUNE_FREEZE")
    pa.FREEZE.write_text(json.dumps({"at": "2020-01-01T00:00:00+00:00", "verdict": "FREEZE",
                                     "judge": "production:ab", "why": "fell"}), "utf-8")
    assert pa.block("A") is None, "a stale freeze lapses"
    pa.record("A", "IMMUNE_FREEZE: x", lane="main", exp_r=0.2, n=40)
    row = json.loads(pa.LEDGER.read_text("utf-8").splitlines()[0])
    assert row["reason"] == "IMMUNE_FREEZE" and row["exp_r"] == 0.2


def test_the_door_is_a_billed_rail_and_the_promoter_calls_it() -> None:
    from libs.portfolio import rails
    r = rails.rail("tier_s_evidence_block")
    assert r.measure == "measure_tier_s_block"
    src = (DESK / "research" / "promoter.py").read_text("utf-8")
    assert src.count("tier_s_block(key)") == 2, "both promotion lanes consult the door"
    import missed_growth
    assert "measure_tier_s_block" in missed_growth.MEASURES


def test_firewall_may_guards_the_promoter_role() -> None:
    from libs.tiers import firewall
    with pytest.raises(firewall.FirewallError):
        firewall.may("promoter", "read", "desks/mt5/data/intelligence/kimi/x.json")
    firewall.may("promoter", "read", "desks/mt5/reports/REPLICATION.json")


def test_conformance_reads_code_not_words() -> None:
    from libs.tiers import conformance
    good = '''
def place(mt5, s):
    record_intent(s)
    heat = allocator_heat(s)
    live = load_sleeves()
    req = {"action": mt5.TRADE_ACTION_PENDING, "magic": 1, "comment": "x"}
    mt5.order_send(req)

def main(mt5):
    mt5.positions_get()
    df = frame.iloc[:-1]
'''
    bad = '''
# record_intent before send, allocator heat re-checked, reconcile positions_get on restart
def place(mt5, s):
    mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "magic": 1})
    record_intent(s)
'''
    g = conformance.check_source(good)
    assert all(g["knobs"].values()), g
    b = conformance.check_source(bad)
    assert b["knobs"]["persist_before_send"] is False, "a journal AFTER the send is not before it"
    assert b["knobs"]["idempotent_client_id"] is False
    assert b["knobs"]["reconcile_on_restart"] is False, "a comment is not a call"
    closing = conformance.check_source('''
def close(mt5, p):
    record_intent(p)
    mt5.order_send({"action": 1, "position": p, "magic": 1, "comment": "c"})
''')
    assert closing["knobs"]["recheck_alloc_at_send"] is True, "a close need not re-ask"


# ---------------------------------------------------------------- scope gaps closed 2026-09-30
def _fake_catalogue(days: int = 400) -> Any:
    from libs.research import alpha_dsl as dsl

    class Cat:
        def __init__(self) -> None:
            self.fields = (
                dsl.Field("fred.DGS10", "macro_level", "macro", "axis:fred", "period_end+1d"),
                dsl.Field("cftc_cot_legacy.net_pct_oi", "positioning", "positioning",
                          "axis:cot", "knowable_at", symbol="XAUUSD"),
                dsl.Field("close", "price", "close", "bars", "bar_close"))
            idx = pd.date_range("2024-01-01", periods=days, freq="D", tz="UTC")
            rng = np.random.default_rng(3)
            self.data = {"fred.DGS10": pd.Series(np.cumsum(rng.normal(0, 1, days)), idx),
                         "cftc_cot_legacy.net_pct_oi": pd.Series(rng.normal(0, 1, days), idx)}

        def series(self, f: Any, index: pd.Index) -> pd.Series:
            s = self.data[f.name]
            return s.reindex(pd.DatetimeIndex(index), method="ffill")
    return Cat()


def test_world_macro_kinds_and_causal_one_day_lead() -> None:
    from libs.tiers import world_macro as wm
    assert wm.kind_of("fred.BAMLH0A0HYM2", "macro_level") == "credit"
    assert wm.kind_of("fred.VIXCLS", "macro_level") == "vol"
    assert wm.kind_of("fred.DTWEXBGS", "macro_level") == "dollar"
    assert wm.kind_of("fred.T10YIE", "macro_level") == "inflation"
    assert wm.kind_of("fred.WALCL", "macro_level") == "liquidity"
    assert wm.kind_of("bis_policy_rates.carry_differential", "rate") == "carry"
    assert wm.kind_of("cftc_cot_legacy.net_pct_oi", "positioning") == "positioning"
    cat = _fake_catalogue()
    days = 400
    idx = pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="UTC")
    # XAUUSD's return on day d+1 is minus the DGS10 change of day d: a planted lead
    dgs = cat.data["fred.DGS10"]
    daily = -0.01 * dgs.diff().shift(1).fillna(0.0)
    hourly = np.repeat(daily.to_numpy() / 24.0, 24)
    closes = {"XAUUSD": pd.Series(100 * np.exp(np.cumsum(hourly)), idx),
              "EURUSD": pd.Series(1 + 0.001 * np.random.default_rng(1).normal(0, 1, len(idx))
                                  .cumsum() / 50, idx)}
    r = wm.run(cat, closes, "2026-09-30T00:00:00+00:00", vocab={"cot_net_fade"})
    assert r["census"]["rates"]["status"] == "MEASURED"
    assert r["census"]["credit"]["status"] == "UNMEASURED"
    assert r["census"]["flows"]["status"] == "UNMEASURED"
    hit = [e for e in r["edges"] if e["driver"] == "fred.DGS10" and e["target"] == "XAUUSD"]
    assert hit and hit[0]["class"] != "FALSE" and hit[0]["beta"] < 0
    # a per-symbol node never reaches another symbol
    assert not [e for e in r["edges"] if e["driver"].startswith("cftc") and e["target"] != "XAUUSD"]
    x = [e for e in r["exprs"] if e["symbol"] == "XAUUSD" and e["bind"] == {"macro": "fred.DGS10"}]
    assert x and x[0]["expr"] == "neg(delta(macro, 24))"
    terms = list(ag.terminal_pool(True, extra=["macro", "positioning", "fundamental"]))
    for e in r["exprs"]:
        assert ag.is_valid(ag.from_str(e["expr"]), terminals=terms)


def test_enqueue_dedupes_by_binding(tmp_path: Path) -> None:
    q = tmp_path / "q.json"
    base = {"symbol": "XAUUSD", "expr": "delta(macro, 24)"}
    assert ts.enqueue_xsci([{**base, "bind": {"macro": "a"}}, {**base, "bind": {"macro": "b"}},
                            {**base, "bind": {"macro": "a"}}], q) == 2


def test_hypothesis_graph_records_every_parent(tmp_path: Path) -> None:
    from libs.research import hypothesis_graph as hg
    g = hg.Graph(tmp_path / "g.jsonl")
    a = hg.Node(symbol="EURUSD", family="trend_ma_cross", params={"f": 1})
    b = hg.Node(symbol="EURUSD", family="trend_ma_cross", params={"f": 2})
    g.append(a)
    g.append(b)
    hg.record_candidates([{"symbol": "EURUSD", "family": "trend_ma_cross", "params": {"f": 3},
                           "parent_ids": [a.id, b.id, "unresolved"]}], "t", graph=g)
    child = next(r for r in g.current().values() if (r.get("params") or {}).get("f") == 3)
    assert child["parent"] == a.id and child["co_parents"] == [b.id]
    roles = [e.get("role") for e in child["edges"] if e["type"] == hg.MUTATED_FROM]
    assert roles.count("co_parent") == 2           # the unresolved claim stays on an edge
    assert {a.id, b.id} <= set(g.ancestors(child["id"]))


def test_crossover_child_names_its_partner() -> None:
    import expression_factory as ef
    assert "co_parents" in ef.Cell.__dataclass_fields__
    src = (DESK / "research" / "expression_factory.py").read_text("utf-8")
    assert "self._partner_pid = mate.pid" in src and '"parent_ids": [p for p in' in src


def test_control_arm_verdicts() -> None:
    from libs.tiers import control_arm as ca
    assert ca.compare([1, 2], [1, 2, 3])["verdict"] == "UNMEASURED"
    assert ca.compare([5, 6, 7, 6], [1, 2, 1, 2])["verdict"] == "ADMITTED"
    assert ca.compare([1, 2, 1, 2], [5, 6, 7, 6])["verdict"] == "REJECTED"
    units = [f"leg{i}" for i in range(2000)]
    share = sum(ca.in_control(u, "market") for u in units) / len(units)
    assert 0.15 < share < 0.25
    assert ca.in_control("x", "market") == ca.in_control("x", "market")


def test_cycle_pricing_never_reprices_a_control_leg(monkeypatch: Any, tmp_path: Path) -> None:
    import cycle_pricing as cp

    from libs.tiers import control_arm as ca
    legs = [f"leg{i}" for i in range(40)]
    doc = {"generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
           "leg_prices": dict.fromkeys(legs, 1.0)}
    monkeypatch.setattr(cp, "_read", lambda _p: doc)
    got = cp._researcher_prices()
    assert got and all(not ca.in_control(lg, "market") for lg in got)
    assert len(got) < len(legs)


def test_suspension_reaches_every_steering_consumer() -> None:
    src = (DESK / "research" / "tier_s.py").read_text("utf-8")
    for organ in ("topology", "genomes", "failure_memory", "frontier", "predictions",
                  "red_queen", "twin"):
        assert f'authority.suspended("{organ}")' in src, organ
    door = (ROOT / "libs" / "tiers" / "promotion_authority.py").read_text("utf-8")
    assert 'suspended("online_fdr")' in door and 'suspended("immune")' in door
    impl = (DESK / "research" / "implementer.py").read_text("utf-8")
    assert 'suspended("self_model"' in impl


def test_suspended_immune_and_fdr_withhold_nothing(monkeypatch: Any, tmp_path: Path) -> None:
    from libs.tiers import authority
    from libs.tiers import promotion_authority as pa
    now = pd.Timestamp.now(tz="UTC").isoformat()
    fdr = tmp_path / "fdr.json"
    fdr.write_text(json.dumps({"generated_utc": now, "certified": [
        {"test_id": "X.y", "over_budget": True, "p": 0.04, "lord_level": 0.001}]}), "utf-8")
    fr = tmp_path / "freeze.json"
    fr.write_text(json.dumps({"at": now, "verdict": "FREEZE", "judge": "production:abc",
                              "why": "immune score fell"}), "utf-8")
    monkeypatch.setattr(pa, "FDR_ROWS", fdr)
    monkeypatch.setattr(pa, "FREEZE", fr)
    monkeypatch.setattr(pa, "REPLICATION", tmp_path / "none.json")
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    monkeypatch.setattr(pa.firewall, "may", lambda *a, **k: True)
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: False)
    assert (pa.block("X.y") or "").startswith("ONLINE_FDR_OVER_BUDGET")
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: organ == "online_fdr")
    assert (pa.block("X.y") or "").startswith("IMMUNE_FREEZE")
    monkeypatch.setattr(authority, "suspended", lambda organ, *a, **k: True)
    assert pa.block("X.y") is None
