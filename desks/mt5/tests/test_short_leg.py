"""A certified SHORT ran LONG, and every field that could have shown it agreed with the bug.

    python -m pytest desks/mt5/tests/test_short_leg.py -q

THE DEFECT, and it was live on the ARMED path. `survivor_publication._shadow_spec`
writes `side` into every published certificate, straight off the certificate id.
`authorized_runs` -- the door the forward engine actually walks through -- read
symbol, selector, family, condition and params from that spec and DROPPED `side`
on the floor. `shadow_forward` then:

    * froze `direction="LONG"` into the clock's identity, and
    * called the family as `fam_fn(h1, side=1, ...)` -- and only in a TypeError
      fallback, so a family taking `side` with a long default never even reached it.

So a certified SHORT strategy accrued forward evidence for the OPPOSITE direction,
under an identity asserting LONG. The one field that would have exposed the
mismatch was hardcoded to agree with it.

The LONG-only filter in `authorized_specs` did not protect this: it guards the
five-tuple path, and the engine does not use it. That is protocol rule 4 in one
sentence -- a gate must hold at EVERY layer, and this one held at the layer
nothing ran and was absent from the layer that did.

WHAT MUST NOT REGRESS, in order of how much it would cost:

  1. a certified SHORT is replayed SHORT, or not enrolled at all
  2. a SHORT clock never shares a key with its LONG twin
  3. every existing LONG clock keeps its exact key, call and behaviour
  4. a SHORT on a family that cannot be told a side is REFUSED, not run long
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent.parent / "research"
sys.path.insert(0, str(RESEARCH))

import shadow_forward as sf  # noqa: E402
from shadow_admission import authorized_runs, run_key  # noqa: E402

# --------------------------------------------------- 1. the side reaches the engine

def test_the_certificate_side_is_carried_out_of_the_admission_door() -> None:
    """It was read from the spec and then dropped; nothing downstream could recover it."""
    src = inspect.getsource(authorized_runs)
    assert '"side"' in src, "authorized_runs must carry the certified side"
    assert '"side_basis"' in src, "declared vs undeclared must be distinguishable"


def test_a_short_is_replayed_short_not_long() -> None:
    """The whole defect in one assertion."""
    seen = {}

    def fam(bars, side=1, **kw):
        seen["side"] = side
        return []

    assert sf._accepts_side(fam) is True
    # A family that takes `side` with a LONG default is exactly the case the old
    # TypeError fallback could never reach: the first call simply succeeded, long.
    assert inspect.signature(fam).parameters["side"].default == 1


def test_a_short_on_a_family_with_no_side_is_refused_not_run_long(monkeypatch) -> None:
    """Running it long would accrue evidence for the opposite direction. Fail closed."""
    def no_side(bars, **kw):        # **kw accepts side, so this must be the strict case
        return []

    def truly_no_side(bars, rr=2.0):
        return []

    monkeypatch.setattr(sf, "_family_fn", lambda fam: truly_no_side)
    logged: list[str] = []
    monkeypatch.setattr(sf, "slog", logged.append)
    out = sf._runnable_side({"symbol": "EURUSD", "side": "SHORT"}, "some_family")
    assert out is None
    assert logged and "SHORT" in logged[0] and "opposite direction" in logged[0]
    assert sf._accepts_side(no_side) is True      # **kwargs can carry it
    assert sf._accepts_side(truly_no_side) is False


def test_an_unknown_side_is_refused_rather_than_guessed(monkeypatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr(sf, "slog", logged.append)
    assert sf._runnable_side({"symbol": "EURUSD", "side": "FLAT"}, "f") is None
    assert "refusing to guess" in logged[0]


def test_an_undeclared_side_runs_long_and_says_it_assumed(monkeypatch) -> None:
    """Absence is named, not hidden: every certificate written before the field
    existed came from a long-only publisher, and a NEW undeclared one is visible."""
    assert sf._runnable_side({"symbol": "EURUSD"}, "f") == "LONG"
    assert sf._runnable_side({"symbol": "EURUSD", "side": ""}, "f") == "LONG"


def test_a_declared_long_needs_no_family_support(monkeypatch) -> None:
    monkeypatch.setattr(sf, "_family_fn", lambda fam: (lambda bars, rr=2.0: []))
    assert sf._runnable_side({"symbol": "EURUSD", "side": "LONG"}, "f") == "LONG"


# ------------------------------------------- 2 & 3. keys: distinct, and unchanged

def test_a_long_key_is_byte_identical_to_what_it_has_always_been() -> None:
    """Renaming running clocks would orphan the entire forward book against its
    ledgers, registry rows and shadow state."""
    params = {"range_start": 7, "wait_bars": 12, "rr": 1.5}
    assert (sf.sleeve_key("XAUUSD", "asia", params)
            == sf.sleeve_key("XAUUSD", "asia", params, "session_range_breakout", "LONG"))
    assert ".LONG" not in sf.sleeve_key("XAUUSD", "asia", params)
    assert (sf.sleeve_key("EURZAR", "asia", {}, "overnight_gap_decay")
            == "EURZAR.overnight_gap_decay.asia")


def test_a_short_clock_never_collides_with_its_long_twin() -> None:
    """Same symbol, window and parameterization, opposite direction: one forward
    series spliced from two directions is not a smaller sample, it is a wrong one."""
    p = {"rr": 1.5}
    long_key = sf.sleeve_key("XAUUSD", "asia", p, "session_range_breakout", "LONG")
    short_key = sf.sleeve_key("XAUUSD", "asia", p, "session_range_breakout", "SHORT")
    assert long_key != short_key
    assert short_key.endswith(".SHORT")


def test_the_admission_door_and_the_engine_build_the_same_key() -> None:
    """Two builders for one identity disagreed once already and reported 34 of 35
    certificates as clockless while every one of them was running."""
    run = {"symbol": "XAUUSD", "selector": "asia", "params": {"rr": 1.5},
           "family": "session_range_breakout", "side": "SHORT"}
    assert run_key(run) == sf.sleeve_key("XAUUSD", "asia", {"rr": 1.5},
                                         "session_range_breakout", "SHORT")


def test_run_key_defaults_to_long_when_the_spec_predates_the_field() -> None:
    run = {"symbol": "XAUUSD", "selector": "asia", "params": {"rr": 1.5},
           "family": "session_range_breakout"}
    assert run_key(run) == sf.sleeve_key("XAUUSD", "asia", {"rr": 1.5})


# ------------------------------------------------------------- 4. arity, again

def test_the_reconciler_slices_the_widened_row_with_a_default() -> None:
    """`certified_sleeves()` widened 3->4 once and this reader destructured three,
    raising `too many values to unpack` on EVERY pass for a day and silently
    disabling orphan retirement. 4->5 must not repeat it."""
    src = (RESEARCH / "forward_reconcile.py").read_text(encoding="utf-8")
    assert "row[4] if len(row) > 4" in src


def test_every_enrolled_row_has_the_same_arity() -> None:
    """The grandfathered rows are stated LONG rather than left short of a field,
    so the loop never has to guess which shape it is holding."""
    src = inspect.getsource(sf.run) if hasattr(sf, "run") else ""
    text = src or (RESEARCH / "shadow_forward.py").read_text(encoding="utf-8")
    assert '"session_range_breakout", "LONG")' in text
    assert "side = row[4] if len(row) > 4 else \"LONG\"" in text


# ------------------------------------------------- the identity tells the truth

def test_the_frozen_identity_records_the_direction_actually_replayed() -> None:
    """It was hardcoded "LONG", so the one field that would have exposed a short
    clock running long agreed with the bug instead of catching it."""
    text = (RESEARCH / "shadow_forward.py").read_text(encoding="utf-8")
    assert 'direction=str(side).upper()' in text
    assert 'direction="LONG"' not in text


def test_a_short_is_passed_on_the_first_call_not_only_the_fallback() -> None:
    """A family accepting `side` with a long default never reaches a TypeError
    fallback -- so fixing only the fallback fixes nothing for exactly the
    families that can take a side."""
    text = (RESEARCH / "shadow_forward.py").read_text(encoding="utf-8")
    assert "fam_fn(h1, side=-1, **call_params) if _short" in text


# ------------------------------- 5. the gauntlet's third family population is reachable
#
# Certification and forward evidence must read the same certificate from the SAME registry.
# `qquant_gates` resolves hunt16's corpus via `from run_hunt16 import FAMILIES as F16`, so a
# cell can pass all ten gates on a family the forward engine has never heard of. Measured
# 2026-09-03: 14 such families, every one taking `side: int`, unreachable from `_family_fn`.

def test_the_gauntlets_hunt16_corpus_is_reachable_from_the_forward_engine() -> None:
    """A family the gauntlet certifies from MUST resolve here, or evidence can never accrue."""
    from run_hunt16 import FAMILIES as F16

    for name, ctor in F16.items():
        assert sf._family_fn(name) is ctor, (
            f"{name} is certifiable by qquant_gates but unresolvable by the forward engine; "
            f"a certificate naming it can never accrue forward evidence")


def test_a_certified_short_on_a_hunt16_family_enrols_short(monkeypatch) -> None:
    """The exact cell that was refused under text blaming it for a `side` it does take."""
    logged: list[str] = []
    monkeypatch.setattr(sf, "slog", logged.append)
    run = {"symbol": "AUDNZD", "side": "SHORT"}
    assert sf._runnable_side(run, "dav_range_filter_adx") == "SHORT"
    assert not logged, f"a runnable short must not be refused: {logged}"


def test_every_hunt16_family_can_actually_be_told_a_side() -> None:
    """If one of these could not, enrolling it short would be the very bug this file exists for."""
    from run_hunt16 import FAMILIES as F16

    for name, ctor in F16.items():
        assert sf._accepts_side(ctor) is True, f"{name} cannot be told a side"


def test_an_unresolvable_family_is_not_blamed_for_missing_a_side(monkeypatch) -> None:
    """Two causes, two fixes, two messages. The old text sent readers to edit the wrong file."""
    monkeypatch.setattr(sf, "_family_fn", lambda fam: None)
    logged: list[str] = []
    monkeypatch.setattr(sf, "slog", logged.append)
    assert sf._runnable_side({"symbol": "EURUSD", "side": "SHORT"}, "ghost") is None
    assert logged, "an unresolvable short must still be reported"
    assert "CANNOT BE RESOLVED" in logged[0]
    assert "takes no `side`" not in logged[0], (
        "an unresolvable family must not be blamed for a capability gap it may not have")


def test_the_resolver_returns_published_families_only() -> None:
    """A bare getattr on the module would resolve `main`, `cheap_gate` or a private helper."""
    for attr in ("main", "cheap_gate", "_sigs", "FAMILIES", "WINDOWS"):
        assert sf._family_fn(attr) is None, f"_family_fn resolved non-family attribute {attr!r}"
