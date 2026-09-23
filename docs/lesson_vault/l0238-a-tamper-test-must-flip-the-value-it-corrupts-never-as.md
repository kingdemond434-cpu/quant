---
id: L0238
cost: blind
tags: ["testing"]
---

# L0238

A tamper test must FLIP the value it corrupts, never assign a constant. Assigning the healthy value makes the test pass only while the system is broken, and it silently stops testing the thing it names the moment you fix the system.

## Evidence

test_the_manifest_row_carries_the_attestation_and_the_chain_still_verifies set allows_new_risk=True and verdict='OK' on row 0 and asserted the hash chain broke. Those are the values a healthy desk already writes. It passed only because NEW_RISK_OK was stuck False for eleven days; the hour that was fixed, the tamper wrote back identical bytes, the row did not change and the chain verified. A test of the hash chain had become a test of whether the desk was refused.

## Tags

#testing

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
