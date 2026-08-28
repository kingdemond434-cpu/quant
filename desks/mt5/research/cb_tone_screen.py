"""Screen: does BIS-corpus central-bank speech TONE precede the speaker's own currency?

MECHANISM UNDER TEST. A central banker's public language moves ahead of the policy it
describes. If hawkish language on day t carries information the FX market has not fully
priced, the speaker's currency should out-appreciate against USD over the following days.
The forced counterparty is anyone holding the currency's rate expectations wrong -- policy is
scheduled, dated and market-moving, which is why this axis was ranked above unscheduled
social-media text.

THIS IS A SCREEN. It sorts and reports; it applies NO threshold in either direction and has
no promotion authority (LAWS L1.60). The canonical ten gates decide.

AVAILABILITY. The BIS collects speeches with a publication delay, so the tone reading is NOT
assumed available on the speech date. Returns are measured from t+LAG trading days forward,
LAG defaulting to 2. A shorter lag would be a look-ahead claim this corpus cannot support.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
LAKE = BASE / "data" / "lake"
SERIES = BASE / "data" / "intelligence" / "central_banks" / "cb_tone_series.jsonl"

#: SEED, not a boundary: FRED daily FX series per currency, with the quote sense recorded.
#: `invert=True` means the series is quoted CCY-per-USD, so a rise is the currency WEAKENING.
PAIRS: dict[str, tuple[str, bool]] = {
    "AUD": ("fred_DEXUSAL.parquet", False),
    "EUR": ("fred_DEXUSEU.parquet", False),
    "NZD": ("fred_DEXUSNZ.parquet", False),
    "GBP": ("fred_DEXUSUK.parquet", False),
    "JPY": ("fred_DEXJPUS.parquet", True),
    "CAD": ("fred_DEXCAUS.parquet", True),
    "CHF": ("fred_DEXSZUS.parquet", True),
}


def load_prices(ccy: str) -> pd.Series | None:
    fname, invert = PAIRS[ccy]
    path = LAKE / fname
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    s = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna()
    s.index = pd.to_datetime(s.index, utc=True, errors="coerce")
    s = s[s.index.notna()].sort_index()
    return 1.0 / s if invert else s


def forward_returns(px: pd.Series, lag: int, horizon: int) -> pd.Series:
    """Log return from t+lag to t+lag+horizon, indexed by t. Trading-day offsets on the price
    index itself, so a weekend never silently consumes part of the window."""
    lp = np.log(px)
    fwd = lp.shift(-(lag + horizon)) - lp.shift(-lag)
    return fwd.dropna()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lag", type=int, default=2)
    ap.add_argument("--horizon", type=int, default=5)
    ap.add_argument("--out", default=str(BASE / "reports" / "cb_tone_screen.json"))
    args = ap.parse_args()

    rows = [json.loads(ln) for ln in SERIES.read_text().splitlines() if ln.strip()]
    tone: dict[str, dict[pd.Timestamp, float]] = defaultdict(dict)
    for r in rows:
        if r["net_tone"] is None:  # no directional language is not neutral language (L1.28a)
            continue
        tone[r["currency"]][pd.Timestamp(r["date"], tz="UTC")] = float(r["net_tone"])

    results = []
    pooled_h: list[float] = []
    pooled_d: list[float] = []
    for ccy in sorted(PAIRS):
        px = load_prices(ccy)
        if px is None or ccy not in tone:
            results.append({"currency": ccy, "status": "UNMEASURED", "reason":
                            "no price series" if px is None else "no tone readings"})
            continue
        fwd = forward_returns(px, args.lag, args.horizon)
        aligned = {d: fwd[d] for d in tone[ccy] if d in fwd.index}
        hawk = [v for d, v in aligned.items() if tone[ccy][d] > 0]
        dove = [v for d, v in aligned.items() if tone[ccy][d] < 0]
        pooled_h += hawk
        pooled_d += dove
        if len(hawk) < 20 or len(dove) < 20:
            results.append({"currency": ccy, "status": "INSUFFICIENT",
                            "n_hawk": len(hawk), "n_dove": len(dove)})
            continue
        h, d = np.array(hawk), np.array(dove)
        se = np.sqrt(h.var(ddof=1) / len(h) + d.var(ddof=1) / len(d))
        results.append({
            "currency": ccy, "status": "MEASURED",
            "n_hawk": len(h), "n_dove": len(d),
            "mean_hawk_bp": round(float(h.mean()) * 1e4, 2),
            "mean_dove_bp": round(float(d.mean()) * 1e4, 2),
            "spread_bp": round(float(h.mean() - d.mean()) * 1e4, 2),
            "t": round(float((h.mean() - d.mean()) / se), 3) if se else None,
        })

    out: dict[str, object] = {"lag_days": args.lag, "horizon_days": args.horizon,
                              "per_currency": results}
    if len(pooled_h) >= 20 and len(pooled_d) >= 20:
        h, d = np.array(pooled_h), np.array(pooled_d)
        se = np.sqrt(h.var(ddof=1) / len(h) + d.var(ddof=1) / len(d))
        out["pooled"] = {
            "n_hawk": len(h), "n_dove": len(d),
            "spread_bp": round(float(h.mean() - d.mean()) * 1e4, 2),
            "t": round(float((h.mean() - d.mean()) / se), 3) if se else None,
            "note": "currency-days are NOT independent -- overlapping horizons and correlated "
                    "USD legs. This t is a sorting number, never an admission statistic.",
        }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
