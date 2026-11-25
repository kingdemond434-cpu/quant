"""SOURCE-FAMILY JUDGE FLOOR -- every alt-data source gets a minimum share of each pass's judge.

WHY (measured on JUDGE_COVERAGE.json, 2026-11-23T16:46Z). Desk-wide the judge has ruled on 49%
of what was mined (941,348 of 1,924,228 non-banned rows). The alt-data sources sit far below:

    source         mined     judged   judged/mined
    cot            25,993       938       3.6%
    tick_tape     104,360     1,627       1.6%
    event_analyst  10,149         0       0.0%

WHERE THE JUDGE'S SLOTS ARE ACTUALLY DECIDED. Not in `judge_coverage.allocate`: the sealed sweep
(`scripts/external_gauntlet.py`) re-sorts the whole docket by its own nine-key sort, whose last
keys are symbol, chart and family, so the docket's own family interleave survives only as a
stable-sort tie-break INSIDE one (symbol, chart, family) -- it sets no family's share. Then
`allocate_by_yield` concatenates each family's kept rows as one BLOCK, in the order each family
first appears, and the build budget (~250 cells an hour sustained) reaches only the head of that
list. So the only place a share-of-each-pass floor can act is that list, inside the sealed file.
`floor_interleave` below is the pure function for it; the sealed call site waits on SEAL CLEAR,
and until then `judge_coverage` publishes the decision (`source_floor` in JUDGE_COVERAGE.json)
with `enforced: false`, so nobody reads a proposal as a running organ (III.16).

THE RULE. Each source family (a declared group of member families, `SOURCE_FAMILY_FLOOR`) is
ACTIVE while its judged/mined ratio is below the desk-wide judged/mined ratio, and inactive at
parity. While active, every prefix of the judge's build list holds at least `min_share` of its
rows from that source's eligible members, for as long as those members have rows to give. When a
source has no rows left, its slots go back to everyone else in their own order -- a floor, never
a cap. The output is a PERMUTATION: the same cells, the same count, nothing added or removed, so
total throughput, every gate, every threshold and every trial charge are exactly as they were.
A family outside the active sources keeps its own relative order and loses, in any prefix, at
most the floor slots handed to the sources.

A MEMBER THAT CANNOT FIRE IS NOT GIVEN SLOTS. A member with no verdict ever, and whose cells come
back from the judge as `never_fires` (zero signal days -- its input is absent on the judge's
side), is BLOCKED: a floor cannot build an input, so it would only spend judge time on cells that
return UNKNOWN. It stays in the docket at its own place, keeps its breadth floor in
`judge_coverage`, and becomes eligible again the pass after its first ruled verdict.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from typing import Any

#: The declared table: source family -> (minimum share of each pass's judge slots, members).
#: A new alt-data family joins its source here; nothing else changes.
SOURCE_FAMILY_FLOOR: dict[str, dict[str, Any]] = {
    "cot": {
        "min_share": 0.05,
        "members": ("cot_positioning", "cot_net_fade", "cot_change_fade",
                    "cot_change_momentum", "cot_comm_follow"),
    },
    "tick_tape": {
        "min_share": 0.05,
        "members": ("execution_state", "liquidity_regime", "orderflow_imbalance"),
    },
    "event_analyst": {
        "min_share": 0.05,
        "members": ("event_reaction", "analyst_cross_market_lead", "analyst_revision_drift"),
    },
}

#: Where the floor is enforced once the seal is cleared (the sealed judge's own build list).
ENFORCED_AT = "desks/mt5/scripts/external_gauntlet.py allocate_by_yield (SEALED)"


def member_to_source(table: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, str]:
    """family -> its source family, from the declared table (first declaration wins)."""
    out: dict[str, str] = {}
    for src, spec in (table or SOURCE_FAMILY_FLOOR).items():
        for fam in spec.get("members") or ():
            out.setdefault(str(fam), str(src))
    return out


def blocked_reason(fam: str, judged_total: Mapping[str, int],
                   never_fires: Mapping[str, int]) -> str | None:
    """Why a member is given no floor slots, or None when it is eligible (see module doc)."""
    if int(judged_total.get(fam, 0) or 0) > 0:
        return None
    nf = int(never_fires.get(fam, 0) or 0)
    if nf > 0:
        return (f"never ruled, and {nf} of its cells came back never_fires (zero signal days): "
                "its input is absent on the judge's side, so floor slots would return UNKNOWN")
    return None


def source_state(mined: Mapping[str, int], judged_total: Mapping[str, int], *,
                 banned: Iterable[str] = (),
                 never_fires: Mapping[str, int] | None = None,
                 backlog: Mapping[str, int] | None = None,
                 table: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Per source family: judged/mined against the desk-wide ratio, active, eligible members.

    The desk-wide ratio excludes banned families (they are not judge work). A source with nothing
    mined is inactive: there is nothing for a floor to reach. With `backlog` (unjudged cells per
    family), a member holding none is not eligible either -- it has nothing to be given a slot.
    """
    tbl = table or SOURCE_FAMILY_FLOOR
    ban = set(banned)
    nf = never_fires or {}
    desk_m = sum(int(v or 0) for f, v in mined.items() if f not in ban)
    desk_j = sum(int(v or 0) for f, v in judged_total.items() if f not in ban)
    desk_ratio = (desk_j / desk_m) if desk_m > 0 else None
    groups: dict[str, Any] = {}
    for src, spec in tbl.items():
        members = [str(m) for m in spec.get("members") or () if str(m) not in ban]
        m = sum(int(mined.get(f, 0) or 0) for f in members)
        j = sum(int(judged_total.get(f, 0) or 0) for f in members)
        ratio = (j / m) if m > 0 else None
        active = bool(ratio is not None and desk_ratio is not None and ratio < desk_ratio)
        blocked = {f: r for f in members
                   if (r := blocked_reason(f, judged_total, nf)) is not None}
        empty = ({f for f in members if f not in blocked and int(backlog.get(f, 0) or 0) <= 0}
                 if backlog is not None else set())
        groups[str(src)] = {
            "members": members,
            "min_share": float(spec.get("min_share") or 0.0),
            "mined": m, "judged": j,
            "judged_mined_ratio": round(ratio, 6) if ratio is not None else None,
            "active": active,
            "eligible_members": [f for f in members if f not in blocked and f not in empty],
            "blocked_members": blocked,
            "no_backlog_members": sorted(empty),
        }
    return {"desk_judged_mined_ratio": (round(desk_ratio, 6) if desk_ratio is not None
                                        else None),
            "groups": groups}


def floor_interleave(rows: list[dict[str, Any]], state: Mapping[str, Any], *,
                     family: Callable[[dict[str, Any]], str] | None = None
                     ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reorder `rows` so every prefix holds each ACTIVE source's floor share. A permutation.

    At position i (prefix length n = i + 1) the next row comes from the first active source, in
    table order, whose eligible rows emitted so far are below ceil(min_share * n) and which still
    has rows; otherwise from everyone else in their own order; when everyone else is exhausted,
    from the sources in table order. Every stream keeps its own relative order, so the judge's
    never-judged-first order inside each family is untouched. Returns (rows, census) where the
    census counts, per source, the floor slots taken ahead of their own place.
    """
    fam_of = family or (lambda r: str(r.get("family") or ""))
    groups = state.get("groups") or {}
    active = [(src, g) for src, g in groups.items()
              if g.get("active") and float(g.get("min_share") or 0.0) > 0.0
              and g.get("eligible_members")]
    census: dict[str, Any] = {src: {"rows": 0, "emitted_by_floor": 0} for src, _ in active}
    if not rows or not active:
        return list(rows), census
    owner: dict[str, str] = {}
    for src, g in active:
        for f in g["eligible_members"]:
            owner.setdefault(str(f), src)
    streams: dict[str, list[dict[str, Any]]] = {src: [] for src, _ in active}
    rest: list[dict[str, Any]] = []
    for r in rows:
        src = owner.get(fam_of(r))
        (streams[src] if src is not None else rest).append(r)
    for src in streams:
        census[src]["rows"] = len(streams[src])
    pos = dict.fromkeys(streams, 0)
    shares = {src: float(g["min_share"]) for src, g in active}
    out: list[dict[str, Any]] = []
    ri = 0
    total = len(rows)
    # Emitted counts track the source's rows in the prefix, whichever branch emitted them.
    while len(out) < total:
        n = len(out) + 1
        pick = None
        for src, _g in active:
            if pos[src] < len(streams[src]) and pos[src] < math.ceil(shares[src] * n - 1e-12):
                pick = src
                break
        if pick is not None:
            out.append(streams[pick][pos[pick]])
            pos[pick] += 1
            census[pick]["emitted_by_floor"] += 1
            continue
        if ri < len(rest):
            out.append(rest[ri])
            ri += 1
            continue
        for src, _g in active:
            if pos[src] < len(streams[src]):
                out.append(streams[src][pos[src]])
                pos[src] += 1
                break
    return out, census


def publish(state: Mapping[str, Any], *, slots_per_pass: float | None,
            table: Mapping[str, Mapping[str, Any]] | None = None,
            missing_inputs: Mapping[str, Any] | None = None,
            enforced: bool = False) -> dict[str, Any]:
    """The JUDGE_COVERAGE `source_floor` block: per source, share, active, ratio, slots granted.

    `slots_granted` is the floor's minimum of one pass of `slots_per_pass` judge slots (the
    judge's measured sustained cells per hour): ceil(min_share * slots) while active and with an
    eligible member, else 0 -- unused slots are everyone else's. `missing_inputs` names, per
    member, the build inputs the probe found absent (research/build_input_probe).
    """
    mi = missing_inputs or {}
    groups: dict[str, Any] = {}
    for src, g in (state.get("groups") or {}).items():
        live = bool(g.get("active") and g.get("eligible_members"))
        granted = (math.ceil(float(g.get("min_share") or 0.0) * float(slots_per_pass))
                   if live and slots_per_pass else 0)
        groups[src] = {**g, "floor_share": g.get("min_share"),
                       "slots_per_pass": slots_per_pass, "slots_granted": granted,
                       "build_input_missing": {f: mi[f] for f in g.get("members") or ()
                                               if mi.get(f)}}
    return {
        "schema": "judge_source_floor/1",
        "table": "desks/mt5/research/judge_source_floor.py SOURCE_FAMILY_FLOOR",
        "desk_judged_mined_ratio": state.get("desk_judged_mined_ratio"),
        "enforced": bool(enforced),
        "enforced_at": ENFORCED_AT,
        "enforcement_status": ("ENFORCED" if enforced else
                               "AWAITING_SEAL_CLEAR: the judge's build order is decided inside "
                               "the sealed sweep; the docket's own family order does not reach "
                               "it, so this block is the decision, not yet the act"),
        "rule": ("a source family is ACTIVE while its judged/mined is below the desk-wide "
                 "judged/mined; while active every prefix of the judge's build list holds at "
                 "least floor_share of rows from its eligible members; unused slots go back; a "
                 "permutation -- no cell added or removed, no gate, threshold or trial charge "
                 "touched"),
        "groups": groups,
    }


def floor_from_report(rows: list[dict[str, Any]], report: Any) -> list[dict[str, Any]]:
    """The one call the sealed judge makes: apply the decision JUDGE_COVERAGE published.

    `report` is the JUDGE_COVERAGE.json path (or its parsed document). Fails OPEN to the rows
    unchanged on any defect -- an unreadable decision never reorders, drops or adds a cell.
    """
    try:
        if isinstance(report, Mapping):
            doc = report
        else:
            import json
            from pathlib import Path
            doc = json.loads(Path(report).read_text("utf-8"))
        block = doc.get("source_floor") or {}
        if not isinstance(block.get("groups"), Mapping):
            return rows
        out, _census = floor_interleave(rows, block)
        return out if len(out) == len(rows) else rows
    except Exception:
        return rows


def sealed_applies(gauntlet_source: Any) -> bool:
    """True when the sealed judge's source calls `floor_from_report` (measured, never assumed)."""
    try:
        from pathlib import Path
        return "floor_from_report" in Path(gauntlet_source).read_text("utf-8")
    except Exception:
        return False
