#!/usr/bin/env python
"""FALSIFIER for the funding-state axis (capability hunt 2026-08-13 s0), run BEFORE the build.

The claim under test: the three wired regime gates (``libs/autodiscovery/regime.regime_robust``,
``libs/risk/sleeve_allocation`` min_regimes_positive, ``scripts/check_promotion_gate`` two_regimes)
all partition by realized-VOLATILITY terciles, and that partition cannot see the state in which the
desk's only surviving edge (funding carry) actually dies.

PRE-REGISTERED KILL CRITERION (fixed before the run, per the proposal's own falsifier):
    If the vol-tercile partition separates carry returns AS WELL AS OR BETTER THAN the funding-state
    partition, the existing certificate already captures what matters and the capability is DEAD --
    record that vol is a sufficient proxy for funding state in crypto.

The decisive statistic is NOT variance explained. The gate's rule is "net-positive in >=2 groups",
so a partition earns its place only if it can produce a group where the edge is NOT positive. A
partition that explains variance while leaving every group profitable changes no verdict.

Runs on data already on disk: data/lake/bronze/crypto/{SYM}/D1 (close + funding).
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.autodiscovery.regime import _VOL_WINDOW, vol_regime_labels
from libs.research.crypto_regime import regime_labels

ROOT = Path(__file__).resolve().parents[1]
_LAKE = ROOT / "data/lake/bronze/crypto"
_OUT = ROOT / "reports/falsify_funding_state_axis.json"

#: a symbol needs this many daily bars to join the panel (2 years -- enough to span both states)
_MIN_BARS = 500
#: the live book's carry sleeve holds this many names (run_cashcarry_executor `top`)
_TOP_N = 10


def _load_panel(min_bars: int = _MIN_BARS) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Return (close, funding) wide frames plus an attrition count (L1.60: skips are counted)."""
    attrition = {"attempted": 0, "no_parts": 0, "unreadable": 0, "too_short": 0, "kept": 0}
    closes: dict[str, pd.Series] = {}
    fundings: dict[str, pd.Series] = {}
    for sym_dir in sorted(_LAKE.iterdir()):
        if not sym_dir.is_dir():
            continue
        attrition["attempted"] += 1
        parts = sorted(glob.glob(str(sym_dir / "D1/**/*.parquet"), recursive=True))
        if not parts:
            attrition["no_parts"] += 1
            continue
        try:
            d = pd.concat([pd.read_parquet(p) for p in parts])
        except (OSError, ValueError):
            attrition["unreadable"] += 1
            continue
        if "funding" not in d.columns or "close" not in d.columns:
            attrition["unreadable"] += 1
            continue
        d = d.dropna(subset=["close"]).drop_duplicates(subset=["timestamp"])
        d = d.set_index(pd.to_datetime(d["timestamp"], utc=True).dt.normalize()).sort_index()
        if len(d) < min_bars:
            attrition["too_short"] += 1
            continue
        closes[sym_dir.name] = d["close"]
        fundings[sym_dir.name] = d["funding"]
        attrition["kept"] += 1
    return pd.DataFrame(closes).sort_index(), pd.DataFrame(fundings).sort_index(), attrition


def carry_sleeve_returns(funding: pd.DataFrame, *, top_n: int = _TOP_N,
                         cost_bps_per_turn: float = 0.0) -> tuple[pd.Series, float]:
    """Daily return of a delta-neutral carry sleeve harvesting the top-N funding names.

    Selection is made from funding known STRICTLY BEFORE the harvest day (shift(1) on a 7-day
    trailing mean), so no future funding chooses the basket. Delta-neutral, so price drops out to
    first order and the sleeve's return is the funding it collects MINUS turnover cost.

    ``cost_bps_per_turn`` is charged on the fraction of the basket that changed, across BOTH legs
    (spot + perp). It is the FIRST cost applied to this series -- the gross funding panel carries
    none -- so this is not the double-charge the desk's own gauntlet lesson warns about.

    Returns (series, mean_daily_turnover).
    """
    signal = funding.rolling(7, min_periods=3).mean().shift(1)
    out: list[float] = []
    idx: list[pd.Timestamp] = []
    turnovers: list[float] = []
    prev: set[str] = set()
    for day in funding.index:
        s = signal.loc[day].dropna()
        if len(s) < top_n:
            continue
        picks = s.nlargest(top_n).index
        realized = funding.loc[day, picks].dropna()
        if realized.empty:
            continue
        held = set(picks)
        turnover = len(held - prev) / float(top_n) if prev else 1.0
        prev = held
        # both legs pay, on the changed fraction only (the sleeve holds through unchanged names)
        cost = turnover * 2.0 * cost_bps_per_turn * 1e-4
        turnovers.append(turnover)
        out.append(float(realized.mean()) - cost)
        idx.append(day)
    mean_turnover = round(float(np.mean(turnovers)), 4) if turnovers else 0.0
    return pd.Series(out, index=pd.DatetimeIndex(idx), name="carry"), mean_turnover


def _group_stats(r: np.ndarray) -> dict[str, float]:
    n = len(r)
    if n < 2:
        return {"n": n, "mean_bps": 0.0, "t_stat": 0.0, "positive": False}
    mean = float(np.mean(r))
    sd = float(np.std(r, ddof=1))
    t = mean / (sd / np.sqrt(n)) if sd > 0 else 0.0
    return {"n": n, "mean_bps": round(mean * 1e4, 4), "t_stat": round(t, 3),
            "positive": bool(mean > 0)}


def _eta_squared(r: np.ndarray, labels: np.ndarray) -> float:
    """Fraction of return variance explained by the partition (0 = partition is uninformative)."""
    valid = labels != "__none__"
    r, labels = r[valid], labels[valid]
    if len(r) < 3:
        return 0.0
    grand = float(np.mean(r))
    ss_total = float(np.sum((r - grand) ** 2))
    if ss_total <= 0:
        return 0.0
    ss_between = 0.0
    for g in np.unique(labels):
        m = labels == g
        ss_between += int(m.sum()) * (float(np.mean(r[m])) - grand) ** 2
    return round(ss_between / ss_total, 5)


def evaluate(carry: pd.Series, close: pd.DataFrame, funding: pd.DataFrame) -> dict[str, Any]:
    """Partition carry returns by BOTH axes and report which one can find a dead state."""
    r = carry.to_numpy(dtype="float64")

    # Axis V -- exactly what the wired gate does: terciles of the STRATEGY'S OWN realized vol.
    vlab = vol_regime_labels(r)
    v_named = np.array([f"vol_{x}" if x >= 0 else "__none__" for x in vlab])

    # Axis F -- the funding rich/poor labeller that exists and is wired into no gate.
    flab = regime_labels(close, funding).reindex(carry.index)["funding"]
    f_named = flab.fillna("__none__").to_numpy().astype(str)

    axes: dict[str, dict[str, Any]] = {}
    for name, labels in (("vol_terciles", v_named), ("funding_state", f_named)):
        groups = {g: _group_stats(r[labels == g]) for g in sorted(set(labels)) if g != "__none__"}
        present = [g for g, s in groups.items() if s["n"] >= 30]
        n_positive = sum(1 for g in present if groups[g]["positive"])
        axes[name] = {
            "groups": groups,
            "n_groups_present": len(present),
            "n_groups_positive": n_positive,
            "finds_dead_state": bool(present) and n_positive < len(present),
            "eta_squared": _eta_squared(r, labels),
            "mean_spread_bps": round(
                (max(groups[g]["mean_bps"] for g in present)
                 - min(groups[g]["mean_bps"] for g in present)) if present else 0.0, 4),
        }

    v, f = axes["vol_terciles"], axes["funding_state"]

    # INSTRUMENT CHECKS -- run BEFORE the adjudication, because a verdict from a blunt instrument
    # is the false-null direction no other gate on this desk catches (L1.62). The first run of this
    # falsifier failed all three and would have reported REFUTED from a criterion that could not
    # fire; they are first-class output, never a footnote.
    roll_vol = pd.Series(r).rolling(_VOL_WINDOW).std()
    instrument = {
        # Q1: if almost no day is negative, `finds_dead_state` is welded off for BOTH axes and the
        # decisive criterion carries zero information (L1.43).
        "share_days_non_positive": round(float((r <= 0).mean()), 4),
        # Q2: the gate partitions the strategy's own returns by their own vol. On a funding-derived
        # series that is partly a partition by |funding| itself.
        "corr_vol_vs_level": round(float(roll_vol.corr(pd.Series(r))), 4),
        # Q3: daily top-N selection re-introduces positive funding even in a market-wide drought,
        # so the sleeve's exposure to funding state is NOT the market's funding state.
        "unselected_share_non_positive": None,  # filled by the caller, which holds the full panel
    }

    can_find_dead_state = v["finds_dead_state"] or f["finds_dead_state"]
    if not can_find_dead_state:
        # UNMEASURED is a real answer (L1.28a). Neither axis was ABLE to fail, so this run cannot
        # distinguish "vol is sufficient" from "the proxy cannot express a dead state".
        verdict = "UNDERPOWERED-no-axis-can-express-a-dead-state"
    elif v["finds_dead_state"] and not f["finds_dead_state"]:
        verdict = "REFUTED-vol-strictly-better"
    elif f["finds_dead_state"] and not v["finds_dead_state"]:
        verdict = "CONFIRMED-only-funding-finds-dead-state"
    elif v["mean_spread_bps"] >= f["mean_spread_bps"]:
        verdict = "REFUTED-vol-separates-at-least-as-well"
    else:
        verdict = "CONFIRMED-funding-separates-more"
    return {"axes": axes, "verdict": verdict, "instrument": instrument}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-bars", type=int, default=_MIN_BARS)
    ap.add_argument("--top-n", type=int, default=_TOP_N)
    ap.add_argument("--cost-bps", type=float, nargs="+", default=[0.0, 2.0, 6.0])
    args = ap.parse_args()

    close, funding, attrition = _load_panel(args.min_bars)
    if close.empty or funding.empty:
        print("UNMEASURED: no symbol cleared the depth floor -- falsifier cannot run")
        return 2

    # The cost is swept rather than asserted: the desk has no derived per-turn number for this
    # sleeve, so publish every rung and the breakeven instead of one figure (L1.51).
    runs: dict[str, Any] = {}
    for cost in args.cost_bps:
        carry, turnover = carry_sleeve_returns(funding, top_n=args.top_n, cost_bps_per_turn=cost)
        if len(carry) < 90:
            print(f"UNMEASURED: carry series only {len(carry)} days -- below the gate's 90-bar floor")
            return 2
        res = evaluate(carry, close, funding)
        # Q3 needs the whole panel, which evaluate() does not hold: the market-wide funding state,
        # unselected, is what regime_labels actually measures.
        unsel = funding.mean(axis=1).reindex(carry.index).dropna()
        res["instrument"]["unselected_share_non_positive"] = round(float((unsel <= 0).mean()), 4)
        res["mean_daily_turnover"] = turnover
        runs[f"{cost}bps"] = res

    out = {
        "panel": {"symbols": int(close.shape[1]), "days": len(carry),
                  "first": str(carry.index[0].date()), "last": str(carry.index[-1].date()),
                  "attrition": attrition, "top_n": args.top_n},
        "runs": runs,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2) + "\n")

    p = out["panel"]
    print(f"panel: {p['symbols']} symbols, {p['days']} days ({p['first']} -> {p['last']})")
    for tag, res in runs.items():
        i = res["instrument"]
        print(f"\n--- cost {tag}/turn (turnover {res['mean_daily_turnover']}/day) ---")
        print(f"  INSTRUMENT: non-positive days {i['share_days_non_positive']} | "
              f"corr(vol,level) {i['corr_vol_vs_level']} | "
              f"unselected non-positive {i['unselected_share_non_positive']}")
        for name, a in res["axes"].items():
            print(f"  {name}: eta^2={a['eta_squared']} spread={a['mean_spread_bps']}bps "
                  f"positive={a['n_groups_positive']}/{a['n_groups_present']} "
                  f"dead_state={a['finds_dead_state']}")
            for g, s in a["groups"].items():
                print(f"      {g:16s} n={s['n']:5d} mean={s['mean_bps']:8.4f}bps t={s['t_stat']:7.3f}")
        print(f"  VERDICT: {res['verdict']}")
    print(f"\nwrote {_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
