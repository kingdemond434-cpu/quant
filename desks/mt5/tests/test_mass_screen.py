"""The mass screen: exact agreement with the engine, honest windows, honest multiplicity, wiring.

Synthetic bars only; no network. The one property everything else rests on is the first test: the
screen's per-trade R for a cell equals `engine.run_backtest`'s R on the signals the SEALED
gauntlet's build path gets from the registered family -- so what the screen measured is what the
judge will replay.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mass_screen as MS  # noqa: E402
from mt5desk import families_orthogonal as FO  # noqa: E402
from mt5desk import mass_screen_rules as MR  # noqa: E402
from mt5desk.engine import Costs, rollovers_between, run_backtest  # noqa: E402

META = {"contract_size": 100000.0, "tick_size": 1e-5, "tick_value": 1.0,
        "median_spread_pts": 10.0, "swap_long": 0.0, "swap_short": 0.0}


def bars(n_days: int = 900, seed: int = 7, plant_hour: int | None = None,
         plant: float = 0.0) -> pd.DataFrame:
    """Weekday hourly bars; optionally a planted drift in the 4 bars after `plant_hour`."""
    idx = pd.date_range("2019-01-01", periods=n_days * 24, freq="h", tz="UTC")
    idx = idx[idx.weekday < 5]
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, 0.001, len(idx))
    if plant_hour is not None:
        hrs = np.asarray(idx.hour)
        for lag in range(1, 5):
            r[lag:][hrs[:-lag] == plant_hour] += plant
    close = 1.1 * np.exp(np.cumsum(r))
    opn = np.r_[close[0], close[:-1]]
    wig = np.abs(rng.normal(0.0, 0.0004, len(idx)))
    df = pd.DataFrame({"open": opn, "close": close,
                       "high": np.maximum(opn, close) + wig,
                       "low": np.minimum(opn, close) - wig,
                       "tick_volume": 100.0}, index=idx)
    df.index.name = "time"
    return df


def test_screen_r_equals_engine_r_on_the_gauntlets_own_build_path() -> None:
    df = bars(400)
    P = MS.Prepared("SYN", df, META, {})
    params = {"feat": "ret_4", "op": "gt", "thr": 1.0, "direction": -1, "hold": 8,
              "stop_atr": 1.0, "cond_feat": "", "cond_lo": -MR.OPEN_BOUND,
              "cond_hi": MR.OPEN_BOUND, "hour": -1, "weekday": -1, "leader": "", "atr_n": 20,
              "gv": MR.GRAMMAR_VERSION}
    fn = FO.ORTHOGONAL_FAMILIES["mass_screen_thresh"]
    h1 = MR._h1(df)
    sigs = fn(h1, side=1, **params)                  # exactly how build_cell calls a family
    res = run_backtest(h1, sigs, Costs.from_symbol(META))
    assert len(res.trades) == len(sigs) > 100        # thinning == single-position discipline
    cond = {k: params[k] for k in ("feat", "op", "thr")}
    kept = MR.thin(np.flatnonzero(P.mask(cond)), 8)
    kept = kept[kept <= P.n - 2 - 8]
    vi = MS.VARIANTS.index((-1, 1.0))
    screen_r = P.R1[8][vi, kept]
    engine_r = np.array([t.r_multiple for t in res.trades[:len(kept)]])
    assert np.allclose(screen_r, engine_r, rtol=0, atol=1e-9)
    # and the daily series is the sealed judge's own (`external_gauntlet.daily_series`, copied
    # verbatim: a dict keyed by entry date, so the LAST trade of a day is the day's value)
    trades = res.trades[:len(kept)]
    theirs = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in trades},
                       dtype=float).groupby(level=0).sum()
    days = P.entry_day[kept]
    st = MS.cell_stats(P.R1[8], P.R3[8], kept, days)
    assert st is not None and int(st["n_days"][0]) == len(theirs)
    assert st["mean"][vi] == pytest.approx(float(theirs.mean()), abs=1e-9)
    assert len(theirs) < len(trades)            # the case where sum and last-wins differ


def test_swap_nights_match_the_engine() -> None:
    rng = np.random.default_rng(1)
    base = pd.Timestamp("2021-03-01", tz="UTC").value
    a = base + rng.integers(0, 400 * 86400, 500) * 10**9
    b = a + rng.integers(0, 6 * 86400, 500) * 10**9
    ours = MS.nights_between(a, b)
    theirs = [rollovers_between(pd.Timestamp(x, tz="UTC"), pd.Timestamp(y, tz="UTC"))
              for x, y in zip(a, b, strict=True)]
    assert np.array_equal(ours, np.array(theirs))


def test_bh_matches_the_repo_procedure_with_the_untestable_padded() -> None:
    from libs.validation.fdr import benjamini_hochberg
    rng = np.random.default_rng(3)
    p = np.r_[rng.uniform(0, 1e-4, 30), rng.uniform(0, 1, 5000)]
    m = 20_000
    listed = p[p <= 0.05]
    cut = MS.bh_threshold(listed, m, 0.05)
    ref = benjamini_hochberg(np.r_[p, np.ones(m - p.size)], alpha=0.05)
    assert cut == pytest.approx(ref.threshold)
    assert int((listed <= cut).sum()) == ref.n_rejected


def test_training_window_never_reaches_the_walk_forward_or_lockbox_region() -> None:
    P = MS.Prepared("SYN", bars(600), META, {})
    for cond in ({"grammar": "clock", "hour": 3}, {"feat": "z_24", "op": "lt", "thr": -1.0}):
        for h in (1, 24):
            full = MR.thin(np.flatnonzero(P.mask(cond)), h)
            full = full[full <= P.n - 2 - h]
            kept, wf_day = MS.cell_days(P, full, h)
            assert kept.size
            assert (kept + 1 + h < P.cut).all()          # outcome ends before the cut
            assert (P.entry_day[kept] < wf_day).all()   # never inside the WF test region
            uniq = np.unique(P.entry_day[full])
            assert wf_day == uniq[MS.wf_start_rank(len(uniq))]


def test_the_mirrored_constants_match_the_sealed_gauntlet() -> None:
    src = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    consts = {n.targets[0].id: n.value.value for n in ast.parse(src).body
              if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
              and isinstance(n.value, ast.Constant)}
    assert consts["WF_SPLITS"] == MS.WF_SPLITS
    assert consts["COST_SCENARIO"] == MS.COST_STRESS
    assert "test_size=max(20, len(arr) // 6)" in src
    assert (MS.WF_MIN_TEST, MS.WF_TEST_DIV, MS.MIN_DAYS) == (20, 6, 60)
    assert "len(d) >= 60" in src


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    frames: dict[str, pd.DataFrame] = {}
    monkeypatch.setattr(MR, "load_bars", lambda s, tf="H1": frames.get(s))
    monkeypatch.setattr(MS, "_load_leaders", lambda syms: {})
    monkeypatch.setattr(MS, "universe_meta", lambda: dict.fromkeys(frames, META))
    yield tmp_path, frames
    R.set_path(None)


def test_a_planted_edge_is_forwarded_and_charged_and_reaches_the_docket(sandbox) -> None:
    tmp, frames = sandbox
    frames["SYNA"] = bars(900, seed=11, plant_hour=10, plant=0.0006)
    doc = MS.run(budget_s=600, workers=1, symbols=["SYNA"], out_dir=tmp / "out")
    assert doc["status"] == "MEASURED"
    assert doc["run"]["cells"] > 50_000
    assert doc["forward"]["created"] >= 1
    fams = {r["family"] for r in doc["forwarded_sample"]}
    assert "mass_screen_clock" in fams
    top = doc["forwarded_sample"][0]
    assert top["n_days"] >= MS.MIN_DAYS and top["mean_r_x3"] > 0
    # every screened cell is a trial, per grammar, in the ledger the lifetime count reads
    rows = [json.loads(x) for x in (tmp / "out" / "MASS_SCREEN_TRIALS.jsonl").read_text()
            .splitlines()]
    assert sum(r["cells_screened"] for r in rows) == doc["run"]["cells"]
    from libs.research import experiment_ledger as EL
    total, by_fam = EL._mass_screen_counts(tmp / "out" / "MASS_SCREEN_TRIALS.jsonl")
    assert total == doc["run"]["cells"] and "mass_screen_clock" in by_fam
    # the registry door -> the docket feed the merge writes into external_survivors.json
    from libs.moat import docket_feed
    fed, census = docket_feed.feed()
    assert census["status"] == "MEASURED" and census["refused_unstamped"] == 0
    ours = [r for r in fed if r["family"].startswith("mass_screen_")]
    assert ours and ours[0]["origin"] == "mass_screen"
    # ... and each one is buildable by the gauntlet: registered, no refused modifier keys
    from mt5desk import cell_modifiers
    fn = FO.ORTHOGONAL_FAMILIES[ours[0]["family"]]
    kwargs, mods = cell_modifiers.split(fn, ours[0]["params"])
    assert not mods and cell_modifiers.refusal(mods) is None
    assert fn(frames["SYNA"], side=1, **kwargs)
    # a second run forwards nothing new (structural dedup), and still charges its trials
    doc2 = MS.run(budget_s=600, workers=1, symbols=["SYNA"], out_dir=tmp / "out")
    assert doc2["forward"]["created"] == 0
    rows2 = (tmp / "out" / "MASS_SCREEN_TRIALS.jsonl").read_text().splitlines()
    assert len(rows2) > len(rows)


def test_pure_noise_forwards_nothing(sandbox) -> None:
    tmp, frames = sandbox
    frames["NOISE"] = bars(700, seed=5)
    doc = MS.run(budget_s=600, workers=1, symbols=["NOISE"], out_dir=tmp / "o2")
    assert doc["run"]["cells"] > 50_000
    assert doc["forward"]["created"] == 0


def test_dry_run_trials_are_not_charged(tmp_path) -> None:
    from libs.research import experiment_ledger as EL
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({"family": "mass_screen_cond", "cells_screened": 10}) + "\n"
                 + json.dumps({"family": "mass_screen_cond", "cells_screened": 99,
                               "dry_run": True}) + "\n")
    assert EL._mass_screen_counts(p) == (10, {"mass_screen_cond": 10})
    assert EL._mass_screen_counts(tmp_path / "absent.jsonl") == (0, {})


def test_default_parameter_sweeps_set_the_grammar_aside() -> None:
    import breadth_sweep
    ok, blocked = breadth_sweep.default_families()
    for g in MR.GRAMMARS:
        assert f"mass_screen_{g}" not in ok
        assert f"mass_screen_{g}" in blocked


def test_the_leg_is_wired_into_the_hourly_cycle() -> None:
    import hourly_cycle as HC

    from libs.research import layers
    assert HC.department_of("mass_screen") == "discovery"
    assert HC.LEG_BUDGET_SEC["mass_screen"] > HC.MASS_SCREEN_BUDGET_S
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("mass_screen", mass_screen)' in src
    assert src.index('_costed("mass_screen"') < src.index('_costed("merge_docket"')
    assert layers.LEG_LAYER.get("mass_screen") == "prediction"


def test_workers_are_derived_from_measurement() -> None:
    w, info = MS.derive_workers()
    assert w >= 1 and info["workers"] == w
    assert "basis" in info
