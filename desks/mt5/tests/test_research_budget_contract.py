"""The research budget is AUTHORITATIVE only on a measured gain, and never cuts a floor.

    python -m pytest desks/mt5/tests/test_research_budget_contract.py -q

A verifier found `research_budget.json` `authoritative: false`. The budget had no contract, so
"a leg spent what the bandit said" was the whole claim. WHAT MUST NOT REGRESS:
  1. every leg keeps its floor (x1.0 of its base) in every arm: control, fallback, no surplus;
  2. the uplift above the floor comes only out of MEASURED spare seconds;
  3. a REJECTED contract falls back to the floor, with the reason recorded;
  4. `authoritative` is true only for a treated hour whose contract the held-out arm ADMITTED,
     and the artifact publishes it with the reason and the control-arm evidence;
  5. the trial ledger records only real, fresh outputs of trial runs (never an absent one as 0);
  6. the contract is declared where the Tier S organ evaluates it, and the hourly cycle feeds it.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_budget as rb  # noqa: E402

ARMS = ["new_mechanism", "mutate_survivor", "combine_survivors", "conditional_state_edge",
        "execution_improvement", "exit_improvement", "cross_asset_signal",
        "alt_data_hypothesis", "failure_derived", "model_architecture", "external_screen"]
NOW = datetime.now(tz=UTC)


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(rb, "BANDIT", tmp_path / "RESEARCH_BANDIT.json")
    monkeypatch.setattr(rb, "OUT", tmp_path / "RESEARCH_BUDGET.json")
    monkeypatch.setattr(rb, "AUCTION", tmp_path / "RESEARCH_AUCTION.json")
    monkeypatch.setattr(rb, "TRIALS", tmp_path / "research_budget_trials.jsonl")
    monkeypatch.setattr(rb, "DESK", tmp_path)
    shares = dict.fromkeys(ARMS, 0.0)
    shares["mutate_survivor"] = 1.0                        # the price asks for x2.0 (CEIL)
    rb.BANDIT.write_text(json.dumps({"shares": shares}), encoding="utf-8")
    state: dict[str, Any] = {"surplus": (10_000.0, "test clock"), "control": False}
    monkeypatch.setattr(rb, "_surplus_s", lambda leg: state["surplus"])
    monkeypatch.setattr(rb, "_in_control", lambda leg, now: state["control"])
    return state


def _trials(rows: list[tuple[str, float]], at: datetime = NOW,
            leg: str = "alpha_evolution") -> None:
    rb.TRIALS.write_text("".join(json.dumps({"at": at.isoformat(), "leg": leg, "arm": a,
                                             "outcome": o}) + "\n" for a, o in rows), "utf-8")


ADMIT = [("treated", 9), ("treated", 10), ("treated", 11), ("treated", 10),
         ("control", 4), ("control", 5), ("control", 4), ("control", 5)]
REJECT = [("treated", 4), ("treated", 5), ("treated", 4), ("treated", 5),
          ("control", 9), ("control", 10), ("control", 11), ("control", 10)]


def test_the_trial_grants_the_uplift_from_surplus_but_is_not_authoritative(desk: Any) -> None:
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert rec["factor"] == rb.CEIL and s == 480
    assert rec["arm"] == "treated" and rec["trial"] is True
    assert rec["contract"]["verdict"] == "UNMEASURED" and rec["authoritative"] is False
    rb.record(rec)
    doc = json.loads(rb.OUT.read_text("utf-8"))
    assert doc["authoritative"] is False and "trial" in doc["authority_why"]
    assert doc["control_arm"]["admitted"] == 0.0


def test_the_uplift_never_exceeds_measured_surplus(desk: Any) -> None:
    desk["surplus"] = (100.0, "tight clock")
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert s == 340 and rec["extra_s"] == 100 and rec["extra_wanted_s"] == 240


@pytest.mark.parametrize("surplus", [(None, "spare unmeasured"), (0.0, "no spare")])
def test_no_measured_surplus_grants_nothing_above_the_floor(desk: Any, surplus: Any) -> None:
    desk["surplus"] = surplus
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert s == 240 and rec["arm"] == "none" and rec["applied"] is False


def test_a_held_out_hour_runs_the_floor_and_is_a_trial_unit(desk: Any) -> None:
    desk["control"] = True
    _trials(ADMIT)
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert s == 240 and rec["arm"] == "control" and rec["trial"] is True
    assert rec["extra_due_s"] == 240 and rec["authoritative"] is False


def test_a_rejected_contract_falls_back_to_the_floor_with_its_reason(desk: Any) -> None:
    _trials(REJECT)
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert s == 240 and rec["arm"] == "fallback" and rec["trial"] is False
    assert "REJECTED" in rec["governed_why"] and "current allocation" in rec["governed_why"]
    rb.record(rec)
    ok, why = rb.authority()
    assert ok is False and "REJECTED" in why


def test_an_admitted_contract_makes_the_budget_authoritative(desk: Any) -> None:
    _trials(ADMIT)
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert s == 480 and rec["authoritative"] is True
    rb.record(rec)
    doc = json.loads(rb.OUT.read_text("utf-8"))
    assert doc["authoritative"] is True and "ADMITTED" in doc["authority_why"]
    assert doc["control_arm"]["admitted"] == 1.0
    assert doc["contract"] == rb.CONTRACT
    ok, why = rb.authority()
    assert ok is True and "alpha_evolution=480s" in why


def test_the_floor_holds_in_every_arm_and_verdict(desk: Any) -> None:
    for rows in ([], ADMIT, REJECT):
        _trials(rows)
        for control in (False, True):
            for surplus in ((None, "u"), (0.0, "z"), (50.0, "s"), (1e9, "big")):
                desk["control"], desk["surplus"] = control, surplus
                for base in (1, 60, 240):
                    s, _ = rb.budget_s("alpha_evolution", base)
                    assert s >= base


def test_a_rejection_expires_out_of_the_window(desk: Any) -> None:
    _trials(REJECT, at=NOW - timedelta(days=rb.TRIAL_WINDOW_D + 1))
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert rec["contract"]["verdict"] == "UNMEASURED" and s == 480


def test_observe_records_only_fresh_output_of_trial_runs(desk: Any, tmp_path: Path) -> None:
    rep = tmp_path / "reports" / "alpha_evolution.json"
    rep.parent.mkdir(parents=True)
    _, rec = rb.budget_s("alpha_evolution", 240)
    # the leg's artifact predates this run: not this run's output, never recorded as zero
    rep.write_text(json.dumps({"generated_at": (NOW - timedelta(hours=2)).isoformat(),
                               "proposals": [1, 2, 3]}), "utf-8")
    assert rb.observe("alpha_evolution", rec) is None
    rep.write_text(json.dumps({"generated_at": datetime.now(tz=UTC).isoformat(),
                               "proposals": [1, 2, 3]}), "utf-8")
    row = rb.observe("alpha_evolution", rec)
    assert row is not None and row["outcome"] == 3.0 and row["arm"] == "treated"
    assert len(rb.TRIALS.read_text("utf-8").splitlines()) == 1
    # a run that was not a trial unit adds nothing
    assert rb.observe("alpha_evolution", {**rec, "trial": False}) is None


def test_deepen_output_is_its_decisions(desk: Any, tmp_path: Path) -> None:
    p = tmp_path / "data" / "hypotheses" / "deepened_candidates.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"built_at": datetime.now(tz=UTC).isoformat(),
                             "dispositions": {"reject": 4, "deepened": 2}}), "utf-8")
    val, _why = rb.run_output("deepen", (NOW - timedelta(minutes=5)).isoformat())
    assert val == 6.0


def test_the_unlimited_sentinel_is_never_governed(desk: Any) -> None:
    s, rec = rb.budget_s("deepen", 0)
    assert s == 0 and rec["trial"] is False and rec["arm"] == "none"


def test_the_contract_is_declared_where_tier_s_evaluates_it() -> None:
    from libs.tiers import contracts
    ledger = json.loads((ROOT / "docs" / "research" / "tier_s_program.json").read_text("utf-8"))
    row = next(r for r in ledger["leg_contracts"] if r["leg"] == "research_budget")
    assert row["contract"] == rb.CONTRACT and not contracts.problems(row["contract"])
    c = contracts.Contract.parse(row["contract"])
    assert contracts.evaluate(c, [1.0])["verdict"] == "ADMITTED"
    assert contracts.read_metric({"control_arm": {"admitted": 0.0}}, c.metric) == 0.0


def test_the_hourly_cycle_measures_what_the_budget_granted() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    i_budget = src.index('_bandit_budget("alpha_evolution", 240)')
    i_run = src.index('"--budget-s", str(_aev_s)')
    i_obs = src.index('_bandit_observe("alpha_evolution", _aev_rec)')
    assert i_budget < i_run < i_obs
    assert '_bandit_observe("deepen", _rec)' in src
