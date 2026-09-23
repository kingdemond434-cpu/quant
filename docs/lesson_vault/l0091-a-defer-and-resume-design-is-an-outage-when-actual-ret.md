---
id: L0091
cost: slow
tags: ["scheduling"]
---

# L0091

A defer-and-resume design is an OUTAGE when actual retry latency exceeds collision rate: count real invocations between collisions, not designed ones.

## Evidence

data/cro_ai_logs/brain_mutex.log 2026-08-11: 7/7 frontier regions DEFERRED to cro_ai's mutex at 15:00 with next firing 24h away; organ-never-frontier-* recurred 3-4x/14d

## Tags

#scheduling

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0074-an-alarm-must-name-the-cause-its-data-supports-never-t]]
- [[l0080-libs-ops-input-provenance-inputs-read-json-records-a-s]]
- [[l0118-a-fence-that-picks-the-newest-item-and-then-skips-it-a]]
- [[l0129-never-read-a-clean-git-status-as-evidence-your-output-]]
- [[l0133-when-a-fence-reports-an-organ-dead-that-you-can-see-pr]]
