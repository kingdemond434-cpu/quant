# Owner permission attestation, 2026-11-17 20:38-20:39Z (zuck; recorded by Global data)

zuck, in the project chat:
- 20:38:20Z "they gave permission"
- 20:38:30Z "all of them did"
- 20:38:44Z "no i lost it no"
- 20:38:57Z "they gave permission its on me stop being timid"
- 20:39:06Z "do it"

## What this is
The owner states that the publishers below granted permission for automated use, that the permission emails were
lost, and that he takes responsibility. The desk records this as an OWNER ATTESTATION. It is not a verified
publisher grant. Every row carries provenance `permission=owner_attestation_2026-11-17` so the basis is never hidden.

## Scope: these sources only
- HKEX Stock Connect flows (northbound/southbound)
- BoJ ETF purchases, and Korea's national pension (NPS) flows
- BoJ bond-buying operations (JGB purchases)
- SNB sight deposits / intervention proxy
- Chicago Fed financial conditions index (NFCI/ANFCI), from the Chicago Fed's own site only, never via FRED
- Exchange options open interest / gamma data (the sources fenced in the 11-13 options/gamma ruling)

NOT covered: FRED/ALFRED, Reddit fetching, prop-firm sites, archive.org/Wayback, YouTube, UN Comtrade, Yahoo,
Dukascopy, ICE, SPDR, IMF PortWatch.

## What still holds
- robots_gate fails closed.
- Honest generic UA and polite rate limits.
- No login, paywall, CAPTCHA or block bypass; a 401/403/429/451 is still a hard stop.
- No paid APIs.

## Reversible
Each source is gated by its own flag in one data file (desks/mt5/data/owner_permissions.json). Flipping a flag to
false re-fences that source on the next pass, with a missed_growth line. If a publisher objects, its flag goes false
the same day.

Owner: Global data discovery and use. This is an agent's record of the owner's statement, not legal advice.
