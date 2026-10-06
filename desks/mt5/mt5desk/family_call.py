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
from typing import Any


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
SESSIONS: dict[str, tuple[int, int] | None] = {
    "asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None,
}
#: The fine sessions (2026-10-06), in the same SERVER hours (New York + 7h): the Tokyo fix
#: (09:55 JST is 02:55 winter / 03:55 summer), the London 4pm fix (15:00-17:00 London is 17-19
#: server) and the London/New York overlap (08:00-11:00 New York is 15-18 server). Each sits
#: INSIDE a broad session, so they are kept out of `SESSIONS`: that table is the day's partition,
#: and organs that place one bar in one session (the regime router, the descendant ladder) read
#: it as such. Before this an unknown name filtered nothing, so a cell named for one ran as `all`.
FINE_SESSIONS: dict[str, tuple[int, int]] = {
    "tokyo_fix": (2, 5), "london_fix": (17, 19), "overlap": (15, 18),
}
#: Every window a cell may be NAMED for: the filter, and every organ that names or anchors a cell.
WINDOWS: dict[str, tuple[int, int] | None] = {**SESSIONS, **FINE_SESSIONS}


def session_window(session: Any) -> tuple[int, int] | None:
    """[start, end) server hours for a session name; None for `all`, missing or unknown."""
    key = str(session or "all").strip().lower()
    return WINDOWS.get(key)


def certified_session(sleeve: dict[str, Any]) -> Any:
    """Read the certified session from flat or legacy nested parameter envelopes."""
    raw = sleeve.get("params") or {}
    if not isinstance(raw, dict):
        return None
    inner = raw.get("params")
    params = inner if isinstance(inner, dict) else raw
    return params.get("session")


def session_filter(sigs: list, session: Any) -> list:
    """Only the signals whose bar hour falls inside the session window; every signal when the
    session is `all` or unknown. A signal with no readable time is kept: absence is not a
    reason to drop a trade the family emitted."""
    win = session_window(session)
    if win is None:
        return list(sigs)
    lo, hi = win
    out = []
    for g in sigs:
        t = getattr(g, "time", None)
        h = getattr(t, "hour", None)
        if h is None or lo <= int(h) < hi:
            out.append(g)
    return out


def certified_session_filter(sigs: list, sleeve: dict[str, Any]) -> list:
    """Apply a sleeve's frozen session, including the legacy nested E8 envelope."""
    return session_filter(sigs, certified_session(sleeve))


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
    out = session_filter(out, session)
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
