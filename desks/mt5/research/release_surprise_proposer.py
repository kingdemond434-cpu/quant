"""Mint `release_surprise` cells from four scheduled public releases (ideas N4, N6, N7, N8).

The consumer of `research/release_surprise_ingest.py`. One leg, two steps, every hour:

  1. INGEST WHAT IS DUE. Each source is fetched only when its release window opened since its
     last good fetch (or a day passed), through the robots gate, and merged into
     `data/axes/release_surprise.json` as first prints; nothing on disk is ever overwritten.
  2. SWEEP. For each basis of `mt5desk.family_release_surprise`, on the instruments its mechanism
     names, run the declared grid, screen every variant net of the round trip with the shared
     proposer screen, deflate by EVERYTHING tried this pass across all bases, and donate one best
     variant per (symbol, basis[, crop]) cell through `proposer_common.donate`. The sealed
     gauntlet judges it via `ORTHOGONAL_FAMILIES`; the family reloads its rows from the axis.

  basis               instruments                   declared hypothesis (+ the fade, tested apart)
  eia_gas_storage     XNGUSD                        bigger-than-normal build -> gas lower
  usda_export_sales   CORN, WHEAT, SOYBEAN (own)    sales above run-rate -> the grain higher
  tic_flow            USDJPY, EURUSD, US500         foreign inflow -> USD and US equity higher
  boj_rinban_size     USDJPY, EURJPY, JPN225        buys above plan -> yen weaker, Nikkei higher
  boj_rinban_cover    USDJPY, EURJPY, JPN225        dealers dumping JGBs -> sign is the test

A BASIS WITH NO ADMITTED ROWS PARKS, BY NAME AND BY COUNT (`release_surprise_absent`, with the
ingest state of its source), and a pass where every basis parks is UNMEASURED as a whole -- never
zero. TIC parks until twelve-plus FIRST PRINTS exist, because its history is revised.

The screen is not the gauntlet: it only keeps the gauntlet from being handed every variant.

    python desks/mt5/research/release_surprise_proposer.py --once --budget-s 600 [--no-ingest]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_release_surprise as F  # noqa: E402

from research import proposer_common as pc  # noqa: E402

SOURCE = "release_surprise"
FAMILY = "release_surprise"
REPORT = DESK / "reports" / "RELEASE_SURPRISE_PROPOSER.json"
UNMEASURED = "UNMEASURED"
DEFAULT_BUDGET_S = 600.0
MIN_BARS = 2000

#: basis -> instruments its mechanism names (crop basis trades the crop's own CFD).
TARGETS: dict[str, tuple[str, ...]] = {
    "eia_gas_storage": ("XNGUSD",),
    "usda_export_sales": F.CROPS,
    "tic_flow": ("USDJPY", "EURUSD", "US500"),
    "boj_rinban_size": ("USDJPY", "EURJPY", "JPN225"),
    "boj_rinban_cover": ("USDJPY", "EURJPY", "JPN225"),
}
#: (move, direction) per (basis, symbol): the declared side first, then its fade.
_UP_LONG = (("up", "long"), ("down", "short"), ("up", "short"), ("down", "long"))
_UP_SHORT = (("up", "short"), ("down", "long"), ("up", "long"), ("down", "short"))
PAIRS: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {
    ("eia_gas_storage", "XNGUSD"): _UP_SHORT,
    **{("usda_export_sales", c): _UP_LONG for c in F.CROPS},
    ("tic_flow", "USDJPY"): _UP_LONG, ("tic_flow", "EURUSD"): _UP_SHORT,
    ("tic_flow", "US500"): _UP_LONG,
    **{("boj_rinban_size", s): _UP_LONG for s in ("USDJPY", "EURJPY", "JPN225")},
    **{("boj_rinban_cover", s): _UP_LONG for s in ("USDJPY", "EURJPY", "JPN225")},
}
WINDOW: dict[str, int] = {"eia_gas_storage": 52, "usda_export_sales": 52, "tic_flow": 24,
                          "boj_rinban_size": 60, "boj_rinban_cover": 60}
MIN_ABS: tuple[float, ...] = (1.0, 1.5)
HOLDS: tuple[int, ...] = (6, 24, 72)


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def reach(meta: dict[str, Any], ingest: dict[str, Any] | None = None
          ) -> dict[str, dict[str, Any]]:
    """Per basis: the instruments it would sweep and its event count, or why it parks."""
    from research import universe_policy as up
    out: dict[str, dict[str, Any]] = {}
    src_state = (ingest or {}).get("sources", {})
    for basis, syms in TARGETS.items():
        lane = [s for s in syms if isinstance(meta.get(s), dict) and up.may_hypothesise(s)]
        try:
            n = {}
            for s in lane:
                crop = s if basis == "usda_export_sales" else ""
                n[s] = len(F.reading(basis, crop=crop, window=WINDOW[basis]))
            ready = sorted(s for s, k in n.items() if k)
            out[basis] = ({"symbols": ready, "readings": n} if ready else
                          {"parked_reason": F.ABSENT, "why": "no scored reading yet",
                           "symbols_parked": len(lane)})
        except F.ReleaseSurpriseUnavailable as exc:
            out[basis] = {"parked_reason": F.ABSENT, "why": str(exc)[:300],
                          "symbols_parked": len(lane),
                          "ingest_state": src_state.get(F.SOURCE_OF[basis], {}).get("state")}
        if not lane:
            out[basis] = {"parked_reason": "not_in_hypothesis_lane",
                          "why": f"none of {', '.join(syms)} is a hypothesis-lane instrument "
                                 "in this host's registry", "symbols_parked": len(syms)}
    return out


def run(*, budget_s: float = DEFAULT_BUDGET_S, now: datetime | None = None,
        donate: bool = True, ingest: bool = True) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    ing: dict[str, Any] | None = None
    if ingest:
        from research import release_surprise_ingest as RI
        try:
            ing = RI.run(apply=True, now=now)
        except Exception as exc:
            ing = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    meta = pc.universe_meta()
    bases = reach(meta, ing)
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "organ": "desks/mt5/research/release_surprise_proposer.py",
                           "family": FAMILY, "ideas": ["N4", "N6", "N7", "N8"],
                           "consumes": ["data/axes/release_surprise.json",
                                        "data/universe/*_H1.parquet"],
                           "ingest": {k: v for k, v in (ing or {}).items()
                                      if k in ("sources", "rows_by_source_and_vintage",
                                               "n_rows", "error")},
                           "bases": bases}
    work = sorted({(s, b) for b, v in bases.items() for s in v.get("symbols", ())})
    if not work:
        rep.update({"status": UNMEASURED, "tests_run": UNMEASURED, "cells_proposed": UNMEASURED,
                    "why": "every basis is parked: see bases[*].parked_reason"})
        _write(REPORT, rep)
        return rep
    syms = sorted({s for s, _ in work})
    start = int(_read(REPORT).get("cursor_next", 0)) % len(syms)
    order = syms[start:] + syms[:start]
    rows: list[dict[str, Any]] = []
    swept: list[str] = []
    skipped: dict[str, str] = {}
    for sym in order:
        if time.monotonic() - t0 > budget_s:
            break
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            skipped[sym] = "no or too few H1 bars"
            swept.append(sym)
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms"
            swept.append(sym)
            continue
        unf = pc.artifact_hours(d)
        for basis in (b for s, b in work if s == sym):
            for move, direction in PAIRS[(basis, sym)]:
                for min_abs in MIN_ABS:
                    for hold in HOLDS:
                        params: dict[str, Any] = {"basis": basis, "move": move,
                                                  "min_abs": min_abs, "direction": direction,
                                                  "window": WINDOW[basis], "hold_bars": hold}
                        if basis == "usda_export_sales":
                            params["crop"] = sym
                        try:
                            sig = F.family_release_surprise(d, **params)
                        except F.ReleaseSurpriseUnavailable as exc:
                            skipped[f"{sym}.{basis}"] = str(exc)[:160]
                            continue
                        sc = pc.screen(d, sig, cost, unf)
                        if sc is None:
                            continue
                        rows.append({"cell": f"{sym}.{FAMILY}.{basis}", "symbol": sym,
                                     "params": params, **sc})
        swept.append(sym)
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"{r['params']['basis'].replace('_', ' ')} release surprised its own "
                   f"baseline {r['params']['move']} by at least {r['params']['min_abs']} sd: "
                   f"{r['symbol']} reprices {r['params']['direction']} over the "
                   f"{r['params']['hold_bars']} bars after the release instant"),
        title=f"{r['cell']} {r['params']['move']} {r['params']['direction']} "
              f"z{r['params']['min_abs']} h{r['params']['hold_bars']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep")}) for r in proposals]
    donated = None
    if donate and cands:
        donated = pc.donate(SOURCE, cands, len(rows))
    rep.update({"status": "OK", "symbols_available": len(syms), "symbols_swept": len(swept),
                "cursor_start": start, "cursor_next": (start + len(swept)) % len(syms),
                "tests_run": len(rows), "cells_proposed": len(proposals),
                "donated": len(cands) if donated else 0, "donation_path": str(donated or ""),
                "donation_refusals": dict(pc.LAST_DONATION) if donated is None and cands
                else None,
                "skipped": skipped, "elapsed_s": round(time.monotonic() - t0, 1),
                "proposals": proposals[:50]})
    _write(REPORT, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--no-ingest", action="store_true")
    a = ap.parse_args(argv)
    r = run(budget_s=a.budget_s, ingest=not a.no_ingest)
    parked = sorted(b for b, v in r.get("bases", {}).items() if "parked_reason" in v)
    print(f"release_surprise_proposer: status={r['status']} swept={r.get('symbols_swept', 0)} "
          f"tests={r['tests_run']} proposed={r['cells_proposed']} "
          f"donated={r.get('donated', 0)} parked={','.join(parked) or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
