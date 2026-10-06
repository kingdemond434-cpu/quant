"""The news stream as a FIREHOSE: no item cap, a cursor, durable spill, syndication dedup,
GDELT story groups, sequenced re-solve requests and a measured intake report.

EVERY INPUT IS SYNTHETIC AND NOTHING HERE TOUCHES THE NETWORK OR THE REGISTRY. Every path the
module writes is redirected into `tmp_path`; the deep lane's registry write and the registry
conversion read are stubbed, so a pass here proves the intake mechanism and nothing else.

THE LOAD-BEARING TEST is `test_a_busy_hour_is_read_in_full_not_cut_at_400`: until 2026-10-06 a
pass kept the 400 newest items and silently dropped the rest. 1,000 captures must all be read.
"""
from __future__ import annotations

import gzip
import io
import json
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import news_event_stream as nes  # noqa: E402

NOW = datetime.now(UTC).replace(microsecond=0)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data, reports = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    reports.mkdir()
    paths = {
        "WORLD_STATE": data / "world_state.json",
        "RESOLVE_REQUEST": data / "allocator_resolve_request.json",
        "EVENT_LOG": data / "events" / "events.jsonl",
        "REPORT": reports / "NEWS_EVENT_STREAM.json",
        "NEWS_CAPTURES": data / "news_captures.jsonl",
        "INTEL": data / "intelligence",
        "MOAT_NORMALIZED": tmp_path / "moat" / "normalized",
        "UNIVERSE": data / "universe.json", "ATLAS": reports / "ATLAS.json",
        "EXEC_ALPHA": reports / "EXEC.json", "COT": data / "cot.json",
        "MACRO_STATE": data / "macro_state.json", "CALENDAR": data / "calendar.json",
        "ACTOR_ATLAS": data / "actor_atlas.json", "CURSOR": data / "cursor.json",
        "PENDING": data / "pending.jsonl", "RESOLVE_QUEUE": data / "resolve_queue.jsonl",
        "INTAKE_REPORT": reports / "WORLD_SENSOR_INTAKE.json",
        "LOCK": data / "locks" / "nes.lock", "SENSOR_ROOT": data / "sensors",
    }
    for name, value in paths.items():
        monkeypatch.setattr(nes, name, value)
    monkeypatch.setattr(nes, "GDELT_VAULTS", (
        ("gdelt_events", data / "vault" / "alt_gdelt_events_country"),
        ("gdelt_translingual", data / "vault" / "alt_gdelt_translingual_country")))
    monkeypatch.setattr(nes, "record_deep", lambda event, deep, notes: {
        "memory": None, "discoveries": 1, "status": "stubbed"})
    monkeypatch.setattr(nes, "_conversion", lambda: {"status": "stubbed"})
    return tmp_path


def _capture(i: int, title: str | None = None, source: str = "reuters",
             published: datetime | None = None) -> dict[str, Any]:
    pub = published or (NOW - timedelta(minutes=30))
    return {"source": source, "title": title or f"Headline number {i} about markets",
            "text": "", "url": f"https://{source}.example/{i}",
            "published_utc": pub.isoformat(), "fetched_utc": (pub + timedelta(seconds=40))
            .isoformat()}


def _write_captures(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_a_busy_hour_is_read_in_full_not_cut_at_400(desk: Path) -> None:
    _write_captures([_capture(i) for i in range(1000)], nes.NEWS_CAPTURES)
    out = nes.run(budget_s=0)
    assert out["items_new"] == 1000
    assert out["items_processed"] == 1000
    assert out["items_spilled"] == 0


def test_the_cursor_reads_only_what_arrived_since(desk: Path) -> None:
    _write_captures([_capture(i) for i in range(30)], nes.NEWS_CAPTURES)
    nes.run(budget_s=0)
    _write_captures([_capture(1000 + i) for i in range(5)], nes.NEWS_CAPTURES)
    out = nes.run(budget_s=0, now=NOW + timedelta(minutes=1))
    assert out["items_new"] == 5


def test_a_syndicated_copy_is_an_observation_not_evidence(desk: Path) -> None:
    title = "Iran seizes oil tanker in the Strait of Hormuz"
    _write_captures([_capture(1, title, "reuters"), _capture(2, title, "apnews"),
                     _capture(3, title.upper() + "!", "investing")], nes.NEWS_CAPTURES)
    out = nes.run(budget_s=0)
    assert out["syndicated_copies"] == 2
    assert len(out["events"]) == 1
    intake = json.loads(nes.INTAKE_REPORT.read_text())
    m = intake["metrics"]
    assert m["raw_observations"] == 3
    assert m["unique_documents"] == 1
    assert m["duplicate_compression_ratio"] == 3.0
    assert m["latency_s"]["publication_to_receipt"]["p50"] == 40.0


def test_what_a_pass_cannot_reach_is_owed_to_the_next(desk: Path) -> None:
    _write_captures([_capture(i) for i in range(20)], nes.NEWS_CAPTURES)
    first = nes.run(budget_s=1e-12)
    assert first["items_spilled"] == 20 and first["items_processed"] == 0
    assert nes.PENDING.exists()
    second = nes.run(budget_s=0, now=NOW + timedelta(minutes=1))
    assert second["items_owed_from_last_pass"] == 20
    assert second["items_processed"] == 20
    assert not nes.PENDING.exists()


def _gdelt_blob(code: str, root: str, fips: str, n: int, slot: str) -> bytes:
    lines = []
    for i in range(n):
        c = [""] * 61
        c[0] = str(1000 + i)
        c[6], c[7] = "IRAN", "IRN"
        c[16], c[17] = "ISRAEL", "ISR"
        c[26], c[27], c[28] = code, code[:3], root
        c[29], c[30], c[31], c[32], c[33], c[34] = "4", "-10", "10", "6", "10", "-7.5"
        c[52], c[53] = "Tehran, Iran", fips
        c[59] = slot
        c[60] = f"https://press.example/{i % 3}"
        lines.append("\t".join(c))
    raw = ("\n".join(lines) + "\n").encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{slot}.export.CSV", raw)
    return buf.getvalue()


def _vault(folder: Path, digest: str, body: bytes, slot: str, translated: bool = False) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{digest}.gz").write_bytes(gzip.compress(body))
    kind = "translation.export" if translated else "export"
    (folder / f"{digest}.meta.json").write_text(json.dumps({
        "url": f"http://data.gdeltproject.org/gdeltv2/{slot}.{kind}.CSV.zip",
        "fetched_utc": (NOW - timedelta(minutes=10)).isoformat()}))


def test_gdelt_blobs_become_story_groups_and_backfill_stays_history(desk: Path) -> None:
    recent = (NOW - timedelta(minutes=30)).strftime("%Y%m%d%H%M00")
    recent = recent[:10] + f"{int(recent[10:12]) // 15 * 15:02d}00"
    old = (NOW - timedelta(days=9)).strftime("%Y%m%d%H0000")
    folder = nes.GDELT_VAULTS[1][1]
    _vault(folder, "aaaa", _gdelt_blob("190", "19", "IR", 12, recent), recent, translated=True)
    _vault(folder, "bbbb", _gdelt_blob("190", "19", "IR", 12, old), old, translated=True)
    _vault(folder, "cccc", _gdelt_blob("042", "04", "IR", 7, recent), recent, translated=True)
    out = nes.run(budget_s=0)
    g = out["grounds"]["gdelt_translingual"]
    assert g["too_old"] == 1
    assert g["blobs"] == 2 and g["rows"] == 19 and g["documents"] == 6
    wars = [e for e in out["events"] if e["kind"] == "war_escalation"]
    assert len(wars) == 1
    assert wars[0]["origin"] == "gdelt:gdelt_translingual"
    assert wars[0]["copies"] == 11
    assert "UNMEASURED" in wars[0]["surprise_basis"]          # no baseline yet: a named prior
    assert {"IR", "IL"} <= set(wars[0]["entities"])
    # a second pass reads nothing it already read
    again = nes.run(budget_s=0, now=NOW + timedelta(minutes=1))
    assert again["grounds"]["gdelt_translingual"]["blobs"] == 0


def test_anomaly_surprise_measures_coverage_against_its_own_history() -> None:
    base: dict[str, Any] = {}
    for _ in range(nes.ANOMALY_WARMUP):
        nes.anomaly_surprise(base, "war|IR", 10.0 + (_ % 3))
    calm = nes.anomaly_surprise(base, "war|IR", 11.0)
    spike = nes.anomaly_surprise(base, "war|IR", 80.0)
    assert calm.measured and spike.measured
    assert spike.score > calm.score
    assert spike.score == 1.0


def test_resolve_requests_are_sequenced_and_fingerprinted(desk: Path) -> None:
    _write_captures([_capture(1, "Russia invades and launches missile strikes on Ukraine",
                              "reuters")], nes.NEWS_CAPTURES)
    out = nes.run(budget_s=0)
    assert out["resolve_requests"]
    _write_captures([_capture(2, "OPEC announces surprise output cut, pipeline explosion halts "
                                 "exports", "apnews")], nes.NEWS_CAPTURES)
    nes.run(budget_s=0, now=NOW + timedelta(minutes=2))
    queue = [json.loads(x) for x in nes.RESOLVE_QUEUE.read_text().splitlines()]
    assert [q["seq"] for q in queue] == list(range(1, len(queue) + 1))
    assert all(len(q["world_state_fingerprint"]) == 16 for q in queue)
    latest = json.loads(nes.RESOLVE_REQUEST.read_text())
    assert latest["seq"] == queue[-1]["seq"]
    assert latest["observation_ids"] and all(isinstance(i, str) for i in latest["observation_ids"])


def test_first_sight_of_a_ground_does_not_replay_its_history(desk: Path) -> None:
    rows = [_capture(i) for i in range(5)]
    _write_captures(rows, nes.NEWS_CAPTURES)
    seat = nes.INTEL / "central_banks"
    seat.mkdir(parents=True)
    stale = seat / "old.json"
    stale.write_text(json.dumps({"items": [_capture(99, "Old statement")]}))
    import os
    old = (NOW - timedelta(days=5)).timestamp()
    os.utime(stale, (old, old))
    out = nes.run(budget_s=0)
    assert out["items_new"] == 5
