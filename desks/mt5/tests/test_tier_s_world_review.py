"""Tier S layers 16 -> 20 -> door: the closure and agent-based worlds reach the review panel.

`organ_worlds` joins each certificate's closure-world and agent-world replays into
data/tier_s/worlds_by_certificate.json; the panel's `ecologist` raises candidate-specific
challenges from them. A HIGH challenge needs a failure the candidate itself caused -- its own
positive edge turned negative in a gap world, or a loss in all three agent ecologies -- and
those two resolvers are candidate-specific at the (withhold-only, billed) promotion door.

Every test runs in tmp_path; none reads or writes the desk's live data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.tiers import agent_worlds, closure_worlds, door_evidence  # noqa: E402
from libs.tiers import review_panel as rp  # noqa: E402


def _m(exp: float) -> dict[str, Any]:
    return {"status": "MEASURED", "expectancy": exp, "delta_expectancy": exp - 0.2,
            "applied": 48}


UNM = {"status": "UNMEASURED", "why": "short tape"}


def _worlds(base: float | None = 0.2, closure: dict[str, Any] | None = None,
            agents: dict[str, Any] | None = None, flags: list[str] | None = None
            ) -> dict[str, Any]:
    return {"worlds": {"baseline_expectancy": base, "flags": flags or [],
                       "closure": dict.fromkeys(closure_worlds.NAMES, UNM) | (closure or {}),
                       "agents": dict.fromkeys(agent_worlds.NAMES, UNM) | (agents or {})}}


def _kinds(ev: dict[str, Any]) -> dict[str, str]:
    return {c.kind: c.severity for c in rp.review("k", ev)}


def test_the_reviewer_lists_match_the_world_modules() -> None:
    assert set(rp.CLOSURE_WORLDS) == set(closure_worlds.NAMES)
    assert set(rp.AGENT_WORLDS) == set(agent_worlds.NAMES)
    assert set(rp.CLOSURE_GAP_WORLDS) == {closure_worlds.MARKET_CLOSURE,
                                          closure_worlds.INSTRUMENT_HALT}
    assert set(rp.CLOSURE_FLAGS) == set(ts.CLOSURE_FLAGS)
    assert set(rp.AGENT_FLAGS) == set(ts.AGENT_FLAGS)
    assert rp.PANEL["ecologist"][1] == ("worlds",), "the ecologist sees the worlds and nothing else"


def test_a_gap_that_breaks_the_candidates_own_edge_is_high_and_failed() -> None:
    ev = _worlds(0.2, closure={closure_worlds.INSTRUMENT_HALT: _m(-0.15)},
                 flags=["halt_fragile"])
    (ch,) = [c for c in rp.review("k", ev) if c.reviewer == "ecologist"]
    assert (ch.kind, ch.severity, ch.resolves_when) == ("CLOSURE_GAP_LOSS", "HIGH",
                                                        "closure_gap_survives")
    assert "instrument_halt -0.150R" in ch.claim and "+0.200R" in ch.claim
    assert rp.resolve(ch, ev) == "FAILED"
    rep = rp.panel_report({"k": ev})
    assert rep["rows"][0]["verdict"] == "FAILED"
    # a later synthetic pass in which the gap no longer breaks it answers the challenge
    healed = _worlds(0.2, closure={closure_worlds.INSTRUMENT_HALT: _m(0.05)})
    assert rp.resolve(ch, healed) == "PASSED"


def test_no_edge_of_its_own_or_a_starved_session_is_only_medium() -> None:
    # the gap world is negative but so was the untouched tape: the gap did not cause the loss
    no_edge = _worlds(-0.05, closure={closure_worlds.MARKET_CLOSURE: _m(-0.3)},
                      flags=["dies_on_market_closure"])
    assert _kinds(no_edge).get("CLOSURE_FRAGILE") == "MEDIUM"
    assert "CLOSURE_GAP_LOSS" not in _kinds(no_edge)
    starved = _worlds(0.2, closure={closure_worlds.SESSION_CLOSED: _m(0.05)},
                      flags=["needs_the_closed_session"])
    assert _kinds(starved) == {"CLOSURE_FRAGILE": "MEDIUM"}
    # a closure world that was never measured is never a clean verdict
    assert rp.RESOLVERS["closure_gap_survives"](_worlds(0.2)) is None
    assert rp.RESOLVERS["closure_gap_survives"](_worlds(None, closure={
        closure_worlds.MARKET_CLOSURE: _m(-0.3)})) is None


def test_losing_in_every_agent_ecology_is_high() -> None:
    all_lose = _worlds(0.2, agents={w: _m(-0.1) for w in agent_worlds.NAMES},
                       flags=list(rp.AGENT_FLAGS))
    assert _kinds(all_lose)["LOSES_IN_EVERY_ECOLOGY"] == "HIGH"
    (ch,) = [c for c in rp.review("k", all_lose) if c.kind == "LOSES_IN_EVERY_ECOLOGY"]
    assert rp.resolve(ch, all_lose) == "FAILED"
    two = _worlds(0.2, agents={"abm_momentum_herd": _m(-0.1), "abm_value_anchor": _m(-0.2),
                               "abm_liquidity_withdrawal": _m(0.1)},
                  flags=["dies_in_herding_market", "dies_in_value_market"])
    assert _kinds(two) == {"ECOLOGY_DEPENDENT": "MEDIUM"}
    assert rp.RESOLVERS["agent_worlds_survive"](two) is True
    one = _worlds(0.2, agents={"abm_momentum_herd": _m(-0.1)},
                  flags=["dies_in_herding_market"])
    assert _kinds(one) == {"ECOLOGY_DEPENDENT": "LOW"}
    # two lost and one unmeasured: not yet a loss in EVERY ecology
    assert rp.RESOLVERS["agent_worlds_survive"](_worlds(0.2, agents={
        "abm_momentum_herd": _m(-0.1), "abm_value_anchor": _m(-0.2)})) is None


def test_an_untouched_certificate_is_named_and_a_clean_one_raises_nothing() -> None:
    assert _kinds(_worlds(0.2)) == {"WORLDS_UNMEASURED": "LOW"}
    (ch,) = rp.review("k", _worlds(0.2))
    assert rp.resolve(ch, _worlds(0.2)) == "OPEN"
    clean = _worlds(0.2, closure={w: _m(0.1) for w in closure_worlds.NAMES},
                    agents={w: _m(0.1) for w in agent_worlds.NAMES})
    assert _kinds(clean) == {}
    assert _kinds({}) == {}, "no worlds evidence at all: the ecologist has nothing to read"


def test_the_door_counts_both_world_failures_as_candidate_specific() -> None:
    assert {"closure_gap_survives", "agent_worlds_survive"} <= door_evidence.CANDIDATE_SPECIFIC
    assert "closure_agent_measured" not in door_evidence.CANDIDATE_SPECIFIC
    ev = _worlds(0.2, closure={closure_worlds.MARKET_CLOSURE: _m(-0.2)},
                 agents={w: _m(-0.1) for w in agent_worlds.NAMES})
    row = rp.panel_report({"a.EURUSD.x": ev})["rows"][0]
    assert door_evidence.review_failed(row) == ["ecologist:CLOSURE_GAP_LOSS",
                                                "ecologist:LOSES_IN_EVERY_ECOLOGY"]
    built = door_evidence.build([row], {"a.EURUSD.x": "f"}, {})
    assert (door_evidence.door_reason(built["a.EURUSD.x"]) or "").startswith(
        "REVIEW_PANEL_FAILED")
    # MEDIUM and LOW world challenges never reach the door
    soft = rp.panel_report({"b": _worlds(0.2, agents={"abm_momentum_herd": _m(-0.1)},
                                         flags=["dies_in_herding_market"])})["rows"][0]
    assert door_evidence.review_failed(soft) == []


def test_organ_worlds_to_organ_review_on_the_hourly_path(tmp_path: Path, monkeypatch: Any
                                                         ) -> None:
    """The join organ_worlds writes is what organ_review hands the ecologist."""
    names = [{"name": n} for n in ("spread_x5", *closure_worlds.NAMES, *agent_worlds.NAMES)]
    synth = {"scenarios": names, "results": [
        {"symbol": "EURUSD", "family": "f", "flags": ["dies_on_market_closure"],
         "baseline": {"n": 80, "expectancy": 0.25},
         "scenarios": {"spread_x5": _m(0.1), closure_worlds.MARKET_CLOSURE: _m(-0.4)}},
        {"symbol": "GBPUSD", "family": "f", "flags": [], "baseline": {"expectancy": 0.2},
         "scenarios": {w: _m(0.1) for w in (*closure_worlds.NAMES, *agent_worlds.NAMES)}}]}
    real_read = ts._read
    monkeypatch.setattr(ts, "_read", lambda p: synth if "SYNTHETIC" in str(p) else
                        real_read(p) if str(p).startswith(str(tmp_path)) else None)
    monkeypatch.setattr(ts, "survivors", lambda: {
        "a": {"shadow_spec": {"symbol": "EURUSD", "family": "f", "selector": "asia"}},
        "b": {"shadow_spec": {"symbol": "GBPUSD", "family": "f", "selector": "asia"}}})
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(ts, "shadow_rows", dict)
    monkeypatch.setattr(ts, "live_rows", list)
    monkeypatch.setattr(ts, "_shared_reward", lambda keys: {
        "status": "UNMEASURED", "static": {"n_violations": 0}, "by_candidate": {}})
    ts.organ_worlds()
    rows = {r["key"]: r for r in json.loads(
        (tmp_path / "worlds_by_certificate.json").read_text("utf-8"))["rows"]}
    assert rows["a"]["baseline_expectancy"] == 0.25
    out = ts.organ_review(None, None, None)
    assert out["verdicts"]["FAILED"] >= 1
    panel = {r["candidate"]: r for r in json.loads(
        (tmp_path / "out" / "REVIEW_PANEL_ROWS.json").read_text("utf-8"))["rows"]}
    eco_a = [c for c in panel["a"]["challenges"] if c["reviewer"] == "ecologist"]
    assert [(c["kind"], c["severity"], c["state"]) for c in eco_a] == [
        ("CLOSURE_GAP_LOSS", "HIGH", "FAILED")]
    assert not [c for c in panel["b"]["challenges"] if c["reviewer"] == "ecologist"]
    assert door_evidence.review_failed(panel["a"]) == ["ecologist:CLOSURE_GAP_LOSS"]
    assert door_evidence.review_failed(panel["b"]) == []
