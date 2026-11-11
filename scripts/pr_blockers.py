"""PER-PR BLOCKERS: for every open PR into LIVE, the ONE thing that holds it, in plain words.

    python scripts/pr_blockers.py [--repo OWNER/NAME] [--md PATH] [--json PATH]

Backlog row 2026-11-03 (Autonomy): "for every PR say exactly which blocker holds it (CI
queued/failed, missing audit, draft, protected policy, deploy failure); stop asking taps."

Each PR gets one `blocker` (the first that applies, in the order the merge path meets them) and
the facts behind it. The gate's own `audit/clear` status description is quoted as `gate_says`,
because that is what the box sweep itself decided on that head:

    CONFLICT        GitHub reports the PR cannot merge into LIVE (rebase or merge LIVE in)
    AUDIT_MISSING   no Auditor registry row for the PR at all
    AUDIT_HOLD      the newest row for the CURRENT head is a HOLD
    AUDIT_STALE     the newest row is for an older head: the current head needs a fresh audit
    CI_FAILED       a gating job (audit_gate.GATING_JOBS) concluded failure/cancelled/timed out
    CI_PENDING      a gating job is queued or running, or has not reported on this head
    VETO_WINDOW     CLEAR on this head, CI green, inside the gate's 24 h veto window
    GATE_PATH_OFF   the gate says the registry path is off (e.g. the ROOT pin does not match)
    READY           nothing above: it waits only for the box sweep to reach it
    UNMEASURED      a read for this PR failed this run (named, never guessed)

Runs as the hourly core leg `pr_blockers`; the report is published with box state.

It reads GitHub (the box login when it works, anonymously otherwise: the repo is public) and the
audit-registry ref. It never merges, comments, re-runs or edits anything.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = "kingdemond434-cpu/quant"
LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
REGISTRY_REF = "audit-registry"
REGISTRY_FILE = "REGISTRY_ROWS.jsonl"
GATE_STATUS = "audit/clear"
#: .github/scripts/audit_gate.py GATING_JOBS and REGISTRY_HOLD_H (pinned by the tests).
GATING_JOBS = ("quality", "mt5-money-path", "coverage-floor")
VETO_H = 24.0
REPORT = ROOT / "desks" / "mt5" / "reports" / "PR_BLOCKERS.json"
UA = "pr-blockers"
ORDER = ("CONFLICT", "AUDIT_MISSING", "AUDIT_HOLD", "AUDIT_STALE", "CI_FAILED", "CI_PENDING",
         "VETO_WINDOW", "GATE_PATH_OFF", "READY", "UNMEASURED")  # fmt: skip
#: Consecutive failed PR reads after which the rest of the run is marked UNMEASURED.
MAX_MISSES = 5
WORDS = {
    "CONFLICT": "cannot merge into LIVE: needs LIVE merged in",
    "AUDIT_MISSING": "no Auditor verdict yet",
    "AUDIT_HOLD": "Auditor HOLD on this head",
    "AUDIT_STALE": "Auditor verdict is for an older head",
    "CI_FAILED": "a gating CI job failed",
    "CI_PENDING": "gating CI queued or running",
    "VETO_WINDOW": "inside the 24 h veto window",
    "GATE_PATH_OFF": "the box's registry merge path is off",
    "READY": "waiting only for the box sweep",
    "UNMEASURED": "its facts could not be read this run",
}
_BAD = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}

Fetch = Callable[[str], Any]


def _ts(s: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def newest_rows(lines: Iterable[str]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("pr"), int):
            out[r["pr"]] = r
    return out


def ci_state(check_runs: Iterable[Mapping[str, Any]]) -> tuple[str, list[str]]:
    """("failed"|"pending"|"green", names) over the gating jobs on one head. The newest run of
    each name wins (a re-run replaces the run it re-ran)."""
    newest: dict[str, Mapping[str, Any]] = {}
    for c in check_runs:
        name = str(c.get("name") or "")
        if name not in GATING_JOBS:
            continue
        cur = newest.get(name)
        if cur is None or str(c.get("started_at") or "") >= str(cur.get("started_at") or ""):
            newest[name] = c
    failed = [n for n, c in newest.items()
              if c.get("status") == "completed" and c.get("conclusion") in _BAD]  # fmt: skip
    if failed:
        return "failed", sorted(failed)
    pending = [n for n in GATING_JOBS
               if n not in newest or newest[n].get("status") != "completed"
               or newest[n].get("conclusion") not in ("success", "neutral", "skipped")]  # fmt: skip
    return ("pending", pending) if pending else ("green", [])


def classify(
    now: datetime,
    pr: Mapping[str, Any],
    row: Mapping[str, Any] | None,
    ci: tuple[str, list[str]],
    gate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """One PR's blocker, from facts only (pure: the tests drive it)."""
    head = str((pr.get("head") or {}).get("sha") or "")
    gate_says = str((gate or {}).get("description") or "")
    found: list[str] = []
    if pr.get("mergeable") is False or pr.get("mergeable_state") == "dirty":
        found.append("CONFLICT")
    if row is None:
        found.append("AUDIT_MISSING")
    elif row.get("sha") != head:
        found.append("AUDIT_STALE")
    elif row.get("verdict") != "CLEAR":
        found.append("AUDIT_HOLD")
    if ci[0] == "failed":
        found.append("CI_FAILED")
    elif ci[0] == "pending":
        found.append("CI_PENDING")
    if row is not None and row.get("sha") == head and row.get("verdict") == "CLEAR":
        at = _ts(row.get("at"))
        if at is not None and (now - at).total_seconds() / 3600.0 < VETO_H:
            found.append("VETO_WINDOW")
    if "path is off" in gate_says or "root digest" in gate_says:
        found.append("GATE_PATH_OFF")
    found.sort(key=ORDER.index)
    blocker = found[0] if found else "READY"
    return {
        "pr": int(pr["number"]), "title": str(pr.get("title") or "")[:90], "head": head[:9],
        "draft": bool(pr.get("draft")), "blocker": blocker, "words": WORDS[blocker],
        "also": found[1:], "audit": None if row is None else {
            "verdict": row.get("verdict"), "sha": str(row.get("sha") or "")[:9], "at": row.get("at")},
        "ci": {"state": ci[0], "jobs": ci[1]}, "gate_says": gate_says[:160],
    }  # fmt: skip


def table(rows: list[dict[str, Any]], at: str) -> str:
    tally = Counter(r["blocker"] for r in rows)
    out = [f"# What holds each open PR ({at})", "",
           f"{len(rows)} open PRs into LIVE. " + ", ".join(
               f"{k} {tally[k]}" for k in ORDER if tally.get(k)) + ".", "",
           "| PR | blocker | in words | also | CI | audit | gate says |",
           "|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in sorted(rows, key=lambda r: (ORDER.index(r["blocker"]), r["pr"])):
        a = r["audit"]
        audit = "none" if a is None else f"{a['verdict']} {a['sha']}"
        ci = r["ci"]["state"] + (f" ({', '.join(r['ci']['jobs'])})" if r["ci"]["jobs"] else "")
        says = r["gate_says"].replace("|", "/")[:80]
        out.append(f"| #{r['pr']}{' (draft)' if r['draft'] else ''} | {r['blocker']} | "
                   f"{r['words']} | {', '.join(r['also'])} | {ci} | {audit} | {says} |")  # fmt: skip
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- the reads


#: The box's own gh (the gate sweep uses it); the hourly cycle does not put it on PATH.
BOX_GH = Path(r"C:\Users\Administrator\tools\gh\bin\gh.exe")


def _gh_bin() -> str:
    env = os.environ.get("GH_BIN")
    if env:
        return env
    try:
        return str(BOX_GH) if BOX_GH.is_file() else "gh"
    except OSError:
        return "gh"


def gh_fetch(path: str) -> Any:
    gh = _gh_bin()
    p = subprocess.run([gh, "api", path], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60, check=False)  # fmt: skip
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200] or f"gh exit {p.returncode}")
    return json.loads(p.stdout or "null")


def anon_fetch(path: str) -> Any:
    hdr = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    req = urllib.request.Request(f"https://api.github.com/{path}", headers=hdr)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def raw_registry(repo: str) -> list[str]:
    url = f"https://raw.githubusercontent.com/{repo}/{REGISTRY_REF}/{REGISTRY_FILE}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8").splitlines()


def _budget_s() -> float:
    """The hourly cycle's cap for this leg (QUANT_LEG_BUDGET_S), less a margin to write."""
    raw = os.environ.get("QUANT_LEG_BUDGET_S")
    if not raw:
        return float("inf")
    try:
        return max(30.0, float(raw) - 30.0)
    except ValueError:
        return float("inf")


def collect(repo: str, now: datetime, fetch: Fetch,
            registry: Callable[[str], list[str]] = raw_registry,
            clock: Callable[[], float] = time.monotonic,
            budget_s: float | None = None) -> list[dict[str, Any]]:  # fmt: skip
    stop = clock() + (_budget_s() if budget_s is None else budget_s)
    prs: list[dict[str, Any]] = []
    for page in range(1, 11):
        batch = fetch(f"repos/{repo}/pulls?state=open&base={LIVE}&per_page=100&page={page}") or []
        prs += batch
        if len(batch) < 100:
            break
    rows = newest_rows(registry(repo))
    out = []
    misses = 0
    for p in prs:
        n, head = int(p["number"]), str(p["head"]["sha"])
        if clock() >= stop:  # the leg's budget: the rest is named, never guessed
            out.append(unmeasured(p, "not read: the leg's time budget ran out"))
            continue
        if misses >= MAX_MISSES:  # rate-limited or GitHub down: the rest is named, never guessed
            out.append(unmeasured(p, f"not read: {MAX_MISSES} reads in a row failed"))
            continue
        try:
            detail = fetch(f"repos/{repo}/pulls/{n}") or {}
            runs = (fetch(f"repos/{repo}/commits/{head}/check-runs?per_page=100") or {}).get(
                "check_runs") or []  # fmt: skip
            st = fetch(f"repos/{repo}/commits/{head}/status") or {}
        except (RuntimeError, OSError, ValueError) as exc:  # one 503 never loses the table
            misses += 1
            out.append(unmeasured(p, f"{type(exc).__name__}: {str(exc)[:80]}"))
            continue
        misses = 0
        gate = next((s for s in st.get("statuses") or [] if s.get("context") == GATE_STATUS), None)
        pr = {**p, "mergeable": detail.get("mergeable"),
              "mergeable_state": detail.get("mergeable_state")}  # fmt: skip
        out.append(classify(now, pr, rows.get(n), ci_state(runs), gate))
    return out


def unmeasured(pr: Mapping[str, Any], why: str) -> dict[str, Any]:
    """A PR whose facts could not be read this run: UNMEASURED, with the reason."""
    return {
        "pr": int(pr["number"]), "title": str(pr.get("title") or "")[:90],
        "head": str((pr.get("head") or {}).get("sha") or "")[:9], "draft": bool(pr.get("draft")),
        "blocker": "UNMEASURED", "words": WORDS["UNMEASURED"], "also": [], "audit": None,
        "ci": {"state": "unmeasured", "jobs": []}, "gate_says": why[:160],
    }  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--json", type=Path, default=REPORT)
    ap.add_argument("--md", type=Path, default=None)
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    try:
        gh_fetch("user")
        fetch: Fetch = gh_fetch
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
        fetch = anon_fetch
    rows = collect(a.repo, now, fetch)
    at = now.isoformat(timespec="minutes")
    doc = {"schema": "pr_blockers/1", "at": at, "open": len(rows),
           "by_blocker": dict(Counter(r["blocker"] for r in rows).most_common()), "prs": rows}  # fmt: skip
    a.json.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.json.with_suffix(a.json.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, a.json)
    if a.md is not None:
        a.md.parent.mkdir(parents=True, exist_ok=True)
        a.md.write_text(table(rows, at), encoding="utf-8")
    print(f"pr_blockers: {len(rows)} open; {doc['by_blocker']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
