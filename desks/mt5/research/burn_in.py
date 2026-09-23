"""Burn-in telemetry: one row per hourly pass on whether the box is running the sealed code and
what that code did with money in the last day.

    python desks/mt5/research/burn_in.py

WHY (2026-09-08, the external review's fourth defect). "Release correctness is newer than its
evidence": every fix on this desk arrives with a seal and an identity check, and the only record
that the box then ran that seal for a day, a week, a month, is scattered across a log, a state
file and a dashboard tile that each say something different. The review's bar is boring: thirty
days of running-SHA == accepted-SHA with fills recorded against it. That bar needs a row per
pass, kept, so "how long has this release been trading" is a subtraction and not a memory.

WHAT IT READS (every input optional; an absent input is recorded as None, never as a pass)

    data/RELEASE.json                 the seal: code_sha
    data/release_identity.json        the gateway's own verdict: ok / verdict / running_sha /
                                      release_sha / allows_new_risk / at
    git rev-parse HEAD                what is checked out on this host now
    data/GATEWAY_PAUSED               present -> no trading this pass, by design
    data/gateway_state.json           armed, placement_pass, the rejection streak
    data/live_ledger.jsonl            closed deals in the last 24 h: n, P&L, R
    data/order_intents.jsonl          intents sent in the last 24 h
    data/stall_watch.json             free disk, the memory census
    reports/attribution_chain.json    the share of deals that walk back to an intent
    data/sync_marker.json             when the last hourly pass finished

WHAT IT WRITES

    reports/burn_in.jsonl             append-only, one row per pass
    reports/burn_in.json              the latest row plus the streak: consecutive passes whose
                                      verdict is BURNING_IN, when the streak started, days and
                                      fills inside it, against the 30-day target

VERDICTS. PAUSED when data/GATEWAY_PAUSED exists; UNMEASURED when the identity artifact is absent
or older than IDENTITY_MAX_AGE_S (a stale verdict is not a verdict); REFUSING when the identity
says new risk is refused; BURNING_IN otherwise. A pass with no verdict of its own breaks the streak
-- the streak counts evidence, not silence. Nothing here sizes, pauses or places anything.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_ROWS = BASE / "reports" / "burn_in.jsonl"
OUT = BASE / "reports" / "burn_in.json"
TARGET_DAYS = 30.0
IDENTITY_MAX_AGE_S = 2 * 3600.0
WINDOW_H = 24.0


def _read_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        for line in path.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue                                    # a torn final line, never fatal
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        pass
    return rows


def _ts(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _git_head(repo: Path) -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
                           text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def _recent(rows: list[dict], since: datetime, key: str = "time") -> list[dict]:
    out = []
    for r in rows:
        t = _ts(r.get(key))
        if t is not None and t >= since:
            out.append(r)
    return out


def observe(now: datetime | None = None, *, base: Path | None = None,
            repo: Path | None = None, head: str | None = None) -> dict:
    """One pass's row. Pure reads; `head` may be injected for hosts without git."""
    base = base or BASE
    repo = repo or REPO
    now = now or datetime.now(UTC)
    since = now - timedelta(hours=WINDOW_H)
    release = _read_json(base / "data" / "RELEASE.json") or {}
    ident = _read_json(base / "data" / "release_identity.json") or {}
    gw = _read_json(base / "data" / "gateway_state.json") or {}
    stall = _read_json(base / "data" / "stall_watch.json") or {}
    chain = _read_json(base / "reports" / "attribution_chain.json") or {}
    marker = _read_json(base / "data" / "sync_marker.json") or {}
    head = head if head is not None else _git_head(repo)
    ident_at = _ts(ident.get("at"))
    ident_age_s = (now - ident_at).total_seconds() if ident_at else None
    ident_fresh = ident_age_s is not None and ident_age_s <= IDENTITY_MAX_AGE_S
    paused = (base / "data" / "GATEWAY_PAUSED").exists()
    deals = _recent(_read_jsonl(base / "data" / "live_ledger.jsonl"), since)
    intents = _recent(_read_jsonl(base / "data" / "order_intents.jsonl"), since)
    hist = gw.get("placement_health") if isinstance(gw.get("placement_health"), dict) else {}

    if paused:
        verdict = "PAUSED"
    elif not ident or not ident_fresh:
        verdict = "UNMEASURED"
    elif ident.get("allows_new_risk") is True or (ident.get("ok") is True
                                                  and ident.get("measured", True)):
        verdict = "BURNING_IN"
    else:
        verdict = "REFUSING"
    return {
        "at": now.isoformat(timespec="seconds"),
        "verdict": verdict,
        "head": head, "sealed": release.get("code_sha"),
        "head_is_sealed": (bool(head and release.get("code_sha") == head)
                           if head and release.get("code_sha") else None),
        "identity": {"ok": ident.get("ok"), "verdict": ident.get("verdict"),
                     "allows_new_risk": ident.get("allows_new_risk"),
                     "running_sha": ident.get("running_sha"),
                     "release_sha": ident.get("release_sha"),
                     "at": ident.get("at"), "age_s": (round(ident_age_s) if ident_age_s is not None
                                                      else None),
                     "reason": str(ident.get("reason") or "")[:300]},
        "paused": paused,
        "armed": gw.get("armed"),
        "placement_pass": gw.get("placement_pass"),
        "rejection_streak": (hist.get("consecutive_total_rejections")
                             if isinstance(hist, dict) else None),
        "deals_24h": len(deals),
        "pl_quote_24h": round(sum(float(d.get("pl_quote") or 0.0) for d in deals), 2),
        "r_24h": round(sum(float(d.get("r_multiple") or 0.0) for d in deals), 4),
        "intents_24h": len(intents),
        "attributed_share": chain.get("share"),
        "free_gb": stall.get("free_gb"),
        "memory": stall.get("memory"),
        "last_cycle": marker.get("last_cycle"),
    }


def summarise(rows: list[dict], now: datetime, base: Path | None = None) -> dict:
    """The streak: consecutive most-recent rows whose verdict is BURNING_IN."""
    base = base or BASE
    streak: list[dict] = []
    for row in reversed(rows):
        if row.get("verdict") == "BURNING_IN":
            streak.append(row)
        else:
            break
    streak.reverse()
    first = _ts(streak[0]["at"]) if streak else None
    days = ((now - first).total_seconds() / 86400.0) if first else 0.0
    fills = 0
    if first:
        fills = len(_recent(_read_jsonl(base / "data" / "live_ledger.jsonl"), first))
    latest = rows[-1] if rows else None
    return {
        "at": now.isoformat(timespec="seconds"),
        "latest": latest,
        "verdict": latest.get("verdict") if latest else "UNMEASURED",
        "streak_passes": len(streak),
        "streak_started_at": streak[0]["at"] if streak else None,
        "days_in_burn_in": round(days, 3),
        "fills_in_burn_in": fills,
        "target_days": TARGET_DAYS,
        "target_met": bool(days >= TARGET_DAYS),
        "rows_kept": len(rows),
        "note": ("thirty days of running-SHA == sealed-SHA with fills recorded against it is the "
                 "bar; a pass without its own identity verdict breaks the streak"),
    }


def main(argv: list[str] | None = None) -> int:
    now = datetime.now(UTC)
    row = observe(now)
    OUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_ROWS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    rows = _read_jsonl(OUT_ROWS)
    summary = summarise(rows, now)
    OUT.write_text(json.dumps(summary, indent=1, default=str), "utf-8")
    print(f"burn-in: {summary['verdict']} | streak {summary['streak_passes']} pass(es), "
          f"{summary['days_in_burn_in']:.2f} of {TARGET_DAYS:.0f} days, "
          f"{summary['fills_in_burn_in']} fill(s) | head {str(row['head'])[:12]} "
          f"sealed {str(row['sealed'])[:12]} | deals 24h {row['deals_24h']} "
          f"attributed {row['attributed_share']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
