"""A zero-heat sleeve that traded anyway (measured on the trading box 2026-09-30).

`xauusd_macro_conditional_asia_p_5fa26e22` was STANDBY at 0% heat with `demote_reason` and an
`admission.why` recorded -- and placed live 0.01-lot orders anyway, because
`heal_silent_demotions` read neither field, called the demotion "silent" and lifted the row back to
LIVE every hour.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ 2. the hourly un-demotion
@pytest.fixture()
def healer(tmp_path, monkeypatch):
    path = _DESK / "scripts" / "heal_silent_demotions.py"
    spec = importlib.util.spec_from_file_location("heal_silent_demotions_t", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sleeves = tmp_path / "sleeves.json"
    monkeypatch.setattr(mod, "SLEEVES", sleeves)

    def run(rows: list[dict]) -> dict[str, str]:
        sleeves.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
        mod.heal(apply=True)
        doc = json.loads(sleeves.read_text(encoding="utf-8"))
        return {r["name"]: r["status"] for r in doc["sleeves"]}
    return run


def test_the_promoters_demote_reason_is_a_verdict_and_is_never_lifted(healer) -> None:
    got = healer([{"name": "xauusd_macro_conditional_asia_p_5fa26e224170b851",
                   "status": "STANDBY", "risk_frac": 0.0,
                   "demote_reason": "standby on the current reading -- refused: the optimiser "
                                    "gives it 0.0000% heat"}])
    assert got["xauusd_macro_conditional_asia_p_5fa26e224170b851"] == "STANDBY"


def test_an_admission_standby_why_is_a_verdict_and_is_never_lifted(healer) -> None:
    got = healer([{"name": "a", "status": "STANDBY",
                   "admission": {"status": "STANDBY", "risk_frac": 0.0,
                                 "why": "standby on the current reading"}}])
    assert got["a"] == "STANDBY"


def test_a_demotion_that_truly_records_nothing_is_still_restored(healer) -> None:
    got = healer([{"name": "b", "status": "STANDBY"}])
    assert got["b"] == "LIVE"
