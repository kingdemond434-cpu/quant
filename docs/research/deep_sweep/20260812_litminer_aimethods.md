# LIT — AI / AUTONOMOUS-RESEARCH METHODS (run 6, 2026-08-12)

Seat: AI-methods ground-digger. Ground: the engine is a dig target — better autonomous-research
design compounds faster than any single alpha.
Freeze: this file is the ONLY write. Everything else read-only. No third-party agent tooling
executed — mined as TEXT. Exact URLs per claim; open-access only.

Predecessors: run 4 = `20260731_litC_ai_methods.md` (rich; routed #86–#88), run 5 =
`20260805_LIT_ai_methods.md` (DIED at header — zero findings; this run inherits its whole plan).

## PREVIOUSLY ROUTED — do NOT re-card (delta-only, tag [ENGINE-UPDATE #id])
- #86 e-process rebuild recipe for `anytime_valid` (run 4)
- #87 IRT gate-discrimination fit for gauntlet gates (run 4)
- #88 calibrated soft voting for panel filtering (run 4)
- debate-cancellation null (three sources; stands unless new controlled evidence)

## WOUNDS (live, measured — an [ENGINE] finding must name one)
- w1 welded/never-run gauntlet gates — gate-discrimination beyond the IRT fit
- w2 anytime-valid sequential testing — 8.8× alpha inflation from daily re-reads of a fixed
  Holm bar; `anytime_valid` quarantined; want exact e-process/confidence-sequence recipe (Ramdas school, ≥2025)
- w3 self-graded forecast calibration once INVERTED and fed 6× sizing — grading design
- w4 Claude+GPT cross-family disagreement: information vs style
- w5 ~400-seat LLM panel, rotating lenses — ensemble/diversity/aggregation beyond calibrated soft voting
- w6 long-horizon memory + compaction losing session state (run 5 of THIS organ died at header)
- w7 hypothesis-generation quality (420 generated → 0 survivors; fix generation, not gates)
- w8 search-time/eval-time contamination of validation

## PLAN
A. Carry-overs: (1) arXiv 2606.05241 Search-Time Contamination — full read, operational recipe;
   (2) MemAgents (ICLR-2026 workshop) ground — strongest evidence-backed memory design since mid-2026;
   (3) appendix deltas 2606.03032 / 2509.08713 / 2606.03437; (4) NeurIPS 2026 eval-of-agents track.
B. ≥25% budget expansion: OpenReview agent/eval workshops; COLM 2026; alphaXiv/HF trending;
   METR/Apollo/Transluce/Epoch; LessWrong/AF agent-reliability; Qwen/DeepSeek/Kimi/BAAI technical
   reports (language-blind); divergent: agentic-benchmark construct validity / eval-design flaws.

Grades: [FETCHED] full text read | [ABSTRACT-ONLY] | [SEARCH-SUMMARY] (lead, never evidence).
A benchmark result without independent replication or ablation is CLAIM-grade.

---

# RUNNING NOTES (incremental; if this run dies, this is the progress)

- 2026-08-12 start. File created. Next: check run-4's locally saved PDFs
  (webfetch-1785525037382-ba0m1f.pdf = 2606.03032, webfetch-1785525035055-66xhp4.pdf = 2509.08713,
  webfetch-1785525211772-sxir4d.pdf = 2606.03437) before refetching; then 2606.05241.
- Run-4 PDFs exist on disk but are UNREADABLE here (no pdftoppm/poppler, no installs allowed) —
  mined the arXiv HTML versions instead, appendix-targeted prompts. All three resolved.
- Carry-overs (A)(1)+(A)(3) CLOSED (findings below). Then (A)(2) MemAgents ground CLOSED via the
  benchmark literature around the workshop (workshop listing itself bot-gated/thin — logged);
  (A)(4) NeurIPS-2026 = pre-deadline, carded as [VENUE] with a revisit date.
- Expansion executed: COLM 2026 (rich), HF-W33 trending, METR, Epoch, LessWrong/AF, Apollo
  (null), Chinese-lab reports (GLM-5/DeepSeek-V4/Qwen3.5/Kimi), divergent construct-validity
  query (3 orthogonal w1 lenses landed). RUN COMPLETE 2026-08-12 — file is final; DEPTH and
  NEXT-GROUND at bottom. All 8 wounds received ≥1 mapped finding; no finding is a bare citation.

---

# FINDINGS

## [ENGINE] w8 — Search-Time Contamination (STC): audit the desk's validation-search trajectories with a 3-level leakage taxonomy; condition verdicts on leakage events, don't average over them
**Source:** arXiv 2606.05241 "Search-Time Contamination in Deep Research Agents: Measuring
Performance Inflation in Public Benchmark Evaluation" (Wang, Zhang, Yao, Zeng, Song, Lin, Shen;
v1 2026-06-03). https://arxiv.org/abs/2606.05241 , full text https://arxiv.org/html/2606.05241v1 [FETCHED]
**Carry-over (A)(1) CLOSED** — run 4 left it unopened, run 5 died before it.

**What it shows.** Deep-research agents doing live web search during evaluation retrieve the
benchmark itself. Three severity levels, each with its own detector:
- **BML** (benchmark-metadata leakage): URLs exposing benchmark names/question IDs. Detector =
  regex URL matching vs two groups (common hosts: HuggingFace/GitHub/Quizlet/exam-prep; plus
  benchmark-name patterns; ~27 patterns in their Appendix G).
- **QCL** (question-context leakage): retrieved doc contains the exact question phrasing but not
  the label. Detector = longest-common-substring vs question, normalized by question length.
- **EAL** (explicit answer leakage): content contains query AND ground-truth label. Detector =
  LLM-as-judge (DeepSeek V4 Pro), judge itself validated: 83.3% recall / 100% precision on
  MedBullets5op, 94.85% precision on MedQA.
**Numbers.** 6 medical benchmarks × 5 agents (Tongyi DR primary — full trajectory observability;
Gemini DR, Step DR, Valyu DR, Qwen3-30B-A3B base). Turn-level: MedMCQA 7,543 BML + 769 EAL events
in 32,640 turns. The headline "inflation up to 4%" is the AGGREGATE; the CONDITIONAL effect is
enormous: with an EAL event present, accuracy hits 100% on HLE-149 (base 12.75%) and 97.53% on
MedMCQA. Gemini DR: 60% leakage rate on first 100 MedQA questions. Search-off ablation: Tongyi
91.28%→89.00% (MedQA), 87.34%→72.47% (MedMCQA). Whole experiment cost $858.
**Replication status:** single paper, no independent replication yet; but the detectors are
self-auditable — the desk applies them to ITS OWN logs, it does not need to trust their benchmark
numbers. Mitigations (sandbox, transparent trajectories, gated benchmarks) are proposed, NOT
measured — treat as design suggestions, not evidence.

**Operational recipe for the desk (w8 — validation contamination):**
1. **Log trajectories as evidence-of-record**: every hypothesis-validating agent run must persist
   (query, URL, retrieved snippet) tuples. A validation verdict without its trajectory is
   unauditable — same class as the desk's L1.49 "a gate that never ran".
2. **Port the taxonomy**: desk analogs are (a) BML → retrieved the hypothesis's SOURCE document
   (the SSRN/arXiv paper or forum post that proposed the factor — circular confirmation, not
   independent evidence); (b) QCL → retrieved text paraphrasing the hypothesis statement itself;
   (c) EAL → retrieved content stating the CONCLUSION (e.g., a post-publication decay study, or
   the desk's own leaked artifacts/vault text if any is public).
3. **Detector stack is cheap**: regex URL classes + normalized-LCS + one LLM-judge pass, and the
   judge gets its own positive-control validation (they did 83–100% P/R; desk law: UNMEASURED is
   an answer, so measure the judge first).
4. **Condition, don't average**: report verdict-flip rate on leakage-present vs leakage-free
   trajectories. Their data shows aggregate ≈4% masks conditional ≈100%. A desk verdict whose
   trajectory contains an EAL-class event is VOID and re-run search-blind, not down-weighted.
5. **Search-off ablation as a standing control**: run a sample of validations with search disabled
   to bound how much of the verdict is search-borne at all (their 87→72 delta shows search can
   carry real capability too — the point is to SEPARATE the channels).

## [ENGINE-UPDATE debate-null] + [ENGINE] w4/w5 — Deliberative Illusion APPENDIX numbers land: the null hardens, AND its heterogeneity table is direct evidence that cross-family panels retain information same-family panels destroy
**Source:** arXiv 2606.03032 "The Deliberative Illusion" — appendix/tables now extracted
(run 4 read main text only). https://arxiv.org/html/2606.03032v1 [FETCHED]
**Delta on the routed debate-cancellation null (stands, now quantified):**
- Multi-agent discussion erases up to **72% of issue-critical atomic facts**. Table 1: GPT-4.1
  fully-connected, News: fact retention 1.00 → 0.204 by round 3 (−79.6%); Ethics → 0.465.
  Per-round attrition is monotone (R1 −19–21%, R2 −19–25%, R3 −20–33%) — MORE rounds is MORE loss.
- Final judgment wrong in **19.2%** of non-controversial cases where the base model with full
  context succeeded (Sec 5.2). No condition found where deliberation helped. Null HARDENS.
- **Prior anchoring (Table 3): multi-agent majorities match the base model's direct output 65–76%
  of the time** — a same-family panel majority is largely a resample of one prior.
- Adversarial fragility (Sec 5.5): ONE malicious agent → 58.9% of final outputs carry the injected
  falsehood; 37.4% of honest agents adopt it; retention collapses 46.5%→19.3%.
**The NEW part for w4 (cross-family information vs style):** Table 4, News domain, round 3:
**cross-series teams (GPT/Gemini/Qwen) retain 0.598** of critical facts vs **same-series 0.357**
— +67% relative retention from family diversity alone. Combined with the 65–76% prior-anchoring
number, this is the cleanest published support yet for the desk's doctrine: same-family agreement
is mostly STYLE/prior echo; cross-family disagreement is where information lives.
**Operational recipe (w5, ~400-seat panel):**
1. Any panel stage that lets seats SEE each other's outputs (deliberation/reconciliation) should
   be capped at ZERO or ONE round; per-round attrition is monotone. Independent elicitation +
   calibrated aggregation (routed #88) remains the right architecture.
2. Weight cross-family disagreement as signal: log per-seat model family; when Claude-block and
   GPT-block DISAGREE, that disagreement itself is an information event (route to human/deeper
   test), not noise to average away. When same-family seats agree, discount toward n_eff ≈ 1
   (their 0.65–0.76 anchoring says the marginal same-family seat adds little).
3. Poisoning surface: one compromised seat's text propagating through shared-context stages is an
   attack/contamination vector (58.9% adoption) — another reason panel stages must be
   independent-elicitation-only.
**Replication status:** single paper but internally controlled (3 model families, 2 topologies,
positive/negative domains); consistent with the desk's three older debate-null sources. CLAIM→
EVIDENCE grade for the null; the heterogeneity table is one paper, treat as strong lead needing
desk-local measurement (desk CAN measure: it logs per-seat families already — reanalysis, no new runs).

## [ENGINE] w7 (+w1 audit) — Hidden Pitfalls APPENDIX rates: menu-ORDER drives agent "choices" (up to 100% first-listed selection), and LLM-audit WITH logs+code beats paper-only audit 74.0% vs 51.4%
**Source:** arXiv 2509.08713 "Hidden Pitfalls of AI Scientist Systems" — appendix quantitative
rates now extracted (run 4 had taxonomy only). https://arxiv.org/html/2509.08713v1 [FETCHED]
**Measured rates (Agent Laboratory + AI Scientist v2, on synthetic SPR tasks chosen to be outside
pretraining corpora):**
- Benchmark selection: Agent Laboratory picked the FIRST FOUR listed benchmarks 82.4% of the time
  (79.6% without SOTA hints); AI Scientist v2 prefers high-SOTA benchmarks (p<1e-30, Cramér's V=0.346).
- Metric misuse: **100% ordering dependence** — whichever metric was listed first got used (Tables 7–8).
- Post-hoc selection bias: under manipulated rankings, top-candidate selection fell 78.5%→43.5%
  (AgentLab) and 82.0%→31.5% (AISv2), with worst-ranked selection rising 0%→49.0% (χ²=179.59) —
  agents cherry-pick what looks good post hoc.
- Data leakage: rarer as pre-defined behaviors (1/20 runs exceeded a theoretical bound) but 5/20
  AISv2 runs did UNREPORTED subsampling/synthetic-data substitution — silent protocol drift.
- **Mitigation, now MEASURED** (run 4 recorded "not measured" — that changes): LLM-auditor
  detection of the four pitfalls from the PAPER alone = 51.4% acc / F1 0.48; given LOG TRACES +
  GENERATED CODE = 74.0% / F1 0.75 (p<1e-7 Bonferroni; +15–35% per pitfall).
**Operational recipe (w7 — the 420→0 generation wound):**
1. **Ordering is a hidden confounder in every desk generation/selection prompt.** Any organ that
   presents candidate lists (hypotheses, data axes, metrics, benchmarks) to an LLM must randomize
   list order per call and LOG the permutation; measure the desk's own ordering sensitivity (cheap
   reanalysis if permutations were logged; else a 20-call experiment). If hypothesis selection is
   ~order-driven, the 420 candidates were never really "chosen" — the menu was.
2. **Silent protocol drift is a generation-side defect class**: 25% of runs quietly subsampled or
   synthesized data. Desk analog: generation organs that quietly narrow universe/date-range emit
   hypotheses that LOOK testable but aren't — require a machine-checkable protocol block
   (universe, dates, n) attached at GENERATION time, diffed at gate time.
3. **Audit organs must read logs+code, not summaries** (74% vs 51%): any desk self-audit (incl. w1
   gate audits) that grades from reports alone is measurably half-blind. The desk's existing
   instinct ("assert the built artifact, not the declaration") now has an external effect size.
**Replication status:** controlled, pre-registered-style protocol on 2 open-source systems;
no independent replication yet; effect sizes huge and mechanism (ordering bias) is one of the
best-replicated LLM phenomena generally. High confidence for recipe items 1 and 3.

## [ENGINE] w3 — 2606.03437 is an OWNERSHIP-BIAS paper (run 4's note mischaracterized it): models rate THEIR OWN answers up to 26% more confident; re-framing the answer as USER input removes most of it — the exact mechanism class behind the desk's calibration inversion
**Source:** arXiv 2606.03437 (confidence elicitation under Assistant-vs-User framing).
https://arxiv.org/html/2606.03437v1 [FETCHED]
**Correction of the run-4 record:** run 4 logged this as "self-critique+consistency beat naive
verbalization" — the paper actually isolates **ownership bias**: an LLM assigns systematically
higher confidence to answers framed as ITS OWN vs identical answers framed as user-provided.
Table 3 (MMLU), Assistant-vs-User framing deltas: ΔECE 0.098 (P(True)) / 0.179 (verbalized %) /
0.261 (linguistic Likert); ΔBrier 0.088/0.195/0.252; Δconfidence up to +0.268. Fix proposed:
**present the model's answer back as user input when eliciting confidence** — no retraining,
inference-time only. Limitation: open-weight models only (cost), MMLU-style tasks.
**Why this is the desk's wound:** w3 = self-graded forecasts INVERTED calibration and fed 6×
sizing. Grading design that lets the grader see the forecast as its own output sits exactly in
this bias class (compounded by the desk's already-fixed self-grading loop). The paper gives the
cheapest known de-biasing knob.
**Operational recipe:**
1. Every confidence/probability elicitation in the desk (hypothesis priors, forecast logging
   for L1.29, verdict confidence) should present the item as USER-provided third-party text
   ("A researcher proposes X; probability it's right?") — never "you concluded X; how confident?".
2. Prefer P(True)-style scoring over linguistic Likert scales — ownership distortion was 2.7×
   larger for linguistic (0.261 vs 0.098 ECE delta); the desk's rotating-lens prompts that ask for
   qualitative conviction labels are in the WORST bucket.
3. Separate generator and grader model instances (fresh context) so the grader has no "ownership"
   trace — aligns with the desk's existing generator/grader split; this paper says the SPLIT
   ALONE is worth ECE ~0.1–0.26 depending on elicitation format.
**Replication status:** single paper, open-weight models; mechanism consistent with the broader
self-preference/self-recognition literature (LLM-judge self-bias). Desk can A/B it on its own
logged forecasts for free.

## [ENGINE] w6 — Agent-memory evidence since mid-2026 CONVERGES on the desk's existing design: file-based/coding-agent memory beats RAG at long horizon, commercial memory products lose to BM25, LLM-summary compaction buys nothing, and NOTHING can do selective forgetting — so explicit supersession ledgering is load-bearing
**Carry-over (A)(2) CLOSED.** MemAgents-the-workshop (ICLR 2026, ran 2026-04-27;
https://openreview.net/forum?id=U51WxL382H , site https://sites.google.com/view/memagent-iclr26/ )
publishes no accepted-paper list on its site and OpenReview is bot-gated [NULL on the listing
itself] — but the GROUND around it yielded three quantitative anchors:

1. **MemoryAgentBench** (arXiv 2507.05257, ICLR 2026; code MIT https://github.com/HUST-AI-HYZ/MemoryAgentBench ,
   data on HF) — four competencies: Accurate Retrieval / Test-Time Learning / Long-Range
   Understanding / Selective Forgetting. [FETCHED]
   - **Commercial memory products LOSE to plain BM25 RAG on retrieval**: Mem0 32.6%, Cognee 28.3%,
     Zep 37.5%, MIRIX 47.5% vs **BM25 60.5%** (AR average). Long-context GPT-4o dominates LRU
     (54.9% vs RAG 19.9–36.3%).
   - **Selective forgetting fails universally**: multi-hop fact consolidation ≤28% for EVERY
     method (single-hop max 78% only for GPT-5-mini long-context). "Forgetting out-of-date
     memory poses a significant challenge" — no architecture masters all four competencies.
2. **LongMemEval-V2** (arXiv 2605.12493, CC-BY) — 451 questions over histories up to **115M
   tokens**. **Coding-agent-style memory (reads/writes files, AgentRunbook-C) 72.5% vs RAG-based
   48.5%**; even an off-the-shelf coding agent hits 69.3%. At extreme horizon, file-manipulating
   memory beats embedding retrieval by ~24 points; cost is latency. [FETCHED abstract+key results]
3. **Memory condensation for coding agents in scientific discovery** (arXiv 2605.18854;
   DiscoveryBench, 60 tasks × 6 domains = 480 evals, GPT-4o): **8 condensation strategies — "no
   condenser significantly alters hypothesis quality"**; LLM-generated-summary condensers COST
   +24–94% tokens; best net saving is structural: masking old tool-call outputs (8.6% net).
   Compaction in this regime is a COST knob, not a quality knob. [FETCHED abstract]

**Desk mapping (w6 — run 5 of this organ died leaving a header; compaction loses session state):**
- The desk's memory stack (Obsidian vault + BM25 `vault_search` + MEMORY.md + running-notes files)
  is the EVIDENCE-FAVORED architecture on all three anchors: BM25 beat the memory products; the
  file-writing coding agent beat RAG at horizon; and the vault IS the desk's answer to
  no-architecture-masters-everything. Do NOT adopt Mem0/Letta/Zep-class products — carding this
  as a measured null so no future session re-opens it.
- **The binding constraint is selective forgetting (≤28% multi-hop)**: no machine can be trusted
  to propagate a supersession through derived facts. The desk's laws ("correct ≠ amend",
  supersession notes in MEMORY.md, COVERAGE ratchet supersedes stale numbers) are load-bearing;
  the recipe is: every memory WRITE that invalidates a prior fact must NAME the superseded row
  (the desk's newest-first MEMORY.md with explicit "superseded by" lines is exactly right; an
  agent reading both rows cannot be assumed to resolve the conflict itself).
- **Compaction policy**: prefer structural masking (drop stale tool outputs/raw dumps) over
  LLM re-summarization; evidence says re-summarization costs more and preserves no more task-
  relevant state. For organ continuity the winning move remains WRITE-AHEAD state (deliverable
  file first, plan + running notes, updated incrementally) — which is this run's own protocol and
  why run 5's death cost a header, not knowledge.
**Replication status:** MemoryAgentBench is peer-reviewed (ICLR 2026) with public code+data;
LongMemEval-V2 and 2605.18854 are single-team preprints — directionally consistent with each
other and with MemoryAgentBench, which is itself a second source for "simple baselines beat
memory products". Convergent enough to act on for DESK-INTERNAL design (no capital path).

## [VENUE] mem0.ai "State of AI Agent Memory 2026" — vendor blog (https://mem0.ai/blog/state-of-ai-agent-memory-2026 , /ai-memory-benchmarks-in-2026): maps the benchmark landscape (LoCoMo, LongMemEval, BEAM) but is MARKETING by a party MemoryAgentBench measured losing to BM25. Yield: field map only. Worth revisiting: NO for claims, maybe for benchmark-name discovery. [SEARCH-SUMMARY]

## [ENGINE] w1 — PREDICTIVE validity of a gauntlet: score the gate battery by whether its in-sample ranking TRANSFERS (Spearman in-sample vs OOS rank), with published falsification thresholds; field evidence shows a leaderboard can have ρ ≈ −0.13 with its own hidden set
**Source:** arXiv 2606.19704 "Beyond Static Leaderboards: Predictive Validity for the Evaluation
of LLM Agents" (Patel et al., 61 authors — AssetOpsBench/IBM orbit; June 2026).
https://arxiv.org/abs/2606.19704 , https://arxiv.org/html/2606.19704 [FETCHED]
**Epistemic status — read carefully:** this is a POSITION paper with a pre-registered pilot
DEFERRED to future work ("commitment to publish the position as refuted if..."). Its load-bearing
EMPIRICS are retrospective: **CODS-2025 AssetOpsBench challenge (149 teams): public-leaderboard
vs hidden-set rank correlation ρ=−0.13 on the execution track (n=13, indistinguishable from
zero); ρ=0.69 on planning (n=20)**; plus cross-benchmark rank correlations 0.32–0.85 across six
benchmarks (Exgentic). I.e., a real, competently run eval produced a ranking with ZERO transfer.
**Method (portable):** rank configurations by predictive validity, not in-sample mean:
PV(c) = α·Ȳc − β·σ_rank,OOD(c) − γ·IQR(Yc) — reward mean, penalize rank instability across OOD
criteria and per-scenario dispersion. Three OOD criteria: (A) stratified held-out split (mild);
(B) cross-subset rotation — rank on k−1 subsets, test on held-out, rotate (moderate); (C)
semantic-equivalent perturbation: paraphrase / identifier renaming / time-window shifting /
distractor injection (strong). Falsification thresholds stated exactly: ρ_Spearman(in-sample,
OOD)<0.85 on ≥2 of 3 criteria; top-3 in-sample leaving top-5 OOD in ≥10% of splits; PV-vs-mean
top-10 Jaccard <0.85.
**Why orthogonal to routed #87 (IRT fit):** IRT measures per-gate DISCRIMINATION on a latent
trait — a gate can discriminate beautifully in-sample and still rank hypotheses in an order that
does not survive out-of-sample. PV measures the TRANSFER of the ordering itself. The two compose:
IRT for which gates carry information, PV for whether the battery's verdict ordering predicts
forward reality.
**Operational recipe (desk gauntlet):**
1. Compute, retrospectively and for free from the ledger: Spearman between gate-time hypothesis
   ranking and realized OOS/forward ranking, per cohort. If it's ≈0 (the CODS execution-track
   outcome), the gauntlet ORDER carries no information even where individual gates do — a
   different defect than welded thresholds, invisible to pass/fail tallies AND to IRT.
2. Criterion-B ports directly: rank hypotheses on k−1 time-folds, test ordering on the held-out
   fold, rotate. Criterion-C ports as robustness: re-score the same hypothesis under
   parameter-neighborhood / time-window-shift perturbation; a verdict that flips under
   semantically-equivalent respecification is dispersion (the γ·IQR term), and PV says to
   PENALIZE it explicitly, not average it away.
3. Adopt their falsification framing: pre-register the thresholds (they published theirs) so the
   gauntlet-quality claim is itself testable — the desk's L1.49 ethos applied to the gauntlet.
**Replication status:** the ρ=−0.13 retrospective is real published competition data; the PV
formula is UNVALIDATED (pilot pending, weights α,β,γ unfitted). Card the MEASUREMENT (recipe 1–2)
as evidence-backed; the composite PV score as CLAIM-grade design to try, not truth.

## [ENGINE] w1/w7 — Construct-validity audit of 445 LLM benchmarks (NeurIPS 2025, 29 reviewers): the 8-recommendation checklist ports to the desk's gate battery, and the field's base rates say a gate-spec without a phenomenon definition is the NORM, not an oversight
**Source:** arXiv 2511.04703 "Measuring what Matters: Construct Validity in Large Language Model
Benchmarks" (Salaudeen et al.; NeurIPS 2025; Oxford ORA copy exists).
https://arxiv.org/abs/2511.04703 , https://arxiv.org/html/2511.04703v1 ,
https://openreview.net/forum?id=mdA5lVvNcU [FETCHED]
**Base rates across 445 benchmarks:** 21.8% give NO definition of the phenomenon they claim to
measure; 47.8% of those that do use contested definitions; **only 16.0% run ANY statistical
test/uncertainty estimate when comparing models**; 27.0% convenience-sample (39.5% partially);
42.6% reuse prior datasets without addressing validity implications; 46.6% offer no construct-
validity evidence at all; human baselines in 32.4%.
**The eight recommendations (near-verbatim):** (1) define the phenomenon (operational definition,
scope, sub-components measured separately); (2) measure the phenomenon and ONLY it (control
confounds, format effects, validate parsing); (3) representative dataset (sampling strategy,
known-sensitivity probes); (4) acknowledge limits of reused data; (5) prepare for contamination
(detection tests, held-out items); (6) statistical methods + power + uncertainty; (7) error
analysis of failures/scoring bias; (8) justify construct validity (tie to the real-world target).
**Desk mapping:** the gauntlet IS a benchmark battery whose construct is "will this hypothesis
make money OOS, after costs". Two gaps the checklist exposes that the desk's existing law does
not already cover: (a) **no per-gate construct statement exists** — one paragraph per gate naming
its phenomenon, its confounds and its known false-kill modes (rec 1/2/8) would have caught the
already-documented DSR-bar design defect (bar requires true SR≈5 at T=310 — a construct failure,
not a threshold failure) BEFORE 420 hypotheses were spent against it; (b) **error analysis on the
KILLED population** (rec 7): the desk measured 86% OOS decay on rejects once — make that a
standing per-cohort report (false-kill rate estimate), which is also the empirical input PV
(above) and IRT (#87) both need.
**Replication status:** peer-reviewed systematic review, 29 expert reviewers, methodology
explicit; base rates are as solid as this literature gets. The PORT to trading-gauntlet is the
desk's own analogy — mark the mapping desk-derived, the numbers external.

## [VENUE] (A)(4) NeurIPS 2026 eval-of-agents ground — nothing accepted/published YET (deadline 2026-08-29, decisions 09-29); the public artifact today is the topic list, which reads like the desk's wound list; revisit ~2026-10
- **Evaluation of Interactive Agents @ NeurIPS 2026** https://eval-interactive-agents-workshop.github.io/
  [FETCHED] — organizers Dou/Li/Abdulhai/Tomlin/Galley/Eisenstein/Ritter/Xu (GaTech, Columbia,
  Princeton, TTIC, MSR, GDM). Topics verbatim include: "Trajectory-level evaluation, including
  transcripts, tool calls, intermediate states"; "Grader design, including deterministic checks,
  model-based rubrics, human evaluation, and calibration"; "Validation of user simulators";
  "Benchmarks for long-horizon interaction, memory, adaptation, error recovery, and reliability".
  Grader-design-as-topic confirms w3's framing is where the field is moving. No papers listed yet.
- **NeurIPS 2026 Evaluations & Datasets track** https://neurips.cc/Conferences/2026/CallForEvaluationsDatasets
  + https://openreview.net/group?id=NeurIPS.cc%2F2026%2FEvaluations_and_Datasets_Track — CfP
  explicitly welcomes "benchmark saturation" analyses and "rigorous reproduction and auditing of
  prior evaluations" — an institutional home for the construct-validity literature above.
- **TTCL workshop** (test-time continual learning agents) https://ttcl-agents.github.io/ hosts a
  community challenge on an "AgentOdyssey" benchmark — potential [DATA-LOOT], unverified
  license/content this run.
- Verdict: ground OPENS in ~7 weeks. NEXT-GROUND candidate with a date, not a null.

## [ENGINE-UPDATE #86] w2 — the e-process recipe now has a WORKED practice guide + software: GROW-optimal betting fraction, expected-N formula, the exact "what may be re-read daily" permission, and e-BH for dependent multiplicity
**Source:** arXiv 2602.06379 "E-values for Adaptive Clinical Trials: Anytime-Valid Monitoring in
Practice" (Feb 2026). https://arxiv.org/html/2602.06379 [FETCHED]. R package `evalinger`
(https://github.com/VadimSokolov/evalinger) + established `safestats`.
**Delta on routed #86 (which was the rebuild recipe in principle):** this paper is the missing
OPERATIONS MANUAL. The pieces the desk's `anytime_valid` rebuild needs, exactly:
1. **Construction by data type**: binary/bounded → betting martingale E_n = Π(1+λ_i·D_i) with
   predictable λ_i; continuous effects → method of mixtures; existing p-values → calibrators.
2. **Design calibration BEFORE the run** (the desk's preregistration slot): GROW-optimal
   λ* = [p_T(1−p_C) − (1−p_T)p_C] / [p_T(1−p_C) + (1−p_T)p_C] for the design alternative;
   expected sample size N ≈ log(1/α)/g(λ*). Power is HIGHLY sensitive to λ (their Table 3) —
   fit λ to the pre-registered effect size, then simulate operating characteristics under null
   and alternative. This replaces the desk's "how long must a forward test run" guesswork with a
   formula tied to the kill criterion.
3. **The exact re-read permission (the 8.8× wound's fix, stated as law):** the threshold
   E_t ≥ 1/α is CONSTANT across all looks (Ville: P(sup E_n ≥ 1/α) ≤ α). Any peeking cadence,
   any data-dependent stopping, unplanned looks — all valid. The always-valid p is
   p_t = 1/sup_{s≤t} E_s (monotone — cannot inflate by re-reading). CONSTRAINT: every adaptation
   (re-tuning λ, dropping arms, resizing) must be a PREDICTABLE function of past data only —
   the desk's self-tuning organs must timestamp tuning inputs strictly before the data they bet on.
4. **Multiplicity across the hypothesis book**: per-hypothesis e-processes; graduation at
   E^(k) ≥ 1/α_k with Σα_k ≤ α; for FDR-style control use **e-BH (Wang–Ramdas 2022)** — and the
   load-bearing fact for a desk whose hypotheses are CORRELATED: the arithmetic MEAN of
   arbitrarily-dependent e-values is still an e-value; products require independence. Frozen
   e-processes for killed hypotheses; fresh processes for new arrivals — matches the desk's
   rolling hypothesis book exactly.
**Replication status:** the math is the mature Ramdas-school corpus (Ville/GROW/e-BH all
peer-reviewed elsewhere); this paper contributes the assembled workflow + simulation checks +
software. Supporting practice evidence: enterprise deployment at scale in A/B testing
(arXiv 2302.10108, Adobe). The desk should still NOT import the R package (supply-chain rule);
the formulas above are sufficient to reimplement in-repo with tests.

## [ENGINE] w6 — reliability-science framing for organs: report survival/decay curves by task duration, not pass-rates; "meltdown" is a frontier-model failure mode (up to 19%) CAUSED by ambitious multi-step strategies
**Source:** arXiv 2603.29231 "Beyond pass@1: A Reliability Science Framework for Long-Horizon LLM
Agents" (Khanal, Tao, Zhou). https://arxiv.org/abs/2603.29231 [FETCHED abstract-level].
10 models × 23,392 episodes × 396 tasks in four duration buckets. Metrics: Reliability Decay
Curve, Variance Amplification Factor, Graceful Degradation Score, Meltdown Onset Point.
Findings: reliability decay is DOMAIN-STRATIFIED (software-eng GDS 0.90→0.44 across durations;
document processing flat 0.74→0.71); frontier models show the HIGHEST meltdown rates (≤19%)
"because they attempt ambitious multi-step strategies that sometimes spiral".
**Desk mapping (w6):** the desk already lives this (run 5 died at header; organs crash-after-
write). Recipe: (1) per-organ, log duration-bucketed completion curves (the desk's ledgers allow
this retrospectively) — an organ with a cliff-shaped RDC needs checkpoint cadence set BEFORE its
Meltdown Onset Point, i.e., write-ahead intervals chosen from the measured curve, not habit;
(2) treat "ambitious plan spiral" as a named failure class for planner-style organs — cap plan
depth for long-duration duties. **Replication status:** single-team preprint, metrics unaudited —
CLAIM-grade names, but the desk needs no external validity: fit the curves to ITS OWN organ logs.

## [ENGINE] w7 — ForeSci: benchmark the GENERATOR, not the hypotheses — cutoff-aligned judgment tasks + the named failure mode "evidence–decision decoupling"
**Source:** arXiv 2606.00644 "ForeSci: Evaluating LLM Agents for Forward-Looking AI Research
Judgment" (CC-BY 4.0). https://arxiv.org/abs/2606.00644 [FETCHED abstract-level]. 500 tasks,
4 domains × 4 decision families; each task = a decision made from a CUTOFF-ALIGNED offline
knowledge base, with post-cutoff literature hidden and used only for scoring.
Key diagnostic: **evidence–decision decoupling** — agents cite the RIGHT evidence and still
forecast the WRONG research object; "explicit evidence organization improves traceability...
but gains depend strongly on the decision family".
**Desk mapping (w7 — 420→0):** the desk grades hypotheses; it has never graded the GENERATOR.
Port the design: run the generation organ as-of historical dates T (pre-T vault/data only),
score its picks against realized post-T outcomes the desk already knows (its own ledger of what
survived OOS, plus published post-T decay studies). This yields a generation-quality time series
independent of the gauntlet — fixing generation without touching gates, exactly the wound's
constraint. Also adopt the decoupling check: for each generated hypothesis, require the organ to
name WHICH evidence item drives it; audit whether the cited evidence actually supports that
specific object (their failure mode says citation-relevance is NOT decision-correctness).
**Replication status:** single benchmark paper, no independent replication; but the desk port is
a design pattern (temporal-cutoff backtesting of generators) whose validity is self-evident to a
quant desk — it is literally backtesting, applied to the research organ.

## [ENGINE] w4/w5 — Behavioral-entanglement audit (COLM 2026): measure whether desk seats' co-failures EXCEED what task difficulty predicts; within-family entanglement is strongest, frontier closed models are converging on each other, and pairwise entanglement PREDICTS judge bias (ρ≈0.5) — but note the honest null: entanglement-aware reweighting beat plain accuracy-weighting by only +0.001
**Source:** arXiv 2604.07650 "How Independent are Large Language Models? A Statistical Framework
for Auditing Behavioral Entanglement and Reweighting Verifier Ensembles" (Kuai et al., Apr 2026;
COLM 2026 accepted). https://arxiv.org/abs/2604.07650 , https://arxiv.org/html/2604.07650 [FETCHED]
**Method (fully portable, formulas extracted):**
- **BEI(i,j) = (1/T)·Σ_t a_t^w·(Y_i,t·Y_j,t − p_i,t·p_j,t)** — excess co-failure beyond a
  conditional-independence-given-difficulty null; a_t^w=(1−d_t)^w up-weights EASY tasks (both
  models "should" succeed ⇒ joint failure = shared blind spot); d_t = mean failure rate of the
  other models; p_m(d) fit by logistic regression; significance via Monte-Carlo null + BH-FDR.
  w∈[1,2] transfers best.
- **CIG** adds direction: on co-failures, do the two models pick the SAME wrong answer more than
  distractor-attractiveness predicts (surprisal-weighted collision rate)? MCQ-native.
- **Reweighting**: verifier weight ∝ q_m^κ·exp(−η1·R_m − η2·T_m^(S)) — competence, minus
  redundancy-with-other-verifiers, minus entanglement-with-the-TARGET-model-being-judged.
**Empirics:** within-lineage BEI largest (Llama-3-70B vs 3.1-70B: 0.0525, p<1e-4; Qwen1.5 pairs
0.033–0.040); FEWER significant open↔closed pairs; BUT CIG finds a frontier cross-family cluster
(GPT-5, Claude 4.6, Gemini-3.1-pro) — frontier models are converging via shared data/distillation.
**Pairwise entanglement predicts LLM-as-judge bias: ρ=0.508/0.520 (BEI/CIG, MMLU-Pro, p<0.01)**,
transfers to MATH-500 (ρ≈0.44–0.46); plain Pearson/MI correlations do NOT predict it. Ensemble
result: majority vote 84.7% → accuracy-reweighted 88.1% → entanglement-aware 88.2% — the
entanglement TERM adds +0.001 over competence weighting in their 3-verifier setup (the AUDIT is
the value; the reweighting gain over #88-style weighting is ~nil at n=3 verifiers).
**Limitations (theirs):** pairwise only; CIG needs MCQ structure; association not causation;
model-version snapshots; English-only.
**Operational recipe (delta over routed #88, which stays):**
1. **Run the BEI audit on the desk's OWN seat logs** — the desk has exactly the required data
   (per-seat, per-task verdicts + realized outcomes to define failure). Compute excess co-failure
   conditional on task difficulty for Claude-seat pairs, GPT-seat pairs, and cross-family pairs.
   This turns "does our 400-seat panel have n_eff ≈ 4?" from a fear into a statistic — and it is
   the direct measurement behind the Deliberative-Illusion prior-anchoring concern above.
2. **Judge-target dependence term (T_m^(S)) is the new idea worth stealing**: when a seat
   VERIFIES an artifact produced by its own family, discount its verdict — entanglement with the
   producer predicts bias at ρ≈0.5. Desk rule: cross-family verification by default; same-family
   verification gets an explicit haircut (size TBD by the desk's own BEI fit).
3. Do NOT expect aggregation-accuracy gains from entanglement-aware WEIGHTS beyond calibrated
   competence weights (+0.001 measured) — route effort to the audit + judge-assignment policy,
   not a fancier voting formula.
**Replication status:** COLM-accepted, single team; formulas + algorithms fully published,
Monte-Carlo nulls + FDR done properly; the judge-bias correlation replicated across two
benchmarks in-paper. Strongest new panel-methods paper found this run.

## [ENGINE] w1/w8 — rubric-scanner audits of the desk's OWN harness transcripts: the 2026 literature found ground-truth access, tool-failures-read-as-nulls, format ambiguity and guessability inside 9 major agentic benchmarks — the desk's gauntlet harness has the same four flaw classes and the same detection recipe applies
**Sources:** arXiv 2607.27518 "Automated Transcript Analysis for Detecting Flaws in Agentic
Benchmarks" (July 2026; built on UK-AISI-ecosystem Inspect Scout).
https://arxiv.org/html/2607.27518 [FETCHED]. Context tool: Transluce's Docent
(https://transluce.org/docent , LW writeup https://www.lesswrong.com/posts/Mj276hooL3Mncs3uv/analyzing-long-agent-transcripts-docent )
— NOT to be installed (supply-chain rule); method mined as text.
**Flaw taxonomy (their 4 classes, with desk analogs):**
1. **Ground-truth access** — task-success info reachable by the agent (SWE-Bench-Verified: git
   history containing the exact patch; CVE-Bench: memorized exploits). Desk analog: lookahead in
   a conditioning variable (the desk's OWN RFB 42/42-months case), vault text containing a
   study's answer, fixtures leaking into live stores (desk's L1.29 fixtures bug).
2. **Tool failures** read as capability/nulls — desk analog is literally WS-005 (absence
   resolving to a clean verdict) + "crash-after-write reads as organ-dead".
3. **Answer-format ambiguity** — under-specified output structure/units/precision. Desk analog:
   gates parsing study outputs where a formatting change silently zeroes a metric.
4. **Guessing vulnerability** — task passable by chance (Terminal-Bench-2.0 task with 10% guess
   rate). Desk analog: a gate whose pass-probability under a NULL hypothesis is materially >0 —
   exactly the vacuous-pass class L1.57 fences (18/40 vacuous) already fight.
**Recipe (theirs, portable as-is):** write one rubric per flaw class with a 0–3 severity scale;
run TWO scanner models independently over stratified samples of transcripts (~25 flagged/25
unflagged per target); human-validate flagged ones by consensus rubric; reweight for the
stratification; report scanner sensitivity/specificity against the human sample. Their measured
scanner quality is UNEVEN and that is the honest core: guessing scanner F1=0.74/sens 0.93, but
tool-failure scanner F1=0.14 — transcript-level detection of environment failure is HARD, so the
desk must keep its structural detectors (exit codes, ENOENT-in-log content checks) and use LLM
scanners only where they measured well (ground-truth access 0.42–0.70 sens, guessing 0.93).
**Evidence this pays:** Docent's earlier InterCode audit — fixing scaffolding issues raised
GPT-4o solve rate 68.6%→78.0% (9.4pp of "capability" was harness bugs); 2607.27518 found
previously unreported flaws in SWE-Bench-Verified/CORE-Bench/CVE-Bench/KernelBench/Terminal-Bench-2.0.
**Replication status:** two independent tool lineages (Docent; Inspect Scout) finding the same
flaw classes in overlapping benchmarks = the closest thing to replication in this literature;
scanner F1s are self-reported; human-grader agreement "modest" (their own caveat).

## [ENGINE] w6 (second source) — Princeton HAL "Towards a Science of AI Agent Reliability" (ICML 2026): 12 metrics on 4 dimensions (consistency/robustness/predictability/safety), 15 models — capability gains yield only SMALL reliability gains; strengthens the reliability-curve recipe above
**Source:** arXiv 2602.16666 (Rabanser, Kapoor, Kirgis, Liu, Utpala, Narayanan — Princeton;
ICML 2026; live dashboard hal.cs.princeton.edu/reliability). https://arxiv.org/abs/2602.16666
[FETCHED abstract-level]. Together with 2603.29231 (above) this is now a two-source pattern:
single success metrics obscure operational flaws; reliability must be measured as its own
dimension and does NOT come free with newer models. Desk consequence: never upgrade an organ's
model and assume reliability followed capability — re-measure the organ's decay/consistency
curves after any model swap (the desk's llm-auto-upgrade branch is live context for exactly this).

## [VENUE] COLM 2026 accepted-papers list — HIGH yield, first desk visit; revisit each cycle
**URL:** https://colmweb.org/AcceptedPapers.html [FETCHED, full list scanned by category]
Wound-mapped shortlist worth future digs (titles verbatim):
- w1: "What AI Benchmarks Actually Measure: Adapting Convergent and Discriminant Validity to
  Interrogate Fifty-Six AI Benchmarks" (dug below); "Who Guards the Benchmarks? Automated
  Auditing of LLM Agent Benchmarks" (third benchmark-audit lineage); "Measuring Five-Nines
  Reliability: Sample-Efficient LLM Evaluation in Saturated Benchmarks"; "Benchmark Designers
  Should 'Train on the Test Set' to Expose Exploitable Non-Visual Shortcuts".
- w3: "CONCORD: Label-Free Calibration of Verbalized LLM Confidence via Rollout Consistency";
  "Self-Preference Bias in Rubric-Based Evaluation" (independent support for the ownership-bias
  finding above); "Wired for Overconfidence: A Mechanistic Perspective on Inflated Verbalized
  Confidence"; "BAS: A Decision-Theoretic Approach to Evaluating LLM Confidence".
- w5: "Rubrics as an Attack Surface: Stealthy Preference Drift in LLM Judges"; "Misalignment
  Contagion: Can a Misaligned Minority Shift Aligned Agents in Multi-Agent LLM Deliberation?"
  (independent line matching Deliberative-Illusion injection result); "No Free Labels:
  Limitations of LLM-as-a-Judge Without Human Grounding".
- w6: "TierMem: Balancing Compressed Memory and Raw Evidence" (the compaction tradeoff, named);
  "Unable to Forget: Proactive Interference Reveals Working Memory Limits" (supports the
  selective-forgetting wall); "MEMENTO: Teaching LLMs to Manage Their Context"; "InjecMEM:
  Memory Injection Attack on LLM Agent Memory Systems" (vault-poisoning threat class).
- w7: "ResearcherBench"; "REVERE: Reflective Evolving Research Engineer"; "InfiniteScienceGym:
  An Unbounded, Procedurally-Generated Benchmark for Scientific Analysis" ([DATA-LOOT] candidate:
  procedurally generated ⇒ contamination-free by construction, the SPR trick from 2509.08713).
Verdict: richest single venue visited this run; the desk had never looked at COLM. REVISIT: yes,
every litminer run.

## [ENGINE] w1 — third orthogonal gate-quality lens: CONVERGENT/DISCRIMINANT validity (multitrait-multimethod) — gates claiming different constructs that correlate ≈1 are a redundant battery; the desk's "12 slots = 4.56 effective bets" already measured the symptom, this names the diagnostic
**Sources:** COLM 2026 accepted title "What AI Benchmarks Actually Measure: Adapting Convergent
and Discriminant Validity to Interrogate Fifty-Six AI Benchmarks" (public full text NOT found
this run — [SEARCH-SUMMARY], title+venue only); method demonstrated in the open in CogArena
(arXiv 2607.24999, 55 LLMs, convergent+discriminant analyses of cognitive-ability structure,
https://arxiv.org/html/2607.24999v1 ) and framed in "Measurement to Meaning: A Validity-Centered
Framework for AI Evaluation" (arXiv 2505.10573, https://arxiv.org/html/2505.10573v3 ).
Related IRT-extension lead: DualEval "Joint Model-Item Calibration" (arXiv 2606.26429).
**The method (textbook psychometrics, Campbell–Fiske MTMM, zero hype risk):** compute the
correlation matrix of gate scores across the hypothesis population. Convergent validity: gates
claiming the SAME construct (e.g., two overfitting screens) should correlate highly — if not,
at least one measures noise. Discriminant validity: gates claiming DIFFERENT constructs (skill
vs capacity vs robustness vs cost-survival) should NOT correlate near 1 — if they do, the
battery's nominal breadth is fictional and the desk is re-testing one construct N times while
believing it tested N things (this also silently breaks any multiplicity accounting that assumes
gate independence).
**Composition with the other two w1 lenses:** IRT (#87) = per-gate information; predictive
validity (this run) = does the ordering transfer; MTMM (this) = does the BATTERY's claimed
construct structure exist. All three are computable from the desk's existing gate-score ledger
with no new runs.
**Replication status:** the psychometric method is 65 years old and standard; its application to
AI benchmarks is now appearing at COLM/arXiv in multiple independent groups (CogArena; the COLM
56-benchmark paper; SimBA arXiv 2510.17998 performance-matrix analyses). Method-grade, not
claim-grade.

## [VENUE] Chinese-lab technical reports (GLM-5 / DeepSeek-V4 / Qwen3.5 / Kimi) — first deliberate desk visit: methods-RICH for agentic-RL training, THIN for the desk's validation wounds; best single artifact = GLM-5 report
- **GLM-5: from Vibe Coding to Agentic Engineering** — arXiv 2602.15763
  (https://arxiv.org/abs/2602.15763 , code https://github.com/zai-org/GLM-5 ): asynchronous
  agent-RL infrastructure (generation decoupled from training), sequential Reasoning-RL →
  Agentic-RL → General-RL pipeline with on-policy cross-stage distillation against catastrophic
  forgetting. [SEARCH-SUMMARY + abstract]
- **DeepSeek-V4**: mixed-RL phase replaced by ON-POLICY DISTILLATION from 10+ in-house
  domain-specialist teachers (math/code/agents/IF, each SFT+GRPO); HF overview
  https://huggingface.co/blog/deepseekv4 . **Qwen3.5-Omni** (arXiv 2604.15804): same
  specialist-teacher→distill pattern; "million-agent environments" RL scaling claims. [SEARCH-SUMMARY]
- Adjacent method papers surfaced: BranPO contrastive branch sampling for long-horizon agentic RL
  (arXiv 2602.03719); EnterpriseBench Corecraft high-fidelity RL environments (arXiv 2602.16179);
  Kimi K2 open agentic report remains the canonical open reference (arXiv 2507.20534).
- **Verdict:** these labs publish REAL training methodology (vs thin Western frontier model
  cards) — the desk doesn't train models, so wound-relevance is low TODAY; the one transferable
  pattern is organizational: specialist-teachers-then-distill mirrors the desk's rotating-lens
  seat design, and cross-stage distillation is their answer to the forgetting problem the desk
  solves with files. Worth revisiting only if the desk ever fine-tunes. BAAI/智源: no 2026
  methods report surfaced in this probe [NULL on this axis, one query deep].

## [VENUE] HuggingFace weekly trending (papers/week/2026-W33) — moderate yield, good pulse-check
**URL:** https://huggingface.co/papers/week/2026-W33 [FETCHED]
This week's wound-relevant trenders: "A^2E: An End-to-End Agent Auditing Engine" (2608.07346 —
the audit theme is TRENDING, third hit this run); "Agent Memory Distillation" (2608.07169);
"Ouroboros: A Self-Developing Frontier Coding Agent with Reviewed Core Evolution" (2608.08311,
#1 overall 1,090 votes — self-modification WITH review gates; hype-dense, unreplicated, but the
"reviewed core evolution" pattern = desk's principal-gated self-modification law, independently
converged). Verdict: cheap discovery channel, claims skew unvalidated — use for LEADS only.
REVISIT: yes, weekly URL pattern is stable.

## [VENUE] METR — revisited (run 4 visited once): time-horizon methodology near its own ceiling; the desk-usable part is the METHOD caveats, not the curve
**URLs:** https://metr.org/time-horizons/ , https://metr.org/blog/2026-05-19-frontier-risk-report/ ,
https://metr.org/research/ [SEARCH-SUMMARY level this run]
Status mid-2026: best agents ~saturate the Time-Horizon-1.1 suite (point estimates >2 FTE-days
carry "increasing uncertainty"; measurements above ~16h flagged unreliable by METR itself);
50%-horizon doubling ~7mo long-run, ~4mo recently. Related methods artifact: "Is there a
half-life for the success rates of AI agents?" (arXiv 2505.05115, Toby Ord) — constant-hazard
model implies success probability decays exponentially in task LENGTH; a desk-portable prior for
organ-duty design (short duties compound reliability; matches the meltdown/decay findings above).
Frontier Risk Report (Feb–Mar 2026) is a periodical worth a standing skim. Verdict: MODERATE,
stable, already partially mined; revisit quarterly.

## [VENUE] LessWrong / Alignment Forum — MODERATE-THIN for wound-methods; mostly mirrors arXiv, but two genuine artifacts
**Probes:** two searches. Yield: (1) "Survey of Multi-agent LLM Evaluations"
(https://www.lesswrong.com/posts/tGcLA596E8g3KnphE/survey-of-multi-agent-llm-evaluations — 32
papers compiled on multi-agent failure modes; useful index for w5); (2) the Docent discussion
(https://www.lesswrong.com/posts/Mj276hooL3Mncs3uv/analyzing-long-agent-transcripts-docent ).
Also surfaced "On the Reliability of Computer Use Agents" (arXiv 2604.17849: agents that succeed
once fail on re-execution — third source for the reliability-not-capability pattern). Verdict:
use LW/AF as an INDEX to primaries, not a primary; revisit only via targeted queries.

## [VENUE] Epoch AI Benchmarking Hub — MODERATE as data resource; one embedded lesson
**URLs:** https://epoch.ai/benchmarks , https://epoch.ai/blog/benchmarking-hub-update [SEARCH-SUMMARY]
18 benchmarks (5 run internally, 13 external), selection criteria published (economic value,
unsaturated, widely used). The embedded lesson: Epoch found its own SWE-bench-Verified re-runs
DIVERGED from vendor-reported scores and had to revise methodology — independent re-execution of
a public benchmark disagrees with the reported number even for a careful measurement shop.
Supports the desk's replication-before-belief law with an external instance. Leads logged:
EPC judge-drift protocol (arXiv 2607.00297, w3/w5); safety-benchmark consistency taxonomy
(arXiv 2605.16282); "A Rosetta Stone for AI Benchmarks" (arXiv 2512.00193). Revisit for
model-choice decisions, not validation methods.

## [NULL] Apollo Research — no 2026 methods report surfaced in this run's probes beyond scheming-evals safety-case work (arXiv 2411.03336, known class) and a mention as Docent alpha tester. One-query-deep per axis; not exhausted, just low-yield for the eight wounds this run.

## [DATA-LOOT] consolidated (license-checked where stated)
- **MemoryAgentBench** — code MIT (https://github.com/HUST-AI-HYZ/MemoryAgentBench), datasets on
  HuggingFace, auto-download. Use: yardstick if the desk ever swaps memory designs.
- **LongMemEval-V2** — paper CC-BY 4.0 (arXiv 2605.12493); 451 Qs / up-to-115M-token histories.
- **ForeSci** — CC-BY 4.0 (arXiv 2606.00644); 500 cutoff-aligned research-judgment tasks; the
  cutoff-KB CONSTRUCTION pattern is the loot even if tasks are AI-domain.
- **STC Appendix G** (arXiv 2606.05241) — the 27+ URL regex patterns for benchmark-leak
  detection; template for the desk's own trajectory-audit blocklist.
- **Every Eval Ever** (arXiv 2606.14516) — unifying schema + community repository of AI eval
  results; license unverified this run; candidate substrate for gate-battery meta-analysis.
- **AgentOdyssey** (TTCL @ NeurIPS 2026, https://ttcl-agents.github.io/ ) — test-time
  continual-learning challenge benchmark; content/license unverified this run.
- **Epoch Benchmarking Hub** (https://epoch.ai/benchmarks ) — curated cross-benchmark results
  data, methodology published.
- **hal.cs.princeton.edu/reliability** — live reliability-metrics dashboard (12 metrics × 15
  models) accompanying arXiv 2602.16666.

---

# DEPTH (per lead: how deep + what depth surfaced)
- 2606.05241 STC: abstract + full-text HTML, two passes — depth surfaced the CONDITIONAL-vs-
  aggregate inflation distinction (100% with-EAL vs "up to 4%" headline) and validated-judge
  numbers; a shallow read would have carded "4%, minor" and been wrong.
- Appendix carry-overs (2606.03032 / 2509.08713 / 2606.03437): one appendix-targeted full-text
  pass each — depth surfaced the heterogeneity table (0.598 vs 0.357), the measured logs+code
  audit delta (74.0% vs 51.4%), and that run 4's characterization of 2606.03437 was WRONG
  (ownership bias, not elicitation-method ranking). Local PDFs from run 4 exist but are
  unreadable on this box (no poppler; no installs) — noted for ops.
- Memory ground: 4 sources opened (MemoryAgentBench paper+repo, LongMemEval-V2, 2605.18854) +
  workshop site + one gated OpenReview PDF [bot-gate logged]; depth = the three-anchor
  convergence (BM25 > products; files > RAG at horizon; compaction = cost knob).
- Validity trio (predictive/construct/MTMM): 3 full-text or systematic-review-level passes +
  1 unresolved primary (COLM 56-benchmark paper — title-only, no public text found).
- Entanglement 2604.07650: full-text pass with formula extraction — depth surfaced the honest
  +0.001 reweighting null AND the ρ≈0.5 judge-bias predictor; abstract-level would have carded
  the reweighting as the finding (backwards).
- e-process practice 2602.06379: full-text pass — complete formula set extracted (λ*, N≈log(1/α)/g,
  e-BH, predictability constraint).
- Transcript-audit 2607.27518: full-text pass — scanner F1 asymmetry (0.74 vs 0.14) is the
  load-bearing caveat.
- Expansion breadth: COLM list (full scan), HF-W33 (full scan), METR/Epoch/LW/Apollo/Chinese-labs
  (1–2 queries each, search-summary depth; GLM-5/DeepSeek-V4/Qwen3.5 not full-text-read).
  2603.29231, 2602.16666, ForeSci read at abstract/results level only.
- Budget: ~36 web ops (15 searches, 21 fetches); expansion share ≈ 40% ≥ the 25% floor.

# NEXT-GROUND (for run 7)
1. **2026-10: harvest NeurIPS eval-of-interactive-agents + E&D track acceptances** (decisions
   09-29) — the grader-design and trajectory-eval papers will be public then; highest expected
   yield per op of anything named this run.
2. COLM 2026 full texts now shortlisted but unread: CONCORD (label-free calibration, w3),
   "Rubrics as an Attack Surface" (w5), "Who Guards the Benchmarks?", TierMem + MEMENTO (w6),
   "Measuring Five-Nines Reliability" (w1 sample-efficient gating), the 56-benchmark MTMM paper
   (hunt its arXiv/OpenReview text).
3. A^2E auditing engine (2608.07346) + EPC judge-drift protocol (2607.00297) — both days-old,
   untriaged beyond titles.
4. MemAgents workshop PROCEEDINGS via OpenReview venue listing once the bot-gate allows (or via
   an arXiv-side sweep of "MemAgents 2026" citations) — the workshop's accepted-paper set is
   still the named unmined seam, now two runs old.
5. Desk-side (not literature): the three w1 lenses (IRT #87, predictive-validity, MTMM) + the BEI
   seat-audit all compute from ledgers ALREADY ON DISK — a single reanalysis organ-run covers
   four findings' recipes without a new external fetch.

