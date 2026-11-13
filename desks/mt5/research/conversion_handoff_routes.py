"""conversion_handoff_routes: cells, peers, parameters and the trial budget.

Split out of conversion_handoff_converter.py so each file of the organ is a size the
independent reviewer can read whole. conversion_handoff_converter re-exports every name here;
the organ's behaviour and docstring live there."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from research.conversion_handoff_common import (
    CAPACITY_MAX_AGE_H,
    DOCKET,
    FALLBACK_TRIALS_PER_DAY,
    JUDGE_VOLUME_FLOOR_PER_DAY,
    MIN_PEER_HISTORY_DAYS,
    MIN_PEER_LEAD_DAYS,
    PASSES_PER_DAY,
    REPORTS,
    ROUTE_TRANSPLANT,
    SEAT,
    UNIVERSE,
    UNMEASURED,
    _now,
)
from research.conversion_handoff_io import (
    _read_json,
    iter_json_list,
)


def _cell_id(symbol: str, family: str, params: Mapping[str, Any], timeframe: str) -> str:
    try:
        from research.frontier_identity import docket_cell_id
    except ImportError:                                           # pragma: no cover - import ctx
        from frontier_identity import docket_cell_id  # type: ignore[no-redef]
    return str(docket_cell_id({"symbol": symbol, "family": family, "params": dict(params),
                               "timeframe": timeframe}))


_HIST_MEMO: dict[tuple[str, str], datetime | None] = {}


def history_start(symbol: str, timeframe: str, universe: Path | None = None) -> datetime | None:
    """The first bar on `symbol`'s `timeframe` chart, from the parquet footer (no bars read)."""
    k = (str(universe or UNIVERSE), f"{symbol}_{timeframe}")
    if k in _HIST_MEMO:
        return _HIST_MEMO[k]
    p = (universe or UNIVERSE) / f"{symbol}_{timeframe}.parquet"
    out: datetime | None = None
    if p.exists():
        try:
            import pyarrow.parquet as pq
            md = pq.ParquetFile(p).metadata
            names = [md.schema.column(i).name for i in range(md.num_columns)]
            col = names.index("time") if "time" in names else None
            lows = []
            if col is not None:
                for g in range(md.num_row_groups):
                    st = md.row_group(g).column(col).statistics
                    if st is not None and st.has_min_max:
                        lows.append(st.min)
            if lows:
                t = min(lows)
                if isinstance(t, datetime):
                    out = t if t.tzinfo else t.replace(tzinfo=UTC)
                elif isinstance(t, (int, float)):
                    out = datetime.fromtimestamp(float(t) / 1e9, tz=UTC)
        except Exception:
            out = None
    _HIST_MEMO[k] = out
    return out


def _policy() -> Any:
    try:
        import research.universe_policy as up
    except ImportError:                                           # pragma: no cover - import ctx
        import universe_policy as up  # type: ignore[no-redef]
    return up


def lane_allows(symbol: str, family: str) -> bool:
    """The two-lane law: a share CFD only in the cross-sectional class-book families, anything
    else only when the policy says it is hunted for hypotheses."""
    up = _policy()
    if up.is_equity(symbol):
        return family in up.CROSS_SECTIONAL_FAMILIES
    return bool(up.may_hypothesise(symbol, family))


def ranked_peers(symbol: str, family: str, timeframe: str, *,
                 now: datetime | None = None,
                 universe: Path | None = None,
                 min_lead_days: int | None = MIN_PEER_LEAD_DAYS) -> tuple[list[str], str | None]:
    """Same-class peers with enough history on the same chart, longest history first.

    Returns (peers, why-none). `min_lead_days=None` drops the lead over the parent's own first
    bar (a cross-sectional pool needs a long panel member, not one older than the parent).
    The class is `universe_policy.peer_class`, from the broker
    registry; an unclassified symbol has no peers (absence is not a permission)."""
    up = _policy()
    if not lane_allows(symbol, family):
        return [], ("two-lane law: the parent is a share CFD and the family is not a "
                    "cross-sectional class book (universe_policy.CROSS_SECTIONAL_FAMILIES)")
    klass = up.peer_class(symbol)
    if not klass:
        return [], f"{symbol} has no peer class in the broker registry (universe_policy)"
    members = [m for m in up.class_members(klass) if str(m).upper() != symbol.upper()]
    t_now = now or _now()
    own = history_start(symbol, timeframe, universe)
    scored: list[tuple[datetime, str]] = []
    for m in members:
        if not lane_allows(m, family):
            continue
        start = history_start(m, timeframe, universe)
        if start is None:
            continue
        if (t_now - start).days < MIN_PEER_HISTORY_DAYS:
            continue
        if (min_lead_days is not None and own is not None
                and (own - start).days < min_lead_days):
            continue
        scored.append((start, str(m)))
    scored.sort()
    if not scored:
        lead = (f" starting >= {min_lead_days}d before {symbol}'s"
                if min_lead_days is not None else "")
        return [], f"no {klass} peer with >= {MIN_PEER_HISTORY_DAYS}d of {timeframe} bars{lead}"
    return [m for _, m in scored], None


ParamsLookup = Callable[[Sequence[Mapping[str, Any]], Callable[[], bool]],
                        dict[str, dict[str, Any]]]
ExistsCheck = Callable[[str, str, Mapping[str, Any], str], bool]
Donor = Callable[[str, list[dict[str, Any]], int], dict[str, Any]]


def registry_params(rows: Sequence[Mapping[str, Any]],
                    time_ok: Callable[[], bool]) -> dict[str, dict[str, Any]]:
    """cell -> {"params", "timeframe"} from the canonical registry (`id` or the `donated_cell`
    alias, both indexed), checked against the judge's own identity; the docket is the fallback."""
    out: dict[str, dict[str, Any]] = {}
    want = {str(r.get("cell")): r for r in rows if r.get("cell")}
    try:
        from libs.moat import registry as reg
        conn = reg.connect()
    except Exception:
        conn = None
    if conn is not None:
        try:
            for cell, r in want.items():
                if not time_ok():
                    break
                for hit in conn.execute(
                        "SELECT family, symbol, params_json, chart FROM research_candidates "
                        "WHERE id=? OR donated_cell=? LIMIT 8", (cell, cell)).fetchall():
                    try:
                        params = json.loads(hit[2] or "{}")
                    except ValueError:
                        continue
                    tf = str(hit[3] or r.get("timeframe") or "H1")
                    if _cell_id(str(hit[1]), str(hit[0]), params, tf) == cell:
                        out[cell] = {"params": params, "timeframe": tf, "source": "registry"}
                        break
        except Exception:
            pass
        finally:
            conn.close()
    missing = {c: r for c, r in want.items() if c not in out}
    if missing and time_ok():
        out.update(docket_params(missing, time_ok))
    return out


def docket_params(want: Mapping[str, Mapping[str, Any]], time_ok: Callable[[], bool],
                  path: Path | None = None) -> dict[str, dict[str, Any]]:
    """cell -> params from the docket, streamed; only rows on a wanted (symbol, family) pair are
    hashed, so the scan costs one parse per docket row."""
    pairs = {(str(r.get("symbol") or ""), str(r.get("family") or "")) for r in want.values()}
    out: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(iter_json_list(path or DOCKET)):
        if i % 2000 == 0 and not time_ok():
            break
        pair = (str(row.get("symbol") or row.get("sym") or ""), str(row.get("family") or ""))
        if pair not in pairs or not isinstance(row.get("params"), dict):
            continue
        try:
            from research.frontier_identity import docket_cell_id
            cid = str(docket_cell_id(row))
        except Exception:
            continue
        if cid in want and cid not in out:
            out[cid] = {"params": dict(row["params"]),
                        "timeframe": str(row.get("timeframe") or want[cid].get("timeframe")
                                         or "H1"),
                        "source": "docket"}
            if len(out) == len(want):
                break
    return out


def registry_has(family: str, symbol: str, params: Mapping[str, Any], chart: str) -> bool:
    """True when the exact rule is already a candidate (its trial was charged by its minter)."""
    try:
        from libs.moat import registry as reg
        conn = reg.connect()
    except Exception:
        return False
    try:
        h = reg.content_hash(family, symbol, params, chart)
        return conn.execute("SELECT 1 FROM research_candidates WHERE content_hash=? LIMIT 1",
                            (h,)).fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def donate_family(trial_family: str, candidates: list[dict[str, Any]],
                  tests_run: int) -> dict[str, Any]:
    """ONE contract file per trial_family through the desk's one donation door, so
    `experiment_ledger._proposer_counts` charges exactly `tests_run` trials to that family."""
    import proposer_common as pc
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", trial_family)[:60] or "family"
    path = pc.donate(source=SEAT, candidates=candidates, tests_run=tests_run, suffix=slug)
    last = dict(pc.LAST_DONATION)
    return {"path": str(path) if path else None, "donated": int(last.get("donated") or 0),
            "refused_wrong_lane": int(last.get("refused_wrong_lane") or 0),
            "refused_unstamped": int(last.get("refused_unstamped") or 0),
            "registry_error": last.get("registry_error")}


def child_candidate(parent: Mapping[str, Any], symbol: str, params: Mapping[str, Any],
                    timeframe: str, child_id: str, route: str, mechanism: str,
                    detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One child cell, in the donation door's shape, with the parent and the route as lineage."""
    fam = str(parent.get("family") or "")
    return {
        "source": SEAT, "kind": SEAT, "symbol": symbol, "family": fam,
        "params": dict(params), "chart": timeframe, "timeframe": timeframe,
        "mechanism": mechanism,
        "title": f"{route} {fam} {parent.get('symbol')} -> {symbol} {timeframe}",
        "url": "", "cell": child_id, "trial_family": parent.get("trial_family") or fam,
        "lineage": {"parent_cell": parent.get("cell"), "route": route,
                    "handoff_reason": parent.get("reason"), "parent_symbol": parent.get("symbol"),
                    "converter": SEAT, **dict(detail or {})},
        "evidence": {"route": route, "parent_cell": parent.get("cell"),
                     "parent_why": str(parent.get("why") or "")[:200],
                     "screen": "none: a conversion, judged only by the ten gates"},
    }


def transplant_candidate(parent: Mapping[str, Any], peer: str, params: Mapping[str, Any],
                         timeframe: str, child_id: str) -> dict[str, Any]:
    fam = str(parent.get("family") or "")
    return child_candidate(
        parent, peer, params, timeframe, child_id, ROUTE_TRANSPLANT,
        f"{fam} on {peer}: the same rule as {parent.get('cell')}, transplanted to a same-class "
        "peer whose history predates the lockbox cut")


# =============================================================================================
# THE MULTIPLE-TESTING BUDGET -- derived from the judge's measured spare capacity
# =============================================================================================

def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _age_h(stamp: Any, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (now - t).total_seconds() / 3600.0


def judge_capacity(reports: Path | None = None, *,
                   now: datetime | None = None) -> dict[str, Any]:
    """Cells the judge judges a day, MEASURED: the last sweep's judged cells over its wall time.

    Returns {"status": "MEASURED", "per_day", "judged_per_sweep", "sweep_s", "sources"} or
    {"status": "UNMEASURED", "why"}. A source older than CAPACITY_MAX_AGE_H is not today's judge."""
    root = reports or REPORTS
    t_now = now or _now()
    judged: float | None = None
    src_judged = ""
    why: list[str] = []
    thr = _read_json(root / "JUDGING_THROUGHPUT.json")
    if isinstance(thr, dict):
        age = _age_h(thr.get("at"), t_now)
        q = thr.get("queue")
        v = _num(q.get("judged_last_sweep")) if isinstance(q, dict) else None
        if age is not None and age > CAPACITY_MAX_AGE_H:
            why.append(f"JUDGING_THROUGHPUT.json is {age:.0f}h old")
        elif v and v > 0:
            judged, src_judged = v, "JUDGING_THROUGHPUT.json queue.judged_last_sweep"
    if judged is None:
        bp = _read_json(root / "GAUNTLET_BACKPRESSURE.json")
        cap = bp.get("capacity") if isinstance(bp, dict) else None
        meas = cap.get("measured") if isinstance(cap, dict) else None
        if isinstance(meas, dict):
            age = _age_h(meas.get("swept_at") or (bp or {}).get("at"), t_now)
            v = _num(meas.get("n_judged"))
            if age is not None and age > CAPACITY_MAX_AGE_H:
                why.append(f"GAUNTLET_BACKPRESSURE.json is {age:.0f}h old")
            elif v and v > 0:
                judged = v
                src_judged = "GAUNTLET_BACKPRESSURE.json capacity.measured.n_judged"
    res = _read_json(root / "JUDGE_RESIDENT.json")
    sweep_s = _num(res.get("last_sweep_s")) if isinstance(res, dict) else None
    if judged is None:
        why.append("no judged-per-sweep figure in JUDGING_THROUGHPUT.json or "
                   "GAUNTLET_BACKPRESSURE.json")
    if not sweep_s or sweep_s <= 0:
        why.append("no sweep wall time (JUDGE_RESIDENT.json last_sweep_s)")
    if judged is None or not sweep_s or sweep_s <= 0:
        return {"status": UNMEASURED, "why": "; ".join(why)}
    return {"status": "MEASURED", "per_day": int(judged * 86400.0 / sweep_s),
            "judged_per_sweep": int(judged), "sweep_s": round(sweep_s, 1),
            "sources": [src_judged, "JUDGE_RESIDENT.json last_sweep_s"]}


def judge_inflow(reports: Path | None = None) -> dict[str, Any]:
    """Cells every other producer mints a day (they compete for the same judge)."""
    doc = _read_json((reports or REPORTS) / "JUDGING_RATE.json")
    v = _num(doc.get("created_per_day")) if isinstance(doc, dict) else None
    if v is None or v < 0:
        return {"status": UNMEASURED, "per_day": 0,
                "why": "JUDGING_RATE.json created_per_day absent: no inflow subtracted"}
    return {"status": "MEASURED", "per_day": int(v),
            "source": "JUDGING_RATE.json created_per_day"}


def trial_budget(reports: Path | None = None, *, charged_today: int = 0,
                 now: datetime | None = None) -> dict[str, Any]:
    """The day's and this pass's conversion budget, in NEW TRIALS (child cells).

    day = measured capacity - other producers' daily inflow (the volume floor is the judge's
    target, published as judge_gap_per_day when capacity is short of it, never fed);
    pass = what is left of the day / the hourly passes left in the UTC day (a missed pass is
    caught up). No capacity artifact: FALLBACK_TRIALS_PER_DAY, labelled UNMEASURED."""
    t_now = now or _now()
    cap = judge_capacity(reports, now=t_now)
    inflow = judge_inflow(reports)
    if cap["status"] == "MEASURED":
        capacity = int(cap["per_day"])
        day = max(0, capacity - int(inflow["per_day"]))
        status = "MEASURED"
        basis = f"measured {cap['per_day']}/day - inflow {inflow['per_day']}/day"
        gap = max(0, JUDGE_VOLUME_FLOOR_PER_DAY - capacity)
    else:
        capacity = None
        gap = None
        day = FALLBACK_TRIALS_PER_DAY
        status = UNMEASURED
        basis = (f"UNMEASURED: {cap.get('why')}; fallback constant FALLBACK_TRIALS_PER_DAY="
                 f"{FALLBACK_TRIALS_PER_DAY}")
    passes_left = max(1, PASSES_PER_DAY - t_now.hour)
    left = max(0, day - int(charged_today))
    per_pass = -(-left // passes_left) if left else 0
    return {"status": status, "per_day": int(day), "per_pass": int(per_pass),
            "charged_today": int(charged_today), "remaining_today": int(left),
            "passes_left_today": passes_left, "capacity_per_day": capacity,
            "judge_volume_floor_per_day": JUDGE_VOLUME_FLOOR_PER_DAY,
            "judge_gap_per_day": gap,
            "capacity": cap, "inflow": inflow, "basis": basis,
            "rule": ("every converted child is a new trial charged to its trial_family; the "
                     "budget is the judge's spare capacity so conversion never outruns what the "
                     "judge can absorb, and never stops short of it")}


# =============================================================================================
# never_fires -> relaxed_threshold, read off the family's own grid
# =============================================================================================

#: Never relaxed: exit-side params (they change how a trade ends, not whether the entry fires)
#: and params with no single firing direction (wait_bars widens one window and delays another).
