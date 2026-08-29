"""Fetch the free public observables that were being called "unavailable".

WHY THIS EXISTS (principal, 2026-08-29: "why don't you fetch data, it's doable, you're coping")

That was correct and I was wrong. Three mechanisms had been marked UNMEASURABLE on the grounds
that "this desk has no options data / no event calendar / no fixing timestamps". Every one of
those was a statement about what the desk HELD, and I never checked what it could REACH. Probed
directly, all three have free public sources with no API key:

    CBOE delayed quotes   28,892 SPX contracts carrying gamma, delta, vega, IV and open
                          interest -- everything needed to compute real dealer gamma exposure
    CBOE VIX history      daily OHLC back to 1990, so implied volatility is available
                          HISTORICALLY, not just going forward
    Fed FOMC calendar     scheduled meeting dates as JSON
    CFTC public reporting COT and TFF live, so positioning stops depending on stale parquets

"We do not have X" and "X cannot be obtained" are different claims, and treating the first as the
second is how a desk quietly shrinks its own universe.

THE ONE HONEST LIMIT, and it shapes everything below: CBOE delayed quotes are a SNAPSHOT of now.
There is no history endpoint, so a gamma-exposure series exists only from the moment this script
starts recording. That makes options_hedging a FORWARD-ONLY observable -- which is not a defect,
it is the truth about the data, and it is exactly the situation the desk's forward-shadow
machinery already exists to handle. VIX is different: its history is real, so implied-vol
mechanisms are testable on the full sample today.

EVERY SNAPSHOT IS STAMPED WITH ITS FETCH TIME, never with the bar it will later be joined to.
A gamma reading taken at 12:50 is knowable at 12:50 and not before, and the adapters lag it
accordingly. Writing a snapshot under a market timestamp is the single easiest way to
manufacture a spectacular backtest from honest data.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OBS = ROOT / "desks" / "mt5" / "data" / "observables"
OUT = ROOT / "data" / "free_observables.json"

_UA = {"User-Agent": "Mozilla/5.0 (quant-desk research fetcher)"}

#: Sources, each with where it lands and what it unblocks. Adding one here is the whole
#: onboarding: the adapters read from `OBS` and do not know about HTTP.
SOURCES: dict[str, dict[str, str]] = {
    "cboe_spx_options": {
        "url": "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json",
        "unblocks": "options_hedging (dealer gamma exposure)",
        "kind": "snapshot",
    },
    "cboe_vix_history": {
        "url": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
        "unblocks": "implied volatility, realised-vs-implied divergence",
        "kind": "history",
    },
    "fomc_calendar": {
        "url": "https://www.federalreserve.gov/json/calendar.json",
        "unblocks": "macro_release (scheduled FOMC dates)",
        "kind": "calendar",
    },
    "cftc_cot_live": {
        "url": ("https://publicreporting.cftc.gov/resource/6dca-aqww.json"
                "?$limit=5000&$order=report_date_as_yyyy_mm_dd%20DESC"),
        "unblocks": "positioning_extreme (live COT, replacing stale parquets)",
        "kind": "history",
    },
}


def _get(url: str, timeout: int = 90) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return bytes(r.read())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None


def fetch_cboe_options(raw: bytes, now: datetime) -> dict[str, Any]:
    """Dealer gamma exposure from the full SPX chain.

    GEX = sum over contracts of gamma * open_interest * 100 * spot^2 * 0.01, with CALLS POSITIVE
    and PUTS NEGATIVE -- the standard dealer convention, on the assumption dealers are long calls
    and short puts against customer flow. That assumption is the model, and it is stated here
    rather than buried: a different assumption flips the sign of every downstream result.
    """
    d = json.loads(raw)
    data = d["data"]
    spot = float(data.get("current_price") or 0.0)
    call_gex = put_gex = 0.0
    n_call = n_put = 0
    for o in data.get("options", []):
        try:
            gamma = float(o.get("gamma") or 0.0)
            oi = float(o.get("open_interest") or 0.0)
        except (TypeError, ValueError):
            continue
        if gamma == 0.0 or oi == 0.0:
            continue
        # The contract symbol encodes the right: ...YYMMDD[C|P]00001000
        sym = str(o.get("option") or "")
        is_call = "C" in sym[-9:]
        notional = gamma * oi * 100.0 * (spot ** 2) * 0.01
        if is_call:
            call_gex += notional
            n_call += 1
        else:
            put_gex += notional
            n_put += 1
    return {
        "fetched_at": now.isoformat(timespec="seconds"),
        "source_timestamp": d.get("timestamp"),
        "spot": spot,
        "call_gex": call_gex, "put_gex": put_gex,
        "net_gex": call_gex - put_gex,
        "contracts": n_call + n_put, "calls": n_call, "puts": n_put,
        "convention": ("calls positive, puts negative -- dealers assumed long calls and short "
                       "puts against customer flow. This assumption IS the model; flipping it "
                       "flips the sign of every result that uses net_gex."),
        "pit_note": ("knowable at fetched_at, NOT at source_timestamp and NOT at any market bar. "
                     "Adapters must lag to fetched_at."),
    }


def fetch_vix_history(raw: bytes, now: datetime) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))
    keep = [{"date": r.get("DATE"), "close": r.get("CLOSE")} for r in rows if r.get("DATE")]
    return {"fetched_at": now.isoformat(timespec="seconds"), "rows": len(keep),
            "first": keep[0]["date"] if keep else None,
            "last": keep[-1]["date"] if keep else None,
            "series": keep}


def fetch_fomc(raw: bytes, now: datetime) -> dict[str, Any]:
    d = json.loads(raw.decode("utf-8-sig", "replace"))
    events = d.get("events", []) or []
    return {"fetched_at": now.isoformat(timespec="seconds"), "events": len(events),
            "sample": events[:3], "raw": events}


def fetch_cot(raw: bytes, now: datetime) -> dict[str, Any]:
    rows = json.loads(raw)
    return {"fetched_at": now.isoformat(timespec="seconds"), "rows": len(rows),
            "markets": len({r.get("market_and_exchange_names") for r in rows}),
            "raw": rows}


_PARSERS = {
    "cboe_spx_options": fetch_cboe_options,
    "cboe_vix_history": fetch_vix_history,
    "fomc_calendar": fetch_fomc,
    "cftc_cot_live": fetch_cot,
}


def main() -> int:
    now = datetime.now(tz=UTC)
    OBS.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"fetched_at": now.isoformat(timespec="seconds"), "sources": {}}

    print(f"FREE OBSERVABLES {now.isoformat(timespec='seconds')}")
    for name, meta in SOURCES.items():
        raw = _get(meta["url"])
        if raw is None:
            report["sources"][name] = {"ok": False, "why": "unreachable",
                                       "unblocks": meta["unblocks"]}
            print(f"  FAIL {name:22s} unreachable -- {meta['unblocks']}")
            continue
        try:
            parsed = _PARSERS[name](raw, now)
        except Exception as exc:
            report["sources"][name] = {"ok": False,
                                       "why": f"{type(exc).__name__}: {str(exc)[:110]}"}
            print(f"  FAIL {name:22s} parse: {type(exc).__name__}")
            continue

        # SNAPSHOTS APPEND, HISTORIES REPLACE. A gamma reading is one observation of a series
        # this desk is building; overwriting it would discard the only history that will ever
        # exist, because the source has no history endpoint.
        if meta["kind"] == "snapshot":
            path = OBS / f"{name}.jsonl"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(parsed) + "\n")
            n = sum(1 for _ in path.open(encoding="utf-8"))
            summary = {"ok": True, "path": str(path.relative_to(ROOT)), "observations": n}
            print(f"  ok   {name:22s} appended, {n} observation(s) -- {meta['unblocks']}")
        else:
            path = OBS / f"{name}.json"
            path.write_text(json.dumps(parsed, indent=1), "utf-8")
            summary = {"ok": True, "path": str(path.relative_to(ROOT)),
                       "rows": parsed.get("rows") or parsed.get("events")}
            print(f"  ok   {name:22s} {summary['rows']} row(s) -- {meta['unblocks']}")
        summary["unblocks"] = meta["unblocks"]
        report["sources"][name] = summary

    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    ok = sum(1 for v in report["sources"].values() if v.get("ok"))
    print(f"\n  {ok}/{len(SOURCES)} sources fetched  -> {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
