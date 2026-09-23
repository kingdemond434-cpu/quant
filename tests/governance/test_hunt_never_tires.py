"""L1.25a (the hunt never tires) + L1.28b(f) (acquisition untouchable) -- presence and wiring.

Both laws are behavioural orders to organs, so their mechanical fence is indirect: the
freshness/productivity wires catch any organ going quiet regardless of reason. What CAN be
asserted directly -- and lapses the moment someone edits it away -- is that the law text reaches
every surface that steers behaviour (constitution, doctrine-at-spawn, matrix mapping, and the
conversion fence's own boundary statement).
"""
from __future__ import annotations

from pathlib import Path


def _flat(path: str) -> str:
    # Markdown wraps at 100 cols, so pinned phrases can span newlines and bold markers --
    # normalise whitespace and strip emphasis before asserting content.
    return " ".join(Path(path).read_text("utf-8").replace("**", "").split())


CONSTITUTION = _flat("docs/CONSTITUTION.md")

#: THE ORGAN-FACING SURFACE MOVED, AND THESE FENCES FOLLOWED IT (2026-09-05).
#: These assertions used to read `ops/principal_doctrine.txt`. That file was COMPACTED by principal
#: order on 2026-08-25 and says so in its own second paragraph -- "the sprawling duty text that used
#: to live here is compacted there", meaning docs/LAWS.md and docs/RESEARCH.md, "with zero law
#: regression", with docs/MANDATE_COVERAGE.md mapping every disposition. The laws below did not stop
#: reaching organs; their address changed, and the doctrine file now routes to LAWS.md by name.
#: A fence still pinning the old address goes red on a deliberate consolidation, and the way a
#: red-but-wrong fence gets satisfied is by pasting the text back into the file it was deliberately
#: moved out of. So the ORGAN-FACING assertions read LAWS.md (the compacted statement every seat is
#: handed) while the UNABRIDGED phrasing stays pinned in CONSTITUTION.md, which is where it lives.
#: `test_the_doctrine_still_routes_organs_to_the_laws` below buys that back: if the doctrine ever
#: stops naming LAWS.md, the compaction has broken the law's only path to a reader and this fails.
LAWS = _flat("docs/LAWS.md")
DOCTRINE = _flat("ops/principal_doctrine.txt")


def test_the_doctrine_still_routes_organs_to_the_laws():
    """The buy-back for reading LAWS.md instead of the doctrine. The doctrine is still the order
    channel every organ opens; it now delegates, and this holds it to the delegation."""
    assert "docs/LAWS.md" in DOCTRINE, (
        "the doctrine no longer routes organs to docs/LAWS.md, so the 2026-08-25 compaction has "
        "cut every law it moved there off from the organs that must read it")


def test_hunt_never_tires_in_constitution():
    assert "L1.25a THE HUNT NEVER TIRES" in CONSTITUTION
    # The two-and-only-two readings, and the ordering fix for the proving instance.
    assert "the diagnostic runs while the hunt continues, never instead of it" in CONSTITUTION
    assert "Survivors are hunted every single day" in CONSTITUTION


def test_hunt_never_tires_reaches_every_organ():
    assert "L1.25a" in LAWS
    assert "the hunt never tires" in LAWS
    assert "null streaks throttle nothing, anywhere" in LAWS


def test_acquisition_untouchable_in_both_surfaces():
    # L1.28b(f): conversion pressure never touches raw information quantity.
    assert "RAW INFORMATION ACQUISITION IS UNTOUCHABLE" in CONSTITUTION
    assert "L1.28b" in LAWS and "conversion parity" in LAWS
    assert "Acquisition is never cut to meet extraction" in CONSTITUTION


def test_conversion_fence_states_the_boundary():
    src = Path("scripts/check_conversion.py").read_text("utf-8")
    assert "L1.28b(f)" in src
    assert "never cut to meet extraction" in src


def test_l125a_mapped_to_real_fences():
    src = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.25a"' in src
    # The wires that catch a quiet organ regardless of its stated reason.
    for fence in ("check_organs", "check_stub_deaths", "check_idle_capability"):
        assert fence in src


# --- L1.28a: the brain seat, the ceiling every LLM cadence competes for -----------------------

def test_brain_seat_ceiling_exists_and_is_honest():
    """Unmeasured contention counts as ZERO, and a measured deferral must name the twin."""
    from scripts.check_utilisation import _brain_seat, collect
    assert any(c.name == "brain_seat_throughput" for c in collect())
    c = _brain_seat()
    if not c.measured:
        assert c.utilisation == 0.0          # never reads healthy for lack of a log
        assert c.binding_constraint          # and must say why
    else:
        assert c.limit >= c.used
        if c.used < c.limit:
            assert "SECOND SEAT" in c.binding_constraint


# --- L1.28c: cadence is aggression ------------------------------------------------------------

def test_cadence_law_present_on_every_surface():
    assert "L1.28c CADENCE IS AGGRESSION" in CONSTITUTION
    assert "PHASE COUNTS AS CADENCE" in CONSTITUTION
    assert "L1.28c" in LAWS and "cadence is aggression" in LAWS
    src = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.28c"' in src


def test_cadence_law_names_all_three_ceiling_types():
    """The three named in full in the constitution, and the law reachable from every organ.

    The enumeration is the enforceable part: "every schedule hunts its own ceiling" is a slogan
    until the KINDS of ceiling are named, because an organ that cannot name which ceiling binds it
    will report the resource one (always visible) and never the information-arrival one.
    """
    for kind in ("INFORMATION-ARRIVAL", "RESOURCE", "DATA-ARRIVAL"):
        assert kind in CONSTITUTION
    assert "L1.28c" in LAWS and "every schedule hunts its own ceiling" in LAWS


# --- the ceiling-pusher pushes the whole growth identity, not one term of it -------------------
#
# TWO TESTS STOOD HERE AND THEIR SUBJECT IS GONE (2026-09-05). They read
# `scripts/run_discretionary_max.growth_levers`, and pinned two things: that all FOUR terms of the
# growth identity are enumerated and ranked (independent bets, hit rate, winner shape, size --
# an organ hunting one while three sit unexamined is polishing a wall, not pushing a ceiling), and
# that SIZE is recorded as HELD-BY-ARITHMETIC with a NEGATIVE gradient, because growth rises with
# size only to full Kelly and falls after, and the odds of a doubling year peak earlier still.
#
# That organ belonged to the retired crypto-exchange desk and was deleted with it under the MT5
# universe mandate (its cron row carries the retirement reason in ops/crontab.manifest). The tests
# go with it -- a wiring test for a deleted module measures nothing.
#
# THE KNOWLEDGE DID NOT GO WITH IT. Both statements are now written into
# `docs/GROWTH_GOVERNANCE.md`, the desk's binding risk mandate, under "The four terms of the growth
# identity"; the size result in particular is the reason `heat_policy.measured_ceiling` refuses to
# bound above the point where the measured growth curve turns over. Recorded there rather than
# re-fenced here, because the claim is a law about compounding, not a property of any one organ.
