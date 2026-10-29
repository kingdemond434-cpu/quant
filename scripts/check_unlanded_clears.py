#!/usr/bin/env python3
"""AN AUDITOR CLEAR THAT NEVER LANDS IS WORK THE DESK PAID FOR AND THREW AWAY (owner rule 23).

    python scripts/check_unlanded_clears.py [--report-only] [--json] [--live REF]

THE DEFECT THIS EXISTS FOR (2026-10-29). Global-data work the auditor cleared on 2026-10-14
(source-fixer-hard-stop 31618ff54, cot-axis cdee27200, cot-zcache-fix 95154ab2f, cot-followups
9702832f0) sat unlanded for fifteen days, and Breadth's two 2026-10-20 clears for nine. Nothing
on the desk named it: a CLEAR lived in a markdown report and a HEADS.txt note, and the only
evidence that it had NOT landed was the absence of a commit, which no fence looks for.

THE GUARD. `context/clear_landing_registry.jsonl` holds one row per auditor-CLEAR item:

    {"id", "sha" (40 hex), "kind": "bundle"|"branch", "path" (bundle, relative to the project
     files share) or "branch", "cleared_at" (ISO-8601 UTC), "report" (the CLEAR file), ...}

Each sha is checked against the LIVE branch: LANDED when it is an ancestor of live, or when every
non-merge commit it carries has an equivalent patch-id on live (`git cherry`). An item unlanded
more than LATE_H hours after `cleared_at` is LATE and the verdict is RED, listing each one. An
item whose commit object is absent from this clone is not in live's history (it cannot be: live
is here and complete), so it reads UNLANDED with its patch-id equivalence UNMEASURED and named.

VERDICTS. GREEN (nothing late), RED (one or more late items, listed), BREACH (the registry is
unreadable or a row is malformed -- fails the push that commits it, report-only or not), and
UNMEASURED with its reason when the live ref is absent or the clone is shallow (L1.28a: a clone
that cannot see live is not evidence that anything landed). With --report-only (the law-gate
registration) RED is printed and exits 0: the remedy for a late CLEAR is a landing, and a gate
that refused every push while one was late would refuse the landing push too.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402

REGISTRY = ROOT / "context" / "clear_landing_registry.jsonl"
LIVE_REF = "refs/remotes/origin/claude/llm-auto-upgrade-verify-gcjac3"
#: Hours a CLEAR may wait for its landing before it is LATE.
LATE_H = 12.0
KINDS = ("bundle", "branch")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=120)


def _when(stamp: object) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at.astimezone(UTC) if at.tzinfo else None


def read_registry(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Rows and the problems with them; an unreadable file is one problem."""
    try:
        text = path.read_text("utf-8")
    except OSError as exc:
        return [], [f"registry unreadable: {exc}"]
    rows: list[dict[str, Any]] = []
    bad: list[str] = []
    seen: set[str] = set()
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            bad.append(f"line {n}: not JSON")
            continue
        if not isinstance(row, dict):
            bad.append(f"line {n}: not an object")
            continue
        why = []
        if not str(row.get("id") or "").strip():
            why.append("no id")
        elif row["id"] in seen:
            why.append(f"duplicate id {row['id']}")
        if not _SHA.match(str(row.get("sha") or "")):
            why.append("sha is not 40 lowercase hex")
        if row.get("kind") not in KINDS:
            why.append(f"kind not in {KINDS}")
        elif not str(row.get("path" if row["kind"] == "bundle" else "branch") or "").strip():
            why.append("bundle row without path" if row["kind"] == "bundle"
                       else "branch row without branch")
        if _when(row.get("cleared_at")) is None:
            why.append("cleared_at is not a zoned ISO-8601 time")
        if not str(row.get("report") or "").strip():
            why.append("no report cited")
        if why:
            bad.append(f"line {n}: " + "; ".join(why))
            continue
        seen.add(row["id"])
        rows.append(row)
    return rows, bad


def landing(repo: Path, sha: str, live: str) -> tuple[str, str]:
    """(state, how) for one sha against live: LANDED, LANDED_BY_PATCH_ID or UNLANDED."""
    if _git(repo, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        return "UNLANDED", ("commit object absent from this clone, so not in live's history; "
                            "patch-id equivalence UNMEASURED (fetch its bundle to measure)")
    anc = _git(repo, "merge-base", "--is-ancestor", sha, live)
    if anc.returncode == 0:
        return "LANDED", "ancestor of live"
    if anc.returncode != 1:
        return "UNLANDED", f"ancestry unreadable: {(anc.stderr or '').strip()[:160]}"
    cherry = _git(repo, "cherry", live, sha)
    marks = [ln[:1] for ln in cherry.stdout.splitlines() if ln.strip()]
    if cherry.returncode == 0 and marks and all(m == "-" for m in marks):
        return "LANDED_BY_PATCH_ID", f"all {len(marks)} commit(s) have an equivalent on live"
    ahead = sum(1 for m in marks if m == "+")
    return "UNLANDED", f"{ahead} commit(s) with no equivalent patch on live"


def judge(*, repo: Path = ROOT, registry: Path = REGISTRY, live: str = LIVE_REF,
          now: datetime | None = None, late_h: float = LATE_H) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    rows, bad = read_registry(registry)
    base: dict[str, Any] = {"generated_utc": at.isoformat(timespec="seconds"), "live": live,
                            "registry": str(registry), "late_h": late_h}
    if bad:
        return {**base, "verdict": "BREACH", "why": f"{len(bad)} malformed row(s)",
                "malformed": bad}
    if _git(repo, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        return {**base, "verdict": "UNMEASURED",
                "why": "shallow clone: ancestry against live cannot be proved"}
    if _git(repo, "rev-parse", "--verify", "--quiet", f"{live}^{{commit}}").returncode != 0:
        return {**base, "verdict": "UNMEASURED",
                "why": f"live ref {live} is not in this clone: nothing can be proved landed"}
    items, late = [], []
    for row in rows:
        state, how = landing(repo, row["sha"], live)
        cleared = _when(row["cleared_at"])
        assert cleared is not None  # validated in read_registry
        age_h = round((at - cleared).total_seconds() / 3600.0, 1)
        if state == "UNLANDED":
            state = "LATE" if age_h > late_h else "PENDING"
        item = {"id": row["id"], "sha": row["sha"][:9], "kind": row["kind"],
                "where": row.get("path") or row.get("branch"), "cleared_at": row["cleared_at"],
                "age_h": age_h, "state": state, "how": how, "report": row["report"]}
        items.append(item)
        if state == "LATE":
            late.append(item)
    verdict = "RED" if late else "GREEN"
    why = (f"{len(late)} CLEAR item(s) unlanded more than {late_h:g}h after clearing: "
           + ", ".join(f"{i['id']} ({i['age_h']:g}h)" for i in late)) if late else (
           f"{len(items)} CLEAR item(s), none late")
    return {**base, "verdict": verdict, "why": why, "items": items,
            "late": [i["id"] for i in late]}


def render(doc: dict[str, Any]) -> list[str]:
    lines = [f"unlanded clears: {doc['verdict']} -- {doc['why']}"]
    for bad in doc.get("malformed") or ():
        lines.append(f"  MALFORMED {bad}")
    for i in doc.get("items") or ():
        lines.append(f"  {i['state']:<18} {i['id']} {i['sha']} cleared {i['cleared_at']} "
                     f"({i['age_h']:g}h) -- {i['how']} [{i['report']}]")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--report-only", action="store_true",
                    help="print RED without failing on it (a malformed registry still fails)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--live", default=LIVE_REF)
    ap.add_argument("--registry", default=str(REGISTRY))
    a = ap.parse_args(argv)
    doc = judge(registry=Path(a.registry), live=a.live)
    print(json.dumps(doc, indent=1) if a.json else "\n".join(render(doc)))
    # Name the passing set (R0237). RED passes only under --report-only, never BREACH.
    passing = {"GREEN", "UNMEASURED"} | ({"RED"} if a.report_only else set())
    return fence_exit(doc["verdict"], passing, fail=1)


if __name__ == "__main__":
    sys.exit(main())
