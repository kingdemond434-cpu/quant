"""THE DELIVERY GUARD: every Audit CLEAR is live on the box within the hour, with no Claude in the
path, or the box repairs what it can and pages (zuck 2026-11-25 20:00Z; rule E34).

WHY. Delivery stalled for 15 days (11-10..11-25) while 185 CLEAR verdicts piled up, and the only
thing that ever noticed was a Claude session reading the box -- which stops when the usage limit
runs out. This runs inside MT5-Guardian (every 15 min, SYSTEM) and needs nothing but the box.

WHAT IT READS (read only):
  * every verdict file the box holds: the inbox's verdicts/ and verdicts/done/, and the drop
    clone's verdicts/ ({"branch", "line": "AUDIT CLEAR|HOLD <sha> ..."}). A verdict's time is the
    OLDEST copy's mtime: when it first reached the box.
  * the live tree's HEAD (C:\\opt\\quant). A CLEAR is LIVE when its sha is an ancestor of HEAD.
  * per branch only the NEWEST verdict counts: an r1 superseded by r2 on the same branch is not
    owed, and a branch whose newest verdict is a HOLD owes nothing.

WHAT IT WRITES: desks/mt5/reports/DELIVERY_LEADTIME.json --
    max_clear_to_live_h     age of the oldest CLEAR not yet live (0 when none)
    behind_newest_clear_h   how far live code lags the CLEARs: the age of the oldest one it lacks
                            (the 24h tier of the same lag; 0 when nothing is owed)
    pending                 each owed CLEAR: sha, branch, age, whether the box has the object
    forge                   the release loop's own DELIVERY_LEADTIME.json, when it exists
    breach                  "CLEAR_NOT_LIVE_1H" / "LIVE_24H_BEHIND" / none

WAIVERS AND MAINTENANCE (Audit should-fixes 1-2): a committed row in DELIVERY_WAIVED.jsonl
withdraws a CLEAR that can never be live; DELIVERY_MAINTENANCE.json names tasks stopped on purpose
(honoured for at most 6h ahead), which the guard then does not restart.

WHAT IT DOES ON A BREACH (bounded, never the money path): starts MT5-AdoptRelease and
QuantForge-Loop when they are not running (Start only; IgnoreNew makes a running one a no-op), at
most once per 30 min each; names a release loop that is not connected to the drop; and pages
through the principal page when the breach shape changes, and again every 6h while it lasts.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = "delivery_guard/1"
REPORT_REL = "desks/mt5/reports/DELIVERY_LEADTIME.json"
STATE_REL = "desks/mt5/data/DELIVERY_GUARD_STATE.json"
QUANTBOX = Path(r"C:\ProgramData\QuantBox")
CLEAR_LIMIT_H = 1.0
BEHIND_LIMIT_H = 24.0
REPAIR_EVERY = timedelta(minutes=30)
#: a breach that persists is paged again this often (a page read once and lost is not enough)
REPAGE_EVERY = timedelta(hours=6)
REPAIR_TASKS = ("MT5-AdoptRelease", "QuantForge-Loop")
#: A CLEAR that can never be live (recut, abandoned, superseded under another branch name, another
#: repository's sha) is WITHDRAWN by a committed row {"sha", "why", "by"}: governed, so a waiver
#: is reviewed like code and never written by the guard itself (Audit should-fix 1).
WAIVED_REL = "desks/mt5/data/DELIVERY_WAIVED.jsonl"
#: A task stopped ON PURPOSE (a boot move): {"tasks": [...], "until": iso, "why": ...}. Honoured
#: for at most MAINT_MAX from now, so a marker left behind cannot silence the guard for long.
MAINT_REL = "desks/mt5/data/DELIVERY_MAINTENANCE.json"
MAINT_MAX = timedelta(hours=6)
_LINE = re.compile(r"^\s*AUDIT (CLEAR|HOLD) ([0-9a-f]{40})\b")

Git = Callable[[Sequence[str]], tuple[int, str]]


def verdict_dirs(quantbox: Path = QUANTBOX) -> list[Path]:
    inbox, forge = quantbox / "inbox" / "verdicts", quantbox / "forge"
    out = [inbox, inbox / "done", forge / "drop" / "verdicts"]
    try:
        cfg = json.loads((forge / "loop.json").read_text(encoding="utf-8"))
        if isinstance(cfg.get("drop"), dict) and cfg["drop"].get("checkout"):
            out.append(Path(cfg["drop"]["checkout"]) / "verdicts")
    except (OSError, ValueError, AttributeError):
        pass
    return out


def read_verdicts(dirs: Iterable[Path]) -> list[dict[str, Any]]:
    """One row per (verdict, sha, branch), at the OLDEST copy's mtime. Unreadable files skipped."""
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for d in dirs:
        try:
            files = sorted(d.glob("*.json")) if d.is_dir() else []
        except OSError:
            continue
        for f in files:
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
                m = _LINE.match(str(doc.get("line") or ""))
                at = datetime.fromtimestamp(f.stat().st_mtime, UTC)
            except (OSError, ValueError, AttributeError):
                continue
            if not m:
                continue
            key = (m.group(1), m.group(2), str(doc.get("branch") or ""))
            if key not in seen or at < seen[key]["at"]:
                seen[key] = {"verdict": key[0], "sha": key[1], "branch": key[2], "at": at,
                             "file": f.name}
    return sorted(seen.values(), key=lambda r: r["at"])


def owed(verdicts: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The newest verdict per branch, when it is a CLEAR. Pure."""
    newest: dict[str, Mapping[str, Any]] = {}
    for v in verdicts:
        b = v["branch"] or v["sha"]
        if b not in newest or v["at"] >= newest[b]["at"]:
            newest[b] = v
    return sorted((dict(v) for v in newest.values() if v["verdict"] == "CLEAR"),
                  key=lambda r: r["at"])


def assess(clears: Sequence[Mapping[str, Any]], *, has: Callable[[str], bool],
           live: Callable[[str], bool], now: datetime) -> dict[str, Any]:
    """The lead-time numbers and the breach. Pure given `has`/`live`."""
    pending, live_at = [], []
    for c in clears:
        known = has(c["sha"])
        if known and live(c["sha"]):
            live_at.append(c["at"])
            continue
        pending.append({"sha": c["sha"], "branch": c["branch"], "clear_at": c["at"].isoformat(),
                        "age_h": round((now - c["at"]).total_seconds() / 3600, 2),
                        "object_on_box": known,
                        "stage": "adopt" if known else "deliver"})
    oldest = max((p["age_h"] for p in pending), default=0.0)
    # live code is behind by the age of the oldest CLEAR it still lacks: a quiet day followed by
    # a fresh CLEAR is not "24h behind" (that CLEAR is minutes old), a CLEAR missing for a day is
    behind = oldest
    breach = [b for b, hit in (("CLEAR_NOT_LIVE_1H", oldest > CLEAR_LIMIT_H),
                               ("LIVE_24H_BEHIND", behind > BEHIND_LIMIT_H)) if hit]
    return {"max_clear_to_live_h": oldest, "behind_newest_clear_h": behind,
            "clears_owed": len(clears), "live": len(live_at), "pending_n": len(pending),
            # NOT ON THE BOX: the drop/forge never delivered it. ON THE BOX, NOT LIVE: the
            # adopter has not taken it. Different repairs, so counted apart.
            "pending_not_on_box": sum(not p["object_on_box"] for p in pending),
            "pending_not_adopted": sum(bool(p["object_on_box"]) for p in pending),
            "pending": sorted(pending, key=lambda p: -p["age_h"])[:50], "breach": breach}


def waived(root: Path) -> dict[str, str]:
    """{sha: why} from the committed waiver rows; malformed rows are ignored."""
    out: dict[str, str] = {}
    try:
        text = (root / WAIVED_REL).read_text(encoding="utf-8")
    except OSError:
        return out
    for ln in text.splitlines():
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if (isinstance(d, dict) and re.fullmatch(r"[0-9a-f]{40}", str(d.get("sha")))
                and str(d.get("why") or "").strip()):
            out[str(d["sha"])] = str(d["why"])
    return out


def in_maintenance(root: Path, now: datetime) -> set[str]:
    """The tasks a maintenance marker says were stopped on purpose, while it holds."""
    d = _read(root / MAINT_REL)
    try:
        until = datetime.fromisoformat(str(d.get("until")))
        until = until if until.tzinfo else until.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return set()
    if not now < until <= now + MAINT_MAX:
        return set()
    return {str(t) for t in d.get("tasks") or [] if isinstance(t, str)}


def _git(root: Path) -> Git:
    def run(args: Sequence[str]) -> tuple[int, str]:
        try:
            p = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(root), *args],
                               capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, str(exc)
        return p.returncode, p.stdout.strip()
    return run


def task_running(name: str) -> bool | None:
    try:
        p = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                            f"(Get-ScheduledTask -TaskName '{name}' -ErrorAction Stop).State"],
                           capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    st = p.stdout.strip()
    return None if p.returncode or not st else st == "Running"


def task_start(name: str) -> bool:
    try:
        p = subprocess.run(["schtasks.exe", "/Run", "/TN", name], capture_output=True,
                           text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0


def repairs(breach: Sequence[str], state: Mapping[str, Any], now: datetime, *,
            running: Callable[[str], bool | None],
            paused: Iterable[str] = ()) -> list[str]:
    """The tasks to start now. Pure given `running`. A task under maintenance is left alone."""
    if not breach:
        return []
    out = []
    skip = set(paused)
    started = state.get("started")
    for t in REPAIR_TASKS:
        if t in skip:
            continue
        last = started.get(t) if isinstance(started, dict) else None
        try:
            recent = bool(last) and now - datetime.fromisoformat(str(last)) < REPAIR_EVERY
        except (ValueError, TypeError):
            recent = False
        if not recent and running(t) is False:
            out.append(t)
    return out


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def run_once(root: Path, *, quantbox: Path = QUANTBOX, now: datetime | None = None,
             git: Git | None = None, running: Callable[[str], bool | None] = task_running,
             start: Callable[[str], bool] = task_start,
             page: Callable[[str], None] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    g = git or _git(root)
    rc, head = g(["rev-parse", "HEAD"])
    if rc or not re.fullmatch(r"[0-9a-f]{40}", head):
        doc: dict[str, Any] = {"schema": SCHEMA, "at": now.isoformat(), "error": "no HEAD",
                               "breach": ["UNMEASURED"]}
    else:
        w = waived(root)
        clears = [c for c in owed(read_verdicts(verdict_dirs(quantbox))) if c["sha"] not in w]
        doc = {"schema": SCHEMA, "at": now.isoformat(), "head": head,
               "waived": len(w),
               **assess(clears, has=lambda s: g(["cat-file", "-e", f"{s}^{{commit}}"])[0] == 0,
                        live=lambda s: g(["merge-base", "--is-ancestor", s, head])[0] == 0,
                        now=now)}
    loop = _read(quantbox / "forge" / "loop.json")
    doc["drop_connected"] = isinstance(loop.get("drop"), dict)
    if loop.get("state"):
        forge = _read(Path(str(loop["state"])).with_name("DELIVERY_LEADTIME.json"))
        if forge:
            doc["forge"] = {k: forge.get(k) for k in ("at", "weekly", "bottleneck") if k in forge}
    doc["adopted_by"] = _read(root / "desks/mt5/data/release_identity.json").get("adopted_by")
    st_path = root / STATE_REL
    state = _read(st_path)
    paused = in_maintenance(root, now)
    doc["maintenance"] = sorted(paused)
    todo = repairs(doc.get("breach") or [], state, now, running=running, paused=paused)
    done = {t: start(t) for t in todo}
    if done:
        state.setdefault("started", {}).update({t: now.isoformat() for t in done})
    doc["repaired"] = done
    shape = "|".join(doc.get("breach") or [])
    try:
        stale = now - datetime.fromisoformat(str(state.get("paged_at"))) > REPAGE_EVERY
    except ValueError:
        stale = True
    if shape and page is not None and (shape != state.get("paged_shape") or stale):
        oldest = (doc.get("pending") or [{}])[0]
        page(f"DELIVERY GUARD: {shape}: {doc.get('pending_n', '?')} Audit CLEAR(s) not live "
             f"({doc.get('pending_not_on_box', '?')} never reached the box, "
             f"{doc.get('pending_not_adopted', '?')} on the box but not adopted), "
             f"oldest {doc.get('max_clear_to_live_h')}h ({str(oldest.get('sha', ''))[:12]} "
             f"{oldest.get('branch', '')}); live {doc.get('behind_newest_clear_h')}h behind the "
             f"newest CLEAR; drop connected={doc['drop_connected']}; "
             f"started {sorted(done) or 'nothing'}")
        state["paged_shape"] = shape
        state["paged_at"] = now.isoformat()
    elif not shape:
        state.pop("paged_shape", None)
    for p, d in ((root / REPORT_REL, doc), (st_path, state)):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, indent=1, sort_keys=True, default=str), encoding="utf-8")
            tmp.replace(p)
        except OSError:
            pass
    return doc
