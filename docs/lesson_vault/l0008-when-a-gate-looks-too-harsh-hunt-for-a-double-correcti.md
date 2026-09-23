---
id: L0008
cost: blind
tags: ["statistics"]
enforced_by: tests/validation/test_screen_admission.py::test_a_net_sharpe_is_not_penalised_for_turnover_again
---

# L0008

When a gate looks too harsh, hunt for a DOUBLE correction before touching any threshold. Two correct multiplicity corrections stacked are indistinguishable from one harsh one.

## Evidence

DSR was deflating by n_trials while the campaign layer already corrected for the same trials; the one-line per_candidate fix restored power with no threshold lowered. libs/autodiscovery/validation.py

## Enforced by

`tests/validation/test_screen_admission.py::test_a_net_sharpe_is_not_penalised_for_turnover_again`

## Tags

#statistics

## Related

- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0026-optimise-the-objective-you-actually-want-maximising-pe]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
