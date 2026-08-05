"""CROSS-MECHANISM CORRELATION -- the one number that decides whether a portfolio-of-weak-edges
architecture is available to this desk at all.

WHY THIS IS THE GATING MEASUREMENT. The desk wants the Medallion shape: many individually-weak,
mutually-uncorrelated edges combined, so that N uncorrelated components of Sharpe s give a
portfolio Sharpe s*sqrt(N). Every term in that sentence is measured on this desk EXCEPT the one
that binds. N is known. s is known. The correlation is not: what
docs/research/REALITY_CHECK_POWER.md measured at rho = 0.348 is SAME-MECHANISM CROSS-SYMBOL
correlation -- momentum-on-BTC against momentum-on-ETH. CROSS-MECHANISM correlation -- carry
against order-flow against barrier-rent -- had never been measured anywhere in this tree, and it
is the only one that governs stacking DIFFERENT edges.

THE ARITHMETIC THAT MAKES IT BINDING. Under equicorrelation, N signals at average pairwise
correlation rho are worth N_eff = N / (1 + (N-1)*rho) independent bets
(libs/research/cohort_independence.effective_bets), and the portfolio Sharpe multiplier is
sqrt(N_eff). That expression CONVERGES as N -> inf: N_eff -> 1/rho. So at the desk's measured
same-mechanism 0.348 the ceiling is 1/0.348 = 2.87 bets, a 1.70x Sharpe multiplier, no matter how
many candidates are stacked. Sharpe 2.0 out of Sharpe-0.2 components needs N_eff = 100, i.e.
rho <= 0.01. ORTHOGONALITY IS THE BINDING CONSTRAINT, NOT CANDIDATE COUNT -- admitting weak
candidates without measuring rho builds a large pile of correlated noise and calls it a portfolio.

MEASURED HERE, 2026-08-05, on the REAL tape already on disk: 21 Binance-Vision daily symbols x
2,037 aligned bars, the desk's own 21 generator specs at every parameter variant = 920 candidate
return streams, net of costs, grouped into 19 MECHANISMS (two lookback settings of one mechanism
are ONE mechanism -- variants and symbols are averaged away before anything is correlated).

    mean off-diagonal cross-mechanism rho   +0.005   -> equicorrelation N_eff 17.3, ceiling 4.16x
    mean ABSOLUTE off-diagonal rho           0.375   -> equicorrelation N_eff  2.45, ceiling 1.57x
    participation ratio (null-calibrated)             ->                  N_eff  4.08, ceiling 2.02x

THE HEADLINE IS 4.08 BETS AND A 2.02x CEILING, AND THE REASON THE FIRST LINE IS NOT THE HEADLINE
IS THE ENTIRE FINDING. A mean off-diagonal correlation of +0.005 reads as "nineteen essentially
independent mechanisms" and it is an artifact of CANCELLATION: the pair distribution runs from
-0.853 to +0.955 with a standard deviation of 0.454. The library is two large blocs -- a
trend-following bloc (time_series_mom, ict_mss_follow, vwap_trend, vol_trend, ma_cross) and a
mean-reversion bloc (vwap_reversion, zscore_fade, shock_fade, wyckoff_spring, ict_sweep_reversal)
-- strongly correlated within and strongly ANTI-correlated across. Their mean is near zero while
the structure is nothing like independence. `cohort_independence`'s own docstring predicts exactly
this failure and says where the disagreement between the two estimators IS the finding; this is
that case, and it is why the equicorrelation number is reported and then explicitly not used.

THE PARTICIPATION RATIO IS READABLE HERE, WHICH IT USUALLY IS NOT. Its known defect is a floor at
T < N. This panel is T = 2,037 against N = 19, so T/N = 107 and there is no floor problem -- and
it is calibrated against an iid null at the same (T, N) anyway rather than assumed: the null
reports 18.83 +- 0.02 where the naive ceiling is 19, so the estimator is unbiased to within 1% on
data whose answer is known, and the observed 4.04 is a measurement rather than an artifact.

NO CROSS-SECTIONAL DEMEANING IS APPLIED ANYWHERE IN THIS FILE, deliberately. Removing a
cross-sectional factor forces residuals to sum to zero at every date, which manufactures average
pairwise correlation of about -1/(N-1) out of data with no structure at all
(`cohort_independence.demeaning_floor`, -0.0556 at N=19) -- the desk has already read that
artifact as a finding once. Every series here is a plain equal-weight average of net returns, so
the floor does not bind; it is reported alongside the measurement so that the distance is visible.

WHAT THIS SAYS ABOUT THE ARCHITECTURE, stated plainly because it is not the answer that was
hoped for. Cross-mechanism stacking is genuinely BETTER than cross-symbol stacking -- 4.08 bets
and 2.02x against 2.87 bets and 1.70x -- so the ensemble path is worth building. It is not
remotely close to the 100 effective bets that Sharpe 2.0 from Sharpe-0.2 components requires.
On this mechanism library the honest ceiling is 0.2 * 2.02 = 0.40 portfolio Sharpe. The binding
constraint is therefore the number of GENUINELY DISTINCT mechanisms, and this library, which
looks like 19, is worth 4. Widening the mechanism space means new DATA AXES, not new rules
computed from the same OHLCV tape -- every one of these 19 is a price-derived rule, which is why
they collapse into two blocs.

PARAMETER VARIANTS BUY ALMOST NOTHING, which is why the grouping is the measurement rather than a
formatting choice. Splitting the same 19 mechanisms into their 44 parameter variants raises
calibrated breadth from 4.08 to 4.42 -- 25 extra "hypotheses" for 0.34 of an extra bet -- while
the naive equicorrelation reading rises from 17.3 to 33.6 and would report a 5.79x ceiling. That
is the illusion the desk's campaign counts have been carrying: 920 candidates, 44 variants, 19
mechanisms, 4 bets.

A SECOND FINDING WORTH RECORDING: the desk's own FAMILY taxonomy does not partition mechanisms.
`liquidity/shock_fade` and `mean_reversion/zscore_fade` sit in different families and correlate at
+0.953; `momentum/time_series_mom` and `trend/vwap_trend` at +0.955. Counting families as
independent bets overstates breadth by about 4x.

NO SIGN IS EVER FLIPPED HERE. Five of the 19 mechanisms have negative in-sample Sharpe and
flipping them would raise every headline. Choosing a sign after seeing the result is the
garden-of-forking-paths this desk's whole gauntlet exists to stop; the sign is a parameter and
must be pre-registered like any other.

    python3 scripts/measure_cross_mechanism_corr.py            # measure from the on-disk cache
    python3 scripts/measure_cross_mechanism_corr.py --fetch     # VPS: populate the cache first

Writes data/cross_mechanism_corr.json. If the tape is not on this checkout and --fetch is not
passed, it writes status NOT-READABLE-HERE naming the exact missing files and exits NONZERO. It
never simulates a market to fill the gap -- the iid null below calibrates an ESTIMATOR whose
answer is known by construction, which is measurement; simulating a tape to learn what mechanisms
do would be invention.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:                       # runnable as `python3 scripts/...` from root
    sys.path.insert(0, str(ROOT))

from libs.research.cohort_independence import (  # noqa: E402
    BENCHMARK_MEAN_CORR,
    demeaning_floor,
    effective_bets,
)

OUT = ROOT / "data" / "cross_mechanism_corr.json"
CACHE = ROOT / "data" / "binance_vision"

#: The 21-symbol Binance USD-M panel declared in scripts/run_real_campaign.py. Frozen in source
#: and copied rather than ranked live: selecting a universe on end-of-sample liquidity and then
#: serving its whole history is the survivorship defect W-21 recorded, and this measurement is
#: about correlation structure, which that bias moves.
UNIVERSE: tuple[str, ...] = (
    "BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX", "ADA", "XRP", "LTC", "BCH",
    "BNB", "TRX", "DOT", "NEAR", "ATOM", "UNI", "FIL", "ETC", "XLM", "ALGO", "AAVE",
)
_INTERVAL, _START, _END = "1d", "2020-12", "2026-07"

#: The same-mechanism cross-symbol correlation this desk has already measured, from
#: docs/research/REALITY_CHECK_POWER.md:78. Every cross-mechanism number is reported AGAINST it,
#: because the whole question is whether stacking different mechanisms buys more than stacking one
#: mechanism across symbols.
SAME_MECHANISM_CROSS_SYMBOL_RHO = 0.348

#: Component Sharpe assumed when quoting the implied portfolio ceiling. 0.2 is the weak-edge case
#: the ensemble architecture exists to exploit; it is a REPORTING assumption, not a measurement,
#: and is named in the artifact so nobody reads the ceiling as an observed Sharpe.
WEAK_COMPONENT_SHARPE = 0.2

#: Portfolio Sharpe the Medallion shape is aiming at, and the N_eff it demands from 0.2 components.
TARGET_PORTFOLIO_SHARPE = 2.0

#: Draws used to calibrate the participation ratio against an iid null at the SAME (T, N). Fixed
#: seed: this artifact is read by other code and a headline that moves when nothing moved is not a
#: headline.
_NULL_DRAWS = 50
_NULL_SEED = 20260805

#: Minimum aligned observations and minimum mechanisms below which the answer is not measurable.
#: Deliberately not "best effort on whatever survived" -- a cross-mechanism rho computed on four
#: mechanisms is a different question, and it would be read as this one's answer anyway.
_MIN_OBS = 400
_MIN_MECHANISMS = 5

#: Fraction of bars a candidate must actually hold a position for, and the return-sd floor below
#: which its feed is dead rather than quiet. Both copied from the campaign path so this measures
#: the SAME candidate set the gauntlet scored; a dead column correlates with nothing because it
#: does nothing, and would read as the most diversifying mechanism in the library.
_MIN_ACTIVE_FRACTION = 0.01
_RET_SD_FLOOR = 1e-12

_PPY = 365.0


# --------------------------------------------------------------------------- estimator internals

def _mean_offdiag(corr: np.ndarray) -> tuple[float, float, float, float, float, float]:
    """(mean, median, mean absolute, sd, min, max) of the strict upper triangle."""
    iu = np.triu_indices(corr.shape[0], k=1)
    pair = corr[iu]
    pair = pair[np.isfinite(pair)]
    if pair.size == 0:
        nan = float("nan")
        return nan, nan, nan, nan, nan, nan
    return (float(pair.mean()), float(np.median(pair)), float(np.abs(pair).mean()),
            float(pair.std(ddof=1)) if pair.size > 1 else 0.0,
            float(pair.min()), float(pair.max()))


def participation_ratio(corr: np.ndarray) -> float:
    """(sum lambda)^2 / sum(lambda^2) -- effective rank, which SEES CLUSTERS.

    The equicorrelation estimator assumes every pair is equally correlated and therefore reports
    near-independence for a matrix of offsetting blocs, whose mean off-diagonal correlation is
    near zero while its structure is anything but. This one reads the eigenvalue spectrum instead,
    so a two-bloc library collapses to roughly two, which is the honest answer.
    """
    ev = np.clip(np.linalg.eigvalsh(np.asarray(corr, dtype="float64")), 0.0, None)
    denom = float(np.sum(ev**2))
    return float(np.sum(ev) ** 2 / denom) if denom > 0 else float("nan")


def _null_participation_ratio(t_obs: int, n: int) -> tuple[float, float]:
    """The participation ratio an IID panel of the same shape reports. Its floor, measured.

    A number with no floor is not a measurement. The participation ratio is biased DOWNWARD at
    finite T because a sample correlation matrix of independent columns is not the identity, and
    booking that bias as redundancy would understate breadth. This is the estimator's answer on
    data whose true answer is exactly N.
    """
    rng = np.random.default_rng(_NULL_SEED)
    draws = [participation_ratio(np.corrcoef(rng.standard_normal((t_obs, n)), rowvar=False))
             for _ in range(_NULL_DRAWS)]
    return float(np.mean(draws)), float(np.std(draws, ddof=1))


def _ceiling(n_eff: float) -> dict[str, float]:
    """Sharpe multiplier sqrt(N_eff) and what it implies for a book of weak components."""
    mult = float(np.sqrt(max(n_eff, 0.0)))
    return {"n_eff": round(float(n_eff), 4),
            "sharpe_multiplier": round(mult, 4),
            "portfolio_sharpe_from_weak_components": round(WEAK_COMPONENT_SHARPE * mult, 4)}


def summarise(corr: np.ndarray, labels: list[str], *, t_obs: int) -> dict[str, Any]:
    """Every reading of one correlation matrix, with the equicorrelation caveat attached."""
    n = len(labels)
    mean, median, mean_abs, sd, lo, hi = _mean_offdiag(corr)
    null_pr, null_sd = _null_participation_ratio(t_obs, n)
    obs_pr = participation_ratio(corr)
    calibrated = float(obs_pr / null_pr * n) if null_pr > 0 else float("nan")
    equi = effective_bets(n, mean)
    equi_abs = effective_bets(n, mean_abs)
    # A near-zero MEAN with a large SPREAD is cancellation, not independence. The threshold is the
    # professional benchmark itself: if the average absolute pair correlation is above 0.159 while
    # the signed mean is below it, the two readings disagree and the signed one is not usable.
    cancelling = bool(mean_abs > BENCHMARK_MEAN_CORR and abs(mean) < BENCHMARK_MEAN_CORR)
    return {
        "n_series": n,
        "n_obs": int(t_obs),
        "labels": labels,
        "mean_offdiag_rho": round(mean, 6),
        "median_offdiag_rho": round(median, 6),
        "mean_abs_offdiag_rho": round(mean_abs, 6),
        "sd_offdiag_rho": round(sd, 6),
        "min_offdiag_rho": round(lo, 6),
        "max_offdiag_rho": round(hi, 6),
        "demeaning_floor": round(demeaning_floor(n), 6),
        "no_demeaning_applied": True,
        "equicorrelation": _ceiling(equi),
        "equicorrelation_on_abs_rho": _ceiling(equi_abs),
        "participation_ratio": round(obs_pr, 4),
        "participation_ratio_iid_null": round(null_pr, 4),
        "participation_ratio_iid_null_sd": round(null_sd, 4),
        "calibrated_breadth": _ceiling(calibrated),
        "headline_n_eff": round(calibrated if cancelling else min(equi, calibrated), 4),
        "cancellation_detected": cancelling,
        "note": (
            "signed mean rho is NOT usable here: mean|rho| is far above it, so the near-zero "
            "average is offsetting blocs cancelling rather than independence. Read "
            "calibrated_breadth." if cancelling else
            "signed and absolute readings agree; the equicorrelation approximation is usable."),
    }


# ------------------------------------------------------------------------------ the candidate set

def _load_panel(symbols: tuple[str, ...], *, allow_fetch: bool) -> tuple[
        dict[str, dict[str, np.ndarray]], list[str]]:
    """Aligned OHLCV per symbol from the on-disk Binance Vision cache. Never invents a bar."""
    from scripts.fetch_binance_vision import load_or_fetch
    panel: dict[str, dict[str, np.ndarray]] = {}
    missing: list[str] = []
    for sym in symbols:
        cached = CACHE / f"{sym}USDT-{_INTERVAL}-{_START}-{_END}.npz"
        if not cached.exists() and not allow_fetch:
            missing.append(str(cached.relative_to(ROOT)) if cached.is_relative_to(ROOT)
                           else str(cached))
            continue
        raw = load_or_fetch(f"{sym}USDT", _INTERVAL, _START, _END)
        if len(raw.get("close", ())) < _MIN_OBS:
            missing.append(f"{cached.name} (fewer than {_MIN_OBS} bars)")
            continue
        panel[sym] = {k: np.asarray(raw[k], dtype="float64")
                      for k in ("open", "high", "low", "close", "volume")}
    return panel, missing


def build_candidates(panel: dict[str, dict[str, np.ndarray]]) -> list[dict[str, Any]]:
    """Every (symbol x generator x parameter variant) net-return stream the campaign scores.

    Constructed by the SAME code path as scripts/run_real_campaign.py -- same generators, same
    net_returns, same activity and variance filters -- so this measures the correlation of the
    candidate set the gauntlet actually judged, not of a lookalike written for this file.
    """
    from libs.autodiscovery.generators import GENERATORS, net_returns
    from libs.autodiscovery.models import MarketSeries
    btc = panel.get("BTC")
    out: list[dict[str, Any]] = []
    for sym, raw in sorted(panel.items()):
        series, n = dict(raw), len(raw["close"])
        ref = None
        if btc is not None and sym != "BTC":
            m = min(n, len(btc["close"]))
            ref = {k: v[-m:] for k, v in btc.items()}
            series = {k: v[-m:] for k, v in series.items()}
            n = m
        ser = MarketSeries(
            close=series["close"], high=series["high"], low=series["low"],
            volume=series["volume"], hour=np.zeros(n),
            ref_close=ref["close"] if ref is not None else None,
            ref_high=ref["high"] if ref is not None else None,
            ref_low=ref["low"] if ref is not None else None,
        )
        for spec in GENERATORS:
            for variant in spec.param_variants:
                try:
                    pos = np.asarray(spec.fn(ser, dict(variant)), dtype="float64")
                except Exception:            # a generator that cannot run on this symbol is
                    continue                 # absent evidence, not a failed measurement
                if pos.size == 0 or float(np.mean(pos != 0.0)) < _MIN_ACTIVE_FRACTION:
                    continue
                r = np.asarray(net_returns(ser, pos), dtype="float64")
                if not np.all(np.isfinite(r)) or float(np.std(r)) <= _RET_SD_FLOOR:
                    continue
                out.append({"symbol": sym, "family": str(spec.family), "subtype": spec.subtype,
                            "params": dict(variant), "returns": r})
    return out


def group_series(candidates: list[dict[str, Any]], keys: tuple[str, ...],
                 t_obs: int) -> tuple[list[str], np.ndarray]:
    """Equal-weight the candidates sharing `keys` into ONE series per group.

    THE GROUPING IS THE MEASUREMENT. Grouping by (family, subtype) is what makes two lookback
    settings of one mechanism ONE mechanism: parameter variants and symbols are averaged away
    before anything is correlated, so the answer is about mechanisms rather than about how many
    knobs each generator happens to expose. Grouping by the parameter tuple instead answers a
    different and much easier question, and is reported separately precisely to show the gap.
    """
    buckets: dict[str, list[np.ndarray]] = {}
    for c in candidates:
        parts = []
        for k in keys:
            parts.append(str(tuple(sorted(c["params"].items()))) if k == "params" else str(c[k]))
        buckets.setdefault("/".join(parts), []).append(c["returns"][-t_obs:])
    labels = sorted(buckets)
    cols = np.column_stack([np.column_stack(buckets[k]).mean(axis=1) for k in labels])
    live = np.std(cols, axis=0) > _RET_SD_FLOOR
    return [lbl for lbl, ok in zip(labels, live, strict=True) if ok], cols[:, live]


def same_mechanism_cross_symbol(candidates: list[dict[str, Any]], t_obs: int) -> dict[str, Any]:
    """Reproduce the desk's PUBLISHED 0.348 on this panel, as the comparison the finding needs.

    Cross-mechanism rho is only interesting relative to the correlation the desk already pays when
    it stacks one mechanism across symbols. Measured the same way, on the same bars, so the two
    numbers are comparable rather than merely adjacent.
    """
    per: dict[str, dict[str, list[np.ndarray]]] = {}
    for c in candidates:
        mech = f"{c['family']}/{c['subtype']}"
        per.setdefault(mech, {}).setdefault(str(c["symbol"]), []).append(c["returns"][-t_obs:])
    rhos: list[float] = []
    for legs in per.values():
        if len(legs) < 2:
            continue
        cols = np.column_stack([np.column_stack(v).mean(axis=1) for _, v in sorted(legs.items())])
        cols = cols[:, np.std(cols, axis=0) > _RET_SD_FLOOR]
        if cols.shape[1] < 2:
            continue
        rhos.append(_mean_offdiag(np.corrcoef(cols, rowvar=False))[0])
    if not rhos:
        return {"measurable": False, "published_rho": SAME_MECHANISM_CROSS_SYMBOL_RHO}
    measured = float(np.mean(rhos))
    n_sym = len({str(c["symbol"]) for c in candidates})
    return {
        "measurable": True,
        "n_mechanisms": len(rhos),
        "n_symbols": n_sym,
        "measured_rho": round(measured, 6),
        "published_rho": SAME_MECHANISM_CROSS_SYMBOL_RHO,
        "published_source": "docs/research/REALITY_CHECK_POWER.md:78",
        "ceiling_at_measured": _ceiling(effective_bets(n_sym, measured)),
        "ceiling_at_published_asymptote": _ceiling(1.0 / SAME_MECHANISM_CROSS_SYMBOL_RHO),
        "note": ("the published figure is a 10-symbol panel; this is the same statistic on the "
                 "21-symbol panel and is reported for comparability, not as a correction"),
    }


def orthogonality_required() -> dict[str, Any]:
    """What rho the Medallion target actually demands. The arithmetic that constrains the fix."""
    n_eff_needed = (TARGET_PORTFOLIO_SHARPE / WEAK_COMPONENT_SHARPE) ** 2
    return {
        "target_portfolio_sharpe": TARGET_PORTFOLIO_SHARPE,
        "component_sharpe": WEAK_COMPONENT_SHARPE,
        "n_eff_required": round(n_eff_needed, 2),
        "max_rho_as_n_to_infinity": round(1.0 / n_eff_needed, 6),
        "note": ("N_eff = N/(1+(N-1)rho) converges to 1/rho, so no candidate count reaches "
                 f"N_eff {n_eff_needed:.0f} unless rho <= {1.0 / n_eff_needed:.4f}. Orthogonality "
                 "is the binding constraint; candidate count is not."),
    }


# ------------------------------------------------------------------------------------------ main

def _blocked(missing: list[str], why: str) -> int:
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "NOT-READABLE-HERE",
        "why": why,
        "missing_inputs": missing,
        "how_to_run": ("python3 scripts/measure_cross_mechanism_corr.py --fetch  (on the VPS, "
                       "which can reach the Binance Vision archive). Nothing here is simulated "
                       "and no partial answer is written -- a cross-mechanism rho computed on a "
                       "truncated panel would be read as the finding."),
        "same_mechanism_cross_symbol_rho_published": SAME_MECHANISM_CROSS_SYMBOL_RHO,
        "orthogonality_required": orthogonality_required(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2), "utf-8")
    print(json.dumps(doc, indent=2))
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default=",".join(UNIVERSE))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--fetch", action="store_true",
                    help="allow network fetch into the cache (VPS); default is cache-only")
    args = ap.parse_args(argv)
    symbols = tuple(s.strip().upper() for s in str(args.symbols).split(",") if s.strip())

    panel, missing = _load_panel(symbols, allow_fetch=bool(args.fetch))
    if len(panel) < 2:
        return _blocked(missing or list(symbols),
                        "fewer than two symbols of tape are readable on this checkout")

    candidates = build_candidates(panel)
    if not candidates:
        return _blocked([], "the generator set produced no scorable candidate on this tape")
    t_obs = min(len(c["returns"]) for c in candidates)
    if t_obs < _MIN_OBS:
        return _blocked([], f"only {t_obs} aligned bars; {_MIN_OBS} required")

    mech_labels, mech_cols = group_series(candidates, ("family", "subtype"), t_obs)
    if len(mech_labels) < _MIN_MECHANISMS:
        return _blocked([], f"only {len(mech_labels)} mechanisms; {_MIN_MECHANISMS} required")
    mech_corr = np.corrcoef(mech_cols, rowvar=False)
    mechanism = summarise(mech_corr, mech_labels, t_obs=t_obs)

    fam_labels, fam_cols = group_series(candidates, ("family",), t_obs)
    var_labels, var_cols = group_series(candidates, ("family", "subtype", "params"), t_obs)

    iu = np.triu_indices(len(mech_labels), k=1)
    pairs = sorted(
        ({"a": mech_labels[i], "b": mech_labels[j], "rho": round(float(mech_corr[i, j]), 4)}
         for i, j in zip(*iu, strict=True)),
        key=lambda d: float(d["rho"]))
    ann = mech_cols.mean(axis=0) / mech_cols.std(axis=0, ddof=1) * np.sqrt(_PPY)

    doc: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "MEASURED",
        "source": f"binance-vision:{_INTERVAL}:{_START}..{_END}",
        "symbols": sorted(panel),
        "unreadable_symbols": missing,
        "n_candidates": len(candidates),
        "n_obs": int(t_obs),
        "grouping": ("MECHANISM = (family, subtype). Parameter variants and symbols are averaged "
                     "equal-weight into one series per mechanism BEFORE any correlation is taken, "
                     "so two lookback settings of one mechanism are one mechanism."),
        "cross_mechanism": mechanism,
        "cross_family": summarise(np.corrcoef(fam_cols, rowvar=False), fam_labels, t_obs=t_obs),
        "by_parameter_variant": summarise(np.corrcoef(var_cols, rowvar=False), var_labels,
                                          t_obs=t_obs),
        "same_mechanism_cross_symbol": same_mechanism_cross_symbol(candidates, t_obs),
        "orthogonality_required": orthogonality_required(),
        "most_negative_pairs": pairs[:6],
        "most_positive_pairs": pairs[-6:],
        "mechanism_ann_sharpe": {lbl: round(float(s), 4)
                                 for lbl, s in sorted(zip(mech_labels, ann, strict=True),
                                                      key=lambda kv: -float(kv[1]))},
        "signs_not_flipped": ("no mechanism's sign was flipped. Choosing a sign after seeing the "
                              "result is a forking path; the sign is a parameter and must be "
                              "pre-registered like any other."),
    }
    head = doc["cross_mechanism"]
    doc["verdict"] = (
        f"{head['n_series']} mechanisms are worth {head['headline_n_eff']:.2f} independent bets "
        f"-> {np.sqrt(head['headline_n_eff']):.2f}x Sharpe ceiling. Sharpe "
        f"{TARGET_PORTFOLIO_SHARPE} from {WEAK_COMPONENT_SHARPE}-Sharpe components needs "
        f"{orthogonality_required()['n_eff_required']:.0f}. The ensemble path is worth building "
        "and the Medallion target is not reachable on this mechanism library; the binding "
        "constraint is DISTINCT MECHANISMS, which means new data axes rather than new rules on "
        "the same tape.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), "utf-8")
    print(json.dumps({k: doc[k] for k in ("n_candidates", "n_obs", "verdict")}, indent=2))
    print(f"cross-mechanism: mean rho {head['mean_offdiag_rho']:+.4f} "
          f"(|rho| {head['mean_abs_offdiag_rho']:.4f}), "
          f"equicorr N_eff {head['equicorrelation']['n_eff']:.2f}, "
          f"calibrated breadth {head['calibrated_breadth']['n_eff']:.2f}, "
          f"ceiling {head['calibrated_breadth']['sharpe_multiplier']:.2f}x")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
