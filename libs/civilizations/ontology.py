"""THE OUTPUT ONTOLOGY: every mined item becomes one or more typed outcomes, each with a consumer.

    zuck, 2026-09-30: "That's how you extract maximum value without polluting the alpha gauntlet
    with irrelevant software examples."

Only ALPHA_MECHANISM goes to the gauntlet. Every other outcome is appended to its own ledger
(`desks/mt5/data/civilizations/outcomes/<OUTCOME>.jsonl`) that names the organ consuming it, so a
fill-model regression test becomes negative knowledge + a validator idea instead of a fake
strategy, and a dataset page becomes a free-substitute ask instead of a scrape.

DETERMINISTIC. The classifier is a bank of named regex signals with weights; the evidence (which
signals fired) is kept on every row so a wrong routing can be traced and the bank fixed. A lane's
roster `ontology_hint` adds a prior, never a verdict: a LEAN execution-model file that ALSO
states a ranking rule is routed to both EXECUTION_IDEA and ALPHA_MECHANISM.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

ALPHA_MECHANISM = "ALPHA_MECHANISM"
FEATURE_PRIMITIVE = "FEATURE_PRIMITIVE"
DATA_IDEA = "DATA_IDEA"
EXECUTION_IDEA = "EXECUTION_IDEA"
PORTFOLIO_IDEA = "PORTFOLIO_IDEA"
RISK_IDEA = "RISK_IDEA"
UNIVERSE_IDEA = "UNIVERSE_IDEA"
VALIDATION_IDEA = "VALIDATION_IDEA"
FAILURE_KNOWLEDGE = "FAILURE_KNOWLEDGE"
RESEARCH_METHOD = "RESEARCH_METHOD"
INFRASTRUCTURE_PATTERN = "INFRASTRUCTURE_PATTERN"
#: The ontology is never closed (zuck 2026-10-05): a recurring concept none of the classes above
#: recognises becomes a class of its own (libs.civilizations.emergent) and items carrying it are
#: routed here instead of to NO_VALUE.
EMERGENT_CLASS = "EMERGENT_CLASS"
NO_VALUE = "NO_VALUE"

#: outcome -> the organ that consumes it. Every outcome has a consumer (the dataset rule: nothing
#: mined is stored unused), and NO_VALUE is itself a counted verdict, not a silent drop.
CONSUMERS: dict[str, str] = {
    ALPHA_MECHANISM: "gauntlet (libs.mining spine -> external_gauntlet)",
    FEATURE_PRIMITIVE: "representation compiler -> libs.research.alpha_grammar",
    DATA_IDEA: "global data scout + paid-substitute engine (Breadth)",
    EXECUTION_IDEA: "execution research lab (order door / fill model challengers)",
    PORTFOLIO_IDEA: "allocator challenger sandbox",
    RISK_IDEA: "risk challenger",
    UNIVERSE_IDEA: "universe policy challenger (research.universe_policy)",
    VALIDATION_IDEA: "evaluator laboratory (gauntlet challengers, never the sealed judge)",
    FAILURE_KNOWLEDGE: "negative-knowledge graph + deterministic regression tests",
    RESEARCH_METHOD: "meta-R&D competition (research-engine challengers)",
    INFRASTRUCTURE_PATTERN: "engineering challenger backlog",
    EMERGENT_CLASS: "ontology frontier: knowledge graph + frontier GitHub search + missions",
    NO_VALUE: "counted and closed (no consumer needed)",
}
OUTCOMES: tuple[str, ...] = tuple(CONSUMERS)

_I = re.IGNORECASE


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), _I)


#: (outcome, signal name, weight, pattern). A score >= THRESHOLD routes the outcome.
SIGNALS: tuple[tuple[str, str, float, re.Pattern[str]], ...] = (
    # ---------------------------------------------------------------- alpha
    (ALPHA_MECHANISM, "insight_emit", 1.0, _rx(r"\bInsight\.Price\(", r"\bInsight\(",
                                               r"InsightDirection\.(Up|Down)")),
    (ALPHA_MECHANISM, "order_on_signal", 0.6, _rx(r"\bSetHoldings\s*\(", r"\bset_holdings\s*\(",
                                                  r"\bMarketOrder\s*\(", r"\bmarket_order\s*\(",
                                                  r"\bOrderSend\s*\(", r"\bbuy\(|\bsell\(")),
    (ALPHA_MECHANISM, "trade_rule_prose", 0.8, _rx(
        r"\b(go|goes|went) (long|short)\b", r"\bbuy (when|if)\b", r"\bsell (when|if)\b",
        r"\blong(-| )short\b", r"\bentry (rule|signal)\b", r"\bexit (rule|signal)\b",
        r"\bthe strategy (buys|sells|goes)\b", r"\btop (decile|quintile)\b")),
    (ALPHA_MECHANISM, "anomaly_named", 0.7, _rx(
        r"\bmomentum\b", r"\bmean[- ]reversion\b", r"\breversal\b", r"\bcarry\b",
        r"\bvalue (factor|premium|strategy)\b", r"\bpairs? trading\b", r"\bbreakout\b",
        r"\bseasonal(ity)?\b", r"\bpost[- ]earnings\b", r"\bdrift\b", r"\btrend[- ]following\b",
        r"\bstatistical arbitrage\b", r"\bbetting against beta\b", r"\bdefensive\b",
        r"\bquality minus junk\b", r"\btime[- ]series momentum\b", r"\bcross[- ]sectional\b")),
    (ALPHA_MECHANISM, "wq_expression", 1.0, _rx(
        r"\b(rank|ts_rank|ts_delta|delta|correlation|decay_linear|ts_argmax|group_neutralize|"
        r"group_rank|ts_zscore|ts_mean|ts_sum|signedpower)\s*\(")),
    (ALPHA_MECHANISM, "returns_claim", 0.4, _rx(r"\bsharpe (ratio )?(of )?\d",
                                                r"\bannuali[sz]ed return",
                                                r"\bt-stat", r"\bexcess returns?\b",
                                                r"\balpha of\b")),
    # ---------------------------------------------------------------- feature primitive
    (FEATURE_PRIMITIVE, "indicator_class", 1.0, _rx(
        r"class \w+\s*\(\s*(Indicator|BarIndicator|TradeBarIndicator|WindowIndicator)",
        r":\s*(Indicator|BarIndicator|TradeBarIndicator|WindowIndicator<)",
        r"\bIndicatorBase<", r"\bIIndicatorWarmUpPeriodProvider\b")),
    (FEATURE_PRIMITIVE, "estimator_prose", 0.6, _rx(
        r"\bestimator\b", r"\b(realized|realised) (volatility|variance)\b", r"\bgarman[- ]klass\b",
        r"\bparkinson\b", r"\byang[- ]zhang\b", r"\bhurst\b", r"\bentropy\b",
        r"\bkalman\b", r"\bfractional(ly)? differenc", r"\bwavelet\b", r"\boperator\b")),
    # ---------------------------------------------------------------- data idea
    (DATA_IDEA, "dataset_named", 1.0, _rx(
        r"\bdataset\b", r"\bdata ?(source|vendor|feed|provider|library)\b",
        r"\balternative data\b", r"\bPythonData\b", r"\bBaseData\b", r"\bAddData\s*\(",
        r"\badd_data\s*\(", r"\bdata field\b", r"\bdatafield\b")),
    (DATA_IDEA, "alt_data_kind", 0.6, _rx(
        r"\bsentiment\b", r"\bsatellite\b", r"\bweb traffic\b", r"\bcredit card\b",
        r"\bgeolocation\b", r"\bfoot traffic\b", r"\bnews analytics\b", r"\bsec filings?\b",
        r"\binsider\b", r"\bcongress\b", r"\bshipping\b", r"\bsupply chain\b", r"\bpatents?\b")),
    # ---------------------------------------------------------------- execution
    (EXECUTION_IDEA, "execution_model", 1.0, _rx(
        r"\bExecutionModel\b", r"\bexecution model\b", r"\bFillModel\b", r"\bSlippageModel\b",
        r"\bFeeModel\b", r"\bfill model\b", r"\bslippage model\b", r"\bVWAP execution\b",
        r"\bTWAP\b", r"\bimplementation shortfall\b", r"\bmarket impact\b", r"\bquote stuffing\b",
        r"\blimit order book\b", r"\border book\b", r"\bqueue position\b", r"\bspread capture\b",
        r"\bmarket[- ]making\b", r"\binventory risk\b")),
    (EXECUTION_IDEA, "order_semantics", 0.5, _rx(
        r"\bLimitOrder\b", r"\bStopMarketOrder\b", r"\bMarketOnOpen\b", r"\bMarketOnClose\b",
        r"\btime in force\b", r"\bpartial fill", r"\border type")),
    # ---------------------------------------------------------------- portfolio
    (PORTFOLIO_IDEA, "portfolio_model", 1.0, _rx(
        r"\bPortfolioConstructionModel\b", r"\bportfolio construction\b", r"\bBlack[- ]Litterman\b",
        r"\bmean[- ]variance\b", r"\brisk parity\b", r"\bhierarchical risk parity\b",
        r"\bequal[- ]weight", r"\bminimum variance\b", r"\bkelly\b", r"\bportfolio optimi[sz]",
        r"\bvolatility target", r"\bfactor exposure\b", r"\bposition sizing\b")),
    # ---------------------------------------------------------------- risk
    (RISK_IDEA, "risk_model", 1.0, _rx(
        r"\bRiskManagementModel\b", r"\brisk management model\b", r"\btrailing stop\b",
        r"\bmaximum drawdown\b", r"\bdrawdown (control|limit)\b", r"\bexposure limit",
        r"\bsector exposure\b", r"\bvalue at risk\b", r"\bexpected shortfall\b",
        r"\btail (risk|hedg)", r"\bcrash (protection|detection)\b", r"\bstop[- ]loss\b")),
    # ---------------------------------------------------------------- universe
    (UNIVERSE_IDEA, "universe_selection", 1.0, _rx(
        r"\bUniverseSelectionModel\b", r"\buniverse selection\b", r"\bCoarseSelection\b",
        r"\bFineSelection\b", r"\bAddUniverse\s*\(", r"\badd_universe\s*\(",
        r"\bdollar volume\b", r"\bliquidity filter\b", r"\bconstituents?\b")),
    # ---------------------------------------------------------------- validation
    (VALIDATION_IDEA, "validation_method", 1.0, _rx(
        r"\bwalk[- ]forward\b", r"\bcross[- ]validation\b", r"\bpurg(ed|ing)\b", r"\bembargo\b",
        r"\bdeflated sharpe\b", r"\bprobability of backtest overfitting\b", r"\bPBO\b",
        r"\bwhite'?s reality check\b", r"\bSPA test\b", r"\bout[- ]of[- ]sample\b",
        r"\bmultiple testing\b", r"\bfalse discovery\b", r"\bbootstrap\b",
        r"\bregression (algorithm|test)\b", r"\bExpectedStatistics\b", r"\bexpected_statistics\b")),
    # ---------------------------------------------------------------- failure
    (FAILURE_KNOWLEDGE, "failure_prose", 1.0, _rx(
        r"\blook[- ]?ahead\b", r"\bsurvivorship\b", r"\boverfit", r"\bdata leak", r"\bleakage\b",
        r"\bworked in backtest\b", r"\bbacktest (vs|versus) live\b",
        r"\blive (vs|versus) backtest\b",
        r"\bdifferent results\b", r"\bdoes not match\b", r"\bdiscrepanc", r"\bbug\b",
        r"\bregression\b", r"\bbroke\b", r"\bstopped working\b", r"\balpha decay\b",
        r"\border rejected\b", r"\binsufficient (margin|buying power)\b", r"\bwrong (price|fill)",
        r"\btime ?zone\b", r"\brollover\b", r"\bsplit adjust", r"\bdividend adjust",
        r"\bdelist", r"\bcorporate action", r"\bwarm[- ]?up\b", r"\bstale (price|data)\b",
        r"\bcrowded\b", r"\bturnover (problem|too high|cost)", r"\bself[- ]correlation\b")),
    # ---------------------------------------------------------------- research method
    (RESEARCH_METHOD, "search_method", 1.0, _rx(
        r"\bgenetic programming\b", r"\bgplearn\b", r"\bsymbolic regression\b",
        r"\bmonte carlo tree search\b", r"\bMCTS\b", r"\bbayesian optimi[sz]", r"\bhyperopt\b",
        r"\boptuna\b", r"\bgrid search\b", r"\bparameter (search|sweep|optimi[sz])",
        r"\bfitness (function|score)\b", r"\bmutation\b", r"\bcrossover operator\b",
        r"\bdiversity\b", r"\bnovelty search\b", r"\bexperiment (tracking|scheduling)\b",
        r"\bfactor (mining|zoo|combination)\b", r"\balpha (mining|generation|pool)\b",
        r"\bneutrali[sz]ation\b", r"\bhypothesis[- ]driven\b", r"\bmeta[- ]analysis\b",
        r"\bOptimizer\b", r"\bparameter set\b")),
    # ---------------------------------------------------------------- infrastructure
    (INFRASTRUCTURE_PATTERN, "infra", 0.7, _rx(
        r"\bbrokerage\b", r"\bdata (normali[sz]ation|pipeline)\b", r"\bscheduler\b",
        r"\bcaching\b", r"\bserializ", r"\bdocker\b", r"\bmessage queue\b",
        r"\bIDataQueueHandler\b",
        r"\bIBrokerage\b", r"\bIHistoryProvider\b", r"\bplugin\b", r"\blauncher\b")),
)
THRESHOLD = 1.0
#: Lane prior added to an outcome the roster says the lane is FOR.
HINT_WEIGHT = 0.5


@dataclass
class Outcome:
    kind: str
    score: float
    evidence: list[str] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        return {"outcome": self.kind, "score": round(self.score, 3), "evidence": self.evidence,
                "consumer": CONSUMERS[self.kind]}


def classify(text: str, *, hints: Iterable[str] = (), forced: Iterable[str] = (),
             cap_chars: int = 60_000) -> list[Outcome]:
    """Outcomes for one item, strongest first. `hints` are the lane's prior (roster
    `ontology_hint`), `forced` are outcomes a structural rule already established (a LEAN
    path under Alphas/ IS an alpha model). An item nothing reaches is NO_VALUE, counted."""
    body = str(text or "")[:cap_chars]
    score: dict[str, float] = {}
    ev: dict[str, list[str]] = {}
    for kind, name, w, rx in SIGNALS:
        hits = len(rx.findall(body))
        if hits:
            # diminishing returns: the second hit adds half, the rest a quarter
            score[kind] = score.get(kind, 0.0) + w * (1 + 0.5 * (hits > 1) + 0.25 * (hits > 2))
            ev.setdefault(kind, []).append(f"{name}x{hits}")
    for h in hints:
        if h in CONSUMERS and h != NO_VALUE and score.get(h):
            score[h] += HINT_WEIGHT
            ev[h].append("lane_hint")
    for f in forced:
        if f in CONSUMERS:
            score[f] = max(score.get(f, 0.0), THRESHOLD) + 1.0
            ev.setdefault(f, []).insert(0, "structural")
    out = [Outcome(k, s, ev.get(k, [])) for k, s in score.items() if s >= THRESHOLD]
    out.sort(key=lambda o: (-o.score, o.kind))
    return out or [Outcome(NO_VALUE, 0.0, ["no signal reached threshold"])]


def is_alpha(outcomes: Iterable[Outcome]) -> bool:
    return any(o.kind == ALPHA_MECHANISM for o in outcomes)


def kinds(outcomes: Iterable[Outcome]) -> list[str]:
    return [o.kind for o in outcomes]


def summarise(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Outcome counts over ledger rows (each row may carry several outcomes)."""
    out = dict.fromkeys(OUTCOMES, 0)
    for r in rows:
        for k in r.get("outcomes") or [r.get("outcome")]:
            if k in out:
                out[k] += 1
    return out
