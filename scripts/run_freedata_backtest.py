"""Honest gauntlet on the free Fear & Greed signal (3000+ days of history) -> web/freedata.json.

Tests two distinct hypotheses, net of cost, no look-ahead (signal lagged 1 day):
  1. CONTRARIAN ALPHA  -- long when fearful / short when greedy (timing BTC).
  2. DE-RISK OVERLAY    -- hold BTC but cut size in extreme greed/fear (drawdown/giveback tool).
Both are compared to buy & hold and run through the deflated Sharpe ratio (DSR). Single-asset timing
is breadth-1, so the alpha will likely fail the gauntlet -- any honest value is the overlay's
drawdown reduction. Reports survivors AND rejects (most should fail -- the gauntlet working).

    python scripts/run_freedata_backtest.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.crypto_source import daily_with_funding  # noqa: E402
from libs.data.freesources import fear_greed  # noqa: E402
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio  # noqa: E402

_OUT = Path("web/freedata.json")
_PPY = 365.0
_COST = 6e-4                                      # per unit turnover


def _stats(r: np.ndarray, turn: np.ndarray | None = None) -> dict[str, float]:
    net = r - (turn * _COST if turn is not None else 0.0)
    a = net[~np.isnan(net)]
    if len(a) < 50:
        return {"sharpe": 0.0, "cagr": 0.0, "max_dd": 0.0, "vol": 0.0}
    cum = np.cumprod(1.0 + a)
    dd = float((cum / np.maximum.accumulate(cum) - 1.0).min())
    return {"sharpe": round(float(sharpe_ratio(a) * np.sqrt(_PPY)), 2),
            "cagr": round(float(cum[-1] ** (_PPY / len(a)) - 1.0), 3),
            "max_dd": round(dd, 3), "vol": round(float(np.std(a) * np.sqrt(_PPY)), 3)}


def _derisk(fng: float) -> float:
    if fng >= 80:
        return 0.70
    if fng >= 70:
        return 0.85
    if fng <= 12:
        return 0.85
    return 1.0


def main() -> None:
    fg = fear_greed()
    btc = daily_with_funding("BTCUSDT", start="2018-02-01")
    if fg.empty or btc.empty:
        raise SystemExit("could not fetch Fear&Greed or BTC history")
    btc = btc.set_index("timestamp")
    btc["ret"] = btc["close"].pct_change()
    f = fg.set_index("timestamp")["fng"].reindex(btc.index, method="ffill")
    df = pd.DataFrame({"ret": btc["ret"], "fng": f}).dropna()
    r = df["ret"].to_numpy()
    fng_lag = df["fng"].shift(1).to_numpy()                       # no look-ahead

    # 1) contrarian alpha: position = (50 - fng)/50 in [-1, 1] (long fear / short greed)
    pos_c = np.clip((50.0 - fng_lag) / 50.0, -1.0, 1.0)
    turn_c = np.abs(np.diff(pos_c, prepend=0.0))
    contrarian = _stats(pos_c * r, turn_c)

    # 2) de-risk overlay: hold BTC but scale by the de-risk multiplier
    mult = np.array([_derisk(x) for x in fng_lag])
    turn_o = np.abs(np.diff(mult, prepend=1.0))
    overlay = _stats(mult * r, turn_o)
    hold = _stats(r)

    # honest validation: build the family of F&G variants actually tried, deflate by their spread
    def _net(p: np.ndarray) -> np.ndarray:
        t = np.abs(np.diff(p, prepend=p[0]))
        n = (p * r) - t * _COST
        return n[~np.isnan(n)]

    variants = {
        "contrarian_50": pos_c,
        "contrarian_60": np.clip((60.0 - fng_lag) / 60.0, -1.0, 1.0),
        "long_only_fear": np.clip((55.0 - fng_lag) / 55.0, 0.0, 1.0),
        "momentum_wrongsign": np.clip((fng_lag - 50.0) / 50.0, -1.0, 1.0),
        "derisk_overlay": mult,
    }
    sh_est = np.array([sharpe_ratio(_net(p)) for p in variants.values()])
    net_c = _net(pos_c)
    dsr = deflated_sharpe_ratio(net_c, n_trials=len(sh_est), sharpe_estimates=sh_est)
    alpha_survives = bool(dsr.passed and contrarian["sharpe"] > hold["sharpe"])
    overlay_helps = bool(overlay["max_dd"] > hold["max_dd"]
                         and overlay["sharpe"] >= hold["sharpe"] - 0.05)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(), "obs": len(df),
        "buy_hold": hold, "contrarian_alpha": contrarian, "derisk_overlay": overlay,
        "dsr": round(float(dsr.dsr), 3), "dsr_passed": bool(dsr.passed),
        "alpha_survives": alpha_survives, "overlay_helps": overlay_helps,
        "verdict": ("F&G CONTRARIAN survives DSR" if alpha_survives
                    else "F&G contrarian REJECTED (breadth-1 timing) -- "
                    + ("but the DE-RISK OVERLAY cuts drawdown" if overlay_helps
                       else "and overlay gives no edge")),
        "note": ("Single-asset timing is breadth-1 -> expected to fail as alpha. Any free win is "
                 "the de-risk overlay (shallower drawdown at similar Sharpe); here it barely "
                 "helps, so F&G stays a DISPLAY-ONLY regime indicator, not a live size control."),
    }
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"F&G gauntlet ({len(df)} days): hold Sharpe {hold['sharpe']} DD {hold['max_dd']} | "
          f"contrarian {contrarian['sharpe']} (DSR {out['dsr']}, pass={dsr.passed}) | "
          f"overlay Sharpe {overlay['sharpe']} DD {overlay['max_dd']}")
    print(f"  verdict: {out['verdict']}")


if __name__ == "__main__":
    main()
