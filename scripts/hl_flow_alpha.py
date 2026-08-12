"""EXPERIMENT: does ELITE ORDER FLOW carry information? (mechanism #3, genuinely new)

Falsified already: (1) aggregate elite positioning level, (2) skill persistence (gapped). Both were
about WHO is good. This tests something different: when big/active Hyperliquid accounts actually
TRADE, does price move their way afterwards? That is the real copytrading mechanism and the spec's
"Information Advantage Engine" (layer 10) -- and it is untested.

TWO CIRCULARITY TRAPS, both designed around:
 (1) SELECTION: picking profitable traders then testing whether their trades preceded favourable
     moves is circular (profit IS that, by definition). So the cohort is selected on monthly VOLUME
     -- skill-neutral, performance-blind.
 (2) LOOKAHEAD: flow at bucket t is tested against the return of bucket t+1 ONLY (never the
     concurrent bucket), and the harness's de-contamination gate checks the signal LEADS rather
     than coincides.

Signed taker flow per bucket = sum(+notional for buys, -notional for sells) across the cohort,
per coin. Screened per-coin AND pooled (pooled t over coins = the honest N).
Multiplicity: this is 1 of 3 pre-registered mechanisms -> bar is |t| >= 2.7, not 2.0.
Stage-A only, zero promotion authority. Run from repo root."""

from __future__ import annotations

import json
import sys
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.axis_screen import stage_a_screen  # noqa: E402

_LB = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
_INFO = "https://api.hyperliquid.xyz/info"
N_TRADERS = 220  # volume-selected cohort
BUCKET_MS = 4 * 3600_000  # 4h buckets
COINS = ["BTC", "ETH", "SOL"]


def _get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-hlflow/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _post(payload, timeout=25):
    req = urllib.request.Request(
        _INFO,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "quant-hlflow/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def cohort() -> list[str]:
    rows = json.loads(_get(_LB))
    rows = rows.get("leaderboardRows", rows) if isinstance(rows, dict) else rows
    scored = []
    for r in rows:
        try:
            wp = dict(r.get("windowPerformances", []))
            vlm = float(wp.get("month", {}).get("vlm", 0) or 0)
            av = float(r.get("accountValue", 0) or 0)
            a = r.get("ethAddress")
            if a and av >= 25_000 and vlm > 0:
                scored.append((vlm, a))  # VOLUME-selected: performance-blind
        except (TypeError, ValueError):
            continue
    scored.sort(reverse=True)
    print(f"leaderboard {len(rows)} -> volume-ranked cohort {N_TRADERS} (performance-blind)")
    return [a for _, a in scored[:N_TRADERS]]


def main() -> None:
    addrs = cohort()
    flow: dict[str, dict[int, float]] = {c: defaultdict(float) for c in COINS}
    ok = 0
    tmin, tmax = None, None
    for i, a in enumerate(addrs):
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
            flow[c][t // BUCKET_MS] += sgn * px * sz
            tmin = t if tmin is None else min(tmin, t)
            tmax = t if tmax is None else max(tmax, t)
        if (i + 1) % 60 == 0:
            print(f"  fills fetched {i + 1}/{len(addrs)} (ok={ok})", flush=True)
    span_d = (tmax - tmin) / 86400_000 if tmin and tmax else 0
    print(f"cohort with fills: {ok}/{len(addrs)} | history span {span_d:.1f} days")

    results, pooled = [], []
    for c in COINS:
        buckets = sorted(flow[c])
        if len(buckets) < 80:
            print(f"{c}: thin ({len(buckets)} buckets)")
            continue
        # price per bucket from Binance (bucket close), aligned to the same grid
        sym = f"{c}USDT"
        kl = json.loads(
            _get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=4h&limit=1000", 40)
        )
        px = {int(k[0]) // BUCKET_MS: float(k[4]) for k in kl}
        grid = [b for b in buckets if b in px and (b + 1) in px]
        if len(grid) < 60:
            print(f"{c}: thin aligned ({len(grid)})")
            continue
        sig = np.array([flow[c][b] for b in grid])
        close = np.array([px[b] for b in grid])
        ret = np.zeros(len(close))
        ret[1:] = close[1:] / close[:-1] - 1.0
        r = stage_a_screen(sig, ret, name=f"hl_elite_flow_{c}", zwin=20)
        r["coin"] = c
        results.append(r)
        pooled.append(r.get("ic", 0.0))
        print(
            f"{c:4s} n={len(grid)} | IC {r.get('ic'):+.4f} | same {r.get('same_period_corr'):+.3f} "
            f"| resid {r.get('residual_ic'):+.4f} | momSh {r.get('sharpe_momentum'):+.2f} "
            f"| revSh {r.get('sharpe_reversal'):+.2f} | {r['verdict']}"
        )

    if len(pooled) > 1:
        p = np.array(pooled)
        t = float(p.mean() / (p.std() / np.sqrt(len(p)))) if p.std() else 0.0
        print(
            f"\nPOOLED mean IC {p.mean():+.4f} (t {t:+.2f}, n={len(p)} coins) "
            f"| bar for 3-mechanism multiplicity: |t| >= 2.7"
        )
    Path("data/hl_flow_alpha.json").write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "cohort_with_fills": ok,
                "history_days": round(span_d, 1),
                "results": results,
            },
            indent=1,
        ),
        "utf-8",
    )


if __name__ == "__main__":
    main()
