"""Integrity of an axis series AT THE COLLECTOR WRITE BOUNDARY -- the gap between a vendor's
answer and a Holm forward slot's input (R0389 vendor revision, R0390 plausibility).

THE BOUNDARY NOTHING GUARDED. `data/*_axis.jsonl` and its siblings are the live inputs to
`run_axis_shadows.py`, the one artifact whose whole purpose is to be unpolluted forward evidence.
Between a vendor API and that artifact there was no check of any kind. On 2026-07-27
`collect_stablecoin_supply.py` stored a 60% one-day collapse in aggregate stablecoin supply
(122.37bn between two ~306bn days) carrying z20=-239.803, and nothing fired. The damage was zero
PURELY BY LUCK: the evaluator takes `np.sign(z)`, so -239.803 and the true -0.950 give the same
position. A bad read the other way flips the sign and books that day's forward return inverted.
SIGN-PRESERVING CORRUPTION IS LUCK, NOT A CONTROL.

TWO WAYS AN AGGREGATE STOPS BEING COMPARABLE TO ITS OWN HISTORY, and only the first was ever
discussed:
  VALUE  the number moves further in a day than the series has ever moved (`check_move`).
  COVER  the number is honest but is computed over a different constituent set (`check_coverage`).
The second is live and unguarded on `data/defi_util_axis.jsonl`: n_pools ran 6691 -> 2511 -> 566
-> 6538 while every day still wrote a z20 the evaluator booked as a position. 566 of ~6800 pools
is 92% of the aggregate missing, and the day is indistinguishable on the value axis because a
ratio of two collapsed sums stays in range. An unmeasurable day booked as evidence is worse than
a missing one, because a missing one is visible.

THE BAR IS DERIVED FROM THE SERIES' OWN MEASURED HISTORY, NEVER COPIED. The hand-picked 10% bar
that fixed the stablecoin instance does not transfer: it was reasoned from that series' float and
means nothing on a utilisation ratio or an FX premium. `move_bar` measures instead, and a rolling
window is not optional -- over DefiLlama's FULL 3,178-day history the max daily move is 27,280%
(the 2020 era, when the whole float was ~$7bn), so a full-history max is not a bar, it is a
licence. Measured on the last 900 days: max 2.10%, p99 1.01%, median+20*MAD 1.93%.

CONTAMINATION-RESISTANCE IS THE REASON FOR THE CAP. A bar set to "the largest move ever seen"
widens to admit any corrupt read that already got stored -- a ratchet pointing the wrong way, on
a series that HAS stored one. So the observed max is capped at a multiple of the robust scale:
normally the observed max governs (we never refuse a move the series has really made), but one
wild outlier cannot blow the bar open.

UNMEASURED IS A REAL ANSWER (L1.28a), AND IT DOES NOT BLOCK. Below `min_obs` no bar can be
derived, so none is asserted: the write proceeds and the verdict records that nothing was
checked. Fail-closed on a young series would stop every new axis from ever starting, which is the
timidity failure wearing a safety costume. The bar is for a mature series; a young one gets
honesty instead of a guess.

WHAT A REFUSAL MUST NOT DO IS VANISH. Two refusal shapes, chosen by what the caller can undo:
  * a LEVEL-storing append-only collector refuses the WRITE (SystemExit), because a corrupt level
    poisons the trailing z-window for the next 20 days, not just its own row;
  * a series RE-DERIVED from an owned archive keeps the row and nulls its z, because
    `run_axis_shadows._evaluate` counts a null-z row `unusable` and structurally cannot book a
    position on it -- the observation stays visible on disk instead of being silently dropped
    (L1.60: a skip nobody counted is indistinguishable from a scope filter).

VENDOR REVISION (R0389). DefiLlama silently rewrites its published history. Re-measured
2026-08-12 against our own point-in-time rows: 2026-08-02 302.35bn -> 305.45bn (+1.03%),
2026-08-03 302.19bn -> 305.34bn (+1.04%), and the bad 2026-07-27 read is now served as 307.99bn.
Every consumer that RE-FETCHES and recomputes -- `stage_a_screen` inside the collector,
`revalidate_clocks.stablesupply()` -- therefore scores on numbers THAT DID NOT EXIST AT DECISION
TIME. This is the as-of-date class from desk memory (a `*_now` denominator joined to historical
events) pointed at the SIGNAL rather than the conditioning variable, and it fails toward a false
verdict in EITHER direction, which is the direction no gate here catches.

The desk already HOLDS the as-of record -- the per-day row each collector appends -- and nothing
anywhere compared the two. `revision_report` does, and records the delta as a first-class series
exactly as L1.46 makes `t_recv - t_venue` first-class. It grants no authority and changes no
value: where the two disagree the point-in-time value is the one a screen may use, and where no
point-in-time row exists (the 900-day history predating the collector) the honest statement is
that the revision is UNMEASURABLE, never that it is zero.

Pure stdlib. Zero promotion authority: nothing here admits, promotes or sizes anything.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

#: Trailing observations the bar is measured over. Long enough to span a regime, short enough
#: that a series' ancient (and structurally different) era cannot set today's bar.
DEFAULT_WINDOW = 900

#: Robust-scale multiple. median + K_MAD*MAD lands at 1.93% on the stablecoin series against an
#: observed 900-day max of 2.10%, i.e. just under the real extreme -- which is the point: the
#: robust term is a FLOOR under the bar, not the bar itself.
K_MAD = 20.0

#: How far above the robust scale a single observed extreme may push the bar before it is
#: treated as contamination rather than history. Without this, one stored corrupt read widens
#: the bar forever.
OUTLIER_CAP = 3.0

#: Headroom over the series' own worst real move, so a genuine new extreme is not refused on the
#: day it happens. A refusal costs one day of data and a loud failure; a stored corruption costs
#: a forward slot.
MARGIN = 1.5

#: Below this many usable moves the series cannot state its own bar.
MIN_OBS = 30

#: A constituent count this far below the median of its own recent history means the aggregate is
#: computed over a different population. 0.5 admits the ordinary churn of a pool census
#: (4014..7795 on the live defi series) and refuses the collapses (566, 2511, 2800).
COVERAGE_FLOOR_FRAC = 0.5

#: Relative move at which a re-fetched historical value counts as REVISED rather than as float
#: noise in the vendor's own rounding.
REVISION_TOL = 1e-4


@dataclass(frozen=True)
class Bar:
    """A plausibility bar and the evidence it was derived from.

    `value is None` means UNMEASURED -- not "no limit" and not "zero". `n` is the denominator
    (L1.57): a bar computed over nothing is not a bar. `skipped` is what the derivation could not
    use (L1.60): a scope filter and an unreadable row must not look identical to a reader.
    """

    value: float | None
    n: int
    skipped: int
    basis: str

    @property
    def measured(self) -> bool:
        return self.value is not None

    def as_dict(self) -> dict[str, object]:
        return {"bar": self.value, "n": self.n, "skipped": self.skipped, "basis": self.basis}


@dataclass(frozen=True)
class Verdict:
    """`ok=False` iff the value cannot be a real successor to its own history.

    An UNMEASURED bar yields `ok=True` with a reason recording that nothing was checked, so a
    caller that logs `reason` whenever it is non-empty reports the gap without blocking on it.
    """

    ok: bool
    reason: str
    bar: Bar

    def __bool__(self) -> bool:
        """Truth IS the verdict.

        A dataclass is unconditionally truthy, so a caller writing the natural `if not verdict:`
        gets a guard that can never fire -- a refusal path that silently does not exist, which is
        the exact class this module was built to catch. It caught the module's own test first.
        """
        return self.ok

    def as_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "reason": self.reason, **self.bar.as_dict()}


def _moves(history: Sequence[float]) -> tuple[list[float], int]:
    """Absolute day-over-day relative moves, and how many pairs could not produce one.

    Counted rather than dropped: a non-positive or non-finite predecessor is a real gap in the
    evidence the bar rests on, and a bar quoting n=800 out of 900 pairs is a different claim
    from one quoting 800 out of 800.
    """
    out: list[float] = []
    skipped = 0
    for i in range(1, len(history)):
        prev, cur = history[i - 1], history[i]
        if not (prev > 0) or prev != prev or cur != cur:   # non-positive base or NaN
            skipped += 1
            continue
        out.append(abs(cur / prev - 1.0))
    return out, skipped


def move_bar(history: Sequence[float], *, window: int = DEFAULT_WINDOW, k: float = K_MAD,
             margin: float = MARGIN, min_obs: int = MIN_OBS) -> Bar:
    """Largest day-over-day move this series may make, measured from the series itself.

    bar = min(max_observed, OUTLIER_CAP * (median + k*MAD)) * margin, floored at the robust term
    so a quiet stretch cannot drive the bar to zero and start refusing ordinary days.
    """
    moves, skipped = _moves(history)
    recent = moves[-window:]
    if len(recent) < min_obs:
        return Bar(None, len(recent), skipped,
                   f"UNMEASURED: {len(recent)} usable moves < min_obs {min_obs}")
    med = median(recent)
    mad = median([abs(x - med) for x in recent])
    robust = med + k * mad
    observed = max(recent)
    # The robust term is a floor (a flat series must not get a zero bar) and, times OUTLIER_CAP,
    # also the ceiling on how far one extreme may widen the bar.
    value = max(robust, min(observed, OUTLIER_CAP * robust)) * margin
    return Bar(value, len(recent), skipped,
               f"max(robust {robust:.4%}, min(observed {observed:.4%}, "
               f"{OUTLIER_CAP:g}x robust)) x {margin:g} over {len(recent)} moves")


def check_move(latest: float, prev: float, bar: Bar) -> Verdict:
    """Can `latest` be a real successor to `prev`?"""
    if not bar.measured:
        return Verdict(True, f"UNCHECKED -- {bar.basis}", bar)
    if not (prev > 0):
        return Verdict(True, f"UNCHECKED -- non-positive predecessor {prev!r}", bar)
    assert bar.value is not None                              # narrowed by bar.measured
    move = latest / prev - 1.0
    if abs(move) > bar.value:
        return Verdict(False, f"day-over-day move {move:+.2%} exceeds this series' own measured "
                              f"bar of {bar.value:.2%} ({bar.basis})", bar)
    return Verdict(True, "", bar)


def coverage_bar(counts: Sequence[float], *, frac: float = COVERAGE_FLOOR_FRAC,
                 min_obs: int = 5) -> Bar:
    """Floor under the constituent count, as a fraction of its own recent median.

    Median, not mean: the collapses this exists to catch are already IN the history it is derived
    from, and a mean would let them drag the floor down to admit the next one.
    """
    usable = [float(c) for c in counts if c == c and c > 0]
    skipped = len(counts) - len(usable)
    if len(usable) < min_obs:
        return Bar(None, len(usable), skipped,
                   f"UNMEASURED: {len(usable)} usable counts < min_obs {min_obs}")
    med = median(usable)
    return Bar(med * frac, len(usable), skipped,
               f"{frac:g} x median constituent count {med:.0f} over {len(usable)} days")


def check_coverage(latest_n: float, bar: Bar) -> Verdict:
    """Is today's aggregate computed over the same population as its own history?"""
    if not bar.measured:
        return Verdict(True, f"UNCHECKED -- {bar.basis}", bar)
    assert bar.value is not None
    if latest_n < bar.value:
        return Verdict(False, f"constituent count {latest_n:.0f} is below the measured floor "
                              f"{bar.value:.0f} ({bar.basis}) -- the aggregate is computed over a "
                              f"different population and is not comparable to its own history",
                       bar)
    return Verdict(True, "", bar)


def revision_report(point_in_time: Mapping[str, float], refetched: Mapping[str, float], *,
                    axis: str, tol: float = REVISION_TOL) -> dict[str, object]:
    """Diff what the vendor said THEN against what it says NOW, on the dates we hold both.

    The denominator is `n_compared` -- dates present on BOTH sides -- and `n_pit_only` /
    `n_vendor_only` are published beside it rather than folded in, because "the vendor dropped a
    date we hold" and "the vendor serves history from before our collector existed" are different
    facts with different repairs (L1.60).

    Returns a record only. Nothing here rewrites a stored value: the point-in-time row IS the
    as-of record, and correcting it to the vendor's revised view would destroy the only evidence
    this comparison exists to produce.
    """
    common = sorted(set(point_in_time) & set(refetched))
    revisions: list[dict[str, float | str]] = []
    unusable = 0
    for d in common:
        was, now = float(point_in_time[d]), float(refetched[d])
        if not (was > 0):
            unusable += 1
            continue
        rel = now / was - 1.0
        if abs(rel) > tol:
            revisions.append({"date": d, "was": was, "now": now, "rel": rel})

    def _mag(r: dict[str, float | str]) -> float:
        rel_v = r["rel"]
        return abs(rel_v) if isinstance(rel_v, float) else 0.0

    worst = max(revisions, key=_mag, default=None)
    return {
        "axis": axis,
        "checked_at": datetime.now(tz=UTC).isoformat(),
        "n_compared": len(common) - unusable,
        "n_unusable": unusable,
        "n_pit_only": len(set(point_in_time) - set(refetched)),
        "n_vendor_only": len(set(refetched) - set(point_in_time)),
        "n_revised": len(revisions),
        "max_abs_rel": _mag(worst) if worst else 0.0,
        # The max is routinely a vendor correcting its OWN bad read (2026-07-27: +151.68%), and a
        # reader anchoring on it misjudges the ordinary case by two orders of magnitude. The
        # median is the number the look-ahead argument actually rests on: 0.53% on the first run,
        # against a series whose 20-day sd is ~0.5% -- i.e. a routine revision is a FULL SIGMA of
        # the signal being screened.
        "median_abs_rel": median([_mag(r) for r in revisions]) if revisions else 0.0,
        "worst": worst,
        # UNMEASURED, never "clean": zero comparable dates says nothing about revision (L1.28a).
        "verdict": ("UNMEASURED" if len(common) - unusable == 0
                    else "REVISED" if revisions else "STABLE"),
        "revisions": revisions[-50:],
    }


def record_revision(report: Mapping[str, object], path: str | Path) -> None:
    """Append one revision report as a first-class series (L1.46's t_recv - t_venue, for vendors).

    No silent swallow (L1.41): an unwritable path raises, because a revision record that vanished
    reads downstream as a series that was never revised.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report, sort_keys=True) + "\n")
