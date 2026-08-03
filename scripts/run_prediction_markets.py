"""Prediction-market calibration + favorite-longshot test (Polymarket, resolved binary markets).

Two questions, both honest:
  1. CALIBRATION: does the de-vigged market probability match realized outcome frequency? (the
     scientific evidence for/against favorite-longshot bias)
  2. DEPLOYABILITY: does a 'back the favorite' strategy clear the validation gauntlet net-of-cost?

PIT: implied probability is taken strictly BEFORE resolution; outcome known only after settlement.
Honest by construction -- binary payoffs are lumpy/fat-tailed, so fragility/DSR gates are decisive.
"""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.data.prediction_markets import (
    fetch_price_history,
    fetch_resolved_markets,
    implied_prob_before,
)
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_OUT = Path("reports/prediction_markets")
_COST = 0.01            # ~1 cent/contract spread+fee haircut on entry
_LEAD_DAYS = 1.0
_FAIL = ["adverse selection (informed counterparties)", "vig/spread", "resolution/oracle risk",
         "tiny capacity", "bias decay as markets mature"]


def _collect(max_markets: int) -> pd.DataFrame:
    markets = fetch_resolved_markets(max_markets=max_markets)
    rows = []
    for i, m in enumerate(markets, 1):
        try:
            hist = fetch_price_history(m["yes_token"])
        except Exception:
            continue
        if hist.empty:
            continue
        end = pd.Timestamp(m["end"])
        p = implied_prob_before(hist, end, lead_days=_LEAD_DAYS)
        if p is None:
            p = float(hist["p"].iloc[0])
        if not (0.02 < p < 0.98):
            continue
        rows.append({"end": end, "p": p, "outcome": m["outcome"], "volume": m["volume"]})
        if i % 100 == 0:
            print(f"  fetched {i}/{len(markets)} markets ({len(rows)} usable)")
    if not rows:
        # AN EMPTY FETCH IS A FACT, NOT AN EXCEPTION. `pd.DataFrame([])` has no columns, so
        # sorting it by "end" raised KeyError and the script died with a pandas traceback that
        # says nothing about the actual problem -- which is that no market was retrieved. That
        # happens whenever the venue is unreachable or returns nothing, and it must read as "the
        # collector is the blocker", the same way every other organ on this desk reports its own
        # empty input.
        return pd.DataFrame(columns=["end", "p", "outcome", "volume"])
    return pd.DataFrame(rows).sort_values("end").reset_index(drop=True)


def _calibration(df: pd.DataFrame) -> list[dict[str, object]]:
    buckets = np.linspace(0, 1, 11)
    out = []
    for lo, hi in pairwise(buckets):
        seg = df[(df["p"] >= lo) & (df["p"] < hi)]
        if len(seg) >= 10:
            out.append({"bucket": f"{lo:.1f}-{hi:.1f}", "n": len(seg),
                        "implied": round(float(seg["p"].mean()), 3),
                        "realized": round(float(seg["outcome"].mean()), 3)})
    return out


def _bet_returns(df: pd.DataFrame, *, min_p: float) -> np.ndarray:
    """Back the FAVORITE (buy the >50% side) when prob exceeds min_p; net of cost. 0 = no bet."""
    r = np.zeros(len(df), dtype="float64")
    for i, row in enumerate(df.itertuples()):
        p, o = row.p, row.outcome
        fav_p = max(p, 1 - p)
        if fav_p < min_p:
            continue
        q = fav_p + _COST                      # entry cost of the favored share
        won = (o == 1.0) if p >= 0.5 else (o == 0.0)
        r[i] = ((1.0 if won else 0.0) - q) / q  # return on capital deployed
    return r


def main() -> None:
    df = _collect(max_markets=2500)
    if df.empty:
        print("prediction-markets: NO RESOLVED MARKETS fetched -- the collector is the blocker "
              "(venue unreachable, or the API returned nothing). Reporting that rather than "
              "crashing on an empty frame: a calibration computed from zero markets would be a "
              "statement about the fetch, not about the market.")
        return
    print(f"\nusable resolved markets: {len(df)}")
    if len(df) < 30:
        raise SystemExit("too few resolved markets to assess anything")

    # Calibration is the scientific question and needs only ~100 obs -- always report it.
    calib = _calibration(df)
    print("CALIBRATION (implied vs realized outcome frequency):")
    for c in calib:
        print(f"  {c['bucket']}  n={c['n']:4}  implied={c['implied']}  realized={c['realized']}")

    variants = [("back_fav_all", 0.5), ("back_fav_60", 0.6), ("back_fav_70", 0.7)]
    series = [(name, _bet_returns(df, min_p=mp)) for name, mp in variants]
    min_len = min(len(r) for _, r in series)
    matrix = np.column_stack([r[-min_len:] for _, r in series])
    sharpes = np.array([sharpe_ratio(r) for _, r in series], dtype="float64")
    pbo, rc = campaign_pbo_rc(matrix)

    survivors = 0
    results = []
    for (name, rets), spr in zip(series, sharpes, strict=True):
        bets = rets[rets != 0.0]
        n_bets = len(bets)
        # The gauntlet needs >=250 obs; below that we report descriptive stats, not a verdict.
        if n_bets >= 250:
            v = validate(bets, hypothesis=Hypothesis(
                family=Family.LIQUIDITY, subtype=f"pm_{name}", symbol="POLYMARKET", params={},
                mechanism=MechanismType.BEHAVIORAL, edge_source="favorite-longshot bias",
                failure_modes=_FAIL), n_trials=len(series), sharpe_estimates=sharpes,
                returns_matrix=matrix, pbo=pbo, rc=rc)
            survived, reason = v.survived, v.rejection_reason
        else:
            survived, reason = False, f"below gauntlet minimum (n={n_bets}<250)"
        survivors += int(survived)
        results.append({"variant": name, "bets": n_bets,
                        "mean_ret": round(float(np.mean(bets)), 4) if n_bets else 0.0,
                        "sharpe_per_bet": round(float(spr), 4),
                        "survived": survived, "reason": reason})

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "report.json").write_text(json.dumps(
        {"usable_markets": len(df), "calibration": calib, "survivors": survivors,
         "strategies": results}, indent=2), "utf-8")
    print(f"\n[prediction-markets] strategies tested={len(series)} survivors={survivors}")
    for r in results:
        print(f"  {r['variant']}: bets={r['bets']} mean={r['mean_ret']} "
              f"sharpe/bet={r['sharpe_per_bet']} survived={r['survived']} {r['reason']}")
    if survivors == 0:
        print("ZERO survivors net-of-cost (honest).")


if __name__ == "__main__":
    main()
