"""THE SWEEP'S SHAPE: exploration guaranteed across ASSET CLASS x CHART x FAMILY.

WHY THIS EXISTS (measured 2026-09-25, audit of 20,900 judged cells). Every certificate the desk
holds is H1 and asia; H4, D1 and W1 are effectively untested; FX exotics, softs, energy, base
metals, silver and bonds together hold a few hundred judged cells against thousands of FX-major
and index ones; and whole families -- `exit_operated` (16,385 compiled), `htf_anchor_trend`
(9,135), `style_premia`, `momentum_volgate`, `range_reversion`, `jump`, `dow_effect`,
`overnight_drift`, `monday_gap` -- reached ZERO judged cells.

THREE DEFECTS PRODUCED THAT, and none of them was a decision anybody made:

  1. THE ORDER WAS DESTROYED BY THE QUOTA. `external_gauntlet.allocate_by_yield` trimmed each
     family to its share and then CONCATENATED the families, so the careful sort in front of it
     (never-judged first, intraday first, least-covered bucket first) survived only inside each
     family block. The build budget is measured in SECONDS and binds at a few hundred cells an
     hour on the 8 GB box, so the sweep built the first two or three families in dict order
     every hour and never reached the rest. Measured on the live docket: the first 1,500 cells
     of the allocated order held FOUR families. A family with no intraday row sorted behind every
     family that had one, which is exactly the list of zero-judged families above.

  2. SHARES WERE OF THE DOCKET, NOT OF THE HOUR. A 15% floor of a family's own queue is a
     membership rule; with the hour spent before the list's tail is reached it guarantees
     nothing. A share only means something if it holds on EVERY PREFIX of the order, because the
     prefix is what the budget buys.

  3. UNEXECUTABLE ROWS HELD THE HEAD OF THE QUEUE. ~25,000 docket rows carry decoration keys
     (`conditioner`, `regime`, `residual`, `entry_timing`, `execution_style`, `side_mode`,
     `representation`, ...) that the family function does not take. `build_cell` raised
     TypeError on each, returned None, and the row was recorded NOT_RUN_BUILD_FAILED -- which is
     not a verdict, so it was never stamped judged, so it sorted to the FRONT of the
     never-judged queue again the next hour and burned the build budget again. `style_premia`
     lost 1,560 of 1,695 rows this way, `range_reversion` 740 of 887, `jump` 800 of 956.

WHAT THIS MODULE DOES ABOUT IT.

  * `unexecutable_reason` names the rows no executor can run, BEFORE ordering, so they cost
    zero build seconds and are reported by name (NOT_RUN_UNEXECUTABLE_PARAMS). Nothing is
    stripped to make them run: running a `regime=high_vol` row as the unconditioned parent would
    certify a claim nobody tested under a name that says otherwise.

  * `shape` re-orders the sweep so that EVERY PREFIX is split between two lanes:
      EXPLORATION (`EXPLORATION_SHARE` of every prefix) -- divided equally across the
        under-tested (asset class, chart) strata, least-tested first, and inside each stratum
        round-robin across families, least-tested family first. Each under-tested stratum is
        also guaranteed `STRATUM_MIN_CELLS` members in the sweep.
      EXPLOITATION (the rest) -- divided across families by the yield shares the allocator
        already derived (capped at its own `YIELD_MAX_SHARE`), so what has produced survivors
        keeps its lead but can no longer take the whole hour.
    Chunks of `CHUNK` consecutive cells are taken from each queue so a symbol's charts stay
    adjacent for the frame cache.

WHAT IT DOES NOT DO. It never drops a member the allocator kept, never touches a gate, a cost,
a threshold or the multiplicity charge, and never re-admits a banned family (the caller removes
those before this runs). It changes which cells the hour reaches FIRST -- nothing about how any
of them is judged. The trial count per cell is unchanged; what changes is that the trials are
spent across the classes and charts the desk has never sampled, instead of on the hundredth
H1 asia cell of the same family.

MEMORY. Lists of references to specs the caller already holds, one small Counter per axis and
the seen-cell ids the caller already loaded. Nothing here reads a frame.
"""
from __future__ import annotations

import hashlib
import inspect
import os
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from typing import Any

#: Share of EVERY PREFIX of the sweep's order that goes to under-tested strata. Half is the
#: deliberate middle: exploitation still gets the other half, which is more than any single
#: family could take under the allocator's own 45% ceiling, and exploration gets enough that a
#: stratum with no judged cell receives a real sample within the first hour's few hundred builds.
EXPLORATION_SHARE = float(os.environ.get("GAUNTLET_EXPLORATION_SHARE", "0.5"))

#: A (class, chart) stratum with fewer judged cells than this is UNDER-TESTED and draws on the
#: exploration lane. 400 is roughly the judged count of the index lane; FX majors (1,109) and
#: the banned family's old ground are above it and are served by exploitation.
UNDERTESTED_JUDGED = int(os.environ.get("GAUNTLET_UNDERTESTED_JUDGED", "400"))

#: Members each under-tested stratum is guaranteed in the sweep, whatever the family trim kept.
#: Forty for the same reason `EXPLORATION_MIN_CELLS` is forty: below it a stratum cannot tell
#: "no edge here" from "not asked".
STRATUM_MIN_CELLS = int(os.environ.get("GAUNTLET_STRATUM_MIN_CELLS", "40"))

#: Consecutive cells taken from one queue per turn, so one symbol's cells stay adjacent.
CHUNK = max(1, int(os.environ.get("GAUNTLET_INTERLEAVE_CHUNK", "4")))

#: Prefix lengths the published projection reports -- the hour's realistic reach on the 8 GB
#: box (a few hundred cells) and on a box running the worker pool (low thousands).
PROJECTION_WINDOWS = (300, 1500)

#: Buckets the hypothesis lane never hunts. They are reported, never explored: an equity row is
#: the event lane's, and an unclassified symbol is hunted by nothing until it is classified.
NOT_EXPLORED = frozenset({"equity", "unclassified"})

#: Registry class (normalised by `universe_policy`) -> research bucket. Metals and FX are split
#: further below from the symbol itself, because the registry's `commodities` lumps gold,
#: silver, platinum and base metals together and its `forex` lumps the USD majors with crosses.
_CLASS_BUCKET = {
    "forex": "fx", "forex majors": "fx_major", "forex crosses": "fx_cross",
    "forex exotics": "fx_exotic", "fx": "fx", "fx major": "fx_major", "fx cross": "fx_cross",
    "fx exotic": "fx_exotic",
    "commodities": "metal", "commodity": "metal", "metal": "metal", "metals": "metal",
    "precious metals": "metal",
    "energy": "energy",
    "soft commodity": "soft", "soft commodities": "soft", "soft": "soft",
    "indices": "index", "index": "index",
    "bonds": "bond", "bond": "bond",
    "crypto": "crypto_cfd", "cryptocurrency": "crypto_cfd",
    "equities": "equity", "equity": "equity", "equities us": "equity", "shares": "equity",
    "share": "equity", "stock": "equity", "stocks": "equity",
}


def _policy() -> Any:
    try:
        from research import universe_policy as up
    except ImportError:                                   # pragma: no cover - path-dependent
        import universe_policy as up  # type: ignore[no-redef]
    return up


def research_bucket(symbol: str) -> str:
    """The research bucket an instrument's cells are budgeted under. Never raises.

    fx_major (a `forex` pair with USD on one side), fx_cross, fx_exotic, gold, silver, metal
    (platinum, palladium, copper, aluminium, nickel, lead, zinc), energy, soft, index, bond,
    crypto_cfd, equity, unclassified. Read from MetaTrader's registry through
    `universe_policy.asset_class_of`; the symbol text is used only to split a class the registry
    itself lumps, never to classify an instrument the registry does not know.
    """
    try:
        klass = _policy().asset_class_of(str(symbol))
    except Exception:
        klass = ""
    bucket = _CLASS_BUCKET.get(str(klass or ""), "")
    if not bucket:
        return "unclassified"
    sym = str(symbol).upper()
    if bucket == "fx":
        return "fx_major" if len(sym) == 6 and "USD" in (sym[:3], sym[3:]) else "fx_cross"
    if bucket == "metal":
        if sym.startswith("XAU"):
            return "gold"
        if sym.startswith("XAG"):
            return "silver"
    return bucket


#: `<sym>[@<TF>].<family>.<p=digest | rr=..>` -- `frontier_identity.cell_id`'s own shape. The
#: symbol may carry dots (`AAPL.24H`), a family never does and always starts lowercase.
_CELL_ID = re.compile(r"^(?P<sym>.+?)(?:@(?P<tf>[A-Z]\d+))?\.(?P<fam>[a-z][a-z0-9_]*)\."
                      r"(?:p=|rr=)")


def parse_cell_id(cid: str) -> tuple[str, str, str] | None:
    """(symbol, chart, family) from a cell id, or None when it is not one."""
    m = _CELL_ID.match(str(cid or ""))
    if not m:
        return None
    return m.group("sym"), (m.group("tf") or "H1"), m.group("fam")


def _banned() -> Callable[[str], bool]:
    try:
        from research.family_policy import family_banned
    except ImportError:                                   # pragma: no cover - path-dependent
        try:
            from family_policy import family_banned  # type: ignore[no-redef]
        except ImportError:
            return lambda _f: False
    return lambda f: bool(family_banned(f))


def judged_counts(cell_ids: Iterable[str],
                  banned: Callable[[str], bool] | None = None) -> tuple[Counter, Counter]:
    """How many cells each (bucket, chart) stratum and each (stratum, family) has had JUDGED.

    Read from the gauntlet's own seen-cell ids -- the same record the never-judged-first order
    uses -- so "under-tested" means exactly what the judge has and has not looked at.

    A BANNED FAMILY'S JUDGEMENTS DO NOT COUNT. 16,456 of the 20,900 judged cells are
    `discovered`, banned since 2026-09-16; counting them would call a stratum "well tested" on
    the strength of a family the desk may never trade, and starve it of exploration for exactly
    the reason the ban exists.
    """
    is_banned = banned if banned is not None else _banned()
    strata: Counter = Counter()
    fam: Counter = Counter()
    buckets: dict[str, str] = {}
    for cid in cell_ids:
        parsed = parse_cell_id(cid)
        if parsed is None:
            continue
        sym, tf, family = parsed
        if is_banned(family):
            continue
        b = buckets.get(sym)
        if b is None:
            b = buckets[sym] = research_bucket(sym)
        strata[(b, tf)] += 1
        fam[(b, tf, family)] += 1
    return strata, fam


# ----------------------------------------------------------------------- executability
#: Arguments the gauntlet or `family_inputs.resolve` SUPPLIES at build time. A family that
#: requires one of these is not unexecutable for lacking it on the row -- whether the input can
#: be rebuilt is `build_cell`'s question, answered by name there.
_SUPPLIED_AT_BUILD = frozenset({
    "peer", "peers", "factors", "spread_series", "flow", "macro", "cot", "events", "symbol",
    "extra", "drivers", "driver", "surface", "swap_diff", "risk", "fx", "_runner", "side",
})

#: For the inputs `build_cell` rebuilds in a FAMILY-SPECIFIC branch, the families that branch
#: serves. A family REQUIRING one of these without being named here gets nothing at build and
#: raises -- measured: `cot_comm_follow` (20 rows) requires a legacy-format `cot` frame and only
#: `cot_positioning` is ever handed one; `usd_session_shock` requires `fx` and nothing builds it.
_SUPPLIED_ONLY_TO: dict[str, frozenset[str]] = {
    "peer": frozenset({"relative_value", "correlation_regime"}),
    "peers": frozenset({"cross_sectional"}),
    "factors": frozenset({"cross_asset_residual", "pca_residual"}),
    "spread_series": frozenset({"liquidity_regime"}),
    "flow": frozenset({"orderflow_imbalance"}),
    "macro": frozenset({"macro_conditional"}),
    "cot": frozenset({"cot_positioning"}),
    "events": frozenset({"event_reaction"}),
    "fx": frozenset(),
}

#: Keys that NAME the cell rather than parameterise the family, besides `family_inputs`'
#: identity keys: the session is filtered generically by `family_call.session_filter`.
_EXTRA_IDENTITY = frozenset({"session", "peer_symbols"})

_SIG_CACHE: dict[str, Any] = {}


def _family_fn(family: str) -> Any:
    try:
        from mt5desk import families
        fn = getattr(families, f"family_{family}", None)
        if fn is None:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
        return fn
    except Exception:
        return None


def _identity_keys() -> frozenset[str]:
    try:
        from mt5desk.family_inputs import IDENTITY_KEYS
        return frozenset(IDENTITY_KEYS) | _EXTRA_IDENTITY
    except Exception:
        return frozenset({"peer_symbol", "factor_symbols", "input_symbol", "input_source",
                          "timeframe", "surface_generated_at"}) | _EXTRA_IDENTITY


def unexecutable_reason(family: str, params: Mapping[str, Any] | None) -> str | None:
    """Why no executor on this desk can run (family, params) -- or None when one can.

    Asked of the family function's SIGNATURE, which is what `build_cell` will call it with. A
    key the function does not take and that is not an identity key raises TypeError at build,
    on every sweep, forever; a required argument nobody supplies does the same. An unknown
    family, or one whose signature cannot be read, returns None: this screen only ever names
    what it can prove, and the build stays the authority on everything else.
    """
    fam = str(family or "")
    if fam not in _SIG_CACHE:
        fn = _family_fn(fam)
        try:
            _SIG_CACHE[fam] = inspect.signature(fn) if fn is not None else None
        except (TypeError, ValueError):
            _SIG_CACHE[fam] = None
    sig = _SIG_CACHE[fam]
    if sig is None:
        return None
    ps = sig.parameters
    if any(p.kind is p.VAR_KEYWORD for p in ps.values()):
        return None
    given = dict(params or {})
    ident = _identity_keys()
    extra = sorted(k for k in given if k not in ps and k not in ident)
    names = list(ps)
    first = names[0] if names else None
    def _supplied(n: str) -> bool:
        if n in _SUPPLIED_ONLY_TO:
            return fam in _SUPPLIED_ONLY_TO[n]
        return n in _SUPPLIED_AT_BUILD

    missing = sorted(n for n, p in ps.items()
                     if n != first and p.default is p.empty
                     and p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)
                     and n not in given and not _supplied(n))
    if not extra and not missing:
        return None
    parts = []
    if extra:
        parts.append(f"carries {', '.join(extra)}, which family_{fam} does not take and no "
                     f"executor applies")
    if missing:
        parts.append(f"lacks required {', '.join(missing)}")
    return ("; ".join(parts) + " -- running it would raise at build on every sweep, and "
            "stripping the keys would certify the undecorated parent under this cell's name")


# ----------------------------------------------------------------------------- the shape
def stratum_of(spec: Mapping[str, Any], chart_of: Callable[[Mapping[str, Any]], str],
               cache: dict[str, str] | None = None) -> tuple[str, str]:
    sym = str(spec.get("sym") or spec.get("symbol") or "")
    if cache is not None:
        b = cache.get(sym)
        if b is None:
            b = cache[sym] = research_bucket(sym)
    else:
        b = research_bucket(sym)
    try:
        tf = str(chart_of(spec)).upper()
    except Exception:
        tf = str((spec.get("params") or {}).get("timeframe") or "H1").upper()
    return b, tf


def _round_robin(rows: list[dict], key: Callable[[dict], Any], order: list[Any],
                 block: int = 1) -> list[dict]:
    """Rows interleaved `block` at a time across the groups `key` puts them in.

    Groups are visited in `order` (groups it does not name follow, sorted by their repr), and
    each group keeps its rows' input order. `block` > 1 keeps a run of one group's rows together
    -- in practice one symbol's cells -- so the frame cache still sees them adjacently.
    """
    by: dict[Any, list[dict]] = {}
    for r in rows:
        by.setdefault(key(r), []).append(r)
    named = [g for g in order if g in by]
    seen = set(named)
    groups = named + sorted((g for g in by if g not in seen), key=repr)
    out: list[dict] = []
    idx = dict.fromkeys(groups, 0)
    step = max(1, int(block))
    while groups:
        nxt = []
        for g in groups:
            i = idx[g]
            out.extend(by[g][i:i + step])
            idx[g] = i + step
            if idx[g] < len(by[g]):
                nxt.append(g)
        groups = nxt
    return out


def _family_round_robin(rows: list[dict], order: list[str], block: int = 1) -> list[dict]:
    """Rows interleaved across families, families in `order`, each in its input order."""
    return _round_robin(rows, lambda r: str(r.get("family") or "?"), list(order), block)


def shape(specs: list[dict], keep: list[dict], family_share: Mapping[str, float],
          judged_ids: Iterable[str], *, chart_of: Callable[[Mapping[str, Any]], str],
          exploration_share: float | None = None, undertested_below: int | None = None,
          stratum_min: int | None = None, chunk: int | None = None,
          ) -> tuple[list[dict], dict[str, Any]]:
    """Return (the sweep in its new order, the record of why).

    `specs` is the whole eligible docket in the caller's priority order; `keep` the members the
    caller's allocator chose (never removed here). The returned list holds every member of `keep`
    plus each under-tested stratum's floor, ordered so that every prefix honours the two lanes.
    """
    es = EXPLORATION_SHARE if exploration_share is None else float(exploration_share)
    es = min(max(es, 0.0), 1.0)
    below = UNDERTESTED_JUDGED if undertested_below is None else int(undertested_below)
    floor_n = STRATUM_MIN_CELLS if stratum_min is None else int(stratum_min)
    step = CHUNK if chunk is None else max(1, int(chunk))

    judged_strata, judged_fam = judged_counts(judged_ids)
    bcache: dict[str, str] = {}
    key_of: dict[int, tuple[str, str]] = {}
    strata: dict[tuple[str, str], list[dict]] = {}
    for s in specs:
        k = stratum_of(s, chart_of, bcache)
        key_of[id(s)] = k
        strata.setdefault(k, []).append(s)

    under = [k for k in strata
             if k[0] not in NOT_EXPLORED and judged_strata.get(k, 0) < below]
    # LEAST-TESTED FIRST; among equals the stratum with more waiting cells first, then by name
    # so the order is reproducible.
    under.sort(key=lambda k: (judged_strata.get(k, 0), -len(strata[k]), k))

    def _fam_order(k: tuple[str, str]) -> list[str]:
        fams = {str(r.get("family") or "?") for r in strata[k]}
        return sorted(fams, key=lambda f: (judged_fam.get((k[0], k[1], f), 0), f))

    member = {id(s) for s in keep}
    floor_added: dict[str, int] = {}
    for k in under:
        rows = strata[k]
        have = sum(1 for r in rows if id(r) in member)
        short = floor_n - have
        if short <= 0:
            continue
        spare = _family_round_robin([r for r in rows if id(r) not in member], _fam_order(k))
        take = spare[:short]
        for r in take:
            member.add(id(r))
        if take:
            floor_added[f"{k[0]}|{k[1]}"] = len(take)

    in_order = [s for s in specs if id(s) in member]
    # Members the caller kept but did not pass in `specs` (none today) keep their place at the end.
    listed = {id(s) for s in in_order}
    in_order.extend(s for s in keep if id(s) not in listed)

    queues: list[tuple[str, list[dict], float]] = []
    if under and es > 0:
        per = es / len(under)
        for k in under:
            rows = [s for s in in_order if key_of.get(id(s)) == k]
            if rows:
                queues.append((f"explore:{k[0]}|{k[1]}",
                               _family_round_robin(rows, _fam_order(k), step), per))
    exploit_w = (1.0 - es) if queues else 1.0
    by_fam: dict[str, list[dict]] = {}
    for s in in_order:
        by_fam.setdefault(str(s.get("family") or "?"), []).append(s)
    raw = {f: max(float(family_share.get(f, 0.0) or 0.0), 1e-9) for f in by_fam}
    tot = sum(raw.values()) or 1.0
    # INSIDE A FAMILY, THE STRATA TAKE TURNS TOO, least-tested first. Left in input order a
    # family's exploitation turns all land on whichever stratum sorts first (intraday FX crosses,
    # on the live docket), so the lane that is meant to follow YIELD would quietly follow the sort.
    # Ties among equally-tested strata are broken by a hash of (family, stratum), NOT by name:
    # an alphabetical tie-break sends every family's first turn to the same zero-judged stratum
    # (measured on the live docket: FX crosses on M30 took a quarter of the first 300 builds).
    def _st_order(fam: str, rows: list[dict]) -> list[tuple[str, str]]:
        ks = {key_of.get(id(r), ("?", "?")) for r in rows}
        return sorted(ks, key=lambda k: (judged_strata.get(k, 0),
                                         hashlib.sha1(f"{fam}|{k[0]}|{k[1]}".encode())
                                         .hexdigest()))

    for f, rows in by_fam.items():
        spread = _round_robin(rows, lambda r: key_of.get(id(r), ("?", "?")), _st_order(f, rows),
                              step)
        queues.append((f"exploit:{f}", spread, exploit_w * raw[f] / tot))

    # SMOOTH WEIGHTED ROUND ROBIN (the nginx upstream rule): every turn each live queue earns
    # its weight, the richest queue spends the total and emits a chunk. Deterministic, and the
    # share a queue holds is the same on every prefix, not only over the whole list.
    emitted: set[int] = set()
    order: list[dict] = []
    pos = [0] * len(queues)
    credit = [0.0] * len(queues)
    live = [i for i, q in enumerate(queues) if q[1] and q[2] > 0]
    while live:
        total = sum(queues[i][2] for i in live)
        for i in live:
            credit[i] += queues[i][2]
        best = max(live, key=lambda i: (credit[i], -i))
        credit[best] -= total
        rows = queues[best][1]
        took = 0
        while pos[best] < len(rows) and took < step:
            r = rows[pos[best]]
            pos[best] += 1
            if id(r) in emitted:
                continue
            emitted.add(id(r))
            order.append(r)
            took += 1
        if pos[best] >= len(rows):
            live = [i for i in live if i != best]
    # Anything a zero-weight queue held still belongs to the sweep: appended, never dropped.
    order.extend(s for s in in_order if id(s) not in emitted)

    projection: dict[str, dict[str, Any]] = {}
    for w in PROJECTION_WINDOWS:
        head = order[:w]
        if not head:
            continue
        ct = Counter(f"{key_of.get(id(s), ('?', '?'))[0]}|{key_of.get(id(s), ('?', '?'))[1]}"
                     for s in head)
        fam_n = len({str(s.get("family") or "?") for s in head})
        projection[f"first_{w}"] = {
            "cells": len(head), "strata": len(ct), "families": fam_n,
            "by_stratum": dict(ct.most_common()),
        }
    record = {
        "rule": ("every prefix of the sweep's order is split between EXPLORATION "
                 "(exploration_share, divided equally across under-tested (asset class, chart) "
                 "strata, least-tested first, families round-robin inside each, least-tested "
                 "family first) and EXPLOITATION (the rest, across families by the allocator's "
                 "yield shares). Nothing the allocator kept is removed; each under-tested stratum "
                 "is floored at stratum_min members."),
        "exploration_share": es, "undertested_below_judged": below,
        "stratum_min_cells": floor_n, "chunk": step,
        "n_strata": len(strata), "n_undertested": len(under),
        "undertested_least_first": [
            {"stratum": f"{k[0]}|{k[1]}", "judged_before": judged_strata.get(k, 0),
             "docket": len(strata[k]),
             "in_sweep": sum(1 for s in in_order if key_of.get(id(s)) == k)}
            for k in under[:80]],
        "floor_added": floor_added,
        "n_floor_added": sum(floor_added.values()),
        "members": len(order),
        "projection": projection,
    }
    return order, record
