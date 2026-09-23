"""SANDBOX ROTATION AND BREADTH -- who gets the hour, and why (LAWS 5h, L1.32).

THE PROBLEM THIS SOLVES. `sandbox_runner` is ONE hourly leg with a budget of minutes and a
federation of sixty-odd systems. Pure ROI ordering is a ratchet: the systems that produced last
week get the hour, so the systems that never got an hour never produce, and a frontier goes dark
without anybody deciding it should. Pure round-robin is the opposite failure -- it spends the
same minutes on a system that has donated nothing in fifty passes as on the one carrying the
book.

TWO LANES, AND EVERY SYSTEM IS IN ONE OF THEM EVERY DAY.

  SCOUT   the most OVERDUE runnable systems get a guaranteed floor share first, oldest first,
          so within `ROTATION_WINDOW_S` every runnable system has run at least once. The scout
          slots are DERIVED from the pass budget (`scout_slots`): enough of them that the whole
          roster fits inside the window at the measured pass rate, never more than half the
          pass. A system that has never run has infinite age and is therefore always a scout.
  EXPLOIT the rest of the budget is ROI-proportional (`external_federation.allocation`) and then
          REWEIGHTED BY INDEPENDENT BREADTH: a system whose donated cells span directions no
          other system spans gets more of the hour than one that re-donates a crowded corner,
          at equal ROI.

BREADTH IS MEASURED, NOT ASSERTED. Each system's donated cells (family x symbol x horizon) are
one row of an indicator matrix; `libs.risk.fx_exposure.effective_rank` -- the participation ratio
of the singular-value spectrum, the same arithmetic the book uses for n_effective -- reads how
many independent directions the whole federation spans. A system's MARGINAL BREADTH is the drop
in that number when its row is removed. Removing a system that only re-donates what others
already donate costs nothing and reads 0.0; removing the only system that reaches a corner costs
a whole direction. That is the number the exploit lane multiplies by, published per system.

NOTHING GOES PERMANENTLY DARK. The scout lane has no ROI test and no breadth test in it, by
construction: it is ordered by AGE alone. `scripts/check_sandbox_liveness.py` fences the result.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from libs.research import external_federation as fed
from libs.risk.fx_exposure import effective_rank

#: Every runnable system runs at least once inside this window. A day is the unit the desk
#: already reports on, and 24 hourly passes is the measured cadence of the leg that calls this.
ROTATION_WINDOW_S: float = 24 * 3600.0
#: The scout lane never takes more than this share of a pass; the rest is ROI x breadth.
MAX_SCOUT_SHARE: float = 0.5
#: How often the leg that calls this runs. `sandbox_runner` is an hourly leg of
#: `desks/mt5/research/hourly_cycle.py`, so a rotation window holds `window_s / CADENCE_S`
#: passes; the scout lane is sized off THAT, never off the pass's own budget (a shorter budget
#: means fewer systems per pass, not fewer passes per day).
CADENCE_S: float = 3600.0
#: How many cells of a system's donations are kept for the breadth matrix. A cap, not a filter:
#: the columns are de-duplicated anyway, so more rows would change the spectrum by dust.
MAX_CELLS = 400


def now_s() -> float:
    return datetime.now(tz=UTC).timestamp()


def age_s(last_at: Any, *, at: float | None = None) -> float:
    """Seconds since a system last ran. A system that never ran is infinitely overdue."""
    try:
        stamp = datetime.fromisoformat(str(last_at))
    except (TypeError, ValueError):
        return float("inf")
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return max(0.0, (at if at is not None else now_s()) - stamp.timestamp())


def cell_key(family: Any, symbol: Any, horizon: Any) -> str:
    return f"{family or 'UNMEASURED'!s}|{symbol or 'UNMEASURED'!s}|{horizon or ''!s}"


def scout_slots(budget_s: float, *, floor_s: int, n_runnable: int,
                window_s: float = ROTATION_WINDOW_S, cadence_s: float = CADENCE_S) -> int:
    """How many overdue systems this pass must run to keep the whole roster inside the window.

    Derived from the leg's CADENCE, not from its budget: the caller runs once an hour, so the
    window holds `window_s / cadence_s` passes and each must carry `n_runnable / passes` of the
    roster, rounded up. The cap is the room a pass has -- half its seconds at the floor share --
    because a scout lane that ate the whole pass would starve the exploit lane it exists beside.
    A budget that cannot afford even one scout still gets one: the floor is the point.
    """
    if n_runnable <= 0 or budget_s <= 0 or floor_s <= 0:
        return 0
    passes = max(1.0, window_s / max(1.0, cadence_s))
    need = int(-(-n_runnable // int(passes)))
    room = int(budget_s * MAX_SCOUT_SHARE // floor_s)
    return max(1, min(need, max(1, room), n_runnable))


def cells_of(rows: Mapping[str, Any]) -> dict[str, list[str]]:
    """system_id -> the donated cells the runner recorded on its state row."""
    out: dict[str, list[str]] = {}
    for sid, row in rows.items():
        if not isinstance(row, Mapping):
            continue
        cells = row.get("cells")
        if isinstance(cells, list | tuple):
            out[str(sid)] = [str(c) for c in cells][:MAX_CELLS]
    return out


def breadth(cells: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    """Marginal independent breadth per system, from the effective rank of the cell matrix.

    Returns `{"total": float, "marginal": {sid: float}, "columns": int, "basis": str}`. A system
    with no recorded cells reads 0.0 marginal breadth, which is the measurement (it has donated
    nothing yet), never a penalty applied to it.
    """
    rows = {sid: sorted({c for c in cs if c}) for sid, cs in cells.items()}
    columns = sorted({c for cs in rows.values() for c in cs})
    index = {c: i for i, c in enumerate(columns)}
    ids = sorted(rows)
    if not columns or not ids:
        return {"total": 0.0, "marginal": dict.fromkeys(ids, 0.0), "columns": 0,
                "basis": "no system has recorded a donated cell yet: breadth is UNMEASURED, "
                         "which is why every system keeps its scout floor"}
    matrix = [[0.0] * len(columns) for _ in ids]
    for r, sid in enumerate(ids):
        for c in rows[sid]:
            matrix[r][index[c]] = 1.0
    total = effective_rank(matrix)
    marginal: dict[str, float] = {}
    for r, sid in enumerate(ids):
        without = [row for i, row in enumerate(matrix) if i != r]
        marginal[sid] = round(max(0.0, total - (effective_rank(without) if without else 0.0)), 4)
    return {"total": round(total, 4), "marginal": marginal, "columns": len(columns),
            "basis": ("participation ratio of the singular-value spectrum of the system x "
                      "(family|symbol|horizon) indicator matrix; marginal = the drop when the "
                      "system's row is removed (libs.risk.fx_exposure.effective_rank)")}


def plan(runnable: Sequence[str], state_rows: Mapping[str, Any], *, budget_s: float,
         floor_s: int, at: float | None = None,
         window_s: float = ROTATION_WINDOW_S,
         cadence_s: float = CADENCE_S) -> dict[str, Any]:
    """The pass's order and its shares: scouts by age, then ROI x breadth for the rest.

    `runnable` is the runner's own list of plannable system ids; `state_rows` is
    `sandbox_runner_state.json["systems"]`. Nothing here reads the clock except through `at`,
    so a test can drive a whole day in one call.
    """
    ids = [str(s) for s in runnable]
    ages = {sid: age_s((state_rows.get(sid) or {}).get("last_at")
                       if isinstance(state_rows.get(sid), Mapping) else None, at=at)
            for sid in ids}
    b = breadth(cells_of({sid: state_rows.get(sid) or {} for sid in ids}))
    marginal = b["marginal"]
    n_scouts = scout_slots(budget_s, floor_s=floor_s, n_runnable=len(ids),
                           window_s=window_s, cadence_s=cadence_s)
    overdue = sorted((s for s in ids if ages[s] >= window_s * 0.5),
                     key=lambda s: (-ages[s], s))
    scouts = overdue[:n_scouts] if overdue else sorted(ids, key=lambda s: (-ages[s], s))[
        :min(n_scouts, len(ids))]
    scout_cost = float(min(budget_s * MAX_SCOUT_SHARE, len(scouts) * floor_s))
    exploit_budget = max(0.0, budget_s - scout_cost)
    rows = []
    for sid in ids:
        row = dict(state_rows.get(sid) or {}) if isinstance(state_rows.get(sid), Mapping) else {}
        rows.append({**row, "system_id": sid})
    alloc = fed.allocation(rows, int(exploit_budget), floor_s=floor_s) if rows else {}
    #: breadth reweighting: a system that spans a direction nobody else spans buys more of the
    #: hour at equal ROI. 1.0 + marginal keeps an unmeasured system at its ROI share exactly.
    weighted = {sid: alloc.get(sid, floor_s) * (1.0 + float(marginal.get(sid, 0.0)))
                for sid in ids}
    total_w = sum(weighted.values()) or 1.0
    shares = {sid: max(floor_s, int(exploit_budget * w / total_w))
              for sid, w in weighted.items()}
    for sid in scouts:
        shares[sid] = max(shares.get(sid, floor_s), floor_s)
    order = scouts + sorted((s for s in ids if s not in set(scouts)),
                            key=lambda s: (-shares.get(s, 0), -float(marginal.get(s, 0.0)), s))
    return {
        "order": order, "shares": shares, "scouts": scouts, "n_scout_slots": n_scouts,
        "window_s": window_s, "cadence_s": cadence_s, "scout_budget_s": round(scout_cost, 1),
        "exploit_budget_s": round(exploit_budget, 1),
        "ages_s": {sid: (None if ages[sid] == float("inf") else round(ages[sid], 1))
                   for sid in ids},
        "overdue": overdue, "breadth": b,
        "rule": ("scouts first, ordered by age alone, so no runnable system goes a rotation "
                 "window without an hour; the rest ROI-proportional x (1 + marginal breadth), "
                 "floored so nothing is switched off"),
    }


def due_violations(runnable: Sequence[str], state_rows: Mapping[str, Any], *,
                   window_s: float = ROTATION_WINDOW_S, at: float | None = None,
                   grace: float = 1.5) -> list[dict[str, Any]]:
    """Runnable systems whose last run is older than the rotation window (x grace). The fence
    reads this; `grace` exists so one skipped pass is not a breach, two days of them is."""
    out = []
    for sid in sorted(str(s) for s in runnable):
        row = state_rows.get(sid)
        age = age_s(row.get("last_at") if isinstance(row, Mapping) else None, at=at)
        if age > window_s * grace:
            out.append({"system_id": sid, "age_s": (None if age == float("inf")
                                                    else round(age, 1)),
                        "last_at": (row or {}).get("last_at") if isinstance(row, Mapping)
                        else None,
                        "window_s": window_s,
                        "why": ("never run" if age == float("inf")
                                else f"last run {age / 3600:.1f}h ago, window "
                                     f"{window_s / 3600:.0f}h")})
    return out
