---
id: L0068
cost: hygiene
tags: ["governance"]
---

# L0068

To prove a failing test is environment rather than your code, add a detached worktree at HEAD and SYMLINK the live data/ dir into it. A bare worktree lacks data/ so live-state tests pass there for the wrong reason -- and ln -sfn into an existing dir creates data/data instead of replacing it.

## Evidence

test_enforcement under-exploration failures 2026-08-05: bare worktree PASSED (no data/moat), same worktree with data/ symlinked FAILED identically to the dirty tree -- proving the moat miner, not the L1.55 build.

## Tags

#governance

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
