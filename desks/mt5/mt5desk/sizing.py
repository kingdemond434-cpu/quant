"""Generic risk-fraction position sizing for promoted sleeves (principal order 2026-08-25).

Replaces the gold-parameterized auto_lot math on the PROMOTED path: every promoted sleeve
risks BASE_RISK_FRAC of current account equity per trade (3% base minimum, principal-set),
computed from the trade's OWN stop distance and the symbol's OWN tick economics as the broker
reports them -- no per-symbol constants, no hardcoded contract math (LAWS anti-hardcode).

Dynamic-up: a sleeve row in data/sleeves.json may carry "risk_frac" above the base when the
promoter records the economic justification (Kelly-shrunk evidence); it is clamped to
[BASE_RISK_FRAC, MAX_RISK_FRAC]. The canary authority ramp (0.25x/0.5x/1.0x by live trade
count) multiplies the risk fraction, not the lot, so authority scales risk in equity terms.

Pure module on purpose: no MetaTrader5 import, so the arithmetic is unit-testable off-box
(promotion rule 13) and reusable by the promoter for capacity checks. The gateway passes the
broker-truth fields in.

The armed GOLD book is untouched (hunt5 authority, q=5.5% validated 2026-08-16, human-armed);
this governs promoted sleeves only.
"""
from __future__ import annotations

BASE_RISK_FRAC = 0.03   # principal 2026-08-25: base minimum risk per promoted trade
MAX_RISK_FRAC = 0.10    # dynamic-up ceiling; raising it is a principal act, never autonomous

#: L1.59 FADE. Must equal decay_monitor.FADE_FACTOR -- pinned by test, because two copies of a
#: risk constant that drift apart is how a halving becomes a quartering nobody ordered.
FADE_FACTOR = 0.5


def authority_ramp(live_n: int) -> float:
    """Canary authority by forward-proven live trades: 0.25x <50, 0.5x <200, 1.0x after."""
    return 0.25 if live_n < 50 else (0.5 if live_n < 200 else 1.0)


def decay_factor(decay_faded: object) -> float:
    """L1.59 FADE as a MULTIPLIER, applied outside `clamp_risk_frac` like `authority_ramp`.

    WHY IT CANNOT LIVE INSIDE THE FRACTION (gap-fixer 2026-08-29). `decay_monitor` halved the
    sleeve's `risk_frac` in `data/sleeves.json` -- 0.03 -> 0.015 -- and `clamp_risk_frac` floors
    at `BASE_RISK_FRAC`, so the gateway read it straight back up to 0.03. MEASURED end to end on
    the real functions: a HEALTHY sleeve and a FADED one both sized **3.0 lots** on identical
    inputs. The monitor wrote its flag, the ledger recorded `FADE risk_frac [0.03, 0.015]`, and
    the trade risked exactly what it had before. LAWS L1.59 says in its own text *"a decay flag
    nothing consumes is an opinion, not a monitor"* -- the flag WAS consumed, by a floor one
    layer below where the law was looking.

    The floor is not the bug: a 3% MINIMUM for a proven sleeve is the principal's anti-timidity
    order (2026-08-25) and is untouched here. But a faded sleeve is one whose edge has been
    MEASURED ABSENT at the same n the desk trusts for promotion, so the premise of that minimum
    -- a proven edge -- no longer holds, and the sealed core is explicit that sizing beyond
    demonstrated edge is not aggression but ruin. Applying the fade OUTSIDE the clamp keeps both
    rules intact: the floor still governs what a proven sleeve may request, and the fade still
    governs what an unproven one actually gets.

    THE FLAG IS THE SINGLE SOURCE OF TRUTH, and that is deliberate. Halving the stored fraction
    as WELL would compound with this multiplier -- a dynamic-up sleeve at 0.06 would be written
    to 0.03, floored to 0.03, then halved to 0.015: a 4x cut where the law orders 2x. It also
    makes UNFADE exact, since removing a flag is lossless where dividing by 0.5 is not.
    """
    return FADE_FACTOR if decay_faded else 1.0


def clamp_risk_frac(value: object) -> float:
    """A sleeve's requested risk fraction, clamped to [base, max]; junk falls to base."""
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return BASE_RISK_FRAC
    return min(max(f, BASE_RISK_FRAC), MAX_RISK_FRAC)


def risk_lot(equity: float, sl_dist_price: float, tick_value: float, tick_size: float,
             volume_min: float, volume_step: float, volume_max: float,
             risk_frac: float = BASE_RISK_FRAC, live_n: int = 0,
             decay_faded: object = None) -> float:
    """Lots such that (stop distance x per-lot value) == risk_frac x ramp x equity.

    tick_value/tick_size are the broker's account-currency economics for ONE lot, so the
    FX conversion is the broker's, not ours. Returns 0.0 when the trade cannot be sized
    honestly (degenerate inputs, or even volume_min risks more than twice the target --
    an unsizeable trade is skipped, never silently oversized).
    """
    if equity <= 0 or sl_dist_price <= 0 or tick_value <= 0 or tick_size <= 0 \
            or volume_step <= 0 or volume_min <= 0:
        return 0.0
    per_lot_risk = sl_dist_price * (tick_value / tick_size)
    target = (equity * clamp_risk_frac(risk_frac) * authority_ramp(live_n)
              * decay_factor(decay_faded))
    raw = target / per_lot_risk
    lots = int(raw / volume_step) * volume_step          # round DOWN: never oversize
    lots = round(lots, 8)
    if lots < volume_min:
        # volume_min itself may still be acceptable if it does not blow the target badly.
        if per_lot_risk * volume_min <= 2.0 * target:
            return float(min(volume_min, volume_max))
        return 0.0
    return float(min(lots, volume_max))
