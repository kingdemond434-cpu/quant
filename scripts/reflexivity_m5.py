"""M5 REFLEXIVITY ENGINE -- the feedback-loop regime measure (mechanism graph M5).

The desk already collects every INPUT to the crypto feedback loop (price, OI, funding,
liquidations) but has never modelled the LOOP itself. Note the question is deliberately NOT
"do liquidations predict price" -- that was tested and is weak. It is:

    IS THE FEEDBACK COEFFICIENT RISING?

Mechanism:  price move -> leverage responds (OI chases) -> forced liquidation -> larger price move

REFLEXIVITY COEFFICIENT: rolling beta of dOI on dPrice. When positive and large, leverage CHASES
price (self-reinforcing = fragile, crash-prone). When negative, leverage FADES price
(mean-reverting,
stabilising). This is a REGIME property, not a directional signal -- so it is tested against forward
REALISED VOLATILITY and forward DRAWDOWN, not against forward return direction.

That framing matters: a regime measure that predicts vol/tail-risk is usable for SIZING (the desk's
log-wealth objective cares about drawdown), even if it says nothing about direction.

Free Binance OI history (openInterestHist, 500 bars). Stage-A, zero promotion authority.
Run from repo root.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

PERIOD, LIMIT, WIN = "4h", 500, 30
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def _get(u, t=40):
    return json.loads(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
        )
        .read()
        .decode()
    )


def oi_hist(sym):
    d = _get(
        f"https://fapi.binance.com/futures/data/openInterestHist?symbol={sym}"
        f"&period={PERIOD}&limit={LIMIT}"
    )
    return (
        {int(x["timestamp"]): float(x["sumOpenInterest"]) for x in d} if isinstance(d, list) else {}
    )


def klines(sym):
    d = _get(
        f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval={PERIOD}&limit={LIMIT}"
    )
    return {int(r[0]): (float(r[4]), float(r[2]), float(r[3])) for r in d}


def main() -> None:
    print("=== M5 REFLEXIVITY: is the feedback coefficient rising? ===")
    print("    reflexivity = rolling beta(dOI, dPrice). >0 leverage CHASES price (fragile);")
    print("    <0 leverage FADES price (stabilising). Tested vs forward VOL and DRAWDOWN.\n")
    out = []
    for sym in SYMS:
        try:
            oi, kl = oi_hist(sym), klines(sym)
        except Exception as e:
            print(f"{sym}: DATA-BLOCKED ({type(e).__name__})")
            continue
        ts = sorted(set(oi) & set(kl))
        if len(ts) < 150:
            print(f"{sym}: thin ({len(ts)})")
            continue
        o = np.array([oi[t] for t in ts])
        c = np.array([kl[t][0] for t in ts])
        np.array([kl[t][1] for t in ts])
        np.array([kl[t][2] for t in ts])
        dp = np.zeros(len(c))
        dp[1:] = c[1:] / c[:-1] - 1.0
        do = np.zeros(len(o))
        do[1:] = o[1:] / o[:-1] - 1.0

        # rolling reflexivity beta
        refl = np.zeros(len(c))
        for i in range(WIN, len(c)):
            x, y = dp[i - WIN : i], do[i - WIN : i]
            v = x.var()
            refl[i] = float(((x - x.mean()) * (y - y.mean())).mean() / v) if v > 1e-12 else 0.0

        # forward targets: realised vol and max drawdown over next 12 bars (2 days)
        H = 12
        fvol = np.full(len(c), np.nan)
        fdd = np.full(len(c), np.nan)
        for i in range(len(c) - H):
            seg = dp[i + 1 : i + 1 + H]
            fvol[i] = seg.std()
            path = np.cumprod(1 + seg)
            fdd[i] = float((path / np.maximum.accumulate(path) - 1).min())
        m = ~np.isnan(fvol)
        m[:WIN] = False
        r_, v_, d_ = refl[m], fvol[m], fdd[m]
        ic_v = float(np.corrcoef(r_, v_)[0, 1]) if r_.std() and v_.std() else 0.0
        ic_d = float(np.corrcoef(r_, d_)[0, 1]) if r_.std() and d_.std() else 0.0
        n = len(r_)
        t_v = ic_v * np.sqrt(max(1, n / H - 2)) / np.sqrt(max(1e-9, 1 - ic_v**2))
        t_d = ic_d * np.sqrt(max(1, n / H - 2)) / np.sqrt(max(1e-9, 1 - ic_d**2))

        # tercile check: does the top-reflexivity regime actually have worse tails?
        q = np.argsort(r_)
        k = max(5, len(r_) // 3)
        hi_v, lo_v = v_[q[-k:]].mean(), v_[q[:k]].mean()
        hi_d, lo_d = d_[q[-k:]].mean(), d_[q[:k]].mean()

        # and the honest control: is it just a direction signal in disguise?
        np.roll(dp, -1)[m]
        scr = stage_a_screen(refl[m], dp[m], name=f"reflexivity_{sym}", zwin=20)

        print(f"{sym}  n={n}  current reflexivity beta {refl[-1]:+.3f}")
        print(
            f"   -> forward VOL      IC {ic_v:+.4f} (t {t_v:+.2f}) | "
            f"high-refl vol {hi_v * 100:.3f}% vs low {lo_v * 100:.3f}%  "
            f"ratio {hi_v / max(lo_v, 1e-9):.2f}x"
        )
        print(
            f"   -> forward DRAWDOWN IC {ic_d:+.4f} (t {t_d:+.2f}) | "
            f"high-refl dd {hi_d * 100:+.3f}% vs low {lo_d * 100:+.3f}%"
        )
        print(
            f"   -> direction control (is it secretly a return signal?): "
            f"IC {scr.get('ic'):+.4f} {scr['verdict']}\n"
        )
        out.append(
            {
                "sym": sym,
                "n": n,
                "reflexivity_now": round(float(refl[-1]), 4),
                "ic_vol": round(ic_v, 4),
                "t_vol": round(float(t_v), 2),
                "ic_dd": round(ic_d, 4),
                "t_dd": round(float(t_d), 2),
                "vol_ratio_hi_lo": round(float(hi_v / max(lo_v, 1e-9)), 3),
                "dd_hi": round(float(hi_d), 5),
                "dd_lo": round(float(lo_d), 5),
                "direction_ic": scr.get("ic"),
                "direction_verdict": scr["verdict"],
            }
        )

    if len(out) >= 2:
        tv = np.array([o["t_vol"] for o in out])
        td = np.array([o["t_dd"] for o in out])
        print(
            f"POOLED across {len(out)} symbols: mean t(vol) {tv.mean():+.2f} | "
            f"mean t(drawdown) {td.mean():+.2f}"
        )
        print(
            f"  consistent sign vol {int((np.sign(tv) == np.sign(tv[0])).sum())}/{len(tv)} | "
            f"dd {int((np.sign(td) == np.sign(td[0])).sum())}/{len(td)}"
        )
    Path("data/reflexivity_m5.json").write_text(
        json.dumps(
            {"updated": datetime.now(tz=UTC).isoformat(), "window": WIN, "results": out}, indent=1
        ),
        "utf-8",
    )


if __name__ == "__main__":
    main()
