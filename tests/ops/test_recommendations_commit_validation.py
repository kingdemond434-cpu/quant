"""A CITATION MUST BE THE SHA ITSELF, AND IT MUST STAY DEREFERENCEABLE (R0478).

`dispose --status implemented` validated only that --commit was NON-EMPTY, so three ledgered rows
carried the literal string 'HEAD' -- a citation that "resolves" to whatever some future checkout
has loaded, which is worse than unresolvable because it is confidently wrong. And nothing ever
read a citation back: a rebase or dropped branch could orphan a proven row's sha with no fence
anywhere to notice (the desk uses merges instead of rebases BECAUSE of that interaction; a checker
makes the failure visible instead of latent).

What these tests pin:
  * a symbolic citation ('HEAD', a branch name) is REFUSED at dispose time,
  * an unresolvable hex citation is REFUSED at dispose time,
  * a valid short sha is accepted and stored as the FULL sha,
  * `verify_citations` classifies symbolic / unresolvable / legacy-uncited separately, because
    the three demand different repairs,
  * a git failure mid-batch reads as UNMEASURED (checked < of), never as clean.
"""

from __future__ import annotations

import argparse
import json
import subprocess

import pytest

from scripts import recommendations as recs


def _git(tmp_path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True,
                          text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A scratch git repo with one commit, and the ledger pointed into it."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("x", "utf-8")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "commit", "-qm", "work")
    sha = _git(tmp_path, "rev-parse", "HEAD")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"recommendations": [
        {"id": "R9001", "source": "t", "summary": "the test row", "roi_bps": None,
         "raised": "2026-08-18T00:00:00+00:00", "status": "open", "reason": None,
         "commit": None, "due": None, "disposed": None},
    ]}), "utf-8")
    monkeypatch.setattr(recs, "LEDGER", ledger)
    monkeypatch.setattr(recs, "ROOT", tmp_path)
    return tmp_path, sha, ledger


def _dispose_args(**kw) -> argparse.Namespace:
    base = {"id": "R9001", "status": "implemented", "reason": None, "commit": None,
            "due": None, "expect": "test row"}
    base.update(kw)
    return argparse.Namespace(**base)


class TestDisposeRefusals:
    def test_literal_head_is_refused(self, repo):
        """The measured defect: 'HEAD' satisfied the non-empty check forever."""
        with pytest.raises(SystemExit, match="symbolic name"):
            recs.dispose(_dispose_args(commit="HEAD"))

    def test_branch_name_is_refused(self, repo):
        with pytest.raises(SystemExit, match="symbolic name"):
            recs.dispose(_dispose_args(commit="master"))

    def test_unresolvable_hex_is_refused(self, repo):
        with pytest.raises(SystemExit, match="does not resolve"):
            recs.dispose(_dispose_args(commit="deadbeefdeadbeef"))

    def test_short_sha_is_accepted_and_stored_full(self, repo):
        _tmp, sha, ledger = repo
        recs.dispose(_dispose_args(commit=sha[:8]))
        row = json.loads(ledger.read_text("utf-8"))["recommendations"][0]
        assert row["status"] == "implemented"
        assert row["commit"] == sha, "the FULL sha must be stored, not the abbreviation"


class TestVerifyCitations:
    def _rows(self, sha):
        mk = {"source": "t", "summary": "s", "raised": "2026-08-18T00:00:00+00:00",
              "reason": None, "due": None, "disposed": None}
        return [
            {"id": "R1", "status": "implemented", "commit": sha, **mk},
            {"id": "R2", "status": "implemented", "commit": "HEAD", **mk},
            {"id": "R3", "status": "implemented", "commit": "deadbeefdeadbeef", **mk},
            {"id": "R4", "status": "implemented", "commit": None, **mk},
            {"id": "R5", "status": "open", "commit": None, **mk},
        ]

    def test_three_classes_are_kept_distinct(self, repo):
        _tmp, sha, _ = repo
        v = recs.verify_citations(self._rows(sha))
        assert v["symbolic"] == [("R2", "HEAD")]
        assert v["unresolvable"] == [("R3", "deadbeefdeadbeef")]
        assert v["legacy_uncited"] == 1, "only the IMPLEMENTED uncited row counts"
        assert v["checked"] == v["of"] == 2

    def test_git_failure_reads_unmeasured_not_clean(self, repo, monkeypatch):
        _tmp, sha, _ = repo

        def boom(*a, **k):
            raise OSError("git gone")
        monkeypatch.setattr(recs.subprocess, "run", boom)
        v = recs.verify_citations(self._rows(sha))
        assert v["checked"] == 0 and v["of"] == 2, (
            "a failed batch-check must read UNMEASURED (checked<of), never as zero defects")
        assert v["unresolvable"] == [], "nothing may be GRADED from a run that measured nothing"

    def test_clean_ledger_verifies_clean(self, repo):
        _tmp, sha, _ = repo
        mk = {"source": "t", "summary": "s", "raised": "2026-08-18T00:00:00+00:00",
              "reason": None, "due": None, "disposed": None}
        v = recs.verify_citations([{"id": "R1", "status": "implemented", "commit": sha, **mk}])
        assert not v["symbolic"] and not v["unresolvable"]
        assert v["checked"] == v["of"] == 1
