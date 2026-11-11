"""The lifetime trial ledger has a writer on a clock (leg `experiment_ledger`).

Measured on the box 2026-11-11: EXPERIMENT_LEDGER.json was last written 2026-09-20 while the
sealed judge charged every DSR from it. Nothing on any clock called `lifetime(write=True)`.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(DESK / "scripts") not in sys.path:
    sys.path.insert(0, str(DESK / "scripts"))

import write_experiment_ledger as w  # noqa: E402

from libs.research import experiment_ledger as el  # noqa: E402


def test_the_leg_rewrites_a_stale_ledger_and_reports_the_drift(monkeypatch, tmp_path, capsys):
    out = tmp_path / "EXPERIMENT_LEDGER.json"
    out.write_text(json.dumps({"generated_utc": "2026-09-20T23:23:46+00:00",
                               "lifetime_trials": 5}), "utf-8")
    monkeypatch.setattr(el, "OUT", out)
    fresh = {"generated_utc": "2026-11-11T09:00:00+00:00", "lifetime_trials": 9,
             "judged_cells": 4, "screened_cells": 5, "by_family": {"a": 9}}

    def fake_lifetime(write: bool = True):
        assert write is True, "the leg exists to WRITE the ledger"
        out.write_text(json.dumps(fresh), "utf-8")
        return fresh

    monkeypatch.setattr(el, "lifetime", fake_lifetime)
    assert w.main([]) == 0
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["lifetime_trials"] == 9
    assert line["previous_lifetime_trials"] == 5
    assert line["previous_generated_utc"] == "2026-09-20T23:23:46+00:00"
    assert json.loads(out.read_text("utf-8"))["generated_utc"] == fresh["generated_utc"]


def test_a_failed_write_exits_one(monkeypatch, tmp_path):
    monkeypatch.setattr(el, "OUT", tmp_path / "missing" / "x.json")

    def broken(write: bool = True):
        raise OSError("disk full")

    monkeypatch.setattr(el, "lifetime", broken)
    assert w.main([]) == 1


def test_the_hourly_cycle_runs_the_writer_every_hour():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    tree = ast.parse(src)
    core = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == "CORE_LEGS"):
            core = ast.literal_eval(node.value.args[0])
    assert core is not None and "experiment_ledger" in core
    assert '"experiment_ledger", "scripts/write_experiment_ledger.py"' in src
