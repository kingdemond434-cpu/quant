"""ARCHITECTURE HEALTH: one read-only look at whether the platform is getting simpler or more tangled.

    python scripts/arch_health.py --repo OWNER/NAME --out ARCH_HEALTH.json   # rc 2 when RED
    python scripts/arch_health.py --repo OWNER/NAME --print
    python scripts/arch_health.py --static-only                              # no GitHub calls

WHY (zuck 2026-11-13 16:43Z, Phases 6 and 7; 16:50Z: "detect permission regressions, stale
dependencies and broken downstream operations automatically. Do not introduce another approval
gate to fix an existing approval gate"). This is a MONITOR, never a gate: it blocks nothing,
merges nothing and is run by the existing hourly pass. No new scheduler.

What it measured on 2026-11-13 and why each check exists:

    flow          PRs opened vs merged. 11-03..11-13: ~530 opened, ~90 merged, 653 open (623
                  drafts). Arrival far above service is an unbounded queue: every new PR lengthens
                  every other PR's wait. WIP_GROWTH goes RED when 7-day opens exceed 3x merges.
    duplicates    files touched by 3+ open PRs. The merge-gate clone had 7 open fixes (#725 #887
                  #901 #973 #984 #1041 #1089); none landed, because each needed the gate it fixed.
    queue         queued runs by workflow/event, the oldest age, and the LIVE run's oldest queued
                  job. A burst of workflow_run runs is CASCADE: cancelling 505 PR runs at 16:2xZ
                  fired 139 audit-gate looks that queued in front of LIVE's seal.
    deploy_lag    hours since the box adopted (RELEASE.json) against LIVE's last code commit.
                  Measured 72 h: every merge since 11-10 16:24Z was inert on the trading box.
    half_landed   a workflow `run:` or a box task `runs=` naming a file that is not in the tree.
                  paperclip-lab.yml failed 36 of 36 hourly runs because #594/#595 (workflow)
                  merged and #593 (the script it runs) never did.
    box_tasks     FAILING tasks from the published process_health, with the scheduler's code.

Alarms are ranked and capped at five, with the full count beside them. MERGE_PIPELINE.json
carried 126 RED lines at 14:20Z; a list nobody can act on is a silent failure with extra steps.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
ROOT = Path(__file__).resolve().parents[1]
#: the merge, release and adoption machinery: where duplicate fixes hurt most
MACHINERY = (
    ".github/",
    "ops/",
    "libs/ops/",
    "scripts/merge_pipeline_watch.py",
    "scripts/live_first_ci.py",
    "desks/mt5/scripts/Adopt",
    "desks/mt5/scripts/Seal-",
)
MAX_ALARMS = 5
SEVERITY = {
    "DEPLOY_LAG": 0,
    "LIVE_CI_STARVED": 1,
    "HALF_LANDED": 2,
    "CASCADE": 3,
    "WIP_GROWTH": 4,
    "DUPLICATE_FIXES": 5,
    "BOX_TASKS_FAILING": 6,
    "QUEUE_AGE": 7,
}

_RUN_PATH = re.compile(
    r"(?:python3?|bash|pwsh|powershell(?:\.exe)?(?:\s+-File)?)\s+(?:-[A-Za-z]+\s+)*"
    r"([\w./-]+\.(?:py|sh|ps1))"
)
_TASK_RUNS = re.compile(r'(?:^|\s)(?:also_)?runs="([^"]+)"')
_CHECKOUT_PATH = re.compile(r"^\s*path:\s*([\w.-]+)\s*$")


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_h(now: datetime, s: str | None) -> float | None:
    t = _ts(s)
    return None if t is None else round((now - t).total_seconds() / 3600, 2)


# ---------------------------------------------------------------- static checks (no network)
def half_landed(root: Path) -> list[dict[str, str]]:
    """Every workflow `run:` and box-task `runs=` path that names a file missing from the tree."""
    out: list[dict[str, str]] = []
    wf = root / ".github" / "workflows"
    for f in sorted(wf.glob("*.y*ml")) if wf.is_dir() else []:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        # a job that checks the repo out into a sub-folder (`path: harness`) runs harness/<file>
        dirs = tuple(m.group(1) + "/" for m in map(_CHECKOUT_PATH.match, lines) if m)
        for n, line in enumerate(lines, 1):
            if line.lstrip().startswith("#"):
                continue
            for p in _RUN_PATH.findall(line):
                if "$" in p or p.startswith("/"):
                    continue
                rel = next((p[len(d) :] for d in dirs if p.startswith(d)), p)
                if not (root / rel).exists():
                    out.append({"where": f"{f.relative_to(root).as_posix()}:{n}", "missing": p})
    man = root / "desks" / "mt5" / "ops" / "box_tasks.manifest"
    if man.is_file():
        for n, line in enumerate(man.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for field in _TASK_RUNS.findall(line):
                for p in field.split(","):
                    p = (p.split() or [""])[0].replace("\\", "/")
                    if p.endswith((".py", ".ps1", ".sh")) and not (root / p).exists():
                        out.append({"where": f"desks/mt5/ops/box_tasks.manifest:{n}", "missing": p})
    return out


# ---------------------------------------------------------------- pure assessments
def flow(
    opened_7d: int, merged_7d: int, open_prs: Sequence[Mapping[str, Any]], now: datetime
) -> dict[str, Any]:
    drafts = sum(1 for p in open_prs if p.get("draft"))
    idle = sum(1 for p in open_prs if (_age_h(now, p.get("updated_at")) or 0) > 7 * 24)
    ratio = round(opened_7d / merged_7d, 1) if merged_7d else None
    return {
        "open": len(open_prs),
        "drafts": drafts,
        "idle_7d": idle,
        "opened_7d": opened_7d,
        "merged_7d": merged_7d,
        "arrival_over_service": ratio,
        # Little's law: at today's merge rate, how many days the open set takes to clear
        "days_to_drain": round(len(open_prs) / (merged_7d / 7), 1) if merged_7d else None,
    }


def duplicate_clusters(
    pr_files: Mapping[int, Iterable[str]], min_prs: int = 3
) -> list[dict[str, Any]]:
    by_file: dict[str, set[int]] = defaultdict(set)
    for pr, files in pr_files.items():
        for f in files:
            if f.startswith(MACHINERY):
                by_file[f].add(pr)
    rows = [{"file": f, "prs": sorted(prs)} for f, prs in by_file.items() if len(prs) >= min_prs]
    return sorted(rows, key=lambda r: (-len(r["prs"]), r["file"]))


def queue(runs: Sequence[Mapping[str, Any]], now: datetime) -> dict[str, Any]:
    comp = Counter(f"{r.get('name')}/{r.get('event')}" for r in runs)
    ages = [a for a in (_age_h(now, r.get("created_at")) for r in runs) if a is not None]
    wr = sorted(
        t
        for t in (_ts(r.get("created_at")) for r in runs if r.get("event") == "workflow_run")
        if t is not None
    )
    burst = 0  # the most workflow_run runs created inside any 30-min window
    j = 0
    for i, t in enumerate(wr):
        while wr[j] < t - timedelta(minutes=30):
            j += 1
        burst = max(burst, i - j + 1)
    return {
        "queued": len(runs),
        "oldest_h": max(ages) if ages else 0.0,
        "by_workflow": dict(comp.most_common()),
        "workflow_run_burst_30m": burst,
    }


def deploy_lag(
    release: Mapping[str, Any] | None, live_code_at: str | None, now: datetime
) -> dict[str, Any]:
    adopted = (release or {}).get("generated_utc")
    t_live, t_box = _ts(live_code_at), _ts(adopted)
    return {
        "box_code_sha": (release or {}).get("code_sha", "")[:9],
        "adopted_at": adopted,
        "release_age_h": _age_h(now, adopted),
        "live_code_at": live_code_at,
        # how long LIVE code has been waiting for the box: 0 when the box is current
        "lag_h": (
            round(max(0.0, (t_live - t_box).total_seconds() / 3600), 2)
            if t_live and t_box
            else None
        ),
    }


def box_tasks(ph: Mapping[str, Any] | None) -> dict[str, Any]:
    procs = (ph or {}).get("processes") or []
    failing = [
        {"name": p.get("name"), "code": p.get("last_result_code"), "why": p.get("why")}
        for p in procs
        if p.get("verdict") == "FAILING"
    ]
    return {
        "at": (ph or {}).get("at"),
        "counts": (ph or {}).get("counts") or {},
        "failing": failing,
    }


def alarms(doc: Mapping[str, Any]) -> list[dict[str, str]]:
    a: list[dict[str, str]] = []
    d = doc.get("deploy_lag") or {}
    if (d.get("lag_h") or 0) > 6:
        a.append(
            {
                "key": "DEPLOY_LAG",
                "say": f"LIVE code has waited {d['lag_h']} h for the box "
                f"(box on {d.get('box_code_sha')}, adopted {d.get('adopted_at')})",
            }
        )
    lq = doc.get("live_ci") or {}
    if (lq.get("oldest_queued_job_h") or 0) > 0.5:
        a.append(
            {
                "key": "LIVE_CI_STARVED",
                "say": f"LIVE run {lq.get('run')} job "
                f"{lq.get('job')} queued {lq['oldest_queued_job_h']} h",
            }
        )
    hl = doc.get("half_landed") or []
    if hl:
        a.append(
            {
                "key": "HALF_LANDED",
                "say": f"{len(hl)} scheduled step(s) name missing files, "
                f"first {hl[0]['where']} -> {hl[0]['missing']}",
            }
        )
    q = doc.get("queue") or {}
    if (q.get("workflow_run_burst_30m") or 0) >= 50:
        a.append(
            {
                "key": "CASCADE",
                "say": f"{q['workflow_run_burst_30m']} workflow_run runs "
                "created inside 30 min: one action is fanning out into the queue",
            }
        )
    f = doc.get("flow") or {}
    if (f.get("arrival_over_service") or 0) > 3 or (f.get("merged_7d") == 0 and f.get("opened_7d")):
        a.append(
            {
                "key": "WIP_GROWTH",
                "say": f"{f.get('opened_7d')} PRs opened vs "
                f"{f.get('merged_7d')} merged in 7 d; {f.get('open')} open, "
                f"{f.get('days_to_drain')} d to drain at this rate",
            }
        )
    dup = doc.get("duplicates") or []
    if dup:
        a.append(
            {
                "key": "DUPLICATE_FIXES",
                "say": f"{len(dup)} machinery file(s) carry 3+ open "
                f"PRs; worst {dup[0]['file']} in {len(dup[0]['prs'])}",
            }
        )
    bt = (doc.get("box_tasks") or {}).get("failing") or []
    if bt:
        a.append(
            {
                "key": "BOX_TASKS_FAILING",
                "say": f"{len(bt)} box task(s) FAILING: "
                + ", ".join(str(t["name"]) for t in bt[:4]),
            }
        )
    if (q.get("oldest_h") or 0) > 2:
        a.append(
            {"key": "QUEUE_AGE", "say": f"{q.get('queued')} runs queued, oldest {q['oldest_h']} h"}
        )
    return sorted(a, key=lambda x: SEVERITY.get(x["key"], 99))


# ---------------------------------------------------------------- collection (GitHub, read-only)
def _gh(path: str, *extra: str) -> Any:
    p = subprocess.run(
        [os.environ.get("GH_BIN") or "gh", "api", *extra, path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"gh api {path}: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout or "null")


def _pages(path: str, key: str | None, pages: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sep = "&" if "?" in path else "?"
    for page in range(1, pages + 1):
        got = _gh(f"{path}{sep}per_page=100&page={page}")
        batch = (got.get(key) if key else got) or []
        out += batch
        if len(batch) < 100:
            break
    return out


def _count(repo: str, q: str) -> int:
    return int(_gh("search/issues", "-X", "GET", "-f", f"q=repo:{repo} is:pr {q}")["total_count"])


def _read(root: Path, rel: str) -> dict[str, Any] | None:
    try:
        d = json.loads((root / rel).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def collect(repo: str, root: Path, now: datetime, dup_cap: int = 150) -> dict[str, Any]:
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "repo": repo}
    doc["half_landed"] = half_landed(root)
    doc["box_tasks"] = box_tasks(_read(root, "desks/mt5/reports/process_health.json"))
    queued = _pages(f"repos/{repo}/actions/runs?status=queued", "workflow_runs", 5)
    doc["queue"] = queue(queued, now)
    live = [r for r in queued if r.get("head_branch") == LIVE]
    lq: dict[str, Any] = {}
    for r in live:
        for j in _gh(f"repos/{repo}/actions/runs/{r['id']}/jobs").get("jobs") or []:
            h = _age_h(now, j.get("created_at"))
            if (
                j.get("status") == "queued"
                and h is not None
                and h > (lq.get("oldest_queued_job_h") or -1)
            ):
                lq = {"run": r["id"], "job": j.get("name"), "oldest_queued_job_h": h}
    doc["live_ci"] = lq
    commits = _gh(f"repos/{repo}/commits?sha={LIVE}&per_page=100")
    code = next(
        (c for c in commits if not c["commit"]["message"].startswith(("mt5 box state", "seal"))),
        None,
    )
    doc["deploy_lag"] = deploy_lag(
        _read(root, "desks/mt5/data/RELEASE.json"),
        code["commit"]["committer"]["date"] if code else None,
        now,
    )
    open_prs = _pages(f"repos/{repo}/pulls?state=open&base={LIVE}", None, 10)
    since = (now - timedelta(days=7)).date().isoformat()
    doc["flow"] = flow(
        _count(repo, f"created:>={since}"),
        _count(repo, f"is:merged merged:>={since}"),
        open_prs,
        now,
    )
    recent = sorted(open_prs, key=lambda p: p.get("updated_at") or "", reverse=True)[:dup_cap]
    files = {
        p["number"]: [
            f["filename"] for f in _gh(f"repos/{repo}/pulls/{p['number']}/files?per_page=100")
        ]
        for p in recent
    }
    doc["duplicates"] = duplicate_clusters(files)
    return doc


def finish(doc: dict[str, Any]) -> dict[str, Any]:
    al = alarms(doc)
    doc["alarms_total"] = len(al)
    doc["alarms"] = al[:MAX_ALARMS]
    doc["status"] = "RED" if al else "GREEN"
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default="kingdemond434-cpu/quant")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--static-only", action="store_true")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    if a.static_only:
        doc = {
            "at": now.isoformat(timespec="seconds"),
            "half_landed": half_landed(a.root),
            "box_tasks": box_tasks(_read(a.root, "desks/mt5/reports/process_health.json")),
        }
    else:
        doc = collect(a.repo, a.root, now)
    doc = finish(doc)
    text = json.dumps(doc, indent=1, default=str)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = a.out.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(a.out)
    if a.print or not a.out:
        print(text)
    return 2 if doc["status"] == "RED" else 0


if __name__ == "__main__":
    sys.exit(main())
