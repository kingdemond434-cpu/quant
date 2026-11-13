"""How a family constructor is CALLED -- one implementation, so the clock and the gateway agree.

WHY THIS EXISTS

`family_inputs` already answers "what extra inputs does this family need"; this answers the
question immediately after it: "how is the function actually invoked, and with which side". The
two were separate only in the forward engine, where the call shape lived as an inline try/except
inside `shadow_forward`'s replay loop, and the gateway had a second, DIFFERENT shape of its own:

    forward clock   fam_fn(h1, side=-1, **call_params)  for SHORT
                    fam_fn(h1, **call_params)           for LONG      (side omitted entirely)
    gateway         family_fn(closed, side)                           (positional, no params)

Both are correct for what they were calling. The gateway's shape is `run_hunt16.FAMILIES`' own
signature and `qquant_shadow` replays hunt16 cells exactly that way; the forward engine's shape is
`mt5desk.families` / `families_orthogonal`, which take keyword params and a keyword side. The
defect was that the gateway could ONLY make the first call, so `GATEWAY_FAMILY_POPULATIONS` had to
read `("hunt16",)` and 65 of the desk's 66 certificates were unexecutable by construction -- 45
orthogonal, 20 `families`, one hunt16 -- which is why `promotion_ready` read 0 with a full canon.

MEASURED 2026-09-05 against `UNIVERSAL_SURVIVORS.canon.json`:

    population    certificates    executor verdict before this module
    orthogonal              45    executor_gap: population not run by the gateway
    families                20    executor_gap: population not run by the gateway
    hunt16                   1    EXECUTABLE

A SECOND IMPLEMENTATION WAS THE ONE THING NOT TO BUILD. Copying the forward engine's call into
`gateway.py` would create the drift this desk keeps paying for: two ways of invoking the same
constructor, diverging silently, with the difference visible only as a sleeve trading differently
live than the clock that certified it -- and that difference IS the strategy, not a detail. So the
shape lives here, `shadow_forward` calls it, the gateway calls it, and a test asserts the branch
structure is the one the clock has always used.

THE LONG CALL OMITS `side` ON PURPOSE and that asymmetry must not be tidied away. Every clock
running today was started by a call that did not pass `side` for a long cell; passing it -- even
as the correct `side=1` -- would re-enter families whose `side` default is not 1, or whose
signature routes an explicit side differently, and would change running clocks for no reason. A
SHORT passes `side=-1` explicitly on the first call, because the alternative (discovering it via
`TypeError`) cannot tell "this family takes no side" from "something inside it raised TypeError",
and under the second reading it silently re-runs a short certificate long.
"""
from __future__ import annotations

import inspect
import math
from datetime import UTC
from typing import Any


def signal_reference_price(family: str, bars: Any, signal: Any) -> float | None:
    """Preserve the overnight replay's entry-to-level geometry at next-bar open.

    The constructor lays absolute levels from its signal-bar open, but engine
    fills at the following open without moving those levels. The forming bar's
    open is already observed at decision time. Other families retain their
    existing signal-close reference. An invalid replay bracket never gains a
    new reference: the existing close-based stale check still applies.
    """
    try:
        value = float(bars.loc[signal.time, "close"])
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    if family == "overnight_gap_decay":
        try:
            index = int(bars.index.get_loc(signal.time))
            if index + 1 < len(bars):
                replay_entry = float(bars.iloc[index + 1]["open"])
                low, high = sorted((float(signal.stop), float(signal.target)))
                if math.isfinite(replay_entry) and low < replay_entry < high:
                    value = replay_entry
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
    return value if math.isfinite(value) and value > 0 else None


def spread_blocks_entry(signal: Any, side: int, bid: float, ask: float) -> bool:
    """The executable side crossed the target solely through the quoted spread.

    This permits another quote check on the same still-current signal bar. It
    grants no order permission and never retries a quote already beyond the
    original target or stop on both sides.
    """
    try:
        stop, target = float(signal.stop), float(signal.target)
        bid, ask = float(bid), float(ask)
    except (AttributeError, TypeError, ValueError):
        return False
    if not all(math.isfinite(x) for x in (stop, target, bid, ask)) or bid >= ask:
        return False
    if side > 0:
        return stop < bid < target <= ask
    return bid <= target < ask < stop


def accepts_side(fn: Any) -> bool:
    """Can this family function be told which way to trade?

    Asked of the SIGNATURE rather than discovered by catching `TypeError`, for the reason in the
    module docstring: a `TypeError` raised INSIDE a family is indistinguishable from one raised by
    the call, and treating the two the same re-runs a short cell long.

    A `**kwargs` family counts as accepting one -- it will forward `side` to whatever it wraps.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    if "side" in sig.parameters:
        return True
    return any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values())


#: THE SESSION AXIS, GENERIC (principal 2026-09-16: "all sessions maximised fully for true 24/7
#: trading"). A family that takes no session can still be certified INSIDE one: the same rule,
#: fired only on bars whose hour falls in the window. Hours are the SERVER clock, the clock every
#: bar and every gold window on this desk is written in (`decision_core.GOLD_WINDOWS`). The
#: filter lives here, in the one call the gauntlet, the forward clock and the live executor
#: share, so a cell certified in a session is replayed and traded in that session and nowhere
#: else. `session` is an identity key like `timeframe`: it names the cell, it is never an
#: argument the family sees.
#
# THE WINDOWS WERE UTC HOURS READ ON THE SERVER CLOCK (Tier S, 2026-09-30). They used to be
# asia 0-8, london 8-16, ny 14-22 in SERVER hours -- the conventional UTC session hours, applied
# to EET/EEST stamps that run 2-3 h ahead of UTC -- so "london" fired from 05:00 UTC in summer
# and closed three hours before London did. Each session is now the market's own 08:00-16:00 in
# its own local clock (`libs/regime/session_clock.MARKET_SESSIONS`), judged per signal with DST.
# ANCHOR-CLOCKED FAMILIES KEEP THEIR ANCHOR (2026-10-06): a family whose signal is defined by an
# open, close, gap or the rollover (`session_clock.anchor_clocked`) is judged from the prior close
# (server 00:00) through that market's 16:00 local -- a window that holds the old server-hour
# window on every weekday, so no such cell loses a signal it had. The numbers below are those
# windows in SERVER hours in summer, kept for the readers that size coverage off them;
# `session_filter` does not use them.
SESSIONS: dict[str, tuple[int, int] | None] = {
    "asia": (2, 10), "london": (10, 18), "ny": (15, 23), "all": None,
}


def session_window(session: Any) -> tuple[int, int] | None:
    """[start, end) SUMMER server hours for a session name; None for `all`, missing or unknown."""
    key = str(session or "all").strip().lower()
    return SESSIONS.get(key)


def certified_session(sleeve: dict[str, Any]) -> Any:
    """Read the certified session from flat or legacy nested parameter envelopes."""
    raw = sleeve.get("params") or {}
    if not isinstance(raw, dict):
        return None
    inner = raw.get("params")
    params = inner if isinstance(inner, dict) else raw
    return params.get("session")


def _session_clock() -> Any:
    import sys
    from pathlib import Path
    root = str(Path(__file__).resolve().parents[3])
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.regime import session_clock
    return session_clock


def _naive_stamp(t: Any) -> Any:
    """A signal's time with no tzinfo: an aware one converted to UTC first."""
    if getattr(t, "tzinfo", None) is not None and t.utcoffset() is not None:
        return t.astimezone(UTC).replace(tzinfo=None)
    return t


def session_filter(sigs: list[Any], session: Any, family: Any = None,
                   params: dict[str, Any] | None = None) -> list[Any]:
    """Only the signals inside the session; every signal when the session is `all` or unknown.

    The session is the market's own 08:00-16:00 local, or -- for an anchor-clocked family -- the
    prior close through that market's 16:00 (`session_clock.filter_mask`). `family` (and its
    `params`) decide which; without them each signal's own `tag` (the family that emitted it)
    does. A signal with no readable time is kept: absence is not a reason to drop a trade the
    family emitted. The certified-sleeve path (`certified_session_filter`, used by
    shadow_forward, the gateway and E8) reaches this same clock."""
    if session_window(session) is None:
        return list(sigs)
    key = str(session).strip().lower()
    clock = _session_clock()
    timed = [i for i, g in enumerate(sigs) if getattr(getattr(g, "time", None), "hour", None)
             is not None]
    inside: dict[int, bool] = {}
    if timed:
        # Naive stamps only: an aware stamp is read on its UTC wall clock (as `server_to_utc`
        # reads a UTC-labelled index), so a list mixing naive and aware stamps -- which pandas
        # refuses to put in one index -- is judged per stamp, as the hour-reading filter was.
        times = [_naive_stamp(sigs[i].time) for i in timed]
        if family is not None:
            flags = [bool(clock.anchor_clocked(family, params))] * len(timed)
        else:
            flags = [bool(clock.anchor_clocked(getattr(sigs[i], "tag", None))) for i in timed]
        market = clock.filter_mask(times, key, anchored=False)
        anchored = clock.filter_mask(times, key, anchored=True) if any(flags) else market
        inside = {i: bool(a if f else m)
                  for i, m, a, f in zip(timed, market, anchored, flags, strict=True)}
    return [g for i, g in enumerate(sigs) if inside.get(i, True)]


def certified_session_filter(sigs: list, sleeve: dict[str, Any]) -> list:
    """Apply a sleeve's frozen session, including the legacy nested E8 envelope."""
    got = sleeve.get("params")
    raw: dict[str, Any] = got if isinstance(got, dict) else {}
    inner = raw.get("params")
    return session_filter(sigs, certified_session(sleeve), sleeve.get("family"),
                          inner if isinstance(inner, dict) else raw)


def signals(fn: Any, bars: Any, *, side: int, params: dict[str, Any] | None = None) -> list:
    """The family's signals over `bars`, called exactly as the forward clock calls it.

    `side` is the desk's integer convention (+1 long, -1 short). `params` are the call params for
    this cell -- `family_inputs.strip_identity_keys` output updated with `family_inputs.resolve`
    extras -- and an empty dict is the correct answer for a price-only family, not a gap.

    THE BRANCHES ARE THE CLOCK'S OWN, preserved literally: short passes `side=-1` on the first
    attempt, long omits `side` entirely, and a `TypeError` from either falls back to passing side
    explicitly. See the module docstring for why the asymmetry is load-bearing.
    """
    kwargs = dict(params or {})
    session = kwargs.pop("session", None)
    # THE MINERS' VARIANT KEYS ARE APPLIED, NOT PASSED -- the same rule the gauntlet applies in
    # `build_cell`, so a certified cell and its clock trade the same signals. `split` moves only a
    # key the family's signature would have rejected, so every call that works today is unchanged.
    from mt5desk import cell_modifiers
    kwargs, mods = cell_modifiers.split(fn, kwargs)
    refused = cell_modifiers.refusal(mods)
    if refused:
        raise ValueError(f"NOT_RUN_MODIFIER: {refused}")
    short = int(side) < 0
    try:
        out = list(fn(bars, side=-1, **kwargs) if short else fn(bars, **kwargs))
    except TypeError:
        out = list(fn(bars, side=-1 if short else 1, **kwargs))
    # The family's own name decides the clock (anchor or market); a wrapped callable without a
    # `family_*` name falls back to each signal's tag.
    name = str(getattr(fn, "__name__", "") or "")
    out = session_filter(out, session, name if name.startswith("family_") else None, kwargs)
    return cell_modifiers.apply(out, bars, mods) if mods else out


def hunt16_signals(fn: Any, bars: Any, side: int) -> list:
    """The hunt16 call: `FAMILIES[fam](h1, side)`, positional, no params.

    Kept as its own function rather than a flag on `signals` because it is a DIFFERENT contract,
    not a variation of one: hunt16 families take their parameterisation from `WINDOWS[selector]`
    at sweep time and their signature is `(df, side)`. `qquant_shadow` replays them this way, so
    the executor must too, and naming it here is what stops the two shapes being confused at the
    call site.
    """
    return list(fn(bars, side))
