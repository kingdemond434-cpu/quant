---
id: L0178
cost: blind
---

# L0178

Never point a re-run at the path holding the only good harvest, and never treat HTTP 403 as an empty result. A crawl that succeeded is an ARTIFACT; a re-run launched to fix a parse bug is a NEW attempt whose failure mode is a rate-limit ban, and if it writes to the same path it destroys the evidence AND looks like a clean empty verdict. Write re-runs to a new path; promote only on a non-empty result.

## Evidence

prospector 2026-08-26: a 2,529-row MQL5 signals population (53 pages, enumerated to the 404 boundary) was overwritten by its own re-run, which 403'd on page 1 after MQL5 rate-limited the IP at ~50-60 sequential pages / 1.5s. Same shape as the 30/30 empty-array archives in desks/mt5/data/intelligence/mql5/ that R0660 documents.

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
