# TRIAGE ADDENDUM — items 82–101, 2026-07-27

Second batch of 20 proposals, classified on the same rules. Nothing skipped.
Running total: **101 items triaged.**

---

## BUILT — already covered

| # | Component | Where | Note |
|---|---|---|---|
| 92 | Research Reproducibility Engine | `experiment_registry.py` | commit sha + artifact set pinned per experiment; 569/569 artifacts present (100%) |
| 101 | Decision Audit Trail | `experiment_registry.jsonl` + commit messages + `suggestion_ledger` | why-funded / why-promoted / why-killed already recorded per experiment |

---

## BUILD — unblocked, cheap, next session

| # | Component | Spec | Why it earns a slot |
|---|---|---|---|
| 86 | **Feature Novelty Detector** | Jaccard + mechanism-overlap of a candidate against `feature_library` and the graveyard. The dedupe already written in `research_exchange.py intake` generalises directly. | Prevents renamed factors. The desk's own history: RSI / stochastic / Williams %R are one mechanism wearing three names, and `M_PRICE_PATTERN` died once but was re-proposed repeatedly. |
| 96 | **Research Experiment Scheduler** | Order the 447 enumerated constructions by `prior × information_gain ÷ cost`. Pure ordering — no autonomy, no promotion authority. | **Corrects my earlier rejection.** I rejected the *Autonomous Research Governor* (premature at 0 alphas) and wrongly swept the scheduler in with it. Ordering a queue that already exists is not autonomy, and the queue is 447 deep with no ordering today. |
| 99 | **Market Anomaly Memory** | Append-only log of rare events: crashes, squeezes, exchange incidents, protocol failures, desk incidents. Seed with incident #6 (hedge inverted twice, 07-27). | Costs almost nothing and only accrues value with time. Starting it late is the only way to lose. Becomes the stress-test library items 87/93 need. |
| 82 | **Data Provenance extension** | Add source / collection-method / manipulation-risk / survivorship fields to the `measurement_gate` per-dataset record. | Gate already does missingness, stability, timestamp integrity, reproducibility. Provenance is the missing column, not a new engine. |

---

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
| 93 | Adaptive Data Acquisition Agent | Depends on Information Advantage Score (BUILD item 17) existing first. |

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
and one alpha flowing out. Sept 1 is the first date the second of those can change.
