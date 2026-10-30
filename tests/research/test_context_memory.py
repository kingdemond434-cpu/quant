"""The repo as research memory: the journal verifies, rationale keeps human text."""
from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CTX = runpy.run_path(str(ROOT / "scripts" / "context.py"))


def test_the_committed_journal_verifies():
    ok, problems = CTX["verify"]()
    assert ok, problems


def test_verify_catches_missing_evidence_and_bad_rows(tmp_path):
    j = tmp_path / "j.jsonl"
    j.write_text(json.dumps({"id": "D-1", "at": "x", "title": "t", "decision": "d", "why": "w",
                             "by": "b", "evidence": ["no/such/file.py"]}) + "\nnot json\n")
    ok, problems = CTX["verify"](j)
    assert not ok
    assert any("does not exist" in p for p in problems)
    assert any("line 2" in p for p in problems)


def test_decide_appends_with_sequential_ids(tmp_path):
    j = tmp_path / "j.jsonl"
    a = argparse.Namespace(title="t", decision="d", why="w", by="me", owner="", evidence=[],
                           supersedes="")
    r1, r2 = CTX["decide"](a, j), CTX["decide"](a, j)
    assert r1["id"].endswith("-001") and r2["id"].endswith("-002")


def test_recovered_journal_gaps_never_reuse_a_receipt_id(tmp_path):
    day = CTX["datetime"].now(CTX["UTC"]).strftime("%Y%m%d")
    rows = [{"id": f"D-{day}-001"}, {"id": f"D-{day}-018"},
            {"id": f"D-{day}-019"}, {"id": "D-19990101-999"},
            {"id": f"D-{day}-malformed"}]
    j = tmp_path / "recovered.jsonl"
    original = "".join(json.dumps(row) + "\n" for row in rows)
    j.write_text(original, encoding="utf-8")
    a = argparse.Namespace(title="t", decision="d", why="w", by="me", owner="",
                           evidence=[], supersedes="")
    first, second = CTX["decide"](a, j), CTX["decide"](a, j)
    assert first["id"] == f"D-{day}-020"
    assert second["id"] == f"D-{day}-021"
    assert j.read_text(encoding="utf-8").startswith(original)


def test_ids_are_minted_past_the_fetched_live_copy_too(tmp_path):
    """The box's file ended at 002 while LIVE carried 003 (2026-10-29 23:01Z): the next id must
    clear both and every open PR branch, or two hosts give two decisions one identity."""
    import subprocess
    day = CTX["datetime"].now(CTX["UTC"]).strftime("%Y%m%d")
    j = tmp_path / "decision_journal.jsonl"

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q")
    rows = [{"id": f"D-{day}-00{n}"} for n in (1, 2, 3)]
    j.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    git("add", j.name)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "live")
    git("update-ref", f"refs/remotes/origin/{CTX['LIVE']}", "HEAD")
    # an open PR branch already holds 004 and 005: they reach LIVE when it merges
    j.write_text("".join(json.dumps({"id": f"D-{day}-00{n}"}) + "\n" for n in (4, 5)),
                 encoding="utf-8")
    git("add", j.name)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "pr")
    git("update-ref", "refs/remotes/origin/claude/some-pr", "HEAD")
    git("update-ref", "refs/heads/claude/local-pr", "HEAD")
    git("checkout", "-q", "--orphan", "box")
    j.write_text("".join(json.dumps(r) + "\n" for r in rows[:2]), encoding="utf-8")
    a = argparse.Namespace(title="t", decision="d", why="w", by="me", owner="",
                           evidence=[], supersedes="")
    assert CTX["decide"](a, j)["id"] == f"D-{day}-006"


def test_rationale_sync_refreshes_generated_block_and_keeps_human_text(tmp_path):
    s = tmp_path / "sleeves.json"
    out = tmp_path / "sleeves"
    s.write_text(json.dumps({"sleeves": [{"name": "X_carry", "status": "LIVE", "family": "carry",
                                          "risk_frac": 0.01}]}))
    CTX["rationale_sync"](s, out)
    p = out / "X_carry.md"
    text = p.read_text().replace("## Kill criterion (the falsifier that retires it)\n\nUNWRITTEN",
                                 "## Kill criterion (the falsifier that retires it)\n\nswap flips")
    p.write_text(text)
    s.write_text(json.dumps({"sleeves": [{"name": "X_carry", "status": "LIVE", "family": "carry",
                                          "risk_frac": 0.02}]}))
    CTX["rationale_sync"](s, out)
    new = p.read_text()
    assert "swap flips" in new and "| risk_frac | 0.02 |" in new and "0.01" not in new


def test_coverage_is_read_only(tmp_path):
    s = tmp_path / "sleeves.json"
    s.write_text(json.dumps({"sleeves": [{"name": "Y", "status": "LIVE"}]}))
    out = tmp_path / "none"
    cov = CTX["coverage"](s, out)
    assert cov["missing_file"] == ["Y"] and not out.exists()



def test_portable_archive_requires_exact_digest_and_confined_path(tmp_path, monkeypatch):
    import hashlib
    env = CTX["_check_pointer"].__globals__
    monkeypatch.setitem(env, "ROOT", tmp_path)
    (tmp_path / "context").mkdir()
    archive = tmp_path / "docs/cro/evidence/receipt.json"
    archive.parent.mkdir(parents=True)
    archive.write_text('{"tests": 33}')
    pointer = "C:/original/receipt.json"
    index = {pointer: {"path": "docs/cro/evidence/receipt.json",
                       "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}}
    registry = tmp_path / "context/evidence_archives.json"
    registry.write_text(json.dumps(index))
    assert CTX["_check_pointer"](pointer) == "OK"
    archive.write_text('{"tests": 34}')
    assert CTX["_check_pointer"](pointer) == "MISSING"
    index[pointer]["path"] = "context/evidence_archives.json"
    registry.write_text(json.dumps(index))
    assert CTX["_check_pointer"](pointer) == "MISSING"
    assert CTX["_check_pointer"]("C:/unknown/receipt.json") == "MISSING"


def test_decide_refuses_an_evidence_pointer_that_cannot_resolve(tmp_path):
    j = tmp_path / "j.jsonl"
    a = argparse.Namespace(title="t", decision="d", why="w", by="me", owner="",
                           evidence=["PR #999999"], supersedes="")
    with pytest.raises(SystemExit):
        CTX["decide"](a, j)
    assert not j.exists()
    a.evidence = ["pr:999999"]
    assert CTX["decide"](a, j)["evidence"] == ["pr:999999"]
