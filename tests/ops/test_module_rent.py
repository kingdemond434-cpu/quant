"""Module rent: every component is billed Elog_with - Elog_without, and nothing sacred.

    "Module Rent = Elog_with - Elog_without for every component; if persistently <= 0, retire it.
     This includes AI. No sacred modules."                          -- the principal, 2026-09-05

What is pinned here, per rent kind, on KNOWN-ANSWER fixtures -- a tree whose ledgers were written
to make one verdict the only arithmetically possible one:

  * a rail that earns is REUSED from the missed-growth ledger, not recomputed, and the two
    reports cannot disagree about its number, its n or its sign;
  * an execution algorithm that costs more per fill than the market baseline reads COSTS, the
    baseline is NOT_BINDING against itself, and a thin sample is UNMEASURED with its count;
  * a proposer arm and a data source that burned trials and put no growth in the funded book are
    named -- dead information is a COSTS verdict, not a quiet zero;
  * a state dimension the admission gauntlet buried COSTS and an admitted one EARNS;
  * the conditioning ledger prices the state modifier in log-wealth per day from realised R;
  * the allocator's own components are billed against the baselines their artifact already
    carries, and the AI organs sit on the same list as everything else;
  * the RETIRE list names a module only after K consecutive weekly windows of COSTS at n >= MIN_N,
    a gap in the record breaks the run, and a missing ledger is UNMEASURED with the path -- never
    folded into a pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.ops import module_rent as mr

DAY = "2026-09-05"


# --------------------------------------------------------------------------- fixture tree
def _write(root: Path, rel: str, doc: Any) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), "utf-8")


def _write_lines(root: Path, rel: str, rows: list[dict[str, Any]]) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A desk tree with nothing in it. Every test writes only the ledger it is about, so a
    verdict can never be borrowed from a neighbouring fixture."""
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    return tmp_path


def _module(name: str) -> mr.Module:
    for m in mr.MODULES:
        if m.name == name:
            return m
    raise AssertionError(f"{name} is not in the registry")


# --------------------------------------------------------------------------- the registry
def test_every_registered_module_declares_a_kind_a_ledger_and_a_measure_that_exists() -> None:
    assert mr.MODULES, "an empty registry bills nothing and would pass every check vacuously"
    for m in mr.MODULES:
        assert m.kind in mr.KINDS, m.name
        assert m.ledger and m.rule, m.name
        assert m.measure in mr.MEASURES, f"{m.name} names a measure that does not exist"
    names = [m.name for m in mr.MODULES]
    assert len(names) == len(set(names)), "a duplicated module would be billed twice"


def test_the_ai_organs_are_on_the_same_list_as_every_other_component() -> None:
    """"This includes AI. No sacred modules." -- so the AI organs must be billable rows."""
    ai = {m.name for m in mr.MODULES if m.kind == "ai_organ"}
    assert "ai_capital_modifier" in ai
    assert ai & set(mr.AI_ORGANS), "the LLM-driven miners carry no rent line"


def test_a_missing_ledger_is_unmeasured_with_the_path_and_never_a_pass(tree: Path) -> None:
    out = mr.measure(tree)
    assert out, "an empty tree must still produce a row per module"
    for name, row in out.items():
        assert row["verdict"] == mr.UNMEASURED, name
        assert row["why"], f"{name} is UNMEASURED without saying why"
    assert mr.MISSED_GROWTH in out["regime_hibernate"]["why"]


# --------------------------------------------------------------------------- rails
def test_a_rail_that_earns_is_reused_from_missed_growth_verbatim(tree: Path) -> None:
    _write(tree, mr.MISSED_GROWTH, {"rails": {
        "state_gate": {"kind": "gate", "verdict": "EARNS_ITS_PLACE", "n": 42,
                       "mean_logw_per_day": 0.0012, "t": 3.4},
        "hard_ceiling": {"kind": "cap", "verdict": "COSTS_GROWTH", "n": 30,
                         "mean_logw_per_day": -0.0004, "t": -2.9},
        "fade": {"kind": "shrink", "verdict": "UNMEASURED", "why": "needs live fills"},
    }})
    out = mr.measure(tree, (_module("state_gate"), _module("hard_ceiling"), _module("fade")))
    earns = out["state_gate"]
    assert earns["verdict"] == mr.EARNS
    assert earns["rent_logw_per_day"] == pytest.approx(0.0012)
    assert earns["n"] == 42 and earns["unit"] == "log-wealth/day"
    assert earns["ledger"] == mr.MISSED_GROWTH
    assert earns["missed_growth_verdict"] == "EARNS_ITS_PLACE"
    lo, hi = earns["ci"]
    assert lo < 0.0012 < hi, "a CI that does not straddle its own mean is not a CI"
    assert out["hard_ceiling"]["verdict"] == mr.COSTS
    assert out["hard_ceiling"]["rent_logw_per_day"] == pytest.approx(-0.0004)
    assert out["fade"]["verdict"] == mr.UNMEASURED


def test_a_rail_priced_per_veto_keeps_its_own_unit(tree: Path) -> None:
    """Vetoes are priced per VETO, not per day. Reporting them in log-wealth/day would compare
    a rail that fired twice with one that fired daily as if they were the same number."""
    _write(tree, mr.MISSED_GROWTH, {"rails": {
        "state_gate": {"kind": "gate", "verdict": "EARNS_ITS_PLACE", "n": 20,
                       "value_logw_per_veto": 0.004, "t": 2.5}}})
    row = mr.measure(tree, (_module("state_gate"),))["state_gate"]
    assert row["unit"] == "log-wealth/veto"
    assert row["rent"] == pytest.approx(0.004)
    assert row["rent_logw_per_day"] is None, "a per-veto number must not read as a per-day one"


# --------------------------------------------------------------------------- execution algos
def _algo_rows(algo: str, cost: float, n: int, filled: float = 1.0) -> list[dict[str, Any]]:
    # A deterministic spread around the mean so the t-statistic is finite and the sign is the
    # fixture's, not the random seed's.
    return [{"algo": algo, "realised_cost": cost + (0.00001 if i % 2 else -0.00001),
             "filled_frac": filled, "expected_cost": cost} for i in range(n)]


def test_an_algorithm_that_costs_more_per_fill_than_the_market_baseline_reads_costs(
        tree: Path) -> None:
    _write_lines(tree, mr.ALGO_OUTCOMES,
                 _algo_rows("market", 0.0010, 30) + _algo_rows("sniper", 0.0025, 30))
    out = mr.measure(tree, (_module("execution_algo:sniper"), _module("execution_algo:market")))
    sniper = out["execution_algo:sniper"]
    assert sniper["verdict"] == mr.COSTS
    assert sniper["unit"] == "price_frac/fill"
    assert sniper["rent"] == pytest.approx(0.0010 - 0.0025, abs=1e-9)
    assert sniper["n"] == 30
    assert sniper["ci"][1] < 0, "a COSTS verdict whose interval touches zero is not a verdict"
    base = out["execution_algo:market"]
    assert base["verdict"] == mr.NOT_BINDING and base["rent"] == 0.0
    assert "baseline" in base["why"], "the baseline must say why its own rent is zero"


def test_an_algorithm_that_beats_the_baseline_earns(tree: Path) -> None:
    _write_lines(tree, mr.ALGO_OUTCOMES,
                 _algo_rows("market", 0.0025, 30) + _algo_rows("twap", 0.0010, 30))
    row = mr.measure(tree, (_module("execution_algo:twap"),))["execution_algo:twap"]
    assert row["verdict"] == mr.EARNS and row["rent"] > 0


def test_a_thin_algorithm_sample_is_unmeasured_and_says_how_many(tree: Path) -> None:
    _write_lines(tree, mr.ALGO_OUTCOMES,
                 _algo_rows("market", 0.0010, 30) + _algo_rows("sniper", 0.0025, 3))
    row = mr.measure(tree, (_module("execution_algo:sniper"),))["execution_algo:sniper"]
    assert row["verdict"] == mr.UNMEASURED
    assert row["n"] == 3 and str(mr.MIN_N) in row["why"]


def test_an_algorithm_that_fills_far_less_of_its_lots_is_not_compared_on_the_subset_that_filled(
        tree: Path) -> None:
    """A cost advantage measured only on the plans that filled is a selection effect wearing an
    execution result: the plans it walked away from are the expensive ones."""
    _write_lines(tree, mr.ALGO_OUTCOMES,
                 _algo_rows("market", 0.0025, 30, filled=1.0)
                 + _algo_rows("iceberg", 0.0005, 30, filled=0.3))
    row = mr.measure(tree, (_module("execution_algo:iceberg"),))["execution_algo:iceberg"]
    assert row["verdict"] == mr.UNMEASURED
    assert "not comparable" in row["why"]


# --------------------------------------------------------------------------- proposers, sources
def test_a_proposer_arm_that_burned_trials_and_funded_no_growth_is_named_dead(tree: Path) -> None:
    _write(tree, mr.RESEARCH_PNL, {"arms": {
        "new_mechanism": {"trials": 400, "certified": 3, "growth_per_day": 0.002,
                          "cost_units": 3600.0, "sources": ["alpha_evolution"]},
        "alt_data_hypothesis": {"trials": 250, "certified": 0, "growth_per_day": 0.0,
                                "cost_units": 2250.0, "sources": ["data_prospector"]}}})
    out = mr.measure(tree, (_module("new_mechanism"), _module("alt_data_hypothesis")))
    good = out["new_mechanism"]
    assert good["verdict"] == mr.EARNS and good["rent_logw_per_day"] == pytest.approx(0.002)
    assert good["spend_cost_units"] == pytest.approx(3600.0)
    assert good["roi_growth_per_cost_unit"] is not None
    dead = out["alt_data_hypothesis"]
    assert dead["verdict"] == mr.COSTS
    assert "dead information" in dead["why"]
    assert dead["n"] == 250


def test_an_arm_with_no_trials_at_all_is_not_binding_rather_than_costing(tree: Path) -> None:
    """A cold arm has not been tried; charging it for growth it never had a chance to make is
    how a desk retires the only arm that could have found the next mechanism."""
    _write(tree, mr.RESEARCH_PNL,
           {"arms": {"failure_derived": {"trials": 0, "certified": 0, "growth_per_day": 0.0,
                                         "cost_units": 0.0}}})
    row = mr.measure(tree, (_module("failure_derived"),))["failure_derived"]
    assert row["verdict"] == mr.NOT_BINDING and row["n"] == 0


def test_a_data_source_rolls_up_every_row_that_carries_its_prefix(tree: Path) -> None:
    """The world forest splits one organ across a source per region cluster; the ORGAN is what is
    being billed, so its rows are summed rather than judged one region at a time."""
    _write(tree, mr.RESEARCH_PNL, {"sources": {
        "deep_forest": {"trials": 100, "certified": 1, "growth_per_day": 0.001,
                        "cost_units": 900.0},
        "deep_forest_jp": {"trials": 40, "certified": 0, "growth_per_day": 0.0,
                           "cost_units": 360.0},
        "alpha_evolution": {"trials": 900, "certified": 9, "growth_per_day": 0.02,
                            "cost_units": 8100.0}}})
    row = mr.measure(tree, (_module("deep_forest_miner"),))["deep_forest_miner"]
    assert row["verdict"] == mr.EARNS
    assert row["n"] == 140, "both deep-forest rows belong to the organ"
    assert row["rent_logw_per_day"] == pytest.approx(0.001)
    assert "alpha_evolution" not in row["sources"]


# --------------------------------------------------------------------------- state dimensions
def test_a_dimension_the_gauntlet_buried_costs_and_an_admitted_one_earns(tree: Path) -> None:
    _write(tree, mr.STATE_ADMISSION, {"verdicts": {
        "session": {"verdict": "ADMIT", "mse_gain": 0.31, "t_deflated": 3.9, "n_test": 400},
        "event": {"verdict": "GRAVEYARD", "mse_gain": -0.22, "t_deflated": -3.1, "n_test": 350},
        "weekday": {"verdict": "RETAIN_SHRUNK", "mse_gain": -0.02, "t_deflated": -0.4,
                    "n_test": 275, "why": "kept by the shrinkage only"}}})
    mods = tuple(_module(f"state_dimension:{d}") for d in ("session", "event", "weekday"))
    out = mr.measure(tree, mods)
    assert out["state_dimension:session"]["verdict"] == mr.EARNS
    assert out["state_dimension:session"]["unit"] == "oos_mse_gain"
    assert out["state_dimension:session"]["rent_logw_per_day"] is None, (
        "an MSE gain is not log-wealth and must not be reported as if it were")
    assert out["state_dimension:event"]["verdict"] == mr.COSTS
    assert out["state_dimension:weekday"]["verdict"] == mr.UNMEASURED


def test_a_dimension_with_no_labeller_reports_the_gap_the_admission_report_recorded(
        tree: Path) -> None:
    _write(tree, mr.STATE_ADMISSION,
           {"verdicts": {}, "gaps": {"session": "no labeller: the broker clock is unavailable"}})
    row = mr.measure(tree, (_module("state_dimension:session"),))["state_dimension:session"]
    assert row["verdict"] == mr.UNMEASURED and "no labeller" in row["why"]


def test_the_conditioning_ledger_prices_the_state_modifier_in_log_wealth_per_day(
        tree: Path) -> None:
    """h x (1 - 1/mult) x realised R, per day: the growth the modifier's heat move earned.

    A multiplier of 2.0 doubles the heat, so half of what the day earned is the modifier's; the
    fixture makes 12 such days all positive, which is the only sign the arithmetic allows.
    """
    days = [f"2026-08-{d:02d}" for d in range(1, 13)]
    _write_lines(tree, mr.MODIFIER_LEDGER,
                 [{"t": f"{d}T12:00:00+00:00", "sleeve": "S", "state": "trend",
                   "category": "BOOST", "multiplier": 2.0, "heat": 0.02} for d in days])
    _write_lines(tree, mr.LIVE_LEDGER,
                 [{"sleeve": "S", "close_time": f"{d}T20:00:00+00:00", "r_multiple": 1.0}
                  for d in days])
    row = mr.measure(tree, (_module("state_posterior"),))["state_posterior"]
    assert row["verdict"] == mr.EARNS
    assert row["n"] == 12
    assert row["rent_logw_per_day"] == pytest.approx(0.02 * 0.5)
    assert row["joined_rows"] == 12


def test_a_conditioning_ledger_that_joins_no_realised_day_is_unmeasured(tree: Path) -> None:
    _write_lines(tree, mr.MODIFIER_LEDGER,
                 [{"t": "2026-08-01T12:00:00+00:00", "sleeve": "S", "multiplier": 1.5,
                   "heat": 0.02}])
    row = mr.measure(tree, (_module("state_posterior"),))["state_posterior"]
    assert row["verdict"] == mr.UNMEASURED
    assert "realised" in row["why"] and row["ledger_rows"] == 1


# --------------------------------------------------------------------------- allocator, kelly
def test_the_allocator_components_are_billed_against_the_baselines_their_artifact_carries(
        tree: Path) -> None:
    _write(tree, mr.ALLOCATION, {
        "proof": {"passed": True, "best_baseline": "equal_weight",
                  "scores": {"dynamic": 0.0031, "equal_weight": 0.0022}},
        "evidence": {"worlds": 4000},
        "posterior_growth": {"adopted": True,
                             "vs_funded": {"delta_elogw_per_day": 0.0004, "ci_lo": 0.0001,
                                           "ci_hi": 0.0007, "beats": True, "n_paths": 2000}},
        "kelly_surface": {"f_tail": 0.6,
                          "rows": [{"f": 0.6, "mean_growth": 0.0024},
                                   {"f": 1.0, "mean_growth": 0.0029}]},
        "regime": {"conditioned": False}})
    mods = tuple(_module(n) for n in ("pf_allocator:dynamic_weights",
                                      "pf_allocator:posterior_growth",
                                      "pf_allocator:kelly_surface",
                                      "pf_allocator:regime_conditioning"))
    out = mr.measure(tree, mods)
    dyn = out["pf_allocator:dynamic_weights"]
    assert dyn["verdict"] == mr.EARNS
    assert dyn["rent_logw_per_day"] == pytest.approx(0.0031 - 0.0022)
    assert dyn["n"] == 4000 and dyn["best_baseline"] == "equal_weight"
    post = out["pf_allocator:posterior_growth"]
    assert post["verdict"] == mr.EARNS and post["ci"] == [0.0001, 0.0007]
    kelly = out["pf_allocator:kelly_surface"]
    assert kelly["verdict"] == mr.COSTS
    assert kelly["rent_logw_per_day"] == pytest.approx(0.0024 - 0.0029)
    assert "ruin it refused" in kelly["note"], (
        "a tail bound's negative rent must be read against the ruin it declined, not alone")
    assert out["pf_allocator:regime_conditioning"]["verdict"] == mr.NOT_BINDING


def test_a_tail_bound_that_does_not_bind_costs_nothing(tree: Path) -> None:
    _write(tree, mr.ALLOCATION, {"kelly_surface": {"f_tail": 1.0,
                                                   "rows": [{"f": 1.0, "mean_growth": 0.003}]}})
    row = mr.measure(tree, (_module("pf_allocator:kelly_surface"),))["pf_allocator:kelly_surface"]
    assert row["verdict"] == mr.NOT_BINDING and row["rent"] == 0.0


# --------------------------------------------------------------------------- discovery
def test_an_algorithm_the_registry_does_not_name_is_still_billed(tree: Path) -> None:
    """A component nothing bills is a component nothing can retire. An unnamed algorithm showing
    up on the outcomes ledger must be measured under the same rule, not left off the report."""
    _write_lines(tree, mr.ALGO_OUTCOMES,
                 _algo_rows("market", 0.0010, 30) + _algo_rows("adaptive_peg", 0.0030, 30))
    out = mr.measure(tree)
    assert "execution_algo:adaptive_peg" in out
    assert out["execution_algo:adaptive_peg"]["verdict"] == mr.COSTS


# --------------------------------------------------------------------------- the RETIRE list
def _history(module: str, weeks: list[str], verdict: str, n: int = 30) -> list[dict[str, Any]]:
    return [{"day": w, "module": module, "kind": "execution_algo", "verdict": verdict,
             "rent": -0.001, "unit": "price_frac/fill", "n": n,
             "ci": [-0.002, -0.0005], "ledger": mr.ALGO_OUTCOMES} for w in weeks]


WEEKS = ["2026-08-17", "2026-08-24", "2026-08-31"]          # three consecutive Mondays


def test_the_retire_list_names_nothing_before_k_windows_and_names_after() -> None:
    for k in range(1, mr.K_WINDOWS):
        assert not mr.retire_list(_history("execution_algo:sniper", WEEKS[-k:], mr.COSTS)), (
            f"{k} window(s) of COSTS is not the {mr.K_WINDOWS} the rule requires")
    named = mr.retire_list(_history("execution_algo:sniper", WEEKS, mr.COSTS))
    assert set(named) == {"execution_algo:sniper"}
    assert named["execution_algo:sniper"]["windows_costs"] == mr.K_WINDOWS
    assert named["execution_algo:sniper"]["since_window"] == "2026-08-17"
    assert named["execution_algo:sniper"]["ledger"] == mr.ALGO_OUTCOMES


def test_a_thin_window_does_not_count_toward_retirement() -> None:
    rows = _history("execution_algo:sniper", WEEKS, mr.COSTS)
    rows[1]["n"] = mr.MIN_N - 1
    assert not mr.retire_list(rows), "a COSTS verdict under MIN_N is not evidence of costing"


def test_a_gap_in_the_record_breaks_the_run_because_silence_is_not_a_costs_verdict() -> None:
    weeks = ["2026-08-03", "2026-08-17", "2026-08-24", "2026-08-31"]   # 2026-08-10 missing
    named = mr.retire_list(_history("execution_algo:sniper", weeks, mr.COSTS))
    assert named["execution_algo:sniper"]["windows_costs"] == 3
    assert named["execution_algo:sniper"]["since_window"] == "2026-08-17"
    short = mr.retire_list(_history("execution_algo:sniper", ["2026-08-03", "2026-08-24",
                                                              "2026-08-31"], mr.COSTS))
    assert not short, "two windows either side of a gap are not three consecutive ones"


def test_one_window_that_is_not_costs_ends_the_run() -> None:
    rows = _history("execution_algo:sniper", WEEKS, mr.COSTS)
    rows[-1]["verdict"] = mr.UNMEASURED
    assert not mr.retire_list(rows)


def test_the_last_reading_in_a_window_speaks_for_it() -> None:
    """A rerun on a later day supersedes the earlier one; it does not add a second window."""
    rows = _history("execution_algo:sniper", WEEKS, mr.COSTS)
    rows.append({**rows[-1], "day": "2026-09-04", "verdict": mr.EARNS})
    assert not mr.retire_list(rows), "the week's last reading was EARNS, so the run is broken"


# --------------------------------------------------------------------------- the pass
def test_run_writes_one_row_per_module_per_day_and_a_second_pass_adds_nothing(tree: Path) -> None:
    _write(tree, mr.MISSED_GROWTH, {"rails": {
        "state_gate": {"kind": "gate", "verdict": "EARNS_ITS_PLACE", "n": 42,
                       "mean_logw_per_day": 0.0012, "t": 3.4}}})
    first = mr.run(tree, today=DAY)
    rows = [json.loads(x) for x in (tree / mr.HISTORY).read_text("utf-8").splitlines() if x]
    assert len(rows) == first["n_modules"] == len(first["modules"])
    assert {r["day"] for r in rows} == {DAY}
    second = mr.run(tree, today=DAY)
    assert second["new_rows"] == 0
    again = [json.loads(x) for x in (tree / mr.HISTORY).read_text("utf-8").splitlines() if x]
    assert len(again) == len(rows), "a re-run on the same day must not double the ledger"
    doc = json.loads((tree / mr.REPORT).read_text("utf-8"))
    assert doc["modules"]["state_gate"]["verdict"] == mr.EARNS
    assert "state_gate" in doc["earns"] and doc["retire"] == {}
    assert doc["lines"] == {"min_n": mr.MIN_N, "t_line": mr.T_LINE, "k_windows": mr.K_WINDOWS}
    assert set(doc["by_kind"]) == set(mr.KINDS)


def test_the_report_names_for_retirement_only_from_its_own_accumulated_history(
        tree: Path) -> None:
    """The report NAMES; a person or the graph check retires. Three windows of COSTS on the
    module's own history is the whole bar, and today's pass is the third."""
    _write_lines(tree, mr.ALGO_OUTCOMES,
                 _algo_rows("market", 0.0010, 30) + _algo_rows("sniper", 0.0025, 30))
    _write_lines(tree, mr.HISTORY, _history("execution_algo:sniper", WEEKS[:2], mr.COSTS))
    doc = mr.run(tree, today="2026-09-02")           # the Monday of the third window
    assert "execution_algo:sniper" in doc["retire"]
    assert doc["retire"]["execution_algo:sniper"]["windows_costs"] == mr.K_WINDOWS
    assert "names" in doc["rule"] and "retires" in doc["rule"]


def test_a_broken_ledger_is_a_reading_and_not_a_crash(tree: Path) -> None:
    p = tree / mr.MISSED_GROWTH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ this is not json", "utf-8")
    row = mr.measure(tree, (_module("state_gate"),))["state_gate"]
    assert row["verdict"] == mr.UNMEASURED
