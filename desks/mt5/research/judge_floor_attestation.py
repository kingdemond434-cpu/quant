"""JUDGE FLOOR ATTESTATION -- is the judge actually ruling 150,000 new cells a day, is it ever
idle for longer than one of its own sweeps, and does it hold its reserved cores?

THE ASK. "Judge never idle at the 150k/day floor" (zuck's standing number: the judge rules at
least 150,000 first-terminal cells a day, 24/7). Three organs already measure pieces of it and
none of them ATTESTS it:

  * `judging_throughput` writes JUDGING_RATE.json -- first-terminal counts for 1h / 24h / 7d --
    but never compares them with the floor, so a judge running at a tenth of its mandate reads
    as a healthy MEASURED rate;
  * `judge_stall_pager` pages `no_verdict` against a FIXED 36 h limit, while the judge's verdicts
    land in bursts at `merge_and_publish` roughly once per sweep: a sweep that normally takes
    six hours can be dead for thirty before the pager fires;
  * `judge_core_share` (the Judge thread's adaptive reservation) publishes how many cores the
    judge holds against its floor, and nothing checks the reading against the floor over time.

THIS ORGAN IS READ-ONLY ON ALL OF THEM and owns three verdicts:

  PACE      first-terminal cells in the last 24 h against the floor (MET at >= floor, SHORT at
            >= 80 %, BELOW otherwise), the 7-day mean beside it, the 7-day shortfall in cells,
            the hourly rate the next 24 h needs, and one attested row per UTC day (the first
            reading after midnight, whose 24 h window IS that day) with the streak of met days.
  IDLE_GAP  hours since the newest verdict against ONE SWEEP of this judge, derived and never a
            constant: the LONGEST completed sweep of the last 7 days (JUDGE_RESIDENT `last_sweep_s`
            when `last_rc == 0`, plus every completed sweep this organ recorded), times 1.25 for
            the publish step -- the longest, because a no-op sweep also exits 0 in seconds;
            with no completed sweep on record, the 90th percentile of the measured gaps between
            verdict bursts (>= 5 gaps; from this organ's hourly history, or the gate ledger's
            32 MB tail until that history holds enough); with neither, UNMEASURED.
  CORES     JUDGE_CORE_SHARE's `judge_busy_cores` against its `floor` whenever its mode is not
            IDLE: one reading under is BELOW, two consecutive hourly readings under is BREACH.

  status    RED if any verdict is BELOW / BREACH / IDLE; AMBER if SHORT or a single BELOW core
            reading; GREEN only when all three are measured and clean; otherwise UNMEASURED.
            An absent or stale input is UNMEASURED, never GREEN (L1.28a).

AUTHORITY: none. It reports; it never changes the judge's cores, its docket, its schedule or
any limit. The Judge thread owns sizing and scheduling (judge_core_share.py,
run_sharded_gauntlet.py, judge_priority.py, judging_throughput.py, market_quota.py).

Outputs: reports/JUDGE_FLOOR_ATTESTATION.json (schema "judge-floor-attestation/1") and
data/judge_floor_history.jsonl (gitignored, trimmed to 60 days / 5,000 rows).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPORTS = DESK / "reports"
OUT = REPORTS / "JUDGE_FLOOR_ATTESTATION.json"
HISTORY = DESK / "data" / "judge_floor_history.jsonl"
SCHEMA = "judge-floor-attestation/1"

RATE = REPORTS / "JUDGING_RATE.json"
STALL = REPORTS / "JUDGE_STALL.json"
RESIDENT = REPORTS / "JUDGE_RESIDENT.json"
CORE_SHARE = REPORTS / "JUDGE_CORE_SHARE.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
#: Until this organ's own history holds enough bursts, the ledger's TAIL is read for them: the
#: last 32 MB only (the file is >1.6M rows; JUDGING_RATE already pays for the full stream).
LEDGER_TAIL_BYTES = 32 * 1024 * 1024
#: Verdicts closer together than this belong to one burst (one merge_and_publish).
BURST_SPLIT_MIN = 30.0

#: zuck's standing floor: first-terminal cells ruled per day. JUDGE_CORE_SHARE's `pace.floor`
#: wins when it is published, so the two organs can never disagree about the number.
FLOOR_PER_DAY = 150_000
SHORT_RATIO = 0.8
#: The publish step after the sweep body (merge_and_publish) is not inside `last_sweep_s`.
SWEEP_SLACK = 1.25
MIN_BURST_GAPS = 5
BURST_QUANTILE = 0.9
#: Inputs older than this are not a reading of the judge now.
RATE_FRESH_H = 3.0
RESIDENT_FRESH_H = 1.0
CORE_FRESH_H = 2.0
CORE_BREACH_RUN = 2
#: The daily row: the first reading within this many hours after UTC midnight.
DAY_READING_H = 3.0
DAYS_SHOWN = 14
RETENTION_DAYS = 60
MAX_ROWS = 5_000
ACTIVE_MODES = frozenset({"FLOOR", "BORROWING", "GIVING_BACK"})

GREEN, AMBER, RED, UNMEASURED = "GREEN", "AMBER", "RED", "UNMEASURED"


# ---------------------------------------------------------------- reading
def _ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(UTC) if t.tzinfo else None


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _read(path: Path) -> dict[str, Any] | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _age_h(at: datetime | None, now: datetime) -> float | None:
    return None if at is None else (now - at).total_seconds() / 3600.0


def load_history(path: Path = HISTORY) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and _ts(r.get("at")) is not None:
            rows.append(r)
    rows.sort(key=lambda r: r["at"])
    return rows


# ---------------------------------------------------------------- PACE
def floor_of(core: Mapping[str, Any] | None) -> tuple[int, str]:
    pace = (core or {}).get("pace")
    f = _num(pace.get("floor")) if isinstance(pace, Mapping) else None
    if f is not None and f > 0:
        return int(f), "JUDGE_CORE_SHARE.json pace.floor"
    return FLOOR_PER_DAY, "standing floor (judge_floor_attestation.FLOOR_PER_DAY)"


def pace(rate: Mapping[str, Any] | None, now: datetime, floor: int) -> dict[str, Any]:
    if rate is None:
        return {"status": UNMEASURED, "why": "JUDGING_RATE.json absent or unreadable"}
    age = _age_h(_ts(rate.get("at")), now)
    if age is None or age > RATE_FRESH_H:
        return {"status": UNMEASURED,
                "why": f"JUDGING_RATE.json is {'unstamped' if age is None else f'{age:.1f} h old'}"
                       f" (fresh limit {RATE_FRESH_H:.0f} h)"}
    ver = rate.get("verdicts")
    if not isinstance(ver, Mapping) or ver.get("status") != "MEASURED":
        why = ver.get("why") if isinstance(ver, Mapping) else None
        return {"status": UNMEASURED, "why": f"judge verdict rate not measured: {why}"}
    ftc = ver.get("first_terminal_counts")
    d24 = _num(ftc.get("24h")) if isinstance(ftc, Mapping) else None
    d7 = _num(ftc.get("7d")) if isinstance(ftc, Mapping) else None
    if d24 is None:
        return {"status": UNMEASURED, "why": "first_terminal_counts.24h absent"}
    ratio = d24 / floor
    status = "MET" if d24 >= floor else "SHORT" if ratio >= SHORT_RATIO else "BELOW"
    out: dict[str, Any] = {
        "status": status, "floor_per_day": floor,
        "first_terminal_24h": int(d24), "ratio_to_floor": round(ratio, 4),
        "needed_per_hour_next_24h": round(floor / 24.0, 1),
        "running_per_hour_24h": round(d24 / 24.0, 1),
        "rate_at": rate.get("at"),
        "basis": "first terminal cell dispositions (judging_throughput); retests never count"}
    if d7 is not None:
        out["first_terminal_7d_mean_per_day"] = round(d7 / 7.0, 1)
        out["shortfall_cells_7d"] = int(max(0.0, 7 * floor - d7))
        out["ratio_7d_to_floor"] = round(d7 / (7.0 * floor), 4)
    return out


def daily_attestation(history: Sequence[Mapping[str, Any]], now: datetime, floor: int,
                      days: int = DAYS_SHOWN) -> dict[str, Any]:
    """One row per UTC day D: the first reading in [D+1 00:00, D+1 00:00 + DAY_READING_H),
    whose 24 h window is day D. A day with no such reading is UNMEASURED, never a zero."""
    by_day: dict[date, Mapping[str, Any]] = {}
    for r in history:
        t = _ts(r.get("at"))
        v = _num(r.get("first_terminal_24h"))
        if t is None or v is None:
            continue
        midnight = t.replace(hour=0, minute=0, second=0, microsecond=0)
        if (t - midnight).total_seconds() / 3600.0 >= DAY_READING_H:
            continue
        d = (midnight - timedelta(days=1)).date()
        by_day.setdefault(d, r)
    rows: list[dict[str, Any]] = []
    today = now.date()
    for k in range(days, 0, -1):
        d = today - timedelta(days=k)
        day_row = by_day.get(d)
        v = _num(day_row.get("first_terminal_24h")) if day_row else None
        rows.append({"date": d.isoformat(),
                     "first_terminal": None if v is None else int(v),
                     "verdict": UNMEASURED if v is None else ("MET" if v >= floor else "BELOW")})
    streak = 0
    for row in reversed(rows):
        if row["verdict"] != "MET":
            break
        streak += 1
    measured = [r for r in rows if r["verdict"] != UNMEASURED]
    return {"days": rows, "met_streak_days": streak,
            "days_measured": len(measured),
            "days_met": sum(r["verdict"] == "MET" for r in measured)}


# ---------------------------------------------------------------- IDLE GAP
def last_verdict(rate: Mapping[str, Any] | None,
                 stall: Mapping[str, Any] | None) -> tuple[datetime | None, str | None]:
    """The NEWEST verdict either organ has seen: JUDGING_RATE streams the whole ledger on its
    own clock, the stall pager reads the tail every few minutes, so the later stamp wins."""
    cands: list[tuple[datetime, str]] = []
    ver = (rate or {}).get("verdicts")
    t = _ts(ver.get("last_verdict_at")) if isinstance(ver, Mapping) else None
    if t is not None:
        cands.append((t, "JUDGING_RATE.json verdicts.last_verdict_at"))
    lv = (stall or {}).get("last_verdict")
    t = _ts(lv.get("at")) if isinstance(lv, Mapping) else None
    if t is not None:
        cands.append((t, "JUDGE_STALL.json last_verdict.at"))
    if not cands:
        return None, None
    return max(cands)


def sweep_length(resident: Mapping[str, Any] | None, history: Sequence[Mapping[str, Any]],
                 now: datetime, days: int = 7) -> tuple[float | None, str]:
    """The LONGEST completed sweep (rc 0) seen in the last `days`: a no-op sweep that finds the
    docket empty also exits 0 in seconds, and a limit built on it would page every hour."""
    cands: list[tuple[float, str]] = []
    if resident is not None:
        s, rc = _num(resident.get("last_sweep_s")), resident.get("last_rc")
        if s is not None and s > 0 and rc == 0:
            cands.append((s, "JUDGE_RESIDENT.json last_sweep_s (last_rc 0)"))
    since = now - timedelta(days=days)
    for r in history:
        s, t = _num(r.get("completed_sweep_s")), _ts(r.get("at"))
        if s is not None and s > 0 and t is not None and t >= since:
            cands.append((s, f"completed sweep recorded {r.get('at')}"))
    if not cands:
        return None, (f"no completed sweep in {days} d (a lane-held or failed sweep is not a "
                      "sweep)")
    s, src = max(cands)
    return s, f"longest completed sweep in {days} d, {len(cands)} on record: {src}"


def burst_gaps_h(history: Sequence[Mapping[str, Any]], now: datetime,
                 days: int = 14) -> list[float]:
    """Gaps between the distinct newest-verdict stamps this organ saw, hour by hour."""
    since = now - timedelta(days=days)
    stamps = sorted({t for r in history
                     if (t := _ts(r.get("last_verdict_at"))) is not None and t >= since})
    return [(b - a).total_seconds() / 3600.0 for a, b in pairwise(stamps)]


def ledger_burst_gaps_h(path: Path, now: datetime, days: int = 14,
                        tail_bytes: int = LEDGER_TAIL_BYTES) -> list[float]:
    """Gaps between verdict BURSTS read from the ledger's tail: stamps closer than
    BURST_SPLIT_MIN are one burst, and a gap is measured from one burst's last verdict to the
    next burst's first. Used only until the organ's own history has MIN_BURST_GAPS gaps."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            blob = fh.read()
    except OSError:
        return []
    since = now - timedelta(days=days)
    stamps: list[datetime] = []
    for ln in blob.decode("utf-8", errors="replace").splitlines()[1:]:
        i = ln.find('"at"')
        if i < 0:
            continue
        j = ln.find('"', ln.find(":", i) + 1)
        k = ln.find('"', j + 1)
        t = _ts(ln[j + 1:k]) if 0 <= j < k else None
        if t is not None and since <= t <= now:
            stamps.append(t)
    stamps.sort()
    split = BURST_SPLIT_MIN * 60.0
    return [(b - a).total_seconds() / 3600.0 for a, b in pairwise(stamps)
            if (b - a).total_seconds() > split]


def _quantile(xs: Sequence[float], q: float) -> float:
    s = sorted(xs)
    pos = q * (len(s) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def idle_gap(rate: Mapping[str, Any] | None, stall: Mapping[str, Any] | None,
             resident: Mapping[str, Any] | None, history: Sequence[Mapping[str, Any]],
             now: datetime, ledger: Path | None = None) -> dict[str, Any]:
    lv, src = last_verdict(rate, stall)
    gaps, gap_src = burst_gaps_h(history, now), "this organ's hourly history"
    if len(gaps) < MIN_BURST_GAPS and ledger is not None:
        tail = ledger_burst_gaps_h(ledger, now)
        if len(tail) > len(gaps):
            gaps, gap_src = tail, f"{ledger.name} tail ({LEDGER_TAIL_BYTES >> 20} MB)"
    burst: dict[str, Any] = ({"n": len(gaps), "source": gap_src,
                              "p50_h": round(_quantile(gaps, 0.5), 2),
                              "p90_h": round(_quantile(gaps, BURST_QUANTILE), 2)}
                             if gaps else {"n": 0, "source": gap_src})
    out: dict[str, Any] = {"burst_gaps_14d": burst}
    if lv is None:
        return {**out, "status": UNMEASURED,
                "why": "no verdict stamp in JUDGING_RATE or JUDGE_STALL"}
    gap = (now - lv).total_seconds() / 3600.0
    out.update({"last_verdict_at": lv.isoformat(), "last_verdict_source": src,
                "hours_since_verdict": round(gap, 2)})
    s, basis = sweep_length(resident, history, now)
    if s is not None:
        limit, why_limit = s * SWEEP_SLACK / 3600.0, f"one sweep x {SWEEP_SLACK}: {basis}"
        out["sweep_s"] = round(s, 1)
    elif len(gaps) >= MIN_BURST_GAPS:
        limit = _quantile(gaps, BURST_QUANTILE)
        why_limit = (f"p{int(BURST_QUANTILE * 100)} of {len(gaps)} measured verdict-burst gaps "
                     f"({basis})")
    else:
        return {**out, "status": UNMEASURED,
                "why": f"limit not derivable: {basis}; {len(gaps)} burst gap(s) < {MIN_BURST_GAPS}"}
    out.update({"limit_h": round(limit, 2), "limit_basis": why_limit})
    idle = gap > limit
    out["status"] = "IDLE" if idle else "OK"
    out["why"] = (f"no new verdict for {gap:.1f} h against a {limit:.1f} h limit ({why_limit})"
                  if idle else f"last verdict {gap:.1f} h ago, inside the {limit:.1f} h limit")
    return out


# ---------------------------------------------------------------- CORES
def cores(core: Mapping[str, Any] | None, history: Sequence[Mapping[str, Any]],
          now: datetime) -> dict[str, Any]:
    if core is None:
        return {"status": UNMEASURED, "why": "JUDGE_CORE_SHARE.json absent (judge_core_share not "
                                             "adopted on this host yet)"}
    age = _age_h(_ts(core.get("at")), now)
    if age is None or age > CORE_FRESH_H:
        return {"status": UNMEASURED,
                "why": "JUDGE_CORE_SHARE.json "
                       + ("unstamped" if age is None else f"{age:.1f} h old")}
    mode = str(core.get("mode") or "")
    busy, floor = _num(core.get("judge_busy_cores")), _num(core.get("floor"))
    base: dict[str, Any] = {"mode": mode, "judge_busy_cores": busy, "floor": floor,
                            "reserved": len(core.get("reserved_cores") or []),
                            "miner_busy_cores": _num(core.get("miner_busy_cores"))}
    if mode not in ACTIVE_MODES:
        st = "NOT_APPLICABLE" if mode == "IDLE" else UNMEASURED
        return {**base, "status": st,
                "why": f"core-share mode {mode or 'absent'}: no floor to hold"}
    if busy is None or floor is None:
        return {**base, "status": UNMEASURED, "why": "judge_busy_cores or floor absent"}
    under = busy < floor
    run = 1 if under else 0
    if under:
        for r in reversed(history):
            if r.get("core_under") is True:
                run += 1
            else:
                break
    window = [r for r in history if (t := _ts(r.get("at"))) is not None
              and t >= now - timedelta(hours=24) and r.get("core_under") is not None]
    at_floor = sum(r.get("core_under") is False for r in window) + (not under)
    base["share_at_floor_24h"] = round(at_floor / (len(window) + 1), 3)
    base["consecutive_under"] = run
    if not under:
        return {**base, "status": "OK", "why": f"judge holds {busy:.2f} >= floor {floor:.0f}"}
    st = "BREACH" if run >= CORE_BREACH_RUN else "BELOW"
    return {**base, "status": st,
            "why": f"judge at {busy:.2f} cores under its {floor:.0f}-core floor in mode {mode}, "
                   f"{run} consecutive reading(s)"}


# ---------------------------------------------------------------- verdict
def overall(p: Mapping[str, Any], g: Mapping[str, Any], c: Mapping[str, Any]) -> str:
    ps, gs, cs = p.get("status"), g.get("status"), c.get("status")
    if ps == "BELOW" or gs == "IDLE" or cs == "BREACH":
        return RED
    if ps == "SHORT" or cs == "BELOW":
        return AMBER
    if UNMEASURED in (ps, gs, cs):
        return UNMEASURED
    return GREEN


def assess(now: datetime, *, rate: Mapping[str, Any] | None, stall: Mapping[str, Any] | None,
           resident: Mapping[str, Any] | None, core: Mapping[str, Any] | None,
           history: Sequence[Mapping[str, Any]], ledger: Path | None = None) -> dict[str, Any]:
    floor, floor_src = floor_of(core)
    p = pace(rate, now, floor)
    g = idle_gap(rate, stall, resident, history, now, ledger)
    c = cores(core, history, now)
    status = overall(p, g, c)
    why = [f"{k}: {v.get('status')} -- {v.get('why') or ''}".rstrip(" -")
           for k, v in (("pace", p), ("idle_gap", g), ("cores", c))
           if v.get("status") not in ("MET", "OK", "NOT_APPLICABLE")]
    if p.get("status") in ("BELOW", "SHORT"):
        why[0] = (f"pace: {p['status']} -- {p['first_terminal_24h']:,} first-terminal cells in "
                  f"24 h = {100 * p['ratio_to_floor']:.1f}% of the {floor:,}/day floor")
    return {"schema": SCHEMA, "at": now.isoformat(timespec="seconds"), "status": status,
            "floor_per_day": floor, "floor_source": floor_src,
            "pace": p, "daily": daily_attestation(history, now, floor),
            "idle_gap": g, "cores": c, "why": why,
            "inputs": {k: str(v.relative_to(DESK)) for k, v in
                       (("rate", RATE), ("stall", STALL), ("resident", RESIDENT),
                        ("core_share", CORE_SHARE))},
            "authority": "none: report only. Judge sizing and scheduling belong to the Judge "
                         "organs; nothing here changes cores, docket, schedule or limits."}


def history_row(doc: Mapping[str, Any], resident: Mapping[str, Any] | None) -> dict[str, Any]:
    p, g, c = doc["pace"], doc["idle_gap"], doc["cores"]
    s = _num((resident or {}).get("last_sweep_s"))
    done = s if (s is not None and s > 0 and (resident or {}).get("last_rc") == 0) else None
    return {"at": doc["at"], "status": doc["status"],
            "first_terminal_24h": p.get("first_terminal_24h"),
            "last_verdict_at": g.get("last_verdict_at"),
            "hours_since_verdict": g.get("hours_since_verdict"),
            "completed_sweep_s": done,
            "core_under": (None if c.get("status") not in ("OK", "BELOW", "BREACH")
                           else c.get("status") != "OK"),
            "judge_busy_cores": c.get("judge_busy_cores")}


def _trim(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    cut = now - timedelta(days=RETENTION_DAYS)
    kept = [r for r in rows if (t := _ts(r.get("at"))) is not None and t >= cut]
    return kept[-MAX_ROWS:]


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(now: datetime | None = None, *, out: Path = OUT, history_path: Path = HISTORY,
        rate_p: Path = RATE, stall_p: Path = STALL, resident_p: Path = RESIDENT,
        core_p: Path = CORE_SHARE, ledger_p: Path = GATE_LEDGER) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    hist = load_history(history_path)
    resident = _read(resident_p)
    doc = assess(now, rate=_read(rate_p), stall=_read(stall_p), resident=resident,
                 core=_read(core_p), history=hist, ledger=ledger_p)
    hist = _trim([*hist, history_row(doc, resident)], now)
    _write_atomic(history_path, "".join(json.dumps(r, sort_keys=True) + "\n" for r in hist))
    _write_atomic(out, json.dumps(doc, indent=1, sort_keys=False) + "\n")
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one attestation (the hourly leg)")
    ap.parse_args(argv)
    try:
        doc = run()
    except Exception as exc:          # a report organ never takes the cycle down
        print(f"judge floor attestation failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"judge floor attestation: {doc['status']} -- " + "; ".join(doc["why"] or ["clean"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
