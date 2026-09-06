---
id: L0162
cost: hygiene
enforced_by: tests/scripts/test_max_audit_checks.py::TestTmpfsHoldersNameTheirProducer::test_a_desk_owned_worktree_carries_its_reclaim_command
---

# L0162

A tmpfs entry's OWNER is the fact that makes freeing it safe, and 'held by nothing' is not it. When /tmp is over its ceiling, the reclaimable class is the one carrying OWNERSHIP EVIDENCE: a git worktree this repo REGISTERED (git worktree list) is a checkout of a committed sha, so removing it destroys no unique work and 'git worktree remove' refuses it while dirty. A bare directory of the same size and age carries none of that and must not be touched. Match ownership by CONTAINMENT, not equality -- a lawgate checkout registers at <entry>/t while <entry> is what holds the RAM.

## Evidence

2026-08-13: /tmp at 838MB vs a 600MB ceiling. 150MB was /tmp/wt-head, a worktree THIS repo registered at 02:55 and abandoned; establishing that took git worktree list, a read of its .git pointer, a diff of its one dirty artifact and a holder scan -- four commands the fence could have done, having already computed size, age and holder. The other 179MB was 255 dead agent-session scratch dirs (oldest 188h) whose producer is the harness, not desk code, and which therefore stays a reported defect (R0603). Fence green after: 838 -> 415MB, MemAvailable 747 -> 1346MB. Commit 268c7f50.

## Enforced by

`tests/scripts/test_max_audit_checks.py::TestTmpfsHoldersNameTheirProducer::test_a_desk_owned_worktree_carries_its_reclaim_command`

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0041-any-objective-defined-over-a-partition-can-be-gamed-by]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
