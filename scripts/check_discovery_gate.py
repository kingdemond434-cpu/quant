#!/usr/bin/env python3
"""DISCOVERY PROMOTION GATE -- what run_discovery.py's forward evidence buys, computed once.

THE LAST PIECE of the chain fixed 2026-08-12: run_discovery.py (Stage A, backtest gauntlet) ->
run_discovery_forward.py (Stage B, real out-of-sample days per sleeve) -> this gate turns
days_forward + forward_sharpe into a size, the same way check_promotion_gate.py already does for
the discretionary sleeve.

WHY THIS REUSES libs.risk.kelly_shrink INSTEAD OF INVENTING A NEW RUNG TABLE. check_promotion_gate
's ladder (50 trades/14 days -> ..., 1%/5%/15% of book) was fixed by explicit PRINCIPAL decision
(2026-07-31) BEFORE evidence existed -- that is the correct process, and this organ has had no
equivalent principal ruling on trade counts or book fractions for systematic discovery sleeves.
Inventing one here would be exactly the un-reviewed capital-sizing policy this desk's own law
forbids a machine from deciding alone (libs.ops.law_police.NEVER_AUTO_CORRECT names "capital",
"allocation" explicitly). kelly_shrink.shrink_fraction, by contrast, is not a threshold table --
it is a continuous, ALREADY principal-adopted (2026-07-12 external-review upgrade) estimator that
answers a narrower, general question with no sleeve-specific tuning: "given this measured Sharpe
and this many independent days, what fraction of full Kelly does the estimation error justify?"
Applying an already-approved general formula to a new evidence source is not new policy.

WHAT THIS DOES NOT DO. It reports a FRACTION OF FULL KELLY, never a dollar figure or a percentage
of book. Converting that fraction into an actual position needs two things this organ deliberately
does not supply: (1) a measured full-Kelly estimate from the sleeve's own return variance -- not
yet computed anywhere for these candidates, and (2) a PRINCIPAL-SET risk budget for "systematic
discovery" as a category. R0143: no return or size number is asserted as a target here, and none
should be inferred from silence. It does not gate, size or place an order -- ZERO promotion
authority beyond the fraction itself, same standing as check_promotion_gate.py relative to the
actuator that reads it.

UNMEASURED (no forward_sharpe yet, i.e. days_forward < MIN_DAYS) IS NEVER A PASS: it reports
authorized_fraction=0.0 and says why, exactly like check_promotion_gate's UNMEASURED criteria.

    python scripts/check_discovery_gate.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.risk.kelly_shrink import shrink_fraction  # noqa: E402

_FORWARD = "web/discovery_forward.json"
_STATE = "data/discovery_promotion_gate.json"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def evaluate(root: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    fwd = _read(root / _FORWARD)

    if not isinstance(fwd, dict) or fwd.get("status") not in ("OK",):
        return {"generated": now.isoformat(), "status": "UNMEASURED",
                "why": f"{_FORWARD} is absent, unreadable, or not status OK "
                       f"(has: {fwd.get('status') if isinstance(fwd, dict) else fwd!r})",
                "sleeves": {}}

    sleeves: dict[str, dict[str, Any]] = {}
    for name, row in (fwd.get("sleeves") or {}).items():
        days = row.get("days_forward")
        sharpe = row.get("forward_sharpe")
        if not isinstance(row, dict) or days is None or sharpe is None:
            sleeves[name] = {
                "authorized_fraction_of_kelly": 0.0, "state": "UNMEASURED",
                "days_forward": days,
                "why": (row.get("why") if isinstance(row, dict) else None)
                       or f"forward_sharpe not yet published ({days}/{row.get('min_days')}d)",
            }
            continue
        frac = shrink_fraction(float(sharpe), float(days))
        sleeves[name] = {
            "authorized_fraction_of_kelly": frac,
            "state": "SIZED" if frac > 0.0 else "UNPROVEN (Sharpe <= 0 or n_eff < 5)",
            "days_forward": days, "forward_sharpe": sharpe,
            "why": f"shrink_fraction(sharpe={sharpe}, n_days={days}) = {frac}",
        }

    return {
        "generated": now.isoformat(),
        "law": "fraction of full Kelly ONLY -- not a dollar figure, not a percent of book. "
               "Turning this into a position needs a measured full-Kelly estimate (not built) and "
               "a principal-set risk budget for systematic discovery (not set). R0143: no return "
               "or size number is a target here.",
        "status": "OK", "sleeves": sleeves,
    }


def main(argv: list[str] | None = None) -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = evaluate()
    out = Path(_STATE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), "utf-8")

    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"discovery gate: {doc['status']} -- {len(doc.get('sleeves', {}))} sleeve(s)")
        for name, s in doc.get("sleeves", {}).items():
            print(f"  {name:18} {s['state']:32} frac={s.get('authorized_fraction_of_kelly')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
