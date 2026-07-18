# SPECIALIZED DIGGER SEATS — SPEC (DeFi Event Miner, GitHub Archeologist, OSINT-flow tier)

_Spec-prebuilt 2026-07-18. The non-regional expansion seats. All obey the DIGGING CHARTER and
feed the SAME triage (EV gate → pre-registration → gauntlet). Freeze-governed; monthly engine,
highest-EV first. All are research/discovery — no risk path._

## A. DEFI EVENT MINER (High-ROI — crypto-native, capacity-bound, institution-ignored)
- MODULE: `scripts/run_defi_event_miner.py` — biweekly. Sources: on-chain governance forums
  (Snapshot, Tally, Commonwealth), protocol upgrade/treasury announcements, token-unlock
  calendars (reconstructed from contracts via Dune — free), bridge/large-transfer feeds.
  Reuses the recorder's on-chain access + Crisis-Autopsy provenance discipline.
- OUTPUT: TIME-BOUND event cards (event, mechanism, expected price impact window, falsification)
  → gauntlet as event-study hypotheses (pre/post windows, purged).
- TEST: a mock governance vote produces a well-formed event card with a dated observable.
- COMPLEXITY: Medium (event parsing + calendar reconstruction). SHADOW-PROOF: event-study
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
- MODULE: extend the OSINT scanner source list (no new seat) with regional flow vectors:
  TRY/crypto premium, Nigerian P2P premium, IDR/VND on-off-ramp, USDT/CNY OTC premium,
  Kimchi premium. Monitored as SIGNALS, fed to OSINT triage (risk + sizing-gate hypotheses).
- OUTPUT: flow-signal series → OSINT lane; never full mechanism mining for these regions.
- TEST: a mock premium series ingests + computes a z-score. COMPLEXITY: Low (add sources +
  premium calc). SHADOW-PROOF: signals shadow-validated before any sizing use. FALSIFICATION:
  flow signals show no predictive content over a quarter → drop that region's vector.
  INDEPENDENCE: research/OSINT only; any SIZING use routes through the existing validated gate.

## MEV RESEARCH — QUARANTINED (do NOT build without the hardware gate)
On-chain MEV/sandwich research (inbox Frontier #7) is quarantined behind a LATENCY GATE:
NOT specced for build unless the engine verifies sub-50ms exchange/relay connectivity. If
cloud-bound (current state), MEV is flagged structurally unviable and SKIPPED to preserve
compute — no spec effort spent until the latency precondition is met.
