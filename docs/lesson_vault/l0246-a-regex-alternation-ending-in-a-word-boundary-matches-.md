---
id: L0246
cost: blind
tags: ["regex", "frontier", "extraction"]
---

# L0246

A regex alternation ending in a word boundary matches the singular and silently fails the plural: 'graph neural network' hits, 'graph neural networks' does not, because the trailing s is still a word character. Invisible in review, fatal in use, since the plural is how people actually write these phrases. Apply the suffix rule once at table-build time rather than auditing twenty patterns by eye for a defect that looks like nothing.

## Evidence

18 of 20 patterns failed at least one real plural before _v() was introduced [cost as recorded: twenty silent vocabulary misses]

## Tags

#regex #frontier #extraction

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
