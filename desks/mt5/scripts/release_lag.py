#!/usr/bin/env python3
"""How far is the box behind the newest GREEN release? A measurement and an alarm, never a decision.

A LIBRARY, NOT AN EXECUTABLE: its one clock is MT5-BoxHeartbeat, which imports it. By hand:
    python -c "import sys; sys.path.insert(0, 'desks/mt5/scripts'); import release_lag as r; \
print(r.refresh(force=True)['reason'])"

WHY (2026-11-03). The box sat on the 10-29 release for five days and nothing alarmed. Two causes
stacked: LIVE had no green CI run (the mt5-money-path job timed out), so no newer release was
promoted; and the box's old adopt_guard HELD on box-published state paths, so the releases that
did exist were not adopted. `check_adoption_freshness.py` watches the adopter RUNNING and HEAD
against the LIVE tip, inside the law gate; nothing compared what the box runs with what CI has
released, and nothing paged. This does both halves:

    GREEN               the adopted code contains the newest green release, or that release is
                        younger than BEHIND_MAX_H (the adopter is hourly; give it its cadences)
    RED  BEHIND         a newer green release has gone unadopted for over BEHIND_MAX_H. The report
                        names the last adopt-guard verdict and reason (reports/ADOPT_GUARD.json),
                        the adopter's last stage (reports/ADOPTION_HEARTBEAT.json), the tail of
                        logs/adopt_and_seal.log, and how many green releases behind the box is
    RED  NO_GREEN_RELEASE  LIVE carries code no green release covers, and the oldest such code
                        landed on LIVE over NO_GREEN_MAX_H ago (or no release exists at all): a
                        CI outage alarms on its own, even on a box that is fully adopted
    UNMEASURED          the adopted identity or the refs cannot be read. Never GREEN (L1.28a)

WHAT IT READS, ALL LOCAL. The adopted identity is `data/RELEASE.json` (`code_sha`, sealed at
`generated_utc`), falling back to HEAD. The newest green release is the `production` pointer that
`release_promotion.promote()` fast-forwards, as the adopter's own `release_promotion.py gate`
fetched it into `refs/quant/release-gate/production` (or `origin/production`), falling back to the
newest local `release/*` tag. LIVE is `refs/quant/release-gate/tip` / `origin/<LIVE>`. The only
network this module ever needs is the fetch the adopter already does; it runs read-only git with
`--no-optional-locks`, so it never takes the index lock the adopter writes under.

WHEN A RELEASE BECAME GREEN. The `release/<UTC>-<sha12>` tag on the release carries its promotion
instant. Where no such tag is in the local clone (the gate fetches tags only when `production` is
absent), the instant this report FIRST SAW that release is used and carried forward -- later than
the truth, so it can only delay an alarm, never invent one.

WHERE IT RUNS. `box_heartbeat.py` (MT5-BoxHeartbeat, every 5 minutes) calls `refresh()`, which
re-measures at most every REMEASURE_MIN and is bounded by per-command timeouts. No scheduled task
of its own. The heartbeat turns a RED or UNMEASURED report into a failing check and pages through
`alert_channels.send_all` on a new failure, a changed kind, and once a day while it persists.

THE CONTRACT. `green_at` is the last instant this report read GREEN, carried forward through RED.
`ops/organ_contract.py` contracts MT5-AdoptRelease on it, so process_health reads the adoption as
STALE once the box has been behind (or CI dark) past the contract, and ABSENT before the first
measurement -- never OK on no evidence.

Writes `desks/mt5/reports/RELEASE_LAG.json` (a state path; the box may write it).
"""
from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "RELEASE_LAG.json"
RELEASE_JSON = BASE / "data" / "RELEASE.json"
ADOPT_GUARD = BASE / "reports" / "ADOPT_GUARD.json"
ADOPT_HEARTBEAT = BASE / "reports" / "ADOPTION_HEARTBEAT.json"
ADOPT_LOG = BASE / "logs" / "adopt_and_seal.log"

#: A green release unadopted for longer than this is BEHIND: three hourly adopter cadences.
BEHIND_MAX_H = 3.0
#: LIVE code no green release covers, older than this, is a CI outage.
NO_GREEN_MAX_H = 24.0
#: The heartbeat runs every 5 minutes; the lag is re-measured at most this often.
REMEASURE_MIN = 15.0
#: A report older than this is no reading at all (the heartbeat reads it UNMEASURED).
REPORT_MAX_MIN = 60.0
GIT_TIMEOUT_S = 15.0
#: The whole measurement's git budget: it rides a 5-minute task with a 2-minute limit, so a slow
#: clone yields UNMEASURED (a failing check), never a killed heartbeat.
GIT_BUDGET_S = 45.0
LOG_TAIL = 8

LIVE_BRANCH = "claude/llm-auto-upgrade-verify-gcjac3"
TIP_REFS = ("refs/quant/release-gate/tip", f"refs/remotes/origin/{LIVE_BRANCH}")
PRODUCTION_REFS = ("refs/quant/release-gate/production", "refs/remotes/origin/production")
TAG_GLOB = "release/*"


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=UTC).isoformat(timespec="seconds")


def _parse_iso(text: Any) -> float | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).timestamp()


def _read_json(p: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


class Git:
    """Read-only git with a timeout per call. `None` from any call is an unread fact."""

    def __init__(self, root: Path, timeout: float = GIT_TIMEOUT_S,
                 budget: float = GIT_BUDGET_S) -> None:
        self.root, self.timeout = root, timeout
        self.deadline = time.monotonic() + budget

    def run(self, *args: str) -> tuple[int, str]:
        left = self.deadline - time.monotonic()
        if left <= 0:
            return -1, ""
        try:
            from libs.ops.release import _git_exe
            exe = _git_exe()
        except Exception:
            exe = "git"
        try:
            r = subprocess.run([exe, "--no-optional-locks", "-c", "core.quotepath=off", *args],
                               cwd=self.root, capture_output=True, text=True, errors="replace",
                               timeout=min(self.timeout, left), check=False)
        except (OSError, subprocess.SubprocessError):
            return -1, ""
        return r.returncode, r.stdout

    def rev(self, spec: str) -> str | None:
        rc, out = self.run("rev-parse", "--verify", "--quiet", f"{spec}^{{commit}}")
        if rc != 0:
            return None
        return out.strip() or None

    def is_ancestor(self, a: str, b: str) -> bool | None:
        rc, _ = self.run("merge-base", "--is-ancestor", a, b)
        return True if rc == 0 else False if rc == 1 else None

    def commit_time(self, sha: str) -> float | None:
        rc, out = self.run("show", "-s", "--format=%ct", sha)
        return float(out.strip()) if rc == 0 and out.strip().isdigit() else None


def _newest(git: Git, shas: list[str]) -> str | None:
    """The candidate every other candidate is an ancestor of; else the newest by commit time."""
    uniq = list(dict.fromkeys(s for s in shas if s))
    if len(uniq) <= 1:
        return uniq[0] if uniq else None
    for s in uniq:
        if all(o == s or git.is_ancestor(o, s) for o in uniq):
            return s
    return max(uniq, key=lambda s: git.commit_time(s) or 0.0)


def _tags(git: Git, not_in: str | None = None) -> list[tuple[str, str]]:
    """(tag name, commit sha) for every local release/* tag; with `not_in`, only the tags whose
    commit that one is missing (one git call, not one per tag)."""
    extra = [f"--no-merged={not_in}"] if not_in else []
    rc, out = git.run("for-each-ref", *extra,
                      "--format=%(refname:short) %(*objectname) %(objectname)",
                      f"refs/tags/{TAG_GLOB}")
    rows: list[tuple[str, str]] = []
    if rc != 0:
        return rows
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            # annotated: name, peeled commit, tag object; lightweight: name, commit
            rows.append((parts[0], parts[1] if len(parts) == 3 else parts[-1]))
    return rows


def _tag_stamp(name: str) -> float | None:
    try:
        from libs.ops.release_promotion import parse_tag
        parsed = parse_tag(name)
    except Exception:
        parsed = None
    return parsed[0].timestamp() if parsed else None


def _code_paths(paths: list[str]) -> list[str]:
    try:
        from libs.ops.release_promotion import code_paths
        return code_paths(paths)
    except Exception:
        return sorted(set(paths))     # unreadable rule: every path counts as code (fail closed)


def _first_unreleased_code_at(git: Git, green: str, tip: str) -> float | None:
    """When the oldest code LIVE carries beyond `green` landed on LIVE: the first-parent commit
    time of the first commit (merges diffed against their first parent) touching a code path."""
    rc, out = git.run("log", "--first-parent", "-m", "--reverse", "--name-only",
                      "--format=@%ct", f"{green}..{tip}")
    if rc != 0:
        return None
    stamp: float | None = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("@") and line[1:].isdigit():
            stamp = float(line[1:])
        elif line and stamp is not None and _code_paths([line]):
            return stamp
    return None


def _adopt_context() -> dict[str, Any]:
    """The adopter's own last words: guard verdict, heartbeat stage, log tail."""
    g = _read_json(ADOPT_GUARD) or {}
    hb = _read_json(ADOPT_HEARTBEAT) or {}
    tail: list[str] = []
    with contextlib.suppress(OSError), ADOPT_LOG.open("rb") as fh:
        fh.seek(0, 2)
        fh.seek(max(0, fh.tell() - 16384))
        tail = fh.read().decode("utf-8", "replace").splitlines()[-LOG_TAIL:]
    gate = hb.get("release_gate") if isinstance(hb.get("release_gate"), dict) else {}
    return {
        "guard": {"present": bool(g), "at": g.get("at"), "step": g.get("step"),
                  "decision": g.get("decision"), "reason": str(g.get("reason") or "")[:400]},
        "heartbeat": {"present": bool(hb), "started_at": hb.get("started_at"),
                      "finished_at": hb.get("finished_at"), "stage": hb.get("stage"),
                      "exit_code": hb.get("exit_code"),
                      "release_gate": {k: gate.get(k) for k in ("decision", "reason", "target")}
                      if gate else None},
        "log_tail": [ln[:300] for ln in tail],
    }


def measure(now: float | None = None, *, root: Path = ROOT, prev: dict[str, Any] | None = None,
            release_json: Path | None = None) -> dict[str, Any]:
    t = time.time() if now is None else now
    git = Git(root)
    doc: dict[str, Any] = {"measured_at": _iso(t), "behind_max_h": BEHIND_MAX_H,
                           "no_green_max_h": NO_GREEN_MAX_H, "problems": []}
    prev = prev or {}
    rel = _read_json(release_json or RELEASE_JSON) or {}
    code_sha = str(rel.get("code_sha") or "").strip()
    adopted = git.rev(code_sha) if code_sha else None
    source = "RELEASE.json code_sha" if adopted else "HEAD"
    if not adopted:
        adopted = git.rev("HEAD")
    doc["adopted"] = {"sha": adopted, "source": source,
                      "sealed_at": rel.get("generated_utc"),
                      "release_json_code_sha": code_sha or None}
    tip = _newest(git, [s for s in (git.rev(r) for r in TIP_REFS) if s])
    tags = _tags(git)
    prod = _newest(git, [s for s in (git.rev(r) for r in PRODUCTION_REFS) if s])
    if prod is None and tags:
        try:
            from libs.ops.release_promotion import newest_release_tag
            newest = newest_release_tag(n for n, _ in tags)
        except Exception:
            newest = None
        prod = dict(tags).get(newest) if newest else None
    doc["live_tip"] = tip
    doc["context"] = _adopt_context()
    if adopted is None:
        doc["problems"].append("neither RELEASE.json's code_sha nor HEAD resolves to a commit")
        return _finish(doc, "UNMEASURED", t, prev)
    if tip is None:
        doc["problems"].append(f"no LIVE tip ref in this clone ({', '.join(TIP_REFS)})")
        return _finish(doc, "UNMEASURED", t, prev)
    if prod is None:
        doc["newest_green"] = None
        doc["kinds"] = ["NO_GREEN_RELEASE"]
        doc["problems"].append("no production pointer and no release/* tag in this clone: no "
                               "green release exists to adopt")
        return _finish(doc, "RED", t, prev)

    names = [n for n, s in tags if s == prod]
    stamps = [s for s in (_tag_stamp(n) for n in names) if s is not None]
    pg = prev.get("newest_green") if isinstance(prev.get("newest_green"), dict) else {}
    if stamps:
        green_since, basis = min(stamps), "release tag"
    elif pg.get("sha") == prod and _parse_iso(pg.get("green_since")) is not None:
        green_since, basis = float(_parse_iso(pg.get("green_since")) or t), "first seen"
    else:
        green_since, basis = t, "first seen"
    age_h = max(0.0, (t - green_since) / 3600.0)
    is_in = git.is_ancestor(prod, adopted)
    doc["newest_green"] = {"sha": prod, "tags": names[:3], "green_since": _iso(green_since),
                           "green_since_basis": basis, "age_h": round(age_h, 2)}
    if is_in is None:
        doc["problems"].append(f"cannot tell whether {prod[:12]} is in {adopted[:12]}")
        return _finish(doc, "UNMEASURED", t, prev)
    doc["adopted"]["contains_newest_green"] = is_in
    kinds: list[str] = []
    if is_in:
        doc["releases_behind"] = 0
    else:
        missing = _tags(git, not_in=adopted)
        doc["releases_behind"] = max(1, len(missing))
        doc["releases_behind_basis"] = ("local release/* tags not in the adopted code (the gate "
                                        "fetches tags only when production is absent, so this "
                                        "can undercount); at least 1 when production is unadopted")
        if age_h > BEHIND_MAX_H:
            kinds.append("BEHIND")
            g = doc["context"]["guard"]
            hbs = doc["context"]["heartbeat"]
            doc["problems"].append(
                f"green release {prod[:12]} ({basis} {_iso(green_since)}) unadopted for "
                f"{age_h:.1f}h > {BEHIND_MAX_H:.0f}h; box runs {adopted[:12]}, "
                f"{doc['releases_behind']} green release(s) behind. Last adopt guard: "
                f"{g.get('step') or '?'} {g.get('decision') or 'NO REPORT'}"
                f"{' -- ' + g['reason'][:200] if g.get('reason') else ''}; adopter stage "
                f"{hbs.get('stage') or '?'} (exit {hbs.get('exit_code')})")
    rc, out = git.run("diff", "--name-only", "--no-renames", prod, tip)
    if rc != 0:
        doc["problems"].append(f"cannot diff {prod[:12]}..{tip[:12]}")
        doc["kinds"] = kinds
        return _finish(doc, "RED" if kinds else "UNMEASURED", t, prev)
    unreleased = _code_paths([ln.strip() for ln in out.splitlines() if ln.strip()])
    doc["unreleased_code_paths"] = len(unreleased)
    if unreleased:
        first = _first_unreleased_code_at(git, prod, tip)
        if first is None:
            first = git.commit_time(tip)
        wait_h = None if first is None else max(0.0, (t - first) / 3600.0)
        doc["unreleased_since"] = None if first is None else _iso(first)
        doc["unreleased_age_h"] = None if wait_h is None else round(wait_h, 2)
        if wait_h is not None and wait_h > NO_GREEN_MAX_H:
            kinds.append("NO_GREEN_RELEASE")
            doc["problems"].append(
                f"LIVE {tip[:12]} carries {len(unreleased)} code path(s) no green release "
                f"covers, the oldest landed {wait_h:.1f}h ago > {NO_GREEN_MAX_H:.0f}h; the "
                f"newest green release is {prod[:12]} ({age_h:.1f}h old). CI is not promoting")
    doc["kinds"] = kinds
    return _finish(doc, "RED" if kinds else "GREEN", t, prev)


def _finish(doc: dict[str, Any], verdict: str, t: float, prev: dict[str, Any]) -> dict[str, Any]:
    doc["verdict"] = verdict
    kinds = doc.get("kinds") or ([] if verdict == "GREEN" else [verdict])
    doc["kinds"] = kinds
    doc["kind"] = "+".join(kinds) if kinds else "GREEN"
    doc["reason"] = "; ".join(doc["problems"]) if doc["problems"] else (
        "the adopted code contains the newest green release" if
        (doc.get("adopted") or {}).get("contains_newest_green")
        else "the newest green release is inside its adoption window")
    # The contract stamp: refreshed only on GREEN, carried through RED and UNMEASURED.
    doc["green_at"] = _iso(t) if verdict == "GREEN" else prev.get("green_at")
    return doc


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(out)


def refresh(now: float | None = None, *, out: Path = OUT, root: Path = ROOT,
            force: bool = False) -> dict[str, Any]:
    """Re-measure when the report is older than REMEASURE_MIN, write it. NEVER RAISES: a crash is
    recorded as an UNMEASURED report, never a missing one that reads as nothing wrong."""
    t = time.time() if now is None else now
    prev = _read_json(out) or {}
    at = _parse_iso(prev.get("measured_at"))
    if not force and at is not None and 0 <= (t - at) / 60.0 < REMEASURE_MIN:
        return prev
    try:
        doc = measure(t, root=root, prev=prev)
    except Exception as exc:
        doc = _finish({"measured_at": _iso(t), "problems": [
            f"measurement crashed: {type(exc).__name__}: {str(exc)[:200]}"]}, "UNMEASURED", t, prev)
    with contextlib.suppress(OSError):
        write(doc, out)
    return doc


def check(now: float, path: Path = OUT) -> dict[str, Any]:
    """The heartbeat check over the report. Missing, unreadable, unstamped, older than
    REPORT_MAX_MIN or anything but GREEN fails; missing or stale reads UNMEASURED, never GREEN."""
    doc = _read_json(path)
    at = _parse_iso((doc or {}).get("measured_at"))
    age = None if at is None else (now - at) / 60.0
    if doc is None or age is None or age > REPORT_MAX_MIN or age < -5:
        verdict, kind = "UNMEASURED", "UNMEASURED"
        reason = (f"{path.name} absent or unreadable" if doc is None else
                  f"{path.name} measured_at {(doc or {}).get('measured_at')!r} is not a reading "
                  f"inside {REPORT_MAX_MIN:.0f} min")
    else:
        verdict = str(doc.get("verdict") or "UNMEASURED")
        kind = str(doc.get("kind") or verdict)
        reason = str(doc.get("reason") or "")
    if verdict not in ("GREEN", "RED", "UNMEASURED"):
        verdict, kind = "UNMEASURED", "UNMEASURED"
    ng = (doc or {}).get("newest_green") or {}
    return {"verdict": verdict, "kind": kind, "reason": reason[:500],
            "age_min": None if age is None else round(age, 1),
            "releases_behind": (doc or {}).get("releases_behind"),
            "newest_green": str(ng.get("sha") or "")[:12] or None,
            "adopted": str(((doc or {}).get("adopted") or {}).get("sha") or "")[:12] or None,
            "fail": verdict != "GREEN"}
