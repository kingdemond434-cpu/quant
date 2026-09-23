"""Forward evidence is the one thing that cannot be recovered later, and it was
wired to the most fragile component in the system.

`shadow_forward.fetch_h1` imported MetaTrader5 directly, so the entire shadow
record was hostage to a Windows box with a logged-in terminal. The Fusion switch
paused that terminal and the daily cycle has been failing on ModuleNotFoundError
ever since -- losing days of bars that no later run can re-evaluate.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import h1_source as H  # noqa: E402

NOW = datetime.now(UTC)


def frame(n=200, end=None, tz="UTC"):
    """Always built in UTC, then converted or stripped — building directly in a
    foreign tz makes pandas argue with the tz-aware `end` rather than testing
    anything about this module."""
    end = (end or NOW).replace(minute=0, second=0, microsecond=0)
    idx = pd.date_range(end=end.replace(tzinfo=None), periods=n, freq="h", tz="UTC")
    df = pd.DataFrame({"open": 2000.0, "high": 2002.0, "low": 1998.0,
                       "close": 2001.0, "tick_volume": 10.0,
                       "spread": 16.0, "real_volume": 0.0}, index=idx)
    if tz is None:
        df.index = df.index.tz_localize(None)
    elif tz != "UTC":
        df.index = df.index.tz_convert(tz)
    return df


def bars(n=200, end=None, source="TEST"):
    return H.Bars(H._normalise(frame(n, end)), source,
                  NOW.isoformat(timespec="seconds"))


# ------------------------------------------------- shadow needs no broker

def test_the_module_does_not_import_MetaTrader5_at_module_level():
    """THE COUPLING THAT STOPPED SHADOW. A top-level import makes every caller
    require a Windows terminal."""
    src = (_DESK / "research" / "h1_source.py").read_text(encoding="utf-8")
    head = src.split("def from_mt5")[0]
    assert "import MetaTrader5" not in head


def test_shadow_forward_no_longer_imports_MetaTrader5_directly():
    """THE COUPLING IS AT MODULE SCOPE, AND SO IS THE ASSERTION.

    This read the WHOLE file for the substring, so it went red when
    `broker_utc_offset_hours` gained an optional, fully-guarded call-site import
    (`try: import MetaTrader5 ... except Exception: <fall back to 0.0>`). That import cannot
    reproduce the outage this test exists to prevent -- shadow keeps running without a terminal,
    it just records no offset -- so the red was a false positive measuring the wrong quantity,
    and a fence that is red for a reason nobody will fix is a fence people learn to ignore.
    Scoped to the module head like its sibling above, and the guard on the call-site import is
    asserted explicitly so the optional form cannot silently become a hard one.
    """
    src = (_DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    head = src.split("def ")[0]
    assert "import MetaTrader5" not in head, "module-level import re-welds shadow to a terminal"
    assert "from research.h1_source import fetch_h1" in src
    # every occurrence must sit inside a try, i.e. be optional
    for chunk in src.split("import MetaTrader5")[:-1]:
        assert chunk.rstrip().endswith("try:"), "MetaTrader5 must stay an optional import"


def test_mt5_tick_age_cannot_become_a_broker_timezone_offset() -> None:
    """A weekend quote is old information, never a -29h clock conversion."""
    class StaleTick:
        time = 0

    class MT5:
        @staticmethod
        def symbol_info_tick(_symbol):
            return StaleTick()

    assert H.broker_utc_offset_hours(MT5()) == 0.0


def test_the_cache_alone_can_serve_shadow(monkeypatch, tmp_path):
    """The property that matters: bars with no terminal, no login, no account."""
    monkeypatch.setattr(H, "from_mt5", lambda s, t: None)
    p = tmp_path / "XAUUSD_H1.parquet"
    frame().to_parquet(p)
    monkeypatch.setattr(H, "UNI", tmp_path)
    b = H.fetch_h1("XAUUSD", NOW - timedelta(days=5))
    assert b is not None and b.source.startswith("CACHE")


def test_nothing_working_returns_None_rather_than_an_empty_frame(monkeypatch, tmp_path):
    """None is a condition the caller must handle as NO DATA. An empty frame
    would replay as a quiet market."""
    monkeypatch.setattr(H, "from_mt5", lambda s, t: None)
    monkeypatch.setattr(H, "UNI", tmp_path)
    monkeypatch.setattr(H, "EXTRA_SOURCES", [])
    assert H.fetch_h1("XAUUSD", NOW - timedelta(days=5)) is None


# ------------------------------------------------------------- the order

def test_the_broker_feed_wins_when_available(monkeypatch, tmp_path):
    monkeypatch.setattr(H, "from_mt5", lambda s, t: bars(source="MT5"))
    frame().to_parquet(tmp_path / "XAUUSD_H1.parquet")
    monkeypatch.setattr(H, "UNI", tmp_path)
    assert H.fetch_h1("XAUUSD", NOW - timedelta(days=5)).source == "MT5"


def test_a_registered_source_beats_the_cache(monkeypatch, tmp_path):
    """A live feed beats a stale file; the cache is last because it is always
    available and would otherwise always win."""
    monkeypatch.setattr(H, "from_mt5", lambda s, t: None)
    monkeypatch.setattr(H, "EXTRA_SOURCES", [lambda s, t: bars(source="HTTP:test")])
    frame().to_parquet(tmp_path / "XAUUSD_H1.parquet")
    monkeypatch.setattr(H, "UNI", tmp_path)
    assert H.fetch_h1("XAUUSD", NOW - timedelta(days=5)).source == "HTTP:test"


def test_authoritative_fusion_cache_beats_registered_proxy_when_requested(
    monkeypatch, tmp_path,
):
    monkeypatch.setattr(H, "from_mt5", lambda s, t: None)
    monkeypatch.setattr(H, "EXTRA_SOURCES", [lambda s, t: bars(source="HTTP:test")])
    frame().to_parquet(tmp_path / "XAUUSD_H1.parquet")
    (tmp_path / "broker_info.json").write_text(
        '{"is_fusion": true}', encoding="utf-8",
    )
    monkeypatch.setattr(H, "UNI", tmp_path)

    chosen = H.fetch_h1(
        "XAUUSD", NOW - timedelta(days=5), prefer_promotion_authority=True,
    )

    assert chosen is not None
    assert chosen.source.startswith("CACHE")
    assert chosen.promotion_authority is True


def test_a_raising_source_does_not_take_the_chain_with_it(monkeypatch, tmp_path):
    def boom(s, t):
        raise RuntimeError("feed exploded")
    monkeypatch.setattr(H, "from_mt5", boom)
    frame().to_parquet(tmp_path / "XAUUSD_H1.parquet")
    monkeypatch.setattr(H, "UNI", tmp_path)
    monkeypatch.setattr(H, "EXTRA_SOURCES", [])
    assert H.fetch_h1("XAUUSD", NOW - timedelta(days=5)) is not None


# ------------------------------------------ absence of bars is not absence of signals

def test_a_source_ending_before_the_window_does_not_cover_it():
    """THE CORRUPTION THIS PREVENTS. Replaying an uncovered window records "no
    trades" for days there was no data, which is indistinguishable from a
    strategy standing aside and inflates every rate the promoter computes."""
    old = bars(end=NOW - timedelta(days=10))
    ok, why = old.covers(NOW - timedelta(days=2))
    assert not ok and "NO DATA, not a quiet market" in why


def test_a_source_ending_mid_window_is_refused_for_the_tail():
    """Enough history to start before the window, but ending days short of now:
    the tail is NO DATA, and replaying it would score those days as quiet."""
    b = bars(n=1000, end=NOW - timedelta(days=3))
    ok, why = b.covers(NOW - timedelta(days=30))
    assert not ok and "not an absence of signals" in why


def test_a_covering_source_passes():
    ok, why = bars(n=500).covers(NOW - timedelta(days=3))
    assert ok and "covers the window" in why


def test_an_empty_source_covers_nothing():
    ok, why = H.Bars(H._normalise(frame(0)), "X", "now").covers(NOW)
    assert not ok and "no bars at all" in why


def test_staleness_is_measured_from_the_freshest_bar():
    monday = datetime(2026, 8, 17, 12, tzinfo=UTC)
    assert H.trading_lag_hours(pd.Timestamp(monday - timedelta(hours=20)), monday) > 6
    assert H.trading_lag_hours(pd.Timestamp(monday), monday) == 0


def test_closed_weekend_does_not_manufacture_staleness():
    friday_close = datetime(2026, 8, 21, 23, tzinfo=UTC)
    saturday = datetime(2026, 8, 22, 20, tzinfo=UTC)
    assert H.trading_lag_hours(pd.Timestamp(friday_close), saturday) == 0


# -------------------------------------------------------------- the stamp

def test_every_fetch_carries_its_provenance():
    s = bars(source="HTTP:yfinance/XAUUSD=X").stamp()
    assert s["bar_source"] == "HTTP:yfinance/XAUUSD=X"
    assert "bars_freshest" in s and "bars_stale" in s


def test_the_shadow_ledger_writes_the_stamp_onto_every_row():
    """A trade replayed on a broker feed and one on free bars are not the same
    evidence, and an expectancy across them averages two different games."""
    src = (_DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert "_stamp = bars.stamp()" in src and "**_stamp" in src


def test_mixed_sources_are_flagged_rather_than_averaged():
    m = H.SourceMix()
    m.add("MT5", 40)
    m.add("HTTP:yfinance/XAUUSD=X", 12)
    assert not m.homogeneous
    assert "MIXED SOURCES" in m.render() and "two different games" in m.render()


def test_one_source_reports_clean():
    m = H.SourceMix()
    m.add("MT5", 40)
    assert m.homogeneous and "all from MT5" in m.render()


# ------------------------------------------------------------ normalisation

def test_a_naive_index_is_refused():
    """A naive index silently shifts every session boundary by the server
    offset, which is the whole strategy on a session-range book."""
    df = frame(tz=None)
    with pytest.raises(ValueError, match="timezone-naive"):
        H._normalise(df)


def test_a_non_utc_index_is_converted_not_stripped():
    df = frame(tz="America/New_York")
    out = H._normalise(df)
    assert str(out.index.tz) in ("UTC", "America/New_York")


def test_missing_columns_are_filled_so_the_engine_can_index_them():
    df = frame()[["open", "high", "low", "close"]]
    out = H._normalise(df)
    assert list(out.columns) == H._COLUMNS


def test_bars_are_sorted():
    df = frame().sample(frac=1.0, random_state=0)
    assert H._normalise(df).index.is_monotonic_increasing


# ------------------------------------------------------- the free feed

def test_the_free_feed_is_not_enabled_by_default():
    """Turning it on is a decision about evidence quality: a ledger silently
    switching feeds mid-record averages two different games."""
    assert H.from_yfinance not in H.EXTRA_SOURCES


def test_an_unmapped_symbol_is_refused_rather_than_approximated():
    """A broker's XAUUSD, a futures front month and a spot cross differ by
    carry, session and roll."""
    assert H.from_yfinance("SOMETHING_ODD", NOW) is None


def test_the_free_feed_names_itself_as_a_different_series():
    import inspect
    doc = inspect.getdoc(H.from_yfinance)
    assert "different series" in doc.lower()
