"""THE ADAPTERS -- one per federated system, each turning an upstream research engine's native
output into an ExternalResearchPacket over a READ-ONLY ResearchBundle (LAWS 5h, 5m).

WHAT AN ADAPTER IS. `run(bundle: ResearchBundle) -> ExternalResearchPacket`, executed INSIDE the
system's sandbox (`python -m libs.research.adapters.<system> --bundle <path> --out <path>`) by
`desks/mt5/research/sandbox_runner.py`, never inside the desk process. The bundle is a COPY of a
few bar frames, axis series with their available_time, the cost surface, a research question, a
compute budget, a seed and the allowed horizons -- written into the sandbox work directory,
never mounted. The packet is the ONLY exit: candidates, representations, mechanisms, research
methods and datasets with provenance and the real search burden (`trials_charged` counts every
parameter the engine evaluated). A verdict-shaped field raises at the contract, here and again
at the desk's boundary, so an upstream engine can donate a hypothesis and never a survivor.

WHAT AN ADAPTER IS NOT. It is not a validator (no Sharpe, no pass, no rank has authority), not a
sizer (riskfolio donates allocation EVIDENCE, never a size), and not a mount: it reads only what
the bundle carries. A library that is absent in the environment is reported UNMEASURED by name
in the packet's research_methods rather than raised, because "the engine did not run" is a
measurement the federation ledger needs and a stack trace is not.

THIS MODULE IS IMPORT-LIGHT ON PURPOSE. It is copied into every sandbox together with the packet
contract, so it may import the standard library and the contract and nothing else at module
scope; numpy is imported lazily because every federated engine already depends on it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import random
import sys
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.research.external_federation import PACKET_FORBIDDEN, ExternalResearchPacket

#: A candidate row that names a registered price-only family compiles as STRUCTURED_HYPOTHESIS
#: in `miner_candidate_compiler` (family defaults, declared instruments). Adapters name ONLY
#: these; a family outside the vocabulary would be read as prose and lose its instrument.
FAMILIES: tuple[str, ...] = (
    "failed_breakout", "level_breakout", "overnight_drift", "mean_reversion_rsi",
    "mean_reversion_bollinger", "volatility_squeeze", "trend_ma_cross", "momentum_volgate",
    "range_reversion", "volume_spike", "pullback_entry", "vol_mean_reversion", "vol_transition",
    "drawdown_conditional", "spread_state",
)


@dataclass(frozen=True)
class Spec:
    """Where a system is distributed, at which measured pin, and what its adapter yields."""

    system_id: str
    distribution: str
    version: str
    module: str
    weight: str = "light"
    yields: tuple[str, ...] = ()
    note: str = ""

    @property
    def requirement(self) -> str:
        return f"{self.distribution}=={self.version}" if self.version else self.distribution


#: THE FIRST ADAPTERS. Pins are the versions `pip download --only-binary :all:` resolved on this
#: desk's interpreter (CPython 3.14, 2026-09-22) -- measured installable wheels, not remembered
#: release numbers. `weight="heavy"` marks a torch dependency (hundreds of MB; provisioned last).
SPECS: dict[str, Spec] = {s.system_id: s for s in (
    Spec("ruptures", "ruptures", "1.0.6", "ruptures", yields=("representations", "candidates"),
         note="1.1.x ships no wheel for this interpreter; 1.0.6 is the pure-python build"),
    Spec("stumpy", "stumpy", "1.14.1", "stumpy", yields=("representations", "candidates")),
    Spec("pysindy", "pysindy", "2.1.0", "pysindy", yields=("mechanisms",)),
    Spec("pydmd", "pydmd", "2025.8.1", "pydmd", yields=("representations",)),
    Spec("tsfresh", "tsfresh", "0.21.2", "tsfresh", yields=("representations",)),
    Spec("riskfolio", "Riskfolio-Lib", "7.3.0", "riskfolio", yields=("research_methods",),
         note="allocator CHALLENGER: allocation evidence, never a size"),
    Spec("pymoo", "pymoo", "0.6.2", "pymoo", yields=("candidates", "research_methods")),
    Spec("nevergrad", "nevergrad", "1.0.12", "nevergrad", yields=("candidates",)),
    Spec("botorch", "botorch", "0.18.1", "botorch", weight="heavy",
         yields=("research_methods", "candidates")),
    Spec("river", "river", "0.26.1", "river", yields=("representations",)),
    Spec("mapie", "mapie", "1.5.0", "mapie", yields=("representations",)),
    Spec("tensorly", "tensorly", "0.9.0", "tensorly", yields=("representations",)),
    Spec("pyrqa", "PyRQA", "", "pyrqa", yields=("representations",),
         note="sdist-only on PyPI and OpenCL-backed; provisioning measures whether it installs"),
    Spec("pgmpy", "pgmpy", "1.1.2", "pgmpy", weight="heavy", yields=("mechanisms",)),
    Spec("pyextremes", "pyextremes", "2.5.0", "pyextremes",
         yields=("representations", "candidates")),
    Spec("scikit_mine", "scikit-mine", "1.0.0", "skmine",
         yields=("representations", "candidates")),
    Spec("tslearn", "tslearn", "0.9.0", "tslearn", yields=("representations", "candidates")),
    Spec("pyvinecopulib", "pyvinecopulib", "1.0.0", "pyvinecopulib", yields=("representations",)),
    Spec("roughpy", "roughpy", "0.3.0", "roughpy", yields=("representations",)),
)}

#: THE MANDATED WAVES (principal 2026-09-19/22): symbolic regression, causal machinery, the
#: foundation models, simulation, feature synthesis, the forecast zoos, information theory,
#: program evolution, topology, distributed search, point processes, reservoirs, scattering,
#: simulation-based inference, the meta-evolution layer, and the WRAPPED/REBUILT institutional
#: methods. A pin is the wheel `pip download --only-binary :all:` resolved on this interpreter
#: on 2026-09-22; an EMPTY pin means no wheel resolved here (sdist-only, a git-only project, or a
#: torch stack this interpreter has no build for) and provisioning measures it again. A
#: git-only project carries NO distribution: `pip download` found no `abides`, `idtxl`,
#: `alphagen` or `quantifact` wheel, and PyPI's `dso` is a different project -- reading a
#: namesake's terms is worse than UNVERIFIED, so those are read from their repositories.
SPECS.update({s.system_id: s for s in (
    Spec("alphagen", "", "", "alphagen", yields=("candidates",),
         note="git-only (RL-MLDM/alphagen): provisioning pins the commit, never a wheel"),
    Spec("dso", "", "", "dso", yields=("mechanisms",),
         note="git-only (dso-org/deep-symbolic-optimization)"),
    Spec("pysr", "pysr", "2.5.0", "pysr", weight="heavy", yields=("mechanisms",),
         note="needs a Julia runtime the first run installs; UNMEASURED until it exists"),
    Spec("tigramite", "tigramite", "5.2.10.1", "tigramite", yields=("mechanisms",)),
    Spec("causal_learn", "causal-learn", "0.1.4.8", "causallearn", yields=("mechanisms",)),
    Spec("dowhy", "dowhy", "0.8", "dowhy", yields=("research_methods", "mechanisms")),
    Spec("chronos2", "chronos-forecasting", "2.3.2", "chronos", weight="heavy",
         yields=("representations",), note="weights come from the local HF cache only"),
    Spec("timesfm", "timesfm", "3.0.2", "timesfm", weight="heavy", yields=("representations",),
         note="3.0 weights are non-commercial by their terms: research representation only"),
    Spec("moment", "momentfm", "0.1.4", "momentfm", weight="heavy", yields=("representations",)),
    Spec("abides", "", "", "abides_core", yields=("datasets", "representations")),
    Spec("featuretools", "featuretools", "1.31.0", "featuretools", yields=("representations",)),
    Spec("cvxportfolio", "cvxportfolio", "1.5.1", "cvxportfolio", yields=("research_methods",),
         note="allocator CHALLENGER: allocation evidence, never a size"),
    Spec("pymc", "pymc", "6.3.2", "pymc", weight="heavy", yields=("representations",)),
    Spec("neuralforecast", "neuralforecast", "3.2.2", "neuralforecast", weight="heavy",
         yields=("representations",)),
    Spec("darts", "u8darts", "0.41.0", "darts", yields=("representations",)),
    Spec("kats", "kats", "0.2.0", "kats", yields=("representations", "candidates")),
    Spec("merlion", "salesforce-merlion", "2.0.4", "merlion", yields=("representations",)),
    Spec("aeon", "aeon", "1.6.0", "aeon", yields=("representations", "candidates")),
    Spec("idtxl", "", "", "idtxl", yields=("mechanisms",),
         note="git-only (pwollstadt/IDTxl); JIDT estimators need a JVM"),
    Spec("tpot", "TPOT", "0.12.2", "tpot", yields=("research_methods",)),
    Spec("openspiel", "open_spiel", "2.0.2", "pyspiel", yields=("research_methods",)),
    Spec("pyg_temporal", "torch-geometric-temporal", "0.56.2", "torch_geometric_temporal",
         weight="heavy", yields=("representations",)),
    Spec("ripser", "ripser", "0.6.15", "ripser", yields=("representations", "candidates")),
    Spec("ray", "ray", "2.58.0", "ray", weight="heavy", yields=("candidates",)),
    Spec("easytpp", "easy-tpp", "0.3.0", "easy_tpp", weight="heavy", yields=("datasets",)),
    Spec("reservoirpy", "reservoirpy", "0.4.2", "reservoirpy", yields=("representations",)),
    Spec("kymatio", "kymatio", "0.3.0", "kymatio", yields=("representations",)),
    Spec("sbi", "sbi", "0.27.0", "sbi", weight="heavy", yields=("representations",)),
    Spec("openevolve", "openevolve", "0.3.2", "openevolve", yields=("research_methods",),
         note="LLM-driven upstream; the research path carries no LLM, so the loop is REBUILT"),
    Spec("darwin_godel_machine", "", "", "dgm", yields=("research_methods",),
         note="REBUILT by the roster: no upstream code runs here"),
    Spec("ai_scientist", "", "", "ai_scientist", yields=("research_methods",),
         note="LLM-driven upstream; REBUILT route"),
    Spec("pyribs", "ribs", "0.12.0", "ribs", yields=("candidates",)),
    Spec("dspy", "dspy", "3.3.1", "dspy", yields=("research_methods",),
         note="prompt optimisation needs an LLM; the research path carries none"),
    Spec("quantifact", "", "", "quantifact", yields=("research_methods",)),
    Spec("bridgewater_pat_aia", "", "", "", yields=("research_methods",),
         note="REBUILT: public architecture only, nothing to install"),
    Spec("alpha_search", "", "", "alpha_search", yields=("research_methods",)),
    Spec("quantrocket", "quantrocket-client", "2.11.0.0", "quantrocket",
         yields=("research_methods",),
         note="WRAPPED: a licensed installation reached by API only"),
    Spec("quantconnect_cloud", "lean", "1.0.229", "lean", yields=("datasets", "research_methods"),
         note="WRAPPED: LEAN core is Apache-2.0; the platform is reached by API"),
    Spec("numerai_method", "", "", "", yields=("research_methods", "candidates"),
         note="REBUILT: the method on the desk's own PIT data, numpy only"),
)})

#: The capability family each adapter's packet routes under (CAPABILITY_FAMILIES) and the
#: licence its upstream PUBLISHES. `licence_expected` is what a maintainer wrote in the project
#: metadata as this desk last read it; it is NOT the licence of record -- only
#: `libs.research.licence_reader` produces that, at a pin, and the runner refuses DIRECT
#: execution until it has (LAWS 5h). The expected id exists so a reading that disagrees is
#: visible as a disagreement rather than silently accepted.
FAMILY_OF: dict[str, str] = {
    "ruptures": "change_point", "stumpy": "time_series_mining", "pysindy": "dynamical_systems",
    "pydmd": "dynamical_systems", "tsfresh": "feature_synthesis",
    "riskfolio": "portfolio_optimization", "pymoo": "multiobjective_search",
    "nevergrad": "evolutionary_search", "botorch": "bayesian_optimization",
    "river": "online_learning", "mapie": "conformal_uncertainty", "tensorly": "tensor_methods",
    "pyrqa": "recurrence_analysis", "pgmpy": "graphical_models", "pyextremes": "extreme_value",
    "scikit_mine": "pattern_mining", "tslearn": "time_series_mining",
    "pyvinecopulib": "copula_dependence", "roughpy": "rough_paths",
    "alphagen": "evolutionary_search", "dso": "symbolic_regression",
    "pysr": "symbolic_regression", "tigramite": "causal_discovery",
    "causal_learn": "causal_discovery", "dowhy": "causal_discovery",
    "chronos2": "foundation_model", "timesfm": "foundation_model",
    "moment": "foundation_model", "abides": "market_simulation",
    "featuretools": "feature_synthesis", "cvxportfolio": "portfolio_optimization",
    "pymc": "probabilistic_programming", "neuralforecast": "forecast_zoo",
    "darts": "forecast_zoo", "kats": "change_point", "merlion": "anomaly_detection",
    "aeon": "time_series_mining", "idtxl": "information_theory", "tpot": "program_evolution",
    "openspiel": "game_theory", "pyg_temporal": "graph_learning", "ripser": "topology",
    "ray": "distributed_compute", "easytpp": "point_process",
    "reservoirpy": "reservoir_computing", "kymatio": "signal_scattering",
    "sbi": "simulation_based_inference", "openevolve": "program_evolution",
    "darwin_godel_machine": "agent_evolution", "ai_scientist": "automated_science",
    "pyribs": "quality_diversity", "dspy": "prompt_optimization",
    "quantifact": "research_reliability", "bridgewater_pat_aia": "institutional_capability",
    "alpha_search": "multi_agent_debate", "quantrocket": "data_tooling",
    "quantconnect_cloud": "research_reliability", "numerai_method": "portfolio_research",
}
LICENCE_EXPECTED: dict[str, str] = {
    "ruptures": "BSD-2-Clause", "stumpy": "BSD-3-Clause", "pysindy": "MIT", "pydmd": "MIT",
    "tsfresh": "MIT", "riskfolio": "BSD-3-Clause", "pymoo": "Apache-2.0", "nevergrad": "MIT",
    "botorch": "MIT", "river": "BSD-3-Clause", "mapie": "BSD-3-Clause",
    "tensorly": "BSD-3-Clause", "pyrqa": "GPL-3.0", "pgmpy": "MIT", "pyextremes": "MIT",
    "scikit_mine": "BSD-3-Clause", "tslearn": "BSD-2-Clause", "pyvinecopulib": "MIT",
    "roughpy": "BSD-3-Clause", "alphagen": "MIT", "dso": "BSD-3-Clause", "pysr": "Apache-2.0",
    "tigramite": "GPL-3.0", "causal_learn": "MIT", "dowhy": "MIT", "chronos2": "Apache-2.0",
    "timesfm": "Apache-2.0", "moment": "MIT", "abides": "BSD-3-Clause",
    "featuretools": "BSD-3-Clause", "cvxportfolio": "Apache-2.0", "pymc": "Apache-2.0",
    "neuralforecast": "Apache-2.0", "darts": "Apache-2.0", "kats": "MIT",
    "merlion": "BSD-3-Clause", "aeon": "BSD-3-Clause", "idtxl": "GPL-3.0", "tpot": "LGPL-3.0",
    "openspiel": "Apache-2.0", "pyg_temporal": "MIT", "ripser": "MIT", "ray": "Apache-2.0",
    "easytpp": "Apache-2.0", "reservoirpy": "MIT", "kymatio": "BSD-3-Clause",
    "sbi": "Apache-2.0", "openevolve": "Apache-2.0", "darwin_godel_machine": "Apache-2.0",
    "ai_scientist": "Apache-2.0", "pyribs": "MIT", "dspy": "MIT", "quantifact": "UNVERIFIED",
    "bridgewater_pat_aia": "N/A (no code)", "alpha_search": "UNVERIFIED",
    "quantrocket": "Proprietary", "quantconnect_cloud": "Apache-2.0",
    "numerai_method": "N/A (method only)",
}
#: THE ROSTER SEEDS (2026-09-23). Every seed the generated roster named as having NO
#: ADAPTER now has one, so
#: `SANDBOX_ROSTER.needs_adapter` is a measurement rather than a backlog. Three kinds:
#: a PROBE (the upstream is a library or a repository -- the adapter measures its API
#: surface here and records UNMEASURED with the install task when it is absent), a
#: REJECTED_WITH_EVIDENCE row (no distribution exists and an LLM/credential requirement
#: the research path refuses -- the adapter names every module it tried), and a REBUILT
#: method (the published technique implemented in numpy on the bundle, RUNS_WITHOUT_
#: LIBRARY, so it runs in-process and produces). An EMPTY version means no wheel was
#: pinned on this interpreter; provisioning measures it, and `requirement` degrades to
#: the bare distribution name.
SPECS.update({s.system_id: s for s in (
    Spec("akshare", "akshare", "", "akshare",
         weight="light", yields=('datasets',),
         note="PROBE: China-native public data surface: axes only, never a hunted universe"),
    Spec("tushare", "tushare", "", "tushare",
         weight="light", yields=('datasets',),
         note="PROBE: the free tier needs a token the sandbox does not carry"),
    Spec("openbb", "openbb", "", "openbb",
         weight="heavy", yields=('datasets',),
         note="PROBE: AGPL and a large dependency tree: provisioned late, used for axes only"),
    Spec("arcticdb", "arcticdb", "", "arcticdb",
         weight="light", yields=('datasets',),
         note="PROBE: BUSL-1.1 is source-available; direct use stays licence-gated"),
    Spec("zvt", "zvt", "", "zvt",
         weight="light", yields=('datasets',),
         note="PROBE: a framework with its own database bootstrap"),
    Spec("dexter", "", "", "dexter",
         weight="light", yields=('research_methods',),
         note="PROBE: no wheel resolved 2026-09-23; repository pin first"),
    Spec("finrobot", "finrobot", "", "finrobot",
         weight="light", yields=('research_methods',),
         note="PROBE: the agents need an LLM key the research path refuses"),
    Spec("ai_hedge_fund", "", "", "ai_hedge_fund",
         weight="light", yields=('research_methods',),
         note="PROBE: git-only (virattt/ai-hedge-fund)"),
    Spec("autohedge", "autohedge", "", "autohedge",
         weight="light", yields=('research_methods',),
         note="PROBE: swarm orchestration over an LLM"),
    Spec("quantagent", "", "", "quantagent",
         weight="light", yields=('research_methods',),
         note="PROBE: no wheel resolved 2026-09-23"),
    Spec("tradingagents", "tradingagents", "", "tradingagents",
         weight="light", yields=('research_methods',),
         note="PROBE: the debate needs an LLM key"),
    Spec("autohypothesis", "", "", "autohypothesis",
         weight="light", yields=('candidates',),
         note="PROBE: no wheel resolved 2026-09-23"),
    Spec("inalpha", "", "", "inalpha",
         weight="light", yields=('candidates',),
         note="PROBE: no wheel resolved 2026-09-23"),
    Spec("nexquant", "", "", "nexquant",
         weight="light", yields=('candidates',),
         note="PROBE: no wheel resolved 2026-09-23"),
    Spec("atlas_gic", "", "", "atlas_gic",
         weight="light", yields=('research_methods',),
         note="PROBE: no wheel resolved 2026-09-23"),
    Spec("alphaquanter", "", "", "alphaquanter",
         weight="light", yields=('research_methods',),
         note="PROBE: no wheel resolved 2026-09-23"),
    Spec("finrl", "finrl", "", "finrl",
         weight="heavy", yields=('research_methods',),
         note="PROBE: pulls a torch stack; provisioned last"),
    Spec("lean", "lean", "", "lean",
         weight="light", yields=('research_methods',),
         note="PROBE: the CLI only; quantconnect_cloud carries the pinned version of the sam"),
    Spec("nautilus", "nautilus_trader", "", "nautilus_trader",
         weight="heavy", yields=('research_methods',),
         note="PROBE: a compiled rust core; wheel availability is measured"),
    Spec("ml_quant_trading", "", "", "ml_quant_trading",
         weight="light", yields=('representations',),
         note="PROBE: no wheel resolved 2026-09-23"),
    Spec("qlib", "pyqlib", "", "qlib",
         weight="heavy", yields=('representations',),
         note="PROBE: needs a provider_uri data directory the sandbox does not carry"),
    Spec("fingpt", "", "", "fingpt",
         weight="heavy", yields=('representations',),
         note="PROBE: git-only; needs model weights and a torch stack"),
    Spec("kronos", "", "", "kronos",
         weight="heavy", yields=('representations',),
         note="PROBE: no wheel resolved 2026-09-23; weights from a local cache only"),
    Spec("rd_agent", "rdagent", "", "rdagent",
         weight="heavy", yields=('research_methods',),
         note="PROBE: the loop is LLM-driven; the mechanism is rebuilt without one"),
    Spec("vnpy", "vnpy", "", "vnpy",
         weight="heavy", yields=('research_methods',),
         note="PROBE: the event engine pulls Qt and broker gateways"),
    Spec("ai_quant_agent", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("ashare_agents", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("hithink", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("quantmind", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("deshaw_tools", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("ai_berkshire", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("ai_trader", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("astockarena", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("contesttrade", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("openfr", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("tradingagents_cn", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("tradingagents_kr", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("valuecell", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("verumtrade", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("vietnam_alpha", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("quanti", "", "", "", yields=("research_methods",),
         note="REJECTED_WITH_EVIDENCE: the adapter names what was tried"),
    Spec("alpha101", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("hubble", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("worldquant_brain_public", "", "", "", yields=('representations',),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("wq_research_engine", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("bl888m", "", "", "", yields=('representations', 'research_methods'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("l1vsun", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("agonalpha", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("alphaagent", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("quantaalpha", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("alphacrafter", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("quantharness", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("quantsplaybook", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("hummingbot", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("rohonchain", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("aitradingarena", "", "", "", yields=('representations',),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_xtx", "", "", "", yields=('representations',),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_two_sigma", "", "", "", yields=('representations',),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_renaissance", "", "", "", yields=('research_methods',),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_citadel", "", "", "", yields=('representations',),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_deshaw", "", "", "", yields=('representations',),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_highflyer", "", "", "", yields=('representations',),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_man_aqr_winton", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_optiver_imc_hrt", "", "", "", yields=('candidates', 'representations'),
         note="REBUILT in desk code (numpy only); runs in-process"),
    Spec("inst_ubiquant_lingjun_minghong", "", "", "", yields=('representations',),
         note="REBUILT in desk code (numpy only); runs in-process"),
)})
FAMILY_OF.update({
    "akshare": "data_source", "tushare": "data_source", "openbb": "data_source",
    "arcticdb": "data_tooling", "zvt": "data_tooling", "dexter": "information_acquisition",
    "finrobot": "information_acquisition", "ai_hedge_fund": "multi_agent_debate",
    "autohedge": "multi_agent_debate", "quantagent": "multi_agent_debate",
    "tradingagents": "multi_agent_debate", "autohypothesis": "evolutionary_search",
    "inalpha": "evolutionary_search", "nexquant": "evolutionary_search",
    "atlas_gic": "trajectory_evolution", "alphaquanter": "rl_policy_search",
    "finrl": "rl_policy_search", "lean": "replay_parity", "nautilus": "replay_parity",
    "ml_quant_trading": "representation_learning", "qlib": "representation_learning",
    "fingpt": "financial_nlp", "kronos": "foundation_model",
    "rd_agent": "factor_model_coevolution", "vnpy": "execution_engine",
    "ai_quant_agent": "data_source", "ashare_agents": "data_source", "hithink": "data_source",
    "quantmind": "data_source", "deshaw_tools": "data_tooling",
    "ai_berkshire": "multi_agent_debate", "ai_trader": "multi_agent_debate",
    "astockarena": "multi_agent_debate", "contesttrade": "multi_agent_debate",
    "openfr": "multi_agent_debate", "tradingagents_cn": "multi_agent_debate",
    "tradingagents_kr": "multi_agent_debate", "valuecell": "multi_agent_debate",
    "verumtrade": "multi_agent_debate", "vietnam_alpha": "trajectory_evolution",
    "quanti": "regime_selection", "alpha101": "dsl_program_search", "hubble": "dsl_program_search",
    "worldquant_brain_public": "dsl_program_search", "wq_research_engine": "dsl_program_search",
    "bl888m": "information_acquisition", "l1vsun": "information_acquisition",
    "agonalpha": "artifact_search", "alphaagent": "structural_novelty",
    "quantaalpha": "trajectory_evolution", "alphacrafter": "regime_selection",
    "quantharness": "walk_forward_harness", "quantsplaybook": "research_reproduction",
    "hummingbot": "microstructure", "rohonchain": "causal_discovery",
    "aitradingarena": "telemetry_source", "inst_xtx": "institutional_capability",
    "inst_two_sigma": "institutional_capability", "inst_renaissance": "institutional_capability",
    "inst_citadel": "institutional_capability", "inst_deshaw": "institutional_capability",
    "inst_highflyer": "institutional_capability",
    "inst_man_aqr_winton": "institutional_capability",
    "inst_optiver_imc_hrt": "institutional_capability",
    "inst_ubiquant_lingjun_minghong": "institutional_capability",
})
LICENCE_EXPECTED.update({
    "akshare": "MIT", "tushare": "BSD-3-Clause", "openbb": "AGPL-3.0", "arcticdb": "BUSL-1.1",
    "zvt": "MIT", "dexter": "UNVERIFIED", "finrobot": "Apache-2.0", "ai_hedge_fund": "MIT",
    "autohedge": "MIT", "quantagent": "UNVERIFIED", "tradingagents": "Apache-2.0",
    "autohypothesis": "UNVERIFIED", "inalpha": "UNVERIFIED", "nexquant": "UNVERIFIED",
    "atlas_gic": "UNVERIFIED", "alphaquanter": "UNVERIFIED", "finrl": "MIT", "lean": "Apache-2.0",
    "nautilus": "LGPL-3.0", "ml_quant_trading": "UNVERIFIED", "qlib": "MIT", "fingpt": "MIT",
    "kronos": "UNVERIFIED", "rd_agent": "MIT", "vnpy": "MIT", "ai_quant_agent": "UNVERIFIED",
    "ashare_agents": "UNVERIFIED", "hithink": "UNVERIFIED", "quantmind": "UNVERIFIED",
    "deshaw_tools": "UNVERIFIED", "ai_berkshire": "UNVERIFIED", "ai_trader": "UNVERIFIED",
    "astockarena": "UNVERIFIED", "contesttrade": "UNVERIFIED", "openfr": "UNVERIFIED",
    "tradingagents_cn": "UNVERIFIED", "tradingagents_kr": "UNVERIFIED", "valuecell": "UNVERIFIED",
    "verumtrade": "UNVERIFIED", "vietnam_alpha": "UNVERIFIED", "quanti": "UNVERIFIED",
    "alpha101": "N/A (published method)", "hubble": "N/A (published method)",
    "worldquant_brain_public": "N/A (public documentation)",
    "wq_research_engine": "N/A (published method)", "bl888m": "N/A (method only)",
    "l1vsun": "N/A (method only)", "agonalpha": "N/A (published architecture)",
    "alphaagent": "N/A (published method)", "quantaalpha": "N/A (published method)",
    "alphacrafter": "N/A (published architecture)", "quantharness": "N/A (published method)",
    "quantsplaybook": "N/A (published research)", "hummingbot": "Apache-2.0",
    "rohonchain": "N/A (published method)", "aitradingarena": "N/A (public methodology)",
    "inst_xtx": "N/A (public architecture)", "inst_two_sigma": "N/A (public architecture)",
    "inst_renaissance": "N/A (public architecture)", "inst_citadel": "N/A (public architecture)",
    "inst_deshaw": "N/A (public architecture)", "inst_highflyer": "N/A (public architecture)",
    "inst_man_aqr_winton": "N/A (published research)",
    "inst_optiver_imc_hrt": "N/A (public architecture)",
    "inst_ubiquant_lingjun_minghong": "N/A (public architecture)",
})

#: Packets from the desk's own sandboxed research cells (desks/mt5/research/sandboxes/) carry
#: this prefix on their system_id: they are REBUILT mechanisms in the desk's own code, so their
#: commit is the desk tree's HEAD rather than a PyPI pin.
CELL_PREFIX = "cell:"


def describe(module: Any, licences: Mapping[str, str] | None = None) -> dict[str, Any]:
    """THE ADAPTER CONTRACT, as a record: name, licence (of record when the runner passes the
    ledger's readings; otherwise UNVERIFIED with the expected id beside it), capability family,
    the pinned requirement, whether the upstream imports HERE, and the run callable."""
    name = str(getattr(module, "SYSTEM", "") or getattr(module, "NAME", ""))
    spec = SPECS.get(name)
    family = str(getattr(module, "CAPABILITY_FAMILY", "") or FAMILY_OF.get(name, ""))
    expected = str(getattr(module, "LICENCE_EXPECTED", "") or LICENCE_EXPECTED.get(name,
                                                                                 "UNVERIFIED"))
    read = (licences or {}).get(name, "")
    licence = read if read and read not in ("UNVERIFIED", "UNMEASURED") \
        else f"UNVERIFIED (expected {expected}; read it with licence_reader)"
    available = bool(spec and spec.module and library(spec.module) is not None)
    return {"name": name, "licence": licence, "licence_expected": expected,
            "capability_family": family, "distribution": spec.distribution if spec else "",
            "requirement": spec.requirement if spec else "", "version": spec.version if spec
            else "", "module": spec.module if spec else "", "weight": spec.weight if spec
            else "light", "yields": list(spec.yields) if spec else [],
            "runs_without_library": bool(getattr(module, "RUNS_WITHOUT_LIBRARY", False)),
            "available_here": available, "run": getattr(module, "run", None)}


def _git_head() -> str:
    """The desk tree's HEAD, read from .git without running git (stdlib, sandbox-safe)."""
    try:
        root = Path(__file__).resolve().parents[3]
        head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head[:12]
        ref_name = head.split(" ", 1)[1].strip()
        ref = root / ".git" / ref_name
        if ref.exists():
            return ref.read_text(encoding="utf-8").strip()[:12]
        packed = root / ".git" / "packed-refs"
        if packed.exists():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref_name):
                    return line.split(" ", 1)[0][:12]
        return "UNMEASURED"
    except OSError:
        return "UNMEASURED"


# ------------------------------------------------------------------------------- the bundle

@dataclass(frozen=True)
class BarFrame:
    """One symbol's bars at one timeframe, as immutable columns (UTC ISO times)."""

    symbol: str
    timeframe: str
    time: tuple[str, ...]
    open: tuple[float, ...]
    high: tuple[float, ...]
    low: tuple[float, ...]
    close: tuple[float, ...]
    volume: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.time)

    @property
    def key(self) -> str:
        return f"{self.symbol}_{self.timeframe}"

    def log_returns(self) -> Any:
        import numpy as np
        c = np.asarray(self.close, dtype=float)
        return np.diff(np.log(np.maximum(c, 1e-12)))


@dataclass(frozen=True)
class AxisSeries:
    """A point-in-time axis: (available_time, value) points and the stamp's own basis."""

    axis: str
    series: str
    points: tuple[tuple[str, float], ...]
    available_time: str
    basis: str = ""


@dataclass(frozen=True)
class CostRow:
    """The cost surface for one symbol: spread by hour in points, tick and contract size."""

    symbol: str
    tick_size: float
    contract_size: float
    pooled_median_spread_pts: float
    spread_pts_p50_by_hour: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchBundle:
    """Everything an adapter may read, copied into the sandbox. Frozen: a bundle is never edited,
    and an engine that wants more data asks the runner for a different bundle."""

    bundle_id: str
    built_at: str
    question: str
    compute_budget_s: int
    seed: int
    horizons: tuple[str, ...]
    universe: tuple[str, ...]
    bars: Mapping[str, BarFrame] = field(default_factory=dict)
    axes: Mapping[str, AxisSeries] = field(default_factory=dict)
    costs: Mapping[str, CostRow] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    read_only: bool = True

    def frames(self, timeframe: str = "H1") -> list[BarFrame]:
        return [f for f in self.bars.values() if f.timeframe == timeframe]

    def frame(self, symbol: str, timeframe: str = "H1") -> BarFrame | None:
        return self.bars.get(f"{symbol}_{timeframe}")

    def watermark(self) -> str:
        """The newest bar time across frames -- the monotonic progress mark of a run."""
        return max((f.time[-1] for f in self.bars.values() if f.time), default="")

    def cost_pts(self, symbol: str) -> float:
        row = self.costs.get(symbol)
        return float(row.pooled_median_spread_pts) if row else float("nan")

    def digest(self) -> str:
        h = hashlib.sha256()
        for key in sorted(self.bars):
            f = self.bars[key]
            h.update(key.encode())
            h.update(str(len(f)).encode())
            h.update((f.time[-1] if f.time else "").encode())
            h.update(repr(f.close[-3:]).encode())
        h.update(json.dumps(sorted(self.axes)).encode())
        h.update(str(self.seed).encode())
        return h.hexdigest()[:16]


def write_bundle(bundle: ResearchBundle, directory: Path) -> Path:
    """Write the bundle as `bundle.json` + `bars/<key>.csv` under `directory`; return the manifest.
    CSV so a sandbox with numpy alone can read it; nothing here needs pandas or pyarrow."""
    directory.mkdir(parents=True, exist_ok=True)
    bars_dir = directory / "bars"
    bars_dir.mkdir(exist_ok=True)
    files: dict[str, str] = {}
    for key, f in bundle.bars.items():
        p = bars_dir / f"{key}.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["time", "open", "high", "low", "close", "volume"])
            for i in range(len(f)):
                w.writerow([f.time[i], f.open[i], f.high[i], f.low[i], f.close[i], f.volume[i]])
        files[key] = f"bars/{key}.csv"
    doc = {
        "bundle_id": bundle.bundle_id, "built_at": bundle.built_at, "question": bundle.question,
        "compute_budget_s": bundle.compute_budget_s, "seed": bundle.seed,
        "horizons": list(bundle.horizons), "universe": list(bundle.universe),
        "bars": {k: {"symbol": f.symbol, "timeframe": f.timeframe, "file": files[k],
                     "n": len(f)} for k, f in bundle.bars.items()},
        "axes": {k: asdict(a) for k, a in bundle.axes.items()},
        "costs": {k: {**asdict(c), "spread_pts_p50_by_hour": dict(c.spread_pts_p50_by_hour)}
                  for k, c in bundle.costs.items()},
        "provenance": dict(bundle.provenance), "read_only": True,
        "digest": bundle.digest(),
    }
    manifest = directory / "bundle.json"
    tmp = manifest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, manifest)
    return manifest


def load_bundle(path: Path) -> ResearchBundle:
    """Read a manifest written by `write_bundle` (paths resolve relative to the manifest)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    base = Path(path).parent
    bars: dict[str, BarFrame] = {}
    for key, meta in (doc.get("bars") or {}).items():
        cols: dict[str, list[Any]] = {c: [] for c in ("time", "open", "high", "low", "close",
                                                       "volume")}
        with (base / meta["file"]).open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                cols["time"].append(str(row["time"]))
                for c in ("open", "high", "low", "close", "volume"):
                    cols[c].append(float(row[c]))
        bars[key] = BarFrame(str(meta["symbol"]), str(meta["timeframe"]), tuple(cols["time"]),
                             tuple(cols["open"]), tuple(cols["high"]), tuple(cols["low"]),
                             tuple(cols["close"]), tuple(cols["volume"]))
    axes = {k: AxisSeries(str(a["axis"]), str(a["series"]),
                          tuple((str(t), float(v)) for t, v in a.get("points") or ()),
                          str(a.get("available_time") or ""), str(a.get("basis") or ""))
            for k, a in (doc.get("axes") or {}).items()}
    costs = {k: CostRow(str(c["symbol"]), float(c.get("tick_size") or 0.0),
                        float(c.get("contract_size") or 0.0),
                        float(c.get("pooled_median_spread_pts") or float("nan")),
                        {str(h): float(v) for h, v in (c.get("spread_pts_p50_by_hour")
                                                        or {}).items()})
             for k, c in (doc.get("costs") or {}).items()}
    return ResearchBundle(
        bundle_id=str(doc.get("bundle_id") or "UNMEASURED"),
        built_at=str(doc.get("built_at") or ""), question=str(doc.get("question") or ""),
        compute_budget_s=int(doc.get("compute_budget_s") or 300),
        seed=int(doc.get("seed") or 0), horizons=tuple(doc.get("horizons") or ("24h",)),
        universe=tuple(doc.get("universe") or ()), bars=bars, axes=axes, costs=costs,
        provenance=dict(doc.get("provenance") or {}))


def synthetic_bundle(*, seed: int = 0, n: int = 600,
                     symbols: Sequence[str] = ("XAUUSD", "EURUSD", "USDJPY"),
                     timeframe: str = "H1", budget_s: int = 60) -> ResearchBundle:
    """Planted random-walk bars with a volatility break half way -- for tests and dry runs.
    Nothing in it is market data; a packet built on it is a shape test, never evidence."""
    rng = random.Random(seed)  # noqa: S311 -- planted bars, never a secret
    t0 = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    step = {"H1": timedelta(hours=1), "M5": timedelta(minutes=5)}.get(timeframe,
                                                                     timedelta(hours=1))
    bars: dict[str, BarFrame] = {}
    for si, sym in enumerate(symbols):
        px = 100.0 * (si + 1)
        t, o, h, lo, c, v = [], [], [], [], [], []
        for i in range(n):
            vol = 0.002 if i < n // 2 else 0.006
            r = rng.gauss(0.0, vol) + (0.0004 * math.sin(i / 37.0))
            nxt = px * math.exp(r)
            hi = max(px, nxt) * (1 + abs(rng.gauss(0, vol / 2)))
            lw = min(px, nxt) * (1 - abs(rng.gauss(0, vol / 2)))
            t.append((t0 + i * step).isoformat())
            o.append(px)
            h.append(hi)
            lo.append(lw)
            c.append(nxt)
            v.append(float(rng.randint(100, 1000)))
            px = nxt
        bars[f"{sym}_{timeframe}"] = BarFrame(sym, timeframe, tuple(t), tuple(o), tuple(h),
                                              tuple(lo), tuple(c), tuple(v))
    axes = {"shadow_usd_liquidity.index": AxisSeries(
        "shadow_usd_liquidity", "index",
        tuple(((t0 + timedelta(days=d)).date().isoformat(), math.sin(d / 9.0))
              for d in range(0, n // 24 + 1)),
        (t0 + timedelta(days=n // 24)).date().isoformat(), "synthetic")}
    costs = {s: CostRow(s, 0.01, 100.0, 15.0, {str(hh): 15.0 + (hh % 5) for hh in range(24)})
             for s in symbols}
    return ResearchBundle(bundle_id=f"synthetic-{seed}", built_at=t0.isoformat(),
                          question="shape test on planted bars", compute_budget_s=budget_s,
                          seed=seed, horizons=("4h", "24h"), universe=tuple(symbols), bars=bars,
                          axes=axes, costs=costs, provenance={"synthetic": True})


# ------------------------------------------------------------------------------- the packet

class Deadline:
    """The compute budget, checked between parameter evaluations so an engine stops honestly and
    charges exactly what it evaluated."""

    def __init__(self, seconds: float) -> None:
        self.t0 = time.monotonic()
        self.seconds = float(seconds)

    def left(self) -> float:
        return self.seconds - (time.monotonic() - self.t0)

    def expired(self) -> bool:
        return self.left() <= 0


def library(name: str) -> Any | None:
    """The upstream module, or None when it is not importable here (reported, never raised)."""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def commit_of(system_id: str) -> str:
    """The exact upstream revision this environment runs: `pypi:<dist>==<installed version>`."""
    if system_id.startswith(CELL_PREFIX):
        return f"desk:{_git_head()}"
    spec = SPECS.get(system_id)
    if spec is None:
        return "UNMEASURED"
    if not spec.distribution:
        return f"desk:{_git_head()}"
    try:
        return f"pypi:{spec.distribution}=={importlib.metadata.version(spec.distribution)}"
    except importlib.metadata.PackageNotFoundError:
        return f"pypi:{spec.distribution}==UNMEASURED"


def run_id_for(system_id: str, bundle: ResearchBundle) -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{system_id}-{bundle.digest()}-{stamp}"


def py(value: Any) -> Any:
    """JSON-safe: numpy scalars/arrays to python, NaN/inf to None, tuples to lists."""
    if hasattr(value, "tolist"):
        return py(value.tolist())
    if isinstance(value, dict):
        return {str(k): py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [py(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def clean(row: Mapping[str, Any]) -> dict[str, Any]:
    """A packet row: JSON-safe and free of verdict-shaped keys (raises, at the source)."""
    hits = sorted(k for k in row if str(k).lower() in PACKET_FORBIDDEN)
    if hits:
        raise ValueError(f"adapter row carries verdict-shaped fields {hits}: an external engine "
                         f"is a researcher, never a validator (LAWS 5h)")
    return {str(k): py(v) for k, v in row.items()}


def candidate(family: str, symbols: Iterable[str], text: str, *, horizon: str,
              evidence: Mapping[str, Any], source: str) -> dict[str, Any]:
    """A STRUCTURED_HYPOTHESIS row: a registered family named outright, declared instruments,
    the engine's evidence riding along. The gauntlet judges; nothing here does."""
    if family not in FAMILIES:
        raise ValueError(f"{family!r} is not a registered price-only family: {FAMILIES}")
    return clean({"kind": "hypothesis", "family": family, "symbols": sorted(set(symbols)),
                  "text": text, "horizon": horizon, "evidence": dict(evidence),
                  "source": source, "authority": "none: a hypothesis for the ten gates"})


def packet(system_id: str, bundle: ResearchBundle, *, trials: int,
           candidates: Sequence[Mapping[str, Any]] = (),
           representations: Sequence[Mapping[str, Any]] = (),
           mechanisms: Sequence[Mapping[str, Any]] = (),
           research_methods: Sequence[Mapping[str, Any]] = (),
           datasets: Sequence[Mapping[str, Any]] = (),
           note: str = "") -> ExternalResearchPacket:
    """Build the packet through the contract: every row cleaned, every trial charged."""
    return ExternalResearchPacket(
        system_id=system_id, run_id=run_id_for(system_id, bundle), commit=commit_of(system_id),
        candidates=tuple(clean(r) for r in candidates),
        datasets=tuple(clean(r) for r in datasets),
        mechanisms=tuple(clean(r) for r in mechanisms),
        representations=tuple(clean(r) for r in representations),
        research_methods=tuple(clean(r) for r in research_methods),
        trials_charged=int(trials),
        provenance={"bundle_id": bundle.bundle_id, "bundle_digest": bundle.digest(),
                    "watermark": bundle.watermark(), "seed": bundle.seed,
                    "question": bundle.question, "note": note,
                    "produced_at": datetime.now(tz=UTC).isoformat(timespec="seconds")})


def unmeasured(system_id: str, bundle: ResearchBundle, why: str) -> ExternalResearchPacket:
    """The engine did not run: a packet that says so BY NAME, with zero trials charged."""
    return packet(system_id, bundle, trials=0,
                  research_methods=({"kind": "UNMEASURED", "system": system_id, "why": why},),
                  note="UNMEASURED")


def is_unmeasured(p: ExternalResearchPacket) -> bool:
    return (p.empty() or (all(str(r.get("kind")) == "UNMEASURED" for r in p.research_methods)
            and not (p.candidates or p.representations or p.mechanisms or p.datasets)))


def to_dict(p: ExternalResearchPacket) -> dict[str, Any]:
    return {"system_id": p.system_id, "run_id": p.run_id, "commit": p.commit,
            "candidates": list(p.candidates), "datasets": list(p.datasets),
            "mechanisms": list(p.mechanisms), "representations": list(p.representations),
            "research_methods": list(p.research_methods), "trials_charged": p.trials_charged,
            "provenance": dict(p.provenance), "counts": p.counts()}


def cli(run: Callable[[ResearchBundle], ExternalResearchPacket], system_id: str,
        argv: Sequence[str] | None = None) -> int:
    """`--bundle <manifest> --out <packet.json>`: the entry point the sandbox runner invokes.
    An adapter that raises still leaves a packet -- UNMEASURED with the failure named -- and
    exits 3, so the runner records RUN_FAILED with a reason instead of an empty out/ directory."""
    ap = argparse.ArgumentParser(description=f"{system_id} adapter (LAWS 5h sandbox worker)")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(list(argv) if argv is not None else None)
    bundle = load_bundle(Path(a.bundle))
    code = 0
    try:
        result = run(bundle)
    except Exception:
        tail = traceback.format_exc().strip().splitlines()[-3:]
        result = unmeasured(system_id, bundle, "adapter raised: " + " | ".join(tail)[:600])
        code = 3
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(to_dict(result), indent=1, default=str), encoding="utf-8")
    os.replace(tmp, out)
    sys.stdout.write(f"{system_id}: {result.counts()} -> {out}\n")
    return code


# ------------------------------------------------------------------------------- shared maths

def realised_vol(rets: Any, window: int) -> Any:
    """Rolling standard deviation of returns (trailing, NaN-padded), numpy only."""
    import numpy as np
    r = np.asarray(rets, dtype=float)
    out = np.full(r.shape[0], np.nan)
    if r.shape[0] >= window:
        c = np.cumsum(np.insert(r, 0, 0.0))
        c2 = np.cumsum(np.insert(r * r, 0, 0.0))
        mean = (c[window:] - c[:-window]) / window
        var = (c2[window:] - c2[:-window]) / window - mean * mean
        out[window - 1:] = np.sqrt(np.maximum(var, 0.0))
    return out


def ma_cross_objective(frame: BarFrame, fast: int, slow: int, cost_pts: float,
                       tick: float) -> dict[str, float]:
    """The objective the parameter-search engines share: a moving-average cross over the frame,
    charged the bundle's own spread. Returns EVIDENCE fields (objective_return,
    objective_drawdown, n_trades) -- names chosen so nothing here reads as a verdict."""
    import numpy as np
    c = np.asarray(frame.close, dtype=float)
    fast, slow = int(max(2, fast)), int(max(3, slow))
    if slow <= fast or c.shape[0] <= slow + 2:
        return {"objective_return": 0.0, "objective_drawdown": 0.0, "n_trades": 0.0}
    k_f = np.convolve(c, np.ones(fast) / fast, mode="valid")
    k_s = np.convolve(c, np.ones(slow) / slow, mode="valid")
    k_f = k_f[slow - fast:]
    pos = np.where(k_f > k_s, 1.0, -1.0)
    px = c[slow - 1:]
    rets = np.diff(np.log(np.maximum(px, 1e-12)))
    pnl = pos[:-1] * rets
    flips = np.abs(np.diff(pos)) > 0
    cost = (cost_pts * tick / np.maximum(px[1:], 1e-12)) if np.isfinite(cost_pts) else 0.0
    pnl = pnl - flips * cost
    eq = np.cumsum(pnl)
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if eq.size else 0.0
    return {"objective_return": float(eq[-1]) if eq.size else 0.0, "objective_drawdown": dd,
            "n_trades": float(flips.sum())}


#: The shared design matrix: three lagged returns and the trailing realised vol.
LAGGED_FEATURE_NAMES: tuple[str, ...] = ("r_1", "r_2", "r_3", "vol_24")


def lagged_design(frame: BarFrame, *, lags: int = 3, window: int = 24, target_bars: int = 1,
                  era_bars: int = 0) -> tuple[Any, Any, Any]:
    """(X, y, era): lagged log returns and realised vol at t-1 against the return over the next
    `target_bars` bars, aligned so nothing in X is later than the bar y starts at. `era` numbers
    rows in blocks of `era_bars` (0 -> one era) for per-era scoring. Numpy only."""
    import numpy as np
    r = frame.log_returns()
    vol = realised_vol(r, window)
    idx = np.arange(window + lags, r.shape[0] - target_bars + 1)
    if idx.shape[0] <= 0:
        return np.zeros((0, lags + 1)), np.zeros(0), np.zeros(0, dtype=int)
    cols = [r[idx - k] for k in range(1, lags + 1)] + [vol[idx - 1]]
    X = np.column_stack(cols)
    if target_bars == 1:
        y = r[idx]
    else:
        c = np.cumsum(np.insert(r, 0, 0.0))
        y = c[idx + target_bars] - c[idx]
    ok = np.isfinite(X).all(axis=1) & np.isfinite(y)
    era = (np.arange(idx.shape[0]) // era_bars) if era_bars > 0 else np.zeros(idx.shape[0],
                                                                                dtype=int)
    return X[ok], y[ok], era[ok]


def api_probe(system_id: str, lib: Any, names: Sequence[str]) -> dict[str, Any]:
    """What an importable-but-not-driven upstream exposes: the measured API surface, so the
    ledger records "imported, these names present" rather than a guess."""
    present = [n for n in names if hasattr(lib, n)]
    return {"kind": "api_surface", "system": system_id,
            "version": str(getattr(lib, "__version__", "") or "UNMEASURED"),
            "expected_names": list(names), "present": present,
            "public_names": sorted(n for n in dir(lib) if not n.startswith("_"))[:40]}
