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
#: P(survival | information source), fitted over every judged cell (Tier-1 C24, graveyard_model).
GRAVEYARD = DESK / "reports" / "GRAVEYARD_MODEL.json"
#: ONE-SIDED FOR THE SAME REASON `ENGINE_FLOOR` IS, and for one more: a source that has certified
#: nothing is the source the desk has the least evidence about, and the only way to get that
#: evidence is to keep running it. A factor below 1.0 here would make ignorance self-sealing.
GRAVEYARD_FLOOR, GRAVEYARD_CEIL = 1.0, 2.0
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


def _graveyard_factor(leg: str) -> tuple[float, str]:
    """P(survival | information source) from the graveyard, folded onto the leg that mines it. C24.

    THE LARGEST LEDGER ON THE DESK PRICED NOTHING. `graveyard_model` fits P(survival | family,
    symbol, source, mechanism, information_source, session, chart) over every judged cell -- 23k
    of them -- and four organs re-fit it in process to annotate a candidate. Not one of them let
    it move a SECOND of compute, so the desk's own record of what has never worked had no effect
    on what the desk does next.

    THE EXPLORATION FLOOR IS THE POINT AND IT IS ONE-SIDED (C4, and the standing order of
    2026-09-08). A source that has certified nothing yet is the source the desk knows least
    about, and the rate at which it certifies is exactly what more compute would measure; cutting
    it would make the estimate permanent. So this factor runs from par UPWARD only: a source
    certifying above the pooled rate is funded above par, and a source below it runs at par with
    its number published in GRAVEYARD_MODEL.json for a human to argue with.
    """
    try:
        doc = _read(GRAVEYARD)
        if doc.get("status") != "MEASURED":
            return 1.0, f"graveyard: {str(doc.get('why') or 'unmeasured')[:70]}; par"
        table = ((doc.get("survival_by") or {}).get("source")
                 if isinstance(doc.get("survival_by"), dict) else None)
        if not isinstance(table, dict) or leg not in table:
            return 1.0, f"graveyard: no survival row for source {leg!r}; par"
        rows = [float(v.get("p_survival") or 0.0) for v in table.values()
                if isinstance(v, dict)]
        pooled = (sum(rows) / len(rows)) if rows else 0.0
        mine = float((table[leg] or {}).get("p_survival") or 0.0)
        raw = (mine / pooled) if pooled > 0 else 1.0
        f = max(GRAVEYARD_FLOOR, min(GRAVEYARD_CEIL, raw))
        return f, (f"graveyard: P(survival|{leg}) {mine:.5f} vs pooled {pooled:.5f} = x{raw:.2f} "
                   f"-> x{f:.2f} (one-sided: an unproven source keeps its exploration budget)")
    except Exception as exc:
        return 1.0, f"graveyard unread ({type(exc).__name__}); par"


def _meta_factor(leg: str) -> tuple[float, str]:
    """The meta-controller's per-ACTION-KIND price, folded onto the leg that executes that kind.

    THE THIRD FACTOR THE LEDGER ASKED FOR (Tier-1 Q12). The bandit prices research ACTIONS and
    the ladder prices BREADTH; `meta_controller` ranks the nine action kinds in dE[log W] per day
    (or, while the compute price is UNMEASURED, in information gain per cell) and until now
    nothing read that ranking to decide what runs. `meta_controller.KIND_LEGS` already declares
    which hourly leg executes each kind, so the join is the controller's own table, not a new one.

    ONE-SIDED, FOR THE REASON `ENGINE_FLOOR` RECORDS. The ledger's own next_step said a leg
    priced below the median should get FEWER seconds. That is a shrink on research, and the
    principal's standing order of 2026-09-08 is that no session lowers the desk's aggressiveness
    by fiat; nothing else claims the seconds it would free, so the leg would simply do less work
    for no measured gain. A kind priced ABOVE the median is funded above par; a kind priced below
    it runs at par and its price is published in META_CONTROLLER.json for a human to argue with.
    """
    try:
        import meta_controller
        doc = _read(DESK / "reports" / "META_CONTROLLER.json")
        boards = doc.get("boards")
        if not isinstance(boards, dict):
            return 1.0, "meta controller: no boards published; par"
        board = None
        for name, key in (("delta_elog", "delta_elog_per_day"), ("information", "info_per_cell"),
                          ("information", "info_gain_nats")):
            cand = boards.get(name)
            if isinstance(cand, dict) and cand.get("status") == "OK" and cand.get("rows"):
                board, value_key = cand, key
                break
        if board is None:
            return 1.0, "meta controller: no board is OK this epoch; par"
        best: dict[str, float] = {}
        for row in board.get("rows") or []:
            if not isinstance(row, dict):
                continue
            v = row.get(value_key)
            if isinstance(v, (int, float)):
                k = str(row.get("kind"))
                best[k] = max(best.get(k, float("-inf")), float(v))
        if not best:
            return 1.0, f"meta controller: no row carries {value_key!r}; par"
        kinds = [k for k, legs in meta_controller.KIND_LEGS.items() if leg in legs]
        mine = [best[k] for k in kinds if k in best]
        if not mine:
            return 1.0, f"meta controller: leg {leg!r} executes no priced kind; par"
        ranked = sorted(best.values())
        median = ranked[len(ranked) // 2] if len(ranked) % 2 else (
            (ranked[len(ranked) // 2 - 1] + ranked[len(ranked) // 2]) / 2.0)
        raw = (max(mine) / median) if median > 0 else 1.0
        f = max(1.0, min(2.0, raw))
        return f, (f"meta controller: leg {leg!r} serves kind(s) {kinds} priced "
                   f"{max(mine):.4g} on the {value_key} board vs median {median:.4g} = x{raw:.2f}"
                   f" -> x{f:.2f} (one-sided: it may fund above par and never below it)")
    except Exception as exc:
        return 1.0, f"meta controller unread ({type(exc).__name__}); par"


def _paradigm_factor(leg: str) -> tuple[float, str]:
    """The bandit's PARADIGM share for the paradigm this leg belongs to (Tier-1 Q18).

    `bandit.paradigm_shares` prices a paradigm by its volume x its INDEPENDENCE -- one minus the
    share of its cells some other paradigm also proposed -- so two searches that keep rediscovering
    each other are one search with two bills, and the budget stops paying twice. The join is the
    census's own `legs` column, never a list maintained here.

    ONE-SIDED, for the reason `ENGINE_FLOOR` records: a paradigm priced below par runs at par and
    its redundancy is published in SEARCH_PARADIGMS.json. Nothing here starves a search.
    """
    try:
        from libs.research import bandit as _bandit
        doc = _bandit.paradigm_shares()
        arms = doc.get("arms") or {}
        shares_ = doc.get("shares") or {}
        if not arms:
            return 1.0, f"paradigm census unmeasured ({doc.get('why', '')[:80]}); par"
        mine = [n for n, row in arms.items() if leg in (row.get("legs") or ())]
        if not mine:
            return 1.0, f"paradigm census: leg {leg!r} belongs to no paradigm; par"
        baseline = 1.0 / max(1, len(shares_))
        raw = max(float(shares_.get(n, 0.0)) for n in mine) / baseline if baseline > 0 else 1.0
        f = max(1.0, min(2.0, raw))
        return f, (f"paradigm census: leg {leg!r} is {mine} at share "
                   f"{max(float(shares_.get(n, 0.0)) for n in mine):.4f} vs equal share "
                   f"{baseline:.4f} = x{raw:.2f} -> x{f:.2f} (one-sided)")
    except Exception as exc:
        return 1.0, f"paradigm census unread ({type(exc).__name__}); par"


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
    meta, meta_why = _meta_factor(leg)
    para, para_why = _paradigm_factor(leg)
    grave, grave_why = _graveyard_factor(leg)
    factor = max(FLOOR, min(CEIL, (share / baseline if baseline > 0 else 1.0) * ladder * dept
                            * archive * auction * engine * meta * para * grave))
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
                # E[dElogW] PER ACTION KIND, FOLDED ONTO THE LEG THAT EXECUTES IT (Tier-1 Q12).
                # The third factor: compute follows the meta-controller's own ranking, not only
                # the bandit's arms and the breadth ladder.
                "meta_factor": round(meta, 3), "meta_why": meta_why,
                # P(SURVIVAL | INFORMATION SOURCE) FROM THE GRAVEYARD (Tier-1 C24). 23k judged
                # cells finally price an hour: a source that certifies above the pooled rate is
                # funded above par, and one below it keeps its exploration budget at par.
                "graveyard_factor": round(grave, 3), "graveyard_why": grave_why,
                # WHICH PARADIGM THIS LEG IS, AND HOW INDEPENDENT IT IS (Tier-1 Q18).
                "paradigm_factor": round(para, 3), "paradigm_why": para_why,
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
