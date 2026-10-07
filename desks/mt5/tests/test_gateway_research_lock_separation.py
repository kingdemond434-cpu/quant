"""Research may never hold the one order-submission lock across a long pass."""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

DESK = Path(__file__).resolve().parents[1]
for path in (str(DESK), str(DESK / "research")):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_gateway_wrapper_checks_orders_once_and_releases_lock(tmp_path, monkeypatch) -> None:
    import run_gateway_loop as loop

    lock = tmp_path / "gateway.lock"
    monkeypatch.setattr(loop, "LOCK", lock)
    calls: list[str] = []
    monkeypatch.setattr(loop.gateway, "main", lambda: calls.append("gateway"))
    loop.main()
    assert calls == ["gateway"]
    assert not lock.exists()

    source = (DESK / "research" / "run_gateway_loop.py").read_text("utf-8")
    main = next(node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    imported = {alias.name for node in ast.walk(main)
                if isinstance(node, ast.Import) for alias in node.names}
    assert imported.isdisjoint({"shadow_forward", "promoter", "regime_monitor",
                                "fetch_universe", "run_hunt7", "run_hunt8", "run_hunt9",
                                "free_shadows", "run_hunt10", "run_hunt12"})


def test_weekly_hunts_have_a_six_day_stamp_outside_gateway(tmp_path, monkeypatch) -> None:
    import daily_cycle

    monkeypatch.setattr(daily_cycle, "BASE", tmp_path)
    monkeypatch.setattr(daily_cycle, "dlog", lambda _: None)
    calls: list[str] = []
    real_import = importlib.import_module
    names = {"fetch_universe", "run_hunt7", "run_hunt8", "run_hunt9",
             "free_shadows", "run_hunt10", "run_hunt12"}
    monkeypatch.setattr(importlib, "import_module", lambda name: (
        SimpleNamespace(main=lambda: calls.append(name)) if name in names
        else real_import(name)))

    daily_cycle._weekly_hunt_refresh()
    assert calls == ["fetch_universe", "run_hunt7", "run_hunt8", "run_hunt9",
                     "free_shadows", "run_hunt10", "run_hunt12"]
    assert (tmp_path / "data" / "hunt7_state.json").exists()
    daily_cycle._weekly_hunt_refresh()
    assert len(calls) == 7
