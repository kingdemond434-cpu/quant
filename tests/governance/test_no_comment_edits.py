"""NO CODE HERE EDITS A GITHUB COMMENT (Governance, 2026-11-05).

audit_gate.py's #445 rule counts ANY edited trusted comment as an AUDIT HOLD at the time of its
edit, because REST shows only a comment's latest body and an edit can hide a HOLD. That HOLD is
absolute: the release authority's own CLEAR cannot lift it (facts() sets the hold, decide() then
returns HOLD), and deleting the comment would defeat the guard. Two PRs (#674, #534) were held this
way by harmless edits. So every helper in this tree only ever POSTS a new comment; this fence
fails on any call that would PATCH an issue, pull-request or commit comment.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()

ENDPOINT = re.compile(r"(?:issues|pulls|commits)/(?:\{?[\w.$]*\}?/)?comments/")
PATCH = re.compile(r"""(?i)(?:-X\s*["']?PATCH|method\s*=\s*["']PATCH|["']PATCH["']|Invoke-RestMethod[^\n]*-Method\s+Patch)""")
EDIT_CALLS = re.compile(r"\b(?:update_issue_comment|update_pull_request_comment|edit_comment|"
                        r"update_review_comment)\b")
SUFFIXES = {".py", ".ps1", ".psm1", ".sh", ".yml", ".yaml", ".cmd", ".js", ".ts"}


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0")
            if p and Path(p).suffix.lower() in SUFFIXES and p != SELF]


def offenders(paths: list[str], read=lambda p: (ROOT / p).read_text("utf-8", "replace")) -> list[str]:
    bad: list[str] = []
    for p in paths:
        try:
            text = read(p)
        except OSError:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            window = " ".join(lines[max(0, i - 3): i + 4])  # a call split across a few lines
            if EDIT_CALLS.search(line) or (ENDPOINT.search(line) and PATCH.search(window)):
                bad.append(f"{p}:{i + 1}: {line.strip()[:160]}")
    return bad


def test_no_tracked_code_edits_a_github_comment() -> None:
    bad = offenders(_tracked())
    assert not bad, "post a new comment instead of editing one (an edit is an AUDIT HOLD):\n" + "\n".join(bad)


def test_the_fence_catches_each_edit_shape() -> None:
    samples = {
        "a.py": 'gh("repos/o/r/issues/comments/123", "-X", "PATCH", "-f", "body=x")',
        "b.ps1": "& gh api -X PATCH repos/$Repo/issues/comments/$id -f body=$b",
        "c.py": "requests.request(method='PATCH', url=f'{api}/repos/{repo}/pulls/comments/{cid}')",
        "d.py": "client.update_issue_comment(owner, repo, comment_id, body)",
        "e.ps1": "Invoke-RestMethod -Uri \"$api/repos/$r/issues/comments/$c\" -Method Patch -Body $j",
    }
    assert len(offenders(list(samples), read=samples.__getitem__)) == len(samples)


def test_posting_a_new_comment_passes() -> None:
    samples = {
        "ok.py": 'gh(f"repos/{repo}/issues/{pr}/comments", "-X", "POST", "-f", f"body={b}")',
        "ok2.ps1": "& gh api repos/$Repo/issues/$Pr/comments -f body=$b",
        "ok3.py": 'gh(f"repos/{repo}/issues/{pr}/comments?per_page=100", "--paginate")',
    }
    assert offenders(list(samples), read=samples.__getitem__) == []
