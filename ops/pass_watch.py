"""PASS WATCH: the hourly pass's numeric checks, run by the box with no LLM, flag only on change.

THE ASK (zuck 2026-11-18 20:27Z, usage at 78% of the weekly limit): use cheaper machinery for
watching jobs and keep the expensive model for ideas. The hourly pass spent most of its tokens
re-reading the same five numbers and finding them unchanged. This script reads those numbers on
the box, compares them with its own previous run, and writes one file. The pass reads that file
and goes deeper only when `flag` is true.

    python ops/pass_watch.py            # writes desks/mt5/reports/PASS_WATCH.json, rc 0
    python ops/pass_watch.py --print    # stdout only, nothing written

INPUTS, all box-local files other organs already write (no network, no GitHub call, no LLM):

    desks/mt5/reports/process_health.json   counts, needing-attention, which names are FAILING
    desks/mt5/data/release_identity.json    is the box running the sealed release
    desks/mt5/reports/MERGE_PIPELINE.json   CI queue, last code commit on LIVE, open PR count
    desks/mt5/reports/DAILY_FILLS.json      per account, did the judged market day fill (#1314,
                                            ops/daily_fills.py). Optional until that lands: while it
                                            has never been seen it is NOT_ON_BOX, not a flag.

FLAGS (a reason string each; `flag` is true when any is present):

    UNMEASURED      an input is missing, unreadable or older than its max age. Never read as fine.
    FIRST_RUN       there is no previous state to compare with.
    LIVE_CODE       the last code commit on LIVE moved (something merged).
    RELEASE         release_identity.ok flipped, or the running or release SHA changed.
    HEALTH_NEW      a process entered FAILING / NOT_SCHEDULED / STALE / NO_ARTIFACT since the
                    last run. STALE is a feed or artifact past its contract age (a stale data
                    feed); NOT_SCHEDULED and NO_ARTIFACT are a scheduled task that did not run.
    ATTENTION_24H   a process has needed attention for 24 h or more. Raised once, on the run it
                    crosses 24 h; the full list stays in state.health.over_24h every run.
    NO_FILL         an account had no entry (or unmeasured fills) on a closed market day: a new
                    DAILY_FILLS alarm. The CRO review of 2026-11-18 found a 19-day dry spell that
                    nothing alerted on; this is the alert.
    ATTENTION_UP    needing-attention rose by ATTENTION_STEP or more.
    PIPELINE        the merge pipeline's status changed (e.g. RED to GREEN).
    QUEUE_JUMP      queued CI runs rose by QUEUE_STEP or more (a likely PR-rule breach: new PRs or
                    LIVE merged into queued PRs). Who did it still needs GitHub, so the pass checks.
    PR_SURGE        open PRs rose by PR_STEP or more since the last run (same reason).

Read-only everywhere except its own report. It never restarts, pages, merges or cancels.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desks" / "mt5" / "reports" / "PASS_WATCH.json"

INPUTS: dict[str, tuple[str, float]] = {
    # name: (path relative to ROOT, max age in minutes before it counts as UNMEASURED)
    "health": ("desks/mt5/reports/process_health.json", 150.0),
    "release": ("desks/mt5/data/release_identity.json", 150.0),
    "pipeline": ("desks/mt5/reports/MERGE_PIPELINE.json", 150.0),
}
FILLS = ("desks/mt5/reports/DAILY_FILLS.json", 180.0)
BAD_VERDICTS = ("FAILING", "NOT_SCHEDULED", "STALE", "NO_ARTIFACT")
LONG_ATTENTION_H = 24.0
ATTENTION_STEP = 3
QUEUE_STEP = 100
PR_STEP = 10


def _parse_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def _read(
    root: Path, rel: str, max_age_min: float, now: datetime
) -> tuple[dict[str, Any] | None, str | None]:
    """The file's JSON, or None and the reason it is UNMEASURED."""
    path = root / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{rel} missing"
    except (OSError, ValueError) as exc:
        return None, f"{rel} unreadable ({type(exc).__name__})"
    if not isinstance(data, dict):
        return None, f"{rel} is not a JSON object"
    at = _parse_at(data.get("at"))
    if at is None:
        return None, f"{rel} has no readable 'at'"
    age = (now - at).total_seconds() / 60.0
    if age > max_age_min:
        return None, f"{rel} is {age:.0f} min old (max {max_age_min:.0f})"
    return data, None


def measure(root: Path, now: datetime) -> tuple[dict[str, Any], list[str]]:
    """The current numbers, and an UNMEASURED reason for each input that could not be read."""
    state: dict[str, Any] = {}
    unmeasured: list[str] = []

    health, why = _read(root, *INPUTS["health"], now)
    if health is None:
        unmeasured.append(str(why))
    else:
        rows = health.get("processes")
        if not isinstance(rows, list) or not rows:
            # A zero-row read is UNMEASURED, never "0 bad" (hourly-pass miss M12).
            unmeasured.append(f"{INPUTS['health'][0]} has no process rows")
        else:
            state["health"] = {
                "at": health.get("at"),
                "n_processes": len(rows),
                "n_needing_attention": health.get("n_needing_attention"),
                "counts": health.get("counts"),
                "bad": {
                    str(r.get("name")): str(r.get("verdict"))
                    for r in rows
                    if isinstance(r, dict) and r.get("verdict") in BAD_VERDICTS
                },
            }

    release, why = _read(root, *INPUTS["release"], now)
    if release is None:
        unmeasured.append(str(why))
    else:
        state["release"] = {
            "at": release.get("at"),
            "ok": release.get("ok"),
            "running_sha": str(release.get("running_sha") or "")[:12],
            "release_sha": str(release.get("release_sha") or "")[:12],
        }

    pipeline, why = _read(root, *INPUTS["pipeline"], now)
    if pipeline is None:
        unmeasured.append(str(why))
    else:
        queue = pipeline.get("queue") or {}
        live = pipeline.get("live") or {}
        coverage = pipeline.get("coverage") or {}
        state["pipeline"] = {
            "at": pipeline.get("at"),
            "status": pipeline.get("status"),
            "queued_runs": queue.get("queued_runs"),
            "oldest_queued_min": queue.get("oldest_queued_min"),
            "last_code_commit": live.get("last_code_commit"),
            "hours_since_code": live.get("hours_since_code"),
            "open_prs": coverage.get("open_prs"),
        }

    fills, why = _read(root, *FILLS, now)
    if fills is None:
        if (root / FILLS[0]).exists():
            unmeasured.append(str(why))
        else:
            state["fills"] = {"status": "NOT_ON_BOX"}
    else:
        alarms = [a for a in fills.get("alarms") or [] if isinstance(a, dict)]
        state["fills"] = {
            "at": fills.get("at"),
            "status": fills.get("status"),
            "alarms": sorted(f"{a.get('key')}@{a.get('date')}" for a in alarms),
            "why": [str(a.get("last_error"))[:200] for a in alarms],
        }
    return state, unmeasured


def _age_h(since: Any, now: datetime) -> float | None:
    at = _parse_at(since)
    return None if at is None else (now - at).total_seconds() / 3600.0


def track_attention(prev: dict[str, Any] | None, cur: dict[str, Any], now: datetime) -> None:
    """Carry each bad process's first-seen time forward, and list those bad for 24 h or more."""
    health = cur.get("health")
    if not health:
        return
    old = ((prev or {}).get("health") or {}).get("first_seen") or {}
    first = {name: old.get(name) or now.isoformat(timespec="seconds") for name in health["bad"]}
    health["first_seen"] = first
    health["over_24h"] = sorted(
        n for n, t in first.items() if (_age_h(t, now) or 0.0) >= LONG_ATTENTION_H
    )


def _rose(prev: Any, cur: Any, step: float) -> bool:
    return isinstance(prev, (int, float)) and isinstance(cur, (int, float)) and cur - prev >= step


def compare(prev: dict[str, Any] | None, cur: dict[str, Any], unmeasured: list[str]) -> list[str]:
    """Every reason the pass should look closer this time. Empty means nothing changed."""
    reasons = [f"UNMEASURED: {u}" for u in unmeasured]
    if not prev:
        reasons.append("FIRST_RUN: no previous state to compare with")
        return reasons

    ph, ch = prev.get("health") or {}, cur.get("health") or {}
    if ph and ch:
        pbad, cbad = ph.get("bad") or {}, ch.get("bad") or {}
        if not isinstance(pbad, dict):  # a report written before verdicts were kept
            pbad = dict.fromkeys(pbad, "?")
        new_bad = sorted(n for n in cbad if n not in pbad)
        if new_bad:
            reasons.append("HEALTH_NEW: " + ", ".join(f"{n} {cbad[n]}" for n in new_bad))
        crossed = sorted(set(ch.get("over_24h") or []) - set(ph.get("over_24h") or []))
        if crossed:
            reasons.append("ATTENTION_24H: " + ", ".join(crossed))
        if _rose(ph.get("n_needing_attention"), ch.get("n_needing_attention"), ATTENTION_STEP):
            reasons.append(
                f"ATTENTION_UP: {ph.get('n_needing_attention')} -> {ch.get('n_needing_attention')}"
            )

    pr, cr = prev.get("release") or {}, cur.get("release") or {}
    if pr and cr:
        for key in ("ok", "running_sha", "release_sha"):
            if pr.get(key) != cr.get(key):
                reasons.append(f"RELEASE: {key} {pr.get(key)} -> {cr.get(key)}")

    pp, cp = prev.get("pipeline") or {}, cur.get("pipeline") or {}
    if pp and cp:
        if pp.get("last_code_commit") != cp.get("last_code_commit"):
            reasons.append(
                f"LIVE_CODE: {pp.get('last_code_commit')} -> {cp.get('last_code_commit')}"
            )
        if pp.get("status") != cp.get("status"):
            reasons.append(f"PIPELINE: {pp.get('status')} -> {cp.get('status')}")
        if _rose(pp.get("queued_runs"), cp.get("queued_runs"), QUEUE_STEP):
            reasons.append(f"QUEUE_JUMP: {pp.get('queued_runs')} -> {cp.get('queued_runs')}")
        if _rose(pp.get("open_prs"), cp.get("open_prs"), PR_STEP):
            reasons.append(f"PR_SURGE: {pp.get('open_prs')} -> {cp.get('open_prs')}")

    pf, cf = prev.get("fills") or {}, cur.get("fills") or {}
    new_alarms = sorted(set(cf.get("alarms") or []) - set(pf.get("alarms") or []))
    if new_alarms:
        reasons.append("NO_FILL: " + ", ".join(new_alarms))
    return reasons


def run(
    root: Path = ROOT, out: Path | None = None, now: datetime | None = None, write: bool = True
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    out = out or (root / "desks" / "mt5" / "reports" / "PASS_WATCH.json")
    prev: dict[str, Any] | None = None
    try:
        old = json.loads(out.read_text(encoding="utf-8"))
        prev = old.get("state") if isinstance(old, dict) else None
    except (OSError, ValueError):
        prev = None
    state, unmeasured = measure(root, now)
    pfills = (prev or {}).get("fills") or {}
    if (state.get("fills") or {}).get("status") == "NOT_ON_BOX" and pfills.get("status") not in (
        None,
        "NOT_ON_BOX",
    ):
        # It was on the box before and is gone now: that is UNMEASURED, not "no alarms".
        unmeasured.append(f"{FILLS[0]} missing (it was present last run)")
        del state["fills"]
    # Keep the last good reading of an input that is UNMEASURED this run, so one bad read does
    # not turn into a false "changed" flag on the next good one.
    for key in ("health", "release", "pipeline", "fills"):
        if key not in state and prev and key in prev:
            state[key] = prev[key]
    if "health" in state and state["health"] is not (prev or {}).get("health"):
        track_attention(prev, state, now)
    reasons = compare(prev, state, unmeasured)
    report = {
        "at": now.isoformat(timespec="seconds"),
        "flag": bool(reasons),
        "reasons": reasons,
        "state": state,
        "doc": "Read by the hourly pass: go deeper only when flag is true. ops/pass_watch.py",
    }
    if write:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(out)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--print", action="store_true", help="stdout only, write nothing")
    args = ap.parse_args(argv)
    report = run(write=not args.print)
    print(json.dumps({"flag": report["flag"], "reasons": report["reasons"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
