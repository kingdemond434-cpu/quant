"""Run the CANONICAL ten gates on H-20260828-005 (fxblue retail-overlap reversal).

L1.58 owed this card its gauntlet verdict on the day it was picked up. This is a DRIVER,
not a second door: it builds cells with `external_gauntlet.build_cell` and judges them with
`external_gauntlet.run_gauntlet`, so the policy, the thresholds and the trial census are the
canonical ones (L1.60). No threshold is applied here in either direction.

THE GRID IS PREREGISTERED HERE AND EVERY CELL IS REPORTED, pass or fail. The card fixes the
hours (15,16 broker stamp) and the extension threshold (1.0 ATR); only the two exit params the
card left open are swept, plus BOTH directions -- the card set `direction: 0` and said in terms
that direction "is the gauntlet's question", so reporting the fade alone would be the producer
answering a question it deferred. 3 symbols x 2 rr x 2 ttl x 2 modes = 24 trials, all counted
and all reported, pass or fail.

M15 arm: UNMEASURED (no M15 parquets on this box), not tested and not failed (L1.28a).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "desks" / "mt5"))
sys.path.insert(0, str(BASE / "desks" / "mt5" / "scripts"))

import external_gauntlet as eg  # noqa: E402

FAMILY = "retail_overlap_reversal"
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
GRID = [{"rr": rr, "ttl_bars": ttl, "mode": m}
        for rr in (1.0, 1.5) for ttl in (2, 4) for m in ("fade", "follow")]
OUT = BASE / "desks" / "mt5" / "reports" / "gauntlet_H-20260828-005.json"


def main() -> int:
    meta_path = BASE / "desks" / "mt5" / "data" / "universe" / "universe.json"
    meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
    meta = meta_raw.get("symbols", meta_raw) if isinstance(meta_raw, dict) else {}

    cells = []
    for sym in SYMBOLS:
        for params in GRID:
            c = eg.build_cell(sym, FAMILY, dict(params), meta)
            if c is None:
                print(f"  BUILD-FAIL {sym} {params}")
                continue
            c["mechanism_status"] = "NAMED"
            c["mechanism_note"] = "H-20260828-005 retail flow concentration / dealer inventory"
            print(f"  built {sym} {params}: {len(c['sigs'])} signals")
            cells.append(c)
    if not cells:
        print("NO CELLS BUILT")
        return 1
    res = eg.run_gauntlet(cells, "H-20260828-005", meta)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "hypothesis": "H-20260828-005",
        "generated_at": datetime.now(UTC).isoformat(),
        "family": FAMILY,
        "symbols": SYMBOLS,
        "grid": GRID,
        "trials_declared": len(SYMBOLS) * len(GRID),
        "m15_arm": "UNMEASURED -- no M15 parquets on this box; H1 arm only",
        "result": res,
    }, indent=1, default=str), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
