"""THE BANDIT'S SHARES SET THE RESEARCH LEGS' TIME BUDGETS -- authority, measured.

The closed-loop attestation asks `research.evig_controller_authoritative` and the honest answer
was no: `research_bandit` priced its arms and the hourly cycle ran every leg on a fixed budget
regardless (Tier-1 B11/B27). This is the smallest true authority: a budgeted leg asks here for
its seconds, and the answer is the leg's base budget scaled by the bandit's current share of the
arms that leg serves against those arms' equal-share baseline, clipped to [FLOOR, CEIL] so a
noisy share can neither starve a leg nor let it run away. Every answer is recorded in
reports/RESEARCH_BUDGET.json with the arms and the share behind it, and `research_bandit` reads
that record back to say whether it was authoritative this hour -- the claim is made by the
organ that OBEYED, never by the one that priced.

An unreadable bandit report returns the base budget and records that it did, so the cycle never
stalls on a missing price and the attestation never reads an absence as authority.

THE DEPARTMENT FACTOR NOW DECLARES WHETHER IT DECIDED (review R4, 2026-09-17). `budget_s` has
always multiplied by `research_departments`' elastic factor, and the record could not tell an
ALLOCATION from a REPORT: an exchange with three unmeasured departments produced the same shape
of number as one with every input measured. `research_departments.spend_factor_for` now answers
(factor, authoritative, why) and both halves land on the leg's record as `department_factor` and
`department_authoritative`, so RESEARCH_BUDGET.json shows which of the two set the seconds.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
BANDIT = DESK / "reports" / "RESEARCH_BANDIT.json"
#: The per-(method, domain) yield table's leg-keyed share vector (Tier-1 W17, engine_registry).
ENGINE = DESK / "reports" / "ENGINE_REGISTRY.json"
#: THE ENGINE FACTOR IS ONE-SIDED AND THE FLOOR OF 1.0 IS WHY. Measured 2026-09-23: the first
#: version clipped to [0.5, 2.0] like every other factor here, and `deepen` -- whose leg share is
#: 0.024 against an equal share of 0.125 -- came back at x0.50, taking 600s to 470s. That is a
#: SHRINK ON RESEARCH, and the principal's standing order is that no session lowers the desk's
#: aggressiveness by fiat. Nothing else claims the seconds it would have freed, so the leg simply
#: does less work. A high-yield leg may be funded ABOVE par; a low-yield one runs at par and its
#: evidence is published in ENGINE_REGISTRY.json for a human to argue with.
ENGINE_FLOOR, ENGINE_CEIL = 1.0, 2.0
AUCTION = DESK / "reports" / "RESEARCH_AUCTION.json"
OUT = DESK / "reports" / "RESEARCH_BUDGET.json"
FLOOR, CEIL = 0.5, 2.0
#: Which bandit arms each budgeted leg serves. The baseline for a leg is the equal share of its
#: arms among all arms, so a leg scales up only when the bandit prices its arms above average.
LEG_ARMS: dict[str, tuple[str, ...]] = {
    "alpha_evolution": ("mutate_survivor", "combine_survivors", "new_mechanism"),
    "deepen": ("new_mechanism", "external_screen", "alt_data_hypothesis", "failure_derived"),
}


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ladder_factor(leg: str) -> float:
    """The breadth ladder's per-leg factor (research is paid in n_eff per compute-hour);
    1.0 when the ladder is unmeasured or unavailable."""
    try:
        import breadth_ladder
        return float(breadth_ladder.budget_factor(leg))
    except Exception:
        return 1.0


def _department_factor(leg: str) -> tuple[float, bool, str]:
    """(factor, authoritative, why) from the resource exchange.

    IT MATTERS WHICH ONE DECIDED. `research_departments.spend` allocates the binding resource by
    measured marginal value, but only when every input behind it is measured; otherwise the
    elastic REPORTING factor is what multiplies here. Both arrive as a float and the leg runs
    either way, so the only way a reader can tell an allocation from a report is if this records
    which it got -- `department_authoritative` on the leg's budget record, and nowhere else.

    An unavailable exchange is 1.0, not authoritative, with the exception named: a missing organ
    must never read as a decision.
    """
    try:
        import research_departments
        factor, authoritative, why = research_departments.spend_factor_for(leg)
        return float(factor), bool(authoritative), str(why)
    except Exception as exc:
        return 1.0, False, f"research_departments unavailable: {type(exc).__name__}: {exc}"


def _archive_factor(leg: str) -> float:
    """The active ResearchOS variant's leg factor (research_os_archive.active_policy); 1.0 when
    the archive is absent or refuses its own policy -- the incumbent is every factor at 1.0."""
    try:
        import research_os_archive
        f = float(research_os_archive.leg_factor(leg))
        return f if 0.0 < f < 10.0 else 1.0
    except Exception:
        return 1.0


def _engine_factor(leg: str) -> tuple[float, str]:
    """The engine registry's measured P(certified | method, domain), folded onto this leg.

    THE BANDIT PRICES ARMS, NOT DOMAINS (Tier-1 W17). Its arms are engines, so an engine that has
    never certified anything in metals and one that certifies routinely in FX were priced by the
    same number. `engine_registry` publishes the per-(method, domain) yield table and normalises
    it onto the legs those methods run on; this reads that vector exactly as `budget_s` already
    reads the bandit's, against the equal-share baseline.

    IT ONLY EVER ADDS. Par (1.0) whenever the report is absent, stale, does not name this leg,
    or prices it below the equal share -- see ENGINE_FLOOR for the measurement that forced that.
    Compute follows yield by funding what certifies ABOVE par, never by starving what has not yet.
    """
    try:
        doc = _read(ENGINE)
        shares = doc.get("shares")
        if not isinstance(shares, dict) or leg not in shares:
            return 1.0, f"engine registry: no share for leg {leg!r}; par"
        baseline = 1.0 / max(1, len(shares))
        raw = float(shares[leg]) / baseline if baseline > 0 else 1.0
        f = max(ENGINE_FLOOR, min(ENGINE_CEIL, raw))
        return f, (f"engine registry: leg share {float(shares[leg]):.4f} vs equal share "
                   f"{baseline:.4f} = x{raw:.2f} -> x{f:.2f} (one-sided: this factor may fund a "
                   f"leg above par and may never take one below it)")
    except Exception as exc:
        return 1.0, f"engine registry unread ({type(exc).__name__}); par"


def _auction_factor(leg: str) -> tuple[float, str]:
    """The research auction's cleared share for this leg's DEPARTMENT (Tier-5 mandate 110).

    The auction is the epoch's price: a department that converts hours into enqueued work, that
    addresses open portfolio bounties, that owns the binding funnel stage or that faces a
    replenishment gap clears ABOVE par, and one that did neither clears at the same FLOOR this
    function already lives under. It is read, never written, and 1.0 whenever the report is
    absent or the leg belongs to no department -- an unpriced hour runs at par, not at nothing.
    """
    try:
        import hourly_cycle
        dept = str(hourly_cycle.department_of(leg))
        doc = _read(AUCTION)
        shares = doc.get("factors")
        if not isinstance(shares, dict) or dept not in shares:
            return 1.0, f"auction: no cleared share for department {dept!r}; par"
        f = float(shares[dept])
        if not 0.0 < f < 10.0:
            return 1.0, f"auction: share for {dept!r} out of range; par"
        epoch = doc.get("epoch_id")
        return f, f"auction: department {dept} cleared x{f:.2f} for epoch {epoch}"
    except Exception as exc:
        return 1.0, f"auction unread ({type(exc).__name__}); par"


def budget_s(leg: str, base: float) -> tuple[int, dict[str, Any]]:
    """(seconds, record) for `leg`: base x (share of its arms / equal-share baseline), clipped."""
    bandit = _read(BANDIT)
    shares = bandit.get("shares") if isinstance(bandit.get("shares"), dict) else {}
    arms = LEG_ARMS.get(leg, ())
    rec: dict[str, Any] = {"leg": leg, "base_s": float(base), "arms": list(arms),
                           "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                           "bandit_at": bandit.get("generated_utc")}
    dept, dept_auth, dept_why = _department_factor(leg)
    if not shares or not arms or not all(isinstance(shares.get(a), (int, float)) for a in arms):
        rec.update({"applied_s": int(base), "factor": 1.0, "applied": False,
                    "department_factor": round(dept, 3), "department_authoritative": dept_auth,
                    "department_why": dept_why,
                    "why": "bandit shares unreadable for these arms; base budget"})
        return int(base), rec
    share = float(sum(float(shares[a]) for a in arms))
    baseline = len(arms) / max(1, len(shares))
    ladder = _ladder_factor(leg)
    archive = _archive_factor(leg)
    auction, auction_why = _auction_factor(leg)
    engine, engine_why = _engine_factor(leg)
    factor = max(FLOOR, min(CEIL, (share / baseline if baseline > 0 else 1.0) * ladder * dept
                            * archive * auction * engine))
    applied = round(base * factor)
    rec.update({"share": round(share, 4), "baseline": round(baseline, 4),
                "ladder_factor": round(ladder, 3), "department_factor": round(dept, 3),
                # DID THE DEPARTMENT FACTOR DECIDE, OR MERELY REPORT? The number multiplies either
                # way; this is the only field that says which, and the attestation reads it here.
                "department_authoritative": dept_auth, "department_why": dept_why,
                "archive_factor": round(archive, 3),
                # THE AUCTION'S PRICE FOR THIS LEG'S DEPARTMENT (Tier-5 mandate 110). It is a
                # multiplier like the others and the same [FLOOR, CEIL] clip holds, so the
                # auction can fund a winner above par and can never take a leg below the floor
                # the bandit already lived under.
                "auction_factor": round(auction, 3), "auction_why": auction_why,
                # WHERE THE YIELD TABLE SENT THIS HOUR (Tier-1 W17). `engine_registry` measures
                # P(certified | method, domain) and normalises it onto legs; this is the leg's
                # share of that, at par when the table is absent or does not name it.
                "engine_factor": round(engine, 3), "engine_why": engine_why,
                "factor": round(factor, 3), "applied_s": applied, "applied": True,
                "why": f"share {share:.3f} of arms {list(arms)} vs equal-share baseline "
                       f"{baseline:.3f} -> x{factor:.2f}, clipped to [{FLOOR}, {CEIL}]"
                       f"; department factor x{dept:.2f} "
                       f"({'AUTHORITATIVE' if dept_auth else 'reported only'})"})
    return applied, rec


def record(rec: dict[str, Any]) -> None:
    """Merge one leg's record into RESEARCH_BUDGET.json (per-leg, latest wins)."""
    doc = _read(OUT)
    legs: dict[str, Any] = dict(doc["legs"]) if isinstance(doc.get("legs"), dict) else {}
    legs[str(rec.get("leg"))] = rec
    doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "legs": legs,
           "n_department_authoritative": sum(
               1 for v in legs.values()
               if isinstance(v, dict) and v.get("department_authoritative")),
           "rule": "a leg's seconds are the bandit's share of its arms against an equal-share "
                   "baseline, clipped; `applied` false means the base budget ran, and "
                   "`department_authoritative` false means the resource exchange REPORTED its "
                   "factor rather than deciding it"}
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    except OSError:
        pass


def authority(max_age_h: float = 3.0) -> tuple[bool, str]:
    """Was the bandit obeyed recently? True when a fresh RESEARCH_BUDGET.json shows at least one
    leg that applied a bandit-derived budget."""
    import time as _time
    doc = _read(OUT)
    legs = doc.get("legs") if isinstance(doc.get("legs"), dict) else {}
    if not legs:
        return False, "no RESEARCH_BUDGET.json: no leg has asked the bandit for its budget"
    try:
        age_h = (_time.time() - OUT.stat().st_mtime) / 3600.0
    except OSError:
        return False, "RESEARCH_BUDGET.json unreadable"
    if age_h > max_age_h:
        return False, f"RESEARCH_BUDGET.json is {age_h:.1f}h old"
    applied = [f"{k}={v.get('applied_s')}s (x{v.get('factor')})" for k, v in legs.items()
               if isinstance(v, dict) and v.get("applied")]
    if not applied:
        return False, "every budgeted leg ran on its base budget (bandit shares unreadable)"
    return True, f"the hourly cycle spent by the bandit's shares: {', '.join(applied)}"
