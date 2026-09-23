---
id: L0169
cost: blind
tags: ["data-access"]
---

# L0169

Re-probe a CAPABILITY verdict before inheriting it, and judge a fetch by CONTENT, never by status or size. A verdict graded from a single-instant probe of N rotating endpoints is a measurement with no repeat; ask 'does the ROTATION succeed', never 'are all N up'. And a full-size HTTP 200 can be a hollow shell: check for a known-good FIELD, with a known-good CONTROL fetched through the same route in the same minute.

## Evidence

2026-08-13: R0527 declared the video fetcher INERT desk-wide from a 4/4-proxy probe on 08-12; the FIRST proxy in the rotation returned a 2089-char transcript next day. Its second claim -- 'www.youtube.com returns 200 so the source is NOT walled' -- inverted the diagnosis: that 200 is hollow. One box, one minute, one route: dQw4w9WgXcQ 1,312,898 B WITH captionTracks vs VseWNnQmmy0 1,265,891 B and eb5ywYlw6E4 1,204,592 B, both LOGIN_REQUIRED, empty <title>, zero captionTracks -- a blocked body is ~96% the size of a good one. Piped adds a hollow SUCCESS: HTTP 200, subtitles:[], empty title, reported identically to 'no captions'. docs/research/video_locked_log.md + search_operator_library.md OP-072; ledger R0582.

## Tags

#data-access

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
