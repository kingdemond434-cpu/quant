Implemented and committed `d8bdf129`:

- Fixed shadow sleeve cost-map failures to retain `KeyError(symbol)` evidence classification in [shadow_forward.py](/home/quant/quant-platform/desks/mt5/research/shadow_forward.py:382).
- Verified targeted shadow/cost suite: 30 passed.
- Verified full MT5 suite: 711 passed, 0 failed.
- Checkpointed controller epoch 129 and released the lease.

Economic effect: missing catalogue/cost entries remain fail-closed while preserving the repair-target identity; one blocked sleeve cannot conceal or halt the rest of the zero-capital forward book.

Blocker: canonical external gauntlet has 19,905 budget-deferred cells and two candidate-conservation losses; continue from its existing checkpoint.