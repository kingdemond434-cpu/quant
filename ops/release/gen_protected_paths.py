#!/usr/bin/env python3
"""Regenerate ops/release/protected_paths.txt from the hand-kept head.

The release controller (.github/scripts/audit_gate.py) reads the file as plain text. Until
2026-10-29 every LAWS 5m rail was appended here; zuck then removed the PROTECTED tier ("remove all
protected ... always"), so the rails take the AUTO path and only the head is copied.

    python ops/release/gen_protected_paths.py [--check]
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ops" / "release" / "protected_paths.txt"
HEAD = ROOT / "ops" / "release" / "protected_head.txt"


def render() -> str:
    return HEAD.read_text(encoding="utf-8").rstrip("\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 when the file is stale")
    want = render()
    if ap.parse_args().check:
        have = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if have != want:
            print(
                "ops/release/protected_paths.txt is stale: run ops/release/gen_protected_paths.py"
            )
            return 1
        return 0
    OUT.write_text(want, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
