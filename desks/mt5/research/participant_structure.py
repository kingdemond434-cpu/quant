"""PARTICIPANT STRUCTURE -- which symbols are retail-heavy, from positioning the desk holds.

WHY (build_check row 103, C_DEDUPE 2026-11-18). A market whose open interest is held largely by
small traders behaves differently from one held by dealers and asset managers: crowding,
round-number stops, attention-driven flows (the A-share retail bias High-Flyer trades, the crypto
retail crowd). The breadth enforcer treated every symbol as one population, so a cluster of
retail-heavy markets could go unexplored while the budget went to the institutional majors.

WHAT IS MEASURED, AND FROM WHAT. Only what the desk already holds:

    gross_small_share   CFTC legacy COT (`data/cot/*.parquet`): the non-reportable (small
                        trader) share of gross positions over the last 52 reports,
                            1 - (noncomm long+short + comm long+short) / (2 x open interest).
                        Non-commercial SPREADING positions are not in the held files, so this is
                        an UPPER BOUND on the small-trader share; it is the same bound on every
                        market, so the ranking is what is used, never the level.
    net_small_share     the axis rows (`data/axes/cot.json`): |net non-reportable| / open
                        interest, net_nonrept = -(net_noncommercial + net_commercial). A crowding
                        reading, published beside the gross share, never used to tag.
    retail crowd        myfxbook's community outlook is behind a managed challenge
                        (ANTIBOT_CHALLENGE since 2026-08-26) and the retail_crowd recorder (#772)
                        is not on this tree, so the crowd leg is UNMEASURED and says so.

THE TAG. Among symbols with a fresh gross reading (last report within FRESH_DAYS), the upper
tercile is RETAIL_HEAVY and the rest INSTITUTIONAL. Everything else is UNMEASURED -- absent
positioning is not evidence of an institutional market.

THE CLUSTER'S OWN EXPLORATION FLOOR. The floor is the cluster's share of the measured symbols,
bounded to FLOOR_BOUNDS: the retail-heavy cluster is never explored below its population share.
`breadth_ladder` publishes it under `cluster_floors` and `breadth_sweep` honours it when a run's
cap binds (reorder, never filter); `market_ecology` reports the tags beside its footprints.
UNMEASURED publishes no floor, and no floor reallocates anything by itself.

    python desks/mt5/research/participant_structure.py [--dry-run]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
COT_DIR = DESK / "data" / "cot"
AXIS = DESK / "data" / "axes" / "cot.json"
OUT = DESK / "reports" / "PARTICIPANT_STRUCTURE.json"
CLUSTER = "retail_heavy"
WINDOW = 52
FRESH_DAYS = 120
FLOOR_BOUNDS = (0.05, 0.5)
UNMEASURED = "UNMEASURED"
#: A legacy COT report carries Tuesday's positions and is published the following Friday, so a
#: row is knowable only COT_RELEASE_LAG_DAYS after its report_date (the same lag
#: orthogonal_sweep applies). Rows not yet published at `now` are dropped, and freshness is aged
#: from publication, not from the positions date. The CFTC releases at 15:30 ET, which is 20:30
#: UTC in winter and 19:30 UTC in summer, so a row is knowable from Friday 21:00 UTC (the later
#: of the two); a Friday reading taken before the release must not see that week's report.
COT_RELEASE_LAG_DAYS = 3
COT_RELEASE_HOUR_UTC = 21

#: Held legacy COT file -> MT5 symbol. SEED, not a boundary: a file not named here is reported
#: as unmapped, never silently dropped.
COT_FILES: dict[str, str] = {
    "aud": "AUDUSD", "cad": "USDCAD", "chf": "USDCHF", "dxy": "USDX", "gbp": "GBPUSD",
    "gold": "XAUUSD", "jpy": "USDJPY", "nasdaq100": "NAS100", "nzd": "NZDUSD",
    "silver": "XAGUSD", "sp500": "US500",
}


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def gross_small_share(path: Path, now: datetime) -> dict[str, Any]:
    try:
        import pandas as pd
        df = pd.read_parquet(path)
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"unreadable ({type(exc).__name__})"}
    need = ("report_date", "open_interest_all", "noncomm_positions_long_all",
            "noncomm_positions_short_all", "comm_positions_long_all", "comm_positions_short_all")
    if any(c not in df.columns for c in need) or df.empty:
        return {"status": UNMEASURED, "why": "missing legacy columns"}
    lag = pd.Timedelta(days=COT_RELEASE_LAG_DAYS, hours=COT_RELEASE_HOUR_UTC)
    known_at = pd.to_datetime(df["report_date"], utc=True) + lag
    df = df[known_at <= pd.Timestamp(now)].sort_values("report_date").tail(WINDOW)
    if df.empty:
        return {"status": UNMEASURED, "why": "no report published by now"}
    oi = df["open_interest_all"].astype(float)
    held = (df["noncomm_positions_long_all"] + df["noncomm_positions_short_all"]
            + df["comm_positions_long_all"] + df["comm_positions_short_all"]).astype(float)
    share = (1.0 - held / (2.0 * oi)).where(oi > 0).dropna()
    last = pd.Timestamp(df["report_date"].iloc[-1])
    last = last.tz_localize("UTC") if last.tzinfo is None else last
    age = (now - (last + lag).to_pydatetime()).days
    if share.empty:
        return {"status": UNMEASURED, "why": "no open interest"}
    row = {"gross_small_share": round(float(share.mean()), 4), "n_reports": len(share),
           "last_report": last.date().isoformat(), "age_days": int(age),
           "contract": str(df.get("contract_market_name", df["report_date"]).iloc[-1])}
    if age > FRESH_DAYS:
        return {**row, "status": "STALE",
                "why": f"last report {age} days old (> {FRESH_DAYS}); not used to tag"}
    return {**row, "status": "MEASURED"}


def net_small_shares(axis: dict[str, Any]) -> dict[str, float]:
    rows = axis.get("rows")
    if isinstance(rows, str):
        try:
            rows = ast.literal_eval(rows)
        except (ValueError, SyntaxError):
            rows = []
    acc: dict[str, list[float]] = {}
    for r in rows if isinstance(rows, list) else []:
        try:
            oi = float(r["open_interest"])
            v = abs(-(float(r["net_noncommercial"]) + float(r["net_commercial"]))) / oi
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        acc.setdefault(str(r.get("symbol")), []).append(v)
    return {s: round(sum(v[-WINDOW:]) / len(v[-WINDOW:]), 4) for s, v in acc.items() if v}


def build(now: datetime | None = None, cot_dir: Path | None = None,
          axis_path: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    cdir = cot_dir or COT_DIR
    per: dict[str, dict[str, Any]] = {}
    unmapped = []
    for f in sorted(cdir.glob("*.parquet")) if cdir.exists() else []:
        sym = COT_FILES.get(f.stem)
        if not sym:
            unmapped.append(f.name)
            continue
        per[sym] = {"source": f"data/cot/{f.name}", **gross_small_share(f, now)}
    net = net_small_shares(_read(axis_path or AXIS))
    for sym, v in net.items():
        per.setdefault(sym, {"status": UNMEASURED, "why": "no gross legacy file held"})
        per[sym]["net_small_share"] = v
    measured = {s: r["gross_small_share"] for s, r in per.items() if r.get("status") == "MEASURED"}
    tags: dict[str, str] = dict.fromkeys(per, UNMEASURED)
    floor: dict[str, Any]
    if len(measured) >= 3:
        ranked = sorted(measured, key=lambda s: measured[s], reverse=True)
        n_heavy = max(1, len(ranked) // 3)
        for i, s in enumerate(ranked):
            tags[s] = "RETAIL_HEAVY" if i < n_heavy else "INSTITUTIONAL"
        cut = measured[ranked[n_heavy - 1]]
        raw = n_heavy / len(ranked)
        floor = {"floor": round(min(FLOOR_BOUNDS[1], max(FLOOR_BOUNDS[0], raw)), 3),
                 "raw": round(raw, 4), "cut_gross_small_share": cut,
                 "basis": "retail-heavy share of the symbols with a fresh gross COT reading"}
    else:
        floor = {"floor": None, "raw": None,
                 "basis": f"UNMEASURED: {len(measured)} fresh reading(s), fewer than 3"}
    members = sorted(s for s, t in tags.items() if t == "RETAIL_HEAVY")
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "MEASURED" if members else UNMEASURED,
        "cluster": CLUSTER, "members": members,
        "n_members": len(members), "n_measured": len(measured),
        "tags": dict(sorted(tags.items())), "per_symbol": dict(sorted(per.items())),
        "exploration_floor": floor,
        "crowd": {"status": UNMEASURED,
                  "why": ("myfxbook community outlook walled (ANTIBOT_CHALLENGE since 2026-08-26); "
                          "retail_crowd recorder (#772) not on this tree")},
        "unmapped_files": unmapped,
        "rule": ("upper tercile of fresh gross small-trader share is RETAIL_HEAVY; the cluster's "
                 f"floor is its share of measured symbols, bounded to {list(FLOOR_BOUNDS)}; "
                 "absent positioning is UNMEASURED, never institutional"),
        "consumers": ["breadth_ladder.cluster_floors", "breadth_sweep.cluster floor order",
                      "market_ecology.participant_structure"],
    }


def load(path: Path | None = None) -> dict[str, Any]:
    return _read(path or OUT)


def cluster_floor(doc: dict[str, Any] | None = None) -> tuple[set[str], float | None]:
    """(members, floor) from the published report; (empty, None) when UNMEASURED."""
    d = doc if doc is not None else load()
    members = {str(s) for s in (d.get("members") or [])}
    fl = (d.get("exploration_floor") or {}).get("floor")
    return (members, float(fl)) if members and isinstance(fl, (int, float)) else (set(), None)


def order_with_floor(rows: list[dict[str, Any]], cap: int, members: set[str],
                     floor: float | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """REORDER, NEVER FILTER. When `cap` binds, pull the cluster's rows forward (keeping their
    own order) until they make up at least `floor` of the first `cap`. Every row is returned."""
    stats: dict[str, Any] = {"cluster": CLUSTER, "floor": floor, "cap": cap, "moved": 0}
    if not members or floor is None or cap <= 0 or len(rows) <= cap:
        stats["why"] = "cap does not bind or cluster UNMEASURED: order unchanged"
        return rows, stats
    want = round(floor * cap)
    head = rows[:cap]
    have = sum(1 for r in head if str(r.get("symbol")) in members)
    stats["in_head_before"] = have
    if have >= want:
        stats["why"] = "the cluster already holds its floor inside the cap"
        return rows, stats
    tail = rows[cap:]
    pull = [r for r in tail if str(r.get("symbol")) in members][: want - have]
    if not pull:
        stats["why"] = "no cluster rows beyond the cap to pull forward"
        return rows, stats
    pulled = {id(r) for r in pull}
    drop = [r for r in reversed(head) if str(r.get("symbol")) not in members][: len(pull)]
    dropped = {id(r) for r in drop}
    new_head = [r for r in head if id(r) not in dropped] + pull
    new_tail = drop[::-1] + [r for r in tail if id(r) not in pulled]
    stats.update({"moved": len(pull), "in_head_after": have + len(pull),
                  "why": f"pulled {len(pull)} {CLUSTER} row(s) inside the cap"})
    return new_head + new_tail, stats


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"participant structure: {doc['status']} {CLUSTER}={doc['members']} "
          f"floor={doc['exploration_floor'].get('floor')} ({doc['exploration_floor']['basis']})")
    for s, r in doc["per_symbol"].items():
        print(f"  {s:<8} {doc['tags'][s]:<14} gross={r.get('gross_small_share')} "
              f"net={r.get('net_small_share')} {r.get('status')}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
