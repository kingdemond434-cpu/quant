---
id: L0252
cost: hygiene
tags: ["testing", "brittleness", "maintenance"]
---

# L0252

A test that pins a LITERAL rather than a PROPERTY fails when the code gets better. All three long-standing desk failures were this: test_risk_units asserted the exact string auto_lot(equity, dist, s['symbol'], sym) after the gold branch correctly moved to gold_lot; test_universe_registry asserted OUT / f'{sym}_H1.parquet' after refresh_tail was generalised to every timeframe (the hardcoded name had left six non-H1 files permanently stale); test_retire_evidence asserted 29-of-30 identical was enough dispersion, written before the 80% modal check that closed the second gold_asia incident. Rewrite to the property and the improvement stops looking like a regression.

## Evidence

3 desk-suite failures, 0 of them actual defects; each fix strengthened rather than relaxed the assertion [cost as recorded: three stale tests reading as three defects]

## Tags

#testing #brittleness #maintenance

## Related

- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
