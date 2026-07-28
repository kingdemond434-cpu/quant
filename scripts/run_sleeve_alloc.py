"""Cross-sleeve allocation: HRP vs equal-weight, head-to-head, GATED -> data/sleeve_weights.json.

The audit's one fair point: the live target blends sleeves equally (w/n), which lets a higher-vol
sleeve dominate portfolio RISK. This computes Hierarchical Risk Parity (robust -- no covariance
inversion, unlike MVO) on the sleeve covariance and compares HRP vs inverse-vol vs equal on history.
It only writes HRP weights if HRP BEATS equal by a margin -- otherwise it keeps equal-weight (no
faith-based switch; the mandate forbids deploying an in-sample 'improvement' that isn't real).
run_crypto_target reads the chosen weights. On the flywheel. -> web/sleeve_alloc.json (dashboard).

    python scripts/run_sleeve_alloc.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.data.universe import RESEARCH_TOP_N
from libs.portfolio.hrp import hrp_weights
from libs.research.crossasset import xsec_momentum_returns
from libs.research.crypto_sleeves import basis_carry_returns, taker_flow_returns
from libs.research.crypto_xsec import adv_tier_cost, xsec_funding_returns
from libs.validation.dsr import sharpe_ratio

_OUT = Path("data/sleeve_weights.json")
_WEB = Path("web/sleeve_alloc.json")
_CRYPTO = Path("data/lake/bronze/crypto")
_PPY = 365.0
_MARGIN = 0.10                                   # HRP must beat equal Sharpe by this to be adopted


def _stats(r: np.ndarray) -> dict[str, float]:
    a = r[r != 0.0]
    if len(a) < 30:
        return {"sharpe": 0.0, "vol": 0.0, "max_dd": 0.0}
    cum = np.cumprod(1.0 + a)
    dd = float((cum / np.maximum.accumulate(cum) - 1.0).min())
    return {"sharpe": round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2),
            "vol": round(float(np.std(a) * np.sqrt(_PPY)), 3), "max_dd": round(dd, 3)}


def main() -> None:
    lake = ParquetLake("data/lake")
    closes, fundings, bases, takers, adv = {}, {}, {}, {}, {}
    for s in list_liquid_perps(top_n=RESEARCH_TOP_N):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or len(df) < 250:
            continue
        closes[s], fundings[s] = df["close"], df["funding"]
        adv[s] = float((df["close"] * df["volume"]).tail(180).mean())
        if "basis" in df.columns:
            bases[s] = df["basis"]
        if "taker_buy_frac" in df.columns:
            takers[s] = df["taker_buy_frac"]
    close = pd.DataFrame(closes).sort_index()
    if close.shape[1] < 12:
        raise SystemExit("need a liquid perp panel")
    funding = pd.DataFrame(fundings).reindex(close.index)
    basis = pd.DataFrame(bases).reindex(close.index) if bases else pd.DataFrame()
    taker = pd.DataFrame(takers).reindex(close.index) if takers else pd.DataFrame()
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}

    sleeves: dict[str, np.ndarray] = {
        "funding": xsec_funding_returns(close, funding, adv, lookback=7, q=0.2, band=0.02),
        "momentum": xsec_momentum_returns(close, cost, lookback=20, q=0.3, band=0.05),
    }
    if not basis.empty and basis.shape[1] >= 12:
        sleeves["basis"] = basis_carry_returns(close[basis.columns], funding[basis.columns],
                                               basis, adv, lookback=3, q=0.2, band=0.02)
    if not taker.empty and taker.shape[1] >= 12:
        sleeves["taker"] = taker_flow_returns(close[taker.columns], funding[taker.columns],
                                              taker, adv, lookback=5, q=0.2, band=0.02)

    names = list(sleeves)
    n = min(len(v) for v in sleeves.values())
    matrix = np.column_stack([sleeves[k][-n:] for k in names])
    cov = np.cov(matrix.T)
    hrp = np.asarray(hrp_weights(cov), dtype=float)
    hrp = hrp / hrp.sum() if hrp.sum() > 0 else np.ones(len(names)) / len(names)
    equal = np.ones(len(names)) / len(names)
    vols = matrix.std(axis=0)
    invvol = (1.0 / vols) / (1.0 / vols).sum() if (vols > 0).all() else equal

    s_eq, s_iv, s_hrp = (_stats(matrix @ equal), _stats(matrix @ invvol), _stats(matrix @ hrp))
    use_hrp = s_hrp["sharpe"] >= s_eq["sharpe"] + _MARGIN
    chosen_w = hrp if use_hrp else equal
    scheme = "hrp" if use_hrp else "equal"

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(), "scheme": scheme,
        "weights": {k: round(float(w), 4) for k, w in zip(names, chosen_w, strict=True)},
    }, indent=2), "utf-8")
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(), "obs": int(n), "sleeves": names,
        "equal": s_eq, "inverse_vol": s_iv, "hrp": s_hrp,
        "hrp_weights": {k: round(float(w), 4) for k, w in zip(names, hrp, strict=True)},
        "chosen": scheme, "margin_required": _MARGIN,
        "sharpe_gain_hrp_vs_equal": round(s_hrp["sharpe"] - s_eq["sharpe"], 2),
        "note": ("HRP adopted ONLY if it beats equal Sharpe by >= margin (else equal stays). HRP "
                 "is robust risk-parity (no covariance inversion). In-sample comparison; the live "
                 "switch is conservative on purpose; equal-weight is the safe default."),
    }, indent=2), "utf-8")
    print(f"sleeve alloc ({n}d): equal Sh {s_eq['sharpe']} | inv-vol {s_iv['sharpe']} | "
          f"HRP {s_hrp['sharpe']} -> CHOSEN: {scheme.upper()} "
          f"(gain {s_hrp['sharpe'] - s_eq['sharpe']:+.2f}, need +{_MARGIN})")


if __name__ == "__main__":
    main()
