"""The registry may not lose a field, invent a cost, or accept a stub as a measurement.

These pin the repair for the defect found 2026-08-26: three producers wrote
`data/universe/universe.json` with three schemas and last-writer-wins, which deleted `tick_value`
from all 197 symbols, zeroed every account-currency cost model, emptied `classify_all`, and
flipped `cost_hash` often enough to break eleven live forward clocks.

THE POSITIVE CONTROL IS THE POINT. `test_derivation_reproduces_broker_tick_values` checks the
derived numbers against tick_values the BROKER itself reported for 23 symbols across metals, JPY
crosses, CHF, CAD and USD pairs. A derivation that only satisfies its own arithmetic proves
nothing; this one has to land on someone else's measurements.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.universe_registry import (  # noqa: E402
    ACCOUNT_CCY,
    backfill_tick_values,
    defects,
    derive_tick_value,
    merge,
    quote_currency,
    spread_cost_per_lot,
)

#: Last H1 closes, near enough to the values the broker's own tick_values were read at.
CLOSES = {"EURUSD": 1.1585, "USDJPY": 159.0, "USDCHF": 0.8034, "USDCAD": 1.3861,
          "EURJPY": 184.20, "AUDUSD": 0.6500, "GBPUSD": 1.3400}

#: `symbol: (tick_size, contract_size, broker_reported_tick_value)` -- the broker's numbers.
BROKER = {
    "EURUSD": (1e-05, 100000.0, 0.8632), "GBPUSD": (1e-05, 100000.0, 0.8632),
    "AUDUSD": (1e-05, 100000.0, 0.8632), "NZDUSD": (1e-05, 100000.0, 0.8632),
    "XAUUSD": (0.01, 100.0, 0.8632), "XAGUSD": (0.001, 5000.0, 4.3161),
    "BTCUSD": (0.01, 1.0, 0.0086), "ETHUSD": (0.01, 1.0, 0.0086),
    "USDJPY": (0.001, 100000.0, 0.5418), "EURJPY": (0.001, 100000.0, 0.5418),
    "CADJPY": (0.001, 100000.0, 0.5418), "GBPJPY": (0.001, 100000.0, 0.5418),
    "AUDJPY": (0.001, 100000.0, 0.5418), "CHFJPY": (0.001, 100000.0, 0.5418),
    "NZDJPY": (0.001, 100000.0, 0.5418),
    "USDCHF": (1e-05, 100000.0, 1.0648), "EURCHF": (1e-05, 100000.0, 1.0648),
    "USDCAD": (1e-05, 100000.0, 0.6224), "NZDCAD": (1e-05, 100000.0, 0.6224),
}


@pytest.mark.parametrize("symbol", sorted(BROKER))
def test_derivation_reproduces_broker_tick_values(symbol: str) -> None:
    tick_size, contract_size, reported = BROKER[symbol]
    got = derive_tick_value(symbol, tick_size, contract_size, CLOSES)
    assert got is not None, f"{symbol}: underivable, which is how the field went missing"
    assert got == pytest.approx(reported, rel=0.02), (
        f"{symbol}: derived {got} vs broker {reported} -- more than rate drift apart")


def test_account_currency_is_not_usd() -> None:
    # The whole defect is that a quote-currency number was charged against the book. If the
    # account were USD the distinction would be invisible for USD pairs and the bug would hide.
    assert ACCOUNT_CCY == "EUR"
    assert derive_tick_value("EURUSD", 1e-05, 100000.0, CLOSES) == pytest.approx(0.8632, rel=0.02)


def test_quote_currency_refuses_to_guess() -> None:
    assert quote_currency("EURUSD") == "USD"
    assert quote_currency("XAUUSD") == "USD"
    assert quote_currency("CADJPY") == "JPY"
    # A share CFD has no readable denomination. None, never an assumed USD.
    assert quote_currency("AAPL") is None
    assert quote_currency("AT&T") is None
    assert derive_tick_value("AAPL", 0.01, 1.0, CLOSES) is None


def test_spread_cost_is_account_currency_not_quote() -> None:
    # The documented 184x error: a JPY cross read in yen against a EUR book.
    jpy = {"median_spread_pts": 15.0, "tick_value": 0.5418,
           "tick_size": 0.001, "contract_size": 100000.0}
    assert spread_cost_per_lot(jpy) == pytest.approx(8.13, rel=0.01)
    wrong = jpy["median_spread_pts"] * jpy["tick_size"] * jpy["contract_size"]
    assert wrong == pytest.approx(1500.0)
    assert wrong / spread_cost_per_lot(jpy) > 150


def test_uncostable_row_returns_none_not_zero() -> None:
    # 0.0 flatters: it backtests as though trading were free. None forces the caller to decide.
    assert spread_cost_per_lot({"median_spread_pts": 12.0, "tick_value": 0.0}) is None
    assert spread_cost_per_lot({"median_spread_pts": 12.0}) is None
    assert spread_cost_per_lot({"tick_value": 0.86}) is None


def test_merge_cannot_delete_a_field_the_producer_does_not_know() -> None:
    base = {"EURUSD": {"tick_size": 1e-05, "contract_size": 100000.0,
                       "tick_value": 0.8632, "median_spread_pts": 12.0, "bars": 50000}}
    # Exactly the payload that deleted tick_value from 197 symbols.
    incoming = {"EURUSD": {"tick_size": 1e-05, "contract_size": 100000.0,
                           "median_spread_pts": 0, "bars": 0, "category": "Forex"}}
    out = merge(base, incoming, source="download_all_symbols", now="2026-08-26T00:00:00+00:00")
    assert out["EURUSD"]["tick_value"] == 0.8632, "a partial producer deleted the cost field"
    assert out["EURUSD"]["bars"] == 50000, "a 0-bar stub overwrote 50,000 real bars"
    assert out["EURUSD"]["category"] == "Forex", "the new field was dropped"
    assert out["EURUSD"]["_provenance"]["category"]["source"] == "download_all_symbols"


def test_merge_lets_a_real_measurement_win() -> None:
    base = {"EURUSD": {"tick_size": 1e-05, "contract_size": 100000.0,
                       "tick_value": 0.8632, "median_spread_pts": 12.0, "bars": 50000}}
    out = merge(base, {"EURUSD": {"median_spread_pts": 3.0, "bars": 60000}},
                source="expand_universe", now="2026-08-26T00:00:00+00:00")
    assert out["EURUSD"]["median_spread_pts"] == 3.0
    assert out["EURUSD"]["bars"] == 60000


def test_merge_never_drops_a_symbol() -> None:
    base = {"EURUSD": {"tick_value": 0.86}, "XAUUSD": {"tick_value": 0.86}}
    out = merge(base, {"EURUSD": {"tick_value": 0.87}}, source="s", now="t")
    assert set(out) == {"EURUSD", "XAUUSD"}, "a 1-symbol producer shrank the universe"


def test_zero_spread_survives_merge_because_a_raw_account_really_is_zero() -> None:
    # USDJPY and GBPUSD genuinely fill at 0 spread on this account (execution_quality.json), so a
    # zero spread is a legitimate reading and is NOT in ZERO_IS_A_STUB. It must be preservable.
    out = merge({"USDJPY": {"median_spread_pts": 13.0}},
                {"USDJPY": {"median_spread_pts": 0}}, source="s", now="t")
    assert out["USDJPY"]["median_spread_pts"] == 0


def test_backfill_fills_what_it_can_and_names_what_it_cannot() -> None:
    reg = {"EURUSD": {"tick_size": 1e-05, "contract_size": 100000.0, "median_spread_pts": 12.0},
           "AAPL": {"tick_size": 0.01, "contract_size": 1.0, "median_spread_pts": 5.0}}
    filled, missing = backfill_tick_values(reg, CLOSES, now="2026-08-26T00:00:00+00:00")
    assert filled == 1 and missing == ["AAPL"]
    assert reg["EURUSD"]["tick_value"] == pytest.approx(0.8632, rel=0.02)
    assert reg["EURUSD"]["_provenance"]["tick_value"]["account_ccy"] == "EUR"
    assert "tick_value" not in reg["AAPL"], "an underivable value must stay absent, not become 0"


def test_defects_catches_the_exact_live_failure() -> None:
    # The registry as it actually stood: no tick_value, bars stubbed, spread zeroed.
    broken = {s: {"tick_size": 1e-05, "contract_size": 100000.0,
                  "median_spread_pts": 0, "bars": 0} for s in ("EURUSD", "USDJPY", "CADJPY")}
    found = defects(broken, parquet_bars={"EURUSD": 50000, "USDJPY": 50000, "CADJPY": 50000},
                    realized_spread_pts={"CADJPY": 1.0})
    blob = " | ".join(found)
    assert "tick_value" in blob
    assert "0 bars while a parquet" in blob
    assert "OWN" in blob and "CADJPY" in blob, "a spread reality already refuted went unreported"
    assert "cannot be costed" in blob


def test_defects_is_silent_on_a_healthy_registry() -> None:
    healthy = {"EURUSD": {"tick_size": 1e-05, "contract_size": 100000.0,
                          "tick_value": 0.8632, "median_spread_pts": 12.0, "bars": 50000}}
    assert defects(healthy, parquet_bars={"EURUSD": 50000}) == []


def test_empty_registry_is_a_defect_not_a_clean_verdict() -> None:
    # WS-005: absence must never resolve to "nothing worth trading".
    assert defects({}) and "empty" in defects({})[0]
