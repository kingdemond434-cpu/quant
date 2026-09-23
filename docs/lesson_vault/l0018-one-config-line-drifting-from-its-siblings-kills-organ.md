---
id: L0018
cost: blind
tags: ["ops"]
enforced_by: tests/governance/test_service_unit_parity.py::test_every_claude_unit_puts_the_binary_on_PATH
---

# L0018

One config line drifting from its siblings kills organs silently. Sibling parity is a TEST, never a reading exercise -- the failure lands before any log exists.

## Evidence

quant-frontier.service lacked Environment=PATH= that its four sibling units carried; systemd's near-empty env made `claude` unfindable and all 7 regional seats died on command-not-found before reading a prompt. tests/governance/test_service_unit_parity.py

## Enforced by

`tests/governance/test_service_unit_parity.py::test_every_claude_unit_puts_the_binary_on_PATH`

## Tags

#ops

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
