"""Split the moat's one skew number into the three things it was silently adding together.

`moat_recorder` samples, per pull, `now_utc - newest time_msc` and reports p50/p95 of it as
"skew". That sum has three unrelated parts:

    zone offset     the broker stamps `time_msc` in SERVER time, not UTC (Fusion is UTC+2 in
                    winter, UTC+3 in summer). Whole hours; a fact about the venue, not a fault.
    clock drift     what is left of the true offset after the whole hours: the box clock against
                    the broker's. Milliseconds to seconds; this is what a lead-lag or quote-lag
                    measurement must subtract, and what nothing measured before.
    staleness       how long ago the newest quote in the pull actually printed. A quiet symbol is
                    "skewed" by minutes because nobody quoted it, which says nothing about clocks.

THE ESTIMATOR. The true offset (zone + drift) plus transport latency is a LOWER BOUND on every
sample: a sample can only be larger, by the time the quote sat before the pull. So the lower
envelope of many samples, across many symbols, estimates offset + minimum latency; an active
symbol that quoted milliseconds before a pull touches it. The envelope is a LOW PERCENTILE, not
the minimum, so one mis-stamped tick cannot drag the clock. `clock_drift_ms` therefore still
includes the minimum transport latency (pull round trip); it is an upper bound on true drift. Staleness is each sample minus that
envelope, so it is >= 0 except for the few samples under the percentile.

WHAT IT REFUSES TO SAY. Below MIN_SAMPLES the split is UNMEASURED, never a guess: a handful of
samples from one quiet symbol would report its staleness as clock drift. And drift is only
separable from the zone because the zone is whole hours; a drift beyond +/-30 minutes cannot be
told apart from a zone change, and is flagged rather than folded in.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

HOUR_MS = 3_600_000
#: Fewer samples than this and the lower envelope is one quiet symbol's staleness.
MIN_SAMPLES = 50
#: The envelope percentile. Low enough to sit on the freshest quotes, high enough that a single
#: mis-stamped tick in a thousand cannot set the clock.
ENVELOPE_PCT = 0.01


def _pct(sorted_vals: Sequence[int], q: float) -> int:
    return sorted_vals[min(len(sorted_vals) - 1, max(0, int(len(sorted_vals) * q)))]


def split_skew(samples: Sequence[int]) -> dict[str, Any]:
    """`samples` are `now_utc_ms - newest_time_msc` per pull. Returns the three-way split."""
    vals = sorted(int(s) for s in samples)
    out: dict[str, Any] = {"clock_samples": len(vals)}
    if len(vals) < MIN_SAMPLES:
        out.update(clock_split="UNMEASURED", clock_offset_ms=None, zone_offset_h=None,
                   clock_drift_ms=None, quote_staleness_ms_p50=None,
                   quote_staleness_ms_p95=None)
        return out
    envelope = _pct(vals, ENVELOPE_PCT)
    # `now - broker_stamp`: a broker AHEAD of UTC gives a NEGATIVE envelope. The zone is the
    # nearest whole hour of that, reported the way people say it (UTC+2 -> +2).
    zone_h = -round(envelope / HOUR_MS)
    drift = envelope + zone_h * HOUR_MS
    stale = [v - envelope for v in vals]
    out.update(
        clock_split="MEASURED",
        clock_offset_ms=envelope,
        zone_offset_h=zone_h,
        clock_drift_ms=drift,
        drift_ambiguous=abs(drift) > HOUR_MS // 2 - 60_000,
        quote_staleness_ms_p50=_pct(stale, 0.5),
        quote_staleness_ms_p95=_pct(stale, 0.95),
    )
    return out
