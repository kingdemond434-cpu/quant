"""THE EXTERNAL SEAT IS FOR THE DIFFERENCE, NOT THE OVERLAP.

An external LLM given "do some quant research" produces a second, costlier copy of research the
desk already did. The valuable output of a second intelligence is what the first one MISSED, so
the seats that are shown the desk's map carry a residual mandate -- and the one seat that is
deliberately kept blind must never receive it.
"""

from __future__ import annotations

import importlib

import pytest

from libs.doctrine.constitution import (
    OBJECTIVE_PREAMBLE,
    RESIDUAL_MANDATE,
    RESIDUAL_PROTOCOL,
)

#: (module, attribute holding the system prompt). Every seat here is SHOWN the desk's dossier.
_SEATED: tuple[tuple[str, str], ...] = (
    ("scripts.breadth_expander", "SYSTEM"),
    ("scripts.meta_architect", "CHARTER"),
    ("scripts.hypothesis_generator", "SYSTEM"),
    ("scripts.collector_author", "SYSTEM"),
    ("scripts.llm_code_auditor", "SYSTEM"),
)


def _norm(s: str) -> str:
    """Line wrapping is a formatting choice; the assertions are about CONTENT.

    Three earlier prompt tests broke purely because a line was re-wrapped, which trains the next
    session to weaken the assertion rather than fix the prompt.
    """
    return " ".join(s.split())


@pytest.mark.parametrize(("mod", "attr"), _SEATED)
def test_EVERY_SEAT_SHOWN_THE_MAP_CARRIES_THE_RESIDUAL_MANDATE(mod: str, attr: str) -> None:
    text = _norm(getattr(importlib.import_module(mod), attr))
    assert _norm(RESIDUAL_MANDATE) in text, f"{mod}.{attr} duplicates the desk, not extends it"


def test_THE_BLIND_RESEARCHER_MUST_NOT_RECEIVE_IT() -> None:
    """Its entire value is deriving the space with the desk's conclusions withheld.

    Handing it the map would destroy the only control the desk has against its own anchoring --
    and it would do so invisibly, because the output would still look like independent research.
    """
    mod = importlib.import_module("scripts.llm_blind_researcher")
    prompts = [v for v in vars(mod).values() if isinstance(v, str) and len(v) > 200]
    assert prompts, "no prompt found -- the fence would pass vacuously"
    assert not any("RESIDUAL MANDATE" in p for p in prompts)


def test_THE_MANDATE_IS_NOT_INSIDE_THE_LENGTH_BOUNDED_PREAMBLE() -> None:
    """The preamble's own test says the answer to outgrowing its bound is to CUT, never to raise
    the number again -- and the preamble binds every organ, while this binds only seated ones."""
    assert "RESIDUAL MANDATE" not in OBJECTIVE_PREAMBLE


def test_NO_QUOTA_IS_STATED_AND_THAT_IS_LOAD_BEARING() -> None:
    """A forced count is met by lowering what counts as a difference."""
    m = _norm(RESIDUAL_MANDATE)
    assert "NO QUOTA" in m
    assert "never item count" in m


def test_A_DESK_REJECTION_IS_INFORMATION_NOT_A_VETO() -> None:
    """Cold on claims, open on hypotheses -- the two are different postures, and collapsing them
    breaks the loop in one of two directions."""
    m = _norm(RESIDUAL_MANDATE)
    assert "NEVER A VETO" in m
    assert "never tested -> that is a research opportunity" in m
    assert "FALSIFICATION OPPORTUNITY and ranks ABOVE a confirmatory one" in m


def test_ARTIFICIAL_CONTRARIANISM_IS_REFUSED_EXPLICITLY() -> None:
    """'Disagree with the desk' is as useless as duplication and costs the same compute."""
    assert "Do not manufacture disagreement" in _norm(RESIDUAL_MANDATE)


def test_EVERY_ITEM_OWES_A_CONVERSION_PATH() -> None:
    m = _norm(RESIDUAL_MANDATE)
    assert "source -> claim -> mechanism -> feature -> hypothesis" in m
    assert "no path to an experiment is an opinion" in m


# --- THE PROTOCOL: HOW a seat searches, as opposed to WHAT it searches for -------------------

@pytest.mark.parametrize(("mod", "attr"), (*_SEATED, ("scripts.llm_blind_researcher", "SYSTEM")))
def test_EVERY_SEAT_CARRIES_THE_PROTOCOL_INCLUDING_THE_BLIND_ONE(mod: str, attr: str) -> None:
    """The blind researcher gets this one and not the mandate, and the split is the point.

    Its independence is about CONTEXT -- the desk's conclusions are withheld so it can derive the
    space unanchored. It is not about EFFORT. Letting the one seat designed to find what nobody
    else can find stop at its first draft would waste the only genuinely uncorrelated search the
    desk owns.
    """
    text = _norm(getattr(importlib.import_module(mod), attr))
    assert _norm(RESIDUAL_PROTOCOL) in text


def test_THE_STOP_CONDITION_IS_MARGINAL_INFORMATION_NOT_A_ROUND_COUNT() -> None:
    """A fixed 'ask ten times' is too few for a rich problem and too many for a thin one -- and on
    the thin one it is actively harmful, because inventing an item becomes the cheapest way to
    comply with the instruction."""
    m = _norm(RESIDUAL_PROTOCOL)
    assert "MARGINAL INFORMATION, NEVER A ROUND COUNT" in m
    assert "too few for a rich problem and too many for a thin one" in m


def test_THE_SEAT_MAY_STOP_EARLY_AND_SAY_SO() -> None:
    """'I found no further material improvement' is a RESULT. A seat that cannot say it will never
    say anything else either -- it will pad instead."""
    m = _norm(RESIDUAL_PROTOCOL)
    assert "PERMITTED TO STOP EARLY" in m
    assert "Never manufacture an item to continue a pass" in m


def test_PASS_COUNT_IS_NEVER_EVIDENCE_OF_COVERAGE() -> None:
    m = _norm(RESIDUAL_PROTOCOL)
    assert "never treat the number of passes as evidence" in m
    assert "thirty passes can still miss something" in m


def test_THE_PASSES_SEARCH_DIFFERENT_FRONTIERS_NOT_THE_SAME_ONE_TWICE() -> None:
    """Asking 'what else?' ten times samples ONE direction ten times."""
    m = _norm(RESIDUAL_PROTOCOL)
    for frontier in ("DATA", "MECHANISM", "FEATURE", "HYPOTHESIS", "CROSS-DOMAIN", "EXECUTION",
                     "PORTFOLIO", "REGIME", "ADVERSARIAL", "UNKNOWN"):
        assert frontier in m, f"the {frontier} frontier is gone"


def test_RECONSIDERATION_IS_NOT_A_REPEAT() -> None:
    """The second pass takes the first as INPUT and hunts what it missed -- otherwise the loop is
    a single pass wearing a loop, and a later discovery never invalidates an earlier dismissal."""
    m = _norm(RESIDUAL_PROTOCOL)
    assert "THEN RECONSIDER, WHICH IS NOT A REPEAT" in m
    assert "Do not restate a point unless you materially improve it" in m


def test_MORE_TOKENS_ARE_NOT_MORE_ALPHA() -> None:
    assert "MORE TOKENS ARE NOT MORE ALPHA" in _norm(RESIDUAL_PROTOCOL)


def test_THE_PROTOCOL_IS_SEPARATE_FROM_THE_MANDATE() -> None:
    """They answer different questions and are wanted in different combinations -- fusing them
    would force the blind researcher to take the map in order to take the method."""
    assert "RESIDUAL MANDATE" not in RESIDUAL_PROTOCOL
    assert "RECURSIVE RESIDUAL-GAP" not in RESIDUAL_MANDATE
    assert "RESIDUAL" not in OBJECTIVE_PREAMBLE
