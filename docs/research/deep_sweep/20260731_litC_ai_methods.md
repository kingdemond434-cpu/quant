# Deep sweep 2026-07-31 — Lit C: AI / Autonomous-Research Methods ("the engine is a dig target")

Sub-agent run 2026-07-31. Last visit 2026-07-26. Ground: methods that improve HOW the desk discovers.
Discipline: NK-005 routes honored (arXiv/OpenReview direct; no paywall circumvention). Cancelled builds
(naive automated debate; self-preference defence) not re-recommended absent NEW controlled evidence.

Budget plan (~25-30 fetches): W1 sequential-testing 5 / W2 calibration 4 / W3 gate-design 3 /
W4 multi-agent aggregation 4 / W5 autonomous-research architecture 4 / EXPANSION RESERVE ≥7 (≥25%).

---

## W1. SEQUENTIAL-TESTING WOUND — anytime-valid daily monitoring for Stage-B forward clocks

(peeking ×4.9 α-inflation measured; homegrown anytime_valid quarantined. Target: exact computable rule.)

### W1-a [ENGINE-FIX candidate] E-backtesting (Wang, Wang & Ziegel) — finance-native e-process, full recipe extracted
- URL: https://arxiv.org/html/2209.00991v5 (v5 read; published Management Science 2025, doi 10.1287/mnsc.2023.01659)
- RECIPE (verbatim structure): per-period e-statistic for a risk forecast; e.g. ES:
  e = (x - z)_+ / [(1-p)(r - z)] with z=VaR forecast, r=ES forecast; VaR: e = 1{x>r}/(1-p).
  Wealth/e-process: M_t(λ) = ∏_{s≤t} [1 - λ_s + λ_s X_s], M_0=1, λ_t ∈ [0,1] predictable
  (chosen from past data only; GRO/GREE/GREL betting schemes, Thm 3 asymptotic optimality).
  Reject when M_t ≥ 1/α. Guarantee (Thm 2): P(sup_t M_t ≥ 1/α) ≤ α under the null —
  REGARDLESS of stopping rule ⇒ daily peeking is FREE. Practical evidence thresholds 2/5/10
  (minor/substantial/strong). Fully model-free: no iid, no parametric family, works with
  time-varying conditional forecasts. Caveat: ES e-statistic needs an accurate auxiliary VaR forecast.
- Desk mapping: this exact wealth-process form is the correct SKELETON for the quarantined
  anytime_valid module. Cost: O(1) per day (one multiply). What was wrong before (daily peeking
  at a fixed-α test) becomes valid by construction.
- Note: e-backtesting monitors RISK-FORECAST validity (tail calibration of the live book) —
  a second, separate desk application (risk overlay), distinct from Stage-B edge confirmation.

### W1-b [ENGINE-FIX candidate] Anytime-valid t-test (Wang & Ramdas) — the exact Sharpe-shaped primitive
- URLs: https://arxiv.org/abs/2310.03722 ; published Sequential Analysis 44(1)
  (https://www.tandfonline.com/doi/full/10.1080/07474946.2024.2428245)
- Object: e-process for H0: Gaussian mean = 0, variance UNKNOWN — i.e. the test statistic is a
  function of the t-statistic ⇒ scale-free ⇒ this is a sequential test on the SHARPE of daily PnL.
  Construction: Lai (1976) flat mixture → Gaussian mixture over mean + variance handled by
  plug-in MLE-under-null (universal inference). CS width has provably unavoidable polynomial
  dependence on error probability (better than classical fixed-n t-test under universal inference).
- Abstract does NOT claim validity beyond Gaussian (robustness under symmetry NOT confirmed —
  do not assume; heavy tails must be handled by design, e.g. winsorized/bounded payoff transform
  + betting e-process (W1-a form), or run both). Full text not read [ABSTRACT+intro grade].
- Desk mapping: replaces the quarantined anytime_valid clock: per candidate, daily update of the
  t-e-process (or betting wealth on bounded transformed returns); confirm at M_t ≥ 1/α; α spent
  ONCE for the whole forward window regardless of peeking cadence. ×4.9 inflation → 1.0 by design.
- Citation chain (level 2): Lai 1976 sequential t-CS; Grünwald–de Heide–Koolen safe testing;
  Ramdas et al. SAVI review arXiv:2210.01948; ICML 2025 SAVI tutorial (https://icml.cc/virtual/2025/40002).

## W2 leads (search layer): ConfidenceBench arXiv:2607.20526 (read, see below); Agent Psychometrics
arXiv:2604.00594 (task-level success prediction, IRT+features — dual-use with W3); overconfidence
mechanistic line arXiv:2604.01457; 2606.03437.

## W5 leads (search layer): Hidden Pitfalls of AI Scientist Systems arXiv:2509.08713 (4 failure
modes: benchmark selection, data leakage, metric misuse, post-hoc selection bias); deep-research
hallucination-in-trajectory arXiv:2601.22984 (rates 1.7–33% claimed); "Correct Answer, Wrong
Mechanism" arXiv:2606.23175; AI Scientist v1 42% experiment-failure rate (search-layer claim);
Nature end-to-end automation s41586-026-10265-5.

## W2. CALIBRATION WOUND — LLM verbalized-confidence calibration for Kelly-relevant logging

### W2-a [ENGINE-IDEA] ConfidenceBench (Jul 2026): verbalized confidence — magnitudes per family
- URL read: https://arxiv.org/html/2607.20526
- Numbers: Brier scores — best models Claude Opus 4.6 and Gemini 3.1 Pro 0.103 (human baseline
  0.105); GPT-5 High/Std 0.117–0.121, Low 0.141; worst Gemini 3.1 Flash-Lite 0.367.
  Calibrated-RANDOM baseline = 0.1875 and 5/15 models score WORSE than it. Within-family:
  more reasoning effort → better calibration (GPT-5 High 0.121 vs Low 0.141) and lower run-to-run
  variance. High performers are UNDERconfident on unknowable questions (default to 25%).
- Limitation: direct JSON verbalization only — no comparison vs consistency/logit elicitation.
- Desk mapping: the desk's two-family (Claude+GPT) forecast-calibration logger should (i) expect
  family-level offsets this large (0.10 vs 0.14 Brier), so calibrate PER FAMILY PER task-type;
  (ii) treat newer≠better-calibrated as live risk on model upgrades — recalibrate on upgrade.
- Grade: single benchmark, fresh (Jul 2026), not yet replicated → CLAIM for exact numbers,
  but "verbalized confidence is miscalibrated at material magnitude" is multi-paper consensus
  (also arXiv:2604.01457 mechanistic overconfidence circuit; arXiv:2606.03437; arXiv:2502.11028).

### W2-b [ENGINE-FIX candidate] Agent Psychometrics (arXiv:2604.00594): PREDICTING per-task agent
### success beats self-report routes — and is dual-use for W3 gate design
- URL read: https://arxiv.org/html/2604.00594v1
- Method: IRT + task features (embeddings incl. solution text; LLM-as-judge rubric features).
  Success model P = σ(θ_LLM + θ_scaffold − β_task) (additive decomposition validated: fixed-scaffold
  vs isolated-LLM ability Pearson r=0.974).
- Effect sizes: per-task success prediction AUC 0.842 on UNSEEN SWE-bench-Verified tasks
  (baseline 0.718, +0.124); 0.810 Terminal-Bench-2 (+0.076); new-agent setting 0.936; held-out
  benchmark 0.696 (+0.125 over 0.571) — honest domain-shift penalty −0.146. Fisher-information
  task-subset selection beats random at budgets <30 tasks; motivates cheap difficulty estimates
  (vs $22k full runs).
- Desk mapping (two organs): (1) calibration logger — an EXTERNAL feature-based predictor of task
  success is a benchmarkable complement to the desk's self-stated confidences (regress desk
  outcomes on task features; compare Brier vs verbalized). (2) W3: the σ(ability − difficulty)
  frame is exactly what the gauntlet lacks — see W3-b.
- Grade: single paper, strong internal validation, no external replication yet → CLAIM.

## W3. GATE-DESIGN WOUND — discrimination vs difficulty (gauntlet rejects true-SR-3 control ~100%)

### W3-a [ENGINE-FIX candidate] Fluid Benchmarking (Ai2): IRT discrimination as the anti-welding tool
- URL read: https://allenai.org/blog/fluid-benchmarking (paper via blog; six benchmarks, Open LLM
  Leaderboard response matrices)
- Method: 2-parameter IRT (difficulty + discrimination per item); Fisher-information adaptive item
  selection at the current ability estimate.
- Effect sizes: 50× fewer items on MMLU at equal-or-better quality; ~99% relative reduction in
  encounters with mislabeled items (low-discrimination items are automatically avoided); reduced
  step-to-step variance in training curves; delayed saturation; better cross-benchmark validity.
- Transfer principle for the gauntlet: a gate is an ITEM. A welded gate (rejects true-SR-3 control
  ~100%) is an item whose difficulty exceeds the ability of everything that will ever face it —
  Fisher information ≈ 0 ⇒ ZERO bits per run, exactly what the desk measured. The published cure:
  estimate per-gate difficulty+discrimination empirically by running a LADDER of synthetic
  strategies with KNOWN true Sharpe (0, 1, 2, 3, 5) through each gate separately, then (i) drop or
  re-parameterize zero-discrimination gates, (ii) tune the composite so P(pass | true SR=target)
  sits near 50% — max-information operating point, (iii) re-certify quarterly.
- Grade: Ai2 published + deployed internally; single-org but with public method → STRONG CLAIM.
- Chain (level 2): "Lost in Benchmarks" PSN-IRT arXiv:2505.15055; adaptive testing arXiv:2511.04689;
  Agent Psychometrics (W2-b) independently converges on same frame — 3 independent groups.

### W3-b Cross-link: W2-b's σ(θ_ability − β_gate) is the model to fit; certify_gauntlet already
produces the response matrix (synthetic control runs) — the desk owns the data, only the fit is missing.

## W4. MULTI-AGENT AGGREGATION WOUND — beyond plurality; cross-family agreement as evidence

### W4-a [NULL, confirmatory] 2025–2026 evidence does NOT overturn the desk's debate cancellation
- Sources: ICLR 2025 blogpost "Multi-LLM-Agents Debate — Performance, Efficiency, and Scaling"
  (https://d2jud02ci9yv69.cloudfront.net/2025-04-28-mad-159/blog/mad/): across NINE benchmarks,
  MAD frameworks fail to consistently beat simpler single-agent strategies even at higher compute.
  Controlled study arXiv:2511.07784 (Knight-Knave-Spy, 6 manipulated factors): gains depend on
  individual reasoner strength + genuine diversity; structural knobs (order, confidence visibility,
  depth) give "limited gains"; majority pressure SUPPRESSES independent correction.
  "The Deliberative Illusion" arXiv:2606.03032 (PDF fetched): deliberation FREQUENTLY DEGRADES
  final accuracy vs individual agents ("substantial" effect sizes; exact deltas in PDF appendix,
  not extracted — saved locally); factual attrition across rounds + stance homogenization =
  consensus that looks confident while information decays.
- Verdict: desk's cancellation of naive automated debate STANDS on newer evidence. Do not rebuild.

### W4-b [ENGINE-FIX candidate] Confidence-weighted aggregation beats plurality (keeps singletons alive)
- URL read: https://arxiv.org/abs/2606.13591 (Multiagent Protocols with Aggregated Confidence Signals)
- Method: transform each agent's confidence to a comparable scale (parametric or non-parametric
  calibrator), then SOFT VOTING or BAYESIAN FUSION instead of plurality. Confidence from sequence
  probability or self-report.
- Findings: aggregated-confidence protocols substantially improve discrimination (AUARC) over
  individual agents AND over standard debate; recover the losses debate incurs on ambiguous tasks;
  calibration step improves F1 for both estimators. 6 homogeneous+heterogeneous pairs, 5 benchmarks.
  (Exact deltas not in abstract-level extraction → CLAIM grade on magnitudes.)
- Desk mapping: the review panels' plurality vote discards singleton findings BY CONSTRUCTION.
  Fix: log each reviewer's stated confidence, calibrate per family (W2 logger provides the data),
  aggregate by soft vote / Bayesian fusion; a high-confidence singleton then survives as a scored
  minority report instead of being dropped. Cross-family (Claude+GPT) agreement fits naturally:
  independent-family confidences multiply in Bayesian fusion (diversity is worth more than
  same-family redundancy — consistent with W4-a's "genuine diversity" moderator).
- Chain: converges with arXiv:2606.10296 (log-prob diagnosis of debate: "The Confident Liar") and
  arXiv:2511.07784's confidence-visibility findings.

## W5. AUTONOMOUS-RESEARCH ARCHITECTURE — AI-Scientist failure modes, memory, verification scaling

### W5-a [ENGINE-IDEA] Hidden Pitfalls of AI Scientist Systems — 4 failure modes ≡ desk organ map
- URL read: https://arxiv.org/pdf/2509.08713 (PDF saved locally; quantitative rates live in
  appendix, NOT extracted this run — carry-over)
- Taxonomy demonstrated across AI-Scientist-style systems: (1) inappropriate benchmark selection,
  (2) data leakage, (3) metric misuse, (4) POST-HOC SELECTION BIAS. Mitigations proposed
  (pre-registration; explore/confirm phase separation; leakage detectors) but NOT measured — the
  desk's own Stage-A/Stage-B split + gauntlet is already ahead of this literature in places.
- Desk mapping: use as an AUDIT CHECKLIST against the desk's own research organs: (4) is exactly
  the wound class the desk keeps finding in itself (Stage-B peeking = post-hoc selection on clocks);
  (2) maps to label_factory/backtest data hygiene; (3) maps to screen_select computed-but-ignored.
- Related, search layer: "Correct Answer, Wrong Mechanism" arXiv:2606.23175 (agents defend general
  claims their OWN data contradicts — mechanism-level review needed, not answer-level);
  AI Scientist v1 42% experiment-failure rate + reviewer misses hallucinations (search-layer claim,
  unverified); deep-research trajectory hallucination rates 1.7–33% (arXiv:2601.22984, unopened);
  Nature 2026 end-to-end automation paper s41586-026-10265-5 (unopened, paywall-likely).
- Grade: taxonomy SOLID (multi-system), magnitudes CLAIM (appendix unread).

### W5-b [ENGINE-IDEA] DeepVerifier (arXiv:2601.15808v2): rubric-guided test-time verification of
### research-agent outputs — real effect sizes, real failure modes
- URL read: https://arxiv.org/html/2601.15808v2
- Mechanism: failure taxonomy auto-built from 555 error points / 90 tasks (5 classes: sources,
  reasoning, problem understanding, action execution, trajectory efficiency) → decomposition module
  turns a trajectory into ≤3 TARGETED follow-up questions (not full re-solve) → verification agent
  answers them with tools → judge scores 1–4 against rubric → agent retries with feedback.
  Exploits verify-easier-than-generate asymmetry.
- Effect sizes: verification F1 73.17 vs 61.54 agent-as-judge vs 25.00 decomposition-only.
  End-task: GAIA-Web +11.11pp (51.11→62.22, Claude-3.7-Sonnet, 2 rounds); GAIA-Full +7.9pp;
  XBench-DeepSearch +6pp; BrowseComp +5pp; GPT-4.1 only ~+3pp (model-dependence).
- FAILURE MODES (important for desk): verifier REGRESSES correct→incorrect at 12.79% in round 1
  (persists 0–3% in rounds 5–10); fix-rate decays 18.99%→0% by round 5 ⇒ gains plateau, peak at
  rounds 3–4 ⇒ EARLY-STOP the verification loop. Cost: extra inference + tool calls per round.
- Desk mapping: the desk's review panel currently judges whole outputs (agent-as-judge ≈ 61.5 F1
  regime). Adopting decompose→verify-≤3-claims→judge is a measured +12 F1 on verification itself,
  and caps review loops at 3–4 rounds on published transition curves.
- Grade: single paper + own benchmark suite → CLAIM, but transition-rate analysis is unusually
  honest; search layer agrees verifier-based selection beats self-consistency at 1–3× fewer tokens
  (e.g. AIME-2025 0.77 acc at 75% tokens, arXiv:2606.02981 search layer; PRMs "tens of points" over
  single sample — unopened).

### W5-c [ENGINE-IDEA] StatefulDiscovery (arXiv:2606.11851, found via NEW-VENUE probe): claim ledger
### with evidence-calibration — literature CONVERGING on the desk's own ledger design
- URL read: https://arxiv.org/pdf/2606.11851 (PDF saved locally; exact deltas vs DeepScientist/
  CoScientist baselines not extracted — carry-over)
- Mechanism: long-horizon claim ledger; every claim carries confidence + evidence-quality weights
  (rigor, replication consistency); OVERCLAIMING measured as calibration error between claim
  confidence and evidentiary warrant; claims cannot advance state without proportionate evidence.
- Desk mapping: the desk already runs a ledger + graveyard + grade-forecast discipline — this
  paper's transferable increment is the explicit per-claim (confidence − evidence-quality) gap as
  a LOGGED METRIC, which plugs straight into the new forecast-calibration logger (W2): grade not
  just outcomes but claim-vs-evidence gaps at write time.
- Grade: CLAIM (single paper, magnitudes unread) — but mechanism-level, adoptable piecemeal.

## EXPANSION RESERVE — new venues probed (7/27 ops ≈ 26% of budget)

### V1 METR (metr.org/research) — VERDICT: RICH. First mine of this venue.
- URL read: https://metr.org/research. Eval-METHODS items: Expenditure Horizon (2026-07-21, new
  optimization-ability metric); Time Horizon 1.1 (2026-01-29; original 2025-03-19 method: task-length
  doubling ~7 months); HCAST human-calibrated task baselining; RE-Bench (71 human expert attempts
  as baseline); Task-substitution/uplift 3-measure decomposition (2026-05-08 — explains
  benchmark-vs-real-impact divergence); **MALT dataset (2025-10-14): manually-reviewed eval-GAMING
  behaviors** — direct W5/gauntlet-integrity relevance. MALT blog fetch 404 on guessed URL
  (https://metr.org/blog/2025-10-14-malt/) — correct URL is a carry-over item.
- Next-run allocation: HIGH. Human-calibrated baselining (HCAST) is the eval-design analog of the
  desk's synthetic-control ladder.

### V2 Epoch AI (epoch.ai/benchmarks) — VERDICT: THIN for methods, RICH as tracking data.
- URL read: https://epoch.ai/benchmarks. Epoch Capabilities Index (ECI) + benchmarking hub;
  13 new evals added 2026-07-01. No methodology documentation surfaced on uncertainty/aggregation/
  saturation. Use as data source (saturation curves), not methods source.

### V3 OpenReview workshop tracks — VERDICT: RICH (the methods frontier lives here now).
- Search layer (URLs listed): NeurIPS 2026 "Evaluation of Interactive Agents"
  (https://eval-interactive-agents-workshop.github.io/ — submissions due 2026-08-29: WATCH);
  ICML 2026 "Agents in the Wild" (https://agentwild-workshop.github.io/icml2026/);
  ICLR 2026 "Reliable Autonomy" (https://openreview.net/group?id=ICLR.cc%2F2026%2FWorkshop%2FReliable_Autonomy);
  ICLR 2026 "MemAgents: Memory for LLM-Based Agentic Systems" (W5 memory ground — unmined);
  ICLR 2026 "AI with Recursive Self-Improvement". Plus MLR-Bench (NeurIPS 2025 poster
  https://neurips.cc/virtual/2025/124579-adjacent; 201 open-ended ML-research tasks + MLR-Judge) —
  candidate external yardstick for the desk's own research organs.
- Yield evidence: this probe surfaced StatefulDiscovery (W5-c) — expansion paying for itself.

### V4 alphaXiv (alphaxiv.org) — VERDICT: MODERATE-THIN.
- URL read: https://www.alphaxiv.org/. Curation layer over arXiv: bookmark-count signals (5–515),
  structured summaries, implementation/GitHub links. Agent-research content present; no calibration
  focus. Incremental discovery value over raw arXiv listings; no discussion-forum depth. Use as a
  trending filter at ~1 fetch/run, not a primary vein.

### V5 Chinese agent ecosystem (open-access tech reports) — VERDICT: THIN for transferable methods.
- Search layer: Qwen3-Coder-Next tech report (arXiv:2603.00729, 2026-03-03 — SWE-bench-Verified
  70.6%, 300-turn cap, fair-scaffold comparisons); GLM-5 (arXiv:2602.15763; internal CC-Bench-V2
  agentic suite, not fully public); DeepSeek-V3.2. These are benchmark CONSUMERS; eval-methods
  novelty low at tech-report level. BUT the trail surfaced "Search-Time Contamination in Deep
  Research Agents" (arXiv:2606.05241, unopened) — measuring benchmark performance inflation from
  eval-time web search; relevant to any desk eval that lets agents search. Carry-over.

### V6 (negative) MALT direct URL dead (404) — see V1. No other blocks hit this run; no bot-gates
encountered; NK-005 routes not needed (all content arXiv/OpenReview/org-sites).

---
## HONEST GAPS / COULD NOT VERIFY THIS RUN
- Exact accuracy-delta tables in Deliberative Illusion (2606.03032) and Hidden Pitfalls (2509.08713)
  appendices — PDFs SAVED LOCALLY under ~/.claude/.../tool-results/ (webfetch-1785525037382-ba0m1f.pdf,
  webfetch-1785525035055-66xhp4.pdf) — free to mine next run without refetching.
- Anytime-valid t-test validity beyond Gaussian: NOT confirmed (abstract-level only). Design around
  it (bounded transform + betting e-process) until full text read.
- AI-Scientist-v1 42% experiment-failure rate and 1.7–33% trajectory-hallucination rates:
  search-layer only, primaries unopened (2601.22984; Nature s41586-026-10265-5 likely paywalled).
- Agentic (multi-step) SELF-confidence calibration: literature still thin — closest found is
  external prediction (Agent Psychometrics, W2-b). This desk wound remains ahead of the literature.
- Agent memory/continual-learning for long-horizon research: only venue-level (MemAgents workshop);
  no measured-effect paper opened this run. Named carry-over target.
- 2606.03437 elicitation ECE deltas extracted only qualitatively (self-critique+consistency beat
  naive verbalization; magnitudes in saved PDF webfetch-1785525211772-sxir4d.pdf).

---
## Fetch log (27 web ops: 11 searches, 16 fetches; 1×404. Expansion: 7 ops = 26%)
Searches: SAVI/e-values practical; LLM verbalized calibration; e-backtesting; IRT benchmarks;
MAD controlled evidence; anytime t-test; agent success prediction; AI-scientist failures;
OpenReview 2026 workshops; Qwen/GLM/DeepSeek eval methods; best-of-n verifier effect sizes.
Fetches (opened): arxiv.org/html/2209.00991v5; allenai.org/blog/fluid-benchmarking;
arxiv.org/abs/2511.07784; arxiv.org/abs/2606.13591; arxiv.org/abs/2310.03722;
arxiv.org/html/2607.20526; arxiv.org/html/2604.00594v1; arxiv.org/pdf/2509.08713;
arxiv.org/pdf/2606.03032; metr.org/research; epoch.ai/benchmarks; alphaxiv.org;
arxiv.org/pdf/2606.11851; metr.org/blog/2025-10-14-malt/ (404); arxiv.org/pdf/2606.03437;
arxiv.org/html/2601.15808v2.
