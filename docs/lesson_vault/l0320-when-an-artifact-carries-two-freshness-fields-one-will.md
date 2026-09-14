---
id: L0320
cost: blind
tags: ["staleness", "measurement"]
---

# L0320

When an artifact carries two freshness fields, one WILL be abandoned and consumers will read the abandoned one. Write every timestamp on every pass, and never let a DATE stand in for a timestamp -- a date cannot distinguish a run at 00:01 from one at 23:59, so it looks maintained while carrying no usable freshness at all.

## Evidence

2026-09-14: shadow_forward set last_run (a date) every pass and left updated_at wherever it last landed. shadow_state.json was rewritten every 30 min carrying updated_at 2026-08-27 -- frozen 18 days -- while every row inside was current to the minute. heal_forward_lane derives STALE_ATTEMPT from that field and had been reporting 'engine last evaluated this row 434.1h ago' about rows just evaluated; 434.1h was exactly the stamp's age, which is how the two were connected.

## Tags

#staleness #measurement

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
