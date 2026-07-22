# GO-LIVE HARDENING & STRUCTURE CHECKLIST (pre-registered 2026-07-23 — Gate-0 blocking unless marked)

**Why now:** every item here is in the class that CANNOT be retrofitted — security posture,
account structure, records-from-inception, tax basis. One hack = −100% CAGR; one un-provable
track record = the 100× allocator lever lost. This list is part of Gate-0.

## A. Security (BLOCKING — a single failure here outweighs every alpha ever found)
- [ ] Live API keys: **trade-only scope, withdrawals DISABLED at the key level**, IP-whitelisted
      to the VPS. Keys never in the repo, never in the remote URL, never in logs.
- [ ] **Rotate the GitHub PAT embedded in the git remote URL to a fine-grained deploy key BEFORE
      any live key exists on this box** — a box holding live trading keys must not also carry a
      broad PAT in plaintext remote config. (CRO flag, 2026-07-23.)
- [ ] Venue account: passkey/hardware 2FA, dedicated email (not the personal one), withdrawal
      address whitelist LOCKED to the cold wallet with the venue's max timelock.
- [ ] VPS: SSH key-only (done), fail2ban, unattended security upgrades; quarterly key rotation
      schedule written into the cadence.
- [ ] Cold wallet for the profit ratchet established and test-swept with a dust amount.

## B. Account & counterparty structure (BLOCKING)
- [ ] **Sub-account per sleeve** — margin isolation so one sleeve's tail event cannot drain the
      others. The carry book, and each future validated sleeve, gets its own sub-account.
- [ ] **Venue diversification schedule (pre-registered):** ≤100% of equity on one venue below
      $10k · ≤50% by $50k · ≤33% at $100k+ — enforced by the same growth-audit that polices
      under-deployment (concentration in a COUNTERPARTY is the same defect class as
      concentration in a name; FTX is the incident report).
- [ ] Profit sweeps to self-custody on the ratchet schedule (Operator Compact §1).

## C. Economics (BLOCKING where marked)
- [ ] (BLOCKING) **Fee tier:** BNB balance funded for the fee discount; maker-first confirmed on
      live endpoints; fee-tier path (VIP/volume) written into the capital plan. Worth several
      %/yr risklessly — the cheapest alpha on this list.
- [ ] (BLOCKING) **Compounding hygiene:** `--capital` re-anchors to mark-to-market equity weekly
      so gains compound (ladder doc §levers).
- [ ] Idle-capital yield floor: EV-gate venue flexible-earn products for the UNDEPLOYED cash
      buffer (1–5%/yr on drag) — with the counterparty caveat priced: earn products are unsecured
      lending to the venue; cap at the venue-diversification limits above. (Non-blocking; EV gate
      decides.)
- [ ] Incentive-aware venue routing (inbox #52) evaluated with LIVE program data before launch.

## D. Records from inception (BLOCKING — cannot be backfilled, worth 100× later)
- [ ] **NAV attestation live from day 1:** `scripts/run_nav_attest.py` (hash-chained daily NAV,
      committed to git = tamper-evident timestamping). An allocator-grade, auditable-from-
      inception track record is the single largest lifetime lever this desk has; self-reported
      spreadsheets are worth nothing. ALREADY RUNNING on paper equity — continuity through
      go-live is the point.
- [ ] **Tax-lot discipline from trade #1:** the trades log is the raw record; PRINCIPAL must
      establish jurisdiction + rates BEFORE live (activates gap #11 tax-aware sizing — tax drag
      belongs in the Kelly objective, and 20–30% annual tax leakage is the largest single net-CAGR
      variable nobody models). Entity/timing structure = human decision with a local advisor;
      the desk's job is perfect records and tax-aware sizing.

## E. Operator (BLOCKING)
- [ ] Operator Compact signed into the ledger (withdrawals, ratchet, drawdown conduct, absence
      protocol, mutual tweak-freeze).
- [ ] Absence step-down rules understood: unanswered pages de-risk the book automatically.
