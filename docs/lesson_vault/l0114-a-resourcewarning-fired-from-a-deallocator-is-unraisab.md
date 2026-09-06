---
id: L0114
cost: blind
tags: ["testing"]
---

# L0114

A ResourceWarning fired from a deallocator is UNRAISABLE, so warnings.simplefilter('error', ResourceWarning) can never propagate it and a leak test written that way passes with or without the leak. Only pytest's unraisableexception plugin makes it observable (it converts the unraisable into PytestUnraisableExceptionWarning, which filterwarnings=error then fails). Write the test as a bare call and VERIFY IT FAILS on the reverted code.

## Evidence

tests/ops/test_audit_coverage_handles.py 2026-08-12: the catch_warnings version passed on the leaking line; the bare version failed with PytestUnraisableExceptionWarning at build_audit_coverage.py:113

## Tags

#testing

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0023-never-accept-done-for-a-human-step-verify-with-the-act]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
