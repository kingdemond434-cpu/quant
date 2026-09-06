---
id: L0140
cost: blind
tags: ["alerts"]
enforcement_retired: tests/ops/test_alert_live_guard_stamp.py::test_a_LIVE_guard_does_not_page -- deleted with the retired crypto desk (MT5 universe mandate 2026-08-18); the property is no longer enforced by anything, so this lesson is back at full weight
---

# L0140

Read the PRODUCER's actual keys before trusting a .get(stamp, default) -- an absent key does not only loosen a threshold, it can WELD a pager permanently ON, and that destroys the signal just as completely while looking defensive.

## Evidence

run_alerts.py:297 read live_guard.json age from lg.get('generated', '1970-01-01T00:00:00+00:00'); run_live_guard stamps 'ts', never 'generated', so live_guard_dead paged 'stale 29776345min' (56 years) 3min after the guard wrote the file, on 100% of runs, key present in data/.last_alerts.json _paged. Fixed 131695d9.

## Tags

#alerts

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
