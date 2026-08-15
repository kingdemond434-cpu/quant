"""THE RETIREMENT LEDGER -- the one place a forward clock may leave the Holm cohort.

WHAT WAS MISSING. `run_clock_retirement_sweep` surfaces every seat that can no longer earn itself
and files a dated, evidenced proposal. Measured on the live box 2026-08-14: m=15 against a cap of
12, ZERO idle, and SIX proposals -- three pre-registered forward kills, two clocks that accrued no
observations at all, and one DEGENERATE instrument fault. Every real candidate behind them was
paying multiplicity for those fifteen seats, and nothing could act on the proposals, because the
only retirement mechanism the desk owned was a `verdict: RETIRED` string inside
`data/axis_shadow_state.json` -- which covers ONE of the three sources the cohort is built from,
lives in a gitignored file, and is therefore a decision no audit can cite (R0160).

So the sweep was a report with no verb. That is the defect class this desk keeps producing, and
naming it in the sweep's own docstring did not stop it being an instance of it.

**RETIREMENT SHRINKS m AND LOOSENS EVERY REMAINING BAR.** That is the phantom-edge direction, and
it is why this module is deliberately awkward:

  * THE LEDGER IS TRACKED, under `docs/research/`, never under `data/`. A retirement is a
    DECISION, and decisions belong in git where they are dated, attributed, diffable and
    reversible. Recorded in gitignored runtime state it would be invisible to every clone and to
    every audit -- the same defect that put real trade evidence somewhere no checkout could cite.
  * AN EVIDENCE-FAILED CLOCK MAY ONLY BE RETIRED AGAINST A LIVE PROPOSAL. `accept()` requires the
    name to appear in
    the CURRENT sweep's RECLAIMABLE set and copies that proposal's evidence verbatim. Retiring by
    hand-typed name is the move that turns "this clock is dead" into "this clock is inconvenient",
    and the two are indistinguishable in a ledger that does not carry the evidence. A principal
    may separately record an account/jurisdiction ineligibility directly in this tracked ledger;
    that frees scarce clock capacity but the high-water multiplicity below still cannot fall.
  * THE MECHANISM OF DEATH IS RECORDED, NOT INFERRED (L1.17). REFUTED retires the ground with the
    clock; UNTESTED returns the hypothesis to the queue. Getting this backwards either buys a dead
    axis a second time at full price, or retires ground nobody ever measured.
  * NOTHING HERE RUNS ON A SCHEDULE. `accept()` is reached only from an explicit human invocation
    of `run_clock_retirement_sweep --accept`. No cycle, no organ and no test calls it.

**WHAT IT DOES NOT DO.** It does not restart a clock, re-file a hypothesis, or free capital. It
removes a name from the cohort and states, in a tracked file, why that was allowed.

Stdlib only. import from libs.research.clock_retirement.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "AUTO_EXCLUDED",
    "LEDGER",
    "RetirementRefused",
    "accept",
    "auto_accept",
    "load",
    "multiplicity_high_water",
    "retired_names",
    "reverse",
]

_ROOT = Path(__file__).resolve().parents[2]

#: TRACKED on purpose. See the module docstring: a retirement recorded under `data/` is a decision
#: no clone can see and no audit can cite, which is indistinguishable from a clock that quietly
#: vanished.
LEDGER = "docs/research/CLOCK_RETIREMENTS.json"

#: Verdict phrases that may NEVER be retired unattended. A clock that accrued NOTHING is the one
#: case where a dead clock and a BROKEN JOIN are byte-identical downstream -- both are the absence
#: of rows, in the same field, on the same artifact. Every other reclaimable verdict is computed
#: FROM observations and so cannot be manufactured by a runner that found none.
AUTO_EXCLUDED: frozenset[str] = frozenset({
    "NO-EVIDENCE",
    "ZERO OBSERVATIONS",
})


class RetirementRefused(RuntimeError):
    """Raised instead of writing. Every refusal names the condition that was not met.

    An exception rather than a False return because the caller is a human at a terminal asking for
    a cohort to shrink: a silently-skipped retirement reads exactly like a successful one, and the
    next `derive_slots` would show the clock still seated with no explanation anywhere.
    """


def load(root: Path | str | None = None) -> dict[str, Any]:
    """The ledger, or an empty one. Never raises -- `derive_slots` calls this on every read."""
    base = Path(root) if root is not None else _ROOT
    try:
        blob = json.loads((base / LEDGER).read_text("utf-8"))
    except (OSError, ValueError):
        return {"retirements": []}
    if not isinstance(blob, dict) or not isinstance(blob.get("retirements"), list):
        return {"retirements": []}
    return blob


def retired_names(root: Path | str | None = None) -> set[str]:
    """Clocks the ledger says have left the cohort.

    A MALFORMED LEDGER RETIRES NOTHING, which is the conservative direction: the cohort stays
    larger, every bar stays tighter, and the failure shows up as seats that will not free rather
    than as bars that quietly loosened.
    """
    out: set[str] = set()
    for row in load(root).get("retirements", []):
        # A REVERSED ROW IS HISTORY, NOT A RETIREMENT. The row stays in the ledger so the record
        # of the mistaken belief survives -- deleting it would erase the only evidence that would
        # let anyone notice the underlying join is still broken.
        if (isinstance(row, dict) and isinstance(row.get("clock"), str) and row["clock"]
                and not row.get("reversed")):
            out.add(row["clock"])
    return out


def multiplicity_high_water(root: Path | str | None = None) -> int:
    """The largest cohort this desk has ever run concurrently, from the ledger's own rows.

    THIS IS WHAT MAKES AUTOMATIC RETIREMENT SAFE, and it is the whole reason retirement stopped
    being a decision that had to be taken by hand.

    The original objection was exact and correct: removing a row SHRINKS m and LOOSENS every
    surviving clock's bar, which is the phantom-edge direction. But that objection conflated two
    different quantities the desk had only ever stored as one number:

        SEATS         a CAPACITY limit. Twelve concurrent forward clocks is what the box, the
                      data and the attention budget support. A dead clock holding one is pure
                      waste and freeing it costs nothing.
        MULTIPLICITY  how many times the desk LOOKED. A clock that ran and failed consumed a
                      trial, and retiring it afterwards does not un-look. This number may never
                      fall, for the same reason you cannot improve a p-value by forgetting an
                      experiment.

    Separating them dissolves the objection entirely: retirement frees the seat and leaves the bar
    exactly where it was. There is then no direction in which automatic retirement can flatter a
    result, so it no longer needs a human in the loop -- what needed the human was the bar
    movement, not the seat.

    ZERO FROM AN EMPTY LEDGER, which is correct rather than merely safe: with no retirements the
    live concurrent count IS the high-water mark, and `derive_slots` takes the max of the two.
    """
    best = 0
    for row in load(root).get("retirements", []):
        if not isinstance(row, dict):
            continue
        for key in ("multiplicity_floor", "seats_before", "cohort_m_before"):
            v = row.get(key)
            if isinstance(v, int):
                best = max(best, v)
                break
    return best


def _auto_eligible(proposal: dict[str, Any]) -> bool:
    """May this proposal be retired UNATTENDED? Measured 2026-08-14, and it cost a real clock.

    THE INCIDENT. `perpdex_funding::aster_BTCUSDT_level_rate::8h` was proposed as RECLAIMABLE with
    "NO-EVIDENCE with zero observations accrued -- it has spent its opportunities and converted
    none of them", and `--accept-all` retired it. It had SEVEN forward observations on disk, in
    `data/perpdex_funding_clock.jsonl`, written by a collector that is cronned, has run all week,
    and holds 184,753 rows. `run_paper_sleeve_forward` reads a different artifact, found no row,
    and published a zero -- which the cohort then read as a MEASUREMENT.

    THE ASYMMETRY THAT MAKES THIS A RULE RATHER THAN A PATCH. The other reclaimable classes cannot
    fail this way:

      * FAILING FORWARD  the clock reached the decision point IT pre-registered and lost there.
                         That verdict is computed FROM its observations, so it cannot be produced
                         by a runner that found none.
      * DEGENERATE       an instrument fault the evaluator diagnosed while looking at real rows.

    ZERO OBSERVATIONS IS THE ONE VERDICT A BROKEN JOIN AND A DEAD CLOCK PRODUCE IDENTICALLY, and
    nothing downstream can tell them apart -- both are the absence of rows, in the same field, on
    the same artifact. So it stays a proposal and a human checks the join. That costs a queue
    position; the alternative destroys forward evidence that cannot be re-earned at any price, and
    the desk has now paid that price once.
    """
    blob = f"{proposal.get('verdict') or ''} {proposal.get('why') or ''}".upper()
    if any(m in blob for m in AUTO_EXCLUDED):
        return False
    obs = proposal.get("observations")
    return not (isinstance(obs, (int, float)) and obs <= 0)


def auto_accept(
    sweep: dict[str, Any],
    *,
    decided_by: str = "cycle",
    root: Path | str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Retire EVERY clock this sweep classified RECLAIMABLE. Returns (rows written, refusals).

    SAFE TO RUN UNATTENDED, AND ONLY BECAUSE OF THE SPLIT ABOVE. Freeing a seat no longer moves
    any bar, so the standing objection to automating this -- that it loosens the fence in the
    phantom-edge direction -- no longer applies to anything it does.

    THE CRITERION IS PRE-REGISTERED IN CODE, NOT CHOSEN PER RUN. `classify_slot` decides
    RECLAIMABLE from the clock's OWN pre-registered kill terms, or from its having converted zero
    observations, or from a DEGENERATE instrument. None of those is a judgement made after seeing
    a result the desk would rather not have. Reading a proposal list and picking the convenient
    entries WOULD be, which is why this takes all of them or none.

    BLOCKED CLOCKS ARE NEVER TOUCHED, and that asymmetry is the point: they cannot be ASSESSED,
    which is a measurement defect upstream. Wrongly reclaiming one destroys forward evidence that
    cannot be re-earned at any price; wrongly protecting one costs a queue position.
    """
    rows: list[dict[str, Any]] = []
    refused: list[str] = []
    for p in sweep.get("proposals", []):
        if not isinstance(p, dict):
            continue
        name = str(p.get("clock") or "")
        if not _auto_eligible(p):
            refused.append(
                f"{name}: ZERO-OBSERVATION clocks are not auto-retired -- see AUTO_EXCLUDED. "
                "It stays proposed; retire it by hand once the join is checked")
            continue
        try:
            rows.append(accept(name, sweep, decided_by=decided_by, root=root))
        except RetirementRefused as exc:
            refused.append(f"{name}: {exc}")
    return rows, refused


def accept(
    clock: str,
    sweep: dict[str, Any],
    *,
    decided_by: str,
    root: Path | str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record one retirement against a live sweep. Returns the ledger row it wrote.

    `sweep` is the payload from `run_clock_retirement_sweep.sweep()`, read fresh. Passing a stale
    one is the failure this signature is shaped to make hard: the proposal, its evidence and its
    requeue class all come from the SAME read, so a ledger row can never cite a verdict that has
    since changed.
    """
    base = Path(root) if root is not None else _ROOT
    stamp = (now or datetime.now(tz=UTC)).isoformat()

    proposals = {str(p.get("clock")): p for p in sweep.get("proposals", [])
                 if isinstance(p, dict)}
    if clock not in proposals:
        blocked = {str(b.get("clock")) for b in sweep.get("blocked", []) if isinstance(b, dict)}
        if clock in blocked:
            raise RetirementRefused(
                f"{clock} is BLOCKED, not reclaimable -- it cannot be ASSESSED, which is a "
                "measurement defect to fix upstream. Wrongly reclaiming it destroys forward "
                "evidence that cannot be re-earned at any price, while wrongly protecting it "
                "costs a queue position; those are not comparable losses")
        if clock in set(sweep.get("protected", [])):
            raise RetirementRefused(
                f"{clock} is ACCRUING -- it is doing exactly what a seat is for. Retiring it "
                "would shrink m and loosen every remaining bar in exchange for nothing")
        raise RetirementRefused(
            f"{clock} is not in the current sweep at all. A retirement typed by hand rather than "
            "taken from a live proposal is how 'this clock is dead' becomes 'this clock is "
            "inconvenient', and a ledger cannot tell the two apart afterwards")

    p = proposals[clock]
    if not str(decided_by).strip():
        raise RetirementRefused(
            "a retirement needs an attributed decider -- an unattributed cohort shrink is exactly "
            "the anonymous bar-loosening this ledger exists to prevent")

    doc = load(base)
    rows = list(doc.get("retirements", []))
    # A REVERSED ROW DOES NOT BLOCK A RE-RETIREMENT. Reversal is not immunity: if the join is
    # checked and the clock really is dead, it retires again, and the ledger then carries both the
    # mistake and the correction rather than silently replacing one with the other.
    if any(isinstance(r, dict) and r.get("clock") == clock and not r.get("reversed")
           for r in rows):
        raise RetirementRefused(f"{clock} is already retired in {LEDGER}")

    seats_before = int(sweep.get("m_now") or 0)
    row = {
        "clock": clock,
        "retired_at": stamp,
        "decided_by": str(decided_by).strip(),
        # THE MECHANISM OF DEATH (L1.17), copied from the proposal rather than re-derived. REFUTED
        # retires the ground with the clock; UNTESTED returns the hypothesis to the queue.
        "requeue_as": p.get("requeue_as"),
        # Verbatim, because the evidence is what makes this reviewable in six months when the
        # artifacts it was computed from have rolled over.
        "verdict": p.get("verdict"),
        "evidence": p.get("evidence"),
        "observations": p.get("observations"),
        "why": p.get("why"),
        "kind": p.get("kind"),
        # CAPACITY, which is what a retirement actually buys. One fewer occupied seat.
        "seats_before": seats_before,
        "seats_after": max(0, seats_before - 1),
        # MULTIPLICITY, which a retirement does NOT buy and must never buy. This number is the
        # floor every future Holm bar is computed against, and it is a HIGH-WATER MARK: a trial
        # that ran, ran. Retiring the clock afterwards frees its seat and changes nothing about
        # the fact that the desk looked. Publishing it in the row makes the guarantee auditable
        # from the ledger alone -- a reader can check that no retirement ever lowered it.
        "multiplicity_floor": seats_before,
        "loosens_bars": False,
    }
    rows.append(row)
    payload = {
        "updated": stamp,
        "retirements": rows,
        "note": ("The ONLY way a forward clock leaves the Holm cohort. Every row is an explicit, "
                 "attributed decision taken against a LIVE sweep proposal, with that proposal's "
                 "evidence copied verbatim. Retiring a clock SHRINKS m and LOOSENS every "
                 "remaining bar -- the phantom-edge direction -- so this file is tracked in git "
                 "rather than runtime state, and no organ, cycle or test may append to it."),
    }
    p_out = base / LEDGER
    p_out.parent.mkdir(parents=True, exist_ok=True)
    p_out.write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    return row


def reverse(clock: str, *, why: str, decided_by: str,
            root: Path | str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Un-retire a clock and put it back in the cohort. THE PATH THIS LEDGER SHIPPED WITHOUT.

    WHY IT WAS MISSING AND WHY THAT WAS WRONG. The ledger was built on the premise that a
    retirement is only ever taken against measured evidence, so reversing one would be re-opening
    a settled question. That premise failed within a day:
    `perpdex_funding::aster_BTCUSDT_level_rate::8h` was retired for "zero observations
    accrued" while holding SEVEN forward observations on disk, because the runner that publishes
    accrual reads a different artifact than the collector writes.
    A ledger with no reversal made a measurement defect permanent.

    THE REVERSAL IS ITSELF LEDGERED, never a deletion. The retirement row stays exactly where it
    is and gains a `reversed` block naming who, when and why. Deleting the row would erase the
    evidence that the desk once believed the clock was dead -- which is the only record that would
    let anyone notice the join is still broken, and the whole reason the ledger is tracked in git.

    IT DOES NOT LOOSEN ANYTHING. Restoring a clock RAISES the seat count and can only TIGHTEN the
    cohort; `multiplicity_high_water` is untouched because the high-water mark never falls anyway.
    So unlike retirement, reversal has no phantom-edge direction and needs no live proposal --
    which is what makes it safe to reach for the moment a false reading is suspected.
    """
    base = Path(root) if root is not None else _ROOT
    stamp = (now or datetime.now(tz=UTC)).isoformat()
    if not str(why).strip() or not str(decided_by).strip():
        raise RetirementRefused(
            "a reversal needs a stated reason and an attributed decider -- an unexplained "
            "un-retirement is indistinguishable from the retirement having been an accident")

    doc = load(base)
    rows = list(doc.get("retirements", []))
    hit = next((r for r in rows
                if isinstance(r, dict) and r.get("clock") == clock and not r.get("reversed")), None)
    if hit is None:
        raise RetirementRefused(f"{clock} is not currently retired in {LEDGER}")
    hit["reversed"] = {"at": stamp, "by": str(decided_by).strip(), "why": str(why).strip()}

    p_out = base / LEDGER
    p_out.parent.mkdir(parents=True, exist_ok=True)
    p_out.write_text(json.dumps({**doc, "updated": stamp, "retirements": rows}, indent=1) + "\n",
                     "utf-8")
    return hit
