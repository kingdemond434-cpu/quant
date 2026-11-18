---
id: L0392
cost: hygiene
tags: ["governance", "data"]
enforced_by: tests/governance/test_honest_user_agent.py::test_no_module_impersonates_a_browser
---

# L0392

CORRECTS L0052: treat a refusal from a public endpoint (401, 403, 429, 451, a wall or a challenge) as final. Retry only with the same honest User-Agent (libs/data/honest_ua.HONEST_UA), never a browser UA, and never to get past a block; record the source as refused with its missed_growth line (LAWS 5e act 6).

## Evidence

Governance ruling 2026-11-18: L0052's browser-UA retry was a block bypass. 87 modules moved off spoofed UAs on claude/gdd-earnings-ua-fence; the fence forbids browser tokens in non-test code.

## Enforced by

`tests/governance/test_honest_user_agent.py::test_no_module_impersonates_a_browser`

## Tags

#governance #data

## Related

- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
