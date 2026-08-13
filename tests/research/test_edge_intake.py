"""Gate items 30/31/34: no discovery disappears, the batch has a consumer, recall reconciles."""
from __future__ import annotations

import json
from pathlib import Path

from libs.research.edge_intake import (
    DISPOSITIONS,
    LEDGER,
    admit,
    classify,
    defer,
    intake_duty,
    next_batch,
    recall_audit,
    stamp_queue,
)


def _backdate_ledger(root: Path, days: int) -> None:
    """Rewrite every stored row's ts/discovered_at N days earlier -- simulates a genuine prior
    day's sighting without waiting on a real clock, for tests that need a REAL day boundary
    rather than the same-day idempotent replay stamp_queue() now short-circuits."""
    p = root / LEDGER
    lines = [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
    for row in lines:
        for key in ("ts", "discovered_at"):
            if row.get(key):
                day, _, rest = str(row[key]).partition("T")
                y, m, d = (int(v) for v in day.split("-"))
                from datetime import date, timedelta
                back = date(y, m, d) - timedelta(days=days)
                row[key] = f"{back.isoformat()}T{rest}"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n", "utf-8")


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
    """A GENUINE second sighting -- a real day later, not a re-stamp of the same batch. Backdate
    the first row to simulate an actual prior day, or this collapses into the same-day idempotent
    case pinned below."""
    _queue(tmp_path, [_MECH])
    stamp_queue("reports/research_queue.json", root=tmp_path)
    _backdate_ledger(tmp_path, days=1)
    _queue(tmp_path, [_MECH])                            # same ident, second sighting, a day later
    out = stamp_queue("reports/research_queue.json", root=tmp_path)
    assert out["by_disposition"] == {"DUPLICATE_OF_EXISTING_TEST": 1}


def test_item30_same_day_restamp_is_idempotent_not_a_duplicate(tmp_path: Path) -> None:
    """THE 2026-08-13 FIX. scripts/mine_research_queue.py stamps its own output inline; twenty
    minutes later ops/crontab.manifest fires scripts/run_edge_intake.py, which stamped the SAME
    default report file again. Before this fix, classify() saw every ident as already "seen" (by
    itself, minutes earlier) and downgraded every fresh NEXT_BATCH_TEST to
    DUPLICATE_OF_EXISTING_TEST before next_batch() ever ran -- reproduced here without backdating,
    which is exactly the production sequence."""
    _queue(tmp_path, [_MECH])
    first = stamp_queue("reports/research_queue.json", root=tmp_path)
    assert first["by_disposition"] == {"NEXT_BATCH_TEST": 1}
    _queue(tmp_path, [_MECH])                            # identical report, re-run minutes later
    second = stamp_queue("reports/research_queue.json", root=tmp_path)
    assert second["n_stamped"] == 0                       # idempotent no-op, nothing re-classified
    assert next_batch(root=tmp_path)[0]["ident"] == "BV1"  # still there for a real consumer


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


def test_intake_duty_empty_when_batch_is_empty(tmp_path: Path) -> None:
    """STEADY: no text at all when nothing is waiting -- matches libs.ops.repair_mode's own
    convention, and ops/brain_env.sh only injects a non-empty block."""
    assert intake_duty(root=tmp_path) == ""


def test_intake_duty_names_waiting_candidates_and_never_calls_admit(tmp_path: Path) -> None:
    """2026-08-13: next_batch()'s only reader printed to a log file nobody opened, and admit()'s
    only caller anywhere in the repo was this test file. intake_duty() closes the reach gap
    without closing the honesty gap -- it must NOT mark anything admitted itself, or a duty
    block would shrink the backlog by pretending (the principal's own standing instruction)."""
    _queue(tmp_path, [_MECH])
    stamp_queue("reports/research_queue.json", root=tmp_path)
    text = intake_duty(root=tmp_path)
    assert "[Part III-31]" in text
    assert "1 candidate" in text
    assert "BV1" not in text  # the title, not the raw ident, is what's shown
    assert next_batch(root=tmp_path)[0]["admitted_at"] is None  # untouched by the duty text alone


def test_intake_duty_adds_work_and_removes_none() -> None:
    """Same banned-verb discipline libs.ops.repair_mode._BANNED_VERBS asserts -- a duty producer
    must never teach an organ to do less."""
    from libs.ops.repair_mode import _BANNED_VERBS
    src = Path("libs/research/edge_intake.py").read_text("utf-8")
    duty_fn = src.split("def intake_duty", 1)[1].split("\ndef ", 1)[0]
    for verb in _BANNED_VERBS:
        assert verb not in duty_fn.lower()


def test_main_calls_the_lawful_guard() -> None:
    src = Path("libs/research/edge_intake.py").read_text("utf-8")
    assert "from libs.ops.lawful import guard as _law_guard" in src
    assert "_law_guard()" in src


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
