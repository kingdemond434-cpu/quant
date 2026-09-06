---
id: L0184
cost: blind
tags: ["scraping"]
---

# L0184

Prove pagination MOVES before trusting any multi-page crawl: fetch page 1 and page 2, compare the extracted ID SETS, and require the overlap to be less than the page size. A site whose pagination is a PATH SEGMENT (/section/pageN) silently ignores a ?page=N query param and serves page 1 every time, so the crawl returns a 200 and full-size HTML on every request and the only evidence is a duplicated archive nobody reads.

## Evidence

MQL5: /en/forum and /en/forum?page=2 return 105/105 IDENTICAL thread ids. desks/mt5/side_channels/mql5_forum.py used params={'page':N} and archived 36 runs / 189 rows / 3 DISTINCT titles -- 30 of the 36 runs hold exactly 6 rows = 2 titles x 3 identical fetches. R0666/R0667.

## Tags

#scraping

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
