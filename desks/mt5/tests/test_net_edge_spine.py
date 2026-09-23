"""THE NET-EDGE SPINE'S FENCES: the three doors, the backward judge, and what it may not do.

Every artifact the organ reads is planted in `tmp_path` and every module path is monkeypatched,
so nothing here touches a tracked file and no test depends on the box's own state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import net_edge as NE  # noqa: E402
from research import net_edge_spine as S  # noqa: E402

#: THE FOUR SEALED FILES. No organ this builder wrote may edit, import for mutation, or write
#: over any of them. The test below pins their bytes across a full pass.
SEALED = (
    _DESK / "scripts" / "external_gauntlet.py",
    _DESK / "research" / "promoter.py",
    _ROOT / "libs" / "portfolio" / "allocator_proof.py",
    _ROOT / "libs" / "regime" / "state_admission.py",
)


# --------------------------------------------------------------------------------- fixtures


def _plant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **override) -> Path:
    """A whole miniature desk: one expensive cell, one cheap one, and the tape to judge them."""
    reports, data = tmp_path / "reports", tmp_path / "data"
    reports.mkdir(parents=True)
    data.mkdir(parents=True)

    docs: dict[str, object] = {
        "COST_TO_EDGE.json": {"by_cost": [
            # EXPENSIVE: a 0.30R round trip against a 0.20R gross edge.
            {"symbol": "EXPENSIVE", "family": "scalp", "measured": True, "stop_pts": 10.0,
             "spread_pts": 3.0, "spread_r": 0.30, "swap_r": 0.0, "holds_overnight": False,
             "swap_pts_worse_side": 0.0, "total_cost_r": 0.30},
            {"symbol": "CHEAP", "family": "carry", "measured": True, "stop_pts": 100.0,
             "spread_pts": 1.0, "spread_r": 0.01, "swap_r": 0.0, "holds_overnight": False,
             "swap_pts_worse_side": 0.0, "total_cost_r": 0.01},
        ]},
        "FUSION_COST.json": {"commission_per_lot_per_side_usd": 2.25, "symbols": [
            {"symbol": "EXPENSIVE", "round_trip_per_lot": {"RAW": 10.0, "ZERO": 2.0}},
            {"symbol": "CHEAP", "round_trip_per_lot": {"RAW": 10.0, "ZERO": 2.0}},
        ]},
        "UNIVERSAL_SURVIVORS.json": {"survivors": {
            "hunt.EXPENSIVE": {"sym": "EXPENSIVE", "days": 200,
                               "shadow_spec": {"symbol": "EXPENSIVE", "family": "scalp"},
                               "gates": {"expected_value": {"ev": 0.20},
                                         "in_sample_screen": {"sharpe": 0.20},
                                         "deflated_sharpe": {"sr0": 0.05, "n_trials": 3000}}},
            "hunt.CHEAP": {"sym": "CHEAP", "days": 200,
                           "shadow_spec": {"symbol": "CHEAP", "family": "carry"},
                           "gates": {"expected_value": {"ev": 0.40},
                                     "in_sample_screen": {"sharpe": 0.40},
                                     "deflated_sharpe": {"sr0": 0.02, "n_trials": 3000}}},
        }},
        "POSTERIOR_ALPHA.json": {"sleeves": [
            {"name": "cheap_sleeve", "symbol": "CHEAP", "family": "carry", "lane": "forward",
             "n": 40, "mu_mean": 0.20, "sharpe_pp": 0.20},
            {"name": "expensive_sleeve", "symbol": "EXPENSIVE", "family": "scalp",
             "lane": "forward", "n": 40, "mu_mean": 0.10, "sharpe_pp": 0.10},
        ]},
        "FORWARD_SLOT_RANKER.json": {"running": [
            {"symbol": "CHEAP", "family": "carry", "lane": "shadow",
             "trade_rate_per_day": 1.0, "slot_value": 1e-3},
            {"symbol": "EXPENSIVE", "family": "scalp", "lane": "shadow",
             "trade_rate_per_day": 4.0, "slot_value": 9e-3},
        ], "waiting": []},
        "CAPACITY.json": {"rows": [{"sleeve": "cheap_sleeve", "ceiling_status": "UNMEASURED",
                                    "ceiling_why": "matched_fills is 0 on this host"}]},
        "COUNTERFACTUAL_ATTRIBUTION.json": {"trades": {"rows": [
            {"deal": 1, "symbol": "CHEAP", "r_realised": 0.30, "at": "2026-09-01T00:00:00+00:00"},
            {"deal": 2, "symbol": "CHEAP", "r_realised": 0.20, "at": "2026-09-02T00:00:00+00:00"},
            {"deal": 3, "symbol": "NOJOIN", "r_realised": 1.0, "at": "2026-09-03T00:00:00+00:00"},
        ]}},
        "pf_allocation.json": {"book": {"cheap_sleeve": 0.14, "expensive_sleeve": 0.08}},
    }
    docs.update(override)
    for name, payload in docs.items():
        (reports / name).write_text(json.dumps(payload), "utf-8")

    monkeypatch.setattr(S, "REPORTS", reports)
    monkeypatch.setattr(S, "DATA", data)
    monkeypatch.setattr(S, "OUT", reports / "NET_EDGE.json")
    monkeypatch.setattr(S, "RANKS", data / "net_edge_ranks.json")
    for attr in ("COST_TO_EDGE", "FUSION_COST", "EXEC_SURFACE", "SURVIVORS", "POSTERIOR",
                 "SLOTS", "CAPACITY", "ATTRIBUTION", "IMPACT", "ALLOCATION"):
        monkeypatch.setattr(S, attr, reports / Path(getattr(S, attr)).name)
    return tmp_path


# ------------------------------------------------------------------------------- the doors


def test_a_planted_gross_positive_cost_negative_cell_is_cost_dead_and_billed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(tmp_path, monkeypatch)
    rep = S.run(budget_s=60.0, write=True, donate_rows=False)

    dead = {r["symbol"] for r in rep["cost_dead"]}
    assert "EXPENSIVE" in dead, rep["cost_dead"]
    assert "CHEAP" not in dead
    assert rep["n_sign_flips"] >= 1

    # THE REFUSAL IS BILLED. A COST_DEAD verdict with no missed-growth line is a silent rail.
    billed = {line["symbol"] for line in rep["missed_growth_lines"]}
    assert "EXPENSIVE" in billed
    line = next(x for x in rep["missed_growth_lines"] if x["symbol"] == "EXPENSIVE")
    assert line["two_sided"] is True
    assert line["gross"] > 0 > line["net"]

    # AND IT IS KEPT, not dropped: the door-(a) contract still carries the cell and its whole
    # decomposition, so the compiler can mark it rather than lose it.
    ranks = json.loads(S.RANKS.read_text("utf-8"))
    hit = ranks["by_cell"]["EXPENSIVE|scalp"]
    assert hit["verdict"].startswith("COST_DEAD")
    assert set(hit["terms"]) == set(NE.TERMS)
    assert hit["terms"]["spread_slippage"]["value"] == pytest.approx(0.30)


def test_the_intake_contract_ranks_by_net_and_never_by_gross(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(tmp_path, monkeypatch)
    rep = S.run(budget_s=60.0, write=True, donate_rows=False)
    ordered = [r["key"] for r in rep["ranked_if_net_were_the_only_ranking"]]
    nets = [r["net"] for r in rep["ranked_if_net_were_the_only_ranking"] if r["net"] is not None]
    assert nets == sorted(nets, reverse=True)
    assert ordered[0].endswith("CHEAP") or "CHEAP" in ordered[0] or "cheap" in ordered[0]


def test_the_forward_slot_ranking_prefers_net_expected_growth_over_gross(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """EXPENSIVE holds the larger GROSS slot value (9e-3 vs 1e-3) and still loses the slot,
    because its net/gross ratio is negative. That reordering is the whole point of door (b)."""
    _plant(tmp_path, monkeypatch)
    rep = S.run(budget_s=60.0, write=True, donate_rows=False)
    rows = rep["forward_slot_ranking_by_net"]
    by_symbol = {r["symbol"]: r for r in rows}
    assert by_symbol["EXPENSIVE"]["slot_value"] > by_symbol["CHEAP"]["slot_value"]
    assert by_symbol["EXPENSIVE"]["net_slot_value"] < by_symbol["CHEAP"]["net_slot_value"]
    assert rows[0]["symbol"] == "CHEAP"


def test_the_allocator_contract_carries_a_capacity_per_sleeve_with_its_status(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(tmp_path, monkeypatch)
    rep = S.run(budget_s=60.0, write=True, donate_rows=False)
    caps = rep["capacity_by_sleeve"]
    assert caps, "the allocator door must publish a row per forward sleeve"
    for row in caps.values():
        assert "capacity" in row and "status" in row["capacity"]
        # No matched fills on this planted host, so every capacity is UNMEASURED WITH A REASON
        # and never an unlimited size.
        assert row["capacity"]["status"] == NE.UNMEASURED
        assert row["capacity"]["lots"] is None
        assert row["capacity"]["why"]

    from libs.portfolio import allocator_evidence as AE
    terms, why = AE.net_of_cost_factors(rep)
    assert terms and why
    assert all(t.name == "net_of_cost" for t in terms.values())
    assert all(0.5 <= t.factor <= 2.0 for t in terms.values())
    rows = AE.net_capacity_rows(rep)
    assert set(rows) == set(caps)


# ------------------------------------------------------------- unmeasured, heat, the sealed


def test_an_unmeasured_cost_term_never_reads_as_zero_in_the_report(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip the cost inputs entirely: every term must come back UNMEASURED with a reason, and
    NOT a priced zero that would make every cell look free."""
    _plant(tmp_path, monkeypatch, **{"COST_TO_EDGE.json": {"by_cost": []},
                                     "FUSION_COST.json": {"symbols": []}})
    rep = S.run(budget_s=60.0, write=True, donate_rows=False)
    assert rep["term_coverage"]["spread_slippage"] == 0
    assert rep["term_coverage"]["financing"] == 0
    assert rep["term_coverage"]["commission"] == 0
    assert rep["term_coverage"]["impact"] == 0
    for row in rep["ranked_if_net_were_the_only_ranking"]:
        for name in ("spread_slippage", "financing", "commission", "impact"):
            term = row["terms"][name]
            assert term["status"] == NE.UNMEASURED
            assert term["value"] is None
            assert term["note"], f"{name} must say WHY it is unmeasured"
        assert row["net_is_bound"] is True
        assert row["verdict"] != NE.NET_POSITIVE      # never a clean pass on unpriced costs


def test_the_pass_never_reduces_the_book_heat(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(tmp_path, monkeypatch)
    rep = S.run(budget_s=60.0, write=True, donate_rows=False)
    heat = rep["heat_reallocation"]
    assert heat["status"] == NE.MEASURED
    assert heat["heat_preserved"] is True
    assert heat["heat_after"] == pytest.approx(heat["heat_before"], abs=1e-9)
    assert heat["heat_after"] == pytest.approx(0.14 + 0.08, abs=1e-9)
    # ...and the pass wrote ONLY its own two artifacts. A spine that could touch the roster or
    # the allocation would be a second allocator wearing a cost model.
    assert S.OUT.exists() and S.RANKS.exists()
    assert not (S.DATA / "sleeves.json").exists()
    assert json.loads(S.REPORTS.joinpath("pf_allocation.json").read_text("utf-8"))["book"] == {
        "cheap_sleeve": 0.14, "expensive_sleeve": 0.08}
    assert "vetoes, caps or sizes" in S.RULE


def test_the_backward_judge_scores_the_cost_model_and_names_what_it_cannot_score(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(tmp_path, monkeypatch)
    rep = S.run(budget_s=60.0, write=True, donate_rows=False)
    errs = rep["prediction_errors"]
    scored = [e for e in errs if e["status"] == NE.MEASURED]
    unscored = [e for e in errs if e["status"] == NE.UNMEASURED]
    assert len(scored) == 2 and all(e["symbol"] == "CHEAP" for e in scored)
    assert len(unscored) == 1 and "NOJOIN" in unscored[0]["why"]
    cal = rep["cost_model_calibration"]
    assert cal["n"] == 2 and cal["status"] == NE.MEASURED
    assert cal["verdict"] in ("CALIBRATED", "OVER_CHARGING", "UNDER_CHARGING")


def test_an_empty_host_produces_a_verdict_and_not_a_crash(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reports, data = tmp_path / "reports", tmp_path / "data"
    reports.mkdir(parents=True)
    data.mkdir(parents=True)
    monkeypatch.setattr(S, "OUT", reports / "NET_EDGE.json")
    monkeypatch.setattr(S, "RANKS", data / "net_edge_ranks.json")
    for attr in ("COST_TO_EDGE", "FUSION_COST", "EXEC_SURFACE", "SURVIVORS", "POSTERIOR",
                 "SLOTS", "CAPACITY", "ATTRIBUTION", "IMPACT", "ALLOCATION"):
        monkeypatch.setattr(S, attr, reports / Path(getattr(S, attr)).name)
    rep = S.run(budget_s=5.0, write=True, donate_rows=False)
    assert rep["n_rows"] == 0
    assert rep["unmeasured"], "an empty host must SAY what was absent"
    assert rep["heat_reallocation"]["status"] == NE.UNMEASURED
    assert rep["cost_model_calibration"]["status"] == NE.UNMEASURED
    assert S.OUT.exists() and S.RANKS.exists()


def test_the_four_sealed_files_are_untouched_by_a_whole_pass(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = {p: p.read_bytes() for p in SEALED if p.exists()}
    assert len(before) == 4, f"a sealed file is missing from this tree: {before.keys()}"
    _plant(tmp_path, monkeypatch)
    S.run(budget_s=60.0, write=True, donate_rows=False)
    for path, blob in before.items():
        assert path.read_bytes() == blob, f"{path} was modified by the net-edge pass"
    source = Path(S.__file__).read_text("utf-8")
    for name in ("external_gauntlet", "promoter", "allocator_proof", "state_admission"):
        assert f"import {name}" not in source and f"from {name}" not in source


def test_the_leg_is_scheduled_layered_and_budgeted() -> None:
    """UNWIRED OR IDLE IS A DEFECT (LAWS III.16): the clock, the layer and the cap, pinned."""
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["net_edge"] == "execution"
    cycle = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("net_edge"' in cycle
    assert '"research/net_edge_spine.py"' in cycle
    assert '"--once", "--budget-s", "600"' in cycle
    assert '"net_edge": nee' in cycle
    assert '"net_edge": 700' in cycle
    from research.hourly_cycle import LEG_DEPARTMENT
    assert LEG_DEPARTMENT["net_edge"] == "execution"


def test_both_doors_read_the_join_file_this_organ_writes() -> None:
    """A CONSUMER OR IT IS NOT DONE. Door (a) and door (b) must name the contract by path."""
    compiler = (_DESK / "research" / "miner_candidate_compiler.py").read_text("utf-8")
    assert "net_edge_ranks.json" in compiler and "COST_DEAD" in compiler
    ranker = (_DESK / "research" / "forward_slot_ranker.py").read_text("utf-8")
    assert "net_edge_ranks.json" in ranker and "net_slot_value" in ranker
    lab = (_DESK / "research" / "financing_lab.py").read_text("utf-8")
    assert "net_of_cost_factors" in lab


# ---------------------------------------------------------------- the commission term's unit


def test_commission_rides_on_the_FULL_spread_not_on_the_raw_regimes_fifth() -> None:
    """THE 5x THAT KILLED EIGHT EURCHF CELLS (measured 2026-09-23, reports/COST_TRUTH.json).

    `fusion_cost.COST_REGIMES` is a table of SPREAD MULTIPLIERS -- RAW is 0.2 -- so the published
    round trips satisfy RAW - ZERO = 0.2 x spread, NOT spread. The old ratio zero/(raw-zero)
    therefore billed commission at 1/0.2 = 5x the truth, on the term that is ~98% of this
    account's charged cost.
    """
    from libs.portfolio.fusion_cost import COST_REGIMES
    mult = COST_REGIMES["RAW"]
    # a venue charging 2.00 per lot of commission against a full spread of 10.0 per lot
    full_spread, commission = 10.0, 2.00
    row = {"symbol": "X", "round_trip_per_lot": {"ZERO": commission,
                                                 "RAW": commission + mult * full_spread,
                                                 "WIDE": commission + 2.0 * full_spread}}
    term = S.commission_term({"spread_r": 0.01}, row)
    # commission is 2.00/10.0 = 0.2 of ONE crossing of the spread, so 0.2 x spread_r
    assert term.value == pytest.approx(0.01 * commission / full_spread)
    # and the pre-fix arithmetic would have been exactly 1/mult times larger
    assert term.value == pytest.approx(0.01 * (commission / (mult * full_spread)) * mult)


def test_a_one_R_stop_can_no_longer_be_billed_a_majority_of_its_risk_in_commission() -> None:
    """EIGHT EURCHF CELLS DIED COST_DEAD ON A COMMISSION THAT ATE MOST OF THEIR 1R STOP.

    EURCHF's own published numbers, from the artifacts this organ reads: spread_r 0.0084 over a
    118.8 pt stop, round trip ZERO 7.2670 against RAW 7.4170 -- so RAW - ZERO is 0.15, which is
    one FIFTH of the 0.75 full spread and not the spread. Old ratio 48.4464x -> 0.4069R of
    commission on a 1R stop; corrected ratio 9.6893x -> 0.0814R. Re-generating FUSION_COST.json
    at the MEASURED 2.00 per side (it was built at 2.25) takes it to ~0.0723R.
    """
    row = {"symbol": "EURCHF", "round_trip_per_lot": {"RAW": 7.4170, "ZERO": 7.2670,
                                                      "WIDE": 8.7670}}
    term = S.commission_term({"spread_r": 0.0084}, row)
    assert term.value == pytest.approx(0.0814, abs=5e-4)
    # the arithmetic it replaced, pinned so the regression is visible and not just described
    as_charged_before = 0.0084 * (7.2670 / (7.4170 - 7.2670))
    assert as_charged_before == pytest.approx(0.4069, abs=5e-4)
    assert term.value * 5.0 == pytest.approx(as_charged_before, rel=1e-6)
    assert term.value < 0.5, "commission may not eat a majority of a 1R stop"
    assert term.status == NE.MODELLED


def test_an_unreadable_regime_table_still_prices_and_says_so() -> None:
    mult, src = S.raw_regime_mult()
    assert 0 < mult <= 1.0
    assert "fusion_cost.COST_REGIMES" in src
