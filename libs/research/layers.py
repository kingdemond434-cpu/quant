"""THE SEVEN LAYERS, DECLARED: which organ does information, prediction, timing, sizing,
portfolio, execution or exit -- and what each layer costs.

MEASURED 2026-09-08 (Tier-1 programme item G14): six of the seven layers have a dedicated,
scheduled engine, so the separation exists de facto -- but nowhere is it declared. A new leg
lands in `hourly_cycle.py` under whatever name its author chose and joins no layer, so nobody
can ask "how many trials did the TIMING layer run this week, and what did they cost?", and the
one layer with no engine at all (EXIT: the exit study runs, nothing sizes or times an exit from
it) is invisible precisely because the taxonomy it is missing from does not exist.

THE REGISTRY IS THE DECLARATION, and the test enforces it: every `_costed("name", ...)` leg in
the hourly and daily cycles must appear here. A leg nobody assigned a layer to fails the suite
-- the taxonomy stays complete by construction rather than by memory.

`census` joins the registry onto the compute ledger (libs/ops/compute_ledger.cost_by_run), so
per-layer hours, runs and failure rates are the ledger's numbers grouped, never re-measured.
The EXIT layer's census reads zero hours against one leg; that zero is the finding.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "layer_census.json"

LAYERS = ("information", "prediction", "timing", "sizing", "portfolio", "execution", "exit",
          "meta")

#: leg name -> layer. `meta` is the machine that runs the machine: health, publishing, the
#: compute ledger itself. It is a layer of the desk, not of a strategy, and is listed so its
#: cost is visible next to the seven it serves.
LEG_LAYER: dict[str, str] = {
    # information: what the desk knows before it predicts anything
    "mine": "information", "moat_miner": "information", "world_crawler": "information",
    # The moat exchange prices candidates the desk already holds -- novelty against the
    # canon and the graveyard, independence against the book. That is information about the
    # desk's own stock of hypotheses, not a new prediction (Tier-1 M6/M4).
    "moat_candidate_compiler": "information",
    # The program database evolves the desk's own SEARCH ALGORITHMS and scores each
    # class against its own organ. That is the meta layer: it changes how the desk looks,
    # not what it predicts (Tier-1 Q3).
    "algorithm_db": "meta",
    # The proposer seat and the kimi hunter both buy the desk a PRIOR it did not have -- which
    # skeleton, which mechanism name, which territory -- before any claim about returns is made.
    # That is information, not prediction: neither one scores anything.
    "proposer_seat": "information", "kimi_hunt": "information",
    "deep_forest": "information", "market_intel": "information", "record_tape": "information",
    "archive_tape": "information", "refresh_bars": "information",
    "timeframe_coverage": "information", "frontier": "information",
    "frontier_ontology": "information", "frontier_unknowns": "information",
    "frontier_implementer": "information", "frontier_report": "information",
    "state_vector": "information", "causal_graph": "information",
    "input_identity": "information",
    # FIFTEEN LEGS LANDED WITHOUT A LAYER AND THIS TEST HAD BEEN RED FOR IT (2026-09-10). Nine
    # of them were added on 2026-09-10 itself and mapped nowhere: exactly the failure the
    # registry exists to prevent, committed by the session that wrote the registry's own fence.
    # A leg with no layer is an hour of compute that `opportunity_cost` cannot attribute, so
    # "what did the desk NOT test this hour" silently omits it.
    "futures_lead_lag": "information", "tape_features": "information",
    # prediction: turning information into a claim about returns
    "compile_candidates": "prediction", "merge_docket": "prediction", "search": "prediction",
    "sweep": "prediction", "hunt12": "prediction",
    "backtest": "prediction", "external_gauntlet": "prediction",
    "deepen": "prediction", "experiment_design": "prediction",
    "experiment_cache": "prediction", "ml_layer": "prediction", "model_league": "prediction",
    "model_skill": "prediction", "forecast_contract": "prediction",
    "graveyard_model": "prediction", "counterfactual_world": "prediction",
    "edge_confidence": "prediction", "adversaries": "prediction",
    "recertify_canon": "prediction", "publish_survivors": "prediction",
    "miner_conversion": "prediction", "opportunity_gap": "prediction",
    "research_org": "prediction", "queue_compact": "prediction",
    "requeue_unrunnable": "prediction", "falsifier_run": "prediction",
    "opportunity_forecast": "prediction", "edge_reliability": "prediction",
    "edges_macro_fusion_sweep": "prediction", "alpha_breadth": "prediction",
    "alpha_periodic_table": "prediction", "regime_coverage": "prediction",
    "arena": "meta", "prosecutor": "meta", "scaling_laws": "meta", "dead_architecture": "meta",
    "producer_census": "meta",
    # timing: when a claim becomes a trade
    "enrol_clocks": "timing", "heal_clocks": "timing", "promoter": "timing",
    "rebalance_trigger": "timing", "entry_timing": "timing",
    # WHICH HOURS the desk has an edge in is a TIMING question, not a sizing one -- this leg
    # measures and allocates nothing, and stacking it on pf_allocator would shrink twice.
    "session_allocation": "timing",
    # Generating a mechanism's other-session and other-chart equivalents is asking WHEN it works,
    # which is a timing question even though the output is a research candidate.
    "session_chart_expansion": "timing",
    # Whether an artifact's own stamp advances is a MEASUREMENT property of the desk, not a
    # property of any strategy -- it belongs with the other self-measurement legs.
    "stamp_freshness": "information",
    # Why an order filled or did not is an EXECUTION measurement, and it is the binding stage.
    "fill_attribution": "execution",
    # What a sleeve pays to trade belongs with execution too: it is a cost, not a signal.
    "cost_to_edge": "execution",
    "swap_rejudge": "execution",
    "asia_plane": "information",
    "sge_premium": "information",
    "asia_collector": "information",
    "asia_parser": "information",
    "index_discovery": "information",
    "empty_cluster_forcer": "prediction",
    "asia_transmission": "information",
    # Whether a data endpoint still serves what it claims is an INFORMATION property -- it decides
    # whether any input exists at all, before any signal is derived from it.
    "source_routes": "information",
    # Per-sleeve return paths are what a PORTFOLIO view is computed from -- n_eff, covariance,
    # joint drawdown. Not a signal and not an execution fact.
    "strategy_paths": "portfolio",
    # THE FOUR ACTIVATION LEGS (2026-09-14). All four organs existed and NOTHING ran them, which
    # is III.16 exactly: built is not a status. `weak_signals` and `residual_factors` mint claims
    # about returns, so they are prediction. `markout` asks what the desk's own fills cost it
    # after the fact -- execution. `exogenous_search` is undirected hunting for inputs nobody has
    # a story for, which is information, and is only affordable because the trial count is sealed.
    "weak_signals": "prediction",
    "residual_factors": "prediction",
    "markout": "execution",
    # THE MARKET DIGITAL TWIN (2026-09-22) is billed to execution: it is calibrated to spreads,
    # depth, cancellations and impact on the desk's own tape, and what it adds to a claim about
    # returns is the counterfactual execution cost of the rule under the posterior worlds. The
    # robustness number it writes routes research; it sizes nothing and predicts no return.
    "digital_twin": "execution",
    "exogenous_search": "information",
    # `stop_reverse` asks what the desk's own orders did to it at the venue -- execution.
    "stop_reverse": "execution",
    # `forward_reconcile` keeps the forward lane's roster true -- which clock may accrue
    # evidence and which is an orphan. That is portfolio bookkeeping, not prediction.
    "forward_reconcile": "portfolio",
    # AND FIVE LEGS WERE STILL UNMAPPED WHEN THOSE FOUR LANDED (2026-09-14). The registry's own
    # comment records fifteen of these in 2026-09-10 and the same drift had recurred, so the test
    # this file exists to satisfy was red before this session touched it. Mapped by what each
    # actually does rather than by its name: `refresh_regime` (costed as `regime_monitor`)
    # conditions on a latent state, which is prediction; `orthogonality` measures tail dependence
    # BETWEEN sleeves, which only the portfolio layer can act on; `lake_promote` asks what share
    # of stored intelligence survives a point-in-time question, which is information about the
    # desk's own inputs; `research_exchange_score` scores which external source converts, likewise;
    # `alpha_rl` searches sequentially against the allocator's marginals, which is prediction.
    "alpha_rl": "prediction",
    "regime_monitor": "prediction",
    "orthogonality": "portfolio",
    "lake_promote": "information",
    "research_exchange_score": "information",
    # The FRED archive and the macro view it feeds are inputs about the world, refreshed hourly
    # when older than six hours: information, and the state the allocator conditions on.
    "fred_macro": "information",
    # Route repair for dead sources and bars-file integrity are both about whether the desk's
    # inputs can be read at all: information.
    "source_fixer": "information",
    # THE FEATURE COMPILER and THE DATA-ACQUISITION SCIENTIST (LAWS 5m): typing what the desk
    # holds, and deciding which dataset to hold next, are both about what the desk knows before
    # it predicts anything: information.
    "feature_compiler": "information",
    "data_acquisition_scientist": "information",
    "universe_integrity": "information",
    # Formulaic alpha generation is a predictor search; the closed-loop attestation is meta.
    "alpha_evolution": "prediction",
    "closed_loop": "meta",
    # The breadth sweep mints cells for every unbanned family on every chart the desk holds bars
    # for -- a predictor search, scheduled hourly since the discovery hunt was banned (2026-09-16).
    "breadth_sweep": "prediction",
    # Whether the allocator's book reaches the sleeves it funds is a measurement of the desk's
    # own wiring, like `wiring_audit`: meta.
    "allocator_join": "meta",
    # Whether every docket candidate is still accounted for is a measurement of the desk's own
    # bookkeeping: meta.
    "candidate_conservation": "meta",
    # Planted point-in-time canaries measure whether the desk can read the future: meta.
    "pit_canaries": "meta",
    # THE TIER-1 CLOSED-LOOP B ROWS (2026-09-23).
    # Whether the running code may create new exposure, which scientist earned what, which
    # structures have started surviving again, and one EVIG price over every research resource
    # are all the machine measuring and scheduling itself: meta.
    "release_authority": "meta", "scientist_standings": "meta", "failure_prior": "meta",
    "evig_acquisition": "meta",
    # The per-asset regime hierarchy and the learned representation lane say what the market IS
    # before anything predicts it -- the information layer, like the crawlers and the miners.
    "regime_hierarchy": "information", "representation_discovery": "information",
    # The residual map turns the desk's own errors into search targets, and the research tree
    # and the CEO docket decide which question is asked next: information.
    "residual_map": "information", "research_tree": "information", "frontier_ceo": "information",
    # Certification fate joined back to the generators that proposed each cell reweights the
    # predictor search itself: prediction.
    "mutation_yield": "prediction",
    # Realised R credited back to the scientist and lane that proposed each cell: the delayed
    # truth that reweights the predictor search (bandit worth, generator weights): prediction.
    "credit_assignment": "prediction",
    # THE 2026-09-16 BLUEPRINT ORGANS (Tier-1 phases C/D).
    "axis_registry": "information", "forced_flow_calendar": "information",
    "standing_questions": "information",
    "novelty_gate": "prediction",
    "posterior_alpha": "sizing", "exposure_decomposition": "portfolio",
    "hazard_engine": "exit",
    "breadth_ladder": "meta", "tier1_scorecard": "meta", "wiring_ceo": "meta",
    # The queue census measures the machine's own backlog, not any strategy's: meta by
    # construction (principal 2026-09-23, "nothing should be queued").
    "queue_census": "meta",
    "probation": "meta", "live_system_state": "meta", "semantic_memory": "meta",
    "model_role_benchmark": "meta", "research_departments": "meta",
    "qd_frontier": "information", "blind_reviewer": "meta",
    "evaluator_lab": "meta", "value_of_data": "information", "research_api_status": "meta",
    "artifact_chain": "meta", "residual_queue": "information", "unseen_frontier": "information",
    "attribution_reconcile": "meta",
    "macro_state_engine": "information",
    "research_artifacts": "meta",
    "engine_registry": "meta",
    "counterfactual_attribution": "meta",
    "trend_core": "prediction",
    "event_surprise": "information",
    "counterexample_agent": "meta",
    "search_paradigm_census": "meta",
    "source_registry": "information", "synthetic_regimes": "meta",
    "event_response_atlas": "information", "causal_lab": "information", "world_lab": "prediction",
    # THE MARKET CONSTITUTION: which rule the price was formed under, as a PIT column, and
    # whether a rule change moved anything -- what the desk knows before it predicts.
    "market_constitution": "information",
    # THE 2026-09-17 WORLD-MODEL TRIAD. `world_model` turns every PIT series into a conditional
    # distribution over forward returns -- prediction, and the only one of the three that makes a
    # claim about returns at all. `residual_hunt` asks what dataset, participant, region,
    # representation, mechanism or interaction the model is MISSING, which is a question about
    # what the desk knows before it predicts: information. `representation_forge` mints the
    # features themselves from ingested series -- also information, and for the same reason
    # `unused_information` is: it decides what inputs exist, not what they imply.
    "world_model": "prediction", "residual_hunt": "information",
    # C9. `residual_gate` measures what a candidate adds to the book the desk ALREADY holds, and
    # that is a statement about the portfolio, not about the market: it is the same layer as the
    # allocator's own evidence work, one rung above a prediction.
    "residual_gate": "portfolio",
    "representation_forge": "information",
    # THE MATHEMATICS CIVILIZATION (2026-09-17): every object it invents is a claim about the
    # residual -- E[eps | f(x)] -- which is a claim about returns, so the hour is billed to
    # prediction like `world_model` and `discovery_compiler`. The representations it mints are a
    # by-product of that claim, not a separate information hour.
    "math_lab": "prediction",
    # THE EXPRESSION FACTORY (2026-09-22): every cell it screens is a claim about returns from
    # a formula on the desk's own bars -- prediction, beside math_lab whose department it shares.
    "expression_factory": "prediction",
    # THE PHYSICS LAB (2026-09-22): the institution around the mathematics + physics scientists --
    # every card it judges is a claim about the residual, so the hour is prediction like math_lab.
    "physics_lab": "prediction",
    # THE CLOSED CO-EVOLUTION and THE MODEL-FAMILY CIVILIZATION (2026-09-22, Tier-1 items 2, 3,
    # 6, 7, 10, 13, 14, 15, 17, 18). Both spend their hour asking what predicts the forward sign
    # -- one by breeding factors against models on islands and re-interrogating the residual, the
    # other by sweeping ten model families across six representations of the same bars. The
    # output of each is a conditioning model, never a size or a fill, so the layer is prediction.
    "coevolution": "prediction", "model_search": "prediction",
    "news_event_stream": "information", "event_sleeves": "prediction",
    "registry_sync": "meta", "axis_proposer": "information", "program_alpha_lane": "prediction",
    "trajectory_evolution": "prediction", "research_os_archive": "meta", "regime_router": "sizing",
    "moat_series": "information", "scout_roster": "information",
    "descendants": "prediction", "forward_slot_ranker": "portfolio",
    # META, both of them, and deliberately: neither buys the desk a prediction. One sizes the
    # JUDGE (how many cells reach a verdict an hour, from measured cores/memory/commit) and the
    # other guarantees every certificate gets a forward clock the moment it is minted. They are
    # the machine that runs the machine -- throughput and evidence plumbing, not edge.
    "judging_throughput": "meta", "forward_enrolment": "meta",
    "analyst_pipeline": "information", "knowledge_graph": "information",
    "card_explosion": "prediction", "alpha_lineage": "prediction",
    "graveyard_resurrection": "prediction", "shadow_discovery": "information",
    "forward_exploitation": "information", "alpha_recombination": "prediction",
    "unused_information": "information", "discovery_compiler": "prediction",
    # The conversion maximiser turns registry rows that are NOT yet claims about returns into
    # claims about returns -- it binds the family, the instrument, the falsifier and the data
    # snapshot. That is the prediction layer's own work, done on the backlog instead of on
    # arrivals, so it sits beside the compiler that does it on arrivals.
    "conversion_maximiser": "prediction",
    # WHICH SOURCES THE DESK MAY LAWFULLY CONSUME is a property of its INPUTS, decided before any
    # signal is derived from them -- the same reading that puts `source_routes` and `data_scout`
    # in information. The ROI reallocator is the machine spending on itself: meta.
    "evidence_router": "information", "research_roi": "meta",
    "research_debt": "meta", "mining_objective": "meta", "research_gap_map": "meta",
    # THE IMPLEMENTER. Meta, not governance: it spends the hour deciding what the desk's own
    # recommendations become, which is the machine acting on the machine. An hour here buys no
    # new hypothesis and is not meant to -- it buys the removal of open rows that name no owner.
    "implementer": "meta",
    # WHAT THE DESK KNOWS AND COULD KNOW ABOUT THE WORLD, per country x sector x information type
    # x mechanism x representation x asset x session x regime x horizon x execution, plus the deep
    # forest's own tensor. It decides WHICH INPUTS EXIST before any signal is derived from them --
    # the same question `source_routes`, `value_of_data` and `unseen_frontier` are information for
    # -- even though the frontier rows it writes become research work downstream. LAWS 5f.
    "coverage_tensor": "information",
    # THE COVERAGE DRAIN. The tensor above says which inputs EXIST; this leg spends its hour
    # turning ground the desk already owns and has never read into ground it has actually
    # fetched -- registering every root the country packs declare, resolving the rows that were
    # minted with no url, crawling them through the existing collectors, and verifying each
    # pack's ten source layers against a registry row that carries a real stamp. Every minute of
    # it buys INPUT and none of it buys a claim about returns, so it is information by the same
    # reading that puts `world_crawler` and `deep_forest` there.
    "coverage_drain": "information",
    # Which families the scarce judge actually spends itself on, measured per family as unjudged
    # backlog. It buys INFORMATION about the mined population, not a signal or a position.
    "judge_coverage": "information",
    "gauntlet_backpressure": "meta", "miner_specialisation": "meta",
    # THE TIER-5 RESIDUALS (mandate 90, 110, 131/132, 133, 134, 136, 97/98, 162). The bounty
    # board and the drawdown-alpha miner are PORTFOLIO: both ask what the BOOK lacks -- a payoff
    # shape, a regime, something that pays while the book bleeds -- which is a question about the
    # combination and not about any one cell's forecast. The autopsy splits a CLOSED deal into
    # signal, cost and slippage against the price the decision intended, which is execution. The
    # auction, the bottleneck law, the latency clock, the replenishment target and the dashboard
    # are the machine measuring and re-funding the machine: meta.
    "portfolio_bounty": "portfolio", "drawdown_alpha_miner": "portfolio",
    "trade_autopsy": "execution",
    "research_auction": "meta", "bottleneck_law": "meta", "research_latency": "meta",
    "alpha_replenishment": "meta", "research_dashboard": "meta",
    "moat_collectors": "information", "source_frontier": "information",
    "scout_swarm": "information", "actor_atlas": "information",
    # INFORMATION, not meta: the understanding seat turns bytes the desk collected but could not
    # READ into claims it can. An hour spent there buys information the desk already paid to
    # fetch and had been throwing away by reading it with the wrong language's rules.
    "understanding_seat": "information",
    "netting_report": "execution", "execution_alpha": "execution",
    "paradigm_router": "meta", "meta_controller": "meta", "lead_replication": "information",
    # THE META-EVOLUTION LAYER, THE COMPUTE-ECONOMICS SCIENTIST AND THE MISSED-TRADE
    # ARCHAEOLOGIST (LAWS 5m, 2026-09-22). The first two are the machine measuring and
    # rewriting the machine: meta. The archaeologist asks which INPUT was absent at a
    # decision -- what the desk knew before it predicted -- which is information, exactly as
    # `residual_hunt` is.
    "research_evolution": "meta", "compute_economics": "meta",
    "missed_trade_archaeologist": "information",
    # THE ANYTIME-VALID SCIENCE CONTROLLER (LAWS 5k/5m): online-FDR wealth per lineage, the
    # effective-trial census and the genome archive. It predicts, sizes and times nothing; it
    # measures whether the machine's evidence is still evidence after an unbounded stream of
    # launches, and refuses the launches that would make it not so: meta.
    "science_controller": "meta",
    # THE CROSS-MARKET EVENT GRAPH (LAWS 5m). It assembles what the desk knows about how events
    # reach assets and adjudicates each mechanism's evidence; it predicts nothing itself, so like
    # `knowledge_graph` and `causal_graph` it is information. THE REPLICATION CIVILIZATION judges
    # the desk's own implementations against a written spec, never the market: it is the
    # machine measuring the machine, beside `evaluator_lab` and `blind_reviewer` -- meta, which
    # is this vocabulary's word for the validation layer.
    "event_graph_lab": "information", "replication_civilization": "meta",
    "data_scout": "information", "japan_department": "information",
    "global_research_os": "information", "macro_department": "information",
    # THE FOREST FEDERATION (2026-09-17). Seventeen research civilizations, each running eleven
    # agent roles in parallel on its own resident. They are INFORMATION legs for the same reason
    # `japan_department` is: what a forest produces is a registry of sources, claims, mechanisms
    # and PIT-safe series -- what the desk KNOWS before it predicts anything. The candidate
    # compiler inside each one donates through `proposer_common`, whose own legs are already
    # billed to prediction, so counting a forest as prediction would bill the same trial twice.
    "forest_korea": "information", "forest_china": "information",
    "forest_russia_cis": "information", "forest_south_asia": "information",
    "forest_asean": "information", "forest_oceania": "information",
    "forest_europe": "information", "forest_north_america": "information",
    "forest_latam": "information", "forest_mena": "information",
    "forest_africa": "information",
    "forest_global_web": "information", "forest_global_academic_code": "information",
    "forest_global_physical_data": "information", "forest_global_market_data": "information",
    "external_federation": "information", "federation_ops": "information",
    # THE SANDBOX RUNNER executes federated engines and rebuilt cells over the desk's bars and
    # donates hypotheses and representations: what the desk can know, so information.
    "sandbox_runner": "information",
    # THE SUPPLY LINE provisions those engines' libraries and the ROSTER names every one of them
    # with what it produced: both are about what the desk CAN know next, so information too.
    "sandbox_provision": "information", "sandbox_roster": "information",
    "source_civilizations": "information", "evidence_watchtower": "information",
    "prediction_markets": "information",
    "archaeology": "information",
    "sares": "information",
    # ONE CERTIFICATE TRUTH: the audit of every certificate/clock store against the one lane is a
    # fence over the machine's own bookkeeping -- meta, like every other fence.
    "certificate_truth": "meta",
    # THE RUNTIME ATTESTATION publishes what ran on this host, hashed -- a fence over the desk's
    # own bookkeeping and its only evidence outside the box, so meta like every other fence.
    "runtime_attestation": "meta",
    # the self-repair registry judges the desk's own defect classes, not the market: meta.
    "self_repair": "meta",
    # THE TWO STANDING BATTERIES rotate rosters that span every layer -- fences over the
    # machine's own bookkeeping, standing fixers, region organs. Billing the rotation to one
    # strategy layer would misattribute every other one, so the wiring mechanism is meta and the
    # organs it runs are billed where their own artifacts land.
    "fence_battery": "meta", "organ_battery": "meta",
    # THE LOOP LIVENESS PROVER measures whether the research loop's ten arrows are advancing --
    # the machine watching the machine, which is meta by the definition at the top of this file.
    # It predicts nothing, times nothing and sizes nothing; it names the stalled arrow's organ.
    "loop_liveness": "meta",
    # CLOCK LIVENESS is the same kind of organ one arrow further in: it measures whether each
    # FORWARD CLOCK is advancing against its venue's own bars and repairs the ones that are not.
    # It predicts nothing and sizes nothing -- it keeps the evidence plumbing honest, which is
    # meta by the definition at the top of this file.
    "clock_liveness": "meta",
    # THE EXPERIMENT SPINE is the machine's account of its own research: one canonical experiment
    # object, the memory graph over it, credit back along ancestry, the priors the next allocation
    # draws from, and the funnel that divides survivors by what they cost. It proposes nothing and
    # sizes nothing -- meta, like every other organ that runs the machine rather than a strategy.
    "experiment_spine": "meta",
    "shadow_institutional": "information",
    "latent_actors": "information",
    "latency_lab": "execution",
    # THE FEED/CLOCK OBSERVATORY and THE IMPACT LAB (LAWS 5m): what the desk's picture of the
    # market is worth at the instant it decides, and what its own orders do to the price. Both
    # are about how an order reaches the venue and what it meets there -- execution.
    "feed_clock_lab": "execution", "impact_lab": "execution",
    # THE NET-EDGE SPINE (principal 2026-09-23): gross minus spread/slippage, impact, financing,
    # commission and the multiplicity charge already owed -- the cost of reaching the venue and
    # of having searched for the cell at all, charged at the cell's own size and state. It ranks
    # and it attributes; it places nothing, so execution is its layer and not sizing.
    "net_edge": "execution",
    # COST TRUTH (principal 2026-09-23): what the model charges against what the broker quotes
    # and what the account paid. It measures the price of reaching the venue -- spread, session
    # structure, commission, swap, slippage -- so its layer is the same as the spine it audits.
    "cost_truth": "execution",
    # THE INGESTION-EXPLOITATION CONTRACT (LAWS 5c, 2026-09-17). The ledger inventories the
    # desk's information estate and gives every ingested datum a downstream state: information.
    # The fusion turns that estate into regime posteriors and nowcasts: prediction. The gate
    # that ratchets both is meta, like every other fence.
    "ingestion_ledger": "information", "macro_intelligence": "prediction",
    # THE DISLOCATION LAB (RESEARCH 11) turns six engines' claims into a calibrated ensemble
    # against the instrument's own market-implied state: a claim about returns, prediction.
    "dislocation_lab": "prediction",
    "ingestion_exploitation": "meta",
    # sizing: how much
    "capacity": "sizing", "ensemble_optimizer": "sizing",
    # portfolio: how the book is composed
    "pf_allocator": "portfolio",
    "allocator_liveness": "portfolio",
    "allocator_trigger": "portfolio",
    # The balance-sheet layer and the Allocator-V2 evidence: what the book costs to carry and
    # what each sleeve is worth to it -- a question about the book's composition, not about
    # how an order reaches the venue.
    "financing_lab": "portfolio",
    # execution: how the order reaches the venue
    "execution_resolver": "execution", "execution_twin": "execution",
    # What the venue charges and where that number came from is execution arithmetic, not
    # research: these three decide what every backtest is billed at the fill.
    "fusion_cost": "execution", "cost_construction": "execution",
    "spread_provenance": "execution", "microstructure_census": "execution",
    # exit: how a position ends
    "exit_study": "exit",
    # meta
    "health": "meta", "issue_board": "meta", "publish_dashboard": "meta",
    "publish_state": "meta", "release_identity": "meta", "smoke_release": "meta",
    "burn_in": "meta", "maintain_miners": "meta", "reclaim_disk": "meta", "daily": "meta",
    "layer_census": "meta", "opportunity_cost": "meta", "acceptance": "meta",
    # CYCLE PRICING is meta for the same reason the control plane is: it decides how much of the
    # hour each of the other layers gets, and predicts, sizes and times nothing itself.
    "cycle_pricing": "meta",
    # CAUSAL INVARIANCE asks whether a cell's effect is the same number in a different session,
    # year or volatility regime. That is a property of the PREDICTION -- whether the claim about
    # returns holds outside the environment it was fitted in -- so it is billed there.
    "causal_invariance": "prediction",
    # THE CLOSED-LOOP ORGANS (Tier-1 B14-B25, 2026-09-23), each billed where its work lands.
    # Acquisition and the actor populations describe the world, so they are information; the
    # destroyer pool and the multi-chart counterfactual are claims about returns, so they are
    # prediction; the shortfall refit is how an order reaches the venue; the bench, the evidence
    # chain, the immutable clock ledger and the meta-tournament are the machine measuring itself.
    "source_evig": "information", "source_drain": "information",
    "actor_pressure": "information",
    "destroyer_pool": "prediction", "counterfactual_timeframes": "prediction",
    "shortfall_model": "execution",
    "quantbench": "meta", "evidence_chain": "meta", "clock_ledger": "meta",
    "meta_rnd": "meta",
    "wiring_audit": "meta", "queue_cycle": "meta", "time_joins": "meta", "brain_ab": "meta",
    # THE CONTROL PLANE is meta by construction: it measures whether the machine that runs the
    # machine is doing what desired state says, and it predicts, sizes and times nothing.
    "control_plane": "meta",
    # THE PLUMBING WATCHDOG and THE BOTTLENECK ATTACKER are meta for the same reason: neither
    # predicts a price, sizes a bet or times an entry. One proves the pipes between the organs
    # are open (the adoption clock, the git-writer lock, commit headroom, producer/consumer path
    # agreement, fences that actually ran); the other names which of the desk's four standing
    # bottlenecks is binding this hour and moves compute toward it. They are the machine looking
    # at the machine, which is what `meta` means here.
    "plumbing_watchdog": "meta", "bottleneck_attack": "meta",
    "session_capital": "portfolio",
}

_LEG_RE = re.compile(r'_costed\("([^"]+)"')


def scheduled_legs(root: Path = ROOT) -> set[str]:
    """Every costed leg the two cycles declare, read from the source."""
    legs: set[str] = set()
    for name in ("hourly_cycle.py", "daily_cycle.py"):
        src = root / "desks" / "mt5" / "research" / name
        if src.exists():
            legs |= set(_LEG_RE.findall(src.read_text("utf-8")))
    return legs


def unassigned(root: Path = ROOT) -> list[str]:
    """Legs that run but belong to no layer. The test pins this to []."""
    return sorted(scheduled_legs(root) - set(LEG_LAYER))


def census(cost_by_run: dict[str, dict[str, Any]], root: Path = ROOT) -> dict[str, Any]:
    """Per-layer hours/runs/failures from the compute ledger's per-run aggregate."""
    by_layer: dict[str, dict[str, Any]] = {
        L: {"legs": sorted(k for k, v in LEG_LAYER.items() if v == L),
            "runs": 0, "hours": 0.0, "failures": 0, "costed_legs": []} for L in LAYERS}
    for run, c in cost_by_run.items():
        layer = LEG_LAYER.get(run)
        if layer is None:
            continue
        b = by_layer[layer]
        b["runs"] += int(c.get("runs") or 0)
        b["hours"] += float(c.get("hours") or 0.0)
        b["failures"] += int(c.get("failures") or 0)
        b["costed_legs"].append(run)
    for b in by_layer.values():
        b["hours"] = round(b["hours"], 4)
        b["failure_rate"] = round(b["failures"] / b["runs"], 4) if b["runs"] else None
        b["dark_legs"] = sorted(set(b["legs"]) - set(b["costed_legs"]))
        b["costed_legs"].sort()
    total_h = sum(b["hours"] for b in by_layer.values())
    for b in by_layer.values():
        b["share_of_hours"] = round(b["hours"] / total_h, 4) if total_h else None
    starved = [L for L in LAYERS[:-1] if by_layer[L]["hours"] == 0.0]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "layers": by_layer, "total_hours": round(total_h, 4),
        "unassigned_legs": unassigned(root),
        "starved_layers": starved,
        "why": ("a layer with declared legs and zero costed hours is either never scheduled or "
                "its cost is unrecorded; either way the desk spends nothing on it"),
    }


def main(argv: list[str] | None = None) -> int:
    from libs.ops.compute_ledger import cost_by_run
    doc = census(cost_by_run())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    print(f"layer census: {doc['total_hours']}h over {len(LEG_LAYER)} legs; starved "
          f"{doc['starved_layers'] or 'none'}; unassigned {doc['unassigned_legs'] or 'none'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
