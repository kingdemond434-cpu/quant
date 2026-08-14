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
  * A CLOCK MAY ONLY BE RETIRED AGAINST A LIVE PROPOSAL. `accept()` requires the name to appear in
    the CURRENT sweep's RECLAIMABLE set and copies that proposal's evidence verbatim. Retiring by
    hand-typed name is the move that turns "this clock is dead" into "this clock is inconvenient",
    and the two are indistinguishable in a ledger that does not carry the evidence.
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
    "LEDGER",
    "RetirementRefused",
    "accept",
    "load",
    "retired_names",
]

_ROOT = Path(__file__).resolve().parents[2]

#: TRACKED on purpose. See the module docstring: a retirement recorded under `data/` is a decision
#: no clone can see and no audit can cite, which is indistinguishable from a clock that quietly
#: vanished.
LEDGER = "docs/research/CLOCK_RETIREMENTS.json"


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
        if isinstance(row, dict) and isinstance(row.get("clock"), str) and row["clock"]:
            out.add(row["clock"])
    return out


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
    if any(isinstance(r, dict) and r.get("clock") == clock for r in rows):
        raise RetirementRefused(f"{clock} is already retired in {LEDGER}")

    m_before = int(sweep.get("m_now") or 0)
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
        # What the desk gave up to gain the seat, stated at the moment of the decision so nobody
        # has to reconstruct it: one fewer row in the cohort is a LOOSER bar for every survivor.
        "cohort_m_before": m_before,
        "cohort_m_after": max(0, m_before - 1),
        "loosens_bars": True,
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
