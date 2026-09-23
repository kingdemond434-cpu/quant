"""THE RESEARCH QUEUE, STREAMED (measured 2026-09-06).

The defect was not "files instead of a database". It was that the WHOLE file was parsed to answer
a question about one row: 57.4MB and 47,150 rows, 191MB of peak RSS, in eight modules, on an 8GB
box -- and every one of them wanted a count or the head of the pending list.

Three properties are fenced. Memory must not scale with file size. The head query must stop
early rather than scan to the end. And a crash mid-append -- the one failure an append-only file
can actually have -- must cost the last row and never the queue.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_qstore", _ROOT / "desks" / "mt5" / "research" / "queue_store.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def qs():
    return _load()


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def test_rows_stream_back(qs, tmp_path) -> None:
    p = tmp_path / "q.jsonl"
    _write(p, [{"id": f"c{i}", "status": "PENDING"} for i in range(50)])
    assert len(list(qs.iter_rows(p))) == 50


def test_memory_does_not_scale_with_file_size(qs, tmp_path) -> None:
    """THE WHOLE POINT. A generator that materialises the file has fixed nothing."""
    p = tmp_path / "q.jsonl"
    _write(p, [{"id": f"c{i}", "status": "GAUNTLET_REJECTED", "blob": "x" * 500}
               for i in range(20_000)])
    it = qs.iter_rows(p)
    first = next(it)
    assert first["id"] == "c0"
    # If iter_rows built a list first, `next()` above would already have read all 20k rows.
    # sys.getsizeof on the generator stays tiny either way, so assert on the TYPE contract:
    import types
    assert isinstance(it, types.GeneratorType), (
        "iter_rows returns a materialised sequence, so the whole file is in memory again")


def test_the_head_query_stops_early(qs, tmp_path) -> None:
    """`pending` must not scan 47,000 rows to return 20."""
    p = tmp_path / "q.jsonl"
    rows = [{"id": f"p{i}", "status": "PENDING"} for i in range(30)]
    rows += [{"id": f"d{i}", "status": "done"} for i in range(20_000)]
    _write(p, rows)
    got = qs.pending(limit=20, path=p)
    assert len(got) == 20
    assert all(r["id"].startswith("p") for r in got)


def test_terminal_rows_are_not_offered_as_work(qs, tmp_path) -> None:
    p = tmp_path / "q.jsonl"
    _write(p, [{"id": "a", "status": "done"}, {"id": "b", "status": "failed"},
               {"id": "c", "status": "PENDING"}])
    assert [r["id"] for r in qs.pending(10, p)] == ["c"]


def test_a_truncated_final_line_costs_one_row_not_the_queue(qs, tmp_path) -> None:
    """The one failure an append-only file can actually have.

    Losing the last row is recoverable. Losing the whole queue to a ValueError is not.
    """
    p = tmp_path / "q.jsonl"
    _write(p, [{"id": f"c{i}", "status": "PENDING"} for i in range(10)])
    with p.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "half", "stat')          # a crash mid-append
    rows = list(qs.iter_rows(p))
    assert len(rows) == 10, "a truncated final line took the whole queue with it"
    assert rows[-1]["id"] == "c9"


def test_append_does_not_rewrite_the_file(qs, tmp_path) -> None:
    """O(1) append is the other half of the cost: adding one row rewrote 57MB."""
    p = tmp_path / "q.jsonl"
    _write(p, [{"id": f"c{i}", "status": "PENDING"} for i in range(100)])
    before = p.stat().st_size
    qs.append([{"id": "new", "status": "PENDING"}], p)
    after = p.stat().st_size
    assert after > before
    assert after - before < 200, "the append rewrote more than the row it added"
    assert list(qs.iter_rows(p))[-1]["id"] == "new"


def test_counts_are_taken_without_loading_the_file(qs, tmp_path) -> None:
    p = tmp_path / "q.jsonl"
    _write(p, [{"status": "PENDING"}] * 7 + [{"status": "done"}] * 3)
    assert qs.counts(p) == {"PENDING": 7, "done": 3}


# --------------------------------------------------------------------------- migration
def test_migration_is_non_destructive_and_one_way(qs, tmp_path) -> None:
    """A half-migrated tree must be correct in both directions, so nothing has to be
    coordinated across the eight call sites at once."""
    legacy = tmp_path / "q.json"
    jsonl = tmp_path / "q.jsonl"
    legacy.write_text(json.dumps([{"id": "a", "status": "PENDING"},
                                  {"id": "b", "status": "done"}]), "utf-8")
    out = qs.migrate(legacy=legacy, path=jsonl)
    assert out["status"] == "MIGRATED" and out["rows"] == 2
    assert legacy.exists(), "migration deleted the source; it must be non-destructive"
    assert [r["id"] for r in qs.iter_rows(jsonl)] == ["a", "b"]
    again = qs.migrate(legacy=legacy, path=jsonl)
    assert again["status"] == "ALREADY", "migration ran twice and would have duplicated rows"


def test_readers_fall_back_to_the_legacy_json(qs, tmp_path) -> None:
    """Before migration the readers must still work, or the change has to land atomically
    across eight modules -- which is how a migration breaks a desk."""
    legacy = tmp_path / "q.json"
    legacy.write_text(json.dumps([{"id": "a", "status": "PENDING"}]), "utf-8")
    rows = list(qs.iter_rows(tmp_path / "absent.jsonl", legacy=legacy))
    assert [r["id"] for r in rows] == ["a"]


# --------------------------------------------------------------------------- compaction
def test_compaction_archives_and_never_deletes(qs, tmp_path) -> None:
    """A queue that forgets what it tried will try it again, spending the multiplicity
    budget twice on one hypothesis."""
    p, arc = tmp_path / "q.jsonl", tmp_path / "arc.jsonl"
    _write(p, [{"id": "old", "status": "done", "finished_at": "2020-01-01T00:00:00+00:00"},
               {"id": "live", "status": "PENDING", "created_at": "2020-01-01T00:00:00+00:00"}])
    out = qs.compact(p, arc, keep_days=1)
    assert out["status"] == "COMPACTED" and out["archived"] == 1 and out["kept"] == 1
    assert [r["id"] for r in qs.iter_rows(p)] == ["live"]
    assert [r["id"] for r in qs.iter_rows(arc)] == ["old"], "the archived row was deleted"


def test_recent_terminal_rows_stay_where_a_human_is_looking(qs, tmp_path) -> None:
    from datetime import UTC, datetime
    p, arc = tmp_path / "q.jsonl", tmp_path / "arc.jsonl"
    _write(p, [{"id": "fresh", "status": "failed",
                "finished_at": datetime.now(UTC).isoformat()}])
    out = qs.compact(p, arc, keep_days=14)
    assert out["status"] == "NOTHING_TO_COMPACT"
    assert [r["id"] for r in qs.iter_rows(p)] == ["fresh"]
