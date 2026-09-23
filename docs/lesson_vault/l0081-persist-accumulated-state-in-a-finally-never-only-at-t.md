---
id: L0081
cost: slow
tags: ["ops"]
---

# L0081

Persist accumulated state in a finally, never only at the end of a long duty sequence. One failing step otherwise erases every step that already succeeded, and the stale timestamps that result are indistinguishable from 'the scheduler never ran'.

## Evidence

2026-08-05: run_cadence.py fired run_external_panel.py (timeout=720) with OpenRouter at -0.59; the panel hung the full 720s, TimeoutExpired escaped main(), and data/cadence_state.json kept mtime 07:13 while the run ended 23:03. Fixed dfdffcd; tests/governance/test_cadence_state_durability.py.

## Tags

#ops

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
