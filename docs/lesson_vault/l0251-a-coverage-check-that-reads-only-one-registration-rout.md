---
id: L0251
cost: hygiene
tags: ["windows", "scheduling", "installer", "duplication"]
---

# L0251

A coverage check that reads only one registration route invites a duplicate via the other. Install-QuantWindows registers most tasks from a table and several from their own blocks (they need settings the table cannot express: an offset trigger, MultipleInstances IgnoreNew). Counting only the table reported MT5-ShadowSync as MISSING, and the obvious fix -- add a table row -- registered it twice with different triggers, the surviving one decided by statement order. The table row would have fired ON the 00/15/30/45 replay slots, the exact race the block's own comment offsets five minutes to avoid.

## Evidence

box output showed both routes registering; the dedicated block sets -MultipleInstances IgnoreNew and a +5min offset [cost as recorded: a coin toss over which settings a live task runs]

## Tags

#windows #scheduling #installer #duplication

## Related

- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0073-a-rail-s-reference-point-and-a-performance-number-may-]]
- [[l0075-a-function-that-takes-a-root-path-argument-must-honour]]
