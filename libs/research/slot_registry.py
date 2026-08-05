"""Single source of truth for the CONCURRENT forward-confirmation slot cohort (the Holm `m`).

Under the TWO-STAGE DISCOVERY LAW the backtest gauntlet has ZERO promotion authority; promotion to
capital comes only from pre-registered FORWARD evidence, and the only multiplicity that applies
there is the number of CONCURRENTLY ACCRUING clocks -- Holm-corrected, capped at
MAX_FORWARD_SLOTS=12. That cohort size is therefore the single most load-bearing integer on the
desk's only path from research to capital.

It was being counted three different ways by three different files:
  * scripts/run_axis_shadows.py -- holm_bar(len(_AXES)) => m=4, the AXIS clocks only
  * scripts/run_alerts.py       -- len(registry) + a hardcoded `_standing = 6` + the axis count
  * data/shadow_sleeves.json    -- [], and it is a RUN-ROSTER of derivative sleeve names
                                   (scripts/run_derivative_shadow.py:77-81), never a cohort registry
Measured 2026-07-30: the axis clocks applied holm_bar(4)=2.24 while the true cohort was 12-13
(bar 2.64-2.67) -- alpha 0.0125 per clock against an intended 0.05/13=0.0038, a realized
family-wise error rate ~3.2x the design. Understating m LOOSENS the bar, so the error ran in the
PHANTOM-EDGE direction. Three deep sweeps (2026-07-26/28/29) each found this and each carried it.

FAIL-SAFE DIRECTION (deliberate, and the reason this is not a plain `len()`): a missing or
unreadable source silently SHRINKS m and loosens every bar, so unknown sources never count as
zero -- they mark the cohort `complete=False`, which run_alerts surfaces. Likewise a dormant clock
is counted until it is RETIRED by an explicit ledgered decision: over-counting only tightens the
bar (the safe error), under-counting admits noise as edge.

Pure stdlib. import from libs.research.slot_registry.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: Law cap -- the fixed-for-life forward bar is only fixed while the cohort stays at/below this.
MAX_FORWARD_SLOTS = 12

#: Standing sleeve clocks, each proven by its own on-disk state file carrying a `shadow_start`.
#: Named explicitly (not globbed) so that ADDING a clock is a visible code change and REMOVING one
#: cannot happen by a file quietly disappearing -- a vanished source becomes `unknown`, not absent.
_STANDING_STATES: dict[str, str] = {
    "cashcarry": "data/cashcarry_shadow_state.json",
    "crossasset": "data/crossasset_shadow_state.json",
    "crypto_combined": "data/crypto_shadow_state.json",
    "trend_30d": "data/trend_shadow_state.json",
    "trend_regime": "data/trend_regime_shadow_state.json",
    "legacy_shadow": "data/shadow_state.json",
}

#: Built-in derivative-shadow sleeves (scripts/run_derivative_shadow.py:77). Extras registered in
#: data/shadow_sleeves.json are added on top -- that file is the RUN roster, and every sleeve it
#: schedules is also a live clock, so it feeds the cohort even though it does not define it.
_DERIVATIVE_BUILTIN: tuple[str, ...] = ("oi_divergence", "ls_contrarian")

_AXIS_STATE = "data/axis_shadow_state.json"
_SLEEVE_ROSTER = "data/shadow_sleeves.json"
_OUT = "data/forward_slots.json"

#: Slot -> (evidence artifact, day-count field). The STATE files above prove a clock was BORN;
#: these prove it is still BREATHING, and the two are not the same question. Measured 2026-08-01:
#: the standing states are birth-certificate stubs carrying nothing but `shadow_start` and are
#: never rewritten, while the derivative slots' state was the hardcoded string literal "ACCRUING"
#: -- so `derive_slots()` ASSERTED that 12 of 12 clocks were accruing without reading a single day
#: count. Five were not: crossasset frozen 41 days at day 1 with NO scheduler line anywhere,
#: cny_premium pinned at 0/40 for 9 days (every z20 null, skipped at run_axis_shadows.py:131),
#: walcl re-stamping one 07-29 observation daily, defi_utilisation 4 days of exactly-zero returns,
#: and cashcarry silently missing its 08-01 run. `idle_slots: 0` then suppressed every idleness
#: alert. This is the L1.28a rule turned on the desk's own evidence pipeline: UNMEASURED
#: UTILISATION COUNTS AS ZERO, and a capability is proven by its ARTIFACT, never by a flag.
_EVIDENCE: dict[str, tuple[str, str]] = {
    "cashcarry": ("web/cashcarry_shadow.json", "forward_days"),
    "crossasset": ("web/crossasset_shadow.json", "forward_days"),
    "crypto_combined": ("web/crypto_shadow.json", "forward_days"),
    "trend_30d": ("web/trend_shadow.json", "forward_days"),
    "trend_regime": ("web/trend_regime_shadow.json", "forward_days"),
    "legacy_shadow": ("web/shadow.json", "forward_days"),
    "oi_divergence": ("web/derivative_shadow.json", "days_accumulated"),
    "ls_contrarian": ("web/derivative_shadow.json", "days_accumulated"),
}

#: A forward clock advances once per day. Past this its artifact is not evidence, it is a fossil.
STALE_AFTER_H = 36.0


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _evidence(name: str, now: datetime, *, days: object = None,
              updated: object = None) -> dict[str, Any]:
    """Is this clock BREATHING? Never asserts -- reports UNMEASURED when it cannot tell.

    Axis slots pass their own row's `days`/`updated`; everything else is looked up in _EVIDENCE.
    NO-EVIDENCE (day count 0) is kept DISTINCT from STALLED (artifact not rewritten): a clock can
    run perfectly on schedule and still accrue nothing, which is exactly how cny_premium sat at
    0/40 for nine days while its collector reported green every morning.
    """
    src = "(axis row)"
    if days is None and updated is None:
        ref = _EVIDENCE.get(name)
        if ref is None:
            return {"evidence": "UNMEASURED", "why": f"no evidence artifact mapped for {name}"}
        src = ref[0]
        doc = _read_json(src)
        if not isinstance(doc, dict):
            return {"evidence": "UNMEASURED", "why": f"{src} missing or unreadable", "source": src}
        days, updated = doc.get(ref[1]), doc.get("updated")
    ts = _parse_ts(updated)
    if ts is None:
        return {"evidence": "UNMEASURED", "why": f"{src} carries no parseable `updated`",
                "source": src}
    age_h = round((now - ts).total_seconds() / 3600.0, 1)
    try:
        # `days` is object-typed off a JSON dict, so narrow before converting rather than
        # silencing. The old `# type: ignore[arg-type]` had stopped matching the real error
        # (call-overload) and mypy then flagged the ignore itself as unused -- two errors from
        # one stale suppression, and CI red on master until it was removed.
        n_days = int(days) if isinstance(days, (int, float, str)) else int(str(days))
    except (TypeError, ValueError):
        return {"evidence": "UNMEASURED", "why": f"{src} carries no day count",
                "source": src, "age_h": age_h}
    state = ("NO-EVIDENCE" if n_days <= 0 else
             "STALLED" if age_h > STALE_AFTER_H else "ACCRUING")
    return {"evidence": state, "days": n_days, "age_h": age_h, "source": src}


def _read_json(rel: str) -> Any | None:
    """Return parsed JSON, or None when the source cannot be trusted (missing/unreadable)."""
    try:
        return json.loads((_ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def derive_slots() -> dict[str, Any]:
    """Enumerate every concurrently-accruing forward clock from the artifacts on disk.

    Returns a payload carrying the slots, the cohort size `m_concurrent`, and `complete` -- False
    whenever any source was unreadable, meaning m is a LOWER BOUND and the true bar may be higher.
    """
    now = datetime.now(tz=UTC)
    slots: list[dict[str, Any]] = []
    unknown: list[str] = []

    axis_doc = _read_json(_AXIS_STATE)
    if axis_doc is None:
        unknown.append(_AXIS_STATE)
    else:
        rows = axis_doc.get("axes", axis_doc) if isinstance(axis_doc, dict) else axis_doc
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            if str(row.get("verdict", "")).upper() == "RETIRED":
                continue
            slots.append({"name": str(row.get("axis", "?")), "kind": "axis",
                          "source": _AXIS_STATE, "state": str(row.get("verdict", "ACCRUING")),
                          # `started` is the clock's DECLARED birth date, carried as a first-class
                          # field so libs.research.promotion_history never has to parse it back out
                          # of the `state` prose. None where the artifact does not declare one --
                          # an absent start is UNKNOWN, never today (L1.30 phantom-birth rule).
                          "started": row.get("shadow_start") or row.get("start"),
                          **_evidence(str(row.get("axis", "?")), now,
                                      days=row.get("forward_days", row.get("n", 0)),
                                      updated=row.get("updated")
                                      or (axis_doc.get("updated")
                                          if isinstance(axis_doc, dict) else None))})

    for name, rel in _STANDING_STATES.items():
        doc = _read_json(rel)
        if doc is None:
            unknown.append(rel)
            continue
        if isinstance(doc, dict) and doc.get("shadow_start"):
            slots.append({"name": name, "kind": "standing", "source": rel,
                          "state": f"since {doc['shadow_start']}",
                          "started": str(doc["shadow_start"]), **_evidence(name, now)})

    roster = _read_json(_SLEEVE_ROSTER)
    if roster is None:
        unknown.append(_SLEEVE_ROSTER)
        names: list[str] = list(_DERIVATIVE_BUILTIN)
    else:
        extras = [str(x) for x in roster if str(x).strip()] if isinstance(roster, list) else []
        names = sorted({*_DERIVATIVE_BUILTIN, *extras})
    for name in names:
        # The roster carries names only, so a derivative sleeve declares no start. `started` is
        # None on purpose: web/derivative_shadow.json publishes `days_accumulated`, and a start
        # back-derived from an accrual counter is an UPPER bound on the birth date (a stalled
        # clock accrues nothing while ageing), so it would push births EARLIER-looking and
        # over-count them. UNKNOWN is the honest answer until the roster carries a date.
        slots.append({"name": name, "kind": "derivative", "source": _SLEEVE_ROSTER,
                      "state": "roster", "started": None, **_evidence(name, now)})

    # m is deliberately UNCHANGED by any of this: a stalled clock stays in the cohort until it is
    # RETIRED by an explicit ledgered decision, because dropping it would SHRINK m and loosen every
    # bar -- the phantom-edge direction this module exists to prevent. What the measurement buys is
    # that a dead clock can no longer report itself as accruing, and that the desk can see it is
    # paying multiplicity for slots returning nothing.
    dead = [s for s in slots if s.get("evidence") in ("STALLED", "NO-EVIDENCE")]
    unmeasured = [s for s in slots if s.get("evidence") == "UNMEASURED"]
    return {
        "updated": now.isoformat(),
        "m_concurrent": len(slots),
        "complete": not unknown,
        "cap": MAX_FORWARD_SLOTS,
        "over_cap": len(slots) > MAX_FORWARD_SLOTS,
        "idle_slots": max(0, MAX_FORWARD_SLOTS - len(slots)),
        "unknown_sources": unknown,
        "accruing": len(slots) - len(dead) - len(unmeasured),
        "not_accruing": [{"name": s["name"], "evidence": s.get("evidence"),
                          "days": s.get("days"), "age_h": s.get("age_h")} for s in dead],
        "unmeasured_slots": [s["name"] for s in unmeasured],
        "evidence_stale_after_h": STALE_AFTER_H,
        "slots": slots,
        "note": ("Holm cohort for every Stage-B forward clock. Unreadable sources are counted as "
                 "UNKNOWN, never zero: understating m loosens every bar. Dormant clocks stay "
                 "counted until RETIRED by an explicit ledgered decision -- `not_accruing` names "
                 "the slots paying multiplicity while returning no evidence, which is a cost to "
                 "fix upstream, never by shrinking m."),
    }


def concurrent_m() -> int:
    """The Holm cohort size. Never returns 0 -- a cohort of nothing would zero out multiplicity."""
    return max(1, int(derive_slots()["m_concurrent"]))


def write_snapshot() -> dict[str, Any]:
    """Persist the derived cohort to data/forward_slots.json and return it."""
    payload = derive_slots()
    (_ROOT / _OUT).write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    return payload


if __name__ == "__main__":  # pragma: no cover -- operator entry point
    snap = write_snapshot()
    print(f"m_concurrent={snap['m_concurrent']} complete={snap['complete']} "
          f"idle={snap['idle_slots']} over_cap={snap['over_cap']}")
    for s in snap["slots"]:
        print(f"  {s['kind']:11s} {s['name']:28s} {s['source']}")
    if snap["unknown_sources"]:
        print("  UNKNOWN:", ", ".join(snap["unknown_sources"]))
