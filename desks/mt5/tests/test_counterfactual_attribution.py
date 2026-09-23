"""The mechanism, not the exit code.

Four things have to be true or the organ is decoration: a state-dependent edge has to SHOW UP in
the conditional bucket and a state-independent one has to NOT show up (a report that finds
structure in noise is worse than no report); a fill that cost more than the model has to land in
the execution term rather than in the residual; an absent ledger and an absent world model have
to produce UNMEASURED rows and a WRITTEN report rather than a crash or a silent skip; and
`--dry-run` has to write nothing at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import counterfactual_attribution as cfa  # noqa: E402

DAYS = 40
NOISE = (0.05, -0.05, 0.1, -0.1, 0.02, -0.02, 0.07, -0.07)


def _day(i: int) -> str:
    return f"2026-0{1 + i // 28}-{1 + i % 28:02d}"


def _axis(path: Path) -> None:
    """A clean bimodal daily state: +1 on even days, -1 on odd ones. The expanding median sits
    at zero once both arms are present, so the bucket is unambiguous and knowable at the time."""
    points = [{"d": _day(i), "v": 1.0 if i % 2 == 0 else -1.0, "sd": 0.2} for i in range(DAYS)]
    path.write_text(json.dumps({"axis": "shadow_latent", "id": "shadow_global_risk_appetite",
                                "latent": "global_risk_appetite", "status": "MEASURED",
                                "n": len(points), "points": points}), "utf-8")


def _ledger(path: Path, rs: list[float]) -> None:
    path.write_text(json.dumps([{"entry_time": f"{_day(i)} 09:00:00+00:00",
                                 "exit_time": f"{_day(i)} 10:00:00+00:00",
                                 "r_multiple": r, "side": 1}
                                for i, r in enumerate(rs)]), "utf-8")


@pytest.fixture()
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A whole fake desk. Every path the organ reads or writes is redirected into tmp_path, so
    no tracked file is touched by any test in this module."""
    for sub in ("data/axes", "data/macro", "reports/shadow"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cfa, "AXES", tmp_path / "data" / "axes")
    monkeypatch.setattr(cfa, "SHADOW", tmp_path / "reports" / "shadow")
    monkeypatch.setattr(cfa, "SLEEVES", tmp_path / "data" / "sleeves.json")
    monkeypatch.setattr(cfa, "LIVE_LEDGER", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(cfa, "COST_SURFACE", tmp_path / "data" / "cost_surface.json")
    monkeypatch.setattr(cfa, "ORDER_INTENTS", tmp_path / "data" / "order_intents.jsonl")
    monkeypatch.setattr(cfa, "UNKNOWN_QUEUE", tmp_path / "data" / "unknown_unknowns_queue.jsonl")
    monkeypatch.setattr(cfa, "EVENT_LEDGER", tmp_path / "data" / "macro" / "event_ledger.jsonl")
    monkeypatch.setattr(cfa, "WORLD_MODEL", tmp_path / "reports" / "WORLD_MODEL.json")
    monkeypatch.setattr(cfa, "MACRO_VIEW", tmp_path / "reports" / "MACRO_VIEW.json")
    monkeypatch.setattr(cfa, "REGIME_ROUTER", tmp_path / "reports" / "REGIME_ROUTER.json")
    monkeypatch.setattr(cfa, "STATE_VECTOR", tmp_path / "data" / "state_vector.json")
    monkeypatch.setattr(cfa, "WORLD_STATE", tmp_path / "data" / "world_state.json")
    monkeypatch.setattr(cfa, "MACRO_STATE", tmp_path / "data" / "macro_state.json")
    monkeypatch.setattr(cfa, "OUT", tmp_path / "reports" / "COUNTERFACTUAL_ATTRIBUTION.json")
    return tmp_path


def _row(rep: dict[str, Any], sleeve: str, state: str = "risk_appetite") -> dict[str, Any]:
    for r in rep["sleeves"]["rows"]:
        if r["sleeve"] == sleeve and r.get("state") == state:
            return dict(r)
    raise AssertionError(f"no {state} row for {sleeve}: "
                         f"{[(r['sleeve'], r.get('state')) for r in rep['sleeves']['rows']]}")


# --------------------------------------------------------------------------------------- (a)
def test_planted_state_edge_is_found_and_a_flat_sleeve_is_not(tree: Path) -> None:
    """A sleeve whose R flips with the state must show a conditional spread; one whose R is the
    same multiset in both buckets must measure tau^2 = 0 and shrink to its unconditional mean."""
    _axis(tree / "data" / "axes" / "shadow_global_risk_appetite.json")
    # planted: +0.8 on the axis's HIGH days, -0.8 on its LOW days, with small noise so the
    # within-bucket variance the shrinkage needs is not zero.
    _ledger(tree / "reports" / "shadow" / "ledger_PLANTED_edge.json",
            [(0.8 if i % 2 == 0 else -0.8) + NOISE[i % len(NOISE)] for i in range(DAYS)])
    # flat: the SAME two values, but paired so each bucket receives an identical multiset.
    _ledger(tree / "reports" / "shadow" / "ledger_FLAT_noedge.json",
            [(0.8 if (i // 2) % 2 == 0 else -0.8) + NOISE[i % len(NOISE)] for i in range(DAYS)])

    rep = cfa.build(budget_s=60, apply=False)
    assert rep["sleeves"]["primary_conditioning"] == "risk_appetite"

    planted = _row(rep, "planted_edge")
    assert planted["status"] == "MEASURED"
    assert planted["shrinkage"]["tau2"] > 0.0, planted["shrinkage"]
    buckets = {b["bucket"]: b for b in planted["buckets"]}
    assert buckets["high"]["mean_r"] > 0.5 > buckets["low"]["mean_r"]
    # the shrinkage must not erase a real effect: lambda near 1 when tau^2 dwarfs the noise
    assert buckets["high"]["lambda"] > 0.9
    assert buckets["high"]["n_eff"] > 0.9 * buckets["high"]["n"]
    assert planted["conditional_spread_r"] > 1.0
    # the E[log W] gradient is the shrunk mean, and it must carry the sign of the bucket
    assert buckets["high"]["elog_gradient"] > 0 > buckets["low"]["elog_gradient"]

    flat = _row(rep, "flat_noedge")
    assert flat["shrinkage"]["tau2"] == 0.0, flat["shrinkage"]
    assert "no between-bucket signal" in flat["shrinkage"]["why"]
    flat_b = {b["bucket"]: b for b in flat["buckets"]}
    # fully shrunk: every bucket reports the unconditional mean and nothing else
    assert flat_b["high"]["lambda"] == 0.0 and flat_b["low"]["lambda"] == 0.0
    assert flat_b["high"]["shrunk_mean_r"] == flat_b["low"]["shrunk_mean_r"]
    assert flat["conditional_spread_r"] == 0.0


def test_a_state_no_source_measures_is_unmeasured_not_a_half(tree: Path) -> None:
    """Thirteen of the fourteen states have no source in this fake tree. Not one of them may
    come back as 0.5 with a straight face."""
    _axis(tree / "data" / "axes" / "shadow_global_risk_appetite.json")
    rep = cfa.build(budget_s=60, apply=False)
    states = {s["state"]: s for s in rep["global_posterior"]["states"]}
    assert set(states) == set(cfa.STATE_NAMES)
    assert states["risk_appetite"]["status"] == "MEASURED"
    for name in ("china_demand", "inflation", "growth", "carry"):
        assert states[name]["status"] == "UNMEASURED"
        assert states[name]["mean"] is None
        assert states[name]["why"], f"{name} is unmeasured with no reason given"
    assert any(u["name"] == "state:china_demand" for u in rep["unmeasured"])


def test_two_agreeing_sources_tighten_the_interval(tree: Path) -> None:
    """Precision-weighted fusion: agreement must narrow the band, not just move the mean."""
    one = cfa.fuse([{"status": "MEASURED", "logit": 1.0, "logit_sd": 0.5}])
    two = cfa.fuse([{"status": "MEASURED", "logit": 1.0, "logit_sd": 0.5},
                    {"status": "MEASURED", "logit": 1.0, "logit_sd": 0.5}])
    assert two["logit_sd"] < one["logit_sd"]
    assert abs(two["mean"] - one["mean"]) < 1e-9
    wide = cfa.fuse([{"status": "MEASURED", "logit": 2.0, "logit_sd": 0.2},
                     {"status": "MEASURED", "logit": -2.0, "logit_sd": 2.0}])
    # the precise source wins; the vague one moves it a little and cannot flip it
    assert wide["logit_mean"] > 1.5
    assert cfa.fuse([{"status": "UNMEASURED"}])["status"] == "UNMEASURED"


# --------------------------------------------------------------------------------------- (b)
def _live(tree: Path) -> None:
    (tree / "data" / "cost_surface.json").write_text(json.dumps({
        "schema": "cost-surface-1", "symbols": {"TESTFX": {
            "tick_size": 0.00001, "contract_size": 100000.0,
            "pooled_median_spread_pts": 10.0,
            "hours": {"4": {"p50": 10.0, "status": "MEASURED"}}}}}), "utf-8")
    (tree / "data" / "order_intents.jsonl").write_text(
        json.dumps({"ticket": 1001, "intended": 1.10000, "symbol": "TESTFX"}) + "\n"
        + json.dumps({"ticket": 1002, "intended": 1.10000, "symbol": "TESTFX"}) + "\n", "utf-8")
    deals = []
    for i, (order, entry) in enumerate(((1001, 1.10000), (1002, 1.10050))):
        deals.append({"time": f"2026-03-0{2 + i}T04:30:00+00:00", "sleeve": "testfx_planted_edge",
                      "symbol": "TESTFX", "r_multiple": 0.5, "pl_quote": 50.0,
                      "risk_quote": 100.0, "volume": 0.1, "contract_size": 100000.0,
                      "commission": -0.2, "swap": 0.0, "deal": 9000 + i,
                      "entry_order": order, "entry_price": entry, "sl": entry - 0.01,
                      "fill_price": entry})
    (tree / "data" / "live_ledger.jsonl").write_text(
        "".join(json.dumps(d) + "\n" for d in deals), "utf-8")


def test_a_fill_that_cost_more_than_the_model_lands_in_the_execution_term(tree: Path) -> None:
    _axis(tree / "data" / "axes" / "shadow_global_risk_appetite.json")
    _live(tree)
    rep = cfa.build(budget_s=60, apply=False)
    rows = {r["deal"]: r for r in rep["trades"]["rows"]}
    assert len(rows) == 2 and rep["trades"]["counts"]["slippage_measured"] == 2

    clean, slipped = rows[9000], rows[9001]
    # the clean fill filled AT its intent: realised cost is commission alone, under the model
    assert clean["cost"]["slippage_quote"] == 0.0
    assert clean["cost"]["multiple"] < 1.0
    assert clean["execution"] > 0.0
    # the slipped fill paid 5.0 quote of slippage on a 100.0 risk: the model said 0.7
    assert slipped["cost"]["slippage_quote"] == pytest.approx(5.0, rel=1e-6)
    assert slipped["cost"]["multiple"] >= cfa.COST_SHOCK_MULTIPLE
    assert slipped["execution"] == pytest.approx((0.7 - 5.2) / 100.0, rel=1e-6)
    assert slipped["execution"] < clean["execution"]
    # AND IT IS NOT IN THE RESIDUAL: both deals share a sleeve, an R and a state, so the only
    # thing that differs between their decompositions is the execution term.
    assert slipped["residual"] == pytest.approx(clean["residual"], abs=1e-9)

    # the identity closes exactly on every row
    for row in rows.values():
        terms = sum(row.get(k) or 0.0 for k in ("unconditional", "conditional", "expected_cost",
                                                "execution", "financing", "residual"))
        assert terms == pytest.approx(row["r_net"], abs=1e-9)

    # the counterfactuals the desk can actually measure
    cf = slipped["counterfactuals"]
    assert cf["modelled_cost_r"] == pytest.approx(slipped["r_net"] - slipped["execution"])
    assert cf["modelled_cost_r"] > slipped["r_net"]           # the model was cheaper
    assert cf["not_taken_r"] == 0.0
    assert cf["not_taken_delta"] == pytest.approx(-slipped["r_net"])

    # and the excess is routed in the queue's OWN vocabulary
    shocks = cfa.cost_shock_rows(rep["trades"])
    assert [s["kind"] for s in shocks] == ["cost_shock"]
    assert shocks[0]["symbol"] == "TESTFX" and shocks[0]["multiple"] >= cfa.COST_SHOCK_MULTIPLE
    assert shocks[0]["producer"] == cfa.SOURCE


def test_the_routed_row_is_appended_once_and_only_when_applied(tree: Path) -> None:
    _axis(tree / "data" / "axes" / "shadow_global_risk_appetite.json")
    _live(tree)
    rep = cfa.build(budget_s=60, apply=False)
    shocks = cfa.cost_shock_rows(rep["trades"])

    dry = cfa.route(shocks, apply=False)
    assert dry["n_written"] == 0 and not cfa.UNKNOWN_QUEUE.exists()

    live = cfa.route(shocks, apply=True)
    assert live["n_written"] == 1
    rows = [json.loads(x) for x in cfa.UNKNOWN_QUEUE.read_text("utf-8").splitlines() if x.strip()]
    assert rows[0]["kind"] == "cost_shock" and rows[0]["producer"] == cfa.SOURCE
    # a second pass over the same hour must not duplicate the row
    again = cfa.route(shocks, apply=True)
    assert again["n_written"] == 0
    assert len(cfa.UNKNOWN_QUEUE.read_text("utf-8").splitlines()) == 1


def test_a_degenerate_risk_quote_is_recomputed_and_named(tree: Path) -> None:
    """The live defect this organ found: `risk_quote` in PRICE units with `r_multiple` at zero.
    Neither a fabricated zero R nor a five-figure one is acceptable."""
    _axis(tree / "data" / "axes" / "shadow_global_risk_appetite.json")
    (tree / "data" / "live_ledger.jsonl").write_text(json.dumps({
        "time": "2026-03-02T04:30:00+00:00", "sleeve": "testfx_planted_edge", "symbol": "TESTFX",
        "r_multiple": 0.0, "pl_quote": -3.24, "risk_quote": -0.00026, "volume": 0.1,
        "contract_size": 100000.0, "commission": -0.2, "swap": 0.0, "deal": 42,
        "entry_price": 0.85627, "sl": 0.85653}) + "\n", "utf-8")
    rep = cfa.build(budget_s=60, apply=False)
    row = rep["trades"]["rows"][0]
    assert rep["trades"]["counts"]["r_reconstructed"] == 1
    assert rep["trades"]["counts"]["risk_quote_disagrees"] == 1
    assert row["risk_quote_used"] == pytest.approx(2.6, rel=1e-6)
    assert row["r_realised"] == pytest.approx(-3.24 / 2.6, rel=1e-6)
    assert any("risk_quote" in u for u in row["unmeasured"])


# --------------------------------------------------------------------------------------- (c)
def test_absent_ledger_and_absent_world_model_give_unmeasured_and_a_written_report(
        tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Nothing exists in this tree at all. The pass must still finish and still publish."""
    assert not cfa.LIVE_LEDGER.exists() and not cfa.WORLD_MODEL.exists()
    assert cfa.main(["--once", "--budget-s", "30"]) == 0
    rep = json.loads(cfa.OUT.read_text("utf-8"))

    assert rep["inputs"]["live_ledger"]["status"] == "absent"
    assert rep["inputs"]["live_ledger"]["why"]
    assert rep["inputs"]["world_model"]["status"] == "absent"
    assert rep["global_posterior"]["n_measured"] == 0
    assert all(s["status"] == "UNMEASURED" and s["mean"] is None
               for s in rep["global_posterior"]["states"])
    assert rep["sleeves"]["primary_conditioning"] is None
    assert rep["trades"]["counts"]["attributed"] == 0
    assert rep["trades"]["rows"] == []
    names = {u["name"] for u in rep["unmeasured"]}
    assert "trade_attribution" in names and "conditional_sleeve_book" in names
    assert rep["allocates_capital"] is False
    assert "REFUSED" in rep["allocation_note"]
    assert capsys.readouterr().out.strip()


def test_a_sleeve_with_too_few_trades_is_unmeasured_not_zero(tree: Path) -> None:
    _axis(tree / "data" / "axes" / "shadow_global_risk_appetite.json")
    _ledger(tree / "reports" / "shadow" / "ledger_THIN_sleeve.json", [0.1, -0.2])
    rep = cfa.build(budget_s=60, apply=False)
    thin = [r for r in rep["sleeves"]["rows"] if r["sleeve"] == "thin_sleeve"]
    assert len(thin) == 1
    assert thin[0]["status"] == "UNMEASURED" and thin[0]["state"] is None
    assert str(cfa.MIN_SLEEVE_N) in thin[0]["why"]


# --------------------------------------------------------------------------------------- (d)
def test_dry_run_writes_nothing(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _axis(tree / "data" / "axes" / "shadow_global_risk_appetite.json")
    _live(tree)
    before = sorted(p.name for p in (tree / "reports").rglob("*"))
    assert cfa.main(["--once", "--budget-s", "30", "--dry-run"]) == 0
    assert not cfa.OUT.exists()
    assert not cfa.UNKNOWN_QUEUE.exists()
    assert sorted(p.name for p in (tree / "reports").rglob("*")) == before
    assert "dry run: nothing written" in capsys.readouterr().out


def test_the_organ_allocates_nothing(tree: Path) -> None:
    """P1 is REFUSED. Nothing in the artifact may be a capital instruction."""
    _axis(tree / "data" / "axes" / "shadow_global_risk_appetite.json")
    rep = cfa.build(budget_s=30, apply=False)
    assert rep["allocates_capital"] is False
    flat = json.dumps(rep)
    for forbidden in ('"risk_frac"', '"heat"', '"lot"', '"cap"', '"veto"'):
        assert forbidden not in flat, f"{forbidden} is a capital instruction, not evidence"
