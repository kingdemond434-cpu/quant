"""Every family a weekly hunt names must exist (box 2026-11-22..24).

run_hunt7 named `families.family7_spread_state_avoidance` and `family4_comex_settlement_effect`,
run_hunt8 the `family2_cot_*` names; all had left mt5desk.families. The AttributeError fired at
import, the daily chain's weekly_hunt_refresh failed every day, and no hunt behind it ran.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from mt5desk import families  # noqa: E402

HUNTS = ("run_hunt7", "run_hunt8", "run_hunt9", "run_hunt10", "run_hunt12", "free_shadows")


def test_every_family_a_weekly_hunt_names_exists() -> None:
    missing = []
    for hunt in HUNTS:
        src = (DESK / "research" / f"{hunt}.py").read_text(encoding="utf-8")
        for name in sorted(set(re.findall(r"\bfamilies\.(\w+)", src))):
            if not hasattr(families, name):
                missing.append(f"{hunt}: families.{name}")
    assert missing == []


def test_one_failing_hunt_does_not_stop_the_rest(monkeypatch, tmp_path) -> None:
    sys.path.insert(0, str(DESK / "research"))
    import types

    import daily_cycle as dcyc
    ran: list[str] = []

    def fake(name, fail=False):
        mod = types.ModuleType(name)

        def main(*_a):
            ran.append(name)
            if fail:
                raise AttributeError("gone")
            return 0
        mod.main = main
        return mod
    for n in ("fetch_universe", "run_hunt8", "run_hunt9", "free_shadows", "run_hunt10",
              "run_hunt12"):
        monkeypatch.setitem(sys.modules, n, fake(n))
    monkeypatch.setitem(sys.modules, "run_hunt7", fake("run_hunt7", fail=True))
    monkeypatch.setattr(dcyc, "BASE", tmp_path)
    monkeypatch.setattr(dcyc, "dlog", lambda *_a, **_k: None)
    try:
        dcyc._weekly_hunt_refresh()
    except RuntimeError as exc:
        assert "run_hunt7 (AttributeError)" in str(exc)
    else:
        raise AssertionError("a failed hunt must still fail the step")
    assert ran == ["fetch_universe", "run_hunt7", "run_hunt8", "run_hunt9", "free_shadows",
                   "run_hunt10", "run_hunt12"]
    assert not (tmp_path / "data" / "hunt7_state.json").exists()
