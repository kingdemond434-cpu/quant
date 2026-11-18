---
id: L0352
cost: capital
tags: ["money-path", "execution"]
enforced_by: desks/mt5/tests/test_close_backstop_and_stop_floor.py::test_family_bracket_past_tolerance_is_re_anchored_with_the_certified_rr
---

# L0352

Lay a family sleeve's bracket from the entry the venue actually gives, never from levels frozen at the signal bar's close: the executor reaches a sleeve minutes after the bar closes and the quote has moved, so an absolute stop can sit 1-2 pips from the fill while the lot sizer inflates the size against that distance. Re-anchor the certified stop and target distances to the fill past a quarter of the stop, refuse a signal the market has already stopped or paid as stale, and ask the venue's deal history whether the bar was already traded before trusting the state mark.

## Evidence

live_ledger 2026-09-16: nine forex closes with a stop under 10 pips, nine losses, mean -1.05R, -36 EUR of the lane's -72; eurgbp_discovered_asia_p_8e61 sold 0.27 lots at 06:14:29 with sl 1.3 pips from entry against a certified 8.4-pip (2 ATR) stop, and sold the same 08:00 bar twice 10 minutes apart after a stop-out

## Enforced by

`desks/mt5/tests/test_close_backstop_and_stop_floor.py::test_family_bracket_past_tolerance_is_re_anchored_with_the_certified_rr`

## Tags

#money-path #execution

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
