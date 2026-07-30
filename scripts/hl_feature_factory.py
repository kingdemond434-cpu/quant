"""TRADER BEHAVIOURAL FEATURE FACTORY -- the principal's reframe (2026-07-27).

STOP evaluating trader RANKING as the strategy. Treat trader behaviour as a high-dimensional
FEATURE SPACE: extract many orthogonal behavioural features from elite trader ACTIONS, screen each
independently through the existing Stage-A harness, and let only survivors earn forward clocks.
Copying is never assumed to be the alpha.

Features are the AGGREGATE behavioural state of a performance-blind elite cohort per 4h bucket --
not "who is good". Each answers a different question: are they crowding? disagreeing? de-risking?
flipping? sizing up? concentrating?

MULTIPLICITY IS THE CENTRAL RISK of a feature factory: k features x m coins inflates false
positives. Handled per the two-stage law -- Stage-A screening is UNLIMITED and carries ZERO
promotion authority; the expected-false-positive count and a Bonferroni alpha are reported so
nothing looks significant by accident. Run from repo root.
"""
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
N = 340
BK = 4 * 3600_000
COINS = ["BTC", "ETH", "SOL"]
CACHE = Path("data/hl_fills_cache.json")


def _get(u, t=180):
    return urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read()


def _post(p, t=20):
    r = urllib.request.Request(INFO, data=json.dumps(p).encode(),
                               headers={"Content-Type": "application/json",
                                        "User-Agent": "q/1.0"})
    with urllib.request.urlopen(r, timeout=t) as x:
        return json.loads(x.read().decode())


if CACHE.exists():
    raw = json.loads(CACHE.read_text())
    print(f"cached fills for {len(raw)} traders")
else:
    rows = json.loads(_get(LB))
    rows = rows.get("leaderboardRows", rows) if isinstance(rows, dict) else rows
    cand = []
    for r in rows:
        try:
            av = float(r.get("accountValue", 0) or 0)
            a = r.get("ethAddress")
            wp = dict(r.get("windowPerformances", []))
            vlm = float(wp.get("month", {}).get("vlm", 0) or 0)
            if a and av >= 50_000 and vlm > 0 and 1.0 <= vlm / av <= 25.0:
                cand.append((av, a))
        except (TypeError, ValueError):
            continue
    cand.sort(reverse=True)
    raw = []
    for i, (_av0, a) in enumerate(cand[:N]):
        try:
            f = _post({"type": "userFills", "user": a})
        except Exception:
            continue
        if isinstance(f, list) and f:
            raw.append([{"c": x.get("coin"), "t": int(x["time"]), "p": float(x["px"]),
                         "s": float(x["sz"]), "b": str(x.get("side", "")).upper().startswith("B"),
                         "d": str(x.get("dir", ""))}
                        for x in f if x.get("coin") in COINS and x.get("time")])
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{min(N, len(cand))} ok={len(raw)}", flush=True)
            CACHE.write_text(json.dumps(raw))
    CACHE.write_text(json.dumps(raw))
print(f"cohort {len(raw)} traders (performance-blind)")

feat = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
per_trader = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
for ti, fills in enumerate(raw):
    for x in fills:
        c = x["c"]
        b = x["t"] // BK
        n_ = x["p"] * x["s"]
        sgn = 1.0 if x["b"] else -1.0
        F = feat[c][b]
        F["net_flow"] += sgn * n_
        F["gross_vol"] += n_
        F["n_trades"] += 1
        F["n_buys"] += 1.0 if x["b"] else 0.0
        d = x["d"]
        if d.startswith("Open"):
            F["open_notional"] += n_
        if d.startswith("Close"):
            F["close_notional"] += n_
        if "Long" in d:
            F["long_notional"] += n_
        if "Short" in d:
            F["short_notional"] += n_
        per_trader[c][b][ti] += sgn * n_

FEATURES = ["net_flow", "flow_imbalance", "gross_vol", "n_trades", "avg_trade_size", "buy_ratio",
            "disagreement", "consensus_strength", "participation", "concentration",
            "open_close_ratio", "long_short_tilt", "net_flow_accel", "vol_accel"]


def build(c):
    bks = sorted(feat[c])
    out = {f: [] for f in FEATURES}
    keep = []
    prev_net = prev_vol = None
    for b in bks:
        F = feat[c][b]
        pt = np.array(list(per_trader[c][b].values()))
        if F["n_trades"] < 3 or len(pt) < 2:
            continue
        gross = max(F["gross_vol"], 1e-9)
        out["net_flow"].append(F["net_flow"])
        out["flow_imbalance"].append(F["net_flow"] / gross)
        out["gross_vol"].append(gross)
        out["n_trades"].append(F["n_trades"])
        out["avg_trade_size"].append(gross / F["n_trades"])
        out["buy_ratio"].append(F["n_buys"] / F["n_trades"])
        out["disagreement"].append(float(pt.std() / (abs(pt.mean()) + 1e-9)))
        out["consensus_strength"].append(float(abs(pt.sum()) / (np.abs(pt).sum() + 1e-9)))
        out["participation"].append(float(len(pt)))
        out["concentration"].append(float(np.abs(pt).max() / (np.abs(pt).sum() + 1e-9)))
        out["open_close_ratio"].append(F["open_notional"] / (F["close_notional"] + 1e-9))
        out["long_short_tilt"].append((F["long_notional"] - F["short_notional"]) / gross)
        out["net_flow_accel"].append(0.0 if prev_net is None else F["net_flow"] - prev_net)
        out["vol_accel"].append(0.0 if prev_vol is None else gross - prev_vol)
        prev_net, prev_vol = F["net_flow"], gross
        keep.append(b)
    return keep, out


results = []
for c in COINS:
    bks, fx = build(c)
    if len(bks) < 70:
        print(f"{c}: thin ({len(bks)})")
        continue
    kl = json.loads(_get(f"https://api.binance.com/api/v3/klines?symbol={c}USDT"
                         f"&interval=4h&limit=1000", 40))
    px = {int(k[0]) // BK: float(k[4]) for k in kl}
    idx = [i for i, b in enumerate(bks) if b in px and (b + 1) in px]
    if len(idx) < 70:
        print(f"{c}: thin aligned ({len(idx)})")
        continue
    cl = np.array([px[bks[i]] for i in idx])
    ret = np.zeros(len(cl))
    ret[1:] = cl[1:] / cl[:-1] - 1
    print(f"\n--- {c}  n={len(idx)} buckets ---")
    for fname in FEATURES:
        sig = np.array([fx[fname][i] for i in idx], dtype="float64")
        if sig.std() == 0:
            continue
        r = stage_a_screen(sig, ret, name=f"{c}:{fname}", zwin=20)
        r.update({"coin": c, "feature": fname})
        results.append(r)
        flag = "*" if r["verdict"] == "SCREEN-INTERESTING" else " "
        print(f" {flag}{fname:20s} IC {r.get('ic'):+.4f} same {r.get('same_period_corr'):+.3f} "
              f"resid {r.get('residual_ic'):+.4f} revSh {r.get('sharpe_reversal'):+.2f} "
              f"{r['verdict']}")

k = len(results)
print(f"\n=== FEATURE FACTORY: {k} feature-coin screens ===")
if k:
    surv = [r for r in results if r["verdict"] == "SCREEN-INTERESTING"]
    exp = 0.05 * k
    print(f"  SCREEN-INTERESTING: {len(surv)}/{k}")
    print(f"  Expected false positives at alpha=0.05: ~{exp:.1f} | Bonferroni alpha {0.05/k:.5f}")
    print(f"  -> survivors {'EXCEED' if len(surv) > exp else 'DO NOT EXCEED'} chance expectation")
    print("\n  per-feature pooled across coins (|t|>=1.5 shown):")
    for f in FEATURES:
        v = [r.get("ic", 0.0) for r in results if r["feature"] == f]
        if len(v) >= 2:
            a = np.array(v)
            t = float(a.mean() / (a.std() / np.sqrt(len(a)))) if a.std() else 0.0
            if abs(t) >= 1.5:
                print(f"    {f:20s} mean IC {a.mean():+.4f} t {t:+.2f} (n={len(a)})")
    for r in surv:
        print(f"    SURVIVOR: {r['name']} IC {r.get('ic'):+.4f}")

Path("data/hl_feature_factory.json").write_text(json.dumps(
    {"updated": datetime.now(tz=UTC).isoformat(), "n_screens": k, "results": results}, indent=1),
    "utf-8")
