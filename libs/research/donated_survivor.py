"""SURVIVORS DONATED BY AN INDEPENDENT FACTORY, priced at the multiplicity they were selected from.

WHAT THIS ENABLES. A second desk -- another agent, another box, another codebase -- runs its OWN
generation, its OWN screens and its OWN shadow clocks, and hands this desk the candidates that
survived. That is real parallel throughput: two factories hunting instead of one, with no shared
implementation to make their mistakes correlated.

WHAT MAKES IT SAFE, AND IT IS ONE FACT CARRIED ACROSS THE WIRE.

A survivor is a MAXIMUM. If a donor screened forty candidates and sends the best one, that
candidate's statistic is the best of forty draws, and judging it against a bar built for one trial
is not a mild optimism -- it is the entire multiple-comparisons problem, imported with the evidence
stripped off. The receiving desk sees a clean row, no record of the forty, and a bar computed
from its own cohort alone. Every number looks right and the error rate is silently multiplied.

The desk has already paid for this exact arithmetic once, in its own registry: `slot_registry`
opens on m being counted three different ways in three files, applying holm_bar(4)=2.24 while
twelve clocks accrued, for a realised error rate 3.2x the design. A second factory forwarding
winners is the same defect with a network hop in the middle -- harder to see, because there is no
file to grep.

**SO A DONATION MUST DECLARE ITS TRIAL COUNT, AND ONE THAT DOES NOT IS REFUSED.** Not down-weighted,
not admitted with a warning: refused. An undeclared trial count is indistinguishable from a trial
count of one, and that is precisely the reading that spends money.

**THE BAR IS RECOMPUTED ON THE UNION, NEVER THE LOCAL COHORT.** m = local concurrent clocks +
donor trials screened. A donor who hunts harder makes their own survivors harder to admit, which
is correct and is what makes the scheme incentive-safe: a factory cannot buy admission by
generating more.

**IT ADMITS TO A FORWARD CLOCK, NEVER TO CAPITAL.** A donated survivor enters this desk exactly
where a local Stage-A survivor enters -- the queue for a forward clock. The donor's backtest has
the same authority as this desk's backtest, which under the two-stage law is none. What is imported
is a HYPOTHESIS WORTH A CLOCK, never a verdict.

Stdlib only. import from libs.research.donated_survivor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from libs.validation.forward_stats import holm_bar

__all__ = [
    "REQUIRED_FIELDS",
    "Donation",
    "Verdict",
    "admit",
    "review",
]

#: Every field a donation must carry. `trials_screened` is the load-bearing one and the reason
#: this list is enforced rather than documented: the others make a row readable, that one makes it
#: honest.
REQUIRED_FIELDS: tuple[str, ...] = ("name", "source", "trials_screened", "t_stat")


@dataclass(frozen=True)
class Donation:
    """One survivor offered by an independent factory, with the search it came out of."""

    name: str
    source: str
    #: HOW MANY CANDIDATES THE DONOR SCREENED to produce this one. The whole contract.
    trials_screened: int
    t_stat: float
    #: The donor's own concurrent forward cohort, when it ran clocks rather than only screens.
    #: Optional: a donor may legitimately screen without running clocks, and demanding a number it
    #: does not have would push donors toward inventing one.
    donor_cohort_m: int | None = None
    mechanism: str = ""
    horizon_days: float | None = None
    note: str = ""


@dataclass(frozen=True)
class Verdict:
    """ADMIT / REFUSE, the bar it was judged against, and the arithmetic behind it."""

    admit: bool
    name: str
    bar: float | None
    union_m: int | None
    why: str

    @property
    def refused(self) -> bool:
        return not self.admit


def _parse(row: dict[str, Any]) -> tuple[Donation | None, str]:
    missing = [f for f in REQUIRED_FIELDS if row.get(f) in (None, "")]
    if missing:
        return None, (
            f"donation is missing {', '.join(missing)}. `trials_screened` in particular is not a "
            "formality: an undeclared trial count is indistinguishable from a trial count of one, "
            "and that is exactly the reading that turns a maximum into an edge")
    try:
        trials = int(row["trials_screened"])
        t = float(row["t_stat"])
    except (TypeError, ValueError):
        return None, "trials_screened / t_stat are not numeric -- the donation cannot be priced"
    if trials < 1:
        return None, (
            f"trials_screened={trials} is not a search. A donor that screened nothing did not "
            "produce a survivor")
    m = row.get("donor_cohort_m")
    return Donation(
        name=str(row["name"]), source=str(row["source"]), trials_screened=trials, t_stat=t,
        donor_cohort_m=int(m) if isinstance(m, (int, float)) else None,
        mechanism=str(row.get("mechanism") or ""),
        horizon_days=(float(row["horizon_days"])
                      if isinstance(row.get("horizon_days"), (int, float)) else None),
        note=str(row.get("note") or ""),
    ), ""


def admit(row: dict[str, Any], *, local_m: int, alpha: float = 0.05) -> Verdict:
    """Should this donated survivor be given a forward clock on THIS desk?

    `local_m` is this desk's concurrent cohort. The bar is computed on the UNION -- local clocks
    plus the donor's screened trials -- because both searches contributed to the chance that the
    best-looking candidate looks good by accident, and only the union prices that.
    """
    d, why = _parse(row)
    if d is None:
        return Verdict(False, str(row.get("name") or "?"), None, None, why)

    union = max(1, int(local_m)) + d.trials_screened
    if d.donor_cohort_m:
        # A donor that also ran CLOCKS contributed concurrent trials on top of its screens, and
        # both count. Taking the max would let a donor hide screens behind a small clock count.
        union += int(d.donor_cohort_m)
    bar = float(holm_bar(union, rank=1, alpha=alpha))

    if d.t_stat < bar:
        return Verdict(False, d.name, bar, union, (
            f"t={d.t_stat:.3f} against a union bar of {bar:.3f} at m={union} "
            f"({local_m} local + {d.trials_screened} donor trials"
            f"{f' + {d.donor_cohort_m} donor clocks' if d.donor_cohort_m else ''}). "
            "The bar is built on the union because BOTH searches contributed to the chance this "
            "candidate looks good by accident. Judged against the local cohort alone it would "
            f"have faced {holm_bar(max(1, int(local_m)), rank=1, alpha=alpha):.3f} -- which is "
            "the number that makes a maximum look like an edge"))

    return Verdict(True, d.name, bar, union, (
        f"t={d.t_stat:.3f} clears the union bar {bar:.3f} at m={union}. ADMITTED TO A FORWARD "
        "CLOCK, NOT TO CAPITAL: the donor's backtest carries the same authority as this desk's "
        "backtest, which under the two-stage law is none. What is imported is a hypothesis worth "
        f"a clock. Source {d.source}"
        + (f"; mechanism {d.mechanism}" if d.mechanism else "")))


def review(rows: list[dict[str, Any]], *, local_m: int,
           alpha: float = 0.05) -> dict[str, Any]:
    """Judge a whole donation batch. REFUSALS ARE THE HALF WORTH READING.

    A batch is judged row by row against the same union bar rather than ranked against each other:
    ranking donated survivors would add a THIRD selection step on top of the donor's and this
    desk's, and nothing downstream would know it happened.

    **WITH MORE THAN ONE DONOR THE UNION SPANS ALL OF THEM, and this is the correction a third
    factory forces.** `admit()` alone prices one donation against the search that produced it,
    which is right when a donation arrives by itself. It is NOT right when three factories each
    send their best on the same day: the desk is then looking at three maxima and admitting
    whichever clears, which is a selection across donors that neither donor can see and neither
    priced. Charging each row only its own donor's trials would understate m by the other two
    searches entirely -- and understating m LOOSENS the bar, the phantom-edge direction, exactly
    as when the desk counted its own cohort three ways in three files.

    So the batch's denominator is local clocks + EVERY donor's trials in the window, and each row
    faces it. The cost is real and is meant to be: a desk running three factories must clear a
    higher bar than a desk running one, because it looked in three times as many places. That is
    the price of the extra throughput, not a defect in it.
    """
    donor_trials = 0
    for r in rows:
        d, _ = _parse(r)
        if d is not None:
            donor_trials += d.trials_screened + (d.donor_cohort_m or 0)
    batch_m = max(1, int(local_m)) + donor_trials
    # Each row is priced at the FULL batch denominator by handing `admit` a local_m that already
    # carries every other donor's search. Its own trials are then added once, by `admit` itself.
    verdicts = []
    for r in rows:
        d, _ = _parse(r)
        others = batch_m - ((d.trials_screened + (d.donor_cohort_m or 0)) if d else 0)
        verdicts.append(admit(r, local_m=others, alpha=alpha))
    ok = [v for v in verdicts if v.admit]
    donors = sorted({str(r.get("source") or "?") for r in rows})
    return {
        "n_offered": len(rows),
        "n_admitted": len(ok),
        "n_refused": len(verdicts) - len(ok),
        "local_m": int(local_m),
        "donors": donors,
        "donor_trials_total": donor_trials,
        "batch_union_m": batch_m,
        "admitted": [{"name": v.name, "bar": v.bar, "union_m": v.union_m, "why": v.why}
                     for v in ok],
        "refused": [{"name": v.name, "bar": v.bar, "union_m": v.union_m, "why": v.why}
                    for v in verdicts if v.refused],
        "note": ("Donated survivors are priced at the multiplicity they were SELECTED FROM, not "
                 "at this desk's cohort alone. A survivor is a maximum: judging the best of forty "
                 "draws against a one-trial bar imports the entire multiple-comparisons problem "
                 "with the evidence stripped off. A donor who hunts harder therefore makes their "
                 "own survivors harder to admit -- which is what stops a factory buying admission "
                 "by generating more. Admission grants a FORWARD CLOCK and never capital."),
    }
