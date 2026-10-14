"""An ordered STANDBY holds against both restorers (measured on the trading box 2026-10-14).

The 2026-10-13 21:30Z stop-the-bleed set the AUDCHF/EURZAR/USDZAR gap-decay principals to STANDBY
with `standby_reason` naming the principal's order. `heal_silent_demotions` read no such field,
called the demotion silent and lifted the rows back to LIVE at 0.10 (EURZAR 21:50Z, USDZAR 23:50Z,
AUDCHF 01:50Z); the promoter's capital reconciliation would have done the same on an admitting
reading from the funded book (its fix rides the laptop's sealed pass). Only the CERT_BOOK_LIVE
0.0 overlay stood between them and an order.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

_HOLD = "stop_the_bleed_2026-10-13: zuck removed AUDCHF/ZAR from Fusion live; forward-only"


@pytest.fixture()
def healer(tmp_path, monkeypatch):
    path = _DESK / "scripts" / "heal_silent_demotions.py"
    spec = importlib.util.spec_from_file_location("heal_silent_demotions_h", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sleeves = tmp_path / "sleeves.json"
    monkeypatch.setattr(mod, "SLEEVES", sleeves)
    (tmp_path / "PRINCIPAL_STOPS.json").write_text('{"stops": []}', encoding="utf-8")

    def run(rows: list[dict]) -> dict[str, str]:
        sleeves.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
        mod.heal(apply=True)
        doc = json.loads(sleeves.read_text(encoding="utf-8"))
        return {r["name"]: r["status"] for r in doc["sleeves"]}
    return run


def test_the_stop_the_bleed_standby_reason_is_never_lifted(healer) -> None:
    got = healer([{"name": "audchf_gap", "status": "STANDBY", "risk_frac": 0.0,
                   "standby_reason": _HOLD}])
    assert got["audchf_gap"] == "STANDBY"


def test_any_reason_field_counts_and_a_restore_stamp_does_not(healer) -> None:
    got = healer([{"name": "a", "status": "STANDBY", "hold_reason": "principal order"},
                  {"name": "b", "status": "STANDBY", "restore_reason": "funded at 5.5% heat"}])
    assert got == {"a": "STANDBY", "b": "LIVE"}
