---
id: L0234
cost: blind
tags: ["diagnostics"]
---

# L0234

A diagnostic that reaches its subject through the module that needs hardware goes UNMEASURED on exactly the host where a person sits down to debug. Import the pure function, not the wrapper.

## Evidence

check_gold_live called gateway.load_sleeves, which imports MetaTrader5, so the roster step -- the ONE authoritative answer about which gold sleeves reach the venue -- printed 'not callable on this host' anywhere but the trading box. decision_core.load_sleeves(path) is the same function without the terminal import; through it the step answers everywhere.

## Tags

#diagnostics

## Related

- [[l0075-a-function-that-takes-a-root-path-argument-must-honour]]
- [[l0077-a-single-tokenized-commodity-chart-cannot-tell-a-real-]]
- [[l0099-an-absolute-path-in-an-edit-targets-the-tree-it-names-]]
- [[l0109-do-not-trust-clock-provenance-sort-key-to-linearise-a-]]
- [[l0144-a-persistently-red-test-is-a-disabled-gate-so-triage-r]]
- [[l0153-ask-of-every-health-fence-what-observation-clears-this]]
- [[l0197-a-normalised-unit-is-not-a-money-unit-comparing-two-sy]]
- [[l0219-never-build-an-fx-liquidity-stress-indicator-from-a-ce]]
