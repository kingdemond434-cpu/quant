"""THE ACCOUNT IS FUSION ZERO, SO THE COST IS COMMISSION PER LOT AND A RESIDUAL SPREAD.

WHAT THE ACCOUNT ACTUALLY CHARGES, and the desk has this written down in two places already:

    `mt5desk/engine.py:39`  "Fusion Zero's published contract is USD 2.25 per lot per side
                             ($4.50 round turn)."
    `mt5desk/universe.py`   "commission-only: symbols genuinely quote a 0.0 median spread and
                             are charged through commission instead ... measured, EURUSD costs
                             17.21 per round trip, not nothing."

Commission is CONTRACTUAL: it is a known constant, identical for every symbol, and it does not
widen. `Costs.stressed` already refuses to stress it, correctly -- "stressing it models nothing
that happens". Spread on a raw account is the small, variable residual on top.

THAT ORDERING IS THE WHOLE POINT, AND IT IS MEASURED. Over the 161 symbols whose stored spread
can be verified against their own bars, COMMISSION IS A MEDIAN 96% OF THE RAW-REGIME ROUND TRIP.
The spread argument this desk keeps having is an argument about the remaining four percent, while
the term that carries the cost is a published constant nobody was disputing.

AND THE SPREADS ARE WRONG IN BOTH DIRECTIONS. Checked against each symbol's own H1 bar median --
itself the WIDE reading, since a bar stamp samples the widest instant of its hour, so a charge
above it cannot be a spread -- 251 symbols split 161 ok, 22 wide, and twelve broken:

    OVER-CHARGED, outside even the 3x their own stress_costs gate tested
        BlockInc  500.0 pts vs bars   1.0  = 500x        USDRUB  21060 vs 605 = 34.8x
        GBPCHF    165.0 pts vs bars   7.0  = 23.6x       NZDJPY    147 vs  15 =  9.8x
        BeyondMeat  8.0 pts vs bars   1.0  =   8x        Walgreens   5 vs   1 =    5x

    UNDER-CHARGED, billed ZERO against positive bars every hour
        Broadcom, EURCAD, GBPCAD, HKDJPY, USDHKD, Walmart

GBPCHF at 165 points is 16.5 pips; with the 3x stress gate on top a cell there is judged at
roughly fifty pips of round-trip cost. NOTHING ON THOSE SIX CAN EVER PASS THE GAUNTLET. That is
not conservatism, it is a Rule 2 breach -- a real opportunity suppressed by a broken number --
and it is the mirror of the six billed nothing at all.

THE THREE REGIMES ARE THE DESK'S OWN AND ARE MIRRORED, NOT INVENTED.
`research/run_edges_macro_fusion_sweep.COST_REGIMES` defines them and reasons about them:

    WIDE  2.0   median spread x2 + commission -- what the earlier sweeps used
    RAW   0.2   20% of median + commission    -- "a raw account still has SOME spread;
                                                 'zero spread' is a marketing description
                                                 of a residual"
    ZERO  0.0   commission only               -- "the optimistic bound -- kept because it is a
                                                 BOUND, not because any account fills at it"

RAW IS THE DEFAULT AND ZERO IS NOT, and that is a deliberate refusal. Charging zero spread makes
every backtest better in the exact direction the desk's guards exist to prevent -- and the module
that defined these regimes says in its own words that no account fills at ZERO. The bound is
computed and published beside the realistic number, because "if a family only works at ZERO it
does not work, and seeing that explicitly is more useful than arguing about which single number
to use". Nothing here picks the regime for a live decision; it publishes all three.

NOTHING HERE REWRITES THE REGISTRY. `median_spread_pts` is a money-path field: rewriting it
re-judges every certificate priced against it and rebases the forward clocks. This measures,
names the direction of every change, and stops -- `scripts/repair_universe_spreads.py --apply`
remains the one deliberate act, and it is a person's.

AND NOTHING HERE REIMPLEMENTS THE ARITHMETIC. `engine.Costs.from_symbol` already converts points
to price units and commission from account currency through `quote_per_account` -- the unit trap
that once undercharged the JPY crosses by 184x. This chooses the regime and audits the inputs;
the sums stay where they are already tested.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: Fusion Zero's published contract, USD per lot PER SIDE. Cited at `mt5desk/engine.py:39` and
#: used as `validate_fusion.FUSION_COMMISSION`. Contractual: it does not widen under stress.
COMMISSION_PER_LOT_PER_SIDE = 2.25

#: Mirrors `research/run_edges_macro_fusion_sweep.COST_REGIMES` exactly. A test pins the equality
#: so the two cannot drift into two different accounts.
COST_REGIMES: dict[str, float] = {"WIDE": 2.0, "RAW": 0.2, "ZERO": 0.0}

#: The realistic regime. NOT `ZERO` -- see the header.
DEFAULT_REGIME = "RAW"

#: `Costs.from_symbol` ends on `max(spread * mult, 0.05)`, so THE `ZERO` REGIME IS NOT A
#: ZERO-SPREAD BOUND: at mult=0.0 the spread term floors here rather than vanishing. On a raw
#: account that is arguably the right behaviour -- a residual is exactly what a raw account has --
#: but it is not what the name says, and a reader computing "the optimistic bound" would otherwise
#: believe it tighter than it is. Mirrored so the published numbers can be decomposed; a test
#: fails if the engine's floor ever moves away from it.
ENGINE_SPREAD_FLOOR = 0.05

#: TWO BARS, AND THE HIGHER ONE IS THE DESK'S OWN. A bar stamp samples the widest instant of its
#: hour, so the bar median is already the WIDE reading of a symbol's spread and a charge above it
#: is a disagreement. But two estimators of the same quantity disagreeing by 1.3x is ordinary, and
#: a list where twenty of twenty-eight rows are ordinary is a list nobody reads -- the same lesson
#: `check_time_joins` learned at 75 rows.
#:
#: So the line that matters is the STRESS multiple the gauntlet already runs at: a charge more
#: than 3x its own bars is outside everything `stress_costs` ever tested, which makes it a defect
#: rather than a disagreement. Between the two the row is reported as WIDE and counted, not
#: flagged. Neither number is invented here: 3.0 is the gauntlet's, 1.2 is only a reporting floor.
IMPLAUSIBLE_ABOVE_BAR = 3.0
NOTEWORTHY_ABOVE_BAR = 1.2

UNIVERSE_REL = "desks/mt5/data/universe/universe.json"
SURFACE_REL = "desks/mt5/data/cost_surface.json"
OUT_REL = "desks/mt5/reports/FUSION_COST.json"

OK = "OK"
WIDE = "CHARGED_WIDE_OF_ITS_OWN_BARS"
IMPOSSIBLE = "CHARGED_ABOVE_ITS_OWN_BARS"
ZERO_BUT_BARS = "CHARGED_ZERO_AGAINST_POSITIVE_BARS"
UNVERIFIABLE = "NO_BARS_TO_CHECK_AGAINST"


@dataclass(frozen=True)
class Reading:
    """One symbol: what it is charged, what its own bars say, and the three regime costs."""

    symbol: str
    charged_pts: float | None
    bar_median_pts: float | None
    source: str
    verdict: str
    why: str
    round_trip: dict[str, float]

    @property
    def ratio(self) -> float | None:
        if self.charged_pts is None or not self.bar_median_pts:
            return None
        return round(self.charged_pts / self.bar_median_pts, 3)

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "charged_pts": self.charged_pts,
                "bar_median_pts": self.bar_median_pts, "charged_over_bars": self.ratio,
                "provenance": self.source, "verdict": self.verdict, "why": self.why,
                "round_trip_per_lot": self.round_trip,
                "commission_share": (
                    round(self.round_trip.get("ZERO", 0.0) / self.round_trip["RAW"], 4)
                    if self.round_trip.get("RAW") else None)}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def registry(root: Path) -> dict[str, dict[str, Any]]:
    doc = _read(root / Path(*UNIVERSE_REL.split("/")))
    syms = doc.get("symbols") or doc
    if isinstance(syms, list):
        return {str(m.get("symbol")): m for m in syms if isinstance(m, dict)}
    return {k: v for k, v in syms.items() if isinstance(v, dict)}


def bar_median_pts(surface: dict[str, Any], symbol: str) -> float | None:
    """The median of a symbol's MEASURED hourly spreads -- the wide reading, and the ceiling."""
    hours = [c.get("p50") for c in ((surface.get("symbols") or {}).get(symbol) or {})
             .get("hours", {}).values()
             if isinstance(c, dict) and c.get("status") == "MEASURED" and c.get("p50") is not None]
    if not hours:
        return None
    vals = sorted(float(v) for v in hours)
    return vals[len(vals) // 2]


def round_trip_per_lot(meta: dict[str, Any]) -> dict[str, float]:
    """Round-trip cost per lot under each regime, through the engine's own arithmetic.

    NOT REIMPLEMENTED HERE. `Costs.from_symbol` handles the two unit traps this desk has already
    paid for -- points to price units, and commission from account currency via
    `quote_per_account`, whose absence once undercharged the JPY crosses by 184x.
    """
    from mt5desk.engine import Costs

    out: dict[str, float] = {}
    for name, mult in COST_REGIMES.items():
        c = Costs.from_symbol(meta, mult=mult,
                              commission_per_lot=COMMISSION_PER_LOT_PER_SIDE)
        out[name] = round(float(c.per_oz_roundtrip()), 6)
    return out


def read_symbol(symbol: str, meta: dict[str, Any], surface: dict[str, Any]) -> Reading:
    raw = meta.get("median_spread_pts")
    charged = float(raw) if isinstance(raw, (int, float)) else None
    bars = bar_median_pts(surface, symbol)
    source = ((meta.get("_provenance") or {}).get("median_spread_pts") or {}).get("source", "")
    rt = round_trip_per_lot(meta)

    if charged is None:
        verdict, why = UNVERIFIABLE, f"{symbol} carries no median_spread_pts"
    elif bars is None:
        verdict, why = UNVERIFIABLE, (
            f"{symbol} has no MEASURED hour in the cost surface, so its charge cannot be checked "
            "against its own bars. Unverifiable is not a pass")
    elif charged == 0.0:
        verdict, why = ZERO_BUT_BARS, (
            f"{symbol} is charged ZERO spread while its own bars median {bars} pts. Fusion Zero "
            "is commission-only on SOME instruments and a genuine 0.0 is real there -- but not on "
            "one whose bars quote a positive spread every hour. Under-charged")
    elif charged > bars * IMPLAUSIBLE_ABOVE_BAR:
        verdict, why = IMPOSSIBLE, (
            f"{symbol} is charged {charged} pts against a bar median of {bars} -- "
            f"{charged / bars:.1f}x. A bar stamp samples the widest instant of its hour, so the "
            "bar median is already the WIDE reading and a charge this far above it cannot be a "
            f"spread. It is outside the {IMPLAUSIBLE_ABOVE_BAR}x the cell's own stress_costs gate "
            "tested, so nothing on this symbol can pass")
    elif charged > bars * NOTEWORTHY_ABOVE_BAR:
        verdict, why = WIDE, (
            f"{symbol} is charged {charged} pts against a bar median of {bars} -- "
            f"{charged / bars:.2f}x. Wide of its own bars but inside the "
            f"{IMPLAUSIBLE_ABOVE_BAR}x its stress gate covers, so this is two estimators "
            "disagreeing and not a defect")
    else:
        verdict, why = OK, (
            f"charged {charged} pts sits under the {bars} pt bar median, which is the wide reading")
    return Reading(symbol, charged, bars, source, verdict, why, rt)


def audit(root: Path | None = None) -> dict[str, Any]:
    """Every symbol, both directions of error named, and what each regime would charge."""
    root = Path(root or _ROOT)
    meta = registry(root)
    surface = _read(root / Path(*SURFACE_REL.split("/")))
    rows = [read_symbol(s, m, surface) for s, m in sorted(meta.items())]

    by = {v: [r for r in rows if r.verdict == v]
          for v in (OK, WIDE, IMPOSSIBLE, ZERO_BUT_BARS, UNVERIFIABLE)}
    # THE SHARE IS TAKEN OVER VERIFIED SYMBOLS ONLY. `Costs.from_symbol` floors the spread term at
    # 0.05, so a symbol whose stored spread is zero or broken reports commission as ~99% of its
    # cost BY CONSTRUCTION -- and 62 of these are exactly that. Pooling them would turn an
    # artifact of the floor into a headline about the account.
    shares = [r.to_dict()["commission_share"] for r in by[OK]
              if r.to_dict()["commission_share"] is not None]
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "account": "Fusion Zero",
        "commission_per_lot_per_side_usd": COMMISSION_PER_LOT_PER_SIDE,
        "regimes": COST_REGIMES,
        "default_regime": DEFAULT_REGIME,
        "n_symbols": len(rows),
        "by_verdict": {k: len(v) for k, v in by.items()},
        "over_charged": [r.to_dict() for r in by[IMPOSSIBLE]],
        "wide_of_bars": [r.to_dict() for r in by[WIDE]],
        "commission_share_measured_on": len(shares),
        "under_charged": [r.to_dict() for r in by[ZERO_BUT_BARS]],
        # THE NUMBER THAT SAYS WHY THE COMMISSION MATTERS MORE THAN THE SPREAD ARGUMENT.
        "median_commission_share_of_raw_cost": (
            round(sorted(shares)[len(shares) // 2], 4) if shares else None),
        "symbols": [r.to_dict() for r in rows],
        "rule": (
            "commission is CONTRACTUAL -- a known constant per lot per side that does not widen, "
            "and on this account it is most of the cost. The spread is a residual, and the desk's "
            "stored spreads are wrong in BOTH directions. RAW is the default and ZERO is not: the "
            "module that defined these regimes says in its own words that ZERO is a bound and no "
            "account fills at it, and defaulting to it would make every backtest better in the "
            "one direction the guards exist to prevent. Nothing here rewrites the registry"),
    }


def render(doc: dict[str, Any]) -> str:
    b = doc["by_verdict"]
    lines = [
        f"FUSION COST  account={doc['account']}  commission "
        f"USD {doc['commission_per_lot_per_side_usd']}/lot/side "
        f"(={doc['commission_per_lot_per_side_usd'] * 2:.2f} round turn)",
        f"  regimes {doc['regimes']}  default={doc['default_regime']}  "
        f"commission is a median {doc['median_commission_share_of_raw_cost']} of RAW cost "
        f"(over the {doc['commission_share_measured_on']} symbols with a VERIFIED spread)",
        f"  {doc['n_symbols']} symbols: {b[OK]} ok, {b[WIDE]} wide, {b[IMPOSSIBLE]} OVER-charged, "
        f"{b[ZERO_BUT_BARS]} UNDER-charged, {b[UNVERIFIABLE]} unverifiable",
    ]
    for r in doc["over_charged"]:
        lines.append(f"  OVER   {r['symbol']:12s} charged {r['charged_pts']:>7} vs bars "
                     f"{r['bar_median_pts']:>7}  x{r['charged_over_bars']}  [{r['provenance']}]")
    for r in doc["under_charged"]:
        lines.append(f"  UNDER  {r['symbol']:12s} charged {r['charged_pts']:>7} vs bars "
                     f"{r['bar_median_pts']:>7}  [{r['provenance'] or 'no provenance'}]")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="what a Fusion Zero account actually charges")
    ap.add_argument("--root", default=str(_ROOT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = audit(root)
    out = root / Path(*OUT_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
