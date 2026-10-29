#!/usr/bin/env python3
"""AN AUDITOR CLEAR THAT NEVER LANDS IS WORK THE DESK PAID FOR AND THREW AWAY (owner rule 23).

    python scripts/check_unlanded_clears.py [--report-only] [--json] [--live REF] [--out PATH]

THE DEFECT THIS EXISTS FOR (2026-10-29). Global-data work the auditor cleared on 2026-10-14
(source-fixer-hard-stop 31618ff54, cot-axis cdee27200, cot-zcache-fix 95154ab2f, cot-followups
9702832f0) sat unlanded for fifteen days, and Breadth's two 2026-10-20 clears for nine. Nothing
on the desk named it: a CLEAR lived in a markdown report and a HEADS.txt note, and the only
evidence that it had NOT landed was the absence of a commit, which no fence looks for.

THE GUARD. `context/clear_landing_registry.jsonl` holds one row per auditor-CLEAR item:

    {"id", "sha" (40 hex), "kind": "bundle"|"branch", "path" (bundle, relative to the project
     files share) or "branch", "cleared_at" (ISO-8601 UTC), "report" (the CLEAR file or relay),
     optional "retired": {"reason": "...", "superseded_by": "<another row's id>"}}

Each sha is checked against the LIVE branch: LANDED when it is an ancestor of live, or when every
non-merge commit it carries has an equivalent patch-id on live (`git cherry`). An item unlanded
more than LATE_H hours after `cleared_at` is LATE. An item whose commit object is absent from
this clone is not in live's history (live is here and complete), so it reads UNLANDED with its
patch-id equivalence UNMEASURED and named. A RETIRED row (audit S1: the CLEAR was superseded by
a later one, or withdrawn) is never late; its reason is printed, and a `superseded_by` must name
a row that exists.

COVERAGE, WHICH CANNOT BE SKIPPED (audit MF2). A registry that misses a CLEAR measures nothing
about it, so every run also checks that every CLEAR has a row: every `AUDIT CLEAR <sha>` comment
on an open or merged PR (GitHub REST via `gh api`; UNMEASURED with the reason when gh is absent
or refuses), and every audit file carrying a CLEAR verdict under `reports/audit/` in this repo
and on the project-files share (a root that is absent here is UNMEASURED, never clean). A file is
covered when a row cites it as `report`; files that already held a CLEAR when the registry was
born are listed with their sha256 in `context/clear_landing_coverage_baseline.json` and read
BASELINED -- a baselined file whose content changes is a new CLEAR candidate and needs a row.
A missing row is RED.

VERDICTS. GREEN (nothing late, nothing missing, every coverage source read), RED (late items or
CLEARs with no row, each listed), BREACH (the registry is unreadable or a row is malformed --
fails the push that commits it, report-only or not), and UNMEASURED with its reason when the live
ref is absent, the clone is shallow, or a coverage source could not be read. Every report says
"as of fetch at <time>": a verdict is only as current as the last fetch of live (audit S2).

TWO READERS. The law gate runs this `--report-only` (RED prints and exits 0: the remedy for a
late CLEAR is a landing, and a gate that refused every push while one was late would refuse the
landing push too; a malformed row still fails). The box reads it hourly through
`desks/mt5/scripts/check_desk_health.py` (audit MF1), which writes
desks/mt5/reports/UNLANDED_CLEARS.json and turns RED into a PROBLEM finding in DESK_HEALTH.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402

REGISTRY = ROOT / "context" / "clear_landing_registry.jsonl"
BASELINE = ROOT / "context" / "clear_landing_coverage_baseline.json"
LIVE_REF = "refs/remotes/origin/claude/llm-auto-upgrade-verify-gcjac3"
REPO_SLUG = "kingdemond434-cpu/quant"
#: Audit roots scanned for CLEAR files: (label, root, absent_is_empty). The label is what the
#: report publishes. The repo's own tree is complete wherever this runs, so a repo without the
#: directory holds no CLEAR file; the share is mounted only on some machines, so its absence is
#: UNMEASURED.
AUDIT_ROOTS: tuple[tuple[str, Path, bool], ...] = (
    ("repo", ROOT / "reports" / "audit", True),
    ("share", Path("/mnt/project-files/reports/audit"), False),
)
#: Hours a CLEAR may wait for its landing before it is LATE.
LATE_H = 12.0
KINDS = ("bundle", "branch")
_SHA = re.compile(r"^[0-9a-f]{40}$")
#: The auditor's PR verdict comment: `AUDIT CLEAR <40-hex sha>` at the start of a line.
_COMMENT_CLEAR = re.compile(r"(?m)^AUDIT CLEAR ([0-9a-f]{40})\b")
#: A CLEAR verdict in an audit file: the word CLEAR, not NOT CLEAR / UNCLEAR / "before CLEAR".
_FILE_CLEAR = re.compile(r"(?<![A-Za-z])CLEAR(?![A-Za-z])")
_NOT_CLEAR = re.compile(r"(NOT|UN|before|until|no)[\s-]*CLEAR", re.IGNORECASE)

Gh = Callable[[str], Any]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=120,
                          check=False)


def _when(stamp: object) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at.astimezone(UTC) if at.tzinfo else None


def _retired(row: dict[str, Any]) -> dict[str, Any] | None:
    r = row.get("retired")
    return r if isinstance(r, dict) else None


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
        if "retired" in row:
            ret = _retired(row)
            if ret is None or not str(ret.get("reason") or "").strip():
                why.append("retired without a reason")
        if why:
            bad.append(f"line {n}: " + "; ".join(why))
            continue
        seen.add(row["id"])
        rows.append(row)
    for row in rows:
        sup = (_retired(row) or {}).get("superseded_by")
        if sup is not None and sup not in seen:
            bad.append(f"row {row['id']}: superseded_by {sup!r} names no registry row")
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


def fetched_at(repo: Path, live: str) -> str:
    """When live was last fetched here: its reflog, else FETCH_HEAD's mtime, else UNMEASURED."""
    log = _git(repo, "log", "-g", "-1", "--format=%gd", "--date=iso-strict", live)
    m = re.search(r"\{([^}]+)\}", log.stdout or "")
    stamp = _when(m.group(1)) if (log.returncode == 0 and m) else None
    if stamp is not None:
        return stamp.isoformat(timespec="seconds")
    gd = _git(repo, "rev-parse", "--git-path", "FETCH_HEAD").stdout.strip()
    if gd:
        p = Path(gd) if Path(gd).is_absolute() else repo / gd
        try:
            return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC).isoformat(
                timespec="seconds")
        except OSError:
            pass
    return "UNMEASURED (no reflog for live and no FETCH_HEAD)"


# --------------------------------------------------------------------------- coverage (MF2)
def _gh_cli(path: str) -> Any:
    """One GitHub REST GET through the gh CLI; raises on any failure."""
    exe = shutil.which("gh")
    if exe is None:
        raise RuntimeError("gh CLI not on PATH")
    r = subprocess.run([exe, "api", path], capture_output=True, text=True, timeout=60,
                       check=False)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path.split('?')[0]} rc={r.returncode}: "
                           f"{(r.stderr or '').strip()[:160]}")
    return json.loads(r.stdout)


def _pages(gh: Gh, path: str, cap: int = 100) -> list[dict[str, Any]]:
    """Every row of a paged REST list, by explicit page number (no Link-header following)."""
    out: list[dict[str, Any]] = []
    for page in range(1, cap + 1):
        sep = "&" if "?" in path else "?"
        got = gh(f"{path}{sep}per_page=100&page={page}")
        if not isinstance(got, list):
            raise RuntimeError(f"{path.split('?')[0]} page {page} is not a list")
        out += [g for g in got if isinstance(g, dict)]
        if len(got) < 100:
            return out
    raise RuntimeError(f"{path.split('?')[0]}: more than {cap} pages")


def pr_comment_clears(gh: Gh, slug: str = REPO_SLUG) -> list[dict[str, Any]]:
    """Every `AUDIT CLEAR <sha>` comment on an open or merged PR of `slug`."""
    pulls = {p["number"]: p for p in _pages(gh, f"repos/{slug}/pulls?state=all")
             if isinstance(p.get("number"), int)}
    found = []
    for c in _pages(gh, f"repos/{slug}/issues/comments"):
        try:
            num = int(str(c.get("issue_url") or "").rstrip("/").rsplit("/", 1)[-1])
        except ValueError:
            continue
        pr = pulls.get(num)
        if pr is None or not (pr.get("state") == "open" or pr.get("merged_at")):
            continue                     # an issue, or a PR closed without merging
        for sha in _COMMENT_CLEAR.findall(str(c.get("body") or "")):
            found.append({"pr": num, "sha": sha, "at": c.get("created_at"),
                          "url": c.get("html_url")})
    return found


def clear_files(roots: tuple[tuple[str, Path, bool], ...] = AUDIT_ROOTS
                ) -> tuple[list[dict[str, str]], list[str]]:
    """(CLEAR files found, roots that could not be read) under each audit root."""
    files, unread = [], []
    for label, root, absent_is_empty in roots:
        if not root.is_dir():
            if not absent_is_empty:
                unread.append(f"{label}: audit root absent here")
            continue
        for p in sorted(root.rglob("*.md")):
            try:
                text = p.read_text("utf-8", errors="replace")
            except OSError as exc:
                unread.append(f"{label}:{p.relative_to(root).as_posix()} unreadable "
                              f"({type(exc).__name__})")
                continue
            if any(_FILE_CLEAR.search(ln) and not _NOT_CLEAR.search(ln)
                   for ln in text.splitlines()):
                files.append({"key": f"reports/audit/{p.relative_to(root).as_posix()}",
                              "where": label,
                              "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    return files, unread


def _baseline(path: Path) -> dict[str, str]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {f"{f.get('where')}:{f.get('key')}": str(f.get("sha256"))
            for f in doc.get("files") or () if isinstance(f, dict)}


def coverage(rows: list[dict[str, Any]], *, gh: Gh | None, roots: tuple[tuple[str, Path, bool], ...],
             baseline: Path) -> dict[str, Any]:
    """Which CLEARs have no registry row (MF2), and which sources could not be read."""
    shas = {r["sha"] for r in rows}
    cited = {str(r.get("report") or "") for r in rows}
    missing: list[str] = []
    unmeasured: list[str] = []
    n_comments = 0
    if gh is None:
        unmeasured.append("PR comments: no GitHub reader configured")
    else:
        try:
            comments = pr_comment_clears(gh)
        except Exception as exc:          # the reader is best-effort; the verdict is not
            unmeasured.append(f"PR comments UNMEASURED: {type(exc).__name__}: {str(exc)[:200]}")
        else:
            n_comments = len(comments)
            for c in comments:
                if c["sha"] not in shas:
                    missing.append(f"PR #{c['pr']} comment AUDIT CLEAR {c['sha'][:9]} "
                                   f"({c['at']}) has no registry row")
    files, unread = clear_files(roots)
    unmeasured += unread
    base = _baseline(baseline)
    n_base = 0
    for f in files:
        if f["key"] in cited:
            continue
        tag = f"{f['where']}:{f['key']}"
        if base.get(tag) == f["sha256"]:
            n_base += 1
            continue
        why = "changed since the baseline" if tag in base else "no row cites it"
        missing.append(f"{tag} carries a CLEAR and {why}")
    return {"missing": missing, "unmeasured": unmeasured, "n_pr_comment_clears": n_comments,
            "n_clear_files": len(files), "n_baselined": n_base}


def judge(*, repo: Path = ROOT, registry: Path = REGISTRY, live: str = LIVE_REF,
          now: datetime | None = None, late_h: float = LATE_H, gh: Gh | None = _gh_cli,
          roots: tuple[tuple[str, Path, bool], ...] = AUDIT_ROOTS,
          baseline: Path = BASELINE) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    rows, bad = read_registry(registry)
    try:
        reg_shown = registry.resolve().relative_to(repo.resolve()).as_posix()
    except (ValueError, OSError):
        reg_shown = registry.name
    base: dict[str, Any] = {"schema": "unlanded_clears/2",
                            "generated_utc": at.isoformat(timespec="seconds"), "live": live,
                            "registry": reg_shown, "late_h": late_h}
    if bad:
        return {**base, "verdict": "BREACH", "why": f"{len(bad)} malformed row(s)",
                "malformed": bad}
    base["live_fetched_at"] = fetched_at(repo, live)
    cov = coverage(rows, gh=gh, roots=roots, baseline=baseline)
    base["coverage"] = cov
    if _git(repo, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        return {**base, "verdict": "UNMEASURED",
                "why": "shallow clone: ancestry against live cannot be proved"}
    if _git(repo, "rev-parse", "--verify", "--quiet", f"{live}^{{commit}}").returncode != 0:
        return {**base, "verdict": "UNMEASURED",
                "why": f"live ref {live} is not in this clone: nothing can be proved landed"}
    items, late = [], []
    for row in rows:
        cleared = _when(row["cleared_at"])
        assert cleared is not None  # validated in read_registry
        age_h = round((at - cleared).total_seconds() / 3600.0, 1)
        ret = _retired(row)
        if ret is not None:
            state = "RETIRED"
            how = str(ret["reason"]) + (f" (superseded by {ret['superseded_by']})"
                                        if ret.get("superseded_by") else "")
        else:
            state, how = landing(repo, row["sha"], live)
            if state == "UNLANDED":
                state = "LATE" if age_h > late_h else "PENDING"
        item = {"id": row["id"], "sha": row["sha"][:9], "kind": row["kind"],
                "where": row.get("path") or row.get("branch"), "cleared_at": row["cleared_at"],
                "age_h": age_h, "state": state, "how": how, "report": row["report"]}
        items.append(item)
        if state == "LATE":
            late.append(item)
    parts = []
    if late:
        parts.append(f"{len(late)} CLEAR item(s) unlanded more than {late_h:g}h after clearing: "
                     + ", ".join(f"{i['id']} ({i['age_h']:g}h)" for i in late))
    if cov["missing"]:
        parts.append(f"{len(cov['missing'])} CLEAR(s) with no registry row")
    if parts:
        verdict, why = "RED", "; ".join(parts)
    elif cov["unmeasured"]:
        verdict = "UNMEASURED"
        why = (f"{len(items)} CLEAR item(s), none late; coverage not fully read: "
               + "; ".join(cov["unmeasured"]))
    else:
        verdict, why = "GREEN", f"{len(items)} CLEAR item(s), none late, every CLEAR has a row"
    return {**base, "verdict": verdict, "why": why, "items": items,
            "late": [i["id"] for i in late]}


def render(doc: dict[str, Any]) -> list[str]:
    lines = [f"unlanded clears: {doc['verdict']} -- {doc['why']}",
             f"  as of fetch at {doc.get('live_fetched_at', 'UNMEASURED')} ({doc.get('live')})"]
    for bad in doc.get("malformed") or ():
        lines.append(f"  MALFORMED {bad}")
    for i in doc.get("items") or ():
        lines.append(f"  {i['state']:<18} {i['id']} {i['sha']} cleared {i['cleared_at']} "
                     f"({i['age_h']:g}h) -- {i['how']} [{i['report']}]")
    cov = doc.get("coverage") or {}
    for m in cov.get("missing") or ():
        lines.append(f"  NO ROW             {m}")
    for u in cov.get("unmeasured") or ():
        lines.append(f"  COVERAGE UNMEASURED {u}")
    if cov:
        lines.append(f"  coverage: {cov['n_pr_comment_clears']} PR-comment CLEAR(s), "
                     f"{cov['n_clear_files']} CLEAR file(s), {cov['n_baselined']} baselined")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--report-only", action="store_true",
                    help="print RED without failing on it (a malformed registry still fails)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--live", default=LIVE_REF)
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--out", default=None, help="also write the verdict document here")
    a = ap.parse_args(argv)
    doc = judge(registry=Path(a.registry), live=a.live)
    print(json.dumps(doc, indent=1) if a.json else "\n".join(render(doc)))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(doc, indent=1) + "\n", "utf-8", newline="\n")
    # Name the passing set (R0237). RED passes only under --report-only, never BREACH.
    passing = {"GREEN", "UNMEASURED"} | ({"RED"} if a.report_only else set())
    return fence_exit(doc["verdict"], passing, fail=1)


if __name__ == "__main__":
    sys.exit(main())
