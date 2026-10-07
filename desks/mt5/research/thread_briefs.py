#!/usr/bin/env python3
"""ONE BRIEF PER THREAD, REGENERATED WITH THE MANDATE AUDIT: WHAT IT OWES, WHERE IT STOPPED.

    python desks/mt5/research/thread_briefs.py                       # desks/mt5/reports/thread_briefs/
    python desks/mt5/research/thread_briefs.py --out /mnt/project-files/reports/thread_briefs

WHY (MISC-18 and MISC-22, principal 2026-10-06). A thread restarted after a usage limit or a
crash started blind: its brief was the long original prompt, its open requirements lived in a
3,601-row audit and a 156-row principal-message file outside the repo, and its PRs were whatever
it remembered. So every restart re-derived its own state, and a requirement the audit owned to it
could be dropped without anyone noticing. This writes one short file per owner thread that the
thread reads first:

    open requirements   every mandate-audit row it owns below RUNNING, by id and state, and every
                        principal-message requirement it owns that a delivery check found
                        NOT STARTED or IN PR, with the requirement text
    PR heads            its open PRs (head sha, draft, last update), when GitHub is reachable; a
                        PR an IN PR verdict cites that is no longer open is flagged for re-check
    next step           the thread's own resume note when it wrote one, else the first open item
    blockers            the distinct blockers its rows name, most frequent first

RESUME STATE. The derived part is regenerated every pass and never edited by hand. A thread
records where it stopped in `<notes_dir>/<slug>.md` (default: `notes/` beside the briefs); the
generator copies that note into the brief verbatim and never writes it.

Called by mandate_audit.main() on every hourly pass with the audit it just built, so the briefs
can never describe an audit older than the one published.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
PM = DESK / "data" / "mandate_audit" / "pm_requirements_2026-10-06.json.gz"
THREADS = DESK / "data" / "mandate_audit" / "threads.json"
OUT_DIR = DESK / "reports" / "thread_briefs"
REPO = "kingdemond434-cpu/quant"

#: Mandate-audit states a thread still owes work on.
OPEN_STATES: tuple[str, ...] = ("ABSENT", "CODED", "WIRED", "SCHEDULED", "BLOCKED", "UNMEASURED")
OPEN_VERDICTS: tuple[str, ...] = ("NOT STARTED", "IN PR")
#: A delivery verdict older than this is printed with a re-check warning.
VERDICT_STALE_H = 72.0
TOP_BLOCKERS = 6
_SESSION_RE = re.compile(r"session_(01[A-Za-z0-9]{20,})")
_PR_RE = re.compile(r"#(\d{2,5})")


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "unowned"


def load_pm(path: Path = PM) -> list[dict[str, Any]]:
    try:
        return list(json.loads(gzip.decompress(path.read_bytes()))["requirements"])
    except (OSError, ValueError, KeyError):
        return []


def load_threads(path: Path = THREADS) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {t["title"]: t for t in doc.get("threads", []) if isinstance(t, dict) and "title" in t}


def fetch_prs(timeout: float = 60.0) -> list[dict[str, Any]] | None:
    """Open PRs with the session that wrote each (from the body's session link). None = unreachable."""
    if shutil.which("gh") is None:
        return None
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{REPO}/pulls?state=open&per_page=100", "--paginate", "--jq",
             ".[] | {n: .number, sha: .head.sha[0:9], draft: .draft, title: .title, "
             "updated: .updated_at, body: (.body // \"\")}"],
            capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    prs = []
    for line in out.stdout.splitlines():
        try:
            p = json.loads(line)
        except ValueError:
            continue
        m = _SESSION_RE.findall(p.pop("body", ""))
        p["session"] = m[-1] if m else None
        prs.append(p)
    return prs


def _age_h(at: Any, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return None
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    return (now - t).total_seconds() / 3600.0


def thread_view(title: str, rows: list[dict[str, Any]], pm: list[dict[str, Any]],
                prs: list[dict[str, Any]] | None, meta: dict[str, Any],
                now: datetime) -> dict[str, Any]:
    """Everything one thread's brief says, as data."""
    mine = [r for r in rows if (r.get("owner_thread") or "UNOWNED") == title]
    open_rows = [r for r in mine if r.get("state") in OPEN_STATES]
    by_state: dict[str, list[str]] = {}
    for r in sorted(open_rows, key=lambda r: (OPEN_STATES.index(r["state"]), r["id"])):
        by_state.setdefault(r["state"], []).append(r["id"])
    pm_open = [p for p in pm if p.get("owner_thread") == title
               and (p.get("delivery") or {}).get("verdict") in OPEN_VERDICTS]
    pm_open.sort(key=lambda p: (OPEN_VERDICTS.index(p["delivery"]["verdict"]), p["id"]))
    sess = str(meta.get("session") or "").removeprefix("cse_").removeprefix("session_")
    my_prs = None if prs is None else [p for p in prs if sess and p.get("session") == sess]
    open_nums = None if prs is None else {p["n"] for p in prs}
    gone: list[str] = []
    for p in pm_open:
        d = p["delivery"]
        if d["verdict"] == "IN PR" and open_nums is not None:
            cited = {int(x) for x in _PR_RE.findall(str(d.get("evidence", "")))}
            if cited and not cited & open_nums:
                gone.append(f"{p['id']} cites #{min(cited)}, which is no longer open: re-check "
                            "whether it merged (BUILT) or closed (NOT STARTED)")
    blockers = Counter(str(r.get("blocker")).strip()[:160] for r in open_rows + pm_open
                       if r.get("blocker") and str(r.get("blocker")).strip().lower()
                       not in ("none", "n/a", "unmeasured", ""))
    if pm_open:
        p = pm_open[0]
        nxt = f"{p['id']}: {p['delivery'].get('note') or p.get('next_repair') or p['requirement']}"
    elif open_rows:
        r = open_rows[0]
        nxt = f"{r['id']}: {r.get('next_repair') or r.get('requirement')}"
    else:
        nxt = "nothing open in the audit or the principal-message check"
    return {
        "title": title, "slug": slug(title), "thread_id": meta.get("thread_id"),
        "session": meta.get("session"), "owned_rows": len(mine), "open_rows": len(open_rows),
        "open_by_state": by_state, "pm_open": pm_open, "prs": my_prs, "pr_rechecks": gone,
        "next_step": str(nxt)[:400], "blockers": blockers.most_common(TOP_BLOCKERS),
        "verdict_stale": any((_age_h(p["delivery"].get("checked_at"), now) or 0) > VERDICT_STALE_H
                             for p in pm_open),
    }


def render(v: dict[str, Any], audit_at: str, now: datetime, note: str | None) -> str:
    L = [f"# {v['title']}: brief and resume state",
         "",
         f"Regenerated {now.isoformat(timespec='minutes')} from the mandate audit of {audit_at}. "
         "Read this first after any restart. The derived sections are rewritten every pass; "
         "write where you stopped in the resume note (path at the bottom), never here.",
         ""]
    L += ["## Where I stopped (thread's own resume note)", ""]
    L += [note.strip() if note else "_No resume note written yet._", ""]
    L += ["## Next step", "", v["next_step"], ""]
    L += [f"## Principal-message requirements still open ({len(v['pm_open'])})", ""]
    if v["verdict_stale"]:
        L += [f"Some verdicts below are older than {VERDICT_STALE_H:.0f}h; re-check before "
              "relying on them.", ""]
    for p in v["pm_open"]:
        d = p["delivery"]
        L.append(f"- **{p['id']}** {d['verdict']} ({d.get('evidence') or 'no evidence'}): "
                 f"{p['requirement']}")
        if d.get("note"):
            L.append(f"  - status: {d['note']}")
    if not v["pm_open"]:
        L.append("None.")
    L += [""]
    for line in v["pr_rechecks"]:
        L.append(f"- RE-CHECK: {line}")
    if v["pr_rechecks"]:
        L.append("")
    L += [f"## Mandate-audit rows still open ({v['open_rows']} of {v['owned_rows']} owned)", ""]
    for state, ids in v["open_by_state"].items():
        L.append(f"- {state} ({len(ids)}): {', '.join(ids)}")
    if not v["open_by_state"]:
        L.append("None.")
    L += ["", "## Open PRs", ""]
    if v["prs"] is None:
        L.append("UNMEASURED: GitHub was not reachable from this host on this pass.")
    elif not v["prs"]:
        L.append("None open from this thread's session.")
    else:
        for p in sorted(v["prs"], key=lambda p: p["n"]):
            L.append(f"- #{p['n']} {'draft ' if p.get('draft') else ''}head {p['sha']} "
                     f"(updated {str(p.get('updated'))[:16]}): {p['title']}")
    L += ["", "## Blockers named by its open rows", ""]
    for text, n in v["blockers"]:
        L.append(f"- ({n}) {text}")
    if not v["blockers"]:
        L.append("None named.")
    L += ["", f"Resume note: `notes/{v['slug']}.md` beside this file."
          + (f" Thread: [{v['title']}](#{v['thread_id']})." if v.get("thread_id") else ""), ""]
    return "\n".join(L)


def write(audit: dict[str, Any], out_dir: Path = OUT_DIR, notes_dir: Path | None = None,
          now: datetime | None = None, prs: list[dict[str, Any]] | None | bool = False,
          pm: list[dict[str, Any]] | None = None,
          threads: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Write every thread's brief and INDEX.json; returns the index. prs=False means fetch."""
    now = now or datetime.now(tz=UTC)
    pm = load_pm() if pm is None else pm
    threads = load_threads() if threads is None else threads
    pr_list = fetch_prs() if prs is False else prs
    notes_dir = notes_dir or out_dir / "notes"
    rows = audit.get("rows") or []
    titles = sorted({r.get("owner_thread") or "UNOWNED" for r in rows}
                    | {p.get("owner_thread") or "UNOWNED" for p in pm} | set(threads))
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for title in titles:
        v = thread_view(title, rows, pm, pr_list if isinstance(pr_list, list) else None,
                        threads.get(title, {}), now)
        note_p = notes_dir / f"{v['slug']}.md"
        try:
            note = note_p.read_text("utf-8")
        except OSError:
            note = None
        text = render(v, str(audit.get("generated_utc")), now, note)
        tmp = out_dir / f".{v['slug']}.md.tmp"
        tmp.write_text(text, "utf-8")
        tmp.replace(out_dir / f"{v['slug']}.md")
        index.append({"title": title, "file": f"{v['slug']}.md", "open_rows": v["open_rows"],
                      "pm_open": len(v["pm_open"]),
                      "prs": None if v["prs"] is None else len(v["prs"]),
                      "has_resume_note": note is not None, "next_step": v["next_step"]})
    doc = {"generated_utc": now.isoformat(timespec="seconds"),
           "audit_generated_utc": audit.get("generated_utc"),
           "prs_measured": isinstance(pr_list, list), "threads": index}
    tmp = out_dir / ".INDEX.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    tmp.replace(out_dir / "INDEX.json")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--notes", type=Path, default=None)
    ap.add_argument("--audit", type=Path, default=None,
                    help="a published MANDATE_AUDIT.json; default: rebuild it now")
    a = ap.parse_args(argv)
    if a.audit:
        audit = json.loads(a.audit.read_text("utf-8"))
    else:
        from research import mandate_audit
        audit = mandate_audit.build()
    doc = write(audit, a.out, a.notes)
    open_pm = sum(t["pm_open"] for t in doc["threads"])
    print(f"thread_briefs: {len(doc['threads'])} threads, {open_pm} open principal-message "
          f"requirements, PRs {'measured' if doc['prs_measured'] else 'UNMEASURED'} -> {a.out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(DESK))
    raise SystemExit(main())
