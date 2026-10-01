"""THE TIER-1 GAP: the desk's breadth, mining, judging and conversion against tier-1 shops.

    python desks/mt5/research/tier1_gap.py --once          # the hourly leg
    python desks/mt5/research/tier1_gap.py --once --json   # print what was written

WHY THIS EXISTS (principal, 2026-09-30). "It must maximise breadth, yield, production and
conversion daily, aim to match tier-1 quants, notice every gap and close it." A gap nobody
measures on a clock is a gap nobody closes. The numbers below were first assembled BY HAND that
morning from a read-only walk of the trading box, and the hand-walk found the headline figures
the desk was quoting were wrong: 55,811 unjudged when the docket held 1,398,253; a drain of 25 h
when the backlog was growing; 837 certificates that behave like 2.5 independent bets.

This organ repeats that walk every hour from the box's own artifacts and publishes one table,
`reports/TIER1_GAP.json`, with each measure beside a tier-1 reference and the ratio
between them. The references are PUBLIC ESTIMATES (orders of magnitude from what the firms
and the literature say), labelled as such; the desk's numbers are MEASURED here and never
typed in. An input that cannot be read is UNMEASURED, never 0 (L1.28a).

NOT THE SCORECARD. `tier1_scorecard.py` grades the fourteen blueprint dimensions against the
desk's own first targets. This file answers the other question -- how far the desk is from the
firms it benchmarks against, in orders of magnitude -- and the two are read side by side.

THE CONSUMER. The CRO noon pass reads this file first (docs/cro/CRO_CYCLE.md) and works the
`gaps` list top down: the gap with the largest log-ratio to tier-1 that a code change can move
is that day's first build. Nothing here sizes, gates or throttles anything; it measures.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
REPORTS = BASE / "reports"
HYP = DATA / "hypotheses"
OUT = REPORTS / "TIER1_GAP.json"

UNMEASURED = "UNMEASURED"

#: Tier-1 references. PUBLIC ESTIMATES, orders of magnitude only -- the ratio column is what the
#: desk steers on, and a factor of two either way in a reference changes no ranking.
TIER1 = {
    "instruments": (20_000, "tens of thousands of instruments across equities, futures, options, "
                            "FX and credit (DE Shaw / Two Sigma / RenTec, public estimate)"),
    "datasets_in_use": (5_000, "thousands of datasets (Two Sigma cites >10k sources)"),
    "cells_created_per_day": (1_000_000, "millions of hypotheses a day at the largest shops"),
    "verdicts_per_day": (1_000_000, "10k-100k+ cores of research compute"),
    "effective_breadth": (500, "hundreds to thousands of independent bets in stat-arb books"),
    "live_symbols_per_day_median": (2_000, "thousands of positions a day"),
    "unknown_share_7d": (0.02, "a judge that returns a named verdict on essentially every cell"),
    "cert_to_forward": (0.9, "certified signals reach paper/live on the next cycle"),
}


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _ts(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")
    except OSError:
        return None


def _jsonl(path: Path, since: datetime | None = None, *, at_key: str = "at"):
    try:
        fh = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            if since is not None:
                t = _ts(row.get(at_key))
                if t is None or t < since:
                    continue
            yield row


# ------------------------------------------------------------------ measures, one per source
def ingestion(now: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {}
    reg = _read(DATA / "data_registry.json")
    ds = (reg or {}).get("datasets") if isinstance(reg, dict) else None
    if isinstance(ds, dict):
        life = Counter(str((v or {}).get("lifecycle") or "?") for v in ds.values())
        out["registry_datasets"] = len(ds)
        out["registry_by_lifecycle"] = dict(life)
        out["datasets_in_use"] = sum(n for k, n in life.items() if k not in ("DISCOVERED", "?"))
    else:
        out["datasets_in_use"] = UNMEASURED
    hunt = _read(REPORTS / "DATASET_HUNT.json")
    if isinstance(hunt, dict):
        out["dataset_hunt"] = {k: v for k, v in hunt.items() if not isinstance(v, (dict, list))}
        for key in ("datasets_in_research_use", "datasets_in_use", "quality_passed"):
            v = hunt.get(key) if key in hunt else (hunt.get("totals") or {}).get(key)
            if isinstance(v, int) and (not isinstance(out["datasets_in_use"], int)
                                       or v > out["datasets_in_use"]):
                out["datasets_in_use"] = v
                out["datasets_in_use_source"] = f"DATASET_HUNT.json {key}"
                break
    uni = DATA / "universe"
    try:
        h1 = list(uni.glob("*_H1.parquet"))
        fresh = [p for p in h1 if (now.timestamp() - p.stat().st_mtime) < 48 * 3600]
        out["instruments"] = len(h1)
        out["instruments_fresh_48h"] = len(fresh)
    except OSError:
        out["instruments"] = UNMEASURED
    cov = _read(DATA / "intelligence" / "coverage_registry.json")
    plats = (cov or {}).get("platforms") if isinstance(cov, dict) else None
    if isinstance(plats, dict):
        out["alt_platforms"] = len(plats)
        out["alt_platforms_yielding"] = sum(
            1 for p in plats.values() if isinstance(p, dict) and (p.get("best_rows") or 0) > 0
            and str(p.get("last_state") or "") == "ok")
    forest = _read(DATA / "deep_forest_frontier.json")
    vec = (forest or {}).get("vectors") if isinstance(forest, dict) else None
    if isinstance(vec, dict):
        oc = Counter(str((v or {}).get("outcome") or "?") for v in vec.values())
        out["forest_vectors"] = len(vec)
        out["forest_by_outcome"] = dict(oc)
    since = now - timedelta(hours=24)
    n = sum(1 for _ in _jsonl(DATA / "ingestion_ledger.jsonl", since))
    out["ingestion_rows_24h"] = n if (DATA / "ingestion_ledger.jsonl").exists() else UNMEASURED
    alt = _read(REPORTS / "ALT_DATA_YIELD.json")
    if isinstance(alt, dict):
        out["alt_data_yield"] = {k: v for k, v in alt.items() if not isinstance(v, (dict, list))}
    return out


def mining_and_judging(now: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cov = _read(REPORTS / "JUDGE_COVERAGE.json")
    tot = (cov or {}).get("totals") if isinstance(cov, dict) else None
    if isinstance(tot, dict):
        for k in ("docket_rows", "mined", "families_mined", "families_unmined", "unjudged_total",
                  "oldest_unjudged_age_h", "drain_status", "backlog_growth_per_hour",
                  "capacity_sustained_per_hour", "hours_to_drain", "unrunnable_bank"):
            out[k] = tot.get(k, UNMEASURED)
    rate = _read(REPORTS / "JUDGING_RATE.json")
    if isinstance(rate, dict):
        out["cells_created_per_day"] = rate.get("created_per_day", UNMEASURED)
        out["verdicts_per_day"] = rate.get("verdicts_per_day", UNMEASURED)
    mass = _read(REPORTS / "MASS_SCREEN.json")
    if isinstance(mass, dict):
        out["mass_screen"] = {k: v for k, v in mass.items() if not isinstance(v, (dict, list))}
        for key in ("cells_screened_per_day", "screened_per_day", "cells_per_day"):
            v = mass.get(key)
            if isinstance(v, (int, float)):
                out["cells_screened_per_day"] = v
                break
    since = now - timedelta(days=7)
    gates: Counter[str] = Counter()
    for row in _jsonl(HYP / "gate_verdict_ledger.jsonl", since):
        gates[str(row.get("terminal_gate") or "UNKNOWN")] += 1
    total = sum(gates.values())
    if total:
        out["verdicts_7d"] = total
        out["verdicts_7d_by_gate"] = dict(gates.most_common())
        out["unknown_share_7d"] = round(gates.get("UNKNOWN", 0) / total, 4)
        out["passed_7d"] = gates.get("PASSED", 0)
    else:
        out["unknown_share_7d"] = UNMEASURED
    ge = _read(REPORTS / "universal_gates_external.json")
    pw = (ge or {}).get("prewarm") if isinstance(ge, dict) else None
    if isinstance(pw, dict):
        sub, fail = pw.get("submitted") or 0, pw.get("failed") or 0
        out["prewarm_failed"] = fail
        out["prewarm_submitted"] = sub
        out["prewarm_fail_share"] = round(fail / sub, 4) if sub else UNMEASURED
        out["prewarm_failures_by_kind"] = pw.get("failures")
    return out


def _cert_family(key: str, v: dict[str, Any]) -> str:
    fam = v.get("family")
    if fam:
        return str(fam)
    parts = key.split(".")
    return parts[2] if len(parts) >= 3 else key


def edges_and_live(now: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {}
    canon = _read(DATA / "UNIVERSAL_SURVIVORS.canon.json") or _read(
        REPORTS / "UNIVERSAL_SURVIVORS.json")
    surv = (canon or {}).get("survivors") if isinstance(canon, dict) else None
    if isinstance(surv, dict):
        fams = Counter(_cert_family(k, v) for k, v in surv.items() if isinstance(v, dict))
        syms = {str(v.get("sym") or v.get("symbol") or "") for v in surv.values()
                if isinstance(v, dict)}
        out["certificates"] = len(surv)
        out["cert_families"] = len(fams)
        out["cert_symbols"] = len(syms - {""})
        top = fams.most_common(1)
        out["cert_top_family_share"] = (round(top[0][1] / max(len(surv), 1), 4)
                                        if top else UNMEASURED)
        out["cert_by_family"] = dict(fams.most_common())
    else:
        out["certificates"] = UNMEASURED
    eb_last = None
    for row in _jsonl(DATA / "effective_breadth.jsonl"):
        eb_last = row
    if eb_last:
        out["effective_breadth"] = eb_last.get("effective_breadth", UNMEASURED)
        out["breadth_nominal"] = eb_last.get("n_nominal")
        out["clusters_occupied"] = eb_last.get("n_clusters_occupied")
        out["clusters_empty"] = eb_last.get("n_clusters_empty")
        out["breadth_at"] = eb_last.get("at")
    else:
        out["effective_breadth"] = UNMEASURED
    sl = _read(DATA / "sleeves.json")
    rows = (sl or {}).get("sleeves") if isinstance(sl, dict) else None
    if isinstance(rows, list):
        live = [r for r in rows if isinstance(r, dict) and r.get("status") == "LIVE"]
        out["live_sleeves"] = len(live)
        out["live_admission_unmeasured"] = sum(
            1 for r in live if str((r.get("admission") or {}).get("status") or "") == "UNMEASURED")
        out["live_banned_discovered"] = sum(1 for r in live if r.get("family") == "discovered")
    since = now - timedelta(days=30)
    per_day: dict[str, set[str]] = {}
    trades = 0
    for row in _jsonl(DATA / "live_ledger.jsonl", since, at_key="time"):
        trades += 1
        d = str(row.get("time"))[:10]
        per_day.setdefault(d, set()).add(str(row.get("symbol") or ""))
    if per_day:
        counts = sorted(len(v) for v in per_day.values())
        out["live_trades_30d"] = trades
        out["live_symbols_30d"] = len(set().union(*per_day.values()) - {""})
        out["live_symbols_per_day_median"] = counts[len(counts) // 2]
    else:
        out["live_symbols_per_day_median"] = UNMEASURED
    prod = _read(REPORTS / "RESEARCH_PRODUCTIVITY.json")
    if isinstance(prod, dict):
        conv = prod.get("conversion") if isinstance(prod.get("conversion"), dict) else prod
        for k in ("certified_to_forward", "cert_to_forward"):
            v = conv.get(k) if isinstance(conv, dict) else None
            if isinstance(v, (int, float)):
                out["cert_to_forward"] = v
                break
    xs = _read(REPORTS / "CROSS_SECTIONAL_BREADTH.json")
    if isinstance(xs, dict):
        out["cross_sectional"] = {k: v for k, v in xs.items() if not isinstance(v, (dict, list))}
    return out


def gap_table(m: dict[str, Any]) -> list[dict[str, Any]]:
    """Each measure beside its tier-1 reference; ranked by how many orders of magnitude short."""
    rows: list[dict[str, Any]] = []
    lower_is_better = {"unknown_share_7d"}
    for key, (ref, why) in TIER1.items():
        us = m.get(key, UNMEASURED)
        if key == "cells_created_per_day" and isinstance(m.get("cells_screened_per_day"),
                                                         (int, float)):
            us = max(us if isinstance(us, (int, float)) else 0, m["cells_screened_per_day"])
        row: dict[str, Any] = {"measure": key, "us": us, "tier1": ref, "tier1_basis": why}
        if isinstance(us, (int, float)) and us > 0:
            ratio = (us / ref) if key in lower_is_better else (ref / us)
            row["times_short"] = round(ratio, 2)
            row["orders_short"] = round(math.log10(max(ratio, 1e-9)), 2)
        elif isinstance(us, (int, float)):
            row["times_short"] = None
            row["orders_short"] = 9.0          # zero of a thing tier-1 has: the widest gap
        else:
            row["times_short"] = UNMEASURED
            row["orders_short"] = None
        rows.append(row)
    rows.sort(key=lambda r: -(r["orders_short"] if isinstance(r["orders_short"], float)
                              else -1.0))
    return rows


def build(now: datetime | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    ing = ingestion(t)
    mj = mining_and_judging(t)
    el = edges_and_live(t)
    flat = {**ing, **mj, **el}
    return {
        "at": t.isoformat(timespec="seconds"),
        "reference_basis": "tier-1 references are public estimates; desk values are measured "
                           "from this box's artifacts every hour",
        "ingestion": ing, "mining_and_judging": mj, "edges_and_live": el,
        "gaps": gap_table(flat),
        "sources": {p.name: _mtime(p) for p in (
            DATA / "data_registry.json", REPORTS / "JUDGE_COVERAGE.json",
            REPORTS / "JUDGING_RATE.json", HYP / "gate_verdict_ledger.jsonl",
            REPORTS / "universal_gates_external.json", DATA / "UNIVERSAL_SURVIVORS.canon.json",
            DATA / "effective_breadth.jsonl", DATA / "sleeves.json", DATA / "live_ledger.jsonl",
            REPORTS / "DATASET_HUNT.json", REPORTS / "MASS_SCREEN.json",
            REPORTS / "ALT_DATA_YIELD.json", REPORTS / "CROSS_SECTIONAL_BREADTH.json")},
    }


def write(doc: dict[str, Any], path: Path | None = None) -> None:
    target = path or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        tmp.replace(target)
    except OSError:                       # Windows: a reader holding the file; write in place
        target.write_text(tmp.read_text("utf-8"), "utf-8")
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    doc = build()
    doc["elapsed_s"] = round(time.time() - t0, 2)
    if not args.no_write:
        write(doc)
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for g in doc["gaps"]:
            print(f"  {g['measure']:<28} us={g['us']!s:<14} tier1={g['tier1']!s:<10} "
                  f"x{g['times_short']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
