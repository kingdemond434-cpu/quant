"""A book with a planted dollar factor: the two majors that ARE that factor must be found to be
one bet, the gold sleeve must not be, and every factor the box cannot build must read UNMEASURED
rather than zero."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import exposure_decomposition as ed  # noqa: E402

N_DAYS = 320
#: Each instrument's loading on the PLANTED dollar factor. EURUSD and GBPUSD are the same bet.
USD_LOADING = {"EURUSD": -1.0, "GBPUSD": -0.9, "AUDUSD": -0.8,
               "USDJPY": 1.0, "USDCAD": 0.9, "USDCHF": 0.8}
PRICE0 = {"EURUSD": 1.10, "GBPUSD": 1.27, "AUDUSD": 0.71, "USDJPY": 150.0,
          "USDCAD": 1.36, "USDCHF": 0.88, "XAUUSD": 2400.0}


def _bars(returns: np.ndarray, start: float, index: pd.DatetimeIndex) -> pd.DataFrame:
    close = start * np.exp(np.cumsum(returns))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": np.ones(len(close), dtype="int64"),
                         "spread": np.full(len(close), 2, dtype="int32")}, index=index)


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A whole synthetic desk: bars with a planted USD factor, a registry, one open position."""
    monkeypatch.setattr(ed, "DESK", tmp_path)
    ed._BARS.clear()
    bars = tmp_path / "data" / "universe"
    bars.mkdir(parents=True)
    idx = pd.date_range("2025-01-01", periods=N_DAYS, freq="D", tz="UTC", name="time")
    rng = np.random.default_rng(7)
    usd = rng.normal(0.0, 0.004, N_DAYS)                    # the factor every major is made from
    for symbol, load in USD_LOADING.items():
        rets = load * usd + rng.normal(0.0, 0.0004, N_DAYS)
        _bars(rets, PRICE0[symbol], idx).to_parquet(bars / f"{symbol}_H1.parquet")
    gold = rng.normal(0.0, 0.006, N_DAYS) + 0.05 * usd      # its own driver, a whiff of dollar
    frame = _bars(gold, PRICE0["XAUUSD"], idx).reset_index()
    frame.to_csv(bars / "XAUUSD_H1.csv", index=False)       # the tolerant CSV path, with a header

    fx = {"asset_class": "Forex", "swap_long": -6.0, "swap_short": 2.0, "tick_size": 1e-05,
          "tick_value": 1.0, "contract_size": 100000.0, "median_spread_pts": 1.0}
    universe = {s: {"symbol": s, **fx} for s in USD_LOADING}
    universe["XAUUSD"] = {"symbol": "XAUUSD", "asset_class": "Commodities", "swap_long": -61.76,
                          "swap_short": 29.45, "tick_size": 0.01, "tick_value": 1.0,
                          "contract_size": 100.0, "median_spread_pts": 14.5}
    (bars / "universe.json").write_text(json.dumps(universe), encoding="utf-8")

    sleeves = {"sleeves": [
        {"name": "eur_long", "symbol": "EURUSD", "family": "discovered", "side": "LONG",
         "risk_frac": 0.01, "lot": "auto_ramp", "status": "LIVE"},
        {"name": "gbp_long", "symbol": "GBPUSD", "family": "discovered", "side": "LONG",
         "risk_frac": 0.01, "lot": "auto_ramp", "status": "LIVE"},
        {"name": "gold_srb", "symbol": "XAUUSD", "family": "session_range_breakout",
         "side": "LONG", "risk_frac": 0.012, "status": "LIVE"},
        {"name": "nobars_sleeve", "symbol": "NOBARS", "family": "carry", "side": "SHORT",
         "risk_frac": 0.005, "status": "LIVE"},
        {"name": "not_live", "symbol": "EURUSD", "family": "discovered", "side": "LONG",
         "risk_frac": 0.09, "status": "STANDBY"}]}
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps(sleeves), encoding="utf-8")
    state = {"equity": 1000.0, "position": [
        {"ticket": 5150, "symbol": "EURUSD", "type": 1, "volume": 0.02,
         "price_open": 1.10, "sl": 1.11, "tp": 1.08, "profit": -1.0}]}
    (tmp_path / "data" / "gateway_state.json").write_text(json.dumps(state), encoding="utf-8")
    return tmp_path


@pytest.fixture
def report(desk):
    return ed.run(write=False)


def _row(report, name):
    return next(r for r in report["sleeves"] + report["positions"] if r["name"] == name)


def test_factors_are_built_from_the_desks_own_bars(report):
    """The six majors make the dollar; the CSV-only symbol makes gold; the trend factor is
    per asset class. What has no bars and no FRED file is UNMEASURED, by name."""
    meta = report["factors"]
    assert set(meta) <= set(ed.FACTORS) and meta["usd"]["n_days"] == ed.LOOKBACK_DAYS
    assert sorted(meta["usd"]["symbols"]) == sorted(USD_LOADING)
    assert meta["gold"]["symbols"] == "XAUUSD" and meta["gold"]["n_days"] == ed.LOOKBACK_DAYS
    assert meta["trend"]["symbols"] == {"Commodities": "commodities", "Forex": "usd",
                                        "Forex Exotics": "usd",
                                        "Soft Commodity": "commodities"}
    # The characteristics are scored over the BOOK's symbols, not the universe's: EURUSD, GBPUSD
    # and XAUUSD are held; NOBARS has neither a registry row nor a price to make a spread relative.
    assert meta["carry"]["kind"] == "characteristic" and meta["carry"]["n_symbols"] == 3
    assert meta["liquidity"]["n_symbols"] == 3 and meta["liquidity"]["signed_by_side"] is False
    for absent in ("oil", "equity_beta", "vol", "rates", "growth", "inflation"):
        assert meta[absent].get("unmeasured") is True, absent
        assert meta[absent]["n_days"] == 0
        assert f"factor:{absent}" in report["unmeasured"]
        assert absent not in report["book"]          # UNMEASURED is never a zero loading


def test_two_long_majors_share_the_usd_factor_and_are_flagged_duplicate(report):
    """EURUSD and GBPUSD long ARE the same dollar bet: same-signed beta, near-equal size, and a
    duplicate pair naming usd among the factors they share."""
    eur, gbp = _row(report, "eur_long"), _row(report, "gbp_long")
    assert eur["exposures"]["usd"] < 0 and gbp["exposures"]["usd"] < 0
    ratio = eur["exposures"]["usd"] / gbp["exposures"]["usd"]
    assert 0.8 < ratio < 1.4                         # -1.11 vs -1.00 on the planted loadings
    assert eur["r2"] is not None and eur["r2"] > 0.9  # the factors ARE this instrument
    pair = next(p for p in report["duplicate_heat"]
                if {p["a"], p["b"]} == {"eur_long", "gbp_long"})
    assert pair["cosine"] >= ed.COSINE_DUP
    assert "usd" in pair["shared_factors"]
    assert pair["shared_heat"] == pytest.approx(0.02)   # 0.01 + 0.01 of heat that is ONE bet


def test_the_gold_sleeve_loads_on_gold_and_is_not_the_dollar_bet(report):
    gold = _row(report, "gold_srb")
    assert gold["cluster"] == "session_liquidity"      # from the desk's declared taxonomy
    assert gold["exposures"]["gold"] == pytest.approx(0.012, rel=0.05)   # beta 1.0 x risk_frac
    assert abs(gold["exposures"]["usd"]) < 0.2 * abs(gold["exposures"]["gold"])
    assert not [p for p in report["duplicate_heat"]
                if {p["a"], p["b"]} == {"gold_srb", "eur_long"}]


def test_an_instrument_without_bars_is_unmeasured_not_zero(report):
    row = _row(report, "nobars_sleeve")
    assert row["exposures"] == {} and row["n_obs"] == 0 and row["r2"] is None
    assert "instrument:NOBARS (no bars)" in report["unmeasured"]
    assert row["weight"] == pytest.approx(-0.005)      # declared SHORT, so signed
    assert "not_live" not in [r["name"] for r in report["sleeves"]]   # STANDBY is not the book


def test_a_stale_factor_costs_its_own_column_not_the_whole_fit(desk):
    """Measured on the live box 2026-09-16: the UST10Y tape had stopped nine months back, an
    all-factor inner join left SIX common days, and EVERY r2 in the report read null. A series
    that stopped must cost its own column in the joint fit and nothing else -- and be named."""
    idx = pd.date_range("2025-01-01", periods=200, freq="D", tz="UTC", name="time")
    rng = np.random.default_rng(11)
    _bars(rng.normal(0.0, 0.003, 200), 110.0, idx).to_parquet(
        desk / "data" / "universe" / "UST10Y_H1.parquet")
    ed._BARS.clear()
    out = ed.run(write=False)
    assert out["factors"]["rates"]["n_days"] == 199     # 200 bars, one eaten by the first diff
    assert out["stale_factors"]["rates"] > ed.STALE_DAYS
    eur = _row(out, "eur_long")
    assert eur["r2"] is not None and eur["r2"] > 0.9   # the fit survives the stopped column
    assert "rates" not in eur["r2_factors"] and "usd" in eur["r2_factors"]
    assert "rates" in eur["exposures"]                 # its own beta is measured on its own days


def test_the_position_weight_is_stop_risk_over_equity(report):
    pos = _row(report, "pos:5150:EURUSD")
    # 0.02 lots x 0.01 of price x (tick_value/tick_size = 100000) = 20 of 1000 equity, SELL.
    assert pos["weight_basis"] == "risk_frac_from_stop"
    assert pos["weight"] == pytest.approx(-0.02)
    assert pos["exposures"]["usd"] > 0                 # short EURUSD is LONG the dollar
    assert pos["cluster"] == "open_position"


def test_the_book_is_the_sum_and_n_eff_counts_the_bets(report):
    for factor, total in report["book"].items():
        rows = [r for r in report["sleeves"] + report["positions"]
                if r["weight_basis"] != "lots_unconverted"]
        assert total == pytest.approx(sum(r["exposures"].get(factor, 0.0) for r in rows), abs=1e-7)
    assert report["book"]["usd"] == pytest.approx(
        sum(_row(report, n)["exposures"]["usd"]
            for n in ("eur_long", "gbp_long", "gold_srb", "pos:5150:EURUSD")), abs=1e-7)
    assert set(report["clusters"]) == {"discovered", "session_liquidity", "macro_rates",
                                       "open_position"}      # 'carry' IS the macro_rates payer
    assert report["clusters"]["discovered"] == pytest.approx(0.02)
    n_eff = report["n_eff_factor_bets"]
    assert 1.0 <= n_eff <= len(report["book"])
    assert report["n_eff_factor_bets_unscaled"] is not None
    assert set(report["factor_scale"]) == set(report["book"])


def test_absent_inputs_never_crash_and_report_unmeasured(tmp_path, monkeypatch):
    monkeypatch.setattr(ed, "DESK", tmp_path / "empty")
    ed._BARS.clear()
    out = ed.run(write=False)
    assert out["n_live_sleeves"] == 0 and out["n_positions"] == 0
    assert out["book"] == {} and out["n_eff_factor_bets"] is None
    assert out["n_factors_measured"] == 0
    assert all(f"factor:{n}" in out["unmeasured"] for n in ed.FACTORS)
    assert out["duplicate_heat"] == [] and out["rule"]


def test_cli_dry_run_prints_and_writes_nothing_then_write_is_atomic(desk, capsys):
    assert ed.main(["--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "EXPOSURE DECOMPOSITION" in printed and "dry run: nothing written" in printed
    assert "UNMEASURED: oil, equity_beta, vol, rates, growth, inflation" in printed
    assert not ed.report_path().exists()

    assert ed.main([]) == 0
    assert "written:" in capsys.readouterr().out
    doc = json.loads(ed.report_path().read_text("utf-8-sig"))
    assert set(doc) >= {"at", "factors", "sleeves", "positions", "book", "clusters",
                        "duplicate_heat", "n_eff_factor_bets", "unmeasured", "rule"}
    assert doc["n_live_sleeves"] == 4
    assert not list(ed.report_path().parent.glob("*.tmp*"))   # the temp file is renamed, not left
