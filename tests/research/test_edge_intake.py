"""Gate items 30/31/34: no discovery disappears, the batch has a consumer, recall reconciles."""
from __future__ import annotations

import json
from pathlib import Path

from libs.research.edge_intake import (
    DISPOSITIONS,
    admit,
    classify,
    defer,
    next_batch,
    recall_audit,
    stamp_queue,
)


def _queue(tmp: Path, rows: list[dict]) -> Path:
    p = tmp / "reports"
    p.mkdir(parents=True, exist_ok=True)
    f = p / "research_queue.json"
    f.write_text(json.dumps({"queue": rows}), "utf-8")
    return f


_MECH = {"video_id": "BV1", "title": "永续合约 资金费率 套利实盘", "score": 9.0,
         "channel": "bilibili:q", "why": ["+5 mechanism"]}
_TOPIC = {"video_id": "BV2", "title": "量化回测入门教程", "score": 5.0,
          "channel": "bilibili:q", "why": ["+3 validation"]}


# ------------------------------------------------------------------ item 30
def test_item30_every_row_leaves_with_a_named_disposition(tmp_path: Path) -> None:
    _queue(tmp_path, [_MECH, _TOPIC])
    out = stamp_queue("reports/research_queue.json", root=tmp_path)
    assert out["status"] == "OK" and out["n_stamped"] == 2
    assert set(out["by_disposition"]) <= set(DISPOSITIONS)
    assert sum(out["by_disposition"].values()) == 2      # nothing dropped


def test_item30_mechanism_row_goes_to_the_batch(tmp_path: Path) -> None:
    disp, why = classify(_MECH, seen={})
    assert disp == "NEXT_BATCH_TEST" and "mechanism" in why


def test_item30_topic_row_is_blocked_with_the_missing_ingredient_named(tmp_path: Path) -> None:
    """NOT a rejection. The desk cannot test a topic; saying WHICH ingredient is missing is the
    difference between a shopping list and a shrug."""
    disp, why = classify(_TOPIC, seen={})
    assert disp == "BLOCKED_PENDING_DATA"
    assert "MISSING INGREDIENT" in why and "Not a rejection" in why


def test_item30_duplicate_links_provenance_and_never_retests(tmp_path: Path) -> None:
    _queue(tmp_path, [_MECH])
    stamp_queue("reports/research_queue.json", root=tmp_path)
    _queue(tmp_path, [_MECH])                            # same ident, second sighting
    out = stamp_queue("reports/research_queue.json", root=tmp_path)
    assert out["by_disposition"] == {"DUPLICATE_OF_EXISTING_TEST": 1}


# ------------------------------------------------------------------ item 31
def test_item31_next_batch_returns_pending_mechanism_rows(tmp_path: Path) -> None:
    _queue(tmp_path, [_MECH, _TOPIC])
    stamp_queue("reports/research_queue.json", root=tmp_path)
    batch = next_batch(limit=8, root=tmp_path)
    assert [r["ident"] for r in batch] == ["BV1"]        # topic row is not in the batch


def test_item31_admitting_removes_a_row_from_the_next_batch(tmp_path: Path) -> None:
    _queue(tmp_path, [_MECH])
    stamp_queue("reports/research_queue.json", root=tmp_path)
    assert admit(["BV1"], root=tmp_path) == 1
    assert next_batch(root=tmp_path) == []               # a real consumer, not a graveyard


def test_item31_repeated_deferral_raises_priority(tmp_path: Path) -> None:
    """NEXT_BATCH_TEST must not become a polite name for never (mandate III-4)."""
    _queue(tmp_path, [_MECH, {**_MECH, "video_id": "BV3", "score": 20.0}])
    stamp_queue("reports/research_queue.json", root=tmp_path)
    # BV3 scores higher, so it leads on score alone...
    assert next_batch(root=tmp_path)[0]["ident"] == "BV3"
    defer(["BV1"], "capacity", root=tmp_path)
    # ...but a deferred row outranks a higher-scoring fresh one.
    assert next_batch(root=tmp_path)[0]["ident"] == "BV1"


# ------------------------------------------------------------------ item 34
def test_item34_recall_reconciles_when_everything_is_stamped(tmp_path: Path) -> None:
    _queue(tmp_path, [_MECH, _TOPIC])
    stamp_queue("reports/research_queue.json", root=tmp_path)
    a = recall_audit(tmp_path, queue_report="reports/research_queue.json")
    assert a["reconciles"] and a["unaccounted"] == 0
    assert a["edges_discovered"] == a["accounted"] == 2


def test_item34_an_unstamped_discovery_is_a_named_defect(tmp_path: Path) -> None:
    """THE POINT OF ITEM 34. A discovery that entered the funnel and left without a disposition is
    the silent dismissal Part III forbids -- it must surface as a DEFECT, not a rounding note."""
    _queue(tmp_path, [_MECH])
    stamp_queue("reports/research_queue.json", root=tmp_path)
    _queue(tmp_path, [_MECH, {**_TOPIC, "video_id": "BV9"}])   # BV9 never stamped
    a = recall_audit(tmp_path, queue_report="reports/research_queue.json")
    assert not a["reconciles"] and a["unaccounted"] == 1
    assert "RESEARCH-RECALL DEFECT" in a["verdict"] and "BV9" in a["unaccounted_idents"]


def test_missing_queue_report_is_blocked_not_a_silent_success(tmp_path: Path) -> None:
    out = stamp_queue("reports/nope.json", root=tmp_path)
    assert out["status"] == "BLOCKED" and out["n_stamped"] == 0
