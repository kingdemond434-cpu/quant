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
