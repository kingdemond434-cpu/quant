# [LIT-c] AI / AUTONOMOUS-RESEARCH METHODS FRONTIER — deep sweep

_Ground: "the engine is a dig target". This desk IS an autonomous AI research agent; improving
HOW it discovers compounds faster than any single alpha. RESEARCH-ONLY session — no code, no
installs, no writes outside this file. Findings route to `docs/research/improvement_inbox.md`
by the PARENT, never to the trading gauntlet._

**Session date:** 2026-07-26
**Operator:** Literature Deep-Miner, ground [LIT-c]
**Discipline applied:** every claimed improvement is scored on BASELINE QUALITY first. A method
that beats a weak baseline is not evidence. Extreme/published/crowded claims are
research-PRIORITY-to-test, never credible-on-arrival (Charter §8).

**Provenance honesty convention used throughout:**
- `[FETCHED]` = URL actually opened and read in this session.
- `[ABSTRACT-ONLY]` = only the abstract/landing page was read.
- `[SEARCH-SUMMARY]` = only a search-engine result snippet. Per improvement-inbox #54
  (GRADE-PROVENANCE RAIL), a search summary is a LEAD, never evidence — such items are
  graded UNVERIFIED and may not be adopted on that basis alone.

---

## FINDINGS

_(appended as resolved — write-as-you-go)_

---

### FINDING 1 — Multi-agent DEBATE loses to matched-compute self-consistency; HETEROGENEITY is the thing that actually works. The desk already has the good half and has a proposal queued for the bad half.

**Method / mechanism.** Multi-Agent Debate (MAD) has agents exchange full responses over R rounds and
converge. Two independent evaluations tore this down. Liu et al., *Stop Overvaluing Multi-Agent
Debate* (position paper) evaluated **5 MAD frameworks** (Multi-Agent-Debate, Multi-Persona,
Exchange-of-Thoughts, AgentVerse, ChatEval) across **9 benchmarks** (MMLU, MMLU-Pro, AGI-Eval,
CommonsenseQA, ARC-Challenge, GSM8k, MATH, HumanEval, MBPP), up to 500 samples each, on GPT-4o-mini
and Llama3.1-8b. Result: MAD **fails to consistently beat single-agent Chain-of-Thought and
Self-Consistency** despite consuming far more inference compute, and **does not scale** with added
budget — "only EOT (GSM8k, MMLU) and MAD (HumanEval) exhibit scalability," and those were not the
best performers anyway. Their diagnostic is the important part: MAD shows **more incorrect answer
reversals** than CoT/SC — agents "lack the ability to reliably identify incorrect answers," so
debate flips right answers to wrong ones at least as often as the reverse. The one intervention that
consistently helped was **model heterogeneity** — different model families in the same panel — which
the authors call "a universal antidote."

The second, sharper one: Bertalanič & Fortuna, *The Cost of Consensus: Isolated Self-Correction
Prevails Over Unguided Homogeneous Multi-Agent Debate* (arXiv 2605.00914v1, 2026-04-29, Jožef Stefan
Institute). N=10 agents, R=3 rounds, GSM-Hard (1,017 items) + MMLU-Hard, with a genuinely good
baseline set: peer debate vs **isolated self-correction** vs **noise injection (unrelated
rationales)** vs zero-shot. Debate LOST to isolated self-correction at every cell: GSM-Hard/Qwen
58.8% vs 61.0% (−2.2pp, p<0.001); MMLU-Hard/Qwen 60.7% vs 66.7% (−6.0pp, p<0.001);
GSM-Hard/Ministral 20.7% vs 48.3% (**−27.6pp**, p<0.001) — while burning **2.1×–3.4× more tokens**
(17.4k–28.6k vs 5.3k–12.8k per problem), with the overhead entirely O(N×K) prompt routing.

**THE MECHANISM THAT MATTERS TO THIS DESK — "consensus collapse" / the oracle gap.** The team
*generated* the correct answer and then *voted it away*. Ministral/GSM-Hard: correct answers present
in the generation pool in **53.0%** of cases, but team accuracy only **20.7%** — a **32.3pp oracle
gap**. Plurality voting actively discards correct reasoning that the panel already produced.
Supporting measurements: modal adoption rates up to **85.5%**, consensus rates **83.5–90.1%** under
debate vs 46.5–84.1% under self-correction (sycophantic conformity), and a correct→wrong
"vulnerability rate" up to **70.0%**.

**Evidence quality — harsh read.** The baseline quality here is unusually GOOD, which is why this
survives the desk's standard skepticism: 2605.00914's baseline is not a strawman single call, it is
*isolated self-correction at matched round count* plus a **noise-injection control** (feeding
unrelated rationales) — that control is what separates "peers add information" from "extra context
perturbs the trajectory," and it is the single most common missing control in this literature.
2502.08788 is compute-matched against Self-Consistency, the correct baseline. **The severe caveats,
stated plainly:** (a) 2605.00914 used only **7–8B models** (Qwen2.5-7B, Llama-3.1-8B, Ministral-8B)
— sycophantic conformity in a 7B model is very plausibly not the failure mode of a frontier model,
and the −27.6pp Ministral result is an outlier that inflates the headline; (b) 2502.08788 used
GPT-4o-mini and Llama3.1-8b — again NOT frontier; (c) 2502.08788 is a **position paper**, a genre
that selects for the negative result; (d) 2605.00914 is a **single-lab arXiv preprint, unreplicated,
~3 months old**. I fetched the ICLR blogpost and the HTML full text; I read 2502.08788 as
**ABSTRACT-ONLY** (the arXiv abstract page carried no numbers — the ICLR blogpost is the substantive
source and it covers the same experiments). **Net: the direction of the effect is well-supported by
two independent groups with real baselines; the magnitude is not transferable to frontier models and
should not be quoted.**

**Concrete application to THIS desk — three specific artifacts.**

1. **`scripts/run_external_panel.py` — the design is ALREADY RIGHT on the axis that matters, and
   that is a finding, not a shrug.** The panel runs **13 heterogeneous seats in parallel with NO
   cross-talk** (`ThreadPoolExecutor`, each seat gets the identical dossier, no agent sees another's
   output). That is *exactly* the configuration the literature endorses — heterogeneous
   self-consistency — and it structurally CANNOT suffer the sycophantic-conformity and
   correct→wrong-reversal failures, because there is nothing to conform to. The desk arrived at the
   endorsed design. Log it as validated-by-external-evidence so it does not get "improved" into
   debate later.

2. **REJECT inbox item #43 "automated debate (≈ panel)".** The improvement inbox tail carries
   `43 automated debate (≈ panel ...)` in the batch list. On this evidence, adding a debate/critique
   round ON TOP of the existing independent panel is a **negative-EV change**: 2.1–3.4× token cost
   for a measured accuracy DECREASE, and it would destroy the one property (independence) that makes
   the current panel's agreement signal meaningful. This is a rare case where the literature kills a
   queued desk proposal outright. Cheapest possible win: a change NOT made.

3. **THE REAL DEFECT — `_consensus()` + the panel-inbox triage instruction implement plurality
   voting, and the oracle gap is an argument against exactly that.** `run_external_panel.py:84-92`
   tallies keyword themes across seats, and the inbox header (lines 319-324) instructs the CRO:
   *"Consensus across models = high prior; a lone claim needs code proof."* Combined with
   `_consensus()` only surfacing themes with `n >= 2` (line 311), a finding raised by **exactly one
   of 13 seats is filtered out of the consensus summary entirely** and is triaged under a higher
   evidential burden. The consensus-collapse result says the correct answer is frequently the
   minority one — a 13-seat panel with an oracle gap is discarding its best findings by construction.
   This is the same shape as the desk's own §35 lesson (a finding not routed is a finding that never
   happened), one level deeper: here the finding is routed, then *filtered*. **Proposed change
   (research-lane, no risk path): keep the consensus tally as a PRIORITISATION aid but stop letting
   it act as a filter — add a "SINGLETON CLAIMS" section to the panel inbox listing every
   substantive claim raised by exactly one seat, and change the triage line from "a lone claim needs
   code proof" to "a lone claim needs code proof — and so does a consensus claim; agreement among
   models that read the same dossier is CORRELATED, not independent, evidence."** The second half
   matters as much as the first: 13 seats reading one dossier share its framing and its omissions,
   so 8/13 agreement is nowhere near 8 independent observations. The desk already half-knows this —
   the full-coverage audit feed (lines 242-253) was built precisely because "the auditee was choosing
   the auditor's evidence."

**Cost.** (1) is free (documentation). (2) is negative cost — it cancels queued work. (3) is a small
research-lane edit to one script's inbox-rendering block: a singleton-extraction pass plus two lines
of prompt text. No new model calls, no added tokens per run, no risk path, fully reversible. The
only real cost is CRO triage time — the singleton section will contain more noise than the consensus
section, which is the honest trade and should be stated in the section header.

**Verdict.**
- Panel-is-already-heterogeneous-and-independent: **adopt-now** (record as validated design).
- Kill inbox #43 automated debate: **adopt-now (reject the proposal)**.
- Singleton-claims section + correlated-evidence wording: **pilot** — one panel cycle, then ask the
  only question that matters: did any singleton claim survive CRO verification? If zero over ~3
  cycles, the filter was right and this reverts.

**Provenance.**
- [FETCHED] https://d2jud02ci9yv69.cloudfront.net/2025-04-28-mad-159/blog/mad/ (ICLR 2025 Blogposts
  track — NEW VENUE for this desk, see coverage note)
- [FETCHED] https://arxiv.org/html/2605.00914 (The Cost of Consensus, 2026-04-29)
- [ABSTRACT-ONLY] https://arxiv.org/abs/2502.08788 (Stop Overvaluing Multi-Agent Debate)
- Desk artifacts: `scripts/run_external_panel.py` lines 84-92, 261-290, 307-330;
  `docs/research/improvement_inbox.md` (item 43 in the batch list)

---

### FINDING 2 — The AI-scientist literature's top proposed fix is a "null-result database." The desk already built one (the graveyard + rulings feed) and is therefore AHEAD of the field — and can generate the empirical evidence the field admits it does not have.

**Method / mechanism.** *Dead Science Walking: Publication Bias and the AI Scientist Pipeline*
(arXiv 2606.04220v1) argues that automated-research pipelines inherit a training corpus that
over-represents positive results, then AMPLIFY that bias at three further stages (retrieval,
generation, evaluation). The concrete failure mode it names is the one this desk cares about: an
automated pipeline **proposes a known-falsified hypothesis as a promising new direction** — cheap for
a domain expert to catch once, impossible to contain at scale ("one rediscovery is a review failure;
thousands of rediscoveries become a queueing problem for human expertise"). Its three proposed
structural remedies are (1) **null-result databases** — failed replications and negative trials
indexed in machine-readable form carrying hypothesis, protocol, outcome, effect size and
pre-registration link; (2) retraction-aware evaluation; (3) training-corpus disclosure cards.

**Evidence quality — harsh read, and it is BAD.** This is a **position paper with conceptual
modelling and NO empirical study.** There is no measured rediscovery rate. The "ego-depletion"
worked example is a thought experiment, explicitly not an experiment. The amplification index is
built from asserted multipliers (α₁=1.4, α₂=1.3, α₃=1.2 → AΔ ≈ 2.18×) that the authors themselves
call "first-order estimates, not direct measurements of a deployed AI scientist," and the model
assumes stage independence which they concede is wrong ("biases are likely positively correlated").
Their own stated limitation is decisive: **"no controlled tests comparing retrieval/generation with
vs. without negative evidence."** The remedy is unvalidated. The borrowed replication numbers are
real but second-hand (psychology ~36% replication, Open Science Collaboration 2015; Begley & Ellis
2012, 11 of 53 landmark studies). The one class of hard numbers is the hallucinated-citation audit,
which is third-party and checkable: **100 confirmed hallucinated citations across 51 accepted NeurIPS
2025 papers**, **>50 in ICLR 2026 submissions**, and a stem-cell study where ChatGPT-4o cited **84 of
93 retracted articles**. Those stand on their own and do not depend on the paper's model.
**Verdict on the paper as evidence: near-zero. Verdict on it as a MAP of what the field thinks
matters: useful, because it tells the desk where it already stands.**

**Concrete application to THIS desk — and the interesting direction is REVERSED.** The desk is not a
consumer of this recommendation; it is a year ahead of it and holds data the paper's authors say
does not exist.

1. **The desk already implements remedy (1) TWICE over, and should record that.** `docs/graveyard.md`
   is a null-result database, and `run_external_panel.py:237-241` feeds up to 60,000 chars of it to
   **every** panel mission (widened from generate-only) under the header "GRAVEYARD (already
   falsified — do NOT propose any of these)". `docs/research/panel_rulings.md` is a second layer —
   the settled-questions feed at lines 220-236 — feeding up to 50,000 chars of prior rulings with the
   instruction to not re-propose without new evidence that defeats the stated reason. The desk's
   graveyard also already carries the schema the paper asks for (mechanism of death is mandatory per
   Charter §33(10)). **No adoption needed. Log as convergent-validation.**

2. **THE REAL OPPORTUNITY — the desk can run the controlled test the paper admits is missing, at
   zero marginal cost, from data it has already logged.** `run_external_panel.py:220-236` records a
   natural experiment in its own comment: **"7 of 27 rulings rejected in the 07-20 run"** were
   re-proposals of already-settled findings — measured BEFORE the settled-questions feed was added,
   and the feed was added in response. Every panel run since is logged to
   `data/external_panel_log.jsonl` with mission and timestamp. **The measurement: re-proposal rate
   (findings matching an existing graveyard/rulings entry, as a share of total findings) before vs
   after the feed landed.** That is precisely "retrieval and generation tests over matched
   hypotheses" — the empirical calibration 2606.04220 names as the missing next step. If the rate
   dropped, the desk has evidence for a design the field has only asserted; if it did NOT drop, the
   desk is spending up to 110k chars of every panel payload on a feed that does not work, which is a
   large silent token cost across 13 seats and would be a genuine defect worth finding. **Either
   outcome is valuable, which is the signature of a good test.** This is a research-lane analysis
   over an existing JSONL — no new model calls, no risk path.

3. **Hallucinated citations are a live rail gap for THIS session's own output class.** The NeurIPS/
   ICLR audit numbers are the strongest evidence in the whole area, and they are about *accepted,
   peer-reviewed* work. The desk's literature organs (this one, the Prospector) emit provenance URLs
   that nothing currently verifies. Improvement-inbox **#54 (GRADE-PROVENANCE RAIL)** already
   established the principle for DATA grades — "a search summary is a LEAD, never evidence," requiring
   a `primary_artifact` field with URL + HTTP code + byte/row count. **The gap: #54 binds data-source
   cards but NOT literature citations**, which are exactly as forgeable and, per the NeurIPS number,
   are empirically forged at scale by machines of this class. **Proposed extension: literature/
   mechanism cards carry the same `primary_artifact` discipline — a fetch-verified URL, or the card
   is auto-graded UNVERIFIED.** This session's own file uses the `[FETCHED]`/`[ABSTRACT-ONLY]`/
   `[SEARCH-SUMMARY]` convention as a manual prototype of exactly that.

**Cost.** (1) free. (2) a small analysis script over `data/external_panel_log.jsonl` plus a matching
heuristic against graveyard/rulings entries — call it a few hours of research-lane work, zero
recurring cost, and it may REMOVE up to 110k chars per seat per run if the feed is shown not to work
(a cost SAVING at 13 seats). (3) is a schema field plus a grader — near-free, and it mirrors machinery
#54 already specified, so it is an extension not a new mechanism.

**Verdict.**
- Graveyard-as-null-result-DB already implemented: **adopt-now (record as convergent validation, no
  work)**.
- Measure the re-proposal rate before/after the settled-questions feed: **pilot** — high value, cheap,
  and it tests a 110k-char-per-seat cost the desk currently pays on faith.
- Extend #54's `primary_artifact` rail from data cards to literature citations: **adopt-now** — the
  NeurIPS/ICLR hallucinated-citation numbers are the rare hard evidence here, and the desk's own
  organs are in the affected class.
- The paper's amplification model itself: **reject** — asserted multipliers, conceded-wrong
  independence assumption, no measurement. Cite it for its remedy list and its third-party citation
  audit only.

**Provenance.**
- [FETCHED] https://arxiv.org/html/2606.04220v1 (Dead Science Walking — position paper, no experiments)
- [SEARCH-SUMMARY] the NeurIPS-2025 / ICLR-2026 hallucinated-citation counts are quoted THROUGH
  2606.04220 and its search snippet; the underlying GPTZero audit was **not** opened in this session.
  Per rail #54 these numbers are a LEAD, not verified evidence — verify before quoting them in any
  desk decision.
- Desk artifacts: `scripts/run_external_panel.py` lines 219-241; `docs/graveyard.md`;
  `docs/research/panel_rulings.md`; `data/external_panel_log.jsonl`;
  `docs/research/improvement_inbox.md` #54

---

### FINDING 3 — SELF-VERIFICATION: the desk's "artifact-on-disk, never self-report" law is CORRECT and now has a measured mechanism behind it (64.5% self-correction blind spot). But the most-cited worry in this space — self-preference bias — is ~80-99% MEASUREMENT ARTIFACT, and the desk should not spend a cent defending against it.

This is the ground the parent flagged: *"the desk already has a law that conversion is credited from
ARTIFACTS ON DISK not self-report; find evidence that supports/extends/refutes that design."*
Answer: **strongly supported, with a mechanism, and with one important scope limit.**

**Method / mechanism — (a) the SELF-CORRECTION BLIND SPOT.** *Self-Correction Bench* (arXiv
2507.02778) isolates a clean asymmetry by controlled error injection: take an error, present it
EITHER as the model's own prior output OR as external/user-supplied text, hold the error content
IDENTICAL, and measure correction. Three datasets — SCLI5 (286 samples, trivial), GSM8K-SC (1,313,
multi-step math), PRM800K-SC (448, realistic LLM-generated errors) — across **14 open-source
non-reasoning models**. Result: **average 64.5% blind spot rate.** On GSM8K-SC, models corrected the
**external** version of an error at ~**88.1%** accuracy and the **identical internal** error at
~**18.3%** — and generated **179.5%** (GSM8K-SC) and **73.6%** (PRM800K-SC) more correction markers
when the error was framed as someone else's. Because the error content is held constant, **knowledge
deficiency is ruled out by construction** — the model KNOWS the answer and does not deploy it against
its own text. Root cause traced to training-data composition: non-reasoning SFT corpora have a 95th-
percentile correction-marker frequency of **1**, versus median marker densities of **30-170** in
reasoning corpora. Appending the single token **"Wait"** after an incorrect response cuts the blind
spot by **89.3%** and raises macro-average mean accuracy by **156.0%** with no finetuning.

**Method / mechanism — (b) the SELF-PREFERENCE REBUTTAL (the best rebuttal outranks the paper).**
*Are LLM Evaluators Really Narcissists? Sanity Checking Self-Preference Evaluations* (arXiv
2601.22548) attacks the entire self-preference literature on a confound: prior work never compared a
judge's preference for its own output against a **capability-matched proxy model that failed the same
example**, so it could not separate genuine narcissism from **evaluator uncertainty on hard items**.
Under their Evaluator Quality Baseline, measured self-preference **collapses**: MATH-500 **−98.76%**
(≈40% → near-zero), MBPP+ code **−89%**, translation **−83%**, MMLU **−80%** (residual ~12%),
AlpacaEval **−79%**, truthfulness **−68%**. Only **51% of examples** retain statistical significance
after the control. Qwen2.5-7B on MATH-500: **49.7% → 9.4%**. Entropy analysis shows **0.85
correlation** between self-judging and proxy-judging on hard examples — "uncertainty-driven overlap"
rather than narcissism. Two secondary kills: **model bias ORDERINGS shift considerably** after the
control (so anyone who picked judge models to avoid "the biased ones" optimised on noise), and
chain-of-thought de-biasing showed "limited effectiveness… relatively inconsistent" once properly
baselined — its apparent benefit was largely artifact reduction. Authors' own careful line: *"This
work does not dispute the existence of self-preference, but it does advise on where (not) to look."*

**Evidence quality — harsh read.** 2507.02778's design is the strongest thing I found this session:
identical-error injection is a genuine controlled experiment with the confound removed by
construction, 14 models, 2,047 total samples, and a mechanistic explanation (marker density in
training corpora) that predicts the moderator. It is peer-reviewed-adjacent (on OpenReview, id
7K1kXowjK1 — **NOT opened this session**) and has a follow-up theory paper (2607.09803, SPARC,
**abstract-only**). **The decisive caveat, and it cuts against over-applying this to the desk:
REASONING / RL-trained models "exhibit minimal blind spots."** The 64.5% figure is for
**non-reasoning open-source models**, which is NOT what the desk runs — `run_external_panel.py:99-105`
forces `reasoning: {effort: "high"}` on every reasoning-capable seat, and the brain is a frontier
reasoning model. So the desk sits in the regime where this effect is *smallest*. It is also the
authors' stated limitation that injected errors ≠ natural errors. 2601.22548 is a single-lab
preprint, unreplicated, but its methodology is a strict IMPROVEMENT on what it critiques (it adds a
control that was absent), and adding a missing control is the one kind of result that does not need
replication to be believed — it changes what the prior numbers MEAN.

**Concrete application to THIS desk.**

1. **Charter §33(2) ARTIFACT-ONLY CREDIT is externally validated — but the honest reason is not the
   one written in the law.** §33(2) says *"an organ does not grade its own homework"* and credits
   conversion only from artifacts on disk. The literature says the failure is narrower and weirder
   than generic dishonesty: models are **fine at grading others and specifically bad at grading
   themselves** (88.1% vs 18.3% on identical content). That is a stronger argument for the law than
   the one the law currently makes, because it survives the obvious objection ("a good model would
   just be accurate about itself"). **Recommend: annotate §33(2) with the mechanism + citation.**
   Cheap, and it hardens the law against a future cycle deciding self-report is fine now.

2. **`scripts/run_external_panel.py` statelessness is the right call, and the desk nearly has
   Cross-Context Review for free.** The panel is deliberately stateless (lines 220-225: *"fresh
   context every run is exactly why it can overturn the CRO without defending a prior position"*) —
   the desk's own reasoning, arrived at independently, is the exact premise of *Cross-Context Review*
   (arXiv 2603.12123), which separates production and review sessions and reports fresh-context
   review beating same-context self-review. **Provenance honesty: I could NOT extract 2603.12123's
   effect sizes — the PDF returned compressed binary streams. Treat its numbers as UNVERIFIED; only
   the qualitative direction is usable, and that direction is already the desk's design.**

3. **THE ACTIONABLE GAP — the desk applies cross-context review to its CODE but not to its
   RESEARCH OUTPUT.** The panel reviews the dossier + rotating source slices
   (`build_audit_coverage.audit_payload`). But dig outputs — this file, `literature_cards.md`,
   mechanism cards — are graded by the organ that wrote them or by the brain that commissioned them,
   both of which are the SELF side of the 88.1%/18.3% asymmetry. **Proposal: route a sample of dig
   output through the existing panel as a mission (`verify`), where seats see the CLAIMS and the
   PROVENANCE URLS with the authoring organ unnamed, and are asked only "which of these citations
   support the claim made?"** This reuses machinery that already exists (mission files in
   `prompts/panel_missions/`, `_ROTATION` at lines 45-47) and it targets exactly the failure mode
   Finding 2 measured in the wild (100 hallucinated citations in 51 accepted NeurIPS papers).

4. **DO NOT build self-preference defences into `scripts/score_panel.py`.** This is a
   spend-nothing finding, and it is the kind the desk should want: the intuitive fix — down-weight a
   seat when it evaluates its own family, or add CoT de-biasing to the judge prompt — is defending
   against an effect that is 80-99% artifact and using an intervention (CoT) shown ineffective under
   proper baselines. **Reject.** The genuinely load-bearing bias defences remain **position bias**
   and **verbosity bias**, which are mechanical and cheap: the panel currently concatenates seats in
   provider order into `panel_inbox.md` (lines 328-329) and the CRO reads top-down — a fixed reading
   order is a position bias the desk imposes on ITSELF. **Randomise the seat order per run** (one
   line, `random.shuffle(ok)`), which costs nothing and removes a real, documented bias.

**Cost.** (1) documentation only. (2) zero — already built. (3) one new mission file + a slot in
`_ROTATION`; ~$0.25/run at existing panel economics, no new infrastructure, and it displaces one
rotation slot rather than adding spend. (4) is NEGATIVE cost (cancels a plausible-sounding build)
plus a one-line shuffle.

**Verdict.**
- Annotate §33(2) with the blind-spot mechanism: **adopt-now**.
- Panel statelessness / cross-context: **adopt-now (already built — record as validated)**.
- `verify` panel mission over dig-output citations: **pilot** — one rotation slot, measure how many
  citations fail to support their claim.
- Self-preference defences in `score_panel.py`: **reject** — 80-99% artifact; would optimise on noise
  and the model-ordering it implies is itself unstable.
- Randomise seat order in `panel_inbox.md`: **adopt-now** — one line, removes a self-imposed
  position bias.
- The "Wait" trick: **reject for the panel** — it is an intervention for non-reasoning models, and
  every desk seat runs reasoning-effort-high, the regime where the blind spot is already minimal.

**Provenance.**
- [FETCHED] https://arxiv.org/html/2507.02778 (Self-Correction Bench)
- [FETCHED] https://arxiv.org/html/2601.22548 (Are LLM Evaluators Really Narcissists?)
- [FAILED-EXTRACTION] https://arxiv.org/pdf/2603.12123 (Cross-Context Review — PDF returned binary;
  direction only, numbers UNVERIFIED)
- [FAILED-EXTRACTION] https://arxiv.org/pdf/2410.21819 (Self-Preference Bias in LLM-as-a-Judge — the
  "perplexity not self-recognition" mechanism; PDF unreadable, so the perplexity claim is
  [SEARCH-SUMMARY] only and is NOT relied on above)
- [NOT OPENED] https://openreview.net/forum?id=7K1kXowjK1 ; https://arxiv.org/abs/2607.09803
- Desk artifacts: `docs/DIGGING_CHARTER.md` §33(2); `scripts/run_external_panel.py` lines 45-47,
  99-105, 220-225, 328-329; `scripts/score_panel.py`; `prompts/panel_missions/`

