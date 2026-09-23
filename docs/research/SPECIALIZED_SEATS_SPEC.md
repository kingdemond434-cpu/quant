# SPECIALIZED DIGGER SEATS — SPEC (Scheduled-Event Miner, GitHub Archeologist, OSINT-flow tier)

_Spec-prebuilt 2026-07-18. The non-regional expansion seats. All obey the DIGGING CHARTER and
feed the SAME triage (EV gate → pre-registration → gauntlet). Freeze-governed; monthly engine,
highest-EV first. All are research/discovery — no risk path._

## A. SCHEDULED-EVENT MINER (High-ROI — calendar-bound, capacity-bound, under-mined)

_RETARGETED 2026-09-05. This seat was the DEFI EVENT MINER: on-chain governance forums, token
unlock calendars, bridge feeds, `scripts/run_defi_event_miner.py`. The 2026-08-18 universe mandate
retired that ground and the module was never built, so nothing is lost by pointing the DESIGN at
the MT5 book — and the design was the valuable half. What made it high-ROI was never the chain: it
was that the events are **scheduled in advance, mechanically dated, and therefore falsifiable on a
pre/post window nobody has to argue about.** The MT5 book is full of those._

- MODULE: biweekly. Sources: central-bank decision and minutes calendars, scheduled macro releases
  (CPI, NFP, PMI, inventories, WASDE), index rebalance and reconstitution dates, futures roll and
  expiry calendars, LBMA/exchange auction and fixing times, session/holiday calendars, and
  broker-side schedule changes (swap-rate revisions, margin and spread changes, symbol
  listings/delistings). All are public, all are dated, none is crowded at the retail-CFD tier.
- OUTPUT: TIME-BOUND event cards (event, mechanism, expected price-impact window, falsification)
  → gauntlet as event-study hypotheses (pre/post windows, purged).
- TEST: a mock scheduled release produces a well-formed event card with a dated observable.
- COMPLEXITY: Medium (calendar ingestion + point-in-time release timestamps — the release TIME is
  the hard part and getting it wrong silently manufactures look-ahead). SHADOW-PROOF: event-study
  backtests are inherently out-of-sample forward once live. FALSIFICATION: event cards' forward
  edge indistinguishable from zero over a quarter → retire. INDEPENDENCE: research only.

## B. GITHUB ARCHEOLOGIST (Med-ROI — near-zero competition)
- MODULE: extended Prospector duty (not a full seat) — deeper GitHub mining: abandoned repos,
  obscure Jupyter notebooks with full strategies, commit-history archaeology, fork-network
  traversal, NLP over notebook markdown+code. Reuses Prospector + GitHub-maximalism charter.
- OUTPUT: mechanism cards from repos that never reached forums/papers, provenance-graded
  (code-with-backtest = SEMI; unverified notebook = CLAIM).
- TEST: a fixture repo with a documented strategy yields a mechanism card. COMPLEXITY: Med
  (GitHub API commit/fork traversal + notebook NLP). SHADOW-PROOF: cards → standard gauntlet.
  FALSIFICATION: 2 quarters, zero surviving repo-sourced cards → fold back into base Prospector.
  INDEPENDENCE: research only.

## C. OSINT REGIONAL-FLOW TIER (Low-Med — flow signals, NOT strategy miners)
- MODULE: extend the OSINT scanner source list (no new seat) with regional flow vectors.
  _RETARGETED 2026-09-05: the original list was crypto on/off-ramp premiums (TRY/crypto, Nigerian
  P2P, IDR/VND ramps, USDT/CNY OTC, kimchi). The MECHANISM behind them — a parallel price for the
  same currency, forced by capital controls or ramp friction — is an FX fact, not a crypto one, and
  the desk trades FX. So: **parallel/black-market vs official rate spreads on exotics the book can
  actually quote** (TRY, ZAR, MXN, BRL, INR, EGP, NGN where listed), central-bank intervention and
  reserve announcements, capital-control and repatriation-rule changes, and onshore/offshore
  deliverable-vs-NDF divergence._ Monitored as SIGNALS, fed to OSINT triage (risk + sizing-gate
  hypotheses).
- OUTPUT: flow-signal series → OSINT lane; never full mechanism mining for these regions.
- TEST: a mock premium series ingests + computes a z-score. COMPLEXITY: Low (add sources +
  premium calc). SHADOW-PROOF: signals shadow-validated before any sizing use. FALSIFICATION:
  flow signals show no predictive content over a quarter → drop that region's vector.
  INDEPENDENCE: research/OSINT only; any SIZING use routes through the existing validated gate.

## MEV RESEARCH — RETIRED 2026-09-05 (was: quarantined behind a latency gate)
On-chain MEV/sandwich research (inbox Frontier #7) was quarantined behind a sub-50ms
exchange/relay connectivity gate and, being cloud-bound, was never built. It is now RETIRED
outright rather than quarantined: MEV is crypto-exchange/chain-native and the 2026-08-18 universe
mandate closed that ground, so the latency precondition can no longer unlock it. **The reasoning
is kept because it generalises and the desk will need it again:** a strategy whose edge is a race
is not a research question until the hardware that decides the race is verified — spec no build
against a latency assumption you have not measured. The same test governs any low-latency MT5
idea (broker execution speed, news-spike fills).
