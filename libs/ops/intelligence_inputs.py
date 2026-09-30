"""THE WRITERS OF THREE INPUTS `scripts/run_intelligence_cycle.py` reads.

`run_intelligence_cycle` read `data/cadence_production.json`, `data/capability_snapshots.json`
and `data/strategy_horizons.json` and NOTHING in the repository wrote any of them (the
phantom-input class, R0228), so the three capabilities sat on NO-INPUT forever with no path to
anything else. All three are derivable from artifacts the desk already keeps. The first two come
from `desks/mt5/data/compute_ledger.jsonl`, one row per costed hourly leg (run, outcome, wall_s,
cpu_s, started_at, commit_sha, output_hash); the third from the decay monitor's fitted half-lives.

  * `data/cadence_production.json` -- per job: fires in the window, the measured interval between
    them (median gap, never the manifest's claimed one), cost per fire (mean cpu seconds), and
    PRODUCTIVE fires = successful fires whose output_hash differs from the previous fire's. A job
    whose rows carry no output_hash cannot say whether a fire produced anything, so it is NOT
    emitted as a record (a zero would read "measured and barren"); it is listed under
    `unmeasured` with the reason. UNMEASURED is a real answer (L1.28a).
  * `data/capability_snapshots.json` -- per job, a before/after pair across the two most recent
    code versions (commit_sha) that each ran it: reliability (share of fires that finished ok),
    latency (mean wall seconds) and compute_cost (mean cpu seconds). That is exactly a capability
    regression check across a code change, measured rather than claimed.
  * `data/strategy_horizons.json` -- per roster sleeve, the half-life the decay monitor FITTED
    (`desks/mt5/data/decay_live.json` -> decay_model[sleeve].half_life_days) against the interval
    the sleeve is evaluated at (its chart's bar length from `desks/mt5/data/sleeves.json`). A
    sleeve with no fitted half-life or no chart is listed under `unmeasured`, never given a 0.

All three are written on the intelligence cycle's own clocks (crontab.manifest every 4h and
ops/run_research_cycle.sh), immediately before it reads them. Pure derivation: nothing here
changes a schedule, a gate or a size.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops import compute_ledger

ROOT = Path(__file__).resolve().parents[2]
CADENCE_OUT = ROOT / "data" / "cadence_production.json"
SNAPSHOTS_OUT = ROOT / "data" / "capability_snapshots.json"
HORIZONS_OUT = ROOT / "data" / "strategy_horizons.json"
DECAY_LIVE = ROOT / "desks" / "mt5" / "data" / "decay_live.json"
SLEEVES = ROOT / "desks" / "mt5" / "data" / "sleeves.json"
#: Bar length in minutes per MT5 chart: the interval a sleeve's signal is evaluated at.
BAR_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440,
               "W1": 10080}
#: Fires needed on each side of a code change before its snapshot is compared.
MIN_FIRES_PER_VERSION = 3


def _ts(row: dict[str, Any]) -> float | None:
    for key in ("started_at", "at"):
        try:
            return datetime.fromisoformat(str(row.get(key)).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            continue
    return None


def _by_job(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    jobs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("run") and _ts(r) is not None:
            jobs[str(r["run"])].append(r)
    for v in jobs.values():
        v.sort(key=lambda r: _ts(r) or 0.0)
    return jobs


def _num(x: Any) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def cadence_production(rows: list[dict[str, Any]]) -> dict[str, Any]:
    jobs, unmeasured = [], []
    for job, rs in sorted(_by_job(rows).items()):
        stamps = [t for t in (_ts(r) for r in rs) if t is not None]
        gaps = [(b - a) / 60.0 for a, b in zip(stamps, stamps[1:], strict=False) if b > a]
        if not gaps:
            unmeasured.append({"job": job, "fires": len(rs),
                               "why": "one fire: no interval can be measured"})
            continue
        hashed = [r for r in rs if r.get("output_hash")]
        if len(hashed) < len(rs):
            unmeasured.append({"job": job, "fires": len(rs),
                               "why": (f"{len(rs) - len(hashed)} of {len(rs)} fires carry no "
                                       "output_hash, so whether a fire produced anything is "
                                       "UNMEASURED -- not zero")})
            continue
        productive, findings, prev = 0, set(), None
        for r in rs:
            h = r.get("output_hash")
            if str(r.get("outcome")) == "ok" and h != prev:
                productive += 1
                findings.add(h)
            prev = h
        cpus = [c for c in (_num(r.get("cpu_s")) for r in rs) if c is not None]
        jobs.append({"job": job, "interval_minutes": round(statistics.median(gaps), 3),
                     "fires": len(rs), "productive_fires": productive,
                     "findings": len(findings),
                     "cost_per_fire": round(statistics.fmean(cpus), 4) if cpus else 0.0,
                     "cost_unit": "cpu_seconds", "hard_floor_reason": ""})
    return {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "source": "desks/mt5/data/compute_ledger.jsonl",
            "window_days": compute_ledger.WINDOW_DAYS,
            "jobs": jobs, "unmeasured": unmeasured,
            "rule": ("interval = median measured gap between fires; productive = an ok fire "
                     "whose output_hash changed; a job without output hashes is UNMEASURED")}


def _snapshot(job: str, sha: str, rs: list[dict[str, Any]]) -> dict[str, Any]:
    walls = [w for w in (_num(r.get("wall_s")) for r in rs) if w is not None]
    cpus = [c for c in (_num(r.get("cpu_s")) for r in rs) if c is not None]
    metrics = {"reliability": round(sum(1 for r in rs if str(r.get("outcome")) == "ok")
                                    / len(rs), 6)}
    if walls:
        metrics["latency"] = round(statistics.fmean(walls), 4)
    if cpus:
        metrics["compute_cost"] = round(statistics.fmean(cpus), 4)
    return {"subsystem": job, "at": f"{sha[:12]} @ {rs[-1].get('at')}", "metrics": metrics,
            "fires": len(rs), "tests_passing": []}


def capability_snapshots(rows: list[dict[str, Any]]) -> dict[str, Any]:
    comparisons, unmeasured = [], []
    for job, rs in sorted(_by_job(rows).items()):
        versions: dict[str, list[dict[str, Any]]] = {}
        for r in rs:
            sha = str(r.get("commit_sha") or "")
            if sha:
                versions.setdefault(sha, []).append(r)
        ready = [(sha, v) for sha, v in versions.items() if len(v) >= MIN_FIRES_PER_VERSION]
        if len(ready) < 2:
            unmeasured.append({"job": job, "versions": len(versions),
                               "why": (f"fewer than two code versions with >= "
                                       f"{MIN_FIRES_PER_VERSION} fires each: no before/after")})
            continue
        ready.sort(key=lambda kv: _ts(kv[1][-1]) or 0.0)
        (b_sha, before), (a_sha, after) = ready[-2], ready[-1]
        comparisons.append({"before": _snapshot(job, b_sha, before),
                            "after": _snapshot(job, a_sha, after)})
    return {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "source": "desks/mt5/data/compute_ledger.jsonl",
            "comparisons": comparisons, "unmeasured": unmeasured,
            "rule": ("per job, the two most recent code versions (commit_sha) with enough fires; "
                     "reliability = ok share, latency = mean wall s, compute_cost = mean cpu s")}


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def strategy_horizons(decay: Any, sleeves: Any) -> dict[str, Any]:
    models = decay.get("decay_model") if isinstance(decay, dict) else None
    rows = sleeves.get("sleeves") if isinstance(sleeves, dict) else sleeves
    charts = {str(r.get("name")): str(r.get("timeframe") or "").upper()
              for r in (rows if isinstance(rows, list) else []) if isinstance(r, dict)}
    out, unmeasured = [], []
    for name, m in sorted((models if isinstance(models, dict) else {}).items()):
        hl = _num(m.get("half_life_days")) if isinstance(m, dict) else None
        bar = BAR_MINUTES.get(charts.get(str(name), ""))
        if not hl or hl <= 0 or not bar:
            unmeasured.append({"strategy": name,
                               "why": ("no fitted half-life" if not hl or hl <= 0 else
                                       f"no chart for the sleeve ({charts.get(str(name))!r})")})
            continue
        out.append({"strategy": name, "half_life_minutes": round(hl * 1440.0, 3),
                    "interval_minutes": float(bar), "edge_bps": 0.0,
                    "opportunities_per_day": 0.0, "hard_floor_reason": "",
                    "basis": m.get("basis") if isinstance(m, dict) else None})
    return {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "source": "desks/mt5/data/decay_live.json + desks/mt5/data/sleeves.json",
            "strategies": out, "unmeasured": unmeasured,
            "status": ("MEASURED" if out else
                       "UNMEASURED" if isinstance(models, dict) else
                       "UNMEASURED: the decay monitor has published no decay_model"),
            "rule": ("half-life = the decay monitor's fitted half_life_days; interval = the "
                     "sleeve chart's bar length; edge_bps and opportunities_per_day are "
                     "unmeasured (0 means unmeasured in cadence_alignment)")}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    tmp.replace(path)


def write_all(ledger: Path | None = None, root: Path | None = None,
              decay: Path | None = None, sleeves: Path | None = None) -> dict[str, int]:
    """Derive and write the three inputs; returns how many records each carries."""
    rows = compute_ledger.rows(path=ledger)
    base = ROOT if root is None else root
    cad = cadence_production(rows)
    snap = capability_snapshots(rows)
    hor = strategy_horizons(_load(DECAY_LIVE if decay is None else decay),
                            _load(SLEEVES if sleeves is None else sleeves))
    _write(base / "data" / CADENCE_OUT.name, cad)
    _write(base / "data" / SNAPSHOTS_OUT.name, snap)
    _write(base / "data" / HORIZONS_OUT.name, hor)
    return {"cadence_jobs": len(cad["jobs"]), "cadence_unmeasured": len(cad["unmeasured"]),
            "snapshot_comparisons": len(snap["comparisons"]),
            "horizon_strategies": len(hor["strategies"])}


if __name__ == "__main__":
    print(write_all())
