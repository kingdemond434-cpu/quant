"""The terms-record gap (LAWS 5e act 6): fetches to hosts with no reviewed-terms record are
counted per pass, an absent input is UNMEASURED (never zero), an unreadable registry makes the
split UNMEASURED, and the backfill queue is ranked by volume. Synthetic fixtures; no network."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import terms_record_gap as gap  # noqa: E402

NOW = datetime(2026, 11, 17, 23, 59, tzinfo=UTC)


def _rec(host: str, verdict: str) -> dict[str, Any]:
    ev = {"verdict": verdict, "terms_url": None, "date_read": None, "quote": "q",
          "quote_kind": "recorded_reading", "source_label": "x",
          "source": {"file": "fixture.py", "object": "EV"}}
    return {"host": host, "verdict": verdict, "terms_url": None, "date_read": None,
            "quote": "q", "recorded_by": "fixture", "evidence": [ev]}


def _registry(tmp: Path) -> Path:
    p = tmp / "terms_records.json"
    p.write_text(json.dumps({"records": {"ok.org": _rec("ok.org", "permits"),
                                         "bad.org": _rec("bad.org", "forbids")}}),
                 encoding="utf-8")
    return p


def _desk(tmp: Path, *, frontier: bool = True, news: bool = True) -> Path:
    desk = tmp / "desk"
    (desk / "data" / "intelligence" / "world").mkdir(parents=True)
    if frontier:
        (desk / "data" / "intelligence" / "world" / "frontier.json").write_text(json.dumps(
            {"sources": {
                "https://www.ok.org/a": {"host": "www.ok.org", "fetches": 5},
                "https://api.ok.org/b": {"host": "api.ok.org", "fetches": 2},
                "https://cdn.bad.org/c": {"host": "cdn.bad.org", "fetches": 3},
                "https://unread.net/d": {"host": "unread.net", "fetches": 7},
                "https://tie-b.net/": {"host": "tie-b.net", "fetches": 4},
                "https://tie-a.net/": {"host": "tie-a.net", "fetches": 4}}}), encoding="utf-8")
    if news:
        rows = [{"url": "https://unread.net/n1"}, {"url": "https://unread.net/n1"},
                {"url": "https://tie-b.net/x"}, {"url": "https://other.io/p"}]
        (desk / "data" / "news_captures.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return desk


def test_gap_counts_unrecorded_fetches_and_refusing_records(tmp_path: Path) -> None:
    report, _ = gap.build(_desk(tmp_path), _registry(tmp_path), now=NOW)
    t = report["totals"]
    # frontier 25 fetches + news 3 distinct URLs (the duplicate counted once)
    assert t["observations"] == 28
    assert t["to_permits"] == 7 and t["to_forbids"] == 3
    assert t["to_unrecorded_hosts"] == 18          # unread 8, tie-b 5, tie-a 4, other.io 1
    assert report["status"] == "DEFECT"
    assert "DEFECT AGAINST LAWS 5e act 6" in report["defect"] and "18 of 28" in report["defect"]
    assert "NOT a permission" in report["not_a_permission"]
    assert report["missed_growth"] is None         # nothing is held by a measurement
    assert [r["host"] for r in report["fetched_despite_refusing_record"]] == ["cdn.bad.org"]


def test_backfill_queue_is_ranked_by_volume_then_breadth_then_name(tmp_path: Path) -> None:
    _, queue = gap.build(_desk(tmp_path), _registry(tmp_path), now=NOW)
    order = [(r["rank"], r["host"], r["observations"]) for r in queue["queue"]]
    assert order == [(1, "unread.net", 8), (2, "tie-b.net", 5), (3, "tie-a.net", 4),
                     (4, "other.io", 1)]
    by = {r["host"]: r for r in queue["queue"]}
    assert by["unread.net"]["by_input"] == {"news_captures": 1, "world_frontier": 7}
    # recorded hosts (and their subdomains) never enter the queue
    assert not {"ok.org", "api.ok.org", "cdn.bad.org"} & set(by)


def test_rank_ties_break_on_inputs_then_host() -> None:
    rows = gap.rank_queue({"b.io": {"x": 2}, "a.io": {"x": 2}, "c.io": {"x": 1, "y": 1}},
                          lambda h: None)
    assert [r["host"] for r in rows] == ["c.io", "a.io", "b.io"]


def test_absent_input_is_unmeasured_never_zero(tmp_path: Path) -> None:
    report, _ = gap.build(_desk(tmp_path, news=False), _registry(tmp_path), now=NOW)
    rows = {i["name"]: i for i in report["inputs"]}
    assert rows["news_captures"]["status"] == gap.UNMEASURED
    assert rows["news_captures"]["why"] == "absent"
    assert "observations" not in rows["news_captures"]
    assert report["totals"]["inputs_measured"] == 1


def test_no_input_at_all_is_unmeasured(tmp_path: Path) -> None:
    report, queue = gap.build(_desk(tmp_path, frontier=False, news=False),
                              _registry(tmp_path), now=NOW)
    assert report["status"] == gap.UNMEASURED
    assert report["totals"]["to_unrecorded_hosts"] == gap.UNMEASURED
    assert report["totals"]["observations"] == gap.UNMEASURED
    assert queue["status"] == gap.UNMEASURED and queue["queue"] == []


def test_unreadable_registry_makes_the_split_unmeasured(tmp_path: Path) -> None:
    bad = tmp_path / "broken.json"
    bad.write_text("{", encoding="utf-8")
    report, queue = gap.build(_desk(tmp_path), bad, now=NOW)
    assert report["registry"]["status"] == gap.UNMEASURED
    assert report["totals"]["to_unrecorded_hosts"] == gap.UNMEASURED
    assert report["totals"]["observations"] == 28   # the volume itself was still measured
    assert queue["queue"] == []


def test_since_last_pass_needs_a_comparable_previous_report(tmp_path: Path) -> None:
    desk, reg = _desk(tmp_path), _registry(tmp_path)
    first, _ = gap.build(desk, reg, now=NOW)
    assert first["since_last_pass"] == gap.UNMEASURED
    second, _ = gap.build(desk, reg, previous=first, now=NOW)
    assert second["since_last_pass"]["observations"] == 0
    assert second["since_last_pass"]["to_unrecorded_hosts"] == 0


def test_main_writes_both_reports(tmp_path: Path, monkeypatch) -> None:
    desk, reg = _desk(tmp_path), _registry(tmp_path)
    real = gap.build
    monkeypatch.setattr(gap, "build", lambda previous=None: real(desk, reg, previous, NOW))
    monkeypatch.setattr(gap, "registry_freshness", lambda: {"status": "CURRENT"})
    out, q = tmp_path / "gap.json", tmp_path / "queue.json"
    assert gap.main(["--once", "--out", str(out), "--queue-out", str(q)]) == 0
    assert json.loads(out.read_text("utf-8"))["registry"]["freshness"]["status"] == "CURRENT"
    assert json.loads(q.read_text("utf-8"))["queue"][0]["host"] == "unread.net"
