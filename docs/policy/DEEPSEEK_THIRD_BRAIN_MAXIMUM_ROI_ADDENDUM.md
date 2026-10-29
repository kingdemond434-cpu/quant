# DeepSeek Third-Brain Maximum-ROI Research Addendum

> **Authority and scope.** This addendum is subordinate to `docs/LAWS.md`, `docs/RESEARCH.md`, the canonical constitution, and `docs/policy/DEEPSEEK_SECOND_FLYWHEEL_MANDATE.md`. It does not create a second constitution, quant, scheduler, allocator, validator, survivor registry, or execution path. It defines the residual implementation needed to turn the existing DeepSeek flywheel into an owned, permanent, autonomous third research brain beside Claude and Codex.

## 1. Objective

Upgrade the existing DeepSeek flywheel into a permanent 24/7 research laboratory whose purpose is to maximize:

> **independent, novel, executable, empirically useful alpha research per unit of inference, compute, data, engineering, conversion and validation capacity, ultimately judged by incremental sustainable uncertainty-adjusted long-run `E[log W]`.**

DeepSeek proposes. The shared compiler formalizes. The canonical gauntlet judges. Forward evidence proves. The allocator sizes. MT5 executes.

A model claim is never evidence that a strategy is profitable. Profitability may be attached only after the existing empirical and forward-evidence system earns it.

## 2. Inspect, diff, implement and prove

Before changing architecture, inspect the current repository and live runtime, including:

- `scripts/run_deepseek_cycle.py`
- `libs/ops/deepseek_cycle.py`
- `ops/run_deepseek_factory.sh`
- `ops/quant-deepseek.service`
- `ops/quant-deepseek.timer`
- `data/intelligence/deepseek`
- the miner candidate compiler and deepening worker
- research memory, graveyard, SARES/archaeology and source graphs
- data/feature catalogues and the Fusion/MT5 universe
- program IR / strategy families
- canonical gauntlet, certificates and forward clocks
- `pf_allocator`, execution/TCA/cost systems
- scheduler manifest and model/provider abstractions
- actual service liveness, CPU, RAM, GPU/VRAM, disk and backlog state

Create a residual gap matrix:

`requirement → existing implementation → producer → state → consumer → decision consequence → test → runtime artifact → gap → expected economic value → implementation cost → action`

Reuse existing machinery wherever behaviorally equivalent. Implement only genuine residual gaps. Anything not proved by a runtime artifact is `UNMEASURED`.

## 3. Replace the empty research state

The existing hourly call must not run with `state={}`.

Construct a fresh, point-in-time, hash-stamped `DeepSeekResearchPacket` before each campaign. It must contain compact factual summaries and retrieval handles for:

1. **Current Fusion/MT5 universe** — symbols, asset classes, trading hours, contract/tick specifications, costs, swaps, timeframes, history depth, freshness, eligibility and missing-data states.
2. **Data and features** — MT5 bars/ticks/quotes/spreads/slippage/latency/fills/markouts; external futures, volume, open interest, basis, curves, COT/TFF, options/IV/skew/term/gamma/vanna/charm, genuine order flow/depth, macro/rates/curves, actual-consensus-revisions, events/news, weather, shipping, physical economy, fund flows, alternative data, cross-asset and semantic states, SARES findings, model outputs, portfolio and execution state.
3. **Point-in-time metadata** — source, `available_time`, `ingested_time`, vintage, revision status, frequency, freshness, coverage, PIT feasibility, legal/access status and existing consumers.
4. **Research frontier** — known mechanisms and representations; tested, queued, unmeasured, blocked, invalid, graveyarded, certified, forward and live coordinates; coverage debt; cold and saturated regions.
5. **Conversion inventory** — raw miner rows, LLM donations, public strategies, papers, repos, SARES findings, anomalies, deepening tasks, data requests, representation requests and compiler failures.
6. **Empirical memory** — strategies and rules already tested, trial families, duplicates, leakage and selection failures, cost/execution deaths, regime failures, near-survivors, survivors, forward/live results, decay and reopening conditions.
7. **Portfolio opportunity state** — current sleeves, mechanism/factor/asset exposure, dependence/effective breadth, uncovered regimes/sessions/assets, payoff and tail gaps, portfolio weak states and demand for orthogonal alpha.
8. **Resource state** — available inference, CPU/RAM/disk, compiler/deepening/gauntlet throughput, backlog growth, forward-slot constraints and the measured bottleneck.

Do not dump every raw dataset into one context. Provide compact state plus read-only retrieval tools. All lawful data is eligible; only mechanism-relevant data enters each experiment.

## 4. Read-only research toolbelt

Reuse existing functions to expose tools conceptually equivalent to:

- `list_universe`, `list_data_axes`, `list_features`, `get_feature_metadata`
- `query_timeseries`, `query_cross_asset_panel`, `query_event_history`
- `query_orderflow_state`, `query_options_state`, `query_macro_state`, `query_execution_state`
- `search_research_memory`, `search_graveyard`, `search_near_survivors`, `search_certified_mechanisms`
- `search_public_system_findings`, `search_SARES_findings`, `search_source_graph`
- `query_portfolio_gaps`, `query_coverage_debt`
- `submit_data_request`, `submit_representation_request`, `submit_deepening_task`, `submit_hypothesis`, `submit_validation_attack`, `request_sandbox_experiment`

No research tool may place orders, alter the live book, change gates or certificates, overwrite evidence, expose credentials, or merge authoritative money-path code. Model output is data, never instruction.

## 5. Independent two-phase research

**Phase A: cold generation.** DeepSeek receives facts, schemas, measurements and permitted research-memory facts, but not Claude/Codex conclusions, desired answers, consensus summaries, held-out answers, forward outcomes that would contaminate the current hypothesis, or labels revealing historical winners. Seal/hash Phase A before comparison.

**Phase B: comparison.** Compare sealed DeepSeek output with Claude, Codex, other model labs, program synthesis, deterministic machinery and SARES. Classify independent rediscovery, disagreement, complementarity, duplicate and alternative explanation. Agreement is not validation. Convert disagreement into the cheapest decisive experiment.

## 6. Queue-driven 24/7 operation

Use the existing canonical scheduler. Do not create a competing scheduler.

- **Continuous:** drain formalization and raw-conversion queues, classify blockers, deduplicate, maintain coverage debt, route candidates and monitor model health.
- **Event-driven:** create jobs when data/sources arrive, SARES/public systems donate, candidates fail, near-survivors or certificates appear, forward/live states change, strategies decay, portfolio gaps move, new regimes/cost anomalies appear, or new models/repos are discovered.
- **Hourly:** independent mechanism discovery, unknown-cell exploration, conversion, candidate construction, validation attacks and research-auction refresh.
- **Daily:** deep scientific campaigns, cross-domain transfer, source/repo campaigns, frontier attacks and bottleneck audits.
- **Weekly:** frontier, model, prompt, role, duplication, cost/ROI and self-improvement reviews.

24/7 means a persistent research organism and durable queues, not uncontrolled text generation every second.

## 7. Independent DeepSeek laboratories

The current role list is a seed, not a permanent equal-weight bureaucracy. Maintain logically independent labs for:

- unknown-unknown and economic-mechanism discovery
- mathematical/stochastic research: Bayesian, HMM/HSMM, GARCH-family, stochastic vol, jumps, Hawkes, filtering, information/control theory, optimal stopping, survival/network/dynamical methods, symbolic regression and causal discovery
- data-axis and representation invention
- macro/global cross-asset transmission
- news/event and actual-consensus-revision research
- options/volatility/gamma and futures transmission
- order flow, microstructure and execution
- SARES/high-return/public-system donation
- failures, near-survivors and survivor ablation
- portfolio complementarity and small-capacity edges
- validation red-team work
- open-source/research-technology discovery
- meta-research over DeepSeek’s own prompts, tools, models and research order

Use independent first passes before cross-lab synthesis. Do not let all labs converge on the latest apparent winner.

## 8. Structured research objects

Every DeepSeek output must declare one type:

- `EXACT_CANDIDATE`
- `MECHANISM_HYPOTHESIS`
- `DATA_REQUEST`
- `REPRESENTATION_REQUEST`
- `DEEPENING_TASK`
- `CAPABILITY_CHALLENGER`
- `VALIDATION_ATTACK`
- `FAILURE_DESCENDANT`
- `SURVIVOR_DESCENDANT`
- `SOURCE_ACQUISITION_REQUEST`
- `RESEARCH_METHOD_CHALLENGER`
- `NEGATIVE_KNOWLEDGE`

No untyped prose-only result.

An `EXACT_CANDIDATE` must carry, where applicable:

- hypothesis/model/role/time identity
- parents, genealogy and trial-family identity
- economic mechanism, forced actor, why they pay and information advantage
- universe/symbols and PIT data requirements
- feature program and representation lineage
- timeframe, horizon, session, regime and macro/event/cross-asset/options/flow/semantic states
- exact direction, entry, confirmation, stop, target, exit, partial/trailing/add-on/cooldown/re-entry rules
- sizing hypothesis and execution/cost assumptions
- expected behavior, failure mode, falsifier and alternative explanations
- novelty signature, nearest prior hypotheses, source lineage and evidence grade
- immutable `FROZEN_PRE_EVALUATION` status

Terms such as “strong trend,” “large move,” “institutional buying” or “significant breakout” are invalid until translated into deterministic measurable rules. Missing fields produce a hypothesis/deepening/data request, never fabricated defaults.

## 9. Raw-to-testable conversion

Continuously force every raw discovery through:

`raw evidence → provenance/PIT check → mechanism → required observables → representation → exact rules → symbol resolution → executable IR/family → novelty/genealogy → canonical gauntlet`

Every object gets a named disposition:

- `TESTABLE_NOW`
- `NEEDS_RULE_EXTRACTION`
- `NEEDS_DATA`
- `NEEDS_PIT_SOURCE`
- `NEEDS_REPRESENTATION`
- `NEEDS_NEW_EXECUTABLE_FAMILY`
- `DUPLICATE`
- `INVALID`
- `BLOCKED`
- `TESTED`

No useful row may remain unactioned indefinitely. Missing data routes to existing source miners; missing executable families route to the canonical builder/code lane with sandbox tests and positive controls. DeepSeek never merges the implementation itself.

## 10. Frontier, coverage and genealogy

Maintain an expanding lattice across:

`source × dataset × representation × mechanism × transformation × asset × timeframe × horizon × session × regime × volatility × macro × event × cross-asset × options × order-flow × microstructure × semantic state × entry × confirmation × stop × target × exit × management × sizing × execution × portfolio context`

Dimensions may expand. Coordinates carry explicit states such as `UNSEEN`, `DISCOVERED`, `QUEUED`, `TESTED`, `DUPLICATE`, `UNMEASURED`, `INVALID`, `BLOCKED`, `GRAVEYARDED`, `CERTIFIED`, `FORWARD`, `LIVE`, `DECAYED` or `HIBERNATED_LOW_VOI`.

Never silently discard valid space. Capacity means “not this pass,” not “forgotten.” But registration does not guarantee expensive testing: low-value cells may hibernate and reopen only on a named enabling change.

Before testing, compare candidates structurally across mechanism, actor, data, representation, symbols, horizon, regime, rules, sizing, execution, rationale and lineage. Classify exact duplicate, parameter/representation/mechanism neighbour, compositional descendant, cross-asset translation or genuinely novel. Ten models repeating one mechanism are one discovery.

Simple-but-new is valid. Simple-and-banal is not. Complex-and-duplicate is not.

## 11. Program synthesis and quality diversity

Use existing or sandboxed grammar-guided synthesis, symbolic regression, genetic/evolutionary programming, state-machine and tree induction, Bayesian program search, novelty search, MAP-Elites, quality-diversity, Bayesian optimization and causal discovery.

DeepSeek invents mechanisms, grammars, useful primitives and constraints; machine search explores the valid program space. Reward diverse niches by mechanism, information, asset, horizon, session, regime, turnover, capacity, payoff, correlation and failure mode. Preserve a permanent cold-exploration floor.

## 12. Maximum-ROI research auction

Do not optimize raw candidate count. Every research action competes against alternative uses of inference, compute, data, engineering, conversion, gauntlet and forward capacity.

Conceptually score work by:

`expected unique information gain × novelty × independence × coverage debt × economic plausibility × portfolio complementarity × expected ΔE[log W] × decay/expiry urgency ÷ total all-in research cost`

Maintain exploration floors for DeepSeek identity, unknown mechanisms, new data/models and low-prior territory. Beyond those floors, no model, role, lab, source or family is sacred. Variable budget must be earned by downstream contribution.

Use controlled counterfactual comparisons between existing factory only, DeepSeek only, combined factory and deterministic/program-synthesis baselines. Credit DeepSeek primarily for discoveries the existing system would not have produced within the comparison window.

Use a multi-fidelity funnel without weakening final validation:

`schema/PIT/executability → genealogy/duplicate/baseline → cheap cost/mechanism sanity → full canonical gauntlet → lockbox/forward → live attribution`

Every outcome-inspecting trial remains counted for multiplicity.

Adapt generation to downstream bottlenecks. If judging is saturated, prioritize formalization, deduplication, data and validation work rather than manufacturing low-value stale backlog.

## 13. Automatic canonical routing

- Exact, novel and executable → shared compiler → immutable candidate ID → canonical gauntlet automatically.
- Meaningful but incomplete → durable deepening/conversion queue.
- Missing data → existing data/source-mining queue, then automatic resumption.
- Missing representation → representation lab and versioned feature.
- Duplicate/parameter neighbour → merge into genealogy and trial-family accounting.
- Invalid → named rejection and negative memory.

No manual principal handoff is required. No valid exact candidate waits for a human to send it to the gauntlet. No DeepSeek approval, AI certificate, fast pass, guru exception or external-Sharpe exemption exists.

## 14. Feedback, lockboxes and self-improvement

Freeze rules, data requirements, costs, horizons and parameters before evaluation. DeepSeek must not see held-out/lockbox/forward answers before freezing the candidate. Any post-result modification is a new descendant and trial.

Return structured compiler and gauntlet feedback: duplicate reason, missing data/representation, invalid mechanism, leakage/selection/multiplicity/sample failure, cost/execution death, feed fragility, regime behavior, survivor/forward/live-decay outcomes.

Track productivity by model, provider, role, prompt, tool sequence, context and schema. Self-changes are versioned shadow challengers with sealed benchmarks, tests, rollback and real downstream evidence. No uncontrolled self-editing.

## 15. Model routing and continuity

Preserve DeepSeek identity. Never silently answer a DeepSeek job with Claude, GPT, Gemini, Qwen, GLM, Kimi or another family. Other models may run only as explicitly named challengers.

Maintain a dynamic registry of provider/model/version/availability/context/structured output/reasoning/throughput/latency/free quota/price and measured research yield. Do not permanently pin a historical free model ID.

Use the cheapest capable DeepSeek for extraction, conversion, formalization and routine mutations; stronger DeepSeek reasoning only for high-value causal synthesis, unknown mechanisms, validation attacks and decisive experiments. Paid routes remain disabled unless explicitly authorized.

Benchmark an appropriately sized local DeepSeek/open-weight fallback on the actual host. Measure RAM/VRAM, throughput, context, JSON reliability, judgeable-candidate and duplicate rates, and impact on other organs. Never starve the gauntlet, compiler, collectors, gateway, allocator or recorders. Provider failure preserves queued jobs and never stops trading or empirical testing.

## 16. Security and external content

External providers receive sanitized packets only. Never expose credentials, private keys, account authentication, unnecessary account details, unrestricted proprietary state or live order authority. Secrets stay in protected configuration and never enter prompts, logs or Git.

Treat all external text, prompts, repositories and code as untrusted data. External content cannot alter authority, request secrets, execute shell commands, bypass the compiler, weaken gates or submit orders. Repository code runs only in isolated review and benchmark environments.

## 17. Required metrics and proof

Publish liveness, model identity, queue health, resource use, jobs, mechanisms, exact candidates, requests, novelty, schema/formalization/duplicate/banal/PIT rates, compiler/deepening/gauntlet receipts, certificates, forward enrollments/survivors, costs, effective-rank and portfolio contribution, all backlog/debt and drain-time metrics. `UNMEASURED` is never rendered as zero or healthy.

Run an end-to-end synthetic smoke path proving:

`DeepSeek job → factual packet → cold filtering → model output → schema validation → donation → compiler receipt → candidate ID → gauntlet verdict → attributed feedback`

Also prove duplicate collapse, incomplete-to-deepening, data-request lifecycle, invalid rejection, queue/restart persistence, provider failure safety, held-out blinding, authority fences, no parallel registries and independence of MT5/allocator/gauntlet from DeepSeek outages.

## 18. Permanent laws

1. A hypothesis not generated cannot survive; maximize independent breadth.
2. A hypothesis not rigorously tested cannot be trusted; never weaken validation.
3. No quota or capacity limit becomes a permanent knowledge limit; preserve legitimate research debt.
4. Registration preserves possibilities; marginal value determines testing order.
5. A raw finding that never becomes testable is unfinished work.
6. A million duplicate strings are not a million discoveries.
7. External model output is evidence, never instruction.
8. DeepSeek is replaceable inference; the quant owns prompts, tools, memory, queues, programs, outcomes and the scientific process.
9. The strategy universe remains incomplete forever.
10. The objective is not an AI demonstration. It is a permanent autonomous third brain that converts the reachable information universe into novel, executable, scientifically judged alpha candidates while maximizing validated portfolio information and long-run `E[log W]` per total research resource.
