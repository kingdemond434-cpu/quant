---
id: L0344
cost: capital
tags: ["execution"]
enforced_by: desks/mt5/tests/test_e8_call_params.py::test_the_nested_envelope_is_unwrapped
---

# L0344

THE {condition, params} ENVELOPE FAULT RECURS BECAUSE EACH FIX HANDLES ONLY THE SHAPE IN FRONT OF IT. Strip envelope keys on EVERY shape, not just the nested one, and coerce word-valued params the families take numerically. When a producer writes params as an envelope, the half that is absent is as dangerous as the half that is present.

## Evidence

E8 live account, 2026-09-15: e8_book writes 'params': {'condition': null} -- the envelope with its params half ABSENT -- so the unwrap (which fires only when params is a dict) left condition in place and four sleeves died on TypeError: family_session_range_breakout() got an unexpected keyword argument 'condition'. A fifth died on 'side': 'SHORT' reaching a numeric comparison: '>' not supported between instances of 'str' and 'int'. Fixing both took the E8 pass from 12 considered with 4 SIGNAL_ERROR to 16 considered with ZERO errors. This is the fifth producer this envelope has broken.

## Enforced by

`desks/mt5/tests/test_e8_call_params.py::test_the_nested_envelope_is_unwrapped`

## Tags

#execution

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
