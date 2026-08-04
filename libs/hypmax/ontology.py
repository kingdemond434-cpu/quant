"""THE RESEARCH ONTOLOGY -- a self-expanding exploration frontier, not a static checklist.

THE PRINCIPAL'S FRAMEWORK (2026-08-01), and its own addendum is the part that matters: turn the
question set into an ONTOLOGY rather than a list, so that

  * every new dataset maps automatically to the questions it can answer,
  * every failed hypothesis raises the EXHAUSTION of the question it came from,
  * every survivor SPAWNS second-order questions that did not exist before,
  * and the system measures coverage per question and prioritises the least-explored,
    highest-expected-value frontier without anyone maintaining a spreadsheet.

That converts a finite list into a search space that grows as it is explored. A checklist is
consumed; an ontology compounds.

WHY THIS IS NOT MORE GOVERNANCE. This desk has 59 audit checks and zero deployed alphas, and the
standing constraint says never add subsystems that do not increase future compounded capital. The
justification here is specific and measurable: the desk has generated 420 hypotheses and cannot
say which regions of the hypothesis space they covered, so it cannot tell "we tested this and it
failed" from "we never looked". Those demand opposite responses. Coverage is the one piece of
information that makes 420 failures INFORMATIVE rather than merely discouraging.

RESEARCH OPTIONALITY MAXIMISATION -- the constitutional addition, and the reason `optionality` is
a first-class term rather than a nice-to-have. A discovery is worth its own alpha PLUS the
research frontier it unlocks. A question that, if answered, opens a new dataset, a new mechanism
family or a new market is worth more than one that closes a leaf, even at equal immediate value,
because it raises the GROWTH RATE of future discovery rather than harvesting the current stock.
Today's discovery making tomorrow's search space larger is what turns research into a compounding
process instead of a depleting one.

Pure and dependency-free. Scores and prioritises; discovers nothing, promotes nothing.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DOMAINS",
    "SEED_QUESTIONS",
    "Question",
    "coverage",
    "exhaustion",
    "load_state",
    "map_dataset",
    "priority",
    "rank_frontier",
    "record_outcome",
    "save_state",
    "spawn_second_order",
]

#: (domain key, human name, base expected value 0..1, base optionality 0..1)
#:
#: EV and OPTIONALITY are scored SEPARATELY and both are needed. Execution questions have high EV
#: and low optionality -- answering one saves money on every trade forever but opens no new search
#: space. Data-discovery questions invert that: a single new dataset can spawn a whole family of
#: hypotheses that were previously impossible to even state. A desk that ranked on EV alone would
#: systematically under-invest in exactly the questions that grow its future capacity.
DOMAINS: dict[str, tuple[str, float, float]] = {
    "ALPHA": ("Alpha Discovery", 0.95, 0.70),
    "FEATURE": ("Feature Discovery", 0.70, 0.60),
    "DATA": ("Data Discovery", 0.85, 0.95),
    "STRUCT": ("Market Structure", 0.90, 0.75),
    "EXEC": ("Execution", 0.80, 0.30),
    "REGIME": ("Regimes", 0.75, 0.55),
    "XMKT": ("Cross-Market", 0.70, 0.65),
    "CRYPTO": ("Crypto-Specific", 0.85, 0.70),
    "BEHAV": ("Behavioural Finance", 0.60, 0.50),
    "INFO": ("Information Discovery", 0.65, 0.85),
    "ML": ("Machine Learning", 0.45, 0.40),
    "PORT": ("Portfolio Construction", 0.80, 0.25),
    "RISK": ("Risk", 0.85, 0.20),
    "PROC": ("Discovery Process", 0.55, 0.60),
    "META": ("Meta-Research", 0.60, 0.80),
    "FRONTIER": ("Long-Term Frontier", 0.50, 1.00),
    "UNKNOWN": ("Unknown-Unknown Discovery", 0.55, 1.00),
    "INFOTH": ("Information-Theoretic Exploration", 0.65, 0.75),
    "COVER": ("Search-Space Coverage", 0.50, 0.70),
    "ADVERS": ("Adversarial Discovery", 0.70, 0.85),
    "TRANSFER": ("Cross-Domain Transfer", 0.55, 0.95),
    "NEGSPACE": ("Negative Space", 0.45, 0.75),
    "GENEALOGY": ("Alpha Genealogy", 0.40, 0.55),
    "DECAY": ("Discovery Decay", 0.55, 0.40),
    "EMERGE": ("Emergence Detection", 0.50, 0.80),
    "RECURSE": ("Recursive Self-Improvement", 0.60, 0.90),
}


@dataclass(frozen=True)
class Question:
    """One exploration frontier. `tags` are what a dataset is matched against."""

    id: str
    domain: str
    text: str
    tags: tuple[str, ...] = ()
    generation: int = 0
    parent: str | None = None

    @property
    def domain_name(self) -> str:
        return DOMAINS.get(self.domain, (self.domain, 0.5, 0.5))[0]


def _q(domain: str, n: int, text: str, *tags: str) -> Question:
    return Question(f"{domain}.{n}", domain, text, tags)


#: THE SEED SET. Generation 0. Every one is a REGION of the search space, never a task -- a
#: question is exhausted only when the region has been explored, and regions spawn sub-regions.
SEED_QUESTIONS: tuple[Question, ...] = (
    # 1 ALPHA
    _q("ALPHA", 1, "Which economically distinct alpha families have never been tested?", "family"),
    _q("ALPHA", 2, "Which existing alpha families are underrepresented?", "family"),
    _q("ALPHA", 3, "Which COMBINATIONS of alpha families have never been explored?", "family"),
    _q("ALPHA", 4, "Which markets show structural inefficiency competitors ignore?", "structure"),
    _q("ALPHA", 5, "Which edges appear ONLY under specific regimes?", "regime"),
    _q("ALPHA", 6, "Which edges disappear under realistic execution?", "execution", "cost"),
    _q("ALPHA", 7, "Which edges become STRONGER combined?", "family"),
    _q("ALPHA", 8, "Which edges are mutually exclusive?", "family"),
    _q("ALPHA", 9, "Which edges survive transaction costs?", "cost", "execution"),
    _q("ALPHA", 10, "Which edges survive FUNDING costs?", "funding", "cost"),
    _q("ALPHA", 11, "Which edges survive liquidity stress?", "liquidity", "depth"),
    _q("ALPHA", 12, "Which edges survive structural breaks?", "regime"),
    # 2 FEATURE
    _q("FEATURE", 1, "Which measurable variables have never been engineered?", "feature"),
    _q("FEATURE", 2, "Which variable COMBINATIONS have never been tested?", "feature"),
    _q("FEATURE", 3, "Which nonlinear transforms create information?", "feature"),
    _q("FEATURE", 4, "Which lag structures matter?", "feature", "lead-lag"),
    _q("FEATURE", 5, "Which interaction terms matter?", "feature"),
    _q("FEATURE", 6, "Which HIDDEN STATE variables exist?", "latent", "depth"),
    _q("FEATURE", 7, "Which temporal aggregations matter?", "feature", "horizon"),
    _q("FEATURE", 8, "Which volatility-adjusted transforms matter?", "vol", "feature"),
    _q("FEATURE", 9, "Which entropy measures matter?", "feature", "entropy"),
    _q("FEATURE", 10, "Which graph representations matter?", "graph", "network"),
    # 3 DATA
    _q("DATA", 1, "Which public datasets remain undiscovered?", "source"),
    _q("DATA", 2, "Which PRIVATE datasets can be reconstructed?", "latent", "reconstruct"),
    _q("DATA", 3, "Which public datasets can be FUSED into something new?", "fuse", "source"),
    _q("DATA", 4, "Which regional datasets are ignored?", "regional", "source"),
    _q("DATA", 5, "Which language ecosystems hold unique information?", "language", "source"),
    _q("DATA", 6, "Which APIs appeared recently?", "source", "new"),
    _q("DATA", 7, "Which archives became searchable?", "source", "archive"),
    _q("DATA", 8, "Which datasets DISAPPEARED?", "source", "negative"),
    _q("DATA", 9, "Which datasets changed methodology?", "source", "provenance"),
    _q("DATA", 10, "Which datasets yield genuine PROPRIETARY derivatives?", "reconstruct", "moat"),
    # 4 STRUCT
    _q("STRUCT", 1, "Where does structural inefficiency ORIGINATE?", "structure"),
    _q("STRUCT", 2, "What incentives create mispricing?", "structure", "incentive"),
    _q("STRUCT", 3, "Which participants systematically LOSE money?", "flow", "participant"),
    _q("STRUCT", 4, "Which participants systematically win?", "flow", "participant"),
    _q("STRUCT", 5, "Where do flows ORIGINATE?", "flow"),
    _q("STRUCT", 6, "Where do flows TERMINATE?", "flow"),
    _q("STRUCT", 7, "What causes FORCED buying?", "forced", "flow"),
    _q("STRUCT", 8, "What causes FORCED selling?", "forced", "liquidation"),
    _q("STRUCT", 9, "Which regulations create opportunities?", "structure", "barrier"),
    _q("STRUCT", 10, "Which exchange mechanics create predictable behaviour?", "venue", "micro"),
    # 5 EXEC
    _q("EXEC", 1, "Where is slippage ASYMMETRIC?", "execution", "cost"),
    _q("EXEC", 2, "Where is liquidity HIDDEN?", "depth", "latent"),
    _q("EXEC", 3, "Where is queue priority exploitable?", "queue", "micro"),
    _q("EXEC", 4, "Where are funding windows exploitable?", "funding"),
    _q("EXEC", 5, "Where are liquidation cascades predictable?", "liquidation", "forced"),
    _q("EXEC", 6, "Which venues execute differently?", "venue"),
    _q("EXEC", 7, "Which execution algorithms dominate?", "execution"),
    _q("EXEC", 8, "Which execution ASSUMPTIONS are wrong?", "execution", "assumption"),
    _q("EXEC", 9, "Which execution costs remain UNMODELLED?", "cost", "execution"),
    # 6 REGIME
    _q("REGIME", 1, "What HIDDEN regimes exist?", "regime", "latent"),
    _q("REGIME", 2, "Which features detect them EARLIEST?", "regime", "lead-lag"),
    _q("REGIME", 3, "Which strategies depend on them?", "regime"),
    _q("REGIME", 4, "Which strategies FAIL under them?", "regime", "risk"),
    _q("REGIME", 5, "How should allocation change across regimes?", "regime", "portfolio"),
    _q("REGIME", 6, "How fast do regimes transition?", "regime", "horizon"),
    _q("REGIME", 7, "Which regime indicators LEAD?", "regime", "lead-lag"),
    _q("REGIME", 8, "Which regime indicators lag?", "regime", "lead-lag"),
    # 7 XMKT
    _q("XMKT", 1, "Which assets LEAD others?", "lead-lag", "xmkt"),
    _q("XMKT", 2, "Which markets transmit information?", "xmkt", "flow"),
    _q("XMKT", 3, "Which markets lag?", "lead-lag", "xmkt"),
    _q("XMKT", 4, "Which markets create SYNTHETIC predictors?", "xmkt", "fuse"),
    _q("XMKT", 5, "Which spreads contain predictive power?", "spread", "xmkt"),
    _q("XMKT", 6, "Which currencies dominate?", "fx", "xmkt"),
    _q("XMKT", 7, "Which commodities matter?", "xmkt"),
    _q("XMKT", 8, "Which crypto SECTORS matter?", "xmkt", "crypto"),
    _q("XMKT", 9, "Which equity sectors matter?", "xmkt"),
    # 8 CRYPTO
    _q("CRYPTO", 1, "Which on-chain metrics remain unused?", "onchain", "crypto"),
    _q("CRYPTO", 2, "Which VALIDATOR behaviours matter?", "onchain", "validator"),
    _q("CRYPTO", 3, "Which bridge flows matter?", "onchain", "flow"),
    _q("CRYPTO", 4, "Which stablecoin mechanics matter?", "stablecoin", "depeg"),
    _q("CRYPTO", 5, "Which governance actions matter?", "onchain", "governance"),
    _q("CRYPTO", 6, "Which staking metrics matter?", "onchain", "validator"),
    _q("CRYPTO", 7, "Which MEV signals matter?", "mev", "micro"),
    _q("CRYPTO", 8, "Which DEX microstructure signals matter?", "dex", "micro"),
    _q("CRYPTO", 9, "Which perpetual FUNDING dynamics matter?", "funding", "crypto"),
    _q("CRYPTO", 10, "Which liquidation mechanics matter?", "liquidation", "forced"),
    # 9 BEHAV
    _q("BEHAV", 1, "Where are humans predictably irrational?", "behaviour"),
    _q("BEHAV", 2, "Which behavioural biases persist?", "behaviour"),
    _q("BEHAV", 3, "Which RETAIL behaviours matter?", "behaviour", "participant"),
    _q("BEHAV", 4, "Which INSTITUTIONAL behaviours matter?", "behaviour", "participant"),
    _q("BEHAV", 5, "Which social behaviours predict flow?", "behaviour", "flow"),
    _q("BEHAV", 6, "Which news structures matter?", "news", "behaviour"),
    _q("BEHAV", 7, "Which narratives propagate?", "news", "behaviour"),
    _q("BEHAV", 8, "Which narratives DECAY?", "news", "decay"),
    # 10 INFO
    _q("INFO", 1, "Which information arrives EARLIEST?", "lead-lag", "source"),
    _q("INFO", 2, "Which sources consistently lead?", "lead-lag", "source"),
    _q("INFO", 3, "Which sources are under-indexed?", "source", "coverage"),
    _q("INFO", 4, "Which LANGUAGES lead?", "language", "lead-lag"),
    _q("INFO", 5, "Which communities lead?", "community", "lead-lag"),
    _q("INFO", 6, "Which repositories appear first?", "repo", "lead-lag"),
    _q("INFO", 7, "Which researchers consistently produce useful work?", "literature"),
    _q("INFO", 8, "Which conferences produce useful ideas?", "literature", "community"),
    # 11 ML
    _q("ML", 1, "Which architectures remain untested?", "ml"),
    _q("ML", 2, "Which representation-learning methods help?", "ml", "feature"),
    _q("ML", 3, "Which self-supervised objectives help?", "ml"),
    _q("ML", 4, "Which embeddings help?", "ml", "feature"),
    _q("ML", 5, "Which graph methods help?", "ml", "graph"),
    _q("ML", 6, "Which CAUSAL methods help?", "ml", "causal"),
    _q("ML", 7, "Which uncertainty estimators help?", "ml", "risk"),
    _q("ML", 8, "Which ensemble methods help?", "ml"),
    # 12 PORT
    _q("PORT", 1, "Which allocation methods DOMINATE Kelly?", "portfolio", "kelly"),
    _q("PORT", 2, "Which risk measures matter?", "portfolio", "risk"),
    _q("PORT", 3, "Which correlations are UNSTABLE?", "portfolio", "correlation"),
    _q("PORT", 4, "Which diversification assumptions fail?", "portfolio", "assumption"),
    _q("PORT", 5, "Which leverage rules maximise E[log wealth]?", "portfolio", "kelly"),
    _q("PORT", 6, "Which rebalancing frequency is optimal?", "portfolio", "cost"),
    _q("PORT", 7, "Which capital constraints matter?", "portfolio"),
    # 13 RISK
    _q("RISK", 1, "Which failure modes remain UNKNOWN?", "risk", "unknown"),
    _q("RISK", 2, "Which assumptions remain untested?", "assumption", "risk"),
    _q("RISK", 3, "Which black swans are ignored?", "risk", "tail"),
    _q("RISK", 4, "Which HIDDEN correlations exist?", "correlation", "risk"),
    _q("RISK", 5, "Which tail events matter?", "tail", "risk"),
    _q("RISK", 6, "Which guardrails are MISSING?", "risk", "rail"),
    _q("RISK", 7, "Which risk metrics fail?", "risk", "assumption"),
    # 14 PROC
    _q("PROC", 1, "Which miners produce UNIQUE information?", "miner", "coverage"),
    _q("PROC", 2, "Which diggers overlap excessively?", "miner", "coverage"),
    _q("PROC", 3, "Which search operators dominate?", "search", "miner"),
    _q("PROC", 4, "Which languages remain underexplored?", "language", "coverage"),
    _q("PROC", 5, "Which source classes remain underexplored?", "source", "coverage"),
    _q("PROC", 6, "Which hypotheses repeatedly SUCCEED?", "genealogy"),
    _q("PROC", 7, "Which repeatedly fail?", "genealogy", "negative"),
    _q("PROC", 8, "Where is marginal information gain DIMINISHING?", "decay", "coverage"),
    _q("PROC", 9, "Which exploration frontiers remain untouched?", "coverage", "unknown"),
    # 15 META
    _q("META", 1, "What are we ASSUMING?", "assumption", "unknown"),
    _q("META", 2, "WHY are we assuming it?", "assumption"),
    _q("META", 3, "What if the OPPOSITE were true?", "assumption", "unknown"),
    _q("META", 4, "Which research directions never get proposed?", "unknown", "coverage"),
    _q("META", 5, "Which hypotheses are IMPOSSIBLE to generate with this architecture?",
       "unknown", "architecture"),
    _q("META", 6, "Which generators underperform?", "generator"),
    _q("META", 7, "Which generators should be MERGED?", "generator"),
    _q("META", 8, "Which should be split?", "generator"),
    _q("META", 9, "Which should be replaced?", "generator"),
    # 16 FRONTIER -- named desks, because each has a genuinely different search prior
    _q("FRONTIER", 1, "What would RENAISSANCE test that we never would?", "adversarial"),
    _q("FRONTIER", 2, "What would TWO SIGMA test?", "adversarial"),
    _q("FRONTIER", 3, "What would HRT test?", "adversarial", "micro"),
    _q("FRONTIER", 4, "What would JUMP test?", "adversarial", "micro"),
    _q("FRONTIER", 5, "What would JANE STREET test?", "adversarial"),
    _q("FRONTIER", 6, "What would DE SHAW test?", "adversarial"),
    _q("FRONTIER", 7, "What would CITADEL test?", "adversarial"),
    _q("FRONTIER", 8, "What would WINTON test?", "adversarial"),
    _q("FRONTIER", 9, "What would AQR test?", "adversarial"),
    _q("FRONTIER", 10, "What would a COMPLETELY DIFFERENT FIELD test?", "transfer"),
    # UNKNOWN-UNKNOWN
    _q("UNKNOWN", 1, "What alpha CLASSES could exist that we have never modelled?", "unknown"),
    _q("UNKNOWN", 2, "Which market mechanisms have NO hypothesis family?", "unknown", "family"),
    _q("UNKNOWN", 3, "Which market assumptions have never been explicitly challenged?",
       "assumption", "unknown"),
    # INFORMATION-THEORETIC
    _q("INFOTH", 1, "Which datasets maximise mutual information with future returns?",
       "source", "entropy"),
    _q("INFOTH", 2, "Which dataset COMBINATIONS create nonlinear information gain?",
       "fuse", "entropy"),
    _q("INFOTH", 3, "Which feature families remain information-ISOLATED?", "feature", "entropy"),
    # COVERAGE
    _q("COVER", 1, "Which regions of hypothesis space have the LOWEST exploration density?",
       "coverage"),
    _q("COVER", 2, "Which languages have the lowest validated source penetration?",
       "language", "coverage"),
    _q("COVER", 3, "Which asset classes remain structurally underexplored?", "coverage", "xmkt"),
    # ADVERSARIAL
    _q("ADVERS", 1, "What would a Renaissance researcher ATTACK first?", "adversarial",
       "assumption"),
    _q("ADVERS", 2, "What would an HFT researcher search that we never search?",
       "adversarial", "micro"),
    _q("ADVERS", 3, "What would a MACRO PM search that crypto researchers ignore?",
       "adversarial", "xmkt"),
    _q("ADVERS", 4, "What would a BLOCKCHAIN researcher search that finance ignores?",
       "adversarial", "onchain"),
    # TRANSFER
    _q("TRANSFER", 1, "What transfers from biology, ecology or epidemiology?", "transfer"),
    _q("TRANSFER", 2, "What transfers from physics, astronomy or meteorology?", "transfer"),
    _q("TRANSFER", 3, "What transfers from neuroscience or network science?", "transfer", "graph"),
    _q("TRANSFER", 4, "What transfers from queueing theory or control theory?",
       "transfer", "queue"),
    _q("TRANSFER", 5, "What transfers from game theory or operations research?", "transfer"),
    _q("TRANSFER", 6, "What transfers from signal processing or linguistics?", "transfer"),
    # NEGATIVE SPACE -- silence is information
    _q("NEGSPACE", 1, "What is NOT being discussed?", "negative", "community"),
    _q("NEGSPACE", 2, "Which topics suddenly disappeared?", "negative", "decay"),
    _q("NEGSPACE", 3, "Which repositories STOPPED updating?", "negative", "repo"),
    _q("NEGSPACE", 4, "Which APIs silently changed?", "negative", "provenance"),
    _q("NEGSPACE", 5, "Which markets became quiet?", "negative", "liquidity"),
    # GENEALOGY
    _q("GENEALOGY", 1, "What did each survivor DESCEND from?", "genealogy"),
    _q("GENEALOGY", 2, "Which datasets ENABLED it?", "genealogy", "source"),
    _q("GENEALOGY", 3, "Which search path found it?", "genealogy", "search"),
    # DECAY
    _q("DECAY", 1, "Which alpha families are SATURATING?", "decay", "family"),
    _q("DECAY", 2, "Which search operators are becoming less productive?", "decay", "search"),
    _q("DECAY", 3, "Which datasets are losing incremental value?", "decay", "source"),
    _q("DECAY", 4, "Which communities have become too mainstream?", "decay", "community"),
    # EMERGENCE
    _q("EMERGE", 1, "Which weak signals collectively indicate NEW market structure?",
       "emergence", "structure"),
    _q("EMERGE", 2, "New participant behaviour?", "emergence", "participant"),
    _q("EMERGE", 3, "New liquidity regimes?", "emergence", "liquidity"),
    _q("EMERGE", 4, "New execution dynamics?", "emergence", "execution"),
    _q("EMERGE", 5, "New funding mechanisms?", "emergence", "funding"),
    # RECURSIVE
    _q("RECURSE", 1, "If we rebuilt the pipeline from scratch today, what changes?",
       "architecture"),
    _q("RECURSE", 2, "Which component is NOW the largest bottleneck?", "architecture"),
    _q("RECURSE", 3, "Which single structural change most raises lifetime validated alpha?",
       "architecture"),
)

#: Attempts at which a question is considered thoroughly explored. Saturating rather than linear:
#: the 1st attempt at an untouched region teaches far more than the 30th, and a linear measure
#: would keep an over-mined region looking fresh long after it stopped paying.
_SATURATION = 25.0

#: No region ever reaches zero priority. A question is deprioritised by exhaustion, never
#: deleted -- a barren region that a new dataset reopens is exactly where a desk finds what
#: everyone else gave up on, and that only works if it is still reachable.
_REVIVAL_FLOOR = 0.02


def coverage(attempts: int) -> float:
    """0..1 exploration density. Saturating -- diminishing returns are the actual shape."""
    return 1.0 - math.exp(-max(0, attempts) / _SATURATION)


def exhaustion(attempts: int, survivors: int) -> float:
    """0..1 evidence that a region is BARREN, not merely visited.

    Coverage and exhaustion are different questions and conflating them is the trap. Thirty
    attempts with two survivors is a RICH region worth mining harder; thirty with none is a
    barren one. Only the second should suppress priority -- and even then never to zero, because
    a region can be reopened by a new dataset, and negative knowledge is reversible here.
    """
    if attempts <= 0:
        return 0.0
    if survivors > 0:
        return 0.0
    return coverage(attempts)


def priority(q: Question, attempts: int = 0, survivors: int = 0,
             state: dict[str, Any] | None = None) -> float:
    """What to explore NEXT: expected value x unexplored-ness x optionality.

    Multiplicative for the same reason EVIG is: a fully exhausted region is worth nothing however
    high its base EV, and a question with no optionality that is also low EV should not be rescued
    by being untouched. Novelty alone is not a reason to explore.
    """
    _, ev, opt = DOMAINS.get(q.domain, (q.domain, 0.5, 0.5))
    if state:
        s = state.get(q.id, {})
        attempts = int(s.get("attempts", attempts))
        survivors = int(s.get("survivors", survivors))
    # FLOORED, and this module's own test is why. Unfloored, a heavily-worked barren region drives
    # both terms to zero and its priority to EXACTLY 0.0 -- permanently unreachable, never
    # revisited, no matter what data arrives later. That contradicts the desk's own law that
    # negative knowledge is reversible, and it is the more dangerous direction of error: an
    # over-explored region that a new dataset reopens is precisely where a desk finds what
    # everyone else gave up on. The floor makes exhaustion a strong DEPRIORITISATION, never a
    # deletion.
    unexplored = max(_REVIVAL_FLOOR, 1.0 - coverage(attempts))
    barren = max(_REVIVAL_FLOOR, 1.0 - exhaustion(attempts, survivors))
    # A second-order question inherits urgency from having been EARNED by a real discovery: the
    # desk already has evidence that its neighbourhood contains something.
    earned = 1.0 + 0.25 * min(q.generation, 4)
    return round(ev * opt * unexplored * barren * earned, 6)


def rank_frontier(questions: tuple[Question, ...] | list[Question] = SEED_QUESTIONS,
                  state: dict[str, Any] | None = None,
                  limit: int | None = None) -> list[dict[str, Any]]:
    """The exploration frontier, highest priority first."""
    state = state or {}
    rows: list[dict[str, Any]] = []
    for q in questions:
        s = state.get(q.id, {})
        a, v = int(s.get("attempts", 0)), int(s.get("survivors", 0))
        rows.append({"id": q.id, "domain": q.domain_name, "text": q.text,
                     "generation": q.generation, "attempts": a, "survivors": v,
                     "coverage": round(coverage(a), 3),
                     "exhaustion": round(exhaustion(a, v), 3),
                     "priority": priority(q, a, v)})
    rows.sort(key=lambda d: -float(d["priority"]))
    return rows[:limit] if limit else rows


def map_dataset(name: str, description: str = "",
                questions: tuple[Question, ...] | list[Question] = SEED_QUESTIONS,
                ) -> list[str]:
    """Which questions a new dataset can help answer. Tag match on name + description.

    Deliberately generous: a false match costs a reader one glance, a MISSED match means a dataset
    lands and nobody realises it reopens a region that was written off as exhausted. The whole
    point of the mapping is that arrival of data should automatically revive questions.
    """
    hay = f"{name} {description}".lower()
    toks = set(re.split(r"[^a-z0-9]+", hay)) - {""}
    hits = []
    for q in questions:
        if any(t in hay or t in toks for t in q.tags):
            hits.append(q.id)
    return hits


def spawn_second_order(parent: Question, discovery: str) -> tuple[Question, ...]:
    """A survivor creates questions that did not exist before it.

    THIS IS WHAT MAKES THE ONTOLOGY SELF-EXPANDING rather than consumed. A finite checklist shrinks
    as it is worked; a search space that grows three new regions per discovery compounds. The four
    spawned here are the four that historically pay: does it generalise, what regime breaks it,
    what does it combine with, and what NEW data would sharpen it.
    """
    g = parent.generation + 1
    base = f"{parent.id}.{g}"
    return (
        Question(f"{base}a", parent.domain, f"Does '{discovery}' generalise to adjacent "
                 f"markets, venues or horizons?", (*parent.tags, "generalise"), g, parent.id),
        Question(f"{base}b", "REGIME", f"Under which regime does '{discovery}' break, and what "
                 f"detects that regime earliest?", ("regime", "lead-lag"), g, parent.id),
        Question(f"{base}c", "ALPHA", f"What does '{discovery}' COMBINE with -- and what is it "
                 f"mutually exclusive with?", ("family", "combination"), g, parent.id),
        Question(f"{base}d", "DATA", f"What new dataset would sharpen '{discovery}', and can we "
                 f"MANUFACTURE it rather than buy it?", ("source", "reconstruct", "moat"),
                 g, parent.id),
    )


def record_outcome(state: dict[str, Any], question_id: str, *, survived: bool) -> dict[str, Any]:
    """Every tested hypothesis updates the region it came from -- pass or fail.

    Failures are the more valuable update and the one a naive design drops: they are what turns
    'we never looked' into 'we looked and it is barren', and those demand opposite responses.
    """
    s = state.setdefault(question_id, {"attempts": 0, "survivors": 0})
    s["attempts"] = int(s.get("attempts", 0)) + 1
    if survived:
        s["survivors"] = int(s.get("survivors", 0)) + 1
    return state


def load_state(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(Path(path).read_text("utf-8"))
        return d.get("questions", d) if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict[str, Any], spawned: list[Question] | None = None) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "questions": state,
        "spawned": [{"id": q.id, "domain": q.domain, "text": q.text, "tags": list(q.tags),
                     "generation": q.generation, "parent": q.parent} for q in (spawned or [])],
    }, indent=1), "utf-8")


@dataclass
class Ontology:
    """Seed questions plus everything discovery has spawned since."""

    questions: list[Question] = field(default_factory=lambda: list(SEED_QUESTIONS))

    def add(self, qs: tuple[Question, ...] | list[Question]) -> None:
        known = {q.id for q in self.questions}
        self.questions.extend(q for q in qs if q.id not in known)

    def __len__(self) -> int:
        return len(self.questions)
