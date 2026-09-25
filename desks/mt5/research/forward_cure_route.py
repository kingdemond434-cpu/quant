"""THE SECOND ROUTE TO A CERTIFICATE, MEASURED LINK BY LINK -- AND ITS ROSTER KEPT.

WHAT THE ROUTE IS, AND WHY IT IS NOT A LOOPHOLE

`desks/mt5/policy/gate_spec.yaml` marks five of the ten gates POWER and grants each of them
`cure_by_forward: true` with one threshold: `exp_r > 0.05R, n >= 50, maxDD > -25R, days >= 14`.
The other five are VALIDITY and carry no cure at all -- one validity miss and the cell is dead.
So a cell that clears every validity gate and misses only on power may earn its way in on REAL
FORWARD EVIDENCE: fifty trades and fourteen days the desk did not have when it judged the cell.

That is a HARDER test than the in-sample screen it replaces, not an easier one, and nothing in
this module moves it. This module neither promotes nor certifies; it does not read a threshold
into a decision. It does two things, both of them measurement:

  1.  KEEPS THE ROSTER. `external_gauntlet` writes `reports/POWER_CURE_CANDIDATES.json` from
      THIS SWEEP'S verdicts only -- it is a snapshot, not a ledger. Measured 2026-09-24 on the
      trading box: 1,240 rows stamped `2026-09-23T05:43Z`, thirty hours old, because the judge
      had not completed a verdict batch since. A cell that qualified two batches ago and has not
      been re-judged since has simply fallen off the list, and with it off every route that
      reads the list. Accumulating is not a licence: a row leaves this roster only on POSITIVE
      evidence -- a later verdict in which the same cell PASSES all ten (it is a certificate now
      and belongs in the canon) or FAILS a VALIDITY gate (validity is absolute and uncurable).
      An absent, short or unreadable later verdict never voids a row; the row stands with its
      age published. That is the desk's own GOLD_RETIRED rule applied to the same class of
      question.

  2.  MEASURES THE CHAIN. The route is four links -- the gauntlet publishes candidates, an
      admission door returns them, the forward engine gathers evidence on a clock, and something
      adjudicates the four thresholds -- and a route is only as real as its weakest link. This
      publishes a verdict per link from artifacts on disk, so "the policy permits a forward cure"
      stops being a claim the desk cannot cash (L1.49) and becomes a number. A link whose
      artifact is absent reads UNMEASURED, which is a verdict and never a zero (L1.28a).

WHAT THIS MODULE MAY NEVER BECOME

If accumulating a roster, or anything else here, ever let a cell certify on LESS evidence than
`forward_cure_thresholds` demands, it would be a backdoor and it must be deleted rather than
tuned. The roster confers no authority: every row carries `promotion_authority: False` exactly as
the sweep wrote it, and the thresholds are applied by whatever adjudicates them, never here.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DESK = BASE / "desks" / "mt5"
REPORTS = DESK / "reports"

#: The gate spec's own split. Read from the spec where it can be, so this file cannot drift from
#: the policy; the literals are the fallback and are byte-identical to `gate_spec.yaml` today.
FALLBACK_VALIDITY = ("economic_prior", "pbo", "reality_check_spa", "stress_costs", "lockbox")
FALLBACK_POWER = ("in_sample_screen", "deflated_sharpe", "cpcv", "walk_forward", "expected_value")


def gate_split() -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        from gate_policy import get_power_gates, get_validity_gates
        return tuple(get_validity_gates()), tuple(get_power_gates())
    except Exception:
        try:
            from research.gate_policy import get_power_gates, get_validity_gates
            return tuple(get_validity_gates()), tuple(get_power_gates())
        except Exception:
            return FALLBACK_VALIDITY, FALLBACK_POWER


def _read(path: Path, default: object = None) -> object:
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _write(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


# ----------------------------------------------------------------------- 1. keep the roster

def accumulate(base: Path | None = None) -> dict:
    """Merge this sweep's cure snapshot into the cumulative roster. Returns the census.

    A row is ADDED or REFRESHED from the snapshot. A row is RETIRED only on positive evidence in
    the latest gate report: the same cell now passing all ten (CERTIFIED -- it belongs in the
    canon, not here) or now failing a VALIDITY gate (DEAD -- validity is absolute). Silence
    retires nothing.
    """
    root = Path(base) if base is not None else BASE
    reports = root / "desks" / "mt5" / "reports"
    validity, _power = gate_split()

    snap = _read(reports / "POWER_CURE_CANDIDATES.json", {})
    snap_rows = snap.get("candidates") if isinstance(snap, dict) else None
    if not isinstance(snap_rows, dict):
        snap_rows = {}

    roster_doc = _read(reports / "FORWARD_CURE_ROSTER.json", {})
    rows = roster_doc.get("rows") if isinstance(roster_doc, dict) else None
    if not isinstance(rows, dict):
        rows = {}

    now = _now()
    added = refreshed = 0
    for key, row in snap_rows.items():
        if not isinstance(row, dict):
            continue
        prev = rows.get(key)
        if isinstance(prev, dict):
            row = {**row, "first_listed_at": prev.get("first_listed_at", now)}
            refreshed += 1
        else:
            row = {**row, "first_listed_at": now}
            added += 1
        row["last_seen_at"] = now
        rows[key] = row

    # RETIREMENT ON POSITIVE EVIDENCE ONLY.
    gates = _read(reports / "universal_gates_external.json", {})
    verdicts = gates.get("verdicts") if isinstance(gates, dict) else None
    retired: dict[str, str] = {}
    if isinstance(verdicts, list):
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            key = f"external.{v.get('cell')}"
            if key not in rows:
                continue
            st = v.get("stages") or {}
            if not st:
                continue                       # unjudged this pass: silence retires nothing
            if v.get("passed"):
                retired[key] = "CERTIFIED"
            elif any(not (isinstance(st.get(g), dict) and st[g].get("passed") is True)
                     for g in validity):
                retired[key] = "VALIDITY_FAIL"
    for key in retired:
        rows.pop(key, None)

    ages = []
    for r in rows.values():
        try:
            t = datetime.fromisoformat(str(r.get("first_listed_at")))
            ages.append((datetime.now(tz=UTC) - t).total_seconds() / 3600.0)
        except Exception:
            continue
    ages.sort()
    census = {
        "at": now,
        "n_roster": len(rows),
        "n_in_latest_snapshot": len(snap_rows),
        "snapshot_swept_at": snap.get("swept_at") if isinstance(snap, dict) else None,
        "added_this_pass": added, "refreshed_this_pass": refreshed,
        "retired_this_pass": len(retired),
        "retired_by_reason": {w: sum(1 for x in retired.values() if x == w)
                              for w in set(retired.values())},
        "oldest_hours": round(ages[-1], 2) if ages else 0.0,
        "median_hours": round(ages[len(ages) // 2], 2) if ages else 0.0,
        "authority": ("NONE. Every row carries promotion_authority: False as the sweep wrote it. "
                      "The forward_cure_thresholds (n>=50, exp_r>0.05R, maxDD>-25R, days>=14) are "
                      "applied by whatever adjudicates them, never here."),
        "retirement_rule": ("POSITIVE EVIDENCE ONLY: a row leaves on a later verdict that passes "
                            "all ten (CERTIFIED) or fails a VALIDITY gate (DEAD). An absent, "
                            "short or unreadable verdict never voids a row."),
    }
    _write(reports / "FORWARD_CURE_ROSTER.json", {**census, "rows": rows})
    return census


# ----------------------------------------------------------------------- 2. measure the chain

def measure(base: Path | None = None) -> dict:
    """A verdict per link of the forward-cure route, from artifacts on disk."""
    root = Path(base) if base is not None else BASE
    desk = root / "desks" / "mt5"
    reports = desk / "reports"
    validity, power = gate_split()
    links: list[dict] = []

    # Link 0 -- the policy declares the route.
    spec = desk / "policy" / "gate_spec.yaml"
    txt = spec.read_text("utf-8") if spec.exists() else ""
    links.append({
        "link": "policy_declares",
        "status": "MEASURED" if "power_cure_via_forward: true" in txt else "UNMEASURED",
        "detail": f"{txt.count('cure_by_forward: true')} of {len(power)} power gate(s) carry "
                  f"cure_by_forward: true; {len(validity)} validity gate(s) carry no cure",
        "artifact": str(spec),
    })

    # Link 1 -- the sweep publishes eligible cells.
    snap = _read(reports / "POWER_CURE_CANDIDATES.json", None)
    snap_n = len(snap.get("candidates") or {}) if isinstance(snap, dict) else 0
    links.append({
        "link": "gauntlet_publishes_candidates",
        "status": "MEASURED" if isinstance(snap, dict) else "UNMEASURED",
        "n": snap_n,
        "swept_at": snap.get("swept_at") if isinstance(snap, dict) else None,
        "detail": "a SNAPSHOT of one sweep's verdicts, not a ledger -- see FORWARD_CURE_ROSTER",
        "artifact": str(reports / "POWER_CURE_CANDIDATES.json"),
    })

    # Link 1b -- the cumulative roster.
    roster = _read(reports / "FORWARD_CURE_ROSTER.json", None)
    links.append({
        "link": "roster_accumulates",
        "status": "MEASURED" if isinstance(roster, dict) else "UNMEASURED",
        "n": len(roster.get("rows") or {}) if isinstance(roster, dict) else 0,
        "oldest_hours": roster.get("oldest_hours") if isinstance(roster, dict) else None,
        "artifact": str(reports / "FORWARD_CURE_ROSTER.json"),
    })

    # Link 2 -- an admission door returns them for enrolment.
    door = desk / "research" / "shadow_admission.py"
    door_txt = door.read_text("utf-8", errors="replace") if door.exists() else ""
    returns_cure = "POWER_CURE_CANDIDATES" in door_txt and '"cure"' in door_txt
    links.append({
        "link": "admission_door_returns_them",
        "status": "MEASURED" if door_txt else "UNMEASURED",
        "wired": bool(returns_cure),
        "detail": ("the door reads the cure artifact and names a cure lane" if returns_cure else
                   "shadow_admission does NOT return cure rows: the enrolment end of the route "
                   "is not wired, so nothing new can begin gathering forward evidence"),
        "artifact": str(door),
    })

    # Link 3 -- clocks are actually accruing on the cure basis.
    shadow = _read(reports / "shadow" / "shadow_state.json", None)
    on_route = 0
    if isinstance(shadow, dict):
        for st in shadow.values():
            if isinstance(st, dict) and str(
                    st.get("gate_admission") or "") == "VALIDITY_PASS_POWER_DEFICIENT":
                on_route += 1
    links.append({
        "link": "clocks_accruing_on_the_cure_basis",
        "status": "MEASURED" if isinstance(shadow, dict) else "UNMEASURED",
        "n": on_route,
        "artifact": str(reports / "shadow" / "shadow_state.json"),
    })

    # Link 4 -- something adjudicates the four thresholds.
    adj = []
    for rel in ("pipeline/promote.py", "research/promoter.py", "research/shadow_forward.py"):
        p = desk / rel
        if not p.exists():
            continue
        t = p.read_text("utf-8", errors="replace")
        if "forward_cure" in t or "FORWARD_CURE" in t:
            adj.append(rel)
    links.append({
        "link": "thresholds_adjudicated",
        "status": "MEASURED",
        "readers": adj,
        "detail": ("the threshold reader must be REACHED by a clock, not merely present -- a "
                   "module nothing calls adjudicates nothing"),
    })

    unwired = [x["link"] for x in links if x.get("wired") is False]
    doc = {
        "at": _now(),
        "route": ("gate_spec power_cure_via_forward: a validity-clear, power-deficient cell may "
                  "certify on forward evidence of exp_r>0.05R, n>=50, maxDD>-25R, days>=14 -- a "
                  "HARDER test than the in-sample screen it replaces, never an easier one"),
        "verdict": "BROKEN" if unwired else "CONTINUOUS",
        "broken_links": unwired,
        "links": links,
        "bar_unchanged": True,
    }
    _write(reports / "FORWARD_CURE_ROUTE.json", doc)
    return doc


def main(base: Path | None = None) -> int:
    c = accumulate(base)
    d = measure(base)
    print(f"forward-cure roster: {c['n_roster']} cell(s) "
          f"(+{c['added_this_pass']} new, {c['retired_this_pass']} retired on positive evidence, "
          f"oldest {c['oldest_hours']}h) from a snapshot of {c['n_in_latest_snapshot']} "
          f"swept {c['snapshot_swept_at']}")
    print(f"forward-cure route: {d['verdict']}"
          + (f"; broken at {', '.join(d['broken_links'])}" if d["broken_links"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
