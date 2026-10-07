"""DATA-19: the world sensor's ten gaps measured from synthetic host artifacts.

An empty host reads UNMEASURED on every gap with the artifact named; a populated one reads
MEASURED with numbers. Nothing touches the network or the real ledger."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sensor_ledger_digest as sld  # noqa: E402
import world_sensor_gaps as wsg  # noqa: E402

from libs.research import sensor_contract as sc  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
PROVIDERS = {"event_consensus_sources": ["ff_calendar_thisweek", "tradingeconomics_calendar"],
             "gdelt": ["gdelt_events_country", "gdelt_translingual_country"]}


def _paths(tmp: Path) -> wsg.Paths:
    return wsg.Paths(desk=tmp / "desk", ledger_root=tmp / "sensors")


def _doc(i: int, *, lang: str, dataset: str, lag_s: float, mins_ago: float) -> Any:
    rx = NOW - timedelta(minutes=mins_ago)
    pub = rx - timedelta(seconds=lag_s)
    return sc.make(sensor_id=f"news:{dataset}", source_id=dataset, dataset_id=dataset,
                   metric="document", kind="document", sensor_class="news",
                   text=f"headline {i}", language=lang, source_publication_time=pub,
                   knowable_at=pub, knowable_basis="printed_stamp", received_at=rx,
                   parse_complete_at=rx, provenance_hash=f"h{i}",
                   attributes={"copies": 1 if i % 4 == 0 else 0})


def test_an_empty_host_is_unmeasured_on_every_gap_and_names_what_it_needed(
        tmp_path: Path) -> None:
    doc = wsg.build(now=NOW, paths=_paths(tmp_path), providers=PROVIDERS, watched=[])
    assert set(doc["gaps"]) == set(wsg.GAPS) and len(wsg.GAPS) == 10
    assert doc["measured"] == 0 and doc["unmeasured"] == 10 and doc["open"] == []
    for name, g in doc["gaps"].items():
        assert g["status"] == "UNMEASURED" and g["missing"], name
        assert g["open"] is None and g["target"] == wsg.TARGETS[name]
    assert "consensus_actuals.jsonl" in doc["gaps"]["pit_consensus_actual"]["missing"][0]


def _populate(tmp: Path) -> wsg.Paths:
    p = _paths(tmp)
    led = sc.SensorLedger(p.ledger_root)
    obs = [_doc(i, lang=("en" if i % 3 else "zh"),
                dataset="rss" if i % 2 else "gdelt_events_country",
                lag_s=30 + i, mins_ago=5 + i * 10) for i in range(60)]
    led.append(obs, now=NOW)
    data = p.desk / "data"
    (data / "macro").mkdir(parents=True)
    (data / "macro" / "consensus_actuals.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"release": "US CPI", "at": (NOW - timedelta(days=2)).isoformat(), "actual": 0.3,
         "consensus": 0.2, "source_id": "fred:CPIAUCSL"},
        {"release": "EIA crude", "at": (NOW - timedelta(days=40)).isoformat(), "actual": 1.0,
         "consensus": 0.5, "source_id": "ff_calendar_thisweek"},
        {"release": "no consensus", "at": NOW.isoformat(), "actual": 1.0}]) + "\n", "utf-8")
    uni = data / "universe"
    uni.mkdir()
    (uni / "universe.json").write_text(json.dumps({"EURUSD": {}, "XAUUSD": {}, "US500": {},
                                                    "GBPUSD": {}}), "utf-8")
    (uni / "XAUUSD_M1.parquet").write_bytes(b"x")
    (uni / "EURUSD_M1.parquet").write_bytes(b"x")
    (data / "tape").mkdir()
    (data / "tape" / "tape_state.json").write_text(json.dumps({
        "EURUSD": {"last_tick_utc": (NOW - timedelta(hours=1)).isoformat()},
        "XAUUSD": {"last_tick_utc": (NOW - timedelta(days=3)).isoformat()}}), "utf-8")
    rep = p.desk / "reports"
    rep.mkdir()
    (rep / "EVENT_RESPONSE_ATLAS.json").write_text(json.dumps({
        "at": (NOW - timedelta(hours=3)).isoformat(), "n_events": 120, "n_cells": 40,
        "clearing": [{"cell": "a"}], "n_events_by_kind": {"cpi": 50, "nfp": 70}}), "utf-8")
    (rep / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({"n": 2, "survivors": {
        "hunt.EURUSD cpi_surprise_fade": {"cell": "cpi_surprise_fade", "status": "PASS"},
        "hunt.XAUUSD donchian": {"cell": "donchian", "status": "PASS"}}}), "utf-8")
    (data / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "cpi_surprise_eurusd", "family": "event_surprise", "status": "LIVE"},
        {"name": "xau_breakout", "family": "donchian", "status": "LIVE"},
        {"name": "nfp_fade", "family": "event_fade", "status": "STANDBY"}]}), "utf-8")
    (data / "allocator_resolve_queue.jsonl").write_text("\n".join(json.dumps(
        {"at": (NOW - timedelta(hours=h)).isoformat(), "event_id": f"e{h}"})
        for h in (1, 2, 30)) + "\n", "utf-8")
    (data / "allocator_reactions.jsonl").write_text(json.dumps(
        {"at": (NOW - timedelta(hours=1)).isoformat(), "kind": "macro_surprise",
         "latency_s": 40.0}) + "\n", "utf-8")
    return p


def test_a_populated_host_measures_every_gap_with_numbers(tmp_path: Path) -> None:
    p = _populate(tmp_path)
    doc = wsg.build(now=NOW, paths=p, providers=PROVIDERS,
                    watched=["desks/mt5/reports/MACRO_VIEW.json"])
    g = doc["gaps"]
    assert doc["measured"] == 10 and doc["unmeasured"] == 0
    tp = g["news_throughput"]["metrics"]
    assert tp["documents_24h"] == 60 and tp["raw_items_24h"] == 75 and tp["peak_hour"] >= 6
    assert g["news_throughput"]["open"] is True                        # 60 < 10000
    ml = g["multilingual_firehose"]["metrics"]
    assert ml["distinct_languages"] == 2 and ml["non_english_share"] == 0.3333
    gd = g["gdelt_intake"]["metrics"]
    assert gd["rows"] == 30 and gd["rows_24h"] == 30 and gd["newest_age_s"] == 300.0
    assert g["gdelt_intake"]["open"] is False
    pc = g["pit_consensus_actual"]["metrics"]
    assert pc["rows"] == 3 and pc["rows_with_both_and_stamp"] == 2 and pc["rows_30d"] == 1
    assert pc["held_sources"] == ["ff_calendar_thisweek"]              # terms gate reads it
    assert g["pit_consensus_actual"]["open"] is True
    wire = g["low_latency_wire"]["metrics"]["publication_to_receipt_s"]
    assert wire["n"] == 60 and wire["p50"] == pytest.approx(59.5)
    assert g["low_latency_wire"]["open"] is False
    mt = g["broad_m1_tick"]["metrics"]
    assert mt["m1_symbols"] == 2 and mt["m1_coverage"] == 0.5 and mt["tick_symbols_24h"] == 1
    assert g["broad_m1_tick"]["open"] is False
    assert g["measured_reactions"]["metrics"]["clearing"] == 1
    assert g["measured_reactions"]["metrics"]["event_surprise_age_s"] == "UNMEASURED"
    ca = g["event_capital_authority"]["metrics"]
    assert ca["live"] == 2 and ca["event_live"] == 1
    assert ca["certified_cells"] == 2 and ca["event_certified_cells"] == 1   # keyed by cell id
    ar = g["event_allocator_reaction"]["metrics"]
    assert ar["requests_24h"] == 2 and ar["allocator_listens_to_news"] is False
    assert ar["event_triggered_solves_7d"] == 0 and g["event_allocator_reaction"]["open"] is True
    cp = g["config_only_providers"]["metrics"]
    assert cp["declared"] == 4 and cp["observed"] == 2       # the GDELT export and the FF feed
    assert cp["config_only_by_group"] == {"event_consensus_sources": ["tradingeconomics_calendar"],
                                          "gdelt": ["gdelt_translingual_country"]}
    assert set(doc["open"]) >= {"news_throughput", "event_allocator_reaction"}


def test_the_gap_closes_when_the_allocator_watches_the_request_and_answers_it(
        tmp_path: Path) -> None:
    # The real watch list (watched=None reads allocator_trigger.sources()) names the request.
    assert any("allocator_resolve_request" in w for w in wsg._watched_paths())
    p = _populate(tmp_path)
    data = p.desk / "data"
    # Watched, requests lodged this week, no event-triggered solve yet: still open.
    g = wsg.build(now=NOW, paths=p, providers=PROVIDERS)["gaps"]["event_allocator_reaction"]
    assert g["metrics"]["allocator_listens_to_news"] is True
    assert g["metrics"]["requests_7d"] == 3 and g["open"] is True
    # The allocator answers one: closed.
    with (data / "allocator_reactions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": (NOW - timedelta(minutes=50)).isoformat(),
                             "kind": "news_resolve_request", "latency_s": 12.0}) + "\n")
    g = wsg.build(now=NOW, paths=p, providers=PROVIDERS)["gaps"]["event_allocator_reaction"]
    assert g["metrics"]["event_triggered_solves_7d"] == 1 and g["open"] is False


def test_a_watched_request_with_nothing_lodged_this_week_is_closed(tmp_path: Path) -> None:
    p = _populate(tmp_path)
    (p.desk / "data" / "allocator_resolve_queue.jsonl").write_text(json.dumps(
        {"at": (NOW - timedelta(days=9)).isoformat(), "event_id": "old"}) + "\n", "utf-8")
    g = wsg.build(now=NOW, paths=p, providers=PROVIDERS,
                  watched=["desks/mt5/data/allocator_resolve_request.json"])
    ar = g["gaps"]["event_allocator_reaction"]
    assert ar["metrics"]["requests_7d"] == 0 and ar["open"] is False


def test_the_sensor_ledger_leg_writes_the_gaps_report(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    def fake_build(**kw: Any) -> dict[str, Any]:
        calls.update(kw)
        return {"measured": 0, "unmeasured": 10, "open": [], "gaps": {}}

    monkeypatch.setattr(wsg, "build", fake_build)
    monkeypatch.setattr(sc, "digest", lambda days=2: {"status": "UNMEASURED", "shards": 0,
                                                      "index_keys": 0, "revised_keys": 0})
    out, gaps = tmp_path / "SL.json", tmp_path / "GAPS.json"
    assert sld.main(["--out", str(out), "--gaps-out", str(gaps)]) == 0
    assert json.loads(gaps.read_text("utf-8"))["unmeasured"] == 10
    assert out.exists() and calls == {"days": 2}
