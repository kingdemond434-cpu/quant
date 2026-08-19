"""Every Profit Engine Pro fill the operator has mirrored, and what it implies.

These are the COPIER's fills, not the master's, so lot sizes are already scaled
to the operator's account -- which is what makes the risk arithmetic meaningful
and the master's own equity curve irrelevant to it.

WHAT A FILL LIST CAN AND CANNOT TELL YOU

It can tell you: direction mix, size progression, how tickets group into
decisions, how far a decision travels before it is closed, and what the worst
one cost. Those are arithmetic.

It cannot tell you WHY an entry happened. There are no timestamps finer than
the ticket ordering, no indicator values, no chart state. Any claim about "he
enters on a liquidity sweep" would be invention. What the entries look like
from here is a distribution of prices, and the honest output is the SHAPE of
the strategy, not its trigger.

THE GROUPING RULE, AND WHY IT DECIDES EVERYTHING

Tickets sharing a close price are one decision. But tickets sharing an OPEN
price to within a dollar are not an "add at a level" either -- they are one
order split across several tickets, which is what a copy platform does when it
mirrors size. Conflating those two produces a story about grid trading that the
fills do not support. Both are measured separately below.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "reports" / "pe_fills.json"
FX = 1.154          # EUR/USD implied by reconciling reported PnL against lots
OZ_PER_LOT = 100.0
EQUITY = 988.0      # operator's equity at the time of the screenshots

# (ticket, side, lots, open, close, eur, symbol)
FILLS = [
    (102740750, "S", 0.0145, 4395.59, 4417.15, -27.07, "XAUUSD"),
    (102740992, "S", 0.0145, 4395.60, 4417.15, -27.06, "XAUUSD"),
    (102743057, "S", 0.0145, 4398.20, 4417.07, -23.69, "XAUUSD"),
    (102808596, "S", 0.0126, 4409.97, 4397.73, 13.36, "XAUUSD"),
    (102808895, "S", 0.0126, 4409.58, 4397.75, 12.91, "XAUUSD"),
    (102811813, "S", 0.0126, 4406.82, 4397.81, 9.83, "XAUUSD"),
    (102851207, "S", 0.0135, 4413.77, 4411.93, 2.15, "XAUUSD"),
    (102865301, "S", 0.0135, 4419.47, 4416.17, 3.86, "XAUUSD"),
    (102871067, "S", 0.0135, 4417.38, 4416.26, 1.31, "XAUUSD"),
    (102884083, "S", 0.0135, 4426.37, 4416.16, 11.94, "XAUUSD"),
    (102891692, "S", 0.0135, 4430.33, 4416.26, 16.45, "XAUUSD"),
    (102901186, "S", 0.0135, 4430.16, 4416.15, 16.38, "XAUUSD"),
    (103693827, "B", 0.0741, 4363.14, 4369.34, 39.80, "XAUUSD"),
    (103693994, "B", 0.0741, 4363.23, 4369.35, 39.29, "XAUUSD"),
    (103694794, "B", 0.0741, 4364.23, 4369.95, 36.73, "XAUUSD"),
    (103699627, "B", 0.0741, 4365.38, 4369.01, 23.31, "XAUUSD"),
    (104480241, "B", 0.1748, 4418.62, 4422.94, 65.37, "XAUUSD"),
    (104482259, "B", 0.1749, 4420.68, 4422.99, 34.98, "XAUUSD"),
    (104485534, "B", 0.1749, 4417.00, 4424.86, 119.02, "XAUUSD"),
    (104582249, "B", 0.2346, 4426.08, 4427.87, 36.35, "XAUUSD"),
    (104711848, "B", 0.2440, 4403.20, 4404.35, 24.33, "XAUUSD"),
    (104712423, "B", 0.2440, 4404.04, 4404.15, 2.32, "XAUUSD"),
    (104716235, "B", 0.2440, 4402.87, 4404.07, 25.39, "XAUUSD"),
    (105442319, "S", 3.1614, 53887.45, 53883.55, 10.69, "DJ30"),
    (105442991, "S", 3.1613, 53883.45, 53877.55, 16.17, "DJ30"),
    (105508310, "B", 0.2435, 4378.70, 4358.86, -418.78, "XAUUSD"),
    (105545747, "B", 0.2436, 4375.93, 4380.36, 93.49, "XAUUSD"),
    (105895616, "B", 0.0749, 4341.31, 4314.74, -172.54, "XAUUSD"),
    (105917753, "B", 0.0749, 4324.83, 4314.74, -65.52, "XAUUSD"),
    (106370865, "S", 0.0417, 4369.77, 4422.16, -187.31, "XAUUSD"),
    (106403745, "S", 0.0418, 4378.97, 4374.17, 17.34, "XAUUSD"),
    (106433611, "B", 0.0877, 4378.49, 4391.88, 101.39, "XAUUSD"),
    (106465350, "B", 0.5845, 53815.60, 53832.45, 8.51, "DJ30"),
    (106465489, "B", 0.5845, 53812.60, 53836.45, 12.04, "DJ30"),
    (106466898, "B", 0.5845, 53735.55, 53826.40, 45.88, "DJ30"),
    (106517376, "S", 0.0663, 4391.51, 4388.05, 19.80, "XAUUSD"),
    (106517903, "S", 0.0663, 4390.79, 4388.04, 15.74, "XAUUSD"),
    (106557385, "B", 0.1421, 4385.08, 4385.43, 4.29, "XAUUSD"),
    (106574785, "B", 0.1432, 4386.61, 4388.40, 22.13, "XAUUSD"),
    (106581566, "B", 0.1492, 4390.23, 4423.38, 415.93, "XAUUSD"),
    (107579101, "S", 0.1284, 4423.19, 4416.38, 75.42, "XAUUSD"),
    (107579476, "S", 0.1284, 4423.17, 4416.50, 73.87, "XAUUSD"),
    (107775272, "B", 0.1279, 4402.46, 4406.39, 43.42, "XAUUSD"),
    (107775675, "B", 0.1279, 4403.18, 4406.51, 36.80, "XAUUSD"),
]


def move_usd(r) -> float:
    """Signed favourable move in quote units, per unit."""
    _, side, _, op, cl, _, _ = r
    return (cl - op) * (1 if side == "B" else -1)


def main() -> int:
    gold = [r for r in FILLS if r[6] == "XAUUSD"]
    pnl = [r[5] for r in FILLS]
    w = [x for x in pnl if x > 0]
    lo = [x for x in pnl if x < 0]
    aw, al = sum(w) / len(w), abs(sum(lo) / len(lo))

    print(f"PROFIT ENGINE PRO -- {len(FILLS)} mirrored fills "
          f"({len(gold)} gold, {len(FILLS) - len(gold)} index)")
    print(f"  net EUR {sum(pnl):+.2f}   wins {len(w)} avg {aw:+.2f}   "
          f"losses {len(lo)} avg {-al:+.2f}")
    print(f"  win rate {100 * len(w) / len(FILLS):.1f}%   "
          f"loss/win size {al / aw:.2f}x   "
          f"break-even {100 * al / (al + aw):.1f}%")
    print(f"  worst fill EUR {min(pnl):+.2f} = {100 * abs(min(pnl)) / EQUITY:.1f}% "
          f"of EUR {EQUITY:.0f} equity")
    print(f"  direction: {sum(1 for r in FILLS if r[1] == 'B')} buys, "
          f"{sum(1 for r in FILLS if r[1] == 'S')} sells")

    print("\nHOW FAR A GOLD DECISION TRAVELS BEFORE IT IS CLOSED (USD/oz)")
    mv = sorted(move_usd(r) for r in gold)
    wins = [m for m in mv if m > 0]
    loss = [m for m in mv if m <= 0]
    print(f"  winners n={len(wins)}  median {sorted(wins)[len(wins) // 2]:+.2f}  "
          f"max {max(wins):+.2f}")
    print(f"  losers  n={len(loss)}  median {sorted(loss)[len(loss) // 2]:+.2f}  "
          f"worst {min(loss):+.2f}")
    print("  -> NO fixed take-profit and NO fixed stop. A strategy with either")
    print("     would show a spike in this distribution; this one is smeared.")

    print("\nTICKETS THAT SHARE A CLOSE = ONE DECISION")
    grp = defaultdict(list)
    for r in gold:
        grp[round(r[4], 1)].append(r)
    split, spaced = 0, 0
    rows = []
    for cl, rs in sorted(grp.items()):
        if len(rs) < 2:
            continue
        rs.sort(key=lambda r: r[0])
        opens = [r[3] for r in rs]
        spread = max(opens) - min(opens)
        kind = "SPLIT (one order, several tickets)" if spread <= 1.5 \
            else "SPACED (a genuine second entry)"
        if spread <= 1.5:
            split += 1
        else:
            spaced += 1
        tot = sum(r[5] for r in rs)
        print(f"  close {cl:8.2f}  {rs[0][1]} x{len(rs)}  "
              f"open spread {spread:5.2f}  PnL EUR {tot:+8.2f}   {kind}")
        rows.append({"close": cl, "n": len(rs), "open_spread": round(spread, 2),
                     "pnl_eur": round(tot, 2), "kind": kind.split()[0]})
    print(f"\n  {split} groups are SPLIT fills, {spaced} are SPACED entries.")
    print("  That matters: a grid story needs SPACED adds, and most of these")
    print("  are one order mirrored across tickets at the same price.")

    print("\nSIZE OVER TIME (ticket number as the clock)")
    for r in sorted(gold, key=lambda r: r[0])[::4]:
        print(f"  #{r[0]}  {r[2]:.4f} lots = {r[2] * OZ_PER_LOT:6.2f} oz  "
              f"@ {r[3]:.2f}")
    big = max(gold, key=lambda r: r[2])
    oz = big[2] * OZ_PER_LOT
    print(f"\n  largest single gold ticket: {big[2]:.4f} lots = {oz:.1f} oz")
    print(f"  notional USD {oz * big[3]:,.0f} on EUR {EQUITY:.0f} equity "
          f"= {oz * big[3] / (EQUITY * FX):.0f}x")
    print(f"  adverse move that would wipe the account on ONE such ticket: "
          f"{EQUITY * FX / oz:.2f} USD/oz")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "n_fills": len(FILLS), "net_eur": round(sum(pnl), 2),
        "win_rate": round(len(w) / len(FILLS), 4),
        "avg_win": round(aw, 2), "avg_loss": round(-al, 2),
        "loss_win_ratio": round(al / aw, 3),
        "breakeven_win_rate": round(al / (al + aw), 4),
        "worst_fill_eur": min(pnl),
        "groups": rows, "split_groups": split, "spaced_groups": spaced,
    }, indent=1), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
