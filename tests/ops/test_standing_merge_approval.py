"""zuck's standing approval (2026-11-10, widened to PROTECTED 2026-11-14): an Auditor CLEAR alone
merges, except root, risk, replay-shadow and review files, and the gate itself."""

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
    gate = [".github/scripts/audit_gate.py"]
    assert not ag.standing("PROTECTED", ON, gate, YES)
    assert not ag.standing("PROTECTED", ON)  # no file list: never standing
    assert not ag.standing("REFUSED", ON, ["data/secrets/x"])
    assert not ag.standing("UNKNOWN", ON, ["README.md"])
    assert not ag.approved({"at": LATER}, AFTER, ag.standing("PROTECTED", ON, gate))[0]
    # his own comment newer than the CLEAR still merges it
    assert ag.approved({"at": AFTER}, LATER, ag.standing("PROTECTED", ON, gate))[0]


YES, NO = (lambda: True), (lambda: False)


def test_a_protected_pr_off_the_never_standing_list_stands_with_trusted_eval() -> None:
    for names in (
        ["pyproject.toml", "libs/x.py"],
        ["ops/gates.sh"],
        ["desks/mt5/conftest.py"],
        ["scripts/moneypath_precommit_guard.py"],
    ):
        assert ag.standing("PROTECTED", ON, names, YES), names
        assert ag.approved({"at": LATER}, AFTER, ag.standing("PROTECTED", ON, names, YES))[0]


def test_a_protected_pr_without_a_base_run_trusted_eval_never_stands() -> None:
    def boom() -> bool:
        raise RuntimeError("trusted-eval runs unreadable")

    for te in (None, NO, boom):
        assert not ag.standing("PROTECTED", ON, ["desks/mt5/conftest.py"], te)
    assert ag.standing("AUTO", ON, ["libs/x.py"])  # the lower tiers do not read it


def test_root_risk_replay_and_review_files_are_never_standing() -> None:
    for name in (
        "ops/release/authority/ROOT_POLICY.json",
        "ops/release/authority/pin_root.py",
        "ops/release/publisher/x.py",
        "ops/release/merger/x.py",
        "ops/box/workflow_gate.ps1",
        ".github/workflows/trusted-eval.yml",
        ".github/workflows/release-gates.yml",
        ".github/workflows/audit-gate.yml",
        "ops/release/ceilings.json",
        "ops/release/replay_shadow.py",
        "ops/release/replay_child.py",
        "ops/release/risk_invariants.py",
        "ops/release/independent_review.py",
        "ops/release/review_rubric.md",
        "ops/release/ruleset-live.json",
        "ops/release/protected_paths.txt",
        "ops/release/risk_suites.txt",
        "ops/release/trusted_eval_suites.txt",
        "OPS/RELEASE/CEILINGS.JSON",  # case-blind, as on the box's NTFS checkout
        # #1162 audit HOLD: every workflow, all of ops/release, the approving machinery
        ".github/workflows/ci.yml",
        "ops/release/not_money_scripts.txt",
        "ops/release/adopt_rows.py",
        "ops/release_authority.py",
        "ops/run_release_authority.cmd",
        "ops/signing/allowed_signers",
        "libs/ops/release.py",
    ):
        assert not ag.standing("PROTECTED", ON, [name], YES), name
        assert not ag.standing("PROTECTED", ON, ["ops/gates.sh", name], YES), name


def test_an_unreadable_root_policy_covers_no_protected_pr(tmp_path: Path, monkeypatch: Any) -> None:
    names = ["desks/mt5/conftest.py"]
    for text in (None, "{", '{"root_files": [], "enforced_root_files": [], "grow_only": []}',
                 '{"root_files": ["x"]}', '{"root_files": ["x"], "enforced_root_files": [1],'
                 ' "grow_only": []}'):  # fmt: skip
        f = tmp_path / "ROOT_POLICY.json"
        if text is None:
            f.unlink(missing_ok=True)
        else:
            f.write_text(text, encoding="utf-8")
        monkeypatch.setattr(ag, "ROOT_POLICY_FILE", f)
        assert not ag.standing("PROTECTED", ON, names, YES), text
        assert ag.standing("AUTO", ON, names)  # the lower tiers do not read it


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
