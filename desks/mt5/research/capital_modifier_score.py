"""Score the AI capital modifier's categories against realised returns. See
`libs.portfolio.capital_modifiers.score`; this is the daily-cycle entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio import capital_modifiers  # noqa: E402


def run() -> dict:
    return capital_modifiers.score(write=True)


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"CAPITAL MODIFIERS  {d['ledger_rows']} ledger rows, {d['matched_rows']} matched")
    for cat, v in d["categories"].items():
        print(f"  {cat:13s} n={v.get('n', 0):5d} mean_r={v.get('mean_r')}  {v.get('verdict')}")
    print(f"written: {capital_modifiers.REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
