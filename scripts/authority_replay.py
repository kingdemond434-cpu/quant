"""REPLAY THE OPEN-PR BACKLOG THROUGH THE RELEASE AUTHORITY -- a dry run that signs nothing.

    python scripts/authority_replay.py --repo OWNER/NAME                # incremental, writes report
    python scripts/authority_replay.py --repo OWNER/NAME --all --print  # every open PR, stdout

Writes desks/mt5/reports/AUTHORITY_REPLAY.json (box state, published with the box's state commits).

WHY (zuck, 2026-11-03): "replay the open-PR backlog through the new authority". The release
authority (ops/release/authority/) decides each PR from facts it gathers itself -- class (ROOT /
CONTROLLER / AUTO / LOW / REFUSED), the required checks' provenance, an Auditor HOLD, freshness --
but it only ever judged the PR in front of it, one pass at a time, and wrote nothing a person or a
thread could read across the whole backlog. So "which of the ~100 open PRs could land with no owner
act, and what exactly holds each of the rest?" had no answer short of the Auditor adjudicating one
by one (the 11-03..11-13 state of this row).

WHAT IT DOES. For each open PR into LIVE it calls the authority's OWN `facts()` and the policy's OWN
`decide()` -- the very functions that sign attestations, imported from this checkout, not copied --
and records:

    verdict          CLEAR / HOLD / FAIL / WAIT, exactly what the authority would conclude now
    class            ROOT / CONTROLLER / AUTO / LOW / REFUSED as the authority classifies it today
    class_if_level2  the class once GitHub enforces the authority's status (Level 2:
                     `enforced_root_files` -- workflow_gate.ps1 and the merger -- drop to CONTROLLER)
    blocker          one word for what holds it (below), and `next` -- who acts next
    reasons          the authority's own words

    blocker          meaning                                         next
    ROOT             a root file: never auto-cleared                 zuck: root_merge.ps1 -Pr N
    REFUSED          a secrets path: never merged                    close it
    AUDIT_HOLD       a trusted AUDIT HOLD stands                     PR owner fixes, Auditor re-audits
    CHECK_FAILED     a required check failed on the exact head       PR owner fixes or re-runs
    REVIEW_QUEUED    independent-review had no free reviewer         reviewer capacity (no person)
    CHECKS_PENDING   required checks not finished                    CI queue (no person)
    BEHIND           not up to date with LIVE                        PR owner merges LIVE in
    DEACTIVATED      merges are switched off                         whoever switched them off
    READY            CLEAR: every required check passed              the gate merges it (no person)
    NOT_ELIGIBLE     not an open same-repo PR into LIVE              none
    UNREADABLE       a read failed this pass (never a pass)          next replay pass

and the totals: how many are READY now, how many would need no owner act after Level 2 (class
not ROOT/REFUSED), how many need zuck (ROOT), and per blocker.

INCREMENTAL. Judging one PR costs ~10 s and ~15 GitHub reads, so a pass judges at most
`--max-prs` (default 15) within `--budget-s` (default 180 s): PRs never judged or whose head moved
first, then the least recently judged. Rows for PRs no longer open are dropped. The whole backlog
is refreshed every few passes; each row carries its own `judged_at` and `head`, so a stale row is
visible as stale. Run hourly from scripts/merge_pipeline_watch.py (Quant-WorkflowGate), so it adds
no scheduled task.

PUBLISHED WITHOUT FREE TEXT. The repository is public, so the report carries per PR only enums,
numbers, shas and times (ROW_KEYS): no PR title, no reasons, no error text (an error is its type
and HTTP code). The authority's own words for each PR go to root data/authority_replay_full.json
(gitignored), on the box, which is also where the incremental state is kept.

WHAT IT NEVER DOES. It never signs or writes an attestation, never posts a commit status, never
comments, merges, labels or re-runs: `issue()`, `write()` and `post_status()` are not called, and a
test fails if they are. Its only GitHub calls are the authority's own reads; its only local effect
besides its report is `git fetch` of PR heads (objects only, no checkout), which `facts()` does.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
AUTHORITY = ROOT / "ops" / "release" / "authority" / "authority.py"
REPORT = ROOT / "desks" / "mt5" / "reports" / "AUTHORITY_REPLAY.json"
#: The rows WITH the authority's own words (reasons name files, HOLD shas, errors) stay on the box:
#: root data/ is gitignored. The published report carries no free text (the repo is public).
LOCAL = ROOT / "data" / "authority_replay_full.json"
ROW_KEYS = (
    "pr",
    "judged_at",
    "head",
    "verdict",
    "cls",
    "class_if_level2",
    "gate_tier",
    "blocker",
    "next",
    "n_files",
    "error",
)
MAX_PRS = 15
BUDGET_S = 180.0

NEXT = {
    "ROOT": "zuck: root_merge.ps1 -Pr {pr} (root files are never auto-cleared)",
    "REFUSED": "close it: a secrets path never merges",
    "AUDIT_HOLD": "PR owner fixes the HOLD; Auditor re-audits the new head",
    "CHECK_FAILED": "PR owner fixes the failing check (or re-runs a flake)",
    "REVIEW_QUEUED": "independent-review capacity (no person)",
    "CHECKS_PENDING": "CI queue (no person)",
    "BEHIND": "PR owner merges LIVE into the branch",
    "DEACTIVATED": "whoever posted DEACTIVATE lifts it",
    "READY": "the gate merges it (no person)",
    "NOT_ELIGIBLE": "none",
    "UNREADABLE": "next replay pass",
}


def load_authority(path: Path = AUTHORITY) -> ModuleType:
    """The authority module from THIS checkout (it loads its policy and the gate the same way)."""
    spec = importlib.util.spec_from_file_location("authority_replay_target", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["authority_replay_target"] = mod
    spec.loader.exec_module(mod)
    return mod


def blocker(f: Mapping[str, Any], verdict: str, reasons: list[str]) -> str:
    """One word for what holds the PR, read off the same facts decide() used."""
    if verdict == "CLEAR":
        return "READY"
    if not (f.get("open") and f.get("same_repo") and f.get("base_ok")):
        return "NOT_ELIGIBLE"
    cls = f.get("cls")
    if cls in ("ROOT", "REFUSED"):
        return str(cls)
    if f.get("hold"):
        return "AUDIT_HOLD"
    if f.get("deactivated"):
        return "DEACTIVATED"
    if verdict == "FAIL":
        return "CHECK_FAILED"
    text = " ".join(reasons)
    if "independent-review queued" in text:
        return "REVIEW_QUEUED"
    if "not up to date" in text:
        return "BEHIND"
    if verdict == "WAIT":
        return "CHECKS_PENDING"
    return "UNREADABLE"


def judge(
    auth: ModuleType,
    ag: Any,
    policy: dict[str, Any],
    repo: str,
    pr: int,
    base: str,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """One PR through the authority's own facts() and decide(); never raises."""
    row: dict[str, Any] = {"pr": pr, "judged_at": now().isoformat(timespec="seconds")}
    try:
        f = auth.facts(ag, repo, pr, base, policy, enforced=False)
        verdict, reasons = auth.pol.decide(f)
    except Exception as exc:  # a read failed: recorded, never a pass
        m = re.search(r"HTTP (\d{3})", str(exc))
        row.update(
            verdict="UNREADABLE",
            blocker="UNREADABLE",
            error={"type": type(exc).__name__, "http": int(m.group(1)) if m else None},
            reasons=[str(exc)[:300]],  # local only: publishable() drops it
        )
        row["next"] = NEXT["UNREADABLE"]
        return row
    cls = f.get("cls")
    cls2 = cls
    names = f.get("files")
    if names and f.get("tier") and cls not in (None, "REFUSED"):
        try:
            read = auth._git_bytes

            def reader(rev: str) -> Callable[[str], str | None]:
                def r(n: str) -> str | None:
                    b = read("show", f"{rev}:{n}")
                    return b.decode("utf-8", "replace") if b is not None else None

                return r

            cls2, _ = auth.pol.classify(
                names, f["tier"], policy, reader(f"origin/{base}"), reader(f["head"]), enforced=True
            )
        except Exception:  # the what-if is best effort; the live class stands
            cls2 = cls
    b = blocker(f, verdict, list(reasons))
    row.update(
        head=str(f.get("head") or "")[:40],
        verdict=verdict,
        cls=cls,
        class_if_level2=cls2,
        gate_tier=f.get("tier"),
        blocker=b,
        next=NEXT[b].format(pr=pr),
        reasons=[str(x)[:240] for x in reasons][:6],
        n_files=len(names or []),
    )
    return row


def order(
    open_prs: Sequence[Mapping[str, Any]], prev: Mapping[int, Mapping[str, Any]]
) -> list[int]:
    """Never judged or head moved first (oldest PR first), then least recently judged."""
    fresh: list[tuple[int, int]] = []
    stale: list[tuple[str, int]] = []
    for p in open_prs:
        n = int(p["number"])
        old = prev.get(n)
        if (
            old is None
            or str(old.get("head") or "") != str(p["head"]["sha"])
            or old.get("verdict") == "UNREADABLE"
        ):
            fresh.append((n, n))
        else:
            stale.append((str(old.get("judged_at") or ""), n))
    return [n for _, n in sorted(fresh)] + [n for _, n in sorted(stale)]


def publishable(row: Mapping[str, Any]) -> dict[str, Any]:
    """A row as published: enums, numbers, shas and times only -- no reasons, title or error
    text (the authority's words stay in LOCAL on the box)."""
    return {k: row.get(k) for k in ROW_KEYS}


def summarise(rows: Sequence[Mapping[str, Any]], open_n: int) -> dict[str, Any]:
    judged = [r for r in rows if r.get("verdict") != "UNREADABLE"]
    need_zuck = [r["pr"] for r in rows if r.get("blocker") == "ROOT"]
    l2_free = [
        r["pr"]
        for r in judged
        if r.get("class_if_level2") not in ("ROOT", "REFUSED")
        and r.get("blocker") != "NOT_ELIGIBLE"
    ]
    return {
        "open_prs": open_n,
        "judged": len(rows),
        "coverage": round(len(rows) / open_n, 3) if open_n else None,
        "by_verdict": dict(Counter(str(r.get("verdict")) for r in rows)),
        "by_blocker": dict(Counter(str(r.get("blocker")) for r in rows)),
        "by_class": dict(Counter(str(r.get("cls")) for r in rows)),
        "ready_now": sorted(r["pr"] for r in rows if r.get("blocker") == "READY"),
        "need_zuck_root": sorted(need_zuck),
        "no_owner_act_after_level2": len(l2_free),
        "root_only_until_level2": sorted(
            r["pr"] for r in judged if r.get("cls") == "ROOT" and r.get("class_if_level2") != "ROOT"
        ),
    }


def run(
    repo: str,
    base: str = LIVE,
    prev_report: Mapping[str, Any] | None = None,
    max_prs: int = MAX_PRS,
    budget_s: float = BUDGET_S,
    auth: ModuleType | None = None,
) -> dict[str, Any]:
    auth = auth or load_authority()
    # facts() fetches with the gate's own git helper, which runs in the current directory: run
    # in this checkout, wherever the caller stood (the box sweep starts elsewhere)
    here = os.getcwd()
    os.chdir(ROOT)
    try:
        return _run(auth, repo, base, prev_report, max_prs, budget_s)
    finally:
        os.chdir(here)


def _run(
    auth: ModuleType,
    repo: str,
    base: str,
    prev_report: Mapping[str, Any] | None,
    max_prs: int,
    budget_s: float,
) -> dict[str, Any]:
    ag = auth.gate()
    policy = auth.pol.load_policy()
    open_prs: list[dict[str, Any]] = []
    for page in range(1, 11):
        batch = ag._gh(f"repos/{repo}/pulls?state=open&base={base}&per_page=100&page={page}")
        open_prs += batch
        if len(batch) < 100:
            break
    open_nums = {int(p["number"]) for p in open_prs}
    prev = {
        int(r["pr"]): r for r in (prev_report or {}).get("prs") or [] if int(r["pr"]) in open_nums
    }
    t0 = time.monotonic()
    done = 0
    for n in order(open_prs, prev):
        if done >= max_prs or time.monotonic() - t0 > budget_s:
            break
        title = next((str(p.get("title") or "") for p in open_prs if int(p["number"]) == n), "")
        row = judge(auth, ag, policy, repo, n, base)
        row["title"] = title[:100]  # local only
        prev[n] = row
        done += 1
    rows = sorted(prev.values(), key=lambda r: int(r["pr"]))
    return {
        "local_rows": rows,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "base": base,
        "judged_this_pass": done,
        "summary": summarise(rows, len(open_prs)),
        "note": "dry run of ops/release/authority facts()+decide(): nothing signed, posted or merged",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--max-prs", type=int, default=MAX_PRS)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--all", action="store_true", help="judge every open PR this pass")
    ap.add_argument("--print", action="store_true", help="stdout only, write nothing")
    ap.add_argument(
        "--min-interval-min", type=float, default=55.0, help="skip when --out is younger"
    )
    a = ap.parse_args(argv)
    prev: dict[str, Any] | None = None
    try:
        prev = json.loads(a.out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = None
    try:  # the full rows (with heads and reasons) carry the incremental state
        local = json.loads(LOCAL.read_text(encoding="utf-8"))
        if isinstance(local, dict) and prev is not None:
            prev = {**prev, "prs": local.get("prs") or prev.get("prs")}
    except (OSError, ValueError):
        pass
    if prev and not a.print and not a.all and a.min_interval_min > 0:
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(str(prev["at"]))).total_seconds() / 60
            if age < a.min_interval_min:
                print("authority replay fresh: not re-run")
                return 0
        except (KeyError, ValueError):
            pass
    if a.all:
        a.max_prs, a.budget_s = 10_000, 1e9
    full = run(a.repo, a.base, prev, a.max_prs, a.budget_s)
    rows = full.pop("local_rows")
    rep = {**full, "prs": [publishable(r) for r in rows]}
    text = json.dumps(rep, indent=1)
    if a.print:
        print(text)
        return 0
    try:
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(json.dumps({"at": rep["at"], "prs": rows}, indent=1), encoding="utf-8")
    except OSError:
        pass
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(a.out)
    s = rep["summary"]
    print(
        f"authority replay: {s['judged']}/{s['open_prs']} judged ({rep['judged_this_pass']} this pass); "
        f"ready {len(s['ready_now'])}, need zuck {len(s['need_zuck_root'])}; {s['by_blocker']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
