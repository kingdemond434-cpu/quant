"""EXPERIMENT (refined): DIRECTIONAL elite flow -- excludes HFT/market-makers.

Prior run selected top-VOLUME accounts = HFT/MM (2000 fills in 30 min); their flow is inventory
management, not conviction (spec layer 11: only directional alpha counts). It was also underpowered
(80 buckets). FIX: select on TURNOVER RATIO (month_vlm / accountValue) -- keep the MODERATE band =
discretionary directional traders. Side effect: their 2000 fills span months -> real power.
Still performance-blind (no PnL in selection) -> no circularity. Flow at t vs return t+1 only.
Bar: |t| >= 2.7 (3-mechanism multiplicity)."""

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
N = 260
BK = 4 * 3600_000
COINS = ["BTC", "ETH", "SOL"]


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
        if 1.0 <= turn <= 25.0:  # directional band: not HFT/MM, not dormant
            cand.append((av, a, turn))
    except (TypeError, ValueError):
        continue
cand.sort(reverse=True)  # largest directional accounts
sel = cand[:N]
print(
    f"leaderboard {len(rows)} -> directional cohort {len(sel)} "
    f"(turnover {min(x[2] for x in sel):.1f}-{max(x[2] for x in sel):.1f}x/mo, performance-blind)"
)

flow = {c: defaultdict(float) for c in COINS}
ok = 0
tmin = tmax = None
for i, (_av, a, _turn) in enumerate(sel):
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
        sgn = 1.0 if str(f.get("side", "")).upper().startswith("B") else -1.0
        flow[c][t // BK] += sgn * px * sz
        tmin = t if tmin is None else min(tmin, t)
        tmax = t if tmax is None else max(tmax, t)
    if (i + 1) % 80 == 0:
        print(f"  {i + 1}/{len(sel)} ok={ok}", flush=True)
print(f"with fills {ok}/{len(sel)} | span {(tmax - tmin) / 86400_000 if tmin else 0:.1f}d")

res = []
pool = []
for c in COINS:
    bks = sorted(flow[c])
    kl = json.loads(
        _get(f"https://api.binance.com/api/v3/klines?symbol={c}USDT&interval=4h&limit=1000", 40)
    )
    px = {int(k[0]) // BK: float(k[4]) for k in kl}
    grid = [b for b in bks if b in px and (b + 1) in px]
    if len(grid) < 60:
        print(f"{c}: thin ({len(bks)} bkts, {len(grid)} aligned)")
        continue
    sig = np.array([flow[c][b] for b in grid])
    cl = np.array([px[b] for b in grid])
    ret = np.zeros(len(cl))
    ret[1:] = cl[1:] / cl[:-1] - 1
    r = stage_a_screen(sig, ret, name=f"hl_dir_flow_{c}", zwin=20)
    r["coin"] = c
    res.append(r)
    pool.append(r.get("ic", 0.0))
    print(
        f"{c:4s} n={len(grid)} | IC {r.get('ic'):+.4f} | same {r.get('same_period_corr'):+.3f} "
        f"| resid {r.get('residual_ic'):+.4f} | momSh {r.get('sharpe_momentum'):+.2f} "
        f"| revSh {r.get('sharpe_reversal'):+.2f} | {r['verdict']}"
    )
if len(pool) > 1:
    p = np.array(pool)
    t = float(p.mean() / (p.std() / np.sqrt(len(p)))) if p.std() else 0.0
    print(f"\nPOOLED mean IC {p.mean():+.4f} (t {t:+.2f}, n={len(p)}) | bar |t|>=2.7")
Path("data/hl_dir_flow.json").write_text(
    json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "cohort": ok, "results": res}, indent=1
    ),
    "utf-8",
)
