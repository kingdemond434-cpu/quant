"""Rebuild the runtime inputs a family needs, from the serialisable identity of a cell.

WHY THIS EXISTS

The gauntlet can test a carry sleeve, a cross-asset residual or a COT-positioning cell, because
`build_cell` reconstructs the extra inputs those families need -- swap terms, peer bars, factor
bars, macro and COT series -- from the params stored on the candidate. The FORWARD engine could
not, so it skipped them by name:

    ENROL-GAP: certified {sym}.{fam} cannot enrol here -- needs {x};
               certificate stands, forward evidence is NOT accruing

Measured 2026-08-29: of 615 validity-passing, power-deficient candidates, 344 were blocked that
way -- cross_asset_residual 140, relative_value 73, carry 72, correlation_regime 30, discovered
25, cot_positioning 4. Every one of them fails ONLY on `deflated_sharpe`, a gate the policy marks
curable by forward evidence, and none of them could gather any. The cure was unreachable for more
than half the candidates that needed it, and the reason was wiring rather than research.

That mattered most for carry: it is this desk's only genuinely non-directional mechanism, and the
book's binding constraint is orthogonality (n_eff ~5.5 across 23 certificates). The 72 carry
cells were the most valuable blocked group precisely because they are the least like everything
else.

ONE MAPPING, TWO CONSUMERS. This logic previously existed only inside `external_gauntlet.
build_cell`. Copying it into the forward engine would have created exactly the drift this desk
keeps paying for -- two implementations of the same rule, diverging silently, with the difference
only visible when a sleeve trades differently forward than it was certified. Both callers use
this, and a test asserts the family coverage here matches `FAMILY_INPUTS`.

FAIL CLOSED AND BY NAME. A family whose inputs cannot be rebuilt returns None with a reason, and
the caller SKIPS it loudly. Running a cell with a silently-missing input is worse than not
running it: `family_carry` returns [] without its swap terms, which reads as "this mechanism
never fires" rather than "this desk never gave it what it needs" -- a mistake this desk has
already made once, for the entire life of the carry family.
"""
from __future__ import annotations

from typing import Any

#: Families that need nothing beyond bars are absent here on purpose: `resolve` returning an
#: empty dict for them is the correct answer, not a gap.
_PEER_FAMILIES = frozenset({"relative_value", "correlation_regime"})


def resolve(sym: str, family: str, params: dict[str, Any],
            h1: Any) -> tuple[dict[str, Any] | None, str]:
    """Return (extra kwargs, reason). `None` kwargs means this cell cannot be run here.

    Mirrors `external_gauntlet.build_cell`'s reconstruction exactly, including its rule that a
    params key naming a peer or factor is REPLACED by the loaded frame rather than passed through.
    """
    extra: dict[str, Any] = {}
    call = dict(params or {})
    try:
        from research import orthogonal_sweep as inputs
    except ImportError:
        try:
            import orthogonal_sweep as inputs  # type: ignore[no-redef]
        except ImportError:
            return None, "orthogonal_sweep unavailable to rebuild runtime inputs"

    try:
        if family == "carry":
            # The gauntlet passes the SYMBOL and lets the family read its own recorded terms.
            extra["symbol"] = sym
            return extra, "ok"

        if family in _PEER_FAMILIES:
            peer_symbol = call.get("peer_symbol")
            if not peer_symbol:
                return None, "no peer_symbol on the candidate"
            peer = inputs._bars(str(peer_symbol))
            if peer is None:
                return None, f"peer bars unavailable for {peer_symbol}"
            extra["peer"] = peer
            return extra, "ok"

        if family == "cross_asset_residual":
            names = call.get("factor_symbols") or []
            factors = [d for d in (inputs._bars(str(s)) for s in names) if d is not None]
            if not factors:
                return None, f"no factor bars available of {len(names)} named"
            extra["factors"] = factors
            return extra, "ok"

        if family in {"liquidity_regime", "orderflow_imbalance"}:
            spread, flow = inputs._tape_series(sym, h1.index)
            series = spread if family == "liquidity_regime" else flow
            if series is None:
                return None, "tape series unavailable"
            extra["spread_series" if family == "liquidity_regime" else "flow"] = series
            return extra, "ok"

        if family == "macro_conditional":
            macro = inputs._macro_series(h1.index)
            if macro is None:
                return None, "macro series unavailable"
            extra["macro"] = macro
            return extra, "ok"

        if family == "cot_positioning":
            cot = inputs._cot_frame(sym)
            if cot is None:
                return None, f"no COT frame for {sym}"
            extra["cot"] = cot
            return extra, "ok"

        if family == "event_reaction":
            events = inputs._event_index()
            if events is None or len(events) == 0:
                return None, "no event calendar vintages on this box"
            extra["events"] = events
            return extra, "ok"

        if family == "discovered":
            from research.edge_search import resolve_inputs

            all_symbols = sorted(p.stem.removesuffix("_H1")
                                 for p in inputs.UNIVERSE.glob("*_H1.parquet"))
            extra["extra"] = resolve_inputs(sym, h1.index, all_symbols)
            return extra, "ok"
    except Exception as exc:                     # a rebuild that raises is a gap, never a guess
        return None, f"{type(exc).__name__}: {str(exc)[:80]}"

    return extra, "ok"


def strip_identity_keys(family: str, params: dict[str, Any]) -> dict[str, Any]:
    """Drop params that NAME an input rather than parameterise the family.

    `peer_symbol`, `factor_symbols`, `input_symbol` and `input_source` identify what to load; the
    loaded object is passed instead. Leaving them in raises TypeError on families that do not
    accept them, which the caller would then mistake for a signature mismatch.
    """
    drop = {"peer_symbol", "factor_symbols", "input_symbol", "input_source"}
    return {k: v for k, v in (params or {}).items() if k not in drop}
