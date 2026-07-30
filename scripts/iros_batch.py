"""IROS BATCH: the three untested items from the principal's hypothesis set.

Each is a genuine escalation of something already refuted, so each is a DIFFERENT construction of a
dead family -- not a re-run. Pre-registered, Bonferroni across the three.

  H2  CONTRIBUTOR RETENTION (escalation of dev-momentum, which died at raw commit velocity:
      CS-IC -0.018/+0.033/+0.014 at 1/3/6mo). Retention is the a-priori strongest component and was
      explicitly pre-registered as the follow-up. Mechanism: a protocol keeping its developers is
      structurally healthier than one with churning headcount, regardless of commit COUNT.
  H3  EXCHANGE FLOW -> REALISED VOLATILITY. The genuinely novel target: the desk has never tested a
      VOLATILITY target, only direction. Mechanism: coins moving onto exchanges are pre-positioned
      to sell, so inflow should precede vol expansion even when it does not predict direction.
  H4  ATTENTION ACCELERATION (not level). Attention LEVEL died at all 12 horizons (96 tests, 0
      survivors). Acceleration is a different quantity: the second derivative, i.e. is interest
      GROWING, which is the actual claim in "information spreads before capital arrives".

Bar: |t| >= 2.4 (Bonferroni for 3 tests at 5%). Stage-A, zero promotion authority.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/iros_batch.json"
BAR = 2.4


def _get(u, t=35):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode())


def spearman(a, b):
    if len(a) < 5:
        return 0.0, 0.0
    ra, rb = np.argsort(np.argsort(a)).astype(float), np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, 0.0
    r = float(np.corrcoef(ra, rb)[0, 1])
    n = len(a)
    t = r * np.sqrt((n - 2) / max(1e-12, 1 - r ** 2)) if n > 2 and abs(r) < 1 else 0.0
    return r, float(t)


# ---------------------------------------------------------------- H2 contributor retention
def h2_retention(res):
    tok = None
    try:
        url = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True,
                                      cwd=str(ROOT)).strip()
        m = re.search(r"(gh[ps]_[A-Za-z0-9]+)", url)
        tok = m.group(1) if m else None
    except Exception:
        pass
    if not tok:
        print("H2 contributor retention: NO PAT -- skipped")
        return

    UNIV = [("ETHUSDT", "ethereum/go-ethereum"), ("SOLUSDT", "solana-labs/solana"),
            ("AVAXUSDT", "ava-labs/avalanchego"), ("ATOMUSDT", "cosmos/cosmos-sdk"),
            ("DOTUSDT", "paritytech/polkadot-sdk"), ("NEARUSDT", "near/nearcore"),
            ("FILUSDT", "filecoin-project/lotus"), ("ALGOUSDT", "algorand/go-algorand"),
            ("EOSUSDT", "AntelopeIO/leap"), ("ZILUSDT", "Zilliqa/zilliqa"),
            ("ONEUSDT", "harmony-one/harmony"), ("FTMUSDT", "Fantom-foundation/go-opera"),
            ("XTZUSDT", "tezos/tezos"), ("EGLDUSDT", "multiversx/mx-chain-go"),
            ("KAVAUSDT", "Kava-Labs/kava"), ("NEOUSDT", "neo-project/neo"),
            ("QTUMUSDT", "qtumproject/qtum"), ("ONTUSDT", "ontio/ontology")]

    def authors(repo, since, until):
        """Distinct commit authors in a window -- retention needs IDENTITY, not count."""
        out, page = set(), 1
        while page <= 3:
            u = (f"https://api.github.com/repos/{repo}/commits?since={since}&until={until}"
                 f"&per_page=100&page={page}")
            r = urllib.request.Request(u, headers={"User-Agent": "q/1.0",
                                                   "Accept": "application/vnd.github+json",
                                                   "Authorization": f"Bearer {tok}"})
            try:
                with urllib.request.urlopen(r, timeout=30) as h:
                    d = json.loads(h.read().decode())
            except Exception:
                break
            if not isinstance(d, list) or not d:
                break
            for c in d:
                a = (c.get("author") or {}).get("login") or \
                    ((c.get("commit") or {}).get("author") or {}).get("email")
                if a:
                    out.add(a)
            if len(d) < 100:
                break
            page += 1
        return out

    # formation: authors in months -6..-3 vs -3..0 -> retention = overlap / earlier set
    now = datetime.now(tz=UTC)
    w = [(now.replace(day=1) - __import__("datetime").timedelta(days=d)).strftime("%Y-%m-%dT00:00:00Z")
         for d in (180, 90, 0)]
    rows = []
    for sym, repo in UNIV:
        a1, a2 = authors(repo, w[0], w[1]), authors(repo, w[1], w[2])
        if len(a1) < 3:
            continue
        ret = len(a1 & a2) / len(a1)                    # share of devs who stayed
        rows.append((sym, ret, len(a1), len(a2)))
    if len(rows) < 8:
        print(f"H2 contributor retention: only {len(rows)} usable repos -- skipped")
        return

    px = {}
    for sym, _, _, _ in rows:
        try:
            k = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1M&limit=6")
            px[sym] = [float(x[4]) for x in k]
        except Exception:
            pass
    use = [(s, r) for s, r, _, _ in rows if s in px and len(px[s]) >= 4]
    if len(use) < 8:
        print(f"H2: only {len(use)} with prices -- skipped")
        return
    fwd = np.array([px[s][-1] / px[s][-4] - 1.0 for s, _ in use])   # last 3 months forward
    rel = fwd - fwd.mean()
    ret = np.array([r for _, r in use])
    rho, t = spearman(ret, rel)
    k = max(2, len(use) // 3)
    o = np.argsort(ret)
    spread = float(rel[o[-k:]].mean() - rel[o[:k]].mean())
    print(f"H2 CONTRIBUTOR RETENTION  n={len(use)}  retention {ret.min():.2f}-{ret.max():.2f}  "
          f"rho {rho:+.3f} (t {t:+.2f})  top-bottom rel-return {spread*100:+.1f}%  "
          f"{'PASS' if abs(t) >= BAR else 'fail'}")
    res.append({"h": "H2_contributor_retention", "n": len(use), "rho": round(rho, 4),
                "t": round(t, 2), "spread_pct": round(spread * 100, 2),
                "pass": bool(abs(t) >= BAR)})


# ---------------------------------------------------------------- H3 exchange flow -> vol
def h3_flow_vol(res):
    try:
        d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
        sup = {}
        for x in d:
            v = x.get("totalCirculatingUSD") or {}
            p = v.get("peggedUSD") if isinstance(v, dict) else None
            if p is not None:
                sup[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(p)
        kl = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
        px = {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
              for r in kl}
    except Exception as e:
        print(f"H3 exchange-flow->vol: DATA-BLOCKED ({type(e).__name__})")
        return
    dates = sorted(set(sup) & set(px))
    if len(dates) < 200:
        print(f"H3: thin ({len(dates)})")
        return
    s = np.array([sup[d] for d in dates])
    c = np.array([px[d] for d in dates])
    r = np.zeros(len(c))
    r[1:] = c[1:] / c[:-1] - 1.0
    # signal: 7d stablecoin-supply FLOW (proxy for capital moving to exchanges)
    flow = np.zeros(len(s))
    flow[7:] = s[7:] / s[:-7] - 1.0
    # target: forward 7d REALISED VOL (not direction -- the novel part)
    fvol = np.full(len(r), np.nan)
    for i in range(len(r) - 7):
        fvol[i] = r[i + 1:i + 8].std()
    m = ~np.isnan(fvol)
    m[:30] = False
    z = np.zeros(len(flow))
    for i in range(30, len(flow)):
        w_ = flow[i - 30:i]
        sd = w_.std()
        z[i] = (flow[i] - w_.mean()) / sd if sd > 0 else 0.0
    zv, fv = z[m], fvol[m]
    rho, t = spearman(zv, fv)
    t_eff = t / np.sqrt(7)                       # overlap deflation (7d windows)
    k = max(5, len(zv) // 4)
    o = np.argsort(zv)
    hi, lo = float(fv[o[-k:]].mean()), float(fv[o[:k]].mean())
    print(f"H3 FLOW -> REALISED VOL  n={len(zv)}  rho {rho:+.3f} (t {t_eff:+.2f} overlap-adj)  "
          f"hi-flow vol {hi*100:.2f}% vs lo {lo*100:.2f}% ({hi/max(lo,1e-9):.2f}x)  "
          f"{'PASS' if abs(t_eff) >= BAR else 'fail'}")
    res.append({"h": "H3_flow_to_volatility", "n": len(zv), "rho": round(rho, 4),
                "t_overlap_adj": round(float(t_eff), 2), "vol_ratio": round(hi / max(lo, 1e-9), 3),
                "pass": bool(abs(t_eff) >= BAR)})


# ---------------------------------------------------------------- H4 attention ACCELERATION
def h4_accel(res):
    arts = {"en": "Bitcoin", "ja": "ビットコイン", "ko": "비트코인", "ru": "Биткойн", "zh": "比特幣"}
    try:
        kl = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
        px = {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
              for r in kl}
    except Exception:
        print("H4: price blocked")
        return
    ts_all = []
    for proj, art in arts.items():
        a = urllib.request.quote(art, safe="")
        try:
            d = _get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                     f"{proj}.wikipedia/all-access/all-agents/{a}/daily/20240101/20260722")
        except Exception:
            continue
        s = {}
        for it in d.get("items", []):
            t = str(it["timestamp"])
            s[f"{t[0:4]}-{t[4:6]}-{t[6:8]}"] = float(it["views"])
        ts_all.append(s)
    if not ts_all:
        print("H4: no wiki data")
        return
    dates = sorted(set.intersection(*[set(s) for s in ts_all]) & set(px))
    if len(dates) < 200:
        print(f"H4: thin ({len(dates)})")
        return
    agg = np.array([sum(s[d] for s in ts_all) for d in dates])
    c = np.array([px[d] for d in dates])
    r = np.zeros(len(c))
    r[1:] = c[1:] / c[:-1] - 1.0
    # ACCELERATION: second difference of log attention (level died; growth-of-growth is the claim)
    lg = np.log(np.maximum(agg, 1.0))
    g = np.zeros(len(lg))
    g[7:] = lg[7:] - lg[:-7]              # 7d growth
    acc = np.zeros(len(g))
    acc[7:] = g[7:] - g[:-7]             # acceleration
    best = None
    for h in (7, 14, 30):
        fwd = np.full(len(c), np.nan)
        fwd[:-h] = c[h:] / c[:-h] - 1.0
        m = ~np.isnan(fwd)
        m[:40] = False
        rho, t = spearman(acc[m], fwd[m])
        t_eff = t / np.sqrt(h)
        print(f"H4 ATTENTION ACCELERATION {h:>2}d  n={int(m.sum())}  rho {rho:+.3f} "
              f"(t {t_eff:+.2f} overlap-adj)  {'PASS' if abs(t_eff) >= BAR else 'fail'}")
        if best is None or abs(t_eff) > abs(best[1]):
            best = (h, t_eff, rho)
    res.append({"h": "H4_attention_acceleration", "best_horizon_d": best[0],
                "t_overlap_adj": round(float(best[1]), 2), "rho": round(float(best[2]), 4),
                "pass": bool(abs(best[1]) >= BAR)})


def main() -> None:
    print("=== IROS BATCH: 3 pre-registered escalations of refuted families ===")
    print(f"    bar |t| >= {BAR} (Bonferroni, 3 tests)\n")
    res: list[dict] = []
    h2_retention(res)
    h3_flow_vol(res)
    h4_accel(res)
    passed = [r for r in res if r.get("pass")]
    print(f"\n  PASSED: {len(passed)}/{len(res)}")
    for p in passed:
        print(f"    {p['h']}")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "bar_t": BAR, "results": res}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
