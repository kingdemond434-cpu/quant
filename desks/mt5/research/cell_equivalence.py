"""CELLS THAT ARE THE SAME TRADE UNDER TWO SPELLINGS ARE BUILT ONCE.

THE WASTE THIS REMOVES. The miners write a cell's parameters as they found them, and the same
executable rule arrives under several spellings: an explicit `timeframe: "H1"` beside a row that
leaves the chart to its H1 default, a keyword spelled out at exactly its signature default, a
`representation` LABEL naming the information axis a child was filed under, a `regime:
"unconditional"` or `entry_timing: "instant"` that `mt5desk.cell_modifiers` applies as a no-op.
Each spelling is a different `cell_id` and a different cache key, so each one paid a full build --
signals, the 1x backtest and the 3x backtest -- to produce a daily series byte-identical to its
twin's. Measured 2026-09-30 on the committed docket: 580 of 57,538 rows (1.0%) are exact
spellings of another row; `cross_asset_residual` alone carries 112.

WHAT IS SHARED, AND WHAT IS NOT. Only the COMPUTE. `canonical_params` names the executable rule
behind a spelling; `scripts/warm_gauntlet_cache.py` builds one member of each group and writes the
same two series under every member's own cache key. The sealed judge then finds each member as a
cache hit and judges it IN FULL -- its own cell id, its own ten gates, its own verdict row. No
verdict is copied, no gate is skipped, nothing about how a cell is judged changes; a member simply
stops paying for a build whose output was already on disk under another name.

EXACT OR NOTHING. The judge's cache is the one place where a wrong identity is undetectable (two
cells that share a key serve each other's returns, see `external_gauntlet._cache_key`), so every
rule below is a rule `external_gauntlet.build_cell` itself applies, and anything this module cannot
prove identical is left alone:

  * `timeframe: "H1"` is dropped for an un-pinned family -- `timeframe_of` reads absence as H1 and
    `build_cell` pops the key before the family is called.
  * A keyword the family NAMES, equal to its signature default AND of the default's own type, is
    dropped -- Python binds an omitted keyword to exactly that value. `1` against a default of
    `1.0` is NOT dropped; neither is `True` against `1`.
  * A key the family does NOT name and has no `**kwargs` for, that `cell_modifiers` classifies as a
    LABEL (`representation`, `cost_aware`), is dropped -- `split` moves it out of the call and
    neither `refusal` nor `apply` reads it.
  * The same for a modifier whose value `cell_modifiers.apply` treats as a no-op (`regime` in
    `NO_OP_REGIMES`, `side_mode` "follow", `entry_timing` "instant", a market `execution_style`).
  * NOTHING is touched on a family that takes `**kwargs`, on a key `build_cell` rewrites per family
    (`input_symbol`, `peer_symbol`, `factor_symbols`, `input_source`, `symbol`, `feature`,
    `session`), or on a family this module cannot resolve. Those cells keep their own spelling and
    build as they always did.

`tests/test_cell_equivalence.py` builds both spellings of every rule through the real
`build_cell` on the same bars and asserts the signals are identical, so a rule that stops being
exact fails the suite rather than a certificate.
"""
from __future__ import annotations

import inspect
import json
from typing import Any

#: Keys `external_gauntlet.build_cell` rewrites or consumes per family before the call. Their
#: meaning depends on the family branch, so no spelling of them is ever canonicalised here.
REWRITTEN_KEYS = frozenset({"input_symbol", "peer_symbol", "factor_symbols", "input_source",
                            "symbol", "feature", "session", "peer", "factors", "extra"})

#: Families pinned to one chart whatever `params` says (mirrors `external_gauntlet`'s own pin).
#: A pinned family's `timeframe` key is left alone: dropping it is safe only for H1-by-absence.
PINNED = frozenset({"lvc_asia_london"})

_FN_CACHE: dict[str, Any] = {}


def family_fn(family: str) -> Any:
    """The callable `build_cell` would call for `family`, or None when it resolves to nothing."""
    if family in _FN_CACHE:
        return _FN_CACHE[family]
    fn = None
    try:
        from mt5desk import families
        fn = getattr(families, f"family_{family}", None)
        if fn is None:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
    except Exception:
        fn = None
    _FN_CACHE[family] = fn
    return fn


def _noop_modifier(key: str, value: Any) -> bool:
    try:
        from mt5desk import cell_modifiers as cm
    except Exception:
        return False
    v = cm._s(value)
    if key == "regime":
        return v in cm.NO_OP_REGIMES
    if key == "side_mode":
        return v in ("", "follow")
    if key == "entry_timing":
        return v in ("", "instant")
    if key in ("execution_style", "entry_style"):
        return v in cm.MARKET_STYLES
    return False


def canonical_params(family: str, params: dict[str, Any] | None) -> dict[str, Any] | None:
    """The executable rule behind a spelling, or None when this module will not vouch for it.

    None means "build this cell under its own spelling" -- the behaviour before this module
    existed. It is returned for an unresolvable family and for a family taking `**kwargs`.
    """
    fn = family_fn(str(family or ""))
    if fn is None:
        return None
    try:
        sig = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return None
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.values()):
        return None
    try:
        from mt5desk import cell_modifiers as cm
        labels, modifiers = cm.LABEL_KEYS, cm.MODIFIER_KEYS
    except Exception:
        labels, modifiers = frozenset(), frozenset()
    out: dict[str, Any] = {}
    for k, v in dict(params or {}).items():
        if k in REWRITTEN_KEYS:
            out[k] = v
            continue
        if k == "timeframe":
            if family not in PINNED and str(v).upper() == "H1":
                continue
            out[k] = v
            continue
        if k in sig:
            d = sig[k].default
            if d is not inspect.Parameter.empty and type(v) is type(d) and v == d:
                continue
            out[k] = v
            continue
        if k in labels and k in modifiers:
            continue
        if k in modifiers and _noop_modifier(k, v):
            continue
        out[k] = v
    return out


def equivalence_key(sym: str, family: str, params: dict[str, Any] | None,
                    timeframe: str) -> str | None:
    """One string per executable rule on one symbol and chart; None when not canonicalisable."""
    canon = canonical_params(family, params)
    if canon is None:
        return None
    return json.dumps({"s": sym, "f": family, "tf": str(timeframe).upper(), "p": canon},
                      sort_keys=True, default=str)


def groups(specs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """{equivalence key: members}, members in input order. Specs carry sym/family/params/tf.

    A spec this module will not vouch for is its own group of one, keyed by its own identity, so
    every input lands in exactly one group and nothing is lost between them.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for sp in specs:
        tf = str(sp.get("tf") or "H1")
        key = equivalence_key(str(sp.get("sym") or ""), str(sp.get("family") or ""),
                              sp.get("params") or {}, tf)
        if key is None:
            key = "self:" + json.dumps({"s": sp.get("sym"), "f": sp.get("family"), "tf": tf,
                                        "p": sp.get("params") or {}}, sort_keys=True, default=str)
        out.setdefault(key, []).append(sp)
    return out
