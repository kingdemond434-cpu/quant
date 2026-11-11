#!/usr/bin/env python3
"""THE FTMO CHALLENGE PACING LEDGER: where the account stands against its target, on what plan,
and how much room the loss limits leave -- measured, every pass of the venue reader.

WHY (hourly pass idea 625, 2026-11-11). The allocator (`research/prop_challenge_allocator.py`)
solves the book from the account as it stands, hour by hour, and forgets: nothing recorded whether
the account is tracking the plan it was solved for, how the plan's days-to-pass moved, or how
close each day came to the daily limit. A challenge is a barrier race -- the target ahead, the
daily and static loss limits behind -- and pacing it needs that race written down day by day.

WHAT IT PUBLISHES (`reports/FTMO_PACING.json`, rewritten every pass; never sizes anything):
  * PROGRESS: the phase's target in $, closed-balance progress and the equity view, the share of
    the way, and what is left;
  * DAYS: trading days done against the firm's minimum (FTMO: 4), weekdays elapsed in the phase,
    and the allocator's plan from the account NOW -- the median and p90 trading days to pass and
    P(pass), as estimated and with every edge halved (the allocator's two worlds);
  * PACE: the realised pace (progress per elapsed trading day) against the pace the plan needs
    (what is left over the plan's median days left), and against the plan the phase STARTED on
    (the first ledger row of the phase: progress expected by now on a straight line to its median
    day). Verdict AHEAD / ON_PACE / BEHIND within +-PACE_BAND, or UNMEASURED -- never a guess;
  * ROOM: today's room to the daily loss limit (equity, floating included, against the balance at
    00:00 CE(S)T) and the room to the static floor, in $ and in days of daily limit;
  * `target_reached_min_days_left`: at target before the minimum trading days -- the rest are
    minimum-lot days, the allocator's own rule.
UNMEASURED IS A VERDICT (L1.28a): an absent, stale or unestablished account state, or a plan for
another phase, is published as such with its reason; nothing falls back to a default account.

THE LEDGER (`data/ftmo_pacing_ledger.jsonl`, append-only): one DAY-CLOSE row per CE(S)T day per
account -- the last snapshot of that day, written by the first pass of the next -- so the race is
on record day by day, including the day's worst room to the daily limit seen across passes.

WHAT IT IS NOT. It is not a rail, a cap or a shrink (GROWTH_GOVERNANCE: never reduce
aggressiveness by fiat). If pace should move capital, that is a two-sided capital modifier with
its missed-growth line, owned by the allocator's solve -- this file is its measured input.

    python desks/mt5/research/prop_pacing.py      one pass from the files on disk
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "FTMO_PACING.json"
LEDGER = BASE / "data" / "ftmo_pacing_ledger.jsonl"
ACCOUNT_STATE = BASE / "reports" / "FTMO_ACCOUNT_STATE.json"
ALLOCATOR = BASE / "reports" / "FTMO_ALLOCATOR.json"
#: The account state is the venue reader's (every five minutes): two missed passes and more is
#: not "now". The allocator plan is hourly (the FTMO allocator at :50): three hours, its own bound.
STATE_MAX_AGE_S = 15 * 60
PLAN_MAX_AGE_S = 3 * 3600
#: AHEAD / BEHIND past this share either side of the pace compared against.
PACE_BAND = 0.10
DAY_TZ = "Europe/Prague"           # FTMO's day: 00:00 CE(S)T


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _iso(v: object) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else None


def cet_date(now: datetime) -> str:
    from zoneinfo import ZoneInfo
    return now.astimezone(ZoneInfo(DAY_TZ)).date().isoformat()


def weekdays_elapsed(start: datetime | None, now: datetime) -> int | None:
    """Weekdays (Mon-Fri) from the phase's first CE(S)T day through today, inclusive."""
    if start is None:
        return None
    a, b = date.fromisoformat(cet_date(start)), date.fromisoformat(cet_date(now))
    if b < a:
        return None
    return int(np.busday_count(a, b + timedelta(days=1)))


def verdict(ratio: float | None) -> str:
    if ratio is None:
        return "UNMEASURED"
    if ratio >= 1.0 + PACE_BAND:
        return "AHEAD"
    if ratio < 1.0 - PACE_BAND:
        return "BEHIND"
    return "ON_PACE"


def _plan(alloc: Any, phase: str, now: datetime) -> tuple[dict[str, Any] | None, str]:
    """The allocator's plan for `phase` from the account now, or (None, why)."""
    if not isinstance(alloc, dict):
        return None, "FTMO_ALLOCATOR.json is absent or unreadable"
    at = _iso(alloc.get("generated_at"))
    if at is None:
        return None, "the allocator report carries no readable time"
    age = (now - at).total_seconds()
    if age > PLAN_MAX_AGE_S:
        return None, (f"the allocator plan is {age / 3600:.1f}h old "
                      f"(limit {PLAN_MAX_AGE_S // 3600}h)")
    if (alloc.get("account") or {}).get("phase") != phase:
        return None, (f"the allocator solved phase {(alloc.get('account') or {}).get('phase')!r}, "
                      f"the account is in {phase!r}")
    block = (alloc.get("phases") or {}).get(phase)
    val = (block or {}).get("validation") if isinstance(block, dict) else None
    if not isinstance(val, dict):
        return None, f"the allocator report has no validated {phase} block"
    est, half = val.get("as_estimated") or {}, val.get("edges_halved") or {}
    plan = {"generated_at": alloc.get("generated_at"), "book_status": block.get("status"),
            "total_risk": block.get("total_risk"),
            "days_median": est.get("days_median"), "days_p90": est.get("days_p90"),
            "p_pass": est.get("p_pass"), "p_fail": est.get("p_fail"),
            "halved_days_median": half.get("days_median"), "halved_p_pass": half.get("p_pass")}
    return plan, f"allocator plan {age / 60:.0f} min old"


def build(state: Any, alloc: Any, history: list[dict[str, Any]], *,
          now: datetime) -> dict[str, Any]:
    """The pacing report. Pure: `history` is the ledger's rows (the phase's first plan)."""
    from prop_challenge_allocator import FTMO_2STEP as rules
    doc: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "cet_date": cet_date(now), "rules": rules.name,
                           "rules_source": rules.source, "pace_band": PACE_BAND}
    if not isinstance(state, dict) or "balance" not in state:
        doc.update({"status": "UNMEASURED", "why": "no FTMO account state"})
        return doc
    at = _iso(state.get("generated_at"))
    age = None if at is None else (now - at).total_seconds()
    try:
        initial = float(state["initial_balance"])
        balance, equity = float(state["balance"]), float(state["equity"])
        start = float(state["day_start_balance"])
        phase = str(state["phase"])
        done = int(state.get("days_traded") or 0)
    except (KeyError, TypeError, ValueError) as exc:
        doc.update({"status": "UNMEASURED", "why": f"account state unreadable ({exc})"})
        return doc
    if not initial > 0:
        doc.update({"status": "UNMEASURED", "why": "no initial balance"})
        return doc
    why = []
    if state.get("status") != "OK":
        why.append(f"account state {state.get('status')}: "
                   f"{state.get('why') or state.get('phase_why')}")
    if age is None or age > STATE_MAX_AGE_S:
        why.append("account state time unreadable" if age is None else
                   f"account state {age / 60:.0f} min old (limit {STATE_MAX_AGE_S // 60} min)")
    doc.update({"account_key": state.get("account_key"), "phase": phase,
                "state_generated_at": state.get("generated_at"),
                "status": "UNMEASURED" if why else "OK", "why": "; ".join(why) or None})
    # ROOM to the loss limits: equity (floating included) against the day's start and the floor.
    daily_limit = rules.daily_loss * initial
    floor = initial * (1.0 - rules.max_loss)
    daily_used = max(0.0, start - equity)
    doc["room"] = {"daily_limit_usd": round(daily_limit, 2),
                   "daily_used_usd": round(daily_used, 2),
                   "daily_room_usd": round(daily_limit - daily_used, 2),
                   "daily_room_frac": round((daily_limit - daily_used) / daily_limit, 4),
                   "floor_usd": round(floor, 2),
                   "max_room_usd": round(equity - floor, 2),
                   "max_room_in_daily_limits": round((equity - floor) / daily_limit, 2)}
    target = rules.targets.get(phase)
    if target is None:
        doc["progress"] = {"phase": phase, "target": None,
                           "why": "funded: no target; pacing is the room alone"}
        doc["pace"] = {"verdict": "UNMEASURED", "why": "no target in the funded phase"}
        return doc
    target_usd = target * initial
    gained, gained_eq = balance - initial, equity - initial
    phase_start = _iso(state.get("phase_started_at"))
    elapsed = weekdays_elapsed(phase_start, now)
    doc["progress"] = {"target_frac": target, "target_usd": round(target_usd, 2),
                       "gained_usd": round(gained, 2), "gained_equity_usd": round(gained_eq, 2),
                       "share": round(gained / target_usd, 4),
                       "share_equity": round(gained_eq / target_usd, 4),
                       "left_usd": round(max(target_usd - gained, 0.0), 2)}
    doc["days"] = {"traded": done, "min_days": rules.min_days,
                   "min_days_left": max(rules.min_days - done, 0),
                   "phase_started_at": state.get("phase_started_at"),
                   "weekdays_elapsed": elapsed}
    doc["target_reached_min_days_left"] = bool(gained >= target_usd and done < rules.min_days)
    plan, pwhy = _plan(alloc, phase, now)
    doc["plan"] = plan if plan is not None else {"why": pwhy}
    # PACE, two ways, never a default.
    realised = gained / elapsed if elapsed else None
    left = max(target_usd - gained, 0.0)
    need = None
    if plan is not None and isinstance(plan.get("days_median"), (int, float)) \
            and plan["days_median"] > 0:
        need = left / float(plan["days_median"])
    first = next((r for r in history if r.get("account_key") == state.get("account_key")
                  and r.get("phase") == phase
                  and isinstance((r.get("plan") or {}).get("days_median"), (int, float))), None)
    expected = None
    if first is not None and elapsed:
        d0 = float(first["plan"]["days_median"]) + max(int(first.get("weekdays_elapsed") or 1) - 1,
                                                       0)
        expected = target_usd * min(elapsed / d0, 1.0) if d0 > 0 else None
    pace: dict[str, Any] = {
        "realised_usd_per_day": None if realised is None else round(realised, 2),
        "needed_usd_per_day_on_plan": None if need is None else round(need, 2),
        "vs_plan_now": verdict(realised / need if realised is not None and need else None),
        "start_plan_days_median": None if first is None else first["plan"]["days_median"],
        "start_plan_cet_date": None if first is None else first.get("cet_date"),
        "expected_gain_by_now_usd": None if expected is None else round(expected, 2),
        "vs_plan_at_start": verdict(gained / expected if expected else None)}
    if left == 0.0:
        pace["vs_plan_now"] = "AHEAD"        # at target: only the minimum days remain
    pace["verdict"] = (pace["vs_plan_at_start"] if pace["vs_plan_at_start"] != "UNMEASURED"
                       else pace["vs_plan_now"])
    if doc["status"] != "OK":
        pace["verdict"] = "UNMEASURED"
    doc["pace"] = pace
    return doc


def _ledger_rows(path: Path | None = None) -> list[dict[str, Any]]:
    try:
        lines = (path or LEDGER).read_text("utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _close_row(snap: dict[str, Any]) -> dict[str, Any]:
    keep = ("cet_date", "account_key", "phase", "status", "progress", "days", "plan", "pace",
            "room", "target_reached_min_days_left", "worst_daily_room_usd", "generated_at")
    row = {k: snap.get(k) for k in keep}
    row["weekdays_elapsed"] = (snap.get("days") or {}).get("weekdays_elapsed")
    row["kind"] = "day_close"
    return row


def run(now: datetime | None = None) -> dict[str, Any]:
    """One pass from the files on disk: the report, and the previous day's close row when the
    CE(S)T day has turned. Never raises (the venue reader calls it)."""
    now = now or datetime.now(tz=UTC)
    try:
        history = _ledger_rows()
        doc = build(_read_json(ACCOUNT_STATE), _read_json(ALLOCATOR), history, now=now)
        prev = _read_json(OUT)
        if isinstance(prev, dict) and prev.get("cet_date") == doc["cet_date"] \
                and prev.get("account_key") == doc.get("account_key"):
            worst = prev.get("worst_daily_room_usd")
        else:
            worst = None
        room = (doc.get("room") or {}).get("daily_room_usd")
        if isinstance(room, (int, float)) and doc.get("status") == "OK":
            worst = room if not isinstance(worst, (int, float)) else min(worst, room)
        doc["worst_daily_room_usd"] = worst
        if isinstance(prev, dict) and prev.get("cet_date") and prev.get("account_key") \
                and prev.get("cet_date") != doc["cet_date"] and prev.get("status") == "OK" \
                and not any(r.get("kind") == "day_close" and r.get("cet_date") == prev["cet_date"]
                            and r.get("account_key") == prev["account_key"] for r in history):
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with LEDGER.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(_close_row(prev), sort_keys=True, default=str) + "\n")
            doc["closed_day"] = prev["cet_date"]
        started = any(r.get("account_key") == doc.get("account_key")
                      and r.get("phase") == doc.get("phase") for r in history)
        if doc.get("status") == "OK" and not started \
                and isinstance((doc.get("plan") or {}).get("days_median"), (int, float)):
            # THE PHASE'S FIRST PLAN is on record at once (the "plan at start" pace needs it).
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with LEDGER.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({**_close_row(doc), "kind": "phase_start"}, sort_keys=True,
                                    default=str) + "\n")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_name(f".{OUT.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, OUT)
        return doc
    except Exception as exc:
        return {"status": "ERROR", "why": f"{type(exc).__name__}: {exc}"[:300]}


if __name__ == "__main__":
    d = run()
    print(json.dumps({k: d.get(k) for k in ("status", "phase", "why", "pace")}, default=str))
