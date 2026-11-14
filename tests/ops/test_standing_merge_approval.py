"""zuck's standing approval (2026-11-10): an Auditor CLEAR alone merges, except the gate itself."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_gate_standing", ROOT / ".github/scripts/audit_gate.py"
)
assert _spec is not None and _spec.loader is not None
ag = importlib.util.module_from_spec(_spec)
sys.modules["audit_gate_standing"] = ag
_spec.loader.exec_module(ag)

BEFORE = "2026-11-03T23:17:29Z"  # his last one-shot approval
AFTER = "2026-11-10T17:00:00Z"
LATER = "2026-11-11T09:00:00Z"


def _c(body: str, at: str, **kw: Any) -> dict[str, Any]:
    return {"body": body, "created_at": at, "updated_at": at, "author_association": "OWNER", **kw}


ON = [_c(ag.ACTIVATE, "2026-10-29T13:52:14Z")]


def test_a_later_clear_is_covered_by_a_standing_approval() -> None:
    ok, why = ag.approved({"at": LATER}, AFTER, ag.standing("AUTO", ON))
    assert ok and "standing" in why


def test_an_approval_typed_before_the_order_is_never_standing() -> None:
    assert not ag.approved({"at": LATER}, BEFORE, ag.standing("AUTO", ON))[0]
    assert ag.approved({"at": "2026-11-03T00:00:00Z"}, BEFORE, True)[0]  # one-shot still works


def test_the_gate_itself_is_never_covered_by_the_standing_approval() -> None:
    assert not ag.standing("PROTECTED", ON)
    assert not ag.standing("REFUSED", ON)
    assert not ag.approved({"at": LATER}, AFTER, ag.standing("PROTECTED", ON))[0]
    # his own comment newer than the CLEAR still merges a PROTECTED PR
    assert ag.approved({"at": AFTER}, LATER, ag.standing("PROTECTED", ON))[0]


def test_a_deactivate_ends_the_standing_approval() -> None:
    off = [*ON, _c(ag.DEACTIVATE, AFTER, author_association="COLLABORATOR")]
    assert not ag.standing("AUTO", off)
    assert not ag.standing("AUTO", [])  # never activated is off
    assert not ag.approved({"at": LATER}, AFTER, ag.standing("AUTO", off))[0]


def test_no_approval_at_all_covers_nothing() -> None:
    assert not ag.approved({"at": LATER}, None, True)[0]


def test_an_app_posted_or_edited_approval_is_not_his() -> None:
    app = [_c(ag.APPROVE, AFTER, performed_via_github_app={"id": 1})]
    edited = [{**_c(ag.APPROVE, AFTER), "updated_at": LATER}]
    assert ag.approval_at(app) is None and ag.approval_at(edited) is None
