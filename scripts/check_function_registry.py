#!/usr/bin/env python3
"""FENCE: no essential function may stand on a false rung (ARCH-09).

    python scripts/check_function_registry.py [--json] [--map PATH]

`docs/research/function_registry.json` declares, for each essential function of the desk, its
owner, inputs, outputs, contracts, runtime process, consumers, decision authority, failure
behaviour and verification. `libs/ops/function_registry.py` derives the ladder rung of each
(declared -> implemented -> connected -> running -> behaviour_verified) and publishes
`desks/mt5/reports/FUNCTION_MAP.json` on the hourly leg `function_registry`.

THIS FENCE FAILS ON A FALSE RUNG, in three shapes:

  1. A row ASSERTS a rung (`rung`, `status`, `verified`, ...). Rungs are derived; a typed one is
     the unverifiable claim the ladder exists to replace.
  2. A STATIC rung is FALSE: the registry names an owner, an output, a failure marker, a
     consumer, a clock or a test that the tree contradicts. The registry is then lying about the
     function and must be corrected -- or the function repaired -- before the commit lands.
  3. The PUBLISHED map (when this host has one) claims a static rung TRUE that a re-derivation
     no longer supports: the artifact other readers trust has gone false since it was written.

It also fails when an essential domain (research, forecasting, validation, allocator, controls,
execution, accounting, data, ops) has no function at all.

running and behaviour_verified are runtime facts. On a host that wrote none of the outputs they
read UNMEASURED -- a verdict, not a pass and not a failure (L1.28a, L1.43) -- so this fence means
the same thing in CI and on the box. A COMMIT FENCE (`_LAW_FENCES`). Exit 0 clean, 1 on any false
rung. It caps nothing and gates no capital.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import function_registry as fr  # noqa: E402


def check(root: Path = fr.ROOT, map_path: Path | None = None) -> dict[str, Any]:
    doc = fr.build(root)
    problems = list(doc["problems"])
    published = None
    path = Path(map_path or fr.OUT)
    try:
        published = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        published = None
    if isinstance(published, dict):
        problems += [f"published map: {p}" for p in fr.published_false_rungs(published, doc)]
    return {"ok": not problems, "problems": problems, "by_rung": doc["by_rung"],
            "n_functions": doc["n_functions"],
            "published_map": str(path) if isinstance(published, dict) else None,
            "functions": [{"id": f["id"], "rung": f["rung"]} for f in doc["functions"]]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--map", type=Path, default=None, help="published FUNCTION_MAP.json to judge")
    args = ap.parse_args(argv)
    res = check(map_path=args.map)
    if args.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"function registry: {res['n_functions']} essential functions; by rung "
              f"{res['by_rung']}; published map "
              f"{'judged' if res['published_map'] else 'absent on this host (UNMEASURED)'}")
        for p in res["problems"]:
            print(f"  FALSE RUNG: {p}")
        print("check_function_registry: " + ("OK" if res["ok"] else "FAILED"))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
