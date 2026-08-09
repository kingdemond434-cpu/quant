"""R0152 discretionary edge hunt -- find the NEXT edge, not just tune the current one.

A second INDEPENDENT edge is worth more than a large improvement to the first, because growth
multiplies across uncorrelated bets and merely adds within one. These tests pin the forced-
participant filter (the desk is 420-tested/0-survived on patterns) and the anti-repetition that
stops a brainstorm loop from regenerating the same six ideas forever.
"""
from __future__ import annotations

import json

from scripts.run_discretionary_hunt import (
    _LENSES,
    EXHAUSTION_REPEAT_RATE,
    build_report,
    lens_for,
    load_registry,
    register,
    validate,
)


def _cand(**kw):
    base = {"name": "stop sweep above a triple-touched high",
            "situation": "price wicks through a level touched three times, then reverses hard",
            "forced_participant": "resting stop orders from swing longs, which execute as market "
                                  "sells the instant the level prints and cannot be withdrawn",
            "mechanism": "the stop cluster is the only guaranteed liquidity at that level, so size "
                         "that needs a fill has to reach for it before the real move begins",
            "falsifier": "sweeps are followed by continuation as often as reversal over 100 events",
            "how_measured": "chart context swing levels plus the liquidations feed"}
    base.update(kw)
    return base


def test_a_candidate_naming_no_forced_participant_is_refused():
    # "traders" and "the market" name nobody. A hypothesis with no compelled counterparty is a
    # pattern, and the desk's record on patterns is 420 tested, 0 survived.
    for bad in ("traders will panic and sell", "the market overreacts here", "everyone chases it"):
        ok, why = validate(_cand(forced_participant=bad))
        assert not ok and "420-tested" in why


def test_a_thin_mechanism_or_falsifier_is_refused():
    assert not validate(_cand(mechanism="it just works"))[0]
    assert not validate(_cand(falsifier="it fails"))[0]
    assert validate(_cand())[0]


def test_a_good_candidate_is_registered_with_no_promotion_authority(tmp_path):
    res = register(tmp_path, [_cand()], "FORCED LIQUIDITY")
    assert res["new"] and res["registry_size"] == 1
    edge = load_registry(tmp_path)["edges"][0]
    assert edge["status"] == "CANDIDATE"
    assert "never capital" in edge["authority"]


def test_the_same_idea_twice_is_a_repeat_not_a_new_edge(tmp_path):
    # A hunt that regenerates the same six ideas every night looks productive and produces
    # nothing -- the failure mode of every brainstorming loop ever built.
    register(tmp_path, [_cand()], "FORCED LIQUIDITY")
    res = register(tmp_path, [_cand()], "FORCED LIQUIDITY")
    assert res["new"] == [] and res["repeats"] and res["repeat_rate"] == 1.0
    assert res["registry_size"] == 1


def test_an_exhausted_lens_says_re_aim_not_run_more_often(tmp_path):
    # Raising the cadence on an exhausted space regenerates the same ideas faster.
    register(tmp_path, [_cand()], "FORCED LIQUIDITY")
    rep = build_report(tmp_path, ask=lambda _p: json.dumps({"candidates": [_cand()]}))
    assert rep["repeat_rate"] >= EXHAUSTION_REPEAT_RATE
    assert "re-aim the lenses" in rep["exhaustion"]
    assert "do NOT raise the cadence" in rep["exhaustion"]


def test_lens_rotation_covers_every_lens_and_is_deterministic():
    got = {lens_for(f"2026080{d}")[0] for d in range(1, 8)}
    assert got == {n for n, _ in _LENSES}
    assert lens_for("20260801") == lens_for("20260801")


def test_the_lenses_are_about_participants_not_indicators():
    blob = " ".join(b for _, b in _LENSES).lower()
    assert "forced" in blob and "late" in blob
    for indicator in ("rsi", "macd", "moving average", "bollinger"):
        assert indicator not in blob


def test_an_unparseable_hunt_is_unmeasured_not_an_empty_search_space(tmp_path):
    rep = build_report(tmp_path, ask=lambda _p: "I decline")
    assert rep["status"] == "NO-CANDIDATES" and "UNMEASURED hunting" in rep["why"]


def test_survivors_go_to_the_allocator_not_to_capital(tmp_path):
    rep = build_report(tmp_path, ask=lambda _p: json.dumps({"candidates": [_cand()]}))
    assert "forward clock" in rep["authority"] and "no capital" in rep["authority"]
    assert "wearing a new name" in rep["authority"]
