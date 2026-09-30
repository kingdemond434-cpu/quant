"""MONEY-PATH SOVEREIGNTY: the invariants every NEW-RISK order must pass.

THE PRINCIPAL'S AUDIT (2026-09-30) of the committed `data/sleeves.json` on the live branch:
40 LIVE sleeves, 24 of them the banned `discovered` family, 31 with `admission.status`
UNMEASURED, 40 of 40 with `artifact.ok` false ("no cost basis"), 7 carrying principal
overrides -- and `decision_core`'s minimum-ticket logic able to place an order when the
allocator's intended size was zero. His words: "allocator says zero -> absolutely zero order",
"unknown material cost -> shadow / UNMEASURED, never live capital", "no LIVE UNMEASURED
sleeves", and the banned family purged from live.

The promoter that writes the registry is sealed, so the invariants are enforced where the money
actually leaves: at the gateway's new-risk placement sites, by this unsealed module. Every
function in the first half is PURE over its arguments; the loaders in the second half do exactly
the file read they name. The gateway calls `verdict` at every site that opens risk and never at
a site that reduces it -- stops, trailing, TTL exits, closes, cancels and OCO repair are never
blocked by anything here, because a refused sleeve is SHADOW, not orphaned.

    I1 ALLOCATOR ZERO MEANS NO ORDER. The allocator's fraction for the sleeve must be a finite
       number > 0. Zero, absent or non-finite is no order. The 0.02-lot gold floor and the
       venue minimum apply only ABOVE zero -- `decision_core.promoted_lot` / `gold_book_lot`
       return 0.0 for a zero fraction, and this refuses the order outright.
    I2 NO NEW RISK FOR AN UNMEASURED ADMISSION. A registry sleeve whose `admission.status` is
       UNMEASURED (or absent) is shadow. A canonical gold window (not a registry row) is
       admitted by the allocator's own book pricing it, which is I1.
    I3 NO NEW RISK FOR A BANNED FAMILY. The ban list is READ from where the desk declares it --
       `research/family_policy.banned_families()` (permanent bans + `data/banned_families.json`)
       united with `mt5desk/live_policy.policy().banned_families` -- never restated here.
    I4 NO NEW RISK WITHOUT A MEASURED MATERIAL COST, AND COST_SURFACES DECIDES IT. The answer is
       `research/cost_surfaces.cost_for(symbol, session=...)` over `reports/COST_SURFACES.json`
       (built from the committed inputs by `cost_surfaces.build()` when the artifact is absent
       on this host). Its spread term must be MEASURED on the account's own fills, or a PRIOR
       whose basis is the broker tape's measured spread x hour model. The registry's pooled
       `median_spread_pts` fallback says in its own basis that no hour was measured, and an
       UNMEASURED term is UNMEASURED: both are shadow.
    I5 NO NEW RISK ON AN UNMEASURED MARGINAL (blueprint CS5/D7). The admission block the promoter
       writes IS the allocator's marginal-dE[log W] reading (`promoter.capital_verdict`). A
       LIVE admission must carry the reading that admitted it: a finite `delta_elogw_per_day`,
       or -- for a sleeve the allocator already funds, where the promoter records no candidate
       delta -- a finite `heat_earned` > 0 from the funded book. Neither is an UNMEASURED
       marginal, and an UNMEASURED marginal is shadow.
    I6 A PRINCIPAL OVERRIDE TRADES ONLY INSIDE THE EXPERIMENTAL BUDGET (blueprint D9). An
       override row takes new risk only when `reports/EXPERIMENTAL_BUDGET.json` (written hourly
       by `research/experimental_budget.py`) is fresh, has a DECLARED `max_heat` > 0 that the
       experimental book is WITHIN, and accounts for this very sleeve. Undeclared, over, stale,
       absent or silent about the sleeve is no new risk -- the budget is the principal's number.

REPORT-ONLY MODE FOR I2 AND I5 (`ENFORCE_UNMEASURED_ADMISSION`, 2026-09-30). The two checks
that read only "the admission scan has not measured this yet" are REPORTED, not enforced, until
the box measures admission: they still write the decision-ledger row and the missed-growth line,
marked `mode: "report_only"`, but the send goes. I1 (allocator zero), I3 (banned family), I4
(unmeasured cost) and I6 (override outside budget) always refuse. Flipping the one switch below
to True makes I2/I5 refuse again; nothing else changes.

PRINCIPAL OVERRIDES DO NOT BYPASS I1-I5. An override row changes a sleeve's status; it does not
change what the allocator, the admission scan, the ban list or the cost surface say about it.

GROWTH GOVERNANCE. Each refusal writes a reason row to the gateway's decision ledger (so the
counterfactual replay prices the order that was not sent) and one line per sleeve, invariant and
day to `data/missed_growth.jsonl` under rail `money_path_sovereignty.<invariant>`, which
`research/missed_growth.py` summarises. The value is UNMEASURED until the replay prices it --
never a zero that would read as "cost nothing".
"""
from __future__ import annotations

import json
import math
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: desks/mt5
BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

ALLOCATOR_ZERO = "allocator_zero"
ADMISSION_UNMEASURED = "admission_unmeasured"
BANNED_FAMILY = "banned_family"
COST_UNMEASURED = "cost_unmeasured"
MARGINAL_UNMEASURED = "marginal_unmeasured"
OVERRIDE_OUTSIDE_BUDGET = "override_outside_budget"
#: I1/I2/I5 re-judged on values re-read immediately before `order_send` (`recheck`).
CHANGED_BEFORE_SEND = "changed_before_send"
#: The invariants, in the order they are reported. `first` of a verdict is the first of these
#: that refused, and it is the decision ledger's `first_blocking_gate`.
INVARIANTS: tuple[str, ...] = (ALLOCATOR_ZERO, ADMISSION_UNMEASURED, BANNED_FAMILY,
                               COST_UNMEASURED, MARGINAL_UNMEASURED, OVERRIDE_OUTSIDE_BUDGET,
                               CHANGED_BEFORE_SEND)

#: THE ONE SWITCH for I2 (ADMISSION_UNMEASURED) and I5 (MARGINAL_UNMEASURED).
#: False = REPORT-ONLY: the check still runs, still writes its decision-ledger row and its
#: missed-growth line (both marked `mode: "report_only"`), but does NOT refuse the send.
#: WHY False today: these two checks refuse on a reading that is only UNMEASURED -- the admission
#: scan has not yet run on the box for those sleeves -- and failing closed on "not measured yet"
#: would flatten the whole book: a risk reduction by fiat that no evidence shows raises
#: E[log W] (growth governance Rule 1). The four checks that read a MEASURED fact (allocator
#: zero, banned family, unmeasured material cost, override outside the declared budget) stay
#: enforced whatever this switch says.
#: TURN IT ON (True) once the box measures admission (a heavy admission scan writing
#: `admission.status` / `delta_elogw_per_day` / `heat_earned` on every LIVE row). That one line
#: is the whole change -- the tests and the fence pin both modes.
ENFORCE_UNMEASURED_ADMISSION = False
#: The invariants the switch governs. Every other invariant always refuses.
UNMEASURED_ADMISSION_INVARIANTS: frozenset[str] = frozenset({ADMISSION_UNMEASURED,
                                                             MARGINAL_UNMEASURED})
ENFORCE = "enforce"
REPORT_ONLY = "report_only"


def enforcing_unmeasured_admission(enforce: bool | None = None) -> bool:
    """The switch's value for one judgement: an explicit `enforce` wins (tests, the fence),
    otherwise the module constant, read at call time so a patched constant takes effect."""
    return ENFORCE_UNMEASURED_ADMISSION if enforce is None else bool(enforce)


def mode_of(invariant: str, enforce: bool | None = None) -> str:
    """`enforce` (the finding refuses the send) or `report_only` (recorded, not refused)."""
    if invariant in UNMEASURED_ADMISSION_INVARIANTS and not enforcing_unmeasured_admission(
            enforce):
        return REPORT_ONLY
    return ENFORCE


#: Decision-ledger reason prefix and missed-growth rail prefix.
REASON_PREFIX = "sovereignty_"
RAIL_PREFIX = "money_path_sovereignty."

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
#: Admission statuses that are NOT a measurement. Absent reads as UNMEASURED (L1.28a).
UNMEASURED_ADMISSIONS = frozenset({"", "UNMEASURED", "NONE", "UNKNOWN"})
#: Roster origin of the three canonical gold windows (`decision_core.roster`).
GOLD_WINDOW_ORIGIN = "gold_window"
#: The basis a cost_surfaces PRIOR must name to count as measured: the broker tape's own
#: spread x hour model. Its sibling ("universe.json pooled median_spread_pts (no measured hour
#: this session)") says in its own words that nothing was measured for the session.
TAPE_PRIOR_MARK = "cost_surface.json"
#: The experimental-budget artifact is hourly; older than this it is not a reading of today.
EXPERIMENTAL_BUDGET_MAX_AGE_H = 6.0

COST_SURFACES = BASE / "reports" / "COST_SURFACES.json"
EXPERIMENTAL_BUDGET = BASE / "reports" / "EXPERIMENTAL_BUDGET.json"
MISSED_GROWTH = BASE / "data" / "missed_growth.jsonl"


# ------------------------------------------------------------------------------ pure checks
def _finite(v: object) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def allocator_fraction(row: Mapping[str, Any]) -> tuple[float | None, str]:
    """(the allocator's fraction for this sleeve, where it came from).

    The gateway's per-pass book wins: a row the gateway joined to the allocator's book carries
    `sized_by == "allocator_book"` and the book's h_i in `risk_frac`. Otherwise the promoter's
    admission block records what the allocator's solve gave the sleeve (`allocator_heat`, else
    `risk_frac`). The row's top-level `risk_frac` is NOT the allocator's number -- on the 31
    UNMEASURED rows it is a promoter default (0.005882) beside an admission fraction of 0.0 --
    and a principal override does not make it one. No source is `None, "absent"`.
    """
    if row.get("sized_by") == "allocator_book":
        return _finite(row.get("risk_frac")), "allocator_book"
    adm = row.get("admission")
    if isinstance(adm, Mapping):
        for key in ("allocator_heat", "risk_frac"):
            if key in adm and adm.get(key) is not None:
                return _finite(adm.get(key)), f"admission.{key}"
    return None, "absent"


def check_allocator(row: Mapping[str, Any]) -> str | None:
    """I1. The reason there is no order, or None when the allocator funded this sleeve."""
    frac, src = allocator_fraction(row)
    if src == "absent":
        return "the allocator gave this sleeve no fraction (absent): no order"
    if frac is None:
        return f"the allocator's fraction ({src}) is not a finite number: no order"
    if not frac > 0.0:
        return f"the allocator's fraction ({src}) is {frac:g}: zero means no order"
    return None


def admission_status(row: Mapping[str, Any]) -> str:
    adm = row.get("admission")
    if not isinstance(adm, Mapping):
        return ""
    return str(adm.get("status") or "").strip().upper()


def check_admission(row: Mapping[str, Any]) -> str | None:
    """I2. A registry sleeve with an UNMEASURED (or absent) admission is shadow."""
    if row.get("origin") == GOLD_WINDOW_ORIGIN:
        # Not a registry row: the window's admission is the allocator's book pricing it, which
        # `check_allocator` already requires to be > 0 this pass.
        return None
    status = admission_status(row)
    if status in UNMEASURED_ADMISSIONS:
        shown = status or "absent"
        return (f"admission is {shown}: a LIVE sleeve the admission scan never measured is "
                f"shadow (positions still managed)")
    return None


def check_marginal(row: Mapping[str, Any]) -> str | None:
    """I5. The admitting marginal reading must exist: a finite dE[log W]/day, or the funded
    book's finite heat > 0. A gold window's marginal is the allocator's book (I1)."""
    if row.get("origin") == GOLD_WINDOW_ORIGIN:
        return None
    adm = row.get("admission")
    if not isinstance(adm, Mapping):
        return "no marginal reading: the row carries no admission block"
    if admission_status(row) in UNMEASURED_ADMISSIONS:
        return "the allocator's marginal dE[log W] for this sleeve is UNMEASURED"
    delta = _finite(adm.get("delta_elogw_per_day"))
    heat = _finite(adm.get("heat_earned"))
    if delta is not None or (heat is not None and heat > 0.0):
        return None
    return ("the admission carries neither a finite marginal dE[log W]/day nor a funded heat: "
            "the marginal is UNMEASURED")


def check_banned(row: Mapping[str, Any], banned: Iterable[str] | None) -> str | None:
    """I3. `banned` is the desk's declared list (see `banned_families`); None = unreadable."""
    if banned is None:
        return "the family ban list is unreadable: no new risk until it is readable"
    fam = str(row.get("family") or "").strip().lower()
    if fam and fam in {str(b).strip().lower() for b in banned}:
        return f"family {fam!r} is banned from live capital"
    return None


def check_cost(cost: Mapping[str, Any] | None) -> str | None:
    """I4. `cost` is a `cost_basis` reading (cost_for's spread term) for the instrument."""
    if not isinstance(cost, Mapping) or cost.get("status") != MEASURED:
        why = (cost or {}).get("why") if isinstance(cost, Mapping) else None
        return f"material cost UNMEASURED ({why or 'no reading'}): shadow, never live capital"
    return None


def is_override(row: Mapping[str, Any]) -> bool:
    return bool(row.get("principal_override"))


def check_override_budget(row: Mapping[str, Any], budget: Mapping[str, Any] | None,
                          now: datetime | None = None) -> str | None:
    """I6. A principal-override row trades only inside the declared experimental budget."""
    if not is_override(row):
        return None
    if not isinstance(budget, Mapping) or not budget:
        return ("principal override with no experimental-budget artifact "
                "(reports/EXPERIMENTAL_BUDGET.json): no new risk outside the budget")
    try:
        at = datetime.fromisoformat(str(budget.get("at") or ""))
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        age_h = ((now or datetime.now(tz=UTC)) - at).total_seconds() / 3600.0
    except ValueError:
        age_h = float("inf")
    if not age_h <= EXPERIMENTAL_BUDGET_MAX_AGE_H:
        return (f"experimental budget is stale ({age_h:.1f} h > "
                f"{EXPERIMENTAL_BUDGET_MAX_AGE_H:g} h): no new risk for an override sleeve")
    b = budget.get("budget") or {}
    cap = _finite(b.get("declared_max_heat")) if isinstance(b, Mapping) else None
    status = str((b or {}).get("status") or "") if isinstance(b, Mapping) else ""
    if cap is None or not cap > 0.0:
        return ("experimental budget is UNDECLARED: an override sleeve has no risk to trade "
                "until the principal declares data/experimental_budget.json max_heat")
    if status != "WITHIN":
        return f"experimental book is {status or 'unaccounted'} its {cap:.4%} budget"
    names = {str(s.get("sleeve")) for s in budget.get("sleeves") or []
             if isinstance(s, Mapping)}
    if str(row.get("name") or "") not in names:
        return "the experimental budget does not account for this override sleeve"
    return None


def verdict(row: Mapping[str, Any], *, banned: Iterable[str] | None,
            cost: Mapping[str, Any] | None,
            budget: Mapping[str, Any] | None = None,
            now: datetime | None = None,
            enforce_unmeasured_admission: bool | None = None) -> dict[str, Any]:
    """Every invariant over one sleeve. Pure. Every refusal is reported, not only the first,
    so the ledger can say a sleeve was refused on three counts rather than one.

    `refusals` holds the findings that REFUSE the send (`mode: "enforce"`) and decide `ok`;
    `reported` holds the findings recorded but not enforced (`mode: "report_only"`: I2/I5 while
    `ENFORCE_UNMEASURED_ADMISSION` is False). `enforce_unmeasured_admission` overrides the
    switch for one call (None = the module constant)."""
    frac, src = allocator_fraction(row)
    checks = ((ALLOCATOR_ZERO, check_allocator(row)),
              (ADMISSION_UNMEASURED, check_admission(row)),
              (BANNED_FAMILY, check_banned(row, banned)),
              (COST_UNMEASURED, check_cost(cost)),
              (MARGINAL_UNMEASURED, check_marginal(row)),
              (OVERRIDE_OUTSIDE_BUDGET, check_override_budget(row, budget, now)))
    found = [{"invariant": inv, "why": why,
              "mode": mode_of(inv, enforce_unmeasured_admission)}
             for inv, why in checks if why]
    refusals = [f for f in found if f["mode"] == ENFORCE]
    reported = [f for f in found if f["mode"] == REPORT_ONLY]
    return {"ok": not refusals, "refusals": refusals, "reported": reported,
            "first": refusals[0]["invariant"] if refusals else None,
            "allocator_fraction": frac, "allocator_source": src,
            "admission": admission_status(row) or None,
            "cost": dict(cost) if isinstance(cost, Mapping) else None}


def recheck(before: Mapping[str, Any], fresh: Mapping[str, Any] | None, *,
            registry_read: bool = True, book_read: bool = True,
            enforce_unmeasured_admission: bool | None = None) -> dict[str, Any]:
    """TIME-OF-CHECK / TIME-OF-USE (2026-09-30). The pass reads the allocator book and the
    registry ONCE, at its start, and a pass can run for minutes; the promoter or the allocator
    may zero, demote or un-measure a sleeve in between. This re-judges the values that can move
    -- the allocator's fraction, the registry status, the admission and its marginal reading --
    on a row the gateway re-read IMMEDIATELY before `order_send`, and refuses under
    `changed_before_send` when any of them no longer holds. Pure.

    `fresh` is `before` with the re-read values laid over it (None: the sleeve is no longer in
    the registry). `registry_read` / `book_read` False: that re-read failed, and a value that
    cannot be re-read cannot be shown to still hold, so the order does not go (fail closed --
    the order is new risk; nothing open is touched).

    The admission and marginal re-checks follow `ENFORCE_UNMEASURED_ADMISSION` exactly as
    `verdict` does: in report-only mode an UNMEASURED admission or marginal at send time lands
    in `reported` (mode `report_only`) rather than refusing the send.
    """
    whys: list[str] = []
    reported: list[dict[str, Any]] = []
    registry = before.get("origin") == "registry"
    if registry and not registry_read:
        whys.append("the registry could not be re-read immediately before the send")
    elif registry and fresh is None:
        whys.append("the sleeve left the LIVE registry after the pass read it")
    if before.get("sized_by") == "allocator_book" and not book_read:
        whys.append("the allocator book could not be re-read immediately before the send")
    if fresh is not None:
        status = str(fresh.get("status") or "LIVE").strip().upper()
        if registry and status != "LIVE":
            whys.append(f"the sleeve's status changed to {status} after the pass read it")
        for inv, check in ((ALLOCATOR_ZERO, check_allocator),
                           (ADMISSION_UNMEASURED, check_admission),
                           (MARGINAL_UNMEASURED, check_marginal)):
            why = check(fresh)
            if not why:
                continue
            if mode_of(inv, enforce_unmeasured_admission) == REPORT_ONLY:
                reported.append({"invariant": inv, "mode": REPORT_ONLY,
                                 "why": f"at send time -- {why}"})
            else:
                whys.append(f"changed since the pass read it -- {why}")
    refusals = [{"invariant": CHANGED_BEFORE_SEND, "why": w, "mode": ENFORCE} for w in whys]
    frac, src = allocator_fraction(fresh) if fresh is not None else (None, "absent")
    return {"ok": not refusals, "refusals": refusals, "reported": reported,
            "first": CHANGED_BEFORE_SEND if refusals else None,
            "allocator_fraction": frac, "allocator_source": src,
            "admission": admission_status(fresh) if fresh is not None else None}


def reason_of(v: Mapping[str, Any]) -> str:
    """The decision-ledger reason for a refused verdict: `sovereignty_<first invariant>`."""
    return f"{REASON_PREFIX}{v.get('first')}"


def missed_growth_line(v: Mapping[str, Any], *, sleeve: str, symbol: str, day: str,
                       at: str, lane: str, report_only: bool = False) -> list[dict[str, Any]]:
    """One missed-growth ledger line per refused invariant -- or, with `report_only`, per
    REPORTED invariant: the send went, and the line records what enforce mode would have
    refused, marked `mode: "report_only"`. Pure.

    VALUE IS UNMEASURED, NEVER ZERO. What the refused order would have earned is priced by the
    counterfactual replay from the decision-ledger row written beside this; a 0.0 here would read
    as "this refusal cost nothing" and is exactly the unbilled rail the governance forbids."""
    if report_only:
        return [{"day": day, "rail": f"{RAIL_PREFIX}{r['invariant']}", "value": None,
                 "status": UNMEASURED, "mode": REPORT_ONLY, "at": at, "sleeve": sleeve,
                 "symbol": symbol, "lane": lane,
                 "allocator_fraction": v.get("allocator_fraction"),
                 "why": (f"{r['why']}. REPORT-ONLY (ENFORCE_UNMEASURED_ADMISSION is False): the "
                         f"order was NOT refused, so no growth was given up; this line records "
                         f"what enforce mode would have refused")}
                for r in v.get("reported") or []]
    return [{"day": day, "rail": f"{RAIL_PREFIX}{r['invariant']}", "value": None,
             "status": UNMEASURED, "mode": ENFORCE, "at": at, "sleeve": sleeve,
             "symbol": symbol, "lane": lane,
             "allocator_fraction": v.get("allocator_fraction"),
             "why": (f"{r['why']}. Growth given up is priced by the counterfactual replay of the "
                     f"not-taken decision row (Rule 1: a risk reduction must prove it raises "
                     f"E[log W]); UNMEASURED until then")}
            for r in v.get("refusals") or []]


# ------------------------------------------------------------------------------ cost basis
def session_of_hour(hour: int | float | None) -> str | None:
    """The cost surface's session for a UTC hour (the surface's own PHASES)."""
    if hour is None:
        return None
    from research.cost_surfaces import session_of
    return str(session_of(int(hour)))


_SESSION_WORDS = (("london_am", "london"), ("london", "london"), ("afternoon", "ny"),
                  ("overlap", "ny"), ("_ny", "ny"), ("asia", "asia"), ("late", "late"))


def session_of_row(row: Mapping[str, Any]) -> str | None:
    """The session a sleeve trades, from its own fields -- for measuring a registry offline."""
    text = " ".join(str(row.get(k) or "") for k in ("window", "session", "selector", "name"))
    text = text.lower()
    for word, sess in _SESSION_WORDS:
        if word in text:
            return sess
    return None


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def cost_basis(symbol: str, session: str | None, *,
               surface: Mapping[str, Any] | None) -> dict[str, Any]:
    """The instrument's measured material cost, as `cost_surfaces.cost_for` decides it.

    `cost_for` walks its measured fill cells (exact -> instrument) and, for the spread alone,
    falls to its PRIOR. MEASURED at any fill level counts; a PRIOR counts only when its basis is
    the broker tape's measured spread x hour model. A `session` of None accepts any session
    with a measurement (used to measure a registry offline). Pure over `surface`."""
    sym = str(symbol or "").strip().upper()
    if not sym:
        return {"status": UNMEASURED, "why": "no instrument"}
    if not surface:
        return {"status": UNMEASURED, "why": "no cost surface readable on this host"}
    from research.cost_surfaces import cost_for
    sessions = [session] if session else ["asia", "london", "ny", "late"]
    seen: list[str] = []
    for sess in sessions:
        t = (cost_for(sym, session=sess, surface=dict(surface))["terms"]
             .get("spread_points") or {})
        if t.get("status") == MEASURED:
            return {"status": MEASURED, "source": f"cost_for:{t.get('level')}",
                    "session": sess, "value": t.get("value"),
                    "why": f"{t.get('n')} measured fill(s)"}
        if t.get("status") == "PRIOR" and TAPE_PRIOR_MARK in str(t.get("basis") or ""):
            return {"status": MEASURED, "source": "cost_for:prior(tape)", "session": sess,
                    "value": t.get("value"), "why": str(t.get("basis"))}
        seen.append(f"{sess}: {t.get('status')} ({t.get('basis') or t.get('level') or 'none'})")
    return {"status": UNMEASURED, "why": f"cost_for({sym}) has no measured spread -- "
                                          + "; ".join(seen)}


def load_cost_surface(base: Path | None = None) -> tuple[dict[str, Any], str]:
    """(the cost surface, where it came from). The published artifact when this host has one;
    otherwise the same surface BUILT from the committed inputs `cost_surfaces.build()` reads, so
    `cost_for` decides on every host rather than an absent file deciding for it."""
    p = (base or BASE) / "reports" / "COST_SURFACES.json"
    doc = _json(p)
    if doc.get("levels") is not None:
        return doc, "reports/COST_SURFACES.json"
    try:
        from research.cost_surfaces import build
        return build(), "cost_surfaces.build() over the committed inputs"
    except Exception as exc:
        return {}, f"unreadable ({type(exc).__name__}: {exc})"


def load_experimental_budget(base: Path | None = None) -> dict[str, Any]:
    return _json((base or BASE) / "reports" / "EXPERIMENTAL_BUDGET.json")


# ------------------------------------------------------------------------------ ban list
def banned_families(family_file: Path | None = None,
                    policy_file: Path | None = None) -> tuple[frozenset[str] | None, str]:
    """(the declared ban list, its sources), or (None, why) when NO source is readable.

    Read, never restated: `research.family_policy.banned_families` carries the permanent bans
    plus the data file; `mt5desk.live_policy` carries the live account's own list. Either one
    readable is a list; neither readable fails CLOSED (I3 refuses)."""
    out: set[str] = set()
    ok: list[str] = []
    bad: list[str] = []
    try:
        from research.family_policy import banned_families as _fp
        out |= {str(k).strip().lower() for k in _fp(family_file)}
        ok.append("research/family_policy")
    except Exception as exc:
        bad.append(f"family_policy unreadable ({type(exc).__name__})")
    try:
        from mt5desk.live_policy import policy
        out |= {str(k).strip().lower() for k in policy(policy_file).banned_families}
        ok.append("mt5desk/live_policy")
    except Exception as exc:
        bad.append(f"live_policy unreadable ({type(exc).__name__})")
    if not ok:
        return None, "; ".join(bad)
    return frozenset(out), "; ".join(ok + bad)


# ------------------------------------------------------------------------------ ledgers
def append_missed_growth(lines: list[dict[str, Any]], path: Path | None = None) -> int:
    """Append lines not already written for (day, rail, sleeve, mode). Never raises; returns
    count. A line with no `mode` (written before the switch existed) is an `enforce` line."""
    p = path or MISSED_GROWTH
    if not lines:
        return 0
    try:
        have: set[tuple[str, str, str]] = set()
        if p.exists():
            for ln in p.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if str(r.get("rail") or "").startswith(RAIL_PREFIX):
                    have.add((str(r.get("day")), str(r.get("rail")), str(r.get("sleeve")),
                              str(r.get("mode") or ENFORCE)))
        fresh = [ln for ln in lines
                 if (str(ln["day"]), str(ln["rail"]), str(ln["sleeve"]),
                     str(ln.get("mode") or ENFORCE)) not in have]
        if not fresh:
            return 0
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for ln in fresh:
                fh.write(json.dumps(ln, default=str) + "\n")
        return len(fresh)
    except Exception:
        return 0


# ------------------------------------------------------------------------------ measurement
def measure_registry(rows: Iterable[Mapping[str, Any]], *,
                     banned: Iterable[str] | None,
                     surface: Mapping[str, Any] | None,
                     budget: Mapping[str, Any] | None = None,
                     live_policy_refuse: Any = None,
                     now: datetime | None = None,
                     enforce_unmeasured_admission: bool | None = None) -> dict[str, Any]:
    """How many LIVE registry rows would remain tradable under every invariant. Pure.

    `live_policy_refuse` (the live policy's `refuse`, optional) is reported as a separate column:
    it is the gateway's EXISTING door, not one of these, and the two are kept apart so the count
    says which rule refused what."""
    live = [dict(r) for r in rows if str(r.get("status") or "").upper() == "LIVE"]
    per: list[dict[str, Any]] = []
    by_inv = dict.fromkeys(INVARIANTS, 0)
    reported = dict.fromkeys(INVARIANTS, 0)
    firsts = dict.fromkeys(INVARIANTS, 0)
    for r in live:
        cost = cost_basis(str(r.get("symbol") or ""), session_of_row(r), surface=surface)
        v = verdict(r, banned=banned, cost=cost, budget=budget, now=now,
                    enforce_unmeasured_admission=enforce_unmeasured_admission)
        pol = live_policy_refuse(r) if callable(live_policy_refuse) else None
        for f in v["refusals"]:
            by_inv[f["invariant"]] += 1
        for f in v["reported"]:
            reported[f["invariant"]] += 1
        if v["first"]:
            firsts[v["first"]] += 1
        per.append({"name": r.get("name"), "symbol": r.get("symbol"),
                    "family": r.get("family"), "ok": v["ok"],
                    "refused_by": [f["invariant"] for f in v["refusals"]],
                    "reported_by": [f["invariant"] for f in v["reported"]],
                    "live_policy": pol, "principal_override": is_override(r),
                    "cost_source": (v["cost"] or {}).get("source")})
    return {"live": len(live),
            "enforce_unmeasured_admission":
                enforcing_unmeasured_admission(enforce_unmeasured_admission),
            "tradable_under_invariants": sum(1 for p in per if p["ok"]),
            "tradable_under_invariants_and_live_policy":
                sum(1 for p in per if p["ok"] and not p["live_policy"]),
            "admitted_by_live_policy_before": sum(1 for p in per if not p["live_policy"]),
            "refused_by_invariant": by_inv, "reported_by_invariant": reported,
            "first_refusal": firsts,
            "principal_overrides": sum(1 for p in per if p["principal_override"]),
            "principal_overrides_tradable": sum(1 for p in per
                                                if p["principal_override"] and p["ok"]),
            "rows": per}
