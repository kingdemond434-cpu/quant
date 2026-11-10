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


# ------------------- #816: the standing path also needs the synced Auditor registry, when set

HEAD = "a" * 40


def _synced(tmp: Path, rows: list[dict[str, Any]], age_h: float = 0.5) -> str:
    import json
    import os
    import time

    f = tmp / "auditor_rows.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    t = time.time() - age_h * 3600
    os.utime(f, (t, t))
    return str(f)


def _clear(**kw: Any) -> dict[str, Any]:
    return {"pr": 811, "sha": HEAD, "verdict": "CLEAR", "at": "2026-11-11T08:00:00+00:00", **kw}


def _standing(monkeypatch: Any) -> tuple[bool, str]:
    return ag.approved(
        {"at": LATER}, AFTER, ag.standing("AUTO", ON), lambda: ag.standing_second(811, HEAD)
    )


def test_with_no_synced_registry_the_standing_rule_is_exactly_as_merged(monkeypatch: Any) -> None:
    monkeypatch.delenv(ag.AUDITOR_ROWS_ENV, raising=False)
    ok, why = _standing(monkeypatch)
    assert ok and "standing" in why
    # the second record is asked only on the standing path: his own newer comment never needs it
    asked: list[int] = []
    assert ag.approved({"at": AFTER}, LATER, True, lambda: asked.append(1) or (False, "x"))[0]
    assert asked == []


def test_an_absent_or_stale_synced_registry_makes_the_standing_path_wait_alerted_once(
    monkeypatch: Any, tmp_path: Path
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(ag, "run_notify", lambda t, b: sent.append(b) or True)
    monkeypatch.setenv(ag.AUDITOR_ROWS_ENV, str(tmp_path / "missing.jsonl"))
    for _ in range(2):
        ok, why = _standing(monkeypatch)
        assert not ok and "second record" in why and "unreadable" in why
    stale = _synced(tmp_path, [_clear()], age_h=ag.AUDITOR_ROWS_MAX_AGE_H + 0.5)
    monkeypatch.setenv(ag.AUDITOR_ROWS_ENV, stale)
    for _ in range(2):
        ok, why = _standing(monkeypatch)
        assert not ok and "stale" in why
    # once per (PR, head, kind of wait): one for the missing copy, one for the stale one
    assert len(sent) == 2 and "unreadable" in sent[0] and "stale" in sent[1]


def test_a_disagreeing_synced_registry_makes_the_standing_path_wait_and_an_agreeing_one_merges(
    monkeypatch: Any, tmp_path: Path
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(ag, "run_notify", lambda t, b: sent.append(b) or False)  # undelivered
    for rows in ([_clear(sha="b" * 40)], [_clear(), _clear(verdict="HOLD")], [_clear(pr=1)]):
        monkeypatch.setenv(ag.AUDITOR_ROWS_ENV, _synced(tmp_path, rows))
        ok, why = _standing(monkeypatch)
        assert not ok and "second record" in why
    assert len(sent) == 3  # undelivered notices are never recorded, so they are tried again
    monkeypatch.setenv(ag.AUDITOR_ROWS_ENV, _synced(tmp_path, [_clear()]))
    ok, why = _standing(monkeypatch)
    assert ok and "agrees" in why
