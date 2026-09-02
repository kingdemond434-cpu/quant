"""The enrolment ceiling is a number now, and the door it describes stays shut.

    python -m pytest desks/mt5/tests/test_enrolment_ceiling.py -q

WHAT WAS INVISIBLE. `authorized_specs` dropped every certified SHORT row on a
bare `continue` in two of its three sources -- and its third source had no side
test at all, so the same certificate was admitted or discarded depending only on
which report carried it. Nothing counted the drops. A reader comparing
"certified" against "enrolled" saw a gap and had no way to tell a bug from a
queue from a wall.

WHY THE DOOR MUST STAY SHUT, which is the half that matters. `shadow_forward`
freezes `direction="LONG"` into the identity of every clock it mints and calls
families as `fam_fn(h1, side=1, ...)`; the spec tuple carries no side at all. So
admitting a SHORT certificate would enrol a clock that REPLAYS LONG and accrues
forward evidence for the opposite direction to the one certified, under an
identity claiming LONG. The first test below is the one that must never be
"fixed" by deleting the filter.

The measurement is what makes the real fix -- threading `side` through the spec,
the frozen identity and `fam_fn` -- rankable against everything else competing
for the same hour.
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
    """NEVER delete this. The engine freezes direction=LONG and calls fam_fn(side=1),
    and the spec tuple carries no side -- so admitting a SHORT certificate enrols a
    clock that replays LONG and accrues evidence for the wrong direction."""
    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "SHORT", "asia")]))
    assert authorized_specs(base) == set()


def test_a_certified_long_is_admitted_exactly_as_before(base: Path) -> None:
    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "LONG", "asia")]))
    specs = authorized_specs(base)
    assert len(specs) == 1
    symbol, selector, state, family, is_universe = next(iter(specs))
    assert (symbol, selector, state, is_universe) == ("EURUSD", "asia", None, False)
    assert family == "session_range_breakout"


def test_the_only_side_the_engine_runs_is_declared():
    """It was a bare `continue` in two places and absent in a third."""
    assert frozenset({"LONG"}) == ENGINE_SIDES


# ----------------------------------------------------------- and it is now counted

def test_the_refused_short_is_counted_with_its_cause(base: Path) -> None:
    _write(base, "QQUANT_GATES.json", _qquant([_row("EURUSD", "breakout", "SHORT", "asia")]))
    out = unreachable_certificates(base)
    assert out["n"] == 1
    assert out["certificates"][0]["symbol"] == "EURUSD"
    assert out["certificates"][0]["side"] == "SHORT"
    assert "no short leg" in out["certificates"][0]["cause"]
    assert sum(out["by_cause"].values()) == 1


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
