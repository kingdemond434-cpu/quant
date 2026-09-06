---
id: L0029
cost: blind
tags: ["ops"]
---

# L0029

Two PIDs with matching args are not two processes until ParentProcessId says so, and every manual launch uses the fully-qualified venv interpreter -- bare `python` is a different, less-provisioned environment.

## Evidence

a live-executor 'duplicate' was a genuine OS-level child; the precautionary kill caused a ~3min executor gap and was probably unnecessary. institutional_knowledge.md 2026-07-09

## Tags

#ops

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]
- [[l0075-a-function-that-takes-a-root-path-argument-must-honour]]
- [[l0112-a-gate-whose-trigger-population-includes-work-the-desk]]
- [[l0127-match-a-citation-to-its-work-by-substance-never-by-an-]]
- [[l0154-cleanup-that-exists-only-in-a-finally-block-leaks-on-s]]
- [[l0194-a-liveness-check-written-against-posix-exceptions-is-d]]
- [[l0218-a-count-is-not-a-frequency-check-bars-per-day-before-c]]
