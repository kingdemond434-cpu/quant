"""EVERY CARD IS A RESEARCH TREE, NOT A RESULT (principal 2026-09-17, ledger M5).

THE FINDING THAT ORDERED THIS. The registry holds a handful of alpha cards -- the LIVE and
STANDBY sleeves and the certified cells -- and each one is treated as a terminal object: it was
found, it was judged, it trades or it waits, and nothing is ever asked of it again. That is the
most expensive habit on this desk. A card is a mechanism that SURVIVED ten gates and a forward
clock, which makes it the single best-evidenced starting point the desk owns; the probability
that the one instrument, one chart, one session, one direction and one holding period it happens
to carry is the BEST cell of its mechanism is essentially zero. The desk spends its hours mining
strangers' blog posts for mechanisms with no evidence at all while the mechanisms it has already
paid to prove sit unexplored on eleven axes.

So: every card becomes a tree. Asset transfer, chart transfer, session transfer, regime
conditioning, horizon transfer, residualised form, inverse form, execution variants, exit
variants, cross-asset conditioning and mechanism combination -- each a child cell, each
registered, each judged by the same ten gates as anything else.

THE MULTIPLE-TESTING CHARGE IS WHY THIS IS NOT A SWEEP. Hundreds of children per card would
ordinarily be hundreds of fresh trials against one shared family-wise error budget, and that
budget is the thing `universe_policy` exists to protect -- 61% of one docket's charge went to an
asset class that should never have been on it. Here every child carries `trial_family = <the
card's id>`: one family-wise budget per card, inherited, so a card that spawns 400 children
spends ONE family's worth of multiplicity and the deflated-Sharpe charge divides inside it. A
child that "wins" is a coordinate of its parent's mechanism, never a new discovery, and its
certificate is read that way.

COMPATIBILITY PRUNES; IT IS NEVER THE CARTESIAN PRODUCT. The product of eleven axes is a number
nobody can defend, and most of its cells are economically incoherent rather than merely untested:

  * A SESSION-WINDOW MECHANISM KEEPS ITS SESSIONS AND NEVER TAKES D1. `asia_momentum` on a daily
    bar is not a transfer of the mechanism, it is the deletion of it -- one bar per day cannot
    resolve an eight-hour window. The session axis is where these families are RICH.
  * A MONTH-END / FORCED-FLOW MECHANISM KEEPS CALENDAR VARIANTS AND DROPS SESSIONS. The flow is
    anchored to a DATE, not an hour; moving it to the Asia window asks a question about a
    coordinate the mechanism does not have, and the honest variants are days-before,
    days-after and the flow window itself.
  * RESIDUAL FORM IS FOR LEVEL-BASED FAMILIES ONLY. The residual of a price level to a factor is
    a real object; the residual of an event flag, a calendar date or a funding rate is not, and
    `relative_value_dislocation` families are already residuals -- a residual of a residual is a
    second beta fitted to the same noise.

The table is keyed on `axis_registry.classify_family`'s MECHANISM, which is the desk's own
vocabulary and not a second spelling of it.

AND A KNOB THE FAMILY DOES NOT HAVE IS A REFUSAL, NOT A CELL. `run_external_backtest.
normalize_grid` filters a cell's params to the family's signature, keeping only the declared
identity keys; a `regime="high_vol"` param on a family with no regime knob is DELETED there and
the child then executes identically to its parent while occupying its own registry row. Measured
across the desk's 65 registered families: a regime knob exists on 3, a trail knob on 1. Those
numbers are the measurement and they are reported as named refusals rather than papered over
with cells that cannot run.

    python desks/mt5/research/moat_card_explosion.py [--dry-run] [--max-per-card 40]
                                                     [--budget-s 240]
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402
from research import axis_registry as ar  # noqa: E402

UNIVERSE = DESK / "data" / "universe"
OUT = DESK / "reports" / "MOAT_CARD_EXPLOSION.json"

#: The intake seat. A colon is not a path character on the box that trades and the seat becomes a
#: directory, so the axis rides on each row's own `source` (`card_explosion:<axis>`), never here.
SEAT = "card_explosion"
ORIGIN = "MOAT"

#: The twelve transformation axes. `calendar` is the session axis's replacement for a mechanism
#: anchored to a date rather than an hour -- see the compatibility table.
AXES: tuple[str, ...] = ("asset", "chart", "session", "calendar", "regime", "horizon", "residual",
                         "inverse", "execution", "exit", "cross_asset", "mechanism")

#: Charts the desk keeps bars on, shortest first. M1 and M30 exist on this tree but are not RUNGS
#: of it, and a card off the ladder gets no chart child rather than an invented one.
CHART_LADDER: tuple[str, ...] = ("M5", "M15", "H1", "H4", "D1")
REGIME_TAGS: tuple[str, ...] = ("high_vol", "low_vol")
HOLD_KEYS: tuple[str, ...] = ("ttl_bars", "hold_bars", "max_hold")
#: The horizon transfer: half the card's hold and twice it. Not a sweep -- two neighbours.
HORIZON_MULTIPLES: tuple[float, ...] = (0.5, 2.0)

CARD_RANK: dict[str, int] = {"live": 3, "standby": 2, "forward": 1, "certified": 1}
MAX_PER_CARD = 40
MAX_PER_AXIS = 4
BUDGET_S = 240.0
#: Cards read in one pass. Each costs a registry read and a signature walk; the box holding the
#: live terminal has 8 GB and a dozen resident python processes.
MAX_CARDS = 200

# ------------------------------------------------------------------ THE COMPATIBILITY TABLE
#: Mechanisms whose rule IS an intraday window. They keep the session axis and may never take a
#: chart that cannot resolve a window inside a day.
SESSION_BOUND = frozenset({"session_handover", "session_information_handoff",
                           "hedging_demand_close_flow", "fx_fixing_flow", "breakout_liquidity",
                           "execution_microstructure", "gamma_hedging_state", "inventory_shock"})
#: Mechanisms anchored to a DATE. Session is meaningless for them and calendar variants are the
#: transfer that means something.
CALENDAR_BOUND = frozenset({"calendar_seasonality", "forced_flow"})
#: Mechanisms whose observable is the price LEVEL itself -- the only ones a residual form is
#: defined for.
LEVEL_BASED = frozenset({"trend_persistence", "range_reversion", "breakout_liquidity",
                         "volatility_shock", "regime_transition"})
#: Already cross-asset by construction: conditioning them on a second cross-asset state is the
#: same information twice.
ALREADY_CROSS_ASSET = frozenset({"relative_value_dislocation", "cross_market_lead"})
#: Charts a session-bound mechanism may never take.
INTRADAY_ONLY_BAN = frozenset({"D1"})

#: Available to every mechanism: none of these asks a question the mechanism does not have.
UNIVERSAL_AXES = frozenset({"asset", "chart", "regime", "horizon", "inverse", "execution",
                            "exit", "mechanism"})


def _allowed(mechanism: str) -> frozenset[str]:
    axes = set(UNIVERSAL_AXES)
    axes.add("calendar" if mechanism in CALENDAR_BOUND else "session")
    if mechanism in LEVEL_BASED:
        axes.add("residual")
    if mechanism not in ALREADY_CROSS_ASSET:
        axes.add("cross_asset")
    return frozenset(axes)


#: mechanism -> the axes it keeps. DECLARED, and the report carries it so a reader can see what
#: was pruned without reading this file.
COMPATIBILITY: dict[str, frozenset[str]] = {
    m: _allowed(m) for m in sorted({mech for mech, _i, _s in ar.FAMILY_TABLE.values()}
                                   | SESSION_BOUND | CALENDAR_BOUND | LEVEL_BASED
                                   | ALREADY_CROSS_ASSET | {ar.UNKNOWN})
}

#: Which mechanisms the ontology says INTERACT -- one creates the condition the other trades.
#: Symmetric; anything not named here produces no combination child, which is the point: an
#: ensemble of two unrelated mechanisms is a curve fitted to two noises.
INTERACTS: tuple[tuple[str, str], ...] = (
    ("session_handover", "breakout_liquidity"),
    ("session_handover", "volatility_shock"),
    ("session_information_handoff", "breakout_liquidity"),
    ("calendar_seasonality", "forced_flow"),
    ("forced_flow", "execution_microstructure"),
    ("macro_release", "volatility_shock"),
    ("macro_release", "regime_transition"),
    ("positioning_crowding", "range_reversion"),
    ("positioning_crowding", "volatility_shock"),
    ("carry_rollover", "regime_transition"),
    ("relative_value_dislocation", "cross_market_lead"),
    ("trend_persistence", "regime_transition"),
    ("breakout_liquidity", "execution_microstructure"),
    ("gamma_hedging_state", "hedging_demand_close_flow"),
    ("inventory_shock", "execution_microstructure"),
)

#: THE KNOB AXES, DECLARED. Four transformations are the same move -- set one parameter the
#: family's own signature exposes to a named alternative -- so they share one builder and one
#: table. `axis -> knob -> ((tag, value), ...)`; a family exposing none of an axis's knobs gets a
#: NAMED refusal rather than a cell that `normalize_grid` would strip back into its parent.
DELAYED_BARS = 4
TRAIL_ON = 1.0
KNOB_AXES: dict[str, dict[str, tuple[tuple[str, Any], ...]]] = {
    # A date-anchored mechanism's real variants: how early the flow starts, how long it runs.
    "calendar": {"days_before": (("early", 1), ("late", 3)),
                 "days_after": (("short", 1), ("long", 5)),
                 "window_before_min": (("narrow", 30), ("wide", 120)),
                 "window_after_min": (("narrow", 45), ("wide", 180))},
    # Regime conditioning, per knob whose BODY honours the value -- see REGIME_KNOB_UNSUPPORTED.
    "regime": {"vol_filter": (("high_vol", "high"), ("low_vol", "low")),
               "require_quiet": (("high_vol", False), ("low_vol", True))},
    # Execution variants: how long after the trigger the cell may act.
    "execution": {"wait_bars": (("instant", 0), ("delayed", DELAYED_BARS)),
                  "cooldown_bars": (("instant", 0), ("delayed", DELAYED_BARS))},
    # Exit variants: trail on / trail off, where the family exposes a trail at all.
    "exit": {"trail_k": (("on", TRAIL_ON), ("off", 0.0)),
             "runner_trail_k": (("on", TRAIL_ON), ("off", 0.0))},
}
#: Why each knob axis is worth a trial, in the card's own terms.
KNOB_AXIS_WHY: dict[str, str] = {
    "calendar": "the flow is anchored to a date, and how wide the window around it is set is the "
                "coordinate nobody varied",
    "regime": "the mechanism may only be paid in one volatility state, and an unconditional card "
              "cannot say which",
    "execution": "the card's fill assumption is an untested parameter, and an edge that only "
                 "survives instant execution is a cost artefact",
    "exit": "the exit is half the strategy and the card only ever ran one of them",
}
#: A knob whose value the family's body does not actually branch on. `session_range_breakout` has
#: a `vol_filter` with only a "high" branch, so its low_vol child would be its parent wearing a
#: different param -- refused and counted.
REGIME_KNOB_UNSUPPORTED: dict[tuple[str, str], str] = {
    ("session_range_breakout", "low_vol"): "the family's body has no low-volatility branch",
}
#: Inverse form: the direction knob the family exposes, and what its opposite IS.
DIRECTION_FLIPS: dict[str, dict[Any, Any]] = {
    "side_mode": {"revert": "momentum", "momentum": "revert"},
    "mode": {"continue": "fade", "fade": "continue", "drift": "reversal", "reversal": "drift",
             "pre_flow": "post_flow", "post_flow": "pre_flow"},
}
NEGATED_KNOBS: tuple[str, ...] = ("side_bias", "side")
#: Cross-asset conditioning states and the instruments that carry them, first present wins.
CROSS_ASSET_STATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("usd", ("USDX", "DXY", "USDCHF")),
    ("gold", ("XAUUSD", "XAUEUR")),
    ("equity", ("US500", "SPX500", "NAS100")),
)
#: The family a cross-asset conditioning child is expressed as. It is a REGISTERED family with a
#: resolvable peer, not a param bolted onto a family that cannot read it.
CROSS_ASSET_FAMILY = "correlation_regime"
RESIDUAL_FAMILY = "cross_asset_residual"
COMBINATION_FAMILY = "ensemble"

RULE = ("one card produces hundreds of registered trials, every child inherits its parent's "
        "trial family so the multiple-testing charge stays honest; compatibility prunes, never "
        "the cartesian product")

_REGISTRY: dict[str, Any] | None = None


# ------------------------------------------------------------------ tolerant reading
def _families() -> dict[str, Any]:
    """family -> callable, across both populations. Empty when nothing is importable."""
    global _REGISTRY
    if _REGISTRY is None:
        out: dict[str, Any] = {}
        try:
            from mt5desk import families as fam_mod
            from mt5desk import families_orthogonal as fo
            for name, e in (getattr(fam_mod, "FAMILY_REGISTRY", {}) or {}).items():
                fn = e.get("func") if isinstance(e, dict) else e
                if callable(fn):
                    out[str(name)] = fn
            for name, fn in (getattr(fo, "ORTHOGONAL_FAMILIES", {}) or {}).items():
                if callable(fn):
                    out.setdefault(str(name), fn)
        except Exception:
            out = {}
        _REGISTRY = out
    return _REGISTRY


def knobs(family: str) -> frozenset[str]:
    """The names this family's signature accepts -- the authority on what a child may touch."""
    fn = _families().get(str(family))
    if fn is None:
        return frozenset()
    try:
        names = list(inspect.signature(fn).parameters)[1:]
    except (TypeError, ValueError):
        return frozenset()
    return frozenset(names)


def sessions() -> tuple[str, ...]:
    """The desk's own session table, never a copy of it."""
    try:
        from mt5desk.family_call import SESSIONS
        return tuple(sorted(SESSIONS))
    except Exception:
        return ("all", "asia", "london", "ny")


def has_bars(symbol: str, chart: str) -> bool:
    return (UNIVERSE / f"{symbol}_{chart or 'H1'}.parquet").exists()


def spec(symbol: Any, family: Any, params: dict[str, Any] | None, chart: str,
         session: str) -> dict[str, Any]:
    """The docket's own convention (`breadth_sweep`): `timeframe` written only when it is not H1
    and `session` only when it is not `all`, so a child's id JOINS the graph rather than sitting
    beside it as a second spelling."""
    p = {k: v for k, v in (params or {}).items() if k not in ("timeframe", "session")}
    if chart and chart != "H1":
        p["timeframe"] = chart
    if session and session != "all":
        p["session"] = session
    return {"symbol": str(symbol or "").upper(), "family": str(family or ""), "params": p,
            "chart": chart or "H1", "session": session or "all"}


def _num(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


# ------------------------------------------------------------------ the cards
def collect_cards(conn: Any = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(cards, unmeasured). LIVE first, then STANDBY, then certified cells; retired excluded."""
    unmeasured: list[dict[str, Any]] = []
    try:
        rows = reg.cards(conn=conn)
    except Exception as exc:
        return [], [{"what": "the registry could not be read", "n": 0,
                     "why": f"{type(exc).__name__}: {exc}"}]
    out: list[dict[str, Any]] = []
    retired = crypto = unusable = 0
    wrong_lane: list[str] = []
    for row in rows:
        status = str(row.get("status") or "").lower()
        market = str(row.get("market") or "").upper()
        if status == "retired":
            retired += 1
            continue
        if any(m in market for m in reg.CRYPTO_MARKETS) or str(row.get("name") or "").startswith(
                "crypto::"):
            crypto += 1
            continue
        symbol = str(row.get("symbol") or row.get("market") or "").upper()
        family = str(row.get("family") or "")
        if not symbol or family not in _families():
            unusable += 1
            continue
        # THE TWO-LANE MANDATE AT THE SOURCE. Refusing only the CHILDREN would be worse than
        # useless: the chart, session, horizon, regime, execution and exit axes all keep the
        # card's own symbol, so every one of those children is an equity cell that `donate`
        # turns away at the door -- after the card's whole cap has been spent building them.
        if not ar.may_hypothesise(symbol):
            wrong_lane.append(symbol)
            continue
        try:
            params = json.loads(row.get("params_json") or "{}")
        except (TypeError, ValueError):
            params = {}
        if not isinstance(params, dict):
            params = {}
        chart = ar.normalise_chart(row.get("chart") or params.get("timeframe"))
        session = ar.normalise_session(params.get("session"))
        mech = ar.classify_family(family)[0]
        out.append({"card": str(row.get("id") or ""), "status": status, "symbol": symbol,
                    "family": family, "mechanism": mech,
                    "asset_class": ar.asset_class_of(symbol),
                    "spec": spec(symbol, family, params, chart, session),
                    "rank": CARD_RANK.get(status, 0)})
    if retired:
        unmeasured.append({"what": "retired cards excluded", "n": retired,
                           "why": "a retired card is history; the MT5 universe mandate retires "
                                  "the crypto-exchange era and it is never hunted again"})
    if crypto:
        unmeasured.append({"what": "crypto-exchange cards excluded", "n": crypto,
                           "why": "MT5 universe mandate 2026-08-18"})
    if wrong_lane:
        unmeasured.append({"what": "cards refused by the two-lane mandate", "n": len(wrong_lane),
                           "symbols": sorted(set(wrong_lane)),
                           "why": "single-name equities are traded on news, financial reports "
                                  "and earnings reaction and are never hunted for statistical "
                                  "hypotheses; an unclassified symbol is not a permission "
                                  "either"})
    if unusable:
        unmeasured.append({"what": "cards with no symbol or no registered family", "n": unusable,
                           "why": "a card whose family this tree cannot call spawns nothing; "
                                  "UNMEASURED, not zero"})
    out.sort(key=lambda c: (-int(c["rank"]), str(c["card"])))
    return out[:MAX_CARDS], unmeasured


# ------------------------------------------------------------------ the axes
def _child(card: dict[str, Any], axis: str, s: dict[str, Any], why: str,
           regime: str = "", horizon: str = "") -> dict[str, Any]:
    fields = {"asset_class": card["asset_class"], "mechanism": card["mechanism"],
              "economic_actor": ar.classify_family(s["family"])[2],
              "information": ar.classify_family(s["family"])[1], "chart": s["chart"],
              "session": s["session"], "horizon": horizon or ar.horizon_of(s["chart"], s["params"]),
              "regime": regime or ar.regime_of(s["params"])}
    return {"card": card["card"], "axis": axis, "spec": s, "why": why,
            "trial_family": card["card"], "parent_ids": [card["card"]], "origin": ORIGIN,
            "generator": f"{SEAT}:{axis}", "grid_cell": reg.grid_cell({**fields,
                                                                      "symbol": s["symbol"]}),
            "hash": reg.content_hash(s["family"], s["symbol"], s["params"], s["chart"],
                                     s["session"], str(fields["regime"]), str(fields["horizon"])),
            **fields}


def _hold(params: dict[str, Any]) -> tuple[str, float] | None:
    for key in HOLD_KEYS:
        v = _num(params.get(key))
        if v is not None and v > 0:
            return key, v
    return None


def axis_asset(card: dict[str, Any], note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same asset class, hypothesis lane only, bars on the card's own chart."""
    s = card["spec"]
    pool = ar.instruments_by_class().get(card["asset_class"], [])
    sibs = [x for x in pool if x != s["symbol"] and ar.may_hypothesise(x)
            and has_bars(x, s["chart"])][:MAX_PER_AXIS]
    if not sibs:
        note.append({"what": f"no asset sibling for {card['card']}", "n": 0,
                     "why": f"class {card['asset_class']!r} has no other hypothesis-lane "
                            f"instrument with {s['chart']} bars on this box"})
    return [_child(card, "asset", spec(x, s["family"], s["params"], s["chart"], s["session"]),
                   f"the mechanism is a property of the class, not of {s['symbol']}")
            for x in sibs]


def axis_chart(card: dict[str, Any], note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    s = card["spec"]
    banned = INTRADAY_ONLY_BAN if card["mechanism"] in SESSION_BOUND else frozenset()
    out = []
    for tf in CHART_LADDER:
        if tf == s["chart"] or tf in banned:
            continue
        if not has_bars(s["symbol"], tf):
            continue
        out.append(_child(card, "chart", spec(s["symbol"], s["family"], s["params"], tf,
                                              s["session"]),
                          f"the same rule read at {tf}: a mechanism that only exists at one "
                          f"sampling rate is a property of the sampling"))
    if banned:
        note.append({"what": f"D1 refused for {card['card']}", "n": 1,
                     "why": f"{card['mechanism']} is an intraday-window mechanism; one bar a day "
                            f"cannot resolve the window, so a D1 child would delete the rule "
                            f"rather than transfer it"})
    return out[:MAX_PER_AXIS]


def axis_session(card: dict[str, Any], _note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    s = card["spec"]
    return [_child(card, "session", spec(s["symbol"], s["family"], s["params"], s["chart"], k),
                   f"the same rule fired only in the {k} window: the participants differ by "
                   f"session and so does the constraint they trade under")
            for k in sessions() if k != s["session"]][:MAX_PER_AXIS]


def axis_knob(card: dict[str, Any], axis: str, note: list[dict[str, Any]]
              ) -> list[dict[str, Any]]:
    """One declared parameter move, from `KNOB_AXES[axis]`, on a knob the family really has."""
    s = card["spec"]
    have = knobs(s["family"])
    table = KNOB_AXES[axis]
    out: list[dict[str, Any]] = []
    for knob, variants in table.items():
        if knob not in have:
            continue
        for tag, value in variants:
            if (s["family"], tag) in REGIME_KNOB_UNSUPPORTED:
                note.append({"what": f"{axis} {tag} refused for {s['family']}", "n": 1,
                             "why": REGIME_KNOB_UNSUPPORTED[(s["family"], tag)]})
                continue
            if s["params"].get(knob) == value:
                continue
            out.append(_child(card, axis,
                              spec(s["symbol"], s["family"], {**s["params"], knob: value},
                                   s["chart"], s["session"]),
                              f"{knob}={value!r} ({tag}): {KNOB_AXIS_WHY[axis]}",
                              regime=tag if axis == "regime" else ""))
    if not out:
        note.append({"what": f"no {axis} knob on {s['family']}", "n": 0,
                     "why": f"the signature exposes none of {sorted(table)}; the desk filters a "
                            f"cell's params to the family signature (normalize_grid), so a "
                            f"{axis} param here would be stripped and the child would execute "
                            f"identically to its parent -- UNMEASURED, not covered"})
    return out[:MAX_PER_AXIS]


def axis_horizon(card: dict[str, Any], note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    s = card["spec"]
    held = _hold(s["params"])
    if held is None:
        key = next((k for k in HOLD_KEYS if k in knobs(s["family"])), None)
        if key is None:
            note.append({"what": f"no hold knob on {s['family']}", "n": 0,
                         "why": f"the signature exposes none of {list(HOLD_KEYS)}; the horizon "
                                f"axis is UNMEASURED for this card, not covered"})
            return []
        note.append({"what": f"hold not set on {card['card']}", "n": 0,
                     "why": f"{key} is the family's default and the card never named it; the "
                            f"horizon axis needs a stated hold to move from"})
        return []
    key, cur = held
    out = []
    for mult in HORIZON_MULTIPLES:
        v = round(cur * mult)
        if v < 1 or float(v) == cur:
            continue
        out.append(_child(card, "horizon",
                          spec(s["symbol"], s["family"], {**s["params"], key: v}, s["chart"],
                               s["session"]),
                          f"{key}={v} (x{mult:g}): the card's hold was chosen by a sweep, and the "
                          f"decay of the effect is the thing that was never asked"))
    return out


def axis_residual(card: dict[str, Any], note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The card's level re-expressed against its class factor. Level-based mechanisms only."""
    s = card["spec"]
    if RESIDUAL_FAMILY not in _families():
        note.append({"what": "residual form unavailable", "n": 0,
                     "why": f"{RESIDUAL_FAMILY} is not a registered family on this tree"})
        return []
    pool = [x for x in ar.instruments_by_class().get(card["asset_class"], [])
            if x != s["symbol"] and has_bars(x, s["chart"])]
    if not pool:
        note.append({"what": f"no residual factor for {card['card']}", "n": 0,
                     "why": f"class {card['asset_class']!r} has no priced sibling to residualise "
                            f"{s['symbol']} against"})
        return []
    held = _hold(s["params"])
    params: dict[str, Any] = {"factor_symbols": [pool[0]]}
    if held is not None:
        params["ttl_bars"] = int(held[1])
    return [_child(card, "residual",
                   spec(s["symbol"], s["family"] and RESIDUAL_FAMILY, params, s["chart"],
                        s["session"]),
                   f"the card trades {s['symbol']}'s level; the residual to {pool[0]} strips the "
                   f"class move and asks whether the edge was idiosyncratic all along")]


def axis_inverse(card: dict[str, Any], note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    s = card["spec"]
    have = knobs(s["family"])
    out = []
    for knob, flips in DIRECTION_FLIPS.items():
        cur = s["params"].get(knob)
        if knob in have and cur in flips:
            out.append(_child(card, "inverse",
                              spec(s["symbol"], s["family"], {**s["params"], knob: flips[cur]},
                                   s["chart"], s["session"]),
                              f"{knob}={flips[cur]!r}: if the mechanism is real its opposite must "
                              f"lose, and a card that never tested its own inverse has not shown "
                              f"that"))
    for knob in NEGATED_KNOBS:
        cur = _num(s["params"].get(knob))
        if knob in have and cur is not None and cur != 0:
            out.append(_child(card, "inverse",
                              spec(s["symbol"], s["family"], {**s["params"], knob: -int(cur)},
                                   s["chart"], s["session"]),
                              f"{knob}={-int(cur)}: the inverse of the card's own direction"))
    if not out:
        note.append({"what": f"no direction knob set on {card['card']}", "n": 0,
                     "why": f"neither {sorted(DIRECTION_FLIPS)} nor {list(NEGATED_KNOBS)} is on "
                            f"the card's params with a flippable value"})
    return out[:MAX_PER_AXIS]


def axis_cross_asset(card: dict[str, Any], note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The card's symbol conditioned on USD, gold and equity state, as a resolvable peer cell."""
    s = card["spec"]
    if CROSS_ASSET_FAMILY not in _families():
        note.append({"what": "cross-asset conditioning unavailable", "n": 0,
                     "why": f"{CROSS_ASSET_FAMILY} is not a registered family on this tree"})
        return []
    out = []
    for state, options in CROSS_ASSET_STATES:
        peer = next((p for p in options if p != s["symbol"] and has_bars(p, s["chart"])), None)
        if peer is None:
            note.append({"what": f"no {state} proxy priced at {s['chart']}", "n": 0,
                         "why": f"none of {list(options)} has {s['chart']} bars on this box"})
            continue
        out.append(_child(card, "cross_asset",
                          spec(s["symbol"], CROSS_ASSET_FAMILY, {"peer_symbol": peer}, s["chart"],
                               s["session"]),
                          f"the card fires unconditionally; conditioning it on {state} state "
                          f"({peer}) asks whether the edge is a regime of the macro driver"))
    return out[:MAX_PER_AXIS]


def axis_mechanism(card: dict[str, Any], others: list[dict[str, Any]],
                   note: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine with another card's mechanism -- only where the ontology says the two interact."""
    s = card["spec"]
    if COMBINATION_FAMILY not in _families():
        note.append({"what": "mechanism combination unavailable", "n": 0,
                     "why": f"{COMBINATION_FAMILY} is not a registered family on this tree"})
        return []
    pairs = {frozenset(p) for p in INTERACTS}
    out = []
    for other in others:
        if other["card"] == card["card"]:
            continue
        if frozenset({card["mechanism"], other["mechanism"]}) not in pairs:
            continue
        members = [{"symbol": s["symbol"], "family": s["family"], "params": dict(s["params"])},
                   {"symbol": s["symbol"], "family": other["spec"]["family"],
                    "params": dict(other["spec"]["params"])}]
        held = _hold(s["params"])
        params: dict[str, Any] = {"members": members, "threshold": 0.5}
        if held is not None:
            params["hold_bars"] = int(held[1])
        out.append(_child(card, "mechanism",
                          spec(s["symbol"], COMBINATION_FAMILY, params, s["chart"], s["session"]),
                          f"{card['mechanism']} and {other['mechanism']} interact: one creates "
                          f"the condition the other trades, and neither card has ever been asked "
                          f"about the other"))
    if not out:
        note.append({"what": f"no interacting partner for {card['card']}", "n": 0,
                     "why": f"no other card carries a mechanism the ontology pairs with "
                            f"{card['mechanism']!r}"})
    return out[:MAX_PER_AXIS]


def children_of(card: dict[str, Any], others: list[dict[str, Any]]
                ) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[str]]:
    """(children by axis, unmeasured, axes pruned by the compatibility table)."""
    allowed = COMPATIBILITY.get(card["mechanism"], _allowed(card["mechanism"]))
    note: list[dict[str, Any]] = []
    pruned = [a for a in AXES if a not in allowed]
    builders = {"asset": axis_asset, "chart": axis_chart, "session": axis_session,
                "horizon": axis_horizon, "residual": axis_residual,
                "inverse": axis_inverse, "cross_asset": axis_cross_asset}
    by_axis: dict[str, list[dict[str, Any]]] = {}
    for axis in AXES:
        if axis not in allowed:
            continue
        if axis == "mechanism":
            by_axis[axis] = axis_mechanism(card, others, note)
        elif axis in KNOB_AXES:
            by_axis[axis] = axis_knob(card, axis, note)
        else:
            by_axis[axis] = builders[axis](card, note)
    return by_axis, note, pruned


def pick(by_axis: dict[str, list[dict[str, Any]]], seen: set[str], cap: int
         ) -> tuple[list[dict[str, Any]], int]:
    """Round-robin across axes so one rich axis cannot eat the card's whole cap; content-hash
    dedupe against everything already generated. Returns (kept, collisions)."""
    queues = {a: list(rows) for a, rows in by_axis.items() if rows}
    kept: list[dict[str, Any]] = []
    collisions = 0
    while queues and len(kept) < cap:
        for axis in [a for a in AXES if a in queues]:
            if len(kept) >= cap:
                break
            row = queues[axis].pop(0)
            if not queues[axis]:
                del queues[axis]
            if row["hash"] in seen:
                collisions += 1
                continue
            seen.add(row["hash"])
            kept.append(row)
    collisions += sum(len(q) for q in queues.values())
    return kept, collisions


# ------------------------------------------------------------------ the registry write
def register(card: dict[str, Any], kept: list[dict[str, Any]], possible: int,
             conn: Any = None) -> tuple[str, int]:
    """One DISCOVERY per card, walked EXPANDED -> COMPILED -> QUEUED with its counters, then one
    candidate per child carrying the card as its trial family. Returns (discovery_id, queued)."""
    s = card["spec"]
    did, _created = reg.record_discovery(
        source_id=card["card"], source_type="alpha_card", mechanism=card["mechanism"],
        origin=ORIGIN, generator=SEAT, assets=[s["symbol"]],
        economic_rationale=f"the card {card['card']} survived to {card['status']}; its mechanism "
                           f"is unexplored on the transformation axes",
        exact_rule=json.dumps({"family": s["family"], "params": s["params"]}, sort_keys=True,
                              default=str),
        sessions=[s["session"]], horizons=[ar.horizon_of(s["chart"], s["params"])], conn=conn)
    reg.set_discovery_state(did, "EXPANDED", possible_cells=possible,
                            generated_cells=len(kept), conn=conn)
    reg.set_discovery_state(did, "COMPILED", possible_cells=possible, generated_cells=len(kept),
                            compiled_cells=len(kept), conn=conn)
    queued = 0
    for row in kept:
        c = row["spec"]
        cid, _new = reg.enqueue_candidate(
            family=c["family"], symbol=c["symbol"], params=c["params"], origin=ORIGIN,
            mechanism=card["mechanism"], status="queued", generator=row["generator"],
            source_id=card["card"], discovery_id=did, transformation=row["axis"],
            trial_family=row["trial_family"], parent_ids=row["parent_ids"],
            asset_class=row["asset_class"], chart=c["chart"], session=c["session"],
            horizon=row["horizon"], regime=row["regime"], information=row["information"],
            economic_actor=row["economic_actor"], causal_rationale=row["why"], conn=conn)
        reg.link("card", card["card"], "cell", cid, f"explosion:{row['axis']}", conn=conn)
        row["candidate_id"] = cid
        queued += 1
    reg.set_discovery_state(did, "QUEUED", possible_cells=possible, generated_cells=len(kept),
                            compiled_cells=len(kept), queued_cells=queued, conn=conn)
    return did, queued


def rows_for(kept: list[dict[str, Any]], cards: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Intake rows: EXACT_RECIPE candidates carrying the card that authorised them."""
    from research.proposer_common import candidate
    out = []
    for row in kept:
        s, card = row["spec"], cards[row["card"]]
        r = candidate(f"{SEAT}:{row['axis']}", s["symbol"], s["family"], dict(s["params"]),
                      mechanism=f"{card['mechanism']}: inherited from the {card['status']} card "
                                f"{row['card']}; this child moves ONE axis ({row['axis']}) -- "
                                f"{row['why']}",
                      title=f"{s['symbol']} {s['family']} {s['chart']}/{s['session']} -- "
                            f"{row['axis']} child of {row['card']}",
                      evidence={"card": row["card"], "card_status": card["status"],
                                "card_spec": card["spec"], "axis": row["axis"],
                                "trial_family": row["trial_family"], "why": row["why"],
                                "rule": RULE})
        r.update({"parent": row["card"], "operator": f"card_explosion:{row['axis']}",
                  "trial_family": row["trial_family"], "origin": ORIGIN, "spec_key": s,
                  "lineage": {"card": row["card"], "axis": row["axis"],
                              "card_family": card["family"], "card_status": card["status"]}})
        out.append(r)
    return out


# ------------------------------------------------------------------ build
def build(*, max_per_card: int = MAX_PER_CARD, budget_s: float = BUDGET_S, dry_run: bool = False
          ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(report, children to donate). Never raises on a missing input."""
    t0 = time.monotonic()
    at = datetime.now(tz=UTC).isoformat(timespec="seconds")
    conn = None
    try:
        conn = reg.connect()
    except Exception:
        conn = None
    cards, unmeasured = collect_cards(conn=conn)
    by_axis_tot = {a: {"possible": 0, "generated": 0, "queued": 0, "pruned": 0} for a in AXES}
    by_card: list[dict[str, Any]] = []
    seen: set[str] = set()
    kept_all: list[dict[str, Any]] = []
    possible_tot = deduped = queued_tot = stopped = 0
    for i, card in enumerate(cards):
        if time.monotonic() - t0 > budget_s:
            stopped = len(cards) - i
            break
        seen.add(reg.content_hash(card["spec"]["family"], card["spec"]["symbol"],
                                  card["spec"]["params"], card["spec"]["chart"],
                                  card["spec"]["session"],
                                  str(ar.regime_of(card["spec"]["params"])),
                                  str(ar.horizon_of(card["spec"]["chart"],
                                                    card["spec"]["params"]))))
        axes, note, pruned = children_of(card, cards)
        unmeasured.extend(note)
        for a in pruned:
            by_axis_tot[a]["pruned"] += 1
        possible = sum(len(v) for v in axes.values())
        for a, rows in axes.items():
            by_axis_tot[a]["possible"] += len(rows)
        kept, collisions = pick(axes, seen, max_per_card)
        deduped += collisions
        possible_tot += possible
        for row in kept:
            by_axis_tot[row["axis"]]["generated"] += 1
        queued = 0
        if not dry_run and conn is not None and kept:
            try:
                _did, queued = register(card, kept, possible, conn=conn)
                for row in kept:
                    by_axis_tot[row["axis"]]["queued"] += 1
            except Exception as exc:
                unmeasured.append({"what": f"registry write failed for {card['card']}", "n": 0,
                                   "why": f"{type(exc).__name__}: {exc}"})
        queued_tot += queued
        kept_all.extend(kept)
        by_card.append({"card": card["card"], "status": card["status"],
                        "mechanism": card["mechanism"], "possible": possible,
                        "generated": len(kept), "queued": queued,
                        "pruned_axes": pruned})
    if stopped:
        unmeasured.append({"what": "cards not exploded", "n": stopped,
                           "why": f"the {budget_s:g}s budget ran out after "
                                  f"{len(cards) - stopped} of {len(cards)} cards; UNMEASURED, "
                                  "not covered"})
    if conn is not None:
        try:
            reg.generator_yield_update(SEAT, generated=len(kept_all), conn=conn)
            reg.remember("moat", f"card explosion {at}: {len(cards)} cards -> {len(kept_all)} "
                                 f"children, {queued_tot} queued", kind="generator_run",
                         memory_key=f"{SEAT}:last_run",
                         metrics={"n_cards": len(cards), "n_generated": len(kept_all),
                                  "n_queued": queued_tot, "n_deduped": deduped},
                         payload={"by_axis": by_axis_tot}, conn=conn)
        except Exception:
            pass
        conn.close()
    report = {
        "at": at, "n_cards": len(cards), "n_children_possible": possible_tot,
        "n_generated": len(kept_all), "n_deduped": deduped, "n_queued": queued_tot,
        "by_axis": by_axis_tot,
        "by_card": [{"card": r["card"], "generated": r["generated"], "queued": r["queued"],
                     "status": r["status"], "mechanism": r["mechanism"],
                     "possible": r["possible"], "pruned_axes": r["pruned_axes"]}
                    for r in by_card],
        "compatibility": {m: sorted(a) for m, a in sorted(COMPATIBILITY.items())},
        "max_per_card": max_per_card, "budget_s": budget_s, "budget_stopped": bool(stopped),
        "seconds": round(time.monotonic() - t0, 2),
        "unmeasured": unmeasured, "rule": RULE,
    }
    return report, kept_all


def _write(path: Path, doc: dict[str, Any]) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print; write nothing, donate nothing")
    ap.add_argument("--max-per-card", type=int, default=MAX_PER_CARD,
                    help=f"children one card may queue per run (default {MAX_PER_CARD})")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    a = ap.parse_args(argv)
    rep, kept = build(max_per_card=a.max_per_card, budget_s=a.budget_s, dry_run=a.dry_run)
    if not a.dry_run and kept:
        from research.proposer_common import donate, donation_counts
        cards = {c["card"]: c for c in _card_index(rep, kept)}
        donate(SEAT, rows_for(kept, cards), tests_run=rep["n_cards"])
        rep["donation"] = donation_counts()
        rep["n_donated"] = int(rep["donation"].get("donated") or 0)
    print(f"CARD EXPLOSION {rep['at']}  cards={rep['n_cards']} possible="
          f"{rep['n_children_possible']} generated={rep['n_generated']} "
          f"deduped={rep['n_deduped']} queued={rep['n_queued']} {rep['seconds']}s")
    print("  by axis  " + "  ".join(f"{a}={rep['by_axis'][a]['generated']}/"
                                    f"{rep['by_axis'][a]['possible']}" for a in AXES))
    for r in rep["by_card"][:8]:
        print(f"  {r['status']:<10} {r['card']:<34} {r['mechanism']:<26} "
              f"gen={r['generated']:<3} queued={r['queued']}")
    for u in rep["unmeasured"][:5]:
        print(f"  UNMEASURED {u['what']}: {str(u['why'])[:88]}")
    if a.dry_run:
        print("  --dry-run: nothing written, nothing queued, nothing donated")
        return 0
    _write(OUT, rep)
    print(f"-> {OUT}")
    return 0


def _card_index(_rep: dict[str, Any], kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The cards behind `kept`, re-read once so `rows_for` can name each child's parent."""
    wanted = {r["card"] for r in kept}
    cards, _ = collect_cards()
    return [c for c in cards if c["card"] in wanted]


if __name__ == "__main__":
    raise SystemExit(main())
