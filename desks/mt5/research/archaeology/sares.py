"""SARES -- THE STRATEGY ARCHAEOLOGY AND REVERSE-ENGINEERING SANDBOX (RESEARCH 11, LAWS 5m).

THE QUESTION THIS ORGAN ANSWERS. Given everything PUBLICLY observable about a trader or a system
-- a statistics page, a trade list, a product description, an interview, a rumour -- what FAMILY
of mechanisms could plausibly have produced the observed behaviour? Never one answer: a smooth
curve with a 90% win rate is a mean-reversion edge, a grid, a short-volatility position, a rebate
scheme and plain luck at the same time, and the falsifier is what separates them.

TEN SPECIALIST AGENTS, each a callable over the population and captures the archaeology
civilization already holds on disk (this module fetches NOTHING; the civilization owns the door):

  performance_archaeologist      the return distribution and everything it implies
  trade_path_reverse_engineer    rules that REPRODUCE the observed decisions
  latent_mechanism_inferencer    a HYPOTHESIS TREE over fifteen mechanism classes
  rule_reconstruction_engine     templates, change-points, behaviour modes, enumerated programs
  strategy_decomposer            signal x regime x entry x exit x sizing x instrument x execution
  mutation_factory               children with a genealogy, so FAMILIES can be judged later
  cross_market_translator        abstract the mechanism, then search Fusion's own registry
  global_archaeologist_swarm     native-language grounds per source layer, never a translation
  fraud_illusion_investigator    martingale, grid, hidden leverage, selection, luck -- each a cell
  counterfactual_reverse_engineer which alternative mechanisms reproduce the same record

EVIDENCE GRADES A-F ON EVERY CELL, exactly as RESEARCH 11 defines them (`GRADES`). A grade is a
statement about the SOURCE, never about the idea: an F-grade rumour may enter cheap exploration
and inherits no credibility from the reputation that carried it, and an A-grade record is still
an unprivileged hypothesis at the ten gates. Leaderboard profitability never bypasses the
gauntlet, and behavioural replication is never proof of the original rules.

GENEALOGY ON EVERY CELL: source -> behaviour -> mechanism -> cell -> mutation. The lineage id is
the hash of the first three, so a family whose every child dies can be retired as a family and a
family that keeps producing survivors can be paid as one.

HISTORY IS MINED AS WELL AS LEADERBOARDS: what once worked, when it decayed, what killed it and
which subcomponent survives -- into NEGATIVE KNOWLEDGE (registry memory and the report), never
into the compiler's docket.

OUTPUT. Registry discoveries (payload kind `sares_hypothesis`, generator
`archaeology:sares:<agent>`, origin as the decompiler's), seat donations the compiler reads at
`desks/mt5/data/intelligence/sares/discoveries_<ts>.json`, and `desks/mt5/reports/SARES.json`.

    python desks/mt5/research/archaeology/sares.py --once --budget-s 900
    python desks/mt5/research/archaeology/sares.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

_DESK = Path(__file__).resolve().parents[2]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deep_forest_miner as dfm  # noqa: E402
import moat_collectors as mc  # noqa: E402
from archaeology import civilization as civ  # noqa: E402
from archaeology import decompiler as dc  # noqa: E402
from archaeology import phenotype as ph  # noqa: E402
from archaeology import snapshots as snap  # noqa: E402

from libs.moat import registry as reg  # noqa: E402
from libs.research import access_classifier as ac  # noqa: E402
from libs.research import polyglot as pg  # noqa: E402
from libs.research import set_aside as sa  # noqa: E402

UNMEASURED = "UNMEASURED"
REPORT: Path = _DESK / "reports" / "SARES.json"
DONATE_DIR: Path = _DESK / "data" / "intelligence" / "sares"
UNIVERSE: Path = _DESK / "data" / "universe" / "universe.json"
GROUNDS: Path = _DESK / "data" / "deep_forest_sources.json"
BUDGET_S = 900.0
KIND = "sares_hypothesis"
SOURCE_TYPE = dc.SOURCE_TYPE
ORIGIN = dc.ORIGIN
GENERATOR = "archaeology:sares"
#: Bounds. A pass is an hour of the intel department, not a Cartesian product.
MAX_SYSTEMS = 40
MAX_CELLS_PER_STRATEGY = 240
MAX_CELLS_PER_PASS = 400
MAX_MUTATIONS = 120
MAX_DONATIONS = 200
MAX_CAPTURE_TEXTS = 40
RULE = ("a public trader is a hypothesis generator, never evidence; every cell carries a grade, a "
        "falsifier and a genealogy; behavioural replication is never proof of the original "
        "rules; leaderboard profitability never bypasses the gauntlet")

AGENTS: tuple[str, ...] = (
    "performance_archaeologist", "trade_path_reverse_engineer", "latent_mechanism_inferencer",
    "rule_reconstruction_engine", "strategy_decomposer", "mutation_factory",
    "cross_market_translator", "global_archaeologist_swarm", "fraud_illusion_investigator",
    "counterfactual_reverse_engineer")

#: RESEARCH 11, verbatim in intent. The grade describes what the SOURCE lets the desk observe.
GRADES: dict[str, str] = {
    "A": "exact public rules and a verified history",
    "B": "detailed public rules, weaker performance evidence",
    "C": "public trades allow behavioural inference",
    "D": "performance statistics only",
    "E": "interview or anecdotal mechanism",
    "F": "rumour or wild claim",
}
#: The confidence prior a cell enters the registry with. F is not zero: it enters CHEAP
#: exploration, which is a lane, not a verdict.
GRADE_PRIOR: dict[str, float] = {"A": 0.55, "B": 0.45, "C": 0.35, "D": 0.25, "E": 0.15,
                                 "F": 0.05}
CHEAP_EXPLORATION: frozenset[str] = frozenset({"E", "F"})
#: Verification classes strong enough to turn public rules into an A.
VERIFIED_FLOOR = 0.6

#: The decomposition axes. Sizing tags are the allocator's vocabulary, and every one of them
#: scales UP on evidence: nothing here is a cap (growth governance rule 2).
REGIMES: tuple[str, ...] = ("none", "high_vol", "low_vol", "trending", "ranging")
ENTRIES: tuple[str, ...] = ("market", "stop_through_level", "limit_pullback", "next_bar_open")
EXITS: tuple[str, ...] = ("fixed_rr", "time_stop", "trailing_atr", "opposite_signal")
SIZINGS: tuple[str, ...] = ("fixed_fraction", "vol_target", "evidence_scaled")
EXECUTIONS: tuple[str, ...] = ("immediate", "session_open", "twap_15m")
MUTATIONS: tuple[str, ...] = ("invert_direction", "shift_session", "double_horizon",
                              "halve_horizon", "swap_regime", "swap_exit", "neighbour_instrument")
SESSION_ORDER: tuple[str, ...] = ("asia", "london", "ny", "all")
#: UTC hours within an hour of which an entry counts as fix/auction-adjacent: Tokyo fix (00:55),
#: the London 4pm fix (15:00 UTC in summer, 16:00 in winter) and the NY close.
FIX_HOURS: frozenset[int] = frozenset({0, 1, 15, 16, 21})
#: The source layers the archaeologist swarm asks in (of `polyglot.SOURCE_LAYERS`).
SWARM_LAYERS: tuple[str, ...] = ("practitioner", "retail_ecology", "archive", "media")
#: Asset classes the hypothesis lane admits, by MetaTrader's own registry vocabulary. Single-name
#: equities are the EVENT lane (two-lane mandate) and are set aside by name, never dropped.
HYPOTHESIS_CLASSES: frozenset[str] = frozenset({
    "Forex", "Forex Exotics", "Commodities", "Soft Commodity", "Energy", "Indices", "Bonds",
    "Crypto", "Metals"})


@dataclass(frozen=True)
class Branch:
    """One branch of the hypothesis tree: a mechanism CLASS, the desk families and registered
    contracts that would express it, what would kill it, and the evidence rules that score it."""

    name: str
    what: str
    families: tuple[str, ...]
    contracts: tuple[str, ...]
    falsifier: str
    classes: tuple[str, ...]
    #: (feature, low, high, weight): the feature inside [low, high] SUPPORTS the branch.
    evidence: tuple[tuple[str, float, float, float], ...]
    information: str = "price_only"
    actor: str = ""


_INF = float("inf")
BRANCHES: tuple[Branch, ...] = (
    Branch("trend", "directional persistence over hours to weeks",
           ("trend_ma_cross", "momentum_volgate", "asia_momentum"), ("trend_persistence",),
           "de-trend the entry states: if expectancy vanishes when trend_z at entry is shuffled, "
           "the trend was not the signal",
           ("Forex", "Forex Exotics", "Commodities", "Indices", "Energy"),
           (("payoff", 1.2, _INF, 1.0), ("win_rate", 0.0, 0.5, 0.6), ("trend_beta", 0.0, _INF, 1.0),
            ("holding_hours", 8.0, _INF, 0.6), ("skew", 0.3, _INF, 0.5),
            ("convexity", 0.0, _INF, 0.8))),
    Branch("mean_reversion", "fading moves back to a local anchor",
           ("mean_reversion_rsi", "mean_reversion_bollinger", "range_reversion"),
           ("range_reversion",),
           "condition on realised range: if the edge is only present when the range later "
           "held, the record is short volatility, not reversion",
           ("Forex", "Forex Exotics", "Commodities", "Indices"),
           (("win_rate", 0.6, 1.0, 0.8), ("payoff", 0.0, 1.0, 0.8), ("convexity", -1.0, 0.0, 0.8),
            ("trend_beta", -_INF, 0.0, 1.0), ("holding_hours", 0.0, 12.0, 0.5))),
    Branch("carry", "being paid to hold the position",
           (), ("carry_rollover",),
           "strip the swap: if per-trade price P&L is <= 0 without the rollover credit, the "
           "mechanism is the financing, and the financing is the venue's",
           ("Forex", "Forex Exotics", "Bonds"),
           (("holding_hours", 48.0, _INF, 1.0), ("frequency_per_day", 0.0, 0.5, 0.6),
            ("abs_directionality", 0.5, 1.0, 0.7), ("vol_beta", -_INF, 0.0, 0.5)),
           information="carry", actor="carry_trader"),
    Branch("breakout", "range expansion through a level with stops behind it",
           ("session_range_breakout", "level_breakout", "volatility_squeeze",
            "failed_breakout"), ("breakout_liquidity",),
           "shuffle the level: if entries at random levels inside the range pay the same, the "
           "level carried no liquidity",
           ("Forex", "Forex Exotics", "Commodities", "Indices", "Energy"),
           (("convexity", 0.0, _INF, 0.7), ("session_max_share", 0.6, 1.0, 0.8),
            ("win_rate", 0.0, 0.5, 0.5), ("vol_beta", 0.0, _INF, 0.6))),
    Branch("liquidity", "providing or taking liquidity where the book is thin",
           ("retail_overlap_reversal", "ict_fvg"), ("breakout_liquidity", "forced_liquidation"),
           "re-price on the desk's own spread surface at the entry minute: if the edge is inside "
           "the spread, it was the maker's rebate",
           ("Forex", "Forex Exotics", "Commodities", "Indices"),
           (("session_max_share", 0.5, 1.0, 0.5), ("holding_hours", 0.0, 4.0, 0.7),
            ("frequency_per_day", 2.0, _INF, 0.5), ("convexity", -1.0, 0.0, 0.4)),
           information="execution"),
    Branch("event_response", "positioning into or reacting after a scheduled release",
           ("vol_transition",), ("macro_release", "inventory_shock"),
           "remove every entry within an hour of a calendar event: if expectancy survives, the "
           "events were coincidence",
           ("Forex", "Forex Exotics", "Commodities", "Indices", "Energy", "Bonds"),
           (("event_sensitivity", 0.3, 1.0, 1.5), ("holding_hours", 0.0, 6.0, 0.4),
            ("vol_beta", 0.0, _INF, 0.5)),
           information="calendar"),
    Branch("volatility", "a long or short volatility position however it was entered",
           ("volatility_squeeze", "vol_mean_reversion", "vol_transition"), ("volatility_shock",),
           "measure convexity: (payoff-1)/(payoff+1) < 0 with vol_beta < 0 is a premium being "
           "collected, and the tail has not arrived yet",
           ("Forex", "Forex Exotics", "Commodities", "Indices", "Energy"),
           (("abs_vol_beta", 0.3, _INF, 1.0), ("convexity", -1.0, -0.2, 0.5),
            ("skew", -_INF, -0.5, 0.5))),
    Branch("market_making", "many tiny round trips paid by the spread",
           (), ("execution_microstructure",),
           "bill each trade the desk's measured half-spread: a market maker's edge is negative "
           "at a taker's cost",
           ("Forex", "Indices"),
           (("holding_hours", 0.0, 1.0, 1.0), ("frequency_per_day", 5.0, _INF, 1.0),
            ("win_rate", 0.6, 1.0, 0.5), ("payoff", 0.0, 1.0, 0.5)),
           information="execution", actor="market_maker"),
    Branch("relative_value", "one leg against another, the spread mean-reverting",
           (), ("relative_value_dislocation",),
           "test each leg alone: relative value is dead if either leg carries the whole P&L",
           ("Forex", "Forex Exotics", "Indices", "Commodities"),
           (("n_assets", 2.0, _INF, 1.0), ("correlation", -1.0, 0.0, 1.0),
            ("abs_directionality", 0.0, 0.3, 0.7))),
    Branch("lead_lag", "one instrument answering another with a delay",
           (), ("cross_market_lead",),
           "lag the leader by one bar more: a genuine lead survives, a contemporaneous "
           "correlation does not",
           ("Forex", "Forex Exotics", "Indices", "Commodities", "Energy"),
           (("n_assets", 2.0, _INF, 0.8), ("holding_hours", 0.0, 24.0, 0.4),
            ("correlation", 0.3, 1.0, 0.5))),
    Branch("order_flow", "riding or fading a crowd that is positioned",
           ("volume_spike",), ("positioning_crowding", "forced_flow"),
           "shuffle the positioning series in time: if the edge stays, it was never the flow",
           ("Forex", "Forex Exotics", "Commodities", "Indices"),
           (("scaling", 0.0, _INF, 0.5), ("frequency_per_day", 1.0, _INF, 0.4),
            ("serial_corr", 0.1, 1.0, 0.6))),
    Branch("seasonality", "the calendar: weekday, turn of month, month, overnight",
           ("dow_effect", "turn_of_month", "calendar_month", "monday_gap",
            "overnight_gap_decay", "overnight_drift"), ("calendar_seasonality",),
           "shift the calendar by one weekday or one week: a seasonal edge does not survive the "
           "shift, a data artefact does",
           ("Forex", "Forex Exotics", "Commodities", "Indices", "Energy"),
           (("dow_concentration", 0.35, 1.0, 1.0), ("hour_concentration", 0.4, 1.0, 0.8),
            ("holding_hours", 12.0, _INF, 0.3)),
           information="calendar"),
    Branch("auction_effects", "fixes, closes and settlements where flow is forced",
           ("london_close_momentum", "comex_settlement"),
           ("fx_fixing_flow", "hedging_demand_close_flow", "session_handover"),
           "move the entry an hour away from the fix: an auction effect vanishes, a session "
           "effect does not",
           ("Forex", "Forex Exotics", "Commodities", "Indices"),
           (("fix_share", 0.4, 1.0, 1.2), ("holding_hours", 0.0, 3.0, 0.5)),
           actor="fixing_hedger"),
    Branch("cross_asset", "one asset class informing another",
           (), ("cross_market_lead", "gamma_hedging_state"),
           "replace the cross-asset input with its own lagged value: the edge must fall",
           ("Forex", "Forex Exotics", "Commodities", "Indices", "Energy", "Bonds"),
           (("n_assets", 3.0, _INF, 0.8), ("correlation", -0.2, 0.2, 0.4),
            ("n_classes", 2.0, _INF, 1.0))),
    Branch("macro", "a slow macro state the position is conditioned on",
           (), ("macro_release", "regime_transition"),
           "condition on the macro state as of the entry, PIT: if the state does not separate "
           "winners from losers, the macro story is a narrative",
           ("Forex", "Forex Exotics", "Commodities", "Indices", "Energy", "Bonds"),
           (("holding_hours", 24.0, _INF, 0.6), ("event_sensitivity", 0.2, 1.0, 0.6),
            ("frequency_per_day", 0.0, 0.3, 0.5), ("n_classes", 2.0, _INF, 0.4)),
           information="macro"),
)
BY_BRANCH: dict[str, Branch] = {b.name: b for b in BRANCHES}

#: The behavioural templates the RULE RECONSTRUCTION ENGINE compares against: a signature of
#: where in the day the family enters, how long it holds, and the win/payoff band a faithful
#: implementation produces. Resemblance is a similarity, never an identification.
Template = dict[str, Any]
TEMPLATES: tuple[tuple[str, Template], ...] = (
    ("session_range_breakout", {"hours": set(range(7, 11)) | set(range(13, 16)),
                                "hold": (1.0, 12.0), "win": (0.3, 0.55), "payoff": (1.2, 4.0)}),
    ("mean_reversion_rsi", {"hold": (2.0, 48.0), "win": (0.55, 0.9), "payoff": (0.5, 1.2)}),
    ("mean_reversion_bollinger", {"hold": (1.0, 36.0), "win": (0.55, 0.9),
                                  "payoff": (0.5, 1.2)}),
    ("range_reversion", {"hours": set(range(0, 8)), "win": (0.55, 0.9), "payoff": (0.4, 1.1),
                         "hold": (0.5, 10.0)}),
    ("trend_ma_cross", {"hold": (12.0, 400.0), "win": (0.3, 0.5), "payoff": (1.5, 6.0)}),
    ("momentum_volgate", {"hold": (4.0, 72.0), "win": (0.35, 0.55), "payoff": (1.2, 4.0)}),
    ("volatility_squeeze", {"hold": (2.0, 48.0), "win": (0.35, 0.55), "payoff": (1.3, 5.0)}),
    ("overnight_gap_decay", {"hours": {21, 22, 23, 0, 1}, "hold": (2.0, 12.0),
                             "win": (0.55, 0.8), "payoff": (0.6, 1.3)}),
    ("dow_effect", {"dow_conc": (0.35, 1.0), "hold": (12.0, 120.0)}),
    ("london_close_momentum", {"hours": {15, 16, 17}, "hold": (1.0, 8.0)}),
    ("asia_momentum", {"hours": set(range(0, 8)), "hold": (1.0, 10.0), "payoff": (1.0, 3.0)}),
    ("pullback_entry", {"hold": (4.0, 72.0), "win": (0.4, 0.65), "payoff": (1.0, 3.0)}),
    ("failed_breakout", {"hold": (1.0, 24.0), "win": (0.45, 0.7), "payoff": (0.8, 2.0)}),
)

#: Every illusion the investigator looks for, with the falsifier that would clear it and the
#: desk family whose INFORMATION the illusion was hiding (empty: registry discovery only).
ILLUSIONS: tuple[tuple[str, str, str], ...] = (
    ("martingale", "at unit size the first entries carry positive expectancy", "range_reversion"),
    ("grid", "the closed-P&L curve survives marking the open ladder to market", "range_reversion"),
    ("hidden_leverage", "per-unit expectancy stays positive at 1x", ""),
    ("survivorship", "the archetype's P(survive) beats the population base rate", ""),
    ("resets", "the equity curve is continuous across every account event", ""),
    ("deposit_manipulation", "growth net of deposits equals growth gross of them", ""),
    ("selective_history", "the published window starts at the account's first trade", ""),
    ("demo_or_hypothetical", "a broker-verified statement exists", ""),
    ("unrealistic_execution", "the fills exist at the desk's measured latency and spread", ""),
    ("rebates", "expectancy survives without the per-lot rebate", ""),
    ("copy_artefact", "the timestamps are not another account's", ""),
    ("short_volatility", "the edge survives the first realised-vol shock in the sample",
     "vol_mean_reversion"),
    ("tail_selling", "the payoff ratio survives one tail event", "vol_mean_reversion"),
    ("competition_gaming", "the same mechanism pays outside the contest window", ""),
    ("luck", "the per-trade t-statistic exceeds 2 out of sample", ""),
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _sha(obj: Any, n: int = 16) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:n]


def _fin(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _mean(a: Sequence[float]) -> float | None:
    return float(np.mean(a)) if len(a) else None


def _std(a: Sequence[float]) -> float | None:
    return float(np.std(a)) if len(a) >= 2 else None


def _skew(a: Sequence[float]) -> float | None:
    if len(a) < 3:
        return None
    x = np.asarray(a, dtype=float)
    s = float(np.std(x))
    return None if s <= 0 else float(np.mean(((x - x.mean()) / s) ** 3))


def _kurtosis(a: Sequence[float]) -> float | None:
    if len(a) < 4:
        return None
    x = np.asarray(a, dtype=float)
    s = float(np.std(x))
    return None if s <= 0 else float(np.mean(((x - x.mean()) / s) ** 4) - 3.0)


def _autocorr(a: Sequence[float]) -> float | None:
    if len(a) < 4:
        return None
    x = np.asarray(a, dtype=float) - float(np.mean(a))
    den = float(np.dot(x, x))
    return None if den <= 0 else float(np.dot(x[:-1], x[1:]) / den)


def _cv(a: Sequence[float]) -> float | None:
    m = _mean(a)
    s = _std(a)
    return None if m is None or s is None or abs(m) <= 0 else s / abs(m)


def _hhi(counts: Mapping[Any, int]) -> float | None:
    tot = float(sum(counts.values()))
    return None if tot <= 0 else float(sum((n / tot) ** 2 for n in counts.values()))


def _drawdown(pnl: Sequence[float]) -> tuple[float | None, float | None]:
    """(max drawdown in P&L units, drawdown / peak) on the cumulative closed P&L."""
    if not pnl:
        return None, None
    cum = np.cumsum(np.asarray(pnl, dtype=float))
    peak = np.maximum.accumulate(np.maximum(cum, 0.0))
    dd = float(np.max(peak - cum))
    top = float(np.max(peak))
    return dd, (dd / top if top > 0 else None)


def _trades_of(system_rows: Any, trade_paths: Mapping[str, Sequence[Mapping[str, Any]]] | None
               ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    header, trades = ph._split(system_rows)
    sid = str(header.get("system_id") or header.get("id") or "")
    if not trades and trade_paths and sid in trade_paths:
        trades = [dict(t) for t in trade_paths[sid]]
    return header, trades


def _parsed(trades: Sequence[Mapping[str, Any]]) -> dict[str, list[Any]]:
    """The columns every agent reads, parsed once: opens, closes, sides, lots, profits, symbols."""
    return {"opens": [ph._time(ph._first(t, ph._TRADE_KEYS)) for t in trades],
            "closes": [ph._time(ph._first(t, ph._CLOSE_KEYS)) for t in trades],
            "sides": [ph._side(t) for t in trades],
            "lots": [ph._num(ph._first(t, ("lot", "lots", "volume", "size"))) for t in trades],
            "profits": [ph._num(ph._first(t, ("profit", "pnl", "net", "result")))
                        for t in trades],
            "symbols": [str(t.get("symbol") or "").upper() for t in trades],
            "prices": [ph._num(ph._first(t, ("open_price", "price", "entry_price", "entry")))
                       for t in trades]}


# --------------------------------------------------------------------------- grades
def grade_of(header: Mapping[str, Any], *, n_trades: int = 0,
             rules_public: bool = False) -> dict[str, Any]:
    """RESEARCH 11's A-F, from what the source lets the desk OBSERVE. Never from reputation."""
    verification = str(header.get("verification") or "unverified")
    strength = float(snap.VERIFICATION.get(verification, 0.15))
    kind = str(header.get("kind") or "")
    stats = header.get("stats")
    has_stats = isinstance(stats, Mapping) and any(_fin(v) is not None for v in stats.values())
    has_rules = rules_public or kind == "code" or any(
        header.get(k) for k in ("rules", "source_code", "exact_rule", "parameters"))
    anecdote = kind in ("forum", "interview", "institutional", "product") and any(
        header.get(k) for k in ("claim", "mechanism", "name", "title"))
    if has_rules and strength >= VERIFIED_FLOOR and (has_stats or n_trades):
        g = "A"
    elif has_rules:
        g = "B"
    elif n_trades:
        g = "C"
    elif has_stats:
        g = "D"
    elif anecdote:
        g = "E"
    else:
        g = "F"
    return {"grade": g, "meaning": GRADES[g], "prior": GRADE_PRIOR[g],
            "exploration": "cheap" if g in CHEAP_EXPLORATION else "standard",
            "credibility_inherited": False,
            "basis": {"verification": verification, "verification_strength": strength,
                      "public_rules": bool(has_rules), "trades": int(n_trades),
                      "stats": bool(has_stats), "anecdote": bool(anecdote)}}


# --------------------------------------------------------------------------- agent 1
def performance_archaeologist(system_rows: Any, *, bars: Any = None,
                              events: Sequence[Any] | None = None,
                              universe: Mapping[str, Mapping[str, Any]] | None = None,
                              trade_paths: Mapping[str, Sequence[Mapping[str, Any]]] | None = None
                              ) -> dict[str, Any]:
    """AGENT 1. The return distribution, frequency, holding, drawdowns, skew, win rate, payoff,
    serial correlation, session behaviour, exposure, turnover, scaling and regime dependency --
    each a number or UNMEASURED, never an imputed zero. The phenotype's own fields are REUSED."""
    header, trades = _trades_of(system_rows, trade_paths)
    fp = ph.fingerprint({**header, "trades": trades}, bars, events=events)
    fields = dict(fp["fields"])
    stats = ph._stats(header)
    m: dict[str, Any] = {}
    win = ph._pick(stats, "win_rate")
    pf = ph._pick(stats, "profit_factor")
    if win is not None:
        m["win_rate"] = win / 100.0 if win > 1 else win
    if pf is not None and m.get("win_rate") not in (None, 0.0, 1.0):
        p = m["win_rate"]
        m["payoff"] = float(pf) * (1.0 - p) / p
    m["profit_factor"] = pf
    m["n_trades"] = ph._pick(stats, "trades")
    m["growth"] = ph._pick(stats, "growth")
    if trades:
        col = _parsed(trades)
        profits = [p for p in col["profits"] if p is not None]
        opens = [o for o in col["opens"] if o is not None]
        m["n_trades"] = float(len(trades))
        m["mean_pnl"], m["std_pnl"] = _mean(profits), _std(profits)
        m["skew"], m["kurtosis"] = _skew(profits), _kurtosis(profits)
        m["serial_corr"] = _autocorr(profits)
        wins = [p for p in profits if p > 0]
        losses = [-p for p in profits if p < 0]
        if profits:
            m["win_rate"] = len(wins) / float(len(profits))
        if wins and losses:
            m["payoff"] = float(np.mean(wins) / np.mean(losses))
            m["profit_factor"] = float(sum(wins) / sum(losses))
        m["max_drawdown"], m["drawdown_ratio"] = _drawdown(profits)
        t = _std(profits)
        m["t_stat"] = (None if t is None or t <= 0 or m["mean_pnl"] is None
                       else float(m["mean_pnl"] / t * math.sqrt(len(profits))))
        if len(opens) >= 2:
            span_days = max((max(opens) - min(opens)).total_seconds() / 86400.0, 1.0)
            m["frequency_per_day"] = len(opens) / span_days
            lots = [x for x in col["lots"] if x is not None]
            m["turnover_lots_per_day"] = (sum(lots) / span_days) if lots else None
        sessions: dict[str, int] = {}
        hours: dict[int, int] = {}
        dows: dict[int, int] = {}
        for o in opens:
            for s in ph._session_of(o.hour):
                sessions[s] = sessions.get(s, 0) + 1
            hours[o.hour] = hours.get(o.hour, 0) + 1
            dows[o.weekday()] = dows.get(o.weekday(), 0) + 1
        n_open = float(len(opens)) or 1.0
        m["session_shares"] = {k: round(v / n_open, 4) for k, v in sorted(sessions.items())}
        m["weekday_shares"] = {str(k): round(v / n_open, 4) for k, v in sorted(dows.items())}
        m["dow_concentration"] = _hhi(dows)
        m["hour_concentration"] = (max(hours.values()) / n_open) if hours else None
        m["fix_share"] = (sum(v for h, v in hours.items() if h in FIX_HOURS) / n_open
                          if hours else None)
        pairs = [(o, c) for o, c in zip(col["opens"], col["closes"], strict=True)
                 if o is not None and c is not None]
        if pairs:
            conc = [sum(1 for o2, c2 in pairs if o2 <= o < c2) for o, _c in pairs]
            m["exposure_concurrency"] = float(np.mean(conc))
        m["regime_dependency"] = _regime_dependency(trades, col, bars)
        classes = {str((universe or {}).get(s, {}).get("asset_class") or "")
                   for s in col["symbols"] if s} - {""}
        m["n_classes"] = float(len(classes)) if universe else None
    feats = _features(fields, m)
    measured = sorted(k for k, v in m.items() if v is not None and v != UNMEASURED)
    out = {"agent": "performance_archaeologist", "status": "measured" if measured else UNMEASURED,
           "source": fp["source"], "system_id": fp["system_id"], "platform": fp["platform"],
           "phenotype": fields, "metrics": {k: (UNMEASURED if v is None else v)
                                            for k, v in m.items()},
           "features": feats, "measured": measured,
           "unmeasured": sorted(k for k, v in m.items() if v is None or v == UNMEASURED),
           "why": ("" if measured else "neither statistics nor a trade path is observable for "
                                       "this system: every performance measure is UNMEASURED")}
    out["behaviour_id"] = _sha({"f": feats, "s": fp["system_id"], "p": fp["platform"]}, 12)
    return out


def _regime_dependency(trades: Sequence[Mapping[str, Any]], col: Mapping[str, list[Any]],
                       bars: Any) -> dict[str, Any] | str:
    if bars is None:
        return UNMEASURED
    states = []
    for t, o, p in zip(trades, col["opens"], col["profits"], strict=True):
        if o is None or p is None:
            continue
        st = ph._bar_state(bars, str(t.get("symbol") or ""), str(t.get("chart") or "H1"), o)
        if st is not None and st.get("atr_ref"):
            states.append((st["atr"] / st["atr_ref"], st["trend_z"], p))
    if len(states) < 6:
        return UNMEASURED
    vol = np.asarray([s[0] for s in states])
    tz = np.asarray([s[1] for s in states])
    pnl = np.asarray([s[2] for s in states])
    hi = vol >= float(np.median(vol))
    up = tz >= 0
    return {"n": len(states),
            "high_vol_mean": float(pnl[hi].mean()) if hi.any() else None,
            "low_vol_mean": float(pnl[~hi].mean()) if (~hi).any() else None,
            "with_trend_mean": float(pnl[up].mean()) if up.any() else None,
            "against_trend_mean": float(pnl[~up].mean()) if (~up).any() else None}


def _features(fields: Mapping[str, Any], m: Mapping[str, Any]) -> dict[str, float | None]:
    """The inferencer's feature vector. None is UNMEASURED and is scored as absent, never 0."""
    vb = _fin(fields.get("vol_beta"))
    dirn = _fin(fields.get("directionality"))
    ss = m.get("session_shares") if isinstance(m.get("session_shares"), Mapping) else {}
    return {
        "win_rate": _fin(m.get("win_rate")), "payoff": _fin(m.get("payoff")),
        "convexity": _fin(fields.get("convexity")),
        "holding_hours": _fin(fields.get("holding_hours_median")),
        "trend_beta": _fin(fields.get("trend_beta")), "vol_beta": vb,
        "abs_vol_beta": None if vb is None else abs(vb),
        "session_asia": _fin(ss.get("asia")), "session_london": _fin(ss.get("london")),
        "session_ny": _fin(ss.get("ny")),
        "session_max_share": max((float(v) for v in ss.values()), default=None) if ss else None,
        "dow_concentration": _fin(m.get("dow_concentration")),
        "hour_concentration": _fin(m.get("hour_concentration")),
        "fix_share": _fin(m.get("fix_share")), "scaling": _fin(fields.get("scaling")),
        "n_assets": _fin(fields.get("n_assets")), "n_classes": _fin(m.get("n_classes")),
        "correlation": _fin(fields.get("correlation")),
        "abs_directionality": None if dirn is None else abs(dirn),
        "event_sensitivity": _fin(fields.get("event_sensitivity")),
        "serial_corr": _fin(m.get("serial_corr")),
        "frequency_per_day": _fin(m.get("frequency_per_day")), "skew": _fin(m.get("skew")),
        "drawdown_ratio": _fin(m.get("drawdown_ratio")),
        "exposure": _fin(m.get("exposure_concurrency")),
    }


# --------------------------------------------------------------------------- agent 2
def trade_path_reverse_engineer(trades: Sequence[Mapping[str, Any]], *, bars: Any = None,
                                events: Sequence[Any] | None = None) -> dict[str, Any]:
    """AGENT 2. Entry/exit timing, stops, scale-ins, averaging vs pyramiding, trailing, session,
    weekday, event proximity, volatility and trend state -> RULES that reproduce the decisions,
    with the share of decisions the rule set actually reproduces."""
    if not trades:
        return {"agent": "trade_path_reverse_engineer", "status": UNMEASURED, "rules": [],
                "replication_score": None,
                "why": "no public trade path: timing, stops and scaling are UNMEASURED"}
    col = _parsed(trades)
    opens = [o for o in col["opens"] if o is not None]
    holds = [(c - o).total_seconds() / 3600.0 for o, c in zip(col["opens"], col["closes"],
                                                              strict=True)
             if o is not None and c is not None and c >= o]
    profits = [p for p in col["profits"] if p is not None]
    n = float(len(trades))
    rules: list[dict[str, Any]] = []
    sessions: dict[str, int] = {}
    hours: dict[int, int] = {}
    dows: dict[int, int] = {}
    for o in opens:
        for s in ph._session_of(o.hour):
            sessions[s] = sessions.get(s, 0) + 1
        hours[o.hour] = hours.get(o.hour, 0) + 1
        dows[o.weekday()] = dows.get(o.weekday(), 0) + 1
    session = max(sessions, key=lambda k: sessions[k]) if sessions else "all"
    if sessions:
        rules.append({"rule": "enter_in_session", "value": session,
                      "support": round(sessions[session] / n, 4)})
    best_w, best_c = 0, 0
    for w in range(0, 24, 2):
        c = sum(v for h, v in hours.items() if (h - w) % 24 < 4)
        if c > best_c:
            best_w, best_c = w, c
    if hours:
        rules.append({"rule": "enter_in_hour_window_utc", "value": [best_w, (best_w + 4) % 24],
                      "support": round(best_c / n, 4)})
    if dows:
        d = max(dows, key=lambda k: dows[k])
        rules.append({"rule": "weekday_preference", "value": d,
                      "support": round(dows[d] / n, 4),
                      "note": "below 0.3 support this is the absence of a weekday rule"})
    lo_h = hi_h = None
    if holds:
        lo_h, hi_h = float(np.percentile(holds, 10)), float(np.percentile(holds, 90))
        rules.append({"rule": "hold_hours_between", "value": [round(lo_h, 3), round(hi_h, 3)],
                      "support": 0.8, "median": round(float(np.median(holds)), 3)})
    sides = [s for s in col["sides"] if s is not None]
    long_share = (sum(1 for s in sides if s > 0) / float(len(sides))) if sides else None
    if long_share is not None:
        bias = "long" if long_share >= 0.7 else "short" if long_share <= 0.3 else "both"
        rules.append({"rule": "direction_bias", "value": bias,
                      "support": round(max(long_share, 1 - long_share), 4)})
    wins = [p for p in profits if p > 0]
    losses = [-p for p in profits if p < 0]
    lcv, wcv = _cv(losses), _cv(wins)
    stops = (UNMEASURED if lcv is None else
             {"kind": "fixed_stop" if lcv <= 0.35 else "variable_stop", "loss_cv": round(lcv, 4),
              "median_loss": round(float(np.median(losses)), 6)})
    targets = (UNMEASURED if wcv is None else
               {"kind": "fixed_target" if wcv <= 0.35 else "variable_target",
                "win_cv": round(wcv, 4), "median_win": round(float(np.median(wins)), 6)})
    wsk = _skew(wins)
    trailing = (UNMEASURED if wsk is None else
                {"kind": "runner_or_trailing" if wsk > 1.0 else "capped_exit",
                 "win_skew": round(wsk, 4)})
    clusters = ph._clusters(trades)
    adds = [cl for cl in clusters if len(cl) >= 2]
    in_adds = sum(len(cl) for cl in adds)
    scale_ins: dict[str, Any] = {"share_of_trades_in_add_clusters": round(in_adds / n, 4),
                                 "deepest_cluster": max((len(cl) for cl in clusters), default=0),
                                 "n_clusters": len(clusters)}
    style = UNMEASURED
    if adds:
        firsts = [col["profits"][cl[0]] for cl in adds if col["profits"][cl[0]] is not None]
        ratios = []
        for cl in adds:
            ls = [col["lots"][i] for i in cl if col["lots"][i] is not None]
            if len(ls) >= 2 and ls[0]:
                ratios.append(ls[-1] / ls[0])
        grow = float(np.median(ratios)) if ratios else None
        first_mean = _mean(firsts)
        if grow is not None and first_mean is not None:
            style = ("averaging_down" if grow > 1.0 and first_mean < 0 else
                     "pyramiding" if grow > 1.0 else "flat_adds")
        scale_ins.update(lot_growth_median=grow, first_entry_mean_pnl=first_mean)
    ev_times = [e for e in (ph._time(x) for x in (events or [])) if e]
    near = (sum(1 for o in opens if any(abs((o - e).total_seconds()) <= 1800 for e in ev_times))
            / n if ev_times and opens else None)
    vol_state = trend_state = UNMEASURED
    if bars is not None:
        atrs, tzs = [], []
        for t, o in zip(trades, col["opens"], strict=True):
            if o is None:
                continue
            st = ph._bar_state(bars, str(t.get("symbol") or ""), str(t.get("chart") or "H1"), o)
            if st is not None and st.get("atr_ref"):
                atrs.append(st["atr"] / st["atr_ref"])
                tzs.append(st["trend_z"])
        if atrs:
            vol_state = {"atr_ratio_at_entry_median": round(float(np.median(atrs)), 4)}
            trend_state = {"trend_z_at_entry_median": round(float(np.median(tzs)), 4),
                           "with_trend_share": round(float(np.mean(np.asarray(tzs) > 0)), 4)}
    reproduced = 0
    for o, c, s in zip(col["opens"], col["closes"], col["sides"], strict=True):
        ok = o is not None and session in ph._session_of(o.hour)
        if ok and lo_h is not None and c is not None:
            h = (c - o).total_seconds() / 3600.0
            ok = lo_h <= h <= hi_h
        if ok and long_share is not None and s is not None and long_share >= 0.7:
            ok = s > 0
        if ok and long_share is not None and s is not None and long_share <= 0.3:
            ok = s < 0
        reproduced += int(bool(ok))
    return {"agent": "trade_path_reverse_engineer", "status": "measured", "n_trades": len(trades),
            "rules": rules, "replication_score": round(reproduced / n, 4),
            "session": session, "stops": stops, "targets": targets, "trailing": trailing,
            "scale_ins": scale_ins, "averaging_or_pyramiding": style,
            "event_proximity": (UNMEASURED if near is None else round(near, 4)),
            "volatility_state": vol_state, "trend_state": trend_state,
            "proof": False,
            "why": "rules that REPRODUCE the decisions; reproduction is not the original rule"}


# --------------------------------------------------------------------------- agent 3
def _plausibility(feats: Mapping[str, float | None], b: Branch
                  ) -> tuple[float | None, list[str], list[str]]:
    used, missing, num, den = [], [], 0.0, 0.0
    for feat, lo, hi, w in b.evidence:
        v = feats.get(feat)
        if v is None:
            missing.append(feat)
            continue
        used.append(feat)
        den += w
        if lo <= v <= hi:
            num += w
    return (None if den <= 0 else round(num / den, 4)), used, missing


def _seat_branch_names(branches: list[dict[str, Any]]) -> dict[str, Any]:
    """THE PROPOSER SEAT, OPTIONAL: a candidate NAME for what the dig found.

    A dig reconstructs a behaviour and scores plausibility over declared branches. The seat may
    propose what the behaviour IS -- a name and a falsifier -- and may not touch a plausibility,
    a rank, a branch list or a contract. Every branch keeps its own falsifier and the ranking
    above is computed exactly as it is with the seat dark. {} on a box with no panel.
    """
    try:
        from libs.research import proposer_seat as ps
        return ps.ask("archaeology", "names",
                      records=[{"key": str(b.get("name") or ""),
                                "claim": str(b.get("what") or "")[:180]}
                               for b in branches[:10]]).to_row()
    except Exception as exc:                              # pragma: no cover - optional seat
        return {"verdict": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}


def latent_mechanism_inferencer(profile: Mapping[str, Any], *,
                                rules: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """AGENT 3. A HYPOTHESIS TREE over fifteen mechanism classes. Every branch stays on the tree
    with its plausibility, the features that scored it and the features it could not read; a
    branch with nothing measured is UNMEASURED, not absent. Never one answer."""
    feats = dict(profile.get("features") or {})
    if rules and isinstance(rules.get("event_proximity"), (int, float)):
        feats.setdefault("event_sensitivity", float(rules["event_proximity"]))
    branches = []
    for b in BRANCHES:
        p, used, missing = _plausibility(feats, b)
        branches.append({"name": b.name, "what": b.what,
                         "plausibility": UNMEASURED if p is None else p,
                         "used_features": used, "unmeasured_features": missing,
                         "children": [{"family": f, "contracts": list(b.contracts)}
                                      for f in b.families]
                         or [{"family": "", "contracts": list(b.contracts)}],
                         "falsifier": b.falsifier, "asset_classes": list(b.classes)})
    scored = [x for x in branches if x["plausibility"] != UNMEASURED]
    scored.sort(key=lambda x: (-float(x["plausibility"]), x["name"]))
    for i, x in enumerate(scored):
        x["rank"] = i + 1
    return {"agent": "latent_mechanism_inferencer",
            "status": "measured" if scored else UNMEASURED,
            "proposer_seat": _seat_branch_names(branches),
            "root": {"behaviour_id": profile.get("behaviour_id"),
                     "system_id": profile.get("system_id")},
            "n_branches": len(branches), "n_scored": len(scored),
            "branches": branches, "top": [x["name"] for x in scored[:5]],
            "competing": len([x for x in scored if float(x["plausibility"]) >= 0.5]),
            "rule": "never one answer: every branch is kept with its falsifier",
            "why": ("" if scored else "no feature of this system is measured, so no branch can "
                                      "be scored; the tree is UNMEASURED and complete")}


# --------------------------------------------------------------------------- agent 4
def _within(v: float | None, band: tuple[float, float] | None) -> bool | None:
    if v is None or band is None:
        return None
    return band[0] <= v <= band[1]


def rule_reconstruction_engine(trades: Sequence[Mapping[str, Any]],
                               profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """AGENT 4. Simple strategies whose BEHAVIOUR resembles the observed one: template
    resemblance, a CUSUM change-point, behaviour modes (a partition over session x holding x
    size), and enumerated rule programs scored by the decisions they cover. Behavioural
    replication is never proof of the original rules, and every output says so."""
    feats = dict((profile or {}).get("features") or {})
    if not trades and not feats:
        return {"agent": "rule_reconstruction_engine", "status": UNMEASURED, "candidates": [],
                "why": "neither trades nor statistics: nothing to resemble"}
    col = _parsed(trades) if trades else None
    opens = [o for o in (col["opens"] if col else []) if o is not None]
    hours = {o.hour for o in opens}
    hour_counts: dict[int, int] = {}
    for o in opens:
        hour_counts[o.hour] = hour_counts.get(o.hour, 0) + 1
    n_open = float(len(opens)) or 1.0
    candidates = []
    for fam, sig in TEMPLATES:
        checks: dict[str, bool | None] = {
            "holding": _within(feats.get("holding_hours"), sig.get("hold")),
            "win_rate": _within(feats.get("win_rate"), sig.get("win")),
            "payoff": _within(feats.get("payoff"), sig.get("payoff")),
            "weekday": _within(feats.get("dow_concentration"), sig.get("dow_conc"))}
        if "hours" in sig:
            share = sum(v for h, v in hour_counts.items() if h in sig["hours"]) / n_open
            checks["hours"] = (share >= 0.5) if hours else None
        measured = {k: v for k, v in checks.items() if v is not None}
        if not measured:
            continue
        resemblance = sum(1 for v in measured.values() if v) / float(len(measured))
        candidates.append({"family": fam, "resemblance": round(resemblance, 4),
                           "checks": measured, "n_checks": len(measured), "proof": False})
    candidates.sort(key=lambda c: (-c["resemblance"], -c["n_checks"], c["family"]))
    change_point: dict[str, Any] | str = UNMEASURED
    profits = [p for p in (col["profits"] if col else []) if p is not None]
    if len(profits) >= 20:
        x = np.asarray(profits, dtype=float)
        s = np.cumsum(x - x.mean())
        k = int(np.argmax(np.abs(s)))
        if 3 <= k <= len(x) - 4:
            change_point = {"index": k, "at": (opens[k].isoformat() if k < len(opens) else None),
                            "mean_before": round(float(x[:k + 1].mean()), 6),
                            "mean_after": round(float(x[k + 1:].mean()), 6),
                            "method": "cusum"}
    modes: dict[str, Any] | str = UNMEASURED
    programs: list[dict[str, Any]] = []
    if col and len(trades) >= 10:
        rows = []
        for o, c, s in zip(col["opens"], col["closes"], col["sides"], strict=True):
            if o is None:
                continue
            h = None if c is None or c < o else (c - o).total_seconds() / 3600.0
            rows.append({"hour": o.hour, "dow": o.weekday(), "side": s,
                         "hold": ("short" if h is not None and h < 4 else
                                  "day" if h is not None and h < 24 else
                                  "swing" if h is not None else None),
                         "session": (ph._session_of(o.hour) or ["off"])[0]})
        keys: dict[str, int] = {}
        for r in rows:
            key = f"{r['session']}|{r['hold']}|{'long' if (r['side'] or 0) > 0 else 'short'}"
            keys[key] = keys.get(key, 0) + 1
        nn = float(len(rows)) or 1.0
        modes = {"n_modes": sum(1 for v in keys.values() if v / nn >= 0.1),
                 "modes": [{"mode": k, "share": round(v / nn, 4)}
                           for k, v in sorted(keys.items(), key=lambda kv: -kv[1])[:6]],
                 "method": "partition over session x holding bucket x side"}
        preds: list[tuple[str, Any]] = []
        for w in range(0, 24, 4):
            preds.append((f"hour in [{w},{w + 4})", lambda r, w=w: (r["hour"] - w) % 24 < 4))
        for d in range(5):
            preds.append((f"weekday == {d}", lambda r, d=d: r["dow"] == d))
        preds.extend([("side == long", lambda r: (r["side"] or 0) > 0),
                      ("side == short", lambda r: (r["side"] or 0) < 0)])
        for hb in ("short", "day", "swing"):
            preds.append((f"hold == {hb}", lambda r, hb=hb: r["hold"] == hb))
        scored = []
        for i, (na, fa) in enumerate(preds):
            cov = sum(1 for r in rows if fa(r)) / nn
            if cov >= 0.25:
                scored.append((cov * 1.0, na, cov, 1))
            for nb, fb in preds[i + 1:]:
                cov2 = sum(1 for r in rows if fa(r) and fb(r)) / nn
                if cov2 >= 0.25:
                    scored.append((cov2 * 1.5, f"{na} and {nb}", cov2, 2))
        scored.sort(key=lambda t: (-t[0], t[1]))
        programs = [{"program": na, "coverage": round(cov, 4), "predicates": k,
                     "proof": False} for _s, na, cov, k in scored[:6]]
    return {"agent": "rule_reconstruction_engine",
            "status": "measured" if candidates or programs else UNMEASURED,
            "candidates": candidates[:8], "change_point": change_point,
            "behaviour_modes": modes, "programs": programs, "proof": False,
            "why": "behavioural replication is never proof of the original rules"}


# --------------------------------------------------------------------------- agent 5
def strategy_decomposer(strategy: Mapping[str, Any], *,
                        cap: int = MAX_CELLS_PER_STRATEGY) -> dict[str, Any]:
    """AGENT 5. One strategy -> signal x regime x entry x exit x sizing x instrument x execution.
    The full product is COUNTED and reported; the cells are emitted diversity-first (by the sum of
    axis indices) and capped, so one strategy yields hundreds of distinct cells and never the
    Cartesian product."""
    signals = [str(s) for s in (strategy.get("signals") or []) if s] or [""]
    instruments = [str(s).upper() for s in (strategy.get("instruments") or []) if s] or [""]
    axes: list[tuple[str, list[str]]] = [
        ("signal", signals), ("regime", list(REGIMES)), ("entry", list(ENTRIES)),
        ("exit", list(EXITS)), ("sizing", list(SIZINGS)), ("instrument", instruments),
        ("execution", list(EXECUTIONS))]
    sizes = [len(v) for _k, v in axes]
    possible = int(np.prod(sizes))
    combos: list[tuple[int, ...]] = []
    max_sum = sum(s - 1 for s in sizes)
    for target in range(max_sum + 1):
        if len(combos) >= cap:
            break
        stack: list[tuple[int, ...]] = [()]
        while stack and len(combos) < cap:
            prefix = stack.pop()
            depth = len(prefix)
            if depth == len(sizes):
                if sum(prefix) == target:
                    combos.append(prefix)
                continue
            remaining_max = sum(s - 1 for s in sizes[depth + 1:])
            used = sum(prefix)
            for i in range(sizes[depth]):
                if used + i <= target <= used + i + remaining_max:
                    stack.append((*prefix, i))
    gen = dict(strategy.get("genealogy") or {})
    grade = str(strategy.get("grade") or "F")
    cells = []
    for combo in combos:
        choice = {k: v[i] for (k, v), i in zip(axes, combo, strict=True)}
        key = "|".join(choice[k] for k, _v in axes)
        cell_id = "sares:" + _sha({"k": key, "m": strategy.get("mechanism"),
                                   "s": gen.get("source")})
        cells.append(_cell(agent="strategy_decomposer",
                           mechanism=str(strategy.get("mechanism") or "unclassified"),
                           mechanism_id=str(strategy.get("mechanism_id") or ""),
                           family=choice["signal"], symbols=[choice["instrument"]]
                           if choice["instrument"] else [],
                           session=str(strategy.get("session") or "all"),
                           chart=str(strategy.get("chart") or "H1"),
                           horizon=str(strategy.get("horizon") or "sub_4h"),
                           information=str(strategy.get("information") or "price_only"),
                           actor=str(strategy.get("actor") or ""),
                           falsifier=str(strategy.get("falsifier") or ""), grade=grade,
                           genealogy={**gen, "cell": cell_id, "mutation": None},
                           why=f"decomposed from {strategy.get('mechanism')}: {key}",
                           params={k: v for k, v in choice.items()
                                   if k not in ("signal", "instrument")},
                           cell_key=key, cell_id=cell_id))
    return {"agent": "strategy_decomposer", "status": "measured" if cells else UNMEASURED,
            "possible_cells": possible, "emitted": len(cells),
            "distinct": len({c["cell_key"] for c in cells}), "axes": {k: len(v) for k, v in axes},
            "cells": cells, "why": "diversity-first enumeration under a cap, never the product"}


def _cell(*, agent: str, mechanism: str, mechanism_id: str, family: str, symbols: Sequence[str],
          session: str, chart: str, horizon: str, information: str, actor: str, falsifier: str,
          grade: str, genealogy: Mapping[str, Any], why: str, params: Mapping[str, Any],
          cell_key: str, cell_id: str) -> dict[str, Any]:
    g = dict(genealogy)
    g.setdefault("lineage", _sha({"s": g.get("source"), "b": g.get("behaviour"),
                                  "m": g.get("mechanism")}, 12))
    return {"cell_id": cell_id, "kind": KIND, "agent": agent, "generator": f"{GENERATOR}:{agent}",
            "mechanism": mechanism, "mechanism_id": mechanism_id, "family": family,
            "symbol": (symbols[0] if symbols else ""), "symbols": list(symbols),
            "session": session, "chart": chart, "horizon": horizon, "information": information,
            "economic_actor": actor, "falsifier": falsifier, "evidence_grade": grade,
            "grade_meaning": GRADES.get(grade, GRADES["F"]),
            "exploration": "cheap" if grade in CHEAP_EXPLORATION else "standard",
            "credibility_inherited": False, "genealogy": g, "why": why,
            "params": dict(params), "cell_key": cell_key, "proof": False, "copy_trade": False}


# --------------------------------------------------------------------------- agent 6
def mutation_factory(cells: Sequence[Mapping[str, Any]], *, cap: int = MAX_MUTATIONS,
                     neighbours: Mapping[str, Sequence[str]] | None = None) -> dict[str, Any]:
    """AGENT 6. Children of the cells, round-robin over the operators, each carrying the whole
    genealogy (source -> behaviour -> mechanism -> cell -> mutation) so families can be judged
    later as families."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    ops = list(MUTATIONS)
    i = 0
    while len(out) < cap and cells and i < cap * 4:
        parent = dict(cells[i % len(cells)])
        op = ops[(i // max(len(cells), 1)) % len(ops)]
        i += 1
        params = dict(parent.get("params") or {})
        symbols = list(parent.get("symbols") or [])
        session = str(parent.get("session") or "all")
        horizon = str(parent.get("horizon") or "sub_4h")
        if op == "invert_direction":
            params["direction"] = "inverse" if params.get("direction") != "inverse" else "same"
        elif op == "shift_session":
            session = SESSION_ORDER[(SESSION_ORDER.index(session) + 1) % len(SESSION_ORDER)] \
                if session in SESSION_ORDER else "asia"
        elif op == "double_horizon":
            horizon = {"sub_4h": "sub_1d", "sub_1d": "multi_day"}.get(horizon, "multi_day")
        elif op == "halve_horizon":
            horizon = {"multi_day": "sub_1d", "sub_1d": "sub_4h"}.get(horizon, "sub_4h")
        elif op == "swap_regime":
            cur = str(params.get("regime") or "none")
            params["regime"] = REGIMES[(REGIMES.index(cur) + 1) % len(REGIMES)] \
                if cur in REGIMES else "high_vol"
        elif op == "swap_exit":
            cur = str(params.get("exit") or "fixed_rr")
            params["exit"] = EXITS[(EXITS.index(cur) + 1) % len(EXITS)] \
                if cur in EXITS else "time_stop"
        elif op == "neighbour_instrument":
            alts = [a for a in (neighbours or {}).get(str(parent.get("symbol") or ""), [])
                    if a not in symbols]
            if not alts:
                continue
            symbols = [alts[0]]
        key = (f"{parent.get('cell_key')}|{op}|{session}|{horizon}|{symbols}|"
               f"{sorted(params.items())}")
        if key in seen:
            continue
        seen.add(key)
        gen = {**dict(parent.get("genealogy") or {}), "parent_cell": parent.get("cell_id"),
               "mutation": op}
        cell_id = "sares:" + _sha({"k": key, "p": parent.get("cell_id")})
        gen["cell"] = cell_id
        out.append(_cell(agent="mutation_factory", mechanism=str(parent.get("mechanism") or ""),
                         mechanism_id=str(parent.get("mechanism_id") or ""),
                         family=str(parent.get("family") or ""), symbols=symbols,
                         session=session, chart=str(parent.get("chart") or "H1"),
                         horizon=horizon, information=str(parent.get("information") or ""),
                         actor=str(parent.get("economic_actor") or ""),
                         falsifier=str(parent.get("falsifier") or ""),
                         grade=str(parent.get("evidence_grade") or "F"), genealogy=gen,
                         why=f"{op} of {parent.get('cell_id')}", params=params,
                         cell_key=key, cell_id=cell_id))
    return {"agent": "mutation_factory", "status": "measured" if out else UNMEASURED,
            "n_parents": len(cells), "n_children": len(out), "operators": ops, "cells": out,
            "why": ("" if out else "no parent cell to mutate")}


# --------------------------------------------------------------------------- agent 7
def _load_universe() -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(UNIVERSE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return {str(k).upper(): dict(v) for k, v in doc.items() if isinstance(v, Mapping)}


def cross_market_translator(mechanism: str, source_symbol: str,
                            universe: Mapping[str, Mapping[str, Any]], *, limit: int = 12
                            ) -> dict[str, Any]:
    """AGENT 7. Abstract the mechanism into REQUIREMENTS, then search Fusion's own registry for
    instruments that satisfy them. Parameters are never copied: every analogue names what must
    be refitted. Single-name equities are set aside by name (two-lane mandate)."""
    b = BY_BRANCH.get(mechanism)
    classes = set(b.classes) if b else set(HYPOTHESIS_CLASSES)
    src = universe.get(str(source_symbol).upper()) or {}
    src_class = str(src.get("asset_class") or "")
    analogues, excluded = [], []
    for sym, row in universe.items():
        klass = str(row.get("asset_class") or "")
        if sym == str(source_symbol).upper():
            continue
        if not klass:
            excluded.append({"symbol": sym, "why": "UNCLASSIFIED in the registry: hunted by "
                                                   "nothing until classified"})
            continue
        if klass not in HYPOTHESIS_CLASSES:
            excluded.append({"symbol": sym, "why": f"{klass}: event lane, never hunted for a "
                                                   "statistical hypothesis"})
            continue
        if klass not in classes:
            continue
        spread = _fin(row.get("median_spread_pts"))
        analogues.append({"symbol": sym, "asset_class": klass,
                          "same_class_as_source": klass == src_class,
                          "median_spread_pts": spread,
                          "why": f"{mechanism} can live in {klass}; the mechanism is abstract, "
                                 f"the parameters are {sym}'s own to fit"})
    analogues.sort(key=lambda a: (not a["same_class_as_source"],
                                  a["median_spread_pts"] if a["median_spread_pts"] is not None
                                  else _INF, a["symbol"]))
    return {"agent": "cross_market_translator", "mechanism": mechanism,
            "status": "measured" if analogues else UNMEASURED,
            "abstract": {"mechanism": mechanism, "what": (b.what if b else ""),
                         "admissible_classes": sorted(classes),
                         "requirements": ["the mechanism's actor exists in the target market",
                                          "the session structure that carries it exists",
                                          "the cost surface leaves the edge net positive"]},
            "source": {"symbol": str(source_symbol).upper(), "asset_class": src_class},
            "analogues": analogues[:limit], "n_candidates": len(analogues),
            "excluded": excluded[:20], "n_excluded": len(excluded),
            "parameters": {"copied": False,
                           "must_refit": ["lookback", "threshold", "stop_distance",
                                          "session_window", "holding_time"]},
            "why": ("" if analogues else f"no registry instrument in {sorted(classes)} outside "
                                         "the event lane; the translation is UNMEASURED")}


# --------------------------------------------------------------------------- agent 8
def _load_grounds() -> list[dict[str, Any]]:
    try:
        doc = json.loads(GROUNDS.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    rows = doc.get("grounds") if isinstance(doc, Mapping) else doc
    return [dict(r) for r in (rows or []) if isinstance(r, Mapping)]


def global_archaeologist_swarm(grounds: Sequence[Mapping[str, Any]], *,
                               instrument: str = "XAUUSD", per_layer: int = 3) -> dict[str, Any]:
    """AGENT 8. Per language, the grounds by source layer (the ten of `polyglot.SOURCE_LAYERS`)
    and NATIVE queries built from the language's own terminology -- never a translated phrase.
    Every ground carries an access verdict from the classifier; ONLY a refused ground (one of the
    five acts of the hard boundary) gets no query. The quarantine that also silenced ACCESS_UNCLEAR
    grounds was deleted on 2026-09-23 (LAWS 5e), so an unclear ground is planned and queried with
    its label attached. This agent reaches no host: it is the plan the civilization's scout
    fetches. A language with no terminology is UNMEASURED by name."""
    by_lang: dict[str, list[dict[str, Any]]] = {}
    for g in grounds:
        lang = str(g.get("language") or "").strip()
        if lang:
            by_lang.setdefault(lang, []).append(dict(g))
    plan: dict[str, Any] = {}
    n_queries = refused = quarantined = 0
    for lang, rows in sorted(by_lang.items()):
        layers: dict[str, int] = {}
        verdicts: dict[str, int] = {}
        for g in rows:
            layer = pg.GROUND_KIND_LAYER.get(str(g.get("kind") or ""), "source_graph")
            v = ac.classify({"url": str(g.get("url") or ""), "source_class": layer,
                             "obtained": "public_page", "title": str(g.get("name") or "")})
            verdicts[v.access_label] = verdicts.get(v.access_label, 0) + 1
            if v.refused:
                refused += 1
                continue
            # `v.quarantine` is False on every row since LAWS 5e (2026-09-23): the counter is
            # kept so the published plan still carries the key, and it now counts nothing.
            quarantined += int(v.quarantine)
            layers[layer] = layers.get(layer, 0) + 1
        queries: dict[str, list[str]] = {}
        for layer in SWARM_LAYERS:
            if layer not in layers:
                continue
            qs = pg.native_queries(lang, layer, instrument=instrument, limit=per_layer)
            if qs:
                queries[layer] = qs
                n_queries += len(qs)
        missing = pg.layers_unmeasured(lang)
        plan[lang] = {"n_grounds": len(rows), "layers": layers, "access": verdicts,
                      "queries": queries,
                      "status": ("measured" if queries else UNMEASURED),
                      "unmeasured_layers": missing,
                      "why": ("" if queries else
                              "no native terminology for this language's archaeology layers: "
                              "a translated query would find the translated corpus")}
    return {"agent": "global_archaeologist_swarm",
            "status": "measured" if n_queries else UNMEASURED,
            "n_languages": len(plan), "n_grounds": sum(len(v) for v in by_lang.values()),
            "n_queries": n_queries, "refused": refused, "quarantined": quarantined,
            "source_layers": list(pg.SOURCE_LAYERS), "swarm_layers": list(SWARM_LAYERS),
            "languages": plan, "fetched": 0,
            "why": ("" if n_queries else "no ground with a native vocabulary in reach")}


# --------------------------------------------------------------------------- agent 9
def fraud_illusion_investigator(system_rows: Any, *, profile: Mapping[str, Any] | None = None,
                                population: Sequence[Mapping[str, Any]] | None = None,
                                trade_paths: Mapping[str, Sequence[Mapping[str, Any]]] | None
                                = None) -> dict[str, Any]:
    """AGENT 9. Every illusion in `ILLUSIONS`, each DETECTED, NOT_DETECTED or UNMEASURED with
    its evidence. A detection is itself a CELL ("persistent short-vol exposure" is a hypothesis
    about a premium), graded by the record and inheriting no credibility from it."""
    header, trades = _trades_of(system_rows, trade_paths)
    prof = dict(profile or performance_archaeologist({**header, "trades": trades},
                                                    trade_paths=trade_paths))
    feats = dict(prof.get("features") or {})
    metrics = dict(prof.get("metrics") or {})
    stats = ph._stats(header)
    grade = grade_of(header, n_trades=len(trades))["grade"]
    sid = str(header.get("system_id") or header.get("id") or "")
    col = _parsed(trades) if trades else None
    find: dict[str, tuple[str, dict[str, Any]]] = {}

    def _v(cond: bool | None, **ev: Any) -> tuple[str, dict[str, Any]]:
        return ("UNMEASURED" if cond is None else "DETECTED" if cond else "NOT_DETECTED"), ev

    win, payoff, conv = feats.get("win_rate"), feats.get("payoff"), feats.get("convexity")
    ddr, hold, freq = feats.get("drawdown_ratio"), feats.get("holding_hours"), \
        feats.get("frequency_per_day")
    if col:
        clusters = ph._clusters(trades)
        adds = [cl for cl in clusters if len(cl) >= 2]
        ratios, firsts, gap_cvs, flat = [], [], [], 0
        for cl in adds:
            ls = [col["lots"][i] for i in cl if col["lots"][i] is not None]
            if len(ls) >= 2 and ls[0]:
                ratios.append(ls[-1] / ls[0])
                flat += int(max(ls) / min(ls) <= 1.05)
            if col["profits"][cl[0]] is not None:
                firsts.append(col["profits"][cl[0]])
            ps = [col["prices"][i] for i in cl if col["prices"][i] is not None]
            if len(ps) >= 3:
                gaps = [abs(b - a) for a, b in pairwise(ps)]
                cvg = _cv(gaps)
                if cvg is not None:
                    gap_cvs.append(cvg)
        growth = float(np.median(ratios)) if ratios else None
        first_mean = _mean(firsts)
        after_loss = [(a, b) for a, b in zip(col["lots"], col["lots"][1:], strict=False)
                      if a and b]
        loss_prev = [b / a for (a, b), p in zip(after_loss, col["profits"], strict=False)
                     if p is not None and p < 0]
        doubling = (float(np.mean(np.asarray(loss_prev) >= 1.5)) if loss_prev else None)
        deepest = max((len(cl) for cl in clusters), default=0)
        find["martingale"] = _v(
            None if growth is None and doubling is None else bool(
                (growth is not None and growth >= 1.5 and (first_mean or 0.0) <= 0)
                or (doubling is not None and doubling >= 0.5)),
            lot_growth_median=growth, first_entry_mean_pnl=first_mean,
            share_size_up_after_loss=doubling, deepest_cluster=deepest)
        regular = (float(np.median(gap_cvs)) if gap_cvs else None)
        # A timestamped path with NO add-on cluster is a measurement (no ladder), not an absence;
        # only a path without a single readable entry time leaves the grid UNMEASURED.
        timed = any(o is not None for o in col["opens"])
        find["grid"] = _v(
            None if not timed else bool(
                (regular is not None and regular <= 0.25 and deepest >= 3)
                or (deepest >= 3 and flat >= 1)),
            deepest_cluster=deepest, price_gap_cv_median=regular, flat_size_clusters=flat)
        find["copy_artefact"] = _copy_artefact(sid, col, population, trade_paths)
        find["unrealistic_execution"] = _v(
            None if hold is None or win is None else bool(hold <= (2.0 / 60.0) and win >= 0.7),
            holding_hours_median=hold, win_rate=win)
        mean_p, std_p = _fin(metrics.get("mean_pnl")), _fin(metrics.get("std_pnl"))
        find["rebates"] = _v(
            None if freq is None or mean_p is None or std_p is None or payoff is None else bool(
                freq >= 10 and abs(mean_p) < 0.05 * std_p and 0.8 <= payoff <= 1.25),
            frequency_per_day=freq, mean_over_std=(None if not std_p else mean_p / std_p))
        t = _fin(metrics.get("t_stat"))
        find["luck"] = _v(None if t is None else bool(abs(t) < 1.0), t_stat=t,
                          n_trades=len(trades))
    else:
        for k in ("martingale", "grid", "copy_artefact", "unrealistic_execution", "rebates"):
            find[k] = _v(None, why="no public trade path")
        nt = ph._pick(stats, "trades")
        find["luck"] = _v(None if nt is None else bool(nt <= 30), n_trades=nt,
                          why="statistics only: fewer than 30 trades cannot exclude luck")
    find["hidden_leverage"] = _v(
        None if ddr is None or win is None else bool(ddr >= 0.5 and win >= 0.8),
        drawdown_ratio=ddr, win_rate=win, leverage_stat=ph._pick(stats, "leverage"))
    find["short_volatility"] = _v(
        None if conv is None or win is None else bool(conv < -0.3 and win >= 0.75),
        convexity=conv, win_rate=win)
    find["tail_selling"] = _v(
        None if payoff is None or win is None else bool(payoff <= 0.5 and win >= 0.85),
        payoff=payoff, win_rate=win)
    kind = str(header.get("kind") or "")
    growth, months = ph._pick(stats, "growth"), ph._pick(stats, "months")
    if kind == "competition":
        find["competition_gaming"] = _v(
            None if growth is None else bool(growth >= 100 and (months is None or months <= 3)),
            growth=growth, months=months)
    else:
        find["competition_gaming"] = _v(False, why="not a competition record")
    ver = str(header.get("verification") or "")
    demo = header.get("demo") if isinstance(header.get("demo"), bool) else None
    find["demo_or_hypothetical"] = _v(
        True if demo or ver == "hypothetical" else
        False if snap.VERIFICATION.get(ver, 0.0) >= VERIFIED_FLOOR else None,
        verification=ver, demo_flag=demo)
    deposits = ph._pick(stats, "deposits")
    find["deposit_manipulation"] = _v(
        None if deposits is None or growth is None else bool(deposits > 1 and growth > 0),
        deposits=deposits, growth=growth)
    find["resets"] = _v(None if deposits is None else bool(deposits >= 3), deposits=deposits)
    created = ph._time(header.get("account_created") or header.get("created"))
    first = min((o for o in (col["opens"] if col else []) if o is not None), default=None)
    find["selective_history"] = _v(
        None if created is None or first is None else bool(
            (first - created).total_seconds() > 90 * 86400),
        account_created=(created.isoformat() if created else None),
        first_trade=(first.isoformat() if first else None))
    find["survivorship"] = _survivorship(header, population)
    findings, cells = [], []
    for name, falsifier, family in ILLUSIONS:
        verdict, ev = find.get(name, ("UNMEASURED", {}))
        row: dict[str, Any] = {"illusion": name, "verdict": verdict, "evidence": ev,
                               "falsifier": falsifier}
        if verdict == "DETECTED":
            symbols = sorted({s for s in (col["symbols"] if col else []) if s})
            gen = {"source": f"{GENERATOR}:{header.get('platform') or 'population'}:{sid}",
                   "behaviour": prof.get("behaviour_id"), "mechanism": f"illusion:{name}"}
            cell_id = "sares:" + _sha({"i": name, "s": sid, "p": header.get("platform")})
            row["cell"] = _cell(agent="fraud_illusion_investigator",
                                mechanism=f"illusion:{name}",
                                mechanism_id=("volatility_shock" if family == "vol_mean_reversion"
                                              else "range_reversion" if family else ""),
                                family=family, symbols=symbols, session="all", chart="H1",
                                horizon="sub_1d", information="price_only",
                                actor="retail_account", falsifier=falsifier, grade=grade,
                                genealogy={**gen, "cell": cell_id, "mutation": None},
                                why=f"{name} detected on {sid or 'this record'}: the finding is "
                                    f"itself a hypothesis about what the record was exposed to",
                                params={"illusion": name}, cell_key=f"illusion|{name}|{sid}",
                                cell_id=cell_id)
            cells.append(row["cell"])
        findings.append(row)
    detected = [f["illusion"] for f in findings if f["verdict"] == "DETECTED"]
    return {"agent": "fraud_illusion_investigator", "status": "measured",
            "system_id": sid, "grade": grade, "findings": findings, "detected": detected,
            "not_detected": [f["illusion"] for f in findings if f["verdict"] == "NOT_DETECTED"],
            "unmeasured": [f["illusion"] for f in findings if f["verdict"] == "UNMEASURED"],
            "cells": cells, "classification": ("illusion" if detected else "no_illusion_detected"
                                               if any(f["verdict"] == "NOT_DETECTED"
                                                      for f in findings) else UNMEASURED)}


def _copy_artefact(sid: str, col: Mapping[str, list[Any]],
                   population: Sequence[Mapping[str, Any]] | None,
                   trade_paths: Mapping[str, Sequence[Mapping[str, Any]]] | None
                   ) -> tuple[str, dict[str, Any]]:
    mine = {(o.isoformat(), s) for o, s in zip(col["opens"], col["symbols"], strict=True) if o}
    others: dict[str, set[tuple[str, str]]] = {}
    for row in population or []:
        rid = str(row.get("system_id") or "")
        if not rid or rid == sid:
            continue
        _h, tr = _trades_of(row, trade_paths)
        if tr:
            oc = _parsed(tr)
            others[rid] = {(o.isoformat(), s) for o, s in zip(oc["opens"], oc["symbols"],
                                                              strict=True) if o}
    if not mine or not others:
        return "UNMEASURED", {"why": "no other trade path in the population to compare"}
    best = max(((len(mine & o) / float(len(mine)), rid) for rid, o in others.items()),
               default=(0.0, ""))
    return ("DETECTED" if best[0] >= 0.5 else "NOT_DETECTED"), {"overlap": round(best[0], 4),
                                                                 "with": best[1]}


def _survivorship(header: Mapping[str, Any], population: Sequence[Mapping[str, Any]] | None
                  ) -> tuple[str, dict[str, Any]]:
    plat = str(header.get("platform") or "")
    rows = [r for r in (population or []) if str(r.get("platform") or "") == plat]
    dates = sorted({str(r.get("snapshot_at") or "") for r in rows} - {""})
    if len(dates) < 2:
        return "UNMEASURED", {"why": "fewer than two prospective snapshots of this platform"}
    d = snap.diff([r for r in rows if r.get("snapshot_at") == dates[-2]],
                  [r for r in rows if r.get("snapshot_at") == dates[-1]])
    base = len([r for r in rows if r.get("snapshot_at") == dates[-2]]) or 1
    rate = d["n_disappeared"] / float(base)
    return ("DETECTED" if rate >= 0.2 else "NOT_DETECTED"), {"disappearance_rate": round(rate, 4),
                                                             "between": [dates[-2], dates[-1]]}


# --------------------------------------------------------------------------- agent 10
def counterfactual_reverse_engineer(trades: Sequence[Mapping[str, Any]],
                                    tree: Mapping[str, Any], *, bars: Any = None,
                                    seed: int = 7) -> dict[str, Any]:
    """AGENT 10. Which ALTERNATIVE mechanisms reproduce the same record? Leverage alone, the
    grid's accounting, luck (a bootstrap of the per-trade P&L), a volatility premium, the
    dominant session's own drift (with bars), and every tree branch at or above even odds.
    The decompiler's strip-and-ask counterfactual is REUSED, not restated."""
    cf = dc.counterfactual(trades, bars=bars) if trades else {"status": UNMEASURED}
    alts: list[dict[str, Any]] = []
    profits = [p for p in (_parsed(trades)["profits"] if trades else []) if p is not None]
    measured = cf.get("status") == "measured"
    raw = _fin(cf.get("raw_expectancy"))
    unit = _fin(cf.get("unit_size_expectancy"))
    alts.append({"alternative": "pure_leverage",
                 "reproduces": (UNMEASURED if not measured or raw is None or unit is None
                                else bool(raw > 0 >= unit)),
                 "evidence": {"raw_expectancy": raw, "unit_size_expectancy": unit}})
    alts.append({"alternative": "grid_accounting",
                 "reproduces": (UNMEASURED if not measured else
                                bool(cf.get("information_survives") is False
                                     and (cf.get("deepest_cluster") or 0) >= 2)),
                 "evidence": {"first_entry_expectancy": cf.get("first_entry_expectancy"),
                              "deepest_cluster": cf.get("deepest_cluster")}})
    if len(profits) >= 10:
        rng = np.random.default_rng(seed)
        x = np.asarray(profits, dtype=float)
        boots = rng.choice(x, size=(400, x.size), replace=True).mean(axis=1)
        p_le0 = float(np.mean(boots <= 0.0))
        alts.append({"alternative": "luck", "reproduces": bool(p_le0 >= 0.2),
                     "evidence": {"p_mean_le_0_bootstrap": round(p_le0, 4), "n": int(x.size)}})
    else:
        alts.append({"alternative": "luck", "reproduces": UNMEASURED,
                     "evidence": {"why": "fewer than ten trades: luck cannot be bounded"}})
    for b in (tree.get("branches") or []):
        p = b.get("plausibility")
        if p == UNMEASURED or p is None:
            continue
        alts.append({"alternative": f"mechanism:{b['name']}", "reproduces": bool(float(p) >= 0.5),
                     "evidence": {"plausibility": p, "features": b.get("used_features")},
                     "falsifier": b.get("falsifier"), "proof": False})
    session_alt: dict[str, Any] = {"alternative": "session_drift", "reproduces": UNMEASURED,
                                   "evidence": {"why": "needs the desk's bars for the session"}}
    if bars is not None and trades:
        session_alt = _session_drift(trades, bars)
    alts.append(session_alt)
    n_rep = sum(1 for a in alts if a["reproduces"] is True)
    return {"agent": "counterfactual_reverse_engineer",
            "status": "measured" if any(a["reproduces"] != UNMEASURED for a in alts)
            else UNMEASURED,
            "decompiler_counterfactual": cf, "alternatives": alts, "n_reproducing": n_rep,
            "verdict": ("the record is reproduced by " + ", ".join(
                a["alternative"] for a in alts if a["reproduces"] is True)
                        if n_rep else "no measured alternative reproduces the record; the "
                                      "original mechanism remains one hypothesis among the "
                                      "unmeasured ones")}


def _session_drift(trades: Sequence[Mapping[str, Any]], bars: Any) -> dict[str, Any]:
    col = _parsed(trades)
    opens = [o for o in col["opens"] if o is not None]
    sym = next((s for s in col["symbols"] if s), "")
    if not opens or not sym:
        return {"alternative": "session_drift", "reproduces": UNMEASURED,
                "evidence": {"why": "no timestamped entries with a symbol"}}
    try:
        frame = bars(sym, "H1")
    except Exception:
        frame = None
    if frame is None or len(frame) < 30:
        return {"alternative": "session_drift", "reproduces": UNMEASURED,
                "evidence": {"why": f"no H1 bars for {sym}"}}
    hours = {o.hour for o in opens}
    try:
        idx = frame.index
        close = np.asarray(frame["close"], dtype=float)
        rets = np.diff(close) / close[:-1]
        in_session = np.asarray([getattr(t, "hour", -1) in hours for t in idx[1:]])
    except Exception:
        return {"alternative": "session_drift", "reproduces": UNMEASURED,
                "evidence": {"why": "bars unreadable"}}
    if not in_session.any():
        return {"alternative": "session_drift", "reproduces": UNMEASURED,
                "evidence": {"why": "no bar in the entry hours"}}
    drift = float(rets[in_session].mean())
    sides = [s for s in col["sides"] if s is not None]
    bias = float(np.mean(sides)) if sides else 0.0
    profits = [p for p in col["profits"] if p is not None]
    same_sign = bool(profits) and (drift * bias > 0) and (float(np.mean(profits)) > 0)
    return {"alternative": "session_drift", "reproduces": same_sign,
            "evidence": {"session_hour_drift": round(drift, 8), "direction_bias": round(bias, 4)}}


# --------------------------------------------------------------------------- history
KILLERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("venue_rule_change", ("broker change", "broker changed", "ea died after the broker")),
    ("cost_regime", ("spread destroyed", "spread killed", "commission", "swap")),
    ("leverage", ("margin call", "blown account", "blew the account", "account wiped",
                  "martingale blew")),
    ("decay_or_crowding", ("stopped working", "no longer works", "curve fitted",
                           "backtest failed live")),
)


def historical_mining(rows: Sequence[Mapping[str, Any]], texts: Sequence[str], *,
                      trees: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """What once worked, when it decayed, what killed it, which subcomponent survives -- into
    NEGATIVE KNOWLEDGE. The civilization's own failure vocabulary is reused for the killers."""
    fail = civ.failure_scan(list(texts))
    eras: dict[str, int] = {}
    decayed: list[dict[str, Any]] = []
    low_texts = [str(t).lower() for t in texts]
    killers: dict[str, int] = {}
    for name, phrases in KILLERS:
        hits = sum(1 for t in low_texts for p in phrases if p in t)
        if hits:
            killers[name] = hits
    for r in rows:
        era = dc.era_of(str(r.get("snapshot_at") or r.get("published") or ""))
        eras[era] = eras.get(era, 0) + 1
        status = str(r.get("status") or "listed")
        if status in ("listed", ""):
            continue
        sid = str(r.get("system_id") or "")
        tree = (trees or {}).get(sid) or {}
        top = (tree.get("top") or [None])[0]
        fam = ""
        if top and BY_BRANCH.get(top) and BY_BRANCH[top].families:
            fam = BY_BRANCH[top].families[0]
        decayed.append({"system_id": sid, "platform": r.get("platform"),
                        "worked_era": era, "decayed_at": r.get("snapshot_at"),
                        "status": status, "mechanism": top or UNMEASURED,
                        "killer": (max(killers, key=lambda k: killers[k]) if killers
                                   else UNMEASURED),
                        "surviving_subcomponent": fam or UNMEASURED})
    measured = bool(decayed) or bool(killers) or fail.get("status") == "measured"
    return {"status": "measured" if measured else UNMEASURED, "eras": eras,
            "n_decayed": len(decayed), "negative_knowledge": decayed[:50],
            "killers": killers, "failure_vocabulary": fail,
            "why": ("" if measured else "no delisted system and no failure text in reach: the "
                                        "graveyard is UNMEASURED this pass")}


# --------------------------------------------------------------------------- outputs
def record_cells(cells: Sequence[Mapping[str, Any]], *, conn: Any, dry_run: bool
                 ) -> dict[str, Any]:
    """One UNPROCESSED discovery per cell: the compiler's intake reads exactly that state. The
    registry's content hash (source, mechanism, assets, exact rule) makes a re-run idempotent."""
    out: dict[str, Any] = {"recorded": 0, "existing": 0, "errors": 0, "by_agent": {},
                           "dry_run": bool(dry_run), "discovery_ids": []}
    per_gen: dict[str, int] = {}
    for c in cells:
        agent = str(c.get("agent") or "")
        out["by_agent"][agent] = out["by_agent"].get(agent, 0) + 1
        if dry_run:
            out["discovery_ids"].append(f"dry:{c.get('cell_id')}")
            continue
        payload, _removed = dc._scrub(dict(c))
        keep, _refused = dc._asset_lane(list(c.get("symbols") or []))
        try:
            did, created = reg.record_discovery(
                source_id=str((c.get("genealogy") or {}).get("source") or GENERATOR),
                source_type=SOURCE_TYPE, mechanism=str(c.get("mechanism") or ""),
                origin=ORIGIN, generator=str(c.get("generator") or GENERATOR),
                assets=keep, sessions=[str(c.get("session") or "all")],
                horizons=[str(c.get("horizon") or "sub_4h")],
                information=str(c.get("information") or "price_only"),
                actor=str(c.get("economic_actor") or ""),
                economic_rationale=str(c.get("why") or "")[:800],
                falsifier=str(c.get("falsifier") or ""),
                required_data=["public record", "desk PIT bars"],
                confidence=GRADE_PRIOR.get(str(c.get("evidence_grade")), 0.05),
                exact_rule=str(c.get("cell_key") or ""), payload=payload, conn=conn)
        except Exception as exc:  # the registry is never allowed to take the pass down
            out["errors"] += 1
            out.setdefault("last_error", f"{type(exc).__name__}: {str(exc)[:120]}")
            continue
        out["discovery_ids"].append(did)
        out["recorded" if created else "existing"] += 1
        if created:
            per_gen[str(c.get("generator"))] = per_gen.get(str(c.get("generator")), 0) + 1
            if c.get("mechanism_id"):
                reg.link("discovery", did, "mechanism", str(c["mechanism_id"]), "explains",
                         conn=conn)
    for gen_name, n in per_gen.items():
        reg.generator_yield_update(gen_name, generated=n, conn=conn)
    out["discovery_ids"] = out["discovery_ids"][:50]
    return out


def donation_rows(cells: Sequence[Mapping[str, Any]], *, cap: int = MAX_DONATIONS
                  ) -> list[dict[str, Any]]:
    """The compiler's contract: `kind: hypothesis` naming a registered family and declared
    instruments. Higher grades first, round-robin over agents so no one agent owns the docket."""
    eligible = [c for c in cells if c.get("family") and c.get("symbols")]
    eligible.sort(key=lambda c: (str(c.get("evidence_grade") or "F"), str(c.get("cell_id"))))
    by_agent: dict[str, list[Mapping[str, Any]]] = {}
    for c in eligible:
        by_agent.setdefault(str(c.get("agent")), []).append(c)
    rows: list[dict[str, Any]] = []
    while len(rows) < cap and any(by_agent.values()):
        for agent in sorted(by_agent):
            if by_agent[agent] and len(rows) < cap:
                c = by_agent[agent].pop(0)
                rows.append({
                    "source": "sares", "kind": "hypothesis", "sares_kind": KIND,
                    "generator": c.get("generator"),
                    "title": f"SARES {agent}: {c.get('mechanism')} on {c.get('symbol')}",
                    "family": c.get("family"), "symbols": list(c.get("symbols") or []),
                    "mechanism": c.get("mechanism"), "mechanism_id": c.get("mechanism_id"),
                    "mechanism_tags": [t for t in (c.get("family"), c.get("mechanism_id")) if t],
                    "testable_claim": c.get("why"), "falsifier": c.get("falsifier"),
                    "evidence_grade": c.get("evidence_grade"),
                    "exploration": c.get("exploration"), "genealogy": c.get("genealogy"),
                    "session": c.get("session"), "params": c.get("params"),
                    "url": f"sares://{agent}/{c.get('cell_id')}", "copy_trade": False,
                    "credibility_inherited": False, "gauntlet_bypass": False})
    return rows


def donate(rows: Sequence[Mapping[str, Any]], *, at: str = "") -> Path | None:
    if not rows:
        return None
    DONATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = (at or _now()).replace(":", "").replace("-", "")[:15]
    path = DONATE_DIR / f"discoveries_{stamp}.json"
    mc._atomic_json(path, {"source": "sares", "generated_at": _now(), "rule": RULE,
                           "discoveries": [dict(r) for r in rows]})
    return path


# --------------------------------------------------------------------------- the pass
def _usable(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    """Rows the access discipline admits -- which since LAWS 5e (2026-09-23) is EVERY row off the
    five refused acts. A row without labels is labelled NOW; an UNCLEAR access path is kept and
    counted, because the quarantine that used to drop it here is deleted and an unresolved
    permission question is a provenance note, not a verdict about the content."""
    keep: list[dict[str, Any]] = []
    refused = quarantined = 0
    for r in rows:
        row = dict(r)
        if "usable" not in row:
            row.update(snap.labels(str(row.get("access_label") or ""),
                                   str(row.get("credibility") or "")))
        if row.get("refused"):
            refused += 1
            continue
        # COUNTED, NEVER DROPPED. `quarantined` is False on every row now; the counter survives
        # so the published census keeps its key and a fence can assert it stays zero.
        quarantined += int(bool(row.get("quarantined")))
        keep.append(row)
    return keep, refused, quarantined


def _capture_texts(limit: int = MAX_CAPTURE_TEXTS) -> list[str]:
    root = snap.archive_root()
    if not root.exists():
        return []
    files = sorted((p for p in root.rglob("*") if p.is_file()),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for p in files:
        try:
            out.append(dfm.html_text(p.read_text(encoding="utf-8", errors="replace")[:200_000])
                       [:20_000])
        except OSError:
            continue
    return out


def _system_key(r: Mapping[str, Any]) -> tuple[float, float, str]:
    return (-float(r.get("evidence_weight") or 0.0), -float(r.get("verification_prior") or 0.0),
            str(r.get("system_id") or ""))


def run(*, budget_s: float = BUDGET_S, dry_run: bool = False, conn: Any = None,
        population: Sequence[Mapping[str, Any]] | None = None,
        trade_paths: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
        bars: Any = None, universe: Mapping[str, Mapping[str, Any]] | None = None,
        grounds: Sequence[Mapping[str, Any]] | None = None, texts: Sequence[str] | None = None,
        events: Sequence[Any] | None = None, at: str = "") -> dict[str, Any]:
    """ONE PASS OF THE SANDBOX over the population and captures already on disk. Writes nothing
    when `dry_run`; reaches no host in any mode."""
    started = time.monotonic()
    close_after = conn is None and not dry_run
    c = conn if conn is not None else (None if dry_run else reg.connect())
    rows_in = list(population) if population is not None else snap.load_population()
    usable, refused, quarantined = _usable(rows_in)
    usable.sort(key=_system_key)
    uni = dict(universe) if universe is not None else _load_universe()
    grd = list(grounds) if grounds is not None else _load_grounds()
    txt = list(texts) if texts is not None else _capture_texts()
    report: dict[str, Any] = {
        "at": _now(), "budget_s": float(budget_s), "dry_run": bool(dry_run), "fetched": 0,
        "population": {"n": len(rows_in), "usable": len(usable), "refused": refused,
                       "quarantined": quarantined},
        "agents": {a: {"ran": False, "produced": 0, "why": ""} for a in AGENTS},
        "systems": [], "systems_not_reached": 0, "cells": {"n": 0, "by_agent": {}, "by_grade": {}},
        "grades": GRADES, "trees": 0, "illusions_detected": {}, "history": {},
        "swarm": {}, "discoveries": {}, "donations": {"n": 0, "path": None},
        "negative_knowledge_remembered": 0, "unmeasured": [], "rule": RULE}
    cells: list[dict[str, Any]] = []
    trees: dict[str, dict[str, Any]] = {}
    cap_left, mut_left = MAX_CELLS_PER_PASS, MAX_MUTATIONS
    try:
        # MAX_SYSTEMS IS A BATCH BUDGET, NOT A SCREEN (LAWS 7). `systems_not_reached` already
        # counted the remainder in this report; the named refusal puts it where a reader
        # comparing organs can see it, with the ordering key that chose the survivors.
        systems = sa.take(usable, MAX_SYSTEMS, organ="sares", stage="usable_systems",
                          ordering="the order `usable` was assembled in (fetch/rank order)")
        report["systems_not_reached"] = max(0, len(usable) - len(systems))
        for k, row in enumerate(systems):
            if time.monotonic() - started > budget_s * 0.8:
                report["systems_not_reached"] += 1
                continue
            # THE CELL BUDGET IS SHARED, NOT FIRST-COME: each system left gets an equal share of
            # what remains (floored so the last one is not starved), and the mutation factory
            # draws on its own cap so a wide decomposition cannot leave it nothing to mutate.
            per_system = max(24, cap_left // max(1, len(systems) - k))
            header, trades = _trades_of(row, trade_paths)
            sid = str(header.get("system_id") or header.get("id") or "")
            plat = str(header.get("platform") or "population")
            g = grade_of(header, n_trades=len(trades))
            prof = performance_archaeologist({**header, "trades": trades}, bars=bars,
                                             events=events, universe=uni)
            rules = trade_path_reverse_engineer(trades, bars=bars, events=events)
            tree = latent_mechanism_inferencer(prof, rules=rules)
            recon = rule_reconstruction_engine(trades, prof)
            inv = fraud_illusion_investigator({**header, "trades": trades}, profile=prof,
                                              population=usable, trade_paths=trade_paths)
            cf = counterfactual_reverse_engineer(trades, tree, bars=bars)
            trees[sid] = tree
            for name in inv["detected"]:
                report["illusions_detected"][name] = report["illusions_detected"].get(name, 0) + 1
            cells.extend(inv["cells"])
            _mark(report, "performance_archaeologist", prof["status"] == "measured", 1,
                  prof.get("why"))
            _mark(report, "trade_path_reverse_engineer", rules["status"] == "measured",
                  len(rules.get("rules") or []), rules.get("why"))
            _mark(report, "latent_mechanism_inferencer", tree["status"] == "measured",
                  tree["n_scored"], tree.get("why"))
            _mark(report, "rule_reconstruction_engine", recon["status"] == "measured",
                  len(recon.get("candidates") or []) + len(recon.get("programs") or []),
                  recon.get("why"))
            _mark(report, "fraud_illusion_investigator", True, len(inv["cells"]), "")
            _mark(report, "counterfactual_reverse_engineer", cf["status"] == "measured",
                  cf["n_reproducing"], "")
            source_id = f"{GENERATOR}:{plat}:{sid}"
            symbols = sorted({s for s in _parsed(trades)["symbols"] if s}) if trades else []
            sys_cells: list[dict[str, Any]] = []
            translated: dict[str, Any] = {}
            for name in tree["top"][:2]:
                b = BY_BRANCH[name]
                src_sym = symbols[0] if symbols else ""
                translated = cross_market_translator(name, src_sym, uni)
                _mark(report, "cross_market_translator", translated["status"] == "measured",
                      translated["n_candidates"], translated.get("why"))
                instruments = ([src_sym] if src_sym else []) + [
                    a["symbol"] for a in translated["analogues"][:5]]
                strategy = {"mechanism": name, "mechanism_id": (b.contracts[0] if b.contracts
                                                               else ""),
                            "signals": list(b.families) or [""], "instruments": instruments,
                            "session": rules.get("session") or "all", "chart": "H1",
                            "horizon": _horizon(prof), "information": b.information,
                            "actor": b.actor, "falsifier": b.falsifier, "grade": g["grade"],
                            "genealogy": {"source": source_id,
                                          "behaviour": prof["behaviour_id"],
                                          "mechanism": name}}
                dec = strategy_decomposer(strategy, cap=max(0, min(MAX_CELLS_PER_STRATEGY,
                                                                   per_system // 2, cap_left)))
                _mark(report, "strategy_decomposer", dec["status"] == "measured", dec["emitted"],
                      dec.get("why"))
                sys_cells.extend(dec["cells"])
                cap_left -= dec["emitted"]
            neigh = {s: [a["symbol"] for a in translated.get("analogues", [])] for s in symbols}
            mut = mutation_factory(sys_cells[:40], neighbours=neigh,
                                   cap=max(0, min(12, mut_left)))
            _mark(report, "mutation_factory", mut["status"] == "measured", mut["n_children"],
                  mut.get("why"))
            mut_left -= mut["n_children"]
            cells.extend(sys_cells)
            cells.extend(mut["cells"])
            report["systems"].append({
                "system_id": sid, "platform": plat, "grade": g["grade"], "source": prof["source"],
                "n_trades": len(trades), "top_mechanisms": tree["top"],
                "competing": tree["competing"], "replication_score": rules["replication_score"],
                "illusions": inv["detected"], "counterfactual": cf["verdict"][:160],
                "resembles": [x["family"] for x in recon.get("candidates", [])[:3]],
                "cells": len(sys_cells) + len(mut["cells"]) + len(inv["cells"])})
        # ---- once per pass: the swarm and the graveyard --------------------------------------
        swarm = global_archaeologist_swarm(grd)
        report["swarm"] = {k: v for k, v in swarm.items() if k != "languages"}
        report["swarm"]["languages_measured"] = sorted(
            k for k, v in swarm["languages"].items() if v["status"] == "measured")
        report["swarm"]["languages_unmeasured"] = sorted(
            k for k, v in swarm["languages"].items() if v["status"] != "measured")
        _mark(report, "global_archaeologist_swarm", swarm["status"] == "measured",
              swarm["n_queries"], swarm.get("why"))
        hist = historical_mining(usable, txt, trees=trees)
        report["history"] = hist
        if not dry_run and c is not None:
            for nk in hist["negative_knowledge"]:
                reg.remember("sares_negative_knowledge",
                             f"{nk['mechanism']} on {nk['platform']}:{nk['system_id']} decayed "
                             f"({nk['status']}) in {nk['worked_era']}; killer {nk['killer']}; "
                             f"surviving subcomponent {nk['surviving_subcomponent']}",
                             kind="negative_knowledge",
                             memory_key=f"sares:nk:{nk['platform']}:{nk['system_id']}",
                             payload=nk, conn=c)
                report["negative_knowledge_remembered"] += 1
        # ---- outputs ---------------------------------------------------------------------------
        report["trees"] = len(trees)
        report["cells"]["n"] = len(cells)
        for cell in cells:
            a, gr = str(cell["agent"]), str(cell["evidence_grade"])
            report["cells"]["by_agent"][a] = report["cells"]["by_agent"].get(a, 0) + 1
            report["cells"]["by_grade"][gr] = report["cells"]["by_grade"].get(gr, 0) + 1
        report["discoveries"] = record_cells(cells, conn=c, dry_run=dry_run or c is None)
        rows = donation_rows(cells)
        report["donations"]["n"] = len(rows)
        if not dry_run:
            path = donate(rows, at=at)
            report["donations"]["path"] = str(path) if path else None
            if c is not None:
                reg.remember("sares", "one SARES pass", kind="organ_pass",
                             memory_key=f"sares:{at or snap.today()}",
                             metrics={"systems": len(report["systems"]), "cells": len(cells),
                                      "recorded": report["discoveries"].get("recorded", 0)},
                             payload={"illusions": report["illusions_detected"]}, conn=c)
                c.commit()
    finally:
        if close_after and c is not None:
            c.close()
    for a, st in report["agents"].items():
        if not st["ran"]:
            report["unmeasured"].append(f"{a}: {st['why'] or 'nothing in reach this pass'}")
    report["agents_ran"] = sum(1 for st in report["agents"].values() if st["ran"])
    report["seconds"] = round(time.monotonic() - started, 2)
    return report


def _mark(report: dict[str, Any], agent: str, ran: bool, produced: int, why: Any) -> None:
    st = report["agents"][agent]
    st["ran"] = st["ran"] or bool(ran)
    st["produced"] += int(produced or 0)
    if not st["ran"] and why:
        st["why"] = str(why)[:200]


def _horizon(profile: Mapping[str, Any]) -> str:
    h = (profile.get("features") or {}).get("holding_hours")
    if h is None:
        return "sub_4h"
    return "sub_4h" if h < 4 else "sub_1d" if h < 24 else "multi_day"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="run every agent; write nothing")
    ap.add_argument("--once", action="store_true", help="one pass and exit (the default)")
    ap.add_argument("--report", default=str(REPORT))
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run)
    if not a.dry_run:
        mc._atomic_json(Path(a.report), doc)
    slim = {k: v for k, v in doc.items() if k not in ("systems", "grades", "history", "agents")}
    print(json.dumps(slim, indent=1, default=str))
    for name, st in doc["agents"].items():
        mark = "ran" if st["ran"] else "UNMEASURED"
        print(f"  {mark:<10} {name:<32} produced={st['produced']:<5} {st['why'][:60]}")
    if a.dry_run:
        print("  (dry run: nothing written)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
