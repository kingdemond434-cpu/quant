---
id: L0303
cost: blind
tags: ["wiring"]
---

# L0303

git add fails the WHOLE invocation (rc=128, 'pathspec did not match any files') when any one pathspec matches nothing on disk AND nothing in the index, staging none of the batch. Never stage a computed path list in one call without a per-path retry -- one phantom aborts every real path beside it.

## Evidence

2026-09-14: Adopt-Release staged in 200-path chunks. A lesson-vault note renamed then reverted across two pushes left such a phantom, so the hourly adoption exited 1 and refused to seal. The box ran the previous night's engines while a census fix, a parity fix and two E8 fixes sat on origin, pushed gated and signed, executing nowhere. The task table showed Ready.

## Tags

#wiring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
