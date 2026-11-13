"""#529 leftovers rebuilt on LIVE: the heavy pass has its own wall clock, and BLAS is sized.

PID 28696 held the allocator lock 6.5h on per-candidate budgets alone. Past `pass_deadline` the
admission scan carries the rest as UNSCORED (first next pass), says `complete: False`, and the
hourly cycle never reads such a scan as a fresh heavy one.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402
from research import hourly_cycle as hc  # noqa: E402
from research import pf_allocator as pa  # noqa: E402


def _sleeve(name, sharpe, rho, core, rng, family, vol=0.35):
    idio = rng.normal(0.0, 1.0, core.size)
    z = rho * core + np.sqrt(max(1.0 - rho * rho, 0.0)) * idio
    z = (z - z.mean()) / z.std()
    return SleeveEvidence(name=name, daily_r=z * vol + sharpe / np.sqrt(252.0) * vol,
                          family=family, symbol=name.split("_")[0], n_trials=50,
                          forward_days=40, live_days=0, cost_r=0.02)


def _book_and_two_candidates(seed=7, n=600):
    rng = np.random.default_rng(seed)
    core = rng.normal(0.0, 1.0, n)
    held = [_sleeve(f"HELD_{i}", 2.3, 0.97, core, rng, "core") for i in range(4)]
    return (held, _sleeve("EURJPY_carry_asia", 1.2, -0.20, core, rng, "carry"),
            _sleeve("XAUUSD_trend_ny", 2.5, 0.95, core, rng, "core"))


def _scan(held, *candidates, **kw):
    ev = [*held, *candidates]
    cfg = WorldConfig(seed=3, n_worlds=96, n_rows=200)
    worlds = sample_worlds(ev, cfg)
    return pa.marginal_admission(ev, worlds, cfg, incumbent={e.name: 0.05 for e in held},
                                 bounds={e.name: 0.20 for e in ev}, total_heat=0.20, **kw)


def test_a_passed_deadline_carries_every_candidate_unscored_and_marks_the_scan_incomplete():
    held, div, star = _book_and_two_candidates()
    doc = _scan(held, div, star, pass_deadline=time.time() - 1.0, budget_s=-1.0)
    assert doc["status"] == "MEASURED"
    assert doc["complete"] is False and doc["deadline_cut"] == 2
    assert doc["admitted"] == []
    for why in doc["unscored"].values():
        assert "pass deadline" in why and "NOT admitted" in why


def test_no_deadline_is_a_complete_scan():
    held, div, star = _book_and_two_candidates()
    doc = _scan(held, div, star, budget_s=-1.0)
    assert doc["complete"] is True and doc["deadline_cut"] == 0
    far = _scan(held, div, star, pass_deadline=time.time() + 3600.0, budget_s=-1.0)
    assert far["complete"] is True and far["admitted"] == doc["admitted"]


def test_hourly_cycle_never_ages_from_or_stamps_an_incomplete_scan(tmp_path):
    now = datetime.now(UTC)
    art = tmp_path / "pf_allocation.json"
    adm = {"status": "MEASURED", "measured_utc": now.isoformat(), "complete": False}
    art.write_text(json.dumps({"admission": adm}), "utf-8")
    hp = tmp_path / "admission_heavy_pass.json"
    assert hc._admission_scan_age_s(art, now=now, heavy_pass=hp) is None
    assert hc._stamp_heavy_pass({"exit_code": 0}, art=art, out=hp,
                                started=now - timedelta(minutes=5)) is False
    adm["complete"] = True
    art.write_text(json.dumps({"admission": adm}), "utf-8")
    assert hc._admission_scan_age_s(art, now=now, heavy_pass=hp) is not None
    assert hc._stamp_heavy_pass({"exit_code": 0}, art=art, out=hp,
                                started=now - timedelta(minutes=5)) is True


def test_blas_threads_are_capped_and_an_explicit_setting_is_kept(monkeypatch):
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MKL_NUM_THREADS", "3")
    n = pa._cap_blas_threads()
    import os
    if n is not None:
        assert 1 <= n <= pa.BLAS_THREAD_CAP
        assert os.environ["OPENBLAS_NUM_THREADS"] == str(n)
    assert os.environ["MKL_NUM_THREADS"] == "3"
    assert pa.HEAVY_ADMISSION_BUDGET_S == 20 * 60
