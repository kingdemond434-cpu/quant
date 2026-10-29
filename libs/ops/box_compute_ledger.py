"""THE BOX COMPUTE LEDGER: which organ spends the box's CPU and what a core-hour buys. Report only.

NOT libs/ops/compute_ledger.py, which records what each research RUN cost from inside the run
(data/compute_ledger.jsonl). This one samples the box from outside, per process, so it also sees
what no run declares: resident loops, miners, the memecoin bot, Defender.

WHY (2026-10-29). The bottleneck hunter (libs/ops/box_shaper.py) sees the box ten minutes at a
time: who is hot NOW. Freeing CPU for the right organ needs the other axis -- what each organ
spent over the day and what it produced for it. This ledger is that, and nothing more: it changes
no process, it only ranks.

PER PASS (called by box_shaper.run_once, every MT5-StallWatch pass):
  * every process is attributed to an ORGAN -- its script stem (`foo.py` -> foo), its module
    (`-m pkg.mod` -> pkg.mod), else its exe name; pool workers and `-c` children inherit the
    organ of the nearest ancestor that has one, so a judge's shards book to the judge launcher;
  * core-seconds are the CUMULATIVE CPU-time delta per process since the previous pass (pid +
    creation time, so a reused pid never inherits a total); a process born since the last pass
    books its whole total; on the very first pass nothing is booked (baseline only);
  * IO is the cumulative read+write delta the same way; RSS is the peak seen.

PER DAY (UTC), in desks/mt5/reports/BOX_COMPUTE_LEDGER.json (gitignored with the rest of reports/):
organ totals. PER HOUR, the same core-seconds in hourly buckets, so a ROLLING 24 h window can be
summed. Where an output count is cheaply known (CPU_SHAPE.json `compute_ledger.outputs`, e.g. the
judge's verdicts/day from JUDGING_THROUGHPUT.json, itself a rolling-24h count) the window's spend
becomes output per core-hour. `free_cpu_first` ranks organs with a measured yield, best yield
first; organs whose output is UNMEASURED follow, largest spender first, and say so.

WHAT IS UNMEASURED, NEVER GUESSED (audit of #493, 2026-10-29):
  * YIELD NEEDS A MATCHING WINDOW. The output is a 24 h count, so it is divided only by 24 h of
    core-seconds: until the ledger's own window covers WINDOW_MIN_H hours, every yield reads
    UNMEASURED (a fresh ledger's 10 minutes of spend against a day of verdicts would read 144x).
  * A STALE OUTPUT IS NO OUTPUT. Each source is believed only while its own timestamp
    (`at_path`, default `at`) is younger than `max_age_s` (default 7200: twice the judging
    throughput leg's hourly cadence). Older, or with no readable timestamp: UNMEASURED.
  * THE WINDOW IS WALL HOURS, AND COVERAGE IS WHAT WAS OBSERVED (audit #493 MF1). The rolling
    window holds only buckets whose hour began within the last 24 wall hours (never "the last 24
    buckets that exist"), and `covered_h` is the pass intervals actually observed inside it, not
    "now minus the first pass". A pass more than MAX_GAP_S after the previous one (an outage) books
    nothing and observes nothing: it re-baselines, because what ran and exited in the gap cannot be
    placed in any hour. With a 10 h outage the window covers ~14 h and every yield is UNMEASURED.
  * SHORT-LIVED PROCESSES ARE NEVER BOOKED PER ORGAN (audit #493 SF1). A process born and gone
    between two passes (a judge shard under 10 minutes) is never seen. The box's own CPU time
    (psutil.cpu_times user+system) is read each pass, so the window's UNBOOKED core-seconds --
    box minus everything booked -- are measured; while they exceed `max_unbooked_share`
    (default 5%) of the box's CPU in the window, or the box reading is missing, every yield reads
    UNMEASURED (a spender's undercount would overstate its yield). pid 0 (System Idle: the box's
    idle time) is never booked, or it would swamp the box's busy CPU and hide all of this.
  * A 24 H COUNT OVER THE HOURS COVERED. The window's core-seconds cover `covered_h` (about 23.2 h
    at a 10-minute cadence), so the output's per-day count is scaled by covered_h / 24 first.
  * AN EXITING PROCESS IS UNDERCOUNTED. A process seen last pass and gone now booked its CPU up to
    last pass; what it spent between that pass and its exit cannot be read once it is gone (psutil
    has no handle to an exited process). The undercount is at most one pass interval per exited
    process; `exited_since_last_pass` says how many there were.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

REPO = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPO / "desks" / "mt5" / "reports" / "BOX_COMPUTE_LEDGER.json"
KEEP_DAYS = 7
#: Hourly buckets kept, and the coverage a yield needs (the output counts are rolling 24 h).
KEEP_HOURS = 24
WINDOW_MIN_H = 23.0
#: Default age past which an output source is stale: twice its hourly cadence.
DEFAULT_MAX_AGE_S = 7200.0
#: A pass further than this from the previous one is an outage: it re-baselines (books nothing,
#: observes nothing). One hour: the bucket width; the real cadence is 10 minutes.
MAX_GAP_S = 3600.0
#: Unbooked share of the box's CPU in the window above which every yield is UNMEASURED.
DEFAULT_MAX_UNBOOKED_SHARE = 0.05
_PY = re.compile(r"([\w.-]+)\.pyw?\b", re.I)


class ProcLike(Protocol):
    pid: int
    ppid: int
    name: str
    group: str
    cmdline: str
    cpu_s: float
    io_mb: float
    rss_mb: float

    @property
    def key(self) -> str: ...

    @property
    def create_time(self) -> float: ...


def own_organ(cmdline: str, name: str) -> str | None:
    """The organ a command line names by itself, or None (a `-c` child, a pool worker)."""
    toks = cmdline.split()
    for i, tok in enumerate(toks):
        if tok == "-m" and i + 1 < len(toks):
            mod = toks[i + 1].strip("\"'")
            return None if mod.startswith("multiprocessing") else mod
        if tok == "-c":
            return None
        m = _PY.search(tok.strip("\"'"))
        if m and i > 0:
            return m.group(1)
    if "python" in name.lower():
        return None
    return name.lower().removesuffix(".exe") or None


def attribute(procs: Sequence[ProcLike]) -> dict[int, str]:
    """pid -> "group:organ". Unnamed python children inherit the nearest named ancestor."""
    by_pid = {p.pid: p for p in procs}
    own = {p.pid: own_organ(p.cmdline, p.name) for p in procs}
    out: dict[int, str] = {}
    for p in procs:
        organ, cur, hops = own[p.pid], p, 0
        while organ is None and cur.ppid in by_pid and hops < 8 and cur.ppid != cur.pid:
            cur = by_pid[cur.ppid]
            organ = own[cur.pid]
            hops += 1
        out[p.pid] = f"{p.group}:{organ or p.name.lower().removesuffix('.exe') or 'unknown'}"
    return out


def pass_delta(procs: Sequence[ProcLike], last: Mapping[str, Any] | None,
               now_epoch: float | None = None, max_gap_s: float = MAX_GAP_S,
               ) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Per-organ {core_s, io_mb, rss_mb, n} since the previous pass, and the new state. Pure.

    The first pass, and a pass more than `max_gap_s` after the previous one (an outage), are
    baselines: nothing is booked (`gap_s` says how long the outage was)."""
    prev = last or {}
    totals_raw = prev.get("totals")
    totals_prev: dict[str, Any] = totals_raw if isinstance(totals_raw, dict) else {}
    since = prev.get("at_epoch")
    baseline = not isinstance(since, (int, float))
    gap_s = None
    if not baseline and now_epoch is not None:
        interval = float(now_epoch) - float(since)  # type: ignore[arg-type]
        if interval > max_gap_s or interval < 0:
            baseline, gap_s = True, round(interval, 1)
    # pid 0 IS THE SYSTEM IDLE PROCESS (audit #493 MF2, 2026-10-29): psutil reports the box's idle
    # time as its CPU. Booked, it swamped the box's own busy CPU, so `unbooked` read 0 and the
    # short-lived-spend check could never fire. It is no organ and is never booked.
    procs = [p for p in procs if p.pid != 0]
    organs = attribute(procs)
    out: dict[str, dict[str, float]] = {}
    totals: dict[str, list[float]] = {}
    for p in procs:
        totals[p.key] = [round(p.cpu_s, 3), round(p.io_mb, 3)]
        o = out.setdefault(organs[p.pid], {"core_s": 0.0, "io_mb": 0.0, "rss_mb": 0.0, "n": 0})
        o["n"] += 1
        o["rss_mb"] += p.rss_mb
        if baseline:
            continue
        before = totals_prev.get(p.key)
        if isinstance(before, list) and len(before) == 2:
            o["core_s"] += max(0.0, p.cpu_s - float(before[0]))
            o["io_mb"] += max(0.0, p.io_mb - float(before[1]))
        elif isinstance(since, (int, float)) and p.create_time >= float(since):
            o["core_s"] += p.cpu_s          # born since the last pass: all of it is this pass's
            o["io_mb"] += p.io_mb
        # else: alive before the last pass but unseen then (access denied, a race) -- its
        # history is not this pass's, so nothing is booked rather than a guess
    exited = 0 if baseline else sum(1 for k in totals_prev if k not in totals)
    return out, {"totals": totals, "baseline": baseline, "exited": exited, "gap_s": gap_s}


def _dig(doc: Any, path: Sequence[str]) -> float | None:
    for k in path:
        if not isinstance(doc, Mapping):
            return None
        doc = doc.get(k)
    return float(doc) if isinstance(doc, (int, float)) and not isinstance(doc, bool) else None


def _age_s(doc: Any, path: Sequence[str], now: datetime) -> float | None:
    for k in path:
        if not isinstance(doc, Mapping):
            return None
        doc = doc.get(k)
    if not isinstance(doc, str):
        return None
    try:
        at = datetime.fromisoformat(doc.replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return (now - at).total_seconds()


def outputs(cfg: Mapping[str, Any], repo: Path = REPO,
            now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """group -> {per_day, unit, source, why} for every configured cheap output count.

    A source is believed only while its own timestamp is younger than `max_age_s`; a stale or
    undated one is skipped (the next source is tried) and, if none is fresh, per_day is None.
    """
    now = now or datetime.now(UTC)
    out: dict[str, dict[str, Any]] = {}
    for group, spec in (cfg.get("outputs") or {}).items():
        value, src, why = None, None, []
        for source in spec.get("sources", []):
            name = str(source.get("file"))
            try:
                doc = json.loads((repo / source["file"]).read_text(encoding="utf-8-sig"))
            except (OSError, ValueError, KeyError, TypeError):
                why.append(f"{name}: unreadable")
                continue
            got = _dig(doc, source.get("path", []))
            if got is None:
                why.append(f"{name}: no number at {'.'.join(source.get('path', []))}")
                continue
            limit = float(source.get("max_age_s", spec.get("max_age_s", DEFAULT_MAX_AGE_S)))
            age = _age_s(doc, source.get("at_path", ["at"]), now)
            if age is None:
                why.append(f"{name}: no readable timestamp, freshness unproven")
                continue
            if age > limit:
                why.append(f"{name}: stale ({round(age / 3600, 1)} h old, limit "
                           f"{round(limit / 3600, 1)} h)")
                continue
            value, src = got, f"{name}:{'.'.join(source.get('path', []))}"
            break
        out[group] = {"per_day": value, "unit": spec.get("unit", "outputs"), "source": src,
                      "why": None if value is not None else "; ".join(why) or "no source"}
    return out


def accumulate(ledger: Mapping[str, Any], delta: Mapping[str, Mapping[str, float]], day: str,
               ) -> dict[str, Any]:
    """Add one pass into the day's totals; keep the last KEEP_DAYS days. Pure."""
    days = {k: dict(v) for k, v in (ledger.get("days") or {}).items() if isinstance(v, dict)}
    d = days.setdefault(day, {"passes": 0, "organs": {}})
    d["passes"] = int(d.get("passes", 0)) + 1
    organs = {k: dict(v) for k, v in (d.get("organs") or {}).items()}
    for organ, v in delta.items():
        o = organs.setdefault(organ, {"core_s": 0.0, "io_mb": 0.0, "rss_mb_peak": 0.0,
                                      "passes_seen": 0})
        o["core_s"] = round(float(o["core_s"]) + v["core_s"], 1)
        o["io_mb"] = round(float(o["io_mb"]) + v["io_mb"], 1)
        o["rss_mb_peak"] = round(max(float(o["rss_mb_peak"]), v["rss_mb"]), 1)
        o["passes_seen"] = int(o["passes_seen"]) + 1
    d["organs"] = organs
    days[day] = d
    return {k: days[k] for k in sorted(days)[-KEEP_DAYS:]}


def accumulate_hours(ledger: Mapping[str, Any], delta: Mapping[str, Mapping[str, float]],
                     hour: str) -> dict[str, Any]:
    """Add one pass's core-seconds and IO into its hourly bucket; keep KEEP_HOURS. Pure."""
    hours = {k: dict(v) for k, v in (ledger.get("hours") or {}).items() if isinstance(v, dict)}
    start = _hour_start(hour)
    if start is not None:   # wall hours, not the last KEEP_HOURS buckets that happen to exist
        hours = {k: v for k, v in hours.items() if in_window(k, start)}
    h = hours.setdefault(hour, {})
    for organ, v in delta.items():
        o = dict(h.get(organ) or {"core_s": 0.0, "io_mb": 0.0})
        o["core_s"] = round(float(o.get("core_s", 0.0)) + v["core_s"], 1)
        o["io_mb"] = round(float(o.get("io_mb", 0.0)) + v["io_mb"], 1)
        h[organ] = o
    hours[hour] = h
    return {k: hours[k] for k in sorted(hours)[-KEEP_HOURS:]}


def _hour_start(key: str) -> datetime | None:
    try:
        return datetime.strptime(key, "%Y-%m-%dT%H").replace(tzinfo=UTC)
    except ValueError:
        return None


def in_window(key: str, now: datetime) -> bool:
    """The bucket's hour began within the last 24 WALL hours (the current hour included)."""
    start = _hour_start(key)
    if start is None:
        return False
    floor = now.replace(minute=0, second=0, microsecond=0)
    return 0 <= (floor - start).total_seconds() <= 23 * 3600


def accumulate_observed(ledger: Mapping[str, Any], hour: str, *, observed_s: float,
                        box_core_s: float | None, booked_core_s: float,
                        now: datetime) -> dict[str, Any]:
    """Per hour: seconds of pass interval actually observed, the box's CPU over them and what
    was booked to organs. Only buckets inside the wall window are kept. Pure."""
    obs = {k: dict(v) for k, v in (ledger.get("observed") or {}).items()
           if isinstance(v, dict) and in_window(k, now)}
    h = obs.setdefault(hour, {"s": 0.0, "box_core_s": 0.0, "booked_core_s": 0.0,
                              "box_unread_passes": 0})
    h["s"] = round(float(h.get("s", 0.0)) + observed_s, 1)
    h["booked_core_s"] = round(float(h.get("booked_core_s", 0.0)) + booked_core_s, 1)
    if box_core_s is None:
        if observed_s > 0:
            h["box_unread_passes"] = int(h.get("box_unread_passes", 0)) + 1
    else:
        h["box_core_s"] = round(float(h.get("box_core_s", 0.0)) + box_core_s, 1)
    obs[hour] = h
    return {k: obs[k] for k in sorted(obs)}


def coverage(observed: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """Observed hours, box CPU, booked and unbooked core-seconds over the wall window. Pure."""
    s = box = booked = 0.0
    unread = 0
    for k, v in observed.items():
        if not in_window(k, now) or not isinstance(v, Mapping):
            continue
        s += float(v.get("s", 0.0))
        box += float(v.get("box_core_s", 0.0))
        booked += float(v.get("booked_core_s", 0.0))
        unread += int(v.get("box_unread_passes", 0))
    unbooked = max(0.0, box - booked) if not unread else None
    share = (unbooked / box) if unbooked is not None and box > 0 else None
    return {"covered_h": round(min(24.0, s / 3600.0), 2), "box_core_s": round(box, 1),
            "booked_core_s": round(booked, 1),
            "unbooked_core_s": None if unbooked is None else round(unbooked, 1),
            "unbooked_share": None if share is None else round(share, 4),
            "box_unread_passes": unread}


def window(hours: Mapping[str, Any], days: Mapping[str, Any],
           now: datetime | None = None) -> dict[str, Any]:
    """The rolling window: every hourly bucket whose hour began within the last 24 wall hours,
    summed per organ (peak RSS from the days). Without `now`, every kept bucket."""
    organs: dict[str, dict[str, Any]] = {}
    for key, bucket in hours.items():
        if now is not None and not in_window(key, now):
            continue
        for organ, v in (bucket or {}).items():
            o = organs.setdefault(organ, {"core_s": 0.0, "io_mb": 0.0, "rss_mb_peak": None})
            o["core_s"] = round(o["core_s"] + float(v.get("core_s", 0.0)), 1)
            o["io_mb"] = round(o["io_mb"] + float(v.get("io_mb", 0.0)), 1)
    for d in days.values():
        for organ, v in (d.get("organs") or {}).items():
            if organ in organs and isinstance(v.get("rss_mb_peak"), (int, float)):
                cur = organs[organ]["rss_mb_peak"]
                organs[organ]["rss_mb_peak"] = max(cur or 0.0, float(v["rss_mb_peak"]))
    return {"organs": organs}


def rank(day: Mapping[str, Any], outs: Mapping[str, Mapping[str, Any]], *,
         unmeasured_why: str | None = None,
         covered_h: float | None = None) -> list[dict[str, Any]]:
    """Which organ should get freed CPU first: measured yield per core-hour, best first; then the
    unmeasured, biggest spender first. A group's output is shared across its organs by spend.
    `unmeasured_why` (e.g. the window does not yet match the output's 24 h) makes every yield
    UNMEASURED and says why.

    `covered_h` is the hours of pass interval the core-seconds actually cover. The output count
    is per 24 h, so it is scaled by covered_h / 24 before it is divided (audit #493: the wall
    window covers ~23.2 h at a 10-minute cadence, and an unscaled 24 h count overstated the
    yield by ~3%). Without it the window is taken as the whole 24 h."""
    scale = 1.0 if covered_h is None else max(0.0, min(24.0, float(covered_h))) / 24.0
    organs = day.get("organs") or {}
    group_core: dict[str, float] = {}
    for organ, v in organs.items():
        g = organ.split(":", 1)[0]
        group_core[g] = group_core.get(g, 0.0) + float(v.get("core_s", 0.0))
    rows: list[dict[str, Any]] = []
    for organ, v in organs.items():
        g = organ.split(":", 1)[0]
        core_h = float(v.get("core_s", 0.0)) / 3600.0
        out = outs.get(g) or {}
        per_day = out.get("per_day")
        row: dict[str, Any] = {"organ": organ, "core_hours": round(core_h, 2),
                               "io_mb": v.get("io_mb"), "rss_mb_peak": v.get("rss_mb_peak")}
        if unmeasured_why and isinstance(per_day, (int, float)):
            row["output"] = f"UNMEASURED: {unmeasured_why}"
            row["output_per_core_hour"] = None
        elif isinstance(per_day, (int, float)) and group_core.get(g, 0.0) > 0:
            group_h = group_core[g] / 3600.0
            row["output"] = f"{per_day:g} {out.get('unit')}/day for group {g}"
            row["output_per_core_hour"] = round(float(per_day) * scale / max(group_h, 1e-9),
                                                3)
            row["output_window_scale"] = round(scale, 4)
        else:
            row["output"] = "UNMEASURED" + (f": {out['why']}" if out.get("why") else "")
            row["output_per_core_hour"] = None
        rows.append(row)
    known = sorted((r for r in rows if r["output_per_core_hour"] is not None),
                   key=lambda r: -float(r["output_per_core_hour"]))
    unknown = sorted((r for r in rows if r["output_per_core_hour"] is None),
                     key=lambda r: -float(r["core_hours"]))
    return known + unknown


def update(procs: Sequence[ProcLike], cfg: Mapping[str, Any], *, now: datetime | None = None,
           path: Path = LEDGER_PATH, repo: Path = REPO,
           box_cpu_s: float | None = None) -> dict[str, Any]:
    """One pass into the ledger file. Never raises into the hunter: a failure is a reading.

    `box_cpu_s` is the box's cumulative user+system CPU seconds (psutil.cpu_times); without it the
    unbooked share is unread and every yield is UNMEASURED."""
    now = now or datetime.now(UTC)
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(ledger, dict):
            ledger = {}
    except (OSError, ValueError):
        ledger = {}
    raw_state = ledger.get("state")
    prev_state: dict[str, Any] = raw_state if isinstance(raw_state, dict) else {}
    delta, state = pass_delta(procs, prev_state, now.timestamp())
    day = now.date().isoformat()
    hour = now.strftime("%Y-%m-%dT%H")
    days = accumulate(ledger, delta, day)
    hours = accumulate_hours(ledger, delta, hour)
    outs = outputs(cfg, repo, now)
    # COVERAGE IS WHAT WAS OBSERVED (MF1): the interval since the previous pass counts only when
    # this pass booked it (not a baseline, not across an outage). The box's own CPU over the same
    # interval measures what no organ was booked for (SF1: short-lived processes).
    observed_s = 0.0 if state["baseline"] else now.timestamp() - float(prev_state["at_epoch"])
    prev_box = prev_state.get("box_cpu_s")
    box_delta: float | None = None
    if (not state["baseline"] and box_cpu_s is not None and isinstance(prev_box, (int, float))
            and box_cpu_s >= float(prev_box)):
        box_delta = float(box_cpu_s) - float(prev_box)
    booked = sum(float(v["core_s"]) for v in delta.values())
    observed = accumulate_observed(ledger, hour, observed_s=observed_s, box_core_s=box_delta,
                                   booked_core_s=booked, now=now)
    cov = coverage(observed, now)
    covered_h = float(cov["covered_h"])
    win = window(hours, days, now)
    max_unbooked = float(cfg.get("max_unbooked_share", DEFAULT_MAX_UNBOOKED_SHARE))
    if covered_h < WINDOW_MIN_H:
        short: str | None = (f"ledger window observed {covered_h:.1f} h of the output's 24 h "
                             "(gaps and outages are not coverage)")
    elif cov["unbooked_share"] is None:
        short = ("short-lived processes unmeasured: the box's CPU time was not read for the "
                 "whole window, so what no organ was booked for is unknown")
    elif float(cov["unbooked_share"]) > max_unbooked:
        short = (f"short-lived processes unmeasured: {float(cov['unbooked_share']):.0%} of the "
                 f"box's CPU in the window was booked to no organ (limit {max_unbooked:.0%})")
    else:
        short = None
    doc = {"schema": "box_compute_ledger/v1", "at": now.isoformat(timespec="seconds"),
           "authority": "report_only", "baseline_pass": state["baseline"],
           "gap_s": state.get("gap_s"),
           "exited_since_last_pass": state["exited"],
           "window": {"basis": "hourly buckets begun within the last 24 wall hours",
                      "covered_h": round(covered_h, 2), "min_h_for_yield": WINDOW_MIN_H,
                      "box_core_s": cov["box_core_s"], "booked_core_s": cov["booked_core_s"],
                      "unbooked_core_s": cov["unbooked_core_s"],
                      "unbooked_share": cov["unbooked_share"],
                      "max_unbooked_share": max_unbooked, "organs": win["organs"]},
           "days": days, "hours": hours, "observed": observed, "outputs": outs,
           "free_cpu_first": rank(win, outs, unmeasured_why=short,
                                  covered_h=covered_h)[:25],
           "state": {"at_epoch": now.timestamp(), "box_cpu_s": box_cpu_s,
                     "totals": state["totals"]}}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    top = doc["free_cpu_first"][0] if doc["free_cpu_first"] else None
    return {"path": str(path.name), "baseline_pass": state["baseline"],
            "organs_today": len(days[day].get("organs", {})),
            "covered_h": round(covered_h, 2), "unbooked_share": cov["unbooked_share"],
            "free_cpu_first": top["organ"] if top else None}
