"""The netting diagnostic on a whole synthetic desk, plus one audit against the REAL registry.

What is pinned, and each item is a way this report could publish a flattering number:

  * two sleeves pointing opposite ways in one symbol net to zero and the ratio says so -- the
    saving the report exists to price;
  * every contributing sleeve keeps its row on the target, so wiring this into the gateway later
    cannot erase the forward evidence of the sleeve that was right while the book was flat;
  * the currency-factor exposure is measured with a RANK, because eighteen pairs from eight
    currencies span at most seven directions and the desk's breadth is already near that wall;
  * everything the box cannot measure is NAMED -- an `auto_ramp` lot, a symbol with no
    `volume_step`, a symbol with no H1 bars, a quote currency with no conversion, a spread with
    no cell -- and never entered as a zero. A zero lot reads exactly like a sleeve that chose to
    hold nothing and a zero spread reads exactly like a free trade (L1.28a);
  * `--dry-run` writes nothing at all;
  * the explicit non-pair symbol map in `libs/risk/fx_exposure.py` agrees with the broker's own
    registry -- `currency_profit` for every index, bond, soft and long-tickered crypto CFD. A map
    that drifts from the authority it was copied from is a fabricated quote leg in a rank.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.risk.fx_exposure import (  # noqa: E402
    CURRENCIES,
    NON_PAIR_SYMBOLS,
    factors_from_registry,
    split_symbol,
)
from research import netting_report as nr  # noqa: E402

FX = {"asset_class": "Forex", "currency_profit": "USD", "contract_size": 100000.0,
      "volume_step": 0.01, "volume_min": 0.01, "tick_size": 1e-05, "tick_value": 0.9,
      "median_spread_pts": 12.0, "digits": 5}
PRICE = {"EURUSD": 1.10, "EURCHF": 0.95, "AUDCAD": 0.90, "GBPUSD": 1.27,
         "XAUUSD": 2400.0, "EURCAD": 1.50, "NOBARS": 1.0}


def _bars(path: Path, last: float) -> None:
    index = pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC", name="time")
    frame = pd.DataFrame({"open": last, "high": last, "low": last, "close": last,
                          "tick_volume": 1, "spread": 2, "real_volume": 0}, index=index)
    frame.to_parquet(path)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A synthetic desk: four symbols with bars, one without, one with no volume step."""
    monkeypatch.setattr(nr, "DESK", tmp_path)
    nr._CLOSE.clear()
    bars = tmp_path / "data" / "universe"
    bars.mkdir(parents=True)
    for symbol in ("EURUSD", "EURCHF", "AUDCAD", "XAUUSD", "EURCAD"):
        _bars(bars / f"{symbol}_H1.parquet", PRICE[symbol])

    registry: dict[str, Any] = {
        "EURUSD": dict(FX),
        "EURCHF": dict(FX, currency_profit="CHF"),
        "AUDCAD": dict(FX, currency_profit="CAD"),
        "EURCAD": dict(FX, currency_profit="CAD"),
        "XAUUSD": dict(FX, asset_class="Commodities", contract_size=100.0,
                       tick_size=0.01, tick_value=0.9, median_spread_pts=16.0),
        "NOBARS": dict(FX),
        "NOSTEP": {k: v for k, v in FX.items() if k != "volume_step"},
        "US500": dict(FX, asset_class="Indices", contract_size=1.0, tick_size=0.01,
                      tick_value=0.9, median_spread_pts=40.0),
    }
    (bars / "universe.json").write_text(json.dumps(registry), encoding="utf-8")

    sleeves = {"sleeves": [
        # one symbol, two sleeves, opposite sides -> the netting case
        {"name": "eurchf_long", "symbol": "EURCHF", "lot": 0.30, "risk_frac": 0.01,
         "status": "LIVE", "side": "LONG"},
        {"name": "eurchf_short", "symbol": "EURCHF", "lot": 0.30, "risk_frac": 0.01,
         "status": "LIVE", "side": "SHORT"},
        # one symbol, two sleeves, same side -> nothing to net
        {"name": "audcad_a", "symbol": "AUDCAD", "lot": 0.10, "risk_frac": 0.02,
         "status": "LIVE", "side": "LONG"},
        {"name": "audcad_b", "symbol": "AUDCAD", "lot": 0.10, "risk_frac": 0.02,
         "status": "LIVE", "side": "LONG"},
        # the live registry's real shape: no lot at all
        {"name": "ramp_sleeve", "symbol": "EURUSD", "lot": "auto_ramp", "risk_frac": 0.03,
         "status": "LIVE", "side": "LONG"},
        # a symbol the registry carries without a volume step
        {"name": "nostep_sleeve", "symbol": "NOSTEP", "lot": 0.10, "risk_frac": 0.01,
         "status": "LIVE", "side": "LONG"},
        # a symbol with no bars on this box
        {"name": "nobars_sleeve", "symbol": "NOBARS", "lot": 0.10, "risk_frac": 0.01,
         "status": "STANDBY", "side": "LONG"},
        # never read: not LIVE and not STANDBY
        {"name": "retired_sleeve", "symbol": "EURUSD", "lot": 9.0, "risk_frac": 0.9,
         "status": "RETIRED", "side": "LONG"},
    ]}
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps(sleeves), encoding="utf-8")
    (tmp_path / "data" / "gateway_state.json").write_text(
        json.dumps({"equity": 1000.0, "position": []}), encoding="utf-8")
    (tmp_path / "data" / "account_state.json").write_text(
        json.dumps({"currency": "EUR", "equity": 1000.0}), encoding="utf-8")
    return tmp_path


@pytest.fixture
def report(desk: Path) -> dict[str, Any]:
    return nr.run(write=False)


def _target(report: dict[str, Any], symbol: str) -> dict[str, Any]:
    rows = [t for t in report["targets"] if t["symbol"] == symbol]
    assert rows, f"{symbol} absent from {[t['symbol'] for t in report['targets']]}"
    return rows[0]


# ---------------------------------------------------------------------------------- the netting
def test_opposite_sleeves_in_one_symbol_net_to_zero(report: dict[str, Any]) -> None:
    target = _target(report, "EURCHF")
    assert target["net_lots"] == 0.0
    assert target["gross_lots"] == pytest.approx(0.60)
    assert target["netting_ratio_is_inf"] is True
    assert target["netting_ratio"] is None
    assert target["orders_saved"] == 2


def test_every_contributing_sleeve_keeps_its_row(report: dict[str, Any]) -> None:
    contributors = _target(report, "EURCHF")["contributors"]
    assert {c["sleeve"] for c in contributors} == {"eurchf_long", "eurchf_short"}
    assert sorted(c["target_lots"] for c in contributors) == [-0.30, 0.30]


def test_same_side_sleeves_net_to_their_sum_at_ratio_one(report: dict[str, Any]) -> None:
    target = _target(report, "AUDCAD")
    assert target["net_lots"] == pytest.approx(0.20)
    assert target["netting_ratio"] == pytest.approx(1.0)
    assert target["orders_saved"] == 1
    assert target["volume_step"] == 0.01


def test_only_live_and_standby_rows_are_read(report: dict[str, Any]) -> None:
    assert report["n_sleeves_read"] == 7
    assert "retired_sleeve" not in report["intent_source"]


def test_the_intent_source_is_recorded_per_sleeve(report: dict[str, Any]) -> None:
    assert report["intent_source"]["eurchf_long"] == "sleeve_lot"
    assert report["intent_source"]["ramp_sleeve"] == "UNMEASURED"
    assert report["intent_source"]["nostep_sleeve"] == "UNMEASURED"


def test_gateway_targets_take_precedence_when_the_gateway_publishes_them(desk: Path) -> None:
    (desk / "data" / "gateway_state.json").write_text(json.dumps({
        "equity": 1000.0,
        "sleeve_targets": {"ramp_sleeve": 0.44, "eurchf_long": 0.10},
    }), encoding="utf-8")
    report = nr.run(write=False)
    assert report["intent_source"]["ramp_sleeve"] == "gateway_targets"
    assert report["intent_source"]["eurchf_long"] == "gateway_targets"
    assert _target(report, "EURUSD")["net_lots"] == pytest.approx(0.44)
    assert _target(report, "EURCHF")["net_lots"] == pytest.approx(-0.20)


# ------------------------------------------------------------------------------ what is unmeasured
def test_an_auto_ramp_lot_is_named_rather_than_counted_as_zero(report: dict[str, Any]) -> None:
    assert any("intent:ramp_sleeve" in row and "auto_ramp" in row
               for row in report["unmeasured"])
    assert not [t for t in report["targets"] if t["symbol"] == "EURUSD"]


def test_a_symbol_without_a_volume_step_is_named_and_not_netted(
        report: dict[str, Any]) -> None:
    assert any(row.startswith("volume_step:NOSTEP") for row in report["unmeasured"])
    assert "NOSTEP" not in [t["symbol"] for t in report["targets"]]


def test_a_symbol_without_bars_is_named_rather_than_priced(report: dict[str, Any]) -> None:
    assert any("nobars_sleeve" in row for row in report["unmeasured"])


def test_the_unmeasured_list_is_deduplicated_and_ordered(report: dict[str, Any]) -> None:
    rows = report["unmeasured"]
    assert rows == sorted(set(rows))


# --------------------------------------------------------------------------- the factor exposure
def test_the_factor_exposure_is_measured_with_a_rank(report: dict[str, Any]) -> None:
    factor = report["factor_exposure"]
    assert factor["status"] == "MEASURED"
    assert factor["basis"] == "notional_from_lots"
    assert set(factor["names"]) >= {"EUR", "CHF", "AUD", "CAD"}
    assert 0.0 < factor["effective_rank"] <= len(factor["names"])
    assert sum(factor["concentration"].values()) == pytest.approx(1.0)


def test_opposite_sleeves_in_one_symbol_cancel_inside_the_factor_vector(
        report: dict[str, Any]) -> None:
    """EURCHF long and short are both HELD, so CHF stays a named factor at zero net -- and the
    rank still counts two rows, because two sleeves that cancel are two bets, not none."""
    factor = report["factor_exposure"]
    exposure = dict(zip(factor["names"], factor["vector"], strict=True))
    assert exposure["CHF"] == pytest.approx(0.0)
    assert factor["n_sleeves_nonzero"] >= 3


def test_the_factor_book_falls_back_to_risk_frac_when_no_lot_is_measurable(
        desk: Path) -> None:
    """The LIVE path today: every sleeve carries `auto_ramp`, so the only measured weight basis
    is risk_frac x equity -- and the artifact says which basis it used."""
    doc = json.loads((desk / "data" / "sleeves.json").read_text("utf-8"))
    for row in doc["sleeves"]:
        row["lot"] = "auto_ramp"
    (desk / "data" / "sleeves.json").write_text(json.dumps(doc), encoding="utf-8")
    report = nr.run(write=False)
    factor = report["factor_exposure"]
    assert report["n_intents"] == 0
    assert factor["basis"] == "risk_frac_x_equity"
    assert factor["status"] == "MEASURED"
    assert factor["effective_rank"] > 0.0


def test_a_book_with_nothing_priceable_reads_unmeasured_not_zero(desk: Path) -> None:
    (desk / "data" / "sleeves.json").write_text(json.dumps({"sleeves": []}), encoding="utf-8")
    report = nr.run(write=False)
    assert report["factor_exposure"]["status"] == "UNMEASURED"
    assert report["factor_exposure"]["effective_rank"] is None
    assert report["n_intents"] == 0


def test_an_absent_conversion_rate_is_named_by_currency(desk: Path) -> None:
    """A CAD-quoted sleeve in a EUR account needs EURCAD. Remove it and the sleeve leaves the
    factor book with its reason on the record -- it is never converted at 1.0."""
    (desk / "data" / "universe" / "EURCAD_H1.parquet").unlink()
    nr._CLOSE.clear()
    report = nr.run(write=False)
    assert any(row.startswith("fx_rate:CAD->EUR") for row in report["unmeasured"])
    assert "AUDCAD" not in str(report["factor_exposure"]["names"])


# ----------------------------------------------------------------------------- the spread saving
def test_the_spread_saving_prices_only_the_lots_that_never_cross(
        report: dict[str, Any]) -> None:
    saved = report["spreads_saved_estimate"]
    eurchf = saved["by_symbol"]["EURCHF"]
    assert eurchf["lots_not_sent"] == pytest.approx(0.60)
    assert eurchf["spread_basis"] == "registry_median"
    assert eurchf["cost_saved"] == pytest.approx(0.60 * 12.0 * 0.9)
    assert saved["by_symbol"]["AUDCAD"]["lots_not_sent"] == 0.0
    assert saved["status"] == "MEASURED"
    assert saved["total"] == pytest.approx(0.60 * 12.0 * 0.9)


def test_a_symbol_with_no_spread_at_all_is_unmeasured_not_free(desk: Path) -> None:
    path = desk / "data" / "universe" / "universe.json"
    registry = json.loads(path.read_text("utf-8"))
    registry["EURCHF"].pop("median_spread_pts")
    registry["EURCHF"].pop("tick_value")
    path.write_text(json.dumps(registry), encoding="utf-8")
    report = nr.run(write=False)
    assert report["spreads_saved_estimate"]["by_symbol"]["EURCHF"]["status"] == "UNMEASURED"
    assert report["spreads_saved_estimate"]["status"] == "PARTIAL"
    assert any(row.startswith("spread:EURCHF") for row in report["unmeasured"])


# ------------------------------------------------------------------------------- the artifact/CLI
def test_the_rule_is_written_into_the_artifact(report: dict[str, Any]) -> None:
    assert report["rule"] == ("netting is an execution economy; the sleeves' intents are "
                              "preserved; nothing here sizes")
    assert report["account_ccy"] == "EUR"
    assert report["schema"] == "netting-1"


def test_writing_lands_an_atomic_artifact_with_no_temp_left_behind(desk: Path) -> None:
    out = nr.report_path()
    assert not out.exists()
    nr.run(write=True)
    assert out.exists()
    loaded = json.loads(out.read_text("utf-8"))
    assert loaded["schema"] == "netting-1"
    assert loaded["targets"]
    assert not list(out.parent.glob("*.tmp*"))


def test_the_cli_dry_run_writes_nothing(desk: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert nr.main(["--dry-run"]) == 0
    assert not nr.report_path().exists()
    assert "dry run: nothing written" in capsys.readouterr().out


def test_the_cli_writes_when_it_is_not_a_dry_run(desk: Path,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    assert nr.main([]) == 0
    assert nr.report_path().exists()
    assert "written:" in capsys.readouterr().out


def test_factor_rank_reading_is_shaped_for_alpha_breadth(desk: Path) -> None:
    """`alpha_breadth` publishes readings as {name, n_eff, n_obs, status, why} and takes the
    minimum of the MEASURED ones. This is offered in that shape and wired by nobody yet."""
    reading = nr.factor_rank_reading()
    assert set(reading) >= {"name", "n_eff", "n_obs", "status", "why"}
    assert reading["name"] == "exposure_notional_rank"
    assert reading["status"] == "MEASURED"
    assert reading["n_eff"] > 0.0
    assert reading["n_obs"] >= 1
    assert not nr.report_path().exists()          # a reading is a read, not a write


# ----------------------------------------------------- the audit against the broker's own registry
def _live_registry() -> dict[str, Any]:
    path = DESK / "data" / "universe" / "universe.json"
    if not path.exists():
        pytest.skip("no universe registry on this box")
    doc = json.loads(path.read_text("utf-8"))
    return {k: v for k, v in doc.items() if isinstance(v, dict)}


def test_the_explicit_symbol_map_agrees_with_the_broker_registry() -> None:
    """Every non-pair symbol's quote leg IS the registry's `currency_profit`. The map was copied
    from the authority; this is what stops it drifting away from it in silence."""
    registry = _live_registry()
    checked = 0
    for symbol, (_base, quote) in NON_PAIR_SYMBOLS.items():
        row = registry.get(symbol)
        if not isinstance(row, dict) or not row.get("currency_profit"):
            continue
        assert quote == str(row["currency_profit"]).upper(), (
            f"{symbol}: map says {quote}, registry says {row['currency_profit']}")
        checked += 1
    assert checked >= 25, f"only {checked} mapped symbols found in the registry"


def test_every_non_forex_universe_symbol_the_desk_may_hold_is_classifiable() -> None:
    """Indices, bonds, softs, energies, metals and crypto CFDs must all resolve -- through the
    explicit map, the six-letter rule, or the registry-derived override. A symbol none of the
    three can classify would be silently absent from every factor share."""
    registry = _live_registry()
    factors = factors_from_registry(registry)
    hunted = {"Indices", "Bonds", "Soft Commodity", "Energy", "Commodities", "Crypto", "Forex",
              "Forex Exotics"}
    unresolved = []
    for symbol, row in registry.items():
        if str(row.get("asset_class") or "") not in hunted:
            continue
        if symbol in factors:
            continue
        try:
            split_symbol(symbol)
        except Exception:                                   # noqa: BLE001 - collect, then report
            unresolved.append(symbol)
    assert not unresolved, f"unclassifiable tradable symbols: {unresolved}"


def test_the_equity_lane_is_classified_by_the_registry_not_by_a_hard_coded_list() -> None:
    """Single names are traded on news and never hunted for hypotheses, but they stay TRADABLE,
    so the factor view must still price them -- from the registry, which is the authority."""
    registry = _live_registry()
    factors = factors_from_registry(registry)
    equities = [s for s, r in registry.items() if str(r.get("asset_class") or "") == "Equities"]
    if not equities:
        pytest.skip("no equities in this registry")
    assert all(s in factors for s in equities)
    assert all(factors[s][1] in CURRENCIES for s in equities)
