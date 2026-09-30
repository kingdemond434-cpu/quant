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

AUTHORITY IS EARNED BY A MEASURED GAIN, NOT BY BEING OBEYED (Tier S admission rule, 2026-09-30).
A verifier found `authoritative: false` and the honest reason was deeper than stale shares: the
budget had no contract, so "the leg spent what the bandit said" was the whole claim, and nothing
measured whether the seconds it added bought anything. Now:

  CONTRACT   INFO_PER_COMPUTE -- a leg-hour the budget funds above its floor yields more output
             (the leg's own artifact: proposals for alpha_evolution, decisions for deepen) than a
             held-out leg-hour at the floor, judged by `libs.tiers.control_arm` (Welch, one-sided
             5%) on the trial ledger `data/research_budget_trials.jsonl`, same desk, same hours.
  FLOOR      every leg keeps its base (x1.0) in every hour and every arm: no miner is starved,
             no information gathering, raw mining or generation is cut.
  SURPLUS    the uplift above the floor comes ONLY out of the leg's department's MEASURED spare
             seconds (`cycle_pricing.spare_capacity`); unmeasured spare grants nothing above
             the floor. The budget reallocates surplus; it never takes from another leg.
  AUTHORITY  ADMITTED: the uplift runs in every treated hour and the record says
             `authoritative: true` with the control-arm evidence. UNMEASURED/UNDECIDED: the
             uplift runs as the trial arm that produces the measurement, `authoritative: false`.
             REJECTED: the leg falls back to its floor (the current allocation) with the reason
             recorded; the verdict re-derives from a rolling window, so it expires by itself.
  CONTROL    a fixed hash-assigned 20% of leg-hours (`control_arm.in_control`, salt
             "research_budget") runs at the floor -- the held-out arm every steering organ has.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
if str(DESK.parent.parent) not in sys.path:        # `libs` (the control arm) from the desk root
    sys.path.insert(0, str(DESK.parent.parent))
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
#: THE FLOOR IS PAR (2026-09-29, Tier-1 #10). It was 0.5, so a bandit share below the equal
#: share halved `alpha_evolution`'s seconds -- a generator throttled on a price nobody had shown
#: raises E[log W]. The principal's standing order is that no miner is starved: every leg keeps
#: its base, and the price only ever funds a leg ABOVE it, exactly as ENGINE_FLOOR and
#: GRAVEYARD_FLOOR already do for their own factors.
FLOOR, CEIL = 1.0, 2.0
#: Which bandit arms each budgeted leg serves. The baseline for a leg is the equal share of its
#: arms among all arms, so a leg scales up only when the bandit prices its arms above average.
LEG_ARMS: dict[str, tuple[str, ...]] = {
    "alpha_evolution": ("mutate_survivor", "combine_survivors", "new_mechanism"),
    "deepen": ("new_mechanism", "external_screen", "alt_data_hypothesis", "failure_derived"),
}

#: THE BUDGET'S CONTRACT (subsystem admission rule, libs/tiers/contracts.py). The same block is
#: declared in docs/research/tier_s_program.json `leg_contracts` so the Tier S organ records its
#: hourly verdict beside every other contract; `control_arm.admitted` is 1.0 when the held-out
#: comparison ADMITTED the uplift for at least one leg.
CONTRACT: dict[str, Any] = {"gain": "INFO_PER_COMPUTE", "metric": "control_arm.admitted",
                            "better": "up", "bar": 1.0, "organ": "report:RESEARCH_BUDGET.json"}
#: One row per budgeted leg-run that was a trial unit (treated with an uplift, or held out when
#: one would have been granted), with the output the leg's own artifact recorded for that run.
TRIALS = DESK / "data" / "research_budget_trials.jsonl"
#: The verdict is re-derived from this rolling window, so a REJECTED reading expires by itself
#: and the trial resumes: a verdict about last month's desk is not a verdict about this one.
TRIAL_WINDOW_D = 14.0
CONTROL_SALT = "research_budget"
#: What one run of each leg PRODUCED, read from the leg's own artifact after it ran:
#: (path under the desk, its timestamp key, the key whose size is the output).
LEG_OUTPUT: dict[str, tuple[str, str, str]] = {
    "alpha_evolution": ("reports/alpha_evolution.json", "generated_at", "proposals"),
    "deepen": ("data/hypotheses/deepened_candidates.json", "built_at", "dispositions"),
}
#: Legs whose budget is SECONDS on a department clock, so their uplift must fit that clock's
#: measured spare. `deepen`'s budget is a task count (0 = the whole queue) and has no clock.
SECONDS_LEGS = frozenset({"alpha_evolution"})


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


def _hour_key(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H")


def _in_control(leg: str, now: datetime) -> bool:
    """Is this leg-hour in the held-out arm? False when the control arm cannot load: then no
    hour is held out and the contract stays UNMEASURED, which is a verdict, never a pass."""
    try:
        from libs.tiers import control_arm
        return bool(control_arm.in_control(f"{leg}|{_hour_key(now)}", CONTROL_SALT))
    except Exception:
        return False


def _surplus_s(leg: str) -> tuple[float | None, str]:
    """(measured spare seconds on this leg's department clock, why); None when unmeasured.

    The only compute the budget may hand out above a floor (`cycle_pricing.spare_capacity`):
    seconds the clock already owns and did not use. A leg whose budget is not seconds has no
    clock to fit, so its surplus is unbounded by this and says so."""
    if leg not in SECONDS_LEGS:
        return float("inf"), f"{leg}'s budget is a count, not seconds on a clock"
    try:
        import cycle_pricing  # type: ignore[import-not-found]
        cap = cycle_pricing.spare_capacity()
        if cap.get("status") != "MEASURED":
            return None, str(cap.get("why") or "spare capacity unmeasured")
        dept = str(cycle_pricing._department_of(leg))
        spare = (cap.get("spare_s") or {}).get(dept)
        if not isinstance(spare, (int, float)):
            return None, f"department {dept!r} has no measured spare in the compute ledger"
        return float(spare), f"department {dept!r} measured spare {float(spare):.0f}s/hour"
    except Exception as exc:
        return None, f"spare capacity unread ({type(exc).__name__}: {exc})"


def _trial_rows(leg: str, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(tz=UTC)
    out: list[dict[str, Any]] = []
    try:
        lines = TRIALS.read_text(encoding="utf-8", errors="replace").splitlines()[-20000:]
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
            t = datetime.fromisoformat(str(r.get("at")))
        except (ValueError, TypeError):
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        if (r.get("leg") != leg or not isinstance(r.get("outcome"), (int, float))
                or (now - t).total_seconds() > TRIAL_WINDOW_D * 86400.0):
            continue
        out.append(r)
    return out


def contract_verdict(leg: str, now: datetime | None = None) -> dict[str, Any]:
    """The control arm's verdict on this leg's uplift: treated leg-runs (the budget funded them
    above the floor) against held-out ones (an uplift was due and withheld), by the output each
    run's own artifact recorded. ADMITTED / REJECTED / UNDECIDED / UNMEASURED."""
    rows = _trial_rows(leg, now)
    treated = [float(r["outcome"]) for r in rows if r.get("arm") == "treated"]
    control = [float(r["outcome"]) for r in rows if r.get("arm") == "control"]
    try:
        from libs.tiers import control_arm
        v = dict(control_arm.compare(treated, control))
    except Exception as exc:
        return {"verdict": "UNMEASURED", "n_treated": len(treated), "n_control": len(control),
                "why": f"control arm unavailable ({type(exc).__name__}: {exc})"}
    v.setdefault("why", f"Welch t={v.get('t')} over {len(treated)} treated vs {len(control)} "
                        f"held-out leg-runs in the last {TRIAL_WINDOW_D:g} days")
    v["window_d"] = TRIAL_WINDOW_D
    return v


def run_output(leg: str, since: str | None) -> tuple[float | None, str]:
    """(what this leg's run produced, why) from its own artifact, only if written at or after
    `since` -- an artifact from an earlier run is not this run's output."""
    spec = LEG_OUTPUT.get(leg)
    if spec is None:
        return None, f"no output artifact declared for {leg}"
    rel, stamp_key, key = spec
    doc = _read(DESK / rel)
    try:
        at = datetime.fromisoformat(str(doc.get(stamp_key)))
        t0 = datetime.fromisoformat(str(since))
    except (TypeError, ValueError):
        return None, f"{rel}: no readable {stamp_key!r} (or run start)"
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=UTC)
    if at < t0:
        return None, f"{rel} predates this run ({at.isoformat()} < {t0.isoformat()})"
    val = doc.get(key)
    if isinstance(val, dict):
        n = float(sum(v for v in val.values() if isinstance(v, (int, float))
                      and not isinstance(v, bool))) if key == "dispositions" else float(len(val))
    elif isinstance(val, list):
        n = float(len(val))
    elif isinstance(val, (int, float)) and not isinstance(val, bool):
        n = float(val)
    else:
        return None, f"{rel}: {key!r} is absent or not countable"
    return n, f"{rel} {key} = {n:g}"


def observe(leg: str, rec: dict[str, Any]) -> dict[str, Any] | None:
    """After the leg ran: append its output to the trial ledger when this run was a trial unit.
    Returns the row, or None when the run was not a trial or its output could not be read (an
    unread output is never recorded as zero)."""
    if not rec.get("trial"):
        return None
    val, why = run_output(leg, rec.get("at"))
    if val is None:
        return None
    row = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "leg": leg,
           "hour": rec.get("hour"), "arm": rec.get("arm"), "base_s": rec.get("base_s"),
           "applied_s": rec.get("applied_s"), "extra_s": rec.get("extra_s"),
           "extra_due_s": rec.get("extra_due_s"), "outcome": val, "outcome_basis": why}
    try:
        TRIALS.parent.mkdir(parents=True, exist_ok=True)
        with TRIALS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        return None
    return row


def _govern(leg: str, base: float, wanted: int, rec: dict[str, Any],
            now: datetime | None = None) -> int:
    """The seconds the budget may actually grant: the floor always, and the uplift only out of
    measured surplus, only in a treated hour, and never once the contract is REJECTED."""
    now = now or datetime.now(tz=UTC)
    floor_s = int(base)
    want_extra = max(0, int(wanted) - floor_s)
    surplus, surplus_why = _surplus_s(leg)
    due = 0 if surplus is None else int(min(float(want_extra), max(0.0, surplus)))
    verdict = contract_verdict(leg, now)
    v = str(verdict.get("verdict"))
    control = _in_control(leg, now)
    if floor_s <= 0:
        arm, extra, why = "none", 0, "the base is the leg's unlimited sentinel; nothing to govern"
    elif due <= 0:
        arm, extra = "none", 0
        why = (f"no uplift due (wanted +{want_extra}; surplus: {surplus_why}); the floor runs"
               if want_extra else "the price wants nothing above the floor")
    elif control:
        arm, extra = "control", 0
        why = (f"held-out hour (control arm): the floor runs so the uplift's gain can be "
               f"measured; +{due}s was due")
    elif v == "REJECTED":
        arm, extra = "fallback", 0
        why = (f"contract REJECTED ({verdict.get('why')}): falls back to the current allocation "
               f"(the floor); +{due}s withheld until the verdict ages out of the window")
    else:
        arm, extra = "treated", due
        why = (f"+{due}s of measured surplus granted above the floor ({surplus_why}); contract "
               f"{v}" + ("" if v == "ADMITTED" else ": this hour is the trial that measures it"))
    authoritative = arm == "treated" and v == "ADMITTED"
    rec.update({"hour": _hour_key(now), "arm": arm, "wanted_s": int(wanted),
                "floor_s": floor_s, "extra_wanted_s": want_extra, "extra_due_s": due,
                "extra_s": extra, "surplus_s": surplus, "surplus_why": surplus_why,
                "contract": verdict, "trial": arm in ("treated", "control"),
                "authoritative": authoritative, "governed_why": why})
    return floor_s + extra


def budget_s(leg: str, base: float) -> tuple[int, dict[str, Any]]:
    """(seconds, record) for `leg`: base x (share of its arms / equal-share baseline), clipped,
    then GOVERNED (`_govern`): the floor always, the uplift only from measured surplus and only
    while the budget's contract has not been measured against it."""
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
                    "department_why": dept_why, "authoritative": False, "trial": False,
                    "arm": "none", "governed_why": "bandit shares unreadable; base budget",
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
    wanted = round(base * factor)
    applied = _govern(leg, base, wanted, rec)
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
                # `factor` is the PRICE (what the budget asked for); `applied_s` is what it was
                # GRANTED after `_govern`, and `applied` says the budget moved seconds this hour.
                "factor": round(factor, 3), "applied_s": applied,
                "applied": rec.get("arm") == "treated",
                "why": f"share {share:.3f} of arms {list(arms)} vs equal-share baseline "
                       f"{baseline:.3f} -> x{factor:.2f}, clipped to [{FLOOR}, {CEIL}]"
                       f"; department factor x{dept:.2f} "
                       f"({'AUTHORITATIVE' if dept_auth else 'reported only'})"
                       f"; {rec.get('governed_why')}"})
    return applied, rec


def record(rec: dict[str, Any]) -> None:
    """Merge one leg's record into RESEARCH_BUDGET.json (per-leg, latest wins)."""
    doc = _read(OUT)
    legs: dict[str, Any] = dict(doc["legs"]) if isinstance(doc.get("legs"), dict) else {}
    legs[str(rec.get("leg"))] = rec
    ok, why = _judge(legs)
    arm = {k: (v.get("contract") or {}) for k, v in legs.items()
           if isinstance(v, dict) and isinstance(v.get("contract"), dict)}
    doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "legs": legs,
           # AUTHORITY, WITH ITS REASON (Tier S admission rule): true only when a leg ran on a
           # budget above its floor in a treated hour AND the held-out comparison ADMITTED it.
           "authoritative": ok, "authority_why": why,
           "contract": dict(CONTRACT),
           "control_arm": {"admitted": float(any(str(v.get("verdict")) == "ADMITTED"
                                                 for v in arm.values())),
                           "legs": arm, "salt": CONTROL_SALT, "trials": str(TRIALS.name)},
           "n_department_authoritative": sum(
               1 for v in legs.values()
               if isinstance(v, dict) and v.get("department_authoritative")),
           "rule": "a leg's price is the bandit's share of its arms against an equal-share "
                   "baseline, clipped to [1, 2]; the floor (x1.0, its base) always runs, and the "
                   "uplift above it is granted only out of the department clock's measured "
                   "spare, only in a treated hour, and not while the contract is REJECTED; "
                   "`applied` false means the floor ran, and `department_authoritative` false "
                   "means the resource exchange REPORTED its factor rather than deciding it"}
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    except OSError:
        pass


def _judge(legs: dict[str, Any]) -> tuple[bool, str]:
    """(authoritative, why) from the per-leg records: the budget decided compute only where it
    moved seconds above a floor AND its contract's held-out comparison ADMITTED that uplift."""
    rows = {k: v for k, v in legs.items() if isinstance(v, dict)}
    if not rows:
        return False, "no leg has asked the budget for its seconds"
    auth = [f"{k}={v.get('applied_s')}s (floor {v.get('floor_s', v.get('base_s'))}s, "
            f"contract ADMITTED t={(v.get('contract') or {}).get('t')})"
            for k, v in rows.items() if v.get("authoritative")]
    if auth:
        return True, ("the hourly cycle spent by the budget, and the held-out arm measured the "
                      f"gain: {', '.join(auth)}")
    notes = []
    for k, v in rows.items():
        c = v.get("contract") or {}
        if v.get("arm") == "treated":
            notes.append(f"{k}: uplift ran as the trial, contract {c.get('verdict')} "
                         f"({c.get('why')})")
        elif v.get("arm") in ("control", "fallback", "none"):
            notes.append(f"{k}: {v.get('governed_why')}")
        else:
            notes.append(f"{k}: floor ran ({v.get('why')})")
    return False, "not authoritative -- " + "; ".join(notes)


def authority(max_age_h: float = 3.0) -> tuple[bool, str]:
    """Did the budget DECIDE compute recently, on a measured gain? True only when a fresh
    RESEARCH_BUDGET.json shows a leg that ran above its floor in a treated hour with the
    contract ADMITTED; otherwise false, with the reason."""
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
    return _judge(legs)
