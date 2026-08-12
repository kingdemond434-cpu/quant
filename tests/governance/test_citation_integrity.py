"""R0369 -- the ledger's proof-of-work must resolve for readers other than its author.

The write-time check (`dispose` refuses an empty --commit) only asks whether the field is
non-empty. These assert the read-time property it cannot reach: that the citation names ONE
commit for EVERY clone.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from libs.research.citation_integrity import BAD_STATES, classify, reachable_sets

_ROOT = Path(__file__).resolve().parents[2]


def _repo(tmp_path: Path) -> Path:
    """A real git repo -- the classifier's whole job is reachability, which a fake cannot have."""
    r = tmp_path / "repo"
    r.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=r, check=True, capture_output=True)  # noqa: E731
    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@t.t")
    run("config", "user.name", "t")
    (r / "f.txt").write_text("one")
    run("add", "f.txt")
    run("commit", "-qm", "one")
    return r


def _sha(r: Path, rev: str = "HEAD") -> str:
    return subprocess.run(["git", "rev-parse", rev], cwd=r, capture_output=True,
                          text=True, check=True).stdout.strip()


def test_symbolic_refs_are_invalid_even_though_they_resolve(tmp_path: Path) -> None:
    """THE DEFECT THAT HID: `git cat-file -e HEAD` always succeeds, so a `HEAD` citation reads as
    healthy to any existence check while naming a different commit for every reader."""
    r = _repo(tmp_path)
    rep = classify([{"id": "R1", "commit": "HEAD"}, {"id": "R2", "commit": "master"}], r)
    assert rep["measured"]
    states = {c.row_id: c.state for c in rep["citations"]}
    assert states == {"R1": "INVALID", "R2": "INVALID"}
    assert rep["n_bad"] == 2


@pytest.mark.parametrize("placeholder", ["pending", "pending-this-commit", "", "   ", "abc"])
def test_placeholders_never_pass(tmp_path: Path, placeholder: str) -> None:
    r = _repo(tmp_path)
    rep = classify([{"id": "R1", "commit": placeholder}], r)
    if not placeholder.strip():
        assert rep["no_citation"] == 1 and not rep["citations"]
    else:
        assert rep["citations"][0].state == "INVALID"


def test_a_local_commit_is_pending_push_not_bad(tmp_path: Path) -> None:
    """A row disposed minutes ago cites an unpushed commit. Counting that as a defect would make
    the fence red on every honest cycle, and a fence red from day one gets switched off."""
    r = _repo(tmp_path)
    rep = classify([{"id": "R1", "commit": _sha(r)}], r)
    c = rep["citations"][0]
    assert c.state == "PENDING-PUSH"
    assert not c.is_bad
    assert rep["n_bad"] == 0


def test_orphaned_commit_is_caught_while_still_recoverable(tmp_path: Path) -> None:
    """R0369's exact case: the SHA a rebase left behind. The object still exists, so an
    existence check passes; no ref reaches it, so no other clone will ever resolve it."""
    r = _repo(tmp_path)
    run = lambda *a: subprocess.run(["git", *a], cwd=r, check=True, capture_output=True)  # noqa: E731
    (r / "f.txt").write_text("two")
    run("commit", "-qam", "two")
    orphan = _sha(r)
    run("reset", "-q", "--hard", "HEAD~1")          # the commit survives, unreferenced
    rep = classify([{"id": "R1", "commit": orphan}], r)
    c = rep["citations"][0]
    assert c.state == "ORPHANED", f"got {c.state}: {c.detail}"
    assert c.is_bad


def test_missing_object_is_distinct_from_orphaned(tmp_path: Path) -> None:
    """ABSENT and UNREACHABLE demand opposite responses (L1.55): one needs the commit found,
    the other needs it pushed before gc. Collapsing them debugs the wrong thing."""
    r = _repo(tmp_path)
    rep = classify([{"id": "R1", "commit": "0" * 40}], r)
    assert rep["citations"][0].state == "MISSING"


def test_unreadable_git_reports_unmeasured_not_clean(tmp_path: Path) -> None:
    """An unmeasured quantity counts as zero, never as fine (L1.28a). If this returned an empty
    reachable set instead, every citation would classify ORPHANED -- a fabricated red board."""
    empty = tmp_path / "not-a-repo"
    empty.mkdir()
    assert reachable_sets(empty) is None
    rep = classify([{"id": "R1", "commit": "a" * 40}], empty)
    assert rep["measured"] is False
    assert rep["n_bad"] == 0 and not rep["citations"]


def test_attrition_is_counted_not_implied(tmp_path: Path) -> None:
    """L1.60: rows with no citation must be visible, so the shrink from rows to citations
    cannot read as coverage."""
    r = _repo(tmp_path)
    rows = [{"id": "R1", "commit": _sha(r)}, {"id": "R2"}, {"id": "R3", "commit": None}]
    rep = classify(rows, r)
    assert rep["attempted"] == 3
    assert rep["no_citation"] == 2
    assert len(rep["citations"]) == 1


def test_bad_states_excludes_pending_push() -> None:
    assert "PENDING-PUSH" not in BAD_STATES
    assert {"ORPHANED", "MISSING", "INVALID"} == set(BAD_STATES)


# --------------------------------------------------------------------------- the fence + verb


def test_fence_floor_is_never_raised_silently() -> None:
    """The floor is a RATCHET (L1.0). This pins it so a future edit upward has to change a test,
    which is the whole mechanism -- raising it to clear a red board is the failure to prevent."""
    src = (_ROOT / "scripts/check_citation_integrity.py").read_text("utf-8")
    line = next(ln for ln in src.splitlines() if ln.startswith("_FLOOR"))
    assert int(line.split("=")[1].strip()) <= 3, (
        "the citation floor may only ever move DOWN, and only in a commit that repoints the "
        "rows it accounts for")


def _fence_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cci_under_test", _ROOT / "scripts/check_citation_integrity.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _root_with_ledger(tmp_path: Path, rows: list[dict]) -> Path:
    """A root that is BOTH a git repo and a ledger home -- which is what production hands the
    fence. A fixture with the ledger but no repo would exercise only the UNMEASURED branch and
    leave OK and DEGRADED, the two verdicts that matter, untested."""
    r = _repo(tmp_path)
    (r / "docs/research").mkdir(parents=True, exist_ok=True)
    (r / "docs/research/recommendation_ledger.json").write_text(
        json.dumps({"recommendations": rows}, indent=1), "utf-8")
    return r


def test_fence_goes_degraded_when_a_new_bad_citation_appears(tmp_path: Path) -> None:
    """THE REFUSAL PATH, exercised rather than asserted. A fence whose failing branch has never
    been shown to fire is a fence whose rejections alone have been observed."""
    mod = _fence_module()
    rows = [{"id": f"R{i:04d}", "status": "implemented", "commit": "pending"}
            for i in range(mod._FLOOR + 1)]
    rep = mod.build_report(_root_with_ledger(tmp_path, rows))
    assert rep["status"] == "DEGRADED", rep["why"]
    assert rep["n_bad"] == mod._FLOOR + 1
    from libs.ops.fence_exit import fence_exit
    assert fence_exit(rep["status"], mod._PASSING, scanned=rep["n_citations"]) == 2


def test_fence_is_ok_when_every_citation_resolves(tmp_path: Path) -> None:
    mod = _fence_module()
    root = _root_with_ledger(tmp_path, [])
    rows = [{"id": "R0001", "status": "implemented", "commit": _sha(root)}]
    (root / "docs/research/recommendation_ledger.json").write_text(
        json.dumps({"recommendations": rows}, indent=1), "utf-8")
    rep = mod.build_report(root)
    assert rep["status"] == "OK", rep["why"]
    assert rep["n_bad"] == 0


def test_fence_refuses_to_pass_an_empty_scope(tmp_path: Path) -> None:
    """L1.57: a passing verdict over zero citations is vacuous, not evidence."""
    mod = _fence_module()
    rep = mod.build_report(_root_with_ledger(tmp_path, [{"id": "R1", "status": "open"}]))
    assert rep["status"] == "UNMEASURED"
    from libs.ops.fence_exit import fence_exit
    assert fence_exit(rep["status"], mod._PASSING, scanned=rep["n_citations"]) == 2


def test_fence_reports_unmeasured_on_an_unreadable_ledger(tmp_path: Path) -> None:
    """Condition 1 of the build standard: the organ must be able to say it could not measure."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cci_under_test", _ROOT / "scripts/check_citation_integrity.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rep = mod.build_report(tmp_path)          # no ledger under here at all
    assert rep["status"] == "UNMEASURED"
    assert "unreadable" in rep["why"]


def _rec_module(ledger: Path):
    """Load recommendations.py with its LEDGER pointed at a fixture.

    IN-PROCESS AND REDIRECTED ON PURPOSE. `LEDGER` is a module-level absolute path, so a test
    that writes a fixture and then shells out to the CLI silently exercises the LIVE ledger --
    which is how a test suite ends up writing to the artifact it is meant to be checking.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_rec_under_test", _ROOT / "scripts/recommendations.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.LEDGER = ledger
    return mod


def _fixture_ledger(tmp_path: Path, commit: str = "HEAD") -> Path:
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps({"recommendations": [
        {"id": "R1", "source": "cycle", "summary": "a row about citations",
         "status": "implemented", "reason": None, "commit": commit, "due": None,
         "disposed": "2026-01-01T00:00:00+00:00"}]}, indent=1), "utf-8")
    return p


def test_repoint_refuses_an_unresolvable_new_citation(tmp_path: Path) -> None:
    """The verb may not launder one dangling pointer into another -- that would let the ledger
    look repaired while still proving nothing."""
    import argparse
    mod = _rec_module(_fixture_ledger(tmp_path))
    args = argparse.Namespace(id="R1", commit="definitely-not-a-commit", expect=None,
                              reason="the original citation was a symbolic ref, per-clone")
    with pytest.raises(SystemExit, match="does not resolve"):
        mod.repoint(args)
    # and the row is untouched
    assert json.loads(mod.LEDGER.read_text("utf-8"))["recommendations"][0]["commit"] == "HEAD"


def test_repoint_moves_the_pointer_and_logs_the_old_one(tmp_path: Path) -> None:
    import argparse
    mod = _rec_module(_fixture_ledger(tmp_path))
    real = _sha(_ROOT)
    mod.repoint(argparse.Namespace(
        id="R1", commit=real, expect="citations",
        reason="rebase rewrote the original SHA; re-pointed at the equivalent commit"))
    row = json.loads(mod.LEDGER.read_text("utf-8"))["recommendations"][0]
    assert row["commit"] == real
    assert row["status"] == "implemented", "repoint must not disturb the disposition"
    assert row["repoints"][0]["was"] == "HEAD"
    assert "rebase" in row["repoints"][0]["why"]


def test_repoint_refuses_a_row_that_is_not_implemented(tmp_path: Path) -> None:
    import argparse
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps({"recommendations": [
        {"id": "R1", "source": "cycle", "summary": "an open row", "status": "open",
         "reason": None, "commit": None, "due": None, "disposed": None}]}, indent=1), "utf-8")
    mod = _rec_module(p)
    with pytest.raises(SystemExit, match="not implemented"):
        mod.repoint(argparse.Namespace(
            id="R1", commit=_sha(_ROOT), expect=None,
            reason="trying to cite a commit on a row that was never implemented"))


def test_repoint_requires_a_substantive_reason(tmp_path: Path) -> None:
    import argparse
    mod = _rec_module(_fixture_ledger(tmp_path))
    with pytest.raises(SystemExit, match="real reason"):
        mod.repoint(argparse.Namespace(id="R1", commit=_sha(_ROOT), expect=None, reason="oops"))


def test_repoint_leaves_the_disposition_alone() -> None:
    """It moves the pointer and nothing else: status and reason are untouched by construction."""
    src = (_ROOT / "scripts/recommendations.py").read_text("utf-8")
    body = src.split("def repoint(")[1].split("\ndef ")[0]
    assert 'row["commit"] = a.commit' in body
    assert "status=" not in body, "repoint must never move a row's status"
    assert 'row["status"] =' not in body
