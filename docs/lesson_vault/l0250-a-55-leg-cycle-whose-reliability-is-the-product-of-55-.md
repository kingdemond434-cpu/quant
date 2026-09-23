---
id: L0250
cost: the entire tail of every affected pass
tags: ["resilience", "hourly-cycle", "error-handling"]
---

# L0250

A 55-leg cycle whose reliability is the product of 55 things going right is a fuse, not a cycle. `_producer` already stated the principle -- 'a crash inside them must not take the cycle's remaining legs with it' -- and only subprocess legs had it; in-process legs and call-construction errors escaped `main`. Extend it to every leg: record the failure, print it, return it as the leg's result so it reaches sync_marker and the issue board, and let the other 54 run. Re-raise KeyboardInterrupt and SystemExit or the cycle becomes unkillable.

## Evidence

one TypeError at leg 48 of 55 cost publish_state, issue_board and four report producers

## Tags

#resilience #hourly-cycle #error-handling

## Related

- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0081-persist-accumulated-state-in-a-finally-never-only-at-t]]
- [[l0084-when-a-detector-fires-correctly-and-its-class-still-re]]
