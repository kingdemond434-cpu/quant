"""Audit what each instrument ACTUALLY risks at its initial stop, against what policy intended.

    python research/audit_risk_conversion.py

WHY LOT SIZES PROVE NOTHING, AND WHY I SAID OTHERWISE ONCE

Reviewing the demo account I compared EURUSD at ~EUR 12.5/pip against gold at ~EUR 6 per dollar
and called them "not close in risk terms". That was not a risk comparison. Monetary risk is

    risk = position sensitivity x DISTANCE TO THE INITIAL STOP

so EUR 12.5/pip on a ~12.5-pip stop and ~EUR 5.2/dollar on a ~$30 stop are both about EUR 156 --
and the realised gold losses of EUR 156.71 and EUR 159.78 are consistent with a COMMON monetary
budget rather than evidence against one. Sensitivity without stop distance is half an equation.

The conversion is still worth auditing. It just has to be audited on the quantity that can
actually be wrong:

    realised loss if the initial stop fills / equity at entry     vs     the intended fraction

That is the number that catches a contract-size error, a tick-value error, a quote-currency
error or a missing FX conversion, because all four corrupt it and none of them are visible in a
lot size. An instrument whose true risk is 7% while the desk logs 1.27% looks completely normal
until the position resolves.

WHAT THIS READS

`data/universe/universe.json` for tick economics, and `mt5desk.risk_units` for the conversion
under test -- the same function the gateway sizes with, so a discrepancy here is a discrepancy
in the money path rather than in a reimplementation of it.

WHAT IT CANNOT SEE

The account's real equity and the stop distances actually placed. Those live on the box. This
audits the CONVERSION across a plausible stop range; a per-ticket audit against the live ledger
is the next step and needs the box, not this clone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import risk_units as ru  # noqa: E402
from mt5desk.gateway_config_fallback import Q_OPT  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe" / "universe.json"

#: Stop distances to price, as multiples of each instrument's MEASURED H1 ATR. Deliberately a
#: RANGE rather than one number: a conversion error scales every row of an instrument the same
#: way, so it shows as a whole symbol at the wrong multiple of budget, not one awkward stop.
STOP_ATR_MULTIPLES = (0.5, 1.0, 2.0)

#: ATR window, matching `gateway.ATR_N` so this audits the scale the desk actually sizes against.
ATR_N = 20

#: The hard lot ceiling inside `risk_units.lot_for_risk`. Read from the function's own default
#: rather than restated, so this audit cannot drift away from the code under test.
LOT_CAP = ru.lot_for_risk.__kwdefaults__["cap"]

#: Nominal equity for the ratio. The absolute figure does not matter -- what is being tested is
#: whether every instrument lands at the SAME fraction, which is scale-free.
EQUITY_EUR = 20_000.0


def _atr(symbol: str) -> float | None:
    """Measured H1 ATR for one symbol, or None when there are no bars to measure from.

    Same true-range EWM the gateway sizes with, so the stop distances tested here are on the
    scale the desk actually trades rather than on a proxy. None rather than a default: an
    instrument whose volatility is unknown cannot be audited, and substituting a plausible
    number would manufacture the verdict.
    """
    p = BASE / "data" / "universe" / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    import pandas as pd                                              # noqa: PLC0415
    df = pd.read_parquet(p)
    if len(df) < ATR_N + 1:
        return None
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - df["close"].shift(1)).abs(),
                    (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    a = float(tr.ewm(alpha=1 / ATR_N, min_periods=ATR_N).mean().iloc[-1])
    return a if a > 0 else None


def main() -> int:
    if not UNI.exists():
        print(f"REFUSED: {UNI} not present. Run this where the universe snapshot lives.")
        return 2
    meta = json.loads(UNI.read_text(encoding="utf-8"))

    print(f"intended risk per trade: Q_OPT = {Q_OPT:.4%} of equity "
          f"(EUR {Q_OPT * EQUITY_EUR:,.2f} at EUR {EQUITY_EUR:,.0f})")
    print(f"{'symbol':<10} {'EUR/price-unit':>15} {'stop':>10} {'lot':>8} "
          f"{'risk EUR':>10} {'% equity':>9}  verdict")

    budget = Q_OPT * EQUITY_EUR
    offenders: list[str] = []
    unpriceable: list[str] = []

    for sym in sorted(meta):
        try:
            per_unit = ru.eur_per_price_unit(sym)
        except Exception as exc:                                    # noqa: BLE001
            # UNMEASURED is a real answer and is reported as one (L1.28a). An instrument the
            # desk cannot price is not an instrument that risks nothing.
            unpriceable.append(f"{sym}: {type(exc).__name__}")
            continue

        # THE INSTRUMENT'S OWN SCALE, MEASURED. A first version used `tick_size * 100` as a
        # stand-in and it was worthless: tick_size does not track volatility across asset
        # classes, so it priced BTCUSD stops at $0.50-$2.00 on a six-figure instrument and
        # reported a 100x "policy breach" that was pure artifact. Real ATR or nothing.
        atr = _atr(sym)
        if atr is None:
            unpriceable.append(f"{sym}: no H1 parquet to measure ATR from")
            continue

        for mult in STOP_ATR_MULTIPLES:
            stop_dist = atr * mult
            lot = ru.lot_for_risk(sym, stop_dist, budget)
            realised = ru.realised_risk_eur(sym, stop_dist, lot)
            frac = realised / EQUITY_EUR
            # TWO VENUE CONSTRAINTS THAT ARE NOT CONVERSION ERRORS, labelled separately so a
            # real defect is not lost among them. The min lot can force a position LARGER than
            # budget on an expensive instrument; the 5-lot cap holds one SMALLER than budget on
            # a tight stop. Both are the venue and the policy talking, not the arithmetic.
            if lot >= LOT_CAP - 1e-9 and realised < budget * 0.95:
                verdict = f"LOT CAP {LOT_CAP:g} binds (not a conversion error)"
            elif lot <= 0.01 + 1e-9 and realised > budget * 1.05:
                verdict = "MIN-LOT FLOOR (not a conversion error)"
            elif abs(frac - Q_OPT) <= 0.10 * Q_OPT:
                verdict = "ok"
            else:
                verdict = f"OFF POLICY by {frac / Q_OPT:.2f}x"
                offenders.append(f"{sym} @ {mult:g}x ATR stop: {frac:.3%} vs {Q_OPT:.3%}")
            print(f"{sym:<10} {per_unit:15.4f} {stop_dist:10.5f} {lot:8.2f} "
                  f"{realised:10.2f} {frac:9.3%}  {verdict}")

    print()
    if unpriceable:
        print(f"UNMEASURED ({len(unpriceable)}) -- cannot be priced, which is not the same as "
              f"risking nothing:")
        for u in unpriceable:
            print(f"  - {u}")
    if offenders:
        print(f"\nOFF POLICY ({len(offenders)}): these do not land at Q_OPT, and a conversion "
              f"error scales every row of an instrument the same way:")
        for o in offenders:
            print(f"  - {o}")
        return 1
    print("every priceable instrument lands within 10% of Q_OPT at every stop tested.")
    print("NOTE: this audits the CONVERSION, not the account. A per-ticket audit against the "
          "live ledger needs the box.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
