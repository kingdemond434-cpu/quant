"""Each owner thread gets one brief from the audit pass: its open rows by id, its open
principal-message requirements with their text, its PRs matched by session, a flag on an IN PR
verdict whose PR closed, and its own resume note copied in and never overwritten."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import thread_briefs as tb  # noqa: E402

NOW = datetime(2026, 10, 7, 4, tzinfo=UTC)
T = "World sensor and macro surprise"


def _audit() -> dict:
    rows = [
        {"id": "ROMAN-0001", "owner_thread": T, "state": "ABSENT", "blocker": "no vol feed",
         "next_repair": "build the vol feed", "requirement": "r1"},
        {"id": "ROMAN-0002", "owner_thread": T, "state": "RUNNING", "requirement": "r2"},
        {"id": "ROMAN-0003", "owner_thread": T, "state": "CODED", "blocker": "no vol feed"},
        {"id": "ASIA-0001", "owner_thread": "Breadth and tier assessment", "state": "CODED"},
    ]
    return {"generated_utc": "2026-10-07T03:00:00+00:00", "rows": rows}


def _pm() -> list[dict]:
    d = {"checked_at": "2026-10-07T03:00:00Z"}
    return [
        {"id": "DATA-44", "owner_thread": T, "requirement": "expectation gap",
         "delivery": {**d, "verdict": "NOT STARTED", "evidence": "", "note": "no gap yet"}},
        {"id": "DATA-41", "owner_thread": T, "requirement": "report",
         "delivery": {**d, "verdict": "IN PR", "evidence": "#204 x.py:1", "note": ""}},
        {"id": "DATA-40", "owner_thread": T, "requirement": "done thing",
         "delivery": {**d, "verdict": "BUILT", "evidence": "a.py:1", "note": ""}},
    ]


THREADS = {T: {"title": T, "session": "cse_01AAAAAAAAAAAAAAAAAAAAAAAA", "thread_id": "cmsg_x"}}
PRS = [{"n": 211, "sha": "abc", "draft": True, "title": "sensor", "updated": "2026-10-07",
        "session": "01AAAAAAAAAAAAAAAAAAAAAAAA"},
       {"n": 300, "sha": "def", "draft": False, "title": "other", "updated": "2026-10-07",
        "session": "01BBBBBBBBBBBBBBBBBBBBBBBB"}]


def _write(tmp: Path, prs: list | None = PRS) -> tuple[dict, str]:
    idx = tb.write(_audit(), tmp, now=NOW, prs=prs, pm=_pm(), threads=THREADS)
    return idx, (tmp / f"{tb.slug(T)}.md").read_text("utf-8")


def test_brief_lists_open_rows_and_open_requirements_only(tmp_path: Path) -> None:
    idx, text = _write(tmp_path)
    assert "ABSENT (1): ROMAN-0001" in text and "CODED (1): ROMAN-0003" in text
    assert "ROMAN-0002" not in text
    assert "**DATA-44** NOT STARTED" in text and "expectation gap" in text
    assert "DATA-40" not in text
    row = next(t for t in idx["threads"] if t["title"] == T)
    assert row["open_rows"] == 2 and row["pm_open"] == 2


def test_next_step_is_the_first_not_started_requirement(tmp_path: Path) -> None:
    _, text = _write(tmp_path)
    assert "## Next step\n\nDATA-44: no gap yet" in text


def test_prs_matched_by_session_and_closed_pr_flagged(tmp_path: Path) -> None:
    _, text = _write(tmp_path)
    assert "#211 draft head abc" in text and "#300" not in text
    assert "RE-CHECK: DATA-41 cites #204" in text


def test_unreachable_github_is_unmeasured_not_empty(tmp_path: Path) -> None:
    idx, text = _write(tmp_path, prs=None)
    assert "UNMEASURED: GitHub was not reachable" in text and "RE-CHECK" not in text
    assert idx["prs_measured"] is False


def test_resume_note_is_copied_and_never_written(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / f"{tb.slug(T)}.md").write_text("Stopped at the vol feed, branch x.\n")
    _, text = _write(tmp_path)
    assert "Stopped at the vol feed, branch x." in text
    assert (notes / f"{tb.slug(T)}.md").read_text() == "Stopped at the vol feed, branch x.\n"
    _, again = _write(tmp_path)
    assert "Stopped at the vol feed" in again


def test_blockers_counted_once_per_row(tmp_path: Path) -> None:
    _, text = _write(tmp_path)
    assert "- (2) no vol feed" in text


def test_committed_inputs_load_and_cover_every_owner() -> None:
    pm = tb.load_pm()
    threads = tb.load_threads()
    assert len(pm) == 156
    assert all(p["delivery"]["verdict"] in ("BUILT", "IN PR", "NOT STARTED") for p in pm)
    owners = {p["owner_thread"] for p in pm}
    assert "UNOWNED" not in owners and owners <= set(threads)


def test_audit_pass_writes_the_briefs(tmp_path: Path, monkeypatch) -> None:
    from research import mandate_audit as ma
    monkeypatch.setattr(ma, "OUT", tmp_path / "MANDATE_AUDIT.json")
    monkeypatch.setattr(tb, "OUT_DIR", tmp_path / "briefs")
    monkeypatch.setattr(tb, "fetch_prs", lambda timeout=60.0: None)
    monkeypatch.setattr(tb.write, "__defaults__",
                        (tmp_path / "briefs", None, None, False, None, None))
    assert ma.main([]) == 0
    idx = json.loads((tmp_path / "briefs" / "INDEX.json").read_text())
    assert idx["threads"] and idx["prs_measured"] is False
