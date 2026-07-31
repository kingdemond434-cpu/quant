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
