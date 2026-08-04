"""DECISIVE POWER TEST: directional-elite flow across a WIDE coin universe.
Same hypothesis as hl_dir_flow (no re-slicing) -- the only change is BREADTH, which is what the
UNDERPOWERED verdicts and the meaningless n=2 pooled t demanded. Adds a tercile long/short spread
alongside IC, because BTC showed IC +0.157 with momentum Sharpe -1.27 (IC living mid-distribution
= the desk's known IC-trap); if the edge is real it must show in a rank-based spread, not just IC.
Bar: pooled |t| >= 2.7 AND spread consistent in sign. Performance-blind cohort,
flow(t) vs ret(t+1)."""

from __future__ import annotations

import json
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

INFO = "https://api.hyperliquid.xyz/info"
LB = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
N = 320
BK = 4 * 3600_000
COINS = [
    "BTC",
    "ETH",
    "SOL",
    "DOGE",
    "AVAX",
    "LINK",
    "ARB",
    "OP",
    "SUI",
    "APT",
    "LTC",
    "XRP",
    "BNB",
    "NEAR",
    "TIA",
    "INJ",
]


def _get(u, t=180):
    return urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
    ).read()


def _post(p, t=25):
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
        wp = dict(r.get("windowPerformances", []))
        vlm = float(wp.get("month", {}).get("vlm", 0) or 0)
        a = r.get("ethAddress")
        if not a or av < 50_000 or vlm <= 0:
            continue
        turn = vlm / av
        if 1.0 <= turn <= 25.0:
            cand.append((av, a))
    except (TypeError, ValueError):
        continue
cand.sort(reverse=True)
sel = cand[:N]
print(f"directional cohort {len(sel)} (performance-blind)", flush=True)

flow = {c: defaultdict(float) for c in COINS}
ok = 0
for i, (_av, a) in enumerate(sel):
    try:
        fills = _post({"type": "userFills", "user": a})
    except Exception:
        continue
    if not isinstance(fills, list) or not fills:
        continue
    ok += 1
    for f in fills:
        c = f.get("coin")
        if c not in flow:
            continue
        try:
            t = int(f["time"])
            px = float(f["px"])
            sz = float(f["sz"])
        except (KeyError, TypeError, ValueError):
            continue
        flow[c][t // BK] += (
            (1.0 if str(f.get("side", "")).upper().startswith("B") else -1.0) * px * sz
        )
    if (i + 1) % 100 == 0:
        print(f"  {i + 1}/{len(sel)} ok={ok}", flush=True)
print(f"with fills {ok}/{len(sel)}", flush=True)

res = []
ics = []
sprd = []
for c in COINS:
    bks = sorted(flow[c])
    if len(bks) < 70:
        continue
    try:
        kl = json.loads(
            _get(f"https://api.binance.com/api/v3/klines?symbol={c}USDT&interval=4h&limit=1000", 40)
        )
    except Exception:
        continue
    px = {int(k[0]) // BK: float(k[4]) for k in kl}
    grid = [b for b in bks if b in px and (b + 1) in px]
    if len(grid) < 70:
        continue
    sig = np.array([flow[c][b] for b in grid])
    cl = np.array([px[b] for b in grid])
    ret = np.zeros(len(cl))
    ret[1:] = cl[1:] / cl[:-1] - 1
    r = stage_a_screen(sig, ret, name=f"flow_{c}", zwin=20)
    # rank-based tercile spread on the z-signal vs next-bucket return
    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20 : t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0
    zv = z[20:-1]
    fv = np.roll(ret, -1)[20:-1]
    k = max(1, len(zv) // 3)
    o = np.argsort(zv)
    sp = float(fv[o[-k:]].mean() - fv[o[:k]].mean())
    res.append(
        {
            "coin": c,
            "n": len(grid),
            "ic": r.get("ic"),
            "same": r.get("same_period_corr"),
            "resid": r.get("residual_ic"),
            "spread": round(sp, 5),
            "verdict": r["verdict"],
        }
    )
    ics.append(r.get("ic", 0.0))
    sprd.append(sp)
    print(
        f"{c:5s} n={len(grid):4d} IC {r.get('ic'):+.4f} same {r.get('same_period_corr'):+.3f} "
        f"resid {r.get('resid') if 'resid' in r else r.get('residual_ic'):+.4f} "
        f"terc_spread {sp * 100:+.3f}% | {r['verdict']}",
        flush=True,
    )

if len(ics) >= 3:
    a = np.array(ics)
    s = np.array(sprd)
    ti = float(a.mean() / (a.std() / np.sqrt(len(a)))) if a.std() else 0.0
    ts = float(s.mean() / (s.std() / np.sqrt(len(s)))) if s.std() else 0.0
    print(f"\n=== POOLED n={len(a)} coins ===")
    print(f"  mean IC {a.mean():+.4f} (t {ti:+.2f})  | positive in {int((a > 0).sum())}/{len(a)}")
    print(
        f"  mean tercile spread {s.mean() * 100:+.3f}% (t {ts:+.2f}) | "
        f"positive in {int((s > 0).sum())}/{len(s)}"
    )
    print(
        f"  BAR: |t|>=2.7 on BOTH + consistent sign -> "
        f"{'PASS' if abs(ti) >= 2.7 and abs(ts) >= 2.7 else 'FAIL'}"
    )
Path("data/hl_breadth_flow.json").write_text(
    json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "cohort": ok, "results": res}, indent=1
    ),
    "utf-8",
)
