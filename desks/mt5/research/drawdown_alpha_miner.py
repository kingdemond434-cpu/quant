"""THE DRAWDOWN-ALPHA MINER (Tier-5 mandate 136): for every drawdown the book's OWN ledgers
printed -- live and forward, never pooled -- what measurably paid inside it, hourly.

`drawdown_alpha` (daily) publishes the shadow book's worst quantile bands and which clusters earn
in them. It reads one basis (shadow), it cuts by quantile rather than by EPISODE, and it never
sees the live ledger. This organ is the episode half on both ledgers:

    live book      data/live_ledger.jsonl        one closed deal per row, R from r_multiple or
                                                 pl_quote / |risk_quote|
    forward book   reports/shadow/ledger_*.json  + backups/moat/shadow_ledgers, R per trade

Each book's cumulative R path is cut into peak-to-recovery EPISODES; the deepest episodes are
the windows. For each window and each forward sleeve the in-window mean R is compared with the
sleeve's out-of-window mean, LEAVE-ONE-OUT on the forward basis (the window is re-cut on the book
excluding the candidate, so a sleeve is never judged against a drawdown it caused), and every
row pays multiplicity: `t_deflated = t - E[max_N Z]` over all (window x sleeve) tests. A row is
a CANDIDATE only at t_deflated >= 2.0 with n >= MIN_N; below the sample floor it is UNMEASURED.

What leaves: DRAWDOWN_ALPHA_MINER.json, one registry memory per candidate (category
`drawdown_alpha_miner`), and one deepening-queue mission per window naming the sleeves that
already pay there and asking research for mechanisms that pay in that state. `portfolio_bounty`
reads the windows; the deepening worker reads the missions. Nothing here sizes anything.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "DRAWDOWN_ALPHA_MINER.json"
LIVE = BASE / "data" / "live_ledger.jsonl"
LEDGER_DIRS = (BASE / "reports" / "shadow", REPO / "backups" / "moat" / "shadow_ledgers")
MIN_DEPTH_R = 1.0
MAX_WINDOWS = 8
MIN_N = 8
T_CANDIDATE = 2.0
T_WATCH = 1.0


def _day(v: Any) -> str | None:
    if not v:
        return None
    s = str(v)
    return s[:10] if len(s) >= 10 and s[4] == "-" else None


def _r(row: dict[str, Any]) -> float | None:
    try:
        r = float(row.get("r_multiple") or 0.0)
    except (TypeError, ValueError):
        r = 0.0
    if r != 0.0 and not row.get("r_unreconstructible"):
        return r
    try:
        risk = abs(float(row.get("risk_quote") or 0.0))
        pl = float(row.get("pl_quote") or 0.0)
    except (TypeError, ValueError):
        return None
    return (pl / risk) if risk > 0 else (r if r != 0.0 else None)


def load_live(path: Path = LIVE) -> list[tuple[str, float]]:
    """(day, R) per closed live deal."""
    out: list[tuple[str, float]] = []
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        d, r = _day(row.get("time")), _r(row)
        if d and r is not None:
            out.append((d, r))
    return out


def load_forward(dirs: tuple[Path, ...] = LEDGER_DIRS) -> list[tuple[str, str, float]]:
    """(sleeve, day, R) per forward trade, keyed on exit day (entry day when exit is absent)."""
    out: list[tuple[str, str, float]] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            try:
                rows = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rows, list):
                continue
            sleeve = f.stem.removeprefix("ledger_")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                day = _day(row.get("exit_time")) or _day(row.get("entry_time"))
                v = row.get("r_multiple")
                try:
                    r = float(v) if v is not None else math.nan
                except (TypeError, ValueError):
                    continue
                if day and math.isfinite(r):
                    out.append((sleeve, day, r))
    return out


def daily(series: list[tuple[str, float]]) -> list[tuple[str, float]]:
    acc: dict[str, float] = defaultdict(float)
    for d, r in series:
        acc[d] += r
    return sorted(acc.items())


def episodes(days: list[tuple[str, float]], min_depth: float = MIN_DEPTH_R,
             limit: int = MAX_WINDOWS) -> list[dict[str, Any]]:
    """Peak-to-recovery drawdown episodes on the cumulative R path, deepest first."""
    cum = 0.0
    peak = 0.0
    start: str | None = None
    trough = 0.0
    trough_day: str | None = None
    out: list[dict[str, Any]] = []

    def close(end: str, recovered: bool) -> None:
        depth = peak - trough
        if start is not None and depth >= min_depth:
            out.append({"start": start, "trough": trough_day, "end": end,
                        "depth_r": round(depth, 4), "recovered": recovered})

    for d, r in days:
        cum += r
        if cum >= peak:
            if start is not None:
                close(d, True)
                start = None
            peak = cum
            continue
        if start is None:
            start, trough, trough_day = d, cum, d
        elif cum < trough:
            trough, trough_day = cum, d
    if start is not None and days:
        close(days[-1][0], False)
    out.sort(key=lambda e: -float(e["depth_r"]))
    return out[:limit]


def _stats(inside: list[float], outside: list[float]) -> dict[str, Any]:
    n_in, n_out = len(inside), len(outside)
    if n_in == 0:
        return {"n_in": 0, "n_out": n_out, "status": "UNMEASURED"}
    mean_in = statistics.fmean(inside)
    mean_out = statistics.fmean(outside) if n_out else 0.0
    pooled = inside + outside
    sd = statistics.pstdev(pooled) if len(pooled) > 1 else 0.0
    t = ((mean_in - mean_out) / (sd / math.sqrt(n_in))) if sd > 1e-12 else 0.0
    return {"n_in": n_in, "n_out": n_out, "mean_in": round(mean_in, 4),
            "mean_out": round(mean_out, 4), "t": round(t, 3),
            "status": "MEASURED" if n_in >= MIN_N else "UNMEASURED"}


def expected_max_z(n_tests: int) -> float:
    """E[max of N standard normals], the Bailey/Lopez de Prado approximation the desk's
    multiplicity module uses; 0 for a single test."""
    n = max(int(n_tests), 1)
    if n == 1:
        return 0.0
    from statistics import NormalDist
    nd = NormalDist()
    return float((1 - 0.5772156649) * nd.inv_cdf(1 - 1.0 / n)
                 + 0.5772156649 * nd.inv_cdf(1 - 1.0 / (n * math.e)))


def mine(live: list[tuple[str, float]], forward: list[tuple[str, str, float]]) -> dict[str, Any]:
    by_sleeve: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for s, d, r in forward:
        by_sleeve[s].append((d, r))
    sleeves = sorted(by_sleeve)
    live_days = daily(live)
    fwd_days = daily([(d, r) for _, d, r in forward])
    live_windows = episodes(live_days)
    fwd_windows = episodes(fwd_days)
    rows: list[dict[str, Any]] = []
    n_tests = 0
    for basis, windows in (("live", live_windows), ("forward", fwd_windows)):
        for w in windows:
            for s in sleeves:
                if basis == "forward":
                    # LEAVE-ONE-OUT: re-cut the window on the book without this sleeve.
                    loo = daily([(d, r) for s2, d, r in forward if s2 != s])
                    eps = [e for e in episodes(loo) if e["start"] <= w["end"]
                           and e["end"] >= w["start"]]
                    if not eps:
                        continue
                    w_use = eps[0]
                else:
                    w_use = w
                inside = [r for d, r in by_sleeve[s] if w_use["start"] <= d <= w_use["end"]]
                outside = [r for d, r in by_sleeve[s] if not (w_use["start"] <= d <= w_use["end"])]
                st = _stats(inside, outside)
                n_tests += 1
                rows.append({"basis": basis, "window": f"{w['start']}..{w['end']}",
                             "depth_r": w["depth_r"], "sleeve": s, **st})
    emz = expected_max_z(n_tests)
    for row in rows:
        if row.get("status") == "MEASURED":
            row["t_deflated"] = round(float(row["t"]) - emz, 3)
            row["verdict"] = ("CANDIDATE" if row["t_deflated"] >= T_CANDIDATE else
                              "WATCH" if row["t_deflated"] >= T_WATCH else "NONE")
        else:
            row["verdict"] = "UNMEASURED"
    rows.sort(key=lambda row: -(float(row.get("t_deflated") or -99.0)))
    return {"windows": {"live": live_windows, "forward": fwd_windows},
            "n_live_trades": len(live), "n_forward_trades": len(forward),
            "n_sleeves": len(sleeves), "n_tests": n_tests, "expected_max_z": round(emz, 3),
            "rows": rows[:400],
            "candidates": [x for x in rows if x["verdict"] == "CANDIDATE"][:50],
            "watch": [x for x in rows if x["verdict"] == "WATCH"][:50],
            "n_unmeasured": len([x for x in rows if x["verdict"] == "UNMEASURED"])}


def missions(doc: dict[str, Any], at: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for basis in ("live", "forward"):
        for w in doc["windows"].get(basis) or []:
            key = f"{w['start']}..{w['end']}"
            payers = [r["sleeve"] for r in doc["candidates"]
                      if r["basis"] == basis and r["window"] == key][:8]
            out.append({
                "mission_id": f"ddam:{basis}:{key}", "source": "drawdown_alpha_miner",
                "kind": "mission", "mission_kind": "drawdown_window", "basis": basis,
                "window": key, "depth_r": w["depth_r"], "issued_at": at, "status": None,
                "title": f"Mission: pay inside the {basis} book's drawdown {key} "
                         f"({w['depth_r']} R deep)",
                "detail": (f"Sleeves already measured positive inside it: "
                           f"{payers or 'none at t_deflated >= 2.0'}. Hunt mechanisms and state "
                           f"variables that predict positive returns specifically in this window "
                           f"on the MT5/Fusion universe; the candidate carries this mission_id."),
                "consumer": "deepening_worker / proposers",
            })
    return out


def publish(doc: dict[str, Any], out: Path = OUT, write_queue: bool = True) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    notes = doc.setdefault("publish", {})
    try:
        from libs.moat import registry
        n = 0
        for r in doc["candidates"][:50]:
            registry.remember("drawdown_alpha_miner",
                              f"{r['sleeve']} pays inside {r['basis']} drawdown {r['window']}: "
                              f"mean_in {r['mean_in']} vs out {r['mean_out']}, "
                              f"t_deflated {r['t_deflated']} (n {r['n_in']})",
                              kind="window_payer",
                              memory_key=f"ddam:{r['basis']}:{r['window']}:{r['sleeve']}",
                              metrics={k: r.get(k) for k in ("t_deflated", "n_in", "mean_in",
                                                              "mean_out", "depth_r")})
            n += 1
        notes["registry_memories"] = n
    except Exception as exc:
        notes["registry"] = f"not written: {type(exc).__name__}: {exc}"
    if write_queue and doc.get("missions"):
        try:
            rc = importlib.import_module("regime_coverage")
            rc._merge_into_queue(doc["missions"], source="drawdown_alpha_miner")
            notes["queue_rows"] = len(doc["missions"])
        except Exception as exc:
            notes["queue"] = f"not written: {type(exc).__name__}: {exc}"


def build(now: datetime | None = None, live: list[tuple[str, float]] | None = None,
          forward: list[tuple[str, str, float]] | None = None) -> dict[str, Any]:
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    doc = mine(live if live is not None else load_live(),
               forward if forward is not None else load_forward())
    doc["at"] = at
    doc["missions"] = missions(doc, at)
    doc["consumer"] = ("portfolio_bounty (windows -> missing-payoff requests), deepening queue "
                       "(missions), registry memory category drawdown_alpha_miner")
    doc["rule"] = ("live and forward ledgers are cut separately and never pooled; forward rows are "
                   "leave-one-out; every row pays E[max_N Z]; below MIN_N a row is UNMEASURED")
    doc["headline"] = (f"{len(doc['windows']['live'])} live + {len(doc['windows']['forward'])} "
                       f"forward drawdown windows; {doc['n_tests']} tests, "
                       f"{len(doc['candidates'])} candidate(s), {len(doc['watch'])} watch, "
                       f"{doc['n_unmeasured']} unmeasured")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = build()
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    doc["budget_s"] = a.budget_s
    publish(doc, a.out, write_queue=not a.no_queue)
    print(f"drawdown-alpha miner: {doc['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
