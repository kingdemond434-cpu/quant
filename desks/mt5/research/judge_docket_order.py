"""THE JUDGE'S OWN DOCKET ORDER, READ FROM OUTSIDE THE SEALED FILE, FOR WHOEVER FEEDS IT.

WHY THIS EXISTS (2026-09-30). The sealed sweep (`scripts/external_gauntlet.py`) judges every cell
in its per-sweep docket that is CACHED for the day, and builds the rest in one fixed order until its
build budget runs out. So a cell the cache warmer builds is a verdict only if it lands in THAT
docket -- the one `main()` computes after the ban set-aside, its eight-key sort, the novelty screen
on the head and `allocate_by_yield`'s per-family trim. A warmer that orders by its own idea of
priority builds cells the next sweep never looks at (the family trim drops them) and leaves cold
cells the sweep then pays ~22 s each to build itself. Measured on the WIP it replaces: the warmer
ordered by `cell_priority`, the judge by `_is_new` then chart then CEO family then bucket then
symbol rotation, and the two agreed on nothing but the never-judged-first tier.

WHAT IS RESTATED AND WHY IT CANNOT DRIFT. The sort key and the ban/novelty/allocation steps live
inside `main()` as closures, so they cannot be imported; they are restated here from the SAME
module-level helpers the sealed file calls (`_seen_cells`, `_stamped_but_unjudged`, `timeframe_of`,
`_build_cursor`, `_family_yield`, `_explore_unmeasured_axes`, `_orthogonality_floor`,
`family_policy.family_banned`, `novelty_gate.screen`) and the same module constants
(`YIELD_ALLOCATION_STRENGTH`, `YIELD_MAX_SHARE`, `YIELD_MIN_SHARE`, `GAUNTLET_NOVELTY_SCREEN`).
`tests/test_judge_docket_order.py` pins the sealed source text of the sort key and proves
`allocate()` returns exactly what `external_gauntlet.allocate_by_yield` returns on the same
input, so
an edit to the sealed order fails the suite here rather than silently desynchronising the warmer.

ONE DELIBERATE DIFFERENCE, AND IT IS A READ-ONLY ONE. `allocate_by_yield` also WRITES
`reports/RESEARCH_ALLOCATION.json`; `allocate()` computes the identical trim and writes nothing, so
the warmer can never overwrite the judge's own published allocation with its view of the docket.

Consumers: `scripts/warm_gauntlet_cache.py` (`run_round`, via `sealed_docket` and `sealed_keep`).
Nothing here decides a verdict, reorders the judge or drops a cell: it only tells a feeder which
cells the judge will read, in the order it will read them.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The sealed sort key, VERBATIM from `external_gauntlet.main`. The drift test asserts the sealed
#: source still contains exactly this text; `order_key` below is its restatement.
SEALED_SORT_KEY_SOURCE = (
    "key=lambda sp: (_is_new(sp),\n"
    "                        _tf_rank(sp),\n"
    "                        _ceo_rank(sp),\n"
    "                        _judged_in_bucket.get(_bucket(sp), 0),\n"
    "                        _cursor.get(str(sp.get(\"sym\") or \"\"), \"\"),\n"
    "                        str(sp.get(\"sym\") or \"\"),\n"
    "                        timeframe_of(sp.get(\"params\"), str(sp.get(\"family\") or \"\")),\n"
    "                        str(sp.get(\"family\") or \"\")))")

INTRADAY = ("M1", "M5", "M15", "M30")


def sealed_docket(G: Any, meta: dict) -> tuple[list[dict], dict[str, int]]:
    """The sweep's eligible cells, derived exactly as `external_gauntlet.main` derives them.

    Streaming read, the point-in-time ratchet (`stamped_only` once any row is stamped), the
    row-level timeframe fold, first-row-wins de-duplication, the economic-prior partition WITH
    `meta`, and the modifier preflight. Returns (eligible specs, census). Each spec carries `tf`.
    A fake `G` without the streaming helpers (tests) falls back to a whole-file read.
    """
    surv_file = Path(G.HYP) / "external_survivors.json"
    census = {"rows": 0, "stamped": 0, "unstamped": 0, "cells": 0, "eligible": 0,
              "rejected_at_prior": 0, "modifier_refused": 0}
    if not surv_file.exists():
        return [], census
    it_rows = getattr(G, "iter_json_array", None)
    stamped_fn = getattr(G, "is_stamped", None)

    def _rows():
        if it_rows is not None:
            yield from it_rows(surv_file)
            return
        try:
            doc = json.loads(surv_file.read_text("utf-8"))
        except (OSError, ValueError):
            doc = []
        yield from (doc if isinstance(doc, list) else [])

    if stamped_fn is not None:
        for h in _rows():
            census["rows"] += 1
            if isinstance(h, dict):
                census["stamped" if stamped_fn(h) else "unstamped"] += 1
    stamped_only = bool(census["stamped"] and census["unstamped"])
    cells: dict[str, dict] = {}
    for h in _rows():
        if stamped_fn is None:
            census["rows"] += 1
        if not isinstance(h, dict) or (stamped_only and not stamped_fn(h)):  # type: ignore[misc]
            continue
        sym, fam = h.get("symbol"), h.get("family")
        if not sym or not fam:
            continue
        params = dict(h.get("params") or {})
        row_tf = str(h.get("timeframe") or "").upper()
        if row_tf and row_tf != "H1" and "timeframe" not in params:
            params["timeframe"] = row_tf
        key = f"{sym}.{fam}.{json.dumps(params, sort_keys=True)}"
        if key not in cells:
            cells[key] = {"sym": sym, "family": fam, "params": params,
                          "mechanism_status": h.get("mechanism_status"),
                          "mechanism_note": h.get("mechanism_note")}
    census["cells"] = len(cells)
    eligible, rejected = G.partition_at_economic_prior(list(cells.values()), meta)
    census["rejected_at_prior"] = len(rejected)
    pre = getattr(G, "modifier_preflight", None)
    if pre is not None:
        keep = []
        for sp in eligible:
            try:
                why = pre(sp)
            except Exception:
                why = None
            if why:
                census["modifier_refused"] += 1
            else:
                keep.append(sp)
        eligible = keep
    for sp in eligible:
        sp["tf"] = G.timeframe_of(sp.get("params"), str(sp.get("family") or ""))
    census["eligible"] = len(eligible)
    return list(eligible), census


def stamp_new(G: Any, specs: list[dict]) -> int:
    """Stamp `_never_judged` by the sealed `_is_new` rule; return how many are never judged.

    `_is_new` is 0 (NEW) when the id is not in the seen record, or is there with no stages behind
    it (`_stamped_but_unjudged`), or `cell_id` raises. Unreadable records read EMPTY, as sealed.
    """
    try:
        seen = G._seen_cells()
    except Exception:
        seen = {}
    try:
        unjudged = G._stamped_but_unjudged()
    except Exception:
        unjudged = set()
    n = 0
    for sp in specs:
        try:
            cid = G.cell_id({"sym": sp.get("sym"), "family": sp.get("family"),
                             "params": sp.get("params") or {}})
        except Exception:
            cid = ""
        new = (not cid) or (cid not in seen) or (cid in unjudged)
        sp["_never_judged"] = bool(new)
        n += int(new)
    return n


def _ceo_families(G: Any) -> set[str]:
    try:
        doc = json.loads((Path(G.BASE) / "desks" / "mt5" / "reports" / "CEO_DOCKET.json")
                         .read_text("utf-8"))
    except Exception:
        return set()
    out: set[str] = set()
    for p in (doc.get("proposals") or []) if isinstance(doc, dict) else []:
        f = str((p.get("family") if isinstance(p, dict) else p) or "").strip()
        if f:
            out.add(f)
    return out


def order(G: Any, specs: list[dict]) -> list[dict]:
    """The sealed eight-key sort (see SEALED_SORT_KEY_SOURCE). Requires `stamp_new` first."""
    tf_of = G.timeframe_of

    def _bucket(sp: dict) -> tuple[str, str]:
        p = sp.get("params") or {}
        return (tf_of(p, str(sp.get("family") or "")),
                str(p.get("session") or p.get("selector") or sp.get("selector") or "all").lower())

    judged_in_bucket: dict[tuple[str, str], int] = {}
    for sp in specs:
        if not sp.get("_never_judged", True):
            b = _bucket(sp)
            judged_in_bucket[b] = judged_in_bucket.get(b, 0) + 1
    try:
        cursor = G._build_cursor()
    except Exception:
        cursor = {}
    ceo = _ceo_families(G)

    def _tf_rank(sp: dict) -> int:
        tf = tf_of(sp.get("params"), str(sp.get("family") or ""))
        return 0 if tf in INTRADAY else (1 if tf == "H4" else 2)

    return sorted(specs, key=lambda sp: (
        0 if sp.get("_never_judged", True) else 1,
        _tf_rank(sp),
        0 if str(sp.get("family") or "") in ceo else 1,
        judged_in_bucket.get(_bucket(sp), 0),
        cursor.get(str(sp.get("sym") or ""), ""),
        str(sp.get("sym") or ""),
        tf_of(sp.get("params"), str(sp.get("family") or "")),
        str(sp.get("family") or "")))


def drop_banned(specs: list[dict]) -> tuple[list[dict], int]:
    """The sealed ban set-aside (`research.family_policy`); unreadable policy sets nothing aside."""
    try:
        from research.family_policy import family_banned
    except Exception:
        return specs, 0
    keep = [sp for sp in specs if not family_banned(sp.get("family"))]
    return keep, len(specs) - len(keep)


def drop_redundant(G: Any, specs: list[dict]) -> tuple[list[dict], int]:
    """The sealed novelty screen on the head (`GAUNTLET_NOVELTY_SCREEN`, default 1500). Read-only:
    the sealed sweep writes `NOVELTY_SET_ASIDE.json`, this does not. Unavailable drops nothing."""
    try:
        import novelty_gate as ng
        head_n = int(os.environ.get("GAUNTLET_NOVELTY_SCREEN", "1500"))
        head = specs[:head_n]
        cands = [{"symbol": sp.get("sym"), "family": sp.get("family"),
                  "params": sp.get("params") or {},
                  "timeframe": G.timeframe_of(sp.get("params"), str(sp.get("family") or "")),
                  "session": (sp.get("params") or {}).get("session")} for sp in head]
        verd = ng.screen(cands)
        drop = {i for i, v in enumerate(verd) if getattr(v, "verdict", "") == "REDUNDANT"}
    except Exception:
        return specs, 0
    return [sp for i, sp in enumerate(specs) if i not in drop], len(drop)


def allocate(G: Any, specs: list[dict]) -> list[dict]:
    """`external_gauntlet.allocate_by_yield`'s `keep`, computed identically and WRITING NOTHING."""
    if not specs:
        return []
    yields = G._family_yield()
    by_fam: dict[str, list[dict]] = {}
    for sp in specs:
        by_fam.setdefault(str(sp.get("family") or "?"), []).append(sp)
    prior = (sum(yields.values()) / len(yields)) if yields else 0.0
    raw = {f: max(yields.get(f, prior), 1e-9) for f in by_fam}
    tot = sum(raw.values()) or 1.0
    n_fam = len(by_fam)
    keep: list[dict] = []
    for fam, rows in by_fam.items():
        share = (G.YIELD_ALLOCATION_STRENGTH * (raw[fam] / tot)
                 + (1.0 - G.YIELD_ALLOCATION_STRENGTH) / n_fam)
        share = min(share, G.YIELD_MAX_SHARE)
        want = max(round(share * len(specs)), int(G.YIELD_MIN_SHARE * len(rows)), 1)
        keep.extend(rows[:want])
    explored, _axes = G._explore_unmeasured_axes(specs, keep)
    keep.extend(explored)
    orthogonal, _rec = G._orthogonality_floor(specs, keep)
    keep.extend(orthogonal)
    return keep


def sealed_keep(G: Any, specs: list[dict], *, novelty: bool = True) -> tuple[list[dict], dict]:
    """The cells the next sweep will read, in the order its pre-warm will build them.

    Returns (keep, census). Every spec is stamped `_never_judged`; `census["outside_keep"]` counts
    eligible cells the family trim leaves for a later sweep (never dropped from the docket).
    """
    n_new = stamp_new(G, specs)
    kept, n_banned = drop_banned(specs)
    ordered = order(G, kept)
    n_redundant = 0
    if novelty:
        ordered, n_redundant = drop_redundant(G, ordered)
    keep = allocate(G, ordered)
    return keep, {"eligible": len(specs), "never_judged": n_new, "banned_set_aside": n_banned,
                  "novelty_set_aside": n_redundant, "keep": len(keep),
                  "keep_never_judged": sum(1 for sp in keep if sp.get("_never_judged")),
                  "outside_keep": len(ordered) - len(keep) if len(ordered) >= len(keep) else 0,
                  "order": "sealed: never-judged, intraday, CEO family, least-covered bucket, "
                           "symbol rotation; then ban set-aside, novelty head, yield trim"}
