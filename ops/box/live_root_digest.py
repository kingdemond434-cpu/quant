#!/usr/bin/env python3
"""Print the ROOT digest of one git revision of this checkout (read only; writes nothing).

    python ops/box/live_root_digest.py origin/claude/llm-auto-upgrade-verify-gcjac3

box_selfheal.ps1 reads LIVE's digest with this AT RUN TIME (Auditor ROOT ruling, 11-11 condition
(d)): a pin is never compared against a remembered value. It uses the release authority's own
`tree_digest`, the function pin_root.py and the gate's pin check use, so the three cannot disagree.
Prints nothing and exits 1 when the revision or the policy cannot be read: UNMEASURED, never a digest.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

AUTH = Path(__file__).resolve().parents[2] / "ops" / "release" / "authority" / "authority.py"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: live_root_digest.py <rev>", file=sys.stderr)
        return 2
    try:
        spec = importlib.util.spec_from_file_location("authority_service", AUTH)
        assert spec is not None and spec.loader is not None
        auth = importlib.util.module_from_spec(spec)
        sys.modules["authority_service"] = auth
        spec.loader.exec_module(auth)
        # an unknown revision lists no files, and "every root file absent" still hashes: refuse it
        if not auth._git_bytes("rev-parse", "--verify", "--quiet", argv[0] + "^{commit}"):
            print(f"UNMEASURED: {argv[0]} is not a commit here", file=sys.stderr)
            return 1
        digest = auth.tree_digest(argv[0], auth.pol.load_policy())
    except Exception as exc:  # noqa: BLE001 -- any failure is UNMEASURED, said once
        print(f"UNMEASURED: {type(exc).__name__}", file=sys.stderr)
        return 1
    if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
        return 1
    print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
