"""The silent-veto ROOT path (zuck 2026-11-18 17:22Z): a ROOT or never-standing PR merges without
his line only when it provably changes comments, docstrings or grow-only insertions, never a
locked file, and only after the 72 h window with no veto. Every test here is a refusal or the one
narrow admission."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_gate_silent_root", ROOT / ".github/scripts/audit_gate.py"
)
assert _spec is not None and _spec.loader is not None
ag = importlib.util.module_from_spec(_spec)
sys.modules["audit_gate_silent_root"] = ag
_spec.loader.exec_module(ag)

PUB = "ops/release/publisher/publish.py"
GROW = "ops/release/risk_suites.txt"

CODE = '''"""Module doc."""
# a comment
def f(x):
    """Doc."""
    return x + 1
'''
CODE_DOCS = '''"""Module doc, reworded."""
# another comment, longer
def f(x):
    """Doc, reworded at length."""

    return x + 1
'''
CODE_CHANGED = CODE.replace("x + 1", "x + 2")


def _files(*names: str, status: str = "modified") -> list[dict[str, Any]]:
    return [{"filename": n, "status": status} for n in names]


def _show(table: dict[tuple[str, str], str]) -> Any:
    def show(rev: str, name: str) -> str:
        return table[(rev, name)]

    return show


def _judge(files: list[dict[str, Any]], table: dict[tuple[str, str], str]) -> tuple[bool, str]:
    ok, why = ag.tightening_only(files, _show(table), "LIVE", "HEAD")
    return bool(ok), str(why)


def test_comment_and_docstring_only_python_is_admitted() -> None:
    ok, why = _judge(_files(PUB), {("origin/LIVE", PUB): CODE, ("HEAD", PUB): CODE_DOCS})
    assert ok, why


def test_a_code_change_is_refused() -> None:
    ok, why = _judge(_files(PUB), {("origin/LIVE", PUB): CODE, ("HEAD", PUB): CODE_CHANGED})
    assert not ok and "changes code" in why


def test_removing_a_function_body_docstring_into_pass_is_still_the_same_code() -> None:
    a = 'def f():\n    """only a doc"""\n'
    b = "def f():\n    pass\n"
    assert ag.code_identity(a) == ag.code_identity(b)


def test_an_unparsable_side_is_refused() -> None:
    ok, _ = _judge(_files(PUB), {("origin/LIVE", PUB): CODE, ("HEAD", PUB): "def ("})
    assert not ok


def test_grow_only_insertion_is_admitted() -> None:
    table = {("origin/LIVE", GROW): "a\nb\n", ("HEAD", GROW): "a\nx\nb\ny\n"}
    ok, why = _judge(_files(GROW), table)
    assert ok, why


def test_grow_only_removal_reorder_or_noop_is_refused() -> None:
    for new in ("a\n", "b\na\nc\n", "a\nb\n", "a\nB\nc\n"):
        ok, _ = _judge(_files(GROW), {("origin/LIVE", GROW): "a\nb\n", ("HEAD", GROW): new})
        assert not ok, new


def test_every_locked_file_is_refused_even_for_a_comment() -> None:
    for name in (
        ".github/scripts/audit_gate.py",
        ".github/scripts/memecoin_gate.py",
        ".github/workflows/ci.yml",
        "ops/box/workflow_gate.ps1",
        "ops/release/authority/ROOT_POLICY.json",
        "ops/release/authority/policy.py",
        "ops/signing/keys.json",
        "ops/release_authority.py",
    ):
        table = {("origin/LIVE", name): CODE, ("HEAD", name): CODE_DOCS}
        ok, why = _judge(_files(name), table)
        assert not ok and "locked" in why, (name, why)


def test_other_never_standing_files_are_refused() -> None:
    # adding a row here LOOSENS replay-shadow, so it is never a grow-only admission
    for name in ("ops/release/expected_divergence.json", "ops/release/not_money_scripts.txt"):
        table = {("origin/LIVE", name): "a\n", ("HEAD", name): "a\nb\n"}
        ok, _ = _judge(_files(name), table)
        assert not ok, name


def test_added_removed_or_renamed_root_files_are_refused() -> None:
    for status in ("added", "removed", "renamed"):
        table = {("origin/LIVE", PUB): CODE, ("HEAD", PUB): CODE_DOCS}
        assert not _judge(_files(PUB, status=status), table)[0], status
    moved = [{"filename": "elsewhere.py", "previous_filename": PUB, "status": "renamed"}]
    assert not _judge(moved, {})[0]


def test_an_unreadable_side_is_refused() -> None:
    assert not _judge(_files(PUB), {("HEAD", PUB): CODE})[0]


def test_a_pr_with_no_root_file_does_not_take_this_path() -> None:
    ok, why = _judge(_files("libs/x.py"), {})
    assert not ok and "no root" in why


def test_a_mixed_pr_is_refused_when_any_root_file_changes_code() -> None:
    table = {
        ("origin/LIVE", PUB): CODE,
        ("HEAD", PUB): CODE_DOCS,
        ("origin/LIVE", "ops/release/merger/merge.py"): CODE,
        ("HEAD", "ops/release/merger/merge.py"): CODE_CHANGED,
    }
    assert not _judge(_files(PUB, "ops/release/merger/merge.py"), table)[0]


def test_veto_is_any_trusted_veto_after_the_clear() -> None:
    clear_at = "2026-11-18T18:00:00Z"
    c = {"body": " veto ", "author_association": "OWNER", "created_at": "2026-11-18T19:00:00Z"}
    assert ag.vetoed([c], clear_at)
    assert not ag.vetoed([{**c, "created_at": "2026-11-18T17:00:00Z"}], clear_at)
    assert not ag.vetoed([{**c, "author_association": "NONE"}], clear_at)
    assert not ag.vetoed([{**c, "body": "veto this?"}], clear_at)


def test_the_window_is_72_hours_from_the_delivered_notice(tmp_path: Path) -> None:
    rec = tmp_path / "reg.silent_root.json"
    now = datetime(2026, 11, 18, 18, tzinfo=UTC)
    sent: list[tuple[str, str]] = []

    def notify(t: str, b: str) -> bool:
        sent.append((t, b))
        return True

    start, why = ag.registry_window(rec, 9, "a" * 40, now, notify, ag.SILENT_ROOT_HOLD_H, "B")
    assert start is None and "72 h window starts" in why and sent[0][1] == "B"
    start, _ = ag.registry_window(rec, 9, "a" * 40, now + timedelta(hours=71), notify, 72.0, "B")
    assert start == now and len(sent) == 1
    # a new head is a new window
    start, _ = ag.registry_window(rec, 9, "b" * 40, now + timedelta(hours=80), notify, 72.0, "B")
    assert start is None and len(sent) == 2


def test_an_undelivered_notice_starts_no_window(tmp_path: Path) -> None:
    rec = tmp_path / "reg.silent_root.json"
    now = datetime(2026, 11, 18, 18, tzinfo=UTC)
    start, _ = ag.registry_window(rec, 9, "a" * 40, now, lambda t, b: False, 72.0, "B")
    assert start is None and not rec.exists()


def test_the_hold_and_the_locked_list_are_pinned() -> None:
    assert ag.SILENT_ROOT_HOLD_H == 72.0
    for p in (".github/workflows/*", ".github/scripts/audit_gate.py", "ops/signing/*",
              ".github/scripts/memecoin_gate.py", "ops/release/authority/*"):  # fmt: skip
        assert p in ag.SILENT_ROOT_LOCKED
