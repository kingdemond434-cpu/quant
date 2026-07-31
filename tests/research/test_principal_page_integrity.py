"""The principal page must never eat its own messages (2026-07-28 data-loss bug).

`max_audit` strips its escalation block before rewriting PRINCIPAL_ACTION.md. The strip was
`existing.split(MARK)[0]` -- which keeps only the text BEFORE the marker. Once the escalation
owned line 1 (i.e. every run after the first), that expression returned "" and SILENTLY DELETED
the entire human-written page below it. Every page the CRO wrote from 2026-07-24 onward was
destroyed by the next sweep, on the desk's only human-escalation channel, with no error anywhere.

These tests pin both halves of the contract: the human's text survives, and the routine 48h
escalation never outranks a fresh Tier-3 ask the principal alone can clear.
"""
from __future__ import annotations

import importlib
import subprocess

import pytest

ma = importlib.import_module("scripts.max_audit")

_ESC = ("MAX-AUDIT ESCALATION: 3 below-max state(s) >48h unfixed/unacked -- a; b; c\n"
        "  - a: first defect\n"
        "  - b: second defect\n")


def _strip(existing: str) -> str:
    """Mirror of the strip in max_audit.main() -- block-only, never split-on-marker."""
    kept, skipping = [], False
    for ln in existing.splitlines():
        if ln.startswith("MAX-AUDIT ESCALATION"):
            skipping = True
            continue
        if skipping and (ln.startswith("  - ") or not ln.strip()):
            continue
        skipping = False
        kept.append(ln)
    return "\n".join(kept).strip()


def test_the_original_bug_would_have_destroyed_the_page():
    """Characterise the defect so nobody reintroduces the clever one-liner."""
    page = _ESC + "\nURGENT 2026-07-28: dead-man reset needed\n\nbody text\n"
    assert page.split("MAX-AUDIT ESCALATION")[0].strip() == ""   # <- the bug: everything lost
    assert "dead-man reset needed" in _strip(page)               # <- the fix keeps it


def test_human_page_survives_the_strip():
    page = _ESC + "\nURGENT 2026-07-28: reset the dead-man\n\ndetail line\n"
    body = _strip(page)
    assert "URGENT 2026-07-28: reset the dead-man" in body
    assert "detail line" in body
    assert "MAX-AUDIT ESCALATION" not in body
    assert "first defect" not in body            # the escalation's own bullets DO go


def test_escalation_never_stacks_across_runs():
    """Three sweeps must leave exactly one escalation block, not three."""
    page = "URGENT 2026-07-28: keep me\n\nbody\n"
    for _ in range(3):
        page = _ESC + "\n" + _strip(page)
    assert page.count("MAX-AUDIT ESCALATION") == 1
    assert "keep me" in page


def test_non_escalation_bullets_are_preserved():
    """Only bullets belonging to the escalation block are dropped.

    A page whose own prose uses '  - ' bullets must not be silently gutted, so the skip state
    ends at the first line that is neither a bullet nor blank.
    """
    page = _ESC + "\nURGENT 2026-07-28: ask\n\nMy list:\n  - my own bullet\n  - another\n"
    body = _strip(page)
    assert "my own bullet" in body
    assert "another" in body


@pytest.mark.parametrize("marker", ["URGENT 2026-07-28", "URGENT 2026-01-01"])
def test_urgent_ttl_governs_line_one(marker):
    """A FRESH urgent page outranks the routine sweep; a stale one is demoted.

    The date is mandatory for exactly this reason -- an undated urgent marker would rot back into
    the stale-line-1 bug the 2026-07-24 delivery fix removed.
    """
    from datetime import UTC, datetime
    stamp = marker.split("URGENT ", 1)[1]
    age_d = (datetime.now(tz=UTC) - datetime.fromisoformat(stamp).replace(tzinfo=UTC)).days
    assert (age_d <= 7) == (stamp == "2026-07-28")


def test_page_on_disk_is_not_empty_and_leads_with_the_urgent_ask():
    """The live artifact -- a page that exists but is empty is the bug in its quiet form."""
    p = ma.ROOT / "data/PRINCIPAL_ACTION.md"
    if not p.exists():
        pytest.skip("no page pending")
    txt = p.read_text("utf-8")
    assert txt.strip(), "PRINCIPAL_ACTION.md exists but is empty"
    assert txt.count("MAX-AUDIT ESCALATION") <= 1, "escalation stacked across runs"


def test_max_audit_run_preserves_a_written_page(tmp_path):
    """End-to-end: run the real script and confirm a written page is still there afterwards."""
    p = ma.ROOT / "data/PRINCIPAL_ACTION.md"
    if not p.exists():
        pytest.skip("no page pending")
    before = p.read_text("utf-8")
    sentinel = "URGENT" if before.lstrip().startswith("URGENT") else None
    if sentinel is None:
        pytest.skip("no urgent page currently pending")
    subprocess.run([".venv/bin/python", "scripts/max_audit.py"],
                   cwd=ma.ROOT, capture_output=True, timeout=300, check=False)
    after = p.read_text("utf-8")
    assert after.lstrip().startswith("URGENT"), "the sweep demoted or destroyed the urgent page"
    assert len(after) > 500, "page collapsed to roughly nothing after a sweep"


def test_non_urgent_page_inserts_below_leading_urgent_run(tmp_path):
    """Deterministic form of the live catch (2026-07-31): the escalation must never take
    line 1 from a pending Tier-3 ask. State-independent so it guards even when no urgent
    page happens to be live at test time."""
    from libs.ops.principal_page import page as _page
    p = tmp_path / "PRINCIPAL_ACTION.md"
    p.write_text("URGENT: reply A/B/C on the book.\n\nURGENT 2: reply YES/NO on the gate.\n\n"
                 "old details body.\n", "utf-8")
    out = _page("MAX-AUDIT ESCALATION: 15 defects >48h\n  - detail line",
                marker="MAX-AUDIT ESCALATION", path=p)
    assert out.startswith("URGENT: reply A/B/C")
    assert "URGENT 2: reply YES/NO" in out.split("MAX-AUDIT ESCALATION")[0], \
        "escalation split the leading urgent run"
    assert "MAX-AUDIT ESCALATION" in out and "old details body." in out


def test_urgent_page_still_takes_line_one(tmp_path):
    from libs.ops.principal_page import page as _page
    p = tmp_path / "PRINCIPAL_ACTION.md"
    p.write_text("URGENT old ask.\n", "utf-8")
    out = _page("URGENT new ask.", marker="URGENT new", path=p)
    assert out.startswith("URGENT new ask.")
    assert "URGENT old ask." in out
