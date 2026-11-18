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
Nothing here decides a verdict or drops a cell: it tells a feeder which cells the judge will read.

THE SECOND DELIBERATE DIFFERENCE (2026-11-18, H2/H4/H5): the ORDER of the kept set. After the
sealed trim, `priority_tilt` reorders `keep` -- never its membership -- by a bounded blend of three
hourly scores from `research/docket_priority.py` (ORIGINAL mechanisms with a quota, rows on which
2+ independent sources agree, and expected information gain). The warmer builds in that order and
the sealed sweep judges every cached cell, so the tilt decides which cells are judged FIRST and
nothing about how any cell is judged. Revert: JUDGE_DOCKET_TILT=0 or data/DOCKET_TILT_DISABLED.
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
    "                        bool(sp.get(\"prejudge_flagged\")),\n"
    "                        _judged_in_bucket.get(_bucket(sp), 0),\n"
    "                        _cursor.get(str(sp.get(\"sym\") or \"\"), \"\"),\n"
    "                        str(sp.get(\"sym\") or \"\"),\n"
    "                        timeframe_of(sp.get(\"params\"), str(sp.get(\"family\") or \"\")),\n"
    "                        str(sp.get(\"family\") or \"\")))")

INTRADAY = ("M1", "M5", "M15", "M30")


def sealed_docket(G: Any, meta: dict, memo: dict | None = None, *,
                  live_ttl_s: float = 3600.0) -> tuple[list[dict], dict[str, int]]:
    """The sweep's eligible cells, derived exactly as `external_gauntlet.main` derives them.

    Streaming read, the point-in-time ratchet (`stamped_only` once any row is stamped), the
    row-level timeframe fold, first-row-wins de-duplication, the economic-prior partition WITH
    `meta`, and the modifier preflight. Returns (eligible specs, census). Each spec carries `tf`.
    A fake `G` without the streaming helpers (tests) falls back to a whole-file read.

    `memo` (2026-10-28, the cache-warmer stall): {memo_key(cell key): outcome} from an earlier
    pass made under the SAME inputs. A cell already in it skips the sealed partition and preflight
    -- on the box those load an intraday frame per non-H1 cell, for 1.65M rows, and that serial
    pass ran at IDLE priority for hours. Cells not in it go through the sealed functions exactly
    as before and are added to it. The result is the same list, in the same order, with the same
    census (`tests/test_warm_docket_memo.py` proves it on a docket where every outcome occurs).
    Its validity is the caller's: `warm_gauntlet_cache` stamps it with the inputs those two
    functions read and a TTL. The judge never reads it; a stale memo can only change which
    cells are WARMED, never a verdict.
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
                          "mechanism_note": h.get("mechanism_note"),
                          "prejudge_flagged": bool((h.get("prejudge") or {}).get("flags"))}
    census["cells"] = len(cells)
    if memo is not None:
        return _partition_memoised(G, meta, cells, memo, census, live_ttl_s=live_ttl_s)
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


def memo_key(cell_key: str, spec: dict | None = None) -> str:
    """The memo key of one de-duplicated cell: 20 hex chars of a sha1 (1.65M cells ~ 40MB).

    It hashes the cell key AND every field of the spec the sealed partition reads besides
    symbol, family and params: `mechanism_status` and `mechanism_note` (both read by
    `frontier_identity.economic_prior`). So a row whose mechanism changes is re-decided, never
    served the old outcome (v1.1, audit of 6ea07bdf2).
    """
    import hashlib
    extra = ""
    if spec is not None:
        extra = "\x1f" + json.dumps([spec.get("mechanism_status"), spec.get("mechanism_note")],
                                    sort_keys=True, default=str)
    return hashlib.sha1((cell_key + extra).encode("utf-8")).hexdigest()[:20]


#: Memo outcomes. An eligible cell also records its CANONICAL symbol and chart, because the sealed
#: partition rewrites `sym` to the registry's spelling and a memo hit must hand back the same spec.
MEMO_REJECTED = "R"
MEMO_MODIFIER = "M"
MEMO_ELIGIBLE = "E"

#: Outcomes that depended on the LIVE TERMINAL (the cell's H1 or own-chart parquet is absent, so
#: the sealed partition asked `_live_frame`) carry the hour they were decided, `@L<hour>`, and are
#: re-decided after `live_ttl_s` -- terminal availability is not a file the memo stamp can see.
LIVE_MARK = "@L"


def _live_dependent(G: Any, sp: dict, tf: str) -> bool:
    uni = getattr(G, "UNI", None)
    if uni is None:
        return False
    sym = str(sp.get("sym") or "")
    try:
        if not (Path(uni) / f"{sym}_H1.parquet").exists():
            return True
        return tf != "H1" and not (Path(uni) / f"{sym}_{tf}.parquet").exists()
    except OSError:
        return True


def _memo_fresh(out: str, now_h: int, live_ttl_h: float) -> bool:
    if LIVE_MARK not in out:
        return True
    try:
        born = int(out.rsplit(LIVE_MARK, 1)[1])
    except ValueError:
        return False
    return (now_h - born) < live_ttl_h


def _partition_memoised(G: Any, meta: dict, cells: dict[str, dict], memo: dict,
                        census: dict[str, int], *, now: float | None = None,
                        live_ttl_s: float = 3600.0) -> tuple[list[dict], dict[str, int]]:
    """`sealed_docket`'s partition + preflight, with outcomes already known read from `memo`."""
    import time as _time

    now_h = int((now if now is not None else _time.time()) // 3600)
    live_ttl_h = max(0.0, live_ttl_s / 3600.0)
    hashed = [(memo_key(k, sp), sp) for k, sp in cells.items()]
    for h, _sp in hashed:
        out = memo.get(h)
        if out is not None and not _memo_fresh(str(out), now_h, live_ttl_h):
            del memo[h]
    todo = [sp for h, sp in hashed if h not in memo]
    census["memo_hits"] = len(hashed) - len(todo)
    census["memo_new"] = len(todo)
    if todo:
        fresh, _rejected = G.partition_at_economic_prior(todo, meta)
        ok = {id(sp) for sp in fresh}
        pre = getattr(G, "modifier_preflight", None)
        for h, sp in hashed:
            if h in memo:
                continue
            tf = G.timeframe_of(sp.get("params"), str(sp.get("family") or ""))
            mark = f"{LIVE_MARK}{now_h}" if _live_dependent(G, sp, tf) else ""
            if id(sp) not in ok:
                memo[h] = MEMO_REJECTED + mark
                continue
            why = None
            if pre is not None:
                try:
                    why = pre(sp)
                except Exception:
                    why = None
            if why:
                memo[h] = MEMO_MODIFIER + mark
            else:
                memo[h] = f"{MEMO_ELIGIBLE}|{sp['sym']}|{tf}{mark}"
    eligible: list[dict] = []
    for h, sp in hashed:
        out = str(memo.get(h) or MEMO_REJECTED).split(LIVE_MARK, 1)[0]
        if out == MEMO_REJECTED:
            census["rejected_at_prior"] += 1
        elif out == MEMO_MODIFIER:
            census["modifier_refused"] += 1
        else:
            _e, sym, tf = [*out.split("|", 2), "", ""][:3]
            sp["sym"] = sym or sp["sym"]
            sp["tf"] = tf or G.timeframe_of(sp.get("params"), str(sp.get("family") or ""))
            eligible.append(sp)
    census["eligible"] = len(eligible)
    # The memo is left holding exactly this docket's cells, so it never outgrows the docket.
    current = {h for h, _sp in hashed}
    for h in [h for h in memo if h not in current]:
        del memo[h]
    return eligible, census


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
    """The sealed nine-key sort (see SEALED_SORT_KEY_SOURCE). Requires `stamp_new` first."""
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
        bool(sp.get("prejudge_flagged")),
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
    keep, tilt = priority_tilt(keep, load_priority(G))
    return keep, {"eligible": len(specs), "never_judged": n_new, "banned_set_aside": n_banned,
                  "novelty_set_aside": n_redundant, "keep": len(keep),
                  "keep_never_judged": sum(1 for sp in keep if sp.get("_never_judged")),
                  "outside_keep": len(ordered) - len(keep) if len(ordered) >= len(keep) else 0,
                  "priority_tilt": tilt,
                  "order": "sealed: never-judged, intraday, CEO family, least-covered bucket, "
                           "symbol rotation; then ban set-aside, novelty head, yield trim; "
                           "then the bounded originality / cross-source / information-gain "
                           "tilt inside the kept set (membership unchanged)"}


# ---------------------------------------------------------------------------------------------
# THE PRIORITY TILT (H2 originality quota, H4 cross-source, H5 information gain; 2026-11-18).
#
# WHAT IT MAY CHANGE: the ORDER of `keep` -- the cells the next sweep reads -- and nothing else.
# Membership is the sealed trim's, every cell stays in the docket, and no gate, verdict or
# certificate reads any of it. The warmer builds `keep` in this order and the sealed sweep judges
# every CACHED cell, so the order decides which cells are judged FIRST when the gate room is
# short; it can never decide whether a cell is judged correctly.
#
# BOUNDED BY CONSTRUCTION. Each cell's sort key is its sealed position (as a fraction of `keep`)
# minus TILT_MAX x blend, blend in [0, 1] the mean of three published scores, so no cell moves up
# by more than TILT_MAX of the docket. The ORIGINAL quota then keeps the share of ORIGINAL rows in
# every prefix at ORIGINAL_QUOTA or above while ORIGINAL rows remain within QUOTA_REACH, pulling
# rows of a not-yet-seen mechanism fingerprint first.
#
# REVERT: env JUDGE_DOCKET_TILT=0, or the file desks/mt5/data/DOCKET_TILT_DISABLED. A lookup that
# is missing, unreadable, of another version or older than PRIORITY_MAX_AGE_S tilts nothing and
# says so in the census (UNMEASURED is a verdict, never a silent default).
# ---------------------------------------------------------------------------------------------

#: The lookup `research/docket_priority.py` writes every hour, relative to the repo root.
PRIORITY_LOOKUP = ("desks", "mt5", "data", "docket_priority.json")
PRIORITY_VERSION = 1
PRIORITY_MAX_AGE_S = 6 * 3600
TILT_DISABLED_FILE = ("desks", "mt5", "data", "DOCKET_TILT_DISABLED")


def _env_frac(name: str, default: float, hi: float = 0.5) -> float:
    try:
        v = float(os.environ.get(name, str(default)))
    except ValueError:
        v = default
    return min(max(v, 0.0), hi)


#: The most any cell may move up, as a fraction of `keep`.
TILT_MAX = _env_frac("JUDGE_DOCKET_TILT_MAX", 0.25)
#: The share of every prefix the ORIGINAL quota keeps for ORIGINAL rows.
ORIGINAL_QUOTA = _env_frac("JUDGE_DOCKET_ORIGINAL_QUOTA", 0.10)
#: How far (fraction of `keep`) the quota may pull a row forward.
QUOTA_REACH = 0.5


def load_priority(G: Any, *, now: float | None = None) -> dict | None:
    """The hourly lookup, or a dict with `_unmeasured` naming why it cannot be used."""
    import time as _time

    base = getattr(G, "BASE", None)
    if base is None:
        return {"_unmeasured": "no repo root on the judge module"}
    if os.environ.get("JUDGE_DOCKET_TILT", "1") == "0":
        return {"_unmeasured": "disabled: JUDGE_DOCKET_TILT=0"}
    if Path(base).joinpath(*TILT_DISABLED_FILE).exists():
        return {"_unmeasured": "disabled: DOCKET_TILT_DISABLED present"}
    path = Path(base).joinpath(*PRIORITY_LOOKUP)
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {"_unmeasured": f"{path.name} absent or unreadable"}
    if not isinstance(doc, dict) or doc.get("version") != PRIORITY_VERSION:
        return {"_unmeasured": f"{path.name} is not version {PRIORITY_VERSION}"}
    age = (now if now is not None else _time.time()) - float(doc.get("at_epoch") or 0.0)
    if age > PRIORITY_MAX_AGE_S:
        return {"_unmeasured": f"{path.name} is {age / 3600:.1f}h old "
                               f"(limit {PRIORITY_MAX_AGE_S / 3600:.0f}h)"}
    return doc


def _scores(DP: Any, sp: dict, original: set[str], agreement: dict,
            info: dict) -> tuple[float, float, float, bool]:
    """(original, cross-source, information gain) in [0, 1] for one cell, and ORIGINAL?"""
    fam = str(sp.get("family") or "")
    params = sp.get("params") or {}
    orig = DP.cell_key(sp.get("sym"), fam, params) in original
    n = int(agreement.get(DP.mech_key(sp.get("sym"), fam)) or 0)
    cross = min(1.0, (n - 1) / 2.0) if n >= 2 else 0.0
    tf_own = str(params.get("timeframe") or "H1").upper()
    ig = info.get(f"{fam}|{sp.get('tf') or tf_own}")
    if ig is None:
        ig = info.get(f"{fam}|{tf_own}")
    return (1.0 if orig else 0.0), cross, min(1.0, max(0.0, float(ig or 0.0))), orig


#: How many ORIGINAL rows the quota scans for a not-yet-placed fingerprint before taking the next.
_QUOTA_SCAN = 256


def priority_tilt(keep: list[dict], prio: dict | None) -> tuple[list[dict], dict]:
    """`keep` reordered by the bounded tilt and the ORIGINAL quota; same cells, same count."""
    n = len(keep)
    if not prio or prio.get("_unmeasured") or n < 2:
        why = (prio or {}).get("_unmeasured") or ("no lookup" if not prio else "fewer than 2")
        return keep, {"status": "DISABLED" if "disabled" in str(why) else "UNMEASURED",
                      "why": why, "moved": 0}
    try:
        import docket_priority as DP
        from originality_share import mechanism_fingerprint
        original = set(prio.get("original") or [])
        agreement = dict(prio.get("agreement") or {})
        info = dict(prio.get("info_gain") or {})
        scored = [_scores(DP, sp, original, agreement, info) for sp in keep]
    except Exception as exc:          # a broken lookup must never cost the sweep its docket
        return keep, {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}", "moved": 0}
    blend = [(o + c + i) / 3.0 for o, c, i, _orig in scored]
    idx = sorted(range(n), key=lambda k: (k / (n - 1) - TILT_MAX * blend[k], k))
    # THE ORIGINAL QUOTA: every prefix keeps ORIGINAL_QUOTA of ORIGINAL rows while one remains
    # within QUOTA_REACH of the head; a row of a fingerprint not yet placed is pulled first.
    reach = max(1, int(QUOTA_REACH * n))
    at = {k: p for p, k in enumerate(idx)}
    origs = [k for k in idx if scored[k][3]]
    fps = {k: mechanism_fingerprint(keep[k]) for k in origs}
    taken = [False] * n
    out: list[int] = []
    seen_fp: set[str] = set()
    mptr = optr = placed_orig = pulled = 0
    while len(out) < n:
        while taken[idx[mptr]]:
            mptr += 1
        while optr < len(origs) and taken[origs[optr]]:
            optr += 1
        k = idx[mptr]
        if (placed_orig < ORIGINAL_QUOTA * (len(out) + 1) and not scored[k][3]
                and optr < len(origs) and at[origs[optr]] - mptr < reach):
            first = None
            for c in origs[optr:optr + _QUOTA_SCAN]:
                if taken[c] or at[c] - mptr >= reach:
                    continue
                if first is None:
                    first = c
                if fps[c] not in seen_fp:
                    first = c
                    break
            if first is not None:
                k = first
                pulled += 1
        taken[k] = True
        out.append(k)
        if scored[k][3]:
            placed_orig += 1
            seen_fp.add(fps[k])
    moves = [k - pos for pos, k in enumerate(out)]
    up = [m for m in moves if m > 0]
    new = [keep[k] for k in out]
    head = max(1, min(n, 1000))
    return new, {
        "status": "APPLIED", "lookup_at": prio.get("at"),
        "tilt_max": TILT_MAX, "original_quota": ORIGINAL_QUOTA,
        "moved": sum(1 for m in moves if m != 0), "moved_up": len(up),
        "max_up": max(up, default=0), "mean_up": round(sum(up) / len(up), 1) if up else 0.0,
        "quota_pulls": pulled,
        "original_rows": sum(1 for s in scored if s[3]),
        "cross_source_rows": sum(1 for s in scored if s[1] > 0),
        "info_gain_scored": sum(1 for s in scored if s[2] > 0),
        "head_original_share": round(sum(1 for k in out[:head] if scored[k][3]) / head, 4),
        "head_original_share_before": round(sum(1 for s in scored[:head] if s[3]) / head, 4)}
