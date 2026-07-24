"""Developer Momentum Factor v1 -- ECOSYSTEM SELECTION, not price prediction.

Tests the Electric-Capital thesis the CORRECT way: each month rank a survivorship-bias-aware basket
(winners + slow survivors + dead/declining L1s) by developer momentum, and ask whether that rank
predicts each token's forward RELATIVE return (return minus the cross-sectional mean) -- at MULTIPLE
lagged horizons (1/3/6 months), because dev acceleration should lead ecosystem outperformance, not
coincide with it. Reports monthly cross-sectional Spearman IC (t-stat over MONTHS = the honest N)
and a top-tercile-minus-bottom-tercile long/short spread (Sharpe + Newey-West t) per horizon.

v1 signal = commit-velocity momentum (cheapest robust proxy). ESCALATION IF v1 shows signal:
contributor breadth (unique/new/external) then developer retention (likely strongest), then targets
B (TVL growth) + C (survival). Do NOT build the composite before the component works.

KNOWN LIMITATIONS (stated, not hidden): (a) Binance-listed universe still tilts to survivors --
v2 should source prices from CoinGecko to start from 'all protocols with GitHub history'; (b) newer
L1s have no pre-2022 history so early cross-sections are thinner; (c) effective sample ~= #months.

Monthly commits via GitHub Link-header trick (PAT, 5000/hr). Writes data/dev_factor_result.json.
Background job (~2000 API calls). Run from repo root."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.validation.forward_stats import nw_tstat

UNIVERSE = [
    # winners / active majors
    ("ETHUSDT", "ethereum/go-ethereum"), ("SOLUSDT", "solana-labs/solana"),
    ("AVAXUSDT", "ava-labs/avalanchego"), ("ATOMUSDT", "cosmos/cosmos-sdk"),
    ("DOTUSDT", "paritytech/polkadot-sdk"), ("ADAUSDT", "IntersectMBO/cardano-node"),
    ("NEARUSDT", "near/nearcore"), ("ARBUSDT", "OffchainLabs/nitro"),
    ("OPUSDT", "ethereum-optimism/optimism"), ("AAVEUSDT", "aave/aave-v3-core"),
    ("UNIUSDT", "Uniswap/v3-core"), ("LDOUSDT", "lidofinance/lido-dao"),
    ("MKRUSDT", "makerdao/dss"), ("INJUSDT", "InjectiveLabs/injective-core"),
    ("SUIUSDT", "MystenLabs/sui"), ("APTUSDT", "aptos-labs/aptos-core"),
    ("TIAUSDT", "celestiaorg/celestia-node"), ("FILUSDT", "filecoin-project/lotus"),
    # slow survivors (old L1s, still listed)
    ("LTCUSDT", "litecoin-project/litecoin"), ("BCHUSDT", "bitcoin-cash-node/bitcoin-cash-node"),
    ("XLMUSDT", "stellar/stellar-core"), ("ETCUSDT", "etclabscore/core-geth"),
    ("XTZUSDT", "tezos/tezos"), ("DASHUSDT", "dashpay/dash"),
    ("ZECUSDT", "zcash/zcash"), ("QTUMUSDT", "qtumproject/qtum"),
    # declining / near-dead
    ("ALGOUSDT", "algorand/go-algorand"), ("EOSUSDT", "AntelopeIO/leap"),
    ("ZILUSDT", "Zilliqa/zilliqa"), ("ONEUSDT", "harmony-one/harmony"),
    ("FTMUSDT", "Fantom-foundation/go-opera"), ("EGLDUSDT", "multiversx/mx-chain-go"),
    ("KAVAUSDT", "Kava-Labs/kava"), ("ONTUSDT", "ontio/ontology"),
    ("NEOUSDT", "neo-project/neo"),
]
HORIZONS = [1, 3, 6]


def _token() -> str:
    url = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
    m = re.search(r"(gh[ps]_[A-Za-z0-9]+)", url)
    if not m:
        raise SystemExit("no PAT in remote URL")
    return m.group(1)


TOK = _token()


def _months(start=(2021, 1), end=(2026, 6)):
    y, m = start
    out = []
    while (y, m) <= end:
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append((f"{y:04d}-{m:02d}", f"{y:04d}-{m:02d}-01T00:00:00Z",
                    f"{ny:04d}-{nm:02d}-01T00:00:00Z"))
        y, m = ny, nm
    return out


def _count(repo: str, since: str, until: str) -> int | None:
    url = f"https://api.github.com/repos/{repo}/commits?since={since}&until={until}&per_page=1"
    req = urllib.request.Request(url, headers={"User-Agent": "quant/1.0",
                                               "Accept": "application/vnd.github+json",
                                               "Authorization": f"Bearer {TOK}"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        link = r.headers.get("Link", "")
        mm = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
        if mm:
            return int(mm.group(1))
        d = json.loads(r.read().decode())
        return len(d) if isinstance(d, list) else 0
    except urllib.error.HTTPError:
        return None


def _binance_monthly(sym: str) -> dict[str, float]:
    url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1M&limit=90"
    req = urllib.request.Request(url, headers={"User-Agent": "x/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read().decode())
        return {datetime.fromtimestamp(int(k[0]) / 1000, tz=UTC).strftime("%Y-%m"): float(k[4])
                for k in rows}
    except Exception:
        return {}


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 4:
        return 0.0
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1]) if ra.std() and rb.std() else 0.0


def main() -> None:
    months = _months()
    mk = [m[0] for m in months]
    commits: dict[str, dict[str, int]] = {}
    prices: dict[str, dict[str, float]] = {}
    for sym, repo in UNIVERSE:
        prices[sym] = _binance_monthly(sym)
        cc = {}
        for k, s, u in months:
            c = _count(repo, s, u)
            if c is not None:
                cc[k] = c
        commits[sym] = cc
        print(f"  {sym:9s} {repo:36s} commits={len(cc)} price={len(prices[sym])}", flush=True)

    def zmom(sym: str, i: int) -> float | None:
        if i < 6:
            return None
        win = [commits[sym].get(mk[j]) for j in range(i - 6, i)]
        cur = commits[sym].get(mk[i])
        win = [w for w in win if w is not None]
        if cur is None or len(win) < 4:
            return None
        sd = np.std(win)
        return (cur - np.mean(win)) / sd if sd > 0 else 0.0

    def cum_ret(sym: str, i: int, h: int) -> float | None:
        c0 = prices[sym].get(mk[i])
        c1 = prices[sym].get(mk[i + h]) if i + h < len(mk) else None
        return (c1 / c0 - 1.0) if c0 and c1 and c0 > 0 else None

    results = {}
    for h in HORIZONS:
        ics, ls = [], []
        for i in range(6, len(mk) - h):
            rows = []
            for sym, _ in UNIVERSE:
                z = zmom(sym, i)
                fr = cum_ret(sym, i, h)
                if z is not None and fr is not None:
                    rows.append((z, fr))
            if len(rows) < 8:
                continue
            zar = np.array([x[0] for x in rows])
            far = np.array([x[1] for x in rows])
            rel = far - far.mean()
            ics.append(_spearman(zar, rel))
            k = max(1, len(rows) // 3)
            order = np.argsort(zar)
            ls.append(rel[order[-k:]].mean() - rel[order[:k]].mean())
        ics = np.array(ics)
        ls = np.array(ls)
        ic_m = float(ics.mean()) if len(ics) else 0.0
        ic_t = float(ic_m / (ics.std() / np.sqrt(len(ics)))) if len(ics) > 2 and ics.std() else 0.0
        ls_m = float(ls.mean()) if len(ls) else 0.0
        ls_sh = float(ls.mean() / ls.std() * np.sqrt(12 / h)) if len(ls) > 2 and ls.std() else 0.0
        ls_t = float(nw_tstat(ls)) if len(ls) >= 3 else 0.0
        verdict = ("INTERESTING (significant)" if abs(ic_t) >= 2.0 and abs(ls_t) >= 2.0
                   else "WEAK/INSIGNIFICANT")
        results[f"{h}mo"] = {"n_months": len(ics), "cs_ic_mean": round(ic_m, 4),
                             "ic_t": round(ic_t, 2), "ls_monthly_mean": round(ls_m, 4),
                             "ls_sharpe": round(ls_sh, 2), "ls_nw_t": round(ls_t, 2),
                             "verdict": verdict}

    out = {"updated": datetime.now(tz=UTC).isoformat(), "factor": "commit_velocity_momentum",
           "universe": len(UNIVERSE), "by_horizon": results}
    Path("data/dev_factor_result.json").write_text(json.dumps(out, indent=1), "utf-8")
    print("\n=== DEVELOPER MOMENTUM FACTOR v1 (cross-sectional, ecosystem sel) ===", flush=True)
    print(f"universe={len(UNIVERSE)} assets", flush=True)
    for h, r in results.items():
        print(f"  horizon {h}: n={r['n_months']}mo | CS-IC {r['cs_ic_mean']:+.4f} "
              f"(t {r['ic_t']:+.2f}) "
              f"| L/S mean {r['ls_monthly_mean']:+.4f} Sharpe {r['ls_sharpe']:+.2f} "
              f"(NW t {r['ls_nw_t']:+.2f}) | {r['verdict']}", flush=True)


if __name__ == "__main__":
    main()
