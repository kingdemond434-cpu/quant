"""MICROSTRUCTURE FEATURE FACTORY -- turn the proprietary moat into measurable state variables.

P0. The blocker is gone: every k="d" record is a COMPLETE top-20 book both sides (verified 1358/1358
at (20,20)), so no reconstruction is needed. 4.4GB, 11,980 files, 30 symbols x spot/fut, and nobody
else has these snapshots at these timestamps. Everything else this desk researches -- GitHub, TVL,
attention, on-chain -- is available to anyone. This is not.

NOT INDICATORS. MECHANISM. The mechanism board rates M_LIQUIDITY_WITHDRAWAL as the ONLY untested
family with a live information advantage, and it reached that verdict from graveyard evidence
without knowing the moat existed. Its economic story: liquidity providers withdraw when inventory
risk binds, so price impact jumps. That yields a falsifiable question --

    DOES LIQUIDITY DISAPPEAR *BEFORE* VOLATILITY ARRIVES, OR ONLY ALONGSIDE IT?

which is exactly the lead-vs-coincident distinction that killed 38% of this desk's hypotheses
(C_WRONG_TIMING). So the test is built around it: withdrawal at bucket t vs realised vol at t+1,
with the CONTEMPORANEOUS relationship measured alongside. A liquidity measure that merely coincides
with volatility is not a signal, it IS volatility.

FEATURES per snapshot (state variables, not signals):
  spread_bps            quoted spread
  depth5 / depth10      notional within 5bps / 10bps of mid, both sides
  imbalance             bid share of near depth
  concentration         top-level share of near depth (thin veneer vs real book)
  slope                 depth10/depth5 -- how fast liquidity accumulates away from touch
Aggregated per hour to level + dispersion, then withdrawal is measured as a z-score against each
symbol's own rolling history.

Read-only. No keys, no LLM. Run from repo root.
"""
from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MOAT = ROOT / "data/moat/fut"
OUT = ROOT / "data/micro_features.json"
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
N_FILES = 60          # most recent contiguous hours per symbol
ROLL = 24             # hours of history for the withdrawal z-score


def book_features(rec: dict) -> dict | None:
    b, a = rec.get("b"), rec.get("a")
    if not b or not a:
        return None
    try:
        bp, ap = float(b[0][0]), float(a[0][0])
    except (TypeError, ValueError, IndexError):
        return None
    if bp <= 0 or ap <= 0 or bp >= ap:
        return None
    mid = (bp + ap) / 2
    d5b = d5a = d10b = d10a = 0.0
    top_b = 0.0
    for i, (p, q) in enumerate(b):
        p, q = float(p), float(q)
        n = p * q
        if p >= mid * 0.9995:
            d5b += n
            if i == 0:
                top_b = n
        if p >= mid * 0.999:
            d10b += n
    for p, q in a:
        p, q = float(p), float(q)
        n = p * q
        if p <= mid * 1.0005:
            d5a += n
        if p <= mid * 1.001:
            d10a += n
    near = d5b + d5a
    if near <= 0:
        return None
    return {"mid": mid, "spread_bps": (ap - bp) / mid * 1e4,
            "depth5": near, "depth10": d10b + d10a,
            "imbalance": d5b / near, "concentration": top_b / max(d5b, 1e-9),
            "slope": (d10b + d10a) / near}


def hourly(sym: str) -> list[dict]:
    d = MOAT / sym
    files = sorted(d.glob("*.jsonl.gz"))[-N_FILES:]
    out = []
    for f in files:
        vals: list[dict] = []
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as fh:
                for ln in fh:
                    if '"k":"d"' not in ln and '"k": "d"' not in ln:
                        continue
                    try:
                        r = json.loads(ln)
                    except json.JSONDecodeError:
                        continue
                    fe = book_features(r)
                    if fe:
                        vals.append(fe)
        except Exception:
            continue
        if len(vals) < 30:
            continue
        mids = np.array([v["mid"] for v in vals])
        row = {"hour": f.stem, "n": len(vals), "mid_close": float(mids[-1]),
               "rv_intra": float(np.diff(np.log(mids)).std() * np.sqrt(len(mids)))}
        for k in ("spread_bps", "depth5", "depth10", "imbalance", "concentration", "slope"):
            arr = np.array([v[k] for v in vals])
            row[k] = float(arr.mean())
            if k in ("depth5", "spread_bps"):
                row[k + "_sd"] = float(arr.std())
        out.append(row)
    return out


def spearman(a, b):
    if len(a) < 8:
        return 0.0, 0.0
    ra, rb = np.argsort(np.argsort(a)).astype(float), np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, 0.0
    r = float(np.corrcoef(ra, rb)[0, 1])
    n = len(a)
    return r, float(r * np.sqrt((n - 2) / max(1e-12, 1 - r ** 2)))


def main() -> None:
    print("=== MICROSTRUCTURE FEATURE FACTORY (proprietary moat, no reconstruction needed) ===")
    print("    mechanism M_LIQUIDITY_WITHDRAWAL: does liquidity vanish BEFORE volatility,")
    print("    or only alongside it? (lead-vs-coincident killed 38% of this desk's ideas)\n")
    results, pooled_lead, pooled_coin, pooled_res = [], [], [], []
    for sym in SYMS:
        rows = hourly(sym)
        if len(rows) < 30:
            print(f"  {sym:<10} thin ({len(rows)} usable hours)")
            continue
        d5 = np.array([r["depth5"] for r in rows])
        rv = np.array([r["rv_intra"] for r in rows])
        spr = np.array([r["spread_bps"] for r in rows])

        # WITHDRAWAL = negative z of near depth vs the symbol's own rolling history
        wd = np.zeros(len(d5))
        for i in range(ROLL, len(d5)):
            w = d5[i - ROLL:i]
            sd = w.std()
            wd[i] = -(d5[i] - w.mean()) / sd if sd > 0 else 0.0
        m = np.zeros(len(d5), bool)
        m[ROLL:-1] = True
        fwd = np.roll(rv, -1)

        r_lead, t_lead = spearman(wd[m], fwd[m])       # withdrawal now -> vol NEXT hour
        r_coin, t_coin = spearman(wd[m], rv[m])        # withdrawal now -> vol NOW
        # DE-CONTAMINATION: volatility CLUSTERS, so vol[t] predicts vol[t+1] on its own. A
        # withdrawal measure that is merely COINCIDENT with vol[t] therefore inherits a fake
        # 'lead'. Regress forward vol on current vol and test withdrawal against the RESIDUAL --
        # what is left is the information withdrawal adds BEYOND vol persistence. This is the same
        # gate that killed coinbase/turkey/elite-flow; applying it to my own result.
        _b = np.polyfit(rv[m], fwd[m], 1)
        resid = fwd[m] - (_b[0] * rv[m] + _b[1])
        r_res, t_res = spearman(wd[m], resid)
        r_persist, _ = spearman(rv[m], fwd[m])         # how strong is vol clustering itself?
        r_spr, _ = spearman(wd[m], spr[m])
        pooled_lead.append(r_lead); pooled_res.append(r_res)
        pooled_coin.append(r_coin)
        k = max(3, int(m.sum()) // 4)
        o = np.argsort(wd[m])
        hi, lo = float(fwd[m][o[-k:]].mean()), float(fwd[m][o[:k]].mean())
        print(f"  {sym:<10} hours={int(m.sum()):<4} depth5 ${d5.mean():>12,.0f}  "
              f"spread {spr.mean():5.2f}bps")
        print(f"             withdrawal -> NEXT-hour RV  rho {r_lead:+.3f} (t {t_lead:+.2f})   "
              f"high-wd RV {hi*100:.3f}% vs low {lo*100:.3f}% = {hi/max(lo,1e-9):.2f}x")
        print(f"             withdrawal -> SAME-hour RV  rho {r_coin:+.3f} (t {t_coin:+.2f})")
        print(f"             vol persistence rho {r_persist:+.3f} | RESIDUAL (de-contaminated) "
              f"rho {r_res:+.3f} (t {t_res:+.2f})  <-- the honest number")
        results.append({"sym": sym, "hours": int(m.sum()), "depth5_usd": round(float(d5.mean()), 0),
                        "spread_bps": round(float(spr.mean()), 3),
                        "lead_rho": round(r_lead, 4), "lead_t": round(t_lead, 2),
                        "coincident_rho": round(r_coin, 4), "coincident_t": round(t_coin, 2),
                        "residual_rho": round(r_res, 4), "residual_t": round(t_res, 2),
                        "vol_persistence": round(r_persist, 4),
                        "rv_ratio_hi_lo": round(hi / max(lo, 1e-9), 3),
                        "withdrawal_vs_spread_rho": round(r_spr, 4)})

    if len(pooled_lead) >= 3:
        pl, pc = np.array(pooled_lead), np.array(pooled_coin)
        t_pl = float(pl.mean() / (pl.std() / np.sqrt(len(pl)))) if pl.std() else 0.0
        print(f"\n  POOLED over {len(pl)} symbols:")
        print(f"    LEAD        mean rho {pl.mean():+.4f} (t {t_pl:+.2f}), "
              f"same sign {int((np.sign(pl) == np.sign(pl[0])).sum())}/{len(pl)}")
        print(f"    COINCIDENT  mean rho {pc.mean():+.4f}")
        pr = np.array(pooled_res)
        t_pr = float(pr.mean() / (pr.std() / np.sqrt(len(pr)))) if pr.std() else 0.0
        print(f"    RESIDUAL    mean rho {pr.mean():+.4f} (t {t_pr:+.2f}), "
              f"same sign {int((np.sign(pr) == np.sign(pr[0])).sum())}/{len(pr)}  <-- DECIDES IT")
        verdict = ("LEADS -- withdrawal adds information BEYOND vol persistence"
                   if abs(t_pr) >= 2.4 and abs(pr.mean()) > 0.15 else
                   "COINCIDENT -- the apparent lead is vol clustering, withdrawal adds nothing")
        print(f"    VERDICT: {verdict}")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "roll_hours": ROLL, "results": results}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
