"""Wires all 25 external discovery channels.

Runs all miners and saves combined discoveries.
Can be invoked standalone or imported by hourly_controller.
"""

import json
import multiprocessing
import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path

# Hard wall-clock budget per miner (seconds). A miner that exceeds it is killed
# so one hung channel can never stall the hourly pipeline. 2026-08-31: academic
# miner was observed spinning CPU for 20+ min and never returning.
MINER_TIMEOUT_S = int(os.environ.get("QUANT_MINER_TIMEOUT_S", "180"))
process_ctx = multiprocessing.get_context("spawn")


def _run_miner_inner(name, fn_ref, q):
    try:
        try:
            from side_channels import net_gate
        except ModuleNotFoundError:
            import net_gate
        net_gate.install()            # every request this miner sends goes through the door
        disc = fn_ref()
        q.put(("ok", disc))
    except Exception as e:
        q.put(("err", type(e).__name__ + ": " + str(e)))


def _run_miner(name, fn):
    """Run one miner under a hard timeout. Returns ("ok", discs) | ("err", msg) | ("timeout", why).

    EVERY PATH RETURNS A PAIR. The timeout path returned a 1-tuple while the caller unpacks two,
    so a single slow miner raised ValueError out of run_all_miners and killed the whole pipeline
    before STEP 1 finished -- no discover, no backtest, no gates, no certify. The youtube miner
    times out at 180s on most runs, so full-pipeline had been dying on it every hour.
    """
    q = process_ctx.Queue()
    p = process_ctx.Process(target=_run_miner_inner, args=(name, fn, q), daemon=True)
    p.start()
    p.join(timeout=MINER_TIMEOUT_S)
    if p.is_alive():
        p.terminate()
        p.join(5)
        if p.is_alive():
            p.kill()
            p.join()
        print(f"  {name}: TIMED OUT after {MINER_TIMEOUT_S}s (killed)")
        return ("timeout", f"killed after {MINER_TIMEOUT_S}s")
    try:
        return q.get(timeout=5)
    except Exception:
        return ("err", "no result after process ended")

# Ensure side_channels dir is on path for direct imports
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

# Only channels with a clear machine-access verdict are imported at all. A channel blocked on its
# owner's terms is listed in BLOCKED_ON_TERMS below with the reason and never loaded, so it
# cannot fetch even if the allowlist is widened by mistake (Hourly pass ask, 2026-11-13).
from central_bank_miner import run_and_save as central_bank_mine
from correlation_miner import run_and_save as correlation_mine
from cot_miner import run_and_save as cot_mine
from github_miner import run_and_save as github_mine
from seasonality_miner import run_and_save as seasonality_mine
from sec_edgar_miner import run_and_save as sec_edgar_mine
from weather_miner import run_and_save as weather_mine

ALL_MINERS = [
    ("github", github_mine),            # GitHub REST API, token from env
    ("central_bank", central_bank_mine),  # central banks' own RSS feeds
    ("cot", cot_mine),                  # CFTC Public Reporting (Socrata), US gov open data
    ("sec_edgar", sec_edgar_mine),      # data.sec.gov JSON, SEC fair-access UA
    ("correlations", correlation_mine),  # local bars
    ("seasonality", seasonality_mine),  # local bars
    ("weather", weather_mine),          # NOAA NHC (US gov); Open-Meteo refused at the door
]

#: Every channel taken out of the suite on its owner's terms, by name, with the reason. The
#: summary reports each as BLOCKED_ON_TERMS, so a removed channel is never a silent zero. Each
#: carries its missed-growth line: what the desk loses is that channel's discoveries, and the
#: free stand-in that replaces it where one exists.
BLOCKED_ON_TERMS: dict[str, str] = {
    # Terms READ and refusing (2026-11-13):
    "youtube": "hard rule: the box never contacts YouTube; no YouTube API key",
    "earnings": "Yahoo terms 2(d)(ix): no automated collection without prior permission "
                "(stand-in: sec_edgar filings)",
    "quantconnect": "QuantConnect terms 2.6 bar extracting data by any means, API included "
                    "(stand-in: github)",
    "google_trends": "trends.google.com robots disallows /explore?; Google terms bar automated "
                     "access against robots (stand-in: none free)",
    "mql5_codebase": "mql5.com robots disallows /code/viewcode/ and /code/download/; site terms "
                     "unreadable to an honest agent, so unclear fails closed (#262)",
    # Terms UNREAD or UNCLEAR for commercial automated use, so they fail closed until read:
    "mql5_articles": "MQL5 terms unreadable to an honest agent: unclear fails closed (#262)",
    "mql5_signals": "MQL5 terms unreadable to an honest agent: unclear fails closed (#262)",
    "mql5_forum": "MQL5 terms unreadable to an honest agent: unclear fails closed (#262)",
    "tradingview": "TradingView terms not confirmed for automated use: fails closed",
    "reddit": "Reddit Data API terms page refuses automated readers; commercial use needs an "
              "agreement: fails closed",
    "forexfactory": "Forex Factory terms unreadable; feed has no terms of its own: fails closed "
                    "(stand-in: central banks' own calendars)",
    "aaii": "AAII survey terms not confirmed (member content): fails closed "
            "(stand-in: cot positioning, FFAJ retail FX)",
    "fear_greed": "cnn.com robots refuses automated readers; CNN terms unread: fails closed",
    "investing": "Investing.com terms not confirmed; robots fences several paths: fails closed",
    "shipping": "Trading Economics / Investing.com terms not confirmed: fails closed "
                "(stand-in: IMF PortWatch route)",
    "china": "Zhihu / Eastmoney off-limits (#1091; stand-in: asia_collector official sources)",
    "korea": "Naver robots and terms refuse automated readers: fails closed",
    "academic": "arXiv API terms allow personal or research use and do not address commercial "
                "use; SSRN terms unreadable: fails closed until read",
}


#: Channels that need a configured credential or contact before they may fetch at all.
REQUIRES_ENV = {"sec_edgar": "QUANT_EDGAR_UA"}


def allowed_channels() -> set[str] | None:
    """QUANT_MINERS_ALLOW (comma-separated channel names) or None for every channel.

    The box sets it to the clear-access channels only (official APIs, open data and local
    computation); a channel outside it is reported SET_ASIDE by name, never as a zero."""
    raw = os.environ.get("QUANT_MINERS_ALLOW", "").strip()
    if not raw:
        return None
    return {x.strip() for x in raw.split(",") if x.strip()}


def run_all_miners() -> dict:
    results = {}
    total = 0
    allow = allowed_channels()
    set_aside = {}
    for name, fn in ALL_MINERS:
        if allow is not None and name not in allow:
            set_aside[name] = "not in QUANT_MINERS_ALLOW (no clear machine-access terms on this host)"
            results[name] = {"status": "SET_ASIDE", "why": set_aside[name]}
            continue
        need = REQUIRES_ENV.get(name)
        if need and not os.environ.get(need):
            set_aside[name] = f"{need} is not configured"
            results[name] = {"status": "SET_ASIDE", "why": set_aside[name]}
            continue
        status, payload = _run_miner(name, fn)
        if status == "ok":
            disc = payload
            results[name] = {"count": len(disc), "discoveries": disc}
            total += len(disc)
            print(f"  {name}: {len(disc)} discoveries")
        elif status == "timeout":
            results[name] = {"count": 0, "error": "timeout_killed", "discoveries": []}
        else:
            results[name] = {"count": 0, "error": payload}
            print(f"  {name}: FAILED ({payload})")
    for name, why in set_aside.items():
        print(f"  {name}: SET_ASIDE ({why})")
    for name, why in BLOCKED_ON_TERMS.items():
        results[name] = {"status": "BLOCKED_ON_TERMS", "why": why}
        print(f"  {name}: BLOCKED_ON_TERMS ({why})")

    ok = sum(1 for r in results.values() if (r.get("count") or 0) > 0)
    results["summary"] = {
        "total_miners": len(ALL_MINERS),
        "ran": len(ALL_MINERS) - len(set_aside),
        "set_aside": sorted(set_aside),
        "blocked_on_terms": sorted(BLOCKED_ON_TERMS),
        "producing": sorted(k for k, r in results.items()
                            if isinstance(r, dict) and (r.get("count") or 0) > 0),
        "total_discoveries": total,
        "successful_miners": ok,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return results


def write_atomic(path: Path, text: str) -> None:
    """tmp file in the same directory, then os.replace: a reader never sees a half-written
    file. A read-only target (Windows refuses os.replace onto one) is made writable first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


if __name__ == "__main__":
    print("=== EXTERNAL DISCOVERY: ALL CHANNELS ===")
    r = run_all_miners()
    s = r["summary"]
    print(f"\n{s['successful_miners']}/{s['total_miners']} miners returned {s['total_discoveries']} discoveries")

    out = Path(__file__).resolve().parent.parent / "data" / "intelligence" / "latest_discoveries.json"
    write_atomic(out, json.dumps(r, indent=2, default=str))
    print(f"Saved to {out}")
