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


def timeframe_of(params: dict[str, Any] | None) -> str:
    """The chart this cell was hunted on. Absent means H1 -- see `frontier_identity`."""
    return str((params or {}).get("timeframe") or "H1").upper()


def resolve(sym: str, family: str, params: dict[str, Any],
            h1: Any) -> tuple[dict[str, Any] | None, str]:
    """Return (extra kwargs, reason). `None` kwargs means this cell cannot be run here.

    Mirrors `external_gauntlet.build_cell`'s reconstruction exactly, including its rule that a
    params key naming a peer or factor is REPLACED by the loaded frame rather than passed through.

    EVERY LOADED FRAME COMES BACK ON THE CELL'S OWN CHART (2026-09-05). A peer or factor frame
    fetched at H1 for an M5 cell does not raise: the families join `how="inner"`, so the join
    silently keeps only the twelve-times-sparser hourly stamps and the family computes an H1
    residual while the certificate says M5. `h1` (the argument keeps its historical name because
    every caller passes bars) is already the cell's own chart -- the caller loaded it -- so this
    only has to make the OTHER instruments agree with it.
    """
    extra: dict[str, Any] = {}
    call = dict(params or {})
    tf = timeframe_of(params)
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
            peer = inputs._bars(str(peer_symbol), tf)
            if peer is None:
                return None, f"peer bars unavailable for {peer_symbol}"
            extra["peer"] = peer
            return extra, "ok"

        if family == "ensemble":
            # Members are ordinary cells; the runner rebuilds each through the gauntlet's own
            # build_cell so a member's inputs are resolved by the same rule as everything else.
            # The identity (members, weights, threshold) passes through untouched -- it IS the
            # certificate.
            try:
                from research.weak_signal_compiler import _runner_factory
            except ImportError:
                from weak_signal_compiler import _runner_factory  # type: ignore[no-redef]
            import json as _json
            from pathlib import Path as _Path
            try:
                meta = _json.loads((_Path(__file__).resolve().parent.parent / "data" / "universe"
                                    / "universe.json").read_text("utf-8"))
            except (OSError, ValueError):
                return None, "universe.json unreadable; ensemble members cannot be rebuilt"
            if not call.get("members"):
                return None, "ensemble has no members on the candidate"
            extra["_runner"] = _runner_factory(meta)
            return extra, "ok"

        if family == "formula":
            # Driver terminals are resolved by ROLE, first available instrument per role, the
            # same registry the residual engine uses -- so `usd` means USDX here and everywhere.
            try:
                from mt5desk.economic_drivers import ROLES

                from libs.research.alpha_grammar import DRIVER_TERMINALS, terminals_in
            except ImportError as exc:
                return None, f"alpha grammar unavailable: {exc}"
            need = [t for t in terminals_in(call.get("expr")) if t in DRIVER_TERMINALS]
            drivers: dict[str, Any] = {}
            for t in need:
                for cand in ROLES.get(t.upper(), ()):
                    b = inputs._bars(str(cand), tf)
                    if b is not None:
                        drivers[t] = b
                        break
                if t not in drivers:
                    return None, f"no bars for driver role {t}"
            extra["drivers"] = drivers
            return extra, "ok"

        if family == "lead_lag":
            drv = call.get("driver_symbol")
            if not drv:
                return None, "no driver_symbol on the candidate"
            b = inputs._bars(str(drv), tf)
            if b is None:
                return None, f"driver bars unavailable for {drv}"
            extra["driver"] = b
            return extra, "ok"

        if family == "style_premia":
            # Carry needs the instrument's own rollover; defensive needs the risk driver. Each
            # style refuses without its input, so both are supplied when they exist and the
            # family decides what it can run.
            try:
                from libs.data.datahub import desk_hub
                q = desk_hub().get("terms.swap_diff", symbol=sym)["payload"]
                extra["swap_diff"] = float(q.value)
            except Exception:
                extra["swap_diff"] = None
            try:
                from mt5desk.economic_drivers import ROLES
                for cand in ROLES.get("RISK", ()):
                    b = inputs._bars(str(cand), tf)
                    if b is not None:
                        extra["risk"] = b
                        break
            except Exception:
                pass
            return extra, "ok"

        # pca_residual TAKES THE SAME `factors` ARGUMENT and was never listed here, so it was
        # handed factors=None on every sweep and every one of its 301 cells failed to build with
        # "parquet missing or build failed" -- a message that names the wrong cause, because the
        # parquets were all present. Same input contract, same branch.
        if family in {"cross_asset_residual", "pca_residual"}:
            names = call.get("factor_symbols") or []
            factors = [d for d in (inputs._bars(str(s), tf) for s in names) if d is not None]
            if not factors:
                return None, f"no factor bars available of {len(names)} named"
            extra["factors"] = factors
            return extra, "ok"

        if family in {"liquidity_regime", "orderflow_imbalance"}:
            spread, flow = inputs._tape_series(sym, h1.index, tf)
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
            # Price-native primitives are rebuilt by family_discovered. Resolving every peer,
            # triangle, tape, macro and COT series for dd/hour/ru cells is unnecessary and large
            # enough to OOM the forward service. Only ext_* features need the external universe.
            feature = str(call.get("feature") or "")
            if "ext_" not in feature:
                return extra, "ok: price-native discovered feature"
            from research.edge_search import resolve_inputs

            # HOURLY BY CONSTRUCTION, and named as such: `edge_search._close` reads
            # `<SYM>_H1.parquet` whatever list it is given, so the external primitives are an
            # HOURLY series reindexed causally onto this cell's own index. Mirrors
            # `external_gauntlet.build_cell` exactly, which is the point of this module.
            all_symbols = sorted(p.stem.removesuffix("_H1")
                                 for p in inputs.UNIVERSE.glob("*.parquet"))
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

    `timeframe` is dropped for the same reason and is the reason this docstring needed a line:
    it names the CHART TO LOAD, exactly as `peer_symbol` names an instrument to load, and no
    family takes it as an argument. It stays in the cell's IDENTITY -- callers pass the unstripped
    params to `resolve` and to the sleeve registry -- because that is the only place it belongs.
    """
    drop = {"peer_symbol", "factor_symbols", "input_symbol", "input_source", "timeframe"}
    return {k: v for k, v in (params or {}).items() if k not in drop}
