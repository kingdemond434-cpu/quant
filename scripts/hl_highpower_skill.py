"""HIGH-POWER long-term skill test. Prior run: n=229 -> SE(rho)~0.066, could only detect rho>=0.13,
95% CI [-0.148,+0.110] -- so WEAK persistence (rho 0.05-0.11) was NOT excluded. Principal correctly
challenged the power. Fix: scale the cohort ~10x (probe deep into the 41k leaderboard, lower the
accountValue floor) -> target n~2500, SE~0.020, detects rho>=0.045.
Same design otherwise: multi-year on-chain records, own-curve 60/40 formation/holding split,
pnlHistory normalised by contemporaneous accountValue, risk-adjusted selection criteria.
Reports explicit CIs and minimum-detectable-effect so the conclusion is power-aware."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

INFO = "https://api.hyperliquid.xyz/info"
LB = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
N_TRY = 2600
MIN_PTS = 60
MIN_SPAN = 200


def _get(u, t=180):
    return urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
    ).read()


def _post(p, t=20):
    r = urllib.request.Request(
        INFO,
        data=json.dumps(p).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "q/1.0"},
    )
    with urllib.request.urlopen(r, timeout=t) as x:
        return json.loads(x.read().decode())


rows = json.loads(_get(LB))
rows = rows.get("leaderboardRows", rows) if isinstance(rows, dict) else rows
cand = []
for r in rows:
    try:
        av = float(r.get("accountValue", 0) or 0)
        a = r.get("ethAddress")
        wp = dict(r.get("windowPerformances", []))
        vlm = float(wp.get("month", {}).get("vlm", 0) or 0)
        if a and av >= 10_000 and vlm > 0:
            cand.append((av, a))
    except (TypeError, ValueError):
        continue
cand.sort(reverse=True)
sel = cand[:N_TRY]
print(f"probing {len(sel)} of {len(cand)} eligible accounts", flush=True)

recs = []
for i, (_av0, a) in enumerate(sel):
    try:
        pf = _post({"type": "portfolio", "user": a})
    except Exception:
        continue
    if not isinstance(pf, list):
        continue
    d = dict(pf).get("allTime") or {}
    pnl = d.get("pnlHistory") or []
    avh = d.get("accountValueHistory") or []
    if len(pnl) < MIN_PTS or len(avh) < MIN_PTS:
        continue
    try:
        t = np.array([int(x[0]) for x in pnl])
        cum = np.array([float(x[1]) for x in pnl])
        avt = np.array([float(x[1]) for x in avh[: len(cum)]])
    except (TypeError, ValueError, IndexError):
        continue
    if len(avt) != len(cum):
        continue
    base = np.where(avt > 1000, avt, np.nan)
    ret = np.zeros(len(cum))
    ret[1:] = np.diff(cum) / np.where(np.isnan(base[1:]), np.inf, base[1:])
    ret = np.clip(np.nan_to_num(ret, nan=0.0, posinf=0.0, neginf=0.0), -0.5, 0.5)
    if (t[-1] - t[0]) / 86400_000 < MIN_SPAN:
        continue
    k = int(len(ret) * 0.6)
    f, h = ret[1:k], ret[k:]
    if len(f) < 25 or len(h) < 15:
        continue
    fs = float(f.mean() / f.std() * np.sqrt(365)) if f.std() > 0 else 0.0
    eq = np.cumprod(1 + f)
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    recs.append(
        {
            "span": (t[-1] - t[0]) / 86400_000,
            "f_sharpe": fs,
            "f_cons": float((f > 0).mean()),
            "f_dd": dd,
            "f_ret": float(np.prod(1 + f) - 1),
            "h_ret": float(np.prod(1 + h) - 1),
            "h_sharpe": float(h.mean() / h.std() * np.sqrt(365)) if h.std() > 0 else 0.0,
        }
    )
    if (i + 1) % 300 == 0:
        print(f"  {i + 1}/{len(sel)} usable={len(recs)}", flush=True)
        Path("data/hl_hp_partial.json").write_text(json.dumps(recs), "utf-8")

n = len(recs)
print(f"\nHIGH-POWER cohort: {n} traders with long records")
if n < 100:
    raise SystemExit("insufficient")
sp = np.array([r["span"] for r in recs])
se = 1 / np.sqrt(max(1, n - 3))
mde = 2 * se
print(f"track record: median {np.median(sp):.0f}d max {sp.max():.0f}d")
print(f"POWER: SE(rho)~{se:.4f} -> minimum detectable |rho| at t=2 is {mde:.4f}")


def spear(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, 0.0
    rho = float(np.corrcoef(ra, rb)[0, 1])
    return rho, float(rho * np.sqrt((n - 2) / max(1e-12, 1 - rho**2))) if n > 2 and abs(
        rho
    ) < 1 else 0.0


hr = np.array([r["h_ret"] for r in recs])
out = {}
for nm, key in (
    ("SHARPE", "f_sharpe"),
    ("CONSISTENCY", "f_cons"),
    ("RETURN", "f_ret"),
    ("DRAWDOWN_CTRL", "f_dd"),
):
    x = np.array([r[key] for r in recs])
    rho, t = spear(x, hr)
    lo, hi = rho - 1.96 * se, rho + 1.96 * se
    o = np.argsort(x)
    k = max(5, n // 4)
    top, bot = hr[o[-k:]], hr[o[:k]]
    sd = np.sqrt(top.var(ddof=1) / k + bot.var(ddof=1) / k)
    ts = (top.mean() - bot.mean()) / sd if sd > 0 else 0
    print(f"\n[{nm}] rho {rho:+.4f} (t {t:+.2f})  95% CI [{lo:+.4f},{hi:+.4f}]")
    print(
        f"   Q4 holding ret {top.mean() * 100:+.1f}% (med {np.median(top) * 100:+.1f}%) vs "
        f"Q1 {bot.mean() * 100:+.1f}% (med {np.median(bot) * 100:+.1f}%) | spread t {ts:+.2f}"
    )
    out[nm] = {
        "rho": round(rho, 4),
        "t": round(t, 2),
        "ci": [round(lo, 4), round(hi, 4)],
        "q4_mean": round(float(top.mean()), 4),
        "q1_mean": round(float(bot.mean()), 4),
        "spread_t": round(float(ts), 2),
    }
print(
    f"\ncohort holding: mean {hr.mean() * 100:+.1f}% median {np.median(hr) * 100:+.1f}% "
    f"| positive {int((hr > 0).sum())}/{n}"
)
Path("data/hl_highpower_skill.json").write_text(
    json.dumps(
        {
            "updated": datetime.now(tz=UTC).isoformat(),
            "n": n,
            "se_rho": round(float(se), 4),
            "min_detectable_rho": round(float(mde), 4),
            "median_span_d": float(np.median(sp)),
            "tests": out,
        },
        indent=1,
    ),
    "utf-8",
)
