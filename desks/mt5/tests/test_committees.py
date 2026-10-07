"""THE ADVERSARIAL COMMITTEES: models argue, arithmetic decides, and nothing gains authority.

NO NETWORK. Every test hands the committees a planted seat (`ask`), planted subjects and a
`tmp_path` state directory. The load-bearing properties:

  * the judge is a deterministic set cover over explanation classes and has no input through
    which a profitability claim could reach it;
  * a contract carries no verdict field and states that it has no authority;
  * claim-type separation discards an explanation that cites stronger evidence than the record
    holds;
  * a dark seat writes UNMEASURED and no contract;
  * the scrap rule fires only on settled evidence, never on UNMEASURED;
  * the falsifier battery takes the committee's lead class as ORDER only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import committees as cm  # noqa: E402

from libs.research import proposer_seat as ps  # noqa: E402


@pytest.fixture
def desk(tmp_path, monkeypatch):
    d = tmp_path / "committees"
    for name, path in {"STATE_DIR": d, "CONTRACTS": d / "contracts.jsonl",
                       "SETTLEMENTS": d / "settlements.jsonl", "STATE": d / "state.json",
                       "PREMORTEMS": d / "premortems.json",
                       "TRIAL_UNION": d / "trial_union.txt",
                       "DONATE_DIR": tmp_path / "intelligence" / "committees",
                       "REPORT": tmp_path / "reports" / "COMMITTEES.json",
                       "THROUGHPUT": tmp_path / "reports" / "JUDGING_THROUGHPUT.json"}.items():
        monkeypatch.setattr(cm, name, path)
    monkeypatch.setattr(cm, "_branches", lambda: {"carry": (), "mean_reversion":
                                                  ("mean_reversion_rsi", "range_reversion")})
    return tmp_path


def _subject(committee=cm.SCIENTIFIC, sym="EURUSD", claim="signal", i=0) -> cm.Subject:
    return cm.Subject(committee, f"s{i}", sym, "session_range_breakout", {"lookback": 20 + i},
                      "London open breakout: overnight stops sit just beyond the Asia range",
                      claim, "test", {"symbols": [sym]})


class FakeSeat:
    """A seat that answers every role with one explanation of a class the role may raise."""

    def __init__(self, extra: dict | None = None) -> None:
        self.calls: list[str] = []
        self.extra = extra or {}

    def __call__(self, organ, kind, *, task="", grammar="", context=(), n=2, validate=None):
        self.calls.append(task)
        role = re.match(r"You are the ([a-z ]+)\.", task).group(1).replace(" ", "_")
        allowed = cm.ROLES[role][1]
        item = {"explanation": f"{role} argues a cause of class {allowed[0]}",
                "class": allowed[0], "predicts": "the effect vanishes under the control",
                "mechanism_branch": "mean_reversion", **self.extra}
        ok = validate(item) is None if validate else True
        return ps.SeatReply(organ, kind, "RAN", items=[item] if ok else [],
                            trials_charged=1.0, discarded=0 if ok else 1)


# --------------------------------------------------------------------------- the judge
def test_the_judge_picks_the_cheapest_cover_and_names_what_it_cannot_cover() -> None:
    said = [{"role": "a", "class": "COST_DEATH"}, {"role": "b", "class": "LEAKAGE"},
            {"role": "c", "class": "NO_EDGE"}, {"role": "d", "class": "COST_DEATH"},
            {"role": "e", "class": cm.MECHANISM}]
    v = cm.judge(said)
    assert v["rival_classes"] == ["COST_DEATH", "LEAKAGE", "NO_EDGE"]
    assert v["experiments"] == ["cost_surface", "half_stability", "truncation"]
    assert v["cost_s"] == 3.5 and v["uncovered"] == [] and v["lead_class"] == "COST_DEATH"
    assert cm.judge(said) == v, "the judge must be reproducible"
    only = {"x": cm.Experiment("x", 1.0, frozenset({"COST_DEATH"}), "falsifiers", "")}
    assert cm.judge(said, only)["uncovered"] == ["LEAKAGE", "NO_EDGE"]


def test_the_judge_cannot_be_moved_by_a_profitability_claim() -> None:
    plain = [{"role": "a", "class": "TAIL_FAILURE"}]
    loud = [{"role": "a", "class": "TAIL_FAILURE", "sharpe": 4.0, "promote": True,
             "expected_return": 0.9}]
    assert cm.judge(plain) == cm.judge(loud)


# --------------------------------------------------------------------------- the disciplines
def test_claim_type_separation_discards_stronger_evidence() -> None:
    check = cm._valid_explanation(("NO_EDGE",), "signal")
    ok = {"explanation": "the effect is the average of a few volatile weeks", "class": "NO_EDGE"}
    assert check(ok) is None
    bad = dict(ok, explanation="live results on the account already confirm this cause")
    assert "claim-type" in check(bad)
    assert cm._valid_explanation(("NO_EDGE",), "live")(bad) is None
    assert "class must be" in check(dict(ok, **{"class": "LEAKAGE"}))


def test_cheap_screen_runs_before_any_call_and_counts_its_reasons() -> None:
    a, b = _subject(i=1), _subject(i=2)
    blank = cm.Subject(cm.SCIENTIFIC, "x", "", "f", {}, "a mechanism long enough to pass", "signal",
                       "t")
    short = cm.Subject(cm.SCIENTIFIC, "y", "EURUSD", "f", {}, "trend", "signal", "t")
    keep, why = cm.screen([a, b, blank, short], {b.fingerprint()})
    assert keep == [a]
    assert why == {"already_reviewed": 1, "no_symbol": 1, "no_mechanism_text": 1}


# --------------------------------------------------------------------------- the pass
def test_falsifier_looks_are_charged_once_at_their_original_count(desk, monkeypatch):
    monkeypatch.setattr(cm, "run_experiments", lambda s, v, d, **k: {
        "status": "KILLED", "kills": ["cost_surface"], "results": {
            "cost_surface": {"verdict": "FAIL"}, "placebo": {"verdict": "PASS"},
            "regime_split": {"verdict": "NOT_REACHED"}, "capacity": {"verdict": "UNMEASURED"}}})
    subjects = {cm.SCIENTIFIC: [_subject()], cm.FORENSIC: []}
    doc = cm.run(ask=FakeSeat(), fates={}, calls=24, subjects=subjects)
    # two falsifiers looked at the returns; the two that did not run are not trials
    assert doc["falsifier_trials"] == {"looks_this_pass": 2, "new_in_union": 2}
    lines = cm.TRIAL_UNION.read_text().split()
    assert len(lines) == 2 and all("|falsifier:" in ln for ln in lines)
    # the same looks on the same cell are never charged again
    again = cm.charge_looks(set(lines), write=True)
    assert again == {"looks_this_pass": 2, "new_in_union": 0}
    assert cm.TRIAL_UNION.read_text().split() == lines


def test_a_pass_writes_contracts_without_authority_and_donates_forensic_cells(desk, monkeypatch):
    monkeypatch.setattr(cm, "run_experiments", lambda s, v, d, **k: {
        "status": "KILLED", "kills": ["cost_surface"], "results": {}})
    seat = FakeSeat()
    doc = cm.run(ask=seat, fates={}, calls=24,
                 subjects={cm.SCIENTIFIC: [_subject()],
                           cm.FORENSIC: [_subject(cm.FORENSIC, "XAUUSD", "public_record", 9)]})
    sci, fo = doc["committees"][cm.SCIENTIFIC], doc["committees"][cm.FORENSIC]
    assert sci["reviewed"] == 1 and sci["kills"] == 1 and sci["calls"] == 6
    assert fo["reviewed"] == 1 and fo["calls"] == 7
    rows = [json.loads(ln) for ln in cm.CONTRACTS.read_text().splitlines()]
    assert len(rows) == 2
    for c in rows:
        assert c["authority"].startswith("NONE")
        assert not (set(c) | set(c["judge"])) & ps.VERDICT_KEYS
        assert c["fingerprint"]["input"] and c["fingerprint"]["code"]
    assert rows[0]["may_not_cite"] == ["sim", "broker_replay", "shadow", "live"]
    don = json.loads(next(cm.DONATE_DIR.glob("discoveries_*.json")).read_text())
    fams = {r["family"] for r in don["discoveries"]}
    assert fams == {"mean_reversion_rsi", "range_reversion"}
    assert all(r["gauntlet_bypass"] is False for r in don["discoveries"])
    hints = json.loads(cm.PREMORTEMS.read_text())
    assert hints and all(h["source"] == "committees" for h in hints.values())
    # the same input is never argued twice
    again = cm.run(ask=seat, fates={}, calls=24,
                   subjects={cm.SCIENTIFIC: [_subject()], cm.FORENSIC: []})
    assert again["committees"][cm.SCIENTIFIC]["set_aside"] == {"already_reviewed": 1}


def test_a_dark_seat_is_unmeasured_and_writes_no_contract(desk, monkeypatch):
    monkeypatch.setenv("QUANT_PROPOSER_SEAT", "0")
    doc = cm.run(fates={}, subjects={cm.SCIENTIFIC: [_subject()], cm.FORENSIC: []})
    assert doc["seat"] == "DARK"
    assert doc["committees"][cm.SCIENTIFIC]["status"] == cm.UNMEASURED
    assert not cm.CONTRACTS.exists() or not cm.CONTRACTS.read_text().strip()


def test_the_call_cap_holds(desk, monkeypatch):
    monkeypatch.setattr(cm, "run_experiments", lambda *a, **k: {"status": "SURVIVED"})
    seat = FakeSeat()
    cm.run(ask=seat, fates={}, calls=8,
           subjects={cm.SCIENTIFIC: [_subject(i=i) for i in range(5)], cm.FORENSIC: []})
    assert len(seat.calls) <= 8


# --------------------------------------------------------------------------- settlement
def _contract(i: int, killed: bool, lead: str = "COST_DEATH") -> dict:
    return {"committee": cm.SCIENTIFIC, "graph_id": f"g{i}", "fingerprint": {"input": f"f{i}"},
            "outcome": {"status": "KILLED" if killed else "SURVIVED"},
            "judge": {"lead_class": lead},
            "explanations": [{"role": "execution_cost", "class": "COST_DEATH"},
                             {"role": "causal_skeptic", "class": "NO_EDGE"}]}


def test_settlement_scores_kills_and_roles_against_the_later_fate() -> None:
    fates = {"g0": {"fate": "FAILED", "gates": {"cost_stress": False}, "why": "cost"},
             "g1": {"fate": "CERTIFIED"}, "g2": {"fate": "BORN"}}
    rows = cm.settle([_contract(0, True), _contract(1, True), _contract(2, True)], set(), fates)
    assert [r["graph_id"] for r in rows] == ["g0", "g1"]
    assert rows[0]["kill_correct"] is True and rows[1]["kill_correct"] is False
    assert rows[0]["died_of"] == "COST_DEATH" and rows[0]["roles"]["execution_cost"] is True
    assert cm.settle([_contract(0, True)], {rows[0]["key"]}, fates) == []


def test_the_scrap_rule_needs_settled_evidence_and_never_fires_on_unmeasured() -> None:
    few = [{"committee_killed": True, "kill_correct": False}] * 10
    assert cm.scrap_verdict(cm.value(few, 100.0, None))[0] is False
    bad = [{"committee_killed": True, "kill_correct": i < 20} for i in range(60)]
    assert cm.scrap_verdict(cm.value(bad, 100.0, None))[0] is True
    good = [{"committee_killed": True, "kill_correct": True} for _ in range(60)]
    v = cm.value(good, 100.0, None)
    assert v["net_compute_s"] == cm.UNMEASURED and cm.scrap_verdict(v)[0] is False
    assert cm.scrap_verdict(cm.value(good, 1e9, 10.0))[0] is True
    assert cm.scrap_verdict(cm.value(good, 100.0, 10.0))[0] is False


def test_a_scrapped_committee_makes_no_calls(desk):
    cm._atomic(cm.STATE, {cm.SCIENTIFIC: {"status": "SCRAPPED", "why": "test"}})
    seat = FakeSeat()
    doc = cm.run(ask=seat, fates={}, subjects={cm.SCIENTIFIC: [_subject()], cm.FORENSIC: []})
    assert doc["committees"][cm.SCIENTIFIC]["status"] == "SCRAPPED"
    assert seat.calls == []


# --------------------------------------------------------------------------- the wiring
def test_the_falsifier_battery_takes_the_committees_class_as_order(desk, monkeypatch):
    import falsifier_run as fr

    from libs.research.hypothesis_graph import node_id
    spec = {"symbol": "EURUSD", "family": "session_range_breakout", "params": {"lookback": 20}}
    cm._atomic(cm.PREMORTEMS, {node_id("EURUSD", "session_range_breakout", {"lookback": 20}):
                               {"failure_class": "TAIL_FAILURE", "source": "committees"}})
    monkeypatch.setattr(fr, "_graveyard_premortems", lambda certs: ({}, "stub"))
    pre, basis = fr._premortems({"c1": {"shadow_spec": spec}, "c2": {"shadow_spec": {}}})
    assert pre == {"c1": {"failure_class": "TAIL_FAILURE", "source": "committees"}}
    assert "committee" in basis
    from libs.validation import falsifiers
    assert falsifiers.schedule(pre["c1"])[0] == "tail_worst_decile"


def test_the_leg_is_on_the_hourly_clock_with_a_layer() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"committees", "research/committees.py", "--once", "--budget-s", "600"' in src
    assert '"committees": cmt' in src
    from libs.research import layers
    assert layers.LEG_LAYER["committees"] == "prediction"
    assert {cm.SCIENTIFIC, cm.FORENSIC} <= set(ps.ORGANS)


def test_the_cli_accepts_the_legs_arguments() -> None:
    with pytest.raises(SystemExit) as exc:
        cm.main(["--once", "--budget-s", "600", "--help"])
    assert exc.value.code == 0
