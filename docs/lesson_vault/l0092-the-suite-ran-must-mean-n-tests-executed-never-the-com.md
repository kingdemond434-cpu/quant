---
id: L0092
cost: blind
tags: ["verification"]
---

# L0092

'The suite ran' must mean N tests EXECUTED, never 'the command returned': a collection-error exit and a completed run are byte-identical to a caller reading exit codes through a pipe.

## Evidence

2026-08-11: R0349/R0373 wrongly rejected on a 2-min collection-error exit read as full-suite completion; the real run was at 39% after 31 min; corrected in R0440

## Tags

#verification

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0074-an-alarm-must-name-the-cause-its-data-supports-never-t]]
