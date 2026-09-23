"""s64: the SIGN-FLIPPED timing conditioner -- the residual s62 declared and did not test.

GROUND. Same as s62 (AQR/FAJ 2011, Israelov & Katz, "To Trade or Not to Trade?"), same panel,
same slow sleeve, same delay machinery. s62 REFUTED the paper's own conditioner on the MT5 panel:
all nine conditional cells negative, and H3 showed an unconditional delay loses money
monotonically to 5 days. Its stated diagnosis was that at a 250-day-TSMOM rebalance the
short-horizon behaviour of this panel is CONTINUATION, not reversal -- so the paper's rule
(a BUY waits for a DOWN print) is pointed the wrong way round for an MT5 CFD book. s62 named the
untested residual explicitly: "delay when the fast signal shows continuation against you rather
than reversal", 9 further declared cells. This is that test.

THE FLIP, stated precisely. s62's rule: for a BUY, wait until the R-day return f <= 0 (buy the
dip). s64's rule: for a BUY, wait until f >= 0 (buy strength); for a SELL, wait until f <= 0.
Everything else -- panel, lookback, rebalance dates, trade set, delay ceiling K, position
construction, shift(1), monthly aggregation, block bootstrap, seed -- is byte-identical to s62,
so the ONLY difference between the two runs is the inequality's direction.

DECLARED BEFORE MEASUREMENT (s29 law -- the sign is written down first, and it is NOT "positive"):
  D1  The flipped conditioner is still NEGATIVE vs immediate execution in every cell. Reason:
      s62's H3 established that a delay of any length costs this sleeve money unconditionally
      (-3.50 bp at k=1, monotone to -8.38 bp at k=5), and no conditioner in a 9-cell grid gets
      to overturn a cost that is paid on the trade itself. I expect no CI to exclude zero above.
  D2  The flipped conditioner nonetheless BEATS s62's original conditioner cell-for-cell (a
      paired comparison on the same (R,K) grid), because the continuation diagnosis predicts the
      original was buying into an adverse drift. If D2 fails, s62's stated diagnosis was wrong
      and the whole conditioner axis is noise -- which is itself the result.
  D3  PLACEBO: a random delay with the flipped arm's own delay multiset does not cover the
      flipped best cell. If it does, D2's margin is delay-length luck, not sign information.
  D4  If any flipped cell is POSITIVE with a CI excluding zero AND clears the placebo, that is a
      real find and routes to a card -- but it is declared here as the LEAST likely branch, and
      it would still be a gross-of-cost timing result on a 1.18 bp/month sleeve (L1.57).

Every cell is a counted trial and every cell is reported (L1.60). Gross of costs by design: the
arms share turnover exactly (identical trade count and identical targets), so no cost model
enters and the s54 zero-cost census defect cannot contaminate the comparison. Diagnostic screen;
no gate threshold applied, no forward clock started, no AQR/BRAIN bar imported (L1.6).
"""
import importlib.util
import itertools
import json
import pathlib

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("s62", pathlib.Path("data/brain/s62_trade_modification.py"))
s62 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s62)

OUT = pathlib.Path("data/brain_hunter_s64_trade_modification_flip.json")
S62_OUT = pathlib.Path("data/brain_hunter_s62_trade_modification.json")
SEED = s62.SEED
FAST, KMAX, N_PLACEBO = s62.FAST, s62.KMAX, s62.N_PLACEBO


def compute_delays_flip(px, rebal, sig, fast, K):
    """Flipped conditional delay: wait for a fast print that AGREES with the trade's direction."""
    loc = {d: i for i, d in enumerate(px.index)}
    fcol = {c: j for j, c in enumerate(fast.columns)}
    F = fast.to_numpy()
    delays, order = {}, []
    cur = pd.Series(0.0, index=px.columns)
    for d in rebal:
        i0 = loc[d]
        tgt = sig.loc[d].fillna(0.0).where(px.loc[d].notna(), cur)
        for s in tgt[(tgt != cur)].index:
            k = K
            for step in range(K + 1):
                f = F[min(i0 + step, len(px.index) - 1), fcol[s]]
                if not np.isfinite(f):
                    continue
                if (tgt[s] > 0 and f >= 0) or (tgt[s] < 0 and f <= 0) or tgt[s] == 0:
                    k = step
                    break
            delays[(d, s)] = k
            order.append((d, s))
        cur = tgt.copy()
    return delays, order


def main() -> None:
    px = pd.read_parquet(s62.CACHE)
    px = px[px.notna().sum(axis=1) >= s62.MIN_SYMS]
    px = px.loc[:, px.notna().sum() >= 1000]
    rets = px.pct_change(fill_method=None)
    rets = rets.where(rets.abs() < 0.5)
    month_ends = px.resample("ME").last().index
    rebal = pd.DatetimeIndex([px.index[px.index <= d][-1] for d in month_ends if (px.index <= d).any()])
    rebal = rebal[(rebal > px.index[s62.LOOKBACK + 20]) & (rebal < px.index[-45])]
    sig = np.sign(px / px.shift(s62.LOOKBACK) - 1.0)

    def port(pos):
        w = pos.div(pos.abs().sum(axis=1).replace(0, np.nan), axis=0)
        return (w * rets).sum(axis=1, min_count=1)

    base_m = port(s62.build_positions(px, rebal, sig, {})).resample("ME").sum()

    def diff_stats(delays):
        m = port(s62.build_positions(px, rebal, sig, delays)).resample("ME").sum()
        idx = base_m.index.intersection(m.index)
        d = (m - base_m).loc[idx].dropna().to_numpy()
        lo, hi, pv = s62.stationary_boot_mean_ci(d, np.random.default_rng(SEED))
        return {
            "n_months": int(len(d)),
            "mean_monthly_diff_bp": round(float(d.mean() * 1e4), 3),
            "ci95_bp": [round(lo * 1e4, 3), round(hi * 1e4, 3)],
            "boot_p": pv,
            "ci_excludes_zero": bool(lo > 0 or hi < 0),
        }

    rng = np.random.default_rng(SEED)
    cells, delay_cache, trials = {}, {}, 0
    for R, K in itertools.product(FAST, KMAX):
        fast = px / px.shift(R) - 1.0
        delays, order = compute_delays_flip(px, rebal, sig, fast, K)
        delay_cache[(R, K)] = (delays, order)
        st = diff_stats(delays)
        st["n_trades"] = len(order)
        st["mean_delay_days"] = round(float(np.mean(list(delays.values()))), 3)
        cells[f"fast{R}d_K{K}"] = st
        trials += 1
        print(f"  flip fast{R}d_K{K}: {st}", flush=True)

    s62_cells = json.loads(S62_OUT.read_text())["conditional_cells"]
    paired = {c: round(cells[c]["mean_monthly_diff_bp"] - s62_cells[c]["mean_monthly_diff_bp"], 3)
              for c in cells if c in s62_cells}
    d2_wins = sum(1 for v in paired.values() if v > 0)

    best = max(cells, key=lambda c: cells[c]["mean_monthly_diff_bp"])
    R = int(best.split("_")[0][4:-1]); K = int(best.split("_K")[1])
    delays, order = delay_cache[(R, K)]
    emp = np.array([delays[key] for key in order])
    obs = cells[best]["mean_monthly_diff_bp"]
    placebo = []
    for b in range(N_PLACEBO):
        perm = rng.permutation(emp)
        d_ = {key: int(v) for key, v in zip(order, perm)}
        m = port(s62.build_positions(px, rebal, sig, d_)).resample("ME").sum()
        idx = base_m.index.intersection(m.index)
        placebo.append(float((m - base_m).loc[idx].dropna().mean() * 1e4))
        if b % 50 == 0:
            print(f"    placebo {b}/{N_PLACEBO}", flush=True)
    placebo = np.array(placebo)

    out = {
        "declared": {
            "D1": "flipped conditioner still NEGATIVE in every cell, no CI excludes zero above",
            "D2": "flipped BEATS s62's original cell-for-cell on the same (R,K) grid",
            "D3": "PLACEBO: random delay with the flipped multiset does not cover the best cell",
            "D4": "a positive cell clearing CI and placebo is a card -- declared least likely",
        },
        "panel": {"symbols": int(px.shape[1]), "start": str(px.index[0].date()),
                  "end": str(px.index[-1].date()), "rebalances": int(len(rebal)),
                  "lookback_days": s62.LOOKBACK},
        "baseline": {"mean_monthly_bp": round(float(base_m.mean() * 1e4), 3),
                     "n_months": int(base_m.notna().sum())},
        "flipped_cells": cells,
        "paired_vs_s62_bp": paired,
        "d2_cells_won": d2_wins,
        "d2_cells_total": len(paired),
        "placebo_control": {
            "best_cell": best, "observed_bp": obs, "n_draws": N_PLACEBO,
            "placebo_mean_bp": round(float(placebo.mean()), 3),
            "placebo_sd_bp": round(float(placebo.std(ddof=1)), 3),
            "placebo_p_ge_observed": round(float((placebo >= obs).mean()), 4),
            "placebo_max_bp": round(float(placebo.max()), 3),
        },
        "trials_reported": trials + 1,
        "seed": SEED,
        "gross_of_costs": True,
        "note": "identical to s62 except the conditioner inequality direction",
    }
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps({"paired": paired, "d2_won": d2_wins, "placebo": out["placebo_control"]}, indent=1))


if __name__ == "__main__":
    main()
