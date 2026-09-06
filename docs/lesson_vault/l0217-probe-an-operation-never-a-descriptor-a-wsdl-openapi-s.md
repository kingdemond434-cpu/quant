---
id: L0217
cost: blind
tags: ["free-data"]
---

# L0217

Probe an OPERATION, never a DESCRIPTOR. A WSDL/OpenAPI spec/SDMX codelist is a static file that outlives its service: mnb.hu/arfolyamok.asmx?WSDL serves HTTP 200 and a well-formed descriptor naming 6 operations, and ALL SIX 404 on SOAP 1.1, SOAP 1.2, HTTP-GET and HTTP-POST. Any collector health check aimed at the spec reports six operations available on a handler that cannot serve one row.

## Evidence

docs/research/data_axis_watchlist.md run (s) ITEM 1a; data/data_universe_map.json mnb_hu_soap_arfolyamok; commit 353f9218 2026-08-28

## Tags

#free-data

## Related

- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
