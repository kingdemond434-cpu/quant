---
id: L0071
cost: blind
tags: ["ci"]
enforced_by: tests/ops/test_max_audit_probe_killed.py::TestKilledProbeIsNotACollectionError::test_signal_death_raises_its_own_defect
---

# L0071

A NEGATIVE exit code is a verdict about the BOX, never about the code. Split death-by-signal from a real non-zero exit at every gate that shells out: the killed child reported nothing, so filing it as a failure files a finding nobody can act on. Capture the resource reading at the moment of death -- on a container that cannot read the kernel log, rc=-9 is the ONLY evidence that will ever exist.

## Evidence

2026-08-05: max_audit's pytest probe rc=-9 raised test-suite-uncollectable with an EMPTY reason and 'install the missing dependency'; the full suite collected rc=0 / 326MB / 19s seconds later. 3.8GB VPS, NO SWAP, several agent sessions. Fixed in run_ci 75cdb2c.

## Enforced by

`tests/ops/test_max_audit_probe_killed.py::TestKilledProbeIsNotACollectionError::test_signal_death_raises_its_own_defect`

## Tags

#ci

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
