"""DIRECT TEST of 'just narrow to traders who make money and drop the ones who don't'.
Rebuilds the long-record cohort SAVING per-trader rows, then applies the filter the principal
describes -- at increasing strictness, and combined -- and reports what each SELECTED group does
FORWARD (out of sample, on the later 40% of each trader's own curve).
The filter is applied using ONLY formation-period info (what you could actually know at
selection time)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np

INFO = "https://api.hyperliquid.xyz/info"
LB = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
N_TRY = 1800
MIN_PTS = 60
MIN_SPAN = 200
CACHE = Path("data/hl_cohort_rows.json")


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


if CACHE.exists():
    recs = json.loads(CACHE.read_text())
    print(f"cached cohort {len(recs)}")
else:
    rows = json.loads(_get(LB))
    rows = rows.get("leaderboardRows", rows) if isinstance(rows, dict) else rows
    cand = []
    for r in rows:
        try:
            av = float(r.get("accountValue", 0) or 0)
            a = r.get("ethAddress")
            wp = dict(r.get("windowPerformances", []))
            if a and av >= 10_000 and float(wp.get("month", {}).get("vlm", 0) or 0) > 0:
                cand.append((av, a))
        except (TypeError, ValueError):
            continue
    cand.sort(reverse=True)
    recs = []
    for i, (_av0, a) in enumerate(cand[:N_TRY]):
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
        if len(avt) != len(cum) or (t[-1] - t[0]) / 86400_000 < MIN_SPAN:
            continue
        base = np.where(avt > 1000, avt, np.nan)
        ret = np.zeros(len(cum))
        ret[1:] = np.diff(cum) / np.where(np.isnan(base[1:]), np.inf, base[1:])
        ret = np.clip(np.nan_to_num(ret, nan=0.0, posinf=0.0, neginf=0.0), -0.5, 0.5)
        k = int(len(ret) * 0.6)
        f, h = ret[1:k], ret[k:]
        if len(f) < 25 or len(h) < 15:
            continue
        eq = np.cumprod(1 + f)
        recs.append(
            {
                "f_ret": float(np.prod(1 + f) - 1),
                "f_sharpe": float(f.mean() / f.std() * np.sqrt(365)) if f.std() > 0 else 0.0,
                "f_cons": float((f > 0).mean()),
                "f_dd": float((eq / np.maximum.accumulate(eq) - 1).min()),
                "h_ret": float(np.prod(1 + h) - 1),
            }
        )
        if (i + 1) % 200 == 0:
            print(f"  {i + 1} usable={len(recs)}", flush=True)
            CACHE.write_text(json.dumps(recs))
    CACHE.write_text(json.dumps(recs))
    print(f"cohort {len(recs)} cached")

fr = np.array([r["f_ret"] for r in recs])
hr = np.array([r["h_ret"] for r in recs])
fs = np.array([r["f_sharpe"] for r in recs])
fc = np.array([r["f_cons"] for r in recs])
fd = np.array([r["f_dd"] for r in recs])


def show(name, m):
    if m.sum() < 5:
        print(f"  {name:<44} n={int(m.sum()):5d}  (too few)")
        return
    s = hr[m]
    print(
        f"  {name:<44} n={int(m.sum()):5d} | fwd mean {s.mean() * 100:+7.1f}% | "
        f"median {np.median(s) * 100:+7.1f}% | positive {(s > 0).mean() * 100:3.0f}%"
    )


print("\n=== 'NARROW TO TRADERS WHO MAKE MONEY' -- what each filtered group does FORWARD ===")
print("  (filter uses ONLY formation-period data = what you could know when choosing)\n")
show("ALL traders (no filter)", np.ones(len(fr), bool))
show("profitable in formation (f_ret > 0)", fr > 0)
show("made > +25%", fr > 0.25)
show("made > +50%", fr > 0.50)
show("made > +100%", fr > 1.0)
show("made > +200%", fr > 2.0)
q = np.quantile(fr, 0.90)
show(f"top 10% by past return (>{q * 100:.0f}%)", fr >= q)
q = np.quantile(fr, 0.99)
show(f"top  1% by past return (>{q * 100:.0f}%)", fr >= q)
print()
show("profitable AND Sharpe>1", (fr > 0) & (fs > 1))
show("profitable AND Sharpe>2", (fr > 0) & (fs > 2))
show("profitable AND consistency>55%", (fr > 0) & (fc > 0.55))
show("ELITE: prof + Sh>1 + cons>55% + dd>-25%", (fr > 0) & (fs > 1) & (fc > 0.55) & (fd > -0.25))
show(
    "ELITE STRICT: prof + Sh>2 + cons>60% + dd>-15%",
    (fr > 0) & (fs > 2) & (fc > 0.60) & (fd > -0.15),
)
print(
    f"\n  For reference: {(fr > 0).mean() * 100:.0f}% were profitable in formation; "
    f"{(hr > 0).mean() * 100:.0f}% were profitable forward."
)
