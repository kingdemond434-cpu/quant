"""The enrolment ceiling is a number now, and the door it describes stays shut.

    python -m pytest desks/mt5/tests/test_enrolment_ceiling.py -q

WHAT WAS INVISIBLE. `authorized_specs` dropped every certified SHORT row on a
bare `continue` in two of its three sources -- and its third source had no side
test at all, so the same certificate was admitted or discarded depending only on
which report carried it. Nothing counted the drops. A reader comparing
"certified" against "enrolled" saw a gap and had no way to tell a bug from a
queue from a wall.

WHY THE DOOR MUST STAY SHUT, which is the half that matters. The five-tuple spec
`(symbol, selector, state, family, is_universe)` carries no side at all, so a
SHORT certificate admitted here would hash to exactly the same tuple as its LONG
twin and a door comparing tuples could not tell them apart. The first test below
is the one that must never be "fixed" by deleting the filter.

AND THE CAUSE MUST BE DERIVED, NOT ASSERTED (2026-09-05). Until this date the
cause read "forward engine has no short leg: shadow_forward freezes
direction=LONG and calls fam_fn(side=1)". Both halves had since been fixed in the
engine -- `_runnable_side` resolves the certified side, `run_forward` calls
`fam_fn(h1, side=-1, ...)`, and the identity is stamped
`direction=str(side).upper()` -- so every blocked certificate on the health
report was attributed to a defect that no longer existed, sending a reader to fix
code that was already correct. The cause is now asked of `shadow_forward`'s own
resolver, so this file cannot drift from the engine again, and the two causes are
different jobs: a certificate the engine CAN replay is blocked only by the
missing spec field (`recoverable_by_threading_side`), while one it cannot needs
the family itself to learn a side.

The measurement is what makes either fix rankable against everything else
competing for the same hour.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))

from shadow_admission import (
    ENGINE_SIDES,
    authorized_specs,
    unreachable_certificates,
)

POLICY = None  # filled from the live attestation below


def _attestation() -> dict:
    from gate_policy import ATTESTATION
    return ATTESTATION if isinstance(ATTESTATION, dict) else {}


def _ten_pass() -> dict:
    """Ten stages that all_ten_pass accepts, built from the live gate list."""
    from gate_policy import GATES
    return {g: {"passed": True} for g in GATES}


def _write(base: Path, name: str, payload: dict) -> None:
    reports = base / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / name).write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def base(tmp_path: Path) -> Path:
    return tmp_path


def _qquant(rows: list[dict]) -> dict:
    return {"gate_policy": _attestation(), "verdicts": rows}


def _row(symbol: str, family: str, side: str, selector: str, condition: str = "NONE") -> dict:
    return {"id": f"{symbol} {family} {side} {selector} {condition}",
            "passed": True, "stages": _ten_pass()}


# ------------------------------------------------- the door stays shut, on purpose

def test_a_certified_short_is_still_refused_admission(base: Path) -> None:
    """NEVER delete this. The five-tuple spec carries no side, so a SHORT certificate
    admitted here hashes to exactly its LONG twin's tuple and no door comparing tuples
    could tell the two apart -- a LONG certificate would authorise a SHORT clock, or
    the reverse. The engine's short leg does not change that; the SPEC's shape does."""
    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "SHORT", "asia")]))
    assert authorized_specs(base) == set()


def test_a_certified_long_is_admitted_exactly_as_before(base: Path) -> None:
    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "LONG", "asia")]))
    specs = authorized_specs(base)
    assert len(specs) == 1
    symbol, selector, state, family, is_universe = next(iter(specs))
    assert (symbol, selector, state, is_universe) == ("EURUSD", "asia", None, False)
    assert family == "session_range_breakout"


def test_the_only_side_the_spec_tuple_can_express_is_declared():
    """It was a bare `continue` in two places and absent in a third. The name changed on
    2026-09-05 because the value was right and the claim behind it was not."""
    import shadow_admission as sa

    assert frozenset({"LONG"}) == ENGINE_SIDES == sa.SPEC_TUPLE_SIDES


# ----------------------------------------------------------- and it is now counted

def test_the_refused_short_is_counted_with_its_cause(base: Path) -> None:
    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "SHORT", "asia")]))
    out = unreachable_certificates(base)
    assert out["n"] == 1
    assert out["certificates"][0]["symbol"] == "EURUSD"
    assert out["certificates"][0]["side"] == "SHORT"
    assert out["certificates"][0]["cause"]
    assert sum(out["by_cause"].values()) == 1


def test_the_cause_is_asked_of_the_engine_not_asserted_by_this_file(base: Path) -> None:
    """The defect this replaces: a constant that described an engine that had been fixed.

    `session_range_breakout` genuinely takes no `side`, so the engine cannot replay it short and
    the row must say so. The point is that the answer comes from `shadow_forward`'s resolver --
    change the engine and this row changes with it, which is what the old constant could not do.
    """
    import shadow_admission as sa

    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "SHORT", "asia")]))
    out = unreachable_certificates(base)
    row = out["certificates"][0]
    assert row["engine_can_replay"] is False
    assert row["cause"] == sa.UNREACHABLE_ENGINE_CANNOT_REPLAY_SHORT
    assert out["recoverable_by_threading_side"] == 0


def test_a_short_the_engine_could_replay_is_priced_as_a_missing_spec_field(base: Path) -> None:
    """The number that makes the real fix rankable, and it must not read as a capability gap.

    A family whose constructor resolves AND takes a side is blocked by ONE thing: the five-tuple
    has nowhere to put the side. Recovering it needs no gate, no new evidence and no change to
    any family -- so it is counted separately from the certificates that need real engineering.
    """
    import shadow_admission as sa

    monkey_family = "pinned_side_family"
    original = sa.engine_can_replay
    sa.engine_can_replay = lambda family, side: (
        True if family == sa._exec_family(monkey_family) else original(family, side))
    try:
        _write(base, "QQUANT_GATES.json",
               _qquant([_row("EURUSD", monkey_family, "SHORT", "asia")]))
        out = unreachable_certificates(base)
        assert out["certificates"][0]["engine_can_replay"] is True
        assert out["certificates"][0]["cause"] == sa.UNREACHABLE_SIDE_NOT_IN_SPEC_TUPLE
        assert out["recoverable_by_threading_side"] == 1
    finally:
        sa.engine_can_replay = original


def test_the_stale_cause_is_no_longer_emitted() -> None:
    """It named a defect that no longer exists, so nothing may still write it on a row."""
    import shadow_admission as sa

    src = (Path(__file__).resolve().parent.parent
           / "research" / "shadow_admission.py").read_text(encoding="utf-8")
    assert src.count("UNREACHABLE_NO_SHORT_LEG") == 1, (
        "the pre-2026-09-05 cause may be kept for archive readers but must not be emitted")
    assert "freezes direction=LONG" in sa.UNREACHABLE_NO_SHORT_LEG


def test_an_admitted_long_is_not_counted_as_blocked(base: Path) -> None:
    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "LONG", "asia")]))
    assert unreachable_certificates(base)["n"] == 0


def test_a_row_that_failed_a_gate_is_not_a_ceiling(base: Path) -> None:
    """The ceiling counts what passed EVERYTHING and still cannot run. A row that
    failed a gate was refused on its merits and belongs to a different number."""
    row = _row("EURUSD", "breakout", "SHORT", "asia")
    row["stages"] = {k: {"passed": False} for k in row["stages"]}
    _write(base, "QQUANT_GATES.json", _qquant([row]))
    assert unreachable_certificates(base)["n"] == 0


def test_both_certificate_sources_are_counted(base: Path) -> None:
    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "SHORT", "asia")]))
    _write(base, "REAL_SURVIVORS.json", {"real_survivors": [
        {"REAL3": True, "sym": "GBPUSD", "win": "london", "fam": "breakout", "side": "SHORT",
         "qquant_gates": {"policy": _attestation(), "stages": _ten_pass()}}]})
    out = unreachable_certificates(base)
    assert out["n"] == 2
    assert {c["source"] for c in out["certificates"]} == {"QQUANT_GATES", "REAL_SURVIVORS"}


# ------------------------------------------------- unreadable is not zero (L1.28a)

def test_no_readable_report_is_unmeasured_and_not_none_blocked(base: Path) -> None:
    """"nothing is blocked" and "I could not read the certificates" are opposite
    facts, and this desk has shipped that confusion before."""
    out = unreachable_certificates(base)
    assert out["n"] is None
    assert out["sources_readable"] == {"QQUANT_GATES": False, "REAL_SURVIVORS": False}


def test_a_report_failing_the_policy_attestation_is_not_read(base: Path) -> None:
    _write(base, "QQUANT_GATES.json",
           {"gate_policy": {"not": "the attestation"},
            "verdicts": [_row("EURUSD", "breakout", "SHORT", "asia")]})
    out = unreachable_certificates(base)
    assert out["sources_readable"]["QQUANT_GATES"] is False
    assert out["n"] is None


def test_measuring_the_ceiling_never_changes_who_is_admitted(base: Path) -> None:
    """The counter is a measurement, not a door."""
    _write(base, "QQUANT_GATES.json", _qquant([
        _row("EURUSD", "breakout", "SHORT", "asia"),
        _row("USDJPY", "breakout", "LONG", "ny")]))
    before = authorized_specs(base)
    unreachable_certificates(base)
    assert authorized_specs(base) == before
    assert len(before) == 1


# ------------------------------------------------------------------- it is WIRED

def test_the_reconciler_publishes_the_ceiling() -> None:
    """III.16: a measurement nothing runs is indistinguishable from one that does
    not exist. The reconciler is on a 20-minute timer, so this rides it."""
    src = (Path(__file__).resolve().parent.parent
           / "research" / "forward_reconcile.py").read_text(encoding="utf-8")
    assert "unreachable_certificates" in src
    assert "unreachable_certified" in src


def test_the_reconciler_survives_a_broken_measurement() -> None:
    """A health report that dies because an enrichment threw is worse than one
    missing a field."""
    src = (Path(__file__).resolve().parent.parent
           / "research" / "forward_reconcile.py").read_text(encoding="utf-8")
    head = src[src.index("unreachable_certificates"):]
    assert "except Exception" in head[:400]
