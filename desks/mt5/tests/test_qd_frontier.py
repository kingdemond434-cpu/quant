"""The quality-diversity frontier: what a niche is, who holds its elite, and what the three
workers are allowed to propose.

Every input is synthetic and every path is redirected into `tmp_path`. The organ reads six
artifacts on the box and all six may be absent, partial or stale, so the tests that matter most
are the ones proving an absent input yields a COUNT and an UNMEASURED verdict rather than a crash
or a clean answer -- and that a big in-sample number never takes an elite seat from a small
forward one.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import axis_registry as ar  # noqa: E402
import qd_frontier as qd  # noqa: E402

#: Two hypothesis-lane classes and one event-lane class, so the two-lane order can be proved
#: without importing the broker registry.
_CLASSES = {"EURUSD": "forex", "GBPUSD": "forex", "USDJPY": "forex",
            "XAUUSD": "commodities", "XAGUSD": "commodities", "APPLE": "equities"}
#: `session_range_breakout` and `level_breakout` share a mechanism bucket, which is what makes a
#: sibling-family mutation testable; `turn_of_month` is deliberately LEFT OUT of the registry.
_FAMILIES = frozenset({"session_range_breakout", "level_breakout", "carry",
                       "overnight_gap_decay", "mean_reversion_rsi"})
_BY_CLASS = {"forex": ["EURUSD", "GBPUSD", "USDJPY"], "commodities": ["XAUUSD", "XAGUSD"],
             "equities": ["APPLE"]}


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_lines(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _axes(symbol: str, family: str, **kw: Any) -> dict[str, str]:
    return ar.axis_cell(symbol, family, kw.get("params"), kw.get("timeframe"),
                        kw.get("session"), regime_hint=kw.get("regime"))


def _cell(symbol: str, family: str, state: str = "MEASURED_FAIL", score: float = 0.0,
          basis: str = "UNMEASURED", **kw: Any) -> dict[str, Any]:
    """One row in the shape `collect_cells` hands to `build_niches`."""
    axes = _axes(symbol, family, **kw)
    return {"cell_id": ar.cell_id(axes), **axes, "state": state, "family": family,
            "score": score, "basis": basis}


def _cells(*rows: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["cell_id"]: r for r in rows}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """The organ pointed at an empty synthetic tree, with every policy shim stubbed."""
    paths = {"AXIS_REPORT": tmp_path / "reports" / "AXIS_REGISTRY.json",
             "AXIS_CELLS": tmp_path / "data" / "axis_registry.jsonl",
             "GATE_LEDGER": tmp_path / "data" / "hypotheses" / "gate_verdict_ledger.jsonl",
             "UNIVERSAL_SURVIVORS": tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json",
             "SHADOW_STATE": tmp_path / "reports" / "shadow" / "shadow_state.json",
             "SLEEVES": tmp_path / "data" / "sleeves.json",
             "OUT_REPORT": tmp_path / "reports" / "QD_FRONTIER.json",
             "OUT_MAP": tmp_path / "data" / "qd_mental_map.json",
             "INTAKE": tmp_path / "data" / "intelligence" / "qd_frontier"}
    for name, path in paths.items():
        monkeypatch.setattr(qd, name, path)
    monkeypatch.setattr(ar, "asset_class_of", lambda s: _CLASSES.get(str(s).upper(), ar.UNKNOWN))
    monkeypatch.setattr(ar, "may_hypothesise",
                        lambda s: _CLASSES.get(str(s).upper()) in ("forex", "commodities"))
    monkeypatch.setattr(ar, "registered_families", lambda: _FAMILIES)
    monkeypatch.setattr(ar, "compiler_vocab", frozenset)
    monkeypatch.setattr(ar, "instruments_by_class", lambda: dict(_BY_CLASS))
    monkeypatch.setattr(ar, "_banned", lambda f: False)
    return paths


def _forward(desk_paths, symbol="EURUSD", family="carry", session="asia", n=16, exp_r=0.02):
    _write(desk_paths["SHADOW_STATE"],
           {f"{symbol}.{family}.{session}": {"status": "ACTIVE", "n": n, "exp_r": exp_r}})


# ------------------------------------------------------------------ the niche key
def test_a_niche_is_the_eight_behavioural_axes_and_two_instruments_share_one(desk):
    """EURUSD and GBPUSD carrying the same edge are ONE niche: the instrument and the execution
    style are spellings of a bet, not different bets."""
    cells = _cells(_cell("EURUSD", "carry", session="asia"),
                   _cell("GBPUSD", "carry", session="asia"))
    niches = qd.build_niches(cells)
    assert len(niches) == 1
    key, row = next(iter(niches.items()))
    assert row["n_cells_tried"] == 2
    assert key.split("|") == [row["niche"][a] for a in qd.NICHE_AXES]
    assert row["niche"]["mechanism"] == "carry_rollover"
    assert row["niche"]["economic_actor"] == "negative_carry_holder"
    assert row["niche"]["constraint"] == "must_pay_the_rate_differential_daily"
    assert row["niche"]["asset_class"] == "forex" and row["niche"]["session"] == "asia"
    assert "instrument" not in key and "EURUSD" not in key
    # A different mechanism is a different niche, and a different session is too.
    assert len(qd.build_niches(_cells(_cell("EURUSD", "carry", session="asia"),
                                      _cell("EURUSD", "carry", session="london"),
                                      _cell("EURUSD", "session_range_breakout")))) == 3


def test_the_constraint_table_covers_exactly_the_mechanisms_the_registry_names():
    """A mechanism in one table and not the other is a niche axis that silently reads UNKNOWN for
    every cell of that mechanism, forever, with nobody looking."""
    assert set(qd.MECHANISM_CONSTRAINT) == set(ar.MECHANISM_ACTOR)
    assert qd.constraint_of("forced_liquidation") == "must_close_on_a_margin_call"
    assert qd.constraint_of("a_mechanism_nobody_named") == qd.UNKNOWN
    assert set(qd.NICHE_AXES) - set(ar.AXES) == {"constraint"}
    assert set(qd.MECHANISM_BUNDLE) <= set(qd.NICHE_AXES)


# ------------------------------------------------------------------ quality and the elite seat
def test_quality_ranks_forward_then_in_sample_then_the_deepest_gate_reached():
    assert qd.quality({"exp_r": 0.25, "n": 16}) == (1.0, qd.FORWARD_BASIS)
    assert qd.quality({"sharpe": 2.0, "days": 252}) == (2.0, "in_sample_t")
    assert qd.quality({"sharpe": 2.0}) == (2.0, "in_sample_sharpe")
    assert qd.quality({"gate_depth": 0.3}) == (0.3, "gate_depth")
    assert qd.quality({}) == (0.0, "UNMEASURED")
    # A clock with no trades is not forward evidence, and `n: True` is a flag, not one trade.
    assert qd.quality({"exp_r": 0.25, "n": 0, "sharpe": 1.0})[1] == "in_sample_sharpe"
    assert qd.quality({"exp_r": 0.25, "n": True})[1] == "UNMEASURED"
    assert qd.BASIS_RANK[qd.FORWARD_BASIS] > qd.BASIS_RANK["in_sample_t"] \
        > qd.BASIS_RANK["gate_depth"] > qd.BASIS_RANK["UNMEASURED"]


def test_forward_evidence_takes_the_elite_seat_from_a_far_bigger_in_sample_number(desk):
    """0.08 forward beats a 3.0 in-sample t. Comparing the magnitudes instead is how a desk ends
    up holding the cells that fitted best rather than the cells that paid."""
    _forward(desk, symbol="EURUSD", n=16, exp_r=0.02)              # 0.02*sqrt(16) = 0.08
    _write(desk["UNIVERSAL_SURVIVORS"], {"survivors": {"k": {
        "shadow_spec": {"symbol": "GBPUSD", "family": "carry", "selector": "asia"},
        "gates": {"in_sample_screen": {"sharpe": 3.0}}, "days": 252}}})
    report, niches, _proposals = qd.build(0)
    assert len(niches) == 1, "both cells describe one niche"
    row = next(iter(niches.values()))
    assert row["elite"]["instrument"] == "EURUSD"
    assert row["elite_evidence_basis"] == qd.FORWARD_BASIS
    assert row["elite_score"] == pytest.approx(0.08)
    assert row["n_forward"] == 1 and row["n_certified"] == 1
    assert report["summary"]["elite_basis"] == {qd.FORWARD_BASIS: 1}


def test_the_gate_ledger_gives_a_depth_and_a_live_sleeve_outranks_everything(desk):
    _write_lines(desk["GATE_LEDGER"], [
        {"cell": "XAGUSD.mean_reversion_rsi.p=abc", "sym": "XAGUSD",
         "family": "mean_reversion_rsi", "passed": False, "terminal_gate": "deflated_sharpe"}])
    _write(desk["SLEEVES"], {"sleeves": [{"symbol": "XAUUSD", "family": "session_range_breakout",
                                          "session": "asia", "status": "LIVE",
                                          "shadow_exp": 0.5, "shadow_n": 9}]})
    _report, niches, _p = qd.build(0)
    by_basis = {r["elite_evidence_basis"]: r for r in niches.values()}
    assert by_basis["gate_depth"]["elite_score"] == pytest.approx(qd.GATE_DEPTH["deflated_sharpe"])
    assert by_basis["gate_depth"]["n_certified"] == 0
    live = by_basis[qd.FORWARD_BASIS]
    assert live["n_live"] == 1 and live["elite"]["state"] == "LIVE"
    assert live["elite_score"] == pytest.approx(1.5)


# ------------------------------------------------------------------ the explorer
def test_the_explorer_only_proposes_empty_niches_one_free_axis_from_an_occupied_one(desk):
    cells = _cells(_cell("EURUSD", "carry", state="LIVE", score=1.0, basis=qd.FORWARD_BASIS,
                         session="asia"))
    niches = qd.build_niches(cells)
    qd.merge_map(niches, {}, datetime.now(UTC).isoformat())
    families, by_class = ar.registered_families(), ar.instruments_by_class()
    space = qd.candidate_niches(families, by_class)
    occupied = next(iter(niches))
    assert occupied in space, "the occupied cell sits on ground the desk could also propose"
    targets = qd.explorer_targets(niches, space, qd.mechanism_bundles(families),
                                  sorted(by_class))
    assert occupied not in {qd.niche_key(t["niche"]) for t in targets}

    picked = qd.select(cells, niches, space, families, by_class, datetime.now(UTC), 30)
    assert picked["explorer"], "one occupied niche has many empty neighbours"
    neighbours = {qd.niche_key(n) for _axis, n in
                  qd.one_move(niches[occupied]["niche"], qd.mechanism_bundles(families),
                              sorted(by_class))}
    for row in picked["explorer"]:
        assert row["niche"] not in niches, "an occupied niche is not empty ground"
        assert row["niche"] in space and row["niche"] in neighbours
        assert row["why"].startswith("EMPTY NICHE:") and row["selector_mode"] == "explorer"
        assert row["source"] == "qd_frontier:explorer"


def test_the_candidate_space_excludes_the_event_lane_unnamed_mechanisms_and_d1_sessions(desk):
    space = qd.candidate_niches(ar.registered_families(), ar.instruments_by_class())
    assert space
    assert not [n for n in space.values() if n["asset_class"] == "equities"]
    assert not [n for n in space.values() if n["mechanism"] == qd.UNKNOWN]
    assert not [n for n in space.values()
                if n["horizon"] == "multi_day" and n["session"] != "all"]
    assert {n["regime"] for n in space.values()} == {qd.PROPOSAL_REGIME}


def test_an_unnamed_mechanism_holds_a_niche_seat_but_is_never_proposed_into(desk):
    """`discovered` cells are counted -- they spent the trial budget -- and never donated: a cell
    with no payer is what the gauntlet's FIRST gate exists to refuse."""
    niche = {"economic_actor": qd.UNKNOWN, "constraint": qd.UNKNOWN,
             "information_source": "price_only", "mechanism": qd.UNKNOWN, "asset_class": "forex",
             "horizon": "sub_4h", "session": "all", "regime": qd.PROPOSAL_REGIME}
    assert qd.proposal(niche, "carry", ["EURUSD"], "connector", "w", 1.0) is None
    named = {**niche, "mechanism": "carry_rollover", "information_source": "carry",
             "economic_actor": "negative_carry_holder"}
    assert qd.proposal(named, "carry", ["EURUSD"], "connector", "w", 1.0)["family"] == "carry"
    cells = _cells(_cell("EURUSD", "discovered"))
    assert len(qd.build_niches(cells)) == 1, "it is still a niche the desk has occupied"


# ------------------------------------------------------------------ the exploiter
def test_the_exploiter_mutates_a_recently_improved_elite_and_leaves_a_stale_one_alone(desk):
    now = datetime.now(UTC)
    fresh = _cell("XAUUSD", "session_range_breakout", state="FORWARD", score=2.0,
                  basis=qd.FORWARD_BASIS, session="asia")
    stale = _cell("EURUSD", "carry", state="FORWARD", score=9.0, basis=qd.FORWARD_BASIS)
    cells = _cells(fresh, stale)
    niches = qd.build_niches(cells)
    fresh_key = qd.niche_key(qd.niche_of(fresh))
    stale_key = qd.niche_key(qd.niche_of(stale))
    niches[fresh_key]["last_improved_at"] = now.isoformat()
    niches[stale_key]["last_improved_at"] = (now - timedelta(days=10)).isoformat()

    assert [k for k, _r in qd.exploiter_targets(niches, now)] == [fresh_key]
    families, by_class = ar.registered_families(), ar.instruments_by_class()
    picked = qd.select(cells, niches, qd.candidate_niches(families, by_class), families,
                       by_class, now, 30)
    assert picked["exploiter"]
    for row in picked["exploiter"]:
        assert "ELITE MUTATION" in row["why"] and "XAUUSD" in row["why"]
        moved = [a for a in ("asset_class", "horizon", "session", "mechanism")
                 if row["niche"].split("|")[qd.NICHE_AXES.index(a)]
                 != niches[fresh_key]["niche"][a]]
        assert moved in ([], ["horizon"], ["session"]), f"{moved} is not one step"
        if not moved:
            assert row["family"] != "session_range_breakout", "an in-niche move is a new family"
    assert {r["family"] for r in picked["exploiter"]} <= _FAMILIES


def test_the_mutation_menu_is_an_adjacent_chart_another_session_and_a_sibling_family(desk):
    niche = qd.niche_of(_cell("XAUUSD", "session_range_breakout", session="asia"))
    elite = {"instrument": "XAUUSD", "family": "session_range_breakout", "chart": "H1",
             "session": "asia"}
    moves = qd.elite_mutations(niche, elite, ar.registered_families())
    axes = {a for a, _v, _n in moves}
    assert axes == {"chart", "session", "family"}
    # One step each way on the chart ladder is M30 and H4. M30 lands in the SAME horizon bucket
    # as H1, whose representative chart is H1, so it is not a distinct proposal and is dropped.
    assert {v for a, v, _n in moves if a == "chart"} == {"H4"}
    assert {v for a, v, _n in moves if a == "session"} == {"all", "london", "ny"}
    assert {v for a, v, _n in moves if a == "family"} == {"level_breakout"}
    for _a, _v, n in moves:
        assert n["mechanism"] == "breakout_liquidity", "a mutation never leaves the mechanism"


# ------------------------------------------------------------------ the connector
def test_the_connector_carries_one_elite_onto_another_niches_session(desk):
    """Two commodities elites: an H1 breakout in `asia` and an H4 carry in `london`. The cross is
    the breakout family run on the carry niche's clock AND horizon -- TWO axes from either parent,
    which is exactly the ground the explorer's one-move rule can never reach."""
    left = _cell("XAUUSD", "session_range_breakout", state="FORWARD", score=2.0,
                 basis=qd.FORWARD_BASIS, session="asia")
    right = _cell("XAGUSD", "carry", state="FORWARD", score=1.0, basis=qd.FORWARD_BASIS,
                  session="london", timeframe="H4")
    cells = _cells(left, right)
    niches = qd.build_niches(cells)
    assert qd.niche_of(right)["horizon"] == "sub_1d" and qd.niche_of(left)["horizon"] == "sub_4h"
    pairs = qd.connector_pairs(niches)
    assert pairs, "both niches are commodities, so they share an asset class"
    assert {p["share"] for p in pairs} == {"asset_class"}
    crossed = [p for p in pairs if p["elite"]["family"] == "session_range_breakout"]
    assert crossed and crossed[0]["niche"]["session"] == "london"
    assert crossed[0]["niche"]["horizon"] == "sub_1d", "the RIGHT niche's horizon"
    assert crossed[0]["niche"]["mechanism"] == "breakout_liquidity", "the LEFT niche's mechanism"

    now = datetime.now(UTC)
    families, by_class = ar.registered_families(), ar.instruments_by_class()
    picked = qd.select(cells, niches, qd.candidate_niches(families, by_class), families,
                       by_class, now, 30)
    assert picked["connector"]
    for row in picked["connector"]:
        assert "CROSS-NICHE" in row["why"] and " share " in row["why"]
        assert row["source"] == "qd_frontier:connector"
    carried = [r for r in picked["connector"] if r["family"] == "session_range_breakout"]
    assert carried and carried[0]["session"] == "london" and carried[0]["timeframe"] == "H4"


def test_two_niches_sharing_nothing_are_never_connected(desk):
    """forex carry and commodities breakout share neither an asset class nor a mechanism."""
    niches = qd.build_niches(_cells(
        _cell("EURUSD", "carry", state="FORWARD", score=1.0, basis=qd.FORWARD_BASIS),
        _cell("XAUUSD", "session_range_breakout", state="FORWARD", score=1.0,
              basis=qd.FORWARD_BASIS, session="asia")))
    assert qd.connector_pairs(niches) == []


# ------------------------------------------------------------------ what may be proposed
def test_every_proposal_names_a_registered_family_and_never_a_single_name_equity(desk):
    _forward(desk, symbol="EURUSD", n=16, exp_r=0.5)
    _write(desk["SLEEVES"], {"sleeves": [{"symbol": "XAUUSD", "family": "session_range_breakout",
                                          "session": "asia", "status": "LIVE",
                                          "shadow_exp": 0.4, "shadow_n": 9}]})
    _report, _niches, proposals = qd.build(qd.DEFAULT_PROPOSALS)
    assert proposals
    assert {p["family"] for p in proposals} <= _FAMILIES
    assert not {p["family"] for p in proposals} & ar.NOT_A_FAMILY
    for p in proposals:
        assert p["kind"] == "hypothesis" and p["source"].startswith("qd_frontier:")
        assert p["selector_mode"] in qd.WORKERS
        assert set(p["axis_cell"]) == set(ar.AXES)
        assert p["symbols"] and all(ar.may_hypothesise(s) for s in p["symbols"])
        assert "APPLE" not in p["symbols"], "the event lane is never hunted"
        assert p["session"] in qd.PROPOSABLE_SESSIONS
        assert p["params"].get("timeframe", p["timeframe"]) == p["timeframe"]
    ids = [ar.cell_id(p["axis_cell"]) for p in proposals]
    assert len(ids) == len(set(ids)), "one coordinate is proposed once, by one arm"


def test_an_elite_whose_family_is_not_registered_is_never_donated(desk):
    """`turn_of_month` is a real historic family and is NOT in this registry. The exploiter must
    fall silent on it rather than fall through to a name the desk cannot call."""
    cells = _cells(_cell("EURUSD", "turn_of_month", state="FORWARD", score=5.0,
                         basis=qd.FORWARD_BASIS))
    niches = qd.build_niches(cells)
    now = datetime.now(UTC)
    qd.merge_map(niches, {}, now.isoformat())
    families, by_class = ar.registered_families(), ar.instruments_by_class()
    picked = qd.select(cells, niches, qd.candidate_niches(families, by_class), families,
                       by_class, now, 30)
    rows = [p for w in qd.WORKERS for p in picked[w]]
    assert rows, "the explorer still has empty ground to reach"
    assert "turn_of_month" not in {p["family"] for p in rows}
    assert picked["exploiter"] == [] and picked["connector"] == []


def test_the_budget_splits_three_ways_and_the_ceiling_cannot_be_argued_away(desk):
    """An equal share each, the remainder to the explorer. An arm with no work leaves its share
    UNSPENT rather than handing it over -- a budget one arm can absorb is a leaderboard again."""
    _forward(desk, symbol="EURUSD", n=16, exp_r=0.5)
    report, _n, proposals = qd.build(10)
    counts = report["summary"]["proposals"]
    assert counts["explorer"] == 4, "3 each plus the remainder"
    assert counts["exploiter"] <= 3
    assert counts["connector"] == 0, "one niche has nothing to cross with"
    assert len(proposals) == sum(counts.values()) <= 10
    # The ceiling lives in `build`, not in the CLI: a bound a flag can argue away is no bound.
    _report, _n, huge = qd.build(100_000)
    assert len(huge) <= qd.MAX_PROPOSALS
    _report, _n, none = qd.build(0)
    assert none == []


# ------------------------------------------------------------------ the accounting
def test_dominance_and_elite_families_are_the_anti_monoculture_numbers(desk):
    """Three niches, two of them held by the same family: that is the number the frontier exists
    to move, and an elite with no family named is not a family holding two thirds of the book."""
    cells = _cells(
        _cell("XAUUSD", "session_range_breakout", state="FORWARD", score=2.0,
              basis=qd.FORWARD_BASIS, session="asia"),
        _cell("EURUSD", "session_range_breakout", state="FORWARD", score=2.0,
              basis=qd.FORWARD_BASIS, session="london"),
        _cell("GBPUSD", "carry", state="FORWARD", score=1.0, basis=qd.FORWARD_BASIS))
    niches = qd.build_niches(cells)
    acc = qd.accounting(niches, qd.candidate_niches(ar.registered_families(),
                                                    ar.instruments_by_class()),
                        {w: [] for w in qd.WORKERS})
    assert acc["niches_occupied"] == 3
    assert acc["elite_families"] == 2
    assert acc["dominance"] == pytest.approx(2 / 3, abs=1e-4)
    assert acc["dominant_family"] == "session_range_breakout"
    assert acc["niches_empty"] == acc["n_candidate_niches"] - 3, "all three are buildable ground"

    unnamed = qd.build_niches(_cells(_cell("EURUSD", "carry")))
    for row in unnamed.values():
        row["elite_family"] = ""
    blank = qd.accounting(unnamed, {}, {w: [] for w in qd.WORKERS})
    assert blank["elite_families"] == 0 and blank["dominance"] == 0.0
    assert blank["elites_without_family"] == 1 and blank["dominant_family"] == qd.UNKNOWN


# ------------------------------------------------------------------ persistence
def test_the_map_remembers_when_a_niche_last_improved_across_two_runs(desk):
    _forward(desk, symbol="EURUSD", n=16, exp_r=0.02)
    assert qd.main([]) == 0
    first = json.loads(desk["OUT_MAP"].read_text(encoding="utf-8-sig"))
    key = next(iter(first["niches"]))
    stamp = first["niches"][key]["last_improved_at"]
    assert stamp and first["niches"][key]["first_seen_at"] == stamp

    # A SECOND RUN OVER THE SAME ARTIFACTS IMPROVES NOTHING. If re-reading reset the clock the
    # exploiter would believe every niche had just got better, forever.
    assert qd.main([]) == 0
    second = json.loads(desk["OUT_MAP"].read_text(encoding="utf-8-sig"))
    assert second["niches"][key]["last_improved_at"] == stamp
    assert second["niches"][key]["first_seen_at"] == stamp
    assert second["at"] != first["at"], "the run stamp still moves"

    _forward(desk, symbol="EURUSD", n=64, exp_r=0.5)               # a better elite
    assert qd.main([]) == 0
    third = json.loads(desk["OUT_MAP"].read_text(encoding="utf-8-sig"))
    assert third["niches"][key]["last_improved_at"] > stamp
    assert third["niches"][key]["first_seen_at"] == stamp


def test_a_weaker_reading_never_resets_the_improvement_clock(desk):
    niches = qd.build_niches(_cells(_cell("EURUSD", "carry", score=0.5,
                                          basis="in_sample_sharpe")))
    key = next(iter(niches))
    old = "2026-09-01T00:00:00+00:00"
    previous = {"niches": {key: {"elite_evidence_basis": qd.FORWARD_BASIS, "elite_score": 9.0,
                                 "last_improved_at": old, "first_seen_at": old}}}
    qd.merge_map(niches, previous, "2026-09-16T00:00:00+00:00")
    assert niches[key]["last_improved_at"] == old
    assert niches[key]["first_seen_at"] == old


# ------------------------------------------------------------------ tolerance and the CLI
def test_every_input_may_be_absent_and_the_report_says_so_rather_than_crashing(desk):
    report, niches, proposals = qd.build()
    assert niches == {} and proposals == []
    assert report["n_cells"] == 0 and report["n_niches"] == 0
    assert set(report["unmeasured"]["inputs"].values()) == {"ABSENT"}
    assert set(report["unmeasured"]["inputs"]) == {
        "AXIS_REGISTRY.json", "axis_registry.jsonl", "gate_verdict_ledger.jsonl",
        "UNIVERSAL_SURVIVORS.json", "shadow_state.json", "sleeves.json", "qd_mental_map.json"}
    assert any("no judged cell" in w for w in report["unmeasured"]["why"])
    assert report["summary"]["niches_occupied"] == 0
    assert report["summary"]["niches_empty"] == report["summary"]["n_candidate_niches"] > 0
    assert report["summary"]["dominance"] == 0.0
    assert report["rule"] and report["summary"]["axis_registry_at"] == qd.UNKNOWN


def test_an_unreadable_or_bom_input_is_named_not_silently_skipped(desk):
    desk["SLEEVES"].parent.mkdir(parents=True, exist_ok=True)
    desk["SLEEVES"].write_text("{", encoding="utf-8")
    desk["SHADOW_STATE"].parent.mkdir(parents=True, exist_ok=True)
    desk["SHADOW_STATE"].write_text(
        json.dumps({"EURUSD.carry.asia": {"status": "ACTIVE", "n": 4, "exp_r": 0.1}}),
        encoding="utf-8-sig")
    report, niches, _p = qd.build(0)
    assert report["unmeasured"]["inputs"]["sleeves.json"].startswith("UNREADABLE")
    assert len(niches) == 1, "a BOM is not a reason to lose a forward clock"


def test_the_cli_dry_run_prints_eight_lines_and_writes_nothing(desk, capsys):
    _forward(desk, symbol="EURUSD", n=16, exp_r=0.5)
    assert qd.main(["--dry-run", "--max-proposals", "6"]) == 0
    lines = capsys.readouterr().out.strip().split("\n")
    assert len(lines) == 8, lines
    assert lines[0].startswith("QD FRONTIER") and "shadow_state.json=READ" in lines[0]
    assert "cells 1" in lines[1] and "niches occupied 1" in lines[1]
    assert "elite_families=1" in lines[3] and "dominance=1.0" in lines[3]
    assert "DRY RUN" in lines[6]
    assert not desk["OUT_REPORT"].exists() and not desk["OUT_MAP"].exists()
    assert not desk["INTAKE"].exists()


def test_a_real_run_writes_the_report_the_map_and_the_intake_donation(desk, capsys):
    _forward(desk, symbol="EURUSD", n=16, exp_r=0.5)
    assert qd.main(["--max-proposals", "6"]) == 0
    report = json.loads(desk["OUT_REPORT"].read_text(encoding="utf-8-sig"))
    assert set(report) >= {"at", "n_cells", "n_niches", "niches", "summary", "proposals",
                           "unmeasured", "rule"}
    assert report["n_cells"] == 1 and report["n_niches"] == 1
    assert set(report["proposals"]) == set(qd.WORKERS)
    assert report["summary"]["proposals"]["explorer"] >= 1
    mental = json.loads(desk["OUT_MAP"].read_text(encoding="utf-8-sig"))
    assert set(mental["niches"]) == set(report["niches"])
    donations = sorted(desk["INTAKE"].glob("discoveries_*.json"))
    assert len(donations) == 1
    rows = json.loads(donations[0].read_text(encoding="utf-8"))
    assert 0 < len(rows) <= 6
    assert all(r["source"].startswith("qd_frontier:") for r in rows)
    assert not list(desk["INTAKE"].glob("*.tmp")), "an atomic write leaves no temp file behind"
    assert len(capsys.readouterr().out.strip().split("\n")) == 8


def test_the_report_caps_its_niche_block_but_never_its_count(desk, monkeypatch):
    monkeypatch.setattr(qd, "REPORT_NICHES", 2)
    _write_lines(desk["GATE_LEDGER"], [
        {"cell": f"{sym}.{fam}.{sess}", "sym": sym, "family": fam, "passed": False,
         "terminal_gate": "pbo"}
        for sym, fam, sess in (("EURUSD", "carry", "asia"), ("GBPUSD", "carry", "london"),
                               ("XAUUSD", "session_range_breakout", "ny"),
                               ("XAGUSD", "mean_reversion_rsi", "all"))])
    report, niches, _p = qd.build(0)
    assert len(niches) == 4 and report["n_niches"] == 4
    assert len(report["niches"]) == 2 and report["summary"]["niches_in_file"] == 2
