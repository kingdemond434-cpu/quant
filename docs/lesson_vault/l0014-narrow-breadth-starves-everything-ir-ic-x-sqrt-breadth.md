---
id: L0014
cost: wasted
tags: ["research", "priors"]
enforced_by: tests/test_alpha_economics.py::test_price_only_narrow_breadth_hard_killed
---

# L0014

Narrow breadth starves everything: IR = IC x sqrt(breadth). The best signal on a 2-name universe is worth less than a mediocre one on 200.

## Evidence

options VRP had the campaign's best IC (+0.06) at breadth 2 -> IR ~ nothing; narrow_breadth prior x0.25

## Enforced by

`tests/test_alpha_economics.py::test_price_only_narrow_breadth_hard_killed`

## Tags

#research #priors
