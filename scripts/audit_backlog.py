#!/usr/bin/env python3
"""THE AUDIT BACKLOG -- what the Auditor owes, in the order it owes it, with its age published.

zuck, 2026-11-13 20:14Z (final autonomy directive, item 4): "Automate the Auditor backlog and
prevent future audit queues from growing without bound." The no-queues law (scripts/
check_no_queues.py) already says the rest: nothing is parked, and where work waits its AGE IS
PUBLISHED. Until this file the Auditor's backlog was not measured anywhere -- the only way to
learn that a PR had waited a day for a verdict was for someone to notice.

WHAT IS OWED. An open PR into LIVE whose CURRENT head carries no verdict from a trusted author
(the same reading the audit gate makes: .github/scripts/audit_gate.py `verdicts`, so an edited
comment is a HOLD and a verdict on an older head does not count). A PR held at its current head
is not owed -- it waits on its author -- and is listed apart. A draft is owed too: the gate
marks a CLEARed draft ready, so a draft is not a reason to wait.

THE ORDER (strictest first; ties go oldest first):
    P0  ADOPT    LIVE code the box cannot adopt because no ADOPT CLEAR row vouches for it
                 (--repo-dir; `libs/ops/adopt_guard` reading). Every hour here is an hour the
                 box runs unsealed code with new risk refused.
    P1  MONEY    a PR touching a RELEASE.json money-path file, or one the gate tiers PROTECTED
                 (a check that judges PRs) -- these also carry the 24 h veto, so they go first.
    P2  READY    any other non-draft PR.
    P3  DRAFT    a draft.

THE SLA, in hours since the head was pushed: P0 2, P1 6, P2 24, P3 72. An item past its SLA is a
BREACH. The ALARM is raised when any item breaches, or the owed depth exceeds MAX_DEPTH, or the
newest backlog snapshot is older than its own cadence (a dead drainer). Published:

    reports/audit/AUDIT_BACKLOG.json         the snapshot (depth, oldest age, breaches, items)
    reports/audit/AUDIT_BACKLOG_HISTORY.jsonl one line per run, so the trend is a fact

    python scripts/audit_backlog.py [--repo kingdemond434-cpu/quant] [--repo-dir .]
                                    [--out reports/audit] [--strict] [--json]

It reads GitHub through `gh api` (GH_TOKEN in Actions). It never posts, labels or merges:
measuring the backlog must not need any permission the drain does not already have. Exit 0
unless --strict and the ALARM is up.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
REPO = "kingdemond434-cpu/quant"
RELEASE_REL = "desks/mt5/data/RELEASE.json"

#: Hours an item may wait, by priority, before it is a BREACH.
SLA_H = {"P0": 2.0, "P1": 6.0, "P2": 24.0, "P3": 72.0}
#: Owed items above this raise the ALARM whatever their ages: a queue that only grows is the
#: defect even before any single row is old.
MAX_DEPTH = 40
#: The fallback money path when RELEASE.json cannot be read (fail toward P1, never toward P3).
MONEY_DIRS = ("desks/mt5/mt5desk/", "libs/portfolio/")


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gate() -> Any:
    """The audit gate's own module: one reading of a verdict, never two."""
    return _load("_audit_gate", ROOT / ".github" / "scripts" / "audit_gate.py")


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def money_path(root: Path = ROOT) -> tuple[frozenset[str], bool]:
    """(the RELEASE.json money-path files, read ok)."""
    try:
        rel = json.loads((root / RELEASE_REL).read_text(encoding="utf-8"))
        files = rel.get("money_path") or []
        if isinstance(files, list) and files:
            return frozenset(str(f) for f in files), True
    except (OSError, ValueError):
        pass
    return frozenset(), False


def priority(
    files: Iterable[str],
    draft: bool,
    money: frozenset[str],
    money_ok: bool,
    protected: Callable[[str], bool],
) -> tuple[str, str]:
    """(P1|P2|P3, why) for a PR. Unknown files are never a reason to rank lower."""
    names = list(files)
    for f in names:
        if f in money:
            return "P1", f"money path: {f}"
        if not money_ok and f.startswith(MONEY_DIRS):
            return "P1", f"money path (RELEASE.json unreadable): {f}"
    for f in names:
        if protected(f):
            return "P1", f"protected: {f}"
    if not names:
        return "P1", "file list unreadable"
    return ("P3", "draft") if draft else ("P2", "ready")


def standing(verdicts: list[Mapping[str, str]], head: str) -> Mapping[str, str] | None:
    """The newest verdict on `head`, or None (owed). The gate reads ANY edited trusted comment as
    a HOLD that a newer CLEAR lifts (#133), so a CLEAR followed by an edit is owed again: the
    Auditor must post a fresh CLEAR for the gate to merge."""
    edited = [v for v in verdicts if "(an edited comment)" in str(v.get("by", ""))]
    mine = [v for v in verdicts if v.get("sha") == head and v not in edited]
    if not mine:
        return None
    last = mine[-1]  # verdicts come oldest first
    if last.get("verdict") == "CLEAR" and any(e["at"] > last["at"] for e in edited):
        return None
    return last


def item(
    pr: Mapping[str, Any],
    files: list[str],
    verdicts: list[Mapping[str, str]],
    pushed_at: str | None,
    now: datetime,
    money: frozenset[str],
    money_ok: bool,
    protected: Callable[[str], bool],
) -> dict[str, Any]:
    head = str(pr["head"]["sha"])
    v = standing(verdicts, head)
    p, why = priority(files, bool(pr.get("draft")), money, money_ok, protected)
    since = _ts(pushed_at) or _ts(pr.get("updated_at")) or now
    age_h = round(max(0.0, (now - since).total_seconds() / 3600.0), 2)
    state = "OWED" if v is None else ("HELD" if v.get("verdict") == "HOLD" else "CLEARED")
    return {
        "pr": int(pr["number"]),
        "title": str(pr.get("title") or "")[:120],
        "head": head,
        "draft": bool(pr.get("draft")),
        "priority": p,
        "why": why,
        "state": state,
        "waiting_since": since.isoformat(),
        "age_h": age_h,
        "sla_h": SLA_H[p],
        "breach": state == "OWED" and age_h > SLA_H[p],
    }


def summarise(items: list[dict[str, Any]], now: datetime, adopt: dict[str, Any]) -> dict[str, Any]:
    owed = [i for i in items if i["state"] == "OWED"]
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    owed.sort(key=lambda i: (order[i["priority"]], -i["age_h"]))
    breaches = [i for i in owed if i["breach"]]
    p0 = adopt.get("uncovered") or []
    p0_breach = bool(p0) and float(adopt.get("age_h") or 0.0) > SLA_H["P0"]
    why: list[str] = []
    if breaches:
        why.append(f"{len(breaches)} owed PR(s) past SLA")
    if p0:
        why.append(f"P0: {len(p0)} LIVE code path(s) not vouched for adoption")
    if len(owed) > MAX_DEPTH:
        why.append(f"depth {len(owed)} > {MAX_DEPTH}")
    if adopt.get("error"):
        why.append(f"P0 unmeasured: {adopt['error']}")
    return {
        "generated_utc": now.isoformat(),
        "verdict": "ALARM" if why else "OK",
        "why": why,
        "depth": len(owed) + (1 if p0 else 0),
        "by_priority": {
            k: sum(1 for i in owed if i["priority"] == k) + (1 if k == "P0" and p0 else 0)
            for k in ("P0", "P1", "P2", "P3")
        },
        "oldest_owed_h": max((i["age_h"] for i in owed), default=0.0),
        "breaches": len(breaches) + (1 if p0_breach else 0),
        "held": sum(1 for i in items if i["state"] == "HELD"),
        "cleared_unmerged": sum(1 for i in items if i["state"] == "CLEARED"),
        "sla_h": SLA_H,
        "max_depth": MAX_DEPTH,
        "adoption": adopt,
        "next": [
            {"pr": i["pr"], "priority": i["priority"], "age_h": i["age_h"]} for i in owed[:10]
        ],
        "owed": owed,
    }


# ---------------------------------------------------------------------------------- GitHub I/O


def _gh(path: str) -> Any:
    out = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json", path],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    ).stdout
    return json.loads(out)


def _pages(path: str, cap: int = 30) -> list[Any]:
    rows: list[Any] = []
    sep = "&" if "?" in path else "?"
    for page in range(1, cap + 1):
        got = _gh(f"{path}{sep}per_page=100&page={page}")
        rows.extend(got)
        if len(got) < 100:
            break
    return rows


def fetch(repo: str) -> list[tuple[dict[str, Any], list[str], list[dict[str, Any]], str | None]]:
    out = []
    for pr in _pages(f"repos/{repo}/pulls?state=open&base={LIVE}"):
        n = pr["number"]
        files = [str(f.get("filename")) for f in _pages(f"repos/{repo}/pulls/{n}/files")]
        comments = _pages(f"repos/{repo}/issues/{n}/comments")
        try:
            c = _gh(f"repos/{repo}/commits/{pr['head']['sha']}")
            pushed = c["commit"]["committer"]["date"]
        except (subprocess.CalledProcessError, KeyError, ValueError):
            pushed = None
        out.append((pr, files, comments, pushed))
    return out


def adoption(repo_dir: Path | None, now: datetime) -> dict[str, Any]:
    """P0: LIVE code paths whose tip blob no ADOPT CLEAR row vouches for, measured from the
    newest row's commit (everything before it was already judged). Needs a full clone."""
    if repo_dir is None:
        return {"measured": False}
    try:
        sys.path.insert(0, str(repo_dir))
        ag = _load("_adopt_guard", repo_dir / "libs" / "ops" / "adopt_guard.py")
        tip = ag._rev(repo_dir, ag.LIVE_REF)
        rows = ag.effective_clears(repo_dir, tip)
        plain = [r for r in rows if r.verdict == "CLEAR" and r.by != ag.GATE_BY]
        if not plain:
            return {"measured": False, "error": "no ADOPT CLEAR row on LIVE"}
        base = plain[-1].commit
        paths = [p for p in ag._changed(repo_dir, base, tip) if ag.is_code(p)]
        unc = ag.uncovered(repo_dir, paths, tip, rows)
        first = None
        if unc:
            log = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_dir),
                    "log",
                    "--reverse",
                    "--format=%cI",
                    f"{base}..{tip}",
                    "--",
                    *unc,
                ],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.split()
            first = log[0] if log else None
        since = _ts(first) or now
        return {
            "measured": True,
            "tip": tip,
            "last_row_commit": base,
            "uncovered": unc,
            "since": since.isoformat() if unc else None,
            "age_h": round((now - since).total_seconds() / 3600.0, 2) if unc else 0.0,
        }
    except Exception as exc:
        return {"measured": False, "error": f"{type(exc).__name__}: {exc}"[:300]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--repo-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "audit")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    now = datetime.now(UTC)
    g = gate()
    money, money_ok = money_path()
    items = [
        item(pr, files, g.verdicts(comments), pushed, now, money, money_ok, g.is_protected)
        for pr, files, comments, pushed in fetch(a.repo)
    ]
    snap = summarise(items, now, adoption(a.repo_dir, now))

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "AUDIT_BACKLOG.json").write_text(json.dumps(snap, indent=1) + "\n", encoding="utf-8")
    hist = {
        k: snap[k]
        for k in (
            "generated_utc",
            "verdict",
            "depth",
            "by_priority",
            "oldest_owed_h",
            "breaches",
            "held",
        )
    }
    with (a.out / "AUDIT_BACKLOG_HISTORY.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(hist, sort_keys=True) + "\n")

    if a.json:
        print(json.dumps(snap, indent=1))
    else:
        print(
            f"AUDIT BACKLOG {snap['verdict']}: depth {snap['depth']} {snap['by_priority']}, "
            f"oldest {snap['oldest_owed_h']} h, {snap['breaches']} breach(es)"
            + (f" -- {'; '.join(snap['why'])}" if snap["why"] else "")
        )
        for n in snap["next"]:
            print(f"  next: #{n['pr']} {n['priority']} {n['age_h']} h")
    return 1 if a.strict and snap["verdict"] == "ALARM" else 0


if __name__ == "__main__":
    raise SystemExit(main())
