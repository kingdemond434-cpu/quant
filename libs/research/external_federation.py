"""THE OPEN-SOURCE RESEARCH FEDERATION -- every public research system as a sandboxed parallel
worker of this desk, and the roster that is a bootstrap set rather than a whitelist.

THE LAW THIS SERVES (docs/LAWS.md 5h, principal 2026-09-17, permanent). It REPLACED the blanket
"NO THIRD-PARTY TOOLING -- mine it as TEXT" prohibition, and the replacement is the whole point:
a capability whose measured expected research value is positive may NOT rest at TEXT_ONLY. Every
discovered system gets exactly one disposition -- DIRECT (run the upstream engine in an isolated
sandbox), WRAPPED (keep its engine, adapt its I/O to our contracts), REBUILT (reproduce the
mechanism in canonical infrastructure), REJECTED_WITH_EVIDENCE (licence, security, incompatibility
or measured negative ROI, with a reopening condition) or DUPLICATE (collapsed into a lineage,
contributing only its unique parts).

WHAT THIS MODULE IS AND IS NOT. It is the registry, the admission arithmetic, the lineage
collapse, the packet contract and the operational test -- all pure, all typed, no I/O. It is NOT
a fetcher and NOT a runner: `desks/mt5/research/external_federation.py` is the organ that reads
desk state and writes reports, and `libs/research/sandbox.py` holds the execution policy. The
separation matters because the roster below is DATA the desk edits every week, while the rules
above it are law.

THE ROSTER IS A BOOTSTRAP SET. The seeds are the systems in force the day the law landed; the
24/7 scouts must keep discovering more (project -> authors -> other projects -> papers ->
citations -> datasets -> code -> forks -> issues -> contributors -> communities -> new entities)
and `admit()` decides mechanically whether a newly found system earns its own sandbox:
EV(new capability) - EV(duplication) - integration cost > 0, AND at least one materially new axis.
A future Japanese framework nobody has named yet reaches the gauntlet by that arithmetic, not by
a human adding a line here.

LICENCES ARE NEVER ASSERTED FROM MEMORY. Every seed carries `licence="UNVERIFIED"` until a
provisioning run reads the LICENSE file at the pinned commit; DIRECT execution is refused while
it is unverified, which is a refusal with a named remedy rather than a guess about somebody
else's terms.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

#: The one disposition vocabulary (LAWS 5h). UNDISPOSED is the ONLY resting state that is a
#: defect: it means the desk found a system and has not yet decided what to do with it.
DISPOSITIONS: tuple[str, ...] = ("DIRECT", "WRAPPED", "REBUILT", "REJECTED_WITH_EVIDENCE",
                                 "DUPLICATE", "UNDISPOSED")
#: Dispositions that put a worker on a clock; each of these MUST reach `operational()`.
RUNNING_DISPOSITIONS: frozenset[str] = frozenset({"DIRECT", "WRAPPED", "REBUILT"})
#: The lifecycle of a source civilization. CURRENT_PUBLIC_FRONTIER_EXHAUSTED is the terminal
#: reading and it is provisional by construction: a commit tomorrow reopens it. There is no
#: DONE_FOREVER in this vocabulary and there never will be.
STATUSES: tuple[str, ...] = ("DISCOVERED", "MAPPED", "DEEP_MINING", "INTEGRATED", "RUNNING",
                             "DONATING", "CONSUMED", "MEASURED",
                             "CURRENT_PUBLIC_FRONTIER_EXHAUSTED")
#: A new system earns its own sandbox only by bringing at least one of these. Ten forks of one
#: framework bring none of them and collapse into the parent lineage instead (LAWS 5g).
NEW_AXES: tuple[str, ...] = ("data", "representation", "hypothesis_language", "search_algorithm",
                             "mathematical_method", "region_language", "causal_machinery",
                             "execution_method", "adversarial_verifier", "research_workflow",
                             "model_family", "simulation_world", "uncertainty_method",
                             "world_model_component", "research_infrastructure")
#: What a system can contribute. Used for the capability fingerprint and for routing a packet.
CAPABILITY_FAMILIES: tuple[str, ...] = (
    "factor_model_coevolution", "experiment_scheduler", "artifact_search", "mcts",
    "trajectory_evolution", "structural_novelty", "dsl_program_search", "symbolic_regression",
    "evolutionary_search", "rl_policy_search", "causal_discovery", "representation_learning",
    "foundation_model", "financial_nlp", "multi_agent_debate", "independent_verifier",
    "regime_selection", "walk_forward_harness", "execution_engine", "replay_parity",
    "microstructure", "data_source", "data_tooling", "research_reproduction",
    "portfolio_research", "information_acquisition",
    # second wave (principal 2026-09-19): search, science, dependence, dynamics, simulation
    "bayesian_optimization", "multiobjective_search", "probabilistic_programming",
    "conformal_uncertainty", "online_learning", "forecast_zoo", "anomaly_detection",
    "feature_synthesis", "information_theory", "game_theory", "graph_learning", "topology",
    "time_series_mining", "point_process", "dynamical_systems", "copula_dependence",
    "tensor_methods", "reservoir_computing", "signal_scattering", "pattern_mining",
    "extreme_value", "graphical_models", "recurrence_analysis", "rough_paths",
    "simulation_based_inference", "market_simulation", "change_point", "portfolio_optimization",
    "distributed_compute", "program_evolution", "agent_evolution", "prompt_optimization",
    "quality_diversity", "automated_science", "research_reliability", "telemetry_source",
    "institutional_capability",
)
#: A packet may never carry a verdict. The external engine is a researcher, never a validator and
#: never a capital authority (LAWS 5h): its own backtester, Sharpe, leaderboard place, confidence
#: score or "survivor" label has zero promotion authority here.
PACKET_FORBIDDEN: frozenset[str] = frozenset({
    "survivor", "survivors", "promote", "promotion", "trade", "trades", "order", "orders",
    "position_size", "size", "lots", "capital", "allocation", "deploy", "live", "verdict",
    "passed", "certified",
})
#: The per-system ledger the law requires (LAWS 5h). The organ fills these; the checker reads them.
LEDGER_FIELDS: tuple[str, ...] = (
    "system_id", "upstream_repo", "commit_sha", "licence", "discovery_source", "region",
    "languages", "capabilities", "integration_mode", "sandbox_status", "datasets_extracted",
    "data_axes_extracted", "mechanisms_extracted", "representations_extracted",
    "research_methods_extracted", "failure_knowledge_extracted", "descendants_generated",
    "orthogonal_cells_generated", "trials_donated", "gauntlet_results", "forward_survivors",
    "live_delta_elog", "compute_spent", "source_roi", "last_deep_scan", "last_delta_scan",
    "next_scan", "consumer_ack", "status", "disposition", "why",
)
#: The twelve conditions of LAWS 5g. A source is CURRENT_PUBLIC_FRONTIER_EXHAUSTED only with all
#: twelve true, and the reading is re-derived every pass rather than remembered.
EXHAUSTION_CONDITIONS: tuple[str, ...] = (
    "surfaces_mapped", "artefacts_represented", "capabilities_disposed", "datasets_routed",
    "mechanisms_have_descendants", "cross_system_considered", "failures_in_negative_knowledge",
    "candidate_accounting_balances", "candidates_reached_gaunttlet", "process_in_meta_rd",
    "forward_live_credited", "delta_watch_active",
)


@dataclass(frozen=True)
class SandboxPolicy:
    """What a third-party process is allowed to touch (LAWS 5h, the external code sandbox law).

    Every field is a REFUSAL, not a preference. The policy travels with the packet so a reader
    months later can see the boundary the output was produced under.
    """

    secrets: bool = False
    broker_credentials: bool = False
    live_order_authority: bool = False
    canonical_write_authority: bool = False
    production_merge_authority: bool = False
    network: str = "allowlist"          # allowlist | none
    filesystem: str = "sandbox_root_only"
    record_dependencies: bool = True
    record_commit: bool = True
    record_licence: bool = True
    outputs_are_untrusted: bool = True

    def violations(self) -> list[str]:
        bad = []
        for field_name in ("secrets", "broker_credentials", "live_order_authority",
                           "canonical_write_authority", "production_merge_authority"):
            if getattr(self, field_name):
                bad.append(f"{field_name} must be False for third-party code")
        if self.network not in ("allowlist", "none"):
            bad.append(f"network policy {self.network!r} is neither allowlist nor none")
        if not self.outputs_are_untrusted:
            bad.append("outputs must be untrusted until independently ingested and verified")
        return bad


#: The single policy every sandbox runs under. It is a constant on purpose: a per-system knob is
#: how one exception becomes the rule.
POLICY = SandboxPolicy()


@dataclass(frozen=True)
class ExternalSystem:
    """One public research system as a potential parallel worker."""

    system_id: str
    name: str
    upstream: str
    role: str
    integration: str
    capabilities: tuple[str, ...]
    axes: tuple[str, ...]
    region: str = "global"
    languages: tuple[str, ...] = ("en",)
    lineage_parent: str | None = None
    licence: str = "UNVERIFIED"
    discovery_source: str = "principal_roster_2026-09-17"
    notes: str = ""

    def unknown_capabilities(self) -> tuple[str, ...]:
        return tuple(c for c in self.capabilities if c not in CAPABILITY_FAMILIES)

    def unknown_axes(self) -> tuple[str, ...]:
        return tuple(a for a in self.axes if a not in NEW_AXES)


def _s(*items: str) -> tuple[str, ...]:
    return tuple(items)


#: THE BOOTSTRAP ROSTER (principal 2026-09-17). Seeds, never a whitelist -- see `admit()`.
#: `upstream` is the public project as the principal named it; a provisioning run resolves and
#: PINS the real URL and commit, and refuses DIRECT execution until it has read the licence.
SEEDS: tuple[ExternalSystem, ...] = (
    ExternalSystem("rd_agent", "Microsoft RD-Agent(Q)", "github:microsoft/RD-Agent",
                   "factor/model co-evolution, autonomous experiment generation, research feedback",
                   "DIRECT", _s("factor_model_coevolution", "experiment_scheduler"),
                   _s("search_algorithm", "research_workflow"),
                   notes="already absorbed as METHODS (hypothesis->feedback, novelty screen); the "
                         "law now also requires it as a running worker"),
    ExternalSystem("qlib", "Microsoft Qlib", "github:microsoft/qlib",
                   "ML/factor laboratory and benchmark environment for RD-Agent descendants",
                   "DIRECT", _s("representation_learning", "walk_forward_harness", "data_tooling"),
                   _s("representation", "research_workflow")),
    ExternalSystem("agonalpha", "AgonAlpha", "public:agonalpha",
                   "artifact-level alpha search, MCTS allocation, independent reviewer, reruns",
                   "DIRECT", _s("artifact_search", "mcts", "independent_verifier"),
                   _s("search_algorithm", "adversarial_verifier", "research_workflow")),
    ExternalSystem("quantaalpha", "QuantaAlpha", "public:quantaalpha",
                   "evolve whole research trajectories; mutation/crossover of procedures",
                   "DIRECT", _s("trajectory_evolution", "evolutionary_search"),
                   _s("search_algorithm", "research_workflow")),
    ExternalSystem("alphaagent", "AlphaAgent", "public:alphaagent",
                   "hypothesis->factor generation with structural novelty and anti-decay",
                   "DIRECT", _s("structural_novelty", "symbolic_regression"),
                   _s("hypothesis_language", "search_algorithm")),
    ExternalSystem("alphacrafter", "AlphaCrafter", "public:alphacrafter",
                   "factor discovery -> regime-aware selection -> adaptive execution harness",
                   "DIRECT", _s("regime_selection", "walk_forward_harness"),
                   _s("research_workflow", "execution_method")),
    ExternalSystem("hubble", "Hubble alpha framework", "paper:hubble",
                   "DSL/AST-constrained factor generation, deterministic evaluation, RAG memory",
                   "REBUILT", _s("dsl_program_search", "structural_novelty"),
                   _s("hypothesis_language", "search_algorithm"),
                   notes="REBUILT until usable public code is confirmed; never recorded as DIRECT "
                         "on the strength of a paper"),
    ExternalSystem("autohypothesis", "AutoHypothesis", "public:autohypothesis",
                   "autonomous hypothesis/strategy mutation laboratory; independent baseline",
                   "DIRECT", _s("evolutionary_search", "walk_forward_harness"),
                   _s("search_algorithm",)),
    ExternalSystem("inalpha", "inalpha", "public:inalpha",
                   "factor timing, strategy-code evolution, machine-gated agent experiments",
                   "DIRECT", _s("evolutionary_search", "experiment_scheduler"),
                   _s("research_workflow", "search_algorithm")),
    ExternalSystem("nexquant", "NexQuant", "public:nexquant",
                   "high-throughput deterministic explore/exploit strategy search",
                   "DIRECT", _s("evolutionary_search", "experiment_scheduler"),
                   _s("search_algorithm",)),
    ExternalSystem("tradingagents", "TradingAgents (TauricResearch)",
                   "github:TauricResearch/TradingAgents",
                   "multi-agent fundamentals/news/sentiment/technical debate",
                   "DIRECT", _s("multi_agent_debate", "information_acquisition"),
                   _s("research_workflow", "hypothesis_language")),
    ExternalSystem("tradingagents_kr", "TradingAgents-KR", "public:tradingagents-kr",
                   "Korea civilization: KIS + DART + ECOS + Naver News, reflective workflow",
                   "WRAPPED", _s("multi_agent_debate", "data_source"),
                   _s("data", "region_language"), region="kr", languages=_s("ko", "en"),
                   lineage_parent="tradingagents",
                   notes="admitted for its KOREAN DATA STACK, not for its reasoning topology"),
    ExternalSystem("tradingagents_cn", "TradingAgents-CN", "public:tradingagents-cn",
                   "China civilization: A-share/HK, local news and data, domestic model ecosystem",
                   "WRAPPED", _s("multi_agent_debate", "data_source"),
                   _s("data", "region_language"), region="cn", languages=_s("zh", "en"),
                   lineage_parent="tradingagents"),
    ExternalSystem("ashare_agents", "AShareAgents / TradingAgents-AShare variants",
                   "public:ashare-agents",
                   "Sina/East Money forum sentiment and local A-share data transplants",
                   "WRAPPED", _s("data_source", "information_acquisition"),
                   _s("data", "region_language"), region="cn", languages=_s("zh",),
                   lineage_parent="tradingagents"),
    ExternalSystem("verumtrade", "VerumTrade", "public:verumtrade",
                   "evidence graph, bull/bear adversarial reasoning, catalyst discovery",
                   "WRAPPED", _s("multi_agent_debate", "independent_verifier"),
                   _s("adversarial_verifier", "research_workflow")),
    ExternalSystem("quantharness", "QuantHarness", "public:quantharness",
                   "price-action/indicator/pattern research population, short horizons",
                   "WRAPPED", _s("walk_forward_harness", "evolutionary_search"),
                   _s("hypothesis_language",)),
    ExternalSystem("alphaquanter", "AlphaQuanter", "public:alphaquanter",
                   "agentic-RL / tool-orchestrated strategy research",
                   "DIRECT", _s("rl_policy_search", "experiment_scheduler"),
                   _s("search_algorithm",)),
    ExternalSystem("contesttrade", "ContestTrade", "public:contesttrade",
                   "competitive multi-agent decision population; self-play experiments",
                   "WRAPPED", _s("multi_agent_debate", "independent_verifier"),
                   _s("research_workflow",)),
    ExternalSystem("quantagent", "Y-Research QuantAgent", "public:quantagent",
                   "financial-reasoning quant-agent population; reasoning diversity",
                   "DIRECT", _s("multi_agent_debate",), _s("hypothesis_language",)),
    ExternalSystem("atlas_gic", "ATLAS / atlas-gic", "public:atlas-gic",
                   "autoresearch / self-improving trading-agent experiments",
                   "DIRECT", _s("trajectory_evolution", "experiment_scheduler"),
                   _s("research_workflow",)),
    ExternalSystem("ai_trader", "HKUDS AI-Trader", "github:HKUDS/AI-Trader",
                   "autonomous trading-agent architecture: reasoning, memory, tools, workflow",
                   "WRAPPED", _s("multi_agent_debate", "information_acquisition"),
                   _s("research_workflow",)),
    ExternalSystem("autohedge", "AutoHedge", "public:autohedge",
                   "swarm-style financial agent organisation; architectural donor",
                   "REBUILT", _s("multi_agent_debate",), _s("research_workflow",)),
    ExternalSystem("ai_hedge_fund", "virattt/ai-hedge-fund", "github:virattt/ai-hedge-fund",
                   "multi-agent analyst-role baseline; adversarial diversity",
                   "DIRECT", _s("multi_agent_debate",), _s("research_workflow",)),
    ExternalSystem("valuecell", "ValueCell", "public:valuecell",
                   "multi-agent financial application framework; alternative orchestration",
                   "WRAPPED", _s("multi_agent_debate", "data_tooling"), _s("research_workflow",)),
    ExternalSystem("finrobot", "FinRobot", "github:AI4Finance-Foundation/FinRobot",
                   "financial-analysis agents: report, retrieval, tool research",
                   "DIRECT", _s("information_acquisition", "financial_nlp"),
                   _s("data", "research_workflow")),
    ExternalSystem("dexter", "Dexter", "public:dexter",
                   "autonomous deep-financial-research agent",
                   "DIRECT", _s("information_acquisition",), _s("data", "research_workflow")),
    ExternalSystem("fingpt", "FinGPT", "github:AI4Finance-Foundation/FinGPT",
                   "financial NLP sandbox: sentiment, event and entity representations",
                   "DIRECT", _s("financial_nlp", "representation_learning"),
                   _s("representation",)),
    ExternalSystem("kronos", "Kronos", "public:kronos",
                   "financial-market foundation model; learned representations and forecasts",
                   "DIRECT", _s("foundation_model", "representation_learning"),
                   _s("representation", "mathematical_method")),
    ExternalSystem("finrl", "FinRL / FinRL-X", "github:AI4Finance-Foundation/FinRL",
                   "RL policy research: allocation, timing, control experiments",
                   "DIRECT", _s("rl_policy_search", "portfolio_research"),
                   _s("search_algorithm", "execution_method")),
    ExternalSystem("lean", "LEAN", "github:QuantConnect/Lean",
                   "event-driven execution/backtest parity reference simulator",
                   "DIRECT", _s("replay_parity", "execution_engine"), _s("execution_method",),
                   notes="already absorbed as the live/backtest parity guard; the engine itself "
                         "remains a research-only sandbox"),
    ExternalSystem("nautilus", "NautilusTrader", "github:nautechsystems/nautilus_trader",
                   "deterministic replay, execution semantics, microstructure simulation",
                   "DIRECT", _s("replay_parity", "execution_engine", "microstructure"),
                   _s("execution_method",)),
    ExternalSystem("hummingbot", "Hummingbot", "github:hummingbot/hummingbot",
                   "market-making/execution/microstructure mechanism mine",
                   "REBUILT", _s("microstructure", "execution_engine"), _s("execution_method",),
                   notes="venue connectors are crypto-exchange ground and are NEVER hunted "
                         "(LAWS 1); only execution mechanisms transfer to Fusion"),
    ExternalSystem("vnpy", "vn.py", "github:vnpy/vnpy",
                   "event-driven quant/execution framework; China ecosystem architecture",
                   "REBUILT", _s("execution_engine", "data_tooling"),
                   _s("execution_method", "region_language"), region="cn", languages=_s("zh",)),
    ExternalSystem("akshare", "AKShare", "github:akfamily/akshare",
                   "China-native public financial data surface",
                   "DIRECT", _s("data_source",), _s("data", "region_language"),
                   region="cn", languages=_s("zh",)),
    ExternalSystem("tushare", "TuShare", "public:tushare",
                   "Chinese market/data axis source",
                   "DIRECT", _s("data_source",), _s("data", "region_language"),
                   region="cn", languages=_s("zh",)),
    ExternalSystem("hithink", "HiThink Financial API", "public:hithink",
                   "Chinese A-share structured data API for data-axis discovery",
                   "WRAPPED", _s("data_source",), _s("data",), region="cn", languages=_s("zh",),
                   notes="terms must be read before any machine access"),
    ExternalSystem("openbb", "OpenBB", "github:OpenBB-finance/OpenBB",
                   "open financial-data/research tool federation",
                   "DIRECT", _s("data_source", "data_tooling"), _s("data",)),
    ExternalSystem("openfr", "OpenFR", "public:openfr",
                   "Chinese financial research swarm: AKShare, debate, 35+ local data tools",
                   "WRAPPED", _s("multi_agent_debate", "data_source"),
                   _s("data", "region_language"), region="cn", languages=_s("zh",)),
    ExternalSystem("quanti", "Quanti", "public:quanti",
                   "A-share platform: autonomous loop, regime snapshots, walk-forward selection",
                   "WRAPPED", _s("regime_selection", "walk_forward_harness"),
                   _s("research_workflow", "region_language"), region="cn", languages=_s("zh",)),
    ExternalSystem("quantmind", "QuantMind", "public:quantmind",
                   "China-focused AI quant stack, six data sources, multiple agents",
                   "WRAPPED", _s("data_source", "multi_agent_debate"),
                   _s("data", "region_language"), region="cn", languages=_s("zh",),
                   notes="performance claims are hypotheses; only the data layer is evidence"),
    ExternalSystem("ai_quant_agent", "AI Quant Agent", "public:ai-quant-agent",
                   "rules+LLM hybrid with Tushare/AkShare/BaoStock/efinance fallback data layer",
                   "WRAPPED", _s("data_source", "data_tooling"),
                   _s("data", "region_language"), region="cn", languages=_s("zh",)),
    ExternalSystem("astockarena", "AStockArena", "public:astockarena",
                   "A-share multi-agent framework, synchronised snapshots, recorded positions",
                   "WRAPPED", _s("multi_agent_debate", "walk_forward_harness"),
                   _s("research_workflow", "region_language"), region="cn", languages=_s("zh",)),
    ExternalSystem("ai_berkshire", "ai-berkshire", "public:ai-berkshire",
                   "Chinese adversarial fundamental/value research framework",
                   "DIRECT", _s("multi_agent_debate", "causal_discovery"),
                   _s("causal_machinery", "region_language"), region="cn", languages=_s("zh",)),
    ExternalSystem("ml_quant_trading", "initial-d/ml-quant-trading", "public:ml-quant-trading",
                   "multi-factor ML, bias correction, portfolio experiments",
                   "DIRECT", _s("representation_learning", "portfolio_research"),
                   _s("representation", "mathematical_method"), region="cn"),
    ExternalSystem("zvt", "zvt", "github:zvtvz/zvt",
                   "modular Chinese quant/data framework",
                   "DIRECT", _s("data_tooling", "data_source"),
                   _s("data", "region_language"), region="cn", languages=_s("zh",)),
    ExternalSystem("quantsplaybook", "QuantsPlaybook", "public:quantsplaybook",
                   "Chinese broker research-reproduction corpus",
                   "REBUILT", _s("research_reproduction",),
                   _s("hypothesis_language", "region_language"), region="cn",
                   languages=_s("zh",)),
    ExternalSystem("vietnam_alpha", "Vietnam self-improving multi-agent alpha project",
                   "public:vn-multi-agent-alpha",
                   "self-improving multi-agent alpha search",
                   "WRAPPED", _s("trajectory_evolution", "multi_agent_debate"),
                   _s("search_algorithm", "region_language"), region="vn", languages=_s("vi",)),
    ExternalSystem("wq_research_engine", "Ewan Sutherland WorldQuant research engine",
                   "public:worldquant-research-engine",
                   "alpha expression search in the BRAIN idiom",
                   "REBUILT", _s("dsl_program_search", "symbolic_regression"),
                   _s("hypothesis_language",)),
    ExternalSystem("rohonchain", "RohOnChain (public artefacts)", "public:rohonchain",
                   "Hawkes intensity, prediction-market dependency, multimodal event reading",
                   "REBUILT", _s("causal_discovery", "information_acquisition"),
                   _s("mathematical_method", "data"),
                   notes="IDEAS ONLY by the principal's order: public papers, code and references "
                         "are read; the account itself is never monitored or mined"),
    ExternalSystem("l1vsun", "L1vsun (public artefacts)", "public:l1vsun",
                   "forced-flow and funding mechanics, narrative state",
                   "REBUILT", _s("information_acquisition", "causal_discovery"),
                   _s("data", "mathematical_method")),
    ExternalSystem("bl888m", "bl888m (public artefacts)", "public:bl888m",
                   "prediction markets, smart-participant provenance, resolution truth",
                   "REBUILT", _s("information_acquisition",), _s("data",)),
    # ---- the six explicit civilizations and the second-wave systems (principal 2026-09-19) --
    ExternalSystem("alpha_search", "Alpha Search", "public:alpha-search",
                   "five-agent opportunity/critique swarm, 37 data adapters, walk-forward",
                   "DIRECT", _s("multi_agent_debate", "data_source", "walk_forward_harness"),
                   _s("research_workflow", "data"),
                   notes="worker and architecture donor, never validated machinery: its own "
                         "changelog was still fixing random-simulation and cost defects"),
    ExternalSystem("quantrocket", "QuantRocket", "public:quantrocket",
                   "global market substrate (70+ markets via IB); commercial",
                   "WRAPPED", _s("data_tooling", "execution_engine"),
                   _s("data", "research_infrastructure"),
                   notes="COMMERCIAL: integrate a licensed installation through its API only; "
                         "never vendored, never copied"),
    ExternalSystem("quantconnect_cloud", "QuantConnect research agents (platform)",
                   "public:quantconnect", "research/validation/backtest/paper/live agents",
                   "WRAPPED", _s("research_reliability", "walk_forward_harness"),
                   _s("research_workflow",),
                   notes="LEAN core is Apache-2.0 (see lean); the agent stack is platform "
                         "functionality reached by API where terms permit"),
    ExternalSystem("numerai_method", "Numerai pattern (method only)", "public:numerai",
                   "independent-model aggregation, feature neutralisation, meta-model, "
                   "contribution measurement", "REBUILT",
                   _s("portfolio_research", "independent_verifier"), _s("research_workflow",),
                   notes="the tournament data is obfuscated and non-tradable by its terms; the "
                         "METHOD applies to our own PIT datasets"),
    ExternalSystem("quantifact", "Quantifact (PAT-inspired)", "public:quantifact",
                   "point-in-time reproducible evidence, research plans, contracts, caching",
                   "DIRECT", _s("information_acquisition", "research_reliability"),
                   _s("research_workflow",)),
    ExternalSystem("bridgewater_pat_aia", "Bridgewater AIA / PAT (public architecture)",
                   "public:bridgewater-aia", "ambiguous question -> plan -> PIT evidence -> "
                   "calculations -> causal explanation -> testable hypotheses", "REBUILT",
                   _s("institutional_capability", "information_acquisition"),
                   _s("research_workflow", "world_model_component"),
                   notes="architecture, talks and public descriptions only; nothing internal "
                         "is public and nothing internal is sought"),
    ExternalSystem("alphagen", "AlphaGen", "public:alphagen",
                   "RL/GP synergistic formulaic-alpha collections with GP/DSO baselines",
                   "DIRECT", _s("evolutionary_search", "rl_policy_search", "symbolic_regression"),
                   _s("search_algorithm",)),
    ExternalSystem("dso", "Deep Symbolic Optimization", "public:dso",
                   "RL over expression trees", "DIRECT", _s("symbolic_regression",),
                   _s("search_algorithm",)),
    ExternalSystem("pysr", "PySR", "github:MilesCranmer/PySR",
                   "high-performance symbolic regression", "DIRECT",
                   _s("symbolic_regression",), _s("mathematical_method",)),
    ExternalSystem("tigramite", "Tigramite", "github:jakobrunge/tigramite",
                   "lagged causal graphs, conditional dependence, hidden-variable-aware tests",
                   "DIRECT", _s("causal_discovery",), _s("causal_machinery",)),
    ExternalSystem("causal_learn", "causal-learn", "github:py-why/causal-learn",
                   "constraint, score, functional and hidden-representation causal discovery",
                   "DIRECT", _s("causal_discovery",), _s("causal_machinery",)),
    ExternalSystem("dowhy", "DoWhy", "github:py-why/dowhy",
                   "causal identification, estimation, counterfactuals and refutation",
                   "DIRECT", _s("causal_discovery", "independent_verifier"),
                   _s("causal_machinery", "adversarial_verifier")),
    ExternalSystem("chronos2", "Chronos-2", "public:chronos-2",
                   "time-series foundation model, zero/few-shot forecasting", "DIRECT",
                   _s("foundation_model",), _s("model_family",)),
    ExternalSystem("timesfm", "TimesFM", "public:timesfm",
                   "time-series foundation model", "DIRECT", _s("foundation_model",),
                   _s("model_family",),
                   notes="3.0 weights are non-commercial/non-production by their terms; licence "
                         "metadata is part of the manifest, never assumed"),
    ExternalSystem("moment", "MOMENT", "public:moment",
                   "time-series foundation representations", "DIRECT",
                   _s("foundation_model", "representation_learning"), _s("model_family",)),
    ExternalSystem("abides", "ABIDES", "public:abides",
                   "agent-based exchange simulation with explicit latency", "DIRECT",
                   _s("market_simulation", "game_theory"), _s("simulation_world",)),
    ExternalSystem("ruptures", "ruptures", "public:ruptures",
                   "change-point detection and nonstationary segmentation", "DIRECT",
                   _s("change_point",), _s("representation",)),
    ExternalSystem("tsfresh", "tsfresh", "public:tsfresh",
                   "hundreds of statistical/nonlinear/signal representations with filtering",
                   "DIRECT", _s("feature_synthesis",), _s("representation",)),
    ExternalSystem("featuretools", "Featuretools", "public:featuretools",
                   "deep feature synthesis across relational entities", "DIRECT",
                   _s("feature_synthesis",), _s("representation",)),
    ExternalSystem("riskfolio", "Riskfolio-Lib", "public:riskfolio",
                   "Kelly/log-growth, many convex risk measures, risk parity", "DIRECT",
                   _s("portfolio_optimization",), _s("adversarial_verifier",),
                   notes="an independent allocator CHALLENGER; it never sizes capital"),
    ExternalSystem("cvxportfolio", "cvxportfolio", "public:cvxportfolio",
                   "independent portfolio optimisation/backtesting", "DIRECT",
                   _s("portfolio_optimization",), _s("adversarial_verifier",)),
    ExternalSystem("botorch", "BoTorch", "public:botorch",
                   "Bayesian optimisation / active experiment selection", "DIRECT",
                   _s("bayesian_optimization",), _s("search_algorithm",)),
    ExternalSystem("nevergrad", "Nevergrad", "public:nevergrad",
                   "derivative-free and evolution-strategy black-box search", "DIRECT",
                   _s("evolutionary_search",), _s("search_algorithm",)),
    ExternalSystem("pymoo", "pymoo", "public:pymoo",
                   "multi-objective evolutionary search (NSGA-II/III, MOEA/D, CMA-ES)",
                   "DIRECT", _s("multiobjective_search",), _s("search_algorithm",)),
    ExternalSystem("pymc", "PyMC", "public:pymc",
                   "hierarchical Bayesian / probabilistic programming", "DIRECT",
                   _s("probabilistic_programming",), _s("mathematical_method",)),
    ExternalSystem("mapie", "MAPIE", "public:mapie",
                   "conformal prediction intervals, adaptive conformal, exchangeability checks",
                   "DIRECT", _s("conformal_uncertainty",), _s("uncertainty_method",)),
    ExternalSystem("river", "River", "public:river",
                   "incremental/online learning with concept drift", "DIRECT",
                   _s("online_learning",), _s("model_family",)),
    ExternalSystem("neuralforecast", "NeuralForecast", "public:neuralforecast",
                   "N-BEATS/N-HiTS/TFT/PatchTST/iTransformer/DeepAR zoo", "DIRECT",
                   _s("forecast_zoo",), _s("model_family",)),
    ExternalSystem("darts", "Darts", "public:darts",
                   "classical/deep/probabilistic forecasting + anomaly ecosystem", "DIRECT",
                   _s("forecast_zoo", "anomaly_detection"), _s("model_family",)),
    ExternalSystem("kats", "Kats", "public:kats",
                   "change-point/anomaly/forecast/feature engine with detector meta-selection",
                   "DIRECT", _s("change_point", "anomaly_detection"), _s("model_family",)),
    ExternalSystem("merlion", "Merlion", "public:merlion",
                   "anomaly/change-point/forecasting AutoML with live-style evaluation",
                   "DIRECT", _s("anomaly_detection", "forecast_zoo"), _s("model_family",)),
    ExternalSystem("aeon", "aeon", "public:aeon",
                   "time-series classification/regression/clustering/segmentation zoo",
                   "DIRECT", _s("time_series_mining",), _s("model_family",)),
    ExternalSystem("tslearn", "tslearn", "public:tslearn",
                   "DTW, barycenters, shape/motif similarity", "DIRECT",
                   _s("time_series_mining",), _s("representation",)),
    ExternalSystem("idtxl", "IDTxl", "public:idtxl",
                   "multivariate transfer entropy, conditional MI, information decomposition",
                   "DIRECT", _s("information_theory",), _s("mathematical_method",)),
    ExternalSystem("tpot", "TPOT", "public:tpot",
                   "genetic-programming evolution of whole ML pipelines", "DIRECT",
                   _s("program_evolution",), _s("search_algorithm",)),
    ExternalSystem("openspiel", "OpenSpiel", "public:openspiel",
                   "multi-agent / imperfect-information game search", "DIRECT",
                   _s("game_theory",), _s("simulation_world",)),
    ExternalSystem("pyg_temporal", "PyTorch Geometric Temporal", "public:pyg-temporal",
                   "dynamic graph neural networks", "DIRECT", _s("graph_learning",),
                   _s("representation",)),
    ExternalSystem("ripser", "Ripser.py / scikit-TDA", "public:ripser",
                   "persistent homology of market state", "DIRECT", _s("topology",),
                   _s("representation",)),
    ExternalSystem("ray", "Ray RLlib / Tune", "public:ray",
                   "distributed RL, evolution strategies, scalable search substrate",
                   "DIRECT", _s("distributed_compute", "rl_policy_search"),
                   _s("research_infrastructure",)),
    ExternalSystem("stumpy", "STUMPY", "public:stumpy",
                   "matrix-profile motif and discord discovery", "DIRECT",
                   _s("time_series_mining",), _s("representation",)),
    ExternalSystem("pysindy", "PySINDy", "public:pysindy",
                   "sparse identification of nonlinear governing equations", "DIRECT",
                   _s("dynamical_systems",), _s("mathematical_method",)),
    ExternalSystem("pydmd", "PyDMD", "public:pydmd",
                   "dynamic mode decomposition / Koopman modes", "DIRECT",
                   _s("dynamical_systems",), _s("mathematical_method",)),
    ExternalSystem("pyvinecopulib", "pyvinecopulib", "public:pyvinecopulib",
                   "vine copulas, tail and conditional dependence", "DIRECT",
                   _s("copula_dependence",), _s("mathematical_method",)),
    ExternalSystem("easytpp", "EasyTPP", "public:easytpp",
                   "neural temporal point processes (Hawkes/Transformer intensities)",
                   "DIRECT", _s("point_process",), _s("model_family",)),
    ExternalSystem("tensorly", "TensorLy", "public:tensorly",
                   "tensor decomposition over asset x feature x regime x time", "DIRECT",
                   _s("tensor_methods",), _s("representation",)),
    ExternalSystem("reservoirpy", "ReservoirPy", "public:reservoirpy",
                   "echo-state / reservoir computing", "DIRECT", _s("reservoir_computing",),
                   _s("model_family",)),
    ExternalSystem("kymatio", "Kymatio", "public:kymatio",
                   "wavelet scattering transforms", "DIRECT", _s("signal_scattering",),
                   _s("representation",)),
    ExternalSystem("scikit_mine", "scikit-mine", "public:scikit-mine",
                   "explicit sequential/pattern mining", "DIRECT", _s("pattern_mining",),
                   _s("hypothesis_language",)),
    ExternalSystem("pyextremes", "pyextremes", "public:pyextremes",
                   "extreme-value theory: exceedances, return periods", "DIRECT",
                   _s("extreme_value",), _s("mathematical_method",)),
    ExternalSystem("pgmpy", "pgmpy", "public:pgmpy",
                   "probabilistic graphical models / dynamic Bayesian networks", "DIRECT",
                   _s("graphical_models",), _s("causal_machinery",)),
    ExternalSystem("pyrqa", "PyRQA", "public:pyrqa",
                   "recurrence quantification analysis", "DIRECT", _s("recurrence_analysis",),
                   _s("representation",)),
    ExternalSystem("roughpy", "RoughPy", "public:roughpy",
                   "rough paths / path signatures from streamed data", "DIRECT",
                   _s("rough_paths",), _s("representation",)),
    ExternalSystem("sbi", "sbi", "public:sbi",
                   "simulation-based inference: posteriors over latent market worlds",
                   "DIRECT", _s("simulation_based_inference",), _s("simulation_world",)),
    # ---- the meta-evolution layer (principal 2026-09-19): evolve the researchers themselves
    ExternalSystem("openevolve", "OpenEvolve (AlphaEvolve-style)", "public:openevolve",
                   "LLM-driven evolution of algorithms/codebases with automated evaluators, "
                   "islands, MAP-Elites dimensions", "DIRECT", _s("program_evolution",),
                   _s("research_workflow", "search_algorithm"),
                   notes="evolves research machinery only; the evaluator, PIT rules, trial "
                         "accounting and rails are immutable and separately authorised"),
    ExternalSystem("darwin_godel_machine", "Darwin Goedel Machine (public work)",
                   "public:darwin-godel-machine",
                   "archive of self-modifying agents with empirical selection", "REBUILT",
                   _s("agent_evolution",), _s("research_workflow",)),
    ExternalSystem("ai_scientist", "The AI Scientist v2 (Sakana, open-sourced)",
                   "public:ai-scientist",
                   "idea -> experiment -> interpretation -> review loop", "DIRECT",
                   _s("automated_science",), _s("research_workflow",)),
    ExternalSystem("pyribs", "pyribs", "public:pyribs",
                   "quality-diversity / MAP-Elites archives", "DIRECT", _s("quality_diversity",),
                   _s("search_algorithm",)),
    ExternalSystem("dspy", "DSPy", "public:dspy",
                   "program-level optimisation of agent prompts/demonstrations (MIPROv2, GEPA)",
                   "DIRECT", _s("prompt_optimization",), _s("research_workflow",)),
    # ---- public formula corpora and observation-only sources ---------------------------
    ExternalSystem("alpha101", "101 Formulaic Alphas (public paper)", "paper:alpha101",
                   "101 explicit formulaic alphas as PARENT GENOMES for the expression factory",
                   "REBUILT", _s("dsl_program_search",), _s("hypothesis_language",),
                   notes="public formulas only; WorldQuant BRAIN data, private alphas and any "
                         "platform extraction are excluded by its terms and by LAWS 5h"),
    ExternalSystem("worldquant_brain_public", "WorldQuant BRAIN (public operators only)",
                   "public:worldquant-brain", "public operator semantics, tutorials, papers",
                   "REBUILT", _s("dsl_program_search", "institutional_capability"),
                   _s("hypothesis_language",),
                   notes="terms prohibit automated extraction: documentation is read, the "
                         "platform is never scraped"),
    ExternalSystem("aitradingarena", "AITradingArena (public telemetry)",
                   "public:aitradingarena", "public methodology, lifecycle transitions, "
                   "transfer-before-tuning evidence; paid code off-limits", "REBUILT",
                   _s("telemetry_source", "research_reliability"), _s("research_workflow",),
                   notes="respect its access rules; observations are hypothesis priors"),
    ExternalSystem("arcticdb", "ArcticDB (Man Group)", "public:arcticdb",
                   "wide/long dataframe time-series database", "DIRECT", _s("data_tooling",),
                   _s("research_infrastructure",)),
    ExternalSystem("deshaw_tools", "D. E. Shaw open tools (Pyflyby, Versioned HDF5)",
                   "public:deshaw-tools", "versioning and research tooling", "DIRECT",
                   _s("data_tooling",), _s("research_infrastructure",)),
    # ---- institutional capability seeds (LAWS 5g/5h): public architecture only, no prestige
    ExternalSystem("inst_renaissance", "Renaissance Technologies (public record)",
                   "public:renaissance", "scientist-first systematic research; common model; "
                   "leverage over low-vol model returns; transaction-cost detail", "REBUILT",
                   _s("institutional_capability",), _s("research_workflow",)),
    ExternalSystem("inst_deshaw", "D. E. Shaw (public record)", "public:deshaw",
                   "cross-strategy exposure view, capacity discipline, financing/liquidity "
                   "allocation", "REBUILT", _s("institutional_capability",),
                   _s("world_model_component",)),
    ExternalSystem("inst_two_sigma", "Two Sigma (public record)", "public:two-sigma",
                   "data-as-code, feature orthogonality, hypothesis-evaluation bottleneck",
                   "REBUILT", _s("institutional_capability",), _s("research_workflow",)),
    ExternalSystem("inst_citadel", "Citadel / GQS (public record)", "public:citadel",
                   "integrated research->portfolio->execution loop, market impact as research",
                   "REBUILT", _s("institutional_capability",), _s("execution_method",)),
    ExternalSystem("inst_xtx", "XTX Markets (public record)", "public:xtx",
                   "ML forecasting over 53,000+ instruments as sensors", "REBUILT",
                   _s("institutional_capability",), _s("model_family",)),
    ExternalSystem("inst_optiver_imc_hrt", "Optiver / IMC / HRT / Jane Street (public record)",
                   "public:market-makers", "probabilistic order-flow reasoning, dynamic market "
                   "structure, low-latency engineering", "REBUILT",
                   _s("institutional_capability",), _s("execution_method",)),
    ExternalSystem("inst_man_aqr_winton", "Man AHL / AQR / Winton / QRT / Squarepoint (public)",
                   "public:systematic-managers", "systematic research platforms, published "
                   "factor research", "REBUILT", _s("institutional_capability",),
                   _s("research_workflow",)),
    ExternalSystem("inst_highflyer", "High-Flyer (public record)", "public:highflyer",
                   "AI-native strategy research, shared-compute scheduling, utilisation "
                   "telemetry", "REBUILT", _s("institutional_capability", "distributed_compute"),
                   _s("research_infrastructure",), region="cn", languages=_s("zh",)),
    ExternalSystem("inst_ubiquant_lingjun_minghong", "Ubiquant / Lingjun / Minghong (public)",
                   "public:cn-quant", "Data Lab / AI Lab / systems lab split, data breadth",
                   "REBUILT", _s("institutional_capability",), _s("research_workflow",),
                   region="cn", languages=_s("zh",)),
)

SEED_BY_ID: dict[str, ExternalSystem] = {s.system_id: s for s in SEEDS}


@dataclass(frozen=True)
class Decision:
    """The outcome of admitting (or refusing) a newly discovered system."""

    disposition: str
    why: str
    novel_axes: tuple[str, ...] = ()
    duplicate_of: str | None = None
    ev: float | None = None


@dataclass(frozen=True)
class ExternalResearchPacket:
    """THE ONLY EXIT FROM A SANDBOX (LAWS 5h).

    It carries research, never a verdict: candidates, datasets, mechanisms, representations and
    research methods with their provenance and the real search burden. Constructing one with a
    verdict-shaped key raises -- the refusal is at the type boundary, not in a reviewer's habits.
    """

    system_id: str
    run_id: str
    commit: str
    candidates: tuple[Mapping[str, Any], ...] = ()
    datasets: tuple[Mapping[str, Any], ...] = ()
    mechanisms: tuple[Mapping[str, Any], ...] = ()
    representations: tuple[Mapping[str, Any], ...] = ()
    research_methods: tuple[Mapping[str, Any], ...] = ()
    trials_charged: int = 0
    provenance: Mapping[str, Any] = field(default_factory=dict)
    policy: SandboxPolicy = POLICY

    def __post_init__(self) -> None:
        if self.trials_charged < 0:
            raise ValueError("trials_charged is the real search burden and cannot be negative")
        bad = self.policy.violations()
        if bad:
            raise ValueError(f"sandbox policy violated: {bad}")
        for group in (self.candidates, self.datasets, self.mechanisms, self.representations,
                      self.research_methods):
            for row in group:
                hits = sorted(k for k in row if str(k).lower() in PACKET_FORBIDDEN)
                if hits:
                    raise ValueError(
                        f"external packet carries verdict-shaped fields {hits}: an external "
                        f"engine is a researcher, never a validator and never a capital "
                        f"authority (LAWS 5h). Donate the hypothesis; the gauntlet judges it.")

    def counts(self) -> dict[str, int]:
        return {"candidates": len(self.candidates), "datasets": len(self.datasets),
                "mechanisms": len(self.mechanisms),
                "representations": len(self.representations),
                "research_methods": len(self.research_methods),
                "trials_charged": self.trials_charged}

    def empty(self) -> bool:
        return sum(v for k, v in self.counts().items() if k != "trials_charged") == 0


def fingerprint(system: ExternalSystem | Mapping[str, Any]) -> str:
    """A capability fingerprint: what a system CAN DO, never what it is called.

    Two repositories with the same capabilities and axes fingerprint identically, which is what
    collapses a fork storm into one lineage before any compute is spent on it.
    """
    if isinstance(system, ExternalSystem):
        caps, axes, region = system.capabilities, system.axes, system.region
    else:
        caps = tuple(system.get("capabilities") or ())
        axes = tuple(system.get("axes") or ())
        region = str(system.get("region") or "global")
    body = "|".join((",".join(sorted(caps)), ",".join(sorted(axes)), region))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def novel_axes(candidate: ExternalSystem, existing: Iterable[ExternalSystem]) -> tuple[str, ...]:
    """Axes the candidate brings that no existing system in its lineage neighbourhood has.

    Region+language counts as a new axis on purpose: a Korean data stack over a known reasoning
    topology is a real addition, and it is exactly the case the principal named.
    """
    seen: set[str] = set()
    for other in existing:
        same_family = bool(set(other.capabilities) & set(candidate.capabilities))
        same_region = other.region == candidate.region
        for axis in other.axes:
            if axis == "region_language" and not same_region:
                continue
            if axis == "data" and not same_region and candidate.region != "global":
                continue
            if same_family or axis not in ("search_algorithm", "hypothesis_language"):
                seen.add(axis)
    return tuple(a for a in candidate.axes if a not in seen)


def admit(candidate: ExternalSystem, existing: Sequence[ExternalSystem],
          *, ev_capability: float | None = None, ev_duplication: float = 0.0,
          integration_cost: float = 0.0) -> Decision:
    """Mechanical admission (LAWS 5h).

    A system earns its own sandbox when EV(new capability) - EV(duplication) - integration cost
    is positive AND it brings at least one materially new axis. Everything else collapses into a
    lineage and contributes only its unique parts -- that is the whole defence against fake
    breadth, and it is applied BEFORE compute, never after a thousand near-identical formulas
    have already been tested.
    """
    if candidate.unknown_capabilities():
        return Decision("UNDISPOSED",
                        f"capabilities outside the vocabulary: {candidate.unknown_capabilities()}")
    if candidate.unknown_axes():
        return Decision("UNDISPOSED", f"axes outside the vocabulary: {candidate.unknown_axes()}")
    fresh = novel_axes(candidate, existing)
    prints = {fingerprint(e): e.system_id for e in existing}
    twin = prints.get(fingerprint(candidate))
    if twin and not fresh:
        return Decision("DUPLICATE",
                        f"same capability fingerprint as {twin} and no new axis: one lineage, "
                        f"not two discoveries", duplicate_of=twin)
    if not fresh:
        return Decision("DUPLICATE",
                        "every axis is already covered by the federation; kept as a lineage "
                        "branch contributing only its unique components",
                        duplicate_of=twin or (existing[0].system_id if existing else None))
    gain = len(fresh) if ev_capability is None else ev_capability
    ev = gain - ev_duplication - integration_cost
    if ev <= 0:
        return Decision("REJECTED_WITH_EVIDENCE",
                        f"measured EV {ev:.3f} <= 0 after duplication and integration cost; "
                        f"reopens when its yield or our cost changes", novel_axes=fresh, ev=ev)
    return Decision(candidate.integration if candidate.integration in RUNNING_DISPOSITIONS
                    else "WRAPPED",
                    f"new axes {fresh}; EV {ev:.3f} > 0", novel_axes=fresh, ev=ev)


def collapse_lineage(systems: Sequence[ExternalSystem]) -> dict[str, list[str]]:
    """parent system_id -> its branches. A fork storm is one parent plus its unique parts."""
    out: dict[str, list[str]] = {}
    for s in systems:
        parent = s.lineage_parent or s.system_id
        out.setdefault(parent, [])
        if s.lineage_parent:
            out[parent].append(s.system_id)
    return out


#: The operational conjunction (LAWS 5h). A folder is not a worker.
OPERATIONAL_TERMS: tuple[str, ...] = ("registered", "sandboxed", "scheduled", "executed",
                                      "progressed", "produced", "consumed")


def operational(row: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """REGISTERED and SANDBOXED and SCHEDULED and EXECUTED and PROGRESSED and PRODUCED and
    CONSUMED -- with the missing terms NAMED, because "not operational" without the term is the
    report that changes nothing."""
    missing = tuple(t for t in OPERATIONAL_TERMS if not bool(row.get(t)))
    return (not missing), missing


def roi(row: Mapping[str, Any]) -> float | None:
    """ROI_s = (E[future independent dG] + information gain) / (compute + data + engineering +
    trial budget). UNMEASURED (None) when nothing has been spent OR nothing has been measured --
    a zero denominator is not an infinite return, and an unspent system is not a bad one."""
    gain = row.get("live_delta_elog")
    info = row.get("information_gain")
    if gain is None and info is None:
        return None
    spend = 0.0
    for k in ("compute_spent", "data_cost", "engineering_cost", "trial_budget_spent"):
        try:
            spend += float(row.get(k) or 0.0)
        except (TypeError, ValueError):
            continue
    if spend <= 0:
        return None
    return (float(gain or 0.0) + float(info or 0.0)) / spend


def allocation(rows: Sequence[Mapping[str, Any]], total_budget_s: int,
               *, floor_s: int = 60) -> dict[str, int]:
    """Compute shares proportional to ROI, with a FLOOR so no frontier is ever switched off.

    An unmeasured system gets the mean share rather than nothing: refusing budget to everything
    that has not yet produced is how a federation freezes on its first week's luck.
    """
    if not rows:
        return {}
    measured = [(str(r.get("system_id")), roi(r)) for r in rows]
    known = [v for _, v in measured if v is not None and v > 0]
    default = (sum(known) / len(known)) if known else 1.0
    weights = {sid: (v if (v is not None and v > 0) else default) for sid, v in measured}
    total_w = sum(weights.values()) or 1.0
    out: dict[str, int] = {}
    for sid, w in weights.items():
        out[sid] = max(floor_s, int(total_budget_s * w / total_w))
    return out


def exhausted(conditions: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """CURRENT_PUBLIC_FRONTIER_EXHAUSTED requires all twelve conditions (LAWS 5g); the ones that
    are false are returned so the next pass knows what to do rather than what to feel."""
    open_ones = tuple(c for c in EXHAUSTION_CONDITIONS if not bool(conditions.get(c)))
    return (not open_ones), open_ones


def ledger_row(system: ExternalSystem, **state: Any) -> dict[str, Any]:
    """A registry row with every field the law names, UNMEASURED where nothing measured it."""
    base: dict[str, Any] = dict.fromkeys(LEDGER_FIELDS, "UNMEASURED")
    base.update({
        "system_id": system.system_id, "upstream_repo": system.upstream,
        "licence": system.licence, "discovery_source": system.discovery_source,
        "region": system.region, "languages": list(system.languages),
        "capabilities": list(system.capabilities), "integration_mode": system.integration,
        "disposition": "UNDISPOSED", "status": "DISCOVERED", "sandbox_status": "NOT_PROVISIONED",
        "why": system.notes or "",
    })
    base.update(state)
    return base


def to_json(systems: Sequence[ExternalSystem]) -> str:
    return json.dumps([asdict(s) for s in systems], indent=1, default=str)


def from_json(text: str) -> tuple[ExternalSystem, ...]:
    rows = json.loads(text)
    return tuple(ExternalSystem(**{**r, "capabilities": tuple(r.get("capabilities") or ()),
                                   "axes": tuple(r.get("axes") or ()),
                                   "languages": tuple(r.get("languages") or ("en",))})
                 for r in rows)
