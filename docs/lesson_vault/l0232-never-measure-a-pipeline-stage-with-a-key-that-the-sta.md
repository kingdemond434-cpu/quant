---
id: L0232
cost: blind
tags: ["measurement"]
---

# L0232

Never measure a pipeline stage with a key that the stage itself destroys. Measure by the provenance field that survives the transformation.

## Evidence

check_miner_conversion computed reached_backtest as novel & tested, both keyed family|SYMBOL|session. Tested rows have all three; RAW miner rows have none -- symbol and family are what the compiler DERIVES -- so every raw row keyed to unknown|*|* and the intersection was empty by construction. 49 of 53 miners read Tested=0 and were labelled 'noise at cost' while the compiler was converting 178,753 rows into 364 executable candidates. Tested rows carry source=ext_<miner>_<SYMBOL>_<family>, which survives the transformation; counting that took zero-yield from 49 miners to 6.

## Tags

#measurement

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0013-positive-ic-is-not-a-profitable-strategy-ic-lives-mid-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
