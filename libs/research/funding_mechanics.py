"""VENUE FUNDING MECHANICS -- what the visible funding number actually MEANS (L1.47).

``funding_clock`` owns WHEN a perp pays. This module owns WHAT THE PRINT IS, and they are
different questions: the visible funding rate (FR) is not the underlying economics. It is a
QUANTIZED (clamp dead-band), CLAMPED (interest anchor), CAPPED (discretionary ceiling), LAGGED
(payment timing) transform of the premium index (PI). Wherever PI is readable, READ PI, NOT FR.

Source: muzineco, Advent Calendar 2023 day 8 -- a venue-mechanics primer. Five fence-grade facts,
each of which silently corrupts a carry estimate in a direction the desk could not see:

 1. CLAMP DEAD-BAND, and it differs by venue. Binance/Bybit: F = P + clamp(I - P, +-0.05%), with
    I = 0.01%. So EVERY PI in [-0.04%, +0.06%] prints identically as 0.01% -- a 0.01% print
    carries a 0.10%-wide hidden PI range, i.e. up to 10bp per period of hedged-carry performance
    spread between its edges, invisible in the series. OKX has no interest term and no clamp
    (F = P). Cross-venue FR comparisons therefore mix differently-quantized series.
 2. IMPACT-MARGIN-NOTIONAL HETEROGENEITY. The impact bid/ask that feeds PI reads a FIXED-NOTIONAL
    book slice, and that notional is per-symbol: Bybit BTCUSDT IMN ~ 20 BTC (~$880k) against HNT
    ~ 21 HNT (~$120), a ~7000x range. An FR extreme on a thin alt can be book microstructure
    rather than positioning.
 3. INTERVAL SWITCHING. 8h -> 4h -> 2h switches are applied to hot alts ad hoc. A funding series
    naive-joined on a fixed 8h grid corrupts carry estimates in exactly the extreme windows that
    matter most.
 4. PAYMENT-TIMING SPLIT. Most venues apply FR immediately after its computation window; OKX and
    BitMEX apply it ONE PERIOD LATE. A funding-to-return join that ignores this is a full-period
    look-ahead (or look-behind), per venue.
 5. CAPS ARE DISCRETIONARY AND UNANNOUNCED. +-0.375/0.75/1.5/3% ladders, raised ad hoc by a human
    when predicted FR pins. Cap-change moments are REGIME EVENTS for any position sized against
    the capped print.

REFUSAL PATH (L1.28a/L1.41), inherited deliberately from ``funding_clock``: every function here
returns ``None`` for a venue it was not told about, rather than assuming Binance mechanics. The
whole point of the module is that venues differ; silently defaulting would rebuild the defect it
exists to name. An unknown venue is a REFUSAL, never a guess.

Pure stdlib. Nothing here changes an order -- it is a research/verification layer (L1.38).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# Rates are DECIMAL FRACTIONS PER PERIOD throughout, matching what the desk already stores:
# `float(r["fundingRate"])` from Binance (libs/data/crypto_source.py:130). 0.0001 == 0.01% == 1bp.
BP = 0.0001


@dataclass(frozen=True)
class VenueMechanics:
    """How one venue turns a premium index into the number it prints."""

    venue: str
    interest: float | None          # the clamp anchor, per period. None = no interest term.
    clamp_half_width: float | None  # F is pinned to `interest` while |I - P| <= this. None = none.
    additive_offset: float          # a flat term added to PI (dYdX's 0.00125%/1h).
    pays_one_period_late: bool      # OKX / BitMEX apply the rate one period after its window.
    caps: tuple[float, ...]         # known discretionary cap ladder, ascending. () = uncapped.
    note: str

    @property
    def clamped(self) -> bool:
        return self.clamp_half_width is not None and self.interest is not None


#: Only venues whose mechanics were actually READ go here. Adding a venue by analogy would be the
#: guess this module refuses -- the entire finding is that the transforms are not interchangeable.
_VENUES: dict[str, VenueMechanics] = {
    "binance": VenueMechanics(
        "binance", 0.0001, 0.0005, 0.0, False, (0.00375, 0.0075, 0.015, 0.03),
        "F = P + clamp(I - P, +-0.05%); I = 0.01%. Dead-band pins F at I for P in "
        "[-0.04%, +0.06%]."),
    "bybit": VenueMechanics(
        "bybit", 0.0001, 0.0005, 0.0, False, (0.00375, 0.0075, 0.015, 0.03),
        "Binance-style clamp. IMN is per-symbol and spans ~7000x (BTCUSDT ~$880k vs HNT ~$120)."),
    "okx": VenueMechanics(
        "okx", None, None, 0.0, True, (0.00375, 0.0075, 0.015, 0.03),
        "NO interest term and NO clamp: F = P exactly. Applies the rate ONE PERIOD LATE."),
    "bitmex": VenueMechanics(
        "bitmex", 0.0001, 0.0005, 0.0, True, (0.00375, 0.0075, 0.015, 0.03),
        "Clamped like Binance, but applies the rate ONE PERIOD LATE."),
    "dydx": VenueMechanics(
        "dydx", None, None, 0.0000125, False, (),
        "F = P + 0.00125%/1h, no clamp and NO CAP -- the tail is genuinely unbounded here."),
}


def mechanics(venue: str) -> VenueMechanics | None:
    """Mechanics for ``venue``, or ``None`` if this desk has not read them. Never guesses."""
    return _VENUES.get(venue.strip().lower()) if venue else None


# ------------------------------------------------------------------ 1. the clamp dead-band
@dataclass(frozen=True)
class PIRange:
    """What the printed FR tells you about PI: a POINT when clamped out, a RANGE when pinned.

    ``width`` is the part of the economics the print threw away. It is not a rounding error --
    at the Binance dead-band it is 10bp per period, which at 3 settlements a day is 30bp/day of
    hedged-carry performance spread between two positions whose funding series look identical.
    """

    lo: float
    hi: float
    pinned: bool          # True == FR sat in the dead-band and PI is UNDETERMINED within [lo, hi]
    venue: str

    @property
    def width(self) -> float:
        return self.hi - self.lo

    @property
    def width_bp(self) -> float:
        return self.width / BP

    @property
    def midpoint(self) -> float:
        return (self.lo + self.hi) / 2.0


def pi_range_from_fr(fr: float, venue: str) -> PIRange | None:
    """Invert the clamp: recover what PI must have been, given the printed FR.

    THE POINT OF THIS FUNCTION is that the inversion is not always unique, and the caller has to
    be told which case it is in. Unclamped venues invert exactly. Clamped venues invert exactly
    ONLY when the print escaped the dead-band; a print sitting AT the interest anchor is
    consistent with a 0.1%-wide band of true premia, and treating it as the number 0.01% is the
    quantization error this module exists to surface.

    Returns ``None`` for an unknown venue -- assuming Binance mechanics is the defect, not the
    fallback.
    """
    m = mechanics(venue)
    if m is None:
        return None
    base = fr - m.additive_offset
    if not m.clamped:
        return PIRange(base, base, False, m.venue)
    interest, half = m.interest, m.clamp_half_width
    assert interest is not None and half is not None  # narrowed by m.clamped
    if abs(base - interest) < 1e-12:
        # Pinned: F == I says only that |I - P| <= half.
        return PIRange(interest - half, interest + half, True, m.venue)
    # Escaped the band: F = P +- half, and the SIGN of (F - I) says which side.
    pi = base + half if base > interest else base - half
    return PIRange(pi, pi, False, m.venue)


def fr_is_pinned(fr: float, venue: str) -> bool | None:
    """True when this print carries no PI information beyond 'somewhere in the dead-band'."""
    r = pi_range_from_fr(fr, venue)
    return None if r is None else r.pinned


def hidden_carry_spread_bp(fr: float, venue: str) -> float | None:
    """Worst-case per-period carry spread, in bp, hidden inside this print. 0.0 when exact."""
    r = pi_range_from_fr(fr, venue)
    return None if r is None else r.width_bp


def comparable_across_venues(venues: list[str]) -> bool:
    """False when the set mixes differently-quantized FR series, so FR is not the right variable.

    A cross-sectional carry signal ranking Binance against OKX on raw FR is ranking a quantized
    series against an unquantized one; the ranking partly measures the transform. Normalize to PI
    (``pi_range_from_fr``) or condition on venue.
    """
    ms = [mechanics(v) for v in venues]
    if any(m is None for m in ms):
        return False           # an unread venue is never assertable as comparable
    return len({(m.clamped, m.additive_offset) for m in ms if m is not None}) <= 1


# ------------------------------------------------------------------ 2. IMN-scaled depth
@dataclass(frozen=True)
class DepthContext:
    """How much book the PI that produced this FR actually looked at."""

    imn_usd: float
    reference_usd: float
    ratio: float               # imn_usd / reference_usd
    thin: bool
    note: str


def imn_depth_context(imn_usd: float, reference_usd: float = 880_000.0,
                      thin_ratio: float = 0.01) -> DepthContext:
    """Context for believing an FR extreme, scaled by the notional its impact prices read.

    ``reference_usd`` defaults to the measured Bybit BTCUSDT IMN (~20 BTC ~ $880k). ``thin_ratio``
    is a STATED PRIOR, NOT A MEASUREMENT -- the desk has not measured where artifact risk starts,
    and this function does not pretend otherwise. It is exposed as an argument precisely so the
    caller owns the threshold rather than inheriting a number that looks calibrated and is not.
    What is measured is the SPREAD: ~7000x between BTCUSDT and HNT on one venue, which is why a
    single FR-extreme rule applied across a symbol universe is not comparing like with like.
    """
    ratio = imn_usd / reference_usd if reference_usd > 0 else 0.0
    thin = ratio < thin_ratio
    return DepthContext(
        imn_usd, reference_usd, ratio, thin,
        f"IMN ${imn_usd:,.0f} is {ratio:.4g}x the ${reference_usd:,.0f} reference"
        + (" -- THIN: treat an FR extreme here as possible book microstructure, not positioning"
           if thin else " -- depth comparable to the reference"))


# ------------------------------------------------------------------ 3. interval switching
def detect_interval_switches(stamps: list[datetime],
                             tol_h: float = 0.25) -> list[tuple[datetime, float, float]]:
    """Points where the settlement spacing CHANGED, as (when, from_hours, to_hours).

    A funding series is routinely assumed to sit on one fixed grid. Venues switch hot alts
    8h -> 4h -> 2h ad hoc, and the switch lands in exactly the high-funding window a carry study
    cares about, so the corruption is concentrated where the signal is. Returns [] for a series
    that never switched -- and [] is also the honest answer for fewer than 3 stamps, where no
    spacing CHANGE is observable.
    """
    if len(stamps) < 3:
        return []
    ts = sorted(s.replace(tzinfo=UTC) if s.tzinfo is None else s.astimezone(UTC) for s in stamps)
    gaps = [(ts[i + 1] - ts[i]).total_seconds() / 3600.0 for i in range(len(ts) - 1)]
    out = []
    for i in range(1, len(gaps)):
        if abs(gaps[i] - gaps[i - 1]) > tol_h:
            out.append((ts[i], gaps[i - 1], gaps[i]))
    return out


def uniform_interval(stamps: list[datetime], tol_h: float = 0.25) -> float | None:
    """The single interval of a series, or ``None`` if it switched -- so callers must handle it.

    Refuses rather than averaging. A mean interval across a switch is a number that describes no
    period of the series, and it is exactly what a naive ``/ 8.0`` produces.
    """
    if len(stamps) < 2:
        return None
    if detect_interval_switches(stamps, tol_h):
        return None
    ts = sorted(s.replace(tzinfo=UTC) if s.tzinfo is None else s.astimezone(UTC) for s in stamps)
    return (ts[1] - ts[0]).total_seconds() / 3600.0


# ------------------------------------------------------------------ 4. payment-timing alignment
def settlement_lag_periods(venue: str) -> int | None:
    """0, or 1 where the venue applies a rate one period AFTER its computation window.

    OKX and BitMEX are the 1s. Joining their funding to returns on the computation stamp reads a
    payment that had not happened yet -- a full-period look-ahead on the exact series a carry
    signal is built from, which is the failure mode that manufactures edge rather than losing it.
    """
    m = mechanics(venue)
    return None if m is None else int(m.pays_one_period_late)


def payment_stamp(computed_at: datetime, venue: str, interval_h: float) -> datetime | None:
    """When the rate computed at ``computed_at`` is actually PAID on ``venue``.

    This is the stamp a funding-to-return join must use. §26(4) alignment material: state it,
    do not infer it -- an unstated alignment voids the screen that rests on it.
    """
    lag = settlement_lag_periods(venue)
    if lag is None or interval_h <= 0:
        return None
    t = computed_at
    t = t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)
    return t + timedelta(hours=interval_h * lag)


# ------------------------------------------------------------------ 5. discretionary caps
def is_cap_pinned(fr: float, venue: str, tol: float = 1e-9) -> bool | None:
    """True when the print is sitting ON a known cap, so the true premium is CENSORED above it.

    A capped print is a lower bound wearing the costume of a measurement. Sizing a position off
    it under-states the move that is actually happening, and the cap can be RAISED without notice
    by a human -- so the moment it moves is a regime event for anything sized against the old one.
    """
    m = mechanics(venue)
    if m is None:
        return None
    return any(abs(abs(fr) - c) <= tol for c in m.caps)


def detect_cap_events(series: list[tuple[datetime, float]],
                      venue: str) -> list[tuple[datetime, float, float]]:
    """Points where the observed |FR| ceiling MOVED, as (when, old_ceiling, new_ceiling).

    Caps are unannounced, so they are only observable as a change in the running maximum against
    the known ladder. Detects a move to a DIFFERENT rung -- not every new high, which would fire
    on ordinary funding variation.
    """
    m = mechanics(venue)
    if m is None or not m.caps or len(series) < 2:
        return []
    out: list[tuple[datetime, float, float]] = []
    rung: float | None = None
    for when, fr in sorted(series, key=lambda r: r[0]):
        hit = next((c for c in m.caps if abs(abs(fr) - c) <= 1e-9), None)
        if hit is None:
            continue
        if rung is not None and hit != rung:
            out.append((when, rung, hit))
        rung = hit
    return out


# ------------------------------------------------------------------ the verification layer
def verify_funding_series(*, venue: str, stamps: list[datetime], rates: list[float],
                          imn_usd: float | None = None) -> dict[str, object]:
    """Run all five fences over one venue's funding series and report what is not trustworthy.

    This is the checklist R0021 asks for, in one call, so a carry study cannot run four of the
    five and believe it ran the set. Returns a report rather than raising: the caller decides
    what to do, but it can no longer claim it was never told.
    """
    m = mechanics(venue)
    if m is None:
        return {"venue": venue, "status": "REFUSED",
                "detail": f"mechanics for {venue!r} have not been read -- assuming Binance-style "
                          "clamp/timing is the defect this module exists to prevent",
                "known_venues": sorted(_VENUES)}
    if len(stamps) != len(rates):
        raise ValueError(f"stamps ({len(stamps)}) and rates ({len(rates)}) must align 1:1")

    pinned = [r for r in rates if fr_is_pinned(r, venue)]
    switches = detect_interval_switches(stamps)
    caps = detect_cap_events(list(zip(stamps, rates, strict=True)), venue)
    capped = [r for r in rates if is_cap_pinned(r, venue)]
    depth = imn_depth_context(imn_usd) if imn_usd is not None else None

    findings = []
    if pinned:
        findings.append(
            f"{len(pinned)}/{len(rates)} prints sit in the clamp dead-band, each hiding a "
            f"{hidden_carry_spread_bp(pinned[0], venue):.1f}bp-wide PI range -- read PI, not FR")
    if switches:
        findings.append(
            f"{len(switches)} interval switch(es) "
            f"({'; '.join(f'{a:.0f}h->{b:.0f}h @ {w:%Y-%m-%d}' for w, a, b in switches[:3])}) "
            "-- a fixed-grid join is corrupted across these")
    if caps:
        findings.append(f"{len(caps)} cap-ladder change(s) -- regime events for anything sized "
                        "against the old ceiling")
    if capped:
        findings.append(f"{len(capped)} print(s) pinned ON a cap -- those are CENSORED lower "
                        "bounds, not measurements")
    if m.pays_one_period_late:
        findings.append("venue pays ONE PERIOD LATE -- join on payment_stamp(), not the "
                        "computation stamp, or the series carries a full-period look-ahead")
    if depth is not None and depth.thin:
        findings.append(f"thin book: {depth.note}")

    return {"venue": m.venue, "status": "CLEAN" if not findings else "CONDITIONS",
            "n": len(rates), "pinned_prints": len(pinned), "interval_switches": len(switches),
            "cap_events": len(caps), "capped_prints": len(capped),
            "pays_one_period_late": m.pays_one_period_late,
            "uniform_interval_h": uniform_interval(stamps), "findings": findings,
            "mechanics_note": m.note}
