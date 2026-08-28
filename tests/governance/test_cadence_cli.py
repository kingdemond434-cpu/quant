"""R0425 -- the cadence engine had no argparse, so `--help` FIRED IT.

`.venv/bin/python scripts/run_cadence.py --help` did not print usage; it executed a full cadence
run (measured 2026-08-05: still running at 3m13s), firing the weekly panel and monthly tier1. The
desk has a documented habit of probing an unfamiliar script with `--help` before invoking it --
that is how several organs were verified -- so the one habit meant to make invocation SAFE was, on
this script, the thing that invoked it. Same class as the Windows-only generation entry point
found by EXECUTING it: the signature is not what the caller assumes.

THE REPORT TABLE IS THE RISK THIS FILE EXISTS TO FENCE. `--report-only` reads a hand-built table
of (duty, state key, period); `_main_body` tests each duty inline. A table that drifted would
report a schedule the engine does not run, and a reader would trust it -- worse than no report at
all. So the pairs are re-derived from the SOURCE here.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "scripts/run_cadence.py"


def _mod():
    spec = importlib.util.spec_from_file_location("_cadence_cli", _SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules["_cadence_cli"] = m
    spec.loader.exec_module(m)
    return m


def test_help_does_not_fire_the_engine():
    """THE DEFECT, end to end. --help must return usage, fast, having fired nothing."""
    r = subprocess.run([sys.executable, str(_SRC), "--help"], capture_output=True,
                       text=True, timeout=90, cwd=_ROOT)
    assert r.returncode == 0
    assert "usage: run_cadence.py" in r.stdout
    # The warning has to be ON the help screen: this script's no-flag behaviour is to FIRE.
    assert "--report-only" in r.stdout


def test_an_unknown_flag_is_refused_with_a_nonzero_exit():
    """--dry-run, --report, --verbose: every one of these used to be a REAL RUN."""
    r = subprocess.run([sys.executable, str(_SRC), "--dry-run"], capture_output=True,
                       text=True, timeout=90, cwd=_ROOT)
    assert r.returncode == 2
    assert "unrecognized arguments" in r.stderr


def test_report_only_emits_json_and_fires_nothing():
    r = subprocess.run([sys.executable, str(_SRC), "--report-only", "--json"],
                       capture_output=True, text=True, timeout=90, cwd=_ROOT)
    assert r.returncode == 0
    rep = json.loads(r.stdout)
    assert rep["duties"] and "REPORT ONLY" in rep["note"]
    assert all({"duty", "state_key", "period_days", "due"} <= set(d) for d in rep["duties"])


def test_main_keeps_its_no_argument_signature():
    """tests/governance/test_cadence_state_durability.py calls `main()` directly.

    Were the parse inside main(), that call would read PYTEST's argv and die on unrecognised
    arguments -- so argv is parsed in the __main__ block instead, deliberately.
    """
    import inspect
    assert list(inspect.signature(_mod().main).parameters) == []


@pytest.mark.parametrize("label,key,period", _mod()._REPORTED_DUTIES)
def test_every_reported_duty_matches_a_real_due_test_in_the_source(label, key, period):
    """THE DRIFT FENCE. A reported period the engine does not actually use is a lie a reader
    would act on -- the same class as the liveness table that drifted from its own sibling."""
    src = _SRC.read_text("utf-8")
    m = _mod()
    # The source may spell the period as a literal (`>= 7`) or as the module constant that holds
    # it (`>= _TIER1_EVERY_D`). Both are the same schedule, so both satisfy the fence.
    names = [n for n, v in vars(m).items()
             if isinstance(v, int) and not isinstance(v, bool) and v == period]
    alts = "|".join([str(period), *map(re.escape, names)])
    pat = rf'_days_since\(\s*state\s*,\s*["\']{re.escape(key)}["\']\s*\)\s*>=\s*(?:{alts})\b'
    assert re.search(pat, src), (
        f"{label}: _REPORTED_DUTIES says {key} every {period}d, but no matching "
        f"`_days_since(state, {key!r}) >= {period}` appears in run_cadence.py -- the report "
        f"would publish a cadence the engine does not run")


# --------------------------------------------------------------------------------------------
# A NAIVE STAMP IS A DATE, NOT AN ABSENCE (regression, 2026-08-28).
#
# Several cadence keys are stamped by LLM organs told in prose to "mark done:
# last_data_axis_dig". They write a bare `"2026-08-28"`. `datetime.fromisoformat` parses that
# into a NAIVE datetime; subtracting it from an aware `now()` raises TypeError; `_days_since`
# swallowed that into its 1e9 "never ran" sentinel. MEASURED: `last_data_axis_dig` held TODAY'S
# date while `--report` printed "never run", so a WEEKLY duty re-fired on EVERY cycle and a
# healthy organ was published as dead. Absence and an unparseable value must never render
# identically (WS-005 / L1.28a).
# --------------------------------------------------------------------------------------------

def test_a_bare_date_stamp_is_read_as_a_date_not_as_never_run():
    """THE REGRESSION. The exact value an LLM organ writes for these keys."""
    m = _mod()
    today = datetime.now(tz=UTC).date().isoformat()
    days = m._days_since({"last_data_axis_dig": today}, "last_data_axis_dig")
    assert days < 2.0, (
        f"a bare date stamped today must read as ~0 days, got {days} -- 1e9 here is what made a "
        "weekly duty fire every cycle and published a live organ as 'never run'")


def test_a_naive_stamp_is_never_read_as_newer_than_it_is():
    """The safe direction. Assuming UTC may age a stamp, never freshen it -- no floor relaxes."""
    m = _mod()
    naive = "2026-08-01T00:00:00"
    aware = "2026-08-01T00:00:00+00:00"
    assert m._days_since({"k": naive}, "k") >= m._days_since({"k": aware}, "k") - 1e-6


@pytest.mark.parametrize("raw", [None, "", "not a date", "2026-13-45", 12345, [], {}])
def test_absence_and_garbage_still_read_as_due(raw):
    """The sentinel must survive for the cases it was actually for -- never skip on junk."""
    m = _mod()
    assert m._days_since({"k": raw}, "k") == 1e9


def test_a_missing_key_reads_as_due():
    m = _mod()
    assert m._days_since({}, "never_stamped_at_all") == 1e9


def test_an_aware_stamp_is_unchanged():
    """The path that already worked must not move."""
    m = _mod()
    then = datetime.now(tz=UTC) - timedelta(days=3)
    assert 2.9 < m._days_since({"k": then.isoformat()}, "k") < 3.1
