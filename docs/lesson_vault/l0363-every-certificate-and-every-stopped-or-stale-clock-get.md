---
id: L0363
cost: capital
tags: ["clocks", "certificates"]
enforced_by: desks/mt5/tests/test_wiring_ceo.py::test_certificates_without_clocks_is_counted_and_unreadable_is_never_zero
---

# L0363

Every certificate and every stopped or stale clock gets a live clock from the fixer, every fifteen minutes, permanently: a certificate without a running forward clock cannot be promoted and its evidence is silently lost; the fixer heals by observation (clock row advancing, artifact written, process alive), never by parsing a label.

## Evidence

wiring_ceo certificates_without_clocks: 35 of 58 on 2026-09-17 (33 refused by the universe policy, 2 healable); heal_identity_broken_clocks; MT5-IdentityHealer

## Enforced by

`desks/mt5/tests/test_wiring_ceo.py::test_certificates_without_clocks_is_counted_and_unreadable_is_never_zero`

## Tags

#clocks #certificates

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0075-a-function-that-takes-a-root-path-argument-must-honour]]
