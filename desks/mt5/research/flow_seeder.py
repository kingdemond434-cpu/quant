#!/usr/bin/env python3
"""FLOW SEEDER: COT positioning, the tick tape's signed-tick imbalance and the equity-option
expiry calendar reach the judge again, on gold, indices and FX majors first.

    python desks/mt5/research/flow_seeder.py --once --budget-s 600
    python desks/mt5/research/flow_seeder.py --once --dry-run      # measure, donate nothing

WHY (hourly pass, 2026-11-13: each of these producers made 0 cells in 24h).
  COT       `cot`, `miner:cot`, `run_cot_screen`, `screen_cot_positioning` and the `quant-cot-*`
            timers are VPS-side or unscheduled: `side_channels/cot_miner.py` is reachable only
            from `side_channels/run_all_miners.py`, which no clock runs; the timers write the
            VPS's root `data/cot_zcache.parquet`, which is gitignored and never reaches the box
            whose gauntlet reads it (`orthogonal_sweep._cot_frame`); and the four raw `cot_*`
            families were set aside as INPUT_NOT_SUPPLIED by `gauntlet_buildability`, whose scan
            of `build_cell` missed `family in RAW_COT_FAMILIES`. All three are fixed beside this
            organ; this organ is the clock that mints them.
  ORDERFLOW `orderflow_imbalance` had no producer that named a tape-backed cell; it now loads the
            whole silver tape itself (`flow_source="tape_signed_ticks"`, `families_flow`).
  GAMMA     `us:custom:expiry_gamma_calendar` is unwired (`countries/us/pack.py`) and an event
            study, not a cell; `expiry_gamma` puts the third-Friday calendar on index bars.

WHAT IT DOES. Enumerates, in book-gap order (gold, indices, FX majors; no symbol whose registry
class says exotic): `cot_report` over every CFTC report the desk holds in-tree (legacy, TFF,
disaggregated) per trader group and mode; the raw legacy `cot_*` families and `cot_positioning`
on the symbols the legacy file maps; `expiry_gamma` over the expiry set x window x direction x
decision hour on US and European indices; and `orderflow_imbalance` on every non-exotic symbol
the tick recorder has a silver tape for. Every cell takes the specialist path unchanged:
`gauntlet_buildability.cell_verdict`, the SEALED `build_cell` (via `specialist_cell.measure`),
the 66 lower-bound trade-day floor, `proposer_common.donate` into `data/intelligence/
flow_seeder/`, and the trial census (`specialist_cell.charge`) over every cell measured. A cell
is re-measured at most once a week; a pass that runs out of budget resumes next hour. The report
also says how old each COT file is, because a stale report is a cell that will never fire
forward -- UNMEASURED and STALE are answers, never zeros. Additive: no other miner is touched.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "flow_seeder"
OUT = BASE / "reports" / "FLOW_SEEDER.json"
STATE = BASE / "data" / "flow_seeder_state.json"
SEED_FLOOR = 66
REMEASURE_DAYS = 7
#: Seconds between state saves inside a pass, so a leg killed at its budget keeps what it
#: measured instead of repeating it every hour (Auditor SF3 on #845, 2026-11-13).
SAVE_EVERY_S = 30.0
#: A COT file whose newest report is older than this cannot fire forward.
COT_STALE_DAYS = 14

#: (bucket, symbol aliases, [(report, market slug, sign)]). sign -1 where the future is the
#: QUOTE currency. The legacy S&P/Nasdaq files stop in 2021, so indices read the TFF report.
COT_MAP: tuple[tuple[str, tuple[str, ...], tuple[tuple[str, str, int], ...]], ...] = (
    ("gold", ("XAUUSD",), (("legacy", "gold", 1), ("disagg", "gold", 1))),
    ("gold", ("XAGUSD",), (("legacy", "silver", 1), ("disagg", "silver", 1))),
    ("index", ("US500", "SPX500", "US500.cash"), (("tff", "sp500", 1),)),
    ("index", ("NAS100", "USTEC", "US100"), (("tff", "nasdaq100", 1),)),
    ("major", ("EURUSD",), (("tff", "eur", 1),)),
    ("major", ("GBPUSD",), (("legacy", "gbp", 1), ("tff", "gbp", 1))),
    ("major", ("USDJPY",), (("legacy", "jpy", -1), ("tff", "jpy", -1))),
    ("major", ("AUDUSD",), (("legacy", "aud", 1), ("tff", "aud", 1))),
    ("major", ("NZDUSD",), (("legacy", "nzd", 1), ("tff", "nzd", 1))),
    ("major", ("USDCAD",), (("legacy", "cad", -1), ("tff", "cad", -1))),
    ("major", ("USDCHF",), (("legacy", "chf", -1), ("tff", "chf", -1))),
)
#: The raw legacy families and their registered grids (`families.register_family`).
RAW_COT_GRID: tuple[tuple[str, dict[str, list]], ...] = (
    ("cot_net_fade", {"lo_q": [0.05, 0.10], "hi_q": [0.90, 0.95]}),
    ("cot_change_fade", {"z_thresh": [1.0, 1.5, 2.0]}),
    ("cot_change_momentum", {}),
    ("cot_comm_follow", {}),
    ("cot_positioning", {"lookback_weeks": [104, 156], "extreme_pct": [0.85, 0.90, 0.95]}),
)
RAW_COT_SYMBOLS = ("XAUUSD", "XAGUSD", "USDJPY", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF")
#: Equity indices whose venue lists third-Friday options (US and Eurex/Euronext/ICE).
GAMMA_INDICES: tuple[tuple[str, ...], ...] = (
    ("US500", "SPX500", "US500.cash"), ("NAS100", "USTEC", "US100"), ("US30", "DJ30"),
    ("US2000", "RUSSELL2000"), ("GER40", "DE40"), ("EUSTX50", "EU50"))
#: (label, day_from, day_to) in weekdays from the third Friday.
GAMMA_WINDOWS = (("opex_week", -4, 0), ("opex_day", 0, 0), ("monday_after", 1, 1),
                 ("week_after", 1, 5))
#: Broker clock (New York + 7): 16 = 09:00 NY, the decision bar just BEFORE the 09:30 cash open
#: (entry at the next bar, 10:00 NY); 22 = 15:00 NY, the last hour into the cash close.
GAMMA_HOURS = (16, 22)
TAPE_PRIORITY: tuple[str, ...] = (
    "XAUUSD", "XAGUSD", "US500", "NAS100", "USTEC", "US30", "GER40", "UK100", "JPN225",
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _grid(spec: dict[str, list]) -> list[dict[str, Any]]:
    import itertools
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]


def admissible(symbol: str, family: str) -> bool:
    """In the registry, hypothesis lane, and not exotic by the registry's own class."""
    from research import universe_policy as up
    if symbol not in up._registry() or not up.may_hypothesise(symbol, family):
        return False
    return "exotic" not in str(up.asset_class_of(symbol) or "").lower()


def _resolve(aliases: tuple[str, ...], family: str) -> str | None:
    return next((s for s in aliases if admissible(s, family)), None)


def cot_cells() -> list[dict[str, Any]]:
    from mt5desk.families_flow import COT_GROUPS
    out: list[dict[str, Any]] = []
    for bucket, aliases, reports in COT_MAP:
        sym = _resolve(aliases, "cot_report")
        if sym is None:
            continue
        for report, market, sign in reports:
            for group in COT_GROUPS[report]:
                base = {"report": report, "market": market, "group": group, "sign": sign}
                points = ([{"mode": m, "lookback_w": lb, "q": q}
                           for m in ("extreme_fade", "extreme_follow")
                           for lb in (52, 104, 156) for q in (0.10, 0.20)]
                          + [{"mode": m, "lookback_w": 52, "z_thr": z}
                             for m in ("change_follow", "change_fade") for z in (1.0, 1.5)])
                for pt in points:
                    out.append({"bucket": bucket, "symbol": sym, "family": "cot_report",
                                "mechanism": f"cot_report.{report}.{group}.{pt['mode']}",
                                "params": {**base, **pt}})
    for sym in RAW_COT_SYMBOLS:
        bucket = "gold" if sym.startswith("XA") else "major"
        for fam, spec in RAW_COT_GRID:
            if not admissible(sym, fam):
                continue
            for pt in (_grid(spec) if spec else [{}]):
                params = dict(pt)
                if fam == "cot_positioning":
                    params["input_source"] = "cot_point_in_time"
                out.append({"bucket": bucket, "symbol": sym, "family": fam, "mechanism": fam,
                            "params": params})
    return out


def gamma_cells() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for aliases in GAMMA_INDICES:
        sym = _resolve(aliases, "expiry_gamma")
        if sym is None:
            continue
        for expiry in ("all", "monthly", "quad"):
            for label, lo, hi in GAMMA_WINDOWS:
                for direction in ("long", "short", "follow", "fade"):
                    for hour in GAMMA_HOURS:
                        out.append({"bucket": "index", "symbol": sym, "family": "expiry_gamma",
                                    "mechanism": f"expiry_gamma.{label}.{direction}",
                                    "params": {"expiry": expiry, "day_from": lo, "day_to": hi,
                                               "direction": direction,
                                               "decision_hour": hour}})
    return out


def pin_cells() -> list[dict[str, Any]]:
    """Archived idea 232: XAUUSD pinned to the $25 strike grid into COMEX gold option expiry."""
    if not admissible("XAUUSD", "strike_pin"):
        return []
    return [{"bucket": "gold", "symbol": "XAUUSD", "family": "strike_pin",
             "mechanism": f"strike_pin.comex_gold.{mode}",
             "params": {"grid": 25.0, "day_from": lo, "day_to": 0, "mode": mode,
                        "decision_hour": hour, "max_frac": frac}}
            for lo in (-3, -1) for mode in ("pin", "unpin") for hour in (16, 20)
            for frac in (0.3, 0.5)]


def tape_cells() -> list[dict[str, Any]]:
    from mt5desk.families_flow import TAPE_FLOW_SOURCE, tape_days
    out: list[dict[str, Any]] = []
    for sym in TAPE_PRIORITY:
        if not admissible(sym, "orderflow_imbalance") or not tape_days(sym):
            continue
        bucket = ("gold" if sym.startswith("XA") else "major" if len(sym) == 6
                  and sym.isalpha() else "index")
        for lookback in (24, 48):
            for z in (1.5, 2.0, 2.5):
                out.append({"bucket": bucket, "symbol": sym, "family": "orderflow_imbalance",
                            "mechanism": "orderflow_imbalance.tape_signed_ticks",
                            "params": {"symbol": sym, "flow_source": TAPE_FLOW_SOURCE,
                                       "lookback": lookback, "z_in": z}})
    return out


def plan() -> list[dict[str, Any]]:
    return cot_cells() + pin_cells() + gamma_cells() + tape_cells()


def cot_freshness(today: date | None = None) -> dict[str, Any]:
    """Newest report date per in-tree CFTC file, and whether it can still fire forward."""
    from mt5desk.families_flow import COT_DIRS, COT_RELEASE_LAG_D, cot_table
    today = today or datetime.now(tz=UTC).date()
    out: dict[str, Any] = {}
    for _bucket, _aliases, reports in COT_MAP:
        for report, market, _sign in reports:
            key = f"{report}/{market}"
            if key in out or report not in COT_DIRS:
                continue
            table = cot_table(report, market)
            if table is None or table.empty:
                out[key] = {"status": "UNMEASURED", "why": "no readable file on this host"}
                continue
            last = table["report_date"].max().date()
            age = (today - last).days
            from mt5desk.market_calendar import cot_usable_at
            when = cot_usable_at(last)
            usable_at = (when.date() if when is not None
                         else last + timedelta(days=COT_RELEASE_LAG_D))
            out[key] = {"last_report": last.isoformat(), "usable_at": usable_at.isoformat(),
                        "age_days": age,
                        "status": "STALE" if age > COT_STALE_DAYS else "FRESH"}
    return out


def tape_freshness(today: date | None = None) -> dict[str, Any]:
    """Per tape symbol: how many silver days exist and whether today's is built yet. A cell on a
    tape whose current day is absent cannot fire forward, and that is said, never left silent
    (Auditor SF4 on #845, 2026-11-13)."""
    from mt5desk.families_flow import tape_days
    today = today or datetime.now(tz=UTC).date()
    out: dict[str, Any] = {}
    for sym in TAPE_PRIORITY:
        days = tape_days(sym)
        if not days:
            continue
        last = days[-1].split(".")[0]
        try:
            lag = (today - date.fromisoformat(last[:10])).days
        except ValueError:
            out[sym] = {"days": len(days), "last_day": last, "status": "UNMEASURED"}
            continue
        out[sym] = {"days": len(days), "last_day": last, "floor_trade_days": SEED_FLOOR,
                    # today's silver day is built after the day closes, so a 1-day lag is
                    # normal and still means today's bars cannot fire yet; 2+ is a stalled tape
                    "status": ("CURRENT" if lag <= 0 else "TAPE_NOT_BUILT_TODAY" if lag == 1
                               else f"TAPE_BEHIND_{lag}_DAYS")}
    return out


def _load_state() -> dict[str, Any]:
    try:
        doc = json.loads(STATE.read_text("utf-8"))
    except (OSError, ValueError):
        doc = None
    return doc if isinstance(doc, dict) and isinstance(doc.get("cells"), dict) else {"cells": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), "utf-8")
    tmp.replace(STATE)


def safe_why(why: object) -> str:
    """A build refusal with any exception MESSAGE cut off after its class name (one rule:
    `specialist_cell.safe_why`; Auditor MF4 -- `BLOCKED_DATA: raw COT for X: OSError: <path>`)."""
    from research.specialist_cell import safe_why as _safe
    return _safe(why)


def _stale(day: str | None, today: date) -> bool:
    try:
        return (today - date.fromisoformat(str(day))).days >= REMEASURE_DAYS
    except ValueError:
        return True


def seed(*, budget_s: float = 600.0, dry_run: bool = False,
         cells: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from research import specialist_cell as sc
    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    started = time.monotonic()
    last_save = started
    today = datetime.now(tz=UTC).date()
    grid = plan() if cells is None else cells
    meta = sc._meta()
    state = _load_state()
    cs: dict[str, Any] = state["cells"]
    by_family: dict[str, Counter] = {}
    gaps: Counter = Counter()
    measured_now: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    stopped = "grid exhausted"
    for c in grid:
        row = by_family.setdefault(c["family"], Counter())
        row["grid"] += 1
        verdict, why = cell_verdict(c["family"], c["params"])
        if verdict != BUILDABLE:
            row["set_aside_unbuildable"] += 1
            gaps[f"{c['family']}: {verdict}: {why[:100]}"] += 1
            continue
        ident = sc.identity(c["symbol"], c["family"], c["params"])
        prior = cs.get(ident) or {}
        if _stale(prior.get("day"), today):
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached; resumes next pass"
                row["not_reached_this_pass"] += 1
                continue
            got = sc.measure(c["symbol"], c["family"], c["params"], meta)
            if "why" in got:
                got["why"] = safe_why(got["why"])
            prior = {**prior, **got, "day": today.isoformat(),
                     **{k: c[k] for k in ("bucket", "symbol", "family", "mechanism", "params")}}
            cs[ident] = prior
            measured_now.append(c)
            if not dry_run and time.monotonic() - last_save > SAVE_EVERY_S:
                _save_state(state)
                last_save = time.monotonic()
            row["measured_this_pass"] += 1
        if not prior.get("built"):
            row["input_gap"] += 1
            gaps[f"{c['family']}: {safe_why(prior.get('why'))[:110]}"] += 1
            continue
        if not int(prior.get("signal_days") or 0):
            row["built_but_zero_signals"] += 1
        if int(prior.get("trade_days_lb") or 0) < SEED_FLOOR:
            row["held_back_under_floor"] += 1
            continue
        row["clears_floor"] += 1
        if not prior.get("donated_at"):
            cands.append({**c, "ident": ident,
                          "firing": {k: prior.get(k) for k in ("signal_days", "trade_days_lb")}})

    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if cands and not dry_run:
        from research import proposer_common as pc
        rows = [pc.candidate(
            SOURCE, c["symbol"], c["family"], c["params"],
            f"{c['mechanism']} on {c['symbol']} ({c['bucket']}): flow from a named participant "
            "-- reported positioning, the option dealer's expiry hedge, or the tape's own "
            "signed ticks",
            f"{c['symbol']} {c['mechanism']} via {c['family']}",
            {"firing": c["firing"], "seed_floor": SEED_FLOOR, "book_gap_bucket": c["bucket"],
             "built_by": "external_gauntlet.build_cell (sealed), measured on its own output"})
            for c in cands]
        for r, c in zip(rows, cands, strict=True):
            r["breadth_unit"] = f"flow/{c['mechanism']}"
        path = pc.donate(SOURCE, rows, len(measured_now) or len(rows))
        counts = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None, **{
                        k: counts.get(k) for k in ("donated", "refused_wrong_lane",
                                                   "refused_unstamped", "registry_error")}}
        if path:
            at = _now()
            for c in cands:
                cs[c["ident"]]["donated_at"] = at
                by_family[c["family"]]["donated_this_pass"] += 1
    if not dry_run:
        _save_state(state)
    donated_total = Counter(str(v.get("family")) for v in cs.values() if v.get("donated_at"))
    return {
        "status": "OK", "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2), "seed_floor_trade_days": SEED_FLOOR,
        "grid": len(grid), "measured_this_pass": len(measured_now),
        "candidates_this_pass": len(cands), "donation": donation,
        "by_family": {k: dict(v) for k, v in by_family.items()},
        "donated_total_by_family": dict(donated_total),
        "trial_charge_this_pass": sc.charge([{**c, "klass": c["bucket"]}
                                             for c in measured_now]),
        "input_gaps": dict(gaps.most_common(20)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        rep = seed(budget_s=a.budget_s, dry_run=a.dry_run)
    except Exception as exc:              # an organ that fails says so in its own artifact
        rep = {"status": f"FAILED: {type(exc).__name__}"}
    try:
        rep["cot_data"] = cot_freshness()
    except Exception as exc:
        rep["cot_data"] = {"status": f"UNMEASURED: {type(exc).__name__}"}
    try:
        rep["tape_data"] = tape_freshness()
    except Exception as exc:
        rep["tape_data"] = {"status": f"UNMEASURED: {type(exc).__name__}"}
    rep["generated_utc"] = _now()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(rep, indent=1, sort_keys=True, default=str), "utf-8")
    tmp.replace(OUT)
    print(json.dumps({k: rep.get(k) for k in ("status", "measured_this_pass",
                                               "candidates_this_pass", "stopped_because")}))
    return 0 if str(rep.get("status")) == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
