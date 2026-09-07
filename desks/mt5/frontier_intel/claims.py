"""Turn what an organisation is SAID to do into something this desk can falsify.

    claim -> strip the mythology -> mechanism proposition -> falsifier -> the existing gauntlet

THE GAP THIS FILLS. `registry.py` already settles the epistemics -- an unverified claim is a
hypothesis, is welcome, and is never privileged by its source -- and `roi.py` already keeps
P(mechanism useful) separate from P(claim accurate) so a rumour with a cheap test is not
discounted at all. What neither does is READ a claim. `frontier_supervisor.extract()` maps a
finding to capability groups with `ontology.map_to_capabilities`, which is deliberately literal:
it matches only text that already NAMES a group. A forum post saying

    "guy who used to work there says they run thousands of small models and average them"

names no group, so it mapped to nothing and left the queue as an unreadable blob of prose. The
claim was admitted and then went nowhere, which is the same outcome as refusing it while looking
like the opposite.

WHAT THE COMPILER ACTUALLY DOES, and what it deliberately does not. It does not decide whether
the firm does the thing. It does not reconstruct anyone's model. It takes the technical
vocabulary out of the sentence and emits the general proposition that vocabulary implies,
together with the falsifier that would kill it here:

    claim        "they run thousands of small models and average them"
    mythology    who said it, which firm, whether they worked there   <- DISCARDED
    mechanism    large ensembles of weak, low-correlated conditional predictors may
                 outperform concentrated high-conviction models on this desk's universe
    capability   ENSEMBLES
    falsifier    an ensemble of N weak learners does not beat the best single learner
                 out-of-sample after costs on the same cells

The employment claim can be a complete fabrication and the mechanism is still testable. That
asymmetry is the whole reason weak sources are worth mining: A FALSE SOURCE CLAIM CAN STILL
GENERATE A TRUE HYPOTHESIS, and the desk's own gates decide which.

THREE THINGS HERE EXIST TO STOP THE OBVIOUS ABUSES.

GENEALOGY, because ten reposts are not ten confirmations. A single origin travelling through a
forum, two aggregators and a translation arrives as four rows, and any counter that treats
"mentioned by four sources" as corroboration has built a machine that believes whatever is most
viral. `independent_sources` clusters near-duplicates by shingle overlap and counts ORIGINS. This
matters most in exactly the ecosystems the principal asked to mine, where the same sentence
propagates across many platforms and languages.

TWO SCORES PER SOURCE, because reliability and usefulness are different properties and collapsing
them throws away the good half. A rumour community can be wrong about facts most of the time and
still be an excellent generator of ideas worth testing; a careful publication can be accurate and
say nothing this desk can act on. `truth_score` gates belief in the CLAIM, `idea_yield` gates
attention to the SOURCE, and they are learned from different ledgers.

THE MNPI FENCE, which is not a disclaimer. A claim that presents itself as confidential internal
material is refused capital authority outright and marked so no downstream stage can promote it.
The desk replicates observable PRINCIPLES; a principle recovered from a paper is more durable
than a fact taken from somewhere it should not have been, and the general form of an idea --
"short-horizon liquidity imbalance may matter" -- is public regardless of who said it first.

NOTHING HERE CREATES A SECOND ALPHA FACTORY. When a mechanism implies a tradeable hypothesis it
is handed to the existing research queue in the existing shape, and the ten gates judge it beside
every other candidate. This organ closes the PROCESS gap; the alpha gap stays where it is.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "frontier_intel" / "data"
TRUTH_LEDGER = DATA / "source_truth.jsonl"
YIELD_LEDGER = DATA / "source_idea_yield.jsonl"

#: Words that carry no technical content and exist only to attach a claim to a person or firm.
#: Removed before the proposition is formed, so the mechanism is judged on its own terms rather
#: than on whose name is attached to it -- the same reason `roi.value` excludes source credibility.
_MYTHOLOGY = re.compile(
    r"\b(allegedly|reportedly|rumou?r(?:ed|s)?|apparently|supposedly|i heard|"
    r"someone said|a friend|ex[- ]employee|former employee|used to work|insider|"
    r"anonymous|leaked|sources say|word is|claims? that|it is said)\b",
    re.I,
)

#: A claim that presents itself as confidential internal material. Such a claim may still open an
#: investigation into the GENERAL principle, but it can never reach capital: see `mnpi_guard`.
_CONFIDENTIAL = re.compile(
    r"\b(confidential|internal only|not public|proprietary source code|"
    r"stolen|non[- ]public|nda|under embargo|material non[- ]public)\b",
    re.I,
)


def _v(body: str) -> re.Pattern[str]:
    """Compile one vocabulary alternation, tolerating the plural.

    MECHANICAL, BECAUSE THE ALTERNATIVE WAS TWENTY HAND-PATCHES. Written the obvious way, every
    entry ends in `\\b`, so `graph neural network` matches and `graph neural networkS` does not --
    the word boundary is satisfied by the pattern's end but the trailing `s` is still a word
    character, so the match fails. That is invisible in review and fatal in use: the plural is how
    people actually write these phrases ("they use graph neural networks", "gpu clusters",
    "embeddings"), and every miss is a claim that reaches the queue as unreadable prose.

    Auditing twenty regexes by eye for a defect that looks like nothing is how the miss got there
    in the first place, so the suffix is applied once, here, to all of them.
    """
    return re.compile(rf"\b(?:{body})(?:e?s)?\b", re.I)


@dataclass(frozen=True)
class Mechanism:
    """One testable proposition recovered from a claim.

    `capability` names an `ontology` group EXACTLY, which is what makes the literal mapper work
    downstream: the compiler's job is to do the naming that `map_to_capabilities` refuses to guess.
    """

    capability: str
    proposition: str
    falsifier: str
    implies_alpha: bool = False


#: THE VOCABULARY TABLE. Each entry is (pattern, Mechanism). A curated table rather than a model,
#: for the same reason `ontology.map_to_capabilities` is literal: a fuzzy extractor assigns
#: SOMETHING to every sentence, and a miner that always finds a mechanism always finds a gap. An
#: unmatched claim is not a failure here -- it goes to `unknowns` as a possible capability this
#: desk's taxonomy does not yet contain, which is where the genuinely new things arrive.
#:
#: EVERY PROPOSITION IS WRITTEN TO BE FALSE-ABLE ON THIS DESK'S OWN UNIVERSE. "They use GPUs" is
#: not a mechanism; "reducing idea-to-result latency raises survivors per research hour" is. The
#: function a capability serves is what gets replicated, never the vanity scale of it.
MECHANISMS: tuple[tuple[re.Pattern[str], Mechanism], ...] = (
    # The adjective slot is not a nicety: the phrasing that actually occurs in the wild is
    # "thousands of SMALL models", "hundreds of WEAK submodels", "lots of TINY predictors".
    # A pattern that demands the noun immediately after the count matches the way the idea is
    # written in a paper abstract and misses the way it is written on a forum -- which is
    # precisely backwards, because the forum is the source the literal mapper already failed on.
    (_v(r"(thousands?|hundreds?|many|lots) of [\w\s-]{0,24}?"
                r"(models?|submodels?|predictors?|learners?)"
                r"|model zoo|ensembl\w+|averag\w+ (over|across) (them|the )?\w*models?"
                r"|weak learners?"),
     Mechanism("ENSEMBLES",
               "large ensembles of weak, low-correlated conditional predictors may outperform "
               "concentrated high-conviction models after costs",
               "an ensemble of N weak learners does not beat the best single learner "
               "out-of-sample after costs on the same cells",
               implies_alpha=True)),
    (_v(r"representation learning|embedding|latent (space|state|factor)|"
                r"foundation model|self[- ]supervised|pre[- ]train\w+"),
     Mechanism("REPRESENTATION_LEARNING",
               "a learned latent market state may carry predictive information that "
               "hand-specified features do not",
               "a learned representation adds no out-of-sample skill over the existing "
               "feature set on the same horizons")),
    (_v(r"graph (neural )?network|gnn|cross[- ]asset graph|lead[- ]lag (map|graph)|"
                r"relationship graph"),
     Mechanism("GRAPH_MODELS",
               "modelling instruments jointly as a dynamic graph may beat treating each "
               "instrument as independent",
               "a joint graph model does not beat per-instrument models out-of-sample "
               "after costs",
               implies_alpha=True)),
    (_v(r"mixture of experts|moe|gating (model|network)|specialist models?|"
                r"regime[- ]specific models?"),
     Mechanism("MIXTURE_OF_EXPERTS",
               "routing between state-specialised predictors may beat one model fitted "
               "across all states",
               "a gated mixture does not beat the single pooled model out-of-sample",
               implies_alpha=True)),
    (_v(r"alternative data|satellite|shipping|freight|weather|inventor\w+|"
                r"search (trends|volume)|card (spend|transactions)|web scrap\w+"),
     Mechanism("ALT_DATA",
               "economic observation outside price and calendar may carry information the "
               "desk's current inputs do not",
               "adding the source changes no forecast's out-of-sample skill: it pays no rent "
               "in the dataset ablation")),
    (_v(r"nlp|language model|text (analysis|mining)|transcripts?|filings?|"
                r"news (analysis|reaction)|sentiment (model|analysis)"),
     Mechanism("NLP",
               "structured, dated claims extracted from public text may predict reaction "
               "beyond the numeric surprise alone",
               "text-derived features add nothing to a model that already sees the numeric "
               "surprise and the state")),
    (_v(r"petabyte|10 ?pb|data ?lake|thousands of (data )?sources|"
                r"100,?000\+? (data )?(types|sources|signals)"),
     Mechanism("DATA",
               "breadth of independent economic observation, not count of derived signals, "
               "is what raises effective breadth",
               "added sources raise the signal count without raising effective independent "
               "breadth, so the book's N_eff does not move")),
    (_v(r"distributed training|gpu cluster|hpc|compute (platform|infrastructure)|"
                r"training infrastructure|experiment (scheduler|throughput)"),
     Mechanism("DISTRIBUTED_TRAINING",
               "reducing idea-to-result latency raises survivors per research hour, which is "
               "the function the hardware serves",
               "halving experiment latency does not raise survivors per research hour")),
    (_v(r"caching|feature store|memoi[sz]\w+|reuse of (intermediate|computed)"),
     Mechanism("CACHING",
               "never recomputing an identical intermediate lets a small machine act far "
               "larger than it is",
               "cache hits do not reduce wall-clock per experiment at this desk's grid size")),
    (_v(r"market impact|slippage model|fill (model|probability)|"
                r"execution (algo|policy|research)|order (routing|placement)|vwap|twap"),
     Mechanism("MARKET_IMPACT",
               "modelling the cost of the order rather than assuming it recovers alpha that "
               "the forecast already found",
               "the modelled cost does not track realised markout on this desk's own fills")),
    (_v(r"reinforcement learning|rl agent|policy gradient|bandit"),
     Mechanism("ORDER_POLICY",
               "a learned execution policy may beat a fixed rule, but only once the "
               "simulator is calibrated against real fills",
               "the learned policy's advantage disappears when the twin is replaced by "
               "realised fills -- i.e. it learned simulator artefacts")),
    (_v(r"tail (risk|hedge)|drawdown control|stress (test|scenario)|"
                r"crisis alpha|convexity"),
     Mechanism("TAIL_RISK",
               "sleeves with positive expectation conditional on book stress permit a "
               "higher growth-optimal heat elsewhere",
               "the candidate's conditional expectation under book stress is not positive")),
    (_v(r"capacity|aum constraint|scal\w+ limits?|liquidity constraint"),
     Mechanism("CAPACITY",
               "an edge's value is a function of the size traded, and small size is this "
               "desk's structural advantage rather than its limitation",
               "the edge's expectation at this desk's actual size is not materially better "
               "than at institutional size")),
    (_v(r"walk[- ]forward|purged|combinatorial|cpcv|deflated sharpe|"
                r"multiple testing|lockbox|holdout"),
     Mechanism("MULTIPLICITY",
               "charging for the number of hypotheses tried is what separates a discovery "
               "from the best of many noises",
               "the correction does not change which candidates survive, i.e. it is not "
               "binding on this desk's search")),
    (_v(r"point[- ]in[- ]time|look[- ]?ahead|survivorship|leakage|"
                r"restatement|revision"),
     Mechanism("LEAKAGE",
               "an observation is only usable at the time it was actually knowable, and "
               "revisions make that different from the timestamp on the row",
               "no candidate's result changes when the input is restricted to its "
               "point-in-time value")),
    (_v(r"kelly|log ?wealth|growth[- ]optimal|geometric (growth|mean)|"
                r"portfolio construction|risk parity"),
     Mechanism("ELOG",
               "sizing to maximise expected log wealth dominates sizing to a target "
               "volatility or a fixed fraction",
               "the growth-optimal book does not beat the current sizing rule on "
               "out-of-sample log growth")),
    (_v(r"effective breadth|n_?eff|independent (signals|bets)|"
                r"decorrelat\w+|orthogonal\w+"),
     Mechanism("BREADTH",
               "the count of signals is irrelevant; the count of INDEPENDENT ones is what "
               "raises growth",
               "adding the candidate raises signal count without raising the book's "
               "effective independent breadth")),
    (_v(r"alpha decay|crowding|edge (decay|half[- ]life)|arms? race"),
     Mechanism("META_RESEARCH",
               "an edge's remaining life is itself predictable, so capital can be withdrawn "
               "before realised expectancy collapses",
               "the mortality model does not rank retired sleeves above surviving ones "
               "ahead of their retirement")),
    (_v(r"nowcast|expectations?|consensus|surprise index|economic surprise|"
                r"implied (expectation|move)"),
     Mechanism("EXPECTATIONS",
               "the tradeable quantity is the surprise against what was ALREADY PRICED, "
               "not the change against the previous print",
               "surprise-versus-implied predicts reaction no better than "
               "actual-minus-previous")),
    (_v(r"counterfactual|what[- ]if|regret|attribution"),
     Mechanism("META_RESEARCH",
               "scoring the decisions not taken turns every pass into training data, not "
               "only the ones that traded",
               "regret decomposition does not identify a stage whose repair changes "
               "realised growth")),
)


@dataclass
class Claim:
    """One public statement, before anything has been decided about it."""

    text: str
    source: str = ""
    firm: str = ""
    url: str = ""
    grade: str = "D"
    language: str = "en"
    retrieved_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat())

    def key(self) -> str:
        return hashlib.sha256(
            f"{self.url}|{self.source}|{self.text[:400]}".encode()
        ).hexdigest()[:16]


def strip_mythology(text: str) -> str:
    """The claim with attribution language removed, so the proposition stands alone.

    Whether the poster worked there is a question about the poster. Whether the technique helps
    is a question about the technique, and only the second one has an experiment attached.
    """
    out = _MYTHOLOGY.sub(" ", text or "")
    return re.sub(r"\s+", " ", out).strip()


def mnpi_guard(text: str) -> tuple[bool, str]:
    """(blocked, why) -- whether the claim presents itself as confidential material.

    BLOCKS CAPITAL AUTHORITY, NOT DISCOVERY. The general principle a confidential-sounding claim
    gestures at is usually public anyway ("short-horizon liquidity imbalance may matter" is in
    every microstructure textbook), and that general form remains testable with lawful data. What
    must never happen is a position sized from something whose only support is material somebody
    should not have published.
    """
    m = _CONFIDENTIAL.search(text or "")
    if not m:
        return False, ""
    return True, (
        f"claim presents itself as confidential material ({m.group(0)!r}): capital authority "
        "refused; only the general, independently testable principle may proceed"
    )


def to_mechanisms(text: str) -> list[Mechanism]:
    """Every mechanism proposition the claim's technical vocabulary implies.

    A list, not one: a sentence about "thousands of submodels trained on a GPU cluster" is a claim
    about ENSEMBLES and about DISTRIBUTED_TRAINING, and those are separately testable with
    separately measurable rent. Collapsing them to a single best match would silently drop half
    the information in the most informative claims.
    """
    stripped = strip_mythology(text)
    seen: set[tuple[str, str]] = set()
    out: list[Mechanism] = []
    for pattern, mech in MECHANISMS:
        if not pattern.search(stripped):
            continue
        ident = (mech.capability, mech.proposition)
        if ident in seen:
            continue
        seen.add(ident)
        out.append(mech)
    return out


def _shingles(text: str, n: int = 5) -> frozenset[str]:
    words = re.findall(r"[a-z0-9]+", strip_mythology(text).lower())
    if len(words) < n:
        return frozenset([" ".join(words)]) if words else frozenset()
    return frozenset(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))


def _overlap(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def genealogy(claims: list[Claim], threshold: float = 0.35) -> list[list[Claim]]:
    """Group claims that are the same statement travelling, not separate observations.

    TEN REPOSTS ARE NOT TEN CONFIRMATIONS. One origin passing through a forum, two aggregators
    and a translation arrives as four rows; a corroboration counter that reads that as four
    independent sources has built a machine that believes whatever propagates fastest. That
    failure is worst in exactly the multilingual ecosystems the desk was asked to mine, where the
    same sentence is repeated across many platforms within hours.

    Shingle overlap rather than exact match, because a repost is rarely byte-identical: it is
    quoted, trimmed, re-headlined and translated back. The threshold is deliberately loose --
    over-merging costs a corroboration the desk did not need, while under-merging manufactures
    agreement that was never there, and only one of those two errors can promote a candidate.

    The FIRST claim of each cluster is its origin by retrieval order, so the cluster head is the
    earliest thing the desk saw rather than the loudest.
    """
    ordered = sorted(claims, key=lambda c: c.retrieved_at)
    clusters: list[list[Claim]] = []
    shingled: list[frozenset[str]] = []
    for claim in ordered:
        sh = _shingles(claim.text)
        for i, head in enumerate(shingled):
            if _overlap(sh, head) >= threshold:
                clusters[i].append(claim)
                break
        else:
            clusters.append([claim])
            shingled.append(sh)
    return clusters


def independent_sources(claims: list[Claim], threshold: float = 0.35) -> int:
    """How many DISTINCT origins a set of claims represents.

    The number `roi` should see as corroboration. Two clusters that came from the same source
    still count once: a site repeating itself is not a second witness.
    """
    origins = {
        (cluster[0].source or cluster[0].url or cluster[0].key())
        for cluster in genealogy(claims, threshold)
    }
    return len(origins)


def _ledger_counts(path: Path, source: str) -> tuple[int, int]:
    hits = total = 0
    if not path.exists():
        return 0, 0
    for line in path.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if str(row.get("source")) != source:
            continue
        total += 1
        hits += 1 if row.get("hit") else 0
    return hits, total


def truth_score(source: str, ledger: Path | None = None) -> tuple[float | None, str]:
    """P(a claim from this source is later corroborated), or None with a reason.

    Gates BELIEF IN THE CLAIM and nothing else. It never multiplies a mechanism's value -- that
    separation is `roi.py`'s central correction and this function must not smuggle it back.
    """
    hits, total = _ledger_counts(ledger or TRUTH_LEDGER, source)
    if total < 5:
        return None, f"only {total} graded claim(s) from {source}; prior stands"
    return hits / total, f"{hits}/{total} claims later corroborated"


def idea_yield(source: str, ledger: Path | None = None) -> tuple[float | None, str]:
    """P(a claim from this source produces a hypothesis worth testing), or None.

    THE SCORE THAT KEEPS WEAK SOURCES IN THE CORPUS. A community can be unreliable about facts
    and still be the best generator of ideas the desk has; the two properties are measured on
    different ledgers precisely so that one cannot silence the other. A source with truth 0.2 and
    yield 0.65 should be crawled often and believed rarely, which is impossible to express with a
    single number.
    """
    hits, total = _ledger_counts(ledger or YIELD_LEDGER, source)
    if total < 5:
        return None, f"only {total} scored claim(s) from {source}; prior stands"
    return hits / total, f"{hits}/{total} claims produced a tested hypothesis"


def compile_claim(claim: Claim) -> dict[str, Any]:
    """One claim -> the record the queue and the ROI ranker consume.

    `capabilities` is filled by the compiler rather than by `ontology.map_to_capabilities`, and
    that is the point of the file: the literal mapper only matches text that already names a
    group, so a claim written in ordinary prose mapped to nothing and stalled. Here the naming is
    the job.

    `mechanism_text` is what downstream stages should read INSTEAD of the raw claim. It carries no
    firm, no person and no employment assertion -- only the proposition and what would refute it.
    """
    blocked, why = mnpi_guard(claim.text)
    mechs = to_mechanisms(claim.text)
    truth, truth_why = truth_score(claim.source)
    yield_, yield_why = idea_yield(claim.source)
    return {
        "claim_id": claim.key(),
        "firm": claim.firm,
        "source": claim.source,
        "url": claim.url,
        "grade": claim.grade,
        "language": claim.language,
        "retrieved_at": claim.retrieved_at,
        "stripped": strip_mythology(claim.text),
        "capabilities": [m.capability for m in mechs],
        # Named so `ontology.map_to_capabilities` succeeds on it: the compiler's output is what
        # the literal mapper was always waiting for.
        "mechanism_text": " | ".join(
            f"{m.capability}: {m.proposition}" for m in mechs),
        "mechanisms": [
            {"capability": m.capability, "proposition": m.proposition,
             "falsifier": m.falsifier, "implies_alpha": m.implies_alpha}
            for m in mechs
        ],
        "implies_alpha": any(m.implies_alpha for m in mechs),
        "capital_authority": "BLOCKED" if blocked else "ZERO",
        # ZERO, never "allowed": no external claim receives trading authority at any grade. The
        # ladder to capital is the same one every candidate walks -- replication, the ten gates,
        # a forward clock, measured rent -- and this field records only that the claim has not
        # been given a shortcut.
        "capital_authority_why": why or (
            "no external claim receives capital authority; the ten gates and a forward clock "
            "decide, exactly as for any other candidate"),
        "research_authority": "ALLOWED",
        "source_truth": truth,
        "source_truth_why": truth_why,
        "source_idea_yield": yield_,
        "source_idea_yield_why": yield_why,
        "unrecognised": not mechs,
        # An unmatched claim is NOT discarded: it is the input `unknowns.unknown_capabilities`
        # exists for, and the genuinely new technique arrives looking exactly like this.
    }


def compile_all(claims: list[Claim]) -> dict[str, Any]:
    """Compile a batch, with corroboration counted by ORIGIN rather than by row."""
    clusters = genealogy(claims)
    compiled = [compile_claim(c) for c in claims]
    by_capability: dict[str, list[Claim]] = {}
    for claim, rec in zip(claims, compiled, strict=True):
        for cap in rec["capabilities"]:
            by_capability.setdefault(cap, []).append(claim)
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "claims": len(claims),
        "origins": len(clusters),
        "compiled": compiled,
        "unrecognised": sum(1 for r in compiled if r["unrecognised"]),
        # CROSS-SOURCE CONVERGENCE, counted honestly. Several unrelated organisations independently
        # investing in a capability is evidence about where to LOOK -- a prior, never a verdict --
        # and it is only evidence at all if the sources are genuinely independent.
        "convergence": {
            cap: independent_sources(cl)
            for cap, cl in sorted(by_capability.items())
        },
    }
