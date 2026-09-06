---
id: L0070
cost: blind
tags: ["governance"]
enforced_by: tests/governance/test_stale_daemon_clock.py::test_proc_start_agrees_with_an_independent_oracle
---

# L0070

A detector that has never fired is not evidence of health. Before trusting any 'nothing found', check its clock and its signal can actually SEPARATE the states it judges -- a comparison against a quantity that tracks ~now can only ever return 'nothing changed'.

## Evidence

2026-08-05: max_audit.check_stale_daemons took process start from Path('/proc/<pid>').stat().st_mtime, which tracks directory ACCESS, so every polled daemon read 0.0167h against true ages of 6.9h/139.8h/180.1h. 'Files newer than started' with started ~= now matched only files edited in the last minute -- zero recall since 2026-07-26 on a class the desk has paid for 3x. Fixed 38ec6e2 (btime + /proc/pid/stat field 22).

## Enforced by

`tests/governance/test_stale_daemon_clock.py::test_proc_start_agrees_with_an_independent_oracle`

## Tags

#governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
