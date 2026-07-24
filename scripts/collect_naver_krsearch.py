"""Korean retail search-attention screen -- NAVER DataLab (official keyed API, day-one deep
history like FRED/Wikipedia, NOT a forward-accruing clock).

MECHANISM: Korean retail sentiment/positioning propagates through a distinct information
ecosystem from Western Crypto Twitter (the desk already treats Upbit/Bithumb/Coinone premium as a
real, orthogonal axis -- kimchi -- so a Korean retail-ATTENTION layer is a natural companion
mechanism, not price-derived). Tests whether KR search-interest for crypto terms leads next-day
BTC returns, exactly like the multilingual Wikipedia-pageviews screen in batch_altdata.py.

LEGITIMACY (charter s13): NAVER DataLab is an official, keyed, developer-registered API
(NAVER Developers / NAVER Cloud Platform) serving a relative search-index -- NOT scraped HTML,
NOT a login-gated session token. Cleanly distinct from Baidu Index (which requires a Baidu-account
OAuth token refreshed via manual login -- graded needs-legitimacy-review, NOT built here) and from
Telegram/Discord/Coinpan/DCInside/5ch (public-but-platform-hosted community scraping -- ToS-grey,
also NOT built here; see docs/research/data_axis_watchlist.md for both exclusions logged).

Key: data/secrets/naver.json {"client_id": "...", "client_secret": "..."} (free NAVER Developers
registration). No key -> graceful skip (exit 0, cycle stays green) -- same convention as
collect_fred_macro.py. USE THE AUDITED HARNESS (charter s26): screening is
libs.research.axis_screen.stage_a_screen, never hand-rolled.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.research.axis_screen import stage_a_screen

_KEYFILE = Path("data/secrets/naver.json")
_ENDPOINT = "https://openapi.naver.com/v1/datalab/search"
_BINANCE = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000"
_OUT = Path("data/batch_krsearch_screen.json")
_LOOKBACK_DAYS = 1000  # conservative window; Naver's actual date-range ceiling is unconfirmed --
                       # a request past its real limit fails cleanly (caught, printed, no crash)
_KEYWORD_GROUPS = [
    {"groupName": "kr_crypto", "keywords": ["비트코인", "암호화폐", "코인"]},
]


def _keys() -> tuple[str, str] | None:
    cid = os.environ.get("NAVER_CLIENT_ID")
    sec = os.environ.get("NAVER_CLIENT_SECRET")
    if cid and sec:
        return cid, sec
    if _KEYFILE.exists():
        try:
            d = json.loads(_KEYFILE.read_text("utf-8"))
            cid, sec = d.get("client_id"), d.get("client_secret")
            if cid and sec:
                return str(cid), str(sec)
        except Exception:
            pass
    return None


def _binance_daily() -> dict[str, float]:
    req = urllib.request.Request(_BINANCE, headers={"User-Agent": "quant-krsearch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read().decode())
    return {datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC).date().isoformat(): float(row[4])
            for row in rows}


def _naver_search(client_id: str, client_secret: str, *, start: str, end: str) -> dict[str, float]:
    """Aggregate ratio across the keyword group's daily series (mean when >1 keyword group)."""
    body = json.dumps({
        "startDate": start, "endDate": end, "timeUnit": "date",
        "keywordGroups": _KEYWORD_GROUPS,
    }).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT, data=body, method="POST",
        headers={
            "X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d: dict[str, Any] = json.loads(r.read().decode())
    out: dict[str, float] = {}
    for group in d.get("results", []):
        for point in group.get("data", []):
            period = str(point.get("period"))
            ratio = float(point.get("ratio", 0.0))
            out[period] = out.get(period, 0.0) + ratio
    n_groups = len(d.get("results", [])) or 1
    return {k: v / n_groups for k, v in out.items()}


def main() -> None:
    keys = _keys()
    if keys is None:
        print("collect_naver_krsearch: no NAVER_CLIENT_ID/SECRET (env or data/secrets/naver.json) "
              "-- graceful skip, cycle stays green")
        return
    client_id, client_secret = keys

    try:
        gb = _binance_daily()
    except Exception as e:
        print(f"collect_naver_krsearch: Binance fetch failed ({type(e).__name__}: {e})")
        return
    dts = sorted(gb)
    if len(dts) < 90:
        print(f"collect_naver_krsearch: only {len(dts)} Binance days -- too thin")
        return
    start, end = dts[max(0, len(dts) - _LOOKBACK_DAYS)], dts[-1]

    try:
        kr = _naver_search(client_id, client_secret, start=start, end=end)
    except Exception as e:
        print(f"collect_naver_krsearch: DATA-BLOCKED ({type(e).__name__}: {e})")
        return

    btc = np.array([gb[d] for d in dts])
    retmap = {dts[0]: 0.0}
    for i in range(1, len(dts)):
        retmap[dts[i]] = btc[i] / btc[i - 1] - 1.0

    dates = sorted(set(kr) & set(retmap))
    if len(dates) < 90:
        print(f"collect_naver_krsearch: only {len(dates)} aligned days -- too thin to screen")
        return
    sig = np.array([kr[d] for d in dates])
    ret = np.array([retmap[d] for d in dates])
    result = stage_a_screen(sig, ret, name="kr_search_btc")
    print(f"kr_search_btc          {len(dates)}d | IC {result.get('ic')} | "
          f"same {result.get('same_period_corr')} | resid {result.get('residual_ic')} | "
          f"momSh {result.get('sharpe_momentum')} | revSh {result.get('sharpe_reversal')} | "
          f"{result['verdict']}")

    _OUT.write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "n_days": len(dates), "result": result},
        indent=1), "utf-8")
    print(f"-> {_OUT}")


if __name__ == "__main__":
    main()
