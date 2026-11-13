#!/usr/bin/env python3
"""HUNT16 SEEDER: the DaviddTech corpus families reach the judge again, aimed at the book's gaps.

    python desks/mt5/research/hunt16_seeder.py --once --budget-s 600
    python desks/mt5/research/hunt16_seeder.py --once --dry-run      # measure, donate nothing

WHY (hourly pass + Judge, 2026-11-13). Eight families had 0 cells mined in seven days:
`hunt16_cell` and the seven `dav_*` mechanisms it carries. The cause is structural, not a dead
clock: `families_orthogonal.hunt16_cell` is judgeable by the sealed gauntlet only with
`base_family` (and optionally direction, signal hour and the prior-NY-session day label) as
params, `orthogonal_sweep` calls every family blind -- so hunt16_cell returns [] there -- and
`run_hunt16` is a one-shot behind a DONE marker. Nothing enumerated the base families, so
nothing could ever mint one.

WHAT IT DOES. For each symbol in book-gap order -- gold first, then indices, then FX crosses with
a USD, JPY or EUR leg and no NOK or CHF leg (the book is NOK/CHF-heavy and holds no gold or
index) -- it enumerates `hunt16_cell` over every hunt16 base family x direction x the hunt's
signal hours (asia 07, london_am 13, ny_open 14, afternoon 17, or any hour) x day label (TREND,
NORMAL, or any). Exotics are not seeded at all, which keeps this organ inside the 90/10 rule.

Every cell takes the specialist path unchanged: `gauntlet_buildability.cell_verdict`, then the
SEALED `external_gauntlet.build_cell` (via `specialist_cell.measure`), then the 66 lower-bound
trade-day seed floor, then `proposer_common.donate` into `data/intelligence/hunt16_seeder/`,
which the compiler turns into docket rows. Every measured cell is charged to the trial census.
A cell is measured at most once a week (the bars move slowly; the state file carries the day),
so a pass that runs out of budget resumes next hour. Additive: no other miner is touched.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "hunt16_seeder"
FAMILY = "hunt16_cell"
OUT = BASE / "reports" / "HUNT16_SEEDER.json"
STATE = BASE / "data" / "hunt16_seeder_state.json"
SEED_FLOOR = 66
REMEASURE_DAYS = 7
#: run_hunt16.WINDOWS signal hours (asia's is its range start), plus None = every hour.
SIGNAL_HOURS: tuple[int | None, ...] = (None, 7, 13, 14, 17)
DAY_STATES: tuple[str | None, ...] = (None, "TREND_DAY", "NORMAL_DAY")
DIRECTIONS = ("LONG", "SHORT")
CROSS_LEGS = frozenset({"USD", "JPY", "EUR"})
CROWDED_LEGS = frozenset({"NOK", "CHF"})


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def gap_symbols() -> list[tuple[str, str]]:
    """[(bucket, symbol)] in book-gap order: gold, index, USD/JPY/EUR non-exotic cross."""
    from research import universe_policy as up
    gold, index, cross = [], [], []
    for sym in sorted(up._registry()):
        if not up.may_hypothesise(sym, FAMILY):
            continue
        cls = str(up.asset_class_of(sym) or "").lower()
        if sym.startswith("XAU"):
            gold.append(("gold", sym))
        elif "ind" in cls and sym != "USDX":
            index.append(("index", sym))
        elif "forex" in cls and "exotic" not in cls and len(sym) == 6:
            legs = {sym[:3], sym[3:]}
            if legs & CROSS_LEGS and not legs & CROWDED_LEGS:
                cross.append(("usd_jpy_eur_cross", sym))
    return gold + index + cross


def base_families() -> list[str]:
    from research.run_hunt16 import FAMILIES
    return sorted(FAMILIES)


def plan(symbols: list[tuple[str, str]] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for bucket, sym in (symbols if symbols is not None else gap_symbols()):
        for base in base_families():
            for d in DIRECTIONS:
                for hour in SIGNAL_HOURS:
                    for ds in DAY_STATES:
                        params: dict[str, Any] = {"base_family": base, "direction": d}
                        if hour is not None:
                            params["signal_at"] = hour
                        if ds is not None:
                            params["day_state"] = ds
                        out.append({"bucket": bucket, "symbol": sym, "family": FAMILY,
                                    "base_family": base, "params": params})
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


def _stale(day: str | None, today: date) -> bool:
    try:
        return (today - date.fromisoformat(str(day))).days >= REMEASURE_DAYS
    except ValueError:
        return True


def seed(*, budget_s: float = 600.0, dry_run: bool = False,
         symbols: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    from research import specialist_cell as sc
    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    started = time.monotonic()
    today = datetime.now(tz=UTC).date()
    cells = plan(symbols)
    meta = sc._meta()
    state = _load_state()
    cs: dict[str, Any] = state["cells"]
    by_bucket: dict[str, Counter] = {}
    by_base: Counter = Counter()
    gaps: Counter = Counter()
    measured_now: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    stopped = "grid exhausted"
    for c in cells:
        row = by_bucket.setdefault(c["bucket"], Counter())
        row["grid"] += 1
        verdict, why = cell_verdict(c["family"], c["params"])
        if verdict != BUILDABLE:
            row["set_aside_unbuildable"] += 1
            gaps[f"{verdict}: {why[:100]}"] += 1
            continue
        ident = sc.identity(c["symbol"], c["family"], c["params"])
        prior = cs.get(ident) or {}
        if _stale(prior.get("day"), today):
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached; resumes next pass"
                row["not_reached_this_pass"] += 1
                continue
            got = sc.measure(c["symbol"], c["family"], c["params"], meta)
            prior = {**prior, **got, "day": today.isoformat(),
                     **{k: c[k] for k in ("bucket", "symbol", "family", "base_family", "params")}}
            cs[ident] = prior
            measured_now.append(c)
            row["measured_this_pass"] += 1
        if not prior.get("built"):
            row["input_gap"] += 1
            gaps[str(prior.get("why"))[:120]] += 1
            continue
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
            f"hunt16 {c['base_family']} (DaviddTech corpus, canonical params), "
            f"{c['params']['direction']} on {c['symbol']}",
            f"{c['symbol']} {c['base_family']} {c['params']['direction']} via hunt16_cell",
            {"firing": c["firing"], "seed_floor": SEED_FLOOR, "book_gap_bucket": c["bucket"],
             "built_by": "external_gauntlet.build_cell (sealed), measured on its own output"})
            for c in cands]
        for r, c in zip(rows, cands, strict=True):
            r["breadth_unit"] = f"hunt16/{c['base_family']}"
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
                by_bucket[c["bucket"]]["donated_this_pass"] += 1
                by_base[c["base_family"]] += 1
    if not dry_run:
        _save_state(state)
    donated_total = Counter(str(v.get("bucket")) for v in cs.values() if v.get("donated_at"))
    return {
        "status": "OK", "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2), "seed_floor_trade_days": SEED_FLOOR,
        "grid": len(cells), "measured_this_pass": len(measured_now),
        "candidates_this_pass": len(cands), "donation": donation,
        "by_bucket": {k: dict(v) for k, v in by_bucket.items()},
        "donated_this_pass_by_base_family": dict(by_base),
        "donated_total_by_bucket": dict(donated_total),
        "trial_charge_this_pass": sc.charge([{**c, "mechanism": c["base_family"],
                                              "klass": c["bucket"]} for c in measured_now]),
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
