"""THE BREADTH ENFORCER: saturated families get an exploration floor, the unknown get the front.

    "make sure the breadth mining discovering enforcer 24/7 is working where families or saturated
     things already like 10 families currently in certies don't get mined n unknowns r forced to be
     mined instead etc optimally intelligently fr maximum breadth goal of mechanisms"
                                                                  -- the principal, 2026-10-13

WHAT WAS WRONG, MEASURED 2026-10-13 ON THE BOX'S OWN REGISTRY (`data/sleeves.json`, 900 rows). Ten
families hold 880 of 891 family-stamped certificates: cross_asset_residual 346, carry 155,
macro_conditional 153, formula 87, discovered 32, overnight_gap_decay 31, clock_transition 27,
spread_state 17, session_range_breakout 16, pca_residual 16. Many organs already MEASURED that
(judge_coverage's certified_breadth_factor, docket_keff, breadth_sweep's cert-ascending key), but
each one was a soft multiplier inside its own ranking. No organ guaranteed a share, the sealed
judge's yield split (`external_gauntlet.allocate_by_yield`) handed the MOST budget to the families
with the MOST certificates, and no fence fired when mining drifted back onto known ground.

WHAT THIS DOES, hourly (leg `breadth_enforcer`, core clock):

  1. MEASURES the saturated set: every family whose certificate count, read from the registry the
     box writes (`data/sleeves.json` rows carrying a `certificate`) and from both survivor files,
     is at least `SAT_MIN_CERTS`. Nothing is hard-coded; the list above is today's reading.
  2. CLASSIFIES every other family the desk knows (docket, gate ledger, the forward engine's
     registered families, the certified book): UNKNOWN (no certificate and almost no verdict, or
     never mined at all), UNDER_MINED (no saturation and mined below the median), EXPLORED. The
     FRONTIER is UNKNOWN + UNDER_MINED, ranked by the ontology frontier first (registered families
     nobody has minted), then measured incremental k_eff per judge-hour (docket_keff's family
     factor over the judge's own seconds per cell), then expected value per judge-second.
  3. PUBLISHES the steer every consumer obeys -- `reports/BREADTH_ENFORCER.json["steer"]` -- and
     the two primitives they obey it with: `allocate_with_steer` logic lives in
     `judge_coverage.allocate(steer=...)`, and `apportion()` below is what a capped producer calls
     before it truncates.
  4. MEASURES the share of mining that went to saturated / frontier / other families, per
     producer (mint lens), for the judge's hour (`JUDGE_COVERAGE.json` quota) and for the sealed
     gauntlet's build split (`RESEARCH_ALLOCATION.json`), and carries a replay of the judge quota
     under the steer beside the quota that shipped, so before/after is on the page every hour.
  5. Carries the MISSED-GROWTH LINES of the redirect: per saturated family, the judge cells moved
     off it, their expected value and expected certificates, against what the frontier gained.

THE TWO RULES IT KEEPS (GROWTH_GOVERNANCE; "never reduce mining"):

  * TOTAL MINING IS NEVER REDUCED. Both primitives are WORK-CONSERVING: a saturated family loses
    only the place that a non-saturated cell takes; when the frontier and the explored ground
    cannot fill the budget, saturated cells fill the rest. No row is dropped anywhere.
  * SATURATED IS NEVER ZERO. Every saturated family keeps judge_coverage's per-family floor, and
    the saturated set together keeps `SAT_EXPLORE_SHARE` of every budget, interleaved so every
    prefix carries it -- a saturated family can still mint the variant that breaks its ceiling.

UNMEASURED IS NEVER A VERDICT (L1.28a). No readable certificate source: no family is saturated,
the steer says UNMEASURED and every consumer behaves exactly as it did before this organ existed.

    python desks/mt5/research/breadth_enforcer.py            # measure + write the report
    python desks/mt5/research/breadth_enforcer.py --json     # and print it
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = BASE / "reports"
OUT = REPORTS / "BREADTH_ENFORCER.json"
SLEEVES = BASE / "data" / "sleeves.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
JUDGE_COVERAGE = REPORTS / "JUDGE_COVERAGE.json"
PRODUCER_BREADTH = REPORTS / "PRODUCER_BREADTH.json"
RESEARCH_ALLOCATION = REPORTS / "RESEARCH_ALLOCATION.json"
BREADTH_SWEEP = REPORTS / "BREADTH_SWEEP.json"
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"

UNMEASURED = "UNMEASURED"
SATURATED, UNKNOWN, UNDER_MINED, EXPLORED = "SATURATED", "UNKNOWN", "UNDER_MINED", "EXPLORED"
FRONTIER = frozenset({UNKNOWN, UNDER_MINED})

#: A family holding this many certificates is SATURATED ground: the next certificate there buys a
#: fraction of an effective bet (k_eff = n/(1+(n-1)rho) is concave in n). The THRESHOLD is a
#: parameter; WHICH families clear it is measured every pass.
SAT_MIN_CERTS = 10
#: The share of any mining budget the saturated set TOGETHER keeps while non-saturated work
#: exists -- the exploration floor, so a saturated family can still mint its breaking variant.
SAT_EXPLORE_SHARE = 0.10
#: The share of any mining budget the frontier is owed, bounded by what the frontier HOLDS: a
#: target the frontier's own backlog cannot fill is a minting debt, not a judge failure.
FRONTIER_TARGET_SHARE = 0.50
#: The share the UNKNOWN class alone is owed (inside the frontier's), bounded the same way.
UNKNOWN_TARGET_SHARE = 0.25
#: How far a measured share may drift past its bound before the fence fails.
SHARE_TOLERANCE = 0.05
#: A family with no certificate and fewer judged verdicts than this is UNKNOWN: the desk has not
#: asked it enough questions to call it barren.
UNKNOWN_JUDGED_MAX = 100
#: Mint-lens window, and the most bytes of docket this organ will load when the per-producer
#: census (`PRODUCER_BREADTH.json`) is absent.
MINT_WINDOW_H = 24.0
MAX_DOCKET_BYTES = 512 * 1024 * 1024
#: WHO OBEYS THE STEER, AND HOW. Read by the fence and published in the report.
OBEYING = {
    "judge_coverage": "judge_coverage.allocate(steer=...): saturated quota held to floor + "
                      "SAT_EXPLORE_SHARE, frontier walked first in the remainder (the docket "
                      "order merge_hypotheses ships)",
    "breadth_sweep": "breadth_sweep.cells(): apportion() before the MAX_NEW_PER_RUN cap",
    "frontier_ceo": "frontier_ceo._missing_families(): the ranked frontier becomes CEO_DOCKET "
                    "family proposals, which the SEALED gauntlet's _ceo_rank serves first; a "
                    "stale gap the steer calls SATURATED is dropped",
    "proposer_seat": "proposer_seat.build_prompt(): saturated named as floor-only, frontier as "
                     "the target (every organ that asks a seat through the one composer)",
    "deepseek": "deepseek_cycle cold prompt carries the same breadth lines",
    "kimi": "kimi_hunter system prompt carries the same breadth lines",
}
#: Mint-lens producers whose head is GUARANTEED by `apportion()`: their saturated share drifting
#: past the floor is a FAILURE. Every other producer is measured and named, never failed --
#: a prompt can be ignored, and a producer that has not been wired cannot be blamed for it.
MINT_ENFORCED = frozenset({"breadth_sweep"})
#: Why the rest do not obey yet, by name, so the gap is a list and not a silence.
NOT_YET_OBEYING = {
    "external_gauntlet": "SEALED: allocate_by_yield gives MORE build budget to certificate-rich "
                         "families (YIELD_MAX_SHARE 0.45) and ORTHOGONAL_FAMILIES forces 60 "
                         "cross_asset_residual-inclusive cells a sweep; the fix is "
                         "patches/breadth_enforcer_judge_yield.patch, not committable here",
    "family-fixed miners": "cot_*, cross_sectional_class_*, session_structure, event lanes ... "
                           "mint ONE family by construction; their family is their mechanism, "
                           "so the steer acts on them at the judge and the CEO order, not at mint",
    "high-volume generic producers": "card_explosion, moat_factory, free_stack_proposer, "
                                     "alpha_recombination, conversion_maximiser: not wired to "
                                     "apportion() in this change; measured per producer in "
                                     "mint.producers",
}


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _ts(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")
    except OSError:
        return None


# ------------------------------------------------------------------------------ certificates
def _family_of_key(key: str) -> str:
    """`external.<SYM>.<family>.p=...` or `<SYM>.<family>.p=...` -> family."""
    parts = str(key).split(".")
    if parts and parts[0] == "external" and len(parts) >= 3:
        return parts[2]
    return parts[1] if len(parts) >= 2 else ""


def _survivor_counts(path: Path) -> dict[str, int] | None:
    doc = _read(path)
    rows = doc.get("survivors") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return None
    out: Counter[str] = Counter()
    for key, cert in rows.items():
        if not isinstance(cert, dict):
            continue
        _sp = cert.get("shadow_spec")
        spec: dict[str, Any] = _sp if isinstance(_sp, dict) else {}
        fam = str(spec.get("family") or cert.get("family") or _family_of_key(key) or "")
        if fam:
            out[fam] += 1
    return dict(out)


def _sleeve_counts(path: Path) -> dict[str, int] | None:
    doc = _read(path)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return None
    out: Counter[str] = Counter()
    for row in rows:
        if isinstance(row, dict) and row.get("certificate") and row.get("family"):
            out[str(row["family"])] += 1
    return dict(out)


def certificate_counts(sleeves: Path | None = None, survivors: Path | None = None,
                       canon: Path | None = None) -> tuple[dict[str, int], dict[str, Any]]:
    """Certificates per family: the MAX over every readable source, each source named.

    MAX, not sum: the registry and the survivor files describe overlapping certificates, and the
    registry the box writes is normally the largest. A source that cannot be read is recorded as
    such; when none can, the counts are empty and the caller reports UNMEASURED.
    """
    srcs = {"sleeves_registry": (sleeves or SLEEVES, _sleeve_counts),
            "universal_survivors": (survivors or SURVIVORS, _survivor_counts),
            "survivors_canon": (canon or CANON, _survivor_counts)}
    best: dict[str, int] = {}
    basis: dict[str, str] = {}
    meta: dict[str, Any] = {}
    for name, (path, fn) in srcs.items():
        counts = fn(path)
        meta[name] = {"path": str(path.relative_to(BASE)) if path.is_relative_to(BASE)
                      else str(path), "mtime": _mtime(path),
                      "certificates": sum(counts.values()) if counts is not None else UNMEASURED}
        for fam, n in (counts or {}).items():
            if n > best.get(fam, 0):
                best[fam], basis[fam] = n, name
    return best, {"sources": meta, "basis_by_family": basis}


def _banned() -> frozenset[str]:
    try:
        from mt5desk.live_policy import DEFAULT_BANNED_FAMILIES
        return frozenset(str(f) for f in DEFAULT_BANNED_FAMILIES)
    except Exception:
        return frozenset()


# ------------------------------------------------------------------------------ the steer
def build_steer(certs: Mapping[str, int], judge: Mapping[str, Any] | None,
                extra_families: Iterable[str] = ()) -> dict[str, Any]:
    """Classify every known family and rank the frontier. Pure: artifacts in, steer out."""
    jc = judge if isinstance(judge, dict) else {}
    _tb = jc.get("families")
    table: dict[str, Any] = _tb if isinstance(_tb, dict) else {}
    unmined = {str(f) for f in (jc.get("unmined_live_families") or []) if f}
    ranking = {str(r.get("family")): r for r in (jc.get("value_ranking") or [])
               if isinstance(r, dict) and r.get("family")}
    fams = ({str(f) for f in table} | set(certs) | unmined | set(ranking)
            | {str(f) for f in extra_families if f})
    fams.discard("")
    if not certs:
        return {"status": UNMEASURED, "why": "no certificate source readable -- nothing is "
                "saturated by absence, every consumer stays exactly as it was",
                "saturated": [], "frontier": [], "classes": {}}
    banned = _banned()
    sat = sorted((f for f in fams if certs.get(f, 0) >= SAT_MIN_CERTS),
                 key=lambda f: (-certs.get(f, 0), f))
    mined_ns = [int((table.get(f) or {}).get("mined") or 0) for f in fams
                if f not in sat and isinstance(table.get(f), dict)]
    median_mined = statistics.median(mined_ns) if mined_ns else 0.0
    classes: dict[str, str] = {}
    detail: dict[str, dict[str, Any]] = {}
    for f in sorted(fams):
        _row = table.get(f)
        row: dict[str, Any] = _row if isinstance(_row, dict) else {}
        mined = int(row.get("mined") or 0)
        judged = int(row.get("judged_total") or 0)
        n_cert = int(certs.get(f, 0))
        if n_cert >= SAT_MIN_CERTS:
            cls = SATURATED
        elif n_cert == 0 and (judged < UNKNOWN_JUDGED_MAX or mined == 0 or f in unmined):
            cls = UNKNOWN
        elif mined < median_mined:
            cls = UNDER_MINED
        else:
            cls = EXPLORED
        classes[f] = cls
        vr = ranking.get(f) or {}
        kf = float(vr.get("keff_factor") or 1.0)
        cost_s = float(vr.get("cost_s_per_cell") or 0.0)
        keff_per_judge_h = ((kf - 1.0) * 3600.0 / cost_s) if cost_s > 0 else None
        detail[f] = {"class": cls, "certificates": n_cert, "mined": mined,
                     "judged_total": judged, "unjudged": int(row.get("unjudged") or 0),
                     "ontology_unmined": f in unmined, "banned_from_capital": f in banned,
                     "keff_factor": round(kf, 4),
                     "keff_per_judge_hour": (round(keff_per_judge_h, 4)
                                             if keff_per_judge_h is not None else UNMEASURED),
                     "ev_per_judge_second": vr.get("ev_per_judge_second")}

    def _frontier_key(f: str) -> tuple[Any, ...]:
        d = detail[f]
        kph = d["keff_per_judge_hour"]
        ev = d["ev_per_judge_second"]
        return (0 if d["class"] == UNKNOWN else 1, 0 if d["ontology_unmined"] else 1,
                -(kph if isinstance(kph, (int, float)) else 0.0),
                -(float(ev) if isinstance(ev, (int, float)) else 0.0), f)
    frontier = sorted((f for f, c in classes.items() if c in FRONTIER and f not in banned),
                      key=_frontier_key)
    total = sum(certs.values())
    return {
        "status": "MEASURED",
        "rule": (f"SATURATED = >= {SAT_MIN_CERTS} certificates (max over the registry and both "
                 f"survivor files); UNKNOWN = no certificate and < {UNKNOWN_JUDGED_MAX} judged "
                 f"verdicts, or never mined, or a registered family nobody mints; UNDER_MINED = "
                 f"below the median mined count of non-saturated families; frontier ranked "
                 f"UNKNOWN first, ontology-unmined first, then incremental k_eff per judge-hour, "
                 f"then ev per judge-second"),
        "params": {"sat_min_certs": SAT_MIN_CERTS, "sat_explore_share": SAT_EXPLORE_SHARE,
                   "frontier_target_share": FRONTIER_TARGET_SHARE,
                   "share_tolerance": SHARE_TOLERANCE, "unknown_judged_max": UNKNOWN_JUDGED_MAX,
                   "unknown_target_share": UNKNOWN_TARGET_SHARE},
        "saturated": sat,
        "saturated_certificates": {f: certs.get(f, 0) for f in sat},
        "saturated_certificate_share": (round(sum(certs.get(f, 0) for f in sat) / total, 4)
                                        if total else None),
        "frontier": frontier,
        "unknown": sorted(f for f, c in classes.items() if c == UNKNOWN),
        "under_mined": sorted(f for f, c in classes.items() if c == UNDER_MINED),
        "ontology_unmined": sorted(unmined),
        "median_mined_non_saturated": median_mined,
        "classes": classes,
        "families": detail,
    }


def class_of(family: str, steer: Mapping[str, Any] | None) -> str:
    """A family's class under the steer. A family the steer has NEVER SEEN is UNKNOWN -- that is
    what unseen means. With no measured steer every family is EXPLORED (par, L1.28a)."""
    if not steer or steer.get("status") != "MEASURED":
        return EXPLORED
    return str((steer.get("classes") or {}).get(str(family), UNKNOWN))


def load_steer(path: Path | None = None, *, max_age_h: float = 6.0) -> dict[str, Any] | None:
    """The published steer, or None when absent, unmeasured or older than `max_age_h` -- a stale
    steer must not keep steering after the organ that writes it has stopped."""
    doc = _read(path or OUT)
    st = doc.get("steer") if isinstance(doc, dict) else None
    if not isinstance(st, dict) or st.get("status") != "MEASURED":
        return None
    at = _ts(doc.get("generated_utc"))
    if at is None or (_now() - at) > timedelta(hours=max_age_h):
        return None
    return st


# ------------------------------------------------------------------------------ the primitive
def apportion(rows: list[Any], budget: int, steer: Mapping[str, Any] | None = None, *,
              family: Callable[[Any], str] | None = None) -> list[Any]:
    """Reorder `rows` so the first `budget` hold the frontier first and the saturated set at its
    exploration floor -- WORK-CONSERVING and lossless.

    Returns every row (same multiset). Inside the head: frontier rows (producer's own order kept),
    then explored rows, with saturated rows interleaved evenly at `SAT_EXPLORE_SHARE` of the
    budget -- or more, when the non-saturated rows cannot fill it. Saturated rows beyond that go
    after the head, where a later pass reaches them. No measured steer: the input order, as is.
    """
    st = steer if steer is not None else load_steer()
    if not st or st.get("status") != "MEASURED" or budget <= 0 or not rows:
        return list(rows)
    fam = family or (lambda r: str((r or {}).get("family") or ""))
    fr: list[Any] = []
    ex: list[Any] = []
    sa: list[Any] = []
    for r in rows:
        c = class_of(fam(r), st)
        (sa if c == SATURATED else fr if c in FRONTIER else ex).append(r)
    nonsat = fr + ex
    n_sat = min(len(sa), max(math.ceil(SAT_EXPLORE_SHARE * budget),
                             budget - len(nonsat)))
    head_ns = nonsat[:max(0, budget - n_sat)]
    head = _interleave(head_ns, sa[:n_sat])
    return head + nonsat[len(head_ns):] + sa[n_sat:]


def _interleave(major: list[Any], minor: list[Any]) -> list[Any]:
    """`minor` spread evenly through `major`, so every prefix carries its share."""
    if not minor:
        return list(major)
    if not major:
        return list(minor)
    out: list[Any] = []
    step = (len(major) + len(minor)) / len(minor)
    slots = {int(i * step) for i in range(len(minor))}
    mi = iter(minor)
    ma = iter(major)
    for i in range(len(major) + len(minor)):
        nxt = next(mi, None) if i in slots else next(ma, None)
        if nxt is None:
            nxt = next(ma, None) if i in slots else next(mi, None)
        out.append(nxt)
    return out


def steer_walk(ranking: list[dict[str, Any]], live: Mapping[str, int],
               steer: Mapping[str, Any]) -> list[str]:
    """The order the remainder is walked under the steer: frontier (steer rank), then explored
    (the ranking's own value order), then saturated (value order). Every live family appears."""
    rank = {f: i for i, f in enumerate(steer.get("frontier") or [])}
    walk = [str(r.get("family") or "") for r in ranking]
    seen = set(walk)
    walk += sorted(f for f in live if f not in seen)

    def tier(f: str) -> int:
        if f in rank:
            return 0
        return 2 if class_of(f, steer) == SATURATED else 1
    idx = {f: i for i, f in enumerate(walk)}
    return sorted(walk, key=lambda f: (tier(f), rank.get(f, 0), idx[f]))


def steer_quota(quota: dict[str, int], live: Mapping[str, int], capacity: int,
                ranking: list[dict[str, Any]], steer: Mapping[str, Any]) -> dict[str, int]:
    """judge_coverage's remainder walk under the steer. `quota` holds the per-family FLOOR already
    handed out (untouched); the spare goes frontier first (steer rank), then explored families
    (value order), then saturated families up to SAT_EXPLORE_SHARE of the hour in total, and
    finally -- work-conserving -- saturated families again if anything is left."""
    q = dict(quota)
    spare = capacity - sum(q.values())
    if spare <= 0:
        return q
    walk = steer_walk(ranking, live, steer)
    order = list(range(len(walk)))
    sat = {f for f in live if class_of(f, steer) == SATURATED}
    sat_room = max(0, int(capacity * SAT_EXPLORE_SHARE) - sum(q.get(f, 0) for f in sat))

    def _take(fam: str, limit: int | None) -> int:
        room = live.get(fam, 0) - q.get(fam, 0)
        t = max(0, min(room, spare, limit if limit is not None else room))
        q[fam] = q.get(fam, 0) + t
        return t
    for i in order:
        fam = walk[i]
        if spare <= 0:
            break
        if fam in sat:
            t = _take(fam, sat_room)
            sat_room -= t
        else:
            t = _take(fam, None)
        spare -= t
    for i in order:                                  # work-conserving: never leave the hour idle
        if spare <= 0:
            break
        if walk[i] in sat:
            spare -= _take(walk[i], None)
    return q


# ------------------------------------------------------------------------------ the shares
def shares(counts: Mapping[str, int], steer: Mapping[str, Any] | None) -> dict[str, Any]:
    n = sum(int(v) for v in counts.values())
    by: Counter[str] = Counter()
    for fam, v in counts.items():
        by[class_of(fam, steer)] += int(v)
    if not n:
        return {"n": 0, "status": UNMEASURED}
    return {"n": n, "saturated_share": round(by[SATURATED] / n, 4),
            "frontier_share": round((by[UNKNOWN] + by[UNDER_MINED]) / n, 4),
            "unknown_share": round(by[UNKNOWN] / n, 4),
            "under_mined_share": round(by[UNDER_MINED] / n, 4),
            "explored_share": round(by[EXPLORED] / n, 4), "status": "MEASURED"}


def judge_bounds(live: Mapping[str, int], capacity: int,
                 steer: Mapping[str, Any], floor_share: float = 0.0) -> dict[str, float]:
    """The bounds a budget of `capacity` cells must keep, given what the pool `live` (cells per
    family available to it) can actually supply. Work-conserving: when non-saturated cells
    cannot fill the budget, saturated cells fill it, and that is mining kept whole, not drift;
    a frontier or unknown target the pool cannot fill is a MINTING debt, not a judge failure.
    `floor_share` is judge_coverage's equal per-family floor: the saturated families' own floors
    are never cut, so their sum is part of the bound."""
    if capacity <= 0:
        return {"saturated_max": 1.0, "frontier_min": 0.0, "unknown_min": 0.0}
    nonsat = sum(n for f, n in live.items() if class_of(f, steer) != SATURATED)
    front = sum(n for f, n in live.items() if class_of(f, steer) in FRONTIER)
    unk = sum(n for f, n in live.items() if class_of(f, steer) == UNKNOWN)
    n_live = sum(1 for n in live.values() if n > 0)
    n_sat = sum(1 for f, n in live.items() if n > 0 and class_of(f, steer) == SATURATED)
    floors = floor_share * n_sat / n_live if n_live else 0.0
    sat_max = max(SAT_EXPLORE_SHARE + floors, 1.0 - nonsat / capacity)
    return {"saturated_max": round(min(1.0, sat_max), 4),
            "frontier_min": round(min(FRONTIER_TARGET_SHARE, front / capacity), 4),
            "unknown_min": round(min(UNKNOWN_TARGET_SHARE, unk / capacity), 4)}


def _floor_share() -> float:
    try:
        from research.judge_coverage import FLOOR_SHARE
        return float(FLOOR_SHARE)
    except Exception:
        return 0.0


def judge_lens(jc: Mapping[str, Any] | None, steer: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(jc, dict) or not jc.get("quota"):
        return {"status": UNMEASURED, "why": "JUDGE_COVERAGE.json absent or carries no quota"}
    quota = {str(k): int(v) for k, v in (jc.get("quota") or {}).items()}
    fams = jc.get("families") or {}
    live = {f: int((r or {}).get("unjudged") or 0) for f, r in fams.items()
            if int((r or {}).get("unjudged") or 0) > 0 and f in quota}
    capacity = int((jc.get("totals") or {}).get("capacity_measured") or sum(quota.values()))
    out: dict[str, Any] = {"status": "MEASURED", "at": jc.get("at"), "capacity": capacity,
                           "shipped": shares(quota, steer),
                           "steer_in_force": bool((jc.get("breadth_steer") or {}).get("in_force")),
                           "bounds": judge_bounds(live, capacity, steer, _floor_share())}
    # THE REPLAY: the same backlog, capacity and value ranking, allocated under the steer.
    try:
        from research import judge_coverage as jcm
        # The published list is in WALK order once the steer is in force; the legacy replay
        # needs the value order back, which is the `rank` every row carries.
        ranking = sorted((r for r in (jc.get("value_ranking") or []) if isinstance(r, dict)),
                         key=lambda r: int(r.get("rank") or 0))
        after = jcm.allocate(live, capacity, ranking=ranking, steer=dict(steer))
        legacy = jcm.allocate(live, capacity, ranking=ranking)
        out["legacy_replay"] = shares(legacy, steer)
        out["steered_replay"] = shares(after, steer)
        out["missed_growth_lines"] = missed_growth_lines(legacy, after, ranking, steer)
        out["total_cells_legacy"] = sum(legacy.values())
        out["total_cells_steered"] = sum(after.values())
    except Exception as exc:
        out["replay"] = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:200]}
    return out


def missed_growth_lines(before: Mapping[str, int], after: Mapping[str, int],
                        ranking: list[dict[str, Any]], steer: Mapping[str, Any]
                        ) -> list[dict[str, Any]]:
    """What the redirect moved, priced in the ranking's own units (ev per cell, P(pass))."""
    by = {str(r.get("family")): r for r in ranking}
    lines: list[dict[str, Any]] = []
    gained_cells = 0
    gained_ev = 0.0
    gained_p = 0.0
    for fam in sorted(set(before) | set(after)):
        d = int(after.get(fam, 0)) - int(before.get(fam, 0))
        r = by.get(fam) or {}
        ev = float(r.get("ev_per_cell") or 0.0)
        p = float(r.get("p") or 0.0)
        if d < 0 and class_of(fam, steer) == SATURATED:
            lines.append({"rail": "breadth_enforcer.saturated_explore_floor", "family": fam,
                          "cells_moved_off": -d, "ev_moved_off": round(-d * ev, 6),
                          "expected_certificates_moved_off": round(-d * p, 4),
                          "verdict": "REDIRECT_NOT_REDUCTION"})
        elif d > 0:
            gained_cells += d
            gained_ev += d * ev
            gained_p += d * p
    if lines:
        lines.append({"rail": "breadth_enforcer.frontier_front", "family": "*frontier+explored*",
                      "cells_moved_on": gained_cells, "ev_moved_on": round(gained_ev, 6),
                      "expected_certificates_moved_on": round(gained_p, 4),
                      "why": ("the same judge hour, re-spent on families whose next certificate "
                              "adds an independent bet rather than a correlated copy")})
    return lines


def verdict_lens(jc: Mapping[str, Any] | None, steer: Mapping[str, Any],
                 ledger: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """WHAT THE SEALED JUDGE ACTUALLY RULED ON, per family: the gate ledger's real verdicts over
    the last MINT_WINDOW_H (judge_coverage.judged_index, the same filter), falling back to
    JUDGE_COVERAGE's per-family judged counts with the basis named. This is the judge's real
    mining -- the quota above is only the order it was handed, and the sealed gauntlet re-sorts."""
    counts: dict[str, int] = {}
    basis = ""
    try:
        from research import judge_coverage as jcm
        path = ledger or jcm.GATE_LEDGER
        if path.exists():
            _seen, _total, win = jcm.judged_index(path, now=now, window_h=MINT_WINDOW_H)
            counts, basis = dict(win), f"gate_verdict_ledger, last {MINT_WINDOW_H:g}h"
    except Exception as exc:
        basis = f"ledger unreadable ({type(exc).__name__})"
    if not counts and isinstance(jc, dict):
        fams = jc.get("families") or {}
        win = {f: int((r or {}).get("judged_window") or 0) for f, r in fams.items()}
        if sum(win.values()):
            counts, basis = win, f"JUDGE_COVERAGE judged_window at {jc.get('at')}"
        else:
            counts = {f: int((r or {}).get("judged_total") or 0) for f, r in fams.items()}
            basis = (f"JUDGE_COVERAGE judged_total (all verdicts the ledger holds) at "
                     f"{jc.get('at')} -- no verdict inside the window on this host")
    s = shares(counts, steer)
    s["basis"] = basis
    return s


def gauntlet_lens(steer: Mapping[str, Any], path: Path | None = None) -> dict[str, Any]:
    doc = _read(path or RESEARCH_ALLOCATION)
    by = doc.get("by_family") if isinstance(doc, dict) else None
    if not isinstance(by, dict):
        return {"status": UNMEASURED, "why": "RESEARCH_ALLOCATION.json absent on this host"}
    built = {f: int((r or {}).get("built_this_sweep") or 0) for f, r in by.items()}
    pool = {f: int((r or {}).get("docket") or 0) for f, r in by.items()}
    return {"status": "MEASURED", "at": doc.get("generated_utc"),
            "steer_in_force": bool(doc.get("breadth_steer")),
            "built": shares(built, steer),
            "bounds": judge_bounds(pool, sum(built.values()), steer),
            "note": ("the sealed judge's yield split; it obeys the steer only once "
                     "patches/breadth_enforcer_judge_yield.patch is applied (steer_in_force)")}


def _producer_of(row: Mapping[str, Any]) -> str:
    p = str(row.get("producer") or row.get("source") or "?")
    return p.split(":", 1)[-1] if p.startswith("miner:") else p


def mint_lens(steer: Mapping[str, Any], *, census: Path | None = None,
              docket: Path | None = None) -> dict[str, Any]:
    """Per producer, the families it minted. PRODUCER_BREADTH (7d, every producer) first; the
    docket's own `producer` stamps over its newest MINT_WINDOW_H otherwise."""
    pb = _read(census or PRODUCER_BREADTH)
    per: dict[str, Counter[str]] = {}
    basis = ""
    if isinstance(pb, dict) and isinstance(pb.get("producers"), dict):
        for name, row in pb["producers"].items():
            fams = ((row or {}).get("covered") or {}).get("families") or {}
            if isinstance(fams, dict) and fams:
                per[str(name)] = Counter({str(k): int(v) for k, v in fams.items()})
        basis = f"PRODUCER_BREADTH.json covered.families (7d), at {pb.get('generated_utc')}"
    if not per:
        path = docket or DOCKET
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        if 0 < size <= MAX_DOCKET_BYTES:
            rows = _read(path)
            rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
            stamps = [t for t in (_ts(r.get("first_seen")) for r in rows) if t is not None]
            newest = max(stamps) if stamps else None
            for r in rows:
                t = _ts(r.get("first_seen"))
                if newest is not None and (t is None or (newest - t).total_seconds()
                                           > MINT_WINDOW_H * 3600):
                    continue
                per.setdefault(_producer_of(r), Counter())[str(r.get("family") or "")] += 1
            basis = (f"docket producer stamps, newest {MINT_WINDOW_H:g}h by first_seen "
                     f"(newest {newest.isoformat(timespec='seconds') if newest else None}, "
                     f"docket mtime {_mtime(path)})")
        elif size > MAX_DOCKET_BYTES:
            basis = f"docket {size} bytes > MAX_DOCKET_BYTES and no PRODUCER_BREADTH census"
    if not per:
        return {"status": UNMEASURED, "why": basis or "no producer census and no docket"}
    bs = _read(BREADTH_SWEEP)
    if isinstance(bs, dict) and isinstance(bs.get("families"), dict):
        per.setdefault("breadth_sweep", Counter()).update(
            {str(k): int(v) for k, v in bs["families"].items()})
    total: Counter[str] = Counter()
    producers: dict[str, Any] = {}
    for name, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
        total.update(c)
        s = shares(c, steer)
        s["obeys_steer"] = name in OBEYING
        s["enforced"] = name in MINT_ENFORCED
        producers[name] = s
    return {"status": "MEASURED", "basis": basis, "all_producers": shares(total, steer),
            "producers": producers}


# ------------------------------------------------------------------------------ the pass
def build(now: datetime | None = None) -> dict[str, Any]:
    at = now or _now()
    certs, cmeta = certificate_counts()
    jc = _read(JUDGE_COVERAGE)
    steer = build_steer(certs, jc)
    doc: dict[str, Any] = {
        "generated_utc": at.isoformat(timespec="seconds"),
        "law": ("saturated families get an exploration floor of every mining budget; unknown and "
                "under-mined families are forced to the front; total mining is never reduced, "
                "only redirected (work-conserving, lossless)"),
        "certificates": {"by_family": dict(sorted(certs.items(), key=lambda kv: -kv[1])),
                         "total": sum(certs.values()), **cmeta},
        "steer": steer,
        "obeying": OBEYING, "mint_enforced": sorted(MINT_ENFORCED),
        "not_yet_obeying": NOT_YET_OBEYING,
    }
    if steer.get("status") != "MEASURED":
        doc["verdict"] = UNMEASURED
        return doc
    doc["judge"] = judge_lens(jc, steer)
    doc["gauntlet"] = gauntlet_lens(steer)
    doc["verdicts"] = verdict_lens(jc, steer, now=at)
    doc["verdicts"]["steer_in_force"] = bool((doc["gauntlet"] or {}).get("steer_in_force"))
    doc["mint"] = mint_lens(steer)
    doc["missed_growth_lines"] = (doc["judge"].get("missed_growth_lines") or [])
    doc["verdict"] = "MEASURED"
    return doc


def write(doc: dict[str, Any], out: Path | None = None) -> Path:
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def render(doc: dict[str, Any]) -> list[str]:
    st = doc.get("steer") or {}
    lines = [f"breadth enforcer {doc.get('generated_utc')}: {doc.get('verdict')}"]
    if st.get("status") != "MEASURED":
        return [*lines, f"  {st.get('why')}"]
    sc = st.get("saturated_certificates") or {}
    lines.append(f"  saturated ({len(sc)}): " + ", ".join(f"{f} {n}" for f, n in sc.items()))
    lines.append(f"  frontier ({len(st.get('frontier') or [])}), head: "
                 + ", ".join((st.get("frontier") or [])[:12]))
    j = doc.get("judge") or {}
    for k in ("shipped", "legacy_replay", "steered_replay"):
        s = j.get(k) or {}
        if s.get("status") == "MEASURED":
            lines.append(f"  judge {k:15s} saturated {s['saturated_share']:.3f}  frontier "
                         f"{s['frontier_share']:.3f}  unknown {s['unknown_share']:.3f}  "
                         f"(n={s['n']})")
    v = doc.get("verdicts") or {}
    if v.get("status") == "MEASURED":
        lines.append(f"  verdicts (sealed)   saturated {v['saturated_share']:.3f}  frontier "
                     f"{v['frontier_share']:.3f}  unknown {v['unknown_share']:.3f}  (n={v['n']}; "
                     f"{v.get('basis')})")
    m = (doc.get("mint") or {}).get("all_producers") or {}
    if m.get("status") == "MEASURED":
        lines.append(f"  mint all producers  saturated {m['saturated_share']:.3f}  frontier "
                     f"{m['frontier_share']:.3f}  (n={m['n']})")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    doc = build()
    path = write(doc, Path(a.out) if a.out else None)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print("\n".join(render(doc)))
        print(f"  -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
