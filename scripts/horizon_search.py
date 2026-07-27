"""TIME HORIZON DISCOVERY (Tier-1 #1) -- with the multiplicity + adjacency guards.

The desk killed whole information classes at a SINGLE daily horizon. Diffusion processes
(attention, TVL rotation) are inherently slow, so a 1-day clock is the wrong instrument and those
kills may be FALSE NEGATIVES. The resurrection engine shortlisted exactly two:
multilingual_wikipedia_attention and defi_health.

THE TRAP (principal, correct): searching 12 horizons just moves overfitting from features to
horizons. Two guards, both mandatory:
  1. BONFERRONI  -- alpha/n_horizons, so a lucky horizon cannot masquerade as a discovery.
  2. ADJACENCY   -- a REAL slow signal is smooth in horizon: if it works at 14d it should also
     show the SAME SIGN at 10d and 21d. An isolated spike at exactly one horizon is noise.
     A survivor must clear Bonferroni AND have >=2 same-sign neighbours.

Overlapping forward windows autocorrelate, so the t-stat is Newey-West-style deflated by
sqrt(horizon) -- otherwise long horizons manufacture significance from overlap alone.
Stage-A only, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HORIZONS = [1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90]
ALPHA = 0.05


def _get(u, t=40):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t).read().decode())


def binance():
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def wiki(proj, art):
    a = urllib.request.quote(art, safe="")
    d = _get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
             f"{proj}.wikipedia/all-access/all-agents/{a}/daily/20240101/20260722")
    out = {}
    for it in d.get("items", []):
        ts = str(it["timestamp"])
        out[f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"] = float(it["views"])
    return out


def llama_tvl():
    d = _get("https://api.llama.fi/v2/historicalChainTvl")
    return {datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat(): float(x["tvl"])
            for x in d}


def llama_chart(url):
    d = _get(url)
    return {datetime.fromtimestamp(int(ts), tz=UTC).date().isoformat(): float(v)
            for ts, v in d.get("totalDataChart", [])}


SIGNALS = {
    "wiki_btc_en": lambda: wiki("en", "Bitcoin"),
    "wiki_btc_ja": lambda: wiki("ja", "ビットコイン"),
    "wiki_btc_ko": lambda: wiki("ko", "비트코인"),
    "wiki_btc_ru": lambda: wiki("ru", "Биткойн"),
    "wiki_btc_zh": lambda: wiki("zh", "比特幣"),
    "defi_tvl": llama_tvl,
    "dex_volume": lambda: llama_chart(
        "https://api.llama.fi/overview/dexs?excludeTotalDataChartBreakdown=true"),
    "protocol_fees": lambda: llama_chart(
        "https://api.llama.fi/overview/fees?excludeTotalDataChartBreakdown=true"),
}


def main() -> None:
    gb = binance()
    bar = ALPHA / len(HORIZONS)
    # two-sided z for the Bonferroni-adjusted alpha
    from math import erf, sqrt

    def p_from_t(t, n):
        # normal approx is fine at these n
        z = abs(t)
        return 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))

    print(f"=== HORIZON DISCOVERY | {len(HORIZONS)} horizons | Bonferroni alpha {bar:.5f} ===")
    print("    (t deflated by sqrt(h) for overlapping windows; survivor needs >=2 same-sign neighbours)\n")
    allres = {}
    for name, fn in SIGNALS.items():
        try:
            s = fn()
        except Exception as e:
            print(f"{name:16s} DATA-BLOCKED ({type(e).__name__})")
            continue
        dates = sorted(set(s) & set(gb))
        if len(dates) < 200:
            print(f"{name:16s} thin ({len(dates)})")
            continue
        sig = np.array([s[d] for d in dates])
        px = np.array([gb[d] for d in dates])
        z = np.zeros(len(sig))
        for t in range(30, len(sig)):
            w = sig[t - 30:t]
            sd = w.std()
            z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0
        row = []
        for h in HORIZONS:
            fwd = np.full(len(px), np.nan)
            fwd[:-h] = px[h:] / px[:-h] - 1.0
            m = ~np.isnan(fwd)
            m[:30] = False
            zv, fv = z[m], fwd[m]
            if len(zv) < 60 or zv.std() == 0 or fv.std() == 0:
                row.append((h, 0.0, 0.0))
                continue
            ic = float(np.corrcoef(zv, fv)[0, 1])
            n_eff = len(zv) / h                      # overlap deflation
            t_stat = ic * np.sqrt(max(1.0, n_eff - 2)) / np.sqrt(max(1e-9, 1 - ic ** 2))
            row.append((h, ic, float(t_stat)))
        allres[name] = row
        best = max(row, key=lambda r: abs(r[2]))
        line = " ".join(f"{h}d:{ic:+.3f}" for h, ic, _ in row)
        print(f"{name:16s} {line}")
        # survivor test
        h_b, ic_b, t_b = best
        p = p_from_t(t_b, 0)
        i = [r[0] for r in row].index(h_b)
        nb = [row[j][1] for j in (i - 1, i + 1) if 0 <= j < len(row)]
        same_sign = sum(1 for v in nb if v * ic_b > 0)
        ok = p < bar and same_sign >= min(2, len(nb))
        print(f"{'':16s}  best {h_b}d IC {ic_b:+.4f} t {t_b:+.2f} p {p:.5f} | "
              f"neighbours same-sign {same_sign}/{len(nb)} -> "
              f"{'*** SURVIVOR ***' if ok else 'no (fails Bonferroni or adjacency)'}\n")
    Path("data/horizon_discovery.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "horizons": HORIZONS,
         "bonferroni_alpha": bar,
         "results": {k: [{"h": h, "ic": ic, "t": t} for h, ic, t in v]
                     for k, v in allres.items()}}, indent=1), "utf-8")


if __name__ == "__main__":
    main()
