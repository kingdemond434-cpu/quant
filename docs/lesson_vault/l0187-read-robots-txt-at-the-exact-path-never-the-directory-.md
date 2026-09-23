---
id: L0187
cost: blind
tags: ["scraping"]
---

# L0187

Read robots.txt at the exact PATH, never the directory -- and when a page renders a tab client-side, grep the inline JS for its Ajax.get URL instead of regexing the HTML. A page-level scrape of a client-rendered tab returns 200 with plausible bytes and finds nothing, which reads as an empty result rather than a blind one.

## Evidence

2026-08-27: /signals/charts/risks IS Disallow-ed in mql5 robots.txt while its sibling /signals/charts/slippage is NOT -- assuming the directory was barred would have killed R0673, a free per-symbol slippage panel covering FusionMarkets, the desk's own venue. The panel is absent from the signal page's HTML entirely; it was found only in the inline LoadBrokerSlippage() JS as GET /signals/charts/slippage?id=&to=. Same run: signals_20260827_0600.json archived the FILTER SIDEBAR ('Filter','Broker server','Maximum profit') as signal rows for 36 straight runs while reporting success.

## Tags

#scraping

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
