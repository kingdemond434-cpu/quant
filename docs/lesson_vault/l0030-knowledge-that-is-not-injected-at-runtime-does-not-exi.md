---
id: L0030
cost: blind
tags: ["design", "memory"]
enforced_by: tests/research/test_review_rubric.py::test_it_reaches_the_doctrine_every_llm_caller_already_injects
---

# L0030

Knowledge that is not injected at runtime does not exist. A 67k-char lesson file referenced only from code comments changes no behaviour in any organ, ever.

## Evidence

docs/institutional_knowledge.md reached no prompt, runner or organ, while ops/principal_doctrine.txt was force-fed at 95,204 chars -- 6.0x max_audit's own 16k dilution threshold

## Enforced by

`tests/research/test_review_rubric.py::test_it_reaches_the_doctrine_every_llm_caller_already_injects`

## Tags

#design #memory

## Related

- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0097-when-a-check-grades-a-timestamp-read-what-writes-it-a-]]
- [[l0103-built-tested-registered-law-mapped-does-not-mean-invok]]
- [[l0117-when-a-check-credits-a-step-by-testing-that-a-file-exi]]
