"""THE DAILY MONITOR SCRIPT -- keying, refusal, and the ledger that gives the flags memory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import scripts.run_exec_monitor as EM


def test_FLAGS_GET_STABLE_KEYS_SO_A_CHANGING_NUMBER_IS_NOT_A_NEW_DEFECT() -> None:
    """The live flag carries today's numbers -- '-37.54 bps over 23 trades'. Keying on the message
    would make every morning a NEW defect and destroy the memory the monitor exists to provide."""
    d1 = EM.keyed_flags(["hold-class >24h bleeding: -37.54 bps over 23 trades"])
    d2 = EM.keyed_flags(["hold-class >24h bleeding: -41.02 bps over 26 trades"])
    assert list(d1) == list(d2) == ["hold_class_bleed"]


def test_THE_THREE_LIVE_FLAGS_ALL_CLASSIFY() -> None:
    keys = EM.keyed_flags([
        "hold-class >24h bleeding: -37.54 bps over 23 trades (net $-72.69)",
        "ENTRY-GATE REGRESSION: 4 open(s) below the 0.00015 funding floor AFTER the gate shipped",
        "maker conversion is LEG-ASYMMETRIC: fut 100.0% vs spot 41.7%",
    ])
    assert set(keys) == {"hold_class_bleed", "entry_gate_regression", "maker_leg_asymmetry"}


def test_AN_UNRECOGNISED_FLAG_IS_KEPT_NOT_DROPPED() -> None:
    """A monitor tracking only the defects someone thought of goes quiet on the sixth -- and the
    sixth is the one nobody is watching for."""
    keys = EM.keyed_flags(["something nobody has a pattern for yet"])
    assert len(keys) == 1 and next(iter(keys)).startswith("unclassified:")


def test_AN_ABSENT_FORENSICS_ARTIFACT_IS_BLOCKED_NOT_CLEAN(tmp_path, monkeypatch, capsys) -> None:
    """Absence of a report is not an absence of defects, and on the money path that distinction is
    the most expensive one this desk keeps re-making."""
    monkeypatch.setattr(sys, "argv", ["run_exec_monitor.py",
                                      "--forensics", str(tmp_path / "nope.json"),
                                      "--ledger", str(tmp_path / "l.json")])
    assert EM.main() == 0
    out = capsys.readouterr().out
    assert "BLOCKED" in out and "UNMEASURED, not a clean book" in out


def test_THE_LEDGER_TURNS_A_REPEAT_INTO_A_PERSISTING_DEFECT(tmp_path, monkeypatch) -> None:
    """Two mornings with the same flag is one defect seen twice, not two findings."""
    fore = tmp_path / "f.json"
    fore.write_text(json.dumps(
        {"flags": ["ENTRY-GATE REGRESSION: gate is not filtering"]}), "utf-8")
    led = tmp_path / "l.json"
    for _ in range(2):
        monkeypatch.setattr(sys, "argv", ["run_exec_monitor.py", "--forensics", str(fore),
                                          "--ledger", str(led)])
        EM.main()
    row = json.loads(led.read_text())["defects"]["entry_gate_regression"]
    assert row["status"] == "PERSISTING" and row["occurrences"] == 2


def test_A_DEFECT_THAT_RETURNS_AFTER_RESOLVED_IS_FLAGGED_AS_A_REGRESSION(
        tmp_path, monkeypatch, capsys) -> None:
    """The category that matters most, and the desk already has one on the live tape."""
    led = tmp_path / "l.json"
    led.write_text(json.dumps(
        {"defects": {"maker_leg_asymmetry": {"status": "RESOLVED"}}}), "utf-8")
    fore = tmp_path / "f.json"
    fore.write_text(json.dumps(
        {"flags": ["maker conversion is LEG-ASYMMETRIC: fut 100 vs spot 41"]}), "utf-8")
    monkeypatch.setattr(sys, "argv", ["run_exec_monitor.py", "--forensics", str(fore),
                                      "--ledger", str(led)])
    EM.main()
    assert "REGRESSION" in capsys.readouterr().out
    assert json.loads(led.read_text())["defects"]["maker_leg_asymmetry"]["times_regressed"] == 1


def test_A_COUNT_ONLY_ARTIFACT_YIELDS_NO_FALSE_DEFECTS(tmp_path) -> None:
    """Some writers report `flags: 3` rather than the rows. Treating an int as iterable would
    invent three single-character defects."""
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"flags": 3}), "utf-8")
    flags, state = EM.load_flags(p)
    assert flags == [] and state == "COUNT-ONLY"


def test_THE_SCRIPT_CHANGES_NOTHING_ON_THE_MONEY_PATH() -> None:
    src = Path("scripts/run_exec_monitor.py").read_text("utf-8")
    for token in ("place_market", "place_order", "flatten", "api_key"):
        assert token not in src.lower(), f"the monitor reached toward an order path: {token!r}"
