"""Batch ALT-DATA orthogonal screen -- multilingual retail attention (Wikipedia pageviews per
language = different geographic user bases) + DeFi protocol-health/flow channels (DefiLlama).
All free, no key, daily history. Hardened harness (de-contam + SUSPECT-LOOKAHEAD rails). These are
genuinely NOT price/derivative feeds -- exactly the low-correlation channels worth screening.
Run from repo root."""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.axis_screen import stage_a_screen  # noqa: E402


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-altdata/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode())


def _binance() -> dict[str, float]:
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


# --- multilingual Wikipedia pageviews (retail attention, per language population) ---------
_WIKI = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
         "{proj}.wikipedia/all-access/all-agents/{art}/daily/20240101/20260722")
_WIKI_ARTS = {"wiki_btc_en": ("en", "Bitcoin"), "wiki_btc_ja": ("ja", "ビットコイン"),
              "wiki_btc_ko": ("ko", "비트코인"), "wiki_btc_ru": ("ru", "Биткойн"),
              "wiki_btc_zh": ("zh", "比特幣")}


def _wiki(proj: str, art: str) -> dict[str, float]:
    art_enc = urllib.request.quote(art, safe="")
    d = _get(_WIKI.format(proj=proj, art=art_enc))
    out = {}
    for it in d.get("items", []):
        ts = str(it["timestamp"])            # YYYYMMDD00
        out[f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"] = float(it["views"])
    return out


# --- DefiLlama protocol-health / flow channels -------------------------------------------
def _llama_tvl() -> dict[str, float]:
    d = _get("https://api.llama.fi/v2/historicalChainTvl")
    return {datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat(): float(x["tvl"])
            for x in d}


def _llama_chart(url: str) -> dict[str, float]:
    d = _get(url)
    chart = d.get("totalDataChart", [])
    return {datetime.fromtimestamp(int(ts), tz=UTC).date().isoformat(): float(v)
            for ts, v in chart}


def _llama_dex() -> dict[str, float]:
    return _llama_chart("https://api.llama.fi/overview/dexs?excludeTotalDataChartBreakdown=true")


def _llama_fees() -> dict[str, float]:
    return _llama_chart("https://api.llama.fi/overview/fees?excludeTotalDataChartBreakdown=true")


def _llama_stables() -> dict[str, float]:
    d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
    out = {}
    for x in d:
        v = x.get("totalCirculatingUSD") or x.get("totalCirculating") or {}
        peg = v.get("peggedUSD") if isinstance(v, dict) else None
        if peg is not None:
            out[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(peg)
    return out


SOURCES = list(_WIKI_ARTS.items())  # wiki handled specially below
LLAMA = {"defi_tvl": _llama_tvl, "dex_volume": _llama_dex,
         "protocol_fees": _llama_fees, "stablecoin_supply": _llama_stables}


def _screen(name: str, series: dict[str, float], gb: dict[str, float], retmap: dict[str, float]):
    dates = sorted(set(series) & set(gb))
    if len(dates) < 90:
        print(f"{name:22s} thin/blocked ({len(dates)}d)")
        return None
    sig = np.array([series[d] for d in dates])
    ret = np.array([retmap[d] for d in dates])
    r = stage_a_screen(sig, ret, name=name)
    print(f"{name:22s} {len(dates)}d | IC {r.get('ic')} | same {r.get('same_period_corr')} "
          f"| resid {r.get('residual_ic')} | momSh {r.get('sharpe_momentum')} "
          f"| revSh {r.get('sharpe_reversal')} | {r['verdict']}")
    return r


def main() -> None:
    gb = _binance()
    dts = sorted(gb)
    btc = np.array([gb[d] for d in dts])
    retmap = {dts[0]: 0.0}
    for i in range(1, len(dts)):
        retmap[dts[i]] = btc[i] / btc[i - 1] - 1.0

    results = []
    for name, (proj, art) in _WIKI_ARTS.items():
        try:
            s = _wiki(proj, art)
        except Exception as e:
            print(f"{name:22s} DATA-BLOCKED ({type(e).__name__}: {e})")
            continue
        r = _screen(name, s, gb, retmap)
        if r:
            results.append(r)
    for name, fetch in LLAMA.items():
        try:
            s = fetch()
        except Exception as e:
            print(f"{name:22s} DATA-BLOCKED ({type(e).__name__}: {e})")
            continue
        r = _screen(name, s, gb, retmap)
        if r:
            results.append(r)

    Path("data/batch_altdata_screen.json").write_text(
        json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "results": results}, indent=1),
        "utf-8")
    surv = [r["name"] for r in results if r["verdict"] == "SCREEN-INTERESTING"]
    print(f"\nSURVIVORS (passed de-contam + lookahead rails): {surv or 'NONE'}")


if __name__ == "__main__":
    main()
