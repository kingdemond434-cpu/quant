from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from scripts.build_mt5_midnight_state import build


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), "utf-8")


def test_build_reports_mt5_conversion_state_without_execution_authority(tmp_path: Path) -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "universe" / "universe.json", {"XAUUSD": {}, "EURUSD": {}})
    (desk / "data" / "universe" / "XAUUSD_H1.parquet").write_bytes(b"bars")
    _write(
        desk / "data" / "research_queue.json",
        [{"id": "a", "status": "QUEUED"}, {"id": "b", "status": "TESTED"}],
    )
    _write(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {"survivors": {"s1": {}}})
    _write(
        desk / "reports" / "shadow" / "shadow_state.json",
        {"last_run": "2026-08-22", "s1": {"n": 7}, "s2": {"n": 3}},
    )
    _write(desk / "reports" / "markout.json", {"usable": False})
    _write(desk / "reports" / "hypothesis_demo.jsonl", {})
    _write(
        tmp_path / "data" / "intelligence" / "mt5_capability_reuse.json",
        {
            "generated_at": now.isoformat(),
            "counts": {"REACHABLE_MT5_STATIC": 3, "UNWIRED_REVIEW": 2},
        },
    )
    for path in (
        desk / "data" / "universe" / "XAUUSD_H1.parquet",
        desk / "reports" / "hypothesis_demo.jsonl",
        desk / "reports" / "markout.json",
        desk / "reports" / "UNIVERSAL_SURVIVORS.json",
    ):
        os.utime(path, (now.timestamp(), now.timestamp()))

    result = build(tmp_path, now=now)

    assert result["scope"] == "MT5_FUSION_ONLY"
    assert result["execution_authority"] is False
    assert result["universe"]["metadata_entities"] == 2
    assert result["universe"]["h1_bar_files"] == 1
    assert result["conversion"] == {
        "research_queue": {"QUEUED": 1, "TESTED": 1},
        "universal_survivors": 1,
        "shadow_sleeves": 2,
        "shadow_observations": 10,
        "shadow_last_run": "2026-08-22",
    }
    assert result["capability_reuse"]["counts"] == {
        "REACHABLE_MT5_STATIC": 3,
        "UNWIRED_REVIEW": 2,
    }
    assert result["capability_reuse"]["proof_level"] == "STATIC_REACHABILITY_ONLY"
    assert result["defects"] == []


def test_build_fails_visible_when_mt5_inputs_are_absent(tmp_path: Path) -> None:
    result = build(tmp_path, now=datetime(2026, 8, 22, 12, tzinfo=UTC))
    assert result["defects"]
    assert result["conversion"]["universal_survivors"] == 0


def test_build_names_stale_shadow_and_missing_markout(tmp_path: Path) -> None:
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "universe" / "universe.json", {"XAUUSD": {}})
    (desk / "data" / "universe" / "XAUUSD_H1.parquet").write_bytes(b"bars")
    _write(desk / "data" / "research_queue.json", [{"id": "a", "status": "DONE"}])
    _write(
        desk / "reports" / "shadow" / "shadow_state.json",
        {"last_run": "2026-08-17", "s1": {"n": 5}},
    )
    _write(desk / "reports" / "hypothesis_demo.jsonl", {})

    result = build(tmp_path, now=datetime(2026, 8, 22, 12, tzinfo=UTC))

    assert "forward shadow daily clock stale" in result["defects"]
    assert "execution markout missing; costs remain unmeasured" in result["defects"]


def test_build_counts_qquant_forward_shadow_when_legacy_book_is_empty(tmp_path: Path) -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "universe" / "universe.json", {"AUDNZD": {}})
    (desk / "data" / "universe" / "AUDNZD_H1.parquet").write_bytes(b"bars")
    _write(desk / "data" / "research_queue.json", [{"id": "a", "status": "DONE"}])
    _write(desk / "reports" / "shadow" / "shadow_state.json", {"configured_sleeves": 0})
    _write(desk / "reports" / "shadow" / "qquant_shadow_state.json", {
        "updated_at": now.isoformat(),
        "qquant.hunt16.pass": {"n": 3, "status": "ACTIVE"},
    })
    _write(desk / "reports" / "markout.json", {"usable": False})
    _write(desk / "reports" / "hypothesis_demo.jsonl", {})
    _write(tmp_path / "data" / "intelligence" / "mt5_capability_reuse.json", {
        "generated_at": now.isoformat(), "counts": {},
    })
    for path in (desk / "data" / "universe" / "AUDNZD_H1.parquet",
                 desk / "reports" / "hypothesis_demo.jsonl"):
        os.utime(path, (now.timestamp(), now.timestamp()))

    result = build(tmp_path, now=now)

    assert result["conversion"]["shadow_sleeves"] == 1
    assert result["conversion"]["shadow_observations"] == 3
    assert "forward shadow state missing or empty" not in result["defects"]


def test_build_uses_canonical_gauntlet_when_legacy_research_loop_is_stale(tmp_path: Path) -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "universe" / "universe.json", {"XAUUSD": {}})
    bars = desk / "data" / "universe" / "XAUUSD_H1.parquet"
    bars.parent.mkdir(parents=True, exist_ok=True)
    bars.write_bytes(b"bars")
    _write(desk / "data" / "research_queue.json", [{"id": "a", "status": "PENDING"}])
    _write(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {"survivors": {}})
    _write(desk / "reports" / "universal_gates_external.json", {"n_judged": 1})
    _write(desk / "reports" / "shadow" / "shadow_state.json",
           {"last_run": "2026-08-22", "s": {"n": 1}})
    _write(desk / "reports" / "markout.json", {"at": now.isoformat(), "usable": False})
    _write(tmp_path / "data" / "intelligence" / "mt5_capability_reuse.json", {
        "generated_at": now.isoformat(), "counts": {},
    })
    for path in (bars, desk / "reports" / "UNIVERSAL_SURVIVORS.json",
                 desk / "reports" / "universal_gates_external.json"):
        os.utime(path, (now.timestamp(), now.timestamp()))

    result = build(tmp_path, now=now)

    assert result["freshness"]["research_loop"] is None
    assert result["freshness"]["research_pipeline"] is not None
    assert "canonical research pipeline stale or unmeasured" not in result["defects"]


def test_build_rejects_a_stale_markout_even_when_file_mtime_is_fresh(tmp_path: Path) -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    desk = tmp_path / "desks" / "mt5"
    _write(desk / "data" / "universe" / "universe.json", {"XAUUSD": {}})
    bars = desk / "data" / "universe" / "XAUUSD_H1.parquet"
    bars.write_bytes(b"bars")
    _write(desk / "data" / "research_queue.json", [{"id": "a", "status": "DONE"}])
    _write(
        desk / "reports" / "shadow" / "shadow_state.json",
        {"last_run": "2026-08-22", "s1": {"n": 5}},
    )
    _write(desk / "reports" / "hypothesis_demo.jsonl", {})
    _write(
        desk / "reports" / "markout.json",
        {"at": "2026-08-20T00:00:00+00:00", "usable": True, "n_matched": 7},
    )
    _write(
        tmp_path / "data" / "intelligence" / "mt5_capability_reuse.json",
        {"generated_at": now.isoformat(), "counts": {}},
    )
    for path in (bars, desk / "reports" / "hypothesis_demo.jsonl"):
        os.utime(path, (now.timestamp(), now.timestamp()))

    result = build(tmp_path, now=now)

    assert "execution markout stale; current costs remain unmeasured" in result["defects"]
