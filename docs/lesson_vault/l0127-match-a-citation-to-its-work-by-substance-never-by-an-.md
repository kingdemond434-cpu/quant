---
id: L0127
cost: blind
tags: ["ledger"]
enforced_by: tests/governance/test_citation_integrity.py::test_symbolic_refs_are_invalid_even_though_they_resolve
---

# L0127

Match a citation to its work by SUBSTANCE, never by an id in a commit subject. A batch commit that says 'R0009/13/26/42/50/52/63 closed' is stating a DISPOSITION, not proving the work is in it -- check the diffstat touches the files that row is about. And ids get renumbered, so the same id can name two unrelated rows across a collision. Store a fixed object name: a stored 'HEAD' or 'pending' is the worst dangling pointer because every existence check passes.

## Evidence

scripts/check_citation_integrity.py first run 2026-08-12: 15 of 227 citations unresolvable, 10 the literal HEAD; 16af6487's subject lists R0042/R0050 as closed but its diffstat touches neither defi_lending nor max_audit; 35eb57fc is titled R0152 but is a different pre-renumber row than ledger R0152

## Enforced by

`tests/governance/test_citation_integrity.py::test_symbolic_refs_are_invalid_even_though_they_resolve`

## Tags

#ledger

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
