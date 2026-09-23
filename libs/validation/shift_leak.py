"""SHIFT-LAG LEAK DETECTION -- does a signal only "predict" because it contains the answer?

REHOMED 2026-09-05, and the reason matters more than the move. `shift_ic` lived inside
`scripts/revalidate_clocks.py`, a crypto-era script deleted in the MT5 purge. It is not a crypto
function: it is a LEAK DETECTOR, and its output is read as evidence that a signal's timestamps
are honest. Deleting the script would have deleted a gate, which is the one thing a cleanup may
never do. `tests/research/test_shift_leak_detector.py` was already pointing at it.

THE MATHS IS UNCHANGED, BYTE FOR BYTE, deliberately. This function has a history: an earlier
version shifted only the numerator leg, which for a ratio signal whose denominator is the
target's own price does not shift the signal at all -- it rebuilds the forward return and reports
an IC near +0.93 on pure noise. That false positive produced the "kimchi is a ~73% timestamp
artifact" verdict on 2026-07-29, which justified a keying change that then 24h-mispaired three
days of live collection and put a refuted mechanism in the graveyard (R0067). A leak detector
that fires on clean data is worse than none: it makes good data look broken and gets "fixed" in
the direction of the damage. Re-deriving it during a file move would risk exactly that, so the
body below is copied, not rewritten. The only post-move edits are annotations and two accumulator
RENAMES (`sig`/`rr` -> `sig_acc`/`rr_acc`, because the originals were rebound from list to array
in place and strict mypy reads that as a type error); every arithmetic line is untouched.

WHAT THE ARGUMENTS MEAN, since the names came from the venue it was written for:
  ``signal``  date -> raw signal level.
  ``gb``      date -> the TARGET instrument's price. Forward returns are computed from this.
  ``shift``   days to lag the finished signal by before scoring it.
  ``fx``      optional date -> divisor, when the signal is a ratio expressed in another currency.
              When given, the signal is built as ``signal/fx/gb - 1``, which is why the
              denominator leg has to move with the numerator.

Returns the IC, or NaN when fewer than 60 aligned dates exist -- too short to score is reported
as unmeasured, never as zero.
"""
from __future__ import annotations

from typing import Any

import numpy as np

#: date key -> value. The keys were `datetime.date` at the venue this was written for and are
#: strings in the MT5 daily panels, and the body only ever intersects and sorts them, so the key
#: type is left open rather than narrowed to whichever caller arrives first.
DateSeries = dict[Any, float]


def shift_ic(signal: DateSeries, gb: DateSeries, shift: int,
             fx: DateSeries | None = None) -> float:
    """IC of z(signal shifted by `shift` days) vs NEXT-day return.

    THE SIGNAL IS BUILT SAME-INSTANT FIRST, THEN THE FINISHED SERIES IS SHIFTED. This used to
    shift only the numerator leg -- signal[i+shift] over fx[i]/gb[i] -- which for a ratio signal
    whose DENOMINATOR is the target's own price does not shift the signal at all: it rebuilds it
    as roughly gb[i+1]/gb[i], i.e. the forward return itself. Measured on an i.i.d.-noise premium
    with zero predictive content by construction, the old form reported a +1d cell of +0.931.

    That false positive is not hypothetical: it is what produced the "kimchi is a ~73% timestamp
    artifact" verdict on 2026-07-29, which justified a +1d keying change that then 24h-mispaired
    three days of live collection and put a refuted mechanism in the graveyard (R0067). A leak
    detector that fires on clean data is worse than none -- it makes good data look broken and
    gets "fixed" in the direction of the damage.
    """
    dates = sorted(set(signal) & set(gb) & (set(fx) if fx else set(gb)))
    if len(dates) < 60:
        return float("nan")
    btc = np.array([gb[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0
    fwd = np.roll(ret, -1)
    series = np.array([signal[d] / fx[d] / gb[d] - 1.0 for d in dates]) if fx else \
        np.array([signal[d] for d in dates], dtype=float)
    sig_acc: list[float] = []
    rr_acc: list[float] = []
    for i in range(len(dates)):
        j = i + shift
        if 0 <= j < len(dates):
            sig_acc.append(series[j])
            rr_acc.append(fwd[i])
    sig, rr = np.array(sig_acc, float), np.array(rr_acc, float)
    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0
    zv, fv = z[20:-1], rr[20:-1]
    return float(np.corrcoef(zv, fv)[0, 1]) if zv.std() and fv.std() else 0.0

