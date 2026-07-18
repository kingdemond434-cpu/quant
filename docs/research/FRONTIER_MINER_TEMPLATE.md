# FRONTIER MINER — TEMPLATE SPEC (max-ROI, one template all regions instantiate)

_Spec-prebuilt 2026-07-18 per the (reconciled) spec-prebuild rule. Every regional miner
(Chinese, Russian, Korean, Japanese, Arabic, Brazilian, …) is THE SAME MODULE parameterized by
an Operationalization Profile — build once, instantiate per region. Governed by the freeze;
built by the monthly engine post-Gate-0, highest-EV region first (CN reference already partly
live via the Prospector). Obeys the DIGGING CHARTER in full._

## MODULE DESIGN
- `scripts/run_frontier_miner.py --region <CODE>` — a single generic miner; region behaviour
  comes entirely from `data/frontier_profiles/<CODE>.json` (the Operationalization Profile).
  Reuses the Prospector transport (`_ask`, provenance grading, graveyard cross-check, card
  schema) and the Literature miner's citation-chain logic — NO new pipeline, only a
  region-scoped source set + language handling. Output → the SAME triage: EV gate →
  pre-registration → gauntlet → forward shadow (via the Overfit Prosecutor).
- Cadence: BIWEEKLY (like all diggers), saturation-relax to monthly (shared cadence engine).
- Seat economics: B-EVOLUTION replace-don't-add — a new frontier seat displaces the
  lowest-scoring rotating seat at monthly review (panel size constant, complexity budget held).

## OPERATIONALIZATION PROFILE (data/frontier_profiles/<CODE>.json) — required before a seat goes live
```
{
  "region": "<CODE>",               # CN|RU|KR|JP|AE|BR
  "language": "<name>",
  "query_budget": 20,               # deeper than the 15-query Prospector default
  "sources": [ ... ],               # the region source list (from the inbox packages)
  "top_slang": [ {"term":"打板","concept":"limit-up chasing"}, ... ],   # >=5, feeds NLP layer
  "regional_alpha_vectors": [ ... ],# >=3 (e.g. USDT/CNY OTC premium, PBOC sentiment, Asia-hours liq)
  "anti_bot": { "degrade_to": ["public RSS","official API"], "captcha": "PROHIBITED" }
}
```
The profile is the ONLY per-region artifact. No profile → the seat cannot run (hard gate).

## PIPELINE (identical for every region — this is "functions the same way as described")
1. Coverage-rotation pick (>=40% budget to least-covered source families in this region).
2. Mine per the Digging Charter: language-blind, GitHub-maximal, comment/reply-layer,
   anti-consensus, depth chains >=2 levels; up to the profile's query_budget.
3. NLP NORMALIZATION (shared layer, separate spec): map region slang → internal concepts
   BEFORE anything downstream. Un-normalizable jargon flagged, not guessed.
4. Provenance grade (VERIFIED/SEMI/CLAIM) + graveyard cross-check.
5. Emit <=3 mechanism cards → `docs/research/frontier_cards_<CODE>.md`, each attribution-tagged
   (source_region, source_type, pipeline_status) for the Discovery Telemetry.
6. Regional alpha vectors → OSINT lane as monitored signals (flow/premium/sentiment).
7. Update `data/frontier_profiles/<CODE>_coverage.md` + source-yield log.

## GUARDRAILS (from the Chinese package, generalized)
- Anti-bot: rotating proxy/UA; on walls/CAPTCHA → gracefully degrade to public RSS/API and flag
  missed data. NEVER burn budget on login walls. CAPTCHA SOLVING PROHIBITED (bright line).
- Reputation weighting: prioritize academic authors, high-rep forum users, verified fund
  managers; filter retail noise.
- Sustainability: monthly liveness check per source + immutable Bronze archive of downloaded
  data (data once downloaded is ours forever).

## TEST PLAN
- Unit: profile loader rejects a profile missing any required field (region/budget/sources/
  >=5 slang/>=3 vectors/anti_bot). Card emitter tags every card with region+type+status.
- Integration (dry, no live search): a mock source set produces >=1 well-formed card through
  the full pipeline incl. NLP normalization; graveyard-matched mechanism is discarded.
- Live smoke (post-activation): CN profile yields >=1 provenance-SEMI+ card in 2 runs.

## COMPLEXITY COST
Low-Medium. One generic module (~200 lines, reuses Prospector/Literature internals) + one JSON
profile per region (~30 lines each). Net new complexity per ADDED region ≈ one profile file →
deletion-credit-friendly. Well within the 3%/month budget.

## SHADOW-PROOF PLAN
Miners produce CANDIDATES only; zero capital touch. "Shadow" = the standard forward-shadow the
gauntlet already imposes on any card that survives. The miner infra itself is additive/reversible
(new files + one script); rollback_guard checkpoints it.

## FALSIFICATION HYPOTHESIS
"A region miner adds validated learning." Falsified for a region if, over 2 quarters, its cards'
Prosecutor-survival and live-ready rates (per the Discovery Telemetry) are statistically
indistinguishable from noise / from English-only yield → that region is defunded by the
Discovery Bottleneck Detector (evidence-driven, per the stop-line doctrine).

## INDEPENDENCE-GATE CLASS
Research/discovery subsystem. Touches NO risk path, NO trading logic, NO frozen component. Two
region miners are non-interacting (separate profiles/coverage files) and may be built in the
same monthly window. Independent of execution + rails entirely.
