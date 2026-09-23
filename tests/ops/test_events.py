"""The event log: a fixed vocabulary, an append-only file, two readers, and every leg emits."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.ops import events as ev  # noqa: E402


def test_emit_appends_one_line_and_flags_a_kind_outside_the_vocabulary(tmp_path: Path) -> None:
    p = tmp_path / "events.jsonl"
    assert ev.emit("DATA_UPDATED", path=p, leg="refresh_bars")["kind"] == "DATA_UPDATED"
    row = ev.emit("SOMETHING_NEW", path=p)
    assert row["unknown_kind"] is True
    lines = p.read_text("utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["leg"] == "refresh_bars"


def test_leg_events_emit_done_or_failed_plus_the_domain_transition(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    assert ev.leg_events("external_gauntlet", "ok", path=p) == ["LEG_DONE", "GAUNTLET_SWEPT"]
    assert ev.leg_events("external_gauntlet", "RuntimeError: x", path=p) == ["LEG_FAILED"], \
        "a failed sweep is not a sweep"
    assert ev.leg_events("health", "ok", path=p) == ["LEG_DONE"]
    assert ev.latest("GAUNTLET_SWEPT", path=p)["outcome"] == "ok"
    assert ev.latest("ALLOCATION_DECIDED", path=p) is None


def test_since_reads_after_a_stamp_and_filters_by_kind(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    rows = [{"at": "2026-09-09T00:00:00+00:00", "kind": "LEG_DONE", "leg": "a"},
            {"at": "2026-09-09T01:00:00+00:00", "kind": "DATA_UPDATED", "leg": "refresh_bars"},
            {"at": "2026-09-09T02:00:00+00:00", "kind": "LEG_DONE", "leg": "b"}]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n", "utf-8")
    seen = [r["leg"] for r in ev.since("2026-09-09T00:30:00+00:00", path=p)]
    assert seen == ["refresh_bars", "b"]
    assert [r["leg"] for r in ev.since(None, kinds=("LEG_DONE",), path=p)] == ["a", "b"]
    c = ev.census(path=p)
    assert c["counts"] == {"LEG_DONE": 2, "DATA_UPDATED": 1}
    assert "GAUNTLET_SWEPT" in c["silent_kinds"]
    assert c["newest"]["LEG_DONE"] == "2026-09-09T02:00:00+00:00"


def test_the_tail_read_is_bounded(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "e.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for i in range(2000):
            fh.write(json.dumps({"at": f"2026-09-09T00:00:{i % 60:02d}+00:00", "kind": "LEG_DONE",
                                 "leg": f"leg{i}"}) + "\n")
    monkeypatch.setattr(ev, "TAIL_BYTES", 4096)
    rows = ev.since(None, path=p)
    assert 0 < len(rows) < 2000 and rows[-1]["leg"] == "leg1999"


def test_every_leg_with_a_domain_event_is_a_declared_kind_and_a_real_leg() -> None:
    from libs.research.layers import LEG_LAYER
    for leg, kind in ev.LEG_EVENT.items():
        assert kind in ev.KINDS, kind
        assert leg in LEG_LAYER, f"{leg} emits an event but is not a registered leg"


def test_the_hourly_cycle_emits_through_costed() -> None:
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    body = src.split("def _costed(", 1)[1].split("SEARCH_BUDGET_SEC", 1)[0]
    assert body.count("_emit_leg(name,") == 2, "both the failed and the ok path emit"
    assert "from libs.ops.events import leg_events" in body
