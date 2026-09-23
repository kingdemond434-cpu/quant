"""An empty working copy of a guarded document is destruction, never an edit.

THE DEFECT (measured live 2026-08-29 05:41Z). `scripts/check_doc_replay_fence.py` heals a tracked
document that has been replayed to an older blob of itself. Its second branch says: the working
blob appears nowhere in the file's history, therefore somebody is editing, therefore leave it
completely alone. That is correct for a real edit and catastrophically wrong for a zero-byte file.

Observed on the box: `docs/GAP_REGISTER.md` sat at 0 bytes against a 495,663-byte HEAD -- the
desk's only work driver, wiped -- while this fence printed "2 clean, 1 being edited, 0 replayed"
and exited 0. Restoring it by hand three times did not stick; the fence watched each wipe and
called it an edit. Destroyed and being-edited must never render identically (L1.28a).

Nobody edits a document by emptying it, and if they do, HEAD still holds every byte -- so the
heal cannot destroy work in either direction. It exits NON-ZERO even when the heal succeeds: a
healed replay is routine here, an emptied guarded document is a class this fence had never seen,
and on the same day a neighbouring route destroyed 87 register rows for good.
"""

from __future__ import annotations

import importlib.util
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
        "check_doc_replay_fence", _ROOT / "scripts" / "check_doc_replay_fence.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                          check=False).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A throwaway repo with one committed guarded document.

    Never the real tree: this fence RUNS `git checkout` against whatever ROOT points at, and a
    test that pointed it at the live checkout would heal or clobber real evidence mid-suite.
    """
    r = tmp_path / "repo"
    (r / "docs").mkdir(parents=True)
    _git(r.parent, "init", str(r))
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "docs" / "GAP_REGISTER.md").write_text("| 1 | a real row |\n" * 50, "utf-8")
    _git(r, "add", "docs/GAP_REGISTER.md")
    _git(r, "commit", "-m", "seed")
    return r


@pytest.fixture()
def mod(repo: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    m = _load()
    monkeypatch.setattr(m, "ROOT", repo)
    monkeypatch.setattr(m, "OUT", repo / "data" / "doc_replay_fence.json")
    monkeypatch.setattr(m, "LOG", repo / "data" / "doc_replay_fence.log")
    monkeypatch.setattr(m, "GUARDED", ["docs/GAP_REGISTER.md"])
    (repo / "data").mkdir(exist_ok=True)
    return m


def test_an_emptied_document_is_healed_and_reported(mod: ModuleType, repo: Path) -> None:
    doc = repo / "docs" / "GAP_REGISTER.md"
    doc.write_text("", "utf-8")
    assert doc.stat().st_size == 0
    rc = mod.main()
    assert doc.stat().st_size > 0, "the exact live failure: 0 bytes against a non-empty HEAD"
    assert doc.read_text("utf-8").count("| 1 |") == 50, "healed to HEAD byte-for-byte"
    assert rc == 1, "a healed EMPTYING still reaches a human; only a healed replay exits 0"


def test_a_real_edit_is_still_left_completely_alone(mod: ModuleType, repo: Path) -> None:
    """The one-way property: this may only ever act on MORE destruction, never on edits."""
    doc = repo / "docs" / "GAP_REGISTER.md"
    doc.write_text("| 1 | a real row |\n" * 50 + "| 2 | a NEW row someone is writing |\n", "utf-8")
    before = doc.read_text("utf-8")
    assert mod.main() == 0
    assert doc.read_text("utf-8") == before, "an in-progress edit must survive the fence"


def test_an_unchanged_document_is_clean(mod: ModuleType, repo: Path) -> None:
    assert mod.main() == 0


def test_an_empty_head_is_not_treated_as_destruction(mod: ModuleType, repo: Path) -> None:
    """If HEAD itself is empty there is nothing to restore and no claim to make."""
    doc = repo / "docs" / "GAP_REGISTER.md"
    doc.write_text("", "utf-8")
    _git(repo, "add", "docs/GAP_REGISTER.md")
    _git(repo, "commit", "-m", "deliberately empty")
    assert mod.main() == 0
    assert doc.stat().st_size == 0


def test_the_artifact_records_the_emptying(mod: ModuleType, repo: Path) -> None:
    import json
    (repo / "docs" / "GAP_REGISTER.md").write_text("", "utf-8")
    mod.main()
    rec = json.loads((repo / "data" / "doc_replay_fence.json").read_text("utf-8"))
    assert rec["status"] == "EMPTIED"
    assert rec["emptied"][0]["file"] == "docs/GAP_REGISTER.md"
    assert rec["emptied"][0]["outcome"] == "HEALED"


def test_a_truncated_prefix_is_healed_too(mod: ModuleType, repo: Path) -> None:
    """The empty rule alone was not enough, and the gap cost a second incident the same day.

    Hours after the 0-byte wipe was fixed, the same register came back as a 114,688-byte PREFIX
    holding 44 of 214 rows. Not empty, and its blob appears nowhere in history, so the
    "somebody is editing" branch left it alone and the fence went quiet over a ledger missing 170
    rows. A prefix is destruction wearing a plausible file size.
    """
    doc = repo / "docs" / "GAP_REGISTER.md"
    full = [f"| {i} | row {i} |" for i in range(1, 51)]
    doc.write_text("\n".join(full) + "\n", "utf-8")
    _git(repo, "add", "docs/GAP_REGISTER.md")
    _git(repo, "commit", "-m", "50 rows")
    doc.write_text("\n".join(full[:10]) + "\n", "utf-8")     # a prefix, not empty
    rc = mod.main()
    assert rc == 1
    assert len(doc.read_text("utf-8").splitlines()) == 50, "every row restored, not just the size"


def test_rewriting_a_rows_text_is_not_destruction(mod: ModuleType, repo: Path) -> None:
    """The invariant is the record's EXISTENCE. Ordinary editing must survive untouched."""
    doc = repo / "docs" / "GAP_REGISTER.md"
    doc.write_text("| 1 | original |\n| 2 | original |\n", "utf-8")
    _git(repo, "add", "docs/GAP_REGISTER.md")
    _git(repo, "commit", "-m", "two rows")
    edited = "| 1 | rewritten at length, with much more detail |\n| 2 | original |\n"
    doc.write_text(edited, "utf-8")
    assert mod.main() == 0
    assert doc.read_text("utf-8") == edited


def test_adding_rows_is_not_destruction(mod: ModuleType, repo: Path) -> None:
    """A session writing new rows must never be healed away -- that would be the fence causing
    exactly the loss it exists to prevent."""
    doc = repo / "docs" / "GAP_REGISTER.md"
    doc.write_text("| 1 | a |\n", "utf-8")
    _git(repo, "add", "docs/GAP_REGISTER.md")
    _git(repo, "commit", "-m", "one row")
    grown = "| 1 | a |\n| 2 | brand new, uncommitted |\n"
    doc.write_text(grown, "utf-8")
    assert mod.main() == 0
    assert doc.read_text("utf-8") == grown
