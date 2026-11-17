"""LEDGER_APPEND: the Auditor's ADOPT_CLEARS rows reach LIVE by PR, proven by the authority itself.

Level 2 blocker B1 (governance/level2-readiness-and-standing-root-2026-11-17.md). Until now an
agent's lander pushed each Auditor ADOPT row straight to LIVE as a person; the LIVE ruleset would
refuse that. This class lets a rows-only PR through WITHOUT trusting whoever wrote it: every
appended row is recomputed from GitHub and tied to the Auditor's own CLEAR comment.

Conditions (Governance 20:12Z, Auditor 20:17Z and 20:18Z, 2026-11-17), each refusing the WHOLE PR:
  C2  append-only: the base ledger is a byte prefix of the head ledger; every added line is one
      single-line JSON row.
  C3  paths: exactly ADOPT_CLEARS.jsonl modified, plus new files (status "added") named
      reports/audit/<date>/adopt_clear_pr<N>_<sha9>.md / .row.json. Nothing else.
  C8  each row is byte-identical to the .row.json the PR adds for it; its report is the .md the PR
      adds, and report_sha256 is that file's sha256.
  C10 the authority recomputes the row: each path is a file the target PR changes (merge-base..
      the CLEARed commit, both sides of a rename); each object id is that path's blob at the
      CLEARed commit, or null when that commit deletes it. A mismatch or extra path refuses.
  C11 the newest trusted, unedited AUDIT verdict on the target PR for that exact commit is CLEAR
      (a later HOLD on the same commit refuses, whatever happened on other heads).
  C12 a row naming an excluded path (money closure, NEVER_STANDING and root lists, .github/**,
      ops/release/**, seal carriers, box adopt/seal machinery), or a seal-carrier head, is forged
      by definition: the Auditor never issues those.
  C13 one row per (PR, commit): not already in the base ledger, not twice in the PR.
  C9  the PR is opened by the merger App.
  C5  anything unreadable refuses (fail closed).
  C14 ADOPT_CLEARS only. SEAL_CLEARS needs its own recomputation rule and stays out.
Pure: every GitHub read is an injected callable, so each refusal is pinned by a test.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from typing import Any

LEDGER = "desks/mt5/data/ADOPT_CLEARS.jsonl"
SEAL_LEDGER = "desks/mt5/data/SEAL_CLEARS.jsonl"
REPORT_RX = re.compile(
    r"^reports/audit/\d{4}-\d{2}-\d{2}/adopt_clear_pr([1-9]\d*)_([0-9a-f]{9})\.(md|row\.json)$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SEAL_CARRIER_REF = "claude/seal-carrier-"
#: Paths the Auditor never vouches for by ADOPT row (C12), on top of the gate's NEVER_STANDING and
#: ROOT_POLICY lists, which the caller passes in as `excluded`.
EXCLUDED = (
    "ops/money_closure.txt", ".github/*", "ops/release/*", "desks/mt5/data/seal_carriers/*",
    "ops/box/*", "desks/mt5/scripts/adopt*", "desks/mt5/scripts/seal-*",
    "libs/ops/adopt_guard.py", "libs/ops/release*.py", LEDGER, SEAL_LEDGER,
)  # fmt: skip

#: (ok, files) for the target PR at a commit: {path: status} over merge-base..commit, with both
#: sides of a rename, and the PR's head ref; None when unreadable.
Target = Callable[[int, str], "dict[str, Any] | None"]
#: (readable, blob sha or None when the commit has no such path).
BlobAt = Callable[[str, str], "tuple[bool, str | None]"]
#: The gate's verdicts() for a PR, oldest first; None when unreadable.
Verdicts = Callable[[int], "list[dict[str, str]] | None"]


def touches(files: list[str]) -> bool:
    """Does this PR change a CLEAR ledger at all? Then it is LEDGER_APPEND or ROOT, never AUTO."""
    return LEDGER in files or SEAL_LEDGER in files


def _excluded(path: str, extra: tuple[str, ...]) -> bool:
    p = path.lower()
    return any(fnmatch.fnmatchcase(p, x.lower()) for x in (*EXCLUDED, *extra))


def check(
    pr_files: list[Mapping[str, Any]],
    opener: str,
    merger_login: str | None,
    base_ledger: bytes | None,
    head_ledger: bytes | None,
    read_head: Callable[[str], bytes | None],
    target: Target,
    blob_at: BlobAt,
    verdicts: Verdicts,
    excluded: tuple[str, ...] | None,
) -> list[str]:
    """Why this rows-only PR may NOT pass as LEDGER_APPEND; [] when every condition holds."""
    out: list[str] = []
    if excluded is None:
        return ["the NEVER_STANDING / root lists cannot be read (fail closed)"]
    if not merger_login or opener != merger_login:
        out.append(f"opened by {opener or '?'}, not the merger App ({merger_login or 'unknown'})")
    added: set[str] = set()
    seen_ledger = False
    for f in pr_files:
        name, status = str(f.get("filename") or ""), str(f.get("status") or "")
        if f.get("previous_filename"):
            out.append(f"{name}: a rename; only appends and new report files pass")
        elif name == LEDGER and status == "modified":
            seen_ledger = True
        elif name == SEAL_LEDGER:
            out.append("SEAL_CLEARS rows are not LEDGER_APPEND (their own class is not ruled)")
        elif REPORT_RX.match(name) and status == "added":
            added.add(name)
        else:
            out.append(f"{name} ({status}): not a ledger append or a new Auditor report file")
    if not seen_ledger:
        out.append(f"{LEDGER} is not modified")
    if base_ledger is None or head_ledger is None:
        return [*out, "the ledger cannot be read at the base or the head"]
    if not head_ledger.startswith(base_ledger) or (not base_ledger.endswith(b"\n") \
            and base_ledger):
        return [*out, "not append-only: the base ledger is not a byte prefix of the head's"]
    tail = head_ledger[len(base_ledger):]
    if not tail.endswith(b"\n"):
        return [*out, "the appended rows do not end in a newline"]
    lines = tail[:-1].split(b"\n")
    have = {_commit(x) for x in base_ledger.split(b"\n") if x.strip()}
    used: set[str] = set()
    rows: set[str] = set()
    for i, line in enumerate(lines, 1):
        out += [f"row {i}: {w}" for w in _row(line, added, used, rows, have, read_head, target,
                                              blob_at, verdicts, excluded)]
    if added - used:
        out.append(f"report files no row uses: {sorted(added - used)}")
    return out


def _commit(line: bytes) -> str | None:
    try:
        d = json.loads(line)
    except ValueError:
        return None
    return str(d.get("commit")) if isinstance(d, dict) else None


def _row(line: bytes, added: set[str], used: set[str], rows: set[str], have: set[str | None],
         read_head: Callable[[str], bytes | None], target: Target, blob_at: BlobAt,
         verdicts: Verdicts, excluded: tuple[str, ...]) -> list[str]:
    try:
        d = json.loads(line)
    except ValueError:
        return ["not one single-line JSON row"]
    if not isinstance(d, dict) or set(d) != {"commit", "verdict", "report", "report_sha256",
                                             "paths"}:
        return ["not an ADOPT row (commit, verdict, report, report_sha256, paths)"]
    commit, report, paths = str(d["commit"]), str(d["report"]), d["paths"]
    if d["verdict"] != "CLEAR" or not HEX40.match(commit) or not isinstance(paths, dict) \
            or not paths:
        return ["verdict, commit or paths malformed"]
    m = REPORT_RX.match(report)
    if not m or m.group(3) != "md" or m.group(2) != commit[:9]:
        return [f"report {report} is not adopt_clear_pr<N>_{commit[:9]}.md"]
    pr = int(m.group(1))
    twin = report[:-3] + ".row.json"
    out: list[str] = []
    if report not in added or twin not in added:
        out.append(f"the PR does not add both {report} and its .row.json")
    used.update({report, twin})
    if commit in have:
        out.append(f"#{pr} {commit[:9]} already has a row in the base ledger")
    if commit in rows:
        out.append(f"#{pr} {commit[:9]} has two rows in this PR")
    rows.add(commit)
    body, rj = read_head(report), read_head(twin)
    if body is None or rj is None:
        return [*out, "a report file cannot be read at the head"]
    if hashlib.sha256(body).hexdigest() != d["report_sha256"]:
        out.append("report_sha256 is not the sha256 of the report the PR adds")
    if rj.strip() != line.strip():
        out.append("the row is not byte-identical to its .row.json")
    found = verdicts(pr)
    if found is None:
        return [*out, f"#{pr}'s AUDIT verdicts cannot be read"]
    mine = [v for v in found if v.get("sha") == commit]
    if not mine or mine[-1].get("verdict") != "CLEAR":
        out.append(f"the newest AUDIT verdict on #{pr} for {commit[:9]} is not CLEAR")
    t = target(pr, commit)
    if t is None:
        return [*out, f"#{pr}'s changes up to {commit[:9]} cannot be read"]
    if str(t.get("head_ref") or "").lower().startswith(SEAL_CARRIER_REF):
        out.append(f"#{pr} is a seal carrier: never adopted by row")
    changed = t.get("files") or {}
    for p, oid in paths.items():
        if _excluded(str(p), excluded):
            out.append(f"{p}: an excluded path; the Auditor never vouches for it by ADOPT row")
            continue
        if p not in changed:
            out.append(f"{p}: #{pr} does not change it up to {commit[:9]}")
            continue
        ok, blob = blob_at(commit, str(p))
        if not ok:
            out.append(f"{p}: its blob at {commit[:9]} cannot be read")
        elif blob != oid:
            out.append(f"{p}: the row says {oid}, {commit[:9]} has {blob}")
    return out
