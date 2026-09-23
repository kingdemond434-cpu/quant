"""Every "we cannot measure that" is a search failure until proven otherwise. Re-litigate it.

WHY THIS EXISTS (principal, 2026-08-29)

    "the desk should always force itself to believe it's coping -- nothing is unmeasurable or
     blocked, you're just not searching hard enough"

That is now law here, and it earned the status the same day by catching this session twice:

    "this desk has no options data"      CBOE publishes 28,892 SPX contracts with gamma, IV and
                                         open interest. Free. No API key.
    "no event calendar exists"           The Fed publishes one as JSON. The real failure was a
                                         PARSER that guessed `date`/`startDate` when the schema
                                         says `month` + `days` + `time`, and reported 2,012
                                         dateable events as unusable.

Both were stated with total confidence and both were wrong, and the second is the more
instructive: the data was already on disk. "Unmeasurable" had become a place to put things that
were merely difficult, and nothing ever went back to check.

THE ASYMMETRY THAT MAKES THIS LAW WORTH ENFORCING. A false "unavailable" is invisible and
permanent -- it silently deletes a mechanism from the desk's universe and nothing ever contradicts
it. A false "available" gets caught immediately by the first adapter that tries to read the file.
So the burden of proof belongs entirely on the negative claim.

WHAT THIS DEMANDS. An adapter may only report UNAVAILABLE if it records WHAT IT SEARCHED. Not
what was missing -- what was LOOKED FOR. "carry_state.json absent" is a fact; "no free source of
dealer positioning exists" is a claim that requires evidence, and without a search record it is
indistinguishable from nobody having looked.

IT RE-PROBES ON A CLOCK. A source that 403'd last month may be open now; a schema that defeated a
parser is one afternoon of work away from yielding. An unmeasurable claim that is never revisited
is a permanent hole in the universe, so this reopens every one of them on a schedule.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "unmeasurable_claims.json"

_UA = {"User-Agent": "Mozilla/5.0 (quant-desk availability probe)"}

#: Candidate free sources per blocked observable. This list is the SEARCH RECORD: an observable
#: with no entry here has not been searched for, which is a different and worse state than
#: "searched and not found".
#:
#: Adding a row costs nothing and is how a claim gets re-litigated. Removing one requires evidence
#: that the source is genuinely gone.
SEARCH_SPACE: dict[str, list[tuple[str, str]]] = {
    "fixing_window_timestamps": [
        ("ECB euro reference rates (14:15 CET daily)",
         "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
         "?lastNObservations=1&format=jsondata"),
        ("Treasury FiscalData exchange rates",
         "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/"
         "rates_of_exchange?page[size]=1"),
    ],
    # The second row here was `api.binance.com/api/v3/depth` (labelled "crypto reference only").
    # Retired 2026-09-05: the crypto-exchange universe is closed to this desk, and a search space
    # is a RESEARCH CHANNEL -- a row here tells the desk where to go looking. It is replaced, not
    # merely deleted, because dropping it would quietly halve the evidence behind "order-flow
    # depth is measurable" and make the claim easier to re-assert as unmeasurable. CFTC TFF
    # carries dealer/asset-manager gross positioning per contract, which is depth-of-participation
    # on the MT5 universe's own instruments rather than on a venue this desk may not trade.
    "order_flow_depth": [
        ("CBOE delayed book quotes",
         "https://cdn.cboe.com/api/global/delayed_quotes/quotes/_SPX.json"),
        ("CFTC TFF gross positioning by trader class (MT5 futures-linked instruments)",
         "https://publicreporting.cftc.gov/resource/gpe5-46if.json?$limit=1"),
    ],
    "term_structure": [
        ("Treasury par yield curve",
         "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/"
         "avg_interest_rates?page[size]=1"),
        ("ECB yield curve",
         "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y"
         "?lastNObservations=1&format=jsondata"),
    ],
    "macro_surprise_consensus": [
        ("Fed calendar (scheduled events)",
         "https://www.federalreserve.gov/json/calendar.json"),
        ("World Bank indicators", "https://api.worldbank.org/v2/country/US/indicator/"
                                  "FP.CPI.TOTL.ZG?format=json&per_page=1"),
    ],
    "dealer_positioning": [
        ("CFTC COT public reporting",
         "https://publicreporting.cftc.gov/resource/6dca-aqww.json?$limit=1"),
        ("CFTC TFF financial futures",
         "https://publicreporting.cftc.gov/resource/gpe5-46if.json?$limit=1"),
    ],
}


def _probe(url: str, timeout: int = 25) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(200)
        return True, f"HTTP {r.status}, {len(body)}b"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {str(e.reason)[:40]}"
    except Exception as e:
        return False, f"{type(e).__name__}"


def _unavailable_claims() -> list[dict[str, Any]]:
    """Every place the codebase asserts something cannot be measured."""
    claims: list[dict[str, Any]] = []
    try:
        from libs.research.measurement import GENERIC_CONTRACTS

        for name, c in GENERIC_CONTRACTS.items():
            if c.measurement_class == "UNMEASURABLE":
                claims.append({"observable": name, "where": "measurement.GENERIC_CONTRACTS",
                               "claim": c.justification[:150]})
    except ImportError:
        pass

    # Any adapter that can name a requirement it does not have is a claim too.
    try:
        from libs.research_os.adapters import REGISTRY

        for mech, ad in REGISTRY.all().items():
            missing = [r for r in ad.requires
                       if "<" not in r and not (ROOT / r).exists()]
            if missing:
                claims.append({"observable": mech, "where": ad.__class__.__name__,
                               "claim": f"requires {missing}"})
    except ImportError:
        pass
    return claims


def main() -> int:
    now = datetime.now(tz=UTC)
    claims = _unavailable_claims()

    print(f"UNMEASURABLE CLAIMS {now.isoformat(timespec='seconds')}")
    print("  LAW: a negative claim carries the burden of proof. 'We cannot measure X' is a")
    print("       search failure until a search record says otherwise.")
    print(f"\n  {len(claims)} standing claim(s) that something cannot be measured:")
    for c in claims:
        print(f"    {c['observable']:26s} [{c['where']}]")

    print(f"\n  RE-PROBING {sum(len(v) for v in SEARCH_SPACE.values())} candidate free sources:")
    findings: dict[str, Any] = {}
    reachable_total = 0
    for observable, sources in SEARCH_SPACE.items():
        rows = []
        for label, url in sources:
            ok, detail = _probe(url)
            reachable_total += int(ok)
            rows.append({"source": label, "url": url, "reachable": ok, "detail": detail})
            print(f"    {'OK  ' if ok else '--  '} {observable:26s} {label[:46]:48s} {detail}")
        findings[observable] = rows

    #: A claim is CONTRADICTED when a source for its observable answers. That is not proof the
    #: mechanism is measurable -- parsing and PIT alignment are still work -- but it is proof the
    #: claim "no data exists" was false, which is the claim being audited.
    contradicted = [obs for obs, rows in findings.items() if any(r["reachable"] for r in rows)]

    report = {
        "checked_at": now.isoformat(timespec="seconds"),
        "standing_claims": claims,
        "probes": findings,
        "contradicted": contradicted,
        "law": ("nothing is unmeasurable until a recorded search says so; a false 'unavailable' "
                "is invisible and permanent, while a false 'available' is caught by the first "
                "adapter that tries to read the file"),
    }
    OUT.write_text(json.dumps(report, indent=1), "utf-8")

    if contradicted:
        print(f"\n  CONTRADICTED ({len(contradicted)}) -- a free source for these ANSWERED, so "
              f"'no data exists' is false for:")
        for obs in contradicted:
            live = [r["source"] for r in findings[obs] if r["reachable"]]
            print(f"    {obs:26s} <- {live[0][:60]}")
        print("    Parsing and PIT alignment are still work. 'No data' is no longer the reason.")
    print(f"\n  {reachable_total} source(s) reachable  -> {OUT}")
    # Non-zero when a standing claim is contradicted: that is a task, not a status quo.
    return 1 if contradicted else 0


if __name__ == "__main__":
    raise SystemExit(main())
