#!/usr/bin/env python3
"""Write or verify the canonical live release. See `libs.ops.release`.

    python scripts/release_manifest.py            # write data/RELEASE.json for this tree
    python scripts/release_manifest.py --verify   # exit 1 if the tree drifted from the release
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.ops import release  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.verify:
        v = release.verify()
        print(json.dumps(v, indent=1) if a.json else
              f"release {v.get('release_id')}: {'OK' if v['ok'] else 'DRIFT'} -- {v['why']}")
        for k, (was, now) in (v.get("diffs") or {}).items():
            print(f"  {k}: {was} -> {now}")
        return 0 if v["ok"] else 1
    d = release.build(write=True)
    print(json.dumps(d, indent=1) if a.json else
          f"release {d['release_id']} written: sha={d['live_sha'][:12]} "
          f"money_path={d['money_path_hash']} allocator={d['allocator_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
