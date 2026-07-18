# STRUCTURAL-EDGE IDEAS — full specs (queued 2026-07-18, freeze-governed)

_8 ideas that exploit advantages the desk ALREADY has (capacity, AI comprehension, on-chain
transparency, its own graveyard + digger feeds). Each spec-prebuilt with the standing rule
fields. Monthly engine builds highest-EV first post-Gate-0. All research/discovery unless
noted — none touch the risk path or frozen components. Theme: extract more from advantages
already owned, not new frontiers._

---
## 1. AI-READABLE-BUT-HUMAN-IGNORED DATA  [NOVEL · High · pre-Gate-0 partial]
- WHAT: systematically parse public-but-tedious text no human trader scales to — full token
  contract code, every governance proposal in full, audit reports, exchange changelogs/
  API-deprecation notices, tokenomics/vesting docs. Edge = COMPLETENESS of comprehension.
- MODULE: `scripts/run_public_text_miner.py` — reuses the digger transport + free explorers
  (Etherscan verified-source, Snapshot/Tally, DefiLlama) + LLM extraction to structured facts
  (unlock dates, quorum thresholds, fee changes, upgrade timelines) → event/mechanism cards.
- TEST: a fixture contract + governance proposal yield correctly-extracted structured facts
  (dates, params) verified against the source. COMPLEXITY: Med (parsers + LLM extraction, no
  new deps). SHADOW-PROOF: cards → standard gauntlet as event-studies. FALSIFICATION: extracted
  facts don't produce edge in 2 quarters → narrow to unlocks-only. INDEPENDENCE: research only.

## 2. OWN-FILL REPLAY CORPUS  [NOVEL · High · POST-LIVE, gated on fills]
- WHAT: every live fill becomes labeled training data for the desk's own execution model —
  proprietary by construction, compounds forever, un-replicable.
- MODULE: extend `fills.csv` → `data/moat/fills_corpus.parquet` with full context at each fill
  (book state from recorder, intended vs realized px, latency, regime). Feeds the TCA model +
  future execution research. Reuses the recorder + fills logging.
- TEST: a week of synthetic fills accumulates queryable rows with full context. COMPLEXITY: Low
  (join fills to recorder snapshots). SHADOW-PROOF: pure data accumulation, no capital path.
  FALSIFICATION: corpus never improves execution vs baseline over 2 quarters → keep as archive
  only. INDEPENDENCE: research/data; GATED on live fills (post-Gate-0).

## 3. SUB-INSTITUTIONAL-CAPACITY EDGE CATALOG  [NOVEL framing · Med-High · the clearest moat]
- WHAT: catalog + test trades BELOW institutional minimum ticket size — new-listing first-hour
  inefficiency, long-tail funding (ranks 50-200, higher funding/thinner books, depth-guard-safe),
  dust-level arb. Institutions cannot deploy here; it is yours by default.
- MODULE: `data/capacity_edge_catalog.json` (curated + digger-fed) + a screener that flags
  candidates by (funding-yield × liquidity-adequacy-for-solo-size), each pre-registered.
- TEST: screener ranks a synthetic universe by solo-appropriate yield, excludes names failing
  the depth guard. COMPLEXITY: Low-Med. SHADOW-PROOF: each edge → forward shadow before capital.
  FALSIFICATION: no sub-institutional edge survives net-of-cost in 2 quarters → conclude the
  band is efficient after all. INDEPENDENCE: research; SIZING routes through the validated gate.

## 4. ON-CHAIN FUND/WHALE STRATEGY REVERSE-ENGINEERING  [NOVEL · Med-High]
- WHAT: track known fund/whale wallets on-chain and reverse-engineer strategies from behavior
  (what they accumulate, when, around which events). Crypto transparency = free smart-money intel.
- MODULE: `scripts/run_whale_reverse.py` — labeled wallets (Arkham/open label lists) + Dune/
  Flipside SQL → per-entity behavior features (accumulation timing, event-response patterns) →
  hypotheses ("entity X front-runs unlocks by N days"). Reuses on-chain free stack.
- TEST: a labeled wallet's history produces a behavior-feature vector. COMPLEXITY: Med (label
  maintenance + SQL). SHADOW-PROOF: behavior-derived signals → gauntlet. FALSIFICATION: whale
  behavior has no forward predictive content over 2 quarters → drop. INDEPENDENCE: research only.

## 5. REGULATORY-ENFORCEMENT MECHANISM MINING  [EXTENSION of Autopsy · Med]
- WHAT: SEC/CFTC complaints describe real edge/manipulation mechanisms in forensic detail (to
  prosecute). Free, precise write-ups of strategies that demonstrably worked.
- MODULE: extend Crisis Autopsy source list with enforcement-action databases; extract the
  MECHANISM (not the wrongdoing) → CLAIM-grade cards for the gauntlet (legal ones only; the desk
  trades the mechanism, never the manipulation). TEST: a sample complaint yields a mechanism
  card. COMPLEXITY: Low (source add + extraction). SHADOW-PROOF: gauntlet. FALSIFICATION: zero
  surviving cards in 2 quarters → fold into Autopsy. INDEPENDENCE: research only.
  ETHICS GATE: only legal, non-manipulative mechanisms are ever pre-registered.

## 6. DEAD-STRATEGY RESURRECTION ENGINE  [EXTENSION of graveyard · High]
- WHAT: map WHY each dead strategy died (fees/liquidity/regulation/tech/crowding), then flag
  those whose kill-reason NO LONGER APPLIES (fees dropped 10×, asset now liquid, tradfi reg
  absent in crypto). Time-arbitrage on obsolescence.
- MODULE: `scripts/run_resurrection.py` — reads docs/graveyard.md + each entry's kill-tag,
  cross-checks current conditions (fee schedules, liquidity, regime), and re-pre-registers any
  entry whose kill-condition has reversed. NO silent revival — fresh pre-registration only.
- TEST: a graveyard entry killed-by-fees is resurrected when a mock fee-drop is injected.
  COMPLEXITY: Low-Med. SHADOW-PROOF: resurrected ideas → full gauntlet fresh. FALSIFICATION: no
  resurrected idea survives in 2 quarters → the graveyard is truly dead, drop the engine.
  INDEPENDENCE: research only.

## 7. PRE-OBSOLESCENCE / CROWDING-EXIT DETECTOR  [NOVEL · Med]
- WHAT: inverse of #6 — detect when a CURRENTLY-working public strategy is about to crowd/die:
  rising cross-community discussion volume = crowding = exit/fade timing. Pairs with the
  Cross-Language Crowding-Stage signal.
- MODULE: reuse the digger feeds — track discussion-frequency of each live/candidate edge's
  keywords over time; a sustained spike → crowding alert → tighten/exit that edge. Near-free
  (reuses existing reads). TEST: a synthetic discussion-volume spike triggers a crowding flag.
  COMPLEXITY: Low. SHADOW-PROOF: signal informs sizing only via the validated gate. FALSIFICATION:
  discussion-volume shows no relation to realized decay → drop. INDEPENDENCE: research/OSINT.

## 8. DIGGER-FEED SENTIMENT LEADING INDICATOR  [NOVEL · Med · near-free]
- WHAT: the diggers already READ forums biweekly — aggregate their topic-frequency + sentiment
  as a leading "what is retail about to pile into" signal. Second output from reads already paid.
- MODULE: `libs/research/feed_sentiment.py` — over the diggers' already-collected text, compute
  per-asset/topic frequency + sentiment deltas → a candidate leading-signal series. Zero new
  data cost. TEST: a fixture feed produces a sentiment series with correct deltas. COMPLEXITY:
  Low. SHADOW-PROOF: signal → gauntlet as a leading indicator. FALSIFICATION: sentiment series
  has no forward IC over 2 quarters → drop. INDEPENDENCE: research only.

---
PRIORITY (CRO recommendation): #3 (clearest moat) and #1 (capability already owned) first;
then #6 (best graveyard leverage), #4 + #8 (cheap, reuse existing infra); #2 post-live; #5, #7
opportunistic. All governed by the Discovery Bottleneck Detector + source-yield telemetry once
running — build order is a starting recommendation, not fixed; evidence re-ranks it.
