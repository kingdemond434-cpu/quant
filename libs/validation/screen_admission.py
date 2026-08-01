"""FILL THE FORWARD SLOTS. The screen's job is RANKING; the forward stage is where safety lives.

THE PROBLEM, IN FOUR MEASURED NUMBERS:

  1. The gauntlet's certified sensitivity floor is TRUE SHARPE 5.0.
  2. This desk's own adopted real-edge band is OOS Sharpe 0.5-1.5, from a 131,441-backtest sweep.
  3. WorldQuant BRAIN -- a live institutional pipeline that PAYS research consultants -- submits
     alphas at fitness > 1.0 and targets Sharpe ~1.25. This desk is 4.0x stricter than a place
     that writes cheques (libs/validation/brain_calibration.py).
  4. Measured power at the band where edges actually live: 0.0% across four of six conditions,
     1.25% and 2.50% on the other two. False positives: 0 of 4,800, at every setting.

A gate with ~0% power and 0% false-positive rate is not a filter. It is a wall. And the price of
that wall is visible: 129 candidates screened on 2026-08-01, ZERO survivors, and
data/forward_slots.json DOES NOT EXIST -- twelve forward slots, none of them occupied, ever.

WHY FILLING THEM IS NOT A RELAXATION, WHICH IS THE ONLY QUESTION THAT MATTERS HERE:

  The desk's own TWO-STAGE DISCOVERY LAW already says the backtest gauntlet is a SCREEN WITH ZERO
  PROMOTION AUTHORITY. Capital moves only on pre-registered FORWARD evidence, Holm-corrected at
  MAX_FORWARD_SLOTS=12, with a fixed end date. That is where safety has always lived.

  And here is the statistical point that settles it: the Holm correction is applied over the
  CONCURRENT SLOT COUNT, which is capped at 12. THE MULTIPLICITY COST OF RUNNING TWELVE FORWARD
  TESTS IS THEREFORE ALREADY PAID, in full, whether or not the slots are used. An empty slot buys
  no safety -- it forfeits a test the desk has already priced. Twelve empty slots is not caution;
  it is twelve wasted, pre-funded experiments and a guaranteed discovery rate of zero.

  So this module does not touch the promotion bar. It does not touch a rail. It changes WHICH
  OBJECT DOES THE FILTERING, from a screen that was never granted the authority to a forward
  stage that always had it and has been sitting idle.

THE SPLIT THAT KEEPS IT SAFE -- structural gates BLOCK, statistical gates RANK:

  STRUCTURAL (hard block, and no amount of forward data repairs them):
    economic_mechanism  no story for who is forced to trade against you -> it is a data artifact
    capacity            cannot be executed at the desk's size -> not tradeable at any confidence
    fragility           tail risk that would damage the book -> a safety property, not a p-value
    expected_value      negative expectancy -> forward-testing it is a paid way to lose
    break_even_win_rate the per-trade arithmetic does not close -> see below
  STATISTICAL (become ranking inputs, because the forward stage tests the same thing better,
  on out-of-sample data, with the multiplicity already priced):
    dsr, pbo, reality_check, walk_forward, cpcv, not_too_lucky

  The principle: a structural gate asks "can this be traded at all, and is there a reason it
  should work?" A statistical gate asks "is this distinguishable from noise?" -- and twelve
  pre-registered forward clocks answer that question with better evidence than any backtest can.

WHAT ADMISSION IS NOT. An admitted candidate receives a FORWARD CLOCK, not money. It owes the
full pre-registered forward test exactly as before: same bar, same Holm correction, same fixed
end date, same graveyard rules. Nothing here shortens that path or widens it. `admit()` returns
slot assignments and would be a defect if it ever returned a position size.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "MIN_ADMISSION_OOS_SHARPE",
    "STATISTICAL_GATES",
    "STRUCTURAL_GATES",
    "Admission",
    "AdmissionPlan",
    "admit",
    "break_even_win_rate",
    "rank_score",
]

#: MINIMUM OOS SHARPE TO OCCUPY A SLOT. A RELEVANCE FLOOR, NOT A SIGNIFICANCE TEST.
#:
#: This exists because removing the statistical wall exposed the opposite failure immediately.
#: Replaying the real 2026-08-01 campaign through admission filled all twelve slots with
#: candidates whose OOS Sharpe was ~0.02 -- statistically indistinguishable from zero and far
#: below anything worth measuring. That is not caution restored, it is the scarce resource being
#: spent on noise: a forward clock runs for months, so a slot occupied by a zero-edge candidate
#: BLOCKS A REAL ONE for that entire period. An idle slot costs nothing; a wasted slot costs a
#: discovery.
#:
#: WHY 0.25 AND WHY IT IS NOT A SIGNIFICANCE BAR. The desk's measured real-edge band starts at
#: OOS Sharpe 0.5. A short backtest window measures a true 1.0 edge noisily, so the floor must sit
#: BELOW the band or it would reject real edges for being imprecisely measured -- half the band's
#: lower edge is the loosest defensible reading. It asks "is there plausibly anything here?", not
#: "is this distinguishable from noise?" -- the forward stage answers the second question, which
#: is the entire point of this module.
#:
#: RAISING THIS TO MANUFACTURE STRICTNESS WOULD REBUILD THE WALL. It is a floor on relevance, and
#: the campaign that motivated it topped out at OOS 0.100 across 129 mechanisms -- so under this
#: floor that campaign correctly admits NOTHING, which is the honest answer for mechanisms the
#: desk has already measured as picked clean.
MIN_ADMISSION_OOS_SHARPE = 0.25

#: A structural failure is disqualifying at any confidence level. These are not thresholds on
#: evidence, they are statements about whether the thing can be traded or should be expected to
#: work at all -- and forward data does not repair any of them.
STRUCTURAL_GATES: tuple[str, ...] = (
    "economic_mechanism",
    "expected_value",
    "capacity",
    "fragility",
    "break_even_win_rate",
    "sample_adequacy",
)

#: These test "is it distinguishable from noise". The forward stage tests exactly that, on data
#: the candidate has never seen, with the concurrent-slot multiplicity already Holm-corrected. So
#: here they ORDER candidates rather than eliminate them.
STATISTICAL_GATES: tuple[str, ...] = (
    "dsr",
    "pbo",
    "reality_check",
    "walk_forward",
    "cpcv",
    "not_too_lucky",
    "beats_baselines",
)


def break_even_win_rate(avg_win: float, avg_loss: float) -> float:
    """The win rate below which a strategy loses money regardless of how good the curve looks.

        p* = |avg_loss| / (avg_win + |avg_loss|)

    THE GAP BETWEEN REALISED AND BREAK-EVEN WIN RATE IS THE ENTIRE EDGE, and it is invisible to
    every other statistic in this desk's gauntlet, all of which are computed PER OBSERVATION. A
    5,000-bar series holding one position throughout has 5,000 observations and one bet; per-bar
    Sharpe cannot see that, and neither can DSR, PBO or the reality check.

    The arithmetic that makes it concrete, from a 432-variant backtest study in the 2026-08-01
    transcript batch: average win 5.72%, average loss 3.13% net, giving p* = 35.4%. Realised win
    rate 41.3%. That 5.9-point gap, compounded over 758 trades, WAS the 24.9x return. Nothing
    else in the result mattered.

    Returns 1.0 when avg_win <= 0 -- a strategy with no average winner cannot break even at any
    win rate, and reporting 0.5 there would read as an easy bar.
    """
    w = float(avg_win)
    loss = abs(float(avg_loss))
    if w <= 0.0:
        return 1.0
    if loss <= 0.0:
        return 0.0
    return loss / (w + loss)


@dataclass(frozen=True)
class Admission:
    name: str
    rank_score: float
    blocked_by: tuple[str, ...] = ()
    statistical_failures: tuple[str, ...] = ()
    admitted: bool = False
    reason: str = ""


@dataclass(frozen=True)
class AdmissionPlan:
    admitted: tuple[Admission, ...] = ()
    blocked: tuple[Admission, ...] = ()
    ranked_out: tuple[Admission, ...] = ()
    idle_slots_before: int = 0
    idle_slots_after: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def summary(self) -> str:
        return (f"{len(self.admitted)} admitted to forward clocks, {len(self.blocked)} "
                f"structurally blocked, {len(self.ranked_out)} out-ranked; "
                f"{self.idle_slots_after} slot(s) still idle")


def rank_score(gates: dict[str, bool], *, oos_sharpe: float, dsr: float,
               reality_p: float) -> float:
    """Order candidates for scarce forward slots. NOT a pass/fail score.

    Built from OOS Sharpe first because that is the quantity the desk has an empirical band for
    (0.5-1.5) and the one the forward stage will actually re-measure. The statistical gates
    contribute as a count of how many were cleared, so a candidate that clears more of them
    outranks one that clears fewer -- ordering, not gating.

    DELIBERATELY NOT A CALIBRATED PROBABILITY. Any attempt to turn this into "probability the
    candidate is real" would be a promotion decision wearing a ranking's clothes, and promotion
    belongs to the forward stage. It only needs to be monotone in the right direction.
    """
    cleared = sum(1 for g in STATISTICAL_GATES if gates.get(g, False))
    # OOS Sharpe dominates; each cleared statistical gate is worth a small, fixed bonus so it can
    # break ties between candidates with similar OOS but cannot outweigh a genuine OOS difference.
    return float(oos_sharpe) + 0.05 * cleared + 0.02 * float(dsr) + 0.02 * (1.0 - float(reality_p))


def _f(row: dict[str, object], key: str, default: float) -> float:
    """Read a numeric field defensively. A caller that omits or mistypes one must get the stated
    default rather than a crash mid-campaign -- but the default is chosen so the omission is
    CONSERVATIVE: a missing oos_sharpe reads as 0.0 and therefore fails the relevance floor."""
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else default


def admit(candidates: list[dict[str, object]], *, idle_slots: int) -> AdmissionPlan:
    """Assign the best structurally-sound candidates to idle forward clocks.

    `candidates` rows carry: name, gates (dict), oos_sharpe, dsr, reality_p.

    THREE INVARIANTS, each of which would be a serious defect to violate and each of which is
    locked by a test:
      1. Admissions never exceed idle_slots. The Holm correction is priced at exactly
         MAX_FORWARD_SLOTS concurrent tests; exceeding it invalidates the correction and is the
         one way this module could actually make the desk less safe.
      2. A structurally-blocked candidate is NEVER admitted, at any rank, however good its
         statistics. Rank cannot buy past a missing mechanism or absent capacity.
      3. Admission confers a forward CLOCK and never capital. Nothing returned here is a size.
    """
    rows: list[Admission] = []
    for c in candidates:
        raw_gates = c.get("gates")
        # Defensive rather than trusting: a caller passing a non-dict must not crash a campaign,
        # and an unreadable gates field means NO gate was cleared, which is the conservative read.
        gates: dict[str, bool] = (
            {str(k): bool(v) for k, v in raw_gates.items()}
            if isinstance(raw_gates, dict) else {})
        name = str(c.get("name", "?"))
        oos = _f(c, "oos_sharpe", 0.0)
        blocked_list = [g for g in STRUCTURAL_GATES if g in gates and not gates[g]]
        # The relevance floor is enforced as a structural block on purpose: it is a statement
        # about whether a scarce forward clock should be spent, not about statistical evidence,
        # and like every other structural block it must be un-out-rankable.
        if oos < MIN_ADMISSION_OOS_SHARPE:
            blocked_list.append("below_relevance_floor")
        stat_fail = tuple(g for g in STATISTICAL_GATES if g in gates and not gates[g])
        score = rank_score(gates, oos_sharpe=oos, dsr=_f(c, "dsr", 0.0),
                           reality_p=_f(c, "reality_p", 1.0))
        rows.append(Admission(name=name, rank_score=score, blocked_by=tuple(blocked_list),
                              statistical_failures=stat_fail))

    blocked = tuple(r for r in rows if r.blocked_by)
    eligible = sorted((r for r in rows if not r.blocked_by),
                      key=lambda r: (-r.rank_score, r.name))
    n = max(0, int(idle_slots))
    admitted = tuple(
        Admission(name=r.name, rank_score=r.rank_score, blocked_by=r.blocked_by,
                  statistical_failures=r.statistical_failures, admitted=True,
                  reason=("admitted to a forward clock by EV rank; owes pre-registered forward "
                          "evidence with an unchanged Holm-corrected bar and a fixed end date"))
        for r in eligible[:n])
    ranked_out = tuple(eligible[n:])

    notes = [
        f"{len(admitted)} of {len(eligible)} structurally-sound candidates fit {n} idle slot(s)",
        "admission is a FORWARD CLOCK, never capital; the promotion bar is unchanged",
    ]
    n_floor = sum(1 for r in blocked if "below_relevance_floor" in r.blocked_by)
    if n_floor:
        notes.append(f"{n_floor} candidate(s) below the {MIN_ADMISSION_OOS_SHARPE} OOS relevance "
                     "floor -- a forward clock runs for months, so a slot spent on noise blocks a "
                     "real edge; an idle slot costs nothing")
    if not eligible and rows:
        notes.append("every candidate failed a STRUCTURAL gate -- that is a real result and is "
                     "not fixed by widening the screen; the mechanisms have no edge, no capacity, "
                     "or no story for who is forced to trade against them")
    if n == 0 and eligible:
        notes.append("no idle slots: the forward stage is saturated, which is the intended "
                     "steady state and the correct reason to admit nothing")
    return AdmissionPlan(admitted=admitted, blocked=blocked, ranked_out=ranked_out,
                         idle_slots_before=n, idle_slots_after=n - len(admitted),
                         notes=tuple(notes))
