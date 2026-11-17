#!/usr/bin/env python3
"""Add cot_positioning_reversal generator to generators.py."""
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/generators.py")
src = p.read_text()

# 1) The function, after _producer_margin_stress's end (before class GeneratorSpec)
anchor = "class GeneratorSpec:"
fn = '''def _cot_positioning_reversal(s: MarketSeries, p: dict[str, float]) -> np.ndarray:
    """Fade extreme speculative net positioning in CME/Coinbase BTC and ETH futures.

    THE PAYER is the leveraged non-commercial crowd whose net stance the CFTC publishes every
    Friday in the Commitments of Traders report -- free, lagging and mechanical. When
    speculators are heavily net long (crowded long), the unwind is the trade: they must
    liquidate on the exchange's schedule once the crowd stops adding, and the funding-fade
    evidence says that unwind is the mean-reverting force. This is the SAME payer as
    ``funding_stress_reversal`` -- a crowded levered book -- but measured from the POSITIONING
    print itself (weekly COT) rather than the perp funding rate (daily venue print). The two
    inputs are complementary: funding is the daily price of leverage, COT is the weekly stock
    of it.

    SHARE OF OPEN INTEREST, NOT CONTRACTS: net non-commercial contracts are not comparable
    across the CME + Coinbase books the lake carries; normalising by OI makes the meter a
    fraction between -1 and 1. The z-score is then computed over a trailing window in WEEKS
    (weekly data reindexed daily), exactly like ``funding_stress_reversal`` z-scores its input.

    NO-LOOKAHEAD: the adapter stamps each COT row with pub_date = report date + 4 days and
    forward-fills past-only, so the bar sees only reports already published.

    DEGRADES TO FLAT without COT data (per-asset; alts and pre-2018 bars have none), like the
    other non-price generators. A spec that cannot see its input is a zero, not a mechanism.

    SIGN: net_spec z > +thr -> crowd is crowded long -> short (position -1).
         net_spec z < -thr -> crowd is crowded short -> long (position +1).
    Fade, never follow: this is a positioning-unwind claim, not an information claim.
    """
    if s.cot_spec_share is None:
        return np.zeros(len(s), dtype="float64")
    pos = np.nan_to_num(s.cot_spec_share, nan=0.0)
    weeks = int(p.get("weeks", 26))
    w = weeks * 7
    z = np.zeros(len(pos), dtype="float64")
    for i in range(w, len(pos)):
        seg = pos[i - w + 1: i + 1]
        sd = seg.std()
        z[i] = (pos[i] - seg.mean()) / sd if sd > 0 else 0.0
    thr = float(p.get("z_entry", 2.0))
    return np.where(z > thr, -1.0, np.where(z < -thr, 1.0, 0.0)).astype("float64")


'''
if anchor not in src:
    print("anchor not found")
    raise SystemExit(2)
src = src.replace(anchor, fn + anchor, 1)

# 2) The spec, after producer_margin_stress's spec block
old_spec = '''    GeneratorSpec(Family.LIQUIDITY, "producer_margin_stress", _producer_margin_stress, _S,
                  "forced selling by a fiat-cost-base producer; the exit is confirmed by a "
                  "DOWNWARD difficulty adjustment, which is mechanical and lagging, not forecast",
                  ["needs hashprice; flat without it",
                   "difficulty is a step function -- compare across the retarget, not bar-to-bar",
                   "census class is treasury_cost_base_liquidation, NOT mechanical_supply_release: "
                   "that is a SCHEDULE known in advance, this is a balance-sheet constraint",
                   "a miner hedging with derivatives sells less spot than the cost base implies"],
                  [{"window": 90, "z_entry": 1.0, "retarget": 14},
                   {"window": 180, "z_entry": 1.5, "retarget": 14}]),
)'''

new_spec = '''    GeneratorSpec(Family.LIQUIDITY, "producer_margin_stress", _producer_margin_stress, _S,
                  "forced selling by a fiat-cost-base producer; the exit is confirmed by a "
                  "DOWNWARD difficulty adjustment, which is mechanical and lagging, not forecast",
                  ["needs hashprice; flat without it",
                   "difficulty is a step function -- compare across the retarget, not bar-to-bar",
                   "census class is treasury_cost_base_liquidation, NOT mechanical_supply_release: "
                   "that is a SCHEDULE known in advance, this is a balance-sheet constraint",
                   "a miner hedging with derivatives sells less spot than the cost base implies"],
                  [{"window": 90, "z_entry": 1.0, "retarget": 14},
                   {"window": 180, "z_entry": 1.5, "retarget": 14}]),
    # CFTC COT positioning fade -- the second generator whose input is NOT a price. Sourced
    # from the weekly Commitments of Traders report (free, published every Friday), so the
    # speculative net share is the CROWD's own balance sheet. Census class
    # positioning_crowding_unwind, the same payer as funding_stress_reversal -- a crowded
    # levered book -- read from the positioning print rather than the funding print.
    GeneratorSpec(Family.LIQUIDITY, "cot_positioning_reversal", _cot_positioning_reversal, _L,
                  "fade the CFTC COT speculative net position in CME/Coinbase BTC+ETH futures: "
                  "a crowded levered book (weekly positioning print) unwinds like a crowded "
                  "funding book (daily venue print) -- same payer, complementary meter",
                  ["needs COT data; flat without it (alts, pre-2018)",
                   "weekly input reindexed daily: the z-score moves once a week, so positions "
                   "persist longer than the daily funding fade -- parameter weeks, not bars",
                   "census class is positioning_crowding_unwind: this ADDS a meter to an "
                   "un-crowded class, it does NOT add a mechanism -- funding_stress_reversal "
                   "already owns the payer",
                   "COT measures CME/Coinbase futures positioning; spot margin books are the "
                   "same crowd only insofar as the basis trade holds them together"],
                  [{"weeks": 26, "z_entry": 2.0},
                   {"weeks": 52, "z_entry": 2.0},
                   {"weeks": 26, "z_entry": 1.5}]),
)'''

if old_spec not in src:
    print("spec anchor not found")
    raise SystemExit(3)
src = src.replace(old_spec, new_spec)

# 3) Divergence record (Family.LIQUIDITY claims liquidity_provision_immediacy; census says
#    positioning_crowding_unwind, so the fence needs the written reason -- same as its sibling)
old_div = '''    "funding_stress_reversal": (
        "FILED `liquidity`, IS `positioning_crowding_unwind`. Fading funding stress is a claim "
        "about a leveraged trader liquidated on the VENUE'S schedule, not about a warehouse being "
        "paid for immediacy. Counting it under liquidity provision would add a sixth member to a "
        "class already tested to exhaustion while hiding the library's only occupant of a class "
        "the price-only classes do not own."
    ),
}'''
new_div = '''    "funding_stress_reversal": (
        "FILED `liquidity`, IS `positioning_crowding_unwind`. Fading funding stress is a claim "
        "about a leveraged trader liquidated on the VENUE'S schedule, not about a warehouse being "
        "paid for immediacy. Counting it under liquidity provision would add a sixth member to a "
        "class already tested to exhaustion while hiding the library's only occupant of a class "
        "the price-only classes do not own."
    ),
    "cot_positioning_reversal": (
        "FILED `liquidity`, IS `positioning_crowding_unwind`. The payer is the same crowded "
        "levered book as funding_stress_reversal, read from the CFTC's weekly positioning print "
        "instead of the venue's daily funding print -- the census class names the PAYER, and "
        "this spec's payer is an unwinding crowd, not a warehouse being paid for immediacy. "
        "Filing it under liquidity provision would add a seventh member to the desk's most "
        "crowded class while the positioning-unwind class stays at two meters of one payer."
    ),
}'''
if old_div not in src:
    print("divergence anchor not found")
    raise SystemExit(4)
src = src.replace(old_div, new_div)

p.write_text(src)
print("Patched generators.py")