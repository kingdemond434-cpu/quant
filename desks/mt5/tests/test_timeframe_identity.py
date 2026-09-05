"""THE CHART IS PART OF THE CELL, and this file is the fence that keeps it that way.

WHAT IT GUARDS AGAINST, and why it is worse than the bug it replaces. The desk hunted H1 and
nothing else (principal 2026-09-05: "m1 m5 m15 m30 h1 h4 d1 all possible every type of mechanism
n chart for all always ... this was a serious flaw we had abt the h1 only"). Widening the sweep to
the full ladder is one line. Widening it WITHOUT putting the chart into cell identity is a silent
corruption of the canon:

  * `external_gauntlet`'s daily-series cache is CONTENT-ADDRESSED. Two cells that hash the same
    serve each other's returns.
  * the certificate key is derived from cell identity, so a certificate minted on one chart is
    claimed by the other.
  * `shadow_forward`'s clock key decides which forward series a row accrues into, so two charts
    sharing a key splice their evidence and either can claim the other's fourteen days.

Every number in such a record stays internally consistent, so no gate, no census and no report can
see it -- which makes it strictly worse than the H1-only limitation it would arrive with.

TWO THINGS ARE PINNED HERE AT ONCE, and they pull against each other:

  1. AN M5 CELL AND AN H1 CELL ARE DIFFERENT IDENTITIES, everywhere identity is computed.
  2. AN H1 CELL'S IDENTITY IS BYTE-IDENTICAL TO WHAT IT HAS ALWAYS BEEN. Naming H1 explicitly
     would rename every id, cache entry, certificate and running clock this desk holds. So H1 is
     spelled by its ABSENCE -- the same asymmetry `sleeve_key` already applies to direction.

The regression pins below hold (2) by recomputing the OLD expressions inline. They are not
decoration: a change that starts writing `@H1` would pass every "they differ" assertion in this
file and orphan the entire canon.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import external_gauntlet  # noqa: E402
import orthogonal_sweep  # noqa: E402
import shadow_forward  # noqa: E402
import sleeve_registry  # noqa: E402
from research.frontier_identity import cell_id  # noqa: E402

from mt5desk import families, families_orthogonal  # noqa: E402
from mt5desk.family_inputs import strip_identity_keys  # noqa: E402
from mt5desk.universe_registry import (  # noqa: E402
    REFERENCE_TIMEFRAME,
    TIMEFRAMES,
    min_bars_for,
    scale_bars,
    timeframe_minutes,
)

SYM = "XAUUSD"
FAM = "vol_transition"
PARAMS_H1: dict = {"lookback": 96}
PARAMS_M5: dict = {"lookback": 96, "timeframe": "M5"}


def _frame(n: int, minutes: int) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq=f"{minutes}min", tz="UTC")
    base = pd.Series(range(n), index=idx, dtype=float) * 0.01 + 100.0
    return pd.DataFrame({"open": base, "high": base + 0.5, "low": base - 0.5,
                         "close": base + 0.1, "tick_volume": 10.0,
                         "spread": 2.0, "real_volume": 0.0}, index=idx)


# ------------------------------------------------------------------ the ladder is one ladder

def test_the_ladder_is_the_full_seven_and_h1_is_its_reference() -> None:
    assert TIMEFRAMES == ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
    assert REFERENCE_TIMEFRAME == "H1"
    assert [timeframe_minutes(tf) for tf in TIMEFRAMES] == [1, 5, 15, 30, 60, 240, 1440]
    with pytest.raises(KeyError):
        # A chart the desk does not know must RAISE, never default to 60: a silent fallback to
        # hourly is the exact collapse this whole file exists to prevent, one layer lower down.
        timeframe_minutes("M3")


def test_a_bar_count_written_for_h1_rescales_to_the_same_market_time() -> None:
    assert scale_bars(120, "H1") == 120, "H1 must be the identity, or every hourly cell moves"
    assert scale_bars(120, "M5") == 120 * 12
    assert scale_bars(120, "D1") == 5
    assert scale_bars(1, "D1") >= 1, "a span shorter than one bar floors at one, never zero"


def test_a_history_floor_is_the_same_market_time_on_every_chart() -> None:
    """A flat bar floor would have emptied the DAILY lane on every symbol, in silence.

    3,000 bars is four months of H1 and twelve YEARS of D1; six years of daily bars is ~1,560.
    """
    assert min_bars_for("H1") == 3000, "the admission floor itself has not moved"
    assert min_bars_for("D1") < 1560, (
        "six years of D1 is ~1,560 bars -- a floor above that admits no daily chart anywhere")
    assert min_bars_for("M1") == 3000 * 60


# ------------------------------------------------------------- the bar clock is not resampled

def test_a_fine_chart_is_not_silently_collapsed_to_h1() -> None:
    """`_h1` resampled EVERY frame (infer_freq is None on any real FX series, so its H1 early-out
    never fired). An M15 parquet of 100,000 bars came back as 25,001 H1 bars -- an M15 cell
    producing H1 signals under an identity claiming M15."""
    m5 = _frame(2000, 5)
    out = families._h1(m5)
    assert len(out) == len(m5)
    assert families.bar_minutes(out) == 5
    assert families.bars_per_day(out) == 288


def test_an_hourly_frame_comes_back_exactly_as_it_always_did() -> None:
    h1 = _frame(2000, 60)
    out = families._h1(h1)
    legacy = h1.resample("1h").agg({"open": "first", "high": "max", "low": "min",
                                    "close": "last", "tick_volume": "sum"}).dropna()
    assert out.index.equals(legacy.index)
    for col in ("open", "high", "low", "close"):
        assert (out[col].to_numpy() == legacy[col].to_numpy()).all()


def test_an_irregular_frame_is_still_resampled_to_h1() -> None:
    """The one case the old behaviour was right for: a series with no regular bar spacing."""
    ragged = _frame(400, 60)
    ragged = ragged.iloc[[0, 3, 4, 17, 18, 40, 91, 92, 150, 151, 152, 300]]
    assert families.bar_minutes(ragged) is None
    out = families._h1(ragged)
    assert (out.index.to_series().diff().dropna() >= pd.Timedelta(hours=1)).all()


# ---------------------------------------------------- identity: M5 and H1 can never be one cell

def test_the_cell_name_carries_the_chart() -> None:
    h1 = cell_id({"sym": SYM, "family": FAM, "params": PARAMS_H1})
    m5 = cell_id({"sym": SYM, "family": FAM, "params": PARAMS_M5})
    assert h1 != m5
    assert "@M5" in m5 and "@" not in h1
    # The chart is honoured whether it rides in params or on the row, because both producers
    # exist: the orthogonal sweep writes both, and `build_cell` puts it on the cell.
    assert cell_id({"sym": SYM, "family": FAM, "timeframe": "M5",
                    "params": PARAMS_H1}) != h1


def test_an_h1_cell_name_is_byte_identical_to_the_pre_ladder_spelling() -> None:
    """Regression pin for rule (2). If this ever fails the whole canon has been renamed."""
    payload = json.dumps(PARAMS_H1, sort_keys=True, separators=(",", ":"), default=str)
    legacy = f"{SYM}.{FAM}.p={hashlib.sha256(payload.encode()).hexdigest()[:16]}"
    assert cell_id({"sym": SYM, "family": FAM, "params": PARAMS_H1}) == legacy
    legacy_short = f"{SYM}.{FAM}.rr=1.5_wb=1"
    assert cell_id({"sym": SYM, "family": FAM,
                    "params": {"rr": 1.5, "wait_bars": 1}}) == legacy_short


def test_the_content_addressed_cache_cannot_serve_one_chart_for_the_other(
        tmp_path, monkeypatch) -> None:
    """THE TRAP, pinned: a shared key means two cells SERVE EACH OTHER'S RETURNS."""
    import numpy as np
    h1_key = external_gauntlet._cache_key(SYM, FAM, PARAMS_H1, "2026-09-04")
    m5_key = external_gauntlet._cache_key(SYM, FAM, PARAMS_M5, "2026-09-04")
    assert h1_key != m5_key

    # MONKEYPATCH, NOT ASSIGNMENT: a bare `external_gauntlet.CACHE_DIR = tmp_path` outlives this
    # test and points every later test in the session at a deleted directory.
    monkeypatch.setattr(external_gauntlet, "CACHE_DIR", tmp_path)
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    series = pd.Series(np.arange(5, dtype=float), index=idx)
    external_gauntlet.cache_save(h1_key, series, series)
    assert external_gauntlet.cache_load(h1_key) is not None
    assert external_gauntlet.cache_load(m5_key) is None, (
        "the M5 cell just loaded the H1 cell's daily series -- every gate downstream would be "
        "judging the wrong returns, consistently, with nothing able to see it")


def test_a_family_pinned_to_a_chart_cannot_collide_with_its_hourly_twin() -> None:
    """`lvc_asia_london` carries no `timeframe` in params at all -- it is pinned in code -- so a
    key built from params alone would give it the SAME address as an H1 cell of that name."""
    pinned = external_gauntlet._cache_key(SYM, "lvc_asia_london", {}, "2026-09-04")
    hourly = external_gauntlet._cache_key(SYM, "vol_transition", {}, "2026-09-04")
    assert pinned != hourly
    assert external_gauntlet.timeframe_of({}, "lvc_asia_london") == "M5"
    assert external_gauntlet.timeframe_of({}, "vol_transition") == "H1"


def test_the_forward_clock_key_and_frozen_identity_carry_the_chart() -> None:
    h1_key = shadow_forward.sleeve_key(SYM, "asia", dict(PARAMS_H1), FAM)
    m5_key = shadow_forward.sleeve_key(SYM, "asia", dict(PARAMS_M5), FAM)
    assert h1_key != m5_key and "@M5" in m5_key
    # Rule (2): a long H1 clock's key is what it has always been, or every running clock is
    # orphaned against its own ledger, registry row and shadow state.
    assert h1_key == f"{SYM}.{FAM}.asia#lookback=96"

    ident = dict(family=FAM, symbol=SYM, direction="LONG", selector="asia",
                 code="c", cost="k", data_venue="MT5:X", behaviour="b")
    h1_id = sleeve_registry.identity(timeframe="H1", params=PARAMS_H1, **ident)
    m5_id = sleeve_registry.identity(timeframe="M5", params=PARAMS_M5, **ident)
    assert h1_id["sleeve_id"] != m5_id["sleeve_id"]


def test_the_chart_names_an_input_and_is_stripped_before_the_family_is_called() -> None:
    """No family takes `timeframe`; it names the CHART TO LOAD, like `peer_symbol` names a
    symbol to load. Left in, every family raises TypeError and a whole chart reads unbuildable."""
    assert "timeframe" not in strip_identity_keys(FAM, PARAMS_M5)
    assert strip_identity_keys(FAM, PARAMS_M5) == PARAMS_H1


# ------------------------------------------------- every mechanism, and where it cannot speak

def test_wall_clock_rescaling_is_the_identity_on_the_reference_chart() -> None:
    for fam in families_orthogonal.WALL_CLOCK_PARAMS:
        assert families_orthogonal.timeframe_overrides(fam, "H1") == {}, (
            f"{fam} would be scheduled with a rewritten parameter on H1, which moves an "
            f"existing cell for no reason and changes its identity")


def test_a_wall_clock_parameter_holds_its_market_time_across_the_ladder() -> None:
    """`family_carry`'s 120-bar hold is FIVE DAYS of financing. Left alone on M5 it is ten hours
    and collects no rollover at all -- a quiet-regime momentum sleeve wearing the word carry."""
    assert families_orthogonal.timeframe_overrides("carry", "M5")["hold_bars"] == 120 * 12
    assert families_orthogonal.timeframe_overrides("carry", "D1")["hold_bars"] == 5


def test_bar_relative_windows_are_left_alone_on_purpose() -> None:
    """The z-score/ATR/correlation windows are what make seven charts seven MECHANISMS. Scale
    them to a fixed wall-clock span and the M1 cell and the D1 cell compute the same number."""
    for fam, names in families_orthogonal.WALL_CLOCK_PARAMS.items():
        assert "lookback" not in names and "atr_n" not in names, (
            f"{fam} declares a statistical window as wall-clock; that collapses the ladder back "
            f"to one chart at seven times the compute")


def test_every_declared_wall_clock_parameter_exists_on_its_family() -> None:
    import inspect
    for fam, names in families_orthogonal.WALL_CLOCK_PARAMS.items():
        fn = families_orthogonal.ORTHOGONAL_FAMILIES.get(fam)
        assert fn is not None, f"{fam} is not a registered family"
        params = inspect.signature(fn).parameters
        for name in names:
            assert name in params, f"{fam} has no parameter {name!r} to rescale"
            assert isinstance(params[name].default, int), (
                f"{fam}.{name} has no integer default to rescale from")


def test_every_timeframe_restriction_is_a_real_chart_and_carries_its_reason() -> None:
    """A silent exclusion is the same defect as a silent zero, one indirection further out."""
    for fam, (charts, why) in families_orthogonal.FAMILY_TIMEFRAMES.items():
        assert fam in families_orthogonal.ORTHOGONAL_FAMILIES, f"{fam} is not a family"
        assert charts, f"{fam} is declared runnable nowhere"
        assert set(charts) <= set(TIMEFRAMES), f"{fam} names a chart off the ladder: {charts}"
        assert len(why) > 60, f"{fam} is restricted without a reason worth reading"


def test_most_families_run_on_every_chart() -> None:
    """The default is ALL SEVEN. A restriction is an exception with a reason, never the norm --
    if this ever inverts, the ladder has been narrowed one family at a time."""
    unrestricted = [f for f in families_orthogonal.ORTHOGONAL_FAMILIES
                    if f not in families_orthogonal.FAMILY_TIMEFRAMES]
    assert len(unrestricted) > len(families_orthogonal.FAMILY_TIMEFRAMES)
    assert families_orthogonal.timeframe_domain("vol_transition") == TIMEFRAMES
    assert families_orthogonal.timeframe_refusal("vol_transition", "M1") is None
    refusal = families_orthogonal.timeframe_refusal("hedging_demand_close", "D1")
    assert refusal and "stamp-hour" in refusal


def test_a_daily_decision_family_takes_one_decision_a_day_on_every_chart() -> None:
    """`hour == 0` alone is one decision per day only on an HOURLY chart: on M1 the first hour
    of a day holds sixty bars that all satisfy it, and this family rests an order at each."""
    m1 = _frame(60 * 24 * 40, 1)
    h1 = _frame(24 * 40, 60)
    kw = {"active_month": 1, "side_bias": 1}
    per_day_m1 = len(families_orthogonal.family_calendar_month(m1, **kw))
    per_day_h1 = len(families_orthogonal.family_calendar_month(h1, **kw))
    assert per_day_m1 <= per_day_h1 + 1, (
        f"M1 emitted {per_day_m1} signals against H1's {per_day_h1} for a family whose own "
        f"docstring promises one decision per UTC day")


def test_a_certificate_on_a_chart_the_gateway_cannot_read_never_becomes_a_live_row(
        monkeypatch) -> None:
    """The one place the ladder could have cost real money.

    `gateway.run_family_sleeves` calls `copy_rates_from_pos(sym, TIMEFRAME_H1, 0, 400)` in every
    one of its four `family_market` paths. A matured M5 certificate promoted through that path
    would hold a live position computed from HOURLY bars -- a strategy nobody certified, under
    the name of one that was, with every artifact agreeing. `executables` is the boundary that
    already exists for "the family resolves but the executor cannot run it"; the chart is the
    same question and gets the same answer: a named `executor_gap` on the clock, never a LIVE row.
    """
    from mt5desk import executables

    monkeypatch.setattr(executables, "population_of", lambda fam: "hunt16")
    assert executables.executor_gap("anything") is None
    assert executables.gateway_can_execute("anything") is True

    gap = executables.executor_gap("anything", "M5")
    assert gap and "M5" in gap and "TIMEFRAME_H1" in gap
    assert executables.gateway_can_execute("anything", "M5") is False
    # The scalp lane is untouched -- it has its own executor and its own timeframe resolution.
    assert executables.GATEWAY_FAMILY_TIMEFRAMES == ("H1",)


# ------------------------------------------------------ THE FENCE: the sweep may never re-narrow

def test_the_sweep_enumerates_every_chart_the_registry_offers(tmp_path, monkeypatch) -> None:
    """THE FENCE (behavioural arm). Break it by narrowing the ladder, by hardcoding a chart in
    `timeframes_of`, or by going back to a `*_H1.parquet` enumeration: all three make this fail.

    PROVEN NON-VACUOUS 2026-09-05, because a fence nobody has watched fire is a comment. In a
    scratch copy `timeframes_of` was reverted to `return ["H1"]` -- the H1-only shape this change
    removed -- and this test failed with `assert ['H1'] == ['M1', 'M5', ..., 'D1']`.
    """
    universe = tmp_path / "universe"
    universe.mkdir()
    for tf in TIMEFRAMES:
        _frame(400, timeframe_minutes(tf)).to_parquet(universe / f"{SYM}_{tf}.parquet")
    monkeypatch.setattr(orthogonal_sweep, "UNIVERSE", universe)

    meta = {SYM: {"asset_class": "Commodities", "bars": 400,
                  "timeframes": list(TIMEFRAMES)}}
    assert orthogonal_sweep.timeframes_of(SYM, meta) == list(TIMEFRAMES)

    pairs = orthogonal_sweep.sweep_pairs(meta)
    assert {tf for _, tf in pairs} == set(TIMEFRAMES), (
        "the sweep reached only some charts. H1-only hunting is the flaw this change exists to "
        "remove and the principal's standing order is that it never returns")
    assert all(sym == SYM for sym, _ in pairs)

    # A chart the registry claims but whose parquet is absent is NOT swept: the files get the
    # last word, so a registry that over-claims cannot send the sweep at a file that is not there.
    (universe / f"{SYM}_M1.parquet").unlink()
    assert "M1" not in orthogonal_sweep.timeframes_of(SYM, meta)


def test_the_fence_the_sweeps_loop_iterates_symbol_chart_pairs() -> None:
    """THE FENCE (structural arm). The behavioural arm above proves the ENUMERATION is wide; this
    proves the LOOP consumes it. A revert to `for sym in symbols:` -- the exact shape this change
    replaced -- would leave `sweep_pairs` intact and passing while the hunt narrowed back to one
    chart, which is how a widened search quietly becomes decoration.

    PROVEN NON-VACUOUS 2026-09-05: in a scratch copy the loop was reverted to
    `for _pair_i, sym in enumerate(symbols): tf = 'H1'` and this test failed on `assert []`.
    """
    tree = ast.parse((DESK / "research" / "orthogonal_sweep.py").read_text("utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "sweep")
    loops = [n for n in ast.walk(fn) if isinstance(n, ast.For)]
    pair_loops = [
        n for n in loops
        if isinstance(n.target, ast.Tuple) and len(n.target.elts) == 2
        and isinstance(n.iter, ast.Call)
        and getattr(n.iter.func, "id", "") == "enumerate"
        and any(getattr(a, "id", "") == "pairs" for a in n.iter.args)
    ]
    assert pair_loops, (
        "sweep() no longer walks (symbol, chart) pairs. Every family must be hunted on every "
        "chart the registry offers -- principal 2026-09-05, 'this was a serious flaw we had abt "
        "the h1 only', and 'this should never revert to old'")

    # And the bars it loads must be asked for BY CHART. `_bars(sym)` alone is the H1 default,
    # which is precisely the narrowing this fence exists to catch.
    bar_calls = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_bars"]
    assert bar_calls, "sweep() loads no bars at all"
    assert all(len(c.args) >= 2 for c in bar_calls), (
        "a `_bars(symbol)` call inside the sweep silently reads the H1 parquet, so that family "
        "would be hunted on H1 while its cell identity claims another chart")
