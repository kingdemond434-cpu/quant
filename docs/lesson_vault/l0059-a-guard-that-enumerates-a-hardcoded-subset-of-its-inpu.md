---
id: L0059
cost: blind
tags: ["validation"]
---

# L0059

A guard that enumerates a hardcoded subset of its input space must return UNTESTABLE on the rest, never PASS. And build its self-test fixture from the WIDEST real schema, not the narrowest -- a fixture that only contains the covered columns is structurally incapable of revealing what the guard is blind to.

## Evidence

libs/features/validation.py:91 mutates only [open,high,low,close]. Demonstrated live: check_causal reports ok=True n_leaked=0 for funding.shift(-1), for a funding[-1] broadcast (reads the FINAL bar of the series), and for full-sample z(funding) -- the exact leak its docstring claims to reject -- while the OHLC control correctly fails at n_leaked=23. Funding/carry is the desk's only repeat survivor. causal_guard.self_test() builds bars from OHLC only. R0289.

## Tags

#validation

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
