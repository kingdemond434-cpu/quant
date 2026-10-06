"""Which API keys this host can see. Prints presence and length, NEVER a value.

    python scripts/check_keys.py            # table
    python scripts/check_keys.py --json     # machine-readable
    python scripts/check_keys.py --names    # just the names, one per line

For each key in libs/ops/env_keys_catalog.json it reports where the value lives: the process
environment, the Windows machine environment (setx /M), the current user's (setx), or another
user's hive. `read_key` reaches all four, so a key present anywhere is usable by the desk.
Exit status is 0 always: a missing key is information, not a failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.ops.env_keys import CATALOG_PATH, catalog, registry_sources


def _row(name: str) -> dict[str, Any]:
    proc = (os.environ.get(name) or "").strip()
    scopes = registry_sources(name)
    where = (["process"] if proc else []) + [s for s, _ in scopes]
    length = len(proc) if proc else (len(scopes[0][1]) if scopes else 0)
    return {"name": name, "present": bool(where), "length": length, "where": where}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--names", action="store_true")
    a = ap.parse_args(argv)
    rows = []
    for k in catalog():
        r = _row(str(k["name"]))
        r.update(group=k["group"], cost=k["cost"], machine=k["machine"])
        rows.append(r)
    if a.names:
        print("\n".join(str(r["name"]) for r in rows))
        return 0
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    print(f"{'KEY':26} {'STATUS':8} {'LEN':>4}  {'WHERE':30} {'GROUP':13} MACHINE")
    for r in rows:
        status = "present" if r["present"] else "MISSING"
        where = ",".join(str(w) for w in r["where"]) or "-"
        print(f"{r['name']!s:26} {status:8} {r['length']!s:>4}  {where[:30]:30} "
              f"{r['group']!s:13} {r['machine']}")
    config = json.loads(CATALOG_PATH.read_text(encoding="utf-8")).get("config") or []
    if config:
        print("\nConfig ids (not secrets) some keyed sources also need:")
        for c in config:
            r = _row(str(c["name"]))
            print(f"  {c['name']!s:26} {'present' if r['present'] else 'MISSING':8} for {c['for']}")
    missing = [r for r in rows if not r["present"] and r["group"] in ("free_data", "free_llm",
                                                                       "free_infra")]
    print(f"\n{len(rows) - sum(1 for r in rows if not r['present'])}/{len(rows)} present; "
          f"free keys still missing: {', '.join(str(r['name']) for r in missing) or 'none'}")
    if any(r["present"] and "process" not in r["where"] for r in rows):
        print("Some keys are set in the registry but not in this shell: open a NEW PowerShell, "
              "or rely on read_key, which reads the registry directly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
