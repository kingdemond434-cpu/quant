"""The box adopts on its own: only audited code, never near a trade window, and back out on its own.

THE GAP (2026-10-28). MT5-AdoptRelease already lands the branch in place, seals it and recycles the
gateway, hourly, with nobody at a keyboard. It sat DISABLED and adoption went back to a laptop
sitting, because the one authority it consulted was "CI is green". The desk's own rule is stronger
-- an auditor HOLD beats green CI -- and the adopter could not see a HOLD, could land code on top
of the gold Asia bracket, and had no way back when the new code would not run. The night of 10-27
the laptop session stalled, the adopt did not happen, and E8, FTMO and Fusion missed the gold trade
the fix was for. A deploy path that needs a person is the outage.

WHAT THIS ADDS TO Adopt-And-Seal.ps1, IN ITS ORDER

    pre        after the release gate chose a target, before anything is written: the BROKER
               clock is outside every gold window's blackout (with the margin a cold adoption
               needs), every governed path the adoption would change carries a blob an auditor
               CLEAR row vouches for and no HOLD row revokes, and none of it is a blob an earlier
               run rolled back.                                      exit 0 go / 10 hold
    smoke      after the in-place adoption, before the seal: every live entry module imports
               (gateway, resident, E8 executor, E8 gold, FTMO follower) and prestart_check.py,
               when the box has one, says start.                     exit 0 ok / 11 unhealthy
    blackout   the same clock test, re-asked just before the seal.   exit 0 clear / 10 inside
    health     after the seal and the recycle: the release identity allows new risk under the
               new seal; a resident gateway STARTED AFTER the recycle stamps that it loaded that
               seal and finished a pass (desks/mt5/data/GATEWAY_LOADED.json, written by
               gateway_resident.py -- the state file alone was rewritten by passes still in flight
               on the old code); and every live lane task that ran since exited 0.
                                                                     exit 0 / 11
    rollback   on any failure after the first byte is written: a new-risk hold goes up FIRST
               (libs/ops/new_risk_hold -- every lane stops opening, management keeps running),
               then every code path, the judge manifest and RELEASE.json go back to the
               pre-adoption commit's bytes in place, including half-written and newly created
               files, are staged by name and committed; the rolled-back blobs are recorded so the
               next hour does not adopt them again. The hold comes down only when a health check
               against the restored seal passes (right after the rollback, or the one-look `heal`
               at the start of a later run); a rollback that fails leaves it up and pages.
                                                                     exit 0 / 12

WHY THE PRE-ADOPTION COMMIT IS A SAFE PLACE TO GO BACK TO. It is the code the gateway was running
under an accepted seal a minute earlier. Restoring its RELEASE.json with its code makes
`release.accepts` answer exactly as it did then -- the diff from the sealed code_sha touches state
only -- so no new seal is minted for a rollback and the record's signature is the original one.

WHAT IS GOVERNED. Every CODE path (`release.accepts`' own classification, plus any script by its
extension wherever it sits) and every non-evidence STATE path the adoption would take from origin
-- money-path config such as sleeves.json, ALLOCATOR_SOVEREIGN.json or this guard's own
ADOPT_POLICY.json sits under desks/mt5/data and would otherwise ride in uncleared. Only evidence
directories (reports, logs, docs, web), the box's own runtime records, and paths whose target blob
equals what the box already holds are exempt.

AUDITOR ROWS. desks/mt5/data/ADOPT_CLEARS.jsonl, one JSON object per line:

    {"commit": <40 hex>, "verdict": "CLEAR"|"HOLD", "report": "reports/audit/....md",
     "report_sha256": <64 hex>?, "paths": {<repo path>: <40-hex object> | null},
     "lifts_rollback": [<40 hex>]?}

`paths` is what the auditor read: the object of every path that commit changes against the branch
it was cut from (null = deleted); `adopt_guard.py clear-row` writes it for CLEAR and HOLD alike, so
the box never needs the audited commit itself. A (path, blob) is vouched for only when some CLEAR
row lists it, no HOLD row lists the same (path, blob), and no HOLD row names the CLEAR row's
commit -- so a HOLD on any PR revokes its blobs even under a broader CLEAR row that also listed
them. The file is read from the TARGET commit's own history and must be append-only there.

WHAT IT DOES NOT CLOSE, SAID ONCE. Anyone who can commit to the live branch can append a CLEAR row,
exactly as anyone who can commit can change the code. A blob cleared in one commit is accepted in
another, so two individually cleared edits to different files can be combined without a combined
review, and a revert can bring back any blob that was ever cleared. The rollback target is the
release that was running; if the auditor has since held that release, the rollback restores it
anyway (it is what was trading a minute earlier) and the hold row only stops it being adopted
again.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.ops import new_risk_hold, release

CLEARS_REL = "desks/mt5/data/ADOPT_CLEARS.jsonl"
POLICY_REL = "desks/mt5/data/ADOPT_POLICY.json"
ROLLBACKS_REL = "desks/mt5/reports/ADOPT_ROLLBACKS.jsonl"
REPORT_REL = "desks/mt5/reports/ADOPT_GUARD.json"
GATEWAY_STATE_REL = "desks/mt5/data/gateway_state.json"
GATEWAY_LOADED_REL = "desks/mt5/data/GATEWAY_LOADED.json"
MANIFEST_REL = "desks/mt5/data/IMMUTABLE_MANIFEST.json"
PAGE_REL = "data/PRINCIPAL_ACTION.md"
BY = "adopt_guard"

#: Directories that hold evidence the box or a session measured, never an input that steers money.
EVIDENCE_PREFIXES: tuple[str, ...] = (
    "desks/mt5/reports/",
    "desks/mt5/logs/",
    "reports/",
    "logs/",
    "docs/",
    "web/",
)
#: The box's own runtime records: written by the running desk, never steering it from origin.
BOX_RUNTIME: frozenset[str] = frozenset(
    {
        release.RELEASE_REL,
        CLEARS_REL,
        GATEWAY_STATE_REL,
        GATEWAY_LOADED_REL,
        "desks/mt5/data/account_state.json",
        "desks/mt5/data/decision_ledger.jsonl",
        "desks/mt5/data/live_ledger.jsonl",
        "desks/mt5/data/live_ledger_corrections.jsonl",
        "desks/mt5/data/order_intents.jsonl",
        "desks/mt5/data/placement_interlock.json",
        "desks/mt5/data/regime_state.json",
        "desks/mt5/data/release_identity.json",
        "desks/mt5/data/tier_s/box_evidence.json",
        "desks/mt5/data/tier_s/door_verdicts.json",
        "desks/mt5/data/tier_s/live_door.json",
    }
)
#: Files under an evidence directory that the live lanes nevertheless READ to size or choose
#: trades (adopter v2 audit, probe 7s): e8_book.py sizes from UNIVERSAL_SURVIVORS.json and
#: fill_surface.py prices from markout.json. Governed like money config whatever their prefix.
MONEY_EVIDENCE: frozenset[str] = frozenset(
    {
        "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
        "desks/mt5/reports/markout.json",
    }
)
SCRIPT_SUFFIXES = (".py", ".ps1", ".psm1", ".cmd", ".bat", ".sh", ".mq5", ".mqh")

#: The gold windows, in BROKER hours (decision_core.GOLD_WINDOWS signal hours 7, 13 and 17; the
#: broker clock is New York + 7 h, so gold Asia is 04:00Z in US summer and 05:00Z in winter --
#: a UTC constant would have opened the window to adoption from 2026-11-01). Thirty minutes each
#: side of the placement, which the FTMO and Fusion followers trail inside.
DEFAULT_BLACKOUTS: list[dict[str, str]] = [
    {"window": "asia", "from": "06:30", "to": "07:30"},
    {"window": "london_am", "from": "12:30", "to": "13:30"},
    {"window": "afternoon", "from": "16:30", "to": "17:30"},
]
DEFAULT_SMOKE: list[str] = [
    "desks/mt5/mt5desk/gateway.py",
    "desks/mt5/research/gateway_resident.py",
    "desks/mt5/prop/e8_executor.py",
    "desks/mt5/prop/e8_gold.py",
    "desks/mt5/prop/ftmo_follower.py",
]
DEFAULT_POLICY: dict[str, Any] = {
    "blackouts_broker": DEFAULT_BLACKOUTS,
    "start_margin_min": 120,
    "health_wait_s": 600,
    "health_poll_s": 15,
    "gateway_alive_s": 300,
    "smoke_files": DEFAULT_SMOKE,
    "prestart": ["desks/mt5/scripts/prestart_check.py", "desks/mt5/prestart_check.py"],
    "lane_tasks": ["E8-Executor", "E8-Gold", "MT5-FTMO-Follower", "MT5-Gateway"],
    #: The task that runs each gold lane (gold_oco's lane names), for box-switch verification.
    "gold_lane_tasks": {
        "e8": ["E8-Gold"],
        "fusion": ["MT5-Gateway"],
        "ftmo": ["MT5-FTMO-Follower"],
    },
}

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPORT = re.compile(r"^(/mnt/project-files/)?reports/audit/\S+\.md$")

GO, HOLD, ERROR, UNHEALTHY, ROLLBACK_FAILED = 0, 10, 2, 11, 12


class GuardError(RuntimeError):
    """Something the guard needed could not be read; the adopter keeps the running release."""


# ------------------------------------------------------------------------------------------ git
def _run(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False, timeout=300
    )


def _git(root: Path, *args: str) -> str:
    p = _run(root, *args)
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "replace").strip()[:300]
        raise GuardError(f"git {' '.join(args[:3])} failed: {err}")
    return p.stdout.decode("utf-8", "replace")


def _rev(root: Path, spec: str) -> str:
    out = _git(root, "rev-parse", "--verify", f"{spec}^{{commit}}").strip()
    if not HEX40.match(out):
        raise GuardError(f"cannot resolve {spec!r}")
    return out


def _show(root: Path, commit: str, rel: str) -> bytes | None:
    p = _run(root, "show", f"{commit}:{rel}")
    return p.stdout if p.returncode == 0 else None


def _tree(root: Path, commit: str) -> dict[str, str]:
    """Every tracked path's object at `commit` -- blobs, symlinks and gitlinks alike, so a gitlink
    can never stand where a cleared deletion was -- in one git call."""
    out = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit)
    objs: dict[str, str] = {}
    for rec in out.split("\0"):
        if not rec:
            continue
        meta, _, path = rec.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] in ("blob", "commit"):
            objs[path] = parts[2]
    return objs


def _changed(root: Path, a: str, b: str) -> list[str]:
    out = _git(root, "diff", "--no-renames", "--name-only", "-z", a, b)
    return sorted({p for p in out.split("\0") if p})


def is_code(rel: str) -> bool:
    """`release.accepts`' classification, plus any script by its extension wherever it sits."""
    if release.is_build_artifact(rel):
        return False
    if rel.lower().endswith(SCRIPT_SUFFIXES):
        return True
    return rel not in release.NON_CODE and not release.is_state_path(rel)


def is_governed_state(rel: str) -> bool:
    """A non-code path that still steers the desk when origin changes it."""
    if rel in MONEY_EVIDENCE:
        return True
    return (
        not is_code(rel)
        and not release.is_build_artifact(rel)
        and rel not in BOX_RUNTIME
        and not rel.startswith(EVIDENCE_PREFIXES)
    )


def governed_delta(root: Path, sealed: str, target: str, head: str = "HEAD") -> list[str]:
    """Every path this adoption would change on the box that needs an auditor's word.

    CODE: every code path whose target object differs from the LAST SEALED release's -- never
    from HEAD's: code that reached the box branch without a seal (a box session's commit) is
    exactly what the seal is about to vouch for, so it needs a CLEAR like any other (adopter v2
    audit, probe 16). STATE: changed by origin since the box and origin diverged and NOT changed
    by the box in that time (Adopt-Release keeps the box's copy of those), where the target's
    object differs from what the box holds.
    """
    head = _rev(root, head)
    mb = _git(root, "merge-base", head, target).strip()
    box_changed = set(_changed(root, mb, head)) if HEX40.match(mb) else set()
    origin_changed = set(_changed(root, mb, target)) if HEX40.match(mb) else set()
    t_tree, h_tree = _tree(root, target), _tree(root, head)
    code = {p for p in _changed(root, sealed, target) if is_code(p)}
    state = {
        p
        for p in origin_changed - box_changed
        if is_governed_state(p) and t_tree.get(p) != h_tree.get(p)
    }
    return sorted(code | state)


# --------------------------------------------------------------------------------------- policy
def load_policy(root: Path) -> dict[str, Any]:
    """Defaults, widened by desks/mt5/data/ADOPT_POLICY.json. The file can ADD blackouts, smoke
    files, prestart checks and lane tasks and lengthen waits; it can never remove a default (the
    file is governed, and even a cleared edit may not quietly empty the guard)."""
    pol: dict[str, Any] = {
        k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
        for k, v in DEFAULT_POLICY.items()
    }
    f = root / POLICY_REL
    if not f.exists():
        return pol
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GuardError(f"{POLICY_REL} unreadable ({type(exc).__name__})") from exc
    if not isinstance(doc, dict):
        raise GuardError(f"{POLICY_REL} is not an object")
    for k, v in doc.items():
        if k not in DEFAULT_POLICY:
            continue
        if isinstance(DEFAULT_POLICY[k], list):
            if not isinstance(v, list):
                raise GuardError(f"{POLICY_REL}: {k} must be a list")
            pol[k] = pol[k] + [x for x in v if x not in pol[k]]
        elif isinstance(DEFAULT_POLICY[k], dict):
            # MORE task names per lane (the box's real ones), never fewer: a default can't be
            # mapped away to a task that does not exist (adopter v6 audit)
            if not isinstance(v, dict) or not all(
                isinstance(x, list) and all(isinstance(n, str) for n in x) for x in v.values()
            ):
                raise GuardError(f"{POLICY_REL}: {k} must map names to lists of task names")
            merged = {lane: list(names) for lane, names in pol[k].items()}
            for lane, names in v.items():
                merged[lane] = merged.get(lane, []) + [
                    n for n in names if n not in merged.get(lane, [])
                ]
            pol[k] = merged
        else:
            try:
                pol[k] = max(float(DEFAULT_POLICY[k]), float(v))
            except (TypeError, ValueError) as exc:
                raise GuardError(f"{POLICY_REL}: {k} must be a number") from exc
    return pol


def _minute(hhmm: str) -> int:
    m = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", str(hhmm))
    if not m:
        raise GuardError(f"blackout time {hhmm!r} is not HH:MM")
    return int(m.group(1)) * 60 + int(m.group(2))


def broker_offset_h(now: datetime) -> int:
    """The venue clock's offset from UTC at `now` (3 in US summer, 2 otherwise)."""
    try:
        from libs.regime.session_clock import utc_offset_h
    except Exception as exc:
        raise GuardError(f"broker clock unavailable ({type(exc).__name__}: {exc})") from exc
    return int(utc_offset_h(now))


def blackout(
    now: datetime,
    policy: dict[str, Any],
    *,
    margin_min: int = 0,
    offset_h: Callable[[datetime], int] = broker_offset_h,
) -> str | None:
    """The reason `now` is inside a gold window's blackout on the BROKER clock, widened backwards
    by `margin_min`; else None."""
    t = now.astimezone(UTC)
    off = offset_h(t)
    b = t + timedelta(hours=off)
    m = b.hour * 60 + b.minute
    for w in policy.get("blackouts_broker") or []:
        start, end = _minute(w["from"]) - int(margin_min), _minute(w["to"])
        span = (end - start) % 1440 or 1440
        if (m - start) % 1440 < span:
            lead = f", or within {margin_min} min before it" if margin_min else ""
            return (
                f"inside the {w.get('window', '?')} blackout {w['from']}-{w['to']} broker time "
                f"(UTC+{off}; now {b:%H:%M} broker{lead})"
            )
    return None


# --------------------------------------------------------------------------------------- clears
@dataclass
class Clear:
    commit: str
    verdict: str
    report: str
    paths: dict[str, str | None] = field(default_factory=dict)
    lifts_rollback: tuple[str, ...] = ()


def parse_clears(text: str) -> list[Clear]:
    """Fail closed: one malformed line refuses the whole file, never a silent skip."""
    rows: list[Clear] = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError as exc:
            raise GuardError(f"{CLEARS_REL}:{n} is not JSON") from exc
        if not isinstance(d, dict):
            raise GuardError(f"{CLEARS_REL}:{n} is not an object")
        commit, verdict, rep = d.get("commit"), d.get("verdict"), d.get("report")
        if not isinstance(commit, str) or not HEX40.match(commit):
            raise GuardError(f"{CLEARS_REL}:{n} commit is not 40 hex")
        if verdict not in ("CLEAR", "HOLD"):
            raise GuardError(f"{CLEARS_REL}:{n} verdict must be CLEAR or HOLD")
        if not isinstance(rep, str) or not REPORT.match(rep) or ".." in rep:
            raise GuardError(f"{CLEARS_REL}:{n} report must name reports/audit/<...>.md")
        rsha = d.get("report_sha256")
        if rsha is not None and not (isinstance(rsha, str) and HEX64.match(rsha)):
            raise GuardError(f"{CLEARS_REL}:{n} report_sha256 must be 64 hex")
        paths = d.get("paths", {})
        if not isinstance(paths, dict) or (verdict == "CLEAR" and not paths):
            raise GuardError(f"{CLEARS_REL}:{n} a CLEAR row must list the paths it read")
        for p, b in paths.items():
            if not isinstance(p, str) or not p or p.startswith("/") or ".." in p.split("/"):
                raise GuardError(f"{CLEARS_REL}:{n} bad path {p!r}")
            if b is not None and not (isinstance(b, str) and HEX40.match(b)):
                raise GuardError(f"{CLEARS_REL}:{n} object for {p} is not 40 hex or null")
        lifts = d.get("lifts_rollback", [])
        if not isinstance(lifts, list) or not all(
            isinstance(x, str) and HEX40.match(x) for x in lifts
        ):
            raise GuardError(f"{CLEARS_REL}:{n} lifts_rollback must be a list of 40-hex commits")
        rows.append(Clear(commit, verdict, rep, dict(paths), tuple(lifts)))
    return rows


def vouched(rows: Iterable[Clear]) -> set[tuple[str, str | None]]:
    """The (path, object) pairs an effective CLEAR vouches for: listed by a CLEAR row whose commit
    no HOLD names, and not listed by any HOLD row."""
    rows = list(rows)
    held_commits = {r.commit for r in rows if r.verdict == "HOLD"}
    held_pairs = {(p, b) for r in rows if r.verdict == "HOLD" for p, b in r.paths.items()}
    good = {
        (p, b)
        for r in rows
        if r.verdict == "CLEAR" and r.commit not in held_commits
        for p, b in r.paths.items()
    }
    return good - held_pairs


def lifted_rollbacks(rows: Iterable[Clear]) -> set[str]:
    rows = list(rows)
    held = {r.commit for r in rows if r.verdict == "HOLD"}
    return {
        b for r in rows if r.verdict == "CLEAR" and r.commit not in held for b in r.lifts_rollback
    }


def committed_clears(root: Path, target: str) -> list[Clear]:
    """The rows as the TARGET commit carries them, after proving no version in its history was
    edited or truncated: every earlier version must be a byte prefix of the target's."""
    if _git(root, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise GuardError(
            "shallow clone: the CLEAR record's history cannot be checked (git fetch --unshallow)"
        )
    final = _show(root, target, CLEARS_REL)
    if final is None:
        return []
    shas = _git(root, "log", "--full-history", "--format=%H", target, "--", CLEARS_REL).split()
    for sha in shas:
        for c in (sha, *_git(root, "rev-list", "--parents", "-n", "1", sha).split()[1:]):
            ver = _show(root, c, CLEARS_REL)
            if ver is not None and not final.startswith(ver):
                raise GuardError(
                    f"{CLEARS_REL} at {c[:12]} is not a prefix of the target's "
                    "copy: a row was edited or dropped"
                )
    return parse_clears(final.decode("utf-8"))


def uncovered(root: Path, paths: list[str], target: str, clears: list[Clear]) -> list[str]:
    """The governed paths whose target content no effective CLEAR vouches for."""
    ok = vouched(clears)
    tree = _tree(root, target)
    return [p for p in paths if (p, tree.get(p)) not in ok]


def clear_row(root: Path, commit: str, verdict: str, report: str, *, base: str) -> dict[str, Any]:
    """The row a lander appends for an auditor verdict on `commit` (cut from `base`): the object
    of every path the commit changes, for a HOLD as much as a CLEAR."""
    c = _rev(root, commit)
    mb = _git(root, "merge-base", c, _rev(root, base)).strip()
    tree = _tree(root, c)
    paths = {p: tree.get(p) for p in _changed(root, mb, c)}
    row: dict[str, Any] = {"commit": c, "verdict": verdict, "report": report, "paths": paths}
    parse_clears(json.dumps(row))
    return row


# ------------------------------------------------------------------------------------ rollbacks
def load_rollbacks(root: Path) -> list[dict[str, Any]]:
    """Fail closed: a garbled record could be the one that keeps bad code out."""
    f = root / ROLLBACKS_REL
    if not f.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        text = f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GuardError(f"{ROLLBACKS_REL} unreadable ({type(exc).__name__})") from exc
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError as exc:
            raise GuardError(f"{ROLLBACKS_REL}:{n} is not JSON") from exc
        if not (isinstance(d, dict) and isinstance(d.get("blobs"), dict)):
            raise GuardError(f"{ROLLBACKS_REL}:{n} carries no blobs map")
        out.append(d)
    return out


def rolled_back_hits(
    root: Path,
    paths: list[str],
    target: str,
    clears: list[Clear],
    rollbacks: list[dict[str, Any]],
) -> list[str]:
    """Governed paths in the target that still carry an object an earlier run rolled back,
    unless an effective CLEAR row names that rollback in `lifts_rollback`."""
    lifted = lifted_rollbacks(clears)
    tree = _tree(root, target)
    hits: list[str] = []
    for p in paths:
        want = tree.get(p)
        for rb in rollbacks:
            if rb.get("bad") in lifted:
                continue
            if p in rb["blobs"] and rb["blobs"][p] == want:
                hits.append(f"{p} (rolled back from {str(rb.get('bad'))[:12]})")
                break
    return hits


# ------------------------------------------------------------------------------------- report
def write_report(root: Path, doc: dict[str, Any]) -> None:
    """Best-effort: a lost diagnostic never changes what the adopter does."""
    try:
        f = root / REPORT_REL
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            json.dumps({"at": datetime.now(UTC).isoformat(), **doc}, indent=1, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def page(root: Path, message: str) -> None:
    """Escalate through the desk's one human channel (the pager sends line 1). Best-effort."""
    try:
        from libs.ops import principal_page

        principal_page.page(f"ADOPT GUARD: {message}", marker="ADOPT GUARD:", path=root / PAGE_REL)
    except Exception:
        pass


def sealed_code_sha(root: Path, commit: str = "HEAD") -> str:
    raw = _show(root, commit, release.RELEASE_REL)
    try:
        sha = str(json.loads(raw or b"{}").get("code_sha") or "")
    except ValueError as exc:
        raise GuardError("RELEASE.json unreadable") from exc
    if not HEX40.match(sha):
        raise GuardError("RELEASE.json names no code_sha")
    return sha


def pre(
    root: Path,
    target: str,
    *,
    now: datetime | None = None,
    offset_h: Callable[[datetime], int] = broker_offset_h,
) -> tuple[int, dict[str, Any]]:
    pol = load_policy(root)
    now = now or datetime.now(UTC)
    why = blackout(now, pol, margin_min=int(pol["start_margin_min"]), offset_h=offset_h)
    if why:
        return HOLD, {"decision": "HOLD_BLACKOUT", "reason": why}
    target = _rev(root, target)
    sealed = sealed_code_sha(root)
    clears = committed_clears(root, target)
    delta = governed_delta(root, sealed, target)
    miss = uncovered(root, delta, target, clears)
    if miss:
        return HOLD, {
            "decision": "HOLD_UNAUDITED",
            "target": target,
            "sealed": sealed,
            "reason": f"{len(miss)} of {len(delta)} governed path(s) carry content no "
            f"effective auditor CLEAR vouches for",
            "uncovered": miss[:50],
        }
    hits = rolled_back_hits(root, delta, target, clears, load_rollbacks(root))
    if hits:
        return HOLD, {
            "decision": "HOLD_ROLLED_BACK",
            "target": target,
            "sealed": sealed,
            "reason": "the target still carries content an earlier run rolled back",
            "rolled_back": hits[:50],
        }
    return GO, {
        "decision": "GO",
        "target": target,
        "sealed": sealed,
        "reason": f"{len(delta)} governed path(s), every one auditor CLEAR",
        "governed_paths": delta[:50],
        # adopter v3 audit MF3: the hold costs entries, so it goes up only when this adoption
        # changes something governed: code against the seal, steering state, or code a box
        # session committed on HEAD that the target rewrites (v5 audit MF3c)
        "needs_hold": bool(delta)
        or any(is_code(p) for p in _changed(root, _rev(root, "HEAD"), target)),
    }


# -------------------------------------------------------------------------------------- smoke
def _python() -> list[str]:
    return [sys.executable]


SMOKE_SNIPPET = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location(sys.argv[2], sys.argv[1])\n"
    "mod = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(mod)\n"
)

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def _default_runner(*a: Any, **k: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(*a, **k, check=False)


def smoke(root: Path, *, runner: Runner | None = None) -> tuple[int, dict[str, Any]]:
    """Import every live entry file the way its task runs it (cwd desks/mt5, never as __main__),
    then run prestart_check.py if the box has one. Each in its own interpreter."""
    pol = load_policy(root)
    run = runner or _default_runner
    desk = root / "desks" / "mt5"
    bad: list[str] = []
    ran: list[str] = []
    for i, rel in enumerate(pol["smoke_files"]):
        f = root / rel
        if not f.exists():
            bad.append(f"{rel}: missing")
            continue
        p = run(
            [*_python(), "-c", SMOKE_SNIPPET, str(f), f"adopt_smoke_{i}"],
            cwd=str(desk),
            capture_output=True,
            text=True,
            timeout=180,
        )
        ran.append(rel)
        if p.returncode != 0:
            tail = (p.stderr or p.stdout or "").strip().splitlines()[-3:]
            bad.append(f"{rel}: import failed: {' | '.join(tail)}")
    for rel in pol["prestart"]:
        f = root / rel
        if not f.exists():
            continue
        p = run([*_python(), str(f)], cwd=str(desk), capture_output=True, text=True, timeout=300)
        ran.append(rel)
        if p.returncode != 0:
            tail = (p.stdout or p.stderr or "").strip().splitlines()[-6:]
            bad.append(f"{rel}: DO NOT START (rc {p.returncode}): {' | '.join(tail)}")
    if bad:
        return UNHEALTHY, {
            "decision": "SMOKE_FAILED",
            "reason": bad[0],
            "failures": bad,
            "ran": ran,
        }
    return GO, {"decision": "SMOKE_OK", "ran": ran}


# ------------------------------------------------------------------------------------- health
def _mtime(root: Path, rel: str) -> datetime | None:
    try:
        return datetime.fromtimestamp((root / rel).stat().st_mtime, UTC)
    except OSError:
        return None


def gateway_alive(root: Path, *, now: datetime | None = None) -> bool:
    at = _mtime(root, GATEWAY_STATE_REL)
    limit = float(load_policy(root)["gateway_alive_s"])
    return at is not None and ((now or datetime.now(UTC)) - at).total_seconds() < limit


def _identity(root: Path) -> dict[str, Any]:
    desk = root / "desks" / "mt5"
    for p in (str(root), str(desk)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from mt5desk import release_identity as ri

    doc: dict[str, Any] = ri.verdict(root, write=False).to_dict()
    return doc


def _when(v: object) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def loaded_problem(
    root: Path, sealed: str, since: datetime, *, running_ok: bool = False
) -> str | None:
    """None when a gateway process started after `since` stamps the `sealed` release and a
    finished pass; else what is missing. The stamp is written by the resident and by every
    MT5-Gateway pass process (run_gateway_loop), whichever runs the gateway.

    `running_ok` (heal only, adopter v3 audit MF2): a process that started BEFORE `since` also
    passes when it runs the `sealed` release and finished a pass after `since` -- nothing new was
    adopted, so nothing needs reloading, and a resident never restarts on its own."""
    try:
        doc = json.loads((root / GATEWAY_LOADED_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "no gateway load stamp (GATEWAY_LOADED.json) yet"
    started, passed = _when(doc.get("started_at")), _when(doc.get("last_pass_at"))
    if running_ok and doc.get("release_sha") == sealed and passed is not None and passed > since:
        return None
    if started is None or started <= since:
        return f"no resident gateway has started since the recycle (stamp {doc.get('started_at')})"
    if doc.get("release_sha") != sealed:
        return (
            f"the resident started under release {str(doc.get('release_sha'))[:12]}, "
            f"not {sealed[:12]}"
        )
    if passed is None or passed <= started:
        return "the restarted resident has not finished a pass yet"
    return None


def _task_info(name: str) -> dict[str, Any] | None:
    """State, last run (UTC) and result of a scheduled task; None when it does not exist or
    cannot be read (not Windows, no PowerShell)."""
    if os.name != "nt":
        return None
    cmd = (
        f"$t = Get-ScheduledTask -TaskName '{name}' -ErrorAction Stop; "
        f"$i = Get-ScheduledTaskInfo -TaskName '{name}' -ErrorAction Stop; "
        "[pscustomobject]@{state=[string]$t.State; "
        "last=$i.LastRunTime.ToUniversalTime().ToString('o'); result=[int64]$i.LastTaskResult}"
        " | ConvertTo-Json -Compress"
    )
    try:
        p = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        doc: dict[str, Any] = json.loads(p.stdout) if p.returncode == 0 else {}
        return doc or None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


#: Task Scheduler results that mean "not finished", not "failed" (adopter v4 audit MF1): a task
#: that is running right now reads 267009 (SCHED_S_TASK_RUNNING), one that never ran 267011.
NOT_FINISHED = frozenset({267009, 267011})


def task_verdict(info: dict[str, Any] | None, since: datetime) -> str:
    """UNMEASURED, DISABLED, NOT_RUN_SINCE, RUNNING, OK or FAILED <result> for one lane task."""
    if not info:
        return "UNMEASURED"
    if str(info.get("state")) == "Disabled":
        return "DISABLED"
    last = _when(info.get("last"))
    if last is None or last <= since:
        return "NOT_RUN_SINCE"
    result = int(info.get("result") or 0)
    if result in NOT_FINISHED or str(info.get("state")) == "Running":
        return "RUNNING"
    return "OK" if result == 0 else f"FAILED {result}"


def lane_problems(
    root: Path,
    since: datetime,
    task_info: Callable[[str], dict[str, Any] | None] = _task_info,
    names: Iterable[str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Each live lane task that has FINISHED a run since `since` must have exited 0. A lane that
    is absent, disabled, running or has not run yet is reported, never failed (its next run is
    under the new code)."""
    bad: list[str] = []
    seen: dict[str, str] = {}
    for name in load_policy(root)["lane_tasks"] if names is None else names:
        seen[name] = task_verdict(task_info(name), since)
        if seen[name].startswith("FAILED"):
            bad.append(f"lane task {name} exited {seen[name][7:]} on the new release")
    return bad, seen


def health(
    root: Path,
    sealed: str,
    since: datetime,
    *,
    gateway_expected: bool,
    identity: Callable[[Path], dict[str, Any]] | None = None,
    task_info: Callable[[str], dict[str, Any] | None] = _task_info,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    wait_s: float | None = None,
    running_ok: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Poll until (a) the release identity allows new risk under the seal of `sealed`, (b) when
    a gateway is expected, a resident started after `since` stamps that seal and a finished pass,
    and (c) no live lane task that ran since `since` failed. Unhealthy when the wait runs out
    (policy health_wait_s, or `wait_s` for a single look)."""
    pol = load_policy(root)
    ident_fn = identity or _identity
    wait = float(pol["health_wait_s"]) if wait_s is None else float(wait_s)
    deadline = clock() + timedelta(seconds=wait)
    while True:
        why: list[str] = []
        try:
            v = ident_fn(root)
        except Exception as exc:
            v = {"verdict": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}
        last: dict[str, Any] = {
            "identity": {
                k: v.get(k)
                for k in ("verdict", "running_sha", "release_sha", "allows_new_risk", "reason")
            }
        }
        if not (
            v.get("verdict") == "OK" and v.get("allows_new_risk") and v.get("release_sha") == sealed
        ):
            why.append(f"release identity: {v.get('verdict')} -- {v.get('reason')}")
        if gateway_expected:
            gp = loaded_problem(root, sealed, since, running_ok=running_ok)
            last["gateway"] = gp or "loaded the new release and passed"
            if gp:
                why.append(f"gateway: {gp}")
        else:
            last["gateway"] = "NOT_EXPECTED (not running before the run and its task is off)"
        lanes_bad, lanes = lane_problems(root, since, task_info)
        last["lanes"] = lanes
        why.extend(lanes_bad)
        if not why:
            return GO, {"decision": "HEALTHY", **last}
        if lanes_bad or clock() >= deadline:
            return UNHEALTHY, {"decision": "UNHEALTHY", "reason": why[0], "failures": why, **last}
        sleep(float(pol["health_poll_s"]))


# ----------------------------------------------------------------------------------- rollback
def _write_in_place(f: Path, data: bytes) -> None:
    """Rewrite CONTENTS without unlinking the directory entry (Adopt-Release's NTFS lesson)."""
    if f.exists():
        with f.open("r+b") as h:
            h.write(data)
            h.truncate()
            h.flush()
            os.fsync(h.fileno())
    else:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("wb") as h:
            h.write(data)


def _tracked(root: Path, rel: str) -> bool:
    return bool(_git(root, "ls-files", "--", rel).strip())


def _untracked(root: Path, rel: str) -> bool:
    return (root / rel).exists() and not _tracked(root, rel)


def rollback(root: Path, to: str, *, bad: str, why: str) -> tuple[int, dict[str, Any]]:
    """Put every code path, the judge manifest and RELEASE.json back to `to`'s bytes -- committed
    changes, half-written files and files the adoption created alike -- and commit what is staged
    as one commit on the branch. `to` is the commit HEAD was before this run adopted. Never
    touches the work tree beyond those paths (no reset --hard, clean or stash; leftover staged
    entries are unstaged, index only); state is the box's and is left alone."""
    to = _rev(root, to)
    head = _rev(root, "HEAD")
    bad = _rev(root, bad)
    branch = _git(root, "symbolic-ref", "-q", "HEAD").strip()
    if not branch:
        return ROLLBACK_FAILED, {"decision": "ROLLBACK_FAILED", "reason": "HEAD is detached"}
    keep = {MANIFEST_REL, release.RELEASE_REL}

    def ours(p: str) -> bool:
        return is_code(p) or p in keep

    committed = [p for p in _changed(root, to, head) if ours(p)]
    dirty = [
        p for p in _git(root, "diff", "--name-only", "-z", "HEAD").split("\0") if p and ours(p)
    ]
    to_tree, bad_tree = _tree(root, to), _tree(root, bad)
    created = [
        p
        for p in _changed(root, to, bad)
        if ours(p) and p not in to_tree and p in bad_tree and _untracked(root, p)
    ]
    paths = sorted(set(committed) | set(dirty) | set(created))
    if not paths:
        return GO, {"decision": "NOTHING_TO_ROLL_BACK", "to": to, "bad": bad}
    head_tree = _tree(root, head)
    blobs_bad = {p: bad_tree.get(p) or head_tree.get(p) for p in paths if is_code(p)}
    failed: list[str] = []
    for p in paths:
        f = root / p
        data = _show(root, to, p)
        try:
            if data is None:
                if f.exists():
                    f.unlink()
            else:
                _write_in_place(f, data)
        except OSError as exc:
            failed.append(f"{p}: {type(exc).__name__}: {exc}")
    if failed:
        return ROLLBACK_FAILED, {
            "decision": "ROLLBACK_FAILED",
            "reason": failed[0],
            "failures": failed,
        }
    stage = [p for p in paths if (root / p).exists() or _tracked(root, p)]
    if stage:
        _git(root, "add", "-A", "--", *stage)
    for guard in ("scripts/moneypath_precommit_guard.py", "scripts/check_protected_records.py"):
        g = root / guard
        if g.exists():
            gp = subprocess.run(
                [*_python(), str(g)],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
            if gp.returncode != 0:
                return ROLLBACK_FAILED, {
                    "decision": "ROLLBACK_FAILED",
                    "reason": f"{guard} refused (rc {gp.returncode})",
                    "output": (gp.stdout + gp.stderr)[-800:],
                }
    staged = [p for p in _git(root, "diff", "--cached", "--name-only", "-z").split("\0") if p]
    # A partial adoption can leave its own chunk-staged entries in the index. They are unstaged
    # (index only: the files on disk are left exactly as they are), so the commit below carries
    # the rollback alone; anything still staged after that is refused.
    leftover = sorted(set(staged) - set(paths))
    if leftover:
        _git(root, "reset", "-q", "--", *leftover)
        staged = [p for p in _git(root, "diff", "--cached", "--name-only", "-z").split("\0") if p]
    stray = sorted(set(staged) - set(paths))
    if stray:
        return ROLLBACK_FAILED, {
            "decision": "ROLLBACK_FAILED",
            "reason": f"index carries paths the rollback did not write: {stray[:6]}",
        }
    tree = _git(root, "write-tree").strip()
    left = [p for p in _changed(root, to, tree) if ours(p)]
    left += [p for p in created if (root / p).exists()]
    if left:
        return ROLLBACK_FAILED, {
            "decision": "ROLLBACK_FAILED",
            "reason": f"{len(left)} path(s) still differ from {to[:12]}",
            "left": left[:20],
        }
    commit = head
    if tree != _git(root, "rev-parse", f"{head}^{{tree}}").strip():
        msg = f"Roll back release {bad[:12]} to {to[:12]} (adopt_guard, unattended)\n\n{why}\n"
        commit = _git(root, "commit-tree", tree, "-p", head, "-m", msg).strip()
        _git(root, "update-ref", branch, commit, head)
    row = {
        "at": datetime.now(UTC).isoformat(),
        "bad": bad,
        "to": to,
        "commit": commit,
        "why": why,
        "blobs": blobs_bad,
    }
    try:
        f = root / ROLLBACKS_REL
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as h:
            h.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError as exc:
        return ROLLBACK_FAILED, {
            "decision": "ROLLBACK_FAILED",
            "commit": commit,
            "reason": f"rolled back but could not record it "
            f"({type(exc).__name__}); next hour may re-adopt",
        }
    return GO, {
        "decision": "ROLLED_BACK",
        "commit": commit,
        "to": to,
        "bad": bad,
        "paths": len(paths),
        "why": why,
    }


#: The untracked code already on disk when this guard's hold went up (box-local strays: a
#: box session's files never committed). A half-written adoption's NEW files are the ones not in
#: it; the strays themselves never keep the hold up (Desk health, 2026-10-28: 14 such files).
UNTRACKED_BASELINE_REL = "desks/mt5/data/ADOPT_UNTRACKED_BASELINE.json"


def untracked_code(root: Path) -> dict[str, str]:
    """Untracked code under the code roots -> the sha256 of its bytes ("" when unreadable)."""
    new = _git(root, "ls-files", "--others", "--exclude-standard", "--", *CODE_ROOTS)
    out: dict[str, str] = {}
    for rel in sorted({ln.strip() for ln in new.splitlines() if ln.strip()}):
        if not is_code(rel):
            continue
        try:
            out[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        except OSError:
            out[rel] = ""
    return out


def hold_new_risk(root: Path, why: str, run: str | None = None) -> bool:
    """Every lane stops OPENING (management keeps running) until a healthy run lifts it.

    Before this guard's FIRST hold goes up, the untracked code on disk is recorded: nothing has
    been written yet, so all of it predates the adoption. A hold already standing keeps the
    record it went up with (re-recording would absorb a failed adoption's new files)."""
    f = root / UNTRACKED_BASELINE_REL
    # A RECORD WITH NO HOLD OF OURS means the hold went without a lift (deleted by hand): a
    # failed adoption's files may be on disk, so the old record stands (v10 audit B7). Each lift
    # of the last hold removes the record.
    if own_hold_since(root) is None and not f.exists():
        # the hold itself never waits on this record: without it every untracked code file
        # counts as half-written (code_dirty fails closed)
        try:
            doc = {"at": datetime.now(UTC).isoformat(), "paths": untracked_code(root)}
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps(doc), encoding="utf-8")
            os.replace(tmp, f)
        except (GuardError, OSError):
            with contextlib.suppress(OSError):
                f.unlink()
    return new_risk_hold.place(why, by=BY, root=root, run=run)


def own_hold_since(root: Path) -> datetime | None:
    """When this guard's hold went up, or None when it has none (a person's hold, in its own
    file, is never ours to heal)."""
    return new_risk_hold.since(by=BY, root=root)


def loaded_since(root: Path, since: datetime) -> bool:
    """A resident gateway started after `since` (it imported whatever code was on disk then)."""
    try:
        doc = json.loads((root / GATEWAY_LOADED_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    started = _when(doc.get("started_at")) if isinstance(doc, dict) else None
    return started is not None and started > since


def lift_hold(root: Path, run: str | None = None) -> bool:
    """Lift the hold only if this guard wrote it (and, with `run`, only if that run wrote it);
    a person's hold is never touched."""
    lifted = new_risk_hold.lift(by=BY, root=root, run=run)
    if lifted and own_hold_since(root) is None:
        with contextlib.suppress(OSError):
            (root / UNTRACKED_BASELINE_REL).unlink()
    return lifted


#: The code roots Adopt-And-Seal refuses to seal over when dirty (its $releaseCodePaths).
CODE_ROOTS = (
    "desks/mt5/mt5desk",
    "desks/mt5/prop",
    "desks/mt5/research",
    "desks/mt5/policy",
    "desks/mt5/scripts",
    "libs",
    "ops",
    "scripts",
    "pyproject.toml",
)


def code_dirty(root: Path) -> list[str]:
    """Tracked code paths whose bytes on disk differ from HEAD: a half-written adoption."""
    out = _git(root, "diff", "--name-only", "--no-ext-diff", "HEAD", "--", *CODE_ROOTS)
    paths = {line.strip() for line in out.splitlines() if line.strip()}
    # a half-written adoption can also leave NEW files the lanes would import (v5 audit MF2g):
    # untracked code that was not already there when the hold went up. No readable record ->
    # every untracked code file counts (fail closed).
    # Keyed by path AND content (v10 audit B3): a stray rewritten after the record, by a
    # half-written adoption or anyone, counts.
    try:
        doc = json.loads((root / UNTRACKED_BASELINE_REL).read_text(encoding="utf-8"))
        before = {str(k): str(v) for k, v in doc["paths"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        before = {}
    paths |= {rel for rel, sha in untracked_code(root).items() if not sha or before.get(rel) != sha}
    return sorted(p for p in paths if is_code(p))
