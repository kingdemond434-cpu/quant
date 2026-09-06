---
id: L0133
cost: blind
tags: ["fences"]
enforced_by: tests/governance/test_organ_liveness.py::test_an_output_this_fence_cannot_watch_is_COUNTED_not_silently_dropped
---

# L0133

When a fence reports an organ dead that you can SEE producing, fix the direction of the repair before the repair. Pointing the declaration at the real path is the obvious move and is often DOWNWARD: check_organ_liveness counts ONLY data/ paths, so correcting a manifest EVIDENCE line to the true reports/ path converts a false RED into an organ the fence skips entirely and never mentions again. Ask which way the repair moves the fence's sight, not just whether it clears the message.

## Evidence

2026-08-12: law gate flagged screen_unlock_supply_series NEVER-PRODUCED while reports/axis_screens/unlock_supply_series.json was fresh that hour. scripts/check_organ_liveness.py:142 drops every non-data/ token; measured 14 of 100 organs with declared evidence invisible, incl resolve_llm_trader_book.py, and n_checked read 87 against 211 scheduled lines. Fixed at e130e096 by COUNTING the skips (n_unwatchable_path), not by widening the guard -- the file itself argues a false GREEN is strictly worse than a false RED.

## Enforced by

`tests/governance/test_organ_liveness.py::test_an_output_this_fence_cannot_watch_is_COUNTED_not_silently_dropped`

## Tags

#fences

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
