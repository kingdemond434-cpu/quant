from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import contract_spec_diff as csd

NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)


def term(sym: str, **kw) -> dict:
    row = {"symbol": sym, "observed_at": NOW.isoformat(), "quote_time_utc": NOW.isoformat(),
           "contract_size": 100.0, "tick_size": 0.01, "tick_value": 0.86, "digits": 2,
           "volume_min": 0.01, "currency_profit": "USD", "swap_mode": 1,
           "swap_rollover3days": 3, "trade_mode": 4}
    row.update(kw)
    return row


def reg(**kw) -> dict:
    row = {"contract_size": 100.0, "tick_size": 0.01, "tick_value": 0.862, "digits": 2,
           "min_volume": 0.01, "currency_profit": "USD", "swap_mode": 1,
           "swap_rollover3days": 3}
    row.update(kw)
    return row


def test_matching_specs_are_clean_and_fx_drift_inside_tolerance_passes() -> None:
    r = csd.compare({"XAUUSD": term("XAUUSD")}, {"XAUUSD": reg()}, {"XAUUSD"})
    assert r["mismatches"] == [] and r["alerts"] == [] and r["fixes"] == {}


def test_a_changed_contract_is_a_live_mismatch_with_the_brokers_fix() -> None:
    r = csd.compare({"XAUUSD": term("XAUUSD", contract_size=10.0, volume_min=0.1)},
                    {"XAUUSD": reg()}, {"XAUUSD"})
    fields = {m["field"] for m in r["live_mismatches"]}
    assert fields == {"contract_size", "volume_min"}
    assert r["fixes"]["XAUUSD"] == {"contract_size": 10.0, "volume_min": 0.1}


def test_stale_tick_value_beyond_fx_tolerance_is_fixed() -> None:
    r = csd.compare({"USDJPY": term("USDJPY", tick_value=0.60, currency_profit="JPY")},
                    {"USDJPY": reg(tick_value=0.50, currency_profit="JPY")}, set())
    (m,) = r["mismatches"]
    assert m["field"] == "tick_value" and m["kind"] == "stale_fx" and m["live"] is False
    assert r["fixes"]["USDJPY"]["tick_value"] == 0.60


def test_eur_profit_tick_value_is_exact() -> None:
    r = csd.compare({"GER40": term("GER40", tick_value=0.01, currency_profit="EUR")},
                    {"GER40": reg(tick_value=0.0101, currency_profit="EUR")}, set())
    assert [m["field"] for m in r["mismatches"]] == ["tick_value"]


def test_close_only_and_unresolvable_swap_mode_alert_on_live_symbols_only() -> None:
    terms = {"XAUUSD": term("XAUUSD", trade_mode=3, swap_mode=6),
             "EURUSD": term("EURUSD", trade_mode=0)}
    r = csd.compare(terms, {"XAUUSD": reg(swap_mode=6), "EURUSD": reg()}, {"XAUUSD"})
    kinds = {(a["symbol"], a["alert"]) for a in r["alerts"]}
    assert kinds == {("XAUUSD", "trade_mode"), ("XAUUSD", "swap_mode_unresolvable")}


def test_degenerate_broker_readings_are_never_compared_or_written() -> None:
    r = csd.compare({"XAUUSD": term("XAUUSD", contract_size=0.0, tick_value=0.0,
                                    currency_profit="")}, {"XAUUSD": reg()}, {"XAUUSD"})
    assert r["mismatches"] == [] and r["fixes"] == {}


def test_a_mass_change_is_treated_as_a_reading_fault_and_withheld() -> None:
    syms = [f"S{i}" for i in range(10)]
    terms = {s: term(s, contract_size=1.0) for s in syms}
    terms["S0"]["digits"] = 3
    r = csd.compare(terms, {s: reg() for s in syms}, set())
    assert r["withheld_fields"] == {"contract_size": 10}
    assert r["fixes"] == {"S0": {"digits": 3.0}}


def test_stale_quotes_do_not_count_as_the_brokers_word() -> None:
    old = (NOW - timedelta(hours=csd.FRESH_H + 1)).isoformat()
    df = pd.DataFrame([term("XAUUSD", quote_time_utc=old, contract_size=1.0)])
    assert csd.latest_terms([df], NOW) == {}
    df2 = pd.DataFrame([term("XAUUSD", observed_at=(NOW - timedelta(hours=1)).isoformat(),
                             contract_size=5.0),
                        term("XAUUSD", contract_size=7.0)])
    assert csd.latest_terms([df2], NOW)["XAUUSD"]["contract_size"] == 7.0


def test_apply_merges_fixes_raises_and_clears_the_alarm(tmp_path: Path, monkeypatch) -> None:
    terms_dir = tmp_path / "terms"
    terms_dir.mkdir()
    registry = tmp_path / "universe.json"
    registry.write_text(json.dumps({"XAUUSD": reg(), "EURUSD": reg()}), "utf-8")
    monkeypatch.setattr(csd, "TERMS", terms_dir)
    monkeypatch.setattr(csd, "REGISTRY", registry)
    monkeypatch.setattr(csd, "OUT", tmp_path / "CONTRACT_SPEC_DIFF.json")
    monkeypatch.setattr(csd, "ALARM", tmp_path / "CONTRACT_SPEC_ALARM.txt")
    monkeypatch.setattr(csd, "PENDING", tmp_path / "pending.json")
    monkeypatch.setattr(csd, "_live_symbols", lambda: {"XAUUSD"})
    day1 = [term("XAUUSD", contract_size=10.0), term("EURUSD", volume_min=0.1)]
    pd.DataFrame(day1).to_parquet(terms_dir / "2026-11-11.parquet")

    # Day 1: the non-live fix lands; the live one is held and alarmed.
    doc = csd.run(apply=True, now=NOW)
    assert doc["status"] == "MISMATCH" and doc["applied"] == {"EURUSD": ["volume_min"]}
    assert doc["live_fixes_held_for_confirmation"] == {"XAUUSD": {"contract_size": 10.0}}
    assert json.loads(registry.read_text("utf-8"))["XAUUSD"]["contract_size"] == 100.0
    assert "held until a second daily read" in (tmp_path / "CONTRACT_SPEC_ALARM.txt").read_text()

    # Same day again: still held.
    assert csd.run(apply=True, now=NOW + timedelta(hours=2))["applied"] == {}

    # Day 2, same broker value: it lands.
    d2 = (NOW + timedelta(days=1)).isoformat()
    day2 = [term("XAUUSD", contract_size=10.0, observed_at=d2, quote_time_utc=d2),
            term("EURUSD", volume_min=0.1, observed_at=d2, quote_time_utc=d2)]
    pd.DataFrame(day2).to_parquet(terms_dir / "2026-11-12.parquet")
    doc2 = csd.run(apply=True, now=NOW + timedelta(days=1))
    assert doc2["applied"] == {"XAUUSD": ["contract_size"]}
    assert json.loads(registry.read_text("utf-8"))["XAUUSD"]["contract_size"] == 10.0

    doc3 = csd.run(apply=True, now=NOW + timedelta(days=1, hours=1))
    assert doc3["status"] == "MATCH" and not (tmp_path / "CONTRACT_SPEC_ALARM.txt").exists()
    assert not (tmp_path / "pending.json").exists()


def test_a_live_reading_that_changes_between_days_never_lands() -> None:
    fixes = {"XAUUSD": {"tick_value": 0.9}}
    _, book, held = csd.confirm_live(fixes, {"XAUUSD"}, {}, "2026-11-11")
    assert held == fixes and book["XAUUSD"]["tick_value"]["first_seen"] == "2026-11-11"
    apply, book2, _ = csd.confirm_live({"XAUUSD": {"tick_value": 0.95}}, {"XAUUSD"}, book,
                                           "2026-11-12")
    assert apply == {} and book2["XAUUSD"]["tick_value"]["first_seen"] == "2026-11-12"
    apply3, _, _ = csd.confirm_live({"XAUUSD": {"tick_value": 0.95}}, {"XAUUSD"}, book2,
                                    "2026-11-13")
    assert apply3 == {"XAUUSD": {"tick_value": 0.95}}


def test_no_fresh_terms_is_unmeasured_not_a_match(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(csd, "TERMS", tmp_path / "none")
    registry = tmp_path / "universe.json"
    registry.write_text(json.dumps({"XAUUSD": reg()}), "utf-8")
    monkeypatch.setattr(csd, "REGISTRY", registry)
    monkeypatch.setattr(csd, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(csd, "ALARM", tmp_path / "alarm.txt")
    monkeypatch.setattr(csd, "PENDING", tmp_path / "pending.json")
    doc = csd.run(apply=True, now=NOW)
    assert doc["status"] == "UNMEASURED" and "terms recorder" in doc["why"]
    assert doc["live_symbols_without_terms"]
