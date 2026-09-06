---
id: L0222
cost: blind
tags: ["artifact"]
---

# L0222

An empty collector artifact cannot distinguish empty from broken OR from FORBIDDEN. Before calling a zero-yield collector a parse bug, read the robots group for the exact path it fetches -- a path-scoped ban is the likeliest cause and is invisible to a host-level check.

## Evidence

2026-08-28: of s11's four 'parse bugs on HTTP-200', two were live robots breaches (zhihu /search, finance.naver.com Disallow: /); only so.eastmoney.com (robots 404 = allow) and kr.investing.com were genuine parse failures. All five wrote 2-byte [] hourly with zero error rows.

## Tags

#artifact

## Related

- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
