"""STAGE-A SCREEN: exchange netflow as a supply-pressure timing signal (BTC + ETH, 16y).

MECHANISM (stated BEFORE any compute, per SCREEN-ON-DISCOVERY point 2 -- screening a catalogued
axis without a mechanism prior is breadth-mining with extra steps, which the 420/0 result already
refuted): coins moving ONTO exchanges are supply arriving at the only venue where it can be sold,
so positive netflow is revealed selling intent and should precede WEAKER returns; coins moving OFF
exchanges are custody/accumulation and should precede STRONGER returns. Expected IC sign is
NEGATIVE. This is a genuine TIMING signal for the asset itself, so absolute forward return is the
mechanism-appropriate target (only 2 assets exist here, so a cross-sectional build would be a
2-wide panel -- reported as unavailable rather than faked).

TIMESTAMP ALIGNMENT (declared, per SCREEN-ON-DISCOVERY point 4 -- unstated alignment VOIDS the
screen): signal and target come from the SAME Coin Metrics daily rows, keyed by the same `date`
field, ingested from one source. `netflow_ntv` is a UTC-day aggregate and `price_usd` is that same
UTC day's reference price, so signal[t] (flow during UTC day t) predicts the return realised over
the FOLLOWING period, which is exactly the t -> t+1 shift stage_a_screen performs. There is no
cross-source timezone join here, which is the defect class that turned the kimchi and Turkey
premia into pure timing artifacts (a KST-day close sits ~1.6d ahead of a UTC-day close). LOOK-AHEAD
RISK: LOW for that reason; the residual risk is Coin Metrics revising a day's flow after
publication, which this local archive cannot detect.

EVERY CONSTRUCTION TRIED IS LOGGED (point 3 -- reporting only the build that printed is
garden-of-forking-paths p-hacking). Two builds x three horizons x two assets = 12 cells, and ALL
12 are reported and counted as trials regardless of which one looks best:
  raw    -- netflow_ntv as-is
  scaled -- netflow_ntv / sply_ex_ntv, a flow/stock ratio. Economically the right normalisation
            over a 16-year window where native-unit volumes grew ~1000x; the raw build's z-score
            has to absorb that drift through a 20-day window alone.

ZERO PROMOTION AUTHORITY (point 5): Stage A earns a pre-registered forward clock at most, never
capital. Negative screens are first-class deliverables (point 6) and are graveyarded with reason.
"""

from __future__ import annotations

import collections
import json
import sys

import numpy as np

from libs.alpha_factory.hypothesis_novelty import PriorIdea, hypothesis_novelty
from libs.research.axis_screen import stage_a_screen

_SRC = "data/coinmetrics_flows.jsonl"
_HORIZONS = (1, 5, 20)


def _log(m: str) -> None:
    print(m, flush=True)


def _load() -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """asset -> (netflow, exchange_supply, price) as date-sorted daily arrays."""
    rows: dict[str, dict[str, tuple[float, float, float]]] = collections.defaultdict(dict)
    with open(_SRC) as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            a, day = d.get("asset"), str(d.get("date", ""))[:10]
            nf, sx, px = d.get("netflow_ntv"), d.get("sply_ex_ntv"), d.get("price_usd")
            if not a or not day or nf is None or px is None:
                continue
            try:
                rows[a][day] = (float(nf), float(sx) if sx is not None else float("nan"),
                                float(px))
            except (TypeError, ValueError):
                continue
    out = {}
    for a, byday in rows.items():
        days = sorted(byday)
        arr = np.array([byday[d] for d in days], dtype="float64")
        out[a] = (arr[:, 0], arr[:, 1], arr[:, 2])
        _log(f"  {a}: {len(days)} daily rows {days[0]} -> {days[-1]}")
    return out


def _forward_returns(price: np.ndarray, h: int) -> np.ndarray:
    """target_ret[t] = simple return realised OVER period t, where a period is h days.

    stage_a_screen applies the t -> t+1 shift itself, so this must be the CONTEMPORANEOUS
    h-day return, never a shifted one -- shifting here too would double-count the lead and
    manufacture a look-ahead.
    """
    r = np.full(len(price), np.nan)
    r[h:] = price[h:] / price[:-h] - 1.0
    return r


def main() -> int:
    nov = hypothesis_novelty(
        "Exchange netflow (coins moving onto exchanges) is revealed selling intent and precedes "
        "weaker forward returns; outflow to custody precedes stronger returns.",
        features=["netflow_ntv", "sply_ex_ntv", "exchange_supply", "supply_pressure"],
        priors=[
            PriorIdea(id="onchain-reversal", statement="On-chain activity mean-reverts price over "
                      "multi-day horizons", category="onchain",
                      features=["active_addresses", "tx_count", "throughput_usd"],
                      lesson="Killed on 11y held-out OOS (backfill_onchain_oos)."),
            PriorIdea(id="kimchi-premium", statement="Korean exchange price premium predicts BTC "
                      "returns", category="cross-venue", features=["kimchi_premium", "prem_btc"],
                      lesson="Retracted: ~73% timestamp artifact, KST vs UTC candle labels."),
        ],
    )
    _log(f"NOVELTY GATE: novelty={nov.novelty_score:.3f} redundant={nov.is_redundant} "
         f"nearest={nov.nearest_id!r} sim={nov.nearest_similarity:.3f}")
    if nov.is_redundant:
        _log("REDUNDANT -> refusing to spend compute (novelty gate).")
        return 0

    _log(f"loading {_SRC}")
    data = _load()

    results = []
    for asset, (netflow, exsupply, price) in sorted(data.items()):
        builds = {"raw": netflow}
        with np.errstate(divide="ignore", invalid="ignore"):
            scaled = np.where(exsupply > 0, netflow / exsupply, np.nan)
        if np.isfinite(scaled).sum() > 400:
            builds["scaled"] = scaled
        else:
            _log(f"  {asset}: 'scaled' build UNAVAILABLE (sply_ex_ntv too sparse) -- reported, "
                 "not silently dropped")
        for build, sig in builds.items():
            for h in _HORIZONS:
                tgt = _forward_returns(price, h)
                ok = np.isfinite(sig) & np.isfinite(tgt)
                if ok.sum() < 300:
                    _log(f"  SKIP {asset}/{build}/h={h}: only {ok.sum()} aligned obs")
                    continue
                res = stage_a_screen(
                    sig[ok], tgt[ok], name=f"exchange_netflow_{asset}_{build}_h{h}",
                    horizon_days=float(h),
                )
                res.update({"asset": asset, "build": build, "horizon_d": h, "n_obs": int(ok.sum())})
                results.append(res)
                # INSUFFICIENT-DATA returns only name/verdict/n, so never assume 'ic' is present.
                _ic = res.get("ic")
                _log(f"  {asset}/{build}/h={h:2d}  n={ok.sum():5d}  "
                     f"IC={f'{_ic:+.4f}' if _ic is not None else '   n/a'}  "
                     f"resid_IC={res.get('residual_ic')}  verdict={res.get('verdict')}")

    _log(f"\n=== ALL {len(results)} CELLS ARE DSR-COUNTED TRIALS (target/horizon sweep duty) ===")
    for r in sorted(results, key=lambda x: -abs(x.get("ic") or 0.0)):
        _ic = r.get("ic")
        _log(f"  {r['asset']:4s} {r['build']:7s} h={r['horizon_d']:2d}  "
             f"IC={f'{_ic:+.4f}' if _ic is not None else '   n/a'}  verdict={r.get('verdict')}")
    interesting = [r for r in results if "INTERESTING" in str(r.get("verdict", ""))]
    _log(f"\nSCREEN-INTERESTING cells: {len(interesting)} of {len(results)}")

    out = "reports/screen_exchange_netflow.json"
    with open(out, "w") as fh:
        json.dump({"novelty": {"score": nov.novelty_score, "nearest": nov.nearest_id,
                               "similarity": nov.nearest_similarity},
                   "n_trials": len(results), "cells": results}, fh, indent=2, default=str)
    _log(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
