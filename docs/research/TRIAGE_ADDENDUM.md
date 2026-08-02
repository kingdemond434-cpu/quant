# TRIAGE ADDENDUM — items 82–101, 2026-07-27

Second batch of 20 proposals, classified on the same rules. Nothing skipped.
Running total: **101 items triaged.**

---

## BUILT — already covered

| 93 | **Adaptive Data Acquisition Agent** | **BUILT 2026-08-02 -> `scripts/acquire_data.py`, wired into run_cadence every cycle.** Scores acquisition candidates EVIG-shaped -- P(usable from the digger's own grade) x information_gain x replication_difficulty x region_priority / cost -- and the ADAPTIVE term is `ontology.priority`, which reads the desk's recorded attempts and survivors. Demonstrated: an on-chain source ranked #1 on a virgin desk falls to #3 once its regions are recorded worked-to-zero-survivors, and the self-recorded tape rises to #1. A hardcoded advantage table cannot do that, which is why building it on `research_cio.SOURCES` was refused -- that would have been one author's priors wearing the vocabulary of measurement. Ungraded sources rank below every graded one INCLUDING the rejected ones, or the ranking rewards not looking. **Previously: UNBLOCKED 2026-07-29,** Its stated blocker was "depends on Information Advantage Score (item 17) existing first" — and 17 shipped, so the blocker expired. Caught mechanically by `max_audit.check_triage_disposition`, not by anyone re-reading the row: a QUEUE verdict is a claim with an expiry date and nobody revisits a blocked item to ask whether it is still blocked. Buildable now against `research_cio.py` §1. |
| # | Component | Where | Note |
|---|---|---|---|
| 92 | Research Reproducibility Engine | `experiment_registry.py` | commit sha + artifact set pinned per experiment; 569/569 artifacts present (100%) |
| 101 | Decision Audit Trail | `experiment_registry.jsonl` + commit messages + `suggestion_ledger` | why-funded / why-promoted / why-killed already recorded per experiment |
| 86 | Feature Novelty Detector | `alpha_lifecycle.py` §3 | Jaccard + dead-mechanism match. Verified live: flags "social attention momentum" against FAMILY KILL M_ATTENTION_DELAY and "RSI oversold bounce" against M_PRICE_PATTERN |
| 96 | Research Experiment Scheduler | `research_erv.py` | orders the queue by `prior × information_gain ÷ cost` (arch/moat/mech/cost). Ordering only — no autonomy, no promotion authority, exactly as the item specified |
| 99 | Market Anomaly Memory | `alpha_lifecycle.py` §4 → `data/anomaly_memory.jsonl` | append-only; seeded with INC-006 (cash-carry hedge inverted short→long, twice) |
| 82 | Data Provenance extension | `measurement_gate.py` `check_provenance` + `docs/research/data_provenance.json` | **built 2026-07-29.** Sixth gate family: source / collection_method / manipulation_risk / survivorship. HIGH manipulation risk and CONTAMINATED survivorship BLOCK; a declaration contradicted by the rows' own venue field is a FAIL; undeclared WARNs and is counted so it can ratchet down |

**Re-verdicted 2026-07-29.** Items 86, 96 and 99 had shipped and were still filed under BUILD;
each was confirmed by RUNNING its producer, not by matching a name. Item 82 was the only one of
the nine open BUILD items across both triage docs that was genuinely unbuilt, and it was built
the same day. Register kept in `docs/`, not `data/`, because `data/` is gitignored and a
provenance record that dies with the working directory is not a record.

---

## BUILD — unblocked, cheap, next session

_EMPTY as of 2026-08-02: #93 was the last open BUILD item and it shipped (`scripts/acquire_data.py`). An empty BUILD section is the correct state, not a missing one -- it means every unblocked item has been done rather than that the section was deleted._

## QUEUE — blocked, blocker named

**Blocked on data acquisition (new collectors) — the principal's own stated bottleneck:**
| # | Component | Note |
|---|---|---|
| 83 | Information Manipulation Detection (wash trading, Sybil wallets, bot social, faked dev metrics) | **High crypto ROI.** Asymmetric data that is *gamed* is worse than no data — it is adversarially wrong. Needs on-chain + venue trade data first. |
| 88 | Market Participant Identity Graph | Tier 1 crypto-specific. Wallet → exchange / MM / treasury / early-investor / retail clustering. Pairs with item 48 (wallet **risk** features only). |
| 89 | Information Velocity Tracker | Needs multi-source timestamped corpora to measure appearance → spread → price reaction. |
| 94 | Market Ecology Map | Who provides / consumes liquidity, who gets liquidated. Overlaps 88. |
| 97 | Data Decay Monitor | Needs dataset-usefulness history; nothing to trend yet. |

**Blocked on ≥1 deployed alpha (currently 0):**
| # | Component |
|---|---|
| 91 | Alpha Attribution Engine — "which data source made the money" requires money to have been made |
| 87 | Synthetic Data / Simulation Engine — robustness-testing 0 deployed alphas |
| 98 | Feature Conflict Detector — needs ≥2 live features to conflict |
| 90 | Signal Crowding Detector — needs a deployed edge plus external adoption data |

**Blocked on engineering only:**
| # | Component | Note |
|---|---|---|
| 84 | Causal Discovery Engine | **Deterministic core already exists**: `leakage_detector.py` does reverse-causality and orthogonalisation-to-confound — the two tests that separate "X causes Y" from "Y causes X" and from "Z causes both". Remaining work is the graph layer, not the statistics. |
| 85 | Data Lineage Graph | Partial: registry already pins source→commit→artifact. Missing the feature→signal→trade edges. |
| 95 | Alpha Causal Graph | Supersedes Alpha Genome (item 76) — build one, not both. |


**Blocked on OpenRouter funding:**
| # | Component |
|---|---|
| 100 | Research Knowledge Compression (papers → mechanisms) |

---

## Standing agreement with the principal's own conclusion

> *"The real remaining bottleneck is no longer architecture. It is: Data acquisition → labelling →
> experiments → deployment speed."*

Confirmed by this triage: of the 20 new items, **0 are blocked by missing architecture**. Five are
blocked by missing *collectors*, four by having *no deployed alpha*, four by ordinary engineering,
one by funding. Four are buildable now and total maybe two hours.

That is the whole argument. The desk does not need more design — it needs unique data flowing in
and one alpha flowing out. Aug 7 is the first date the second of those can change.
