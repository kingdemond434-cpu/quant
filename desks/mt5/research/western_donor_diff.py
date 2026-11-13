#!/usr/bin/env python3
"""N8, THE WESTERN HALF: the donor-capability diff, run every pass.

    python desks/mt5/research/western_donor_diff.py --budget-s 240
    python desks/mt5/research/western_donor_diff.py --no-fetch          # the diff alone

THE ASK (OWNERSHIP_2026-10-13, row N8; BACKLOG 2026-09-30 "mine N8 western donors"). A
continuous donor-capability diff: donor -> capability -> our equivalent -> gap -> challenger ->
gauntlet. The Western donors named for it are WorldQuant BRAIN, QuantConnect/LEAN, Numerai and
Man AHL, "used within each platform's terms". The Asian half (High-Flyer, Ubiquant, ...) belongs
to the Asia thread; nothing here touches it.

WHY A DIFF AND NOT ANOTHER CRAWLER. The deep-forest miner already reads Western practitioner
ground (Quantocracy, Alpha Architect, the QuantConnect forum, arXiv q-fin, SSRN) for trader
STORIES. What no organ did was hold a named donor's CAPABILITIES against this repository and say,
measured on the tree that runs, which ones the desk has, which it has only on paper, and which it
lacks. That is `capability_challenger`'s eight-station walk; this organ is its first scheduled
producer, and each capability is registered through `capability_challenger.register` so a walk
with a blank station reads INCOMPLETE rather than looking analysed.

WHAT A PASS DOES.

  1. THE DIFF, measured on the repository every pass. Each capability names ANCHORS -- a file and
     a pattern that must be in it -- and the status is read, never written down:
       COVERED             every anchor present and at least one anchor module has a consumer
                           (another non-test module names it)
       EXISTS_NO_CONSUMER  every anchor present, but nothing imports the code: built, not wired
       PARTIAL             some anchors present
       GAP                 none present
     A deleted organ turns its capability back into a GAP on the next pass, with no edit here.
  2. THE CHALLENGERS. An ALPHA capability that is not COVERED becomes a challenger row in this
     seat's intelligence directory. Where the donor's rule is exactly a registered price-only
     family it is a `{"kind": "hypothesis", "family": ...}` row (STRUCTURED_HYPOTHESIS in the
     compiler); otherwise it is a `story_mechanism` row carrying the donor's own words, which the
     compiler hands to the deepening worker. A METHOD capability (validation, sizing, execution)
     is never a cell: its gap goes to the report's work queue, named.
  3. THE DONORS' OWN PUBLIC TEXT, mined. Each pass fetches a rotating slice of the donors' public
     documents and does two things with the text: confirms which capability keywords the donor
     still states (evidence freshness, kept across passes), and extracts verbatim mechanism
     claims with the forest's own grammar (`mechanism_claims.extract`). Claims are written in the
     deep-forest task shape (`deep_forest_miner._task`) to the same seat directory, so they walk
     the forest's path: data/intelligence/<seat>/ -> compiler -> gauntlet, or -> deepening
     (story_mechanism) when the prose is not yet a rule.

THE ACCESS LAW HERE IS THE STRICT ONE, AND IT IS ORDERED (Governance ruling 2026-11-10, PR #819;
the coordinator's ruling that the terms gate fails closed):
  * TERMS FIRST. A source is fetched only when its terms record reads PERMITTED. UNKNOWN fails
    closed exactly as FORBIDDEN and LOGIN_REQUIRED do. The WorldQuant BRAIN platform is behind a
    login; Man Institute and the numer.ai and quantconnect.com sites have no recorded permitting
    clause. Each is listed with its reason and never requested.
  * LICENCE SECOND, for repository files. A repository's LICENSE is read (through the same robots
    gate) and must be a permissive licence before any other file of it is read. numerai/docs and
    numerai/example-scripts carry no LICENSE file and therefore stay closed; that is a measured
    refusal on every pass, not an assumption.
  * ROBOTS THIRD. robots.txt is read with this organ's own User-Agent; a Disallow on the exact
    path stops the fetch, 401/403 is a Disallow of everything, and robots that cannot be read are
    not permission.
  * One honest User-Agent naming what this is, one request per host every few seconds (arXiv's
    API terms ask three), no login, no proxy, no paywall, no retry storm. Code is never copied:
    only sentences are kept, with the URL and a hash of the page.

THE UNIVERSE. MT5/Fusion only. `mechanism_claims.extract` drops crypto-exchange sentences and
anything with no MT5 analogue; challenger instruments are filtered through
`universe_policy.may_hypothesise`, so a single-name share CFD can never be named outside its
cross-sectional or event lane.

UNMEASURED IS A VALUE (L1.28a). A source not reached this pass reads NOT_ATTEMPTED, a refused one
names its refusal, and a capability whose evidence was never confirmed online says so. The report
is `desks/mt5/reports/WESTERN_DONOR_DIFF.json`; it decides nothing about capital and caps nothing.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(ROOT), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "western_donors"
LEG = "western_donors"
#: Module globals, not frozen constants: the tests point the whole organ at a tmp desk.
REPORT = BASE / "reports" / "WESTERN_DONOR_DIFF.json"
OUT = BASE / "data" / "intelligence" / SOURCE
STATE = BASE / "data" / "western_donor_state.json"
CLAIMS = BASE / "data" / "western_donor_claims.jsonl"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
REPO = ROOT

UA = ("quant-desk-donor-diff/1.0 (research; reads public permissively-licensed documents; "
      "honours robots.txt)")
#: Seconds between two requests to one host. arXiv's API terms ask for three.
HOST_SPACING_S = 3.0
MAX_FETCHES = 16
MAX_BYTES = 2_000_000
PERMITTED, FORBIDDEN, UNKNOWN, LOGIN_REQUIRED = "PERMITTED", "FORBIDDEN", "UNKNOWN", "LOGIN_REQUIRED"
#: Licence names whose text may be READ for its sentences. Nothing is copied either way; the set
#: exists so a repository with no licence, or a restrictive one, is never read at all.
PERMISSIVE_LICENCES: tuple[tuple[str, str], ...] = (
    ("Apache-2.0", r"Apache License\s+Version 2\.0"),
    ("MIT", r"\bMIT License\b|Permission is hereby granted, free of charge"),
    ("BSD", r"Redistribution and use in source and binary forms"),
)
UNMEASURED = "UNMEASURED"
#: The licence a route's QUOTED text is published under. A repository route's licence is the one
#: the gate read from its LICENSE this pass; arXiv's API metadata (title, abstract) is CC0.
ARXIV_LICENCE = "CC0-1.0 (arXiv metadata)"

GH = "https://raw.githubusercontent.com"
LEAN = f"{GH}/QuantConnect/Lean/master"
NUMERAI_TOOLS = f"{GH}/numerai/numerai-tools/master"
NUMERAI_DOCS = f"{GH}/numerai/docs/master"
ARXIV = "https://export.arxiv.org/api/query"


# ------------------------------------------------------------------------------- the donors ---
@dataclass(frozen=True)
class Source:
    """One public document route of a donor, with the terms record that decides whether it is
    read at all. `licence_url` is the repository LICENSE the route's files depend on."""

    id: str
    donor: str
    urls: tuple[str, ...]
    machine_use: str
    basis: str
    licence_url: str = ""
    kind: str = "document"


@dataclass(frozen=True)
class Capability:
    """One donor capability, the anchors that measure our equivalent, and its challenger."""

    id: str
    donor: str
    name: str
    kind: str                       # "alpha" (a tradable mechanism) or "method"
    public_capability: str
    evidence_grade: str
    economic_mechanism: str
    anchors: tuple[tuple[str, str], ...]
    desk_analogue: str
    solo_scale_implementation: str
    controlled_test: str
    evidence: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    challenger: Mapping[str, Any] = field(default_factory=dict)


DONORS: dict[str, dict[str, str]] = {
    "worldquant_brain": {"name": "WorldQuant BRAIN", "region": "us"},
    "quantconnect_lean": {"name": "QuantConnect / LEAN", "region": "us"},
    "numerai": {"name": "Numerai", "region": "us"},
    "man_ahl": {"name": "Man AHL", "region": "gb"},
}

_ARXIV_BASIS = ("arXiv API Terms of Use permit programmatic access to the API at no more than "
                "one request every three seconds; article metadata (title, abstract) is "
                "published CC0. Only the API's Atom metadata is read, never a PDF.")
_GH_BASIS = ("files are read only after the repository's own LICENSE is fetched and matches a "
             "permissive licence; raw.githubusercontent.com publishes no robots rules, and the "
             "robots gate is still asked per path")

SOURCES: tuple[Source, ...] = (
    Source("wq_alpha101_paper", "worldquant_brain",
           (f"{ARXIV}?id_list=1601.00991",), PERMITTED, _ARXIV_BASIS, kind="arxiv"),
    Source("wq_arxiv_search", "worldquant_brain",
           (f"{ARXIV}?search_query=all:%22WorldQuant%22&sortBy=submittedDate&max_results=25",),
           PERMITTED, _ARXIV_BASIS, kind="arxiv"),
    Source("wq_brain_platform", "worldquant_brain",
           ("https://platform.worldquantbrain.com/learn",), LOGIN_REQUIRED,
           "the BRAIN documentation and simulator sit behind an account login; the desk does not "
           "log in to read a donor"),
    Source("lean_framework", "quantconnect_lean",
           (f"{LEAN}/readme.md",
            f"{LEAN}/Algorithm.Framework/Alphas/EmaCrossAlphaModel.py",
            f"{LEAN}/Algorithm.Framework/Alphas/HistoricalReturnsAlphaModel.py",
            f"{LEAN}/Algorithm.Framework/Alphas/BasePairsTradingAlphaModel.py",
            f"{LEAN}/Algorithm.Framework/Portfolio/"
            "MeanVarianceOptimizationPortfolioConstructionModel.py",
            f"{LEAN}/Algorithm.Framework/Portfolio/"
            "BlackLittermanOptimizationPortfolioConstructionModel.py",
            f"{LEAN}/Algorithm.Framework/Portfolio/RiskParityPortfolioConstructionModel.py",
            f"{LEAN}/Algorithm.Framework/Risk/TrailingStopRiskManagementModel.py",
            f"{LEAN}/Algorithm.Framework/Risk/MaximumDrawdownPercentPerSecurity.py",
            f"{LEAN}/Algorithm.Framework/Execution/StandardDeviationExecutionModel.py",
            f"{LEAN}/Algorithm.Framework/Execution/SpreadExecutionModel.py",
            f"{LEAN}/Algorithm.Framework/Execution/VolumeWeightedAveragePriceExecutionModel.py",
            f"{LEAN}/Algorithm.Python/Alphas/GlobalEquityMeanReversionIBSAlpha.py"),
           PERMITTED, _GH_BASIS, licence_url=f"{LEAN}/LICENSE", kind="github"),
    Source("lean_arxiv_search", "quantconnect_lean",
           (f"{ARXIV}?search_query=all:%22QuantConnect%22&sortBy=submittedDate&max_results=25",),
           PERMITTED, _ARXIV_BASIS, kind="arxiv"),
    Source("quantconnect_site", "quantconnect_lean",
           ("https://www.quantconnect.com/docs/v2",), UNKNOWN,
           "no permitting clause for automated or commercial reading is recorded for the site; "
           "the same documentation is read from its Apache-2.0 repositories instead"),
    Source("numerai_tools", "numerai",
           (f"{NUMERAI_TOOLS}/README.md", f"{NUMERAI_TOOLS}/numerai_tools/scoring.py"),
           PERMITTED, _GH_BASIS, licence_url=f"{NUMERAI_TOOLS}/LICENSE", kind="github"),
    Source("numerai_docs_repo", "numerai",
           (f"{NUMERAI_DOCS}/numerai-tournament/scoring/README.md",
            f"{NUMERAI_DOCS}/numerai-tournament/scoring/meta-model-contribution-mmc.md",
            f"{NUMERAI_DOCS}/numerai-tournament/scoring/feature-neutral-correlation.md"),
           PERMITTED, _GH_BASIS, licence_url=f"{NUMERAI_DOCS}/LICENSE", kind="github"),
    Source("numerai_arxiv_search", "numerai",
           (f"{ARXIV}?search_query=all:%22Numerai%22&sortBy=submittedDate&max_results=25",),
           PERMITTED, _ARXIV_BASIS, kind="arxiv"),
    Source("numerai_site", "numerai", ("https://docs.numer.ai/",), UNKNOWN,
           "no permitting clause for automated or commercial reading is recorded for the hosted "
           "docs; the repository route above is tried instead and is itself licence-gated"),
    Source("man_institute", "man_ahl", ("https://www.man.com/maninstitute",), UNKNOWN,
           "no permitting clause for automated or commercial reading is recorded for man.com; "
           "Man AHL's public research is read through arXiv metadata instead"),
    Source("man_ahl_arxiv_search", "man_ahl",
           (f"{ARXIV}?search_query=all:%22Man%20AHL%22&sortBy=submittedDate&max_results=25",
            f"{ARXIV}?search_query=all:%22Oxford-Man%20Institute%22%20AND%20all:trend"
            "&sortBy=submittedDate&max_results=25"),
           PERMITTED, _ARXIV_BASIS, kind="arxiv"),
)

_FP = "FIRST_PARTY_TECHNICAL_DISCLOSURE"
_VENDOR = "VENDOR_MARKETING_CLAIM"
_PEER = "PEER_REPORTED"

CAPABILITIES: tuple[Capability, ...] = (
    # ------------------------------------------------------------------ WorldQuant BRAIN ----
    Capability(
        "wq_formulaic_expressions", "worldquant_brain", "formulaic alpha expressions", "method",
        "alphas written as short expressions over price/volume operators (rank, ts_rank, "
        "correlation, delay, decay) and evaluated on a grid of instruments",
        _FP, "a compact grammar lets many cheap, low-capacity signals be generated and judged "
        "without bespoke code per idea",
        (("libs/research/alpha_grammar.py", r"def _ts_rank"),
         ("desks/mt5/research/expression_factory.py", r"alpha_grammar|expression")),
        "the alpha grammar and the expression factory",
        "the grammar already evaluates on H1 bars of the MT5 universe",
        "expression cells through the sealed gauntlet like any family",
        evidence=(f"{ARXIV}?id_list=1601.00991",),
        keywords=("rank", "correlation", "decay_linear", "ts_rank")),
    Capability(
        "wq_group_neutralization", "worldquant_brain", "peer-group neutralisation", "method",
        "a signal is demeaned within its peer group (market, sector, industry) before it is "
        "traded, so it bets on relative and not common moves",
        _FP, "the common factor is the crowded, priced bet; the residual is the idiosyncratic "
        "one a small book can hold",
        (("desks/mt5/research/universe_policy.py", r"CROSS_SECTIONAL_FAMILIES"),
         ("libs/research/alpha_grammar.py", r"indneutralize")),
        "class books ranked within an MT5 peer class, and indneutralize in the grammar",
        "peer classes from MetaTrader's own registry (fx, index, commodity, equity)",
        "a class-book cell against the same family un-neutralised",
        evidence=(f"{ARXIV}?id_list=1601.00991",),
        keywords=("indneutralize", "IndClass", "neutraliz")),
    Capability(
        "wq_decay_truncation", "worldquant_brain", "signal decay and weight truncation",
        "method",
        "the raw signal is linearly decayed over several days to cut turnover, and any one "
        "instrument's weight is truncated at a maximum share of the book",
        _VENDOR, "turnover is cost; a capped weight stops one instrument's noise owning the "
        "alpha's whole result",
        (("libs/research/alpha_grammar.py", r'"decay"'),
         ("desks/mt5/mt5desk/families_cross_sectional.py", r"(?i)truncat|max_weight")),
        "a decay operator in the grammar; no per-instrument weight cap in the class books",
        "a max-weight parameter on the class book, swept like any other parameter",
        "class book with and without the cap, judged on net E[log W]",
        keywords=("decay_linear",)),
    Capability(
        "wq_self_correlation_gate", "worldquant_brain", "self-correlation submission test",
        "method",
        "a new alpha is accepted only if it is not highly correlated with the author's existing "
        "alphas, so each submission adds breadth",
        _VENDOR, "a second copy of a held bet adds trials and no independent edge",
        (("desks/mt5/research/docket_keff.py", r"def daily_returns"),
         ("desks/mt5/research/orthogonality.py", r"def ")),
        "the docket's marginal k_eff and the orthogonality screens",
        "already a desk organ; the gap, if any, is that it is not a hard admission test",
        "survivor overlap before and after a correlation fence",
        keywords=()),
    Capability(
        "wq_alpha_combination", "worldquant_brain", "combining many weak alphas", "method",
        "many individually weak, mutually low-correlated alphas are combined into one book "
        "whose Sharpe exceeds any member's",
        _FP, "breadth: the information ratio grows with the square root of independent bets",
        (("desks/mt5/research/pf_allocator.py", r"def "),
         ("libs/portfolio/allocator_blend.py", r"def ")),
        "the growth allocator over every certified sleeve",
        "already the capital authority",
        "the allocator's own proof against equal weight",
        evidence=(f"{ARXIV}?id_list=1601.00991",),
        keywords=("combin", "portfolio")),
    Capability(
        "wq_short_horizon_formulas", "worldquant_brain", "Alpha101 short-horizon formulas",
        "alpha",
        "the 101 published formulaic alphas, most with holding periods of one to a few days, "
        "built from price/volume ranks and correlations",
        _FP, "short-horizon liquidity provision and reversal earn a premium for absorbing "
        "temporary order imbalance",
        (("libs/research/adapters/alpha101.py", r"alpha0?01|alpha101"),
         ("desks/mt5/research/expression_factory.py", r"(?i)alpha101|alpha_101")),
        "the Alpha101 adapter feeding the expression factory",
        "the formulas transpiled through the grammar onto MT5 bars",
        "each formula as a cell through the sealed gauntlet",
        evidence=(f"{ARXIV}?id_list=1601.00991",),
        keywords=("101", "formulaic", "alpha")),
    # ------------------------------------------------------------------ QuantConnect / LEAN --
    Capability(
        "lean_framework_layers", "quantconnect_lean", "five-layer algorithm framework", "method",
        "an algorithm is split into universe selection, alpha, portfolio construction, risk "
        "management and execution, each a swappable model",
        _FP, "separation lets one layer be improved and judged without re-deriving the others",
        (("libs/research/layers.py", r"\"information\"|'information'"),),
        "the seven strategy layers every hourly leg is assigned to",
        "already the leg taxonomy; the gap is model-level swappability inside a sleeve",
        "one sleeve with two execution models, judged on realised cost",
        evidence=(f"{LEAN}/readme.md",),
        keywords=("Alpha", "Portfolio", "Execution", "Risk")),
    Capability(
        "lean_reality_models", "quantconnect_lean", "fill, slippage and fee models", "method",
        "backtests run through explicit fill, slippage, fee and margin models rather than "
        "assuming the mid price",
        _FP, "an edge smaller than its cost is not an edge",
        (("desks/mt5/research/cost_surface.py", r"def "),
         ("desks/mt5/research/execution_science.py", r"def ")),
        "measured Fusion cost surfaces and execution science",
        "already measured on the venue", "cost-stamped certificates against unstamped",
        keywords=("fee", "slippage", "fill")),
    Capability(
        "lean_portfolio_models", "quantconnect_lean", "portfolio construction model zoo",
        "method",
        "mean-variance, Black-Litterman and risk-parity portfolio construction models, each "
        "selectable per algorithm",
        _FP, "how capital is spread across signals changes realised growth as much as the "
        "signals do",
        (("libs/portfolio/optimize.py", r"risk_parity"),
         ("libs/portfolio/challengers.py", r"(?i)mean.variance"),
         ("libs/portfolio/challengers.py", r"(?i)black.?litterman")),
        "risk parity and mean-variance challengers to the allocator; no Black-Litterman",
        "a Black-Litterman challenger whose views are the certified sleeves' forward means",
        "the allocator's proof against each challenger on the same book",
        evidence=(f"{LEAN}/Algorithm.Framework/Portfolio/"
                  "BlackLittermanOptimizationPortfolioConstructionModel.py",),
        keywords=("BlackLitterman", "MeanVariance", "RiskParity")),
    Capability(
        "lean_risk_models", "quantconnect_lean", "per-position risk models", "method",
        "trailing-stop and maximum-drawdown-per-security risk models that close a position "
        "independently of the alpha",
        _FP, "a stop changes the payoff's shape; whether it raises growth is an empirical question",
        (("libs/research/profit_retention.py", r"trailing_stop"),),
        "profit retention's trailing-stop study",
        "a sleeve-level stop judged two-sided against no stop",
        "same sleeve with and without the stop, judged on E[log W]",
        evidence=(f"{LEAN}/Algorithm.Framework/Risk/TrailingStopRiskManagementModel.py",),
        keywords=("trailing", "drawdown")),
    Capability(
        "lean_execution_models", "quantconnect_lean", "conditional execution models", "method",
        "orders are released only when the price sits a set number of standard deviations "
        "favourable, or the spread is below a threshold, or spread over the day by volume",
        _FP, "waiting for a better print trades fill probability for price improvement",
        (("desks/mt5/research/execution_science.py", r"def "),
         ("desks/mt5/mt5desk/families.py", r"spread_state")),
        "execution science and the spread-state family",
        "a spread-and-deviation release rule in the executor, judged on realised cost",
        "paired fills with and without the release rule",
        evidence=(f"{LEAN}/Algorithm.Framework/Execution/StandardDeviationExecutionModel.py",
                  f"{LEAN}/Algorithm.Framework/Execution/SpreadExecutionModel.py"),
        keywords=("deviation", "spread")),
    Capability(
        "lean_ema_cross", "quantconnect_lean", "EMA cross alpha model", "alpha",
        "a fast exponential moving average crossing a slow one predicts the direction of the "
        "next move",
        _FP, "slow-moving information and herding make trends persist",
        (("desks/mt5/mt5desk/families.py", r"trend_ma_cross"),),
        "the trend_ma_cross family",
        "already a registered family", "already judged by the gauntlet",
        evidence=(f"{LEAN}/Algorithm.Framework/Alphas/EmaCrossAlphaModel.py",),
        keywords=("EMA", "cross"),
        challenger={"family": "trend_ma_cross",
                    "symbols": ("EURUSD", "USDJPY", "XAUUSD", "US500")}),
    Capability(
        "lean_ibs_reversion", "quantconnect_lean", "internal bar strength reversion", "alpha",
        "equity indices ranked on yesterday's internal bar strength (close relative to the "
        "day's range): the highest is predicted to fall and the lowest to rise the next day",
        _FP, "a close pinned to the day's extreme marks one-sided flow that is partly reversed "
        "when liquidity returns",
        (("desks/mt5/mt5desk/families_cross_sectional.py", r"cross_sectional_class_reversal"),
         ("desks/mt5/mt5desk/families_cross_sectional.py", r"(?i)\bibs\b|internal.bar")),
        "close-to-close class reversal exists; no range-position (IBS) score",
        "an IBS score for the index class book: (close - low) / (high - low) on daily bars",
        "the IBS class book against close-to-close class reversal on the same index class",
        evidence=(f"{LEAN}/Algorithm.Python/Alphas/GlobalEquityMeanReversionIBSAlpha.py",),
        keywords=("IBS", "Internal Bar Strength", "mean reversion"),
        challenger={"symbols": ("US500", "NAS100", "US30", "GER40", "UK100", "JPN225",
                                "AUS200", "HK50", "EUSTX50", "FRA40"),
                    "text": "Rank the MT5 index CFDs daily on internal bar strength, "
                            "(close - low) / (high - low) of the prior day; short the highest, "
                            "long the lowest, hold one day. Needs an IBS score in the index "
                            "class book; close-to-close reversal is not the same rule."}),
    # ------------------------------------------------------------------ Numerai -------------
    Capability(
        "numerai_era_validation", "numerai", "per-era scoring", "method",
        "predictions are scored era by era and judged on the mean and the consistency (Sharpe) "
        "of the per-era correlations, not on one pooled number",
        _FP, "a signal that works in a few regimes and fails in most is not one signal",
        (("desks/mt5/scripts/external_gauntlet.py", r"(?i)fold"),),
        "the gauntlet's walk-forward folds",
        "already folded; the gap, if any, is a per-fold consistency statistic in the verdict",
        "fold-Sharpe as a gate statistic against the pooled one, on placebo controls",
        keywords=("era", "sharpe")),
    Capability(
        "numerai_feature_neutral", "numerai", "feature-neutral correlation", "method",
        "a prediction is scored after neutralising it to the features, so credit goes to what "
        "is not a linear restatement of known inputs",
        _FP, "exposure to a known factor is cheap to buy elsewhere; only the residual is paid",
        (("libs/research/alpha_dsl.py", r"(?i)neutrali[sz]e"),
         ("libs/research/adapters/numerai_method.py", r"era_corr")),
        "a neutralise operator in the DSL and the Numerai method adapter",
        "neutralise a cell's signal to the desk's known families before judging",
        "survivors with and without neutralisation, on placebo controls",
        evidence=(f"{NUMERAI_TOOLS}/numerai_tools/scoring.py",),
        keywords=("neutralize", "neutral_contribution")),
    Capability(
        "numerai_mmc", "numerai", "meta-model contribution", "method",
        "a model is paid for what it adds to the stake-weighted meta model, measured as its "
        "correlation with the target after orthogonalising to the meta model",
        _FP, "a crowd pays for marginal information, not for agreeing with itself",
        (("desks/mt5/research/docket_keff.py", r"def cell_key"),
         ("desks/mt5/research/orthogonality_yield.py", r"def ")),
        "marginal k_eff on the docket and orthogonality yield",
        "credit a producer by its survivors' marginal contribution to the live book",
        "producer budgets steered by marginal contribution against by survivor count",
        evidence=(f"{NUMERAI_TOOLS}/numerai_tools/scoring.py",),
        keywords=("correlation_contribution", "orthogonalize", "stake_weight")),
    Capability(
        "numerai_purged_cv", "numerai", "purged, embargoed cross-validation", "method",
        "folds drop the observations whose labels overlap the test window and hold out an "
        "embargo after it, so overlapping targets cannot leak",
        _PEER, "overlapping labels make a naive fold optimistic",
        (("libs/autodiscovery/validation.py", r"_CPCV_PURGE"),),
        "CPCV with purge and embargo in the validation library",
        "the same purge on the sealed gauntlet's folds",
        "fold results with and without the purge on a leaking twin",
        keywords=()),
    # ------------------------------------------------------------------ Man AHL -------------
    Capability(
        "ahl_multi_speed_trend", "man_ahl", "multi-speed volatility-scaled trend", "alpha",
        "trend signals at several speeds are blended and each position is scaled by the "
        "instrument's own volatility",
        _PEER, "trends persist across horizons for different participants; blending speeds "
        "diversifies the turning-point loss",
        (("desks/mt5/mt5desk/family_multi_speed_trend.py", r"def "),),
        "the multi-speed trend family",
        "already a registered family", "already judged by the gauntlet",
        keywords=("trend", "momentum"),
        challenger={"family": "momentum_volgate",
                    "symbols": ("XAUUSD", "EURUSD", "USDJPY", "XTIUSD", "US500")}),
    Capability(
        "ahl_backtest_haircut", "man_ahl", "multiple-testing haircut on backtests", "method",
        "a backtested Sharpe ratio is haircut for the number of strategies tried before it "
        "is believed",
        _PEER, "the best of many noisy trials is biased upward by construction",
        (("libs/research/intraday_rotation.py", r"def deflated_sharpe"),
         ("desks/mt5/research/alpha_recombination.py", r"def dsr_bar")),
        "the deflated-Sharpe gate and the trials-charged DSR bar",
        "already a gate", "already measured on every certificate",
        keywords=("overfitting", "multiple testing", "backtest")),
    Capability(
        "ahl_execution_research", "man_ahl", "execution cost attribution", "method",
        "every fill is compared with its decision price and the shortfall is attributed and "
        "fed back to the cost model",
        _PEER, "unmeasured slippage is a silent tax on every sleeve",
        (("desks/mt5/research/fill_attribution.py", r"def "),
         ("desks/mt5/research/cost_surface.py", r"def ")),
        "fill attribution and the cost surface",
        "already measured per fill", "already a leg",
        keywords=("execution", "slippage", "cost")),
)

_ANCHOR_SCAN_ROOTS = ("libs", "desks/mt5", "scripts", "ops")


# ---------------------------------------------------------------------------- the access law --
FetchFn = Callable[[str], tuple[int | None, str]]


class Gate:
    """Terms, licence and robots, in that order, over an injected transport.

    `fetch(url) -> (status, text)`; status None means a transport failure. One robots read and
    one licence read per pass; a host is asked again no sooner than HOST_SPACING_S."""

    def __init__(self, fetch: FetchFn, *, spacing_s: float = HOST_SPACING_S,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._fetch = fetch
        self._spacing = spacing_s
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | str] = {}
        self._licences: dict[str, tuple[str | None, str]] = {}
        self.requests = 0

    def _get(self, url: str) -> tuple[int | None, str]:
        host = urllib.parse.urlsplit(url).netloc
        wait = self._last.get(host, -1e18) + self._spacing - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last[host] = self._clock()
        self.requests += 1
        try:
            return self._fetch(url)
        except Exception as exc:  # the transport may never take the pass down
            return None, f"{type(exc).__name__}: {exc}"[:160]

    def robots(self, url: str) -> str | None:
        """None when robots.txt allows this exact path for our agent, else why not."""
        parts = urllib.parse.urlsplit(url)
        key = f"{parts.scheme}://{parts.netloc}"
        if key not in self._robots:
            status, text = self._get(f"{key}/robots.txt")
            rp = urllib.robotparser.RobotFileParser()
            out: urllib.robotparser.RobotFileParser | str
            if status is not None and 200 <= status < 300:
                rp.parse(text.splitlines())
                out = rp
            elif status in (404, 410):
                rp.parse([])
                out = rp
            elif status in (401, 403):
                rp.parse(["User-agent: *", "Disallow: /"])
                out = rp
            else:
                out = (f"robots.txt unreadable (HTTP {status})" if status is not None
                       else f"robots.txt unreadable ({text[:60]})")
            self._robots[key] = out
        rules = self._robots[key]
        if isinstance(rules, str):
            return rules
        if not rules.can_fetch(UA, url):
            return "robots.txt disallows this path"
        return None

    def licence(self, licence_url: str) -> tuple[str | None, str]:
        """(licence name, why). A missing, unreadable or non-permissive LICENSE is (None, why)."""
        if licence_url in self._licences:
            return self._licences[licence_url]
        refused = self.robots(licence_url)
        if refused:
            got: tuple[str | None, str] = (None, f"LICENSE not read: {refused}")
        else:
            status, text = self._get(licence_url)
            if status is None or not 200 <= status < 300:
                got = (None, f"no readable LICENSE at {licence_url} (HTTP {status}); a "
                             "repository with no licence grants nothing, so it stays closed")
            else:
                name = next((n for n, rx in PERMISSIVE_LICENCES if re.search(rx, text[:20_000])),
                            None)
                got = ((name, f"LICENSE reads {name}") if name else
                       (None, "LICENSE is not a permissive licence; the repository stays closed"))
        self._licences[licence_url] = got
        return got

    def licence_of(self, src: Source) -> str | None:
        """The licence name the quoted text of this route travels under, or None if unknown."""
        if src.licence_url:
            return self._licences.get(src.licence_url, (None, ""))[0]
        return ARXIV_LICENCE if src.kind == "arxiv" else None

    def read(self, src: Source, url: str) -> tuple[str, str, str]:
        """(outcome, detail, text). Outcomes: FETCHED, TERMS_FAIL_CLOSED, LICENCE_FAIL_CLOSED,
        ROBOTS_REFUSED, UNREACHABLE."""
        if src.machine_use != PERMITTED:
            return "TERMS_FAIL_CLOSED", f"{src.machine_use}: {src.basis}", ""
        if src.licence_url:
            name, why = self.licence(src.licence_url)
            if name is None:
                return "LICENCE_FAIL_CLOSED", why, ""
        refused = self.robots(url)
        if refused:
            return "ROBOTS_REFUSED", refused, ""
        status, text = self._get(url)
        if status is None or not 200 <= status < 300:
            return "UNREACHABLE", f"HTTP {status}" if status is not None else text[:120], ""
        return "FETCHED", f"HTTP {status}", text[:MAX_BYTES]


def _default_fetch(url: str) -> tuple[int | None, str]:
    from libs.data import polite_fetch as pf
    r = pf.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=20.0, retries=1,
               leg=LEG, max_bytes=MAX_BYTES)
    if r.status is None:
        return None, r.error or "transport failure"
    return r.status, r.text


# ---------------------------------------------------------------------------------- the diff --
def _scan_texts(root: Path) -> dict[str, str]:
    """Every non-test Python file under the scan roots, by repo-relative path."""
    out: dict[str, str] = {}
    for sub in _ANCHOR_SCAN_ROOTS:
        base = root / sub
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            rel = p.relative_to(root).as_posix()
            if "/tests/" in f"/{rel}" or p.name.startswith("test_") or "/data/" in rel:
                continue
            with contextlib.suppress(OSError):
                out[rel] = p.read_text("utf-8", errors="ignore")
    return out


def _has_consumer(rel: str, texts: Mapping[str, str]) -> bool:
    """Another non-test module names this one (import or dotted path). A file named by nothing
    is code with nothing on the other end -- built, not wired."""
    stem = re.escape(Path(rel).stem)
    # An IMPORT or a path to the file, never a bare word: `validation` or `families` appear as
    # ordinary words in hundreds of files, and a word is not a consumer.
    rx = re.compile(rf"^\s*import\s+(?:[\w.]+\.)?{stem}\b"
                    rf"|^\s*from\s+(?:[\w.]+\.)?{stem}\s+import\b"
                    rf"|^\s*from\s+[\w.]+\s+import\s+\(?[^\n]*\b{stem}\b"
                    rf"|\b{stem}\.py\b", re.M)
    return any(other != rel and rx.search(t) for other, t in texts.items())


def measure(cap: Capability, root: Path, texts: Mapping[str, str]) -> dict[str, Any]:
    """The capability's status on THIS tree. Read, never written down."""
    found: list[dict[str, Any]] = []
    for rel, pattern in cap.anchors:
        p = root / rel
        try:
            body = texts.get(rel) if rel in texts else p.read_text("utf-8", errors="ignore")
        except OSError:
            body = None
        hit = bool(body is not None and re.search(pattern, body))
        found.append({"path": rel, "pattern": pattern, "file_exists": body is not None,
                      "present": hit,
                      "has_consumer": bool(hit and _has_consumer(rel, texts))})
    n = len(found)
    k = sum(1 for a in found if a["present"])
    if n == 0 or k == 0:
        status = "GAP"
    elif k < n:
        status = "PARTIAL"
    elif any(a["has_consumer"] for a in found):
        status = "COVERED"
    else:
        status = "EXISTS_NO_CONSUMER"
    return {"status": status, "anchors_present": k, "anchors_total": n, "anchors": found}


def _registration(cap: Capability, status: str) -> dict[str, Any]:
    """Walk the eight stations through capability_challenger.register (the shared validator)."""
    try:
        from libs.research import capability_challenger as cc
    except Exception as exc:  # pragma: no cover - the module is on LIVE
        return {"status": UNMEASURED, "why": f"capability_challenger unavailable: {exc}"}
    gap = {"COVERED": "none measured: every anchor present and consumed",
           "EXISTS_NO_CONSUMER": "built but nothing consumes it",
           "PARTIAL": "some anchors absent",
           "GAP": "no desk equivalent found"}[status]
    return cc.register(cc.Capability(
        name=cap.id, public_capability=cap.public_capability, evidence_grade=cap.evidence_grade,
        economic_mechanism=cap.economic_mechanism, desk_analogue=cap.desk_analogue, gap=gap,
        solo_scale_implementation=cap.solo_scale_implementation,
        controlled_test=cap.controlled_test, source=", ".join(cap.evidence)))


# --------------------------------------------------------------------------------- the state --
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    """Write to a sibling temp file and move it over the target. Windows refuses os.replace onto
    a read-only destination, so the target's read-only bit is cleared first when it is set."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str), "utf-8")
    with contextlib.suppress(OSError):
        if path.exists() and not os.access(path, os.W_OK):
            os.chmod(path, 0o644)
    os.replace(tmp, path)


def _universe() -> set[str]:
    meta = _read_json(UNIVERSE, {})
    return {str(k).upper() for k in meta} if isinstance(meta, dict) else set()


def _may_hypothesise(symbol: str, family: str | None) -> bool:
    try:
        from research import universe_policy as up
        return bool(up.may_hypothesise(symbol, family))
    except Exception:
        return False   # an unreadable policy names nothing: absence is not a permission


# ---------------------------------------------------------------------------- the challengers --
def challenger_rows(caps: Sequence[Capability], diff: Mapping[str, Mapping[str, Any]],
                    universe: set[str], evidence_text: Mapping[str, str],
                    licences: Mapping[str, str | None] | None = None) -> list[dict[str, Any]]:
    """One row per alpha capability that is not COVERED and carries a challenger spec.

    ATTRIBUTION TRAVELS WITH THE QUOTE (Auditor should-fix, #1020). A row that carries the
    donor's own words carries the licence they are published under and their URL, because the
    seat directory is committed to a public repository. A quote whose licence is not known this
    pass is not carried at all."""
    out: list[dict[str, Any]] = []
    now = _now()
    for cap in caps:
        spec = dict(cap.challenger or {})
        if cap.kind != "alpha" or not spec or diff[cap.id]["status"] == "COVERED":
            continue
        family = spec.get("family")
        symbols = [s for s in spec.get("symbols", ()) if s in universe
                   and _may_hypothesise(s, family)][:4]
        if not symbols:
            continue
        url = cap.evidence[0] if cap.evidence else ""
        licence = (licences or {}).get(url)
        verbatim = evidence_text.get(url, "") if licence else ""
        desc = (f"N8 donor-capability challenger. {DONORS[cap.donor]['name']}: "
                f"{cap.public_capability}. Mechanism: {cap.economic_mechanism}. Our equivalent: "
                f"{cap.desk_analogue} -- measured {diff[cap.id]['status']}. "
                + (str(spec.get("text") or "") + " " if spec.get("text") else "")
                + (f"Donor's own words: {verbatim[:600]} " if verbatim else "")
                + "Concept only, never copied code; stated performance is not evidence.")
        cid = hashlib.sha256(f"{cap.id}|{family}|{','.join(symbols)}|{desc[:200]}"
                             .encode()).hexdigest()[:16]
        row: dict[str, Any] = {
            "source": SOURCE, "challenger_id": cid, "capability_id": cap.id,
            "donor": cap.donor, "title": f"{DONORS[cap.donor]['name']}: {cap.name}",
            "description": desc, "mechanism": cap.economic_mechanism, "symbols": symbols,
            "evidence_grade": cap.evidence_grade, "url": url, "source_url": url,
            "retrieved_at": now, "available_time": now,
            "content_hash": hashlib.sha256(desc.encode()).hexdigest()[:16],
            "region": DONORS[cap.donor]["region"], "language": "en", "lang": "en",
            "consumer": "miner_candidate_compiler -> gauntlet (or -> deepening_worker)"}
        if verbatim:
            row.update({"licence": licence, "quoted_from": url,
                        "attribution": f"{DONORS[cap.donor]['name']}, {url}, {licence}"})
        if family:
            row.update({"kind": "hypothesis", "family": family})
        else:
            row.update({"kind": "story_mechanism", "mechanism_class": "reversal",
                        "mechanism_key": f"{SOURCE}:{cap.id}"})
        out.append(row)
    return out


# ------------------------------------------------------------------------------------ the run --
def _claim_rows(text: str, *, src: Source, url: str, universe: set[str],
                seen: set[str], licence: str | None = None
                ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    from libs.research import mechanism_claims as mc
    r = mc.extract(text, universe=universe or None)
    now = _now()
    src_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rows: list[dict[str, Any]] = []
    for c in r["claims"]:
        if c["claim_hash"] in seen:
            continue
        seen.add(c["claim_hash"])
        rows.append({**c, "kind": "story_mechanism", "ground": f"{SOURCE}:{src.id}",
                     "ground_kind": src.kind, "region": DONORS[src.donor]["region"],
                     "language": "en", "cluster": "west", "source": SOURCE,
                     "route": src.kind, "url": url, "title": src.id,
                     "evidence_grade": "FIRST_PARTY_TECHNICAL_DISCLOSURE"
                     if src.kind == "github" else "ACADEMIC",
                     "published_time": None, "available_time": now, "ingested_time": now,
                     "revision": None, "source_hash": src_hash, "terms_note": src.basis[:160],
                     "fetched_utc": now, "score": mc.claim_score(c), "donor": src.donor,
                     "licence": licence or UNMEASURED, "quoted_from": url})
    counts = {k: int(r.get(k) or 0) for k in ("dropped_venue", "dropped_unmappable",
                                              "duplicate_mechanisms")}
    return rows, counts


def _tasks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The deep forest's own task shape, so the claim walks the forest's path."""
    try:
        import deep_forest_miner as dfm
    except Exception:
        return []
    tasks = []
    for r in rows:
        with contextlib.suppress(Exception):
            t = dfm._task(r, [r])
            t["source"] = SOURCE
            t["donor"] = r.get("donor")
            # The claim sentence is the donor's text: its licence and URL ride the task.
            t["licence"] = r.get("licence") or UNMEASURED
            t["quoted_from"] = r.get("quoted_from") or r.get("url")
            tasks.append(t)
    return tasks


def _plan(sources: Sequence[Source], cursor: int, max_fetches: int) -> list[tuple[Source, str]]:
    """A rotating slice of every (source, url), so each pass reaches new documents and the whole
    list is walked in len/max passes. Fail-closed sources are in the slice too: their refusal is
    recorded every pass at no network cost."""
    flat = [(s, u) for s in sources for u in s.urls]
    if not flat:
        return []
    n = min(max_fetches, len(flat))
    return [flat[(cursor + i) % len(flat)] for i in range(n)]


def run(*, budget_s: float = 240.0, max_fetches: int = MAX_FETCHES, fetch: FetchFn | None = None,
        network: bool = True, write: bool = True, root: Path | None = None,
        sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    started = time.monotonic()
    repo = root or REPO
    state = _read_json(STATE, {})
    state = state if isinstance(state, dict) else {}
    seen_claims: set[str] = set(state.get("claims") or [])
    emitted: set[str] = set(state.get("challengers") or [])
    evidence_seen: dict[str, dict[str, Any]] = dict(state.get("evidence") or {})
    cursor = int(state.get("cursor") or 0)
    universe = _universe()

    # 1. THE DOCUMENTS (first, so a challenger can carry the donor's own words this pass).
    gate = Gate(fetch or _default_fetch, sleep=sleep)
    plan = _plan(SOURCES, cursor, max_fetches) if network else []
    fetch_log: list[dict[str, Any]] = []
    texts_by_url: dict[str, str] = {}
    licence_by_url: dict[str, str | None] = {}
    new_claims: list[dict[str, Any]] = []
    drop_counts = {"dropped_venue": 0, "dropped_unmappable": 0, "duplicate_mechanisms": 0}
    for src, url in plan:
        if time.monotonic() - started > budget_s:
            fetch_log.append({"source": src.id, "url": url, "outcome": "BUDGET_EXHAUSTED"})
            continue
        outcome, detail, text = gate.read(src, url)
        fetch_log.append({"source": src.id, "donor": src.donor, "url": url,
                          "outcome": outcome, "detail": detail[:200], "bytes": len(text)})
        if outcome != "FETCHED":
            continue
        texts_by_url[url] = text
        licence_by_url[url] = gate.licence_of(src)
        if licence_by_url[url] is None:
            continue   # a quote with no known licence is never republished
        rows, counts = _claim_rows(text, src=src, url=url, universe=universe, seen=seen_claims,
                                   licence=licence_by_url[url])
        new_claims.extend(rows)
        for k, v in counts.items():
            drop_counts[k] += v
    attempted = {(e["source"], e["url"]) for e in fetch_log}
    for src in SOURCES:
        for url in src.urls:
            if (src.id, url) not in attempted:
                fetch_log.append({"source": src.id, "donor": src.donor, "url": url,
                                  "outcome": "NOT_ATTEMPTED" if network else "NO_FETCH",
                                  "detail": "outside this pass's rotating slice" if network
                                  else "--no-fetch", "bytes": 0})

    # 2. EVIDENCE FRESHNESS: which capability keywords the donor still states, kept across passes.
    for cap in CAPABILITIES:
        for url in cap.evidence:
            text = texts_by_url.get(url)
            if text is None:
                continue
            hits = [kw for kw in cap.keywords if kw.lower() in text.lower()]
            evidence_seen[f"{cap.id}|{url}"] = {"at": _now(), "keywords_hit": hits,
                                                "keywords_total": len(cap.keywords)}

    # 3. THE DIFF, on this tree.
    texts = _scan_texts(repo)
    diff = {cap.id: measure(cap, repo, texts) for cap in CAPABILITIES}

    # 4. THE CHALLENGERS, and the claims, into the seat directory.
    verbatim = {u: _verbatim_for(t) for u, t in texts_by_url.items()}
    challengers = [r for r in challenger_rows(CAPABILITIES, diff, universe, verbatim,
                                              licence_by_url)
                   if r["challenger_id"] not in emitted]
    tasks = _tasks(new_claims)
    out_rows = challengers + tasks
    out_file: Path | None = None
    if write and out_rows:
        out_file = OUT / f"discoveries_{datetime.now(tz=UTC):%Y%m%d_%H%M}.json"
        try:
            from libs.research.source_provenance import stamp_rows
            stamped = stamp_rows([dict(r) for r in out_rows])
        except Exception:
            stamped = out_rows
        _write_json(out_file, stamped)
        emitted.update(r["challenger_id"] for r in challengers)
        with CLAIMS.open("a", encoding="utf-8") as fh:
            for r in new_claims:
                fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    # 5. THE REPORT.
    caps_out = []
    work_queue = []
    for cap in CAPABILITIES:
        d = diff[cap.id]
        ev = {k.split("|", 1)[1]: v for k, v in evidence_seen.items()
              if k.split("|", 1)[0] == cap.id}
        caps_out.append({
            "id": cap.id, "donor": cap.donor, "name": cap.name, "kind": cap.kind,
            "public_capability": cap.public_capability, "evidence_grade": cap.evidence_grade,
            "desk_analogue": cap.desk_analogue, **d,
            "evidence": list(cap.evidence),
            "evidence_confirmed_online": ev or UNMEASURED,
            "registration": _registration(cap, d["status"]),
            "challenger": ("EMITTED" if any(r["capability_id"] == cap.id for r in challengers)
                           else "HELD" if cap.kind == "alpha" and cap.challenger
                           and d["status"] != "COVERED" else "NONE")})
        if d["status"] != "COVERED":
            work_queue.append({"capability": cap.id, "donor": cap.donor, "status": d["status"],
                               "kind": cap.kind,
                               "next": cap.solo_scale_implementation,
                               "test": cap.controlled_test,
                               "missing_anchors": [a["path"] for a in d["anchors"]
                                                   if not a["present"]]})
    status_rank = {"GAP": 0, "PARTIAL": 1, "EXISTS_NO_CONSUMER": 2}
    work_queue.sort(key=lambda w: (status_rank.get(w["status"], 3), w["kind"] != "alpha"))

    by_donor: dict[str, dict[str, Any]] = {}
    for cap in CAPABILITIES:
        b = by_donor.setdefault(cap.donor, {"name": DONORS[cap.donor]["name"], "capabilities": 0,
                                            "COVERED": 0, "EXISTS_NO_CONSUMER": 0,
                                            "PARTIAL": 0, "GAP": 0})
        b["capabilities"] += 1
        b[diff[cap.id]["status"]] += 1
    outcomes: dict[str, int] = {}
    for e in fetch_log:
        outcomes[e["outcome"]] = outcomes.get(e["outcome"], 0) + 1
    report = {
        "generated_at": _now(), "organ": "western_donor_diff", "seat": SOURCE,
        "law": "N8 donor -> capability -> our equivalent -> gap -> challenger -> gauntlet. "
               "Status is measured on the tree each pass; terms fail closed; licence and "
               "robots are read before any document; claims go to data/intelligence/"
               f"{SOURCE}/ in the deep-forest task shape.",
        "user_agent": UA,
        "donors": by_donor,
        "capabilities": caps_out,
        "work_queue": work_queue,
        "sources": [{"id": s.id, "donor": s.donor, "machine_use": s.machine_use,
                     "basis": s.basis, "licence_url": s.licence_url or None,
                     "n_urls": len(s.urls)} for s in SOURCES],
        "fetch": {"network": network, "requests": gate.requests, "outcomes": outcomes,
                  "log": fetch_log},
        "claims": {"new": len(new_claims), "tasks_written": len(tasks), **drop_counts,
                   "ledger": str(CLAIMS.relative_to(BASE)) if CLAIMS.is_relative_to(BASE)
                   else str(CLAIMS)},
        "challengers": {"new": len(challengers), "emitted_ever": len(emitted),
                        "ids": [r["challenger_id"] for r in challengers]},
        "discoveries_file": str(out_file) if out_file else None,
        "unmeasured": ([] if network else ["fetch: --no-fetch, so no donor document was read "
                                           "and no evidence was confirmed this pass"])
                      + ([] if universe else ["universe.json unreadable: no challenger can "
                                              "name an instrument"]),
        "elapsed_s": round(time.monotonic() - started, 2),
    }
    if write:
        flat = sum(len(s.urls) for s in SOURCES)
        state.update({"claims": sorted(seen_claims), "challengers": sorted(emitted),
                      "evidence": evidence_seen,
                      "cursor": (cursor + len(plan)) % flat if flat and plan else cursor,
                      "runs": int(state.get("runs") or 0) + 1, "updated": _now()})
        _write_json(STATE, state)
        _write_json(REPORT, report)
    return report


def _verbatim_for(text: str) -> str:
    """The donor's own comment block, when a file opens with one (LEAN's alphas do), else ''."""
    lines = [ln.lstrip("# ").rstrip() for ln in text.splitlines()
             if ln.startswith("#") and "Licen" not in ln and "QUANTCONNECT" not in ln
             and "Copyright" not in ln and "apache.org" not in ln.lower()
             and "WITHOUT WARRANTIES" not in ln and "distributed under" not in ln
             and "compliance with" not in ln and "AS IS" not in ln
             and "governing permissions" not in ln]
    return " ".join(ln for ln in lines if ln)[:800]


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--max-fetches", type=int, default=MAX_FETCHES)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(list(argv) if argv is not None else None)
    rep = run(budget_s=a.budget_s, max_fetches=a.max_fetches, network=not a.no_fetch,
              write=not a.dry_run)
    print(json.dumps({"donors": rep["donors"], "fetch": rep["fetch"]["outcomes"],
                      "claims": rep["claims"], "challengers": rep["challengers"],
                      "work_queue": len(rep["work_queue"])}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
