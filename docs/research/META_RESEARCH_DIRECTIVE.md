# META-RESEARCH DIRECTIVE (Ceiling Version) — CONSTITUTIONAL, NEVER SKIPPED

**Status: PERMANENT. Principal directive, 2026-07-28.** Runs at the end of every major research
cycle. This is the CIO layer: allocate scarce research capital to maximise **future Validated
Alpha Discovery Rate, long-term CAGR, and research productivity per engineering hour**.

> **Why this file exists instead of more prompt text.** This desk's own record is that
> *prompt-only duties are aspirations* — `check_clock_saturation` says it in those words, and
> four consecutive charters shipped laws with zero enforcement. A directive pasted into every
> organ's system prompt is also a tax: `principal_doctrine.txt` is already 27.5k chars and
> `max_audit` flags it as a live defect, because **every organ pays that context on every call**.
> So the directive is stored ONCE here, referenced by pointer, and its computable parts are
> executed by `scripts/meta_research_review.py`. Mechanical beats memorised: a check that runs
> cannot be skipped, and it costs no context until it produces output.

## The objective function (§13 is supreme)

Maximum **long-term compounded capital growth** — not research output. Every hour, project,
collector, experiment, validation task, deployment and infra change is an investment competing
for scarce capital in ONE unified Expected Research Value (ERV) ranking. No category is
automatically prioritised.

**Maximum Constraint.** Never optimise for research volume, experiment count, feature count,
collector count, subsystem count, model complexity, or code size unless doing so is expected to
increase future compounded capital. Reject any recommendation that improves an intermediate
metric while reducing expected long-term capital growth — however intellectually interesting.

**The purpose of meta-research is not to maximise research activity. It is to maximise deployed,
validated alpha.**

---

## 1. Research Capital Allocation
Rank every possible project by Expected Research Value, probability of improving future alpha
discovery, engineering effort, time to measurable impact, strategic importance, opportunity cost.
**Always produce a ranked capital-allocation table.**

## 2. Bottleneck Analysis
Identify the SINGLE greatest limiter of future alpha generation, from: data acquisition,
collector coverage, feature engineering, hypothesis quality, validation, statistical power,
execution, deployment, monitoring, infrastructure, capital, research throughput. Estimate ROI of
removing each. **Recommend only the highest-ROI bottleneck first.**

## 3. Information Frontier Expansion
Does meaningful asymmetric information still exist outside current coverage? Search: unexplored
participant behaviour, forced flows, information delays, alternative data, market-structure
change, emerging venues, new protocols, new asset classes, regional advantages, behavioural
fingerprints, structural inefficiencies. Rank by information advantage, expected alpha, research
cost, replication difficulty, long-term moat.

## 4. Blind Spot Analysis
Coverage %, research depth, information advantage, expected value remaining, expected marginal
ROI per market domain. **Prioritise low-coverage, high-value domains.**

## 5. Data Moat Review
Per dataset: uniqueness, persistence, predictive potential, replication difficulty, maintenance
cost, decay risk → **expand / maintain / retire**.

## 6. Research Efficiency
Experiments per engineering hour; validated experiments per hour; deployed alpha per hour;
information gained per hour. Identify wasted effort; recommend process improvements.

## 7. Validation Efficiency
Unnecessary tests? Automation headroom? Has rigor weakened? Has the multiple-testing burden
grown? Is statistical power sufficient? **NEVER reduce statistical standards — only improve
efficiency.**

## 8. Alpha Lifecycle Review
Classify every live hypothesis: emerging / strengthening / weakening / decaying / retired.
**Recommend replacement research BEFORE decay reaches production.**

## 9. System Complexity Audit
Every subsystem justifies its existence: engineering cost, maintenance burden, measurable
economic contribution, research contribution. Recommend simplification or removal for anything
not materially improving alpha discovery.

## 10. External Frontier Review
New public datasets, APIs, exchanges, protocols, academic work, market-structure changes.
Recommend only sources with high expected information advantage.

## 11. Research Portfolio Optimization
Every project is an investment. Continuously rebalance toward highest ERV; cut investment where
expected contribution has materially declined.

## 12. Continuous Evolution
ONE prioritised roadmap. Every recommendation carries: expected impact, supporting evidence,
engineering effort, estimated completion, implementation risk, dependencies, success metric, ERV
score. **Sorted strictly by ERV**; #1 is always the highest expected long-term improvement to
validated alpha discovery.

## 13. Capital Growth Optimization (highest level)
Global ranking across the whole organisation — collectors, features, hypotheses, validation,
execution, monitoring, infra, automation, deployment, capital allocation, process, simplification,
retirement. For each: expected upside, downside risk, opportunity cost, time to measurable impact,
expected persistence, engineering cost. Ranked against contribution to future validated-alpha
discovery rate, CAGR, Sharpe, geometric growth, drawdown reduction, robustness, research
compounding, information advantage.

**Opportunity Cost test, applied to every major project:** *"If this engineering hour were spent
elsewhere, would expected long-term capital growth improve?"* If yes → reallocate. If no →
continue.

---

## Scoring addenda (applied to every ERV score)

| Lens | Rule |
|---|---|
| **Research Compounding Score** | Prioritise work that unlocks MORE FUTURE discoveries over one-off wins. |
| **Marginal Utility Rule** | Every recommendation must beat the current highest-ranked alternative. |
| **Portfolio Allocation** | Maintain an explicit balance: exploration / exploitation / infrastructure / maintenance / risk reduction / debt reduction. |
| **Optionality Score** | Reward work creating multiple future research paths. |
| **Knowledge Reuse Score** | Reward reusable infrastructure; penalise one-off systems. |
| **Time Value of Research** | Prefer earlier compounding when expected value is similar. |
| **Negative Information Value** | Reward conclusively DISPROVING hypotheses — a killed family is real information. |
| **Discovery Diversity Monitor** | Prevent overconcentration in one research family. |
| **Meta-Learning Engine** | Learn which research PROCESSES produce the most validated alpha, and improve those. |

---

## Enforcement (why this cannot be skipped)

1. `scripts/meta_research_review.py` computes every mechanically-derivable input (§1 ranking
   scaffold, §2 bottleneck evidence, §5 moat table, §6 efficiency ratios, §8 lifecycle counts,
   §9 complexity/orphan census, §11 portfolio balance) and writes `data/meta_research_review.json`.
2. `scripts/run_cadence.py` fires it on the cycle cadence and records `last_meta_research`, with
   a floor in `_STATE_FLOORS_D` — the review cannot silently stretch.
3. `scripts/max_audit.py` check `meta-research` fires a live defect when the review is stale or
   has never run, so a skipped review escalates to the principal's pager like any other defect.

**A cycle that ended without this review is an incomplete cycle.** The judgment sections (§3
frontier, §10 external, and the final ERV ordering) are the brain's work; the script supplies
the measured inputs so that judgment is exercised on evidence rather than recall.

## One honest tension, recorded rather than hidden

Running all 13 sections *in full* every cycle is itself research volume — which §12 and the
Maximum Constraint say to reject unless it raises validated alpha. The desk's ORDER OF OPERATIONS
already puts meta LAST for this reason, and the GENERATION-FIRST duty states that a cycle which
crowded out generation has FAILED its primary duty. The resolution: the mechanical review runs
every cycle (cheap, seconds, no LLM), and the FULL judgment pass runs on the meta cadence or on
trigger — a materially changed bottleneck, a new frontier, or a decaying sleeve. Meta-research
that displaces generation is the exact failure this directive exists to prevent.
