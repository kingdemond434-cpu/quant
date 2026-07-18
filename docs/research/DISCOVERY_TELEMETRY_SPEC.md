# ALPHA DISCOVERY MULTIPLIER — TELEMETRY SPEC (measures every expansion's ROI)

_Spec-prebuilt 2026-07-18. The reporting layer atop source-yield learning: it MEASURES what each
region/source actually yields so allocation is evidence-driven and dead regions get defunded on
data. Lane-A instrumentation — lockdown-compatible (no risk path). Attribution tagging can start
the moment any digger runs; the live-calibration segments need Gate 0._

## MODULE DESIGN
- ATTRIBUTION (all diggers, present+future): every emitted card carries
  `{source_region, source_type, pipeline_status}` and is logged to
  `data/information_value.jsonl` (extends the existing information-value record — reuse, don't
  duplicate). pipeline_status advances as the card moves: Ingested → NLP_Normalized →
  Prosecutor_Rejected | Gauntlet_Passed → Live_Calibration.
- REPORT: `scripts/discovery_multiplier.py` (monthly, appended to the ledger + digest):
  - Data-Breadth Multiplier: active unstructured sources now vs the pre-expansion baseline
    (baseline snapshot stored once in `data/source_baseline.json`).
  - Raw intake rate / month by source_region.
  - Prosecutor survival rate by region (Gauntlet_Passed / Ingested).
  - Net live-ready alpha by region (count reaching >=10 calibration rows).
  - Discovery Probability Index: rolling 3-month live-ready candidates per 100 queries,
    English vs each non-English region.
- OUTPUT: a one-line asymmetry summary into the weekly digest + monthly tier-1 scorecard, e.g.
  "CN: 450 raw → 120 normalized → 15 prosecutor-passed → 2 live. CN discovery 3.4× English."
- PERMANENCE: any live-deployed strategy records source_region + source_type in the decision
  ledger permanently (and the Alpha Knowledge Graph once built).

## TEST PLAN
- Unit: a synthetic set of tagged cards produces correct per-region intake/survival counts.
- Property: multipliers are monotone in their inputs; missing region tags default to "Other",
  never crash.
- Regression: the report is deterministic on a fixed information_value.jsonl fixture.

## COMPLEXITY COST
Low. Tagging = 3 fields on an existing record. Report = one monthly script over an existing
JSONL. No trading impact, no new dependency.

## SHADOW-PROOF PLAN
Pure measurement/reporting. No capital path. Additive + reversible (a script + extra JSONL
fields). rollback_guard checkpoints it.

## FALSIFICATION HYPOTHESIS
"Per-region telemetry changes allocation." Falsified if 2 quarters of reports never inform a
single defund/upweight decision → simplify to intake+survival only (drop the finer indices).

## INDEPENDENCE-GATE CLASS
Telemetry/reporting. No risk path, no trading logic, no frozen component. Fully independent;
buildable anytime (Lane-A) — the live-calibration columns simply read zero until Gate 0.
