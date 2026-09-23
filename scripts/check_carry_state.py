#!/usr/bin/env python3
"""CARRY-STATE FENCE (L1.5 / L1.28a / L1.59) -- is the financing leg PRICED on the live book?

`desks/mt5/mt5desk/engine.py` contains zero references to swap, so every backtest, gate,
certificate and forward clock on this desk charges overnight financing at 0.00. That was an
honest UNMEASURED until 2026-08-26, when the broker swap panel began accruing; since then it has
been an uncharged cost with the rate sitting on disk. `desks/mt5/research/carry_state.py`
resolves the rate. This fence asks the only question that matters afterwards: **is any position
being carried overnight whose financing nothing has charged, and has any of it repriced under a
clock that is already running?**

STATUSES -- and the reason each is its own value rather than folded into a neighbour:

  OK                (exit 0) -- every live sleeve's symbol has a resolved financing leg, and the
                                leg is immaterial or already accounted for.
  CARRY-UNCHARGED   (exit 2) -- a live sleeve holds a symbol with a MATERIAL financing leg that
                                the engine charges at zero. The finding, not an error.
  CARRY-FLIP        (exit 2) -- a live sleeve's symbol changed the SIGN of a financed side since
                                its forward clock started. The clock is measuring a strategy
                                priced on a book the broker no longer runs. HIBERNATE, never
                                graveyard: a cost change is not an alpha death, and retiring a
                                sleeve for one is the plumber fixing the water (L1.28b).
  UNMEASURED        (exit 2) -- the artifact holds no measured side, or a live sleeve's symbol
                                has no resolvable rate. Never OK: absence is not a clean verdict
                                (L1.28a / WS-005).
  STATE-MISSING     (exit 2) -- no carry-state artifact. Run the producer.
  STALE             (exit 2) -- the state is older than MAX_AGE_H. 81 of 248 symbols repriced in
                                a three-day window, so a stale carry state is a wrong one.
  NO-LIVE-SLEEVES   (exit 2) -- nothing to check. Explicitly NOT OK: a fence that examined an
                                empty population has produced a vacuous pass (L1.57), and this
                                one is guarding a money path.

THE DIRECTION PROBLEM, STATED RATHER THAN ASSUMED AWAY. `sleeve_registry.json` records
`direction: None` on all 17 live sleeves, so this fence cannot know which side each one holds.
It therefore reports the WORST side and the BEST side and judges on the worst. Picking the
convenient side would be the false-null direction, and picking neither would report a clean
verdict about an unknown (L1.28a). The registry gap is the real repair and is named in the
report so it cannot be mistaken for a property of the market.

The thresholds are CONSTANTS and this fence does not re-baseline them. A fence that re-measures
its own threshold accepts every regression as the new normal, which is a gate welded open.

    python scripts/check_carry_state.py [--json] [--quiet]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_DESK = _ROOT / "desks" / "mt5"
_STATE = _DESK / "data" / "carry_state.json"
_SLEEVES = _DESK / "data" / "sleeve_registry.json"
_OUT = _ROOT / "data" / "carry_state_report.json"

_PASSING = frozenset({"OK"})

#: The panel is hourly and 81 of 248 symbols moved in three days. Two days of tolerance is three
#: missed daily runs, not a hiccup.
MAX_AGE_H = 48.0

#: A financing leg worth at least this share of one spread crossing PER NIGHT is material enough
#: that charging it at zero can change a verdict. At 0.20 a five-night hold silently omits a full
#: extra round trip -- the same magnitude of error as the cost defects this desk has already paid
#: for, in the same direction.
MATERIAL_RATIO = 0.20


def _age_h(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        t = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (datetime.now(UTC) - t).total_seconds() / 3600.0


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def sleeve_symbol(name: str, entry: dict[str, Any]) -> str | None:
    """The symbol a sleeve trades. The registry field first; the name prefix only as a fallback.

    The fallback is a convention, not a fact, so it is reported as `symbol_source` rather than
    silently blended with a recorded value -- a derived key that reads identically to a stored one
    is how a wrong join survives review.
    """
    sym = entry.get("symbol")
    if sym:
        return str(sym)
    head = name.split(".")[0].split("#")[0]
    return head or None


def scan(state: dict[str, Any], sleeves: dict[str, Any]) -> dict[str, Any]:
    rows = (sleeves.get("sleeves") or sleeves) if isinstance(sleeves, dict) else {}
    live = {k: v for k, v in rows.items()
            if isinstance(v, dict) and v.get("status") == "LIVE"}
    symbols = state.get("symbols") or {}

    uncharged: list[dict[str, Any]] = []
    flipped: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    checked = 0

    for name, entry in sorted(live.items()):
        sym = sleeve_symbol(name, entry)
        src = "registry" if entry.get("symbol") else "name-prefix"
        cell = symbols.get(sym) if sym else None
        if not cell:
            unresolved.append({"sleeve": name, "symbol": sym, "symbol_source": src,
                               "why": "no carry-state row for this symbol"})
            continue
        legs = [cell["long"], cell["short"]]
        priced = [x for x in legs if x.get("swap_money_per_lot_night") is not None]
        if not priced:
            unresolved.append({"sleeve": name, "symbol": sym, "symbol_source": src,
                               "why": legs[0].get("unit") or "financing rate UNMEASURED"})
            continue
        checked += 1

        worst = min(priced, key=lambda x: x["swap_money_per_lot_night"])
        best = max(priced, key=lambda x: x["swap_money_per_lot_night"])
        ratio = worst.get("carry_ratio_vs_spread")
        if ratio is not None and ratio <= -MATERIAL_RATIO:
            uncharged.append({
                "sleeve": name, "symbol": sym, "symbol_source": src,
                "direction_recorded": entry.get("direction"),
                "worst_side": worst["side"],
                "worst_money_per_lot_night": worst["swap_money_per_lot_night"],
                "worst_ratio_vs_spread": ratio,
                "best_side": best["side"],
                "best_money_per_lot_night": best["swap_money_per_lot_night"],
                "charged_by_engine": 0.0,
                "triple_swap_weekday": cell.get("triple_swap_weekday"),
            })
        fwd = entry.get("forward_start")
        for leg in priced:
            if leg.get("sign_flipped") and (not fwd or str(leg.get("since") or "") >= str(fwd)):
                flipped.append({
                    "sleeve": name, "symbol": sym, "side": leg["side"],
                    "forward_start": fwd, "since": leg.get("since"),
                    "prev_state": leg.get("prev_state"), "state": leg["state"],
                    "money_per_lot_night": leg["swap_money_per_lot_night"],
                })

    return {"live_sleeves": len(live), "checked": checked, "uncharged": uncharged,
            "flipped": flipped, "unresolved": unresolved}


def build_report() -> dict[str, Any]:
    rep: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "state_path": str(_STATE.relative_to(_ROOT)),
        "material_ratio": MATERIAL_RATIO,
        "max_age_h": MAX_AGE_H,
    }
    state = _load(_STATE)
    if not state:
        rep["status"] = "STATE-MISSING"
        rep["why"] = ("no carry-state artifact -- run "
                      "desks/mt5/research/carry_state.py. The engine charges swap at zero and "
                      "nothing here can say whether that is right.")
        return rep

    age = _age_h(state.get("generated_at"))
    rep["age_h"] = None if age is None else round(age, 2)
    rep["n_symbols"] = state.get("n_symbols", 0)
    rep["n_measured_sides"] = state.get("n_measured_sides", 0)
    rep["n_unmeasured_sides"] = state.get("n_unmeasured_sides", 0)
    rep["n_paid_sides"] = state.get("n_paid_sides", 0)
    rep["n_adverse_sides"] = state.get("n_adverse_sides", 0)
    rep["n_changed_symbols"] = state.get("n_changed_symbols", 0)

    if not state.get("n_measured_sides"):
        rep["status"] = "UNMEASURED"
        rep["why"] = "the carry state resolved no financing rate at all"
        rep["scanned"] = 0
        return rep
    if age is None or age > MAX_AGE_H:
        rep["status"] = "STALE"
        rep["why"] = (f"carry state is {rep['age_h']}h old (limit {MAX_AGE_H}h); "
                      f"{rep['n_changed_symbols']} symbols repriced inside the panel's own window")
        rep["scanned"] = state.get("n_measured_sides", 0)
        return rep

    sleeves = _load(_SLEEVES)
    if not sleeves:
        rep["status"] = "UNMEASURED"
        rep["why"] = "no sleeve registry: cannot say what is being carried overnight"
        rep["scanned"] = 0
        return rep

    found = scan(state, sleeves)
    rep.update(found)
    rep["scanned"] = found["checked"]
    if not found["live_sleeves"]:
        rep["status"] = "NO-LIVE-SLEEVES"
        rep["why"] = "no LIVE sleeve in the registry -- a verdict over an empty population (L1.57)"
    elif found["flipped"]:
        rep["status"] = "CARRY-FLIP"
    elif found["uncharged"]:
        rep["status"] = "CARRY-UNCHARGED"
    elif found["unresolved"]:
        rep["status"] = "UNMEASURED"
        rep["why"] = f"{len(found['unresolved'])} live sleeve(s) have no resolvable financing rate"
    else:
        rep["status"] = "OK"
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=_OUT)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    _law_guard()

    rep = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1, sort_keys=True))
    elif not args.quiet:
        print(f"carry-state fence: {rep['status']}  "
              f"symbols={rep.get('n_symbols', 0)} "
              f"measured_sides={rep.get('n_measured_sides', 0)} "
              f"unmeasured_sides={rep.get('n_unmeasured_sides', 0)} "
              f"live_sleeves={rep.get('live_sleeves', 0)}")
        if rep.get("why"):
            print(f"  {rep['why']}")
        for f in rep.get("uncharged", []):
            print(f"  UNCHARGED {f['sleeve']}: {f['symbol']} {f['worst_side']} "
                  f"{f['worst_money_per_lot_night']:+.3f}/lot/night "
                  f"({f['worst_ratio_vs_spread']:+.2f} spread crossings), engine charges 0.00; "
                  f"other side {f['best_side']} {f['best_money_per_lot_night']:+.3f}")
        for f in rep.get("flipped", []):
            print(f"  FLIP {f['sleeve']}: {f['symbol']} {f['side']} changed sign at {f['since']} "
                  f"(clock started {f['forward_start']}) -> {f['money_per_lot_night']:+.3f}")
        for u in rep.get("unresolved", []):
            print(f"  UNRESOLVED {u['sleeve']}: {u['why']}")
    return fence_exit(rep["status"], _PASSING, scanned=rep.get("scanned"),
                      of="live sleeves with a resolved financing leg", fence="check_carry_state")


if __name__ == "__main__":
    sys.exit(main())
