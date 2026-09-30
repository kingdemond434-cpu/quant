"""The deepener may not splice daily bars onto an intraday chart, nor rewrite a bar it found.

Both properties are load-bearing for the same reason: `data/universe/*.parquet` is the desk's
entire research input and the sealed judge reads it with no error handling.

  * THE DENSE FLOOR. Fusion serves M30/H1/H4 back to 1997, but before ~2019 it holds only DAILY
    bars and MetaTrader renders each of them as ONE bar on every chart. Taking that depth would
    hand a session mechanism twenty years of "M30" bars that are daily closes, which is the
    cheapest way there is to manufacture an edge that cannot exist.
  * PREPEND ONLY. A bar already on disk is one the judge may have judged and `refresh_tail` may
    own the live end of. Rewriting it would make this organ race two other writers; adding only
    strictly-older bars cannot.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research.deepen_universe import (  # noqa: E402
    BAR_COLUMNS,
    deepen_one,
    dense_frontier,
    in_blackout,
    walk_back,
)

_RATE = np.dtype([("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"),
                  ("close", "<f8"), ("tick_volume", "<u8"), ("spread", "<i4"),
                  ("real_volume", "<u8")])


def _days(start: date, n_days: int, per_day: int) -> Counter[date]:
    out: Counter[date] = Counter()
    for i in range(n_days):
        d = start + timedelta(days=i)
        if d.weekday() < 5:
            out[d] = per_day
    return out


def test_dense_frontier_cuts_a_daily_derived_prefix() -> None:
    """Twenty months at one bar a day, then twenty at forty-eight: the cut lands between them."""
    days = _days(date(2018, 1, 1), 600, 1)
    days |= _days(date(2019, 9, 1), 600, 48)
    cut = dense_frontier(days, "M30")
    assert cut is not None
    assert date(2019, 9, 1) <= cut <= date(2019, 11, 1), cut


def test_dense_frontier_keeps_a_wholly_dense_series() -> None:
    assert dense_frontier(_days(date(2022, 1, 3), 900, 48), "M30") is None


def test_dense_frontier_is_self_calibrating_for_a_share_cfd() -> None:
    """A 6.5-hour US equity runs 13 M30 bars a day and is DENSE; a flat nominal would refuse it."""
    assert dense_frontier(_days(date(2021, 3, 8), 1200, 13), "M30") is None


def test_dense_frontier_never_trims_a_daily_chart() -> None:
    assert dense_frontier(_days(date(1997, 10, 10), 9000, 1), "D1") is None


def test_blackout_covers_the_gold_placement_windows() -> None:
    assert in_blackout(datetime(2026, 9, 24, 4, 0, tzinfo=UTC)) == "03:40-04:20Z"
    assert in_blackout(datetime(2026, 9, 24, 10, 0, tzinfo=UTC))
    assert in_blackout(datetime(2026, 9, 24, 14, 0, tzinfo=UTC))
    assert in_blackout(datetime(2026, 9, 24, 21, 0, tzinfo=UTC)) == ""


class _FakeMT5:
    """A terminal that serves `total` M30 bars and caps its chart cache at `maxbars`."""

    def __init__(self, total: int, maxbars: int, start: datetime) -> None:
        self._all = np.array(
            [(int((start + timedelta(minutes=30 * i)).timestamp()), 1.0, 1.0, 1.0, 1.0, 1, 1, 0)
             for i in range(total)], dtype=_RATE)
        self._maxbars = maxbars
        self.TIMEFRAME_M30 = 30
        self.calls = 0

    def terminal_info(self) -> object:
        return type("TI", (), {"maxbars": self._maxbars, "name": "fake", "build": 0})()

    def last_error(self) -> tuple[int, str]:
        return (0, "ok")

    def copy_rates_from_pos(self, _sym: str, _tf: int, start: int,
                            count: int) -> np.ndarray:
        self.calls += 1
        served = self._all[max(0, len(self._all) - self._maxbars):]
        lo = max(0, len(served) - start - count)
        return served[lo:len(served) - start]

    def copy_rates_from(self, _sym: str, _tf: int, when: datetime,
                        count: int) -> np.ndarray:
        self.calls += 1
        served = self._all[max(0, len(self._all) - self._maxbars):]
        cut = int(when.timestamp())
        older = served[served["time"] <= cut]
        return older[-count:] if len(older) else older[:0]


def test_walk_back_names_the_terminal_cap_as_ours() -> None:
    """300,000 bars behind a 100,000-bar cache: the CLIENT is what stopped, and it must say so.

    The last request comes back empty exactly as it would from a venue with no more history, so
    a walk that lands within one chunk-anchor of the cap is named MAXBARS regardless. One bar is
    lost to the anchor overlap between the two chunks, which the dedupe removes.
    """
    mt5 = _FakeMT5(total=300_000, maxbars=100_000, start=datetime(2020, 1, 1, tzinfo=UTC))
    rows, stop = walk_back(mt5, "EURUSD", mt5.TIMEFRAME_M30, 100_000)
    assert stop == "MAXBARS"
    assert len(rows) == 99_999
    assert len(np.unique(rows["time"])) == len(rows)


def test_walk_back_names_a_venue_end_as_theirs() -> None:
    mt5 = _FakeMT5(total=60_000, maxbars=100_000, start=datetime(2020, 1, 1, tzinfo=UTC))
    rows, stop = walk_back(mt5, "EURUSD", mt5.TIMEFRAME_M30, 100_000)
    assert stop == "venue-end"
    assert len(rows) == 60_000


@pytest.fixture()
def _store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import research.deepen_universe as mod
    monkeypatch.setattr(mod, "UNIVERSE", tmp_path)
    return tmp_path


def test_deepen_prepends_and_never_rewrites_a_bar_it_found(_store: Path) -> None:
    mt5 = _FakeMT5(total=40_000, maxbars=100_000, start=datetime(2021, 1, 1, tzinfo=UTC))
    served = pd.to_datetime(mt5._all["time"], unit="s", utc=True)
    held = pd.DataFrame(
        {c: np.full(5_000, 7.0 if c in {"open", "high", "low", "close"} else 7)
         for c in BAR_COLUMNS}, index=served[-5_000:])
    held.index.name = "time"
    held = held.astype({"tick_volume": "uint64", "spread": "int32", "real_volume": "uint64"})
    path = _store / "EURUSD_M30.parquet"
    held.to_parquet(path)
    # What is ON DISK is the reference: parquet has no second-resolution timestamp, so a frame
    # built at `datetime64[s]` reads back at `[ms]` on current pandas/pyarrow.
    held = pd.read_parquet(path)

    res = deepen_one(mt5, "EURUSD", "M30", dry_run=False)
    assert res["status"] == "DEEPENED", res
    after = pd.read_parquet(path)
    assert len(after) == 40_000
    assert after.index.min() == served[0]
    # every bar that was already on disk is byte-identical, values and dtypes alike
    pd.testing.assert_frame_equal(after.iloc[-5_000:], held)


def test_deepen_is_idempotent(_store: Path) -> None:
    mt5 = _FakeMT5(total=9_000, maxbars=100_000, start=datetime(2021, 1, 1, tzinfo=UTC))
    served = pd.to_datetime(mt5._all["time"], unit="s", utc=True)
    held = pd.DataFrame({c: np.ones(1_000) for c in BAR_COLUMNS}, index=served[-1_000:])
    held.index.name = "time"
    held = held.astype({"tick_volume": "uint64", "spread": "int32", "real_volume": "uint64"})
    (_store / "EURUSD_M30.parquet").parent.mkdir(parents=True, exist_ok=True)
    held.to_parquet(_store / "EURUSD_M30.parquet")

    first = deepen_one(mt5, "EURUSD", "M30", dry_run=False)
    assert first["status"] == "DEEPENED"
    second = deepen_one(mt5, "EURUSD", "M30", dry_run=False)
    assert second["status"] == "AT_FLOOR", second
    assert len(pd.read_parquet(_store / "EURUSD_M30.parquet")) == 9_000


def test_a_file_already_at_the_cap_costs_the_terminal_nothing(_store: Path) -> None:
    """The free skip, and the assertion that matters is that NO terminal call was made.

    M1 and M5 hold ~100,000 rows on nearly every symbol, and their first walk is what makes the
    first sweep expensive -- the terminal rebuilds a whole timeseries from its .hcc history. A
    file already holding at least `maxbars` bars cannot gain one, and the parquet footer says so
    for free.
    """
    mt5 = _FakeMT5(total=9_000, maxbars=1_000, start=datetime(2021, 1, 1, tzinfo=UTC))
    served = pd.to_datetime(mt5._all["time"], unit="s", utc=True)
    held = pd.DataFrame({c: np.ones(2_000) for c in BAR_COLUMNS}, index=served[-2_000:])
    held.index.name = "time"
    held.to_parquet(_store / "EURUSD_M30.parquet")

    res = deepen_one(mt5, "EURUSD", "M30", dry_run=False)
    assert res["status"] == "AT_FLOOR", res
    assert res["file_rows"] == 2_000
    assert mt5.calls == 0, f"{mt5.calls} terminal call(s) made for a chart that cannot gain one"


def test_deepen_leaves_a_symbol_with_no_file_to_its_own_producer(_store: Path) -> None:
    mt5 = _FakeMT5(total=9_000, maxbars=100_000, start=datetime(2021, 1, 1, tzinfo=UTC))
    assert deepen_one(mt5, "NOPE", "M30", dry_run=False)["status"] == "NO_FILE"
    assert not list(_store.glob("*.parquet"))


def test_the_deepener_is_on_its_daily_step_clock_and_has_no_orphan_wrapper() -> None:
    """#104 re-score: the registry declared `invoked:scripts/check_desk_module_drift.py` (a fence
    that only LISTS the path) while the real runner is `daily_cycle:deepen_bars`, and
    `ops/run_deepen_universe.cmd` was scheduled by nothing."""
    repo = _DESK.parents[1]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from desks.mt5.ops import components

    assert components.daily_step_imports().get("deepen_universe") == "deepen_bars"
    reg = components.build_registry(repo)
    spec = next(s for s in reg.all()
                if s.code_paths == ("desks/mt5/research/deepen_universe.py",))
    assert spec.schedule == "daily_cycle:deepen_bars"
    assert spec.cadence_s == 86_400
    assert not (repo / "ops" / "run_deepen_universe.cmd").exists()
