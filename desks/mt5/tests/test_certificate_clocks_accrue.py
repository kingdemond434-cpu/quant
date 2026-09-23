"""A CERTIFICATE'S CLOCK MUST ACCRUE, and a clock that does not must be LOUD.

THE DEFECT THIS FILE PINS, measured on the trading box 2026-09-23. `PRODUCTIVITY_CENSUS.json`
read `certificates 28 | forward_enrolled 2`, so the reading was that 26 certificates had no
clock. They all had one. All 28 were enrolled, `FORWARD_ENROLMENT.json` reported `n_missing: 0`,
and `scripts/check_forward_enrolment.py` passed -- while NOT ONE of the 28 was accruing a single
bar of forward evidence:

    REFUSED_BY_UNIVERSE_POLICY   24    every FX symbol read UNCLASSIFIED
    BLOCKED_NO_BARS               4    XAUUSD, mid-parquet-rewrite

A certificate that accrues nothing can never reach `days >= 14`, so it can never be promoted, so
it is inert -- the AUTOMATIC PROMOTION order (principal 2026-09-04) is breached exactly as
completely as if the clock were absent. The fence could not see it because it asked whether a ROW
EXISTED. `scripts/check_enrolment_gap.py` had said so in its own docstring for weeks ("`has a
clock` and `is accruing evidence` are different claims and only one of them is what the desk
needs") and nothing on a clock read it.

The two halves here pull against each other on purpose, the way `test_universe_policy` does: one
asserts the blocked clock is LOUD, the other asserts that a healthy clock and a DECIDED one are
not slandered as defects. A fence that fired on every promoted cell would be turned off in a day.

NOTHING HERE IS A CAP. Every assertion is about MEASUREMENT and about naming a blocker; none of
them rations a clock, ranks one, or suggests retiring anything.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import forward_enrolment as fe  # noqa: E402

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
STAMP = "2026-09-23T03:12:00+00:00"


def _run(symbol="XAUUSD", family="session_range_breakout", selector="asia", side="LONG"):
    return {"symbol": symbol, "family": family, "selector": selector, "side": side, "params": {}}


def _key(run) -> str:
    return f"{run['symbol']}.{run['family']}.{run['selector']}.{run['side']}"


def _census(monkeypatch, status: str, **row):
    monkeypatch.setattr(fe, "_run_key", _key)
    run = _run()
    clock = {"status": status, "enrolled_at": STAMP, "lane": "shadow_state.json", **row}
    return fe.census([run], {_key(run): clock},
                     {("XAUUSD", "session_range_breakout", "asia", "LONG"): STAMP}, NOW)


# ------------------------------------------------- the defect: enrolled, and accruing nothing
def test_a_refused_clock_is_enrolled_and_blocked_not_a_clean_zero(monkeypatch) -> None:
    """The exact live state: 24 of 28 certificates refused by the lane policy."""
    body = _census(monkeypatch, "REFUSED_BY_UNIVERSE_POLICY",
                   last_error="EURJPY is in the unclassified lane")
    assert body["n_enrolled"] == 1, "it HAS a clock -- that was never the question"
    assert body["n_missing"] == 0
    assert body["n_accruing"] == 0, "and it is gathering nothing, which is the defect"
    assert body["n_blocked"] == 1
    assert body["blocked"][0]["status"] == "REFUSED_BY_UNIVERSE_POLICY"
    assert "unclassified lane" in body["blocked"][0]["blocker"]
    assert body["blocked_by_status"] == {"REFUSED_BY_UNIVERSE_POLICY": 1}


def test_a_starved_clock_is_blocked_too(monkeypatch) -> None:
    body = _census(monkeypatch, "BLOCKED_NO_BARS", last_error="no H1 bars for XAUUSD")
    assert body["n_blocked"] == 1 and body["n_accruing"] == 0
    assert body["blocked"][0]["why"] == fe.BLOCKED_WHY


def test_the_fence_fails_on_a_blocked_certificate_and_names_it(monkeypatch, tmp_path) -> None:
    """The permanence half: the law gate must go RED, not quietly COVERED."""
    import importlib

    gate = importlib.import_module("scripts.check_forward_enrolment")
    body = _census(monkeypatch, "REFUSED_BY_UNIVERSE_POLICY", last_error="unclassified lane")
    report = tmp_path / "FORWARD_ENROLMENT.json"
    report.write_text(__import__("json").dumps({"at": NOW.isoformat(), **body}), encoding="utf-8")
    fails, _notes = gate.check_state(report=report, now=NOW)
    assert fails, "a certificate accruing nothing must FAIL the gate, never pass it"
    assert any("CERTIFIED-NOT-ACCRUING" in f for f in fails)
    assert any("XAUUSD" in f for f in fails), "and it must name the cell, not just count it"


# ------------------------------------------------- the other half: do not slander a good clock
def test_an_active_clock_is_accruing(monkeypatch) -> None:
    body = _census(monkeypatch, "ACTIVE")
    assert body["n_accruing"] == 1 and body["n_blocked"] == 0
    assert body["certificates"][0]["accruing"] is True


def test_an_unruled_clock_with_an_empty_status_is_accruing(monkeypatch) -> None:
    """The engine writes `""` for an evaluated, unruled row. Reading that as broken would fail
    on nearly every healthy clock the desk holds."""
    body = _census(monkeypatch, "")
    assert body["n_accruing"] == 1 and body["n_blocked"] == 0


def test_a_decided_clock_is_not_a_defect(monkeypatch) -> None:
    """PROMOTED and KILL are the clock having DONE ITS JOB, not a stall."""
    for status in ("PROMOTED", "KILL", "PROMOTION CANDIDATE", "RETIRED",
                   "QUARANTINED_FORWARD_CLOCK_BREACH"):
        body = _census(monkeypatch, status)
        assert body["n_blocked"] == 0, f"{status} is a verdict, not a wiring defect"
        assert body["certificates"][0]["decided"] is True


def test_the_fence_is_silent_when_every_clock_accrues(monkeypatch, tmp_path) -> None:
    import importlib

    gate = importlib.import_module("scripts.check_forward_enrolment")
    body = _census(monkeypatch, "ACTIVE")
    report = tmp_path / "FORWARD_ENROLMENT.json"
    report.write_text(__import__("json").dumps({"at": NOW.isoformat(), **body}), encoding="utf-8")
    fails, notes = gate.check_state(report=report, now=NOW)
    assert not fails
    assert any("accruing=1" in n for n in notes), "and it must still publish the number"


def test_an_older_census_reads_unmeasured_not_pass(tmp_path) -> None:
    """L1.28a: a report predating the measurement is UNMEASURED, never a clean bill."""
    import importlib
    import json as _json

    gate = importlib.import_module("scripts.check_forward_enrolment")
    report = tmp_path / "FORWARD_ENROLMENT.json"
    report.write_text(_json.dumps({"at": NOW.isoformat(), "n_certificates": 28,
                                   "n_enrolled": 28, "n_missing": 0}), encoding="utf-8")
    fails, notes = gate.check_state(report=report, now=NOW)
    assert not fails
    assert any("UNMEASURED" in n for n in notes)
