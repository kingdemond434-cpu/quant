# Tier S research institution: the 46-layer gap map

Derived from `docs/research/tier_s_program.json` by `python scripts/check_tier_s_program.py --render`. Never edit by hand.

**Admission rule.** A subsystem ships only with a measurable contract (gain in: ALPHA_DISCOVERY, FALSIFICATION, INFO_PER_COMPUTE, FDR_REDUCTION, CALIBRATION, EXECUTION_CAPTURE, OPERATIONAL_RISK, PRODUCTIVITY). Evaluated hourly by tier_s.contracts: ADMITTED, REJECTED or UNMEASURED. Blueprint CLOSED 2026-09-29: no new categories.

Every layer runs hourly (leg `tier_s` unless named). The verdict column is the contract's latest hourly verdict when rendered with `--with-verdicts` on the box; `-` means not joined. Live verdicts: `desks/mt5/reports/tier_s/CONTRACTS.json`.

| id | layer | gain | metric | verdict | latest | money-path authority awaiting the principal |
|---|---|---|---|---|---|---|
| S01 | Truth kernel: content-addressed journal, constitution, evidence seal | OPERATIONAL_RISK | `truth_kernel.metric.journal_ok` (up) | - | - |  |
| S02 | World data OS: bitemporal store and point-in-time audit | CALIBRATION | `data_os.metric.pit_share` (up) | - | - |  |
| S03 | World model: causal edges classified stable/decaying/false; broken edges become hypotheses | ALPHA_DISCOVERY | `world_science.metric.hypotheses` (up) | - | - |  |
| S04 | Researcher civilization: heterogeneous cohorts priced by independent discoveries | PRODUCTIVITY | `market.metric.n_researchers` (up) | - | - |  |
| S05 | AlphaEvolve for alpha: genome evolution with operator yield | PRODUCTIVITY | `genomes.metric.diversity` (up) | - | - |  |
| S06 | MAP-Elites quality-diversity archive | ALPHA_DISCOVERY | `qd.metric.qd_score` (up) | - | - |  |
| S07 | Evolving researcher genomes (fitness = validated independent info per compute) | INFO_PER_COMPUTE | `genomes.metric.best_fitness` (up) | - | - |  |
| S08 | Researcher market: Thompson sampling + MILP compute allocation, floors never cut | INFO_PER_COMPUTE | `market.metric.independently_discovered` (up) | - | - |  |
| S09 | Red Queen: attackers and validator defenders co-evolve | FALSIFICATION | `red_queen.metric.defender_balanced` (up) | - | - |  |
| S10 | Planted traps: immune score with FREEZE verdict | FALSIFICATION | `immune.metric.immune_score` (up) | - | - | the promoter honouring data/tier_s/PROMOTION_FREEZE.json (admission) |
| S11 | Online FDR: LORD++ and e-LOND over the lifetime trial stream | FDR_REDUCTION | `online_fdr.metric.over_budget_share` (down) | - | - | online-FDR wealth gating admission |
| S12 | Epistemic firewall: per-role static audit with ratchet | OPERATIONAL_RISK | `firewall.metric.violations` (down) | - | - |  |
| S13 | Negative-knowledge graph: typed failure causes and failure theorems | FDR_REDUCTION | `failure_memory.metric.theorems` (up) | - | - |  |
| S14 | Ancestry graph: novelty against ancestors and exact repeats | ALPHA_DISCOVERY | `topology.metric.effective_discoveries` (up) | - | - |  |
| S15 | Effective independent alpha rank (linear, rank, tail, drawdown, ancestry) | ALPHA_DISCOVERY | `topology.metric.effective_rank` (up) | - | - |  |
| S16 | Counterfactual world lab: edges tested for stability across states | FALSIFICATION | `world_science.metric.stable_edges` (up) | - | - |  |
| S17 | Alpha theory compiler: seven-slot mechanisms | PRODUCTIVITY | `theory.metric.complete_share` (up) | - | - |  |
| S18 | Theory-evidence graph: Beta posteriors weighted live 3 / forward 2 / backtest 1 | CALIBRATION | `theory.metric.supported` (up) | - | - |  |
| S19 | Non-LLM intelligence: information, spectral, Kalman, queueing, ecology, network, MCMC labs | ALPHA_DISCOVERY | `world_science.metric.hypotheses` (up) | - | - |  |
| S20 | Peer review panels: typed challenges with resolvers | FALSIFICATION | `review.metric.resolved_share` (up) | - | - |  |
| S21 | Auto-invented tests: proposed on one suite, confirmed on another | FALSIFICATION | `test_invention.metric.candidate_gates` (up) | - | - |  |
| S22 | Evolving research grammars: primitives learned from winners, dead operators retired | PRODUCTIVITY | `grammar.metric.n_primitives` (up) | - | - |  |
| S23 | Execution science: signal alpha separated from execution drag | EXECUTION_CAPTURE | `report:EXECUTION_SCIENCE.json.attribution.median_drag_as_share_of_signal_alpha` (down) | - | - |  |
| S24 | No-trade as a first-class action in the exchange | EXECUTION_CAPTURE | `exchange.metric.defer_share` (up) | - | - |  |
| S25 | Opportunity exchange: bids cleared by robust E[log W] (shadow) | ALPHA_DISCOVERY | `exchange.metric.expected_log_growth` (up) | - | - | the exchange's book replacing or steering the allocator (sizing) |
| S26 | Live prediction accounting: CRPS, PIT, coverage, honesty shrinkage | CALIBRATION | `predictions.metric.accounted_share` (up) | - | - |  |
| S27 | Live reality outranks backtests: overconfidence measured on live outcomes | CALIBRATION | `predictions.metric.overconfidence` (down) | - | - |  |
| S28 | Digital twin: registered-after-only paired evaluation, one-op rollback | PRODUCTIVITY | `twin.metric.challengers` (up) | - | - |  |
| S29 | Self-model: deficiency ranking and sealed scorecard regression | PRODUCTIVITY | `self_model.metric.regressed` (down) | - | - |  |
| S30 | Architecture evolution: challengers adopted on sealed evidence | PRODUCTIVITY | `twin.metric.adopted` (up) | - | - | adoption of money-path challengers (always PROPOSE, never automatic) |
| S31 | Formal verification of the money path: BFS model check of the order protocol | OPERATIONAL_RISK | `formal.metric.protocol_proven` (up) | - | - |  |
| S32 | Independent evaluator civilization: evaluators challenged by the panel | FALSIFICATION | `review.metric.challenged` (up) | - | - |  |
| S33 | Architecture evolution above strategy evolution: validator genomes compete | FALSIFICATION | `red_queen.metric.defender_balanced` (up) | - | - |  |
| S34 | Immutable meta-benchmark suite: sealed hash of generator, seeds and prices | FALSIFICATION | `immune.metric.balanced` (up) | - | - |  |
| S35 | Active information acquisition: acquisition predictions calibrated on arrival | INFO_PER_COMPUTE | `data_os.metric.calibrated_rankers` (up) | - | - |  |
| S36 | Research-search frontier estimator: Chao1, Good-Turing, yield exponent | INFO_PER_COMPUTE | `frontier.metric.coverage` (up) | - | - |  |
| S37 | Epistemic uncertainty engine: known .. unknowable, 'not enough evidence to decide' | CALIBRATION | `epistemic.metric.decidable_share` (up) | - | - |  |
| S38 | Cross-engine replication: independent rebuild from the written spec | FALSIFICATION | `report:REPLICATION.json.counts.REPLICATED` (up) | - | - | a MISMATCH blocking promotion (admission) |
| S39 | Architecture-level counterfactual failure search: protocol knob ablations | OPERATIONAL_RISK | `formal.metric.knobs_evidenced` (up) | - | - |  |
| S40 | Compute OS: researcher prices published for cycle pricing | INFO_PER_COMPUTE | `market.metric.independently_discovered` (up) | - | - |  |
| S41 | Global state replay: ledgers re-derived from streams | OPERATIONAL_RISK | `replay.metric.reconstructible_share` (up) | - | - |  |
| S42 | Continual recovery experiments: chaos campaigns and corruption drills on copies | OPERATIONAL_RISK | `chaos.metric.drills_failing` (down) | - | - |  |
| S43 | Mechanisms from other sciences | ALPHA_DISCOVERY | `world_science.metric.hypotheses` (up) | - | - |  |
| S44 | Abstraction discovery: library learning over winning genomes | PRODUCTIVITY | `grammar.metric.n_primitives` (up) | - | - |  |
| S45 | Scientific memory compression: failure theorems with provenance | PRODUCTIVITY | `failure_memory.metric.rows_per_statement` (up) | - | - |  |
| S46 | Human-machine separation of powers: amendments ratified by the principal only | OPERATIONAL_RISK | `truth_kernel.metric.constitution_violation` (down) | - | - |  |

## What each layer is built from

- **S01** Truth kernel: content-addressed journal, constitution, evidence seal: `libs/tiers/truth_kernel.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/TRUTH_KERNEL.json`
- **S02** World data OS: bitemporal store and point-in-time audit: `libs/tiers/bitemporal.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/DATA_OS.json`
- **S03** World model: causal edges classified stable/decaying/false; broken edges become hypotheses: `libs/tiers/world_edges.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/WORLD_SCIENCE.json`
- **S04** Researcher civilization: heterogeneous cohorts priced by independent discoveries: `libs/tiers/researcher_market.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/MARKET.json`
- **S05** AlphaEvolve for alpha: genome evolution with operator yield: `libs/tiers/evolution.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/GENOMES.json`
- **S06** MAP-Elites quality-diversity archive: `libs/tiers/evolution.py`, `desks/mt5/research/research_diversity_archive.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/QD.json`
- **S07** Evolving researcher genomes (fitness = validated independent info per compute): `libs/tiers/evolution.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/GENOMES.json`
- **S08** Researcher market: Thompson sampling + MILP compute allocation, floors never cut: `libs/tiers/researcher_market.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/MARKET.json`
- **S09** Red Queen: attackers and validator defenders co-evolve: `libs/tiers/red_queen.py`, `desks/mt5/research/adversary_evolution.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/RED_QUEEN.json`
- **S10** Planted traps: immune score with FREEZE verdict: `libs/tiers/traps.py`, `libs/tiers/meta_benchmark.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/IMMUNE.json`
- **S11** Online FDR: LORD++ and e-LOND over the lifetime trial stream: `libs/tiers/online_fdr.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/ONLINE_FDR.json`
- **S12** Epistemic firewall: per-role static audit with ratchet: `libs/tiers/firewall.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/FIREWALL.json`
- **S13** Negative-knowledge graph: typed failure causes and failure theorems: `libs/tiers/failure_memory.py`, `desks/mt5/research/negative_knowledge.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/FAILURE_MEMORY.json`
- **S14** Ancestry graph: novelty against ancestors and exact repeats: `libs/tiers/topology.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/TOPOLOGY.json`
- **S15** Effective independent alpha rank (linear, rank, tail, drawdown, ancestry): `libs/tiers/topology.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/TOPOLOGY.json`
- **S16** Counterfactual world lab: edges tested for stability across states: `libs/tiers/world_edges.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/WORLD_SCIENCE.json`
- **S17** Alpha theory compiler: seven-slot mechanisms: `libs/tiers/theory.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/THEORY.json`
- **S18** Theory-evidence graph: Beta posteriors weighted live 3 / forward 2 / backtest 1: `libs/tiers/theory.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/THEORY.json`
- **S19** Non-LLM intelligence: information, spectral, Kalman, queueing, ecology, network, MCMC labs: `libs/tiers/cross_science.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/WORLD_SCIENCE.json`
- **S20** Peer review panels: typed challenges with resolvers: `libs/tiers/review_panel.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/REVIEW.json`
- **S21** Auto-invented tests: proposed on one suite, confirmed on another: `libs/tiers/test_invention.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/TEST_INVENTION.json`
- **S22** Evolving research grammars: primitives learned from winners, dead operators retired: `libs/tiers/evolution.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/GRAMMAR.json`
- **S23** Execution science: signal alpha separated from execution drag: `desks/mt5/research/execution_science.py`; clock `hourly_cycle:execution_science`; artifact `desks/mt5/reports/EXECUTION_SCIENCE.json`
- **S24** No-trade as a first-class action in the exchange: `libs/tiers/opportunity_exchange.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/EXCHANGE.json`
- **S25** Opportunity exchange: bids cleared by robust E[log W] (shadow): `libs/tiers/opportunity_exchange.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/EXCHANGE.json`
- **S26** Live prediction accounting: CRPS, PIT, coverage, honesty shrinkage: `libs/tiers/prediction_accounting.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/PREDICTIONS.json`
- **S27** Live reality outranks backtests: overconfidence measured on live outcomes: `libs/tiers/prediction_accounting.py`, `libs/tiers/theory.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/PREDICTIONS.json`
- **S28** Digital twin: registered-after-only paired evaluation, one-op rollback: `libs/tiers/twin.py`, `libs/tiers/rollback.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/TWIN.json`
- **S29** Self-model: deficiency ranking and sealed scorecard regression: `libs/tiers/self_model.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/SELF_MODEL.json`
- **S30** Architecture evolution: challengers adopted on sealed evidence: `libs/tiers/twin.py`, `libs/tiers/self_model.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/TWIN.json`
- **S31** Formal verification of the money path: BFS model check of the order protocol: `libs/tiers/formal.py`, `desks/mt5/research/formal_invariants.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/FORMAL.json`
- **S32** Independent evaluator civilization: evaluators challenged by the panel: `libs/tiers/review_panel.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/REVIEW.json`
- **S33** Architecture evolution above strategy evolution: validator genomes compete: `libs/tiers/red_queen.py`, `libs/tiers/twin.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/RED_QUEEN.json`
- **S34** Immutable meta-benchmark suite: sealed hash of generator, seeds and prices: `libs/tiers/meta_benchmark.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/IMMUNE.json`
- **S35** Active information acquisition: acquisition predictions calibrated on arrival: `libs/tiers/bitemporal.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/DATA_OS.json`
- **S36** Research-search frontier estimator: Chao1, Good-Turing, yield exponent: `libs/tiers/frontier.py`, `desks/mt5/research/frontier_map.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/FRONTIER.json`
- **S37** Epistemic uncertainty engine: known .. unknowable, 'not enough evidence to decide': `libs/tiers/epistemic.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/EPISTEMIC.json`
- **S38** Cross-engine replication: independent rebuild from the written spec: `desks/mt5/research/replication_civilization.py`; clock `hourly_cycle:replication_civilization`; artifact `desks/mt5/reports/REPLICATION.json`
- **S39** Architecture-level counterfactual failure search: protocol knob ablations: `libs/tiers/formal.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/FORMAL.json`
- **S40** Compute OS: researcher prices published for cycle pricing: `libs/tiers/researcher_market.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/MARKET.json`
- **S41** Global state replay: ledgers re-derived from streams: `libs/tiers/replay.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/REPLAY.json`
- **S42** Continual recovery experiments: chaos campaigns and corruption drills on copies: `libs/tiers/chaos.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/CHAOS.json`
- **S43** Mechanisms from other sciences: `libs/tiers/cross_science.py`, `desks/mt5/research/market_ecology.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/WORLD_SCIENCE.json`
- **S44** Abstraction discovery: library learning over winning genomes: `libs/tiers/evolution.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/GRAMMAR.json`
- **S45** Scientific memory compression: failure theorems with provenance: `libs/tiers/failure_memory.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/FAILURE_MEMORY.json`
- **S46** Human-machine separation of powers: amendments ratified by the principal only: `libs/tiers/truth_kernel.py`, `libs/tiers/firewall.py`, `desks/mt5/research/tier_s.py`; clock `hourly_cycle:tier_s`; artifact `desks/mt5/reports/tier_s/TRUTH_KERNEL.json`
