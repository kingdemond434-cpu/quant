---
id: L0213
cost: blind
tags: ["coverage"]
---

# L0213

Credit a coverage counter ONLY on a search that actually returned. A sweep loop that increments queries_exercised and marks queries DONE regardless of the search result manufactures a coverage claim and burns the ground permanently.

## Evidence

global_survivor_frontier.run_and_save: search() returns [] for every query (DDG-HTML 202 anti-bot, Mojeek 403, measured 2026-08-28) yet frontier_coverage.json reads queries_exercised=207 across 13 locales, populations_found=0, and all 207 native queries sit in frontier_state.queries_done as permanently skipped

## Tags

#coverage

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0079-grep-for-a-governance-flag-s-consumers-not-its-writers]]
- [[l0081-persist-accumulated-state-in-a-finally-never-only-at-t]]
