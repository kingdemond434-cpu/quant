"""PUBLIC GOLD-BOT MECHANISM DONOR -- rebuild claims as gauntlet-bound hypotheses.

Source snapshot: basantzp/ai-gold-trading-bot@9f5745a24a46d53ed62b297c976c2ebca05dd47f.
No upstream code is imported.  The claimed win rates and hand-written confidence scores are not
evidence.  The upstream's synthetic-candle and live-to-simulation fallbacks are recorded as
negative controls, never copied.  Four economically testable atoms are mapped onto families the
desk already executes, which deduplicates before expensive testing and charges all descendants
to the ordinary multiplicity ledger downstream.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "gold_public_mechanisms"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "research_reproduction"
UPSTREAM = ("ai_gold_trading_bot",)
FALLBACK = "desk-owned mechanism cards mapped to registered families; foreign code never runs"
SOURCE = "https://github.com/basantzp/ai-gold-trading-bot"
PIN = "9f5745a24a46d53ed62b297c976c2ebca05dd47f"

ATOMS: tuple[dict[str, object], ...] = (
    {
        "id": "trend_filtered_macd_continuation",
        "family": "trend_ma_cross",
        "mechanism": ("trend-following participants reinforce displacement: price on the EMA200 "
                      "trend side and a MACD signal crossover from the opposite side of zero "
                      "marks pullback exhaustion and trend resumption"),
        "falsifier": ("net OOS expectancy is non-positive after broker costs, or the zero-line "
                      "condition adds no held-out value over the family baseline"),
        "recipe": {"trend_anchor": "EMA200", "trigger": "MACD-signal crossover",
                   "state": "bull cross below zero / bear cross above zero"},
    },
    {
        "id": "liquidity_extreme_failed_breakout",
        "family": "failed_breakout",
        "mechanism": ("stop and breakout flow beyond a prior rolling extreme can exhaust when "
                      "price closes back inside; trapped breakout inventory then unwinds"),
        "falsifier": ("close-back-inside plus wick depth does not improve net OOS expectancy "
                      "over an unconditional failed-breakout baseline"),
        "recipe": {"level": "prior rolling extreme", "trigger": "penetrate then close inside",
                   "conditioning": "wick/body and ATR-normalised penetration"},
    },
    {
        "id": "wick_rejection_reversal",
        "family": "failed_breakout",
        "mechanism": ("a large rejection wick beyond a crowded reference level reveals failed "
                      "price acceptance and adverse inventory for late breakout participants"),
        "falsifier": ("wick ratio and penetration depth have no stable incremental OOS value "
                      "after session, volatility and multiple-testing controls"),
        "recipe": {"trigger": "wick beyond level and close back inside",
                   "representations": "wick/body, ATR depth, next-bar confirmation"},
    },
    {
        "id": "ohlcv_failed_auction_proxy",
        "family": "range_reversion",
        "mechanism": ("an excursion outside a rolling median-plus-ATR envelope which immediately "
                      "returns inside is failed price acceptance and may revert toward the median"),
        "falsifier": ("the OHLCV proxy adds no held-out value and does not agree with genuine "
                      "Fusion tick-direction evidence when that evidence is available"),
        "recipe": {"centre": "rolling median close", "envelope": "centre +/- ATR multiple",
                   "activity_proxy": "close location value times tick volume",
                   "truth_label": "OHLCV proxy; not genuine order flow or volume profile"},
    },
)


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    del ctx
    frames = bundle.frames()
    symbols = [f.symbol for f in frames if len(f) >= 300][:8]
    candidates = []
    for atom in ATOMS:
        for symbol in symbols:
            candidates.append(A.candidate(
                str(atom["family"]), [symbol],
                f"{atom['id']}: {atom['mechanism']}; falsifier: {atom['falsifier']}",
                horizon="4h", source=f"{SOURCE}@{PIN}",
                evidence={"source_claim_is_prior_only": True, "recipe": atom["recipe"],
                          "source_commit": PIN, "extraction": "independent reimplementation"}))
    mechanisms = tuple({"kind": "MECHANISM_ATOM", "source": f"{SOURCE}@{PIN}", **atom}
                       for atom in ATOMS)
    methods = (
        {"kind": "CONFLUENCE_ABLATION", "arms": [
            "each atom alone", "each pair", "all atoms", "simple family baseline"],
         "measurement": "incremental held-out net value and effective breadth, not confidence"},
        {"kind": "DATA_INTEGRITY_NEGATIVE_CONTROL",
         "finding": "synthetic candles cannot be relabelled market observations"},
        {"kind": "EXECUTION_SEMANTICS_NEGATIVE_CONTROL",
         "finding": "a failed live action cannot become a successful simulated action"},
        {"kind": "PROXY_TRUTH_SPLIT",
         "finding": "OHLCV close-location activity and median-close bands are proxies; compare "
                    "separately with genuine Fusion tick-direction and quote data"},
    )
    return A.packet(SYSTEM, bundle, trials=0, candidates=candidates, mechanisms=mechanisms,
                    research_methods=methods,
                    note=("source claims are priors; descendants receive normal multiplicity "
                          "and gates"))
