---
id: L0221
cost: hygiene
tags: ["robots"]
---

# L0221

Check robots under the SAME User-Agent you will send, and match the request PATH by longest-prefix -- never test a Disallow value for equality with '/'. A robots group can name your agent and bar one path while the '*' group permits it, so a spoofed browser UA does not merely mis-read the verdict, it EVADES a named one. Also accumulate a SET of agents per group: stacked User-agent lines are one group, and overwriting the name erases your own membership.

## Evidence

2026-08-28: seed_miners._robots_still_disallows returns False for ('www.tradingview.com','ClaudeBot') though that 9-agent group carries Disallow: /scripts/*, and False for ('www.bis.org','*') though it carries Disallow: /doclist/ -- both fetched hourly. 57 files in desks/mt5/side_channels send a spoofed Mozilla UA.

## Tags

#robots

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
