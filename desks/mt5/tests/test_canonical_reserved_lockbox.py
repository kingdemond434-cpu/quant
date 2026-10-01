"""Policy v3: the reserved lockbox is the certificate authority's gate 9, and nothing else mints.

    python -m pytest desks/mt5/tests/test_canonical_reserved_lockbox.py -q

The external audit of 2026-09-29 found 58/58 authority certificates with lockbox_sharpe equal to
walk_forward.oos_sharpe: the canonical path (scripts/external_gauntlet.py) still computed gate 9
as `wf_oos >= 0` while universal_gate.py -- which cannot mint -- had the corrected carve.

WHAT MUST NOT REGRESS:
  1. the authority carves the final calendar fraction BEFORE any other gate reads the series
  2. gate 9 reads the held-out rows only, and fails closed when there are too few of them
  3. the policy version changed, so every pre-v3 certificate stops conferring authority
  4. no other lane can pass gate 9 by restating walk-forward
  5. an UNMEASURED cost basis fails swap_cost closed
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK / "scripts", DESK.parent.parent):
    sys.path.insert(0, str(p))

from research import gate_policy as gp  # noqa: E402


def _daily(n: int, mu_dev: float, mu_tail: float, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = [date(2020, 1, 1) + timedelta(days=i) for i in range(n)]
    cut = int(n * 0.8)
    vals = np.concatenate([rng.normal(mu_dev, 1.0, cut), rng.normal(mu_tail, 1.0, n - cut)])
    return pd.Series(vals, index=idx)


# ------------------------------------------------------------------ 1-2. carve and stage

def test_carve_splits_every_series_at_one_calendar_key() -> None:
    a, b = _daily(500, 0.1, 0.1, 1), _daily(420, 0.1, 0.1, 2)
    cut = gp.lockbox_cut([a, b, None])
    dev, held = gp.carve_lockbox([a, b, None], cut)
    assert dev[2] is None and held[2] is None
    for full, d, h in ((a, dev[0], held[0]), (b, dev[1], held[1])):
        assert len(d) + len(h) == len(full)
        assert d.index.max() < cut <= h.index.min()


def test_no_cut_means_no_lockbox_for_anyone() -> None:
    s = _daily(50, 0.1, 0.1, 3)
    cut = gp.lockbox_cut([s])
    assert cut is None
    _dev, held = gp.carve_lockbox([s], cut)
    assert held == [None]
    st = gp.lockbox_stage(held[0], lambda a: 1.0)
    assert st["passed"] is False and st["lockbox_sharpe"] is None


def test_stage_reads_held_out_rows_only() -> None:
    held = pd.Series(np.full(gp.LOCKBOX_MIN_DAYS, -1.0) + np.linspace(0, 0.1, gp.LOCKBOX_MIN_DAYS))
    st = gp.lockbox_stage(held, lambda a: float(np.mean(a)))
    assert st["passed"] is False
    assert st["n_days"] == gp.LOCKBOX_MIN_DAYS
    assert st["basis"] == gp.ATTESTATION["lockbox_basis"]


# ------------------------------------------------------------------ 3. re-certification

def test_a_v2_attestation_no_longer_confers_authority() -> None:
    v2 = {k: v for k, v in gp.ATTESTATION.items() if k != "lockbox_basis"}
    v2["version"] = "mt5-original-universal-10-v2-calibrated-inputs"
    assert gp.is_exact_policy(v2) is False
    assert gp.is_exact_policy(dict(gp.ATTESTATION)) is True
    assert "reserved-lockbox" in gp.VERSION


# ------------------------------------------------------------------ the authority itself

@pytest.fixture(scope="module")
def eg():
    import external_gauntlet
    return external_gauntlet


def _cell(sym: str, fam: str, ds: pd.Series, seed: int) -> dict:
    return {"sym": sym, "family": fam, "params": {"seed": seed},
            "_cached_ds": ds, "_cached_ds3": ds - 0.01}


_META = {s: {"median_spread_pts": 10.0, "tick_size": 1e-5, "tick_value": 0.9,
             "contract_size": 1e5, "swap_long": -3.0, "swap_short": 1.0}
         for s in ("EURUSD", "GBPUSD", "USDJPY")}


def test_the_authority_lockbox_is_not_walk_forward(eg, monkeypatch,
                                                  measured_dsr_inputs) -> None:
    monkeypatch.setattr("research.cost_to_edge.verdict",
                        lambda *a, **k: (False, "", {"measured": False, "why": "no terminal"}))
    cells = [_cell("EURUSD", "carry", _daily(700, 0.15, -0.6, 7), 1),
             _cell("GBPUSD", "carry", _daily(700, 0.12, 0.3, 8), 2),
             _cell("USDJPY", "carry", _daily(700, 0.10, 0.2, 9), 3)]
    out = eg.run_gauntlet(cells, "t", _META)
    judged = [v for v in out["verdicts"] if not v.get("unmeasured")]
    assert len(judged) == 3
    for v in judged:
        lb, wf = v["stages"]["lockbox"], v["stages"]["walk_forward"]
        assert lb["lockbox_sharpe"] != wf["oos_sharpe"]
        assert lb["n_days"] >= gp.LOCKBOX_MIN_DAYS
        assert v["days"] + lb["n_days"] == 700, "dev and held-out must partition the series"
    lose = next(v for v in judged if v["sym"] == "EURUSD")
    assert lose["stages"]["lockbox"]["passed"] is False, "a losing reserved tail must fail gate 9"
    assert out["gate_independence"]["lockbox_restates_walk_forward"]["n"] == 0


def test_unmeasured_cost_basis_fails_swap_cost_closed(eg, monkeypatch) -> None:
    monkeypatch.setattr("research.cost_to_edge.verdict",
                        lambda *a, **k: (False, "", {"measured": False, "why": "no terminal"}))
    meta = dict(_META)
    meta["GBPUSD"] = {k: v for k, v in _META["GBPUSD"].items() if k != "swap_long"}
    cells = [_cell("EURUSD", "carry", _daily(700, 0.15, 0.2, 7), 1),
             _cell("GBPUSD", "carry", _daily(700, 0.12, 0.3, 8), 2),
             _cell("ZZZ", "carry", _daily(700, 0.10, 0.2, 9), 3)]
    out = eg.run_gauntlet(cells, "t", meta)
    by = {v["sym"]: v["stages"]["swap_cost"] for v in out["verdicts"] if not v.get("unmeasured")}
    assert by["EURUSD"]["passed"] is True
    assert by["GBPUSD"]["passed"] is False and "swap_long" in by["GBPUSD"]["why"]
    assert by["ZZZ"]["passed"] is False and "absent" in by["ZZZ"]["why"]


def test_registry_basis_names_every_missing_field(eg) -> None:
    assert eg.registry_cost_basis("EURUSD", _META)["measured"] is True
    r = eg.registry_cost_basis("X", {"X": {"tick_size": 0.0}})
    assert r["measured"] is False
    for f in ("median_spread_pts", "tick_size", "tick_value", "swap_short"):
        assert f in r["why"]


# ------------------------------------------------------------------ 4. no second mint

@pytest.mark.parametrize("path", ["research/qquant_gates.py", "scripts/full_pipeline.py",
                                  "side_channels/ug_remote.py", "scripts/external_gauntlet.py"])
def test_no_lane_restates_walk_forward_as_the_lockbox(path: str) -> None:
    src = (DESK / path).read_text(encoding="utf-8")
    assert '"lockbox_sharpe": round(wf_oos' not in src
    assert 'stages["lockbox"] = {"passed": bool(wf_oos' not in src


# ------------------------------------------------------------------ 6. lifetime multiplicity

def test_the_lifetime_union_sets_the_charge_and_never_lowers_it(eg) -> None:
    led = {"status": "MEASURED", "lifetime_trials": 50_000,
           "family_trials": {"carry": 40_000, "tiny": 3}}
    n, why = eg.charged_lifetime_trials(109, "carry", led, 10)
    assert n == 50_000 and "union" in why, "a family is charged the whole union, not its slice"
    assert eg.charged_lifetime_trials(109, "tiny", led, 10)[0] == 50_000
    assert eg.charged_lifetime_trials(109, "new", led, 10)[0] == 50_000
    small = {"status": "MEASURED", "lifetime_trials": 20, "family_trials": {}}
    assert eg.charged_lifetime_trials(109, "new", small, 10)[0] == 109, "never below campaign"


def test_an_unreadable_ledger_fails_the_charge_closed(eg) -> None:
    n, why = eg.charged_lifetime_trials(109, "carry", {"status": "UNMEASURED"}, 1000)
    assert n is None and "UNMEASURED" in why
    n, _ = eg.charged_lifetime_trials(109, "carry", {"status": "MEASURED", "family_trials": {}}, 3)
    assert n is None, "a ledger without a union count is not a measurement"


def test_the_attestation_names_the_lifetime_floor() -> None:
    assert "lifetime" in gp.ATTESTATION["lifetime_trial_floor"]
