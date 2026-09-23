"""THE DAILY CLOCK WAS DECLARED, NEVER FED -- AND FINER BARS TURNED IT OFF (Tier-1 audit G17).

`state_vector_build.ASSET_CLOCKS` has always declared six clocks, `weekly` and `daily` among
them, and `BAR_SUFFIXES` searched `M5, M15, H1` FINEST FIRST and handed the winner to every one
of them. Finest-first is right about granularity and silent about coverage, and the silence had
a price.

MEASURED IN THIS TREE 2026-09-09, before the change:

    XAUUSD_M5.parquet    20,000 bars over    73 days   <- chosen for every clock
    XAUUSD_H1.parquet    49,964 bars over 2,181 days   <- never consulted once M5 existed

    XAUUSD@weekly   15 weekly bars, needs 120   REFUSED
    XAUUSD@daily    73 daily  bars, needs 250   REFUSED

`XAUUSD@daily` is the state vector's `global` state -- the book-wide regime `pf_allocator`'s
world draw reads. So DOWNLOADING FINER BARS FOR GOLD SILENTLY TURNED OFF THE BOOK-WIDE REGIME,
and the artifact recorded it as a perfectly honest gap that nobody connected to the download.

Two halves are pinned here. `refresh_tail` now DERIVES `<SYM>_D1.parquet` from the symbol's own
H1 file, so the daily tier has a file of its own instead of depending on which intraday parquet
a symbol happens to have acquired this week; and the loader picks its file PER CLOCK rather than
once per symbol. The second half is what fixes the measurement above; the first is what stops the
same accident arriving from the other direction.

AND THE NEW GUARD IS A REFUSAL, NOT A PERMISSION. A D1 file that could be selected made `H4` and
`H1` reachable from daily bars, and neither had any guard -- `resample("1h")` over daily closes
returns the daily stamps wearing an hourly label. `_series` now refuses a series coarser than the
clock it is asked for, which is the M15 guard's rule applied one tier up.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import refresh_tail as rt  # noqa: E402
import research.state_vector_build as svb  # noqa: E402

from libs.regime.asset_state import CLOCKS, observations_at  # noqa: E402


def _bars(n: int, freq: str, start: str = "2020-01-01") -> pd.DataFrame:
    """A bar frame with the columns the store actually carries."""
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    rng = np.random.default_rng(11)
    close = 100 * np.exp(np.cumsum(rng.normal(scale=0.0006, size=n)))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": np.arange(n, dtype=float),
                         "spread": np.full(n, 12.0), "real_volume": np.zeros(n)}, index=idx)


# ---------------------------------------------------------------- the derived daily series
def test_the_daily_bar_is_an_aggregate_and_not_a_sample(tmp_path, monkeypatch) -> None:
    """open=first, high=max, low=min, close=last -- a resample that took `.last()` on all four
    would write a daily bar whose range is one hour wide."""
    monkeypatch.setattr(rt, "OUT", tmp_path)
    h1 = _bars(24 * 30, "h")
    h1.to_parquet(tmp_path / "TEST_H1.parquet")

    status = rt.derive_series("TEST", "D1")
    assert status.startswith("29 bars"), status          # 30 days, the last one still forming
    d1 = pd.read_parquet(tmp_path / "TEST_D1.parquet")

    day = h1.loc["2020-01-02"]
    got = d1.loc[pd.Timestamp("2020-01-02", tz="UTC")]
    assert got["open"] == pytest.approx(day["open"].iloc[0])
    assert got["close"] == pytest.approx(day["close"].iloc[-1])
    assert got["high"] == pytest.approx(day["high"].max())
    assert got["low"] == pytest.approx(day["low"].min())
    # A level averages, a flow sums. Carrying `spread` as a sum would report 288 points of
    # spread on a 12-point instrument.
    assert got["spread"] == pytest.approx(12.0)
    assert got["tick_volume"] == pytest.approx(day["tick_volume"].sum())


def test_the_bar_still_forming_is_dropped_the_same_way_a_fetched_one_is(tmp_path,
                                                                       monkeypatch) -> None:
    """The source tail is the last CLOSED hourly bar, so its calendar day is almost always still
    open. A daily bar whose close is really 14:00's close is not late, it is WRONG -- and it
    would be silently corrected tomorrow with no reader able to tell it had ever been wrong."""
    monkeypatch.setattr(rt, "OUT", tmp_path)
    # Ten full days plus a part-day: fifteen hours into the eleventh.
    out = rt.resample_bars(_bars(24 * 10 + 15, "h"), "D1")
    assert len(out) == 10, "the in-progress day was written as if it had closed"
    assert out.index.max() == pd.Timestamp("2020-01-10", tz="UTC")


def test_a_symbol_with_no_source_is_reported_and_never_counted_as_derived(tmp_path,
                                                                         monkeypatch) -> None:
    """Absence is never a pass (L1.28a): a skip that reads as success is how the frozen
    sub-hourly series lasted weeks."""
    monkeypatch.setattr(rt, "OUT", tmp_path)
    monkeypatch.setattr(rt, "DERIVED_MANIFEST", tmp_path / "derived_series.json")
    _bars(24 * 400, "h").to_parquet(tmp_path / "HASBARS_H1.parquet")

    doc = rt.derive_all(["HASBARS", "NOBARS"])
    assert "HASBARS_D1" in doc["series"]
    assert doc["skipped"]["NOBARS_D1"] == "no-H1-source"
    assert (tmp_path / "derived_series.json").exists()
    assert not (tmp_path / "NOBARS_D1.parquet").exists()


def test_a_derived_series_is_rebuilt_and_never_fetched(tmp_path, monkeypatch) -> None:
    """Our D1 bar is stamped 00:00 UTC because it aggregates UTC-stamped H1 bars; the terminal's
    own D1 bar is stamped at the BROKER's day start, 21:00 or 22:00 UTC. A fetch into this file
    would append a second bar for every day at a different instant, and the dedupe -- which keys
    on the timestamp -- would keep both."""
    monkeypatch.setattr(rt, "OUT", tmp_path)
    monkeypatch.setattr(rt, "DERIVED_MANIFEST", tmp_path / "derived_series.json")
    _bars(24 * 400, "h").to_parquet(tmp_path / "HASBARS_H1.parquet")
    rt.derive_all(["HASBARS"])

    # `refresh_symbol` would otherwise reach for the terminal here; `mt5` is None in this
    # container, so a fetch attempt is unambiguous -- it cannot silently succeed.
    got = rt.refresh_symbol("HASBARS", "D1")
    assert "rebuilt, not fetched" in got, got
    assert "H1" in got


def test_the_refresher_loads_and_answers_2_without_a_terminal(tmp_path, monkeypatch) -> None:
    """`daily_cycle._refresh_bars` does `import refresh_tail` before it calls anything, so a bare
    top-level `import MetaTrader5` killed the VPS step on the IMPORT rather than on the terminal
    check it was written to survive. rc=2 is the answer the cycle already tolerates."""
    monkeypatch.setattr(rt, "OUT", tmp_path)
    monkeypatch.setattr(rt, "DERIVED_MANIFEST", tmp_path / "derived_series.json")
    _bars(24 * 400, "h").to_parquet(tmp_path / "HASBARS_H1.parquet")
    assert rt.mt5 is None, "this container has no MetaTrader5; the guard is what is under test"
    assert rt.main() == 2
    # ...and the derivation, which needs no terminal, still ran.
    assert (tmp_path / "HASBARS_D1.parquet").exists()


def test_the_derived_timeframe_reuses_the_sweeps_own_bar_table() -> None:
    """Two tables of bar lengths is how a D1 file ends up with H4 bars in it."""
    from research.orthogonal_sweep import _resample_rule
    assert rt._rule("D1") == _resample_rule("D1") == "1440min"


# ---------------------------------------------------------------- the loader picks per clock
def test_the_loader_chooses_the_file_that_can_actually_serve_the_clock(tmp_path,
                                                                      monkeypatch) -> None:
    """THE MEASURED DEFECT, reproduced at scale. A short fine file and a long coarse one, exactly
    the shape of XAUUSD_M5 against XAUUSD_H1."""
    monkeypatch.setattr(svb, "UNI", tmp_path)
    svb._bars.cache_clear()
    # 73 days of M5 -- what the store actually held for gold -- and 3 years of H1.
    _bars(21_000, "5min", start="2026-06-01").to_parquet(tmp_path / "GOLDY_M5.parquet")
    _bars(24 * 1000, "h", start="2023-01-01").to_parquet(tmp_path / "GOLDY_H1.parquet")

    fast = svb._close("GOLDY", "M5")
    slow = svb._close("GOLDY", "daily")
    assert fast is not None and slow is not None
    assert fast.index.to_series().diff().median() == pd.Timedelta("5min")
    assert slow.index.to_series().diff().median() == pd.Timedelta("1h")
    # The refusal that used to happen is gone, and it is gone because a real file answered.
    assert observations_at(fast, "daily") < CLOCKS["daily"]["min_obs"]
    assert observations_at(slow, "daily") >= CLOCKS["daily"]["min_obs"]


def test_no_clock_named_still_means_the_finest_file(tmp_path, monkeypatch) -> None:
    """An event shock window is measured in MINUTES and an edge-search index match wants the
    finest bars there are; neither names a clock, and neither may be handed daily bars."""
    monkeypatch.setattr(svb, "UNI", tmp_path)
    svb._bars.cache_clear()
    _bars(21_000, "5min", start="2026-06-01").to_parquet(tmp_path / "GOLDY_M5.parquet")
    _bars(24 * 1000, "h", start="2023-01-01").to_parquet(tmp_path / "GOLDY_H1.parquet")
    s = svb._close("GOLDY")
    assert s is not None and s.index.to_series().diff().median() == pd.Timedelta("5min")


def test_a_clock_no_file_can_serve_still_refuses_on_real_bars(tmp_path, monkeypatch) -> None:
    """Nothing here loosens a floor. With only hourly bars the intraday tiers still refuse, and
    the series handed back is the finest one so the shortfall is reported against real bars."""
    monkeypatch.setattr(svb, "UNI", tmp_path)
    svb._bars.cache_clear()
    _bars(24 * 400, "h").to_parquet(tmp_path / "ONLYH1_H1.parquet")
    s = svb._close("ONLYH1", "M15")
    assert s is not None, "a refusal must be reported against bars, not as 'no bars at all'"
    assert observations_at(s, "M15") is None, "hourly bars must not serve a fifteen-minute clock"


def test_a_symbol_with_only_a_daily_file_still_gets_its_daily_state(tmp_path,
                                                                   monkeypatch) -> None:
    """The point of putting D1 in BAR_SUFFIXES: a symbol whose only file is daily is no longer
    'no bars for X' on every clock. The loader handles the absence of everything finer."""
    monkeypatch.setattr(svb, "UNI", tmp_path)
    svb._bars.cache_clear()
    assert "D1" in svb.BAR_SUFFIXES and svb.BAR_SUFFIXES[-1] == "D1", (
        "D1 is the coarsest suffix and must be searched last")
    _bars(900, "D").to_parquet(tmp_path / "DAILYONLY_D1.parquet")
    assert observations_at(svb._close("DAILYONLY", "daily"), "daily") == 900
    assert observations_at(svb._close("DAILYONLY", "weekly"), "weekly") > 120
    # ...and it does NOT thereby acquire an hourly regime it has no bars for.
    assert observations_at(svb._close("DAILYONLY", "H1"), "H1") is None
    assert observations_at(svb._close("DAILYONLY", "H4"), "H4") is None


def test_an_absent_symbol_is_still_no_bars_at_all(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(svb, "UNI", tmp_path)
    svb._bars.cache_clear()
    assert svb._close("GHOST", "daily") is None
    assert svb._close("GHOST") is None


# ---------------------------------------------------------------- the coarseness guard
@pytest.mark.parametrize("clock", ["H1", "H4", "M15", "M5"])
def test_daily_bars_may_not_wear_an_intraday_label(clock: str) -> None:
    """`resample("1h").last().dropna()` over daily closes returns the daily stamps with an hourly
    label, and `H4`/`H1` had no guard at all until a D1 file could be selected."""
    daily = _bars(900, "D")["close"]
    assert observations_at(daily, clock) is None


@pytest.mark.parametrize("clock", ["weekly", "daily"])
def test_daily_bars_serve_the_clocks_they_are_bars_of(clock: str) -> None:
    assert observations_at(_bars(900, "D")["close"], clock) > 0


def test_an_hourly_file_still_serves_the_hourly_clock() -> None:
    """The predicate is `>` and not `>=` on purpose: an H1 file is exactly an H1 clock's bar.
    Spelling this with `needs_finer_than` would have refused every hourly fit on the desk."""
    hourly = _bars(24 * 400, "h")["close"]
    assert observations_at(hourly, "H1") == CLOCKS["H1"]["max_obs"]
    assert observations_at(hourly, "H4") > 0
    assert observations_at(hourly, "daily") > 0


def test_every_clock_declares_the_bar_it_is_built_from() -> None:
    """A clock with no `bar` silently opts out of the guard, which is how H4 and H1 had none."""
    for clock, spec in CLOCKS.items():
        assert spec.get("bar"), f"{clock} declares no bar length"
        assert pd.Timedelta(spec["bar"]) > pd.Timedelta(0), clock
