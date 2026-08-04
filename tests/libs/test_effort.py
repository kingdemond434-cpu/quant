"""REASONING DEPTH IS MEASURED, NOT HARDCODED.

THE DEFECT THIS CLOSES. Every reasoning organ sent `"reasoning": {"effort": "high"}` as a literal
-- six copies, none derived from what the seat can actually do. It is the same shape as
`seats.resolve(SEATS, n=len(SEATS))`, found in six organs earlier this session: a constant quietly
bounding something meant to grow with the roster. And "high" is not a maximum; it is the middle
rung of a ladder whose top differs per model and per month, so a flagship the desk pays for was
being asked a shallower question than it can answer -- with the call succeeding either way, so the
cost never surfaced on its own.

THE HARD PART IS THE FALLBACK. A seat whose capabilities have never been recorded must degrade to
exactly the old behaviour, never to an invented parameter name: a made-up field is either rejected
by the provider or, far worse, silently ignored while the desk believes it bought deeper
reasoning. So the tests below care as much about what happens with NO data as with data.
"""

from __future__ import annotations

import json
from pathlib import Path

from libs.llm.effort import (
    DEFAULT_EFFORT,
    EFFORT_LADDER,
    coverage,
    effort_for,
    reasoning_payload,
)


def _caps(tmp_path, mapping: dict) -> Path:
    p = tmp_path / "caps.json"
    p.write_text(json.dumps({"models": mapping}), "utf-8")
    return p


def test_the_deepest_advertised_rung_is_requested(tmp_path) -> None:
    """The input context is the expensive half of the call and is already paid for, so a
    shallower rung buys a cheaper answer to a question the desk has already funded."""
    p = _caps(tmp_path, {"lab/model-x": ["temperature", "reasoning", "low", "medium", "high",
                                         "max"]})
    effort, why = effort_for("lab/model-x", path=p)
    assert effort == "max"
    assert "deepest rung" in why


def test_a_seat_advertising_only_a_middle_rung_gets_that_rung(tmp_path) -> None:
    p = _caps(tmp_path, {"lab/mid": ["low", "medium"]})
    assert effort_for("lab/mid", path=p)[0] == "medium"


def test_an_unrecorded_seat_degrades_to_the_old_literal_and_says_so(tmp_path) -> None:
    """THE FALLBACK THAT MATTERS. An unknown seat must not become a broken seat, and inventing a
    parameter name is worse than the old default -- it is either rejected or silently ignored."""
    effort, why = effort_for("lab/never-seen", path=tmp_path / "absent.json")
    assert effort == DEFAULT_EFFORT
    assert "no recorded capabilities" in why
    assert "may be buying a shallower answer than it is paying for" in why


def test_a_seat_with_parameters_but_no_reasoning_rung_keeps_the_default(tmp_path) -> None:
    """Declaring `temperature` and `top_p` says nothing about reasoning depth. Picking a rung
    anyway would be inventing a capability from unrelated evidence."""
    p = _caps(tmp_path, {"lab/plain": ["temperature", "top_p"]})
    effort, why = effort_for("lab/plain", path=p)
    assert effort == DEFAULT_EFFORT
    assert "rather than inventing one" in why


def test_a_corrupt_capabilities_file_never_breaks_a_call(tmp_path) -> None:
    """Telemetry must not be able to kill an organ. A malformed record is a gap, not a crash."""
    p = tmp_path / "bad.json"
    p.write_text("{not json", "utf-8")
    assert effort_for("lab/x", path=p)[0] == DEFAULT_EFFORT


def test_the_payload_is_a_dict_so_one_place_can_change_its_shape() -> None:
    """A bare string at six call sites means six edits when a provider changes the contract, and
    they will not all get made."""
    assert reasoning_payload("unknown/seat") == {"effort": DEFAULT_EFFORT}


def test_the_ladder_runs_weakest_to_deepest() -> None:
    assert EFFORT_LADDER[0] == "low" and EFFORT_LADDER[-1] == "max"
    assert DEFAULT_EFFORT in EFFORT_LADDER
    assert EFFORT_LADDER.index(DEFAULT_EFFORT) < len(EFFORT_LADDER) - 1, (
        "the fallback must NOT be the top rung -- if it were, this module would have nothing to "
        "add and the literal it replaced would have been correct all along")


def test_coverage_counts_the_fallback_seats_because_that_is_the_cost(tmp_path) -> None:
    """Every seat on the fallback may be a flagship being under-driven, and the call succeeds
    either way so nothing surfaces it."""
    p = _caps(tmp_path, {"lab/known": ["high", "max"]})
    c = coverage(["lab/known", "lab/unknown"], path=p)
    assert c["measured"] == 1 and c["fallback"] == 1
    assert c["fallback_seats"] == ["lab/unknown"]
    assert "under-driven" in c["note"]


def test_full_coverage_reports_cleanly(tmp_path) -> None:
    p = _caps(tmp_path, {"a": ["max"], "b": ["high"]})
    assert coverage(["a", "b"], path=p)["fallback"] == 0
    assert "measured from the live catalog" in coverage(["a", "b"], path=p)["note"]


# ------------------------------------------------------------------ the wiring


def test_no_organ_still_hardcodes_the_effort_literal() -> None:
    """Structural, because a convention living only in a commit message decays the first time
    somebody adds an organ -- this desk has watched that happen with seat caps and with the
    doctrine injection."""
    offenders = []
    for p in sorted(Path("scripts").glob("*.py")):
        src = p.read_text("utf-8", errors="ignore")
        if '"reasoning": {"effort": "high"}' in src:
            offenders.append(p.stem)
    assert offenders == [], (
        f"organ(s) still hardcode the reasoning literal: {offenders}. Use "
        "libs.llm.effort.reasoning_payload(model) so depth follows the roster.")


def test_the_roster_refresh_records_capability_so_it_can_be_measured() -> None:
    """It is the only place with a live catalog, so it is the only place that can turn seat
    capability from a guess into data."""
    src = Path("scripts/refresh_panel_roster.py").read_text("utf-8")
    assert "supported_parameters" in src
    assert "roster_capabilities.json" in src
