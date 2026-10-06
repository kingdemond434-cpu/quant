"""The repo as research memory: the journal verifies, rationale keeps human text."""
from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path

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

