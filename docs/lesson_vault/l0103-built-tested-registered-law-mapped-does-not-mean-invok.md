---
id: L0103
cost: blind
tags: ["governance"]
---

# L0103

Built + tested + registered + law-mapped does NOT mean invoked. Grep for the script name across run_law_gate, run_ci, max_audit, cron and the hooks before believing a fence runs -- and never trust an EXECUTED verdict whose evidence is a citation string, since a path inside a dict literal satisfies a substring check while invoking nothing.

## Evidence

scripts/check_extractor_invariants.py shipped with zero invocation sites anywhere in the repo, while data/enforcement_execution.json recorded it verdict=EXECUTED evidence='invoked by scripts/build_enforcement_matrix.py' -- a file whose grep for subprocess/Popen/import_module/exec returns nothing. Its own cron exemption cited check_sizing_derivation and check_return_targeting as peers; both were already in run_law_gate._LAW_FENCES and it was not. Wired in 307851f (10 fences -> 11). Reachability false-green raised as R0473.

## Tags

#governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
