---
id: L0179
cost: blind
enforced_by: desks/mt5/tests/test_identity_venue.py::test_identity_survives_a_terminal_outage
---

# L0179

An identity check must hash WHAT a thing is, never HOW it reached you. A route (file path, cache name, transport) sitting in a provenance field is a false-positive machine AND blind to the real change: it fires on every outage and cannot see two different venues arriving by the same route.

## Evidence

shadow_forward froze data_venue=str(bars.source); 195 IDENTITY BROKEN lines in desks/mt5/logs/shadow.log, data_venue named in 195/195, so the 14-day forward window never survived one day and nothing could ever promote. Meanwhile broker_info.json read FusionMarkets-Demo while every frozen row read -Live -- a real venue change the route string could not see. Fixed e40151e5.

## Enforced by

`desks/mt5/tests/test_identity_venue.py::test_identity_survives_a_terminal_outage`

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
