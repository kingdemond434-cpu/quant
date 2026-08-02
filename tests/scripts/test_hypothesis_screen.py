"""The daily hypothesis funnel -- volume in, screened candidates out, bar unmoved.

THE PRINCIPAL'S IDEA: have an AI work thousands of hypotheses a day against the desk's standards
so the real gauntlet receives pre-screened candidates. It aims at the measured bottleneck exactly
-- 420 candidates, zero survivors, and waiving the campaign veto was proven to promote nobody, so
the candidates are the problem and not the bar.

THE TRAP THESE TESTS EXIST FOR: an LLM cannot test a hypothesis. It has no price data and runs no
backtest. Ask one to "apply the gate standards and return survivors" and it returns survivors --
fluently, with plausible numbers, having computed nothing. That is a random filter wearing the
language of rigour, and it is strictly WORSE than no screen, because its output reaches the
gauntlet carrying a false prior of quality.

So the fabrication guard is the load-bearing test here, and the direction matters: a fabricated
verdict must not be able to KILL a live hypothesis, which is the failure that would silently
delete real alpha while looking like diligence.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location("hs", ROOT / "scripts/hypothesis_screen.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


HS = _mod()


def _h(name: str, **kw) -> dict:
    return {"name": name, "data": kw.pop("data", "orderbook depth feed"),
            "lens": kw.pop("lens", "MEASUREMENT ADVANTAGE"),
            "test": kw.pop("test", "4 hour horizon"), "seat": kw.pop("seat", "openai/x"), **kw}


# --------------------------------------------------------------- the fabrication guard


@pytest.mark.parametrize("reason", [
    "backtested Sharpe of 0.2",
    "t-stat below 2",
    "p-value 0.4 so no edge",
    "I ran this and the IC of 0.01 is noise",
    "annualized return of 3% does not clear costs",
])
def test_a_verdict_claiming_statistics_is_discarded_entirely(reason: str) -> None:
    """Not the phrase -- the WHOLE verdict. A seat willing to invent a t-stat is answering from
    plausibility rather than from the four questions it was given, so its mechanism judgement in
    the same breath is worth nothing."""
    clean, dropped = HS.strip_fabrication(
        [{"name": "h", "seat": "bad/seat", "verdict": "KILL", "reason": reason}])
    assert clean == [] and len(dropped) == 1


def test_a_fabricated_kill_cannot_delete_a_live_hypothesis() -> None:
    """THE DIRECTION THAT MATTERS. A hallucinated Sharpe must never remove a real candidate."""
    verdicts = [
        {"name": "depth replenishment", "seat": "a/1", "verdict": "PASS", "reason": "real barrier"},
        {"name": "depth replenishment", "seat": "b/2", "verdict": "KILL",
         "reason": "backtested Sharpe of 0.1"},
        {"name": "depth replenishment", "seat": "c/3", "verdict": "KILL",
         "reason": "t-stat under 1"},
    ]
    clean, dropped = HS.strip_fabrication(verdicts)
    adj = HS.adjudicate(clean, n_seats=3)
    assert len(dropped) == 2
    assert adj["depth replenishment"]["survived"] is True


def test_a_genuine_mechanism_kill_still_works() -> None:
    """The guard must not make the screen toothless -- real reasons must still kill."""
    verdicts = [
        {"name": "h", "seat": "a/1", "verdict": "KILL",
         "reason": "public data, already arbitraged"},
        {"name": "h", "seat": "b/2", "verdict": "KILL", "reason": "no barrier to entry"},
        {"name": "h", "seat": "c/3", "verdict": "PASS", "reason": "unsure"},
    ]
    adj = HS.adjudicate(verdicts, n_seats=3)
    assert adj["h"]["survived"] is False


# --------------------------------------------------------------- majority, not veto


def test_one_seat_can_never_kill() -> None:
    """A single veto would let one model's blind spot define what the desk may investigate --
    the single-reviewer trap the multi-lab roster exists to break."""
    verdicts = [{"name": "h", "seat": "a/1", "verdict": "KILL", "reason": "do not like it"},
                {"name": "h", "seat": "b/2", "verdict": "PASS", "reason": "fine"},
                {"name": "h", "seat": "c/3", "verdict": "PASS", "reason": "fine"}]
    assert HS.adjudicate(verdicts, n_seats=3)["h"]["survived"] is True


def test_a_tie_survives() -> None:
    """Ambiguity must not kill: a wrongly-killed hypothesis is never recovered, a wrongly-passed
    one dies in the gauntlet for the price of some compute."""
    verdicts = [{"name": "h", "seat": "a/1", "verdict": "KILL", "reason": "x"},
                {"name": "h", "seat": "b/2", "verdict": "PASS", "reason": "y"}]
    assert HS.adjudicate(verdicts, n_seats=2)["h"]["survived"] is True


def test_a_seat_that_did_not_answer_is_not_a_vote() -> None:
    verdicts = [{"name": "h", "seat": "a/1", "verdict": "KILL", "reason": "x"}]
    e = HS.adjudicate(verdicts, n_seats=8)["h"]
    assert e["voted"] == 1 and e["quorum"] is False


# --------------------------------------------------------------- arithmetic stage


def test_arithmetic_kills_only_on_present_evidence() -> None:
    """Missing fields can never cause a rejection -- a hypothesis nobody measured must reach
    stage 2."""
    kept, why = HS.deterministic_screen([_h("unmeasured idea")])
    assert len(kept) == 1 and not why


def test_cost_floor_and_degenerate_turnover_do_kill() -> None:
    kept, why = HS.deterministic_screen([
        _h("cannot pay for itself", gross_edge_bps=1.0, round_trip_cost_bps=2.0),
        _h("takes no positions", turnover=0.0),
        _h("survivor"),
    ])
    assert len(kept) == 1 and kept[0]["name"] == "survivor"
    assert sum(why.values()) == 2


def test_every_candidate_carries_a_fingerprint_and_horizon_bucket() -> None:
    kept, _ = HS.deterministic_screen([_h("x", test="12 hour horizon")])
    assert kept[0]["fingerprint"].count("|") == 2
    assert kept[0]["horizon_bucket"] == "swing"


def test_an_unstated_horizon_becomes_unknown_not_a_guess() -> None:
    """Inventing a horizon would let two genuinely different mechanisms collide, and the
    trivial-variation blocker would then suppress a live one."""
    kept, _ = HS.deterministic_screen([_h("no horizon stated", test="see description")])
    assert kept[0]["horizon_bucket"] == "unknown"


# --------------------------------------------------------------- seat yield


def test_yield_ranks_distinct_survivors_not_raw_volume() -> None:
    """A seat emitting near-identical hypotheses outranks everyone on count while contributing
    almost nothing. The desk's own measurement already showed reputation is the wrong prior:
    gpt produced 0 parseable rows on 5 of 6 breadth lenses where nemotron/grok produced 18."""
    spammer = [_h(f"same idea {i}", seat="spam/model", data="orderbook depth") for i in range(8)]
    diverse = [_h(f"idea {i}", seat="broad/model", data=f"source{chr(97 + i)} feed")
               for i in range(8)]
    gen = spammer + diverse
    kept, _ = HS.deterministic_screen([dict(r) for r in gen])
    ys = {y["seat"]: y for y in HS.seat_yield(gen, kept)}
    assert ys["broad/model"]["distinct_survivors"] > ys["spam/model"]["distinct_survivors"]
    assert ys["spam/model"]["duplicate_rate"] > 0.5
    assert HS.seat_yield(gen, kept)[0]["seat"] == "broad/model", "ranked by distinct survivors"


def test_yield_is_empty_without_input_rather_than_crashing() -> None:
    assert HS.seat_yield([], []) == []


# --------------------------------------------------------------- contract


def test_the_adjudication_prompt_forbids_statistics_explicitly() -> None:
    s = HS.ADJUDICATION_SYSTEM
    assert "NO PRICE DATA" in s and "NEVER state or estimate a Sharpe" in s
    assert "voids your entire verdict" in s
    assert "If unsure, PASS" in s, "the screen must bias toward letting things through"


def test_the_funnel_claims_no_promotion_authority() -> None:
    src = (ROOT / "scripts/hypothesis_screen.py").read_text("utf-8")
    assert "ZERO promotion authority" in src
    assert "Two-Stage Discovery Law" in src


def test_moat_candidates_cannot_be_starved_by_public_volume() -> None:
    """P26. EVIG already prefers owned data ~3x on replication cost, but PREFERENCE LOSES TO
    VOLUME: ninety public ideas and three moat ones puts public work at the head anyway, and the
    desk spends the day exploring data anyone can buy while the un-replicable asset waits."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.hypothesis_screen import MOAT_SLOT_FLOOR, score_evig
    rows = [{"name": f"public {i}", "data_source": "public funding endpoint"} for i in range(40)]
    rows += [{"name": f"depth withdrawal {i}", "data_source": "our recorded order books"}
             for i in range(3)]
    out = score_evig(rows, {})
    head = out[:20]
    assert sum(1 for c in head if c["moat_advantage"] > 0.5) == 3, (
        "every available moat candidate must reach the head when the floor allows room")
    assert MOAT_SLOT_FLOOR > 0


def test_reserving_slots_never_changes_the_bar() -> None:
    """NOT A BAR CHANGE, and the distinction is load-bearing: everything here already passed the
    same screen. Reserving among equals only decides which SURVIVOR gets scarce compute first."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.hypothesis_screen import reserve_moat_slots
    ranked = [{"n": i, "moat_advantage": 0.37} for i in range(10)]
    ranked += [{"n": 99, "moat_advantage": 1.03}]
    out = reserve_moat_slots(ranked)
    assert len(out) == len(ranked), "reserving must never add or drop a candidate"
    assert {id(c) for c in out} == {id(c) for c in ranked}
    assert out[0]["moat_advantage"] > 0.5
    assert "Not a bar change" in out[0]["moat_slot_note"]


def test_an_empty_reservation_is_not_left_idle() -> None:
    """P12: idle capacity with positive-return work waiting is a failure, so unused reserved
    slots go to the next best rather than sitting empty."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.hypothesis_screen import reserve_moat_slots
    ranked = [{"n": i, "moat_advantage": 0.37} for i in range(10)]
    assert reserve_moat_slots(ranked) == ranked
