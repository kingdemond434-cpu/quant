#!/usr/bin/env python3
"""Regenerate ops/release/protected_paths.txt: the hand-kept head plus every LAWS 5m rail.

The release controller (.github/scripts/audit_gate.py) reads the file as plain text and never
imports repository code, so the rail list is copied here. tests/ops/test_release_controller.py
fails when a rail is missing from the file, so a new rail cannot slip into the AUTO tier.

    python ops/release/gen_protected_paths.py [--check]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ops" / "release" / "protected_paths.txt"
HEAD = ROOT / "ops" / "release" / "protected_head.txt"
MARK = "# ---- generated from libs/research/immutable_rails.py (do not edit below) ----"


def rail_patterns() -> list[str]:
    sys.path.insert(0, str(ROOT))
    from libs.research import immutable_rails as IR

    out = set()
    for r in IR.immutable_rails():
        p = IR.norm(r.path)
        out.add(p.rstrip("/") + "/*" if r.path.endswith("/") else p)
    return sorted(out)


def render() -> str:
    head = HEAD.read_text(encoding="utf-8").rstrip("\n")
    return "\n".join([head, "", MARK, *rail_patterns()]) + "\n"


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
