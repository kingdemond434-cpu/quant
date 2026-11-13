#!/usr/bin/env python3
"""NO RAW ACCOUNT NUMBER IN A TRACKED FILE (Governance ruling, 2026-11-13).

    python scripts/check_no_raw_account_ids.py            # the fence: exit 2 on an ARRIVAL
    python scripts/check_no_raw_account_ids.py --json     # the census as JSON

THE DEFECT. This repository is public, and the box publishes its state into it. A broker login
is an account identifier; once it is in a tracked file it is published. `mt5desk.provenance`
replaced the raw login in `live_ledger.jsonl` and `order_intents.jsonl` with a keyed
`account_key` on 2026-10-20, but nothing stopped the next writer from doing it again: the
`broker_info.json` that `refresh_tail.py` writes carried the login 249 times (once at the top and
once per symbol) until 2026-11-13.

WHAT COUNTS. In every tracked `.json` / `.jsonl` file, a key naming an account (`account`,
`login`, `account_login`, `account_number`, `account_id`, `acct`) whose value is a whole number of
at least five digits, or a string of five to twelve digits. Keys are matched at any depth. The
VALUE is never printed, logged or written: the report names the file and a count.
`data/intelligence/**` is out of scope by name: it holds mined PUBLIC records about third-party
accounts (strategy-site listing ids), published by their source, not the desk's own.

A RATCHET THAT ONLY TIGHTENS. Rows written before the fix cannot be rewritten in place:
`live_ledger.jsonl`'s prefix is sealed (`live_ledger_corrections.jsonl` binds its sha256, and
`libs/ops/live_ledger_view.py` raises on any change), and LIVE history is never rewritten. They
are the committed floor, `docs/research/raw_account_id_floor.json`, as a per-file COUNT. A file
over its floor, or a file not on it, FAILS. A file under its floor passes and is reported HEALED,
so the floor can be lowered (never raised) by hand.

WHAT THIS DOES NOT FIX. A value already committed stays in git history, which only a history
rewrite removes. This fence stops new ones.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402

FLOOR = ROOT / "docs" / "research" / "raw_account_id_floor.json"
KEYS = frozenset({"account", "login", "account_login", "account_number", "account_id", "acct"})
_DIGITS = re.compile(r"\d{5,12}")
#: Files larger than this are not parsed (bar stores, tapes); none carries account rows.
MAX_BYTES = 64 * 1024 * 1024
_PASSING = frozenset({"OK"})
#: Out of scope BY NAME: mined PUBLIC records about THIRD-PARTY accounts (a strategy site's
#: listing ids, a leaderboard's trader ids). Those are published by their source; this fence is
#: about the desk's own broker accounts, which only the box's state files carry.
EXCLUDE_PREFIXES = ("data/intelligence/",)


def is_raw_id(value: Any) -> bool:
    """A value that reads as a broker account number. bool is an int in Python and is excluded."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 10_000
    if isinstance(value, float):
        return value.is_integer() and value >= 10_000
    if isinstance(value, str):
        return _DIGITS.fullmatch(value.strip()) is not None
    return False


def count_in(obj: Any) -> int:
    """How many identifier-keyed raw account numbers `obj` holds, at any depth."""
    n = 0
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(k, str) and k.lower() in KEYS and is_raw_id(v):
                    n += 1
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return n


def count_file(path: Path) -> int:
    """Raw account numbers in one JSON or JSON-lines file. Unparseable content counts nothing:
    this fence measures identifiers in records, it is not a JSON validator."""
    try:
        if path.stat().st_size > MAX_BYTES:
            return 0
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    if path.suffix == ".jsonl":
        n = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                n += count_in(json.loads(line))
            except ValueError:
                continue
        return n
    try:
        return count_in(json.loads(text))
    except ValueError:
        return 0


def tracked(root: Path) -> list[str] | None:
    """Tracked JSON files, or None when git cannot list them (a fence that cannot see fails)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", "*.json", "*.jsonl"],
                             capture_output=True, check=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def load_floor(path: Path = FLOOR) -> dict[str, int] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    files = doc.get("files") if isinstance(doc, dict) else None
    if not isinstance(files, dict):
        return None
    out: dict[str, int] = {}
    for k, v in files.items():
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            return None
        out[str(k)] = v
    return out


def census(root: Path = ROOT, floor_path: Path = FLOOR) -> dict[str, Any]:
    files = tracked(root)
    floor = load_floor(floor_path)
    rep: dict[str, Any] = {"floor": str(floor_path.relative_to(root)) if floor_path.is_relative_to(root)
                           else str(floor_path)}
    if files is None:
        rep.update(status="UNMEASURED", why="git ls-files failed", scanned=0)
        return rep
    if floor is None:
        rep.update(status="UNMEASURED", why="the floor file is absent or malformed", scanned=0)
        return rep
    found = {}
    files = [p for p in files if not p.startswith(EXCLUDE_PREFIXES)]
    for rel in files:
        n = count_file(root / rel)
        if n:
            found[rel] = n
    arrivals = {p: {"count": n, "floor": floor.get(p, 0)} for p, n in sorted(found.items())
                if n > floor.get(p, 0)}
    healed = {p: {"count": found.get(p, 0), "floor": f} for p, f in sorted(floor.items())
              if found.get(p, 0) < f}
    rep.update(scanned=len(files), found=found, arrivals=arrivals, healed=healed,
               status="FAIL" if arrivals else "OK")
    if arrivals:
        rep["why"] = ("a tracked file carries a raw account number over its floor -- write the "
                      "keyed account_key (mt5desk.provenance.stamp), never the login")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = census()
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"raw account ids: {rep['status']} over {rep.get('scanned', 0)} tracked JSON file(s)")
        for p, v in (rep.get("arrivals") or {}).items():
            print(f"  ARRIVAL {p}: {v['count']} raw account id(s), floor {v['floor']}")
        for p, v in (rep.get("healed") or {}).items():
            print(f"  healed  {p}: {v['count']} under floor {v['floor']} -- lower the floor")
        if rep.get("why"):
            print(f"  {rep['why']}")
    return fence_exit(rep["status"], _PASSING, scanned=rep.get("scanned", 0),
                      of="tracked *.json/*.jsonl files")


if __name__ == "__main__":
    sys.exit(main())
