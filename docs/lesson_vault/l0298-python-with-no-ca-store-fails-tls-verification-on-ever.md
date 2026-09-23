---
id: L0298
cost: blind
tags: ["ops", "network"]
---

# L0298

Python with no CA store fails TLS verification on every HTTPS host and the error reads as an unreachable host. Check ssl.get_default_verify_paths() before concluding a source is firewalled, and set SSL_CERT_FILE to certifi machine-wide.

## Evidence

2026-09-12: cafile None / capath None on the trading box while certifi sat installed with a valid bundle. Seven of eleven data sources failed with CERTIFICATE_VERIFY_FAILED and were recorded as unreachable. Setting SSL_CERT_FILE took reachability 3/11 -> 9/11 and unblocked four breadth families in one change.

## Tags

#ops #network

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
