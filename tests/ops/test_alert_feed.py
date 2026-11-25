"""Box pages reach Claude: ops/alert_feed.py reads the ntfy topic back into a published feed."""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("alert_feed", _ROOT / "ops" / "alert_feed.py")
assert _spec and _spec.loader
af = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(af)

NOW = datetime(2026, 11, 25, 2, 0, tzinfo=UTC)


def _msgs(*ids: str, titled: bool = True) -> list[dict]:
    return [{"id": i, "event": "message", "time": 1795000000 + n, "message": "x" * 900,
             **({"title": f"page {i}"} if titled else {})} for n, i in enumerate(ids)]


def _paths(tmp: Path) -> dict[str, Path]:
    return {"feed": tmp / "feed.jsonl", "status": tmp / "status.json", "cursor": tmp / "cur.json",
            "bodies": tmp / "bodies.jsonl"}


def test_new_pages_land_once_with_cut_bodies_and_a_cursor(tmp_path):
    p = _paths(tmp_path)
    seen_since: list[str] = []

    def fetch(topic, since):
        seen_since.append(since)
        return _msgs("a", "b")

    st = af.poll(fetch=fetch, topic="t", now=NOW, **p)
    assert st["ok"] and st["new"] == 2 and st["pages"] == 2
    rows = [json.loads(x) for x in p["feed"].read_text().splitlines()]
    assert [r["id"] for r in rows] == ["a", "b"] and "message" not in rows[0]
    body = [json.loads(x) for x in p["bodies"].read_text().splitlines()]
    assert [b["id"] for b in body] == ["a", "b"] and len(body[0]["message"]) == af.BODY_MAX
    assert seen_since == [af.FIRST_SINCE]
    st2 = af.poll(fetch=fetch, topic="t", now=NOW, **p)     # same messages again: no duplicates
    assert st2["new"] == 0 and len(p["feed"].read_text().splitlines()) == 2
    assert seen_since[-1] == "b"


def test_unarmed_and_failed_polls_are_recorded_states(tmp_path):
    p = _paths(tmp_path)
    st = af.poll(fetch=lambda *a: [], topic="", now=NOW, **p)
    assert not st["ok"] and "NOT ARMED" in st["why"]

    def boom(*a):
        raise OSError("down")

    st = af.poll(fetch=boom, topic="t", now=NOW, **p)
    assert not st["ok"] and st["why"].startswith("poll failed")
    assert json.loads(p["status"].read_text())["ok"] is False


def test_the_topic_is_never_written_anywhere(tmp_path):
    p = _paths(tmp_path)
    af.poll(fetch=lambda *a: _msgs("a"), topic="quant-SECRET-topic", now=NOW, **p)
    for f in p.values():
        assert "SECRET" not in f.read_text()


def test_replies_are_marked_as_replies(tmp_path):
    p = _paths(tmp_path)
    af.poll(fetch=lambda *a: _msgs("r", titled=False), topic="t", now=NOW, **p)
    assert json.loads(p["feed"].read_text())["kind"] == "reply"


def test_routing_counts_only_alerts_a_publish_carried(tmp_path):
    feed, events, flow, out = (tmp_path / "f.jsonl", tmp_path / "e.jsonl", tmp_path / "flow.json",
                               tmp_path / "ALERT_ROUTING.json")
    feed.write_text("\n".join(json.dumps(r) for r in [
        {"id": "a", "at": "2026-11-25T00:00:00+00:00", "title": "old page", "kind": "page"},
        {"id": "b", "at": "2026-11-25T01:30:00+00:00", "title": "new page", "kind": "page"},
        {"id": "c", "at": "2026-11-25T01:31:00+00:00", "kind": "reply"},
        {"id": "z", "at": "2026-11-23T00:00:00+00:00", "title": "outside 24h", "kind": "page"},
    ]) + "\n")
    events.write_text(json.dumps({"at": "2026-11-25T01:40:00+00:00", "kind": "PLUMBING_DEFECT",
                                  "organ": "board MT5-LawGate"}) + "\n"
                      + json.dumps({"at": "2026-11-25T01:41:00+00:00", "kind": "OTHER"}) + "\n")
    flow.write_text(json.dumps({"last_published_at": "2026-11-25T01:00:00+00:00"}))
    doc = af.routing(now=NOW, feed=feed, events=events, flow=flow, out=out)
    assert doc["alerts_24h"] == 3 and doc["routed_24h"] == 1 and doc["all_routed"] is False
    assert {u["what"] for u in doc["unrouted"]} == {"new page", "board MT5-LawGate"}
    assert json.loads(out.read_text())["all_routed"] is False


def test_routing_with_no_publish_is_never_all_routed(tmp_path):
    feed = tmp_path / "f.jsonl"
    feed.write_text(json.dumps({"id": "a", "at": "2026-11-25T01:00:00+00:00", "title": "p",
                                "kind": "page"}) + "\n")
    doc = af.routing(now=NOW, feed=feed, events=tmp_path / "none", flow=tmp_path / "none",
                     out=tmp_path / "o.json")
    assert doc["all_routed"] is False and doc["last_published_at"] == "UNMEASURED"


def test_the_public_feed_carries_no_figure_host_account_or_reply_body(tmp_path):
    """Audit MF1: the feed is synced to a public origin; bodies stay box-local."""
    p = _paths(tmp_path)
    page = {"id": "x1", "event": "message", "time": 1795000000, "priority": 5,
            "title": "E8 daily loss -846.12 USD, equity 99331.72 on 1.2.3.4 box.example.com",
            "message": "account 12345678 at https://vmi.example/x mail a@b.co",
            "tags": ["warning", "acct-12345678"]}
    reply = {"id": "x2", "event": "message", "time": 1795000001, "message": "my pin is 4321"}
    af.poll(fetch=lambda *a: [page, reply], topic="t", now=NOW, **p)
    wire = p["feed"].read_text()
    for bad in ("846", "99331", "1.2.3.4", "example", "12345678", "4321", "@", "http",
                "message", "equity 9"):
        assert bad not in wire, bad
    rows = [json.loads(x) for x in wire.splitlines()]
    assert rows[0]["title_class"] == "daily loss usd equity on"
    assert rows[0]["tags"] == ["warning"] and rows[0]["priority"] == 5
    local = p["bodies"].read_text()
    assert "846.12" in local and "4321" in local          # the evidence stays on the box
    sync = (Path(af.ROOT) / "desks/mt5/scripts/sync_shadow_to_git.ps1").read_text("utf-8")
    assert "alert_feed_bodies" not in sync and "CLAUDE_ALERT_FEED.jsonl" in sync
