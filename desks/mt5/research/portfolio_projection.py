"""Portfolio projection for all current survivors (gold book + hunt12 cells).

Recomputes per-trade cost-adjusted R for every survivor cell, builds aligned
daily-R series, then reports:
  - per-sleeve stats + rank
  - cross-sleeve correlation / effective independent count
  - portfolio net Sharpe (daily R, annualized) and 8y CAGR at two risk
    budgets (q_total = 5.5% and 5.5%*sqrt(N_eff), per-day R units)

All R figures are net of the validation cost model (spread+commission).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"

GOLD_WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
H12_WINDOWS = GOLD_WINDOWS  # identical structure in run_hunt12


def cell_trades(sym: str, win: str, state: str | None, h1: pd.DataFrame,
                costs: Costs, states: dict | None) -> list:
    sigs = families.family_session_range_breakout(h1, **H12_WINDOWS[win])
    if states is not None:
        sdays = [pd.Timestamp(s.time).date() for s in sigs]
        sigs = [s for s, d in zip(sigs, sdays) if states.get(d) == state]
    r = run_backtest(h1, sigs, costs)
    return r.trades


def load_h12_survivors() -> list[dict]:
    """The hunt12 survivor cells. RAISES when the report is absent — it must never return [].

    **THE EMPTY LIST SILENTLY TRUNCATED THE BOOK.** Five of the nine deployed sleeves are hunt12
    cells; the other four are gold. `reports/` is gitignored (.gitignore:118), so this file is
    absent on every fresh clone AND on the VPS — measured 2026-08-20, `swap_exposure.py` refuses
    all five AUDCAD cells on both. Where it was absent, this returned [], `build_sleeves` built a
    GOLD-ONLY four-sleeve book, and `main` wrote it over the nine-sleeve artifact, recomputing
    mean_corr, n_eff and port_sharpe consistently on the truncation. No error anywhere, and
    nothing downstream able to tell it from the real answer.

    That is the WS-005 shape aimed at the artifact the whole book ranking rests on. An absent
    input must produce a refusal, not a smaller book (L1.28a).

    **RUN `research/run_hunt12.py` FIRST.** It writes this file — and it was itself dead with a
    missing import until 2026-08-19 (commit 82db21fc), which is why the report was never
    regenerated and the committed projection went stale.
    """
    p = BASE / "reports" / "hunt12_partial.json"
    if not p.exists():
        raise SystemExit(
            f"REFUSING to project: {p} is absent, so the hunt12 survivor cells cannot be loaded.\n"
            "Five of the nine deployed sleeves live in that file. Returning an empty list here "
            "would build a GOLD-ONLY book and overwrite the nine-sleeve artifact with it, and "
            "nothing downstream could tell the difference.\n"
            "reports/ is gitignored, so this file never travels with the repo. Regenerate it: "
            "python research/run_hunt12.py")
    saved = json.loads(p.read_text(encoding="utf-8"))
    return [c for c in saved.get("all", []) if c.get("gate")]


def build_sleeves() -> list[dict]:
    """Sleeve records (name, sym, win, state, r, dates) for gold book
    (armed windows) + current hunt12 survivors. Shared loader."""
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    sleeves = []
    h1g = families._h1(pd.read_parquet(UNI / "XAUUSD_H1.parquet"))
    # GAP 114: this read `Costs(spread_per_lot=0.48, ...)` until 2026-08-20. 0.48 is dollars per
    # OUNCE in a field that wants dollars per LOT, so the engine divided by contract_size 100 and
    # charged gold 0.0048/oz against a measured 0.16/oz median -- 3% of its real spread, on every
    # gold row in the artifact the whole book ranking rests on.
    #
    # `Costs.from_symbol` was written to end exactly this and this call site never adopted it
    # (row 110's defect class). `research/calibrate_engine.py` confirms both halves with a
    # known-answer probe: the old constant recovers 0.2099x of the planted cost and FAILS,
    # from_symbol recovers 0.9166x and passes. mult=2.0 is the honest baseline, not a stress --
    # a round trip crosses the spread on the way in and again on the way out.
    #
    # MEASURED EFFECT on the gold half: annualised Sharpe 2.92 -> 2.32, 2.05 -> 1.43,
    # 1.78 -> 1.19, and gold_ny_open flips +0.0157R -> -0.0475R. Gold-only portfolio Sharpe
    # 2.49 -> 1.52. One of the four gold sleeves is a loser at its true spread.
    gold_costs = Costs.from_symbol(meta["XAUUSD"], mult=2.0)
    for wname, wp in GOLD_WINDOWS.items():
        tr = cell_trades("XAUUSD", wname, None, h1g, gold_costs, None)
        sleeves.append(dict(name=f"gold_{wname}", sym="XAUUSD", win=wname,
                            state="base",
                            r=[t.r_multiple for t in tr],
                            dates=[t.entry_time.date() for t in tr]))
    from research.run_hunt12 import day_states  # noqa: PLC0415
    unpriceable: list[str] = []
    for cell in load_h12_survivors():
        sym, win, state = cell["sym"], cell["win"], cell["state"]
        # A SURVIVOR CAN NAME AN INSTRUMENT THE VENUE NO LONGER LISTS, AND THAT IS NOT A CRASH.
        #
        # AUDCAD was dropped from the venue snapshot at the 2026-08-20 refresh while hunt12's five
        # AUDCAD survivors stayed in `hunt12_partial.json`. `meta[sym]` then raised KeyError
        # halfway through the loop, so the projection died with a traceback instead of publishing
        # a book -- and a run that dies is indistinguishable from a run nobody started.
        #
        # Skipping quietly is the other failure and the worse one: it would publish a SMALLER book
        # and call it the book (row 115's defect class, and WS-005). So the sleeve is named,
        # counted, and reported as UNPRICEABLE -- a real answer under L1.28a, distinct both from
        # "this sleeve failed" and from "this sleeve does not exist".
        parquet = UNI / f"{sym}_H1.parquet"
        if sym not in meta or not parquet.exists():
            why = "absent from universe.json" if sym not in meta else "no H1 parquet on disk"
            unpriceable.append(f"{sym}_{win}_{state} ({why})")
            continue
        h1 = families._h1(pd.read_parquet(parquet))
        m = meta[sym]
        # Same fix. The non-gold branch was under-charged too: it built the spread at mult=1.0,
        # crossing it once where a round trip crosses it twice.
        costs = Costs.from_symbol(m, mult=2.0)
        states = day_states(h1)
        tr = cell_trades(sym, win, state, h1, costs, states)
        sleeves.append(dict(name=f"{sym}_{win}_{state}", sym=sym, win=win,
                            state=state,
                            r=[t.r_multiple for t in tr],
                            dates=[t.entry_time.date() for t in tr]))
    if unpriceable:
        # Printed on every run, not written to a report nobody opens. The book below is missing
        # these sleeves and the reader has to know that before ranking anything in it.
        print(f"UNPRICEABLE: {len(unpriceable)} gated survivor(s) excluded from this book -- "
              f"the venue no longer prices them:", flush=True)
        for name in unpriceable:
            print(f"  - {name}", flush=True)
        print("  These are NOT failures and NOT absences. Re-admit through the universal gate if "
              "the venue relists them; do not carry the old result forward.", flush=True)
    return sleeves


def build_daily(sleeves: list[dict]) -> pd.DataFrame:
    """Aligned daily-R matrix: rows = dates, cols = sleeves."""
    alldays = sorted({d for s in sleeves for d in s["dates"]})
    daily = pd.DataFrame(index=alldays,
                         columns=[s["name"] for s in sleeves],
                         dtype=float)
    for s in sleeves:
        d = pd.Series(s["r"], index=pd.Index(s["dates"]))
        daily[s["name"]] = d.groupby(level=0).sum().reindex(alldays).fillna(0.0)
    return daily


def main() -> None:
    sleeves = build_sleeves()

    print(f"{'rank':>4} {'sleeve':<26} {'n':>5} {'exp':>7} {'PF':>5} "
          f"{'maxDD':>7} {'S/trade':>7} {'annSharpe':>9}")
    rows = []
    for s in sleeves:
        rs = np.array(s["r"])
        n = len(rs)
        exp = float(rs.mean())
        std = float(rs.std(ddof=1)) if n > 1 else 0.0
        pf = float(rs[rs > 0].sum() / abs(rs[rs < 0].sum())) if (rs < 0).any() else np.inf
        cum = np.cumsum(rs)
        maxdd = float(min(cum[i] - cum[:i + 1].max() for i in range(len(cum))))
        st = exp / std if std > 0 else 0.0
        days = len(set(s["dates"]))
        ann = st * np.sqrt(252 * days / max(n, 1))
        s.update(n=n, exp=exp, pf=pf, maxdd=maxdd, st=st, ann=ann)
        rows.append(s)

    rows.sort(key=lambda s: -s["ann"])
    for i, s in enumerate(rows, 1):
        print(f"{i:4d} {s['name']:<26} {s['n']:5d} {s['exp']:+7.3f} {s['pf']:5.2f} "
              f"{s['maxdd']:7.1f} {s['st']:7.3f} {s['ann']:9.2f}")

    # aligned daily R per sleeve
    daily = build_daily(rows)

    corr = daily.corr()
    vals = corr.values
    off = vals[~np.eye(len(vals), dtype=bool)]
    mean_corr = float(off.mean()) if len(off) else 0.0
    n_eff = len(rows) / (1 + (len(rows) - 1) * mean_corr)

    port = daily.sum(axis=1)
    m, s = port.mean(), port.std(ddof=1)
    sharpe = m / s * np.sqrt(252) if s > 0 else 0.0
    print(f"\nmean cross-sleeve corr = {mean_corr:.3f} | effective N = {n_eff:.1f} "
          f"of {len(rows)} sleeves")

    for q in (0.055, 0.055 * np.sqrt(n_eff)):
        w = (1.0 + q * port).prod()
        years = (daily.index.max() - daily.index.min()).days / 365.25
        cagr = w ** (1 / years) - 1
        worst = float((1.0 + q * port).cumprod().min())
        print(f"q_total={q:.3f}/day-R: net Sharpe {sharpe:.2f}, 8y CAGR {cagr*100:.1f}%, "
              f"min wealth {worst:.3f}")

    out = dict(rows=[{k: s[k] for k in ("name", "sym", "win", "state", "n",
                                        "exp", "pf", "maxdd", "st", "ann")}
                     for s in rows],
               mean_corr=mean_corr, n_eff=n_eff, port_sharpe=sharpe,
               port_daily_mean=m, port_daily_std=s)
    (BASE / "reports" / "portfolio_projection.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\n-> reports/portfolio_projection.json")


if __name__ == "__main__":
    main()