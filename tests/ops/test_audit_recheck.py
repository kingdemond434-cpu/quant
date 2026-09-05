"""Tests for libs/ops/audit_recheck.py -- subject-change freshness (L1.44 one level down).

The parity test is the load-bearing one. VOLATILE is a hardcoded mapping, and a hardcoded scope
list that the run never verifies is the L1.57 defect: it cannot grow when a new commit-volatile
check is written, and it cannot fall when one is deleted, so the single event it exists to reveal
is the one event it structurally cannot show. Deriving the truth by AST from max_audit and
asserting equality is what makes the registry a MEASUREMENT rather than a memory.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from libs.ops import audit_recheck as ar

_MAX_AUDIT = Path(__file__).resolve().parents[2] / "scripts" / "max_audit.py"


def _porcelain_emitters() -> dict[str, list[str]]:
    """Functions in max_audit that read the git WORKING TREE and emit a defect id.

    Reading `git status --porcelain` is what makes a check's verdict flip the moment any session
    commits, which is exactly the property VOLATILE is supposed to enumerate.
    """
    src = _MAX_AUDIT.read_text("utf-8")
    tree = ast.parse(src)
    lines = src.splitlines()
    out: dict[str, list[str]] = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        body = "\n".join(lines[fn.lineno - 1:fn.end_lineno])
        if '"status"' not in body or '"--porcelain"' not in body:
            continue
        ids = []
        for call in ast.walk(fn):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "append" and call.args):
                arg = call.args[0]
                if (isinstance(arg, ast.Tuple) and arg.elts
                        and isinstance(arg.elts[0], ast.Constant)):
                    ids.append(arg.elts[0].value)
        if ids:
            out[fn.name] = sorted(set(ids))
    return out


def test_registry_matches_the_checks_that_read_the_working_tree() -> None:
    """VOLATILE is exactly the ids emitted by working-tree-reading checks -- measured, not recalled.

    If this fails, a commit-volatile check was added or removed and the registry did not follow.
    The repair is upward (L1.49): add the id, never delete the test.
    """
    emitters = _porcelain_emitters()
    derived = {did: fname for fname, ids in emitters.items() for did in ids}
    assert derived == ar.VOLATILE, (
        f"registry drift: max_audit's working-tree checks emit {derived}, "
        f"VOLATILE holds {ar.VOLATILE}")


def test_every_registered_check_exists_and_is_callable() -> None:
    """A registry naming a function that is gone would refuse every re-measure forever, silently
    degrading to the snapshot behaviour this module replaced."""
    import importlib

    audit = importlib.import_module("scripts.max_audit")
    for did, fname in ar.VOLATILE.items():
        fn = getattr(audit, fname, None)
        assert callable(fn), f"{did} -> max_audit.{fname} missing or not callable"


def test_cleared_when_the_live_tree_no_longer_has_the_defect(monkeypatch) -> None:
    """The measured case: the snapshot names a defect, the tree is clean now."""
    monkeypatch.setattr(ar, "_live_volatile_ids", lambda: (set(), ""))
    rc = ar.recheck(["dig-output-uncommitted", "some-other-defect"], ran=None)
    assert rc.cleared == ["dig-output-uncommitted"]
    assert rc.standing == []
    assert rc.unverified == []
    assert rc.ran is True
    # a non-volatile id is not this module's business and must pass through untouched
    assert "some-other-defect" not in rc.cleared + rc.standing + rc.appeared


def test_standing_when_the_defect_is_still_live(monkeypatch) -> None:
    monkeypatch.setattr(ar, "_live_volatile_ids", lambda: ({"dig-output-uncommitted"}, ""))
    rc = ar.recheck(["dig-output-uncommitted"], ran=None)
    assert rc.standing == ["dig-output-uncommitted"]
    assert rc.cleared == []


def test_appeared_is_reported_even_though_it_was_not_handed_over(monkeypatch) -> None:
    """A defect that arrived AFTER the audit is the one no other organ will mention."""
    monkeypatch.setattr(ar, "_live_volatile_ids", lambda: ({"dig-output-uncommitted"}, ""))
    rc = ar.recheck([], ran=None)
    assert rc.appeared == ["dig-output-uncommitted"]
    assert rc.cleared == []


def test_failed_measurement_never_clears_anything(monkeypatch) -> None:
    """THE REFUSAL PATH. A re-measure that could not run must leave the snapshot verdict standing
    and say so -- clearing on a failed measurement is WS-005 on the one input that says what is
    broken."""
    monkeypatch.setattr(ar, "_live_volatile_ids", lambda: (set(), "git unavailable"))
    rc = ar.recheck(["dig-output-uncommitted"], ran=None)
    assert rc.cleared == []
    assert rc.unverified == ["dig-output-uncommitted"]
    assert rc.ran is False
    assert "git unavailable" in rc.why
    assert any("UNMEASURED, not clean" in ln for ln in ar.render(rc))


def test_a_raising_check_is_reported_not_swallowed(monkeypatch) -> None:
    """No silent swallow (L1.41): an exception inside a check becomes a named reason."""
    import importlib

    audit = importlib.import_module("scripts.max_audit")

    def boom(defects):
        raise RuntimeError("porcelain exploded")

    monkeypatch.setattr(audit, "check_dig_uncommitted", boom)
    found, why = ar._live_volatile_ids()
    assert found == set()
    assert "porcelain exploded" in why and "RuntimeError" in why


def test_git_outage_never_reads_as_cleared(monkeypatch) -> None:
    """THE SWALLOW-POISONS-THE-CONSUMER CASE, and it is the reason `_git_works` exists.

    check_dig_uncommitted returns with NO defect when git is unavailable -- correct for an audit,
    fabrication for a re-measure. If the probe is skipped, a git outage renders as "the defect was
    fixed", which is the one direction that buries a live defect permanently.
    """
    monkeypatch.setattr(ar, "_git_works", lambda root=None: False)
    found, why = ar._live_volatile_ids()
    assert found == set()
    assert "fabricated" in why

    rc = ar.recheck(["dig-output-uncommitted"], ran=None)
    assert rc.cleared == []
    assert rc.unverified == ["dig-output-uncommitted"]


def test_git_probe_is_true_in_this_repo() -> None:
    """Positive control: a probe that can only ever return False would silently disable the
    re-measure and degrade to the snapshot behaviour this module replaced (desk lesson: run the
    positive control -- a detector never shown to PASS has not been validated)."""
    assert ar._git_works(_MAX_AUDIT.parent) is True


def test_commits_since_is_none_when_unmeasurable() -> None:
    """Unmeasurable must never render as zero -- that would read as 'the tree has not moved'."""
    assert ar.commits_since(None) is None
    assert ar.commits_since("not-a-timestamp", root=Path("/nonexistent-path-xyz")) is None


@pytest.mark.parametrize("field_name", ["cleared", "standing", "appeared", "unverified"])
def test_render_mentions_every_populated_bucket(field_name: str) -> None:
    rc = ar.Recheck(**{field_name: ["dig-output-uncommitted"]}, why="w", commits_since=3)
    lines = ar.render(rc)
    if field_name == "standing":
        assert lines == []          # standing needs no banner: the handed list is already right
    else:
        assert any("dig-output-uncommitted" in ln for ln in lines)
