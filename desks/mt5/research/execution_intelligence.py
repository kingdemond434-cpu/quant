"""Daily execution intelligence: refit the fill/slip surface, measure netting. Cycle entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import fill_surface, netting  # noqa: E402


def run() -> dict:
    fs = fill_surface.run(write=True)
    nt = netting.savings_report(write=True)
    return {"fill_surface": fs.get("note"), "fills": fs.get("n_fills"),
            "netting": nt.get("verdict"), "opposing_share": nt.get("opposing_share")}


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"EXECUTION INTELLIGENCE  surface: {d['fill_surface']} ({d['fills']} fills); "
          f"netting: {d['netting']} opposing_share={d['opposing_share']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
