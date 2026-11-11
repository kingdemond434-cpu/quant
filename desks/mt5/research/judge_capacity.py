"""JUDGE CAPACITY -- the 7-day verdict trend (idea 630) and the five-stage queue model (idea 632).

WHY (hourly pass 102, 2026-11-11). JUDGING_RATE.json says how many verdicts the last 24 hours
held: 7,056 first-terminal against a 150,000/day floor. It does not say whether that is a bad
day or the seventh bad day in a row, how many verdicts one sweep yields, or which stage of the
pipe is the one that cannot keep up. This organ answers all three from artifacts the box already
writes, and changes nothing: no gate, no bar, no trial count, no worker count. REPORT ONLY.

  reports/JUDGING_RATE_TREND.json
    * per UTC day, the last 7 days: changed-verdict events and FIRST-TERMINAL verdicts, read from
      judging_throughput's ledger index (data/judging_rate_ledger_index.json, which keeps every
      row's stamp for 8 days). No second stream of the 1.6M-row ledger is ever made.
    * per sweep: each distinct sweep end JUDGE_RESIDENT.json reports is recorded with its
      duration and the verdicts stamped inside it, so verdicts/sweep and verdicts per
      sweep-hour accumulate one row per sweep, kept for the newest SWEEP_KEEP.
    * status BELOW_FLOOR when the newest COMPLETE day's first-terminal count is under
      FLOOR_PER_DAY (zuck's 150k/day); AT_FLOOR when it is not; UNMEASURED with the reason when
      the index is absent, unreadable, or stops short of the day.

  reports/CAPACITY_MODEL.json
    * five stages, miners -> intake -> judge -> cert -> clock. Each carries an arrival rate, a
      service rate (both per hour), a queue depth and the implied wait (depth / service), with
      the artifact and field each number came from. A number no artifact carries is UNMEASURED,
      never zero.
    * every pass appends one sample; a stage whose arrival exceeded its service on EVERY sample
      across the last ALARM_HOURS (with samples spanning at least that long) is ALARM. Fewer
      hours of samples is UNMEASURED for the alarm, never a clean OK.

Both files keep their own history inside themselves (the previous file is read, extended and
rewritten atomically), so the organ owns no other state."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
OUT = REPORTS / "JUDGING_RATE_TREND.json"
CAPACITY_OUT = REPORTS / "CAPACITY_MODEL.json"

LEDGER_INDEX = BASE / "data" / "judging_rate_ledger_index.json"
RESIDENT = REPORTS / "JUDGE_RESIDENT.json"
RATE = REPORTS / "JUDGING_RATE.json"
THROUGHPUT = REPORTS / "JUDGING_THROUGHPUT.json"
BACKPRESSURE = REPORTS / "GAUNTLET_BACKPRESSURE.json"
CERT_CLOCK = REPORTS / "CERTIFICATE_CLOCK_LAW.json"
CLOCK_LEDGER = REPORTS / "FORWARD_CLOCK_LEDGER.json"

UNMEASURED = "UNMEASURED"
#: zuck's standing judge floor: first-terminal verdicts per UTC day.
FLOOR_PER_DAY = 150_000
TREND_DAYS = 7
SWEEP_KEEP = 200
#: An index last updated longer ago than this cannot speak for the day after it.
INDEX_STALE_H = 3.0
ALARM_HOURS = 6.0
#: A source artifact older than this cannot speak for the current hour: its numbers read
#: UNMEASURED with its age, never as a rate of zero.
SOURCE_STALE_H = 6.0
SAMPLE_KEEP = 96
STAGES = ("miners", "intake", "judge", "cert", "clock")


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(UTC)).astimezone(UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t.astimezone(UTC) if t.tzinfo is not None else None


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _write_atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------------------------
# 630: the 7-day trend
# --------------------------------------------------------------------------------------------

def _index_rows(index: Any) -> tuple[list[tuple[int, int]] | None, str]:
    """The index's kept rows as (epoch, is_first), or None and why."""
    if not isinstance(index, dict):
        return None, f"{LEDGER_INDEX.name} absent or unreadable"
    rows: list[tuple[int, int]] = []
    try:
        for r in index.get("recent") or []:
            rows.append((int(r[0]), int(r[1])))
    except (TypeError, ValueError, IndexError):
        return None, f"{LEDGER_INDEX.name} `recent` is malformed"
    return rows, ""


def daily_series(rows: list[tuple[int, int]], now: datetime, kept_since: int | None,
                 updated_at: datetime | None) -> list[dict[str, Any]]:
    """One row per UTC day for the last TREND_DAYS days, oldest first. Pure.

    A day is COMPLETE when it has ended before the index's last update AND the index kept rows
    from its start; today is PARTIAL; a day the index cannot fully speak for is UNMEASURED."""
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = [today - timedelta(days=k) for k in range(TREND_DAYS - 1, -1, -1)]
    events = dict.fromkeys(days, 0)
    first = dict.fromkeys(days, 0)
    for at, is_first in rows:
        d = datetime.fromtimestamp(at, UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        if d in events:
            events[d] += 1
            first[d] += int(bool(is_first))
    out = []
    for d in days:
        end = d + timedelta(days=1)
        if kept_since is not None and int(d.timestamp()) < kept_since:
            state = UNMEASURED
            why = "the index no longer keeps this day's first rows"
        elif d == today:
            state, why = "PARTIAL", "today, still accumulating"
        elif updated_at is None or updated_at < end:
            state = UNMEASURED
            why = "the index was last updated before this day ended"
        else:
            state, why = "COMPLETE", ""
        row: dict[str, Any] = {"day": d.date().isoformat(), "state": state,
                               "verdict_events": events[d], "first_terminal": first[d],
                               "floor_share": round(first[d] / FLOOR_PER_DAY, 4)}
        if why:
            row["why"] = why
        out.append(row)
    return out


def record_sweep(sweeps: list[dict[str, Any]], resident: Any,
                 rows: list[tuple[int, int]] | None) -> list[dict[str, Any]]:
    """Append the resident's last completed sweep if it is new. Pure; returns a new list."""
    out = [s for s in sweeps if isinstance(s, dict)]
    if not isinstance(resident, dict):
        return out
    end = _parse(resident.get("last_sweep_ended_utc"))
    dur = _num(resident.get("last_sweep_s"))
    if end is None or dur is None or dur <= 0:
        return out
    end_iso = _iso(end)
    if any(s.get("ended_utc") == end_iso for s in out):
        return out
    start = end - timedelta(seconds=dur)
    row: dict[str, Any] = {"ended_utc": end_iso, "started_utc": _iso(start),
                           "seconds": round(dur, 1), "sweep_no": resident.get("sweeps"),
                           "rc": resident.get("last_rc")}
    if rows is None:
        row.update(verdict_events=UNMEASURED, first_terminal=UNMEASURED,
                   first_terminal_per_sweep_hour=UNMEASURED)
    else:
        lo, hi = start.timestamp(), end.timestamp()
        inside = [f for at, f in rows if lo <= at <= hi]
        n_first = sum(1 for f in inside if f)
        row.update(verdict_events=len(inside), first_terminal=n_first,
                   first_terminal_per_sweep_hour=round(n_first / (dur / 3600.0), 3))
    out.append(row)
    out.sort(key=lambda s: str(s.get("ended_utc")))
    return out[-SWEEP_KEEP:]


def build_trend(now: datetime | None = None, *, index: Any = None, resident: Any = None,
                previous: Any = None) -> dict[str, Any]:
    t = _now(now)
    rows, why = _index_rows(index)
    updated = _parse(index.get("updated_at")) if isinstance(index, dict) else None
    kept = None
    if isinstance(index, dict):
        with contextlib.suppress(TypeError, ValueError):
            kept = int(index.get("kept_since") or 0) or None
    prev_sweeps = (previous.get("sweeps") if isinstance(previous, dict) else None) or []
    sweeps = record_sweep(list(prev_sweeps), resident, rows)
    doc: dict[str, Any] = {"at": _iso(t), "floor_per_day": FLOOR_PER_DAY,
                           "floor_basis": "first-terminal verdicts per UTC day",
                           "source": f"desks/mt5/data/{LEDGER_INDEX.name}",
                           "index_updated_at": _iso(updated) if updated else None,
                           "sweeps": sweeps}
    if rows is None:
        doc.update(status=UNMEASURED, why=why, days=[])
    else:
        days = daily_series(rows, t, kept, updated)
        doc["days"] = days
        complete = [d for d in days if d["state"] == "COMPLETE"]
        stale = updated is None or (t - updated) > timedelta(hours=INDEX_STALE_H)
        if not complete:
            doc.update(status=UNMEASURED, why="no complete day in the index's window")
        else:
            last = complete[-1]
            doc["last_complete_day"] = last["day"]
            doc["status"] = ("BELOW_FLOOR" if last["first_terminal"] < FLOOR_PER_DAY
                             else "AT_FLOOR")
            doc["shortfall_per_day"] = max(0, FLOOR_PER_DAY - int(last["first_terminal"]))
            doc["days_below_floor"] = sum(1 for d in complete
                                          if d["first_terminal"] < FLOOR_PER_DAY)
            doc["complete_days"] = len(complete)
            if len(complete) >= 2:
                a, b = complete[0]["first_terminal"], complete[-1]["first_terminal"]
                doc["direction"] = "UP" if b > a else ("DOWN" if b < a else "FLAT")
        if stale:
            doc["index_stale"] = True
            doc["index_stale_why"] = (f"index last updated more than {INDEX_STALE_H:.0f} h "
                                      "ago; days after it read UNMEASURED")
    measured = [s for s in sweeps if isinstance(s.get("first_terminal"), int)]
    if measured:
        hours = sum(float(s["seconds"]) for s in measured) / 3600.0
        n = sum(int(s["first_terminal"]) for s in measured)
        doc["per_sweep"] = {"sweeps": len(measured),
                            "first_terminal_per_sweep": round(n / len(measured), 1),
                            "first_terminal_per_sweep_hour": round(n / hours, 3) if hours else None,
                            "mean_sweep_hours": round(hours / len(measured), 3)}
    else:
        doc["per_sweep"] = {"status": UNMEASURED,
                            "why": "no completed sweep recorded with the index readable yet"}
    return doc


# --------------------------------------------------------------------------------------------
# 632: the five-stage queue model
# --------------------------------------------------------------------------------------------

def _dig(doc: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(k)
    return doc


def _stage(arrival: float | None, service: float | None, depth: float | None,
           sources: dict[str, str]) -> dict[str, Any]:
    st: dict[str, Any] = {
        "arrival_per_h": round(arrival, 3) if arrival is not None else UNMEASURED,
        "service_per_h": round(service, 3) if service is not None else UNMEASURED,
        "queue_depth": depth if depth is not None else UNMEASURED,
        "sources": sources}
    if depth is not None and service:
        st["implied_wait_h"] = round(depth / service, 1)
    elif depth is not None and service == 0 and depth > 0:
        st["implied_wait_h"] = "INFINITE"
    else:
        st["implied_wait_h"] = UNMEASURED
    if arrival is not None and service is not None:
        st["net_per_h"] = round(service - arrival, 3)
    return st


def _certs_last_24h(cert: Any, now: datetime) -> float | None:
    rows = _dig(cert, "certificates")
    if not isinstance(rows, list):
        return None
    cut = now - timedelta(hours=24)
    n = 0
    for r in rows:
        t = _parse(r.get("certified_at")) if isinstance(r, dict) else None
        if t is not None and cut <= t <= now:
            n += 1
    return float(n)


def stages(now: datetime, *, rate: Any, throughput: Any, backpressure: Any, cert: Any,
           clocks: Any, previous_samples: list[dict[str, Any]]
           ) -> tuple[dict[str, dict[str, Any]], float | None]:
    created_h = _num(_dig(rate, "created", "per_hour", "24h"))
    born_h = _num(_dig(backpressure, "windows", "24h", "intake", "per_hour"))
    first_h = _num(_dig(rate, "verdicts", "first_terminal_per_hour", "24h"))
    depth = _num(_dig(throughput, "queue", "depth"))
    passed_24 = _num(_dig(backpressure, "core", "testing_24h", "passed"))
    passed_h = passed_24 / 24.0 if passed_24 is not None else None
    certs_24 = _certs_last_24h(cert, now)
    certs_h = certs_24 / 24.0 if certs_24 is not None else None
    no_clock = _num(_dig(cert, "counts", "NO_CLOCK"))
    # Clocks opened per hour: the change in FORWARD_CLOCK_LEDGER.n_clocks between this pass and
    # the oldest earlier sample inside 24h that carried it. One sample is UNMEASURED.
    n_clocks = _num(_dig(clocks, "n_clocks"))
    clocks_h = None
    if n_clocks is not None:
        cut = now - timedelta(hours=24)
        for s in previous_samples:
            t = _parse(s.get("at"))
            prev = _num(s.get("n_clocks"))
            if t is not None and prev is not None and cut <= t < now - timedelta(hours=1):
                clocks_h = max(0.0, (n_clocks - prev) / ((now - t).total_seconds() / 3600.0))
                break
    return {
        "miners": _stage(None, created_h, None, {
            "service_per_h": "JUDGING_RATE.json created.per_hour.24h (cells the registry minted)",
            "arrival_per_h": "source stage: nothing upstream is measured",
            "queue_depth": "no artifact counts donations awaiting registration"}),
        "intake": _stage(created_h, born_h, None, {
            "arrival_per_h": "JUDGING_RATE.json created.per_hour.24h",
            "service_per_h": "GAUNTLET_BACKPRESSURE.json windows.24h.intake.per_hour",
            "queue_depth": "no artifact counts registered-but-not-born cells"}),
        "judge": _stage(born_h, first_h, depth, {
            "arrival_per_h": "GAUNTLET_BACKPRESSURE.json windows.24h.intake.per_hour",
            "service_per_h": "JUDGING_RATE.json verdicts.first_terminal_per_hour.24h",
            "queue_depth": "JUDGING_THROUGHPUT.json queue.depth"}),
        "cert": _stage(passed_h, certs_h, None, {
            "arrival_per_h": "GAUNTLET_BACKPRESSURE.json core.testing_24h.passed / 24",
            "service_per_h": "CERTIFICATE_CLOCK_LAW.json certificates[].certified_at in 24h / 24",
            "queue_depth": "no artifact counts passes awaiting a certificate"}),
        "clock": _stage(certs_h, clocks_h, no_clock, {
            "arrival_per_h": "CERTIFICATE_CLOCK_LAW.json certificates[].certified_at in 24h / 24",
            "service_per_h": "FORWARD_CLOCK_LEDGER.json n_clocks, change per hour vs a sample "
                             ">1h and <=24h old",
            "queue_depth": "CERTIFICATE_CLOCK_LAW.json counts.NO_CLOCK"}),
    }, n_clocks


def alarm(stage: str, samples: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """ALARM when arrival > service on every sample in the last ALARM_HOURS. Pure."""
    cut = now - timedelta(hours=ALARM_HOURS)
    window, older = [], False
    for s in samples:
        t = _parse(s.get("at"))
        if t is None:
            continue
        if t < cut:
            older = True
            continue
        if t <= now:
            window.append(s)
    pairs = []
    for s in window:
        st = _dig(s, "stages", stage) or {}
        a, v = _num(st.get("a")), _num(st.get("s"))
        if a is None or v is None:
            return {"status": UNMEASURED,
                    "why": f"a sample in the last {ALARM_HOURS:.0f} h lacks a rate"}
        pairs.append((a, v))
    if not older or len(pairs) < 2:
        return {"status": UNMEASURED,
                "why": f"samples do not yet span {ALARM_HOURS:.0f} h"}
    if all(a > v for a, v in pairs):
        return {"status": "ALARM", "samples": len(pairs),
                "why": f"arrival exceeded service on all {len(pairs)} samples in "
                       f"{ALARM_HOURS:.0f} h"}
    return {"status": "OK", "samples": len(pairs)}


def fresh(doc: Any, now: datetime) -> tuple[Any, dict[str, Any]]:
    """The artifact if its own `at` is within SOURCE_STALE_H, else None; and its age. Pure."""
    t = _parse(doc.get("at")) if isinstance(doc, dict) else None
    if t is None:
        return None, {"status": UNMEASURED, "why": "absent, unreadable or unstamped"}
    age = round((now - t).total_seconds() / 3600.0, 2)
    if age > SOURCE_STALE_H:
        return None, {"status": "STALE", "at": _iso(t), "age_h": age}
    return doc, {"status": "FRESH", "at": _iso(t), "age_h": age}


def build_capacity(now: datetime | None = None, *, rate: Any = None, throughput: Any = None,
                   backpressure: Any = None, cert: Any = None, clocks: Any = None,
                   previous: Any = None) -> dict[str, Any]:
    t = _now(now)
    ages: dict[str, Any] = {}
    rate, ages[RATE.name] = fresh(rate, t)
    throughput, ages[THROUGHPUT.name] = fresh(throughput, t)
    backpressure, ages[BACKPRESSURE.name] = fresh(backpressure, t)
    cert, ages[CERT_CLOCK.name] = fresh(cert, t)
    clocks, ages[CLOCK_LEDGER.name] = fresh(clocks, t)
    prev = [s for s in ((previous.get("samples") if isinstance(previous, dict) else None) or [])
            if isinstance(s, dict)]
    st, n_clocks = stages(t, rate=rate, throughput=throughput, backpressure=backpressure,
                          cert=cert, clocks=clocks, previous_samples=prev)
    sample = {"at": _iso(t), "n_clocks": n_clocks,
              "stages": {k: {"a": _num(v["arrival_per_h"]), "s": _num(v["service_per_h"])}
                         for k, v in st.items()}}
    samples = [*prev, sample][-SAMPLE_KEEP:]
    for k in STAGES:
        st[k]["alarm"] = alarm(k, samples, t)
    firing = [k for k in STAGES if st[k]["alarm"]["status"] == "ALARM"]
    # The binding stage is the one with the lowest service rate measured; it caps the pipe.
    served = {k: _num(st[k]["service_per_h"]) for k in STAGES}
    measured = {k: v for k, v in served.items() if v is not None}
    return {"at": _iso(t), "stages": st, "order": list(STAGES),
            "alarms": firing, "n_alarms": len(firing),
            "n_unmeasured_stages": sum(1 for k in STAGES
                                       if _num(st[k]["arrival_per_h"]) is None
                                       and _num(st[k]["service_per_h"]) is None),
            "status": "ALARM" if firing else (
                "OK" if all(st[k]["alarm"]["status"] == "OK" for k in STAGES) else UNMEASURED),
            "source_ages": ages,
            "binding_stage": min(measured, key=lambda k: measured[k]) if measured else UNMEASURED,
            "alarm_rule": f"arrival > service on every sample over {ALARM_HOURS:.0f} h",
            "rule": "report only: rates are 24h rolling readings of artifacts the box already "
                    "writes; a number no artifact carries is UNMEASURED, never zero",
            "samples": samples}


def run(now: datetime | None = None, *, write: bool = True) -> dict[str, Any]:
    t = _now(now)
    trend = build_trend(t, index=_read(LEDGER_INDEX), resident=_read(RESIDENT),
                        previous=_read(OUT))
    cap = build_capacity(t, rate=_read(RATE), throughput=_read(THROUGHPUT),
                         backpressure=_read(BACKPRESSURE), cert=_read(CERT_CLOCK),
                         clocks=_read(CLOCK_LEDGER), previous=_read(CAPACITY_OUT))
    if write:
        _write_atomic(OUT, trend)
        _write_atomic(CAPACITY_OUT, cap)
    return {"trend": trend, "capacity": cap}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    a = ap.parse_args(argv)
    out = run(write=not a.dry_run)
    tr, cap = out["trend"], out["capacity"]
    print(f"judge_capacity: trend={tr.get('status')} last_day={tr.get('last_complete_day')} "
          f"capacity={cap['status']} binding={cap['binding_stage']} alarms={cap['alarms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
