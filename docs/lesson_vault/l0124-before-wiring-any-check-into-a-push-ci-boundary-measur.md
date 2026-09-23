---
id: L0124
cost: slow
enforced_by: tests/ops/test_birth_properties.py::TestOrphanRewriteIsAnIdentity::test_agrees_with_the_replaced_regex
---

# L0124

Before wiring any check into a push/CI boundary, measure its TIME and its PEAK RSS. A 90-second, 621MB check is not a gate -- it gets OOM-killed or deleted. rc=-9 with 'no output' from a subprocess runner is the OOM killer, not a logic bug, and it is indistinguishable from a pass unless the runner treats it as failure.

## Evidence

check_orphan_scripts measured 91.56s of 91.66s and 621MB RSS on a 3.8GB box with 616MB free; run_law_gate reported 'BREACH check_birth_properties.py (rc=-9): no output'. Per-script full-corpus regex -> one tokenization (26x); re.findall -> finditer (3x memory). 2026-08-12.

## Enforced by

`tests/ops/test_birth_properties.py::TestOrphanRewriteIsAnIdentity::test_agrees_with_the_replaced_regex`

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
