---
id: L0342
cost: slow
tags: ["data", "governance"]
enforcement_retired: desks/mt5/research/asia_collector.py -- names an organ, not a test (repaired 2026-09-29): no test enforces this property, so the lesson stays at full weight rather than claiming a graduation that does not resolve
---

# L0342

NO SOURCE IS EVER BLOCKED FOR WANT OF A COLLECTOR. A declared source with no fetcher is a FLAW, not a backlog item. Write ONE generic collector driven by the registry -- address, declared SHAPE, cadence, key requirement -- so a new source is collected the hour it is declared and the 90th source is not blocked the day it is added. Bespoke per-source fetchers rot at N different rates and guarantee the next source repeats the problem. And DERIVE the blocked/available tier from the lake, never from a hardcoded list: a status asserted where it could be read is the same defect in a different costume.

## Evidence

2026-09-15: 750 of 774 Asia cells were BLOCKED_ON_DATA against a hardcoded tuple naming ONE source. One registry-driven collector (asia_collector.py) put point-in-time vaulted bytes on disk for 43 of 85 sources on its first pass, and deriving the tier from the lake took BLOCKED_ON_DATA 750 -> 381 and MEASURABLE_NOW 24 -> 393 with no per-source work. Using certifi's CA bundle took UNREACHABLE 26 -> 1: the CERTIFICATE_VERIFY_FAILED self-signed errors on every Chinese government host were TLS interception on the egress path, not broken sites -- and the fix was the correct CA bundle, never disabling verification.

## Tags

#data #governance

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
