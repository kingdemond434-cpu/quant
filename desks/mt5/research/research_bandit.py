"""Daily research-direction budget: run the bandit, print the shares. See `libs.research.bandit`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import bandit  # noqa: E402


def run(seed: int = 0) -> dict:
    return bandit.run(seed=seed)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    d = run(seed=a.seed)
    print(f"RESEARCH BANDIT  {d['graph_rows']} graph rows, pooled certify rate "
          f"{d['arms'].get('_pooled_rate')}")
    for arm, s in sorted(d["shares"].items(), key=lambda kv: -kv[1]):
        e = d["arms"][arm]
        print(f"  {arm:24s} share={s:5.1%}  born={e['born']:6d} failed={e['failed']:6d} "
              f"certified={e['certified']:3d}  p={e['p_survivor']:.3f} worth={e['worth']:.2f} "
              f"cost={e['cost']:.1f}")
    print(f"written: {bandit.BUDGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
