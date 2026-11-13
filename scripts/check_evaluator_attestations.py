#!/usr/bin/env python3
"""EVALUATOR ATTESTATIONS (R3) -- a hash written in the release authority's name must be the one
the authority signed.

`ops/release/authority/evaluator_attest.py verify`, as a portable law fence: every attestation
IMMUTABLE_MANIFEST.json carries must verify against the pinned authority key, and every file the
manifest says the authority re-signed must hold exactly the attested new hash. A manifest with no
attestations is clean (the owner's own `--sign` path is untouched). Exit 1 on any breach.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops" / "release" / "authority" / "evaluator_attest.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("evaluator_attest", MODULE)
    if spec is None or spec.loader is None:
        print(f"evaluator attestations: {MODULE} is missing -- FAILED, never skipped")
        return 1
    mod = importlib.util.module_from_spec(spec)
    sys.modules["evaluator_attest"] = mod
    spec.loader.exec_module(mod)
    return int(mod.main(["verify"]))


if __name__ == "__main__":
    sys.exit(main())
