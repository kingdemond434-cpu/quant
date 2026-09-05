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

#: The growth attribution's per-source verdict. `allocator_attribution` names a source DEAD
#: INFORMATION when it has burned trials past the exploration floor and bought no growth in the
#: funded book; that naming only becomes a decision where the budget is set, which is here.
ATTRIBUTION = _DESK / "reports" / "allocator_attribution.json"


def dead_information() -> list[str]:
    """Sources the growth attribution named DEAD INFORMATION.

    A dead SOURCE does not stop the ARM -- an arm is many sources, and killing an arm for one
    exhausted feed would throw away the others with it. It stops being a REASON to fund the arm,
    which is what the share is computed from.
    """
    import json
    try:
        doc = json.loads(ATTRIBUTION.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return sorted(str(s) for s in ((doc.get("information") or {}).get("dead_information") or []))


def run(seed: int = 0) -> dict:
    d = bandit.run(seed=seed)
    d["dead_information"] = dead_information()
    return d


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
