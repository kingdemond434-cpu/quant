"""THE INSTITUTIONAL CAPABILITY ONTOLOGY -- what an external finding is ABOUT.

    "This prevents every article from becoming another random module."   -- the principal

WHY A FIXED VOCABULARY IS THE FIRST FILE. A frontier miner without one produces a module per
article: fifty firms describe distributed training fifty ways, and the desk implements it fifty
times under fifty names, each one a new organ nobody bills. That is the failure this whole desk
has already paid for in another form -- 27 decision-affecting organs that no rent line could
price -- and a meta-miner is the fastest possible way to reproduce it at scale.

So every finding maps to one or more of these groups BEFORE anything else happens to it, and the
groups are what the gap graph, the ROI ranking and the capability matrix all key on. Two firms
describing the same capability differently collapse to one row, which is the entire point.

EACH GROUP CARRIES THE DESK'S OWN ADDRESS FOR IT. A capability domain that cannot say which of our
modules would change is not a domain, it is a topic -- and a topic cannot be compared to what we
have, priced, or closed. `owner` is that address: the module or report on this tree that either
implements the capability or is where an implementation would land.

AND EACH CARRIES ITS ALLOCATOR LEVEL, so a frontier finding inherits the currency the rest of the
desk spends. `libs.ops.allocators` declares six nested levels on one currency; a capability that
improves data acquisition is an INFORMATION-level gain, one that improves fill modelling is an
EXECUTION-level gain, and the difference decides which budget pays for it and which ledger prices
it. A finding with no level is a finding with no price.
"""
from __future__ import annotations

from dataclasses import dataclass

#: The allocator levels a capability can improve, in the dependency order `libs.ops.allocators`
#: declares. `frontier` is the seventh, added with this package: which external capability
#: deserves replication effort at all.
LEVELS = ("frontier", "information", "research", "compute", "forecast", "capital", "execution")


@dataclass(frozen=True)
class Capability:
    """One canonical capability group: what it is, who owns it here, what it improves."""

    name: str
    #: Which allocator's currency a gain here is denominated in.
    level: str
    #: The module or report on THIS tree that implements it, or where an implementation lands.
    #: Empty means the desk has no address for it at all -- itself the most useful finding a
    #: frontier miner can produce, and the reason this field is never optional in spirit.
    owner: str
    #: One sentence: what having this capability lets a desk do that lacking it does not.
    what: str


#: The canonical groups. DELIBERATELY FLAT AND FINITE. A tree of sub-capabilities would let every
#: article invent a new leaf, which is the vocabulary explosion this file exists to stop; when a
#: finding genuinely does not fit, that is a registry decision made once, not per article.
CAPABILITIES: tuple[Capability, ...] = (
    # ------------------------------------------------------------------ information
    Capability("DATA", "information", "desks/mt5/research/data_prospector.py",
               "how many independent economic observations the desk can see at all"),
    Capability("DATA_QUALITY", "information", "scripts/check_pit.py",
               "whether an observation carries the time it was actually knowable"),
    Capability("DATA_ACQUISITION", "information", "desks/mt5/research/data_prospector.py",
               "turning an identified information family into an ingested point-in-time series"),
    Capability("ALT_DATA", "information", "",
               "economic observation outside price and calendar: flows, physical, text"),
    Capability("MICROSTRUCTURE_DATA", "information", "desks/mt5/recorders/tick_recorder.py",
               "the desk's own tape -- ticks, spreads, depth -- which cannot be backfilled"),
    # ------------------------------------------------------------------ research
    Capability("FEATURES", "research", "desks/mt5/research/feature_roi.py",
               "turning observations into inputs a model can use, and retiring dead ones"),
    Capability("REPRESENTATION_LEARNING", "research", "",
               "a learned latent state of the market rather than hand-specified features"),
    Capability("NLP", "research", "desks/mt5/macro/assess.py",
               "reading unstructured text into structured, dated, tradeable claims"),
    Capability("MULTIMODAL", "research", "",
               "combining text, price and cross-asset response in one model of an event"),
    Capability("SELF_SUPERVISED", "research", "",
               "learning structure from unlabelled market data, of which there is far more"),
    Capability("ALPHA_DISCOVERY", "research", "desks/mt5/research/edge_search.py",
               "generating candidate mechanisms faster than they are exhausted"),
    Capability("EXPERIMENT_SEARCH", "research", "libs/research/bandit.py",
               "choosing which hypothesis to spend the next research pass on"),
    Capability("META_RESEARCH", "research", "desks/mt5/research/research_pnl.py",
               "learning which kinds of research produce survivors, and funding those"),
    Capability("FAILURE_MINING", "research", "libs/research/graveyard_model.py",
               "treating the record of what did not work as an asset, not as waste"),
    # ------------------------------------------------------------------ compute
    Capability("COMPUTE", "compute", "libs/ops/compute_ledger.py",
               "knowing what a research run costs, without which nothing can be rationed"),
    Capability("DISTRIBUTED_TRAINING", "compute", "",
               "running many experiments at once rather than many in sequence"),
    Capability("CACHING", "compute", "",
               "never recomputing an identical feature matrix, replay or world sample"),
    Capability("STORAGE", "compute", "desks/mt5/data/universe/",
               "holding enough history, at enough resolution, to ask a question twice"),
    Capability("RESEARCH_PRODUCTIVITY", "compute", "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",
               "idea to out-of-sample result latency -- the metric compute buys"),
    # ------------------------------------------------------------------ forecast
    Capability("FORECASTING", "forecast", "desks/mt5/research/shadow_forward.py",
               "a dated, scoreable claim about a future return distribution"),
    Capability("ENSEMBLES", "forecast", "",
               "combining predictions whose ERRORS are independent, not whose returns are"),
    Capability("MIXTURE_OF_EXPERTS", "forecast", "",
               "specialists per regime with a gate that learns which one to believe"),
    Capability("CAUSAL_MODELS", "forecast", "desks/mt5/research/world_causal_graph.py",
               "why a relationship holds, so its failure is predictable rather than surprising"),
    Capability("CROSS_ASSET", "forecast", "desks/mt5/mt5desk/family_lead_lag.py",
               "one instrument's information priced into another's next move"),
    Capability("GRAPH_MODELS", "forecast", "",
               "the market as a graph of relationships rather than a list of instruments"),
    # ------------------------------------------------------------------ validation
    Capability("VALIDATION", "research", "desks/mt5/research/universal_gate.py",
               "refusing an edge that only exists in the sample that found it"),
    Capability("MULTIPLICITY", "research", "desks/mt5/research/multiplicity.py",
               "charging for every trial, so a wide search cannot buy significance"),
    Capability("LEAKAGE", "research", "libs/validation/shift_leak.py",
               "detecting information that could not have been known at decision time"),
    Capability("LOCKBOX", "research", "libs/validation/replay2.py",
               "evidence held back and spent once, so it cannot be optimised against"),
    Capability("ROBUSTNESS", "research", "libs/validation/redteam.py",
               "surviving a hostile reading of the same evidence"),
    Capability("STRESS", "research", "libs/portfolio/rails.py",
               "surviving worlds more extreme than the sample contains"),
    # ------------------------------------------------------------------ capital
    Capability("PORTFOLIO", "capital", "desks/mt5/research/pf_allocator.py",
               "allocating so the book grows, not so each sleeve looks good alone"),
    Capability("ELOG", "capital", "libs/portfolio/robust_elog.py",
               "maximising expected log wealth rather than a ratio"),
    Capability("BREADTH", "capital", "desks/mt5/reports/EFFECTIVE_BREADTH.json",
               "counting BETS rather than labels: independent sources of return"),
    Capability("FACTOR_RISK", "capital", "desks/mt5/macro/factors.py",
               "knowing what the book is actually exposed to underneath its names"),
    Capability("TAIL_RISK", "capital", "libs/portfolio/rails.py",
               "bounding the loss that ends compounding, which no average can price"),
    Capability("CAPACITY", "capital", "",
               "what an edge is worth AT OUR SIZE, which is not what it is worth at any size"),
    # ------------------------------------------------------------------ execution
    Capability("EXECUTION", "execution", "desks/mt5/mt5desk/execution_registry.py",
               "the fraction of a predicted edge that survives contact with the venue"),
    Capability("MARKET_IMPACT", "execution", "",
               "what our own order does to the price we get"),
    Capability("FILL_MODELS", "execution", "desks/mt5/mt5desk/fill_surface.py",
               "predicting the fill before sending, so the choice can be made"),
    Capability("ORDER_POLICY", "execution", "desks/mt5/mt5desk/execution_registry.py",
               "market, passive, split or wait -- chosen on evidence rather than by default"),
    # ------------------------------------------------------------------ event intelligence
    Capability("EVENT_INTELLIGENCE", "information", "desks/mt5/macro/run_macro_intel.py",
               "scheduled and unscheduled information, classified and priced before the move"),
    Capability("MACRO", "information", "desks/mt5/macro/factors.py",
               "the state of the world the book is being held in"),
    Capability("EXPECTATIONS", "information", "desks/mt5/macro/prices.py",
               "surprise measured against what was PRICED, not against the previous print"),
    Capability("GEOPOLITICS", "information", "",
               "unscheduled structural events that reprice whole factor complexes"),
    # ------------------------------------------------------------------ operations
    Capability("AGENT_ORGANIZATION", "research", "desks/mt5/research/research_supervisor.py",
               "who does which research, and how that is decided"),
    Capability("RESEARCH_GOVERNOR", "frontier", "libs/ops/allocators.py",
               "one currency across every resource the desk spends"),
    Capability("OPS", "compute", "desks/mt5/scripts/stall_watch.ps1",
               "the desk running at all, unattended, for weeks"),
    Capability("REPRODUCIBILITY", "compute", "scripts/release_manifest.py",
               "reconstructing exactly which code and data produced a result"),
    Capability("MONITORING", "compute", "desks/mt5/scripts/build_zentech_state.py",
               "knowing a component is dead before its absence costs money"),
    Capability("RECOVERY", "compute", "scripts/run_organ_er.py",
               "a dead component coming back without a person noticing it died"),
)

BY_NAME: dict[str, Capability] = {c.name: c for c in CAPABILITIES}
NAMES: frozenset[str] = frozenset(BY_NAME)


def map_to_capabilities(text: str) -> tuple[str, ...]:
    """Capability groups a finding's text plausibly concerns, by exact group-name mention.

    DELIBERATELY LITERAL, and this is a design decision rather than a shortcut. A fuzzy mapper
    -- keyword lists, embeddings, an LLM asked "which of these fifty" -- assigns SOMETHING to
    every article, and a miner that always finds a capability always finds a gap. Returning an
    empty tuple for a finding whose extractor did not name a group is the correct answer: it goes
    back to extraction, where naming the group is the job, rather than forward with a guess.
    """
    upper = (text or "").upper()
    return tuple(sorted(n for n in NAMES if n in upper))


def unaddressed() -> tuple[str, ...]:
    """Capability groups this desk has NO module for.

    The most useful single query in this package: not "what are we bad at" but "what have we not
    built at all". A gap in a capability we own is an improvement; a gap in one we have no address
    for is a category of work the desk has never done, and those are where the largest measured
    differences to an elite organisation live.
    """
    return tuple(c.name for c in CAPABILITIES if not c.owner)
