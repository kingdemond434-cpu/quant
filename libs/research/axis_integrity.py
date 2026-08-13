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

VENDOR REVISION (R0389) IS **NOT** HERE, DELIBERATELY -- IT IS `libs/research/vintage.py`.
DefiLlama silently rewrites its published history: measured 2026-08-12 against our own
point-in-time rows, 18 of 20 comparable dates were revised, every one UPWARD, median +0.53% and
max +1.04%. That is the same defect vintage.py was already built for under R0316 (Receita Federal:
39/42 months revised within three months, worst +40.9%), down to the systematic upward sign.

This module originally shipped its own `revision_report`, which was a DUPLICATE and a worse one:
it stored a summary line, while `vintage.record` stores the as-of VALUES, so `vintage.as_of(d)`
can reconstruct what was actually knowable on date d. Only the second one can ever support a true
point-in-time screen, and the store is append-on-change, so keeping every vintage forever is
close to free. Upgrade before build (L2.9) -- the collector calls vintage.record directly.

Pure stdlib. Zero promotion authority: nothing here admits, promotes or sizes anything.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
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
