"""THE CERTIFICATE SATURATION MAP -- what the certified book already OWNS, measured in bets.

    "A thousand certificates representing ten correlated economic bets are not one thousand
     edges. ... Breadth decides WHAT WE SEARCH NEXT. Breadth must never decide WHAT PASSES."
                    -- the principal, MAXIMUM EFFECTIVE-BREADTH / ANTI-SATURATION LAW, 2026-10-05
                       (verbatim: /mnt/project-files/mandates/breadth_law_2026-10-05.md)

WHAT ALREADY EXISTED AND WHAT IT COULD NOT SAY (diffed 2026-10-06 before a line was written).
`alpha_breadth` measures the TRADED book's k_eff; `docket_keff` prices a docket (family, symbol)
against that traded book; `occupancy_map` counts the funnel per FAMILY x CLASS x CHART x SESSION x
HORIZON cell; `alpha_fitness.existing_exposure_term` (Codex a4df0745b) charges a candidate its
family's NOMINAL share of the canon times its nearest same-family structural similarity; and
`breadth_sweep._orthogonal_key` (Codex 02348d423) orders by the NOMINAL certified count per family.
None of them could answer the principal's question: how many INDEPENDENT bets do the ~840
certificates actually hold, which structural clusters are saturated, and how much would ONE MORE
candidate here add? A nominal share treats 344 cross_asset_residual certificates on 40 USD pairs
as 344 units of exposure -- and treats a candidate on the 41st USD pair as novel because the
ticker is new. This module is that missing measurement. It is a library plus one published
artifact; it decides nothing on its own. The organs that already order work read it.

THE MAP (every certificate on the 21 axes the law lists, `AXES`):

    payer, information_source, family, instrument, economic_factor, currency_exposure,
    asset_class, direction, session, timeframe, horizon, entry_mechanism, exit_mechanism,
    regime, event_dependence, volatility_state, liquidity_state, carry_dependence,
    cross_asset_dependence, execution_dependence, realised_pnl_cluster

Ten of them are `axis_registry.axis_cell`'s own derivations (imported, never re-implemented);
the rest are derived here from the family table, the symbol's economic factor and the params.
`realised_pnl_cluster` is the only EMPIRICAL axis and reads UNMEASURED until forward ledgers
clear the sample floor.

THE HIERARCHY (law section 5): L1 payer/mechanism, L2 information source, L3 market expression
(asset class), L4 factor exposure, L5 temporal expression (session x chart bucket x horizon),
L6 realised return cluster. A STRUCTURAL CLUSTER is L1..L5; an ECONOMIC CLUSTER is L1 x L4.

STRUCTURAL SIMILARITY, BEFORE EVIDENCE (section 3). A preregistered weighted agreement over the
axes, `WEIGHTS`. THE INSTRUMENT CARRIES ZERO WEIGHT and the family label one unit of ~17: a
renamed family, another ticker in the same factor, a parameter change, a minor chart shift or a
stop tweak buys almost nothing, which is the no-gaming rule (section 24) as arithmetic. An axis
either side cannot name counts as AGREEMENT: absence is not independence.

INSTRUMENT COUPLING. The same rule on two instruments is coupled by |rho| of their daily returns
on the desk's own bars where >= MIN_COUPLING_OBS aligned days exist, else by a declared prior
(same structural factor 0.7, same asset class 0.3, otherwise the desk's measured cross mean
0.21). FACTOR-RESIDUAL CLUSTERING (sections 10/12): inside each structural factor the first
principal component is stripped and the residual correlation clusters the members; a residual
measured distinct earns half of the factor axis back, nothing more.

N_EFFECTIVE_CERTIFICATES (section 13). Certificates collapse to (structure, instrument) groups
-- parameter variants of one rule on one instrument are one bet -- and the group matrix
C = structural similarity (factor-free) x instrument coupling feeds the desk's own bet count,
n^2 / sum_ij C_ij (`effective_breadth.exposure_neff` with unit risks). Forward evidence then
UPDATES C (section 23): a pair measured dependent at a Fisher lower bound >= REVOKE_RHO has its
entry raised to that bound (credit revoked, recorded with the date); a pair measured independent
on >= MIN_INDEPENDENCE_OBS days at an upper bound <= INDEPENDENT_RHO may lower it to that bound
(exception F). Low-sample correlation is UNMEASURED and changes nothing.

NOVELTY CREDIT (section 18), PREREGISTERED AND NOT TUNED AFTER SEEING PASSES:

    effective_local_count(c) = sum over certificate groups g with C(c, g) >= LOCAL_FLOOR of C(c, g)
    novelty_credit(c)        = 1 / sqrt(1 + effective_local_count(c))

Effective, not raw: parameter variants count once, and each neighbour counts by how strongly it
is coupled to the candidate. A first sleeve in empty ground reads 1.0; the 41st USD pair in a
40-pair cluster reads ~0.19.

SATURATION (sections 6, 7, 20) is ADAPTIVE, never "five certificates": a structural cluster is
SATURATED when the marginal search value of one more clone -- its novelty credit times its
posterior survivor yield relative to the desk's -- has fallen below MATERIAL_FALL (half of what a
first entry into empty ground at the desk's mean yield is worth), with at least two certificates.

EXCEPTIONS A-H (section 8) are labelled per docket row: A-E structurally against the nearest
saturated cluster (new payer / information / temporal clock / regime / factor), F and H only on
MEASURED evidence carried by the row, G (quality replacement) when the row declares it or is a
certified descendant. A row in saturated ground with no exception is a STRONG DUPLICATE: it moves
to the tail of its family stream. NOTHING IS DROPPED, NO GATE MOVES, NO ROW LEAVES THE DOCKET.

WHAT READS IT: `judge_coverage` (docket VALUE order with a protected QUALITY channel, and the
family factor in `rank_by_value`), `docket_keff` (empty-cluster bonus decayed by effort),
`breadth_sweep` and `breadth_rotation` (producer ordering), `empty_cluster_forcer` (prior decay),
`alpha_fitness.existing_exposure_term`, `libs/research/bandit` (duplicate tax), `portfolio_bounty`
(breadth-debt bounties into the auction), `breadth_ladder` (A/B/C/D split) and the DeepSeek seat
(its cold context). Published hourly by the existing `alpha_breadth` leg to
`reports/CERTIFICATE_SATURATION.json`; producer feedback by `judge_coverage` to
`reports/BREADTH_FEEDBACK.json`.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(ROOT), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from research import axis_registry as ar
except Exception:                                     # pragma: no cover - run as a script
    import axis_registry as ar  # type: ignore[no-redef,import-not-found]

REPORTS = BASE / "reports"
REPORT = REPORTS / "CERTIFICATE_SATURATION.json"
FEEDBACK = REPORTS / "BREADTH_FEEDBACK.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
#: THE BOX'S LIVE SURVIVOR SET (the sweep writes it; ~847 rows on 2026-10-06). Read FIRST; the
#: sealed git canon (52 rows in the repo) is the fallback. Every N_CERT carries its basis.
SURVIVORS_LIVE = REPORTS / "UNIVERSAL_SURVIVORS.json"
#: a survivor file swept (or written) within this many hours is the box's live set; older is a
#: snapshot carried by git and is labelled so wherever its counts are printed
LIVE_BASIS_MAX_AGE_H = 48.0
#: Certified specs published for the near-duplicate index (the box holds ~850).
MAX_SPECS_PUBLISHED = 20_000
SHADOW_STATE = REPORTS / "shadow" / "shadow_state.json"
SLEEVES = BASE / "data" / "sleeves.json"
SEEN_CELLS = BASE / "data" / "hypotheses" / "gauntlet_seen_cells.json"
UNIVERSE_DIR = BASE / "data" / "universe"
UNKNOWN = "UNKNOWN"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"

# ------------------------------------------------------------------ the preregistered constants
#: The 21 axes of section 2, in the law's order.
AXES: tuple[str, ...] = (
    "payer", "information_source", "family", "instrument", "economic_factor",
    "currency_exposure", "asset_class", "direction", "session", "timeframe", "horizon",
    "entry_mechanism", "exit_mechanism", "regime", "event_dependence", "volatility_state",
    "liquidity_state", "carry_dependence", "cross_asset_dependence", "execution_dependence",
    "realised_pnl_cluster")

#: Structural similarity weights. PREREGISTERED 2026-10-06 -- changing them after seeing which
#: candidates passed is the correlation-shopping section 9 forbids. The economic content (who
#: pays, what information, which factor, which clock) carries the weight; the spellings that
#: section 24 lists as gaming (instrument, family label, chart shift, stop tweak) carry little or
#: none. `factor_residual` is the half of the factor axis a measured residual can earn back.
WEIGHTS: dict[str, float] = {
    "payer": 3.0, "information_source": 2.0, "family": 1.0, "economic_factor": 1.0,
    "factor_residual": 1.0, "currency_exposure": 0.5, "asset_class": 1.0, "direction": 0.5,
    "session": 1.0, "timeframe": 0.25, "horizon": 1.0, "entry_mechanism": 0.5,
    "exit_mechanism": 0.25, "regime": 1.0, "event_dependence": 0.5, "volatility_state": 0.5,
    "liquidity_state": 0.25, "carry_dependence": 0.5, "cross_asset_dependence": 0.5,
    "execution_dependence": 0.25,
}
SIG_AXES: tuple[str, ...] = tuple(WEIGHTS)
#: Axes left out of the factor-free similarity used inside C, because instrument coupling already
#: prices the factor -- charging it twice would double-count one difference.
FACTOR_AXES = frozenset({"economic_factor", "factor_residual", "currency_exposure", "asset_class"})

#: C(candidate, group) at or above this joins the candidate's local neighbourhood.
LOCAL_FLOOR = 0.5
#: Nearest structural similarity at or above which a candidate stands in a cluster's ground.
SATURATED_GROUND_SIM = 0.7
#: A cluster is SATURATED when one more clone's search value falls below this fraction of a first
#: entry into empty ground at the desk's mean yield. "Materially fallen" = halved.
MATERIAL_FALL = 0.5
#: Exceptions honour at least the credit of ground holding one effective neighbour.
EXCEPTION_FLOOR = 1.0 / math.sqrt(2.0)
#: Beta prior strength (pseudo-trials) for cluster survivor yield.
PRIOR_STRENGTH = 50.0
#: Instrument coupling priors where the desk's own bars cannot measure a pair.
RHO_SAME_FACTOR, RHO_SAME_CLASS, RHO_CROSS = 0.7, 0.3, 0.21
MIN_COUPLING_OBS = 250
#: Factor-residual: members of one factor whose residual |rho| reaches this share a cluster.
RESIDUAL_LINK = 0.5
#: Forward independence (section 4/23): Fisher-z 95% bounds on overlapping days.
MIN_PAIR_OBS = 20
MIN_INDEPENDENCE_OBS = 60
REVOKE_RHO = 0.3
INDEPENDENT_RHO = 0.3
#: Challenger set kept per saturated cluster (section 20).
CHALLENGERS = 3
#: Producer feedback: duplicate share and minimum rows at which a producer is told to RETARGET,
#: and the consecutive RETARGET readings before it is named a PARK candidate (section 21).
RETARGET_SHARE = 0.5
RETARGET_MIN_ROWS = 50
RETARGET_PATIENCE = 24
#: A near-duplicate's breadth value is at most the credit of ONE effective twin (preregistered).
DUPLICATE_TAX_CREDIT = 1.0 / math.sqrt(2.0)
#: The duplicate tax's four terms (breadth law §22: density, duplicate rate, effective trials
#: already spent, declining survivor yield). PREREGISTERED 2026-10-06. Trials scale: a cluster
#: that has already cost this many judged cells halves a duplicate's value again at 3x it.
DUPLICATE_TAX_TRIALS_SCALE = 100.0
#: The tax never takes a duplicate's value below this: it sinks in the order, it is never lost,
#: and when the judge reaches it it is charged its trial like any cell.
DUPLICATE_TAX_FLOOR = 0.01
#: THE PER-PRODUCER DUPLICATE BUDGET (audit rank 6, 2026-10-06). The share of a producer's next
#: generation that may be near-duplicates of the certified book before it is told to retarget.
#: Half the RETARGET share: the budget warns before the retarget fires. Preregistered, never
#: tuned on which producers passed. A producer over budget loses ORDER (its duplicates go to the
#: tail and are taxed) and is told so; nothing it produced is dropped, and every judged row is
#: still charged its trial.
DUPLICATE_BUDGET_SHARE = 0.25
#: The map the docket reads must be this fresh; older reads as UNMEASURED (par for every row).
MAX_AGE_H = 6.0
#: Empty-cluster prior floor (section 17): an exhausted empty cluster keeps this much priority.
EXPLORE_FLOOR = 0.1
MAX_GROUPS_PUBLISHED = 4000

#: Structural failure modes per mechanism (section 22). DECLARED, published as such, and
#: superseded by a measured co-drawdown label wherever the forward ledgers carry one.
MECHANISM_FAILURE: dict[str, tuple[str, ...]] = {
    "trend_persistence": ("trend_reversal", "volatility_collapse"),
    "breakout_liquidity": ("false_breakout_chop", "volatility_collapse"),
    "range_reversion": ("trend_persistence_shock", "liquidity_shock"),
    "session_handover": ("liquidity_shock", "regime_break"),
    "session_information_handoff": ("liquidity_shock", "regime_break"),
    "carry_rollover": ("carry_unwind", "risk_off"),
    "macro_release": ("policy_surprise", "regime_break"),
    "forced_flow": ("calendar_regime_shift", "liquidity_shock"),
    "positioning_crowding": ("positioning_squeeze", "policy_surprise"),
    "calendar_seasonality": ("calendar_regime_shift",),
    "relative_value_dislocation": ("correlation_breakdown", "liquidity_shock"),
    "cross_market_lead": ("correlation_breakdown", "regime_break"),
    "volatility_shock": ("volatility_collapse", "risk_off"),
    "regime_transition": ("regime_break",),
    "execution_microstructure": ("liquidity_shock", "cost_shock"),
    "gamma_hedging_state": ("volatility_collapse", "liquidity_shock"),
    "hedging_demand_close_flow": ("calendar_regime_shift", "liquidity_shock"),
    "fx_fixing_flow": ("calendar_regime_shift", "liquidity_shock"),
    "inventory_shock": ("liquidity_shock",),
    "forced_liquidation": ("risk_off", "liquidity_shock"),
}
FACTOR_FAILURE: dict[str, str] = {
    "JPY_CARRY": "jpy_carry_unwind", "USD": "usd_shock", "PRECIOUS_REAL_YIELD": "real_yield_shock",
    "OIL": "commodity_supply_shock", "NATGAS": "commodity_supply_shock",
    "INDUSTRIAL_METALS": "china_growth_shock", "COMMODITY_FX": "china_growth_shock",
    "EQUITY_US": "risk_off", "EQUITY_EU": "risk_off", "EQUITY_ASIA": "risk_off",
    "EM_FX": "risk_off", "CHF_HAVEN": "risk_off", "CRYPTO_BETA": "risk_off",
    "RATES": "policy_surprise", "AGRI": "commodity_supply_shock",
}
#: What hunts a book that fails for reason X (section 13 of the producer law, "what hurts the
#: book"): mechanisms whose declared failure set excludes X. Derived from MECHANISM_FAILURE below.

#: Sources whose output is a QUALITY / REPLACEMENT challenger by construction (law section 15,
#: 23): a mutation, an exit or execution study, a refinement of a certified rule.
QUALITY_SOURCE_TOKENS: tuple[str, ...] = ("mutate", "mutation", "exit_", "execution", "refine",
                                          "challenger", "survivor_distiller", "replacement",
                                          "alpha_evolution", "certified_descendant")

#: Method breadth is not alpha breadth (law 18): how a producer generates, read from its name.
METHOD_TOKENS: tuple[tuple[str, str], ...] = (
    ("deepseek", "llm"), ("kimi", "llm"), ("llm", "llm"), ("seat", "llm"),
    ("pysr", "symbolic"), ("formula", "symbolic"), ("symbolic", "symbolic"),
    ("evolution", "evolutionary"), ("mutate", "evolutionary"), ("genome", "evolutionary"),
    ("gnn", "ml"), ("learned", "ml"), ("attention", "ml"), ("causal", "causal"),
    ("mass_screen", "screen"), ("sweep", "grid_sweep"), ("video", "public_strategy"),
    ("forest", "regional_miner"), ("country", "regional_miner"), ("miner", "miner"),
    ("compiler", "compiler"), ("qd_", "quality_diversity"), ("occupancy", "breadth_targeting"),
    ("forcer", "breadth_targeting"), ("axis", "breadth_targeting"))


# ----------------------------------------------------------------------- reading the world
def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


_CLASS_CACHE: dict[str, str] = {}


def asset_class(symbol: str) -> str:
    s = str(symbol or "").strip().upper()
    if s not in _CLASS_CACHE:
        _CLASS_CACHE[s] = ar.asset_class_of(s) if s else UNKNOWN
    return _CLASS_CACHE[s]


_EM = frozenset({"MXN", "ZAR", "TRY", "BRL", "RUB", "INR", "IDR", "KRW", "THB", "CNH", "HUF",
                 "PLN", "CZK", "ILS"})
_COMMODITY_CCY = frozenset({"AUD", "NZD", "CAD", "NOK"})
_EUROPE = frozenset({"EUR", "GBP", "SEK", "DKK"})
_EQ_US = frozenset({"US500", "NAS100", "US30", "US2000", "CA60"})
_EQ_EU = frozenset({"GER40", "FRA40", "UK100", "EUSTX50", "E35", "NETH25"})
_EQ_ASIA = frozenset({"JPN225", "HK50", "CHINAH", "AUS200"})


def legs(symbol: str) -> tuple[str, ...]:
    s = str(symbol or "").upper()
    cls = asset_class(s)
    if cls.startswith("forex") and len(s) == 6 and s.isalpha():
        return (s[:3], s[3:])
    if s.startswith(("XAU", "XAG", "XPT", "XPD")) and len(s) == 6:
        return (s[:3], s[3:])
    return ()


def factor_of(symbol: str) -> str:
    """The STRUCTURAL economic factor an instrument loads on (law section 10). Declared, coarse
    on purpose, and refined -- never replaced -- by the measured residual clustering."""
    s = str(symbol or "").strip().upper()
    if not s:
        return UNKNOWN
    cls = asset_class(s)
    lg = legs(s)
    if cls.startswith("forex") and lg:
        a, b = lg
        if "JPY" in lg:
            return "JPY_CARRY"
        if a in _EM or b in _EM:
            return "EM_FX"
        if "CHF" in lg:
            return "CHF_HAVEN"
        if "USD" in lg:
            return "USD"
        if a in _COMMODITY_CCY or b in _COMMODITY_CCY:
            return "COMMODITY_FX"
        if a in _EUROPE and b in _EUROPE:
            return "EUROPE_FX"
        return "OTHER_FX"
    if s.startswith(("XAU", "XAG", "XPT", "XPD")):
        return "PRECIOUS_REAL_YIELD"
    if s.startswith(("XCU", "XAL", "XNI", "XZN", "XPB")):
        return "INDUSTRIAL_METALS"
    if s.startswith(("XTI", "XBR")) or "OIL" in s:
        return "OIL"
    if s.startswith("XNG"):
        return "NATGAS"
    if s == "USDX":
        return "USD"
    if s in _EQ_US:
        return "EQUITY_US"
    if s in _EQ_EU:
        return "EQUITY_EU"
    if s in _EQ_ASIA:
        return "EQUITY_ASIA"
    if "soft" in cls:
        return "AGRI"
    if "bond" in cls or s.startswith(("UST", "UKGILT")):
        return "RATES"
    if "crypto" in cls:
        return "CRYPTO_BETA"
    if "equit" in cls:
        return "EQUITY_SINGLE"
    if "indices" in cls or "index" in cls:
        return "EQUITY_OTHER"
    return cls.upper() if cls and cls != UNKNOWN else UNKNOWN


def _first(*values: Any) -> Any:
    for v in values:
        if v is not None and str(v).strip() != "":
            return v
    return None


_SIDE_KEYS = ("side", "direction", "sign")
_EXIT_HINTS = (("rr", "rr_target"), ("target", "price_target"), ("tp", "price_target"),
               ("stop", "stop"), ("sl", "stop"), ("trail", "trailing"),
               ("max_hold", "time"), ("hold", "time"), ("ttl", "time"), ("horizon", "time"),
               ("exit_on", "signal_flip"), ("flip", "signal_flip"))
_VOL_TOKENS = ("vol", "atr", "adx", "squeeze", "regime")
_DRIVER_KEYS = ("driver", "peer", "peer_symbol", "lead", "leader", "basket", "factor",
                "driver_symbol", "lead_symbol")
_EVENT_INFO = frozenset({"event", "macro"})


def _direction(params: Mapping[str, Any], spec: Mapping[str, Any], mech: str) -> str:
    raw = _first(*(params.get(k) for k in _SIDE_KEYS), *(spec.get(k) for k in _SIDE_KEYS))
    if raw is not None:
        v = _num(raw)
        if v is not None:
            return "long" if v > 0 else ("short" if v < 0 else "both")
        t = str(raw).strip().lower()
        if t in ("long", "buy", "up"):
            return "long"
        if t in ("short", "sell", "down"):
            return "short"
    if mech in ("trend_persistence", "breakout_liquidity"):
        return "with_move"
    if mech in ("range_reversion", "relative_value_dislocation"):
        return "against_move"
    return "both"


def _exit(params: Mapping[str, Any]) -> str:
    keys = [str(k).lower() for k in params]
    found = sorted({label for k in keys for hint, label in _EXIT_HINTS if k.startswith(hint)})
    return "+".join(found) if found else "family_default"


def _chart_bucket(chart: str) -> str:
    if chart in ("M1", "M5", "M15", "M30"):
        return "intraday"
    if chart in ("H1", "H4"):
        return "hourly"
    if chart == "D1":
        return "daily"
    return UNKNOWN


def axes_of(symbol: Any, family: Any, params: Mapping[str, Any] | None = None, *,
            timeframe: Any = None, session: Any = None, regime_hint: Any = None,
            exec_field: Any = None, spec: Mapping[str, Any] | None = None,
            factor_residual: Mapping[str, str] | None = None) -> dict[str, str]:
    """The 21-axis representation (plus `factor_residual`) of one rule on one instrument.

    `axis_registry.axis_cell` supplies asset class, chart, session, horizon, mechanism,
    information source, payer (economic actor), regime and execution style; the remainder is
    derived from those and the parameters. Every axis resolves to a token."""
    p = dict(params) if isinstance(params, Mapping) else {}
    sp = dict(spec) if isinstance(spec, Mapping) else {}
    sym = str(symbol or "").strip().upper()
    cell = ar.axis_cell(sym, family, p, timeframe, session, exec_field, regime_hint)
    mech, info = cell["mechanism"], cell["information_source"]
    fac = factor_of(sym)
    lg = legs(sym)
    chart = cell["chart"]
    regime = cell["regime"]
    keys = " ".join(str(k).lower() for k in p)
    vol = ("vol_conditioned" if any(t in keys for t in _VOL_TOKENS) or any(
        t in regime for t in ("vol", "atr", "adx")) else "any")
    sess = cell["session"]
    liq = ("microstructure" if info == "microstructure" else
           {"asia": "thin", "london": "deep", "ny": "deep", "overlap": "deepest",
            "all": "mixed"}.get(sess, UNKNOWN))
    carry = ("carry" if mech == "carry_rollover" or info == "carry" else
             ("carry_exposed" if fac == "JPY_CARRY" else "none"))
    driver = _first(*(p.get(k) for k in _DRIVER_KEYS))
    cross = (str(driver).upper() if driver is not None else
             ("basket" if info == "cross_asset" else "none"))
    execd = {"M1": "high", "M5": "high", "M15": "medium", "M30": "medium"}.get(chart, "low")
    resid = (factor_residual or {}).get(sym) or fac
    return {
        "payer": cell["economic_actor"] if cell["economic_actor"] != UNKNOWN else mech,
        "information_source": info,
        "family": ar._tok(family) or UNKNOWN,
        "instrument": sym or UNKNOWN,
        "economic_factor": fac,
        "factor_residual": resid,
        "currency_exposure": ",".join(sorted(lg)) if lg else fac,
        "asset_class": cell["asset_class"],
        "direction": _direction(p, sp, mech),
        "session": sess,
        "timeframe": chart,
        "horizon": cell["horizon"],
        "entry_mechanism": f"{mech}:{cell['execution_style']}",
        "exit_mechanism": _exit(p),
        "regime": regime,
        "event_dependence": "scheduled_event" if info in _EVENT_INFO else "none",
        "volatility_state": vol,
        "liquidity_state": liq,
        "carry_dependence": carry,
        "cross_asset_dependence": cross,
        "execution_dependence": execd,
        "realised_pnl_cluster": UNMEASURED,
        "_mechanism": mech,
    }


def hierarchy(ax: Mapping[str, str]) -> dict[str, str]:
    """L1..L6 keys (law section 5)."""
    return {"L1": str(ax.get("_mechanism") or ax.get("payer") or UNKNOWN),
            "L2": str(ax.get("information_source") or UNKNOWN),
            "L3": str(ax.get("asset_class") or UNKNOWN),
            "L4": str(ax.get("economic_factor") or UNKNOWN),
            "L5": "|".join((str(ax.get("session") or UNKNOWN),
                            _chart_bucket(str(ax.get("timeframe") or "")),
                            str(ax.get("horizon") or UNKNOWN))),
            "L6": str(ax.get("realised_pnl_cluster") or UNMEASURED)}


def cluster_key(ax: Mapping[str, str]) -> str:
    """The STRUCTURAL cluster: L1..L5."""
    h = hierarchy(ax)
    return "/".join(h[k] for k in ("L1", "L2", "L3", "L4", "L5"))


def economic_key(ax: Mapping[str, str]) -> str:
    h = hierarchy(ax)
    return f"{h['L1']}/{h['L4']}"


def failure_modes(ax: Mapping[str, str]) -> tuple[str, ...]:
    mech = str(ax.get("_mechanism") or "")
    modes = set(MECHANISM_FAILURE.get(mech, ("unnamed_mechanism",)))
    fm = FACTOR_FAILURE.get(str(ax.get("economic_factor") or ""))
    if fm:
        modes.add(fm)
    return tuple(sorted(modes))


def signature(ax: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(str(ax.get(a, UNKNOWN)) for a in SIG_AXES)


def similarity(a: Mapping[str, str], b: Mapping[str, str], *, factor_free: bool = False) -> float:
    """Preregistered weighted agreement in [0, 1]. UNKNOWN on either side AGREES."""
    num = den = 0.0
    for axis, w in WEIGHTS.items():
        if factor_free and axis in FACTOR_AXES:
            continue
        va, vb = str(a.get(axis, UNKNOWN)), str(b.get(axis, UNKNOWN))
        den += w
        if va in (vb, UNKNOWN) or vb == UNKNOWN:
            num += w
    return num / den if den else 1.0


def novelty_credit(effective_local_count: float) -> float:
    """1 / sqrt(1 + effective local count). Preregistered (law section 18)."""
    return 1.0 / math.sqrt(1.0 + max(0.0, float(effective_local_count)))


# ------------------------------------------------------------------- rows and certificates
def row_fields(row: Mapping[str, Any]) -> tuple[str, str, dict[str, Any], Any, Any, Any]:
    """(symbol, family, params, timeframe, session, regime_hint) of a docket row."""
    raw = row.get("params")
    params: dict[str, Any] = dict(raw) if isinstance(raw, Mapping) else {}
    sym = row.get("symbol") or row.get("sym")
    if not sym and isinstance(row.get("symbols"), list) and row["symbols"]:
        sym = row["symbols"][0]
    tf = params.get("timeframe") if "timeframe" in params else row.get("timeframe")
    sess = _first(params.get("session"), row.get("session"), row.get("selector"),
                  params.get("selector"))
    reg = _first(row.get("condition"), row.get("regime"))
    return (str(sym or "").strip().upper(), str(row.get("family") or ""), params, tf, sess, reg)


def _param_value(v: str) -> Any:
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in v else f
    except ValueError:
        return v


def parse_cert_key(key: str) -> tuple[str, str, dict[str, Any], Any]:
    """(SYMBOL, family, params, timeframe) from a survivor KEY or cell when the row's own fields
    are missing. Handles the box's shapes:

        external.XAUUSD.session_range_breakout.p=...      (lane prefix, dotted)
        external.XAUUSD.session_range_breakout.rr=1.5_wb=12
        XAUUSD@M5.carry.k=3                                (chart on the symbol)
        qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY  (spaced)
    """
    import re
    s = str(key or "").strip()
    s = re.sub(r"^qquant\.[^ ]*?\.json\.", "", s)
    for prefix in ("external.", "universal.", "qquant.", "internal."):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    if " " in s.split(".", 1)[0] or (" " in s and "." not in s.split(" ", 1)[0]):
        tok = s.split()
        sym, fam, rest = (tok[0] if tok else ""), (tok[1] if len(tok) > 1 else ""), ""
    else:
        bits = s.split(".", 2)
        sym = bits[0] if bits else ""
        fam = bits[1] if len(bits) > 1 else ""
        rest = bits[2] if len(bits) > 2 else ""
    tf = sym.rsplit("@", 1)[-1] if "@" in sym else None
    sym = sym.split("@", 1)[0].upper()
    params: dict[str, Any] = {}
    if rest.startswith("p=") and "=" in rest[2:]:
        rest = rest[2:]                       # `p=<k=v,...>`: the payload is the params
    if rest:
        segs = re.split(r"[,;]", rest) if re.search(r"[,;]", rest) else \
            re.split(r"_(?=[A-Za-z][A-Za-z0-9]*=)", rest)
        for seg in segs:
            if "=" in seg:
                k, v = seg.split("=", 1)
                if k.strip():
                    params[k.strip()] = _param_value(v.strip())
    return sym, fam, params, tf


def cert_fields(key: str, cert: Mapping[str, Any]) -> tuple[str, str, dict[str, Any], Any, Any,
                                                            Any, dict[str, Any]]:
    raw = cert.get("shadow_spec")
    spec: dict[str, Any] = dict(raw) if isinstance(raw, Mapping) else {}
    rp = spec.get("params") if isinstance(spec.get("params"), Mapping) else cert.get("params")
    params: dict[str, Any] = dict(rp) if isinstance(rp, Mapping) else {}
    # fields first; the KEY (the box's `external.<SYM>.<family>.p=...`) only fills what is missing
    k_sym, k_fam, k_params, k_tf = parse_cert_key(str(cert.get("cell") or key))
    if not k_sym or not k_fam:
        k_sym, k_fam, k_params, k_tf = parse_cert_key(str(key))
    if not params:
        params = dict(k_params)
    sym = str(spec.get("symbol") or cert.get("sym") or cert.get("symbol") or k_sym).upper()
    sym = sym.split("@", 1)[0]
    fam = str(spec.get("family") or cert.get("family") or k_fam)
    tf = _first(spec.get("timeframe"), params.get("timeframe"), cert.get("timeframe"), k_tf)
    sess = _first(spec.get("selector"), spec.get("session"), params.get("session"))
    reg = _first(spec.get("condition"), spec.get("regime"))
    return sym, fam, params, tf, sess, reg, spec


def survivor_basis(path: Path, doc: Any, *, now: datetime | None = None,
                   live: bool = True) -> dict[str, Any]:
    """Where an N_CERT came from: path, mtime, swept_at, rows, and `basis` -- `box_live` for the
    live survivor file swept (or written) within LIVE_BASIS_MAX_AGE_H, else `git_snapshot` (the
    sealed canon fallback is always `git_snapshot`)."""
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        mtime = None
    swept = doc.get("swept_at") if isinstance(doc, dict) else None
    ref = None
    try:
        ref = datetime.fromisoformat(str(swept).replace("Z", "+00:00")) if swept else mtime
    except ValueError:
        ref = mtime
    age = (((now or datetime.now(tz=UTC)) - ref).total_seconds() / 3600.0) if ref else None
    sv = doc.get("survivors") if isinstance(doc, dict) else None
    try:
        rel = str(path.relative_to(BASE.parents[1]))
    except ValueError:
        rel = str(path)
    return {"basis": ("box_live" if live and age is not None and age <= LIVE_BASIS_MAX_AGE_H
                      else "git_snapshot"),
            "source": rel, "source_mtime": mtime.isoformat(timespec="seconds") if mtime else None,
            "swept_at": swept, "age_h": round(age, 2) if age is not None else None,
            "n_rows": len(sv) if isinstance(sv, dict) else None}


def load_survivors(*, now: datetime | None = None) -> tuple[Any, dict[str, Any]]:
    """The box's live survivor set first (reports/UNIVERSAL_SURVIVORS.json), the git canon only
    when that is absent or empty; the basis is returned either way."""
    for path in (SURVIVORS_LIVE, CANON):
        doc = _read(path)
        sv = doc.get("survivors") if isinstance(doc, dict) else None
        if isinstance(sv, dict) and sv:
            return doc, survivor_basis(path, doc, now=now, live=path == SURVIVORS_LIVE)
    return None, {"basis": UNMEASURED, "source": None,
                  "why": f"neither {SURVIVORS_LIVE.name} nor {CANON.name} holds survivors"}


def cert_edge(cert: Mapping[str, Any]) -> float | None:
    """Validated edge quality of a certificate: walk-forward OOS Sharpe, else CPCV mean OOS."""
    g = cert.get("gates") if isinstance(cert.get("gates"), Mapping) else {}
    wf = g.get("walk_forward") if isinstance(g.get("walk_forward"), Mapping) else {}
    cp = g.get("cpcv") if isinstance(g.get("cpcv"), Mapping) else {}
    return _num(_first(wf.get("oos_sharpe"), cp.get("mean_oos_sharpe")))


def is_quality_row(row: Mapping[str, Any]) -> bool:
    """QUALITY / REPLACEMENT channel membership (law section 15 and producer law 23)."""
    exc = str(row.get("breadth_exception") or "").strip().upper()
    if exc in ("G", "QUALITY", "REPLACEMENT"):
        return True
    if row.get("parent_certificate") or row.get("variant_of") or row.get("challenger_of"):
        return True
    return _quality_source(str(row.get("source") or ""))


_QSRC: dict[str, bool] = {}


def _quality_source(source: str) -> bool:
    hit = _QSRC.get(source)
    if hit is None:
        low = source.lower()
        hit = _QSRC[source] = any(t in low for t in QUALITY_SOURCE_TOKENS)
    return hit


def method_of(source: str) -> str:
    s = str(source or "").lower()
    for tok, method in METHOD_TOKENS:
        if tok in s:
            return method
    return "other"


# ------------------------------------------------------------------ instrument coupling
def daily_series(sym: str, universe: Path | None = None) -> Any:
    """Daily log returns from the desk's own H1 bars, or None (the docket_keff panel)."""
    f = (universe or UNIVERSE_DIR) / f"{sym}_H1.parquet"
    if not f.exists():
        return None
    try:
        import pandas as pd
        d = pd.read_parquet(f, columns=["close"])
        r = np.log(d["close"]).diff().dropna().resample("1D").sum()
        r = r[r != 0]
    except Exception:
        return None
    return r if len(r) >= MIN_COUPLING_OBS else None


def coupling_table(symbols: Iterable[str], loader: Callable[[str], Any] | None = None
                   ) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """{a: {b: |rho|}} on pairwise-aligned daily returns with >= MIN_COUPLING_OBS days, plus the
    factor-residual clustering per structural factor. Pairs below the floor are absent and the
    caller uses the declared prior -- low sample is UNMEASURED, never zero."""
    load = loader or daily_series
    import pandas as pd
    series = {}
    for s in sorted({str(x).upper() for x in symbols if x}):
        r = load(s)
        if r is not None:
            series[s] = r
    names = sorted(series)
    out: dict[str, dict[str, float]] = {s: {} for s in names}
    if len(names) < 2:
        return out, {"status": UNMEASURED, "why": f"{len(names)} instrument(s) with bars"}
    frame = pd.DataFrame(series)
    m = frame.to_numpy(dtype="float64")
    ok = ~np.isnan(m)
    for i, a in enumerate(names):
        for j in range(i + 1, len(names)):
            both = ok[:, i] & ok[:, j]
            n = int(both.sum())
            if n < MIN_COUPLING_OBS:
                continue
            x, y = m[both, i], m[both, j]
            if x.std() <= 0 or y.std() <= 0:
                continue
            rho = shrink_abs_rho(float(np.corrcoef(x, y)[0, 1]), n)
            if math.isfinite(rho):
                out[a][names[j]] = round(rho, 4)
                out[names[j]][a] = round(rho, 4)
    # FACTOR-RESIDUAL CLUSTERING: strip each factor's first principal component, cluster what
    # remains. A factor with fewer than three measured members has no common component to strip.
    by_factor: dict[str, list[str]] = defaultdict(list)
    for s in names:
        by_factor[factor_of(s)].append(s)
    residual: dict[str, str] = {}
    detail: dict[str, Any] = {}
    for fac, mem in sorted(by_factor.items()):
        if len(mem) < 3:
            detail[fac] = {"members": mem, "status": UNMEASURED,
                           "why": "fewer than three measured members: no common factor to strip"}
            continue
        sub = frame[mem].dropna()
        if len(sub) < MIN_COUPLING_OBS:
            detail[fac] = {"members": mem, "status": UNMEASURED,
                           "why": f"{len(sub)} complete-case days, below {MIN_COUPLING_OBS}"}
            continue
        z = (sub - sub.mean()) / sub.std()
        zz = z.to_numpy(dtype="float64")
        _u, _s, vt = np.linalg.svd(zz, full_matrices=False)
        pc = zz @ vt[0]
        beta = (zz * pc[:, None]).sum(axis=0) / float(pc @ pc)
        res = zz - np.outer(pc, beta)
        rc = np.abs(np.corrcoef(res, rowvar=False))
        explained = float(_s[0] ** 2 / float((_s ** 2).sum()))
        groups = _link_groups(mem, rc, RESIDUAL_LINK)
        clusters = sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g))
        for k, g in enumerate(clusters):
            for s in g:
                residual[s] = f"{fac}#r{k}"
        detail[fac] = {"members": mem, "status": MEASURED, "n_obs": len(sub),
                       "first_pc_share": round(explained, 4),
                       "residual_clusters": clusters,
                       "n_residual_clusters": len(clusters)}
    return out, {"status": MEASURED, "factors": detail, "residual_of": residual,
                 "n_symbols": len(names)}


def _link_groups(names: list[str], mat: np.ndarray, link: float) -> dict[int, list[str]]:
    """Single-linkage groups of `names` whose pairwise `mat` entry reaches `link`."""
    parent = list(range(len(names)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if mat[i, j] >= link:
                parent[find(i)] = find(j)
    groups: dict[int, list[str]] = defaultdict(list)
    for i, s in enumerate(names):
        groups[find(i)].append(s)
    return groups


def coupling(a: str, b: str, table: Mapping[str, Mapping[str, float]]) -> float:
    """|rho| between two instruments: measured where the panel can, else the declared prior."""
    a, b = str(a).upper(), str(b).upper()
    if a == b:
        return 1.0
    v = (table.get(a) or {}).get(b)
    if v is not None:
        return float(v)
    if factor_of(a) == factor_of(b) and factor_of(a) != UNKNOWN:
        return RHO_SAME_FACTOR
    if asset_class(a) == asset_class(b) and asset_class(a) != UNKNOWN:
        return RHO_SAME_CLASS
    return RHO_CROSS


# ----------------------------------------------------------------- forward independence
def fisher_bounds(rho: float, n: int) -> tuple[float, float]:
    """95% Fisher-z interval for a correlation on n observations."""
    r = min(max(float(rho), -0.999999), 0.999999)
    if n <= 3:
        return -1.0, 1.0
    z, se = math.atanh(r), 1.0 / math.sqrt(n - 3)
    return math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)


def sleeve_identity(label: str) -> tuple[str, str, str]:
    """(SYMBOL, family, session) from a shadow-ledger sleeve label `SYMBOL_family_selector`."""
    low = str(label or "").strip()
    head = low.split("_")[0].split(".")[0].upper()
    sym = {"XAU": "XAUUSD", "XAG": "XAGUSD"}.get(head, head)
    fam = ""
    rest = low[len(low.split("_")[0]) + 1:] if "_" in low else ""
    for known in sorted(ar.FAMILY_TABLE, key=len, reverse=True):
        if known in rest:
            fam = known
            break
    tail = low.rsplit("_", 1)[-1].lower() if "_" in low else ""
    sess = ar.SESSION_ALIAS.get(tail, "")
    return sym, fam, sess


def forward_dependence(daily: Mapping[str, Mapping[str, float]], *,
                       overlap: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Pairwise realised dependence between forward sleeves at Fisher bounds (law 4, 23).

    DEPENDENT when the lower bound reaches REVOKE_RHO; INDEPENDENT only on >= MIN_INDEPENDENCE_OBS
    overlapping days with the upper |rho| bound at or below INDEPENDENT_RHO; everything else is
    UNMEASURED. Streams are single-linkage over DEPENDENT pairs among sleeves with any measured
    pair; a sleeve with no measured pair is not counted as a stream (absence is not a stream)."""
    names = sorted(k for k, v in daily.items() if v)
    pairs: list[dict[str, Any]] = []
    parent = {n: n for n in names}
    # BEHAVIOURAL OVERLAP (breadth law §4, §15, §16): drawdown, co-crash, event, regime, signal
    # and lead/lag overlap. A pair whose largest measured term reaches OVERLAP_LINK is one bet
    # even when its rho is modest; a pair that overlaps above OVERLAP_INDEPENDENT never earns
    # exception F. Absent terms are UNMEASURED and neither link nor clear a pair.
    if overlap is None:
        try:
            ov = _so().book_overlap(daily)
        except Exception as exc:                                         # pragma: no cover
            ov = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:200], "pairs": {}}
    else:
        ov = dict(overlap)
    ov_pairs = ov.get("pairs") if isinstance(ov.get("pairs"), Mapping) else {}
    link, indep = _so().OVERLAP_LINK, _so().OVERLAP_INDEPENDENT

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    measured: set[str] = set()
    for i, a in enumerate(names):
        da = daily[a]
        for b in names[i + 1:]:
            db = daily[b]
            days = sorted(set(da) & set(db))
            if len(days) < MIN_PAIR_OBS:
                continue
            x = np.array([da[d] for d in days], dtype="float64")
            y = np.array([db[d] for d in days], dtype="float64")
            if x.std() <= 0 or y.std() <= 0:
                continue
            rho = float(np.corrcoef(x, y)[0, 1])
            if not math.isfinite(rho):
                continue
            lo, hi = fisher_bounds(rho, len(days))
            measured.update((a, b))
            o = ov_pairs.get((a, b)) or ov_pairs.get(f"{a}|{b}") or {}
            score = _num(o.get("overlap_score")) if isinstance(o, Mapping) else None
            if lo >= REVOKE_RHO or (score is not None and score >= link):
                state = "DEPENDENT"
                parent[find(a)] = find(b)
            elif len(days) >= MIN_INDEPENDENCE_OBS and max(abs(lo), abs(hi)) <= INDEPENDENT_RHO \
                    and (score is None or score <= indep):
                state = "INDEPENDENT"
            else:
                state = UNMEASURED
            pairs.append({"a": a, "b": b, "n": len(days), "rho": round(rho, 4),
                          "lo": round(lo, 4), "hi": round(hi, 4), "state": state,
                          "overlap_score": score,
                          "overlap_binding": (o.get("binding_term")
                                              if isinstance(o, Mapping) else None),
                          # the C a dependent pair is lifted to: the larger of its rho lower
                          # bound and its behavioural overlap
                          "dependence": round(max(lo, score or 0.0), 4)})
    streams: dict[str, list[str]] = defaultdict(list)
    for n in sorted(measured):
        streams[find(n)].append(n)
    status = MEASURED if measured else UNMEASURED
    worst = ov.get("stream_worst") if isinstance(ov.get("stream_worst"), Mapping) else {}
    by_identity: dict[str, float] = {}
    for name, w in worst.items():
        sym, fam, _ = sleeve_identity(name)
        sc = _num((w or {}).get("overlap_score"))
        if sym and fam and sc is not None:
            k = f"{sym}|{fam}"
            by_identity[k] = max(by_identity.get(k, 0.0), sc)
    return {"status": status, "pairs": pairs, "n_sleeves_with_measured_pair": len(measured),
            "overlap": {k: ov.get(k) for k in ("status", "n_streams", "n_pairs",
                                                "n_pairs_measured", "terms_measured",
                                                "event_calendar", "n_linked", "rule", "why")},
            "overlap_by_identity": by_identity,
            "streams": sorted(streams.values(), key=lambda g: (-len(g), g)),
            "n_independent_streams": len(streams) if measured else None,
            "rule": (f"Fisher-z 95%: DEPENDENT at lower bound >= {REVOKE_RHO}; INDEPENDENT only on "
                     f">= {MIN_INDEPENDENCE_OBS} days with |bound| <= {INDEPENDENT_RHO}; else "
                     f"UNMEASURED. Pairs need >= {MIN_PAIR_OBS} overlapping days")}


# ---------------------------------------------------------------- book-level stress/tail
def _so() -> Any:
    try:
        from research import stream_overlap as so
    except ImportError:                                                  # pragma: no cover
        import stream_overlap as so  # type: ignore[import-not-found,no-redef]
    return so


def book_breadth(exposure: Mapping[str, float], panel: Mapping[str, Any]) -> dict[str, Any]:
    """Full, stress and TAIL k_eff of the CERTIFIED book's instrument exposure (law 14, 15, 21).

    Unit risk per certificate group on its instrument, unsigned (a certificate's sign is often
    undeclared), so correlations enter as |rho| -- the conservative direction. Stress conditions
    on the top quintile of a LAGGED 20-day volatility; tail uses two-sided co-exceedance of the
    worst decile: lambda_ij = P(|r_j| in its top decile | |r_i| in its top decile)."""
    from libs.research.effective_breadth import exposure_neff, lagged_vol_regime
    syms = sorted(s for s in exposure if s in panel)
    if len(syms) < 2:
        return {"status": UNMEASURED, "why": f"{len(syms)} certified instrument(s) with bars"}
    import pandas as pd
    df = pd.DataFrame({s: panel[s] for s in syms}).dropna()
    if len(df) < MIN_COUPLING_OBS:
        return {"status": UNMEASURED, "why": f"{len(df)} aligned days, below {MIN_COUPLING_OBS}"}
    m = df.to_numpy(dtype="float64")
    x = np.array([abs(float(exposure[s])) for s in syms])
    nominal = float(x.sum())
    out: dict[str, Any] = {"status": MEASURED, "n_instruments": len(syms), "n_obs": len(df),
                           "nominal": nominal}

    def keff(mat: np.ndarray) -> float | None:
        if mat.shape[0] < MIN_PAIR_OBS * 3:
            return None
        sd = mat.std(axis=0)
        if not np.all(sd > 0):
            return None
        c = np.abs(np.corrcoef(mat, rowvar=False))
        bias = math.sqrt(2.0 / (math.pi * mat.shape[0]))       # shrink_abs_rho, vectorised
        c = np.clip(c - bias, 0.0, None)
        np.fill_diagonal(c, 1.0)
        c, _psd = nearest_psd(c, "book_correlation")
        try:
            return round(float(exposure_neff(nominal, x, c)), 4)
        except ValueError:
            return None
    out["k_eff_full"] = keff(m)
    try:
        regime = lagged_vol_regime({s: list(df[s]) for s in syms}, window=20)
        reg = np.asarray(regime, dtype="float64")
        if reg.size == m.shape[0]:
            cut = np.nanquantile(reg, 0.8)
            out["k_eff_stress"] = keff(m[reg >= cut])
    except Exception as exc:
        out["k_eff_stress"] = None
        out["stress_why"] = f"{type(exc).__name__}"
    a = np.abs(m)
    thr = np.quantile(a, 0.9, axis=0)
    hit = a >= thr
    cnt = hit.sum(axis=0).astype("float64")
    co = (hit.T.astype("float64") @ hit.astype("float64"))
    lam = co / np.maximum(cnt[:, None], 1.0)
    lam = (lam + lam.T) / 2.0
    np.fill_diagonal(lam, 1.0)
    try:
        out["k_eff_tail"] = round(float(exposure_neff(nominal, x, lam)), 4)
    except ValueError:
        out["k_eff_tail"] = None
    vals = [v for v in (out.get("k_eff_full"), out.get("k_eff_stress"), out.get("k_eff_tail"))
            if isinstance(v, (int, float))]
    out["robust_k_eff"] = min(vals) if vals else None
    out["binding"] = (min(("k_eff_full", "k_eff_stress", "k_eff_tail"),
                          key=lambda k: out.get(k) if isinstance(out.get(k), (int, float))
                          else float("inf")) if vals else None)
    return out


# ------------------------------------------------------------------------ the build
def shrink_abs_rho(rho: float, n: int) -> float:
    """|rho| with its small-sample upward bias removed, shrunk toward 0 (audit should-fix,
    2026-10-06): E|r| under rho = 0 is sqrt(2 / (pi n)), so pure noise on 60 days reads ~0.10 and
    enters C as coupling. Subtracting that floor and clipping at 0 is n-weighted shrinkage: a long
    sample is barely moved, a short one is pulled hard toward independence's reading of 0."""
    if n <= 1 or not math.isfinite(rho):
        return 0.0
    return max(0.0, abs(float(rho)) - math.sqrt(2.0 / (math.pi * n)))


def nearest_psd(c: np.ndarray, label: str = "C") -> tuple[np.ndarray, dict[str, Any]]:
    """(C, record): C unchanged when positive semi-definite, else its nearest PSD correlation
    matrix (eigenvalues clipped at 0, rescaled to a unit diagonal), with the repair LOGGED.
    A similarity matrix built pairwise from products of factors is not PSD by construction."""
    try:
        ev = np.linalg.eigvalsh(c)
    except np.linalg.LinAlgError as exc:
        return c, {"matrix": label, "status": UNMEASURED, "why": f"eigvalsh: {exc}"}
    rec: dict[str, Any] = {"matrix": label, "size": int(c.shape[0]),
                           "min_eigenvalue": round(float(ev.min()), 8), "repaired": False}
    if ev.min() > -1e-9:
        return c, {**rec, "status": "PSD"}
    w, v = np.linalg.eigh(c)
    fixed = (v * np.clip(w, 0.0, None)) @ v.T
    d = np.sqrt(np.clip(np.diag(fixed), 1e-12, None))
    fixed = fixed / np.outer(d, d)
    np.fill_diagonal(fixed, 1.0)
    rec.update({"status": "REPAIRED", "repaired": True,
                "max_abs_change": round(float(np.abs(fixed - c).max()), 6)})
    return fixed, rec


def _keff_from(counts: np.ndarray, c: np.ndarray) -> float:
    total = float(counts.sum())
    var = float(counts @ c @ counts)
    return (total * total) / var if var > 0 else 0.0


def judged_by_pair(path: Path | None = None) -> dict[tuple[str, str], int]:
    try:
        from research.breadth_rotation import judged_counts
        return dict(judged_counts(path)[1])
    except Exception:
        return {}


def build(*, canon: Any = None, shadow: Any = None, sleeves: Any = None,
          judged: Mapping[tuple[str, str], int] | None = None,
          coupling_tab: Mapping[str, Mapping[str, float]] | None = None,
          residual: Mapping[str, Any] | None = None,
          forward_daily: Mapping[str, Mapping[str, float]] | None = None,
          book: Mapping[str, Any] | None = None, previous: Any = None,
          loader: Callable[[str], Any] | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    """The whole saturation map. Every input left None is read from its artifact."""
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    if canon is None:
        canon, basis = load_survivors(now=now)
    else:
        basis = {"basis": "supplied", "source": "caller", "source_mtime": None,
                 "n_rows": (len(canon.get("survivors") or {}) if isinstance(canon, dict)
                            else None)}
    survivors = canon.get("survivors") if isinstance(canon, dict) else None
    if not isinstance(survivors, dict) or not survivors:
        return {"at": at, "status": UNMEASURED,
                "why": f"no readable certificates in {SURVIVORS_LIVE.name} or {CANON.name}: "
                       "saturation is UNMEASURED and every consumer orders exactly as it did "
                       "before this map existed",
                "certificates": {"n_certificates": 0, "n_effective_certificates": None,
                                 **basis}}
    shadow = _read(SHADOW_STATE) if shadow is None else shadow
    sleeves = _read(SLEEVES) if sleeves is None else sleeves
    judged = judged_by_pair() if judged is None else judged
    previous = _read(REPORT) if previous is None else previous

    certs: list[dict[str, Any]] = []
    for key, cert in survivors.items():
        if not isinstance(cert, dict):
            continue
        sym, fam, params, tf, sess, reg, spec = cert_fields(str(key), cert)
        if not sym or not fam:
            continue
        certs.append({"key": str(key), "sym": sym, "fam": fam, "params": params, "tf": tf,
                      "sess": sess, "reg": reg, "spec": spec, "edge": cert_edge(cert),
                      "gated_at": str(cert.get("gated_at") or ""),
                      "src": str(cert.get("source") or cert.get("hunt")
                                 or str(key).split(".", 1)[0] or UNKNOWN)})
    syms = sorted({c["sym"] for c in certs})
    if coupling_tab is None:
        try:
            coupling_tab, residual = coupling_table(syms, loader)
        except Exception as exc:
            coupling_tab, residual = {}, {"status": UNMEASURED,
                                          "why": f"{type(exc).__name__}: {exc}"[:200]}
    residual = dict(residual or {"status": UNMEASURED})
    resid_of = dict(residual.get("residual_of") or {})

    # forward + live identity, for counts per cluster and L6
    fwd: Counter[tuple[str, str, str]] = Counter()
    fwd_fam: Counter[tuple[str, str]] = Counter()
    for k, row in (shadow or {}).items() if isinstance(shadow, dict) else []:
        if not isinstance(row, dict):
            continue
        parsed = ar.parse_shadow_key(str(k))
        n = _num(row.get("n"))
        ran = bool(n) or str(row.get("status") or "").upper().startswith(("ACTIVE", "PROMOTION"))
        if ran and parsed.get("symbol"):
            s = str(parsed["symbol"]).upper()
            f = ar._tok(parsed.get("family"))
            fwd[(s, f, ar.normalise_session(parsed.get("session")))] += 1
            fwd_fam[(s, f)] += 1
    live: Counter[tuple[str, str]] = Counter()
    srows = sleeves.get("sleeves") if isinstance(sleeves, dict) else sleeves
    for r in srows if isinstance(srows, list) else []:
        if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE":
            live[(str(r.get("symbol") or "").upper(), ar._tok(r.get("family")))] += 1

    # 21 axes per certificate, grouped (structure, instrument)
    groups: dict[tuple[tuple[str, ...], str], dict[str, Any]] = {}
    for c in certs:
        ax = axes_of(c["sym"], c["fam"], c["params"], timeframe=c["tf"], session=c["sess"],
                     regime_hint=c["reg"], spec=c["spec"], factor_residual=resid_of)
        c["axes"] = ax
        c["cluster"] = cluster_key(ax)
        c["economic"] = economic_key(ax)
        gk = (signature(ax), c["sym"])
        g = groups.setdefault(gk, {"sig": gk[0], "sym": c["sym"], "axes": ax, "n": 0,
                                   "cluster": c["cluster"], "economic": c["economic"],
                                   "certs": [], "families": set()})
        g["n"] += 1
        g["certs"].append(c["key"])
        g["families"].add(c["fam"])
    glist = list(groups.values())
    G = len(glist)
    counts = np.array([float(g["n"]) for g in glist])
    sigs = sorted({g["sig"] for g in glist})
    sig_ix = {s: i for i, s in enumerate(sigs)}
    sig_axes = {g["sig"]: g["axes"] for g in glist}
    S = np.ones((len(sigs), len(sigs)))
    for i, a in enumerate(sigs):
        for j in range(i + 1, len(sigs)):
            v = similarity(sig_axes[a], sig_axes[sigs[j]], factor_free=True)
            S[i, j] = S[j, i] = v
    C = np.ones((G, G))
    for i in range(G):
        for j in range(i + 1, G):
            v = (S[sig_ix[glist[i]["sig"]], sig_ix[glist[j]["sig"]]]
                 * coupling(glist[i]["sym"], glist[j]["sym"], coupling_tab))
            C[i, j] = C[j, i] = v
    C, psd_structural = nearest_psd(C, "structural_C")
    n_eff_structural = _keff_from(counts, C)

    # FORWARD CONFIRMATION (law 23): realised dependence raises C (revokes credit); measured
    # independence on a sufficient sample may lower it (exception F). Never history-rewriting:
    # every adjustment is listed with its evidence.
    fdep = forward_dependence(forward_daily or {}) if forward_daily is not None else {
        "status": UNMEASURED, "why": "no forward ledgers supplied", "pairs": [],
        "n_independent_streams": None, "streams": []}
    g_of_pair: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, g in enumerate(glist):
        for fam in g["families"]:
            g_of_pair[(g["sym"], ar._tok(fam))].append(i)
    revocations: list[dict[str, Any]] = []
    credits_f: list[dict[str, Any]] = []
    for p in fdep.get("pairs") or []:
        if p["state"] == UNMEASURED:
            continue
        sa, fa, _ = sleeve_identity(p["a"])
        sb, fb, _ = sleeve_identity(p["b"])
        ia, ib = g_of_pair.get((sa, fa), []), g_of_pair.get((sb, fb), [])
        for i in ia:
            for j in ib:
                if i == j:
                    continue
                dep = float(p.get("dependence", p["lo"]))
                if p["state"] == "DEPENDENT" and C[i, j] < dep:
                    revocations.append({"a": glist[i]["certs"][0], "b": glist[j]["certs"][0],
                                        "structural_C": round(float(C[i, j]), 4),
                                        "measured_lower_bound": p["lo"],
                                        "measured_overlap": p.get("overlap_score"),
                                        "overlap_binding": p.get("overlap_binding"),
                                        "n": p["n"], "sleeves": [p["a"], p["b"]]})
                    C[i, j] = C[j, i] = dep
                elif p["state"] == "INDEPENDENT" and C[i, j] > p["hi"]:
                    credits_f.append({"a": glist[i]["certs"][0], "b": glist[j]["certs"][0],
                                      "structural_C": round(float(C[i, j]), 4),
                                      "measured_upper_bound": p["hi"], "n": p["n"]})
                    C[i, j] = C[j, i] = max(0.0, abs(p["hi"]))
    # a mixed forward adjustment can leave C indefinite: repaired to the nearest PSD matrix and
    # logged (audit should-fix), rather than silently discarding the forward evidence
    C, psd_adjusted = nearest_psd(C, "forward_adjusted_C")
    n_eff = (_keff_from(counts, C) if psd_adjusted.get("status") != UNMEASURED
             else n_eff_structural)

    # clusters: saturation scores (law 6), adaptive saturation (law 20)
    total_judged = sum(int(v) for v in judged.values())
    n_cert = len(certs)
    global_yield = (n_cert / total_judged) if total_judged else None
    judged_by_econ: Counter[str] = Counter()
    for (sym, fam), n in judged.items():
        ax = axes_of(sym, fam, {})
        judged_by_econ[f"{ax['_mechanism']}/{ax['economic_factor']}"] += int(n)
    by_cluster: dict[str, list[int]] = defaultdict(list)
    for i, g in enumerate(glist):
        by_cluster[g["cluster"]].append(i)
    certs_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in certs:
        certs_by_cluster[c["cluster"]].append(c)
    l1_values: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for g in glist:
        h = hierarchy(g["axes"])
        for axis in ("session", "horizon", "regime", "information_source", "economic_factor",
                     "asset_class"):
            l1_values[h["L1"]][axis].add(str(g["axes"].get(axis)))
    clusters: dict[str, dict[str, Any]] = {}
    for ck, idx in by_cluster.items():
        sub_n = counts[idx]
        sub_c = C[np.ix_(idx, idx)]
        eff = _keff_from(sub_n, sub_c)
        cs = certs_by_cluster[ck]
        edges = sorted(e for e in (c["edge"] for c in cs) if e is not None)
        econ = glist[idx[0]]["economic"]
        tri = judged_by_econ.get(econ, 0)
        n_k = len(cs)
        # Beta posterior for this economic cluster's yield, centred on the desk's own rate
        if global_yield is not None:
            a0 = global_yield * PRIOR_STRENGTH
            b0 = (1.0 - global_yield) * PRIOR_STRENGTH
            eccerts = sum(1 for c in certs if c["economic"] == econ)
            post = (a0 + eccerts) / (a0 + b0 + max(tri, eccerts))
            yield_ratio = post / global_yield if global_yield > 0 else 1.0
        else:
            post, yield_ratio = None, 1.0
        # a clone of this cluster: its effective local count is the C-weighted count of the
        # cluster's (structure, instrument) groups around its densest member -- parameter
        # variants count once, exactly as the Scorer counts a docket candidate's neighbours
        local = (float(max((sub_c[r] * (sub_c[r] >= LOCAL_FLOOR)).sum()
                           for r in range(len(idx)))) if idx else 0.0)
        clone_credit = novelty_credit(local)
        value = clone_credit * min(yield_ratio, 2.0)
        mean_c = (float((sub_c.sum() - np.trace(sub_c)) / max(len(idx) * (len(idx) - 1), 1))
                  if len(idx) > 1 else None)
        h = hierarchy(glist[idx[0]]["axes"])
        occupied = {a: {str(glist[i]["axes"].get(a)) for i in idx}
                    for a in ("session", "horizon", "regime")}
        unexplored = {a: sorted(l1_values[h["L1"]][a] - occupied.get(a, set()))
                      for a in ("session", "horizon", "regime")}
        fwd_n = sum(fwd[(c["sym"], ar._tok(c["fam"]), str(c["axes"].get("session")))]
                    for c in cs)
        live_n = sum(live[(c["sym"], ar._tok(c["fam"]))] for c in cs)
        saturated = n_k >= 2 and value < MATERIAL_FALL
        ranked = sorted(cs, key=lambda c: (-(fwd_fam[(c["sym"], ar._tok(c["fam"]))] > 0),
                                           -(c["edge"] if c["edge"] is not None else -9.0),
                                           c["key"]))
        clusters[ck] = {
            "hierarchy": h, "economic_cluster": econ,
            "certificate_count": n_k, "strategy_variants": len(idx),
            "effective_certificate_count": round(eff, 4),
            "forward_count": fwd_n, "live_count": live_n,
            "effective_trials_spent": tri, "effective_trials_basis": (
                "judged cells of the economic cluster (gauntlet_seen_cells, family x symbol)"),
            "best_validated_edge": round(edges[-1], 4) if edges else None,
            "median_validated_edge": round(float(np.median(edges)), 4) if edges else None,
            "incremental_survivor_yield": round(post, 6) if post is not None else None,
            "yield_ratio": round(yield_ratio, 4),
            "mean_intra_cluster_C": round(mean_c, 4) if mean_c is not None else None,
            "worst_stress_correlation": None, "worst_stress_status": UNMEASURED,
            "realised_marginal_k_eff": None, "realised_marginal_status": UNMEASURED,
            "clone_effective_local_count": round(local, 4),
            "clone_novelty_credit": round(clone_credit, 4),
            "marginal_search_value": round(value, 4),
            "remaining_unexplored_axes": unexplored,
            "families": sorted({c["fam"] for c in cs}),
            "failure_modes": list(failure_modes(glist[idx[0]]["axes"])),
            "state": "SATURATED" if saturated else ("OCCUPIED" if n_k else "EMPTY"),
            # law 20 / producer law 19: one champion, a small challenger set, the rest archive
            "champion": ranked[0]["key"] if (saturated and ranked) else None,
            "challengers": [c["key"] for c in ranked[1:1 + CHALLENGERS]] if saturated else [],
            "archive_count": max(0, len(ranked) - 1 - CHALLENGERS) if saturated else 0,
            "_archive": [c["key"] for c in ranked[1 + CHALLENGERS:]] if saturated else [],
        }

    # failure-mode breadth (law 22) and what hurts the book (producer law 13)
    fm_count: Counter[str] = Counter()
    for c in certs:
        for m in failure_modes(c["axes"]):
            fm_count[m] += 1
    tot = sum(fm_count.values())
    shares = np.array([v / tot for v in fm_count.values()]) if tot else np.array([])
    fm_eff = float(1.0 / (shares ** 2).sum()) if shares.size else None
    hurts = [m for m, _ in fm_count.most_common(3)]
    hedgers = sorted(mech for mech, modes in MECHANISM_FAILURE.items()
                     if not set(modes) & set(hurts))

    # empty-cluster priors (law 17) for the 15 declared phenomena, decaying with effort
    empty_priors = _empty_priors(certs, judged, global_yield, previous)

    # family split / merge (law 29 of the open-ended law)
    fam_clusters: dict[str, Counter[str]] = defaultdict(Counter)
    for c in certs:
        fam_clusters[c["fam"]][hierarchy(c["axes"])["L1"] + "|" + hierarchy(c["axes"])["L5"]] += 1
    split = [{"family": f, "clusters": dict(cnt.most_common(6))}
             for f, cnt in sorted(fam_clusters.items())
             if sum(1 for v in cnt.values() if v >= 3) >= 2]
    merge = [{"cluster": ck, "families": v["families"]} for ck, v in sorted(clusters.items())
             if len(v["families"]) >= 2]

    # breadth debts (producer law 27 / open-ended law 21)
    debts = _breadth_debts(clusters, glist, judged, global_yield, n_cert, n_eff, hurts,
                           empty_priors)
    l6 = fdep.get("n_independent_streams")
    live_streams = None
    if fdep.get("status") == MEASURED:
        live_names = {f"{s}|{f}" for (s, f) in live}
        live_streams = sum(1 for g in fdep.get("streams") or []
                           if any("|".join(sleeve_identity(x)[:2]) in live_names for x in g))
    n_variants = len({g["cluster"] for g in glist})
    quality = edge_quality(certs, now=now)
    # DUPLICATE SURVIVORS (producer law 8): certificates that passed every gate into a SATURATED
    # cluster behind its champion and challengers -- the archive. A share, not a verdict: they stay
    # certified; the share says how much of the factory's output bought no new bet.
    dup_keys = {k for v in clusters.values() for k in (v.get("_archive") or [])}
    by_src: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for c in certs:
        by_src[c["src"]][0] += 1
        by_src[c["src"]][1] += int(c["key"] in dup_keys)
    duplicate_survivors = {
        "share": round(len(dup_keys) / n_cert, 4) if n_cert else None,
        "n_duplicate_survivors": len(dup_keys),
        "by_producer": {k: {"certificates": n, "duplicates": d, "share": round(d / n, 4)}
                        for k, (n, d) in sorted(by_src.items()) if n},
        "rule": ("a certificate archived behind the champion and challengers of a SATURATED "
                 "cluster; it stays certified and nothing is revoked"),
    }
    # N_EFF IS ONLY AS MEASURED AS ITS COUPLING (audit 2026-10-06): an instrument with no bars has
    # no measured |rho| to anything and couples at the DECLARED prior. The 09-28 canon had 13 of
    # 27 certified instruments without bars, so its N_EFF was a prior-weighted figure. Any such
    # instrument labels the headline UNMEASURED with the count; the number stays beside it.
    cert_syms = sorted({str(g["sym"]).upper() for g in glist})
    unbarred = [x for x in cert_syms if not (coupling_tab or {}).get(x)]
    n_eff_status = (MEASURED if cert_syms and not unbarred else
                    f"{UNMEASURED}: {len(unbarred)} of {len(cert_syms)} certified instruments "
                    f"without bars couple at the declared prior")
    # THE CHAMPION CAP, RESEARCH SIDE ONLY (law 20, producer law 19). Beyond the champion and
    # its challengers a SATURATED cluster's certificates earn NO breadth credit: the capped
    # count drops them from the group weights. Nothing about their certification, capital,
    # sizing, promotion or live status changes -- that side of the cap is REFUSED by growth
    # governance and never built (`capital_side` below says so in the artifact).
    counts_cap = np.array([float(sum(1 for k in g["certs"] if k not in dup_keys))
                           for g in glist])
    n_eff_capped = (_keff_from(counts_cap, C) if counts_cap.sum() > 0 else 0.0)
    champion_cap = {
        "n_certificates_credited": int(counts_cap.sum()),
        "n_certificates_archived": len(dup_keys),
        "n_effective_certificates_champion_capped": round(n_eff_capped, 3),
        "scope": "research priority and breadth counting only",
        "capital_side": ("REFUSED_BY_GROWTH_GOVERNANCE: the cap never touches capital, sizing, "
                         "promotion or live status; the promoter only annotates breadth_role"),
    }
    try:
        from research.near_duplicate import structural_key
    except ImportError:                                                 # pragma: no cover
        from near_duplicate import structural_key  # type: ignore[import-not-found,no-redef]
    struct_keys = sorted({structural_key(g["axes"], resid_of) for g in glist})
    headline = {
        **basis,
        "n_certificates": n_cert,
        "n_effective_certificates": round(n_eff, 3),
        "n_effective_status": n_eff_status,
        "instruments_without_bars": unbarred,
        "n_effective_certificates_structural": round(n_eff_structural, 3),
        "n_strategy_variants": G,
        "n_structural_clusters": n_variants,
        "n_economic_clusters": len({g["economic"] for g in glist}),
        "n_payer_clusters": len({hierarchy(g["axes"])["L1"] for g in glist}),
        "n_information_sources": len({g["axes"]["information_source"] for g in glist}),
        "n_factors": len({g["axes"]["economic_factor"] for g in glist}),
        "n_temporal_clusters": len({hierarchy(g["axes"])["L5"] for g in glist}),
        "n_independent_forward_streams": l6,
        "n_live_independent_streams": live_streams,
        "independent_streams_status": fdep.get("status"),
        "effective_over_nominal": round(n_eff / n_cert, 4) if n_cert else None,
        "n_saturated_clusters": sum(1 for v in clusters.values() if v["state"] == "SATURATED"),
        "duplicate_survivor_share": duplicate_survivors["share"],
        "n_certificates_credited": champion_cap["n_certificates_credited"],
        "n_effective_certificates_champion_capped":
            champion_cap["n_effective_certificates_champion_capped"],
        "failure_mode_effective_count": round(fm_eff, 3) if fm_eff else None,
        "median_validated_edge_recent": quality.get("median_recent"),
        "median_validated_edge_prior": quality.get("median_prior"),
        "robust_k_eff_book": (book or {}).get("robust_k_eff"),
        "stress_k_eff_book": (book or {}).get("k_eff_stress"),
        "tail_k_eff_book": (book or {}).get("k_eff_tail"),
    }
    publish_groups = sorted(range(G), key=lambda i: -counts[i])[:MAX_GROUPS_PUBLISHED]
    return {
        "at": at, "status": MEASURED,
        "certificates": headline,
        "line": (f"{n_cert} nominal certificates -> {G} strategy variants -> {n_eff:.1f} "
                 f"effective certificates -> {headline['n_economic_clusters']} economic clusters "
                 f"-> {l6 if l6 is not None else 'UNMEASURED'} independent forward streams"),
        "rule": ("novelty_credit = 1/sqrt(1 + effective_local_count), effective_local_count = "
                 f"sum C(c,g) over certificate groups with C >= {LOCAL_FLOOR}; C = factor-free "
                 "structural similarity x instrument coupling; SATURATED when clone credit x "
                 f"yield ratio < {MATERIAL_FALL} with >= 2 certificates. PRIORITY ONLY: breadth "
                 "decides what is hunted and judged next, never what passes"),
        "weights": WEIGHTS,
        "constants": {"LOCAL_FLOOR": LOCAL_FLOOR, "SATURATED_GROUND_SIM": SATURATED_GROUND_SIM,
                      "MATERIAL_FALL": MATERIAL_FALL, "EXCEPTION_FLOOR": EXCEPTION_FLOOR,
                      "RHO_SAME_FACTOR": RHO_SAME_FACTOR, "RHO_SAME_CLASS": RHO_SAME_CLASS,
                      "RHO_CROSS": RHO_CROSS, "PRIOR_STRENGTH": PRIOR_STRENGTH,
                      "preregistered": "2026-10-06"},
        "global_survivor_yield": global_yield,
        "groups": [{"sig": list(glist[i]["sig"]), "sym": glist[i]["sym"],
                    "n": int(counts[i]), "cluster": glist[i]["cluster"],
                    "economic": glist[i]["economic"], "families": sorted(glist[i]["families"]),
                    "certs": glist[i]["certs"][:5]} for i in publish_groups],
        "groups_total": G,
        "coupling": {a: dict(v) for a, v in (coupling_tab or {}).items()},
        "coupling_rule": "|rho| minus its noise floor sqrt(2/(pi n)), clipped at 0",
        "psd_check": [psd_structural, psd_adjusted],
        "symbol_clusters": residual,
        "clusters": clusters,
        "forward_independence": {k: v for k, v in fdep.items() if k != "pairs"} | {
            "pairs": (fdep.get("pairs") or [])[:200]},
        "revocations": revocations[:200], "measured_independence_credits": credits_f[:200],
        "book_breadth": dict(book or {"status": UNMEASURED, "why": "not supplied"}),
        "failure_modes": {"counts": dict(fm_count.most_common()),
                          "effective_count": round(fm_eff, 3) if fm_eff else None,
                          "status": "DECLARED", "hurts_book": hurts,
                          "hedging_mechanisms": hedgers},
        "empty_cluster_priors": empty_priors,
        "family_split_candidates": split, "family_merge_candidates": merge[:100],
        "breadth_debts": debts,
        "duplicate_survivors": duplicate_survivors,
        "champion_cap": champion_cap,
        # the certified book as the near-duplicate rules and the cheap structural check read it
        "certified_specs": [{"key": c["key"], "sym": c["sym"], "family": c["fam"],
                             "params": c["params"], "tf": c["tf"], "sess": c["sess"],
                             "src": c["src"]} for c in certs[:MAX_SPECS_PUBLISHED]],
        "structural_keys": [list(k) for k in struct_keys],
    }


def edge_quality(certs: list[dict[str, Any]], *, now: datetime | None = None,
                 window_days: float = 7.0) -> dict[str, Any]:
    """Median validated edge of certificates gated in the last `window_days` against the rest:
    the quality half of E[log W] ~ quality^2 x breadth, read by the ladder's budget split."""
    t0 = (now or datetime.now(tz=UTC)).timestamp() - window_days * 86400.0
    recent: list[float] = []
    prior: list[float] = []
    for c in certs:
        e = c.get("edge")
        if e is None:
            continue
        try:
            ts = datetime.fromisoformat(str(c.get("gated_at")).replace("Z", "+00:00"))
            ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        except ValueError:
            continue
        (recent if ts.timestamp() >= t0 else prior).append(float(e))
    return {"median_recent": round(float(np.median(recent)), 4) if recent else None,
            "median_prior": round(float(np.median(prior)), 4) if prior else None,
            "n_recent": len(recent), "n_prior": len(prior), "window_days": window_days}


def _empty_priors(certs: list[dict[str, Any]], judged: Mapping[tuple[str, str], int],
                  global_yield: float | None, previous: Any) -> dict[str, Any]:
    """Per declared alpha cluster: the survivor prior after the effort spent there (law 17).

    `decay` = posterior yield / desk yield, clipped [EXPLORE_FLOOR, 1], and 1.0 until the
    cluster has consumed a STATISTICALLY MEANINGFUL effort -- the trial count at which zero
    survivors would be surprising at p < 0.05 under the desk's own rate. A cluster's effort
    resets on an explicit REOPEN TRIGGER: its implementing family set changed (new family =
    new mechanism/representation). The trigger and the offset are carried in the artifact."""
    try:
        from libs.research.alpha_clusters import CLUSTERS, classify_family
    except Exception:                                                   # pragma: no cover
        return {}
    certs_by: Counter[str] = Counter(classify_family(c["fam"]) for c in certs)
    judged_by: Counter[str] = Counter()
    fams_by: dict[str, set[str]] = defaultdict(set)
    for (_sym, fam), n in judged.items():
        k = classify_family(fam)
        judged_by[k] += int(n)
        fams_by[k].add(ar._tok(fam))
    for fam in ar.FAMILY_TABLE:
        fams_by[classify_family(fam)].add(fam)
    prev = (previous or {}).get("empty_cluster_priors") if isinstance(previous, dict) else None
    prev = prev if isinstance(prev, dict) else {}
    meaningful = (math.ceil(math.log(0.05) / math.log(1.0 - global_yield))
                  if global_yield and 0 < global_yield < 1 else None)
    out: dict[str, Any] = {}
    for c in CLUSTERS:
        k = c.key
        fams = sorted(fams_by.get(k, set()))
        fp = ",".join(fams)
        p = prev.get(k) if isinstance(prev.get(k), dict) else {}
        offset = int(p.get("effort_offset") or 0)
        reopened = p.get("reopened_at")
        trigger = p.get("reopen_trigger")
        if p and p.get("families_fingerprint") not in (None, fp):
            offset, reopened = judged_by.get(k, 0), None
            trigger = "family set changed (new mechanism/representation reachable)"
            reopened = datetime.now(tz=UTC).isoformat(timespec="seconds")
        effort = max(0, judged_by.get(k, 0) - offset)
        nc = certs_by.get(k, 0)
        if global_yield is None or meaningful is None:
            decay, status = 1.0, UNMEASURED
        elif nc > 0:
            decay, status = 1.0, "OCCUPIED"
        else:
            # CONTINUOUS, NOT A CLIFF (audit should-fix, 2026-10-06). It was 1.0 up to the
            # meaningful effort and then dropped at once to the posterior ratio (~0.14 at a 1%
            # desk yield). The posterior ratio is now blended in linearly with the effort's share
            # of the meaningful effort: 1.0 at zero effort, exactly the old value at the
            # meaningful effort, the posterior itself beyond it, monotone throughout.
            a0 = global_yield * PRIOR_STRENGTH
            b0 = (1.0 - global_yield) * PRIOR_STRENGTH
            post = (a0 + nc) / (a0 + b0 + effort)
            ratio = min(1.0, max(EXPLORE_FLOOR, post / global_yield))
            w = min(1.0, effort / float(meaningful)) if meaningful else 1.0
            decay = 1.0 - w * (1.0 - ratio)
            status = "SEARCHED_EMPTY" if effort >= meaningful else "UNDER_SEARCHED"
        out[k] = {"certificates": nc, "effort_judged": effort, "meaningful_effort": meaningful,
                  "decay": round(decay, 4), "status": status, "families": fams,
                  "families_fingerprint": fp, "effort_offset": offset,
                  "reopened_at": reopened, "reopen_trigger": trigger,
                  "reopen_when": ("a new family classifies into this cluster, a new dataset "
                                  "feeds it, or market structure changes; recorded here")}
    return out


def _breadth_debts(clusters: Mapping[str, Mapping[str, Any]], glist: list[dict[str, Any]],
                   judged: Mapping[tuple[str, str], int], global_yield: float | None,
                   n_cert: int, n_eff: float, hurts: list[str],
                   empty_priors: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The most valuable MISSING return streams, re-priced every pass (producer law 27, 21).

    The frontier is (L1 mechanism x L2 information x L3 hypothesis-lane class): every pair a
    registered family implements, crossed with the classes the desk may hypothesise on, minus
    what the certified book occupies. Not the full Cartesian product -- only reachable ground."""
    try:
        from libs.research.alpha_clusters import classify_family
        from libs.research.breadth_credit import marginal_k_eff
    except Exception:                                                   # pragma: no cover
        return []
    occupied = {(v["hierarchy"]["L1"], v["hierarchy"]["L2"], v["hierarchy"]["L3"])
                for v in clusters.values()}
    occ_l1 = Counter(v["hierarchy"]["L1"] for v in clusters.values())
    classes = ("forex", "forex_exotics", "commodities", "energy", "indices", "soft_commodity",
               "bonds", "crypto")
    impl: dict[tuple[str, str], list[str]] = defaultdict(list)
    for fam, (mech, info, _style) in ar.FAMILY_TABLE.items():
        if mech != UNKNOWN and fam not in getattr(ar, "NOT_A_FAMILY", frozenset()):
            impl[(mech, info)].append(fam)
    effort: Counter[tuple[str, str, str]] = Counter()
    for (sym, fam), n in judged.items():
        mech, info, _ = ar.classify_family(fam)
        effort[(mech, info, asset_class(sym))] += int(n)
    def _dk(rho: float) -> float | None:
        try:
            return (marginal_k_eff(max(n_cert, 2), max(n_eff, 1e-6), rho)
                    if n_cert > 1 else 1.0)
        except ValueError:
            return None

    # EACH DEBT IS PRICED BY ITS OWN dk_eff (audit must-fix 2, 2026-10-06). The constant RHO_CROSS
    # price gave every debt the same 0.082, so six debts saturated every bid and nothing repriced.
    # A missing cluster's expected correlation with the book now rises with how much of its
    # (payer, information, asset class) the certified book already holds: rho = RHO_CROSS +
    # (RHO_SAME_FACTOR - RHO_CROSS) x shared/3 against the most similar occupied cluster. Paying
    # one debt occupies its cluster, which raises `shared` for its neighbours and so reprices them.
    dk_ref = _dk(RHO_CROSS)
    debts: list[dict[str, Any]] = []
    for (mech, info), fams in sorted(impl.items()):
        for cls in classes:
            if (mech, info, cls) in occupied:
                continue
            shared = max((int(m == mech) + int(i == info) + int(c == cls)
                          for (m, i, c) in occupied), default=0)
            rho_d = RHO_CROSS + (RHO_SAME_FACTOR - RHO_CROSS) * shared / 3.0
            dk = _dk(rho_d)
            e = effort.get((mech, info, cls), 0)
            cluster = next((classify_family(f) for f in sorted(fams)
                            if classify_family(f) != "UNCLASSIFIED"), "UNCLASSIFIED")
            decay = float((empty_priors.get(cluster) or {}).get("decay") or 1.0)
            info_value = 1.0 + 1.0 / (1.0 + e / 100.0)
            hedge = 1.5 if not (set(MECHANISM_FAILURE.get(mech, ())) & set(hurts)) else 1.0
            payer_bonus = 1.5 if occ_l1.get(mech, 0) == 0 else 1.0
            prio = float(dk if dk is not None else 1.0) * decay * info_value * hedge * payer_bonus
            debts.append({
                "missing_cluster": f"{mech}/{info}/{cls}", "mechanism": mech,
                "information_source": info, "asset_class": cls, "alpha_cluster": cluster,
                "economic_rationale": ar.MECHANISM_ACTOR.get(mech, UNKNOWN),
                "current_nearest_exposure": (f"{occ_l1[mech]} occupied cluster(s) share this "
                                             "payer" if occ_l1.get(mech) else
                                             "no certified sleeve holds this payer anywhere"),
                "expected_delta_k_eff": round(dk, 6) if dk is not None else None,
                "expected_rho_to_book": round(rho_d, 4), "shared_axes_with_book": shared,
                # value in units of one cross-correlated new stream: what the auction sums
                "value_units": (round(max(0.0, dk) / dk_ref, 6)
                                if dk is not None and dk_ref else None),
                "expected_independence": round(1.0 - rho_d, 3),
                "required_data": info, "candidate_producers": sorted(fams)[:8],
                "historical_search_effort": e,
                "failure_history": ("searched, nothing certified" if e else "never searched"),
                "empty_prior_decay": round(decay, 4),
                "hedges_failure_modes": hedge > 1.0, "new_payer": payer_bonus > 1.0,
                "reopen_trigger": ("new family / dataset / representation for this payer, or "
                                   "market-structure change"),
                "bounty": round(prio, 6),
            })
    debts.sort(key=lambda d: (-d["bounty"], d["missing_cluster"]))
    for i, d in enumerate(debts):
        d["priority"] = i + 1
    return debts[:200]


# ------------------------------------------------------------------- publish / load
def publish(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    target = path or REPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    out = dict(doc)
    cl = out.get("clusters")
    if isinstance(cl, dict):
        out["clusters"] = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                           | {"archive": v.get("_archive", [])}
                           for k, v in cl.items()}
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    os.replace(tmp, target)
    return target


def load(path: Path | None = None, *, max_age_h: float = MAX_AGE_H,
         now: datetime | None = None) -> tuple[dict[str, Any] | None, str]:
    """The published map, or (None, why) when absent, unmeasured or stale."""
    p = path or REPORT
    doc = _read(p)
    if not isinstance(doc, dict):
        return None, f"{p.name} absent or unreadable"
    if doc.get("status") != MEASURED:
        return None, f"{p.name} is {doc.get('status')}: {doc.get('why')}"
    try:
        t = datetime.fromisoformat(str(doc.get("at")).replace("Z", "+00:00"))
        age = ((now or datetime.now(tz=UTC)) - t).total_seconds() / 3600.0
        if age > max_age_h:
            return None, f"{p.name} is {age:.1f}h old, beyond {max_age_h}h"
    except (TypeError, ValueError):
        return None, f"{p.name} carries no readable timestamp"
    return doc, "fresh"


def read_fresh(path: Path | None = None, *, max_age_h: float = MAX_AGE_H,
               now: datetime | None = None) -> dict[str, Any]:
    """The map for a reader that wants a dict: the published map when fresh, else an UNMEASURED
    stub naming why (audit should-fix, 2026-10-06). A map older than its window is never read as
    the old number -- a stale reading of breadth is not a reading of breadth now (L1.28a)."""
    doc, why = load(path, max_age_h=max_age_h, now=now)
    return dict(doc) if doc is not None else {"status": UNMEASURED, "why": why}


# ------------------------------------------------------------------------ the scorer
class Scorer:
    """Scores candidates against a published map. Vectorised over the certificate signatures and
    cached twice -- on the raw row fields and on the derived (structure, instrument) key -- so a
    1.4M-row docket costs a few thousand similarity evaluations, not 1.4M."""

    def __init__(self, doc: Mapping[str, Any]):
        self.doc = doc
        self.coupling = doc.get("coupling") or {}
        self.resid = dict((doc.get("symbol_clusters") or {}).get("residual_of") or {})
        self.clusters = doc.get("clusters") or {}
        gs = doc.get("groups") or []
        self.g_sym = [str(g["sym"]) for g in gs]
        self.g_cluster = [str(g.get("cluster")) for g in gs]
        sigs = sorted({tuple(g["sig"]) for g in gs})
        self.sig_ix = {s: i for i, s in enumerate(sigs)}
        self.g_sig = np.array([self.sig_ix[tuple(g["sig"])] for g in gs], dtype=int)
        self.sig_axes = [dict(zip(SIG_AXES, s, strict=False)) for s in sigs]
        self.vocab: list[dict[str, int]] = []
        mat = np.full((max(len(sigs), 1), len(SIG_AXES)), -1, dtype=int)
        for a in range(len(SIG_AXES)):
            voc: dict[str, int] = {}
            for i, s in enumerate(sigs):
                v = str(s[a]) if a < len(s) else UNKNOWN
                if v == UNKNOWN:
                    continue
                mat[i, a] = voc.setdefault(v, len(voc))
            self.vocab.append(voc)
        self.mat = mat[:len(sigs)]
        self.w_full = np.array([WEIGHTS[a] for a in SIG_AXES])
        self.w_ff = np.array([0.0 if a in FACTOR_AXES else WEIGHTS[a] for a in SIG_AXES])
        self.sym_cache: dict[str, np.ndarray] = {}
        self.cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self.raw_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self.archive = {k for v in self.clusters.values() for k in (v.get("archive") or [])}
        self.champions = {v.get("champion") for v in self.clusters.values() if v.get("champion")}
        self.struct_keys = {tuple(k) for k in (doc.get("structural_keys") or [])
                            if isinstance(k, list)}
        self._nd_index: Any = None
        fi = doc.get("forward_independence") if isinstance(doc.get("forward_independence"),
                                                           Mapping) else {}
        self._cap_ctx: Any = None
        self.overlap_by_identity = {str(k): float(v) for k, v in
                                    ((fi or {}).get("overlap_by_identity") or {}).items()
                                    if _num(v) is not None}

    def near_dup(self, row: Mapping[str, Any]) -> tuple[str, str] | None:
        """The near-duplicate rule `row` breaks against the certified book (law §3), or None."""
        if self._nd_index is None:
            try:
                from research import near_duplicate as nd
            except ImportError:
                import near_duplicate as nd  # type: ignore[import-not-found,no-redef]
            self._nd = nd
            self._nd_index = nd.Index(self.doc.get("certified_specs") or [])
        return self._nd.near_duplicate(row, self._nd_index)

    def capacity(self, sym: str, ax: Mapping[str, Any]) -> dict[str, Any]:
        """The six capacity terms in breadth credit (law §15); 1.0 when unreadable."""
        try:
            if self._cap_ctx is None:
                try:
                    from research import breadth_capacity as bcap
                except ImportError:
                    import breadth_capacity as bcap  # type: ignore[import-not-found,no-redef]
                self._bcap = bcap
                self._cap_ctx = bcap.Context()
            return dict(self._bcap.terms(sym, ax, self._cap_ctx))
        except Exception as exc:                                         # pragma: no cover
            return {"factor": 1.0, "terms": {}, "unmeasured": {"all": type(exc).__name__}}

    def _coup(self, sym: str) -> np.ndarray:
        v = self.sym_cache.get(sym)
        if v is None:
            v = np.array([coupling(sym, s, self.coupling) for s in self.g_sym])
            self.sym_cache[sym] = v
        return v

    def _sims(self, ax: Mapping[str, str]) -> tuple[np.ndarray, np.ndarray]:
        code = np.array([(-1 if str(ax.get(a, UNKNOWN)) == UNKNOWN
                          else self.vocab[i].get(str(ax.get(a)), -2))
                         for i, a in enumerate(SIG_AXES)], dtype=int)
        eq = (self.mat == code) | (self.mat == -1) | (code == -1)
        full = (eq @ self.w_full) / self.w_full.sum()
        ff = (eq @ self.w_ff) / self.w_ff.sum()
        return full, ff

    def score_fields(self, sym: str, fam: str, params: Mapping[str, Any], tf: Any, sess: Any,
                     reg: Any) -> dict[str, Any]:
        rk = _raw_key(sym, fam, params, tf, sess, reg)
        hit = self.raw_cache.get(rk)
        if hit is not None:
            return hit
        ax = axes_of(sym, fam, params, timeframe=tf, session=sess, regime_hint=reg,
                     factor_residual=self.resid)
        key = (signature(ax), sym)
        hit = self.cache.get(key)
        if hit is not None:
            self.raw_cache[rk] = hit
            return hit
        cap = self.capacity(sym, ax)
        if not self.g_sym:
            out = {"novelty_credit": 1.0, "effective_local_count": 0.0, "nearest_sim": 0.0,
                   "nearest_cluster": None, "saturated_ground": False, "exceptions": [],
                   "cluster": cluster_key(ax), "economic": economic_key(ax),
                   "capacity_factor": cap["factor"], "capacity_terms": cap["terms"]}
            self.cache[key] = self.raw_cache[rk] = out
            return out
        sims, sims_ff = self._sims(ax)
        c = sims_ff[self.g_sig] * self._coup(sym)
        local = float(c[c >= LOCAL_FLOOR].sum())
        full = sims[self.g_sig]
        j = int(np.argmax(full))
        near_cluster = self.g_cluster[j]
        near_state = (self.clusters.get(near_cluster) or {}).get("state")
        sat_ground = bool(full[j] >= SATURATED_GROUND_SIM and near_state == "SATURATED")
        near = self.sig_axes[int(self.g_sig[j])]
        exc: list[str] = []
        if sat_ground:
            if ax["_mechanism"] != UNKNOWN and ax.get("payer") != near.get("payer"):
                exc.append("A")
            if ax["information_source"] != near.get("information_source"):
                exc.append("B")
            if (ax["horizon"] != near.get("horizon")
                    or ax["event_dependence"] != near.get("event_dependence")):
                exc.append("C")
            if ax["regime"] != near.get("regime"):
                exc.append("D")
            if (ax["economic_factor"] != near.get("economic_factor")
                    or ax["factor_residual"] != near.get("factor_residual")):
                exc.append("E")
        try:
            from research.near_duplicate import structural_key
        except ImportError:
            from near_duplicate import structural_key  # type: ignore[import-not-found,no-redef]
        out = {"novelty_credit": round(novelty_credit(local), 6),
               "structural_duplicate": structural_key(ax, self.resid) in self.struct_keys,
               "effective_local_count": round(local, 4),
               "nearest_sim": round(float(full[j]), 4), "nearest_cluster": near_cluster,
               "saturated_ground": sat_ground, "exceptions": exc,
               "cluster": cluster_key(ax), "economic": economic_key(ax),
               "capacity_factor": cap["factor"], "capacity_terms": cap["terms"]}
        self.cache[key] = self.raw_cache[rk] = out
        return out

    def score_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        sym, fam, params, tf, sess, reg = row_fields(row)
        base = dict(self.score_fields(sym, fam, params, tf, sess, reg))
        exc = list(base["exceptions"])
        # BEHAVIOURAL OVERLAP (breadth law §4, §16): the row's own measured overlap with the
        # book, else the realised overlap of the forward sleeve that runs this rule on this symbol
        ov = row.get("measured_overlap")
        ov_score = _num(ov.get("overlap_score")) if isinstance(ov, Mapping) else _num(ov)
        if ov_score is None:
            ov_score = self.overlap_by_identity.get(f"{str(sym).upper()}|{ar._tok(fam)}")
        so = _so()
        mi = row.get("measured_independence")
        if isinstance(mi, Mapping):
            n, hi = _num(mi.get("n")), _num(mi.get("rho_upper"))
            if n is not None and hi is not None and n >= MIN_INDEPENDENCE_OBS \
                    and abs(hi) <= INDEPENDENT_RHO \
                    and (ov_score is None or ov_score <= so.OVERLAP_INDEPENDENT):
                exc.append("F")
        if (_num(row.get("delta_elogw")) or 0.0) > 0 and row.get("delta_elogw_status") == MEASURED:
            exc.append("H")
        quality = is_quality_row(row)
        if quality:
            exc.append("G")
        declared = str(row.get("breadth_exception") or "").strip().upper()[:1]
        if declared and declared in "ABCDEH" and declared not in exc:
            # a declared A-E/H is RECORDED but honoured only when structure or evidence agrees
            base["declared_unverified"] = declared
        credit = float(base["novelty_credit"])
        if any(e in exc for e in "ABCDEFH"):
            credit = max(credit, EXCEPTION_FLOOR)
        if ov_score is not None:
            # a stream that behaves like the book is not new breadth, whatever its axes say
            base["measured_overlap"] = round(ov_score, 4)
            credit = min(credit, max(DUPLICATE_TAX_FLOOR, 1.0 - ov_score))
        # CAPACITY IN BREADTH CREDIT (law §15): breadth the desk cannot hold at size counts less
        credit *= float(base.get("capacity_factor") or 1.0)
        nd = self.near_dup(row) if self.doc.get("certified_specs") else None
        base["near_duplicate_rule"] = nd[0] if nd else None
        base["near_duplicate_of"] = nd[1] if nd else None
        duplicate = bool((base["saturated_ground"] or nd) and not exc)
        parent = str(row.get("parent_certificate") or row.get("challenger_of") or "")
        base.update({"exceptions": exc, "channel": "QUALITY" if quality else "BREADTH",
                     "breadth_value": round(credit, 6), "duplicate": duplicate,
                     "challenges_archived": bool(parent and parent in self.archive),
                     "challenges_champion": bool(parent and parent in self.champions)})
        return base


_RELEVANT_PARAM_KEYS = frozenset(_SIDE_KEYS) | frozenset(_DRIVER_KEYS) | frozenset(
    ar.HOLD_KEYS) | frozenset(ar.REGIME_KEYS) | {"timeframe", "session", "selector",
                                                  "hold_days", "horizon_days"}


def _raw_key(sym: str, fam: str, params: Mapping[str, Any], tf: Any, sess: Any,
             reg: Any) -> tuple[Any, ...]:
    keys = tuple(sorted(str(k) for k in params))
    vals = tuple(str(params.get(k)) for k in keys if k in _RELEVANT_PARAM_KEYS)
    return (sym, fam, str(tf), str(sess), str(reg), keys, vals)


def scorer(doc: Mapping[str, Any] | None = None) -> Scorer | None:
    d = doc
    if d is None:
        d, _why = load()
    return Scorer(d) if isinstance(d, Mapping) and d.get("status") == MEASURED else None


def credit_for(symbol: str, family: str, params: Mapping[str, Any] | None = None, *,
               timeframe: Any = None, session: Any = None, sc: Scorer | None = None) -> float:
    """novelty credit for one rule on one instrument; 1.0 (par) when the map is UNMEASURED."""
    s = sc if sc is not None else _default_scorer()
    if s is None:
        return 1.0
    return float(s.score_fields(str(symbol).upper(), family, dict(params or {}), timeframe,
                                session, None)["novelty_credit"])


_DEFAULT: list[Scorer | None] = []


def _default_scorer() -> Scorer | None:
    if not _DEFAULT:
        try:
            _DEFAULT.append(scorer())
        except Exception:
            _DEFAULT.append(None)
    return _DEFAULT[0]


# ------------------------------------------------------------------ docket stamping
def stamp(rows: list[dict[str, Any]], doc: Mapping[str, Any] | None = None, *,
          seconds_per_cell: float | None = None,
          debt: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Stamp `_sat` (breadth value), `_satq` (1 = QUALITY channel) and `_dup` (1 = strong
    duplicate in saturated ground) on every row, and return the evidence plus per-producer
    feedback. Never raises, never removes a row; an absent map stamps nothing (par)."""
    d = doc
    why = "supplied"
    if d is None:
        d, why = load()
    if not isinstance(d, Mapping) or d.get("status") != MEASURED:
        return {"status": UNMEASURED, "why": why, "rows": len(rows)}
    sc = Scorer(d)
    # BREADTH-CONSTRAINED MODE (producer law §3): while BREADTH_DEBT.json says ON, a row landing
    # on an empty payer, an empty information source or a low-occupancy mechanism has its
    # breadth value raised by breadth_debt.MODE_BOOST. ORDER ONLY; a stale or absent queue is 1.0.
    try:
        try:
            from research import breadth_debt as _bd
        except ImportError:
            import breadth_debt as _bd  # type: ignore[import-not-found,no-redef]
        debt_doc: Any = dict(debt) if debt is not None else _bd.load()
        boost_for: Any = _bd.boost_for
    except Exception:
        debt_doc, boost_for = None, (lambda _c, _d: 1.0)
    boosted = 0
    cap_below = 0
    cap_terms: Counter[str] = Counter()
    taxed = 0
    tax_sum: Counter[str] = Counter()
    # the duplicate rate each producer was last published at (the tax's rate term)
    prev_rate: dict[str, float] = {}
    fb_prev = _read(FEEDBACK)
    for k, v in ((fb_prev.get("producers") or {}) if isinstance(fb_prev, dict) else {}).items():
        r0 = _num(v.get("duplicate_share")) if isinstance(v, Mapping) else None
        if r0 is not None:
            prev_rate[str(k)] = r0
    # EXPECTED dk_eff AT GENERATION (breadth law 13, producer law 9): each row's P(survivor) x the
    # marginal k_eff of admitting it at its effective coupling to the certified book
    # (rho = 1 - novelty credit). Signed: a duplicate's marginal is negative, which is the point.
    cert_h = d.get("certificates") if isinstance(d.get("certificates"), Mapping) else {}
    n_book, k_book = cert_h.get("n_certificates"), cert_h.get("n_effective_certificates")
    g_yield = d.get("global_survivor_yield")
    try:
        from libs.research.breadth_credit import marginal_k_eff
    except Exception:                                                   # pragma: no cover
        marginal_k_eff = None  # type: ignore[assignment]

    future: list[tuple[Mapping[str, Any], str, float, float]] = []

    def expected_dk(row: Mapping[str, Any], credit: float, src: str = "") -> float | None:
        if marginal_k_eff is None or not isinstance(n_book, (int, float)) \
                or not isinstance(k_book, (int, float)) or n_book <= 0 or k_book <= 0:
            return None
        pre = row.get("premortem") if isinstance(row.get("premortem"), Mapping) else {}
        ps = _num(pre.get("p_survivor"))
        if ps is None:
            ps = _num(g_yield)
        if ps is None:
            return None
        rho = max(0.0, min(1.0, 1.0 - credit))
        try:
            dk = ps * marginal_k_eff(n_book, k_book, rho)
        except ValueError:
            return None
        future.append((row, src, ps, rho))
        return dk

    prod: dict[str, dict[str, Any]] = {}
    exc_count: Counter[str] = Counter()
    by_cluster: Counter[str] = Counter()
    dup = quality = sat = struct_all = 0
    near_all: Counter[str] = Counter()
    credit_sum = 0.0
    for row in rows:
        try:
            s = sc.score_row(row)
        except Exception:
            continue
        if float(s.get("capacity_factor") or 1.0) < 1.0:
            cap_below += 1
        for t, v in (s.get("capacity_terms") or {}).items():
            if v is not None:
                cap_terms[t] += 1
        b = boost_for(s["cluster"], debt_doc) if not s["duplicate"] else 1.0
        if b > 1.0:
            s["breadth_value"] = float(s["breadth_value"]) * b
            boosted += 1
        if s.get("near_duplicate_rule") and s["duplicate"]:
            # THE DUPLICATE TAX (law §3, §22): density, the producer's duplicate rate, the twin
            # cluster's effective trials spent and its survivor-yield decline. Order only.
            tw = sc.clusters.get(str(s.get("nearest_cluster"))) or {}
            src0 = str(row.get("source") or row.get("producer") or "unattributed")
            s["breadth_value"], tax = duplicate_tax(
                float(s["breadth_value"]), local_count=_num(s.get("effective_local_count")),
                duplicate_rate=prev_rate.get(src0),
                trials_spent=_num(tw.get("effective_trials_spent")),
                yield_ratio=_num(tw.get("yield_ratio")))
            for k, v in tax.items():
                tax_sum[k] += v
            taxed += 1
        row["_sat"] = s["breadth_value"]
        row["_satq"] = 1 if s["channel"] == "QUALITY" else 0
        row["_dup"] = 1 if s["duplicate"] else 0
        if s["channel"] == "QUALITY" and s.get("challenges_archived"):
            row["_satq_arch"] = 1
        dup += row["_dup"]
        quality += row["_satq"]
        sat += 1 if s["saturated_ground"] else 0
        credit_sum += float(s["breadth_value"])
        for e in s["exceptions"]:
            exc_count[e] += 1
        by_cluster[s["cluster"]] += 1
        src = str(row.get("source") or row.get("producer") or "unattributed")
        p = prod.setdefault(src, {"rows": 0, "duplicates": 0, "saturated_ground": 0,
                                  "quality": 0, "credit_sum": 0.0, "clusters": Counter(),
                                  "dup_groups": set(), "new_clusters": set(),
                                  "method": method_of(src), "exp_dk": 0.0, "exp_n": 0,
                                  "near": Counter(), "struct": 0})
        p["rows"] += 1
        p["duplicates"] += row["_dup"]
        p["saturated_ground"] += 1 if s["saturated_ground"] else 0
        p["quality"] += row["_satq"]
        p["credit_sum"] += float(s["breadth_value"])
        edk = expected_dk(row, min(float(s["novelty_credit"]), float(s["breadth_value"])), src)
        if edk is not None:
            p["exp_dk"] += edk
            p["exp_n"] += 1
        p["clusters"][s["cluster"]] += 1
        if s.get("near_duplicate_rule"):
            p["near"][s["near_duplicate_rule"]] += 1
            near_all[s["near_duplicate_rule"]] += 1
        if s.get("structural_duplicate"):
            p["struct"] += 1
            struct_all += 1
        if s["duplicate"]:
            p["dup_groups"].add(s["nearest_cluster"])
        if s["cluster"] not in sc.clusters:
            p["new_clusters"].add(s["cluster"])
    # MARGINAL BREADTH AGAINST THE PROJECTED FUTURE BOOK (producer law §11, BREADTH-0278). The
    # future book is today's certified book plus every docket row's expected survivors: n grows
    # by sum(P(survivor)) and k_eff by the sum of their positive expected marginals. Each row's
    # marginal is then re-read against that book, so a row that only looks new because a dozen
    # rows like it are queued is priced as what it will be when they land. Facts per producer.
    fut = {"status": UNMEASURED, "why": "no row carried a P(survivor) and a measured book"}
    if future and isinstance(n_book, (int, float)) and isinstance(k_book, (int, float)) \
            and marginal_k_eff is not None:
        n_f = float(n_book) + sum(ps for _, _, ps, _ in future)
        k_f = float(k_book)
        for _, _, ps, rho in future:
            try:
                k_f += max(0.0, ps * marginal_k_eff(n_book, k_book, rho))
            except ValueError:
                continue
        tot_f = 0.0
        for _row, src, ps, rho in future:
            try:
                dkf = ps * marginal_k_eff(n_f, max(k_f, 1e-9), rho)
            except ValueError:
                continue
            tot_f += dkf
            pp = prod.get(src)
            if pp is not None:
                pp["exp_dk_future"] = pp.get("exp_dk_future", 0.0) + dkf
        fut = {"status": MEASURED, "n_book": n_book, "k_eff_book": k_book,
               "n_future": round(n_f, 3), "k_eff_future": round(k_f, 4),
               "rows": len(future), "expected_delta_k_eff_future": round(tot_f, 6),
               "rule": ("future book = certified book + the docket's expected survivors "
                        "(n + sum P, k_eff + sum of positive expected marginals)")}
    n = len(rows)
    spc = float(seconds_per_cell or 0.0)
    producers: dict[str, Any] = {}
    for src, p in sorted(prod.items(), key=lambda kv: -kv[1]["rows"]):
        share = p["duplicates"] / p["rows"] if p["rows"] else 0.0
        hours = p["rows"] * spc / 3600.0 if spc else None
        producers[src] = {
            "rows": p["rows"], "method": p["method"],
            "duplicate_candidates": p["duplicates"], "duplicate_share": round(share, 4),
            "duplicate_effective_trials": len(p["dup_groups"]),
            "duplicate_compute_hours": (round(p["duplicates"] * spc / 3600.0, 4)
                                        if spc else None),
            "duplicate_survivor_share": None, "duplicate_survivor_status": UNMEASURED,
            "saturated_ground_share": round(p["saturated_ground"] / p["rows"], 4),
            "quality_rows": p["quality"],
            "mean_novelty_credit": round(p["credit_sum"] / p["rows"], 4),
            "provisional_breadth_credit": round(len(p["new_clusters"]) * 1.0
                                                + p["credit_sum"] / max(p["rows"], 1), 4),
            "new_structural_clusters": len(p["new_clusters"]),
            "expected_delta_k_eff": (round(p["exp_dk"], 6) if p["exp_n"] else None),
            "expected_delta_k_eff_rows": p["exp_n"],
            "expected_delta_k_eff_future_book": (round(p["exp_dk_future"], 6)
                                                 if "exp_dk_future" in p else None),
            "judge_compute_hours": round(hours, 6) if hours else None,
            # per JUDGE hour here; research_auction adds the producer's own generation hours
            "delta_k_eff_per_compute_hour": (round(p["exp_dk"] / hours, 6)
                                             if hours and p["exp_n"] else None),
            "quality_per_compute_hour": None,
            "quality_status": ("UNMEASURED: the quality channel is paid in realised edge, which "
                               "needs execution.matched_fills > 0"),
            "top_clusters": dict(p["clusters"].most_common(5)),
            "near_duplicates_by_rule": dict(p["near"].most_common()),
            "structural_duplicates": p["struct"],
            "state": ("RETARGET" if (p["rows"] >= RETARGET_MIN_ROWS
                                     and share >= RETARGET_SHARE) else "OK"),
        }
    return {"status": MEASURED, "rows": n, "strong_duplicates": dup, "quality_rows": quality,
            "saturated_ground_rows": sat,
            "mean_breadth_value": round(credit_sum / n, 6) if n else None,
            "exceptions": dict(exc_count), "rows_by_cluster_top": dict(by_cluster.most_common(20)),
            "near_duplicates_by_rule": dict(near_all.most_common()),
            "structural_duplicates": struct_all,
            "breadth_constrained_mode": (debt_doc or {}).get("breadth_constrained_mode",
                                                             UNMEASURED),
            "mode_boosted_rows": boosted,
            "future_book": fut,
            "capacity": {"rows_below_par": cap_below,
                         "terms_measured": dict(cap_terms),
                         "rule": "breadth value x product of six capacity terms (floor 0.25)"},
            "duplicate_tax": {"rows_taxed": taxed,
                              "mean_factor": {k: round(v / taxed, 6) for k, v in tax_sum.items()}
                              if taxed else {},
                              "terms": "density x rate x trials x yield (breadth law §22)"},
            "map_at": d.get("at"), "certificates": d.get("certificates"),
            "producers": producers,
            "rule": ("_sat = novelty credit (exception floor where A-F/H holds); _dup = in "
                     "saturated ground with no exception -> tail of its family stream; _satq = "
                     "QUALITY channel, served at its own protected share. Reorder only")}


def duplicate_tax(value: float, *, local_count: float | None = None,
                  duplicate_rate: float | None = None, trials_spent: float | None = None,
                  yield_ratio: float | None = None) -> tuple[float, dict[str, float]]:
    """A near-duplicate's taxed breadth value and the factor each §22 term applied.

    density      the novelty credit at the effective local count, never above one twin's
    rate         1 - rate/2 for the producer's last published duplicate share
    trials       1/sqrt(1 + spent/DUPLICATE_TAX_TRIALS_SCALE) for the twin cluster's trials
    yield        min(1, yield ratio) where the cluster's survivor yield has fallen below the desk's

    An unmeasured term is 1.0 (it neither taxes nor credits). ORDER ONLY: the result is floored
    at DUPLICATE_TAX_FLOOR and moves a row down its family stream; it never removes a row, never
    touches a trial charge, a gate, a verdict, capital or sizing."""
    f: dict[str, float] = {}
    f["density"] = min(DUPLICATE_TAX_CREDIT, novelty_credit(max(1.0, float(local_count or 1.0))))
    r = _num(duplicate_rate)
    f["rate"] = 1.0 - 0.5 * max(0.0, min(1.0, r)) if r is not None else 1.0
    t = _num(trials_spent)
    f["trials"] = 1.0 / math.sqrt(1.0 + max(0.0, t) / DUPLICATE_TAX_TRIALS_SCALE) \
        if t is not None else 1.0
    y = _num(yield_ratio)
    f["yield"] = max(0.0, min(1.0, y)) if y is not None else 1.0
    taxed = float(value)
    taxed = min(taxed, f["density"]) * f["rate"] * f["trials"] * f["yield"]
    return max(DUPLICATE_TAX_FLOOR, taxed), {k: round(v, 6) for k, v in f.items()}


def family_factor(rows: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """1 + mean breadth value of a family's stamped rows: in (1, 2], the EFFECTIVE-density
    replacement for the nominal `2 - certified_share` family term. Absent when unstamped."""
    tot: dict[str, float] = defaultdict(float)
    n: Counter[str] = Counter()
    for r in rows:
        v = r.get("_sat")
        if v is None:
            continue
        f = str(r.get("family") or "")
        tot[f] += float(v)
        n[f] += 1
    return {f: 1.0 + tot[f] / n[f] for f in n if n[f]}


def write_feedback(evidence: Mapping[str, Any], *, path: Path | None = None,
                   now: datetime | None = None) -> Path | None:
    """Publish per-producer feedback (producer law 8, 9, 21, 26). RETARGET persists across
    readings; a producer RETARGETed for RETARGET_PATIENCE consecutive readings whose duplicate
    share did not fall is named PARK_CANDIDATE -- published, never acted on here."""
    if evidence.get("status") != MEASURED:
        return None
    p = path or FEEDBACK
    prev = _read(p)
    prev_p = (prev or {}).get("producers") if isinstance(prev, dict) else None
    prev_p = prev_p if isinstance(prev_p, dict) else {}
    doc_map, _ = load()
    debts = [d["missing_cluster"] for d in ((doc_map or {}).get("breadth_debts") or [])[:5]]
    producers = {}
    for src, row in (evidence.get("producers") or {}).items():
        r = dict(row)
        old = prev_p.get(src) if isinstance(prev_p.get(src), dict) else {}
        streak = int(old.get("retarget_streak") or 0) + 1 if r["state"] == "RETARGET" else 0
        first_share = old.get("retarget_first_share") if streak > 1 else r["duplicate_share"]
        r["retarget_streak"] = streak
        r["retarget_first_share"] = first_share
        if streak >= RETARGET_PATIENCE and first_share is not None \
                and r["duplicate_share"] >= float(first_share):
            r["state"] = "PARK_CANDIDATE"
        sv = _survivor_share_for(src, (doc_map or {}).get("duplicate_survivors"))
        if sv is not None:
            r["duplicate_survivor_share"] = sv
            r["duplicate_survivor_status"] = MEASURED
        allowed = math.ceil(DUPLICATE_BUDGET_SHARE * max(int(r.get("rows") or 0), 1))
        r["duplicate_budget"] = {
            "max_duplicate_share": DUPLICATE_BUDGET_SHARE,
            "next_generation_max_duplicates": allowed,
            "this_generation_duplicates": int(r.get("duplicate_candidates") or 0),
            "over_budget": float(r.get("duplicate_share") or 0.0) > DUPLICATE_BUDGET_SHARE,
            "near_duplicates_by_rule": r.get("near_duplicates_by_rule") or {},
            "avoid_clusters": list((r.get("top_clusters") or {}).keys())[:5],
            "rule": ("read before the next generation: keep near-duplicates of the certified "
                     "book at or under this share; over it, duplicates are taxed to the tail and "
                     "the producer is retargeted to the breadth debts. Nothing is dropped and "
                     "every judged row is charged its trial"),
        }
        if r["state"] != "OK":
            r["instruction"] = ("stop producing near-duplicates of the clusters below; the desk "
                                "already owns them. Retarget to the breadth debts named, or "
                                "declare the work a QUALITY challenger (breadth_exception: G)")
            r["retarget_to"] = debts
            r["saturated_clusters_hit"] = r.get("top_clusters")
        producers[src] = r
    methods: Counter[str] = Counter()
    for r in producers.values():
        methods[r["method"]] += int(r["rows"])
    tot = sum(methods.values())
    m_eff = (1.0 / sum((v / tot) ** 2 for v in methods.values())) if tot else None
    total_rows = sum(int(r["rows"]) for r in producers.values())
    total_dup = sum(int(r["duplicate_candidates"]) for r in producers.values())
    out = {"at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
           "status": MEASURED, "map_at": evidence.get("map_at"),
           "certificates": evidence.get("certificates"),
           "duplicate_share": round(total_dup / total_rows, 4) if total_rows else None,
           # the SURVIVOR side of the same question: certified output that bought no new bet
           "duplicate_survivors": (doc_map or {}).get("duplicate_survivors"),
           "method_breadth": {"rows_by_method": dict(methods.most_common()),
                              "effective_methods": round(m_eff, 3) if m_eff else None,
                              "note": ("method breadth is NOT alpha breadth (law 18): it is "
                                       "published separately from the structural clusters")},
           "producers": producers,
           "consumers": ["libs/research/bandit.breadth_credit (duplicate tax per arm)",
                         "scripts/run_deepseek_cycle.py (the seat's cold context)",
                         "research/breadth_ladder.py (exploration temperature)"]}
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    os.replace(tmp, p)
    return p


def _survivor_share_for(src: str, dup_surv: Any) -> float | None:
    """This producer's share of certified output archived behind a saturated cluster's champion
    and challengers, matched on the producer token either way round; None when unmatched."""
    by = (dup_surv or {}).get("by_producer") if isinstance(dup_surv, Mapping) else None
    if not isinstance(by, Mapping) or not src:
        return None
    s = str(src).lower()
    tot = dup = 0
    for k, v in by.items():
        kl = str(k).lower()
        if isinstance(v, Mapping) and kl and (kl in s or s in kl):
            tot += int(v.get("certificates") or 0)
            dup += int(v.get("duplicates") or 0)
    return round(dup / tot, 4) if tot else None


def producer_brief(source_token: str = "", *, doc: Mapping[str, Any] | None = None,
                   feedback: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """FACTS a generator receives before proposing (producer law 1, 5, 26): what the desk owns,
    what is saturated, the breadth debts, and its own recent duplicate record. Facts only --
    counts and names, no ranking opinion -- so it survives a cold-context strip."""
    d = doc
    if d is None:
        d, _ = load(max_age_h=48.0)
    fb = feedback if feedback is not None else _read(FEEDBACK)
    if not isinstance(d, Mapping):
        return {}
    sat = sorted(((k, v) for k, v in (d.get("clusters") or {}).items()
                  if v.get("state") == "SATURATED"),
                 key=lambda kv: -int(kv[1].get("certificate_count") or 0))[:12]
    own = {}
    if isinstance(fb, Mapping) and source_token:
        for src, r in (fb.get("producers") or {}).items():
            if source_token.lower() in str(src).lower() and isinstance(r, Mapping):
                own[src] = {k: r.get(k) for k in ("rows", "duplicate_share", "state",
                                                  "top_clusters", "retarget_to",
                                                  "duplicate_budget",
                                                  "duplicate_survivor_share")}
    return {
        "desk_owns": d.get("certificates"),
        "book_context": _book_context(d),
        "saturated_clusters": [{"cluster": k, "certificates": v.get("certificate_count"),
                                "effective": v.get("effective_certificate_count"),
                                "families": v.get("families"),
                                "effective_trials_spent": v.get("effective_trials_spent"),
                                "incremental_survivor_yield":
                                    v.get("incremental_survivor_yield")} for k, v in sat],
        "open_breadth_debts": [{"cluster": x.get("missing_cluster"),
                                "payer": x.get("economic_rationale"),
                                "producers": x.get("candidate_producers")}
                               for x in (d.get("breadth_debts") or [])[:10]],
        "failure_modes_the_book_holds_most": (d.get("failure_modes") or {}).get("hurts_book"),
        "own_recent_output": own,
        "breadth_constrained_mode": _debt_brief(),
    }


#: Every producer's brief, published once per hourly pass (producer law §1, §5): the hourly
#: launcher hands its path to every producer leg (QUANT_PRODUCER_BRIEF) and the proposer seat
#: puts the brief's lines into every research organ's prompt.
BRIEFS = REPORTS / "PRODUCER_BRIEFS.json"


def publish_briefs(*, doc: Mapping[str, Any] | None = None,
                   feedback: Mapping[str, Any] | None = None,
                   path: Path | None = None) -> Path | None:
    """Write the desk-wide brief and each producer's own record to PRODUCER_BRIEFS.json."""
    desk = producer_brief("", doc=doc, feedback=feedback)
    if not desk:
        return None
    fb = feedback if feedback is not None else _read(FEEDBACK)
    own: dict[str, Any] = {}
    for src, r in ((fb or {}).get("producers") or {}).items() if isinstance(fb, Mapping) else []:
        if isinstance(r, Mapping):
            own[str(src)] = {k: r.get(k) for k in ("rows", "duplicate_share", "state",
                                                   "top_clusters", "retarget_to",
                                                   "duplicate_budget",
                                                   "duplicate_survivor_share")}
    out = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "desk": {k: v for k, v in desk.items() if k != "own_recent_output"},
           "producers": own,
           "rule": "facts only: counts and names, no ranking and no instruction"}
    p = path or BRIEFS
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def brief_for(name: str, *, path: Path | None = None, max_age_h: float = 6.0,
              now: datetime | None = None) -> dict[str, Any]:
    """The published brief for producer `name`: the desk facts plus its own record. {} when the
    file is absent or older than `max_age_h` (a stale brief is not live context)."""
    d = _read(path or BRIEFS)
    if not isinstance(d, dict):
        return {}
    try:
        at = datetime.fromisoformat(str(d.get("at")))
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
    except ValueError:
        return {}
    if ((now or datetime.now(tz=UTC)) - at).total_seconds() / 3600.0 > max_age_h:
        return {}
    tok = str(name or "").lower()
    own = {k: v for k, v in (d.get("producers") or {}).items()
           if tok and (tok in str(k).lower() or str(k).lower() in tok)}
    return {**(d.get("desk") or {}), "own_recent_output": own, "brief_at": d.get("at")}


def brief_lines(name: str, *, limit: int = 12, path: Path | None = None) -> list[str]:
    """The brief as short public-fact lines for a model prompt (proposer seat context)."""
    b = brief_for(name, path=path)
    if not b:
        return []
    out: list[str] = []
    own_desk = b.get("desk_owns") if isinstance(b.get("desk_owns"), Mapping) else {}
    if own_desk:
        out.append(f"desk holds {own_desk.get('n_certificates')} certificates = "
                   f"{own_desk.get('n_effective_certificates')} effective bets")
    sat = [c.get("cluster") for c in (b.get("saturated_clusters") or [])[:4]]
    if sat:
        out.append("saturated (avoid near-duplicates): " + "; ".join(map(str, sat)))
    debts = [x.get("cluster") for x in (b.get("open_breadth_debts") or [])[:4]]
    if debts:
        out.append("open breadth debts (mechanism/info/class): " + "; ".join(map(str, debts)))
    mode = b.get("breadth_constrained_mode") if isinstance(b.get("breadth_constrained_mode"),
                                                           Mapping) else {}
    if mode:
        out.append(f"breadth-constrained mode {mode.get('mode')}; empty clusters: "
                   + ", ".join(map(str, (mode.get("empty_clusters") or [])[:8])))
    ctx = b.get("book_context") if isinstance(b.get("book_context"), Mapping) else {}
    for key, label in (("information_source_clusters", "information sources held"),
                       ("factor_exposures", "factor exposures held"),
                       ("temporal_session_clusters", "session clocks held")):
        rows = ctx.get(key) if isinstance(ctx.get(key), list) else []
        if rows:
            out.append(f"{label}: " + ", ".join(
                f"{next(iter(r.values()))}={r.get('certificates')}" for r in rows[:5]
                if isinstance(r, Mapping)))
    hurts = b.get("failure_modes_the_book_holds_most")
    if hurts:
        out.append("the book fails most on: " + ", ".join(map(str, hurts)))
    for src, r in list((b.get("own_recent_output") or {}).items())[:2]:
        if isinstance(r, Mapping):
            out.append(f"your recent output ({src}): {r.get('rows')} rows, duplicate share "
                       f"{r.get('duplicate_share')}, state {r.get('state')}")
    return [line[:240] for line in out[:limit]]


def _book_context(d: Mapping[str, Any], top: int = 12) -> dict[str, Any]:
    """The book a producer is adding to, by every cluster level it can aim at (producer law 1):
    certificates held per information source (L2), economic factor (L4), session/chart/horizon
    clock (L5) and realised-return cluster (L6), the desk's recent survivor yield, and the
    effective trials already spent across the map. A level the map cannot read is UNMEASURED."""
    clusters = d.get("clusters") if isinstance(d.get("clusters"), Mapping) else {}
    by: dict[str, Counter[str]] = {lv: Counter() for lv in ("L1", "L2", "L4", "L5", "L6")}
    trials = 0.0
    trials_seen = False
    fwd = live = 0
    for v in (clusters or {}).values():
        if not isinstance(v, Mapping):
            continue
        h = v.get("hierarchy") if isinstance(v.get("hierarchy"), Mapping) else {}
        n = int(v.get("certificate_count") or 0)
        fwd += int(v.get("forward_count") or 0)
        live += int(v.get("live_count") or 0)
        for lv in by:
            by[lv][str((h or {}).get(lv) or UNKNOWN)] += n
        t = v.get("effective_trials_spent")
        if isinstance(t, (int, float)) and not isinstance(t, bool):
            trials += float(t)
            trials_seen = True
    l6 = by["L6"]
    realised: Any = ([{"cluster": k, "certificates": c} for k, c in l6.most_common(top)]
                     if set(l6) - {UNMEASURED, UNKNOWN} else UNMEASURED)
    return {
        "forward_sleeves": fwd,
        "promoted_live_sleeves": live,
        "economic_mechanism_clusters": [{"mechanism": k, "certificates": c}
                                        for k, c in by["L1"].most_common(top)],
        "information_source_clusters": [{"cluster": k, "certificates": c}
                                        for k, c in by["L2"].most_common(top)],
        "factor_exposures": [{"factor": k, "certificates": c}
                             for k, c in by["L4"].most_common(top)],
        "temporal_session_clusters": [{"clock": k, "certificates": c}
                                      for k, c in by["L5"].most_common(top)],
        "realised_return_clusters": realised,
        "recent_survivor_yield": d.get("global_survivor_yield", UNMEASURED),
        "effective_trials_spent": round(trials, 3) if trials_seen else UNMEASURED,
        "stress_k_eff_book": (d.get("certificates") or {}).get("stress_k_eff_book")
        if isinstance(d.get("certificates"), Mapping) else None,
        "tail_k_eff_book": (d.get("certificates") or {}).get("tail_k_eff_book")
        if isinstance(d.get("certificates"), Mapping) else None,
    }


def _debt_brief() -> dict[str, Any]:
    """The mode flag and the priority targets every producer reads (BREADTH_DEBT.json)."""
    try:
        try:
            from research import breadth_debt as bd
        except ImportError:
            import breadth_debt as bd  # type: ignore[import-not-found,no-redef]
        d = bd.load()
    except Exception:
        d = {}
    if not d:
        return {"mode": UNMEASURED, "why": "BREADTH_DEBT.json absent or stale"}
    return {"mode": d.get("breadth_constrained_mode"),
            "fired": (d.get("mode") or {}).get("fired"),
            "priority_targets": d.get("priority_targets"),
            "empty_clusters": [e.get("cluster") for e in d.get("empty_clusters") or []]}


__all__ = [
    "AXES",
    "FEEDBACK",
    "MATERIAL_FALL",
    "REPORT",
    "Scorer",
    "axes_of",
    "book_breadth",
    "build",
    "cluster_key",
    "coupling",
    "coupling_table",
    "credit_for",
    "factor_of",
    "family_factor",
    "forward_dependence",
    "hierarchy",
    "load",
    "novelty_credit",
    "producer_brief",
    "publish",
    "scorer",
    "similarity",
    "stamp",
    "write_feedback",
]
