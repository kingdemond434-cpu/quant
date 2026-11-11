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
import operator
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

#: Every key a transformation miner writes into `params` to name a variant rather than tune a
#: family. Keys a family accepts natively stay in its call; this set only says which unknown keys
#: are variants (and therefore ours to apply or refuse) instead of plain signature errors.
MODIFIER_KEYS = frozenset({
    "regime", "side_mode", "entry_timing", "execution_style", "entry_style", "representation",
    "cost_aware", "residual", "residual_tag", "conditioner", "macro_axis", "macro_state",
    "publication_lag_d", "transform", "selector",
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

#: RISK-ON / RISK-OFF, DEFINED ONCE (2026-11-11). Until now `risk_on`/`risk_off` were refused as
#: "no desk definition", and the NOT_RUN census of 2026-11-11 counted 98,000 cells (50.7k / 47.1k)
#: stopped on exactly that. The definition is the desk's own RISK role
#: (`economic_drivers.ROLES["RISK"]`: US500, then NAS100, then AUS200 -- the first whose H1 bars
#: are on this box): RISK-ON while that index's trailing RISK_LOOKBACK_BARS log return is above
#: zero, RISK-OFF while it is below. Point in time: the state at a bar is read from index bars
#: that CLOSED by that bar's open (shifted one bar), carried forward at most RISK_STALE_H so a
#: dead index feed reads as "no state", never as an old one. The two states partition every bar
#: that has a state, so both children of a parent are measured, never just the convenient one.
RISK_REGIMES = {"risk_on": 1, "risk_off": -1}
RISK_LOOKBACK_BARS = 120          # ~one trading week of H1 bars
RISK_STALE_H = 72.0               # covers a weekend; a feed older than this has no state

SIDE_MODES = frozenset({"", "follow", "revert", "long", "short"})

#: THE ONE CONDITIONER FORM THAT IS APPLIED, NOT REFUSED (2026-09-30). A second information axis
#: is measurable only when a point-in-time series stands behind it. `research/alt_proxies.py`
#: writes such series under `data/lake/series/<file>.csv` in the lake's PIT envelope and names
#: them `alt:<file>:<column>:<op>:<threshold>`. The series is read through
#: `family_exogenous_conditioner.conditioner` -- the same loader, the same `available_time` join
#: and the same publication-day lag that family already uses -- forward-filled onto the bars, and
#: a signal survives only where the condition held AT ITS OWN BAR. Every other conditioner value
#: ("carry", "macro", "positioning") has no series behind it and is refused exactly as before.
ALT_CONDITIONER_PREFIX = "alt:"
ALT_OPS: dict[str, Callable[[Any, Any], Any]] = {
    "gt": operator.gt, "ge": operator.ge, "lt": operator.lt, "le": operator.le}
_ALT_CACHE: dict[tuple[str, str, float], Any] = {}


def alt_conditioner(value: Any) -> tuple[str, str, str, float] | None:
    """`alt:<file>:<column>:<op>:<threshold>` -> (file, column, op, threshold), else None."""
    text = str(value if value is not None else "").strip()
    if not text.startswith(ALT_CONDITIONER_PREFIX):
        return None
    parts = text[len(ALT_CONDITIONER_PREFIX):].split(":")
    if len(parts) != 4 or not parts[0] or not parts[1] or parts[2] not in ALT_OPS:
        return None
    if any(c in parts[0] for c in ("/", "\\", "..")):
        return None
    try:
        thr = float(parts[3])
    except ValueError:
        return None
    return parts[0], parts[1], parts[2], thr


def _alt_series(file: str, column: str, root: Path | None = None) -> Any:
    """The PIT conditioning series (lagged, on its availability clock), or None when absent."""
    from mt5desk.family_exogenous_conditioner import SERIES_DIR, conditioner, series_path

    path = series_path(file, root)
    if path is None:
        return None
    key = (f"{root or SERIES_DIR}/{file}", column, path.stat().st_mtime)
    if key not in _ALT_CACHE:
        if len(_ALT_CACHE) > 64:
            _ALT_CACHE.clear()
        _ALT_CACHE[key] = conditioner(file, column, "raw", root=root)
    return _ALT_CACHE[key]
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
        spec = alt_conditioner(mods["conditioner"])
        if spec is None:
            return (f"conditioner={mods['conditioner']!r}: no conditioning series is wired for a "
                    "second information axis, so the interaction cannot be measured")
        if _alt_series(spec[0], spec[1]) is None:
            return (f"conditioner={mods['conditioner']!r}: the series {spec[0]}.{spec[1]} is not "
                    "on this box (UNMEASURED), so the interaction cannot be measured here")
    if "macro_axis" in mods or "macro_state" in mods:
        return (f"macro condition {mods.get('macro_axis')!r}={mods.get('macro_state')!r}: no "
                "point-in-time macro state series is wired into the replay")
    if "publication_lag_d" in mods or "transform" in mods:
        return "publication-lagged transform: no point-in-time input series is wired for it"
    if "selector" in mods:
        from mt5desk.family_call import SESSIONS

        selector = _s(mods.get("selector"))
        if selector not in SESSIONS:
            return (f"selector={mods.get('selector')!r}: no declared session window; refusing "
                    "rather than running the cell across all hours")
    regime = _s(mods.get("regime"))
    if regime in RISK_REGIMES and _risk_series() is None:
        return (f"regime={mods.get('regime')!r}: no RISK-role index "
                f"({', '.join(_risk_symbols())}) has H1 bars on this box (UNMEASURED)")
    if regime not in NO_OP_REGIMES and regime not in VOL_REGIMES \
            and regime not in CALENDAR_REGIMES and regime not in RISK_REGIMES:
        return (f"regime={mods.get('regime')!r} has no desk definition (volatility, month/"
                "quarter-end and risk-on/off are defined)")
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


def _risk_symbols() -> tuple[str, ...]:
    try:
        from mt5desk.economic_drivers import ROLES
        return tuple(ROLES.get("RISK") or ())
    except ImportError:
        return ("US500", "NAS100", "AUS200")


#: Version of the modifier definitions above. Bumped whenever a regime name that used to be
#: refused gains a definition, so judge_coverage can record the census of newly judgeable cells
#: (and the trial charge they add) as a named cause the pass it lands, not a mystery jump.
DEFINITIONS_VERSION = "2026-11-11.risk_on_off"
NEWLY_DEFINED = {"2026-11-11.risk_on_off": tuple(sorted(RISK_REGIMES))}

#: Per-process memo of the RISK index's PIT sign series. load_peer caches the frame on the
#: parquet's (path, mtime), so the frame OBJECT changes exactly when the file does; the memo
#: holds that object and is reused while load_peer keeps returning it.
_RISK_MEMO: dict[str, object] = {}


def _risk_series() -> tuple[str, pd.Series] | None:
    """(symbol, close) of the first RISK-role index with H1 bars here, else None."""
    from mt5desk.family_learned_propagation import load_peer

    for sym in _risk_symbols():
        df = load_peer(sym)
        if df is not None and len(df) > RISK_LOOKBACK_BARS:
            if _RISK_MEMO.get("frame") is not df:
                _RISK_MEMO.clear()
                _RISK_MEMO.update(frame=df, sym=sym,
                                  close=df["close"].astype(float).sort_index())
            return sym, _RISK_MEMO["close"]  # type: ignore[return-value]
    return None


def _risk_sign(series: pd.Series) -> pd.Series:
    import numpy as np

    s = series[~series.index.duplicated(keep="last")].sort_index()
    # The index bar stamped t closes at t + 1 bar; shifting one bar means the state stamped at t
    # was fully known at t, the open of a target bar stamped t.
    return np.sign(np.log(s).diff(RISK_LOOKBACK_BARS)).shift(1)


def risk_state(bars: pd.DataFrame, series: pd.Series | None = None) -> pd.Series:
    """+1 risk-on, -1 risk-off, 0 no state, on `bars`' own index (see RISK_REGIMES)."""
    if series is None:
        got = _risk_series()
        if got is None:
            return pd.Series(0, index=bars.index, dtype=int)
        if _RISK_MEMO.get("sign_of") is not got[1]:
            _RISK_MEMO.update(sign_of=got[1], sign=_risk_sign(got[1]))
        sign = _RISK_MEMO["sign"]
        sign = sign.copy()  # type: ignore[union-attr]
    else:
        sign = _risk_sign(series)
    tz = getattr(bars.index, "tz", None)
    if tz is None and getattr(sign.index, "tz", None) is not None:
        sign.index = sign.index.tz_convert(None)
    elif tz is not None and getattr(sign.index, "tz", None) is None:
        sign.index = sign.index.tz_localize("UTC").tz_convert(tz)
    known = sign.reindex(bars.index, method="ffill",
                         tolerance=pd.Timedelta(hours=RISK_STALE_H))
    return known.fillna(0).astype(int)


def _regime_mask(bars: pd.DataFrame, regime: str) -> pd.Series:
    from mt5desk.family_generic import _CONTEXTS

    if regime in RISK_REGIMES:
        return risk_state(bars) == RISK_REGIMES[regime]
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
    if regime in VOL_REGIMES or regime in CALENDAR_REGIMES or regime in RISK_REGIMES:
        mask = _regime_mask(bars, regime)
        out = [s for s in out if bool(mask.get(s.time, False))]
    spec = alt_conditioner(mods.get("conditioner")) if "conditioner" in mods else None
    if spec is not None:
        out = _alt_filter(out, bars, spec)
    if "selector" in mods:
        from mt5desk.family_call import session_filter

        out = session_filter(out, mods.get("selector"))
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


def _alt_filter(sigs: list[Any], bars: pd.DataFrame, spec: tuple[str, str, str, float],
                root: Path | None = None) -> list[Any]:
    """Keep a signal only where the PIT series, as last known at its bar, meets the condition.
    A bar before the series' first availability knows nothing and keeps nothing."""
    series = _alt_series(spec[0], spec[1], root)
    if series is None or len(series) == 0:
        return []
    try:
        known = series.reindex(series.index.union(bars.index)).ffill().reindex(bars.index)
    except (TypeError, ValueError):
        return []
    # A NaN (no value known yet) compares False under every operator, so it keeps nothing.
    keep = ALT_OPS[spec[2]](known.astype(float), spec[3]).astype(bool)
    return [s for s in sigs if bool(keep.get(s.time, False))]
