from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import carry_crash_gate as g  # noqa: E402


def test_family_parse():
    assert g.family_of("AUDJPY.carry.p=44136fa355b3678a") == "carry"
    assert g.family_of("AUDJPY@H1.carry.p=1") == "carry"
    assert g.family_of("EXT:fx_carry_book") == "carry"
    assert g.family_of("EURUSD.momentum.p=1") == "momentum"


def test_no_carry_members_is_unmeasured_with_unit_multiplier(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "REPORT", tmp_path / "CARRY_CRASH.json")
    idx = pd.bdate_range("2020-01-01", periods=10)
    doc = g.run_from({"EURUSD.momentum.p=1": (pd.Series(0.1, index=idx), None)})
    assert doc["status"] == "UNMEASURED" and doc["current"]["multiplier"] == 1.0
    assert json.loads((tmp_path / "CARRY_CRASH.json").read_text())["status"] == "UNMEASURED"


def test_carry_members_pool_and_report(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "REPORT", tmp_path / "CARRY_CRASH.json")
    monkeypatch.setattr(g, "load_cot", lambda: None)
    monkeypatch.setattr(g, "load_vix", lambda: None)
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2019-01-01", periods=1200)
    series = {f"X{k}JPY.carry.p={k}": (pd.Series(0.02 + 0.4 * rng.normal(size=idx.size),
                                                 index=idx), None) for k in range(3)}
    doc = g.run_from(series)
    assert doc["inputs"]["carry_members"] == 3
    assert doc["status"] in {"ARMED", "DISARMED", "UNMEASURED"}
    assert doc["current"]["multiplier"] == (doc["current"].get("proposed_multiplier")
                                            if doc["status"] == "ARMED" else 1.0)
