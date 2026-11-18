"""Box self-repair reports: per-region forest production, the fault queue, and the log lint."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import deep_forest_regions as dfr  # noqa: E402
import fault_queue as fq  # noqa: E402
from organ_contract import CONTRACTS  # noqa: E402

NOW = datetime(2026, 11, 18, 3, 0, tzinfo=UTC)


def _jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_regions_are_judged_on_claims_and_completed_passes(tmp_path: Path) -> None:
    fresh = (NOW - timedelta(hours=2)).isoformat()
    old = (NOW - timedelta(days=3)).isoformat()
    claims = _jsonl(tmp_path / "claims.jsonl", [
        {"region": "kr", "available_time": fresh},
        {"region": "cn", "available_time": old},
        {"language": "ru", "ingested_time": old},
        {"region": "zz", "available_time": fresh},
        "not a dict",  # type: ignore[list-item]
    ])
    wm = tmp_path / "wm"
    wm.mkdir()
    (wm / "resident__dept_europe.json").write_text(json.dumps({"at": fresh, "value": 9}), "utf-8")
    doc = dfr.build(NOW, claims=claims, runs=tmp_path / "none.jsonl", watermarks=wm)
    rows = {r["forest"]: r for r in doc["regions"]}
    assert rows["korea"]["verdict"] == "PRODUCING" and rows["korea"]["claims_24h"] == 1
    assert rows["china"]["verdict"] == "IDLE" and rows["china"]["claims_7d"] == 1
    assert rows["russia_cis"]["claims_total"] == 1
    assert rows["europe"]["verdict"] == "PRODUCING" and rows["europe"]["watermark_passes"] == 9
    assert doc["claims_unowned"] == 1
    assert "claim" not in json.dumps(doc["regions"]).replace("claims", "").replace(
        "newest_claim_at", "")


def test_no_evidence_on_the_host_is_unmeasured(tmp_path: Path) -> None:
    doc = dfr.build(NOW, claims=tmp_path / "a", runs=tmp_path / "b", watermarks=tmp_path / "c")
    assert doc["verdicts"] == {"UNMEASURED": doc["n_forests"]}


def test_fault_queue_keeps_first_seen_and_clears_resolved() -> None:
    health = {"processes": [{"name": "MT5-Forest-Korea", "verdict": "STALE", "bad_reads": 3,
                             "why": "older than its contract"},
                            {"name": "MT5-Fine", "verdict": "OK", "bad_reads": 0}]}
    ns = {"escalated": [{"task": "MT5-Gateway", "verdict": "FAILING", "code": 1,
                         "diagnosis": "exit 1"}],
          "acted": [{"task": "MT5-X", "verdict": "STALE", "action": "start FAILED",
                     "detail": "access denied"}]}
    first = fq.merge({}, fq.detect(health, ns, {}), NOW)
    assert first["n_open"] == 3 and first["open_by_kind"] == {
        "bad_streak": 1, "needs_human": 1, "heal_failed": 1}
    later = NOW + timedelta(hours=1)
    second = fq.merge(first, fq.detect(health, {}, {}), later)
    assert second["n_open"] == 1
    row = second["open"][0]
    assert row["first_queued_at"] == NOW.isoformat(timespec="seconds")
    assert row["passes_open"] == 2
    assert {r["key"] for r in second["resolved"]} == {"escalated:MT5-Gateway",
                                                      "heal_failed:MT5-X"}


def test_idle_forest_is_a_fault() -> None:
    found = fq.detect({}, {}, {"regions": [{"forest": "africa", "task": "MT5-Forest-Africa",
                                            "verdict": "IDLE"}]})
    assert list(found) == ["forest_idle:africa"]


#: Contracts judged on a log file, which moves on errors as well as on output. The set may only
#: shrink: a new organ is contracted on what it PRODUCES (box self-repair F6, 2026-11-18).
LOG_CONTRACTS_GRANDFATHERED = frozenset({
    "MT5-Healers", "MT5-MoatSilver", "MT5-UniversalGate", "MT5-CacheWarm",
    "MT5-IdentityHealer", "MT5-NewsDesk", "MT5-AuditLane", "MT5-ConvertSwarm", "MT5-DeepSeek",
})


@pytest.mark.parametrize("name", sorted(CONTRACTS))
def test_no_new_contract_is_judged_on_a_log(name: str) -> None:
    artifact = CONTRACTS[name][0].replace("\\", "/")
    if "/logs/" in artifact:
        assert name in LOG_CONTRACTS_GRANDFATHERED, (
            f"{name} is contracted on {artifact}: a log moves on errors too. Contract it on the "
            f"file it produces.")
