"""The push ladder -- exhaust every seat, every organ, every day.

THE OBSERVATION (principal, 2026-07-31): these models generate MORE when pushed. The first
answer is shaped by an implicit sense of "a reasonable amount to say", not by the model's actual
inventory, so a short follow-up reliably surfaces material the first answer omitted.

The tests that matter here are the STOP conditions, because the design claim is "push until it
gives up" rather than "push N times". A fixed count either stops while the seat still has
material (wasted inventory the desk already paid the input cost for) or keeps billing for
paraphrases (throughput without information -- the exact mode collapse batch_diversity() exists
to catch). Exhaustion has to be measured, and a failed push must never cost the answer that
already succeeded.
"""

from __future__ import annotations

import contextlib
import itertools

import pytest

from libs.llm.push import (
    GENERATION_LADDER,
    MAX_ROUNDS,
    MIN_NOVELTY,
    PUSH_LADDER,
    _rungs_for,
    novelty,
    push_rounds,
)


def _scripted(*replies: str):
    """An `ask` that returns each reply in turn, then recycles the last one forever."""
    it = iter(replies)
    last = {"v": ""}

    def ask(_msgs):
        with contextlib.suppress(StopIteration):
            last["v"] = next(it)
        return last["v"]
    return ask


# --------------------------------------------------------------- stop conditions


def test_exhaustion_stops_the_ladder_when_novelty_dies() -> None:
    """THE CENTRAL BEHAVIOUR: recycled content ends the ladder, and is not billed further."""
    r = push_rounds(_scripted(
        "funding basis carry mechanism spread",
        "depth queue replenishment iceberg latent",
        "liquidation cascade collateral unlock validator",
        "funding basis carry mechanism spread",       # recycled -> exhausted
    ), "sys", "user")
    assert "exhausted" in r.stop_reason
    assert r.rounds == 3, "must stop ON the recycled round, not after it"


def test_explicit_surrender_is_believed_immediately() -> None:
    """Paying for another round to confirm a 'no' is pure waste."""
    r = push_rounds(_scripted("real material about funding", "NOTHING FURTHER"), "sys", "user")
    assert "surrender" in r.stop_reason
    assert r.rounds == 1


def test_an_inexhaustible_model_is_capped() -> None:
    """A model that hallucinates novelty forever must not bill indefinitely."""
    c = itertools.count()
    r = push_rounds(lambda _m: f"alpha{next(c)} beta{next(c)} gamma{next(c)} delta{next(c)}",
                    "sys", "user")
    assert r.rounds == MAX_ROUNDS
    assert "cap" in r.stop_reason, (
        "hitting the cap must be recorded DISTINCTLY from exhaustion -- it means the limit "
        "stopped the ladder, not the model, and the cap should probably rise")


def test_a_failed_push_never_loses_the_completed_answer() -> None:
    """If losing a follow-up cost the answer, pushing would be strictly worse than not pushing --
    and would therefore get switched off."""
    n = {"i": 0}

    def flaky(_msgs):
        n["i"] += 1
        if n["i"] > 3:
            raise TimeoutError("gateway")
        return f"distinct{n['i']} material{n['i']} content{n['i']}"

    r = push_rounds(flaky, "sys", "user")
    assert r.rounds == 2
    assert "failed" in r.stop_reason and "prior rounds kept" in r.stop_reason
    assert "distinct1" in r.text and "distinct3" in r.text


def test_an_empty_opening_is_not_pushed() -> None:
    """Pushing an empty thread bills for nothing."""
    r = push_rounds(_scripted(""), "sys", "user")
    assert r.rounds == 0 and "not pushed" in r.stop_reason


def test_empty_mid_ladder_response_stops_cleanly() -> None:
    r = push_rounds(_scripted("real content here about spreads", ""), "sys", "user")
    assert "empty response" in r.stop_reason


# --------------------------------------------------------------- novelty measure


def test_novelty_is_zero_for_a_pure_repeat() -> None:
    seen = {"funding", "basis", "carry"}
    assert novelty("funding basis carry", seen) == 0.0


def test_novelty_is_one_for_wholly_new_content() -> None:
    assert novelty("liquidation collateral validator", {"funding"}) == 1.0


def test_short_late_rounds_are_not_punished() -> None:
    """Late rounds are SHORT -- the easy material is gone. A strict bar would cut the ladder
    exactly where the rare items live, which is the opposite of the point."""
    seen = {"funding", "basis", "carry", "spread", "depth", "queue"}
    assert novelty("funding basis unlockschedule", seen) > MIN_NOVELTY


# --------------------------------------------------------------- ladder design


@pytest.mark.parametrize("ladder", [PUSH_LADDER, GENERATION_LADDER])
def test_ladders_are_ten_rungs_and_never_repeat_themselves(ladder) -> None:
    """Asking 'anything else?' ten times gets 'no' by round two -- a repeated question reads as
    a signal the model has finished. Each rung must attack a different suppression mechanism."""
    assert len(ladder) >= 10
    assert len(set(ladder)) == len(ladder)
    for rung in ladder:
        assert len(rung) > 80, "a one-line nudge does not move a model off its first answer"


def test_generation_ladder_re_asserts_the_output_contract() -> None:
    """A pushed model drifts toward prose, and a hypothesis without a mechanism, a test and a
    kill condition is not a hypothesis."""
    fmt = sum(1 for r in GENERATION_LADDER if "format" in r.lower() or "MECHANISM" in r)
    assert fmt >= 8, f"only {fmt}/{len(GENERATION_LADDER)} rungs restate the contract"


def test_analysis_ladder_forbids_silent_cost_self_censorship() -> None:
    """A named failure pattern here: ideas needing money get pre-rejected and never reach the
    principal. Spend is his decision, never one the model makes quietly."""
    assert any("cost is a decision" in r.lower() for r in PUSH_LADDER)


def test_both_ladders_offer_an_explicit_surrender_phrase() -> None:
    """Without a way to say 'done', the model pads -- and padding is what we are paying to avoid."""
    for ladder in (PUSH_LADDER, GENERATION_LADDER):
        assert any("NOTHING FURTHER" in r for r in ladder)


# --------------------------------------------------------------- policy enforcement


def test_every_idea_organ_pushes_and_asks_every_seat() -> None:
    """Standing policy, checked structurally -- a convention living only in a commit message
    decays the first time someone adds an organ."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import scripts.max_audit as M
    d: list = []
    M.check_llm_exhaustion(d)
    assert d == [], [k for k, _ in d]


# --------------------------------------------------------------- the compounding filter


def test_every_rung_carries_the_compounding_filter() -> None:
    """THE LADDER'S OWN RISK, CLOSED. Ten rounds of "what breaks / what should you stop" is a
    machine for breeding timidity if left unguarded -- each item reasonable, the sum a desk that
    compounds slower, arriving dressed as thoroughness."""
    from libs.llm.push import COMPOUNDING_FILTER
    for ladder in (PUSH_LADDER, GENERATION_LADDER):
        for rung in ladder:
            assert COMPOUNDING_FILTER in rung


def test_the_filter_names_exactly_three_compounding_paths() -> None:
    """Growth now, capability to grow later, or ruin prevention. Nothing else qualifies."""
    from libs.llm.push import COMPOUNDING_FILTER as f
    assert "raises E[log(wealth)] NOW" in f
    assert "CAPABILITY to raise" in f
    assert "prevents a RUIN event" in f
    assert "DELETE IT" in f, "an item with no compounding path must not even be mentioned"


def test_the_filter_scores_timidity_as_a_defect() -> None:
    from libs.llm.push import COMPOUNDING_FILTER as f
    assert "TIMIDITY" in f
    assert "round down out of caution" in f
    assert "feel careful" in f, "a control whose purpose is reassurance is not a control"


def test_ruin_prevention_is_a_growth_argument_not_an_exemption() -> None:
    """The subtle one. Path (3) is not a loophole for caution -- ruin ends all future
    compounding, so preventing it IS the log objective, which is exactly why maximum aggression
    on proven edge and zero on unproven are the same rule."""
    from libs.llm.push import COMPOUNDING_FILTER as f
    assert "ruin ends all future compounding" in f
    assert "survival rails" in f and "never loosened" in f


def test_the_inversion_rung_cannot_become_a_rail_removal_request() -> None:
    """'What should we stop doing' must not be answerable with 'stop having a kill switch'."""
    rung = next(r for r in PUSH_LADDER if "Invert it" in r)
    assert "Do NOT propose removing a survival rail" in rung
    assert "freed" in rung and "GROWTH" in rung


def test_the_decay_rung_asks_how_to_harvest_not_whether_to_skip() -> None:
    """'This edge will decay' is an argument for speed, never for abstention."""
    rung = next(r for r in PUSH_LADDER if "Second-order" in r)
    assert "harvest it BEFORE it does, never to skip it" in rung
    assert "aggressive version" in rung


def test_the_six_standing_questions_are_a_rung() -> None:
    """The principal's permanent exploration set. Every seat answers all six, every push, with a
    number or a named artifact -- not prose."""
    rung = next((r for r in PUSH_LADDER if "BOTTLENECK" in r), None)
    assert rung is not None
    for q in ("COMPOUNDS", "INSTITUTIONAL", "SELF-IMPROVING", "OPPORTUNITY COST",
              "VALIDATION INTEGRITY"):
        assert q in rung, q
    assert "never more survivors waved through" in rung, (
        "throughput must never be bought by lowering the bar -- that is negative discovery")


def test_the_round_cap_never_truncates_the_ladder_SILENTLY() -> None:
    """THE INVARIANT CHANGED 2026-08-11 AND THIS TEST CHANGED WITH IT, deliberately.

    It used to assert `len(PUSH_LADDER) <= MAX_ROUNDS` -- the cap may never be shorter than the
    ladder. The principal capped rounds at 4 on measured cost (eleven rounds is ~$412/month of
    re-sent context against a $20 cap), so the old invariant is now false BY DECISION, and
    asserting it would just be a red test nobody could fix without overspending.

    What survives is the part that actually protected the desk: a cap may truncate, but it may
    never truncate SILENTLY -- the synthesis rung, which ranks everything produced across all
    rounds, must still be asked. A run that generates material and never orders it has paid for
    the expensive half and skipped the cheap half that makes it usable.
    """
    for ladder in (PUSH_LADDER, GENERATION_LADDER):
        rungs = _rungs_for(ladder, MAX_ROUNDS)
        assert len(rungs) == min(MAX_ROUNDS, len(ladder))
        assert rungs[-1] == ladder[-1], "the capped ladder dropped its synthesis rung"


def test_the_filter_forbids_proposing_a_control_that_only_says_no() -> None:
    """THE LADDER'S SECOND RISK, and the one that actually happened. A model asked "what else?"
    ten times reaches for another gate, another approval, another audit -- a new control is the
    easiest defensible recommendation there is and nobody is ever blamed for one. Each is
    individually reasonable and the aggregate re-optimises the desk from "find as many good
    things as possible while preventing catastrophe" to "never deploy something bad". This is
    the highest-volume proposal source on the desk, so it is where that gets caught."""
    from libs.llm.push import COMPOUNDING_FILTER as f
    assert "GOVERNANCE IS A WEAPON, NOT A POLICE FORCE" in f
    assert "name the THROUGHPUT IT MULTIPLIES" in f
    assert "a tax paid to feel careful" in f
    assert "same defect as under-sizing a proven edge" in f


def test_the_filter_scores_timidity_on_every_axis_not_just_capital() -> None:
    """The old anti-timidity language policed capital only. Research, engineering, discovery and
    conversion timidity went unpoliced, which is the asymmetry that let governance win."""
    from libs.llm.push import COMPOUNDING_FILTER as f
    assert "EVERY axis, not just capital" in f
    assert "same defect as idle cash" in f
    assert "ALWAYS to expand conversion, NEVER to throttle discovery" in f


# ------------------------------------------------------------------ the 4-round cost cap
# PRINCIPAL DIRECTIVE 2026-08-11: rounds capped at 4, a COST decision. The hazard of lowering a
# ladder cap is silent truncation -- this file's own module warned about exactly that -- so these
# pin the two properties that make a short ladder honest rather than broken.

def test_cap_is_four_rounds() -> None:
    from libs.llm.push import MAX_ROUNDS
    assert MAX_ROUNDS == 4


def test_capped_run_still_ends_on_the_synthesis_rung() -> None:
    """A capped run must not stop mid-ladder having generated material and never ranked it."""
    from libs.llm.push import PUSH_LADDER, _rungs_for
    rungs = _rungs_for(PUSH_LADDER, 4)
    assert len(rungs) == 4
    assert rungs[-1] == PUSH_LADDER[-1], "the final cross-round ranking was truncated away"
    assert rungs[:3] == PUSH_LADDER[:3]


def test_uncapped_selection_is_identity() -> None:
    from libs.llm.push import PUSH_LADDER, _rungs_for
    assert _rungs_for(PUSH_LADDER, len(PUSH_LADDER)) == PUSH_LADDER
    assert _rungs_for(PUSH_LADDER, 99) == PUSH_LADDER


def test_zero_cap_asks_nothing_and_does_not_crash() -> None:
    from libs.llm.push import PUSH_LADDER, _rungs_for
    assert _rungs_for(PUSH_LADDER, 0) == ()


def test_cap_of_one_is_the_synthesis_alone() -> None:
    """At n=1 the head is empty, so the single rung must be the ranking -- not rung 1."""
    from libs.llm.push import PUSH_LADDER, _rungs_for
    assert _rungs_for(PUSH_LADDER, 1) == (PUSH_LADDER[-1],)
