"""The forward clocks were welded shut by a ROUTE string sitting in a VENUE field.

Measured 2026-08-26: `shadow_forward` froze `data_venue = str(bars.source)`. `source` names how
the bars reached the process -- "MT5:FusionMarkets-Live" from a live terminal, "CACHE:<file>"
from the parquet cache of THOSE SAME broker bars. On this Linux box the terminal is never up, so
every run drifted, every drift is terminal, and the 14-day forward window never survived a day:
195 IDENTITY BROKEN lines, `data_venue` named in 195/195.

These tests pin BOTH directions, because the fix is only correct if it is stricter:
an outage must NOT break a clock, and a genuine venue change MUST.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import h1_source as H  # noqa: E402
from research import sleeve_registry as R  # noqa: E402

NOW = datetime.now(UTC)


def _bars(source: str, venue: str) -> H.Bars:
    idx = pd.date_range(end=NOW.replace(minute=0, second=0, microsecond=0, tzinfo=None),
                        periods=50, freq="h", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                       "tick_volume": 1.0, "spread": 1.0, "real_volume": 0.0}, index=idx)
    return H.Bars(H._normalise(df), source, NOW.isoformat(timespec="seconds"), venue=venue)


def _ident(venue: str) -> dict:
    return R.identity(family="f", symbol="XAUUSD", selector="asia", params={"rr": 2.0},
                      code="c", cost="k", data_venue=venue)


# --------------------------------------------- the venue is not the route

def test_cache_of_the_same_broker_is_the_same_evidence_venue():
    """THE WELD. Live terminal and the cache of that terminal's own bars are one venue."""
    live = _bars("MT5:FusionMarkets-Demo", "MT5:FusionMarkets-Demo")
    cached = _bars("CACHE:XAUUSD_H1.parquet", "MT5:FusionMarkets-Demo")
    assert live.source != cached.source, "precondition: the ROUTES differ"
    assert live.evidence_venue == cached.evidence_venue


def test_identity_survives_a_terminal_outage():
    """POSITIVE CONTROL: this is the exact comparison that fired 195 times."""
    frozen = _ident(_bars("MT5:FusionMarkets-Demo", "MT5:FusionMarkets-Demo").evidence_venue)
    after_outage = _ident(_bars("CACHE:XAUUSD_H1.parquet", "MT5:FusionMarkets-Demo").evidence_venue)
    assert frozen["data_venue"] == after_outage["data_venue"]
    assert frozen["sleeve_id"] == after_outage["sleeve_id"]


def test_the_old_field_would_have_broken_here():
    """The bug reproduces against `source`, so the test above is not vacuously green."""
    assert (_bars("MT5:FusionMarkets-Demo", "MT5:FusionMarkets-Demo").source
            != _bars("CACHE:XAUUSD_H1.parquet", "MT5:FusionMarkets-Demo").source)


# --------------------------------------------- and it is STRICTER, not looser

def test_a_real_venue_change_still_breaks_the_clock():
    """Demo and live are different prints; the route cannot tell them apart, the venue can."""
    demo = _bars("CACHE:XAUUSD_H1.parquet", "MT5:FusionMarkets-Demo")
    live = _bars("CACHE:XAUUSD_H1.parquet", "MT5:FusionMarkets-Live")
    assert demo.source == live.source, "precondition: identical ROUTE -- the old field was blind"
    assert demo.evidence_venue != live.evidence_venue
    assert _ident(demo.evidence_venue)["sleeve_id"] != _ident(live.evidence_venue)["sleeve_id"]


def test_a_free_feed_is_never_the_broker_venue():
    assert (_bars("HTTP:yfinance/XAUUSD=X", "HTTP:yfinance").evidence_venue
            != _bars("CACHE:XAUUSD_H1.parquet", "MT5:FusionMarkets-Demo").evidence_venue)


def test_unknown_venue_fails_closed():
    """An unrecoverable venue must break a clock, never quietly match one (L1.28a)."""
    unknown = _bars("CACHE:XAUUSD_H1.parquet", "")
    assert unknown.evidence_venue == "UNKNOWN-VENUE"
    assert (_ident(unknown.evidence_venue)["sleeve_id"]
            != _ident("MT5:FusionMarkets-Demo")["sleeve_id"])


# --------------------------------------------- provenance is not lost

def test_the_stamp_still_carries_the_route():
    """Both facts are recorded; the fix must not cost the ledger its transport provenance."""
    st = _bars("CACHE:XAUUSD_H1.parquet", "MT5:FusionMarkets-Demo").stamp()
    assert st["bar_source"] == "CACHE:XAUUSD_H1.parquet"
    assert st["evidence_venue"] == "MT5:FusionMarkets-Demo"


def test_shadow_forward_freezes_the_venue_not_the_route():
    src = (_DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert "data_venue=str(bars.evidence_venue)" in src
    assert "data_venue=str(bars.source)" not in src


def test_migration_only_retires_route_shaped_rows():
    sys.path.insert(0, str(_DESK / "scripts"))
    import migrate_identity_venue as M  # noqa: PLC0415
    assert M._is_route("CACHE:XAUUSD_H1.parquet")
    assert M._is_route("HTTP:yfinance/XAUUSD=X")
    assert not M._is_route("MT5:FusionMarkets-Demo")
    assert not M._is_route("HTTP:yfinance")
