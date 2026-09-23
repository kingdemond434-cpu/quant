---
id: L0052
cost: wasted
tags: ["data"]
enforced_by: tests/data/test_venue_http_ua.py::test_the_default_headers_carry_a_browser_ua_not_the_library_default
---

# L0052

A 403 from a public venue endpoint is a User-Agent bot-block far more often than a real refusal. Retry with a browser UA BEFORE recording the venue as blocked -- an honestly-recorded wrong diagnosis outlives the outage it describes.

## Evidence

OKX returned 403 to Python-urllib and full data to the identical request with a browser UA. libs/data/venue_http.py; the same tree already carries binance-451 and bybit-CloudFront notes that deserve a re-test.

## Enforced by

`tests/data/test_venue_http_ua.py::test_the_default_headers_carry_a_browser_ua_not_the_library_default`

## Tags

#data

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
