"""88% of the universe was unreadable because five downloaders dropped one keyword.

MEASURED 2026-08-27. `desks/mt5/data/universe/*_H1.parquet` is the ground the whole shadow and
forward chain reads. 173 of its 197 files carried a TIMEZONE-NAIVE index, so `_normalise` raised,
`fetch_h1` swallowed the exception in its `except Exception: continue`, and the caller was told
"no H1 source returned bars" -- a statement about the MARKET -- when the truth was a malformed
file. Nobody investigates a market fact, so the desk's universal-ground mandate (LAWS L1.61) ran
on 24 symbols while the registry advertised 197, and the two `overnight_gap_decay` certificates --
the only ones outside session_range_breakout, against a largest_family_share of 0.87 -- sat at
NO_DATA and never started a forward clock.

THE CAUSE WAS ONE KEYWORD. MT5 `rates["time"]` is UNIX EPOCH SECONDS. Every producer under
research/ and mt5desk/ calls `pd.to_datetime(..., unit="s", utc=True)`; the five bulk downloaders
under desks/mt5/scripts/ omitted `utc=True`, which keeps the identical instants and merely drops
the label. Restoring it is provenance, not an assumption -- and the session structure confirms it:
the naive files' Friday tail (21,22,23) and Monday head (0,1,2) match the tz-aware files exactly,
which a server-offset shift could not.

THE GENERIC GUARD STAYS STRICT. A naive index from an arbitrary feed really is ambiguous; the
restoration is confined to the one directory whose provenance is known, and it is RECORDED on the
Bars so a reader can tell a declared clock from a reconstructed one.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
DESK = ROOT / "desks" / "mt5"


@pytest.fixture
def h1():
    sys.path.insert(0, str(DESK))
    sys.path.insert(0, str(DESK / "research"))
    spec = importlib.util.spec_from_file_location(
        "_t_h1_source", DESK / "research" / "h1_source.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _frame(tz: str | None) -> pd.DataFrame:
    """Bars built from EPOCH SECONDS -- the same source MT5 serves."""
    epoch = [1_756_000_000 + 3600 * i for i in range(48)]
    idx = pd.to_datetime(epoch, unit="s", utc=True)
    if tz is None:
        idx = idx.tz_localize(None)
    return pd.DataFrame(
        {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05,
         "tick_volume": 10, "spread": 2, "real_volume": 0}, index=idx)


def test_a_naive_cache_file_is_read_not_refused(h1, monkeypatch, tmp_path) -> None:
    _frame(None).to_parquet(tmp_path / "EURZAR_H1.parquet")
    monkeypatch.setattr(h1, "UNI", tmp_path)
    bars = h1.from_cache("EURZAR", datetime(2020, 1, 1, tzinfo=UTC))
    assert bars is not None, "the file the whole universe is made of was refused"
    assert bars.n == 48
    assert bars.df.index.tz is not None
    assert bars.naive_index_restored is True


def test_restoring_the_label_does_not_move_a_single_instant(h1, monkeypatch, tmp_path) -> None:
    """The safety argument in one assertion: same epoch in, same epoch out."""
    aware = _frame("UTC")
    _frame(None).to_parquet(tmp_path / "USDZAR_H1.parquet")
    monkeypatch.setattr(h1, "UNI", tmp_path)
    bars = h1.from_cache("USDZAR", datetime(2020, 1, 1, tzinfo=UTC))
    assert bars is not None
    assert list(bars.df.index) == list(aware.index), (
        "the restored index shifted -- a session-boundary move is exactly what the naive guard "
        "exists to prevent, and this restoration must never become the hole in it")


def test_an_already_stamped_file_is_untouched(h1, monkeypatch, tmp_path) -> None:
    _frame("UTC").to_parquet(tmp_path / "XAUUSD_H1.parquet")
    monkeypatch.setattr(h1, "UNI", tmp_path)
    bars = h1.from_cache("XAUUSD", datetime(2020, 1, 1, tzinfo=UTC))
    assert bars is not None
    assert bars.naive_index_restored is False


def test_the_generic_guard_still_refuses_a_naive_frame_from_anywhere_else(h1) -> None:
    """The positive control: the restoration must be scoped to the cache directory only."""
    with pytest.raises(ValueError, match="timezone-naive"):
        h1._normalise(_frame(None))


def test_every_bulk_downloader_stamps_utc() -> None:
    """The producer half. A reader fix alone leaves the next download naive again."""
    offenders = []
    for path in sorted((DESK / "scripts").glob("*.py")):
        text = path.read_text("utf-8", errors="replace")
        for line in text.splitlines():
            if 'to_datetime(df["time"], unit="s"' in line and "utc=True" not in line:
                offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, (
        "a bulk downloader converts MT5 epoch seconds without utc=True; every file it writes "
        f"will be refused by h1_source._normalise: {offenders}")
