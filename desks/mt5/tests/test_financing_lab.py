"""The financing lab on temporary files: a dry run writes nothing, a real run writes the two
artifacts, the evidence carries lineage factors and a measured financing shift for a sleeve
the swap rejudge priced, and everything the host cannot measure is UNMEASURED by name."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import financing_lab as FL  # noqa: E402

pd = pytest.importorskip("pandas")


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    data, reports = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    reports.mkdir()
    (data / "tape" / "contract_terms").mkdir(parents=True)
    (data / "universe").mkdir()
    for name, path in (("ACCOUNT_STATE", data / "account_state.json"),
                       ("GATEWAY_STATE", data / "gateway_state.json"),
                       ("SLEEVES", data / "sleeves.json"),
                       ("ALLOCATION", reports / "pf_allocation.json"),
                       ("ROI_EVIDENCE", data / "roi_capital_evidence.json"),
                       ("SWAP_REJUDGE", reports / "SWAP_REJUDGE.json"),
                       ("LIVE_LEDGER", data / "live_ledger.jsonl"),
                       ("BROKER_CLOCK", data / "broker_clock.json"),
                       ("TERMS_DIR", data / "tape" / "contract_terms"),
                       ("UNIVERSE", data / "universe" / "universe.json"),
                       ("BARS_DIR", data / "universe"),
                       ("CAPACITY", reports / "CAPACITY.json"),
                       ("OUT_EVIDENCE", data / "allocator_evidence.json"),
                       ("OUT_REPORT", reports / "FINANCING_LAB.json")):
        monkeypatch.setattr(FL, name, path)
    # no terminal in the test, whatever the host has
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    (data / "account_state.json").write_text(json.dumps(
        {"currency": "EUR", "balance": 600.0, "equity": 600.0, "margin_free": 600.0}), "utf-8")
    (data / "gateway_state.json").write_text(json.dumps(
        {"equity": 610.0, "position": [
            {"ticket": 1, "type": 0, "volume": 0.5, "price_open": 1.10, "profit": 1.0,
             "symbol": "EURUSD"},
            {"ticket": 2, "type": 1, "volume": 0.1, "price_open": 11.4, "profit": -0.5,
             "symbol": "CHFNOK"}]}), "utf-8")
    (data / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "CHFNOK_carry_asia", "symbol": "CHFNOK", "family": "carry", "status": "LIVE",
         "timeframe": "H1", "shadow_days": 20, "shadow_n": 10},
        {"name": "NOKCHF_carry_asia", "symbol": "NOKCHF", "family": "carry", "status": "STANDBY",
         "timeframe": "H1"},
        {"name": "EURZAR_overnight_gap_decay_asia", "symbol": "EURZAR",
         "family": "overnight_gap_decay", "status": "LIVE", "timeframe": "H1"},
        {"name": "retired_one", "symbol": "EURUSD", "family": "carry", "status": "RETIRED"},
    ]}), "utf-8")
    (reports / "pf_allocation.json").write_text(json.dumps({
        "book": {"CHFNOK_carry_asia": 0.04, "EURZAR_overnight_gap_decay_asia": 0.01},
        "growth": {"mean_log_per_day": 0.02},
        "marginal_delta_elog": {"CHFNOK_carry_asia": 0.04},
        "decay_posterior": {"by_sleeve": {"CHFNOK_carry_asia": {"hazard": 0.1}}},
        "effective_heat": {"top_loading": {"CHFNOK_carry_asia": -0.8}},
        "macro_regime": {"tilts": {}}}), "utf-8")
    (data / "roi_capital_evidence.json").write_text(json.dumps({
        "kind": "evidence", "by_mechanism": {
            "carry": {"roi": 0.2, "roi_status": "MEASURED", "judged": 200, "verdict": "OK"},
            "overnight_gap_decay": {"roi": 0.0, "roi_status": "MEASURED", "judged": 200,
                                    "verdict": "NEGATIVE_KNOWLEDGE"}}}), "utf-8")
    (reports / "SWAP_REJUDGE.json").write_text(json.dumps({"records": [
        {"certificate": "external.CHFNOK.carry.asia", "symbol": "CHFNOK", "family": "carry",
         "window": "asia", "edge_r": 0.12, "swap_charge_r": -0.006, "nights_per_trade": 1.2,
         "verdict": "SURVIVES"}]}), "utf-8")
    (data / "live_ledger.jsonl").write_text(
        json.dumps({"time": "2099-01-01T00:00:00+00:00", "symbol": "CHFNOK",
                    "sleeve": "CHFNOK_carry_asia", "swap": -0.31}) + "\n", "utf-8")
    (data / "broker_clock.json").write_text(json.dumps({"utc_offset_hours": 2}), "utf-8")
    terms = pd.DataFrame([
        {"observed_at": "2026-09-16T03:00:00+00:00", "symbol": "EURUSD", "swap_long": -5.66,
         "swap_short": 2.01, "swap_mode": 1, "swap_rollover3days": 3, "digits": 5,
         "contract_size": 100000.0, "tick_size": 0.00001, "tick_value": 0.909,
         "currency_profit": "USD", "currency_margin": "EUR", "margin_initial": 100000.0,
         "margin_maintenance": 0.0},
        {"observed_at": "2026-09-16T03:00:00+00:00", "symbol": "CHFNOK", "swap_long": 20.0,
         "swap_short": -60.0, "swap_mode": 1, "swap_rollover3days": 3, "digits": 5,
         "contract_size": 100000.0, "tick_size": 0.00001, "tick_value": 0.0855,
         "currency_profit": "NOK", "currency_margin": "CHF", "margin_initial": 100000.0,
         "margin_maintenance": 0.0}])
    terms.to_parquet(data / "tape" / "contract_terms" / "2026-09-16.parquet")
    (data / "universe" / "universe.json").write_text(json.dumps({
        "EURUSD": {"asset_class": "Forex"}, "CHFNOK": {"asset_class": "Forex Exotics"},
        "EURZAR": {"asset_class": "Forex Exotics", "contract_size": 100000.0, "digits": 5,
                   "tick_size": 0.00001, "currency_profit": "ZAR", "swap_long": -100.0,
                   "swap_short": 20.0}}), "utf-8")
    idx = pd.date_range("2026-01-05", periods=60, freq="h", tz="UTC")
    pd.DataFrame({"close": [1.10 + 0.001 * ((i * 7) % 11) - 0.004 for i in range(60)]},
                 index=idx).to_parquet(data / "universe" / "EURUSD_H1.parquet")
    pd.DataFrame({"close": [11.4 + 0.01 * ((i * 5) % 9) for i in range(60)]},
                 index=idx).to_parquet(data / "universe" / "CHFNOK_H1.parquet")
    pd.DataFrame({"close": [11.7] * 60}, index=idx).to_parquet(
        data / "universe" / "EURNOK_H1.parquet")
    return {"data": data, "reports": reports}


def test_a_dry_run_measures_everything_and_writes_nothing(rig: dict[str, Path]) -> None:
    out = FL.run(budget_s=30, dry_run=True)
    assert not FL.OUT_EVIDENCE.exists() and not FL.OUT_REPORT.exists()
    rep = out["report"]
    assert rep["dry_run"] is True and rep["account"]["n_positions"] == 2
    assert rep["balance_sheet"]["equity"] == 610.0           # the gateway's fresher reading
    assert rep["balance_sheet"]["margin_used"]["status"] == "UNMEASURED"  # no terminal here
    assert rep["borrow"]["status"] == "UNMEASURED_BY_CONSTRUCTION"
    assert rep["swaps_paid"]["status"] == "MEASURED" and rep["swaps_paid"]["n_deals"] == 1
    assert rep["swaps_paid"]["by_sleeve"]["CHFNOK_carry_asia"] == pytest.approx(-0.31)
    assert rep["settlement"]["rollover_hour_utc"] == 22
    # the EUR account's USD leg is priced off EURUSD; its NOK leg is priced off EURNOK's terms
    # only when the tape carries them, which it does not here -> UNMEASURED by name
    usd = rep["funding_by_currency"]["legs"]["USD"]
    assert usd["funding_price"]["status"] == "MEASURED" and usd["funding_price"]["pair"] == "EURUSD"
    assert rep["funding_by_currency"]["legs"]["NOK"]["funding_price"]["status"] == "UNMEASURED"
    # the three scenarios ran on the priced book; the 2026 event is measured off the bars
    st = rep["stress"]
    assert set(st) >= {"2020-03 pandemic liquidation", "2022 rate shock"}
    tape = [k for k in st if k.startswith("2026 tape event")]
    assert tape and st[tape[0]]["status"] == "MEASURED"
    assert st["2020-03 pandemic liquidation"]["status"] == "DECLARED"
    assert st["2020-03 pandemic liquidation"]["pnl"] < 0    # a dollar squeeze hurts long EURUSD
    assert rep["tape_event_2026"]["EURUSD"]["move"] < 0


def test_the_evidence_carries_lineage_roi_and_a_measured_financing_shift(rig) -> None:
    ev = FL.run(budget_s=30, dry_run=True)["evidence"]
    assert ev["kind"] == "evidence" and "at" in ev
    sl = ev["sleeves"]
    assert set(sl) == {"CHFNOK_carry_asia", "NOKCHF_carry_asia",
                       "EURZAR_overnight_gap_decay_asia"}      # LIVE/STANDBY only, never RETIRED
    carry = sl["CHFNOK_carry_asia"]
    # the swap rejudge priced this sleeve: a carry CREDIT of 0.006 R/trade x 0.5 trades/day
    assert carry["financing_cost_r_per_day"] == pytest.approx(-0.003)
    assert carry["financing_charged_in_replay"] is False
    assert carry["terms"]["financing_stress"]["status"] == "MEASURED"
    assert carry["terms"]["financing_stress"]["factor"] == 1.0     # consumed as a shift only
    assert carry["terms"]["research_roi"]["factor"] > 1.0          # the better mechanism
    assert sl["EURZAR_overnight_gap_decay_asia"]["terms"]["research_roi"]["factor"] < 1.0
    # NOKCHF shares CHFNOK's lineage (same legs, same family): both read the same share,
    # and the unique lineage in the book (EURZAR) is tilted up relative to them
    assert sl["NOKCHF_carry_asia"]["lineage"] == carry["lineage"]
    assert sl["NOKCHF_carry_asia"]["terms"]["lineage_concentration"]["value"] == \
        pytest.approx(carry["terms"]["lineage_concentration"]["value"])
    assert sl["EURZAR_overnight_gap_decay_asia"]["lineage_factor"] > carry["lineage_factor"]
    # descriptive terms are reported with factor 1.0 -- never consumed twice
    assert carry["terms"]["posterior_edge"]["status"] == "MEASURED"
    assert carry["terms"]["posterior_edge"]["factor"] == 1.0
    assert carry["terms"]["alpha_half_life"]["value"] == pytest.approx(6.931, rel=1e-3)
    # the book: after-financing growth, with the credit RAISING it
    book = ev["book"]
    assert book["after_financing_growth"]["after_financing_log_per_day"] > 0.02
    assert book["n_lineages_funded"] == 2
    assert all(t["factor"] == 1.0 for t in sl["NOKCHF_carry_asia"]["terms"].values()
               if t["status"] == "UNMEASURED")


def test_a_real_run_writes_both_artifacts_atomically(rig: dict[str, Path]) -> None:
    FL.run(budget_s=30, dry_run=False)
    ev = json.loads(FL.OUT_EVIDENCE.read_text("utf-8"))
    rep = json.loads(FL.OUT_REPORT.read_text("utf-8"))
    assert ev["kind"] == "evidence" and rep["dry_run"] is False
    assert not FL.OUT_EVIDENCE.with_suffix(".json.tmp").exists()
    assert rep["law"].startswith("LAWS 5m")


def test_an_empty_host_is_unmeasured_by_name_and_never_raises(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    for name in ("ACCOUNT_STATE", "GATEWAY_STATE", "SLEEVES", "ALLOCATION", "ROI_EVIDENCE",
                 "SWAP_REJUDGE", "LIVE_LEDGER", "BROKER_CLOCK", "UNIVERSE", "CAPACITY"):
        monkeypatch.setattr(FL, name, tmp_path / f"{name}.json")
    monkeypatch.setattr(FL, "TERMS_DIR", tmp_path / "terms")
    monkeypatch.setattr(FL, "BARS_DIR", tmp_path / "bars")
    monkeypatch.setattr(FL, "OUT_EVIDENCE", tmp_path / "ev.json")
    monkeypatch.setattr(FL, "OUT_REPORT", tmp_path / "rep.json")
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    out = FL.run(budget_s=5, dry_run=True)
    rep = out["report"]
    assert rep["balance_sheet"]["status"] == "UNMEASURED"
    assert rep["stress"]["status"] == "UNMEASURED"
    assert rep["swaps_paid"]["status"] == "UNMEASURED"
    assert out["evidence"]["sleeves"] == {}
    assert any("equity" in u for u in rep["unmeasured"])
