"""Every Profit Engine Pro fill for which the operator captured a timestamp.

Timestamps are what turned this from outcome-watching into mechanism-reading.
They also killed two claims I had already made from prices alone, which is why
they live in their own file with the clock as a first-class column.

WHAT THE CLOCK OVERTURNED

  "Winners exit fast, losers are held indefinitely." False. The single worst
  fill (-418.78) was cut in 24.0 minutes -- the same band as the winners. A
  -187.31 was held 74 hours. Hold time does not order the losses.

  "Loss size is a function of duration." Also false. -418.78 came from SIZE
  (0.2435 lots at -0.45%); -187.31 came from DURATION (0.0417 lots at -1.20%).
  Two different failure modes wearing the same colour.

Times are broker server time, offset unknown. Nothing here depends on the
offset except the session hypothesis, which is labelled as a hypothesis.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "reports" / "pe_timed.json"
FMT = "%d/%m/%Y %H:%M:%S"

# (ticket, symbol, side, lots, open, close, eur, open_time, close_time)
TIMED = [
    (104716235, "XAUUSD", "B", 0.2440, 4402.87, 4404.07, 25.39,
     "12/08/2026 19:56:08", "12/08/2026 20:02:22"),
    (105442319, "DJ30", "S", 3.1614, 53887.45, 53883.55, 10.69,
     "13/08/2026 16:36:53", "13/08/2026 16:52:32"),
    (105442991, "DJ30", "S", 3.1613, 53883.45, 53877.55, 16.17,
     "13/08/2026 16:36:57", "13/08/2026 16:52:29"),
    (105508310, "XAUUSD", "B", 0.2435, 4378.70, 4358.86, -418.78,
     "13/08/2026 17:06:17", "13/08/2026 17:30:14"),
    (105545747, "XAUUSD", "B", 0.2436, 4375.93, 4380.36, 93.49,
     "13/08/2026 17:20:51", "13/08/2026 17:44:13"),
    (105895616, "XAUUSD", "B", 0.0749, 4341.31, 4314.74, -172.54,
     "14/08/2026 04:00:51", "14/08/2026 05:11:10"),
    (106370865, "XAUUSD", "S", 0.0417, 4369.77, 4422.16, -187.31,
     "14/08/2026 15:16:30", "17/08/2026 17:26:53"),
    (107777349, "XAUUSD", "B", 0.1279, 4400.07, 4406.20, 67.74,
     "17/08/2026 21:33:51", "17/08/2026 21:50:37"),
    (108382441, "DJ30", "B", 1.8355, 53296.76, 53396.44, 157.97,
     "18/08/2026 16:30:41", "18/08/2026 16:44:20"),
    (108385335, "DJ30", "B", 1.8359, 53358.54, 53405.44, 74.34,
     "18/08/2026 16:31:13", "18/08/2026 16:44:10"),
    (108386611, "DJ30", "B", 1.8359, 53388.66, 53411.44, 36.11,
     "18/08/2026 16:31:29", "18/08/2026 16:44:08"),
    (108637270, "XAUUSD", "B", 0.1902, 4366.62, 4372.61, 98.33,
     "18/08/2026 18:00:08", "18/08/2026 18:04:16"),
    (108718822, "XAUUSD", "B", 0.2030, 4358.80, 4360.91, 36.98,
     "18/08/2026 18:19:14", "18/08/2026 18:39:22"),
    (108725467, "XAUUSD", "B", 0.2030, 4353.76, 4361.17, 129.88,
     "18/08/2026 18:20:07", "18/08/2026 18:39:32"),
    (108730054, "XAUUSD", "B", 0.2030, 4354.47, 4359.53, 88.69,
     "18/08/2026 18:20:22", "18/08/2026 18:40:14"),
]


def t(s):
    return datetime.strptime(s, FMT)


def pct(r):
    sgn = 1 if r[2] == "B" else -1
    return 100.0 * sgn * (r[5] - r[4]) / r[4]


def mins(r):
    return (t(r[8]) - t(r[7])).total_seconds() / 60.0


def main() -> int:
    rows = sorted(TIMED, key=lambda r: t(r[7]))
    print(f"{len(rows)} timestamped fills\n")
    print(f"{'ticket':>10} {'sym':<7}{'sd':>3}{'lots':>8}{'EUR':>9}"
          f"{'move%':>9}{'held':>12}   opened")
    for r in rows:
        m = mins(r)
        hs = f"{m:.1f} min" if m < 120 else f"{m / 60:.1f} HOURS"
        print(f"{r[0]:>10} {r[1]:<7}{r[2]:>3}{r[3]:>8.4f}{r[6]:>9.2f}"
              f"{pct(r):>9.4f}{hs:>12}   {r[7]}")

    print("\nWHAT ORDERS THE LOSSES?  (it is not hold time)")
    for r in [x for x in rows if x[6] < 0]:
        print(f"  {r[0]}  EUR {r[6]:+8.2f}  = {pct(r):+.4f}% on {r[3]:.4f} lots,"
              f" held {mins(r):.1f} min")
    print("  -418.78 was cut in 24 minutes and is the WORST fill: big SIZE.")
    print("  -187.31 ran 74 hours and is smaller: small size, long DURATION.")
    print("  Two failure modes. A stop fixes one of them and not the other.")

    print("\nDJ30 ENTRY TIMES -- two different days")
    dj = [r for r in rows if r[1] == "DJ30"]
    for r in dj:
        print(f"  {r[7]}  {r[2]}  @ {r[4]:.2f}")
    span = [t(r[7]).hour * 60 + t(r[7]).minute for r in dj]
    print(f"  every DJ30 entry falls in {min(span) // 60}:{min(span) % 60:02d}"
          f"-{max(span) // 60}:{max(span) % 60:02d} server time, on both days.")
    print("  HYPOTHESIS (offset unverified): at UTC+3 that is 13:30-13:37 UTC,")
    print("  the first seven minutes of the New York cash session.")

    print("\nBASKET TARGETS -- lot-weighted, tickets closed together")
    grp = defaultdict(list)
    for r in rows:
        grp[(r[1], t(r[8]).strftime("%d/%m %H:%M"))].append(r)
    tg = []
    for (sym, when), rs in sorted(grp.items()):
        if len(rs) < 2:
            continue
        L = sum(x[3] for x in rs)
        ae = sum(x[3] * x[4] for x in rs) / L
        ax = sum(x[3] * x[5] for x in rs) / L
        sgn = 1 if rs[0][2] == "B" else -1
        p = 100.0 * sgn * (ax - ae) / ae
        tg.append(p)
        print(f"  {sym:<7} {when}  x{len(rs)}  entry {ae:10.2f} -> {ax:10.2f}"
              f"   {p:+.4f}%")
    if tg:
        print(f"  mean basket target {sum(tg) / len(tg):+.4f}% "
              f"across {len(tg)} baskets on 2 instruments")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        [{"ticket": r[0], "symbol": r[1], "side": r[2], "lots": r[3],
          "open": r[4], "close": r[5], "eur": r[6],
          "open_time": r[7], "close_time": r[8],
          "move_pct": round(pct(r), 4), "held_min": round(mins(r), 1)}
         for r in rows], indent=1), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
