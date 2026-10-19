"""The cold phase must never be handed an empty state (addendum section 3).

These tests pin the packet's contract: every section is measured from a named artifact, the
hash identifies content rather than the second it ran, and an unreadable tree is reported as
UNAVAILABLE rather than passed off as an empty but valid context.
"""
from __future__ import annotations

import json
from pathlib import Path

from libs.ops.deepseek_cycle import research_packet
from libs.ops.deepseek_packet import build


def _write(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _fixture(tmp_path: Path) -> Path:
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "universe" / "universe.json", {
        "EURUSD": {"tradeable": True, "category": "FX", "last": "2026-10-19 22:00:00+00:00",
                   "bars_by_timeframe": {"H1": 9000, "M5": 5000}},
        "XAUUSD": {"tradeable": True, "category": "Metals", "last": "2026-10-19 22:00:00+00:00",
                   "bars_by_timeframe": {"H1": 9000}},
        "DELISTED": {"tradeable": False, "category": "FX", "bars_by_timeframe": {}},
    })
    _write(desk / "data" / "sleeves.json", {"sleeves": [
        {"name": "a", "status": "LIVE"}, {"name": "b", "status": "RETIRED"},
    ]})
    _write(desk / "data" / "account_state.json", {
        "venue": "Fusion Markets Pty Ltd", "currency": "EUR", "balance": 484.83,
        "equity": 484.83, "open_positions": 0,
    })
    _write(desk / "reports" / "pf_allocation.json", {
        "mode": "LIVE", "armed": True, "effective_heat": 0.1, "book": {"a": 1},
        "mechanism_mix": {"breakout": 0.5}, "no_trade": False,
    })
    _write(desk / "data" / "hypotheses" / "admissible_docket.json", {
        "n": 2, "cells": [{"family": "formula"}, {"family": "formula"}],
    })
    _write(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {
        "n": 2, "survivors": {"EURUSD.formula.p=1": {"hunt": "external_discoveries"}},
    })
    _write(desk / "data" / "hypotheses" / "miner_deepening_queue.json", {"tasks": [{}, {}]})
    ledger = desk / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps({"passed": False, "terminal_gate": "UNKNOWN", "family": "formula",
                    "failed_gates": ["observations"], "prereg_status": "POST_HOC"}) + "\n"
        + json.dumps({"passed": True, "terminal_gate": "PASS", "family": "formula"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "research").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "graveyard.md").write_text("# graveyard\none\n", encoding="utf-8")
    (tmp_path / "docs" / "research" / "capability_challengers.jsonl").write_text(
        "{}\n", encoding="utf-8")
    (desk / "data" / "axes").mkdir(parents=True, exist_ok=True)
    (desk / "data" / "axes" / "bis.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_packet_is_measured_from_named_artifacts(tmp_path: Path) -> None:
    packet = build(_fixture(tmp_path))
    assert packet["status"] == "MEASURED"
    assert packet["sections_measured"] >= 6
    assert packet["sections"]["universe"]["tradeable"] == 2
    assert packet["sections"]["universe"]["by_category"]["FX"] == 2
    assert packet["sections"]["research_frontier"]["docket_rows"] == 2
    assert packet["sections"]["research_frontier"]["certified_survivors"] == 2
    assert packet["sections"]["empirical_memory"]["judgements_in_tail"] == 2
    assert packet["sections"]["empirical_memory"]["passed_in_tail"] == 1
    assert packet["sections"]["portfolio_opportunity_state"]["sleeves"] == 2
    assert packet["sections"]["conversion_inventory"]["deepening_queue"] == 2
    assert packet["sections"]["point_in_time_metadata"]["artifacts"]


def test_packet_hash_identifies_content_not_clock(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    first, second = build(root), build(root)
    assert first["packet_hash"] == second["packet_hash"]
    assert first["generated_utc"] != "" and len(first["packet_hash"]) == 64


def test_an_unreadable_tree_is_unavailable_not_empty(tmp_path: Path) -> None:
    packet = research_packet(tmp_path)
    assert isinstance(packet, dict) and packet
    assert packet["status"] in {"PARTIAL", "UNAVAILABLE"}
    assert packet.get("why") or packet.get("sections")
    assert packet.get("sections") is not None
