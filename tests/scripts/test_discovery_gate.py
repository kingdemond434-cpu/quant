"""check_discovery_gate.py + run_discovery_actuator.py -- the last link from a discovery
sleeve's forward evidence to an authorized fraction, closing what run_discovery_forward.py fed.

Reuses libs.risk.kelly_shrink.shrink_fraction (already principal-adopted 2026-07-12) rather than
inventing a new rung table -- check_promotion_gate.py's ladder was fixed by an explicit principal
ruling (2026-07-31) before evidence existed, and no equivalent ruling exists for systematic
discovery sleeves. A machine choosing its own trade-count/book-fraction thresholds here would be
exactly the unreviewed capital policy libs.ops.law_police.NEVER_AUTO_CORRECT forbids.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def gate_mod(tmp_path: Path, monkeypatch):
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "check_discovery_gate", _REPO / "scripts/check_discovery_gate.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def actuator_mod(tmp_path: Path, monkeypatch):
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "run_discovery_actuator", _REPO / "scripts/run_discovery_actuator.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write_forward(tmp_path: Path, sleeves: dict) -> None:
    web = tmp_path / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "discovery_forward.json").write_text(
        json.dumps({"status": "OK", "sleeves": sleeves}), "utf-8")


# ------------------------------------------------------------------ the gate
def test_absent_forward_artifact_is_unmeasured(gate_mod, tmp_path: Path) -> None:
    doc = gate_mod.evaluate(root=tmp_path)
    assert doc["status"] == "UNMEASURED"
    assert doc["sleeves"] == {}


def test_a_sleeve_below_min_days_reports_zero_not_a_verdict(gate_mod, tmp_path: Path) -> None:
    _write_forward(tmp_path, {"funding_carry": {"days_forward": 10, "forward_sharpe": None,
                                                 "min_days": 40}})
    doc = gate_mod.evaluate(root=tmp_path)
    row = doc["sleeves"]["funding_carry"]
    assert row["authorized_fraction_of_kelly"] == 0.0
    assert row["state"] == "UNMEASURED"


def test_a_ready_sleeve_gets_shrink_fraction_not_full_kelly(gate_mod, tmp_path: Path) -> None:
    _write_forward(tmp_path, {"funding_carry": {"days_forward": 40, "forward_sharpe": 2.3,
                                                 "min_days": 40}})
    doc = gate_mod.evaluate(root=tmp_path)
    row = doc["sleeves"]["funding_carry"]
    assert row["state"] == "SIZED"
    assert 0.0 < row["authorized_fraction_of_kelly"] < 1.0, (
        "must be a SHRUNK fraction, never full Kelly at day 40")


def test_a_negative_sharpe_sleeve_gets_zero(gate_mod, tmp_path: Path) -> None:
    _write_forward(tmp_path, {"xsec_reversal": {"days_forward": 90, "forward_sharpe": -0.5,
                                                "min_days": 40}})
    doc = gate_mod.evaluate(root=tmp_path)
    assert doc["sleeves"]["xsec_reversal"]["authorized_fraction_of_kelly"] == 0.0


def test_more_forward_days_never_lowers_the_fraction_at_fixed_sharpe(gate_mod, tmp_path: Path
                                                                     ) -> None:
    _write_forward(tmp_path, {"s": {"days_forward": 40, "forward_sharpe": 2.0, "min_days": 40}})
    d40 = gate_mod.evaluate(root=tmp_path)["sleeves"]["s"]["authorized_fraction_of_kelly"]
    _write_forward(tmp_path, {"s": {"days_forward": 90, "forward_sharpe": 2.0, "min_days": 40}})
    d90 = gate_mod.evaluate(root=tmp_path)["sleeves"]["s"]["authorized_fraction_of_kelly"]
    assert d90 >= d40, "more evidence at the same Sharpe must never shrink the authorized fraction"


def test_the_gate_never_states_a_dollar_or_book_percentage(gate_mod, tmp_path: Path) -> None:
    """Checked on the OUTPUT DOCUMENT, not the source text -- the docstring legitimately
    explains why 'percent of book' must never appear, which would trip a naive source-text
    grep on its own explanation (the same string-marker trap this desk has hit before)."""
    _write_forward(tmp_path, {"funding_carry": {"days_forward": 40, "forward_sharpe": 2.3,
                                                 "min_days": 40}})
    doc = gate_mod.evaluate(root=tmp_path)
    row = doc["sleeves"]["funding_carry"]
    assert set(row) == {"authorized_fraction_of_kelly", "state", "days_forward",
                        "forward_sharpe", "why"}, (
        "the per-sleeve row must carry only the Kelly fraction and its evidence -- no "
        "book_fraction/dollar-shaped field for a future reader to mistake for a size")


# ------------------------------------------------------------------ the actuator
def test_actuator_holds_a_rising_fraction_for_the_confirm_window(actuator_mod, tmp_path: Path
                                                                  ) -> None:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/discovery_promotion_gate.json").write_text(json.dumps(
        {"status": "OK", "sleeves": {"s": {"authorized_fraction_of_kelly": 0.4}}}), "utf-8")
    doc = actuator_mod.run(root=tmp_path)
    row = doc["sleeves"]["s"]
    assert row["fraction"] == 0.0, "first sight of a positive grant must not apply instantly"
    assert row["direction"] == "HOLD-PENDING-CONFIRM"


def test_actuator_derisks_immediately_on_a_falling_fraction(actuator_mod, tmp_path: Path) -> None:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/discovery_authority.json").write_text(json.dumps(
        {"sleeves": {"s": {"fraction": 0.3, "gate_fraction": 0.3,
                          "gate_fraction_since": "2020-01-01T00:00:00+00:00"}}}), "utf-8")
    (tmp_path / "data/discovery_promotion_gate.json").write_text(json.dumps(
        {"status": "OK", "sleeves": {"s": {"authorized_fraction_of_kelly": 0.1}}}), "utf-8")
    doc = actuator_mod.run(root=tmp_path)
    row = doc["sleeves"]["s"]
    assert row["fraction"] == 0.1
    assert row["direction"] == "DERISK"


def test_actuator_applies_a_held_rise_past_the_confirm_window(actuator_mod, tmp_path: Path
                                                                ) -> None:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/discovery_authority.json").write_text(json.dumps(
        {"sleeves": {"s": {"fraction": 0.0, "gate_fraction": 0.4,
                          "gate_fraction_since": "2020-01-01T00:00:00+00:00"}}}), "utf-8")
    (tmp_path / "data/discovery_promotion_gate.json").write_text(json.dumps(
        {"status": "OK", "sleeves": {"s": {"authorized_fraction_of_kelly": 0.4}}}), "utf-8")
    doc = actuator_mod.run(root=tmp_path)
    row = doc["sleeves"]["s"]
    assert row["fraction"] == 0.4
    assert row["direction"] == "RAISE"


def test_an_unmeasured_gate_holds_the_previous_authority(actuator_mod, tmp_path: Path) -> None:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/discovery_authority.json").write_text(json.dumps(
        {"sleeves": {"s": {"fraction": 0.2}}}), "utf-8")
    doc = actuator_mod.run(root=tmp_path)
    assert doc["status"] == "UNMEASURED"
    assert doc["sleeves"] == {"s": {"fraction": 0.2}}


def test_the_actuator_has_no_execution_wiring(actuator_mod) -> None:
    src = (_REPO / "scripts/run_discovery_actuator.py").read_text("utf-8")
    for forbidden in ("place_order", "submit_order", "send_order", "execute_trade"):
        assert forbidden not in src
    assert "no execution path" in src.lower()


# ------------------------------------------------------------------ the running organs
def test_gate_runs_as_a_cron_line_would_invoke_it() -> None:
    r = subprocess.run([sys.executable, str(_REPO / "scripts/check_discovery_gate.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=60)
    assert "ModuleNotFoundError" not in r.stderr


def test_actuator_runs_as_a_cron_line_would_invoke_it() -> None:
    r = subprocess.run([sys.executable, str(_REPO / "scripts/run_discovery_actuator.py"),
                       "--dry-run"], cwd=_REPO, capture_output=True, text=True, timeout=60)
    assert "ModuleNotFoundError" not in r.stderr
