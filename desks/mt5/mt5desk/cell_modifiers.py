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
#: RISK REGIMES AND STATE CONDITIONERS THE DESK ALREADY COMPUTES (2026-10-06). These were
#: refused as "no desk definition" while `research/free_shadows.py` publishes, point-in-time,
#: `data/states/free_states.parquet`: `gold_risk_off_z` (z(VIX) + z(HY credit spread), FRED lag
#: applied) and `gold_macro_stress` (the VIX / credit / real-yield / dollar composite). Despite the
#: names both are GLOBAL risk states; `run_hunt10.GATES` already trades `risk_off` as
#: `gold_risk_off_z > 0` and macro stress as `|gold_macro_stress| > 0.5` (its hi and lo gates).
#: These are those definitions, unchanged, with `risk_on` the other side of the same z.
#: A state is used only while FRESH (`STATE_MAX_AGE`): a bar the file does not reach keeps no
#: signal -- an unknown state is not a state.
STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "states" / "free_states.parquet"
STATE_MAX_AGE = pd.Timedelta(days=4)
RISK_REGIMES: dict[str, tuple[str, str, float]] = {
    "risk_off": ("gold_risk_off_z", "gt", 0.0),
    "risk_on": ("gold_risk_off_z", "lt", 0.0),
}
STATE_CONDITIONERS: dict[str, tuple[str, str, float]] = {
    "macro": ("gold_macro_stress", "abs_gt", 0.5),
}
#: Conditioners that ARE a `family_generic._CONTEXTS` mask: the second participant "pressed" is
#: the month-end window for seasonality (the calendar regime this module already applies) and
#: the wide-range (thin book) state for microstructure.
CONTEXT_CONDITIONERS: dict[str, str] = {"seasonality": "month_end",
                                        "microstructure": "low_liquidity"}
_STATE_CACHE: dict[tuple[str, float], Any] = {}


def _states(path: Path | None = None) -> Any:
    p = path or STATE_FILE
    try:
        key = (str(p), p.stat().st_mtime)
    except OSError:
        return None
    if key not in _STATE_CACHE:
        _STATE_CACHE.clear()
        try:
            frame = pd.read_parquet(p)
        except Exception:
            return None
        idx = pd.DatetimeIndex(frame.index)
        frame.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
        _STATE_CACHE[key] = frame.sort_index()
    return _STATE_CACHE[key]


def _state_rule(name: str, op: str, thr: float, sigs: list[Any],
                path: Path | None = None) -> list[Any]:
    """Keep a signal only where the state, as last published at or before its bar (and no older
    than STATE_MAX_AGE), meets the rule."""
    frame = _states(path)
    if frame is None or name not in frame.columns or not sigs:
        return []
    col = frame[name].dropna()
    if col.empty:
        return []
    out = []
    for sig in sigs:
        t = pd.Timestamp(sig.time)
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        i = col.index.searchsorted(t, side="right") - 1
        if i < 0 or t - col.index[i] > STATE_MAX_AGE:
            continue
        v = float(col.iloc[i])
        ok = abs(v) > thr if op == "abs_gt" else ALT_OPS[op](v, thr)
        if ok:
            out.append(sig)
    return out


def _state_refusal(name: str, path: Path | None = None) -> str | None:
    frame = _states(path)
    if frame is None:
        return (f"the state file {(path or STATE_FILE).name} is not on this box (UNMEASURED), so "
                "the state cannot be measured here")
    if name not in frame.columns:
        return f"state {name!r} is absent from {(path or STATE_FILE).name} (UNMEASURED)"
    return None


ENTRY_TIMINGS = frozenset({"", "instant", "delayed"})
MARKET_STYLES = frozenset({"", "market"})
#: A LIMIT VARIANT IS A DECLARED LIMIT ORDER (2026-10-06, audit of #222). The first cut set
#: `trigger` to the signal close and let `mt5desk.engine` INFER limit-vs-stop from the next open:
#: after a gap down a "limit" buy filled as a STOP above the market, and when the next open equals
#: the close (22% of XAUUSD M5 bars, 63% of EURUSD H1) it filled exactly like market. The engine
#: now has `Signal.order_type == "limit"`: a buy rests at the signal bar's close for one bar and
#: fills only if the low reaches it, at min(open, limit) -- never above the limit, never as a stop;
#: sells mirror it. A signal that already rests on its own trigger is a STOP entry by the family's
#: design; it has no limit expression, so the limit variant drops it rather than re-labelling the
#: parent's order as the child's.
LIMIT_STYLES = frozenset({"limit"})


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
    cond = _s(mods.get("conditioner")) if "conditioner" in mods else ""
    if cond in STATE_CONDITIONERS:
        why = _state_refusal(STATE_CONDITIONERS[cond][0])
        if why:
            return f"conditioner={mods['conditioner']!r}: {why}"
    elif cond in CONTEXT_CONDITIONERS:
        pass
    elif "conditioner" in mods:
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
    if regime in RISK_REGIMES:
        why = _state_refusal(RISK_REGIMES[regime][0])
        if why:
            return f"regime={mods.get('regime')!r}: {why}"
    elif regime not in NO_OP_REGIMES and regime not in VOL_REGIMES \
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
        if style not in MARKET_STYLES and style not in LIMIT_STYLES:
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
    elif regime in RISK_REGIMES:
        out = _state_rule(*RISK_REGIMES[regime], out)
    cond = _s(mods.get("conditioner")) if "conditioner" in mods else ""
    if cond in STATE_CONDITIONERS:
        out = _state_rule(*STATE_CONDITIONERS[cond], out)
    elif cond in CONTEXT_CONDITIONERS:
        from mt5desk.family_generic import _CONTEXTS

        cmask = pd.Series(_CONTEXTS[CONTEXT_CONDITIONERS[cond]](bars),
                          index=bars.index).fillna(False).astype(bool)
        out = [s for s in out if bool(cmask.get(s.time, False))]
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
    if any(_s(mods.get(k)) in LIMIT_STYLES for k in ("execution_style", "entry_style")):
        closes = bars["close"]
        rested = []
        for s in out:
            if s.trigger is not None:
                continue
            ref = closes.get(s.time)
            if ref is None or not (float(ref) == float(ref)):
                continue
            rested.append(replace(s, trigger=float(ref), wait_bars=1, order_type="limit"))
        out = rested
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


#: THE RESIDUAL VARIANT'S INPUT, built from the desk's existing causal residual
#: (`mt5desk.causal_residual`, betas fitted strictly before the bar they price). INERT ON THIS
#: TREE: `refusal` still refuses `residual=` because applying it means handing the family
#: different BARS, and the gauntlet's `build_cell` (sealed) loads the bars. The sealed patch
#: `/mnt/project-files/patches/residual_modifier_build_cell.patch` calls this from `build_cell`
#: and `family_call.signals`; until it is applied nothing here runs.
RESIDUAL_FACTOR_SYMBOLS: dict[str, str] = {"usd": "USDX", "gold": "XAUUSD", "equity": "US500"}
RESIDUAL_WINDOW = 240


def residual_frame(bars: pd.DataFrame, factor_bars: pd.DataFrame,
                   win: int = RESIDUAL_WINDOW) -> pd.DataFrame | None:
    """`bars` with the factor's move removed: close follows exp(cumsum(causal residual log
    return)) from the first close, and open/high/low keep their distance from close in RATIO,
    so a family reads the same bar geometry on the residual path. None when the two series do
    not overlap for longer than the beta window."""
    import numpy as np

    from mt5desk.causal_residual import causal_residual

    y = np.log(bars["close"].astype(float)).diff()
    fx = np.log(factor_bars["close"].astype(float)).diff().reindex(bars.index).ffill()
    ok = y.notna() & fx.notna()
    if int(ok.sum()) <= win + 1:
        return None
    eps = pd.Series(np.nan, index=bars.index)
    eps[ok] = causal_residual(y[ok].to_numpy(), fx[ok].to_numpy().reshape(-1, 1), win)
    eps = eps.fillna(0.0)
    eps.iloc[: int(np.argmax(ok.to_numpy())) + win] = 0.0      # no beta yet: no residual move
    close0 = float(bars["close"].iloc[0])
    new_close = close0 * np.exp(eps.cumsum())
    scale = new_close / bars["close"].astype(float)
    out = bars.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = bars[col].astype(float) * scale
    return out


def residual_signals_to_real(sigs: list[Any], bars: pd.DataFrame,
                             rbars: pd.DataFrame) -> list[Any]:
    """Signals decided on the residual path, priced back onto the REAL bars the engine trades:
    every price level is divided by that bar's residual/real scale, so the stop and target keep
    their distance from the entry reference in ratio. A signal off the bar index is dropped."""
    scale = (rbars["close"].astype(float) / bars["close"].astype(float))
    out = []
    for s in sigs:
        k = scale.get(s.time)
        if k is None or not (float(k) > 0):
            continue
        k = float(k)
        out.append(replace(s, stop=float(s.stop) / k, target=float(s.target) / k,
                           trigger=None if s.trigger is None else float(s.trigger) / k))
    return out
