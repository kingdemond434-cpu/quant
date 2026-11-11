"""SERVICE LEVELS WITH ERROR BUDGETS for the money path and the pipeline that feeds it.

    python scripts/slo_status.py [--print] [--no-alert]

Writes desks/mt5/reports/SLO_STATUS.json (published by `publish_state`). Runs as the core hourly
leg `slo_status`. rc 2 when any budget is EXHAUSTED.

WHY (Hourly pass idea 607, 2026-11-11). Every organ here answers "is it broken RIGHT NOW". None
answers "how much breakage have we spent this week, and how much is left". The merge gate was red
for twelve hours and every hourly reading was just one more RED row; nothing said that a week's
worth of tolerance had gone in half a day. An error budget turns a stream of readings into one
number per service that falls while things break and recovers as they stop.

ONE SAMPLE PER SERVICE PER PASS, read only from artifacts other organs already write -- this
measures nothing itself, so it can never disagree with them:

    adoption        release_identity.json OK, measured and not stale, and LIVE code waits no more
                    than ADOPT_LAG_H unadopted (MERGE_PIPELINE.live vs the release's age)
    merge_gate      the gate sweep's own beat (MERGE_PIPELINE.sweep): rc 0, inside 30 min
    allocator       pf_allocation.json refreshed inside its 90 min contract (MT5-AllocatorFast)
    judge_volume    MEASURED verdicts/day >= JUDGE_PER_DAY (the 40k "volume fixed" bar of
                    2026-10-27; zuck's 150k floor is reported beside it as `floor_ratio`)
    feeds           while the FX market is open: newest bar <= FEED_MAX_H old and no RED tape

A sample is GOOD, BAD or UNMEASURED. UNMEASURED never counts as good (an unread service is not a
healthy one) and never spends budget (it is not a breach either): it is counted, and a service
whose window is mostly UNMEASURED says so instead of reporting a budget it cannot know.

THE BUDGET over a rolling WINDOW of samples (box-local history, desks/mt5/data/slo_history.jsonl):
    allowed bad = (1 - target) x max(measured, 168)   (168 = one sample per hourly pass for 7 days,
    so the budget is a fixed number of bad hours a week: adoption 8.4 h, allocator 1.7 h ...)
    remaining = 1 - bad / allowed
    EXHAUSTED  remaining <= 0      AT_RISK  remaining < 25%      OK  otherwise
Exhaustion pages ONCE per service (send_all) when it starts, and once when it recovers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "SLO_STATUS.json"
HISTORY = DESK / "data" / "slo_history.jsonl"
STATE = DESK / "data" / "slo_state.json"

WINDOW = timedelta(days=7)
ADOPT_LAG_H = 6.0
GATE_MAX_MIN = 30.0
ALLOC_MAX_MIN = 90.0
JUDGE_PER_DAY = 40_000.0
JUDGE_FLOOR = 150_000.0
FEED_MAX_H = 2.0
JUDGE_RATE_MAX_H = 3.0
AT_RISK = 0.25
#: A service is UNMEASURED overall when fewer than this share of its window was measured.
MIN_MEASURED_SHARE = 0.5
EXPECTED_SAMPLES = int(WINDOW.total_seconds() // 3600)  # one sample per hourly pass

#: service -> (target good share, what it means in plain words)
SERVICES: dict[str, tuple[float, str]] = {
    "adoption": (0.95, "the box runs LIVE's sealed code, and new LIVE code is adopted within 6 h"),
    "merge_gate": (0.95, "the merge sweep runs and finishes cleanly every 10 minutes"),
    "allocator": (0.99, "the allocation is refreshed inside its 90 minute contract"),
    "judge_volume": (0.90, "the judge measures at least 40k verdicts a day"),
    "feeds": (0.99, "bars and ticks are fresh while the FX market is open"),
}

Sample = tuple[str, str]  # (GOOD | BAD | UNMEASURED, why)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def fx_open(now: datetime) -> bool:
    """Sunday 22:00 to Friday 21:00 UTC (box_heartbeat's conservative FX week)."""
    wd, h = now.weekday(), now.hour + now.minute / 60.0
    if wd == 5:
        return False
    if wd == 6:
        return h >= 22.0
    if wd == 4:
        return h < 21.0
    return True


# ----------------------------------------------------------------------------- the SLIs


def sli_adoption(rel: Mapping[str, Any] | None, pipe: Mapping[str, Any] | None) -> Sample:
    if rel is None:
        return "UNMEASURED", "release_identity.json unreadable"
    if not rel.get("measured"):
        return "UNMEASURED", "release identity not measured"
    if rel.get("verdict") != "OK" or rel.get("stale"):
        return "BAD", f"release identity {rel.get('verdict')} (stale={rel.get('stale')})"
    live = (pipe or {}).get("live") or {}
    since_code, age = live.get("hours_since_code"), rel.get("age_h")
    if isinstance(since_code, (int, float)) and isinstance(age, (int, float)):
        lag = float(age) - float(since_code)
        if lag > ADOPT_LAG_H:
            return "BAD", f"LIVE code from {since_code:.1f} h ago waits unadopted ({lag:.1f} h)"
    return "GOOD", "running LIVE's sealed code"


def sli_merge_gate(pipe: Mapping[str, Any] | None, now: datetime) -> Sample:
    sweep = (pipe or {}).get("sweep")
    if not isinstance(sweep, dict):
        return "UNMEASURED", "MERGE_PIPELINE.json has no sweep beat"
    at = _ts(sweep.get("at"))
    if at is None:
        return "UNMEASURED", "sweep beat has no time"
    age = (now - at).total_seconds() / 60.0
    if age > GATE_MAX_MIN:
        return "BAD", f"no sweep beat for {age:.0f} min"
    if sweep.get("rc") != 0:
        return "BAD", f"sweep rc {sweep.get('rc')}: {str(sweep.get('note') or '')[:100]}"
    return "GOOD", "sweep ran cleanly"


def sli_allocator(path: Path, now: datetime) -> Sample:
    try:
        age = (now.timestamp() - path.stat().st_mtime) / 60.0
    except OSError:
        return "BAD", f"{path.name} absent"
    if age > ALLOC_MAX_MIN:
        return "BAD", f"{path.name} {age:.0f} min old"
    return "GOOD", f"{path.name} {age:.0f} min old"


def sli_judge(rate: Mapping[str, Any] | None, now: datetime | None = None) -> Sample:
    r = (rate or {}).get("rate") if isinstance((rate or {}).get("rate"), dict) else rate
    at = _ts((r or {}).get("at") or (rate or {}).get("at"))
    if now is not None and at is not None and now - at > timedelta(hours=JUDGE_RATE_MAX_H):
        return "UNMEASURED", f"judge rate {(now - at).total_seconds() / 3600:.1f} h old"
    per_day = (r or {}).get("verdicts_per_day")
    if not isinstance(per_day, (int, float)):
        return "UNMEASURED", f"verdicts/day {per_day!r}"
    if per_day < JUDGE_PER_DAY:
        return "BAD", f"{per_day:,.0f} verdicts/day < {JUDGE_PER_DAY:,.0f}"
    return "GOOD", f"{per_day:,.0f} verdicts/day"


def sli_feeds(
    bars: Mapping[str, Any] | None, tape: Mapping[str, Any] | None, now: datetime
) -> Sample:
    if not fx_open(now):
        return "UNMEASURED", "FX market closed"
    age = ((bars or {}).get("summary") or {}).get("newest_bar_age_h")
    if not isinstance(age, (int, float)):
        return "UNMEASURED", "BARS_STATE.json has no newest bar age"
    if age > FEED_MAX_H:
        return "BAD", f"newest bar {age:.1f} h old"
    if (tape or {}).get("status") == "RED":
        return "BAD", f"tape RED: {str((tape or {}).get('cause') or '')[:100]}"
    return "GOOD", f"newest bar {age:.1f} h old"


def sample_all(now: datetime, desk: Path = DESK) -> dict[str, Sample]:
    pipe = _read(desk / "reports" / "MERGE_PIPELINE.json")
    rate = _read(desk / "reports" / "JUDGING_THROUGHPUT.json")
    return {
        "adoption": sli_adoption(_read(desk / "data" / "release_identity.json"), pipe),
        "merge_gate": sli_merge_gate(pipe, now),
        "allocator": sli_allocator(desk / "reports" / "pf_allocation.json", now),
        "judge_volume": sli_judge(rate, now),
        "feeds": sli_feeds(
            _read(desk / "data" / "BARS_STATE.json"),
            _read(desk / "reports" / "TAPE_FRESHNESS.json"),
            now,
        ),
    }


# ----------------------------------------------------------------------------- the budget


def budget(samples: list[str], target: float) -> dict[str, Any]:
    good, bad = samples.count("GOOD"), samples.count("BAD")
    measured, total = good + bad, len(samples)
    out: dict[str, Any] = {
        "target": target,
        "samples": total,
        "good": good,
        "bad": bad,
        "unmeasured": total - measured,
    }
    if total == 0 or measured < MIN_MEASURED_SHARE * total:
        out.update(status="UNMEASURED", remaining=None, sli=None)
        return out
    # A fixed budget of bad hourly samples per window, so one bad first hour is not "exhausted".
    allowed = (1.0 - target) * max(measured, EXPECTED_SAMPLES)
    remaining = 1.0 - (bad / allowed) if allowed > 0 else (1.0 if bad == 0 else -1.0)
    out.update(
        sli=round(good / measured, 4),
        bad_allowed=round(allowed, 1),
        remaining=round(remaining, 3),
        status="EXHAUSTED" if remaining <= 0 else "AT_RISK" if remaining < AT_RISK else "OK",
    )
    return out


def window(history: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    floor = now - WINDOW
    return [h for h in history if (t := _ts(h.get("at"))) is not None and floor <= t <= now]


def build(
    now: datetime,
    current: dict[str, Sample],
    history: list[dict[str, Any]],
    rate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [*window(history, now), {"at": now.isoformat(), **{k: v[0] for k, v in current.items()}}]
    services = {}
    for name, (target, means) in SERVICES.items():
        b = budget([str(r.get(name)) for r in rows if r.get(name)], target)
        b.update(means=means, now=current[name][0], why=current[name][1])
        services[name] = b
    per_day = ((rate or {}).get("rate") or {}).get("verdicts_per_day") if rate else None
    if isinstance(per_day, (int, float)):
        services["judge_volume"]["floor_ratio"] = round(per_day / JUDGE_FLOOR, 3)
    worst = [n for n, s in services.items() if s["status"] == "EXHAUSTED"]
    return {
        "schema": "slo_status/1",
        "at": now.isoformat(),
        "window_days": WINDOW.days,
        "verdict": "EXHAUSTED" if worst else "OK",
        "exhausted": worst,
        "breaching_now": [n for n, s in services.items() if s["now"] == "BAD"],
        "services": services,
    }


def pages(doc: Mapping[str, Any], state: Mapping[str, Any]) -> list[tuple[str, str]]:
    """One page per service whose budget became EXHAUSTED, or recovered, since the last pass."""
    was = set(state.get("exhausted") or [])
    now_ex = set(doc["exhausted"])
    out = []
    for n in sorted(now_ex - was):
        s = doc["services"][n]
        out.append(
            (
                f"Error budget EXHAUSTED: {n}",
                f"{s['means']}: {s['bad']} bad of {s['good'] + s['bad']} measured samples "
                f"this week against a {s['target']:.0%} target. Now: {s['why']}",
            )
        )
    for n in sorted(was - now_ex):
        out.append((f"Error budget recovered: {n}", doc["services"][n]["why"]))
    return out


def _history(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None, send: Callable[[str, str], Any] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--print", action="store_true", help="stdout only: nothing written or paged")
    ap.add_argument("--no-alert", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 2 while any budget is exhausted")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    current = sample_all(now)
    history = _history(HISTORY)
    doc = build(now, current, history, _read(DESK / "reports" / "JUDGING_THROUGHPUT.json"))
    if a.print:
        print(json.dumps(doc, indent=1))
        return 2 if a.strict and doc["exhausted"] else 0
    kept = [*window(history, now), {"at": now.isoformat(), **{k: v[0] for k, v in current.items()}}]
    _write(HISTORY, "".join(json.dumps(r, sort_keys=True) + "\n" for r in kept))
    state = _read(STATE) or {}
    due = [] if a.no_alert else pages(doc, state)
    marked = list(doc["exhausted"])
    if due:
        try:
            if send is None:
                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))
                from libs.ops.alert_channels import send_all as send
            title = "; ".join(t for t, _ in due)[:180]
            res = send(title, "\n".join(f"{t}: {b}" for t, b in due)[:3500])
            doc["paged"] = {
                "armed": (res or {}).get("armed"),
                "delivered": (res or {}).get("delivered"),
            }
            # Remember a transition only once it reached someone (or nothing is armed to reach):
            # an armed channel that failed is retried next hour instead of going quiet.
            if (res or {}).get("armed") and not (res or {}).get("delivered"):
                marked = list(state.get("exhausted") or [])
        except Exception as exc:  # the report is the second voice
            doc["paged"] = f"not sent ({type(exc).__name__})"
            marked = list(state.get("exhausted") or [])
    _write(STATE, json.dumps({"exhausted": marked, "at": now.isoformat()}))
    _write(REPORT, json.dumps(doc, indent=1, sort_keys=True))
    print(
        f"slo_status: {doc['verdict']} "
        + " ".join(f"{n}={s['status']}" for n, s in doc["services"].items())
    )
    return 2 if a.strict and doc["exhausted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
