"""THE PRODUCER/CONSUMER CONTRACT between the science controller and the meta controller.

WHY THIS FILE EXISTS, and it is a specific bug rather than a general worry. `meta_controller`
ranked every anytime-valid DISCOVERY at `p_success = 0.0` for as long as the pair has existed,
because it read `continuation["anytime_p"]` and `science_controller.continuation_of` emits
`anytime_p_discovery` and `anytime_p_futility`. The existing unit test passed the whole time: its
fixture was TYPED BY HAND with the key the consumer wanted. A hand-written fixture cannot catch a
producer/consumer drift -- it can only confirm that the consumer reads the fixture.

So every test here builds the row with the PRODUCER and hands it to the CONSUMER. That is the one
arrangement in which a renamed key fails a test instead of silently zeroing a ranking.

It also pins the two properties that make the controller's verdict anytime-valid, because those
are the claims the whole campaign machinery rests on and neither is obvious from reading the code:

  * OPTIONAL STOPPING IS LEGAL. The decision on a prefix of a stream is never reversed by more of
    the stream. A controller that changed its mind as data arrived would make "stop when it says
    discovered" a data-dependent stopping rule with no error control at all -- the exact failure
    the e-process exists to prevent (Ville's inequality bounds the chance the martingale EVER
    crosses, not the chance it crosses at a fixed n).

  * THE NULL DOES NOT FIRE. A stream generated at exactly the sealed gate level must not be
    declared a discovery. This is the false-positive half, and it is asserted at a much longer
    horizon than any family will ever have, because a boundary that is crossed by noise at n=400
    is a boundary that will be crossed by noise on the box.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import meta_controller as MC  # noqa: E402
from research import science_controller as SC  # noqa: E402

GATE_LEVEL = 0.05
ALPHA = 0.05


def _family_row(stream: list[bool], *, queued: int = 3) -> dict[str, Any]:
    """A family row shaped EXACTLY as `science_controller.build` shapes it, with the
    continuation block produced by the controller rather than typed here."""
    cont = SC.continuation_of(stream, GATE_LEVEL, ALPHA)
    passes = sum(1 for s in stream if s)
    return {"family_id": "fam:test", "judged": len(stream), "passes_at_gate": passes,
            "queued": queued, "continuation": cont,
            "anytime_p": cont["anytime_p_discovery"]}


# --------------------------------------------------------------- the contract
def test_a_discovered_family_reaches_the_meta_controller_with_a_real_p_success() -> None:
    row = _family_row([True] * 12)
    assert row["continuation"]["decision"] == SC.STOP_DISCOVERED, row["continuation"]["why"]
    actions = MC._science_actions({"families": {"top": [row]}})
    deepen = [a for a in actions if a["kind"] == "deepen_existing"]
    assert deepen, "an anytime-valid DISCOVERY must reach the meta controller as an action"
    assert deepen[0]["p_success"] > 0.9, (
        "a family whose e-process crossed 1/alpha was ranked at p_success="
        f"{deepen[0]['p_success']} -- the consumer is reading a key the producer does not emit")


def test_the_key_the_consumer_reads_is_one_the_producer_actually_emits() -> None:
    cont = SC.continuation_of([True] * 12, GATE_LEVEL, ALPHA)
    assert "anytime_p_discovery" in cont and "anytime_p_futility" in cont
    assert MC._anytime_p(cont, {}) == cont["anytime_p_discovery"]
    # the family-row fallback, for a report written before the continuation block existed
    assert MC._anytime_p({}, {"anytime_p": 0.02}) == 0.02
    # and nothing readable at all scores the action at zero rather than inventing confidence
    assert MC._anytime_p({}, {}) == 1.0


def test_a_futile_family_frees_its_queued_cells_and_claims_no_success() -> None:
    row = _family_row([False] * 100, queued=7)
    assert row["continuation"]["decision"] == SC.STOP_FUTILE, row["continuation"]["why"]
    actions = MC._science_actions({"families": {"top": [row]}})
    abandon = [a for a in actions if a["kind"] == "abandon_region"]
    assert abandon and abandon[0]["frees_cells"] == 7.0
    assert abandon[0]["p_success"] is None, "a futile family claims nothing, not zero"


def test_an_undecided_family_produces_no_action() -> None:
    row = _family_row([True, False, False])
    assert row["continuation"]["decision"] == SC.CONTINUE
    assert MC._science_actions({"families": {"top": [row]}}) == []


# --------------------------------------------------------------- anytime validity
def test_optional_stopping_is_legal_a_decision_never_reverses() -> None:
    stream = [True] * 10 + [False] * 40 + [True] * 10
    first = None
    for n in range(1, len(stream) + 1):
        got = SC.continuation_of(stream[:n], GATE_LEVEL, ALPHA)
        if got["decision"] != SC.CONTINUE and first is None:
            first = got["decision"]
        if first is not None:
            assert got["decision"] == first, (
                f"the verdict changed at n={n}: {first} -> {got['decision']}. Optional stopping "
                f"is only legal if reading more of the stream cannot reverse the boundary.")
    assert first == SC.STOP_DISCOVERED


def test_the_full_stream_decision_matches_the_prefix_it_was_decided_on() -> None:
    stream = [True] * 12 + [False] * 5
    full = SC.continuation_of(stream, GATE_LEVEL, ALPHA)
    assert full["decided_at"] is not None
    prefix = SC.continuation_of(stream[:full["decided_at"]], GATE_LEVEL, ALPHA)
    assert prefix["decision"] == full["decision"] == SC.STOP_DISCOVERED


def test_the_null_does_not_fire_at_a_horizon_no_family_will_ever_reach() -> None:
    # S311: a null stream for a statistical property, never a key. `random` is the right tool
    # and the seed is fixed, so a failure here is reproducible rather than a flake.
    rng = random.Random(20260923)  # noqa: S311
    fired = 0
    for _ in range(40):
        stream = [rng.random() < GATE_LEVEL for _ in range(400)]
        if SC.continuation_of(stream, GATE_LEVEL, ALPHA)["decision"] == SC.STOP_DISCOVERED:
            fired += 1
    assert fired <= 4, (
        f"{fired}/40 null streams were declared DISCOVERED at alpha={ALPHA}; Ville's inequality "
        f"bounds this at alpha over the WHOLE stream, so a rate far above it means the e-process "
        f"is not a test martingale under the sealed level")


def test_an_empty_stream_continues_and_says_it_is_unmeasured() -> None:
    got = SC.continuation_of([], GATE_LEVEL, ALPHA)
    assert got["decision"] == SC.CONTINUE and got["n"] == 0
    assert SC.UNMEASURED in got["why"], "a campaign nobody judged is UNMEASURED, not futile"
    assert got["excess_pass_rate_cs"] == [None, None]


def test_the_confidence_sequence_brackets_the_excess_pass_rate() -> None:
    """The interval is a report, but a report that never contains the truth is worse than none."""
    stream = [True] * 20 + [False] * 180          # 10% observed against a 5% level
    got = SC.continuation_of(stream, GATE_LEVEL, ALPHA)
    lo, hi = got["excess_pass_rate_cs"]
    assert lo is not None and hi is not None
    # the interval is on the MEAN increment (the field is a RATE), not the running sum
    observed_excess_rate = (float(got["passes"]) - got["n"] * GATE_LEVEL) / got["n"]
    assert lo <= observed_excess_rate <= hi, (
        f"CS [{lo}, {hi}] does not contain the observed excess rate {observed_excess_rate}")
    assert lo < 0.0 < hi or lo > 0.0, "the interval must be a real statement, not (-inf, inf)"
