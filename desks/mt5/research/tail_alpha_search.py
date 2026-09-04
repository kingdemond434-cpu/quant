"""Tail-diversity search: what makes money specifically when the current book is hurting?

    fitness_tail(i) = E[ R_i | R_book < q_10 ]        conditional on the BOOK's worst decile

alpha-foundry's tail-diversity experiments, made a proposer. The book's daily P&L (the shadow
ledgers, summed) defines the bad days; every registered family x instrument x recipe on a short
grid is screened as usual and then RANKED by its conditional expectancy on those days, with the
usual deflation across everything tried. A strategy that is merely average on bad days but
positive overall is proposed by the other sweeps; this one proposes only cells whose bad-day
expectancy is positive with a t above the bar -- the diversifier that raises the optimal
total heat far more than another normal-state strategy would.

TailNovelty(i) = 1 - max_j rho(PnL_i, PnL_j | stress) is reported beside it: a cell that is
independent of the book precisely in stress, not on a Tuesday.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import proposer_common as pc  # noqa: E402

SOURCE = "tail_alpha"
REPORT = _DESK / "reports" / "tail_alpha_search.json"
TAIL_Q = 0.10
TAIL_T = 2.0
#: A deliberately short recipe grid over families with a price-only signature; the point is the
#: conditioning, not the grid.
GRID: tuple[tuple[str, dict], ...] = (
    ("multi_speed_trend", {"crisis_only": True}),
    ("multi_speed_trend", {}),
    ("formula", {"expr": ["neg", ["delta", "close", 24]], "side_mode": "follow",
                 "entry_z": 1.5, "hold_bars": 8}),
    ("formula", {"expr": ["zscore", "range", 48], "side_mode": "fade", "entry_z": 1.5,
                 "hold_bars": 6}),
    ("spread_state", {"mode": "spike_reversion"}),
    ("style_premia", {"style": "volatility", "entry": 1.0, "hold_bars": 24}),
)


def _book_bad_days() -> tuple[set, pd.Series] | tuple[None, None]:
    try:
        from research.state_admission_run import load_trades
        rows = [(pd.Timestamp(t.when), float(t.r)) for t in load_trades("shadow")]
    except Exception:                                            # noqa: BLE001
        return None, None
    if not rows:
        return None, None
    s = pd.Series({(w.tz_convert("UTC") if w.tzinfo else w.tz_localize("UTC")).normalize(): r
                   for w, r in rows}).groupby(level=0).sum()
    if len(s) < 40:
        return None, None
    thr = float(s.quantile(TAIL_Q))
    return set(s[s <= thr].index), s


def _trade_days(d: pd.DataFrame, signals) -> dict[pd.Timestamp, float]:
    idx = d.index
    o = d["open"].to_numpy(dtype=float)
    c = d["close"].to_numpy(dtype=float)
    pos = {ts: i for i, ts in enumerate(idx)}
    out: dict[pd.Timestamp, float] = {}
    last = -1
    for s in sorted(signals, key=lambda x: x.time):
        i = pos.get(s.time)
        if i is None or i + 1 >= len(o) or i + 1 <= last:
            continue
        e = i + 1
        x = min(e + max(1, int(s.ttl_bars)), len(c) - 1)
        if o[e] <= 0:
            continue
        r = math.log(c[x] / o[e]) * int(s.side)
        if math.isfinite(r):
            day = idx[e].normalize()
            out[day] = out.get(day, 0.0) + r
            last = x
    return out


def run(symbols: list[str] | None = None, budget_s: float = 900.0) -> dict:
    from mt5desk import families_orthogonal as fo
    bad, book = _book_bad_days()
    if bad is None:
        rep = {"generated_at": datetime.now(tz=UTC).isoformat(), "tests_run": 0,
               "cells_proposed": 0, "why": "no shadow ledger to define the book's bad days"}
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(rep, indent=1), "utf-8")
        return rep
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    try:
        from research.state_vector_build import book_symbols
        todo = [s for s in (symbols or book_symbols()) if s in have]
    except Exception:                                            # noqa: BLE001
        todo = [s for s in (symbols or []) if s in have]
    rows: list[dict] = []
    started = time.monotonic()
    for sym in sorted(set(todo)):
        if time.monotonic() - started > budget_s:
            break
        d = pc.bars(sym)
        if d is None or len(d) < 3000:
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            continue
        unf = pc.artifact_hours(d)
        for fam, params in GRID:
            fn = fo.ORTHOGONAL_FAMILIES.get(fam)
            if fn is None:
                continue
            try:
                sig = fn(d, **params)
            except TypeError:
                continue
            sc = pc.screen(d, sig, cost, unf)
            if sc is None:
                continue
            days = _trade_days(d, sig)
            on_bad = np.array([r - cost for day, r in days.items() if day in bad])
            t_tail = (float(on_bad.mean() / (on_bad.std(ddof=1) / math.sqrt(on_bad.size)))
                      if on_bad.size >= 8 and on_bad.std(ddof=1) > 0 else 0.0)
            j = pd.Series(days).reindex(book.index).fillna(0.0)
            stress = j[[i in bad for i in j.index]]
            bs = book[[i in bad for i in book.index]]
            rho = float(np.corrcoef(stress, bs)[0, 1]) if stress.std() > 0 and bs.std() > 0 else 0.0
            rows.append({"cell": f"{sym}.{fam}.tail", "symbol": sym, "family": fam,
                         "params": params, **sc, "n_bad_days": int(on_bad.size),
                         "tail_mean_r": round(float(on_bad.mean()), 6) if on_bad.size else None,
                         "t_tail": round(t_tail, 2), "tail_novelty": round(1.0 - abs(rho), 3)})
    rows = pc.deflate(rows)
    for r in rows:
        r["proposed"] = bool(r.get("proposed") and r["t_tail"] >= TAIL_T)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], r["family"], dict(r["params"]),
        mechanism=(f"pays on the book's worst-decile days: tail mean {r['tail_mean_r']:+.5f} "
                   f"(t={r['t_tail']}, n={r['n_bad_days']}), tail novelty {r['tail_novelty']}"),
        title=f"{r['cell']} tail t={r['t_tail']}",
        evidence={k: r.get(k) for k in ("n_independent", "net_per_trade", "t_gross",
                                        "t_deflated_sweep", "n_tests_sweep", "t_tail",
                                        "tail_mean_r", "tail_novelty", "n_bad_days")})
        for r in proposals]
    rep = {"generated_at": datetime.now(tz=UTC).isoformat(), "bad_days": len(bad),
           "symbols_swept": len(todo), "tests_run": len(rows), "cells_proposed": len(proposals),
           "proposals": proposals,
           "top_tail": sorted(rows, key=lambda r: -r["t_tail"])[:10]}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    if cands:
        rep["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=900.0)
    a = ap.parse_args()
    r = run(symbols=a.symbol, budget_s=a.budget_s)
    print(f"TAIL ALPHA  bad_days={r.get('bad_days')} {r['tests_run']} tests, "
          f"{r['cells_proposed']} proposed")
    for x in r.get("top_tail", [])[:8]:
        print(f"  {x['cell']:36s} t_tail={x['t_tail']:+.2f} tail_mean={x['tail_mean_r']} "
              f"nov={x['tail_novelty']} t={x['t_gross']:+.2f}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
