"""Sweep AQR's six styles and their public combinations across the book, propose survivors.

Every (instrument, style-or-combo, entry, hold) cell is a trial; the whole grid is charged. Carry
reads Fusion's own swap table through the DataHub; defensive reads the risk driver. The expected
honest result is a small number of survivors on a small number of instruments -- the styles are
harvested at institutional cost -- and that small number is the diversifier the breakout book
lacks. Proposals leave as EXACT_RECIPE under family `style_premia`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.family_style_premia import COMBOS, STYLES, family_style_premia  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SOURCE = "style_premia"
REPORT = _DESK / "reports" / "style_premia_sweep.json"
ENTRIES = (1.0, 1.5)
HOLDS = (24, 72)


def _book_symbols() -> list[str]:
    try:
        from research.state_vector_build import book_symbols
        return book_symbols()
    except Exception:                                            # noqa: BLE001
        return []


def _swap(sym: str) -> float | None:
    try:
        from libs.data.datahub import desk_hub
        return float(desk_hub().get("terms.swap_diff", symbol=sym)["payload"].value)
    except Exception:                                            # noqa: BLE001
        return None


def _risk_bars():
    try:
        from mt5desk.economic_drivers import ROLES
        for cand in ROLES.get("RISK", ()):
            b = pc.bars(str(cand))
            if b is not None:
                return b
    except Exception:                                            # noqa: BLE001
        pass
    return None


def run(symbols: list[str] | None = None, budget_s: float = 1200.0) -> dict:
    meta = pc.universe_meta()
    have = {p.stem.rpartition("_")[0] or p.stem for p in pc.UNI.glob("*.parquet")}
    todo = [s for s in (symbols or _book_symbols()) if s in have]
    risk = _risk_bars()
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    started = time.monotonic()
    for sym in sorted(set(todo)):
        if time.monotonic() - started > budget_s:
            skipped[sym] = "sweep budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < 3000:
            skipped[sym] = "under 3000 H1 bars"
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms to price the round trip"
            continue
        unf = pc.artifact_hours(d)
        swap = _swap(sym)
        for name in STYLES + COMBOS:
            style, combo = (name, None) if name in STYLES else ("carry" if name.startswith("carry")
                                                                else "trend", name)
            for entry in ENTRIES:
                for hold in HOLDS:
                    params = {"style": style, "combo": combo, "entry": entry, "hold_bars": hold}
                    sig = family_style_premia(d, swap_diff=swap, risk=risk, **params)
                    sc = pc.screen(d, sig, cost, unf)
                    if sc is None:
                        continue
                    rows.append({"cell": f"{sym}.style_premia.{name}", "symbol": sym,
                                 "params": params, **sc})
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "style_premia", dict(r["params"]),
        mechanism=(f"AQR style {r['params']['combo'] or r['params']['style']} on "
                   f"{r['symbol']}: an economic premium harvested at the instrument's own "
                   "scale; carry from Fusion's rollover, defensive from beta to the risk driver"),
        title=f"{r['cell']} entry>={r['params']['entry']} hold={r['params']['hold_bars']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep")}) for r in proposals]
    rep = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(todo),
           "tests_run": len(rows), "cells_proposed": len(proposals), "skipped": skipped,
           "proposals": proposals,
           "by_style": {n: sum(1 for r in rows if r["cell"].endswith("." + n))
                        for n in STYLES + COMBOS}}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    if cands:
        rep["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=1200.0)
    a = ap.parse_args()
    r = run(symbols=a.symbol, budget_s=a.budget_s)
    print(f"STYLE PREMIA  {r['symbols_swept']} symbols, {r['tests_run']} tests, "
          f"{r['cells_proposed']} proposed  by_style={r['by_style']}")
    for p in r["proposals"][:10]:
        print(f"  {p['cell']:40s} t={p['t_gross']:+.2f} t_defl={p['t_deflated_sweep']:+.2f} "
              f"n={p['n_independent']}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
