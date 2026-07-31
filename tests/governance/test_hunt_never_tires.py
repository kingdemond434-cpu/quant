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
DOCTRINE = _flat("ops/principal_doctrine.txt")


def test_hunt_never_tires_in_constitution():
    assert "L1.25a THE HUNT NEVER TIRES" in CONSTITUTION
    # The two-and-only-two readings, and the ordering fix for the proving instance.
    assert "the diagnostic runs while the hunt continues, never instead of it" in CONSTITUTION
    assert "Survivors are hunted every single day" in CONSTITUTION


def test_hunt_never_tires_reaches_every_organ():
    assert "L1.25a" in DOCTRINE
    assert "THE HUNT NEVER TIRES" in DOCTRINE
    assert "NEITHER reading ever reduces cadence, generation volume, or seat count" in DOCTRINE


def test_acquisition_untouchable_in_both_surfaces():
    # L1.28b(f): conversion pressure never touches raw information quantity.
    assert "RAW INFORMATION ACQUISITION IS UNTOUCHABLE" in CONSTITUTION
    assert "CONVERSION PRESSURE NEVER TOUCHES RAW INFORMATION QUANTITY" in DOCTRINE
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
    assert "L1.28c" in DOCTRINE and "CADENCE IS AGGRESSION" in DOCTRINE
    src = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.28c"' in src


def test_cadence_law_names_all_three_ceiling_types():
    for kind in ("INFORMATION-ARRIVAL", "RESOURCE", "DATA-ARRIVAL"):
        assert kind in CONSTITUTION
        assert kind in DOCTRINE


# --- the ceiling-pusher pushes the whole growth identity, not one term of it -------------------

def test_all_four_growth_terms_are_enumerated_and_ranked():
    """It targeted the hit rate alone -- one term of four, and not the steepest.

    Compounding enters through exactly four inputs: independent bets, hit rate, winner shape and
    size. An organ hunting one while three sit unexamined is polishing a wall, not pushing a
    ceiling.
    """
    from pathlib import Path

    from scripts.run_discretionary_max import _GROWTH_TERMS, growth_levers
    g = growth_levers(Path("."))
    assert {t["term"] for t in g["terms"]} == set(_GROWTH_TERMS)
    assert "g_year" in g["identity"]
    # an ASSUMED input outranks a measured one: it cannot be improved on purpose
    assert g["binding_term"] == "WINNER-SHAPE"


def test_size_is_recorded_as_the_anti_lever_never_as_headroom():
    """The one dial where 'uncap it' and 'achieve it' point in opposite directions.

    Growth rises with size only to full Kelly and falls after; the odds of a doubling year peak
    earlier still. This must stay written down, because raising it is the change that always
    LOOKS like aggression and is arithmetically self-defeating.
    """
    from pathlib import Path

    from scripts.run_discretionary_max import growth_levers
    f = next(t for t in growth_levers(Path("."))["terms"] if t["symbol"] == "f")
    assert f["state"] == "HELD-BY-ARITHMETIC"
    assert "NEGATIVE" in f["gradient"]
    assert f["action"].startswith("HOLD")
    assert "timidity" in f["action"]          # the reason, so it is not re-litigated as caution
