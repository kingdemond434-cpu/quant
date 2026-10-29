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
organ totals, and -- where an output count is cheaply known (CPU_SHAPE.json
`compute_ledger.outputs`, e.g. the judge's verdicts/day from JUDGING_THROUGHPUT.json) -- output per
core-hour. `free_cpu_first` ranks organs with a measured yield, best yield first; organs whose
output is UNMEASURED follow, largest spender first, and say so.
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
               ) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Per-organ {core_s, io_mb, rss_mb, n} since the previous pass, and the new state. Pure."""
    prev = last or {}
    totals_raw = prev.get("totals")
    totals_prev: dict[str, Any] = totals_raw if isinstance(totals_raw, dict) else {}
    since = prev.get("at_epoch")
    baseline = not isinstance(since, (int, float))
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
    return out, {"totals": totals, "baseline": baseline}


def _dig(doc: Any, path: Sequence[str]) -> float | None:
    for k in path:
        if not isinstance(doc, Mapping):
            return None
        doc = doc.get(k)
    return float(doc) if isinstance(doc, (int, float)) and not isinstance(doc, bool) else None


def outputs(cfg: Mapping[str, Any], repo: Path = REPO) -> dict[str, dict[str, Any]]:
    """group -> {per_day, unit, source} for every configured cheap output count."""
    out: dict[str, dict[str, Any]] = {}
    for group, spec in (cfg.get("outputs") or {}).items():
        value, src = None, None
        for source in spec.get("sources", []):
            try:
                doc = json.loads((repo / source["file"]).read_text(encoding="utf-8"))
            except (OSError, ValueError, KeyError, TypeError):
                continue
            value = _dig(doc, source.get("path", []))
            if value is not None:
                src = f"{source['file']}:{'.'.join(source.get('path', []))}"
                break
        out[group] = {"per_day": value, "unit": spec.get("unit", "outputs"), "source": src}
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


def rank(day: Mapping[str, Any], outs: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Which organ should get freed CPU first: measured yield per core-hour, best first; then the
    unmeasured, biggest spender first. A group's output is shared across its organs by spend."""
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
        if isinstance(per_day, (int, float)) and group_core.get(g, 0.0) > 0:
            group_h = group_core[g] / 3600.0
            row["output"] = f"{per_day:g} {out.get('unit')}/day for group {g}"
            row["output_per_core_hour"] = round(float(per_day) / max(group_h, 1e-9), 3)
        else:
            row["output"] = "UNMEASURED"
            row["output_per_core_hour"] = None
        rows.append(row)
    known = sorted((r for r in rows if r["output_per_core_hour"] is not None),
                   key=lambda r: -float(r["output_per_core_hour"]))
    unknown = sorted((r for r in rows if r["output_per_core_hour"] is None),
                     key=lambda r: -float(r["core_hours"]))
    return known + unknown


def update(procs: Sequence[ProcLike], cfg: Mapping[str, Any], *, now: datetime | None = None,
           path: Path = LEDGER_PATH, repo: Path = REPO) -> dict[str, Any]:
    """One pass into the ledger file. Never raises into the hunter: a failure is a reading."""
    now = now or datetime.now(UTC)
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(ledger, dict):
            ledger = {}
    except (OSError, ValueError):
        ledger = {}
    delta, state = pass_delta(procs, ledger.get("state"))
    day = now.date().isoformat()
    days = accumulate(ledger, delta, day)
    outs = outputs(cfg, repo)
    doc = {"schema": "box_compute_ledger/v1", "at": now.isoformat(timespec="seconds"),
           "authority": "report_only", "baseline_pass": state["baseline"],
           "days": days, "outputs": outs, "free_cpu_first": rank(days[day], outs)[:25],
           "state": {"at_epoch": now.timestamp(), "totals": state["totals"]}}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    top = doc["free_cpu_first"][0] if doc["free_cpu_first"] else None
    return {"path": str(path.name), "baseline_pass": state["baseline"],
            "organs_today": len(days[day].get("organs", {})),
            "free_cpu_first": top["organ"] if top else None}
