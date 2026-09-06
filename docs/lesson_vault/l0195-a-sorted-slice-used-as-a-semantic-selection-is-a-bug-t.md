---
id: L0195
cost: blind
tags: ["research-integrity"]
enforced_by: desks/mt5/tests/test_orthogonal_sweep_inputs.py::test_the_peer_is_related_not_alphabetically_first
---

# L0195

A sorted slice used as a semantic selection is a bug that produces plausible output forever. Ask of any sorted(x)[:n] whether the sort key IS the semantics; if not it is arbitrary, and the output still reads as coverage.

## Evidence

orthogonal_sweep.py picked peers as [s for s in symbols if s != sym][:12] over an alphabetical universe, so relative_value and correlation_regime ran XAUUSD against 3M (the share CFD) and every FX cross against 3M/ADAUSD/ADP/AMD/AT&T -- both reporting 'ran on 297 symbols'. ~590 economically arbitrary pairings reading as healthy coverage. Fixed 2026-08-28, commit 26064450.

## Enforced by

`desks/mt5/tests/test_orthogonal_sweep_inputs.py::test_the_peer_is_related_not_alphabetically_first`

## Tags

#research-integrity

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0073-a-rail-s-reference-point-and-a-performance-number-may-]]
- [[l0075-a-function-that-takes-a-root-path-argument-must-honour]]
