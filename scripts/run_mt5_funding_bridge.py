"""Funding-signal -> MT5 crypto-CFD bridge: research globally, execute natively on MT5.

Our best signal (Binance perpetual funding) cannot be *captured* on MT5 -- a CFD pays no perp
funding. But the funding extreme is also a PREDICTOR (crowded longs -> negative drift). The honest
question for the Python-brain / MT5-hands architecture: does the global funding
signal predict MT5 crypto-CFD *price* moves enough to trade the CFDs net of CFD spread AND daily
overnight financing (which you pay, with no funding income to offset it)?

Construction: dollar-neutral cross-sectional book over the MT5-tradeable crypto CFDs, long the
lowest-funding names / short the highest, inverse-vol, turnover band. Returns are PRICE-ONLY.
Reported: (a) gross price-only edge (is the signal predictive at all?), (b) a financing sensitivity
sweep (at what daily swap does it die?), and (c) the realistic-financing series through the full
gauntlet. No parameter mining; survivors reported straight.

    python scripts/run_mt5_funding_bridge.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.research.crossasset import xsec_signal_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("reports/mt5_funding_bridge")
_PPY = 365.0
_CFD_COST = 6.0e-4          # per-side MT5 crypto-CFD spread/slippage
_REALISTIC_FIN = 5.0e-4     # realistic daily CFD overnight financing (per side, on gross)
_FIN_SWEEP = (0.0, 2.0e-4, 5.0e-4, 8.0e-4)
_MT5_CFDS = ("BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD", "BCHUSD", "ADAUSD", "DOTUSD", "SOLUSD")
_MIN_NAMES = 4
_FAIL = ["funding signal does not transfer to CFD price", "CFD financing exceeds edge",
         "too few CFD names for dispersion", "correlated crypto crash", "edge decay"]


def _perp_for(cfd: str) -> str:
    return cfd[:-3] + "USDT"          # BTCUSD -> BTCUSDT


def _panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    """MT5 CFD close panel + matching Binance perp funding panel, date-aligned."""
    lake = ParquetLake("data/lake")
    closes, fundings = {}, {}
    for cfd in _MT5_CFDS:
        perp = _perp_for(cfd)
        if not (_CRYPTO / cfd / Timeframe.D1.value).exists():
            continue
        if not (_CRYPTO / perp / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=cfd, asset_class=AssetClass.CRYPTO,
                                           description=cfd))
        register_instrument(InstrumentSpec(symbol=perp, asset_class=AssetClass.CRYPTO,
                                           description=perp))
        cdf = lake.read_bars(Layer.BRONZE, cfd, Timeframe.D1).set_index("timestamp")
        pdf = lake.read_bars(Layer.BRONZE, perp, Timeframe.D1).set_index("timestamp")
        if "funding" not in pdf.columns or len(cdf) < 250:
            continue
        closes[cfd] = cdf["close"]
        fundings[cfd] = pdf["funding"]      # key by CFD symbol (the executable instrument)
    close = pd.DataFrame(closes).sort_index()
    funding = pd.DataFrame(fundings).reindex(close.index)
    return close, funding


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def main() -> None:
    close, funding = _panels()
    if close.shape[1] < _MIN_NAMES:
        raise SystemExit(f"need >={_MIN_NAMES} MT5 crypto CFDs with matching perp funding; "
                         "run scripts/ingest_multiasset.py and ingest_crypto.py --universe liquid")
    print(f"MT5 crypto-CFD panel: {close.shape[1]} names x {close.shape[0]} days "
          f"({close.index[0].date()}..{close.index[-1].date()})  CFDs={list(close.columns)}")

    signal = funding.rolling(7).mean()          # lagged inside xsec_signal_returns
    cost = dict.fromkeys(close.columns, _CFD_COST)

    # (a) gross predictive edge + (b) financing sweep
    sweep = []
    for fin in _FIN_SWEEP:
        hc = dict.fromkeys(close.columns, fin) if fin else None
        r = xsec_signal_returns(close, signal, cost, q=0.3, band=0.02,
                                min_names=_MIN_NAMES, long_high=False, hold_cost=hc)
        sweep.append({"daily_financing_bps": round(fin * 1e4, 1), "ann_sharpe": _ann(r)})

    # (c) realistic-financing variants -> full gauntlet
    variants = []
    for lb in (3, 7, 14):
        sig = funding.rolling(lb).mean()
        hc = dict.fromkeys(close.columns, _REALISTIC_FIN)
        r = xsec_signal_returns(close, sig, cost, q=0.3, band=0.02,
                                min_names=_MIN_NAMES, long_high=False, hold_cost=hc)
        variants.append((f"bridge_lb{lb}_fin5bp", r))

    min_len = min(len(r) for _, r in variants)
    matrix = np.column_stack([r[-min_len:] for _, r in variants])
    sharpes = np.array([sharpe_ratio(r[r != 0.0]) for _, r in variants], dtype="float64")
    pbo, rc = campaign_pbo_rc(matrix)

    survivors, results = 0, []
    for (name, r), spr in zip(variants, sharpes, strict=True):
        active = r[r != 0.0]
        v = (validate(active, hypothesis=Hypothesis(
            family=Family.CARRY, subtype=name, symbol="MT5_CRYPTO_CFD", params={},
            mechanism=MechanismType.RISK_PREMIUM,
            edge_source="Binance funding signal -> MT5 crypto-CFD price (financed)",
            failure_modes=_FAIL), n_trials=len(variants), sharpe_estimates=sharpes,
            returns_matrix=matrix, pbo=pbo, rc=rc) if len(active) >= 250 else None)
        survived = bool(v.survived) if v else False
        survivors += int(survived)
        gates = v.gates if v else {}
        results.append({"variant": name, "days": len(active),
                        "ann_sharpe": round(float(spr) * np.sqrt(_PPY), 2), "survived": survived,
                        "gates_passed": f"{sum(gates.values())}/{len(gates)}" if gates else "n<250",
                        "reason": v.rejection_reason if v else "n<250"})

    _OUT.mkdir(parents=True, exist_ok=True)
    payload = {"cfd_names": close.shape[1], "days": close.shape[0],
               "financing_sweep": sweep, "survivors": survivors, "variants": results}
    (_OUT / "report.json").write_text(json.dumps(payload, indent=2), "utf-8")

    print("\nfinancing sensitivity (gross -> realistic):")
    for s in sweep:
        print(f"  swap={s['daily_financing_bps']:4}bps/day  ann_sharpe~{s['ann_sharpe']}")
    print(f"\n[mt5-funding-bridge] tested={len(variants)} survivors={survivors}")
    for r in results:
        print(f"  {r['variant']:20} days={r['days']:4} ann_sharpe~{r['ann_sharpe']:6} "
              f"gates={r['gates_passed']:5} survived={r['survived']}  {r['reason']}")
    if survivors == 0:
        print("\nZERO survivors: funding edge does not survive MT5 CFD execution (honest).")


if __name__ == "__main__":
    main()
