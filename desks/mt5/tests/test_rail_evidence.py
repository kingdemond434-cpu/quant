"""Two rails' evidence: where the veto table comes from, and what the effective ceiling cost.

Both are cases of the same defect this desk keeps finding -- a better measurement existed and the
ledger that bills the rail was reading the older one:

  * VETO EVIDENCE. `counterfactual_replay` prices every decision minute, both sides, against
    every alternative, on one axis with the desk's own cost posterior, and publishes the result
    under the SAME field names `FILTER_VALUE.json` uses. `measure_veto` needed no change; what it
    reads did. A reason the counterfactual world has measured now wins, and a box that has not
    replayed keeps exactly the FILTER_VALUE behaviour it had -- a merge, never a swap.

  * THE EFFECTIVE CEILING. `heat_policy.effective_ceiling` caps NOMINAL heat at the heat the
    book's INDEPENDENT risk earns. It was registered in `rails.py` against `measure_ceiling`,
    which reads `heat.binding == "ceiling"` -- so the fence passed while the rail bound, on a
    measurement of a different rail. `measure_effective_ceiling` prices the one that binds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import missed_growth as mg  # noqa: E402

from libs.portfolio.rails import RAILS, rail  # noqa: E402

#: A growth curve whose top is flat and whose right-hand side falls, so "what the cap cost" has
#: an unambiguous sign at every heat the tests read off it. It lives under `heat.curve` on the
#: allocation artifact, which is where `_curve` reads it.
CURVE = [[0.20, 0.0020], [0.25, 0.0024], [0.30, 0.0021]]


@pytest.fixture
def reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(mg, "FILTER_VALUE", tmp_path / "FILTER_VALUE.json")
    monkeypatch.setattr(mg, "COUNTERFACTUAL", tmp_path / "COUNTERFACTUAL_WORLD.json")
    return tmp_path


def _write(where: Path, name: str, doc: Any) -> None:
    (where / name).write_text(json.dumps(doc), "utf-8")


# --------------------------------------------------------------------------- veto evidence
FV_ROW = {"n_vetoed_and_triggered": 12, "mean_avoided_r": 0.10, "filter_value_r": 1.2,
          "t": 2.1, "verdict": "EARNS_ITS_PLACE"}
CF_ROW = {"n_vetoed_and_triggered": 400, "mean_avoided_r": -0.05, "filter_value_r": -20.0,
          "t": -3.4, "verdict": "COSTS_EDGE", "mean": -0.0004}


def test_a_veto_alpha_arm_overrides_the_filter_value_row_for_the_same_reason(
        reports: Path) -> None:
    _write(reports, "FILTER_VALUE.json", {"filters": {"state_gate": FV_ROW}})
    _write(reports, "COUNTERFACTUAL_WORLD.json",
           {"alphas": {"VETO_ALPHA": {"arms": {"state_gate": CF_ROW}}}})
    ev = mg._veto_evidence()
    row = ev["filters"]["state_gate"]
    assert row["n_vetoed_and_triggered"] == 400, "the world's row must win, not FILTER_VALUE's"
    assert row["verdict"] == "COSTS_EDGE"
    assert row["source"] == "COUNTERFACTUAL_WORLD.VETO_ALPHA"
    assert row["d_elog_per_veto"] == pytest.approx(-0.0004)
    assert ev["source"] == "FILTER_VALUE + COUNTERFACTUAL_WORLD.VETO_ALPHA"
    # and the rail's verdict follows the better evidence
    v = mg.measure_veto(rail("state_gate"), {"book": {"S": 0.02}}, ev)
    assert v["verdict"] == mg.COSTS and v["n"] == 400


def test_a_reason_the_world_has_not_measured_keeps_its_filter_value_row(reports: Path) -> None:
    """A merge, not a swap: the replay reaches only some reasons, and the ones it did not reach
    must not lose the verdicts they already had."""
    _write(reports, "FILTER_VALUE.json",
           {"filters": {"state_gate": FV_ROW, "margin_guard": FV_ROW}})
    _write(reports, "COUNTERFACTUAL_WORLD.json",
           {"alphas": {"VETO_ALPHA": {"arms": {"state_gate": CF_ROW}}}})
    ev = mg._veto_evidence()
    assert ev["filters"]["margin_guard"] == FV_ROW
    assert set(ev["filters"]) == {"state_gate", "margin_guard"}


def test_an_absent_counterfactual_world_leaves_filter_value_behaviour_exactly_as_it_was(
        reports: Path) -> None:
    _write(reports, "FILTER_VALUE.json", {"filters": {"state_gate": FV_ROW}, "n": 3})
    ev = mg._veto_evidence()
    assert ev["filters"] == {"state_gate": FV_ROW}
    assert ev["n"] == 3, "the rest of the FILTER_VALUE document survives the merge"
    v = mg.measure_veto(rail("state_gate"), {"book": {"S": 0.02}}, ev)
    assert v["verdict"] == mg.EARNS and v["n"] == 12


def test_an_unmeasured_veto_alpha_does_not_overwrite_a_measured_filter_value_row(
        reports: Path) -> None:
    """The world publishes VETO_ALPHA as UNMEASURED with its reason on a box that has no
    decision ledger. That is an absence of evidence and must not replace evidence."""
    _write(reports, "FILTER_VALUE.json", {"filters": {"state_gate": FV_ROW}})
    _write(reports, "COUNTERFACTUAL_WORLD.json",
           {"alphas": {"VETO_ALPHA": {"status": "UNMEASURED", "n": 0, "alpha": None}}})
    assert mg._veto_evidence()["filters"] == {"state_gate": FV_ROW}
    _write(reports, "COUNTERFACTUAL_WORLD.json",
           {"alphas": {"VETO_ALPHA": {"arms": {"state_gate": {"verdict": "COSTS_EDGE"}}}}})
    assert mg._veto_evidence()["filters"] == {"state_gate": FV_ROW}, (
        "an arm row without n_vetoed_and_triggered has measured nothing")


def test_the_run_names_which_evidence_the_vetoes_were_judged_on(reports: Path) -> None:
    _write(reports, "FILTER_VALUE.json", {"filters": {}})
    assert mg.run(write=False)["veto_evidence_source"] == (
        "FILTER_VALUE + COUNTERFACTUAL_WORLD.VETO_ALPHA")


# --------------------------------------------------------------------------- effective ceiling
def _alloc(binding: str, **heat: Any) -> dict[str, Any]:
    return {"heat": {"binding": binding, "hard_ceiling": 0.30, "curve": CURVE, **heat}}


def test_the_effective_ceiling_rail_is_billed_by_its_own_measurement() -> None:
    """It was registered against `measure_ceiling`, which reads binding == 'ceiling' -- so the
    fence passed while this rail bound, on a measurement of a different rail."""
    r = rail("effective_heat_ceiling")
    assert r.measure == "measure_effective_ceiling"
    assert r.kind == "cap" and r.measure in mg.MEASURES
    assert all(x.measure in mg.MEASURES for x in RAILS)


def test_a_pass_bound_by_the_effective_ceiling_prices_the_growth_it_declined() -> None:
    alloc = {"heat": {"binding": "effective_ceiling", "hard_ceiling": 0.30,
                      "effective_ceiling": 0.20, "free_optimum": 0.25, "state_optimum": 0.0,
                      "curve": CURVE}}
    m = mg.measure_effective_ceiling(rail("effective_heat_ceiling"), alloc, {})
    assert m["verdict"] == "SAMPLE" and m["sample"] is True
    assert m["value_logw_per_day"] == pytest.approx(0.0020 - 0.0024), (
        "growth at the earned cap minus growth at what the book wanted")
    assert m["value_logw_per_day"] < 0, "a cap that bound below the optimum cost growth"


def test_the_state_curves_argmax_counts_as_what_growth_wanted() -> None:
    """A state-conditioned book can want more than the unconditional free optimum; charging the
    cap only against the smaller number would under-report what it declined."""
    alloc = {"heat": {"binding": "effective_ceiling", "hard_ceiling": 0.30,
                      "effective_ceiling": 0.20, "free_optimum": 0.20, "state_optimum": 0.25,
                      "curve": CURVE}}
    assert mg.measure_effective_ceiling(rail("effective_heat_ceiling"), alloc, {})[
        "value_logw_per_day"] == pytest.approx(0.0020 - 0.0024)


def test_what_growth_wanted_is_never_read_above_the_hard_ceiling() -> None:
    alloc = {"heat": {"binding": "effective_ceiling", "hard_ceiling": 0.30,
                      "effective_ceiling": 0.20, "free_optimum": 0.90, "state_optimum": 0.0,
                      "curve": CURVE}}
    assert mg.measure_effective_ceiling(rail("effective_heat_ceiling"), alloc, {})[
        "value_logw_per_day"] == pytest.approx(0.0020 - 0.0021)


def test_a_pass_binding_on_anything_else_reads_not_binding_and_costs_nothing() -> None:
    for binding in ("ceiling", "mandate", "catastrophe", "free"):
        m = mg.measure_effective_ceiling(rail("effective_heat_ceiling"),
                                         _alloc(binding, effective_ceiling=0.20), {})
        assert m["verdict"] == mg.NOT_BINDING, binding
        assert m["value_logw_per_day"] == 0.0 and m["sample"] is True


def test_no_allocator_pass_is_unmeasured_and_a_curve_that_misses_the_heat_says_so() -> None:
    absent = mg.measure_effective_ceiling(rail("effective_heat_ceiling"), {}, {})
    assert absent["verdict"] == mg.UNMEASURED and "no allocator pass" in absent["why"]
    thin = mg.measure_effective_ceiling(
        rail("effective_heat_ceiling"),
        {"heat": {"binding": "effective_ceiling", "effective_ceiling": 0.20,
                  "free_optimum": 0.25, "hard_ceiling": 0.30, "curve": []}}, {})
    assert thin["verdict"] == mg.UNMEASURED and "curve" in thin["why"]
