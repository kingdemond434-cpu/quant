"""run_discovery.py's DEPLOYABLE/SHADOW sleeves had no Stage-B forward clock -- this is it.

MEASURED 2026-08-12, chasing "why can't promotion be automated": scripts/run_promotion_actuator.py
and scripts/run_slot_retirement.py already exist, are principal-approved, and already run every 15
minutes via run_pipeline_cycle.py -- automated promotion for the discretionary sleeve is not
hypothetical, it is live. But check_promotion_gate.py (the gate that actuator transmits) reads only
discretionary-sleeve evidence; it has never heard of web/discovery.json. A DEPLOYABLE verdict from
run_discovery.py is a full gauntlet pass on BACKTEST data -- Stage A by the desk's own Two-Stage
Discovery Law, with zero promotion authority on its own. This organ gives those sleeves the Stage-B
forward clock oi_divergence/ls_contrarian already have, so a future gate has real evidence to size
against with libs.risk.kelly_shrink's already-adopted evidence-ramped formula.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def mod(tmp_path: Path, monkeypatch):
    import importlib.util
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "run_discovery_forward", _REPO / "scripts/run_discovery_forward.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write_discovery(tmp_path: Path, results: list[dict]) -> None:
    web = tmp_path / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "discovery.json").write_text(json.dumps({"results": results}), "utf-8")


# ------------------------------------------------------------------ absent/unreadable input
def test_absent_discovery_json_is_unmeasured_not_zero(mod) -> None:
    mod.main()
    out = json.loads(Path("web/discovery_forward.json").read_text("utf-8"))
    assert out["status"] == "UNMEASURED"
    assert out["sleeves"] == {}


def test_no_promotable_sleeves_is_named_separately(mod, tmp_path: Path) -> None:
    _write_discovery(tmp_path, [{"sleeve": "xsec_reversal", "status": "REJECTED"}])
    mod.main()
    out = json.loads(Path("web/discovery_forward.json").read_text("utf-8"))
    assert out["status"] == "NO-PROMOTABLE-SLEEVES"


# ------------------------------------------------------------------ the birth-date ledger
def test_birth_date_is_first_write_wins(mod) -> None:
    b1 = mod._load_birth(["funding_carry"], "2026-08-01")
    Path("data").mkdir(exist_ok=True)
    Path("data/discovery_forward_birth.json").write_text(json.dumps(b1), "utf-8")
    b2 = mod._load_birth(["funding_carry"], "2026-08-10")
    assert b2["funding_carry"] == "2026-08-01", "reappearing must not buy an earlier/later birth"


def test_new_sleeve_gets_todays_birth(mod) -> None:
    b = mod._load_birth(["ts_trend"], "2026-08-12")
    assert b["ts_trend"] == "2026-08-12"


# ------------------------------------------------------------------ the forward-only filter
def test_only_returns_strictly_after_birth_count(mod) -> None:
    """Everything at or before birth was already visible to the gauntlet that promoted the
    sleeve -- counting it as forward evidence would let a backtest re-prove itself."""
    idx = pd.to_datetime([date(2026, 8, 1) + timedelta(days=i) for i in range(10)])
    series = pd.Series(np.full(10, 0.01), index=idx)
    fwd = mod._forward_slice(series, "2026-08-05")
    assert len(fwd) == 5, "days 6-10 (indices 5-9) are strictly after 2026-08-05"


def test_zero_returns_are_excluded_as_non_trading_days(mod) -> None:
    idx = pd.to_datetime([date(2026, 8, 1) + timedelta(days=i) for i in range(5)])
    series = pd.Series([0.01, 0.0, 0.02, 0.0, 0.01], index=idx)
    fwd = mod._forward_slice(series, "2026-07-31")
    assert len(fwd) == 3


# ------------------------------------------------------------------ the panel-dependent path
def test_promotable_sleeve_accrues_from_a_fake_panel(mod, tmp_path: Path, monkeypatch) -> None:
    _write_discovery(tmp_path, [{"sleeve": "funding_carry",
                                 "status": "DEPLOYABLE (gauntlet pass)"}])
    # Pre-seed a fixed birth date so accrual is deterministic regardless of wall-clock "today".
    Path("data").mkdir(exist_ok=True)
    Path("data/discovery_forward_birth.json").write_text(
        json.dumps({"funding_carry": "2026-08-09"}), "utf-8")   # day 39 of the 60-day panel
    idx = pd.to_datetime([date(2026, 7, 1) + timedelta(days=i) for i in range(60)])
    close = pd.DataFrame({"BTCUSDT": np.linspace(100, 200, 60)}, index=idx)
    r = np.full(60, 0.001)

    def _fake_panels():
        return close, pd.DataFrame(index=idx), pd.DataFrame(), pd.DataFrame(), {"BTCUSDT": 1e7}

    def _fake_candidates(*a, **k):
        return {"funding_carry": r}

    monkeypatch.setattr(mod, "_panels", _fake_panels)
    monkeypatch.setattr(mod, "_candidates", _fake_candidates)
    mod.main()
    out = json.loads(Path("web/discovery_forward.json").read_text("utf-8"))
    assert out["status"] == "OK"
    row = out["sleeves"]["funding_carry"]
    assert row["days_forward"] == 20, "days 40-59 (indices after day 39) are forward, 20 total"
    assert row["status"].startswith("ACCUMULATING"), "20 < MIN_DAYS(40) -- not ready yet"
    assert row["forward_sharpe"] is None, "not peek-safe before MIN_DAYS"
    assert "e_value" in row["anytime_peek"], "e-value IS peek-safe and reports before MIN_DAYS"


def test_a_sleeve_missing_from_todays_panel_reports_why_not_zero_silently(
        mod, tmp_path: Path, monkeypatch) -> None:
    _write_discovery(tmp_path, [{"sleeve": "basis_carry", "status": "SHADOW (orthogonal +edge)"}])
    idx = pd.to_datetime([date(2026, 8, 1)])
    monkeypatch.setattr(mod, "_panels",
                        lambda: (pd.DataFrame({"BTCUSDT": [1.0]}, index=idx),
                                pd.DataFrame(index=idx), pd.DataFrame(), pd.DataFrame(),
                                {"BTCUSDT": 1e7}))
    monkeypatch.setattr(mod, "_candidates", lambda *a, **k: {})   # basis_carry didn't qualify today
    mod.main()
    out = json.loads(Path("web/discovery_forward.json").read_text("utf-8"))
    assert out["sleeves"]["basis_carry"]["days_forward"] == 0
    assert "why" in out["sleeves"]["basis_carry"]


# ------------------------------------------------------------------ the network refusal path
def test_a_panel_refusal_is_reported_not_silently_frozen(mod, tmp_path: Path, monkeypatch) -> None:
    _write_discovery(tmp_path, [{"sleeve": "funding_carry", "status": "DEPLOYABLE"}])

    def _boom():
        raise SystemExit("REFUSED: could not list the tradeable universe")
    monkeypatch.setattr(mod, "_panels", _boom)
    mod.main()
    out = json.loads(Path("web/discovery_forward.json").read_text("utf-8"))
    assert out["status"] == "REFUSED"
    assert out["sleeves"]["funding_carry"]["days_forward"] is None


# ------------------------------------------------------------------ zero promotion authority
def test_it_never_gates_sizes_or_promotes_anything(mod) -> None:
    src = (_REPO / "scripts/run_discovery_forward.py").read_text("utf-8")
    assert "ZERO promotion authority" in src
    for forbidden in ("place_order", "live_authority", "book_fraction"):
        assert forbidden not in src


def test_writes_the_exact_path_a_future_gate_would_read(mod) -> None:
    assert Path("web/discovery_forward.json") == mod._OUT


# ------------------------------------------------------------------ the running organ
def test_the_script_runs_as_a_cron_line_would_invoke_it() -> None:
    r = subprocess.run([sys.executable, str(_REPO / "scripts/run_discovery_forward.py")],
                       cwd=_REPO, capture_output=True, text=True, timeout=120)
    assert "ModuleNotFoundError" not in r.stderr
