"""A detector whose only observed behaviour is silence has not been validated.

The desk's standing lesson (`institutional_knowledge.md`, "run the positive control") is that a
gate never shown to FIRE on a known-present defect has had only its silences observed. Two of
this desk's own detectors shipped scoring 0/3 against hand-verified positives. So the tests below
PLANT each reversion class into a real git repo and require it to be found, and only then check
that honest ledgers stay quiet.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from libs.ops.ledger_reversion import (
    LEDGER_REL,
    census,
    repair_plan,
    rows_of,
)


def _row(rid: str, **kw: object) -> dict[str, object]:
    row: dict[str, object] = {"id": rid, "summary": f"row {rid}", "status": "open"}
    row.update(kw)
    return row


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs/research").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    return root


def _commit(root: Path, rows: list[dict[str, object]], msg: str) -> None:
    (root / LEDGER_REL).write_text(json.dumps({"recommendations": rows}), "utf-8")
    subprocess.run(["git", "add", LEDGER_REL], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=root, check=True)


# --------------------------------------------------------------------------- positive controls

def test_POSITIVE_CONTROL_a_reverted_status_is_FOUND(tmp_path: Path) -> None:
    """The exact shape of merge a9c13de1: decided in one commit, open again in the next."""
    root = _repo(tmp_path)
    _commit(root, [_row("R0001")], "raise")
    _commit(root, [_row("R0001", status="implemented", commit="abc123",
                        reason="did the thing")], "dispose")
    _commit(root, [_row("R0001")], "a merge takes the stale side")

    cen = census(root)
    assert cen.status == "REVERTED", "the planted reversion was not detected"
    assert [r.id for r in cen.reversions] == ["R0001"]
    got = cen.reversions[0]
    assert got.kind == "STATUS"
    assert got.was == "implemented"
    assert got.fields["commit"] == "abc123", "the repair needs the ORIGINAL citation back"


def test_POSITIVE_CONTROL_a_shrunken_history_list_is_FOUND(tmp_path: Path) -> None:
    """R0042/R0050's shape: still disposed, so the status test cannot see it."""
    root = _repo(tmp_path)
    _commit(root, [_row("R0001", status="implemented", commit="old")], "dispose")
    _commit(root, [_row("R0001", status="implemented", commit="new",
                        repoints=[{"was": "old", "now": "new"}])], "repoint")
    _commit(root, [_row("R0001", status="implemented", commit="old")], "merge drops the repoint")

    cen = census(root)
    assert cen.status == "REVERTED"
    assert [(r.id, r.kind) for r in cen.reversions] == [("R0001", "HISTORY")]
    assert "repoints 1->0" in cen.reversions[0].detail


def test_a_status_reversion_on_a_row_that_is_STILL_DISPOSED_is_caught_by_the_history_test(
        tmp_path: Path) -> None:
    """`done` -> `implemented` is a reversion the open-row test structurally cannot see.

    This is R0050 exactly: it went back to `implemented` citing the literal string 'HEAD', which
    is why `check_citation_integrity` sits at exit 2 desk-wide. Nothing about the row is open, so
    only the append-only invariant reaches it.
    """
    root = _repo(tmp_path)
    _commit(root, [_row("R0001", status="implemented", commit="HEAD")], "dispose badly")
    _commit(root, [_row("R0001", status="done", commit=None,
                        corrections=[{"was": "implemented", "why": "unresolvable"}])], "correct")
    _commit(root, [_row("R0001", status="implemented", commit="HEAD")], "merge reverts it")

    cen = census(root)
    assert [(r.id, r.kind) for r in cen.reversions] == [("R0001", "HISTORY")]
    assert cen.reversions[0].was == "done"


# ------------------------------------------------------------------------------- true negatives

def test_a_legitimate_correction_is_NOT_a_reversion(tmp_path: Path) -> None:
    """`correct()` re-opens a MISFILED row on purpose and records why.

    13 rows on the live ledger carry this history. A fence that flagged them would be red on
    honest work from its first run and would be acked into silence within a day (L1.43).
    """
    root = _repo(tmp_path)
    _commit(root, [_row("R0001")], "raise")
    _commit(root, [_row("R0001", status="implemented", commit="abc")], "dispose")
    _commit(root, [_row("R0001", corrections=[{"was": "implemented", "why": "misfiled"}])],
            "correct")

    cen = census(root)
    assert cen.status == "OK", [r.as_row() for r in cen.reversions]


def test_an_honest_ledger_is_quiet_and_still_reports_its_denominator(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _commit(root, [_row("R0001"), _row("R0002", status="implemented", commit="a")], "raise")
    _commit(root, [_row("R0001"), _row("R0002", status="implemented", commit="a"),
                   _row("R0003")], "raise another")

    cen = census(root)
    assert cen.status == "OK"
    assert cen.n_rows == 3, "the denominator must count what was compared, not what was found"
    assert cen.n_open == 2
    assert cen.n_versions_read == 2


# ----------------------------------------------------------------- absence is never a clean pass

def test_a_repo_with_no_ledger_history_is_UNMEASURED_not_OK(tmp_path: Path) -> None:
    """L1.28a: "we could not look" and "there is nothing there" are different claims."""
    root = _repo(tmp_path)
    (root / LEDGER_REL).write_text(json.dumps({"recommendations": [_row("R0001")]}), "utf-8")
    cen = census(root)                      # never committed -- no history to compare against
    assert cen.status == "UNMEASURED"
    assert cen.n_versions_read == 0


def test_an_unreadable_version_is_COUNTED_not_silently_skipped(tmp_path: Path) -> None:
    """L1.60: four of the live ledger's 423 versions are torn. A skip nobody counts is a lie."""
    root = _repo(tmp_path)
    _commit(root, [_row("R0001", status="implemented", commit="abc")], "dispose")
    (root / LEDGER_REL).write_text("<<<<<<< HEAD\nnot json\n", "utf-8")
    subprocess.run(["git", "add", LEDGER_REL], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "torn"], cwd=root, check=True)
    _commit(root, [_row("R0001")], "reverted")

    cen = census(root)
    assert cen.n_unreadable == 1
    assert cen.n_versions_attempted == 3
    assert cen.n_versions_read == 2
    assert [r.id for r in cen.reversions] == ["R0001"], "a torn version must not hide the loss"


# ------------------------------------------------------------------------------------- the repair

def test_repair_restores_the_decision_and_stamps_that_it_happened(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _commit(root, [_row("R0001")], "raise")
    _commit(root, [_row("R0001", status="implemented", commit="abc123",
                        reason="did it", disposed="2026-08-19T00:00:00+00:00")], "dispose")
    _commit(root, [_row("R0001")], "merge reverts")

    rows = rows_of(json.loads((root / LEDGER_REL).read_text("utf-8")))
    touched = repair_plan(census(root, head_rows=rows), rows, "2026-08-20T00:00:00+00:00")

    assert [r["id"] for r in touched] == ["R0001"]
    assert rows[0]["status"] == "implemented"
    assert rows[0]["commit"] == "abc123", "the citation must come back with the status"
    assert rows[0]["reason"] == "did it"
    stamp = rows[0]["restorations"][0]
    assert stamp["restored_to"] == "implemented"
    assert "merge" in stamp["why"], "the record must say WHY the row moved, not just that it did"
    # And the repair is idempotent: re-running finds nothing left to restore.
    assert census(root, head_rows=rows).status == "OK"


def test_repair_puts_a_lost_history_list_back_WITH_its_fields(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _commit(root, [_row("R0001", status="implemented", commit="old")], "dispose")
    _commit(root, [_row("R0001", status="implemented", commit="new",
                        repoints=[{"was": "old", "now": "new"}])], "repoint")
    _commit(root, [_row("R0001", status="implemented", commit="old")], "merge drops it")

    rows = rows_of(json.loads((root / LEDGER_REL).read_text("utf-8")))
    repair_plan(census(root, head_rows=rows), rows, "2026-08-20T00:00:00+00:00")

    assert len(rows[0]["repoints"]) == 1, "the lost repoint must come back"
    assert rows[0]["commit"] == "new", "and so must the citation it moved to"
    assert census(root, head_rows=rows).status == "OK"


def test_repair_NEVER_invents_a_row_that_HEAD_no_longer_has(tmp_path: Path) -> None:
    """A vanished row is a DIFFERENT defect; re-creating it here would hide it."""
    root = _repo(tmp_path)
    _commit(root, [_row("R0001", status="implemented", commit="abc")], "dispose")
    _commit(root, [_row("R0001")], "revert")

    rows: list[dict[str, object]] = []                 # HEAD lost the row entirely
    cen = census(root, head_rows=[_row("R0001")])
    assert cen.reversions, "guard the guard: the census must have something to try to repair"
    assert repair_plan(cen, rows, "2026-08-20T00:00:00+00:00") == []


# ------------------------------------------------------------------------------------- shapes

@pytest.mark.parametrize("payload,n", [
    ({"recommendations": [{"id": "R1"}]}, 1),
    ([{"id": "R1"}, {"id": "R2"}], 2),                 # the ledger's earlier bare-list shape
    ({"recommendations": "not a list"}, 0),
    ([{"no_id": 1}, "not a dict"], 0),
    (None, 0),
])
def test_rows_of_reads_both_ledger_shapes_and_refuses_junk(payload: object, n: int) -> None:
    assert len(rows_of(payload)) == n


# ------------------------------------------------------------- the fence's own exit-code contract

def test_scripts_check_ledger_reversion_EXITS_2_on_a_reverted_ledger(tmp_path: Path) -> None:
    """The whole point is the exit code: a fence that finds the defect and exits 0 is decoration.

    Driven as a subprocess against a planted repo rather than by importing `main()`, because the
    exit code IS the interface -- `ops/gates.sh` and the cron line both read nothing else.
    """
    root = _repo(tmp_path)
    _commit(root, [_row("R0001", status="implemented", commit="abc")], "dispose")
    _commit(root, [_row("R0001")], "merge reverts it")

    fence = Path(__file__).resolve().parents[2] / "scripts/check_ledger_reversion.py"
    env = {**os.environ, "QUANT_LAW_GUARD": "off"}       # the guard is not what is under test
    red = subprocess.run([sys.executable, str(fence), "--root", str(root)], env=env,
                         capture_output=True, text=True)
    assert red.returncode == 2, red.stdout + red.stderr
    assert "REVERTED" in red.stdout

    fixed = subprocess.run([sys.executable, str(fence), "--repair", "--root", str(root)], env=env,
                           capture_output=True, text=True)
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert "restored 1" in fixed.stdout
    assert json.loads((root / LEDGER_REL).read_text("utf-8"))[
        "recommendations"][0]["status"] == "implemented"

    green = subprocess.run([sys.executable, str(fence), "--root", str(root)], env=env,
                           capture_output=True, text=True)
    assert green.returncode == 0, green.stdout + green.stderr


def test_a_ledger_with_every_row_DISPOSED_still_passes(tmp_path: Path) -> None:
    """Draining the backlog to zero open rows must not turn this fence red.

    The denominator is ROWS COMPARED, not OPEN rows -- otherwise the fence would fail for having
    achieved exactly what it exists to encourage, which is L1.53(4) pointed backwards. Caught by
    the CLI test above before it shipped.
    """
    root = _repo(tmp_path)
    _commit(root, [_row("R0001")], "raise")
    _commit(root, [_row("R0001", status="implemented", commit="abc")], "dispose the last one")

    cen = census(root)
    assert cen.status == "OK" and cen.n_open == 0 and cen.n_rows == 1
    fence = Path(__file__).resolve().parents[2] / "scripts/check_ledger_reversion.py"
    out = subprocess.run([sys.executable, str(fence), "--root", str(root)],
                         env={**os.environ, "QUANT_LAW_GUARD": "off"},
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_scripts_check_ledger_reversion_REFUSES_a_repair_it_cannot_measure(
        tmp_path: Path) -> None:
    """No history read means nothing is KNOWN lost; repairing anyway would fabricate."""
    root = _repo(tmp_path)
    (root / LEDGER_REL).write_text(json.dumps({"recommendations": [_row("R0001")]}), "utf-8")
    fence = Path(__file__).resolve().parents[2] / "scripts/check_ledger_reversion.py"
    out = subprocess.run([sys.executable, str(fence), "--repair", "--root", str(root)],
                         env={**os.environ, "QUANT_LAW_GUARD": "off"},
                         capture_output=True, text=True)
    assert out.returncode == 2, out.stdout + out.stderr
    assert "REFUSING" in out.stdout
