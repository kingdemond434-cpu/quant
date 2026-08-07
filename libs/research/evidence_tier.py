"""CLAIMED IS NOT VERIFIED -- the ledger that keeps a forum post from becoming a survivor.

THE PRINCIPAL'S RULE, WRITTEN AS CODE (2026-08-07): *"a Reddit post saying 'my BTC bot made 40%
last month' is research ore, not evidence."* Everything a miner returns is ore. It becomes evidence
only when THIS desk reproduces it on its own data, and the two must never share a column -- because
the single cheapest way for a research programme to manufacture survivors is to let a number that
arrived in a sentence sit in the field reserved for a number the desk computed.

So `Reproduction` carries `claimed` and `verified` as SEPARATE fields, `verified` starts as None,
and nothing in this module can move a value from one to the other. Populating `verified` requires
a run.

WHAT THE TIERS ARE FOR, AND WHAT THEY ARE EMPHATICALLY NOT FOR. A finding is tiered by how
expensive it is to KILL, not by how likely it is to be true::

    EXECUTABLE         code + data + parameters -> refutable in an afternoon
    REPRODUCIBLE_SPEC  enough detail to rebuild it -> refutable in a cycle
    MECHANISM_ONLY     an economic story, no numbers -> a hypothesis to enumerate
    BARE_CLAIM         a headline return -> nothing to test but the sentence

EXECUTABLE RANKS FIRST BECAUSE IT IS CHEAPEST TO REFUTE, NOT BECAUSE CODE IS MORE HONEST. Published
bot code is, if anything, MORE likely to be overfit than a forum anecdote -- it has been tuned
until the equity curve looked good. The reason to hunt it first is that the desk can settle it
instead of arguing about it, and a research programme's real currency is DECISIONS PER UNIT
EFFORT. A tier is a queue position. It is never a prior on truth, and it may never substitute for
a gate.

THE SOURCE-CLASS PRIORS ARE ORDERING HINTS AND NOTHING ELSE. A Hummingbot strategy discussion
yields executable artifacts far more often than a general crypto subreddit, so it is worth reading
first. It does NOT follow that its claims are better -- and the desk's own history says the
opposite is common: `claim_screen` was written from three claims that arrived looking professional.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "BACKTEST_MARKERS",
    "CRYPTO_MECHANISMS",
    "SOURCE_CLASS_YIELD",
    "TIERS",
    "Finding",
    "Reproduction",
    "classify",
    "rank",
    "translate_to_crypto",
]

#: Ordered CHEAPEST-TO-REFUTE first. The order is the queue, not a ranking of credibility.
TIERS: tuple[str, ...] = ("EXECUTABLE", "REPRODUCIBLE_SPEC", "MECHANISM_ONLY", "BARE_CLAIM")

#: Words that mean someone reported a BACKTEST. Presence routes a finding to the backtest-mining
#: category; it says nothing whatever about quality -- `undeflated_sharpe` and the rest of
#: `claim_screen` exist precisely because these words cluster around the weakest claims.
BACKTEST_MARKERS: frozenset[str] = frozenset({
    "backtest", "backtested", "back-tested", "backtesting", "sharpe", "sortino", "calmar",
    "cagr", "drawdown", "profit factor", "win rate", "pnl", "equity curve", "out-of-sample",
    "oos", "walk-forward", "walkforward", "in-sample", "monte carlo", "paper trading",
    "live results", "track record", "annualised return", "annualized return",
})

#: Words that mean someone accounted for the things that kill crypto strategies. Their ABSENCE is
#: the finding: a backtest that never mentions fees, funding or slippage is not a weaker result,
#: it is a different quantity from the one the desk would compute -- and on a perp book funding
#: alone routinely exceeds the edge (WS-006: a Holm-cleared signal netting -0.656 bp/bar).
COST_MARKERS: frozenset[str] = frozenset({
    "fee", "fees", "commission", "slippage", "funding", "funding rate", "transaction cost",
    "market impact", "spread", "taker", "maker", "borrow", "execution cost", "latency",
})

#: The desk's crypto mechanism vocabulary, as SEARCH KEYS and as the extraction taxonomy. A finding
#: that maps to none of these is not worthless -- it is the interesting case, because the desk's
#: whole feature set lives in this list and a mechanism outside it is the only kind that can widen
#: the search space rather than re-search it.
CRYPTO_MECHANISMS: tuple[str, ...] = (
    "funding", "open_interest", "liquidation", "basis", "order_flow", "book_imbalance",
    "trade_intensity", "volatility", "market_regime", "cross_exchange_spread", "stablecoin_flow",
    "onchain_flow", "whale_activity", "cex_dex_flow", "mev", "arbitrage", "liquidation_cascade",
    "sentiment", "derivatives_positioning", "options_skew", "term_structure", "funding_dispersion",
    "volume_price", "latency_microstructure",
)

#: Expected EXECUTABLE-artifact yield by source class. Ordering hints for a miner's reading queue,
#: calibrated on nothing -- they are stated priors, and a miner that measures its own hit rate per
#: class should overwrite them with data. Recorded as a dict rather than prose so that is possible.
SOURCE_CLASS_YIELD: dict[str, float] = {
    "bot_framework": 0.90,        # Hummingbot / Freqtrade / Jesse / OctoBot -- code IS the post
    "code_repository": 0.85,      # GitHub crypto trading / MM / arb / LOB-ML
    "quant_platform": 0.70,       # QuantConnect / LEAN / vn.py / Qlib / NautilusTrader
    "microstructure_research": 0.65,   # order book, execution, latency, impact
    "academic": 0.55,             # arXiv q-fin, SSRN crypto -- method-rich, data often absent
    "alpha_ecosystem": 0.50,      # WorldQuant BRAIN, Numerai -- operators and process
    "exchange_research": 0.45,    # Binance / OKX / Deribit / Kaiko research desks
    "onchain_analytics": 0.40,    # Dune / Flipside / Glassnode / CryptoQuant
    "governance_forum": 0.30,     # Aave / Uniswap / Curve -- flow and incentive mechanics
    "regional_community": 0.25,   # CN/KR/JP/RU/BR/AR/IN forums -- mechanism-rich, code-poor
    "general_forum": 0.10,        # r/CryptoCurrency and similar -- ore, occasionally
}


@dataclass(frozen=True)
class Finding:
    """One mined artifact, described by WHAT IT CARRIES rather than by what it claims."""

    title: str = ""
    text: str = ""
    source_class: str = "general_forum"
    has_code: bool = False
    has_data: bool = False
    has_params: bool = False
    mechanism_stated: bool = False

    @property
    def mentions_backtest(self) -> bool:
        return _hits(self.text, BACKTEST_MARKERS)

    @property
    def accounts_for_costs(self) -> bool:
        return _hits(self.text, COST_MARKERS)


def _hits(text: str, markers: frozenset[str]) -> bool:
    low = (text or "").lower()
    return any(re.search(rf"(?<!\w){re.escape(m)}(?!\w)", low) for m in markers)


@dataclass(frozen=True)
class Reproduction:
    """The two-column ledger. `verified` is None until THIS desk computed it.

    NOTHING IN THIS MODULE WRITES `verified`. There is no `promote()`, no `accept()`, no default
    that copies `claimed` across on the grounds that it is probably fine. Moving a number from the
    left column to the right one requires a run against the desk's own data, and that run lives in
    the study harness, not here -- which is the entire point of keeping them apart.
    """

    metric: str
    claimed: float | None = None
    verified: float | None = None
    status: str = "NOT_ATTEMPTED"   # NOT_ATTEMPTED | IRREPRODUCIBLE | CONFIRMS | REFUTES
    note: str = ""

    @property
    def is_evidence(self) -> bool:
        """Only a completed reproduction is evidence. A claim never is, however specific."""
        return self.verified is not None and self.status in {"CONFIRMS", "REFUTES"}

    def summary(self) -> str:
        if self.is_evidence:
            return (f"{self.metric}: claimed {self.claimed}, VERIFIED {self.verified} "
                    f"({self.status})")
        if self.status == "IRREPRODUCIBLE":
            return (f"{self.metric}: claimed {self.claimed}; reproduction ATTEMPTED AND FAILED -- "
                    "which is a finding about the claim, not a missing measurement")
        return (f"{self.metric}: claimed {self.claimed}; NOT REPRODUCED. This is ore, not "
                "evidence, and it may not be cited as a result.")


def classify(f: Finding) -> tuple[str, str]:
    """(tier, why). Tiering is about the cost of refutation, never about credibility.

    A BARE_CLAIM IS NOT A REJECTION. It is still worth mining -- the mechanism inside a fabricated
    track record is usually real and the author neither invented nor understood it -- but it enters
    as a hypothesis to enumerate, never as a result to act on.
    """
    if f.has_code and f.has_data:
        return "EXECUTABLE", (
            "code and data both present: the desk can settle this instead of arguing about it. "
            "Ranked first because it is cheapest to REFUTE -- published bot code is if anything "
            "more overfit than an anecdote, having been tuned until the curve looked good.")
    if f.has_code or (f.has_params and f.mechanism_stated):
        return "REPRODUCIBLE_SPEC", (
            "enough specification to rebuild it without guessing the parameters that decide the "
            "answer. One cycle to settle rather than an afternoon.")
    if f.mechanism_stated:
        return "MECHANISM_ONLY", (
            "an economic story with no numbers attached. This is the form that TRANSFERS -- a "
            "mechanism survives translation across venues and regimes, and a parameter does not.")
    return "BARE_CLAIM", (
        "a headline with nothing behind it but the sentence. Mine it for the mechanism, the data "
        "source and the vocabulary; the number itself is not testable and is not a result.")


def rank(findings: list[Finding]) -> list[tuple[Finding, str, float]]:
    """Reading order: (finding, tier, score). Executable artifacts first, then source-class yield.

    THE SCORE ORDERS A QUEUE AND CONFERS NOTHING. It cannot admit, promote or size anything, and a
    high score on a finding that fails `claim_screen` means the desk should read a bad claim
    sooner -- not believe it.
    """
    out = []
    for f in findings:
        tier, _ = classify(f)
        score = (len(TIERS) - TIERS.index(tier)) + SOURCE_CLASS_YIELD.get(f.source_class, 0.1)
        if f.mentions_backtest and f.accounts_for_costs:
            score += 0.5      # a costed backtest is rarer and far closer to comparable
        out.append((f, tier, round(score, 3)))
    return sorted(out, key=lambda t: -t[2])


#: Traditional-market constructs and their crypto-native counterparts. THE TRANSLATION IS THE
#: POINT: an equity or futures result copied verbatim is untestable on a perp book, while the
#: MECHANISM behind it usually has an exact analogue that the desk can measure on Binance.
_TRANSLATIONS: tuple[tuple[str, str], ...] = (
    ("futures basis", "perpetual funding rate + spot-perp basis"),
    ("roll yield", "funding carry across the perp curve"),
    ("term structure", "quarterly-vs-perp basis term structure"),
    ("commitment of traders", "open interest by venue + long/short account ratio"),
    ("short interest", "aggregate perp short OI and funding sign"),
    ("earnings drift", "post-listing and post-unlock drift"),
    ("dividend capture", "funding-payment capture around settlement"),
    ("index rebalance", "index-token and perp-listing rebalance flow"),
    ("order imbalance", "book imbalance + aggressor-side trade intensity"),
    ("stock lending fee", "borrow rate on margin venues"),
    ("market maker inventory", "maker inventory skew visible in quote asymmetry"),
    ("flight to quality", "stablecoin flows and BTC dominance rotation"),
)


def translate_to_crypto(text: str) -> list[tuple[str, str]]:
    """Traditional-finance constructs found in `text`, paired with their crypto analogue.

    This is where the international and academic miners earn their keep. A Japanese futures-basis
    paper is not a Binance strategy and copying it produces nothing testable; its MECHANISM maps
    onto perpetual funding, which the desk records every eight hours. The translation step is what
    turns a foreign result into a hypothesis this desk can actually run.
    """
    low = (text or "").lower()
    return [(a, b) for a, b in _TRANSLATIONS if a in low]


@dataclass(frozen=True)
class MiningRecord:
    """The schema a miner fills per discovery: mechanism -> hypothesis -> evidence -> data -> repro.

    `failure` IS A FIRST-CLASS FIELD and the most valuable one on the page. A documented failure
    with a stated cause is evidence the desk did not have to pay for, and it is the half of every
    writeup the crowd skips -- which is exactly why it is still there to be found.
    """

    mechanism: str
    hypothesis: str = ""
    evidence: tuple[Reproduction, ...] = field(default_factory=tuple)
    failure: str = ""
    near_miss: str = ""
    data_source: str = ""
    tier: str = "BARE_CLAIM"
    source: str = ""
    derives_from: tuple[str, ...] = ()
    derives_from_checked: bool = False

    @property
    def is_survivor(self) -> bool:
        """ALWAYS FALSE. Nothing mined is a survivor; the gauntlet decides, on the desk's data.

        Present as a property rather than absent so the answer is explicit at every call site that
        reaches for it. An attribute that does not exist invites a caller to invent one.
        """
        return False
