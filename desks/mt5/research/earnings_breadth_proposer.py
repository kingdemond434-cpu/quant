"""Mint `earnings_breadth` cells on the US index CFDs from 8-K 2.02 reaction breadth (its consumer).

The family (`mt5desk.family_earnings_breadth`) reads the desk's cached SEC 8-K item 2.02 filings
(`data/edgar_cache/*.json`) and the share CFDs' own bars, and trades ONLY an index CFD. This
proposer sweeps the index symbols the registry carries AND classes as indices on the hypothesis
lane (`INDEX_SYMBOLS` = US500, NAS100, US30, US2000; a share CFD never becomes a cell -- the two
lanes), over one small declared grid:

    stat     share_up | median
    (move, direction)  (up, long) | (down, short)   -- the index drifts WITH the breadth
    hold     24 | 72 bars
    fixed    min_abs 1.5, min_reporters 10, window 20

= 8 variants per index symbol, every one charged: each variant that reaches the shared screen is
deflated by EVERYTHING this pass tried (`proposer_common.deflate`), and one best variant per
index cell is donated through `proposer_common.donate`. The sealed gauntlet judges it via
`ORTHOGONAL_FAMILIES`; the family reloads its input from the cache itself.

AN ABSENT INPUT PARKS, BY NAME: no cache, no 8-K 2.02 filing with a ticker, or no reporter on a
share CFD with bars gives `status: UNMEASURED` with `parked_reason: earnings_breadth_absent` and
the index symbols it would have swept -- never zero.

The screen is not the gauntlet: it only keeps the gauntlet from being handed every variant.

    python desks/mt5/research/earnings_breadth_proposer.py --once --budget-s 600
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

from mt5desk import family_earnings_breadth as F  # noqa: E402

from research import proposer_common as pc  # noqa: E402

SOURCE = "earnings_breadth"
FAMILY = "earnings_breadth"
REPORT = DESK / "reports" / "EARNINGS_BREADTH_PROPOSER.json"
UNMEASURED = "UNMEASURED"
DEFAULT_BUDGET_S = 600.0
MIN_BARS = 2000

STATS: tuple[str, ...] = ("share_up", "median")
#: The declared hypothesis: the index drifts the way the breadth points. Not every sign.
PAIRS: tuple[tuple[str, str], ...] = (("up", "long"), ("down", "short"))
HOLDS: tuple[int, ...] = (24, 72)
FIXED: dict[str, Any] = {"min_abs": 1.5, "min_reporters": 10, "window": 20}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def index_symbols(meta: dict[str, Any]) -> list[str]:
    """The declared index CFDs the registry holds, on the hypothesis lane, never a share CFD."""
    from research import universe_policy as up
    return [s for s in F.INDEX_SYMBOLS
            if isinstance(meta.get(s), dict) and up.may_hypothesise(s)
            and not up.is_equity(s)]


def reach(meta: dict[str, Any]) -> dict[str, Any]:
    """The input's measured reach: filings, mapped share CFDs with bars, index symbols."""
    syms = index_symbols(meta)
    out: dict[str, Any] = {"index_symbols": syms}
    try:
        rows = F.cached_filings()
    except F.EarningsBreadthUnavailable as exc:
        return {**out, "parked_reason": F.ABSENT, "why": str(exc)[:300],
                "symbols_parked": len(syms)}
    tmap = F.ticker_cfd()
    shares = sorted({next(tmap[t] for t in r["tickers"] if t in tmap) for r in rows
                     if any(t in tmap for t in r["tickers"])})
    with_bars = [s for s in shares if F._is_share(s) and pc.bars(s) is not None]
    out.update({"filings_8k_202": len(rows), "share_cfds_mapped": len(shares),
                "share_cfds_with_bars": len(with_bars)})
    if not with_bars:
        out.update({"parked_reason": F.ABSENT, "symbols_parked": len(syms),
                    "why": "no 8-K 2.02 filer maps to a share CFD with H1 bars on this host"})
    return out


def run(*, budget_s: float = DEFAULT_BUDGET_S, now: datetime | None = None,
        donate: bool = True) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    meta = pc.universe_meta()
    got = reach(meta)
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "organ": "desks/mt5/research/earnings_breadth_proposer.py",
                           "family": FAMILY,
                           "consumes": ["data/edgar_cache/*.json", "data/universe/*_H1.parquet"],
                           "reach": got,
                           "grid": {"stat": list(STATS), "pairs": [list(p) for p in PAIRS],
                                    "hold_bars": list(HOLDS), **FIXED}}
    syms = got.get("index_symbols") or []
    if "parked_reason" in got or not syms:
        rep.update({"status": UNMEASURED, "tests_run": UNMEASURED, "cells_proposed": UNMEASURED,
                    "parked_reason": got.get("parked_reason") or F.ABSENT,
                    "why": got.get("why") or "no index CFD on the hypothesis lane"})
        _write(REPORT, rep)
        return rep
    rows: list[dict[str, Any]] = []
    swept: list[str] = []
    skipped: dict[str, str] = {}
    for sym in syms:
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
        for stat in STATS:
            for move, direction in PAIRS:
                for hold in HOLDS:
                    params: dict[str, Any] = {"stat": stat, "move": move, "direction": direction,
                                              "hold_bars": hold, **FIXED}
                    try:
                        sig = F.family_earnings_breadth(d, **params)
                    except F.EarningsBreadthUnavailable as exc:
                        skipped[sym] = str(exc)[:160]
                        continue
                    sc = pc.screen(d, sig, cost, unf)
                    if sc is None:
                        continue
                    rows.append({"cell": f"{sym}.{FAMILY}", "symbol": sym, "params": params,
                                 **sc})
        swept.append(sym)
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"earnings reaction breadth ({r['params']['stat']}) moved "
                   f"{r['params']['move']} by at least {r['params']['min_abs']} sd across "
                   f">= {r['params']['min_reporters']} reporters: index holders absorb the "
                   f"aggregate earnings news over the {r['params']['hold_bars']} bars after, "
                   f"{r['symbol']} {r['params']['direction']}"),
        title=f"{r['cell']} {r['params']['stat']} {r['params']['move']} "
              f"{r['params']['direction']} h{r['params']['hold_bars']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep")}) for r in proposals]
    donated = None
    if donate and cands:
        donated = pc.donate(SOURCE, cands, len(rows))
    rep.update({"status": "OK", "symbols_available": len(syms), "symbols_swept": len(swept),
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
    a = ap.parse_args(argv)
    r = run(budget_s=a.budget_s)
    print(f"earnings_breadth_proposer: status={r['status']} swept={r.get('symbols_swept', 0)} "
          f"tests={r['tests_run']} proposed={r['cells_proposed']} "
          f"donated={r.get('donated', 0)} parked={r.get('parked_reason') or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
