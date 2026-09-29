"""The variant keys a transformation miner puts on a cell, APPLIED -- one implementation.

WHY THIS EXISTS

`research.transformation_miners` mints children by moving one axis of a parent: the regime it is
conditioned on, the side it takes, when and how it enters. Each move is written into the child's
`params` (`regime`, `side_mode`, `entry_timing`, `execution_style`, ...). Nothing downstream ever
implemented them. `external_gauntlet.build_cell` and `family_call.signals` passed them to the
family function as keyword arguments, every family refused the unknown keyword, and the cell died
inside a bare `except` as "parquet missing or build failed".

MEASURED 2026-09-29 on the trading box: 8,939 of the 8,941 fresh cells in one sweep failed that
way and the pre-warm pool built 0. ~8,300 of them failed ONLY on these keys (regime 3,560,
conditioner 3,393, representation 1,905, residual 984, entry_timing/execution_style 671,
side_mode 263). Breadth was frozen at the cached set while the miners kept minting.

THE CONTRACT

`split` takes the keys a family does NOT accept out of its call; `refusal` names every one this
module cannot apply honestly; `apply` applies the rest to the family's signals. The gauntlet
(`build_cell`, which `external_shadow` also replays through) and the forward clock / executor
(`family_call.signals`) both call these three, in the same order after the session filter, so a
cell is judged, clocked and traded on the same signals.

NOTHING THAT RUNS TODAY CHANGES. A key is only moved out of the call when the family neither names
it nor takes `**kwargs`, which is exactly the case that raised TypeError before -- so every call
that currently succeeds is byte-for-byte the call it was.

WHAT IS NOT APPLIED IS REFUSED BY NAME, never approximated. A `risk_on` regime with no desk
definition of risk, a limit fill with no fill model, a second-axis `conditioner` with no series
behind it: each returns a reason, and the cell is recorded NOT_RUN with that reason rather than
built as something other than what it claims to be.
"""
from __future__ import annotations

import inspect
from dataclasses import replace
from typing import Any

import pandas as pd

#: Every key a transformation miner writes into `params` to name a variant rather than tune a
#: family. Keys a family accepts natively stay in its call; this set only says which unknown keys
#: are variants (and therefore ours to apply or refuse) instead of plain signature errors.
MODIFIER_KEYS = frozenset({
    "regime", "side_mode", "entry_timing", "execution_style", "entry_style", "representation",
    "cost_aware", "residual", "residual_tag", "conditioner", "macro_axis", "macro_state",
    "publication_lag_d", "transform",
})

#: Labels: they name the coordinate a cell occupies and change nothing about how it trades.
#: `representation` is the information-type axis the child was filed under (the same value as
#: the spec's `information`); `cost_aware` marks a cost-killed resurrection, whose actual change
#: is carried by its execution keys.
LABEL_KEYS = frozenset({"representation", "cost_aware"})

#: Regimes with a desk definition. The volatility and month-end masks are
#: `family_generic._CONTEXTS`, the definitions the generic family already trades on; quarter-end
#: is that month-end window in a quarter's last month.
VOL_REGIMES = {"high_vol": "high_vol", "high_volatility": "high_vol", "low_vol": "low_vol"}
CALENDAR_REGIMES = frozenset({"month_end", "quarter_end"})
NO_OP_REGIMES = frozenset({"", "unconditional", "all", "any"})

SIDE_MODES = frozenset({"", "follow", "revert", "long", "short"})
ENTRY_TIMINGS = frozenset({"", "instant", "delayed"})
MARKET_STYLES = frozenset({"", "market"})


def _accepts(fn: Any) -> tuple[frozenset[str], bool]:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return frozenset(), True
    varkw = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    return frozenset(params), varkw


def split(fn: Any, params: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """(call kwargs, modifiers). Only keys the family would have rejected are moved."""
    kwargs = dict(params or {})
    names, varkw = _accepts(fn)
    if varkw:
        return kwargs, {}
    mods = {k: kwargs.pop(k) for k in list(kwargs) if k in MODIFIER_KEYS and k not in names}
    return kwargs, mods


def _s(value: Any) -> str:
    return str(value if value is not None else "").strip().lower()


def refusal(mods: dict[str, Any]) -> str | None:
    """The named reason this cell cannot be built as it claims, or None when every key applies."""
    for key in ("residual", "residual_tag"):
        if key in mods:
            return (f"{key}={mods[key]!r}: this family does not residualise its input, and "
                    "building it un-residualised would test the parent under the child's name")
    if "conditioner" in mods:
        return (f"conditioner={mods['conditioner']!r}: no conditioning series is wired for a "
                "second information axis, so the interaction cannot be measured")
    if "macro_axis" in mods or "macro_state" in mods:
        return (f"macro condition {mods.get('macro_axis')!r}={mods.get('macro_state')!r}: no "
                "point-in-time macro state series is wired into the replay")
    if "publication_lag_d" in mods or "transform" in mods:
        return "publication-lagged transform: no point-in-time input series is wired for it"
    regime = _s(mods.get("regime"))
    if regime not in NO_OP_REGIMES and regime not in VOL_REGIMES \
            and regime not in CALENDAR_REGIMES:
        return (f"regime={mods.get('regime')!r} has no desk definition (volatility and month/"
                "quarter-end are defined; a risk-on/off state needs a named risk series first)")
    side = _s(mods.get("side_mode"))
    if side not in SIDE_MODES:
        return f"side_mode={mods.get('side_mode')!r} has no declared meaning"
    timing = _s(mods.get("entry_timing"))
    if timing not in ENTRY_TIMINGS:
        return f"entry_timing={mods.get('entry_timing')!r} has no declared meaning"
    for key in ("execution_style", "entry_style"):
        style = _s(mods.get(key))
        if style not in MARKET_STYLES:
            return (f"{key}={mods.get(key)!r}: the replay fills at the next open; a {style} "
                    "fill needs a queue/fill model this desk does not have yet")
    return None


def _regime_mask(bars: pd.DataFrame, regime: str) -> pd.Series:
    from mt5desk.family_generic import _CONTEXTS

    if regime in VOL_REGIMES:
        mask = _CONTEXTS[VOL_REGIMES[regime]](bars)
    else:
        mask = pd.Series(_CONTEXTS["month_end"](bars), index=bars.index)
        if regime == "quarter_end":
            mask = mask & pd.Series(bars.index.month.isin((3, 6, 9, 12)), index=bars.index)
    return pd.Series(mask, index=bars.index).fillna(False).astype(bool)


def _flip(sig: Any, bars: pd.DataFrame) -> Any:
    """The same trade the other way round: identical entry reference and risk geometry.

    Stop and target are absolute prices, so they are mirrored around the entry reference -- the
    resting trigger when there is one, else the signal bar's close (the engine fills at the next
    open). A long breakout's buy-stop becomes a sell at the same level with the stop the same
    distance beyond it, i.e. the breakout faded.
    """
    if sig.trigger is not None:
        ref = float(sig.trigger)
    else:
        ref = float(bars["close"].get(sig.time, float("nan")))
    if ref != ref:
        return None
    return replace(sig, side=-int(sig.side), stop=2.0 * ref - float(sig.stop),
                   target=2.0 * ref - float(sig.target))


def apply(sigs: list, bars: pd.DataFrame, mods: dict[str, Any]) -> list:
    """Apply the modifiers `refusal` accepted: regime at signal time, then side, then timing."""
    out = list(sigs or [])
    if not mods or not out:
        return out
    regime = _s(mods.get("regime"))
    if regime in VOL_REGIMES or regime in CALENDAR_REGIMES:
        mask = _regime_mask(bars, regime)
        out = [s for s in out if bool(mask.get(s.time, False))]
    side = _s(mods.get("side_mode"))
    if side == "revert":
        out = [f for f in (_flip(s, bars) for s in out) if f is not None]
    elif side == "long":
        out = [s for s in out if int(s.side) > 0]
    elif side == "short":
        out = [s for s in out if int(s.side) < 0]
    if _s(mods.get("entry_timing")) == "delayed":
        # One bar later: the signal moves to the next bar, so the engine fills a bar after it
        # would have. A signal on the last bar has no next bar and is dropped, not kept early.
        pos = {t: i for i, t in enumerate(bars.index)}
        delayed = []
        for s in out:
            i = pos.get(s.time)
            if i is not None and i + 1 < len(bars.index):
                delayed.append(replace(s, time=bars.index[i + 1]))
        out = delayed
    return out
