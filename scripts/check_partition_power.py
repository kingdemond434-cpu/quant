#!/usr/bin/env python3
"""PARTITION-POWER FENCE (L1.63) -- can the desk's robustness certificates ever say NO?

Three wired gates certify "regime robust" by requiring an edge to be net-positive in >= K groups
of a partition: ``libs/autodiscovery/regime.regime_robust`` (blocks REGISTRY promotion),
``libs/risk/sleeve_allocation`` min_regimes_positive (a sizing ceiling), and
``scripts/check_promotion_gate`` two_regimes (LIVE at 15% of book). All three partition by
realized-VOLATILITY terciles. This fence measures, on the desk's own data, whether that partition
-- and every other axis on the roster -- is CAPABLE of producing the failing group it claims to
test for. See ``libs/validation/partition_power`` for why no existing instrument can ask this.

STATUSES, and none of them may read clean on an empty measurement set (L1.28a):
  OK         (exit 0) -- every graded partition is able to fail an edge.
  PARTIAL    (exit 0) -- some partitions ungraded, none welded. Coverage is a RATCHET (L1.0)
                         whose gap is the work queue; a fence red on its first day gets switched
                         off (L1.43).
  WELDED     (exit 2) -- at least one certificate could not have failed the edge it certifies.
  UNMEASURED (exit 2) -- no panel, or no partition reached a gradeable size.

THE REPAIR IS UPWARD (L1.49). A WELDED reading never justifies deleting a gate or lowering a bar;
it justifies giving the certificate an axis that can go negative, or recording out loud that it
carries no information for this edge.

    python scripts/check_partition_power.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.autodiscovery.regime import vol_regime_labels  # noqa: E402
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.crypto_regime import regime_labels  # noqa: E402
from libs.validation.partition_power import (  # noqa: E402
    UNLABELLED,
    PartitionVerdict,
    partition_power,
    summarise,
)

_OUT = _ROOT / "data" / "partition_power.json"
_PASSING = frozenset({"OK", "PARTIAL"})

#: a symbol needs this many daily bars to join the panel
_MIN_BARS = 500
#: the live carry sleeve's basket size (run_cashcarry_executor `top`)
_TOP_N = 10
#: charged on the changed fraction of the basket, both legs -- the FIRST cost on this series
_COST_BPS_PER_TURN = 6.0


def load_panel(root: Path, min_bars: int = _MIN_BARS) -> tuple[pd.DataFrame, pd.DataFrame,
                                                               dict[str, int]]:
    """(close, funding) wide frames + attrition. Every skip is counted (L1.60)."""
    att = {"attempted": 0, "no_parts": 0, "unreadable": 0, "no_columns": 0, "too_short": 0,
           "kept": 0}
    closes: dict[str, pd.Series] = {}
    fundings: dict[str, pd.Series] = {}
    lake = root / "data/lake/bronze/crypto"
    if not lake.is_dir():
        return pd.DataFrame(), pd.DataFrame(), att
    for sym_dir in sorted(lake.iterdir()):
        if not sym_dir.is_dir():
            continue
        att["attempted"] += 1
        parts = sorted(glob.glob(str(sym_dir / "D1/**/*.parquet"), recursive=True))
        if not parts:
            att["no_parts"] += 1
            continue
        try:
            d = pd.concat([pd.read_parquet(p) for p in parts])
        except (OSError, ValueError):
            att["unreadable"] += 1
            continue
        if "funding" not in d.columns or "close" not in d.columns:
            att["no_columns"] += 1
            continue
        d = d.dropna(subset=["close"]).drop_duplicates(subset=["timestamp"])
        d = d.set_index(pd.to_datetime(d["timestamp"], utc=True).dt.normalize()).sort_index()
        if len(d) < min_bars:
            att["too_short"] += 1
            continue
        closes[sym_dir.name] = d["close"]
        fundings[sym_dir.name] = d["funding"]
        att["kept"] += 1
    return pd.DataFrame(closes).sort_index(), pd.DataFrame(fundings).sort_index(), att


def carry_sleeve(funding: pd.DataFrame, *, top_n: int = _TOP_N,
                 cost_bps_per_turn: float = _COST_BPS_PER_TURN) -> pd.Series:
    """Delta-neutral carry sleeve: daily top-N by TRAILING funding, net of turnover cost.

    Selection uses funding known strictly before the harvest day, so no future funding picks the
    basket. This is the desk's only surviving edge family, which is why it is the series the
    robustness certificates are graded against.
    """
    signal = funding.rolling(7, min_periods=3).mean().shift(1)
    out: list[float] = []
    idx: list[pd.Timestamp] = []
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
        out.append(float(realized.mean()) - turnover * 2.0 * cost_bps_per_turn * 1e-4)
        idx.append(day)
    return pd.Series(out, index=pd.DatetimeIndex(idx), name="carry")


def build_partitions(carry: pd.Series, close: pd.DataFrame,
                     funding: pd.DataFrame) -> dict[str, np.ndarray]:
    """The roster: every axis a robustness certificate on this desk does or could partition by."""
    r = carry.to_numpy(dtype="float64")

    # WIRED -- exactly what regime_robust / min_regimes_positive / two_regimes use.
    vol = np.array([f"vol_{x}" if x >= 0 else UNLABELLED for x in vol_regime_labels(r)])

    # BUILT BUT WIRED INTO NO GATE -- libs/research/crypto_regime.regime_labels.
    lab = regime_labels(close, funding).reindex(carry.index)
    fund = lab["funding"].fillna(UNLABELLED).to_numpy().astype(str)
    trend = lab["trend"].fillna(UNLABELLED).to_numpy().astype(str)

    # NOT BUILT ANYWHERE -- how many names are selectable at all. Added because the falsifier that
    # produced this module measured selection, not market state, as what absorbs a funding drought.
    sig = funding.rolling(7, min_periods=3).mean().shift(1)
    live = sig.notna().sum(axis=1).reindex(carry.index)
    frac = (sig > 0).sum(axis=1).reindex(carry.index) / live.replace(0, np.nan)
    if frac.notna().sum() >= 3:
        q1, q2 = frac.quantile([1 / 3, 2 / 3])
        breadth = np.where(frac.isna(), UNLABELLED,
                           np.where(frac <= q1, "breadth_low",
                                    np.where(frac <= q2, "breadth_mid", "breadth_high")))
    else:
        breadth = np.full(len(r), UNLABELLED)

    return {"vol_terciles_WIRED": vol, "funding_state": fund, "trend_state": trend,
            "funding_breadth": breadth}


def build(root: Path | None = None) -> dict[str, Any]:
    r = root or _ROOT
    close, funding, att = load_panel(r)
    if close.empty or funding.empty:
        return {"generated_at": datetime.now(UTC).isoformat(), "status": "UNMEASURED",
                "n_partitions": 0, "n_welded": 0, "n_discriminating": 0, "n_unmeasured": 0,
                "panel": {"attrition": att, "symbols": 0, "days": 0},
                "why": "no symbol cleared the depth floor -- no panel, so no verdict (L1.28a)",
                "next_action": "check data/lake/bronze/crypto D1 coverage", "partitions": []}
    carry = carry_sleeve(funding)
    if len(carry) < 90:
        return {"generated_at": datetime.now(UTC).isoformat(), "status": "UNMEASURED",
                "n_partitions": 0, "n_welded": 0, "n_discriminating": 0, "n_unmeasured": 0,
                "panel": {"attrition": att, "symbols": int(close.shape[1]), "days": len(carry)},
                "why": (f"carry series is {len(carry)} days, below the gate's own 90-bar floor -- "
                        "cannot grade a partition on it"),
                "next_action": "extend the panel", "partitions": []}

    verdicts: list[PartitionVerdict] = [
        partition_power(carry.to_numpy(dtype="float64"), labels, name=name)
        for name, labels in build_partitions(carry, close, funding).items()
    ]
    rep = summarise(verdicts)
    rep["generated_at"] = datetime.now(UTC).isoformat()
    rep["panel"] = {"attrition": att, "symbols": int(close.shape[1]), "days": len(carry),
                    "first": str(carry.index[0].date()), "last": str(carry.index[-1].date()),
                    "top_n": _TOP_N, "cost_bps_per_turn": _COST_BPS_PER_TURN}
    return rep


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        p = rep.get("panel", {})
        print(f"partition power (L1.63): {rep['status']} -- {rep['n_welded']} welded / "
              f"{rep['n_discriminating']} discriminating of {rep['n_partitions']} "
              f"({p.get('symbols', 0)} symbols, {p.get('days', 0)} days)")
        for v in rep.get("partitions", []):
            mark = {"WELDED": "WELDED    ", "DISCRIMINATING": "DISCRIMIN.",
                    "UNMEASURED": "UNMEASURED"}[v["status"]]
            print(f"  {mark} {v['name']}: {v['n_groups_positive']}/{v['n_groups_graded']} groups "
                  f"positive, can_fail={v['can_fail']}")
        print(f"  why:  {rep['why']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to L1.57: the roster size is this fence's denominator, so a run that graded nothing
    # refuses its own pass rather than reporting a clean board.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_partitions"],
                      of="robustness partitions", fence="check_partition_power.py")


if __name__ == "__main__":
    raise SystemExit(main())
