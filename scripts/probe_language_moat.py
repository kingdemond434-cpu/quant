#!/usr/bin/env python3
"""LANGUAGE-MOAT PROBE (R0594) -- every regional seat assumes its language IS the moat, and until
now not one of them had tested it.

THE PREMISE UNDER TEST. The desk runs seven regional frontier seats on a shared assumption: that
material written in CN / RU / KR / JP / BR / AR is ground the English-speaking crowd cannot reach,
so digging it buys an information advantage. That is a real mechanism and for some regions it is
true. It is an ASSUMPTION, it is cheap to check, and checking it decides where a seat's hours go.

WHAT THE AR SEAT MEASURED (OP-075, 2026-08-13) AND WHY IT GENERALISES. AR-script repository search
returned arbitrage 1/0/0 and quant-trading 0, against CN 1174 / RU 24 / KR 6 -- while AR-REGION
developers who mention trading numbered ~99, with UAE (67) ABOVE the Korea control (59). Both
halves matter and neither alone is a finding: the population EXISTS, and it publishes in English.
Its output is therefore already inside the EN seat's ground, so an AR-language dig re-reads what
another seat already has. The seat was re-aimed on that measurement rather than on a hunch.

THE THREE QUERIES, AND THE THIRD IS WHAT MAKES IT A MEASUREMENT:

    native-key repo search     is there OUTPUT in this language?
    developer search BY LOCATION   is there a POPULATION in this region?
    sibling-language control   is the instrument working at all?

Without the control a zero is unreadable -- a language with no output and a language whose queries
the API rejected produce the same number, and only one of them is a finding. Without the location
query, "no output" cannot be told from "no people", and those demand opposite responses: re-aim
the seat, or accept that this ground is genuinely empty and go elsewhere.

WHAT A NEGATIVE RESULT DOES AND DOES NOT AUTHORISE. MOAT-UNSUPPORTED means the LANGUAGE is not the
barrier. It does NOT mean the region is dead, and it is never grounds for cutting a seat (L1.25a:
a null streak throttles nothing). It re-aims: hunt the region's population where it actually
writes, and stop paying a translation tax for ground another seat already holds.

    python scripts/probe_language_moat.py [--region jp] [--sleep 7]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

OUT = _ROOT / "data/language_moat_probe.json"
_API = "https://api.github.com/search/{kind}?q={q}&per_page=1"
_UA = {"User-Agent": "quant-desk language-moat-probe",
       "Accept": "application/vnd.github+json"}

#: THE VOCABULARY IS MT5, NOT CRYPTO (principal's 2026-08-18 universe mandate). The AR measurement
#: that produced this probe used crypto-arbitrage keys; re-running those would be hunting a banned
#: universe to answer a universe-independent question. What is being measured is whether a
#: LANGUAGE carries output at all, so the keys must simply be terms this desk's actual market
#: would be discussed in: MetaTrader, expert advisors, FX, gold.
#:
#: `control` is the EN sibling for the SAME concept. It is the instrument check: if the control
#: also returns zero, the query shape is broken and every zero beside it is uninterpretable.
REGIONS: dict[str, dict[str, Any]] = {
    "jp": {"keys": ["MT5 エキスパートアドバイザ", "FX 自動売買 MetaTrader"],
           "location": "japan", "control": "MetaTrader expert advisor"},
    "cn": {"keys": ["外汇 EA 量化", "黄金 交易 策略 MT5"],
           "location": "china", "control": "MetaTrader expert advisor"},
    "ru": {"keys": ["форекс советник MT5", "торговый робот MetaTrader"],
           "location": "russia", "control": "MetaTrader expert advisor"},
    "kr": {"keys": ["해외선물 자동매매", "FX마진 전략"],
           "location": "korea", "control": "MetaTrader expert advisor"},
    "br": {"keys": ["robô forex MetaTrader", "estratégia ouro MT5"],
           "location": "brazil", "control": "MetaTrader expert advisor"},
    "ar": {"keys": ["فوركس تداول آلي", "مستشار خبير ميتاتريدر"],
           "location": "united arab emirates", "control": "MetaTrader expert advisor"},
}

#: Native-language repositories at or below this count read as NO OUTPUT. Not a bar anything has
#: to clear -- nothing is promoted, funded or cut on it; it is the threshold for printing
#: MOAT-UNSUPPORTED next to a pair of measured counts.
_NO_OUTPUT: int = 5

#: Developers found by location, at or above which the POPULATION is real. Calibrated against the
#: AR run's own numbers -- UAE 67 above a Korea control of 59 -- which is what made "they exist and
#: write in English" a measurement rather than a guess. Re-derived here 2026-08-20 on the same
#: query shape: UAE 113, Korea 60, Japan 56, Brazil 82. Every real region sits 3-5x above this,
#: so the threshold separates "a population" from "a failed query", which is all it is for.
_POPULATION: int = 20

#: Unauthenticated GitHub search allows ~10 requests/minute. Slower than needed on purpose: a
#: probe that trips the rate limit measures the rate limit.
_SLEEP: float = 7.0

_PASSING = ("OK", "PARTIAL")


def search(kind: str, query: str, *, timeout: int = 25) -> int | str:
    """Total hits, or a STRING naming why the count is unavailable.

    THE RETURN TYPE IS THE POINT AND IT IS DELIBERATELY UNION. A rate-limited or rejected query
    that returned 0 would be indistinguishable from a language with no output -- the same number,
    opposite meanings, and the one direction that would retire a region's ground by accident
    (WS-005). Every failure is named and carried through to the report as a non-number.
    """
    url = _API.format(kind=kind, q=urllib.parse.quote(query))
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=_UA), timeout=timeout) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return f"HTTP-{exc.code}" + (" (rate limit -- NOT a zero)" if exc.code in (403, 429)
                                     else "")
    except Exception as exc:                 # DNS, TLS, timeout, refused: reported, never swallowed
        return f"{type(exc).__name__}"
    count = body.get("total_count")
    return int(count) if isinstance(count, int) else "NO-COUNT-FIELD"


def probe_region(region: str, spec: dict[str, Any], *, sleep: float = _SLEEP) -> dict[str, Any]:
    """One region's three-query probe, graded."""
    native: dict[str, int | str] = {}
    for key in spec["keys"]:
        native[key] = search("repositories", key)
        time.sleep(sleep)
    # THE LOCATION IS QUOTED AND THE TERM IS BROAD, AND BOTH ARE REPAIRS THE FIRST LIVE RUN
    # FORCED. Unquoted, `location:united arab emirates trading` parses as location:united plus
    # three loose words and returned 0 developers for the AR region -- a malformed query
    # rendering as an empty population, which is the instrument fault this probe exists to avoid
    # committing. And `forex` is too narrow to reproduce OP-075's construction: quoted, with
    # `trading`, the Korea control comes back 60 against the 59 that measurement recorded a week
    # earlier, and UAE 113 against its 67. Matching the original construction is what makes the
    # threshold below calibrated rather than invented.
    people = search("users", f'location:"{spec["location"]}" trading')
    time.sleep(sleep)
    control = search("repositories", spec["control"])

    counted = [v for v in native.values() if isinstance(v, int)]
    rec: dict[str, Any] = {
        "region": region, "native": native, "developers": people, "control": control,
        "native_total": sum(counted) if counted else None,
    }

    if not counted or not isinstance(control, int):
        rec["verdict"] = "UNMEASURED"
        rec["why"] = ("the native queries or the control did not return a count, so a zero here "
                      "would be a fact about this probe rather than about the language")
        return rec
    if control <= _NO_OUTPUT:
        rec["verdict"] = "INSTRUMENT-BROKEN"
        rec["why"] = (f"the EN sibling control returned {control}, at or below the no-output "
                      "threshold. The query shape is wrong, so every native zero beside it is "
                      "uninterpretable -- fix the control before reading anything else here")
        return rec

    total = rec["native_total"]
    if total > _NO_OUTPUT:
        rec["verdict"] = "MOAT-SUPPORTED"
        rec["why"] = (f"{total} native-language repositor(ies) against an EN control of "
                      f"{control}: this language carries output of its own, so digging it is "
                      "reaching material the EN seat does not already hold")
    elif isinstance(people, int) and people >= _POPULATION:
        rec["verdict"] = "MOAT-UNSUPPORTED"
        rec["why"] = (f"{total} native-language repositor(ies) but {people} developer(s) in the "
                      "region: the population EXISTS and publishes in English, so its output is "
                      "already inside the EN seat's ground. RE-AIM the seat -- this is not "
                      "grounds for cutting it (L1.25a)")
    else:
        rec["verdict"] = "THIN-EVERYWHERE"
        rec["why"] = (f"{total} native repositor(ies) and {people} developer(s): neither output "
                      "nor population is established here, which is a statement about this probe's "
                      "reach and not yet about the region")
    return rec


def report(regions: dict[str, dict[str, Any]] | None = None, *,
           sleep: float = _SLEEP) -> dict[str, Any]:
    """Probe every region and roll up."""
    regions = REGIONS if regions is None else regions
    rows = [probe_region(r, spec, sleep=sleep) for r, spec in sorted(regions.items())]
    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    measured = [r for r in rows if r["verdict"] in ("MOAT-SUPPORTED", "MOAT-UNSUPPORTED")]

    if not rows:
        status, nxt = "UNMEASURED", "no regions to probe -- the scope discovery returned nothing"
    elif not measured:
        # NOT OK. A verdict about language moats earned over zero graded regions is vacuous
        # (L1.57), and here it would argue for leaving every seat exactly as it is.
        status, nxt = "UNMEASURED", (
            f"{len(rows)} region(s) probed and NONE graded ({tally}). This says the probe could "
            "not reach GitHub search or its query shapes are wrong -- it does NOT say every "
            "seat's premise holds (L1.28a). Re-run when the network allows.")
    else:
        unsupported = [r["region"] for r in measured if r["verdict"] == "MOAT-UNSUPPORTED"]
        status = "OK" if len(measured) == len(rows) else "PARTIAL"
        nxt = (f"{len(measured)}/{len(rows)} region(s) graded"
               + (f"; language-is-the-moat UNSUPPORTED for: {', '.join(unsupported)} -- re-aim "
                  "those seats at where the population actually writes, and do NOT cut them"
                  if unsupported else "; every graded region carries native-language output"))
    return {"status": status, "n_regions": len(rows), "n_graded": len(measured),
            "tally": tally, "regions": rows, "next_action": nxt}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description="does this seat's language actually gate its ground?")
    ap.add_argument("--region", action="append", help="probe only these (default: all)")
    ap.add_argument("--sleep", type=float, default=_SLEEP, help="seconds between API calls")
    ap.add_argument("--report-only", action="store_true", help="always exit 0")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    chosen = ({r: REGIONS[r] for r in args.region if r in REGIONS} if args.region else None)
    rep = report(chosen, sleep=args.sleep)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, indent=1, ensure_ascii=False), "utf-8")
    except OSError as exc:
        print(f"  could not write {OUT}: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(rep, indent=1, ensure_ascii=False))
    else:
        print(f"language moat: {rep['status']} -- {rep['n_graded']}/{rep['n_regions']} graded")
        for r in rep["regions"]:
            print(f"  [{r['verdict']:<17}] {r['region']}  native={r['native_total']} "
                  f"devs={r['developers']} control={r['control']}")
            print(f"                      {r['why'][:110]}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_graded"], of="regions graded",
                      fence="probe_language_moat.py")


if __name__ == "__main__":
    sys.exit(main())
