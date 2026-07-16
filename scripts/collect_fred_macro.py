"""Daily FRED macro archiver -- free US-macro context for macro-crypto relative value.

Unlike the OI/LS and stablecoin clocks (which must ACCUMULATE forward days), FRED serves deep
history on day one, so this family is immediately backtestable against the crypto lake: each run
re-fetches the last ~800 observations per series and overwrites the archive (idempotent,
self-healing). Series chosen for crypto relevance, not macro completeness:

  DGS10     10y Treasury yield        (risk-free anchor / carry-vs-rates competition)
  T10Y2Y    2s10s curve               (macro regime / recession signal)
  VIXCLS    VIX                       (cross-asset risk appetite; crypto vol correlate)
  DTWEXBGS  broad dollar index        (USD liquidity; inverse crypto beta)
  WALCL     Fed balance sheet (W)     (system liquidity; the 2020-22 crypto liquidity driver)
  M2SL      M2 money supply (M)       (broad liquidity; slow regime context)

Key: data/secrets/fred.json {"key": "..."} or FRED_API_KEY env. No key -> graceful skip
(exit 0, cycle stays green). API host verified reachable from the VPS 2026-07-16 (the
registry's old "blocked" note was the website host, not api.stlouisfed.org).

    python scripts/collect_fred_macro.py
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

_KEYFILE = Path("data/secrets/fred.json")
_ARCHIVE = Path("data/fred_macro.json")
_WEB = Path("web/fred_macro.json")
_BASE = "https://api.stlouisfed.org/fred/series/observations"
_SERIES = ("DGS10", "T10Y2Y", "VIXCLS", "DTWEXBGS", "WALCL", "M2SL")
_LOOKBACK_DAYS = 1200                            # ~3y daily obs: enough for regime research


def _key() -> str | None:
    k = os.environ.get("FRED_API_KEY")
    if k:
        return k
    try:
        return str(json.loads(_KEYFILE.read_text("utf-8"))["key"])
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _fetch(key: str, sid: str) -> list[tuple[str, float]]:
    start = (datetime.now(tz=UTC) - timedelta(days=_LOOKBACK_DAYS)).date().isoformat()
    q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json",
                                "observation_start": start})
    req = urllib.request.Request(f"{_BASE}?{q}", headers={"User-Agent": "quant-fred/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        obs = json.loads(r.read()).get("observations", [])
    out: list[tuple[str, float]] = []
    for o in obs:
        v = o.get("value", ".")
        if v not in (".", "", None):                     # FRED encodes missing as "."
            out.append((str(o["date"]), float(v)))
    return out


def main() -> None:
    key = _key()
    if not key:
        print("fred-macro: no key (data/secrets/fred.json or FRED_API_KEY) -- skipped")
        return
    series: dict[str, list[tuple[str, float]]] = {}
    for sid in _SERIES:
        try:
            series[sid] = _fetch(key, sid)
        except Exception as e:                           # one dead series never kills the rest
            print(f"fred-macro: {sid} FAILED {e!r}"[:120])
    if not series:
        raise SystemExit("fred-macro: zero series fetched -- check the key")
    ts = datetime.now(tz=UTC).isoformat()
    _ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVE.write_text(json.dumps({"updated": ts, "series": series}), "utf-8")
    latest = {sid: {"date": rows[-1][0], "value": rows[-1][1],
                    "chg_30obs": (round(rows[-1][1] - rows[-31][1], 4)
                                  if len(rows) > 31 else None)}
              for sid, rows in series.items() if rows}
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps({
        "updated": ts, "latest": latest,
        "note": ("Free FRED macro context (macro-crypto relative value family). Deep history "
                 "from day one -- backtestable immediately, no forward clock needed."),
    }, indent=2), "utf-8")
    n = sum(len(r) for r in series.values())
    print(f"fred-macro: {len(series)}/{len(_SERIES)} series, {n} obs -> {_ARCHIVE}")


if __name__ == "__main__":
    main()
