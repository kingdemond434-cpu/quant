#!/usr/bin/env python3
"""Is `reality_check` a correct gate or an unpassable one? Measure it, do not argue about it.

WHY THIS EXISTS. The real campaign finally produced per-gate death counts, and after the
double-multiplicity fix every gate discriminates except one: `reality_check` rejects 196 of 196.
DSR fell to 147, PBO surfaced at 91 -- both now per-candidate -- while this one still kills
everything, which is exactly the signature of a gate with no discriminating power.

But "kills everything" has TWO possible causes and they demand opposite responses:

  CORRECT   -- the mechanisms genuinely do not clear family-wise error control at 5% over 196
               candidates, and the desk should accept that as a real result about its edge.
  UNPASSABLE -- the bar is set where no realistic strategy can reach it, in which case the gate
               is not measuring edge at all, it is measuring the desk's own campaign design.

The desk has been wrong about which of these it faced at least twice, both times by reasoning
instead of counting. So this counts.

WHAT IS MEASURED, on synthetic data matched to the real cohort's shape (T=2,018 bars, N=196
candidates, mean pairwise correlation 0.047 -- all three read off reports/real_campaign.json):

  1. FALSE POSITIVE RATE on a pure null. If this is not near alpha, the gate is broken and
     nothing else here matters.
  2. POWER as a function of TRUE annualised Sharpe -- the minimum real edge the gate can see.
  3. The same two at N = 196, 50, 20 and 5, because multiplicity burden is the desk's own
     CHOICE. 196 candidates is 14 mechanisms x parameter variants x 10 symbols; nothing forces
     that number, and if power is governed by N then the campaign design is the defect rather
     than the gate.

WHAT THIS IS NOT. It does not touch alpha, the gate, or any threshold. A gate that is too strict
gets FIXED BY TESTING FEWER THINGS or by getting more data -- never by moving the bar, which
would convert a real statistical guarantee into a number that means nothing. If the honest answer
is "these mechanisms have no edge", that is a finding the desk should accept and act on.

    python scripts/audit_reality_check.py [--trials 12] [--boot 200]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.validation.stepwise import romano_wolf_stepdown

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "reports" / "reality_check_audit.json"

#: Read off reports/real_campaign.json -- the shape of the cohort the gate actually judged.
REAL_T = 2018
REAL_N = 196
REAL_CORR = 0.047
PPY = 365.0

#: Annualised Sharpe levels swept. The desk's own measured real-edge band is 0.5-1.5 annualised
#: (from an external 131,441-backtest sweep), so the interesting question is whether the gate can
#: see anything INSIDE that band. 3.0 is included as a sanity anchor: a gate that cannot see a 3.0
#: is broken, not strict.
SHARPE_GRID = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)

#: MEASURED 2026-08-01 on the real OKX panel, not assumed. Raw cross-symbol daily return
#: correlation is 0.622; the correlation of the SAME MECHANISM's returns across those symbols --
#: which is what pooling actually averages -- is 0.348. The distinction matters: pooling gain is
#: driven by the strategy-return correlation, and using the raw asset number would have understated
#: it by a wide margin.
MEASURED_CROSS_CORR = 0.348
N_SYMBOLS = 10


def cohort(rng: np.random.Generator, *, t: int, n: int, corr: float,
           true_sharpe_ann: float, n_alphas: int = 1) -> np.ndarray:
    """A (T x N) return panel with the real cohort's correlation and a KNOWN injected edge.

    Correlation is induced by a single common factor with loading sqrt(corr), which reproduces an
    equicorrelated panel exactly -- the same approximation `cohort_independence` uses, so the
    number here is comparable to the 0.047 measured on the real campaign.

    The edge is injected as a DRIFT on the first `n_alphas` columns. Everything else is a true
    null, which is what makes the false-positive rate readable off the same run.
    """
    load = np.sqrt(max(corr, 0.0))
    common = rng.standard_normal((t, 1))
    idio = rng.standard_normal((t, n))
    panel = load * common + np.sqrt(max(1.0 - corr, 0.0)) * idio
    if true_sharpe_ann and n_alphas:
        panel[:, :n_alphas] += true_sharpe_ann / np.sqrt(PPY)
    return panel


def one_trial(rng: np.random.Generator, *, t: int, n: int, sharpe: float,
              boot: int, seed: int) -> tuple[bool, int]:
    """Returns (the injected alpha was rejected, how many TRUE NULLS were rejected)."""
    panel = cohort(rng, t=t, n=n, corr=REAL_CORR, true_sharpe_ann=sharpe, n_alphas=1)
    res = romano_wolf_stepdown(panel, alpha=0.05, n_boot=boot, seed=seed)
    rej = np.asarray(res.rejected, dtype=bool)
    return bool(rej[0]), int(rej[1:].sum())


def theoretical_min_sharpe(t: int, n: int) -> float:
    """The annualised Sharpe that puts a candidate's t-statistic at the max-null critical value.

    t = sqrt(T) * SR_per_bar = SR_ann * sqrt(T / PPY), i.e. SR_ann * sqrt(years). The Romano-Wolf
    critical value is the 95th percentile of the maximum of N bootstrap t-statistics, which for
    approximately independent columns is close to the 1 - 0.05/N normal quantile. So the minimum
    detectable annualised Sharpe is that quantile divided by sqrt(years) -- a closed form the
    simulation below should agree with, and a disagreement would mean the implementation is doing
    something other than what it claims.
    """
    from scipy.stats import norm
    crit = float(norm.ppf(1.0 - 0.05 / max(n, 1)))
    return crit / np.sqrt(t / PPY)


def pooled_power(rng_seed: int, *, n_symbols: int, cross_corr: float, sharpe: float,
                 t: int = REAL_T, n_hypotheses: int = 20, boot: int = 300,
                 trials: int = 20) -> float:
    """Power when ONE mechanism is tested across `n_symbols` as a SINGLE hypothesis.

    THE ONLY LEVER THAT ACTUALLY EXISTS, and it took a wrong answer to find it. The obvious
    response to "not enough observations" is higher-frequency bars -- but the t-statistic is
    sqrt(T) * SR_per_bar and SR_per_bar = SR_ann / sqrt(periods_per_year), so
    t = SR_ann * sqrt(T / PPY) = SR_ann * sqrt(YEARS). Moving from daily to 4h bars multiplies both
    T and PPY by six and changes the statistic by exactly nothing. Bar count is not evidence;
    elapsed time is.

    Pooling is different in kind. The campaign tests `time_series_mom[40]` on BTC, on ETH, on SOL
    and so on as TEN separate hypotheses, which both multiplies the multiplicity burden and throws
    away the fact that they are evidence about the SAME claim. Testing the mechanism once against
    the equal-weight average of its per-symbol returns pools that evidence: the averaged series has
    variance (1 + (m-1) * rho) / m of a single symbol's, so the effective observation count rises
    by m / (1 + (m-1) * rho) -- and N falls from 196 to roughly the number of mechanisms at the
    same time. Both move the bar in the same direction, for free, without touching alpha.
    """
    hits = 0
    for k in range(trials):
        rng = np.random.default_rng(rng_seed + k)
        cols = []
        for h in range(n_hypotheses):
            # Per-symbol returns for one hypothesis: a shared per-hypothesis factor at
            # `cross_corr` plus idiosyncratic noise, averaged equal-weight into one series.
            shared = rng.standard_normal((t, 1))
            per_sym = (np.sqrt(cross_corr) * shared
                       + np.sqrt(max(1.0 - cross_corr, 0.0))
                       * rng.standard_normal((t, n_symbols)))
            if h == 0 and sharpe:
                per_sym += sharpe / np.sqrt(PPY)
            cols.append(per_sym.mean(axis=1))
        panel = np.column_stack(cols)
        res = romano_wolf_stepdown(panel, alpha=0.05, n_boot=boot, seed=k)
        hits += int(bool(res.rejected[0]))
    return round(hits / trials, 3)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    rows: list[dict[str, Any]] = []
    for n in (REAL_N, 50, 20, 5):
        for sharpe in SHARPE_GRID:
            hits = 0
            false_pos = 0
            for k in range(args.trials):
                rng = np.random.default_rng(10_000 + k)
                ok, fp = one_trial(rng, t=REAL_T, n=n, sharpe=sharpe,
                                   boot=args.boot, seed=k)
                hits += int(ok)
                false_pos += fp
            n_nulls = args.trials * (n - 1)
            rows.append({
                "n_candidates": n,
                "true_ann_sharpe": sharpe,
                "power": round(hits / args.trials, 3),
                "false_positive_rate": round(false_pos / max(n_nulls, 1), 5),
                "n_null_columns_tested": n_nulls,
            })
            print(f"  N={n:4d}  SR_ann={sharpe:.1f}  power={hits}/{args.trials}"
                  f"  false_pos={false_pos}/{n_nulls}")

    # THE POOLED DESIGN, at the MEASURED cross-symbol correlation.
    pooled: list[dict[str, Any]] = []
    mult = N_SYMBOLS / (1.0 + (N_SYMBOLS - 1) * MEASURED_CROSS_CORR)
    for sharpe in (0.5, 0.75, 1.0, 1.5):
        p = pooled_power(20_000, n_symbols=N_SYMBOLS, cross_corr=MEASURED_CROSS_CORR,
                         sharpe=sharpe, n_hypotheses=20, boot=args.boot, trials=args.trials)
        pooled.append({"true_ann_sharpe": sharpe, "power": p})
        print(f"  POOLED N=20  SR_ann={sharpe:.2f}  power={p:.2f}")

    min_sr = {n: round(theoretical_min_sharpe(REAL_T, n), 3) for n in (REAL_N, 50, 20, 5, 1)}
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "MEASURED",
        "cohort_shape": {"T": REAL_T, "N": REAL_N, "mean_pairwise_corr": REAL_CORR,
                         "source": "reports/real_campaign.json"},
        "alpha": 0.05, "trials_per_cell": args.trials, "n_boot": args.boot,
        "sweep": rows,
        "pooled_by_mechanism": {
            "n_symbols": N_SYMBOLS,
            "measured_cross_symbol_strategy_corr": MEASURED_CROSS_CORR,
            "raw_cross_symbol_return_corr": 0.622,
            "effective_obs_multiplier": round(mult, 3),
            "t_stat_gain": round(float(np.sqrt(mult)), 3),
            "min_detectable_ann_sharpe": round(
                theoretical_min_sharpe(REAL_T, 20) / float(np.sqrt(mult)), 3),
            "power": pooled,
        },
        "min_detectable_ann_sharpe_closed_form": min_sr,
        "desk_real_edge_band_ann_sharpe": [0.5, 1.5],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), "utf-8")
    print(f"\nclosed-form minimum detectable annualised Sharpe by N: {min_sr}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
