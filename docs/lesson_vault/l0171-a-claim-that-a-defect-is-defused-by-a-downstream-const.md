---
id: L0171
cost: blind
tags: ["control-flow"]
enforced_by: tests/test_check_risk_units.py::test_the_fence_catches_the_defect_it_was_built_for
---

# L0171

A claim that a defect is 'defused' by a downstream constant is a claim about CONTROL FLOW, and control flow is checkable in one command. Read the writer AND every rewriter before concluding a path is dead -- a field set three hundred lines away can turn 'latent, timidity' into 'live, ruin'.

## Evidence

The s3 proposal argued promoter.py's literal lot=0.01 meant auto_lot was never reached; gateway.sleeve_set():841 rewrites lot to 'auto_ramp' for every promoted sleeve, so promoted_lot->auto_lot is ALWAYS taken. 2026-08-20, commit c5877741

## Enforced by

`tests/test_check_risk_units.py::test_the_fence_catches_the_defect_it_was_built_for`

## Tags

#control-flow

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
