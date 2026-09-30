# QUANT REFERENCE
## Subsystem Expectations for the Existing MT5/Fusion Desk

This document is consulted by the CRO/builder when a subsystem is relevant, changed, failing, overdue for deep review, or currently binding.

It is not read as a full checklist every cycle.

---

## 1. WHOLE-DESK MANIFEST

Maintain a finite, versioned manifest of important producers, feeds, datasets, country/region packs, research families, sandboxes, compilers/converters, gauntlet workers, forward clocks, certificates, promoted sleeves, allocators, gateways, execution components, broker-reconciliation components, provider/model paths, builders, fixers and watchdogs.

For each component retain:

- owner;
- expected cadence;
- current version;
- last valid run;
- last useful output;
- consumer;
- evidence location;
- current state;
- queue/backlog status;
- maximum review age;
- next expected event.

Unregistered runtime components are reconciliation defects.

---

## 2. WHOLE-DESK PATH

For applicable paths trace:

SOURCE/PRODUCER  
→ durable output  
→ canonical intake  
→ compiler/conversion  
→ evaluator  
→ verdict  
→ certificate  
→ forward/shadow  
→ promotion  
→ allocator  
→ gateway  
→ order intent  
→ broker response  
→ order/deal/position  
→ reconciliation  
→ attribution/feedback.

Research-only outputs may legitimately terminate as formula, feature, dataset, measurement, negative result, method improvement or explicit blocker.

Do not force everything into a BUY/SELL strategy.

---

## 3. PRODUCER PRODUCTIVITY

For every approved producer periodically measure:

- jobs attempted;
- jobs completed;
- useful outputs;
- novel mechanisms;
- duplicate rate;
- converted outputs;
- evaluator admissions;
- completed evaluations;
- blockers;
- negative knowledge;
- downstream use;
- maintenance burden.

A process can be technically healthy while economically unproductive.

Repeated low-value output triggers diagnosis of source exhaustion, stale cursors, poor query generation, bad parsing, access/authentication, language mismatch, low novelty, compiler incompatibility, consumer failure or excessive maintenance cost.

Park/retire when justified.

Reopen when triggers appear.

---

## 4. REGIONAL / LANGUAGE RESEARCH

Keep the universe open across all approved regions/languages.

Use native-language search and local terminology where useful.

Do not pretend translated English queries equal native ecosystem coverage.

Regional packs may be ACTIVE, EXPLORATORY, COLD, PARKED, RETIRED or REOPENED.

Equivalent capability does not require equal compute.

Coverage debt should be visible.

---

## 5. HIGH-RETURN / SURVIVOR REVERSE ENGINEERING

Investigate public/licensed systematic traders, EAs, copy systems, competitions, leaderboards, strategy platforms, performance histories, abandoned/failed/retired systems, technical descriptions and public institutional mechanisms.

For worthwhile leads preserve:

- canonical source/version;
- evidence grade;
- return/profit/AUM/notional distinction;
- capital flows where visible;
- leverage;
- compounding;
- costs;
- funding/financing;
- feature/observation set;
- entry;
- filters;
- exits;
- sizing;
- execution;
- regime;
- unknowns;
- alternative explanations;
- falsifier;
- literal reproduction where feasible;
- baseline;
- ablations;
- descendants;
- combinations;
- valid MT5 transfer hypotheses.

Screenshots and extraordinary claims are priors, not proof.

Repeated publication is not independent corroboration.

---

## 6. DATA / ASYMMETRY PROGRAMME

Continuously investigate, when useful:

### Market
prices, quotes, spreads, ticks, permitted depth, reference markets, basis, financing, swap, liquidity, execution conditions.

### Derivatives
term structure, futures curves, basis, open interest, positioning, permitted options surfaces, IV, skew, expiries, roll mechanics, dispersion.

### Macro
inflation, labor, growth, rates, central banks, curves, auctions, repo, issuance, fiscal, expectations, revisions, interventions, capital controls.

### Events
public official sources, regulators, courts, sanctions, tariffs, elections, conflict, policy implementation/reversal, speeches, testimony, press conferences, corrections.

### Physical economy
energy, production, inventory, refineries, mines, agriculture, crops, weather, ports, freight, pipelines, river levels, power, outages, permitted geospatial measures.

### Corporate/economic networks
filings, earnings, guidance, corporate actions, tenders, contracts, permits, enforcement, courts, supply chains.

### Own observations
quotes, ticks, attempts, fills, rejects, latency, slippage, stale periods, non-fired setups, blocked decisions, prediction errors, failures.

For each dataset/version retain source, rights/permitted use, coverage, units, point-in-time availability, publication/receipt time, revision behavior, quality, hashes/lineage, consumers, enabled hypothesis families and outcome history.

---

## 7. EVENT INTELLIGENCE

Separate:

### FAST PATH
authorized event  
→ version/timestamp  
→ factual/extraction confidence  
→ surprise/novelty  
→ existing validated event-conditioned sleeve inputs  
→ allocator.

### RESEARCH PATH
event + subsequent outcomes  
→ event-family hypotheses  
→ gauntlet  
→ prospective evidence.

A headline never directly creates lots.

Keep factual political/event extraction neutral and sourced.

Do not infer motives or make unsupported political outcome predictions.

---

## 8. EXTERNAL SANDBOX FEDERATION

Examples may include RD-Agent(Q), AlphaForge, AlphaSAGE, EA Studio, StrategyQuant where legitimately available, Seq2Pat, pysubgroup, DreamCoder-style systems, PySR, Tigramite, STUMPY, PySINDy, PyDMD, causal-discovery methods, GP/evolution, GFlowNet, Bayesian search, quality-diversity and other genuinely distinct methods.

Do not count installed/importable as productive.

Check:

- version/license;
- input rotation;
- actual typed outputs;
- provenance;
- conversion;
- evaluator admission;
- completed verdicts;
- incremental contribution;
- maintenance burden.

External systems propose.

They do not validate themselves or grant capital.

---

## 9. HMM / REGIME / VOLATILITY / BAYESIAN RESEARCH

When these families are active, challenge shallow implementations.

### State models

- multiple state counts;
- sticky/persistent variants;
- hierarchical/coupled variants where justified;
- heavy-tailed emissions;
- HSMM/duration;
- switching autoregressions;
- Markov-switching volatility;
- covariate-dependent transitions;
- change-point challengers;
- multivariate states;
- posterior state uncertainty;
- transition stability.

Never use future-informed smoothed labels as live features.

### Volatility

- GARCH;
- EGARCH;
- GJR/TGARCH;
- APARCH;
- FIGARCH/long-memory where justified;
- heavy-tailed/skew innovations;
- realized-vol models where supported;
- multivariate/DCC;
- event/regime conditioning;
- vol-of-vol;
- jumps/extremes;
- spread/slippage/liquidity-vol forecasts.

Compare with simple rolling/EWMA baselines.

### Bayesian

- hierarchical shrinkage;
- partial pooling;
- dynamic parameters;
- posterior predictive distributions;
- state/change-point uncertainty;
- model averaging;
- calibration;
- prior sensitivity;
- Bayesian optimization;
- sequential updating.

Bayesian language is not decoration.

A posterior used operationally needs calibration evidence.

---

## 10. CONVERSION

Every admitted item/version receives explicit disposition.

Possible states:

TESTABLE  
QUEUED  
EVALUATING  
EVALUATED  
RESEARCH_ONLY  
DUPLICATE  
INVALID  
BLOCKED_DATA  
BLOCKED_RULES  
BLOCKED_INSTRUMENT  
BLOCKED_RIGHTS  
BLOCKED_EXECUTOR  
BLOCKED_SAMPLE  
PARKED  
RETIRED

or canonical equivalents.

Silent loss must be zero.

Preserve semantics, timing, required legs, units, provenance, costs and lineage.

Do not silently simplify multi-leg or timing-dependent ideas into invalid single-leg rules.

---

## 11. GAUNTLET

Validate both integrity and power.

### Integrity controls

- lookahead;
- future revisions;
- target leakage;
- bad timing;
- invalid units;
- duplicate alpha;
- cost-free bogus strategies;
- deliberately overfit searches.

### Power controls

Use controlled positive signals to verify that the evaluator can detect specified effects.

The gauntlet itself can fail.

Do not tune it to produce a desired number of survivors.

---

## 12. FORWARD CLOCKS

Audit:

- candidate/version identity;
- enrollment;
- last update;
- raw trades;
- effective observations;
- dependence;
- calendar/trading days;
- data/model version;
- missing intervals;
- completion;
- adjudication.

Completed-but-unadjudicated clocks are defects.

Clock progress comes from qualifying evidence, not heartbeat time.

---

## 13. PROMOTABLE-CANDIDATE CENSUS

Use canonical equivalents of:

NOT_READY  
PROMOTABLE  
PROMOTION_BLOCKED  
PROMOTED_NOT_ARMED  
ARMED_NOT_CONSUMED  
CONSUMED_NO_ORDER_OPPORTUNITY  
ORDER_ATTEMPTED  
LIVE_FILLED  
LIVE_ACTIVE  
LIVE_COMPLETED  
LIVE_DEFECT

Verify exact code/data/model evidence versions before promotion.

Promotion eligibility is not promotion.

Promotion is not arming.

---

## 14. ALLOCATOR

Verify:

- intended cadence;
- fresh evidence;
- complete eligible sleeve set;
- current costs;
- current positions;
- correlations/exposures;
- uncertainty;
- event-conditioned inputs where applicable;
- versioned decisions;
- gateway consumption;
- attribution feedback.

Audit expected-log-growth units/horizon.

Compare complex allocation against appropriate simple baselines prospectively.

Do not force heat/utilization.

---

## 15. LIVE EXECUTION

Inspect:

- deployed strategy;
- certificate;
- promotion;
- arm state;
- allocation;
- last valid signal;
- last order attempt;
- last broker response;
- fills;
- open/closed positions;
- P&L;
- spread;
- commissions;
- swap/financing;
- slippage;
- rejects;
- missed signals;
- stale feed;
- clock drift.

Broker/account/environment identity must be explicit.

Demo/shadow/live must never be ambiguous.

---

## 16. PROVIDERS / OPENROUTER

OpenRouter, Kimi, DeepSeek, Claude, Codex, Gemini and other enabled providers are tools in the research plane.

Verify:

- authentication;
- usable model/version;
- quota/budget;
- substantive invocation;
- useful outputs;
- checkpointing;
- failover;
- downstream conversion;
- evaluator admission where applicable.

Useful model work may include:

**mine → extract → generate → deepen → reconstruct → criticize → falsify → descendants/ablations/combinations → compile cells → learn from gauntlet results.**

Token volume is not productivity.

If a provider is shallow, duplicative or unconverted, fix routing/task design/conversion or reduce its role.

---

## 17. CEO / BUILDER / CHECKER / FIXER

The loop is:

OBSERVE  
→ prioritize  
→ implement  
→ independently check  
→ fix failed checks  
→ integrate  
→ release  
→ verify runtime  
→ measure benefit.

Uncommitted completed work, stale branches, conflicts, divergence, failed merges/rebases, failed CI and release/deploy mismatches are implementation defects.

Resolve semantically.

Do not blindly accept “ours,” “theirs,” latest timestamp or last writer.

---

## 18. BLIND-SPOT COVERAGE

Maintain a mapping:

failure mode  
→ detector  
→ evidence source  
→ response  
→ last tested  
→ last successful detection/recovery exercise.

Unknown coverage remains DETECTION_GAP.

Continuously reduce important detection gaps.

---

## 19. PERIODIC DEEP-AUDIT TOPICS

Rotate deep audits based on risk, change rate, overdue age, current anomalies and information value.

Topics include:

- region/language coverage;
- statistical/multiplicity contract;
- sandbox productivity;
- data quality/rights;
- provider/model routing;
- release integrity;
- disaster recovery;
- allocator;
- execution/reconciliation;
- forward clocks;
- blind-spot detection;
- research-family depth.

Do not deep-audit all of these every twice-daily cycle.

---

## 20. PROVE REAL DOWNSTREAM CONSUMPTION

For non-capital paths, use replay/shadow/paper/canary evidence where appropriate.

For live trading, wait for naturally occurring authorized signals.

Never manufacture a real trade merely to prove integration.

An implementation is not complete until the intended consumer processes the released version or a legitimate explicit blocker is recorded.
