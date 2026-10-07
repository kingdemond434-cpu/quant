"""A protected ledger may not lose records, and the guard is wired where the attack lands.

THE DEFECT (measured 2026-08-29). `ecc14ab0 "desk snapshot 2026-08-29T04:22Z"` rewrote
docs/GAP_REGISTER.md with 1 insertion and 813 deletions, destroying 87 gap rows -- ids 89 and
111-196, including five closed by the gap-fixer three hours earlier and row 194, a principal
console item with a 2026-09-10 deadline.

libs/ops/protected_artifacts.py already listed that file, and its stated reason was exactly this
failure: "Regenerated from a partial cycle it drops rows -- and a gap that vanishes reads exactly
like a gap closed." The list had ONE enforcer, the pytest conftest, and an automated snapshot
commit from another box never runs pytest. The guard was wired to the path the attack does not
take.

WHY RECORDS AND NOT A LINE THRESHOLD: a percentage is a heuristic, and on a shared tree a
heuristic either eats real edits or is loose enough to miss the real case. These files are
ledgers, and a ledger has one invariant worth enforcing -- a record that existed must still
exist. Rewriting a row's text is ordinary work and passes.

The first two tests are the positive and negative control run against the real commits.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(
        "check_protected_records", _ROOT / "scripts" / "check_protected_records.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod() -> ModuleType:
    return _load()


def _have(sha: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=_ROOT,
                          capture_output=True, check=False).returncode == 0


def test_the_real_destroying_commit_is_caught(mod: ModuleType,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    """Positive control against the commit that actually deleted 87 rows."""
    if not _have("ecc14ab0"):
        pytest.skip("ecc14ab0 not present in this clone")
    assert mod.main(["--range", "ecc14ab0^", "ecc14ab0"]) == 2
    out = capsys.readouterr().out
    assert "RECORDS_LOST" in out and "87 record(s)" in out
    assert "194" in out, "the principal-console row must be named, not just counted"


def test_a_legitimate_row_adding_commit_passes(mod: ModuleType) -> None:
    """Negative control: the commit that ADDED rows 189-196 must not trip the guard."""
    if not _have("bcc1b8a9"):
        pytest.skip("bcc1b8a9 not present in this clone")
    assert mod.main(["--range", "bcc1b8a9^", "bcc1b8a9"]) == 0


def test_markdown_rows_are_identified_by_id(mod: ModuleType) -> None:
    text = "| 12 | a row |\n| 13 | another |\nnot a row at all\n"
    assert mod.records("docs/GAP_REGISTER.md", text) == {"12", "13"}


def test_rewriting_a_rows_text_is_not_a_loss(mod: ModuleType) -> None:
    """Ordinary work must pass: only the record's EXISTENCE is the invariant."""
    before = "| 7 | old wording |\n"
    after = "| 7 | completely rewritten wording, much longer |\n"
    assert mod.compare("docs/GAP_REGISTER.md", before, after) is None


def test_a_deleted_row_is_a_loss(mod: ModuleType) -> None:
    f = mod.compare("docs/GAP_REGISTER.md", "| 7 | a |\n| 8 | b |\n", "| 7 | a |\n")
    assert f is not None
    assert f["kind"] == "RECORDS_LOST"
    assert f["lost"] == ["8"]


def test_emptying_is_caught_even_for_an_unknown_shape(mod: ModuleType) -> None:
    """An unreadable format yields no record identities, so the empty rule is what governs it."""
    f = mod.compare("docs/whatever.txt", "content that matters\n", "")
    assert f is not None and f["kind"] == "EMPTIED"


def test_an_unknown_shape_invents_no_records(mod: ModuleType) -> None:
    """Fabricating identities for a format this cannot read would fabricate losses AND passes."""
    assert mod.records("docs/whatever.txt", "anything\nat all\n") == set()


def test_jsonl_records_use_their_own_id(mod: ModuleType) -> None:
    text = '{"id": "R0001", "x": 1}\n{"id": "R0002", "x": 2}\n'
    assert mod.records("docs/x.jsonl", text) == {"id='R0001'", "id='R0002'"}


def test_a_json_object_loses_a_key(mod: ModuleType) -> None:
    f = mod.compare("data/x.json", '{"a": 1, "b": 2}', '{"a": 9}')
    assert f is not None and f["lost"] == ["b"]


def test_the_override_is_explicit(mod: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """A deliberate retirement is allowed, but only by someone who typed the variable."""
    if not _have("ecc14ab0"):
        pytest.skip("ecc14ab0 not present in this clone")
    monkeypatch.setenv(mod.OVERRIDE, "1")
    assert mod.main(["--range", "ecc14ab0^", "ecc14ab0"]) == 0


def test_the_pre_commit_hook_actually_calls_it() -> None:
    """A guard nobody calls always returns True -- the lesson this desk has already paid for."""
    hook = (_ROOT / "ops" / "githooks" / "pre-commit").read_text("utf-8")
    assert "check_protected_records.py" in hook


# ---------------------------------------------------------------------------------------------
# MERGE AWARENESS AND THE NARROWED LOSS OVERRIDE (2026-10-07).
#
# Merging LIVE into a branch that predates a lessons edit staged LIVE's exact blob, and the guard,
# which compares the staged blob with HEAD (the first parent) only, called three lessons
# RECORDS_REWRITTEN. The content was already committed, and already checked, on the other parent.
# A staged blob that equals a MERGE_HEAD parent's blob is now exempt; every other case is checked
# as before. ALLOW_PROTECTED_RECORD_LOSS used to let a rewrite through as well; it no longer does.
# These tests drive main() against a real temporary git repository.
# ---------------------------------------------------------------------------------------------

_LEDGER = "docs/ledger.jsonl"


def _line(rid: str, lesson: str) -> str:
    return json.dumps({"id": rid, "lesson": lesson}) + "\n"


@pytest.fixture()
def repo(tmp_path: Path, mod: ModuleType, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", mod.OVERRIDE,
                "ALLOW_PROTECTED_RECORD_REWRITE"):
        monkeypatch.delenv(var, raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    _g(root, "init", "-q", "-b", "main")
    (root / "docs").mkdir()
    (root / _LEDGER).write_text(_line("L1", "a") + _line("L2", "b"), encoding="utf-8")
    _g(root, "add", _LEDGER)
    _g(root, "commit", "-q", "-m", "base")
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "REPORT", tmp_path / "PROTECTED_RECORDS.json")
    monkeypatch.setattr(mod, "_protected", lambda: {_LEDGER: "a test ledger"})
    return root


def _g(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.hooksPath=/dev/null",
         "-c", "commit.gpgsign=false", *args],
        cwd=root, capture_output=True, text=True, check=True).stdout


def _branch_rewriting(root: Path, name: str, lesson: str) -> None:
    """A side branch off the base that rewrites L1, leaving main where it was."""
    _g(root, "checkout", "-q", "-b", name, "main")
    (root / _LEDGER).write_text(_line("L1", lesson) + _line("L2", "b"), encoding="utf-8")
    _g(root, "commit", "-q", "-am", f"rewrite L1 on {name}")
    _g(root, "checkout", "-q", "main")


def _diverge_main(root: Path) -> None:
    (root / "other.txt").write_text("main moved\n", encoding="utf-8")
    _g(root, "add", "other.txt")
    _g(root, "commit", "-q", "-m", "main moves on")


def test_a_merge_taking_a_parents_exact_blob_passes(
        mod: ModuleType, repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _branch_rewriting(repo, "side", "a, sharpened upstream")
    _diverge_main(repo)
    _g(repo, "merge", "--no-commit", "--no-ff", "side")
    side = _g(repo, "rev-parse", "side").strip()
    assert mod.main([]) == 0
    assert f"equals parent {side}" in capsys.readouterr().out


def test_an_octopus_merge_matches_any_parent(
        mod: ModuleType, repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _g(repo, "checkout", "-q", "-b", "quiet", "main")
    (repo / "quiet.txt").write_text("q\n", encoding="utf-8")
    _g(repo, "add", "quiet.txt")
    _g(repo, "commit", "-q", "-m", "quiet branch")
    _g(repo, "checkout", "-q", "main")
    _branch_rewriting(repo, "side", "a, sharpened upstream")
    _diverge_main(repo)
    _g(repo, "merge", "--no-commit", "--no-ff", "quiet", "side")
    side = _g(repo, "rev-parse", "side").strip()
    assert mod.main([]) == 0
    assert f"equals parent {side}" in capsys.readouterr().out


def test_a_merge_blob_matching_neither_parent_is_refused(mod: ModuleType, repo: Path) -> None:
    _branch_rewriting(repo, "side", "a, sharpened upstream")
    _diverge_main(repo)
    _g(repo, "merge", "--no-commit", "--no-ff", "side")
    (repo / _LEDGER).write_text(_line("L1", "a third thing") + _line("L2", "b"),
                                encoding="utf-8")
    _g(repo, "add", _LEDGER)
    assert mod.main([]) == 2


def test_the_loss_override_never_lets_a_rewrite_through(
        mod: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / _LEDGER).write_text(_line("L1", "silently replaced") + _line("L2", "b"),
                                encoding="utf-8")
    _g(repo, "add", _LEDGER)
    monkeypatch.setenv(mod.OVERRIDE, "1")
    assert mod.main([]) == 2


def test_the_loss_override_still_allows_a_loss(
        mod: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / _LEDGER).write_text(_line("L1", "a"), encoding="utf-8")
    _g(repo, "add", _LEDGER)
    assert mod.main([]) == 2
    monkeypatch.setenv(mod.OVERRIDE, "1")
    assert mod.main([]) == 0
