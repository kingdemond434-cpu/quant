---
id: L0280
cost: blind
tags: ["ops"]
enforced_by: desks/mt5/tests/test_stall_watch_disk.py::test_it_never_terminates_on_a_human_decision
---

# L0280

A watchdog that ends on 'needs a human decision' is a watchdog that does not work. Escalate through named tiers, measure what each tier actually reclaimed, say when a pool path is missing, and re-run on the next pass.

## Evidence

2026-09-08 02:10 'was 0.5GB free -> 0.5GB' then stopped; desk publisher dead at 02:20; gauntlet, allocator, shadow and dashboard stale for twelve hours.

## Enforced by

`desks/mt5/tests/test_stall_watch_disk.py::test_it_never_terminates_on_a_human_decision`

## Tags

#ops

## Related

- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0075-a-function-that-takes-a-root-path-argument-must-honour]]
- [[l0084-when-a-detector-fires-correctly-and-its-class-still-re]]
- [[l0095-a-handed-defect-owed-work-list-is-a-snapshot-of-a-queu]]
- [[l0100-a-collector-that-overwrites-a-revised-source-destroys-]]
- [[l0110-before-reporting-that-two-independent-estimates-agree-]]
