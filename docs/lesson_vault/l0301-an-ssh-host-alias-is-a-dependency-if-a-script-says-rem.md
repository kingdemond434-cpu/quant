---
id: L0301
cost: blind
tags: ["wiring"]
---

# L0301

An ssh Host alias is a dependency. If a script says REMOTE = 'some-alias', check that ~/.ssh/config actually defines it on THIS machine -- a missing alias degrades every tool that uses it to UNREACHABLE, which reads as 'the box is down' rather than 'this checkout was never configured'.

## Evidence

2026-09-14: no ~/.ssh/config existed on the mirror at all, while 10+ scripts (fetch_universe, shadow_forward, pull_bars, run_forward_on_box, sync_allocation_to_desk, run_external_pipeline) reference contabo-mt5. check_desk_code_parity reported UNREACHABLE -- parity UNMEASURED for as long as that was true.

## Tags

#wiring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
