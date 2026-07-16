"""90-day forward shadow of the cash-and-carry strategy -- its honest validation path (paper).

Freezes the strategy and tracks realized cash-carry returns AFTER a freeze date, reporting forward
Sharpe vs the backtest. Cash-and-carry cannot run on the futures testnet (no spot leg), so this
forward shadow IS its certification route until a live spot+perp account is opened. The strategy is
the SAME function used in the backtest (apples-to-apples). Writes web/cashcarry_shadow.json.

    python scripts/run_cashcarry_shadow.py
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
from libs.research.cashcarry import cashcarry_returns
from libs.validation.dsr import sharpe_ratio
from libs.validation.forward_stats import autocorr_factor, nw_tstat

_CRYPTO = Path("data/lake/bronze/crypto")
_OUT = Path("web/cashcarry_shadow.json")
_STATE = Path("data/cashcarry_shadow_state.json")
_PPY = 365.0


def _panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    lake = ParquetLake("data/lake")
    fundings, bases = {}, {}
    for s in list_liquid_perps(top_n=120):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or "basis" not in df.columns or len(df) < 250:
            continue
        fundings[s] = df["funding"]
        bases[s] = df["basis"]
    f = pd.DataFrame(fundings).sort_index()
    return f, pd.DataFrame(bases).reindex(f.index)


def _ann(r: np.ndarray) -> float:
    a = r[r != 0.0]
    return round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2) if len(a) > 5 else 0.0


def main() -> None:
    funding, basis = _panels()
    if funding.shape[1] < 12:
        raise SystemExit("need a liquid perp panel with basis")
    r = cashcarry_returns(funding, basis)
    dates = pd.to_datetime(funding.index)

    st = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    if "shadow_start" not in st:
        st["shadow_start"] = datetime.now(tz=UTC).date().isoformat()
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(st), "utf-8")
    start = pd.Timestamp(st["shadow_start"], tz="UTC")
    fwd_mask = np.asarray(dates >= start)
    fwd, bt = r[fwd_mask], r[~fwd_mask]
    fwd_days = int((dates[fwd_mask].max() - start).days) if fwd_mask.any() else 0
    fwd_active = fwd[fwd != 0.0]

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "strategy": "cash_and_carry (long spot + short perp)",
        "shadow_start": st["shadow_start"],
        "backtest_ann_sharpe": _ann(bt),
        "forward_ann_sharpe": _ann(fwd),
        "forward_days": fwd_days,
        "forward_cum_return": round(float(np.prod(1.0 + fwd_active) - 1.0), 4) if len(fwd_active)
        else 0.0,
        "target": 1.5,
        "execution": "shadow only -- futures testnet has no spot; live needs a spot+perp account.",
    }
    # adaptive promotion window (live_deployment_policy v2, 2026-07-12 external review):
    # FAST-TRACK at >=40d needs ALL of (a) NEWEY-WEST corrected t >= 1.65 -- the naive
    # Sharpe*sqrt(d/365) assumes IID daily returns and funding is sticky, so the naive t
    # overstates significance exactly when N is small; (b) fwd >= 0.5x backtest; (c) >=1
    # REGIME EVENT inside the window (an aggregate funding-inversion day or a basis-
    # dislocation day) -- 40 calm days test a market mood, not an edge. Carry is the
    # PRE-REGISTERED PRIMARY hypothesis (registered alone, before any cohort) -> exempt
    # from the Holm cohort correction that later candidates carry.
    fs, bs = out["forward_ann_sharpe"], out["backtest_ann_sharpe"]
    tstat = round(float(fs) * (fwd_days / 365.0) ** 0.5, 2) if fs else 0.0
    # NW t on ALL forward days (round-2 review: dropping zero days truncates the return
    # distribution -- a day the live strategy earned nothing IS evidence, not missing data)
    t_nw = nw_tstat(fwd) if len(fwd) >= 5 else 0.0
    # inversion day = even the TOP-20 funding names average <=0 (true carry famine for the
    # harvestable set -- broad-panel mean is <=0 on most days and would gate nothing)
    top_f = funding.apply(lambda row: row.nlargest(20).mean(), axis=1)
    mean_b = basis.mean(axis=1)
    b_sd = float(mean_b[~fwd_mask].std()) or 1e9
    inv_days = int((top_f[fwd_mask] <= 0).sum())
    dis_days = int((mean_b[fwd_mask].abs() > 3.0 * b_sd).sum())
    events = inv_days + dis_days
    # REGIME EVIDENCE v2 (round-2 review: discrete crisis events are rare enough to make the
    # fast-track a dead letter -- consensus fix): the window qualifies via an EVENT OR via
    # funding-rate VARIANCE >= the 25th percentile of the backtest's rolling-40d distribution
    # (proves the window was not in the calmest quartile of history; continuous, not binary).
    bt_roll_sd = top_f[~fwd_mask].rolling(40).std().dropna()
    vol_bar = float(bt_roll_sd.quantile(0.25)) if len(bt_roll_sd) > 50 else 0.0
    fwd_vol = float(top_f[fwd_mask].std()) if int(fwd_mask.sum()) > 5 else 0.0
    regime_ok = events >= 1 or (vol_bar > 0.0 and fwd_vol >= vol_bar)
    ft_ok = fwd_days >= 40 and t_nw >= 1.65 and fs >= 0.5 * bs and regime_ok
    out["forward_tstat_naive"] = tstat
    out["forward_tstat"] = t_nw                       # Newey-West corrected -- the binding number
    fac = autocorr_factor(np.asarray(fwd)) if len(fwd) >= 20 else 1.0
    out["autocorr"] = {"factor": round(fac, 2), "clamped_at_max": fac >= 5.0}
    # clamped_at_max=True means true persistence may EXCEED the correction -- treat the
    # t-stat as an upper bound that cycle, never as exact (round-2/3 review)
    out["regime_events"] = {"inversion_days": inv_days, "basis_dislocation_days": dis_days}
    out["funding_vol"] = {"fwd": round(fwd_vol, 6), "bar_25pct_bt": round(vol_bar, 6),
                          "regime_ok": regime_ok}
    out["multiplicity"] = ("pre-registered PRIMARY hypothesis (shadow frozen before any cohort) "
                           "-> Holm-exempt; cohort candidates use forward_stats.holm_bar over ALL "
                           "trailing-180d forward entrants INCLUDING killed ones (no attrition)")
    out["fast_track"] = (
        "ELIGIBLE (>=40d + NW-t>=1.65 + fwd>=0.5xbt + regime evidence) -> live-promotable" if ft_ok
        else (f"day {fwd_days}/40 min; NW-t={t_nw} (naive {tstat}); regime evidence "
              f"{'OK' if regime_ok else 'PENDING'} (events {events}, funding-vol "
              f"{round(fwd_vol, 5)} vs bar {round(vol_bar, 5)})"))
    out["verdict"] = (f"forward day {fwd_days} (fast-track 40d / standard 90d); NW t-stat {t_nw} "
                      f"(naive {tstat}), regime evidence {'OK' if regime_ok else 'pending'}. "
                      f"Backtest Sharpe {bs} -- must hold forward before any capital.")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"cash-carry shadow: backtest {out['backtest_ann_sharpe']} | forward "
          f"{out['forward_ann_sharpe']} ({fwd_days}/90d) since {st['shadow_start']}")


if __name__ == "__main__":
    main()
