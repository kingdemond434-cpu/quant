"""Which API keys this host can see. Prints presence and length, NEVER a value.

    python scripts/check_keys.py            # table
    python scripts/check_keys.py --json     # machine-readable
    python scripts/check_keys.py --names    # just the names, one per line

For each key in libs/ops/env_keys_catalog.json it reports where the value lives: the process
environment, the Windows machine environment (setx /M), the current user's (setx), or another
user's hive. `read_key` reaches all four, so a key present anywhere is usable by the desk.
A missing key is information, not a failure. Exit status is 1 only when the catalog itself is
broken (a duplicate name, a row without its name, group or machine, or a group no reader knows),
because then every count above, and keys_needed's alerts, read a list that is wrong.
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


def _row(name: str, aliases: list[str] | None = None) -> dict[str, Any]:
    where: list[str] = []
    length = 0
    for n in [name, *(aliases or [])]:
        proc = (os.environ.get(n) or "").strip()
        scopes = registry_sources(n)
        tag = "" if n == name else f"({n})"
        where += ([f"process{tag}"] if proc else []) + [s + tag for s, _ in scopes]
        if not length:
            length = len(proc) if proc else (len(scopes[0][1]) if scopes else 0)
    return {"name": name, "present": bool(where), "length": length, "where": where}


#: Every group a reader of the catalog interprets (env_keys.REFUSED_GROUPS, keys_needed's ASK and
#: NEVER_ASK sets). A row outside them is asked for by nothing and refused by nothing.
KNOWN_GROUPS = frozenset({"free_data", "free_llm", "free_infra", "account_free", "official_api",
                          "unavailable", "paid_blocked", "paid_llm", "banned", "legacy",
                          "not_built", "infra"})


def catalog_defects(rows: tuple[dict[str, Any], ...]) -> list[str]:
    """What is wrong with the catalog itself, one line each; empty when it is sound."""
    out, seen = [], set()
    for i, k in enumerate(rows):
        name = str(k.get("name") or "")
        for field in ("name", "group", "machine"):
            if not k.get(field):
                out.append(f"row {i} ({name or '?'}): no {field}")
        if k.get("group") and k["group"] not in KNOWN_GROUPS:
            out.append(f"{name}: unknown group {k['group']!r}")
        if name in seen:
            out.append(f"{name}: listed twice")
        seen.add(name)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--names", action="store_true")
    a = ap.parse_args(argv)
    defects = catalog_defects(catalog())
    rows = []
    for k in catalog():
        r = _row(str(k["name"]), list(k.get("aliases") or []))
        r.update(group=k["group"], cost=k["cost"], machine=k["machine"])
        rows.append(r)
    if a.names:
        print("\n".join(str(r["name"]) for r in rows))
        return 1 if defects else 0
    if a.json:
        print(json.dumps(rows, indent=1))
        return 1 if defects else 0
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
    if any(r["present"] and not any(str(w).startswith("process") for w in r["where"])
           for r in rows):
        print("Some keys are set in the registry but not in this shell: open a NEW PowerShell, "
              "or rely on read_key, which reads the registry directly.")
    for d in defects:
        print(f"CATALOG DEFECT: {d}")
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
