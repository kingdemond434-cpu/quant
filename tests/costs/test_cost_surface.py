"""COST SURFACE + COST-BASIS FENCE (L1.5 / L1.28a).

These tests live under `tests/` and NOT under `desks/mt5/tests/` deliberately: `pyproject.toml`
sets `testpaths = ["tests"]`, so nothing -- not `ops/gates.sh`, not CI, not the pre-push hook --
ever collects the desk's own 551 tests. A wiring test that is never run is not a wiring test.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cs():
    return _load("_cost_surface", "desks/mt5/research/cost_surface.py")


@pytest.fixture(scope="module")
def fence():
    return _load("_check_cost_surface", "scripts/check_cost_surface.py")


def _frame(bars_per_day: int, days: int, spread: float, *, start="2024-01-01",
           tick_volume: int = 100, spread_overrides: dict[int, float] | None = None):
    """A synthetic H1 frame: `bars_per_day` bars on each of `days` days, from hour 0."""
    idx, sp = [], []
    for d in range(days):
        day = pd.Timestamp(start) + pd.Timedelta(days=d)
        for h in range(bars_per_day):
            idx.append(day + pd.Timedelta(hours=h))
            sp.append((spread_overrides or {}).get(h, spread))
    return pd.DataFrame({"spread": sp, "tick_volume": [tick_volume] * len(idx),
                         "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0},
                        index=pd.DatetimeIndex(idx))


# --------------------------------------------------------------------------------------------
# The defect this module's own first run produced, kept as a regression test.
# --------------------------------------------------------------------------------------------

def test_short_session_symbol_is_profiled_not_silently_dropped(cs):
    """A 7-bar equity CFD session must profile. A fixed >=20-bars/day rule dropped all 74.

    This is the anti-hardcode law with a measured price: the first version of `profile_symbol`
    used a universal `MIN_BARS_PER_DAY = 20`, which is a 24-hour-FX threshold. It excluded every
    US share CFD -- their spread columns are 96%+ non-zero and perfectly usable -- and the
    artifact reported them as "no usable spread column" and read as successfully built.
    """
    prof = cs.profile_symbol(_frame(bars_per_day=7, days=200, spread=30.0))
    assert prof is not None, "a 6.5-hour cash session must be profiled, not dropped"
    assert prof["session_bars"] == 7
    assert prof["n_hours_measured"] == 7
    assert prof["days_full"] == 200


def test_session_length_survives_a_majority_splice(cs):
    """`session_bars` must resist the splice being the MAJORITY of days.

    USDZAR's median bars/day is 1 (58% of its days are single spliced daily bars) and
    Accenture's MODE is 1 over 6,305 days. Either statistic alone is defeated by one of them,
    which is why the estimator is `max(mode, p90)` and not either half.
    """
    full = _frame(bars_per_day=24, days=40, spread=100.0)
    splice = _frame(bars_per_day=1, days=60, spread=0.0, start="2025-01-01")
    idx = pd.DatetimeIndex(list(splice.index) + list(full.index))
    assert cs.session_bars(idx) == 24, "a majority of one-bar days must not define the session"


def test_splice_days_are_excluded_and_the_evidence_is_published(cs):
    """The exclusion must be auditable, not asserted: publish the tick-volume ratio."""
    full = _frame(bars_per_day=24, days=100, spread=100.0, tick_volume=100)
    splice = _frame(bars_per_day=1, days=100, spread=50.0, start="2025-06-01",
                    tick_volume=50_000)
    df = pd.concat([full, splice]).sort_index()
    prof = cs.profile_symbol(df)
    assert prof is not None
    assert prof["days_full"] == 100, "the one-bar days must not count as sessions"
    assert prof["excluded_days"] == 100
    assert prof["splice_tickvol_ratio"] > 100, (
        "a spliced DAILY bar carries a whole day of ticks; publishing the ratio is what "
        "separates 'removed an artifact' from 'threw away real half-sessions'")


# --------------------------------------------------------------------------------------------
# L1.28a -- unmeasured never renders as a number, and zero is absence not a free trade.
# --------------------------------------------------------------------------------------------

def test_cell_below_min_obs_is_unmeasured_and_carries_no_number(cs):
    prof = cs.profile_symbol(_frame(bars_per_day=24, days=10, spread=100.0))
    assert prof is not None
    for cell in prof["hours"].values():
        assert cell["status"] == "UNMEASURED"
        assert "p50" not in cell, "an UNMEASURED cell must not carry a price a consumer can read"
    assert prof["n_hours_measured"] == 0


def test_zero_spread_bars_are_absence_not_a_free_trade(cs):
    """Hour 3 is entirely unpriced. It must go UNMEASURED, never report a cheap p50."""
    df = _frame(bars_per_day=24, days=400, spread=100.0, spread_overrides={3: 0.0})
    prof = cs.profile_symbol(df)
    assert prof is not None
    assert prof["hours"]["3"]["status"] == "UNMEASURED"
    assert prof["hours"]["3"]["zero_frac"] == 1.0
    assert prof["hours"]["4"]["status"] == "MEASURED"
    assert prof["hours"]["4"]["p50"] == 100.0


def test_spread_pts_refuses_rather_than_substituting_the_pooled_scalar(cs):
    surface = {"symbols": {"X": {"hours": {
        "1": {"status": "MEASURED", "p50": 500.0},
        "2": {"status": "UNMEASURED", "n_nonzero": 3},
    }}}}
    assert cs.spread_pts(surface, "X", 1) == 500.0
    assert cs.spread_pts(surface, "X", 2) is None, "UNMEASURED must refuse, not round to pooled"
    assert cs.spread_pts(surface, "X", 5) is None
    assert cs.spread_pts(surface, "MISSING", 1) is None
    assert cs.spread_pts(surface, "X", None) is None, (
        "a caller that has not said WHEN it fills has not asked this question")


def test_producer_refuses_to_write_an_empty_surface(cs, tmp_path, capsys):
    """An empty artifact asserts absence. Exit 2 and write nothing (L1.28a)."""
    out = tmp_path / "surface.json"
    rc = cs.main(["--out", str(out), "--universe", str(tmp_path / "no_such_dir")])
    assert rc == 2
    assert not out.exists(), "an empty surface must not be written at all"
    assert "NO SYMBOLS PROFILED" in capsys.readouterr().out


# --------------------------------------------------------------------------------------------
# The consumer: the engine must be able to charge the hour, and must not move by default.
# --------------------------------------------------------------------------------------------

def test_costs_from_symbol_default_is_byte_identical_to_today(monkeypatch):
    """`spread_pts=None` must reproduce today's arithmetic exactly -- this is the money path."""
    monkeypatch.syspath_prepend(str(_DESK))
    from mt5desk.engine import Costs

    meta = {"contract_size": 1e5, "tick_size": 1e-5, "median_spread_pts": 329.0,
            "tick_value": 1.0}
    assert Costs.from_symbol(meta) == Costs.from_symbol(meta, spread_pts=None)
    assert Costs.from_symbol(meta).spread_per_lot == pytest.approx(329.0)


def test_costs_from_symbol_charges_the_hour_when_given_one(monkeypatch):
    """The whole point: a fill-hour spread must reach `per_oz_roundtrip`."""
    monkeypatch.syspath_prepend(str(_DESK))
    from mt5desk.engine import Costs

    meta = {"contract_size": 1e5, "tick_size": 1e-5, "median_spread_pts": 329.0,
            "tick_value": 1.0}
    pooled, hourly = Costs.from_symbol(meta), Costs.from_symbol(meta, spread_pts=2028.0)
    assert hourly.spread_per_lot == pytest.approx(2028.0)
    assert hourly.per_oz_roundtrip() > pooled.per_oz_roundtrip()
    # `mult` must still scale the override, not silently ignore it.
    assert Costs.from_symbol(meta, 2.0, spread_pts=2028.0).spread_per_lot == pytest.approx(4056.0)
    # And the other unit traps stay carried -- a new field must not revert quote_per_account.
    assert hourly.quote_per_account == pooled.quote_per_account


# --------------------------------------------------------------------------------------------
# The fence.
# --------------------------------------------------------------------------------------------

def test_fence_reports_both_directions_of_dispersion(fence):
    surface = {"symbols": {
        "WIDE": {"pooled_median_spread_pts": 100.0, "hours": {
            "1": {"status": "MEASURED", "p50": 600.0, "n_nonzero": 900},   # 6x undercharged
            "2": {"status": "MEASURED", "p50": 100.0, "n_nonzero": 900},   # fine
            "3": {"status": "MEASURED", "p50": 10.0, "n_nonzero": 900},    # 10x OVERcharged
            "4": {"status": "UNMEASURED", "n_nonzero": 2},
        }},
    }}
    rows = fence.scan_symbols(surface)
    assert {r["hour"] for r in rows} == {1, 3}, "only material cells, and both directions"
    by_hour = {r["hour"]: r for r in rows}
    assert by_hour[1]["direction"] == "UNDERCHARGED"
    assert by_hour[3]["direction"] == "OVERCHARGED", (
        "the overcharged direction raises no alert anywhere else on this desk and must be "
        "reported with equal weight -- it is how a real edge dies silently")
    assert rows[0]["hour"] == 3, "sorted by severity, which is symmetric in the ratio"


def test_fence_severity_survives_an_extreme_ratio(fence):
    """`round(ratio, 2)` is 0.0 below 200x cheaper, and sorting on it divided by zero."""
    surface = {"symbols": {"X": {"pooled_median_spread_pts": 1000.0, "hours": {
        "1": {"status": "MEASURED", "p50": 1.0, "n_nonzero": 900},
    }}}}
    rows = fence.scan_symbols(surface)
    assert rows and rows[0]["severity"] == pytest.approx(1000.0)


def test_fence_never_renders_unmeasured_or_missing_as_ok(fence):
    from libs.ops.fence_exit import fence_exit

    for bad in ("UNMEASURED", "SURFACE-MISSING", "STALE", "COST-BASIS-MISMATCH"):
        assert fence_exit(bad, fence._PASSING) != 0, f"{bad} must fail closed (L1.28a)"
    for good in ("OK", "DISPERSED", "NOT-READABLE-HERE"):
        assert fence_exit(good, fence._PASSING, scanned=1, of="cells") == 0
    # A passing status over an EMPTY measurement set must still fail (L1.57).
    assert fence_exit("OK", fence._PASSING, scanned=0, of="cells") != 0


def test_fence_flags_a_mispriced_live_sleeve(fence, monkeypatch):
    """The end-to-end property: a LIVE sleeve charged 2.5x under its own fill bars must fail."""
    surface = {"symbols": {"USDZAR": {
        "pooled_median_spread_pts": 329.0, "tick_size": 1e-5, "contract_size": 1e5,
        "hours": {"1": {"status": "MEASURED", "p50": 1496.0, "n_nonzero": 1700}}}}}
    sleeves = {"sleeves": {"USDZAR.overnight_gap_decay.asia": {
        "status": "LIVE",
        "identity": {"symbol": "USDZAR", "family": "overnight_gap_decay", "params": {}},
        "cost_fields": {"spread_per_lot": 808.0}}}}
    # Replay 400 fills at hour 1, each recording a 2,028-pt spread on its own bar.
    monkeypatch.setattr(fence, "fill_bars", lambda *a, **k: ([1] * 400, [2028.0] * 400))
    findings, unresolved = fence.scan_sleeves(surface, sleeves)
    assert not unresolved
    assert len(findings) == 1
    f = findings[0]
    assert f["ratio"] == pytest.approx(2.51, abs=0.01)
    assert f["direction"] == "UNDERCHARGED"
    assert f["fill_bar_p50_pts"] == 2028.0
    assert f["surface_hour_p50_pts"] == 1496.0, (
        "the unconditional hour cell is published beside the fill-bar truth so the SELECTION "
        "effect stays visible -- 1496 reads as 1.85x and would have been silent")


def test_fence_refuses_a_sleeve_it_cannot_price_rather_than_passing_it(fence, monkeypatch):
    surface = {"symbols": {"USDZAR": {
        "pooled_median_spread_pts": 329.0, "tick_size": 1e-5, "contract_size": 1e5,
        "hours": {"1": {"status": "UNMEASURED", "n_nonzero": 4}}}}}
    sleeves = {"sleeves": {"S": {
        "status": "LIVE",
        "identity": {"symbol": "USDZAR", "family": "overnight_gap_decay", "params": {}},
        "cost_fields": {"spread_per_lot": 808.0}}}}
    # Too few PRICED fill bars: the tape says nothing, so no verdict may be issued.
    monkeypatch.setattr(fence, "fill_bars", lambda *a, **k: ([1] * 400, [2028.0] * 3))
    findings, unresolved = fence.scan_sleeves(surface, sleeves)
    assert not findings
    assert len(unresolved) == 1 and "too few priced fill bars" in unresolved[0]["why"]

    # And an unreachable tape is a refusal, never an implicit pass.
    monkeypatch.setattr(fence, "fill_bars", lambda *a, **k: None)
    findings, unresolved = fence.scan_sleeves(surface, sleeves)
    assert not findings and len(unresolved) == 1


def test_fence_measures_the_fill_bar_not_the_signal_bar(fence):
    """`run_backtest` fills at `searchsorted(idx, sig.time) + 1`. Off by one bar = off by ~2x.

    Measuring the signal bar overstates this defect (hour 00 is far wider than hour 01 on the
    ZAR crosses); measuring it that way is how a fence cries wolf until it gets switched off.
    """
    src = (_ROOT / "scripts/check_cost_surface.py").read_text("utf-8")
    assert "int(i) + 1" in src, "the fence must replay the engine's own +1 fill offset"


# --------------------------------------------------------------------------------------------
# WIRING -- these fail if the capability is built but nothing runs it (III.16).
# --------------------------------------------------------------------------------------------

def test_fence_is_mapped_to_a_principle_and_the_reference_resolves():
    """Mapped is not enough -- the reference must RESOLVE, or it is a claim that cannot be cashed.

    A bare `check_cost_surface` ref reads as correct in review and lands in
    `broken_references`, because bare names resolve as max_audit FUNCTIONS and this fence is a
    standalone script. That near-miss is the whole reason this generator reports both directions.
    """
    src = (_ROOT / "scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"scripts/check_cost_surface.py"' in src, (
        "a fence with no principle is unvoted complexity; map it BY PATH")

    matrix = _ROOT / "data/enforcement_matrix.json"
    if not matrix.exists():
        pytest.skip("enforcement_matrix.json not built on this box")
    rows = json.loads(matrix.read_text("utf-8"))["matrix"]
    l15 = next(r for r in rows if r["principle"] == "L1.5")
    assert "scripts/check_cost_surface.py" in l15["enforced_by"]
    assert not any("cost_surface" in b for b in l15["broken_references"]), (
        "a broken reference enforces nothing while reading as coverage")


def test_producer_and_fence_are_both_scheduled():
    manifest = (_ROOT / "ops/crontab.manifest").read_text("utf-8")
    assert "desks/mt5/research/cost_surface.py" in manifest, \
        "the surface must be rebuilt on a schedule"
    assert "scripts/check_cost_surface.py" in manifest, "an unscheduled fence never runs (L1.49)"
    # ORDER IS LOAD-BEARING: a fence that runs before its own producer reads yesterday's surface.
    assert manifest.index("desks/mt5/research/cost_surface.py >>") < \
        manifest.index("scripts/check_cost_surface.py >>"), \
        "the surface must be rebuilt BEFORE the fence reads it"


def test_the_engine_still_exposes_the_hour_path():
    """If someone removes `spread_pts`, the surface becomes a report nothing consumes."""
    src = (_DESK / "mt5desk/engine.py").read_text("utf-8")
    assert "spread_pts" in src, (
        "Costs.from_symbol must keep the hour-conditioned override, or the cost surface is "
        "measurement with no consumer -- the exact producer/consumer collapse it was built to end")


def test_the_committed_surface_is_real_and_measured():
    """The artifact must exist, be non-empty, and carry measured cells -- not just be built."""
    p = _DESK / "data/cost_surface.json"
    if not p.exists():
        pytest.skip("cost_surface.json not present on this box")
    rep = json.loads(p.read_text("utf-8"))
    assert rep["schema"] == "cost-surface-1"
    assert rep["n_symbols"] > 0
    measured = sum(1 for r in rep["symbols"].values()
                   for c in r["hours"].values() if c["status"] == "MEASURED")
    assert measured > 0, "a surface with zero measured cells is UNMEASURED, not built"


def test_numpy_pandas_imported_for_lints():
    """Keep the module-level imports honest -- they are used by the frame builder above."""
    assert np is not None and pd is not None
