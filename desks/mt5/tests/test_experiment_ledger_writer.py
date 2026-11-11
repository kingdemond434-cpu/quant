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
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import write_experiment_ledger as w  # noqa: E402

from libs.research import experiment_ledger as el  # noqa: E402


def test_the_leg_rewrites_a_stale_ledger_and_reports_the_drift(monkeypatch, tmp_path, capsys):
    out = tmp_path / "EXPERIMENT_LEDGER.json"
    out.write_text(json.dumps({"generated_utc": "2026-09-20T23:23:46+00:00",
                               "lifetime_trials": 5}), "utf-8")
    monkeypatch.setattr(el, "OUT", out)
    fresh = {"generated_utc": "2026-11-11T09:00:00+00:00", "lifetime_trials": 9,
             "judged_cells": 4, "screened_cells": 5, "by_family": {"a": 9}}

    def fake_lifetime(write: bool = True):
        assert write is False, "the leg writes it itself, atomically, after the drop check"
        return fresh

    monkeypatch.setattr(el, "lifetime", fake_lifetime)
    assert w.main([]) == 0
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["lifetime_trials"] == 9
    assert line["previous_lifetime_trials"] == 5
    assert line["previous_generated_utc"] == "2026-09-20T23:23:46+00:00"
    assert json.loads(out.read_text("utf-8"))["generated_utc"] == fresh["generated_utc"]


def test_a_failed_count_exits_one(monkeypatch, tmp_path):
    monkeypatch.setattr(el, "OUT", tmp_path / "missing" / "x.json")

    def broken(write: bool = True):
        raise OSError("disk full")

    monkeypatch.setattr(el, "lifetime", broken)
    assert w.main([]) == 1


def test_a_graph_read_failure_never_lowers_the_ledger(monkeypatch, tmp_path):
    """`_graph_counts` returns (0, {}) on an OSError; the file must keep the higher count."""
    out = tmp_path / "EXPERIMENT_LEDGER.json"
    before = {"generated_utc": "2026-09-20T23:23:46+00:00", "lifetime_trials": 26728834,
              "by_family": {"macro_conditional": 38293}}
    out.write_text(json.dumps(before), "utf-8")
    raw = out.read_bytes()
    monkeypatch.setattr(el, "OUT", out)
    monkeypatch.setattr(el, "_graph_counts", lambda: (0, {}))
    monkeypatch.setattr(el, "_prescreen_counts", lambda: (0, {}))
    monkeypatch.setattr(el, "_proposer_counts", lambda: (5, {"macro_conditional": 5}))
    monkeypatch.setattr(el, "_mass_screen_counts", lambda: (0, {}))
    monkeypatch.setattr(el, "_claim_selection_counts", lambda: (0, {}))
    monkeypatch.setattr(el, "_prereg_counts", lambda: 0)
    assert w.main([]) == 1
    assert out.read_bytes() == raw


def test_one_family_falling_refuses_the_write_even_when_the_total_rises():
    prev = {"lifetime_trials": 10, "by_family": {"a": 6, "b": 4}}
    doc = {"lifetime_trials": 50, "by_family": {"a": 49, "b": 1}}
    assert set(w.drops(prev, doc)) == {"family:b"}
    assert w.drops(prev, {"lifetime_trials": 12, "by_family": {"a": 6, "b": 6}}) == {}


def test_the_hourly_cycle_runs_the_writer_every_hour():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    tree = ast.parse(src)
    core = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == "CORE_LEGS"):
            core = ast.literal_eval(node.value.args[0])
    assert core is not None and "experiment_ledger" in core
    assert '"experiment_ledger", "research/write_experiment_ledger.py"' in src


def test_the_declared_artifact_is_the_ledger_the_judge_reads():
    assert w.OUT.resolve() == el.OUT.resolve()
