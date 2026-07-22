# OPERATOR COMPACT — pre-committed human-side rules (principal + CRO, 2026-07-23)

**Why this exists:** the largest destroyer of realized CAGR in every retail-to-pro journey is not
the strategy — it is the operator: ad-hoc withdrawals, panic intervention in drawdowns, euphoric
over-sizing after wins, and absence. The desk has governance for the AI; this is the matching
governance for the HUMAN, pre-committed NOW (the principal's own words 2026-07-23: "I won't tweak
it after it's gone live — do it now"). This document IS that pledge, made enforceable.

## 1. Bankroll policy (pre-registered)
- **Injections:** welcome any time, any size — logged as capital FLOWS, never as PnL (the track
  record stays pure). At seed scale, external injections are the cheapest CAGR that exists.
- **Withdrawals:** ZERO below $25k equity. Above $25k: max 20% of trailing-year PROFITS per year,
  pre-announced 30 days in the ledger. Compounding is the entire engine; ad-hoc withdrawals are
  engine sabotage.
- **Profit ratchet (survivorship lock):** at each equity DOUBLING above $10k ($20k, $40k, $80k…),
  sweep 10% of the gained amount to cold self-custody, PERMANENTLY un-redeployable by the desk.
  Cost: a small drag on pure Kelly. Buys: realized gains that survive any venue failure, model
  failure, or tail event. With fat tails and counterparty risk, this is lifetime-log-wealth
  optimal even though naive Kelly says never ratchet.

## 2. Drawdown conduct (the panic protocol)
- During any drawdown >15% from high-water: **NO strategy edits, NO parameter changes, NO manual
  position intervention** until the root-cause engine has classified the loss and the governance
  rule (no policy modified immediately after losses) has been satisfied. The rails handle
  survival; the operator's job in a drawdown is *nothing*.
- Manual intervention is legitimate ONLY via pre-defined triggers: kill switch (deliberate,
  logged), dead-man latch response, PRINCIPAL_ACTION items.
- **Euphoria rule (mirror image):** after any +50% month or ladder unlock, NO ladder-step skips,
  no "just this once" leverage, no ruin-schedule edits. Upgrades arrive only via the ladder's
  own evidence gates. Winning changes nothing about process.

## 3. Absence protocol (the desk must survive the operator's life)
- The operator is 18 with exams, family, and a life. If a PRINCIPAL_ACTION page goes unanswered
  **7 days**: the desk steps DOWN one ladder step (if levered). **14 days**: descend to step 0
  (1.0x, base book) until contact resumes. The dead-man rail is unchanged and independent.
- Auth/credit decay is treated as absence too: brain-dead >7 days on a human-side blocker =
  same step-down. (Origin: 2026-07-20/22 — the brain sat dead for 2+ days on auth with the book
  running; the machine must de-risk when its thinking layer or its human goes dark.)

## 4. The tweak freeze the principal asked for
After go-live, changes reach the live system ONLY through the desk's own governance (EV gate,
independence gate, tests, controlled restart, ledger) — never through ad-hoc operator edits.
The principal's standing instruction "I won't tweak after live" is recorded here as MUTUAL:
the CRO equally may not hot-patch the live risk path outside the maintenance exception.

*Amendable only BEFORE Gate-0, or after it via a ledgered proposal with a 7-day cooling period —
never during a drawdown, never in the same week as a big win.*
