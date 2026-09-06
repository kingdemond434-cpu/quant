---
id: L0196
cost: blind
tags: ["research-integrity"]
enforced_by: desks/mt5/tests/test_orthogonal_sweep_inputs.py::test_every_family_needing_an_input_is_wired_to_one
---

# L0196

When a component reports 'missing input X', check the CALLER passes X before believing the data is absent. A refusal message and a data gap are indistinguishable in a log.

## Evidence

pca_residual returned [] on all 297 symbols, filed as 'no-signals (4+ factor instruments H1)' -- its own len(factors)<4 refusal quoted back, while the sweep held the frames three lines away and never passed them. Same shape: _macro_series parsed top-level scalars of a nested file, returned None, and macro_conditional reported 'no-signals (a macro state series)' while data/fred_macro.json held 22 dated series. 2026-08-28.

## Enforced by

`desks/mt5/tests/test_orthogonal_sweep_inputs.py::test_every_family_needing_an_input_is_wired_to_one`

## Tags

#research-integrity

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
