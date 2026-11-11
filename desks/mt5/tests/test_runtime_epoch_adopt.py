"""The registry adopts the engine's own runtime epoch when that is the ONLY drift.

Box read CL3, 2026-11-11: the engine restarted ten clocks onto a new runtime epoch on 10-05 and
10-07 and the registry was never stamped (CHFNOK/XAUAUD: registry None vs state session-8a37;
AUDSGD: registry session-8a37 vs state contract-867e). The engine marked them IDENTITY_BROKEN on
runtime_version drift every pass, the healer resumed them every 30 minutes, and nothing accrued
for three weeks.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "desks" / "mt5" / "research" / "sleeve_registry.py"

FROZEN = {
    "family": "macro_conditional", "symbol": "CHFNOK", "direction": "LONG",
    "timeframe": "M30", "selector": "asia", "condition": None,
    "params": {"atr_n": 20, "session": "ny"},
    "code_hash": "aaaa", "cost_hash": "bbbb", "data_venue": "MT5:FusionMarkets-Live",
}
KEY = "CHFNOK.macro_conditional.asia@M30"


def _reg(tmp_path: Path, row: dict):
    spec = importlib.util.spec_from_file_location("sleeve_registry_adopt_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.REGISTRY = tmp_path / "sleeve_registry.json"
    module.REGISTRY.write_text(json.dumps({"sleeves": {KEY: row}}), encoding="utf-8")
    return module


def _row(reg) -> dict:
    return json.loads(reg.REGISTRY.read_text(encoding="utf-8"))["sleeves"][KEY]


def _base(**extra) -> dict:
    row = {"identity": dict(FROZEN), "forward_start": "2026-09-01T00:00:00+00:00",
           "status": "IDENTITY_BROKEN", "status_why": "runtime_version changed after the clock froze"}
    row.update(extra)
    return row


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    sys.modules.pop("sleeve_registry_adopt_test", None)


def _ident(version: str) -> dict:
    return {**FROZEN, "runtime_version": version}


def test_a_legacy_registry_adopts_the_engines_epoch_and_resumes(tmp_path) -> None:
    reg = _reg(tmp_path, _base())
    assert reg.verify(KEY, _ident("session-8a37")) == ["runtime_version"]
    why = reg.adopt_runtime_version(KEY, _ident("session-8a37"),
                                    forward_start="2026-10-07T12:30:37+00:00",
                                    prior_versions=["legacy-unfiltered"], replayed=True)
    assert why
    row = _row(reg)
    assert row["status"] == "LIVE" and row["runtime_version"] == "session-8a37"
    assert row["forward_start"] == "2026-10-07T12:30:37+00:00"
    assert row["runtime_windows_before"][-1]["runtime_version"] is None
    assert row["identity"] == FROZEN
    assert reg.verify(KEY, _ident("session-8a37")) == []


def test_a_registry_epoch_the_state_moved_past_is_adopted(tmp_path) -> None:
    reg = _reg(tmp_path, _base(runtime_version="session-8a37"))
    why = reg.adopt_runtime_version(KEY, _ident("contract-867e"),
                                    forward_start="2026-10-07T12:30:37+00:00",
                                    prior_versions=["legacy-unfiltered", "session-8a37"],
                                    replayed=True)
    assert why and _row(reg)["runtime_version"] == "contract-867e"


def test_a_registry_on_an_epoch_the_state_never_passed_is_left_alone(tmp_path) -> None:
    reg = _reg(tmp_path, _base(runtime_version="session-zzzz"))
    assert reg.adopt_runtime_version(KEY, _ident("contract-867e"), forward_start=None,
                                     prior_versions=["session-8a37"], replayed=True) is None
    assert _row(reg)["status"] == "IDENTITY_BROKEN"


def test_any_other_drift_keeps_the_clock_broken(tmp_path) -> None:
    reg = _reg(tmp_path, _base())
    moved = {**_ident("session-8a37"), "code_hash": "cccc"}
    assert reg.adopt_runtime_version(KEY, moved, forward_start=None,
                                     prior_versions=[], replayed=True) is None
    assert _row(reg)["status"] == "IDENTITY_BROKEN"


def test_a_clock_with_order_authority_is_never_adopted(tmp_path) -> None:
    reg = _reg(tmp_path, _base())
    assert reg.adopt_runtime_version(KEY, _ident("session-8a37"), forward_start=None,
                                     prior_versions=[], replayed=False) is None


def test_forward_start_never_moves_earlier(tmp_path) -> None:
    reg = _reg(tmp_path, _base())
    reg.adopt_runtime_version(KEY, _ident("session-8a37"),
                              forward_start="2026-08-01T00:00:00+00:00",
                              prior_versions=[], replayed=True)
    assert _row(reg)["forward_start"] == "2026-09-01T00:00:00+00:00"


@pytest.mark.parametrize("status", ["KILL", "PROMOTED", "RETIRED"])
def test_a_terminal_verdict_is_never_reopened(tmp_path, status) -> None:
    reg = _reg(tmp_path, _base(status=status))
    assert reg.adopt_runtime_version(KEY, _ident("session-8a37"), forward_start=None,
                                     prior_versions=[], replayed=True) is None
    assert _row(reg)["status"] == status
