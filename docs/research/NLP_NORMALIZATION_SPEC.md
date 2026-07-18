# NLP NORMALIZATION LAYER — SPEC (shared infra for ALL language miners)

_Spec-prebuilt 2026-07-18. Shared dependency of every Frontier Miner (CN/RU/KR/JP/AE/BR). Maps
region-specific trading slang/jargon to standard internal operational concepts BEFORE any card
reaches the Overfit Prosecutor — so a mechanism described as 打板 is prosecuted as
"limit-up momentum chasing," not misread or discarded. Governed by the freeze; built with the
first Frontier Miner._

## MODULE DESIGN
- `libs/research/nlp_normalize.py`:
  - `load_glossary(region) -> dict[str,str]` — reads `data/frontier_profiles/<CODE>.json` top_slang
    (>=5 seed terms) plus an append-only learned glossary `data/nlp_glossary_<CODE>.json`.
  - `normalize(text, region) -> (normalized_text, flags)` — two-stage: (1) deterministic
    glossary substitution (fast, auditable); (2) LLM-assisted pass for un-mapped jargon that
    PROPOSES a concept mapping — proposals are FLAGGED, never silently trusted, and appended to
    the learned glossary only after a card using them survives the Overfit Prosecutor (so the
    glossary learns from validated usage, not from the model's guess).
- Applied by `run_frontier_miner` step 3 and reusable by the OSINT lane for regional posts.

## TEST PLAN
- Unit: each seed term normalizes to its concept; unknown term returns flagged (not dropped).
- Property: normalization is idempotent (normalize(normalize(x)) == normalize(x)).
- Regression: a curated set of CN/RU/KR/JP slice terms map to human-verified concepts.
- Guard: normalization NEVER changes numbers, tickers, or dates (only jargon tokens).

## COMPLEXITY COST
Low. ~80 lines + a small seed glossary per region (in the profile). The learned glossary grows
append-only. No new dependency (reuses the panel `_ask` transport for the LLM pass).

## SHADOW-PROOF PLAN
Pure preprocessing on research text; zero capital/risk path. New glossary entries are shadow-
validated by construction — only added after a card using the term survives the gauntlet.
Reversible (delete the glossary file to reset).

## FALSIFICATION HYPOTHESIS
"Normalization improves cross-language mechanism capture." Falsified if cards from a region show
NO higher Prosecutor-pass rate WITH normalization than a control run WITHOUT it over a quarter →
the layer is retired for that region (it is adding cost without signal).

## INDEPENDENCE-GATE CLASS
Research-preprocessing utility. No risk path, no trading logic. Shared read-only dependency of
the miners; independent of execution + rails.
