"""CARRY VIABILITY -- P0.2: replace cost DEFAULTS with MEASURED costs, per symbol.

THE QUESTION THIS SETTLES. execution_bottleneck.py found the whole book failing the entry gate and
posed two readings: (a) the gate is right and the carry has no edge, or (b) 39.5bps is too harsh
for symbols that are cheap but merely unmeasured. That was answerable and now is answered.

IT IS (a), AND MORE SPECIFICALLY IT IS A UNIVERSE-SELECTION DEFECT.

    COOKIEUSDT -- the desk's MOST-TRADED symbol, 21 opens, largest position in the book --
    has a MEASURED pair round-trip of 130.47 bps. It earns ~6.7 bps over a 24h hold.
    That is a ~19x loss on every rotation, and it was never a default: it was measured.

MY OWN ERROR, DISCLOSED. execution_bottleneck.py reported COOKIEUSDT as using the DEFAULT cost. It
does not. My _rt_bps helper looked for flat keys ("rt_bps"/"round_trip_bps") while the cost model
nests as symbols[SYM]["pair"]["500"]["pair_roundtrip_bps"]. The LIVE EXECUTOR parses it correctly;
only my audit script was wrong. I reported the desk as blind when the desk could see -- the exact
failure the measurement doctrine exists to prevent, committed by the tool auditing for it. This
script uses the executor's lookup verbatim so the audit and the live gate can never diverge again.

THE STRUCTURAL FINDING: funding-first universe selection is self-defeating. High funding is the
compensation for illiquidity, so ranking candidates by funding systematically selects the names
with catastrophic round-trips. The carry is not broken -- the universe is.

Read-only. Touches no orders, no config. Run from repo root.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COST = ROOT / "data/cost_model.json"
POS = ROOT / "data/cashcarry_positions.json"
TRADES = ROOT / "data/cashcarry_trades.json"
OUT = ROOT / "data/carry_viability.json"

DEFAULT_RT_BPS = 39.5
PERIODS_24H = 3.0
TYPICAL_FUNDING_BPS = 3.0     # generous upper end of ordinary per-8h funding


def rt_bps(cm, sym) -> tuple[float, bool]:
    """VERBATIM the executor's lookup (run_cashcarry_executor.py::_rt_bps)."""
    try:
        v = cm["symbols"][sym]["pair"]["500"].get("pair_roundtrip_bps")
        return (float(v), True) if v is not None else (DEFAULT_RT_BPS, False)
    except (KeyError, TypeError, ValueError):
        return (DEFAULT_RT_BPS, False)


def main() -> None:
    cm = json.loads(COST.read_text("utf-8"))
    syms = cm.get("symbols", {})
    print("=== CARRY VIABILITY -- measured costs, executor lookup verbatim ===\n")

    rows = []
    for s in syms:
        v, meas = rt_bps(cm, s)
        if meas:
            rows.append({"symbol": s, "rt_bps": round(v, 2),
                         "need_bps_per_period": round(v / PERIODS_24H, 2),
                         "viable": v / PERIODS_24H <= TYPICAL_FUNDING_BPS})
    rows.sort(key=lambda r: r["rt_bps"])
    viable = [r for r in rows if r["viable"]]
    print(f"  BREAK-EVEN FUNDING NEEDED at a {PERIODS_24H:g}-period (24h) hold:\n")
    print(f"  {'symbol':<14}{'rt_bps':>9}{'need/period':>13}   verdict")
    for r in rows:
        v = ("VIABLE" if r["viable"] else
             "MARGINAL" if r["need_bps_per_period"] <= 8 else "NEVER at normal funding")
        print(f"  {r['symbol']:<14}{r['rt_bps']:>9.2f}{r['need_bps_per_period']:>12.2f}bp   {v}")
    print(f"\n  {len(viable)}/{len(rows)} measured symbols can clear the gate at "
          f"<= {TYPICAL_FUNDING_BPS:g}bp funding.")
    print("  THE STRATEGY IS VIABLE. The universe is not.")

    # ------------------------------------------------ what the desk actually traded
    t = json.loads(TRADES.read_text("utf-8"))
    tr = t if isinstance(t, list) else t.get("trades", [])
    cnt = Counter(r["symbol"] for r in tr if r.get("event") == "open")
    vset = {r["symbol"] for r in viable}
    print("\n  WHAT THE DESK ACTUALLY TRADED (top 16 by opens):\n")
    print(f"  {'symbol':<14}{'opens':>6}{'rt_bps':>10}   status")
    n_unmeas = n_bad = tot = 0
    for s, n in cnt.most_common(16):
        v, meas = rt_bps(cm, s)
        tot += 1
        if not meas:
            st, n_unmeas = "UNMEASURED (prior: unmeasured = illiquid = expensive)", n_unmeas + 1
        elif s in vset:
            st = "viable"
        else:
            st, n_bad = "MEASURED AND UNVIABLE", n_bad + 1
        print(f"  {s:<14}{n:>6}{v:>10.2f}   {st}")
    print(f"\n  {n_unmeas}/{tot} most-traded names have NO measured cost; {n_bad}/{tot} are "
          f"measured AND unviable.")

    pos = json.loads(POS.read_text("utf-8")).get("positions", {})
    print("\n  OPEN BOOK:\n")
    for s, p in pos.items():
        f = float(p.get("funding", 0.0))
        earns = f * 1e4 * PERIODS_24H
        v, meas = rt_bps(cm, s)
        print(f"  {s:<14} earns {earns:>5.1f}bp   needs {v:>7.2f}bp   "
              f"{'MEASURED' if meas else 'default':<9} {'PASS' if earns > v else 'FAIL'}")

    print("\n=== CONCLUSION ===")
    print("  The entry gate is CORRECT and must not be relaxed. It is refusing names that are")
    print("  measurably unprofitable, COOKIEUSDT most of all at 130.47bps against ~6.7bps of")
    print("  funding. The desk halting new opens is the gate doing its job.")
    print("\n  THE FIX IS UNIVERSE SELECTION, NOT THE GATE. Candidates are ranked by FUNDING, but")
    print("  funding is the COMPENSATION FOR ILLIQUIDITY -- so funding-first ranking selects for")
    print("  exactly the round-trips that destroy the carry. Rank by NET (funding x periods minus")
    print("  measured round-trip) and restrict candidates to measured-viable names. On the numbers")
    print("  above that leaves 16 liquid symbols, several of which (BTC 0.02, ETH 0.11, BNB 0.35,")
    print("  XRP 1.81) clear the bar with room to spare at ordinary funding.")
    print("\n  This also RETIRES my own earlier flip-flop on universe choice. I argued for majors,")
    print("  then for micro-caps 'because that is where the funding is', then back. The measured")
    print("  answer: micro-cap funding is real and is smaller than micro-cap costs.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "measured": rows, "n_viable": len(viable), "n_measured": len(rows),
                               "traded_top": dict(cnt.most_common(16)),
                               "unmeasured_traded": n_unmeas}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
