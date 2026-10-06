from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from side_channels import discovery_io as io  # noqa: E402

from libs.data.pit import is_stamped, payload_hash  # noqa: E402


def test_discovery_archive_and_returned_intake_have_the_same_provenance(tmp_path: Path) -> None:
    path = tmp_path / "source" / "discoveries_today.json"
    raw = [{"title": "captured recipe", "captured_at": "2026-10-03T08:00:00+00:00"}]
    emitted = io.write_discoveries(path, raw)
    assert json.loads(path.read_text("utf-8")) == emitted
    assert is_stamped(emitted[0])
    assert emitted[0]["payload_hash"] == payload_hash(emitted[0])
    assert emitted[0]["available_time"] == raw[0]["captured_at"]
    assert "payload_hash" not in raw[0]


def test_refused_batch_cannot_erase_prior_discoveries(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "discoveries_today.json"
    qpath = tmp_path / "quarantine" / "discoveries.jsonl"
    path.write_text('[{"title":"previous"}]', encoding="utf-8")
    monkeypatch.setattr(io, "stamp_or_refuse", lambda *_: ([], [{"why": "no provenance"}]))
    out = io.write_discoveries(path, [{"title": "new"}], quarantine=qpath)
    assert out == [] and out.quarantined == 1
    assert json.loads(path.read_text("utf-8")) == [{"title": "previous"}]
    assert json.loads(qpath.read_text("utf-8"))["row"] == {"title": "new"}


def test_one_bad_row_is_quarantined_and_the_rest_are_written(tmp_path: Path,
                                                             monkeypatch) -> None:
    """A single unstampable or non-object row used to throw the whole batch away."""
    path = tmp_path / "seat" / "discoveries_today.json"
    qpath = tmp_path / "quarantine" / "discoveries.jsonl"
    real = io.stamp_or_refuse

    def door(rows, source):
        if rows and rows[0].get("title") == "bad":
            return [], [{"why": "stamp produced no available_time", "title": "bad"}]
        return real(rows, source)

    monkeypatch.setattr(io, "stamp_or_refuse", door)
    rows = [{"title": "good one", "captured_at": "2026-10-03T08:00:00+00:00"},
            {"title": "bad"},
            "not a row",
            {"title": "good two", "captured_at": "2026-10-03T09:00:00+00:00"}]
    out = io.write_discoveries(path, rows, quarantine=qpath)
    assert [r["title"] for r in out] == ["good one", "good two"]
    assert out.quarantined == 2 and out.quarantine_path == qpath
    assert json.loads(path.read_text("utf-8")) == list(out)
    lines = [json.loads(x) for x in qpath.read_text("utf-8").splitlines()]
    assert [x["index"] for x in lines] == [1, 2]
    assert all(x["why"] and x["destination"] == str(path) for x in lines)
    assert "available_time" in lines[0]["why"] and lines[0]["row"] == {"title": "bad"}


def test_a_clean_batch_quarantines_nothing(tmp_path: Path) -> None:
    qpath = tmp_path / "q.jsonl"
    out = io.write_discoveries(tmp_path / "s" / "d.json",
                               [{"title": "x", "captured_at": "2026-10-03T08:00:00+00:00"}],
                               quarantine=qpath)
    assert out.quarantined == 0 and out.quarantine_path is None and not qpath.exists()


def test_the_quarantine_is_outside_the_compilers_intake_glob() -> None:
    from research import discovery_compiler as dc

    assert dc.INTEL not in io.QUARANTINE.parents


def test_interrupted_replace_preserves_existing_archive(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "discoveries_today.json"
    path.write_text('[{"title":"previous"}]', encoding="utf-8")

    def fail(*_):
        raise OSError("disk failure")

    monkeypatch.setattr(io.os, "replace", fail)
    with pytest.raises(OSError, match="disk failure"):
        io.write_discoveries(path, [{"title": "new"}])
    assert json.loads(path.read_text("utf-8")) == [{"title": "previous"}]
    assert list(tmp_path.glob("*.tmp")) == []


def test_converter_archive_and_latest_are_identically_stamped(tmp_path, monkeypatch):
    from side_channels import convert_to_hypotheses as converter

    raw = [{"symbol": "USDJPY", "family": "carry", "params": {}, "source": "fixture"}]
    monkeypatch.setattr(converter, "OUT", tmp_path)
    monkeypatch.setattr(converter, "convert_discoveries", lambda: raw)
    converter.save_hypotheses()
    latest = json.loads((tmp_path / "latest_external.json").read_text("utf-8"))
    archive = next(tmp_path.glob("external_*.json"))
    assert latest == json.loads(archive.read_text("utf-8"))
    assert is_stamped(latest[0])
    assert latest[0]["payload_hash"] == payload_hash(latest[0])
    assert "payload_hash" not in raw[0]


def test_bridge_grid_preserves_executable_identity_and_adds_provenance(tmp_path, monkeypatch):
    from side_channels import bridge_to_hunt as bridge

    monkeypatch.setattr(bridge, "HYPO", tmp_path)
    raw = [{"symbol": "USDJPY", "family": "carry", "params": {"x": 1}}]
    saved = json.loads(bridge.save_grid(raw).read_text("utf-8"))
    assert {k: saved[0][k] for k in raw[0]} == raw[0]
    assert is_stamped(saved[0])
    assert saved[0]["payload_hash"] == payload_hash(saved[0])


def test_every_write_leaves_a_receipt_naming_the_producer(tmp_path: Path) -> None:
    qpath = tmp_path / "q" / "discoveries.jsonl"
    rpath = tmp_path / "q" / "write_receipts.jsonl"
    io.write_discoveries(tmp_path / "seat_a" / "d1.json",
                         [{"title": "x", "captured_at": "2026-10-03T08:00:00+00:00"}, "bad"],
                         quarantine=qpath, receipts=rpath)
    io.write_discoveries(tmp_path / "seat_b" / "d2.json",
                         [{"title": "y", "captured_at": "2026-10-03T08:00:00+00:00"}],
                         quarantine=qpath, receipts=rpath)
    got = [json.loads(x) for x in rpath.read_text("utf-8").splitlines()]
    assert [(g["producer"], g["artifact"], g["written"], g["quarantined"]) for g in got] == [
        ("seat_a", "d1.json", 1, 1), ("seat_b", "d2.json", 1, 0)]


def test_producer_breadth_publishes_quarantined_rows_per_producer(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from research import producer_breadth as pb

    rpath = tmp_path / "write_receipts.jsonl"
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    rows = [{"at": "2026-10-06T10:00:00+00:00", "producer": "cot", "written": 5, "quarantined": 2},
            {"at": "2026-10-05T10:00:00+00:00", "producer": "cot", "written": 4, "quarantined": 1},
            {"at": "2026-09-01T10:00:00+00:00", "producer": "cot", "written": 9, "quarantined": 9},
            {"at": "2026-10-06T11:00:00+00:00", "producer": "china", "written": 3,
             "quarantined": 0}]
    rpath.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    got, why = pb.quarantine_by_seat(now, rpath)
    assert got == {"cot": {"writes": 2, "written": 9, "quarantined": 3},
                   "china": {"writes": 1, "written": 3, "quarantined": 0}}
    absent, why = pb.quarantine_by_seat(now, tmp_path / "none.jsonl")
    assert absent == {} and why.startswith(pb.UNMEASURED)


def test_the_receipts_rotate_by_size_and_the_totals_stay_exact(tmp_path: Path,
                                                              monkeypatch) -> None:
    """Audit of #222: both door files grew without bound. Past the cap the live file becomes
    `.1`, the old `.1` is folded into totals.json, and totals + `.1` + live == every write."""
    qpath = tmp_path / "q" / "discoveries.jsonl"
    rpath = tmp_path / "q" / "write_receipts.jsonl"
    monkeypatch.setattr(io, "MAX_SEGMENT_BYTES", 400)
    for k in range(40):
        io.write_discoveries(tmp_path / f"seat_{k % 2}" / f"d{k}.json",
                             [{"title": "x", "captured_at": "2026-10-03T08:00:00+00:00"},
                              "bad"], quarantine=qpath, receipts=rpath)
    segs = [s for s in (rpath.parent / (rpath.name + ".1"), rpath) if s.exists()]
    assert all(s.stat().st_size < 2 * 400 for s in segs)
    assert (rpath.parent / (rpath.name + ".1")).exists()
    totals = json.loads(io.totals_path(rpath).read_text("utf-8"))
    live = [json.loads(x) for seg in segs for x in seg.read_text("utf-8").splitlines()]
    writes = sum(v["writes"] for v in totals["by_producer"].values()) + len(live)
    quarantined = (sum(v["quarantined"] for v in totals["by_producer"].values())
                   + sum(r["quarantined"] for r in live))
    assert writes == 40 and quarantined == 40
    qtot = json.loads(io.totals_path(qpath).read_text("utf-8"))
    qlive = sum(len(seg.read_text("utf-8").splitlines())
                for seg in (qpath.parent / (qpath.name + ".1"), qpath) if seg.exists())
    assert sum(v["quarantined"] for v in qtot["by_producer"].values()) + qlive == 40


def test_a_fold_is_never_counted_twice(tmp_path: Path) -> None:
    rpath = tmp_path / "write_receipts.jsonl"
    seg = tmp_path / "write_receipts.jsonl.1"
    seg.write_text(json.dumps({"producer": "a", "written": 2, "quarantined": 1}) + "\n", "utf-8")
    io._fold(seg, io._tally_receipts)
    io._fold(seg, io._tally_receipts)                # the pass died before the delete
    doc = json.loads(io.totals_path(rpath).read_text("utf-8"))
    assert doc["by_producer"]["a"] == {"writes": 1, "written": 2, "quarantined": 1}
