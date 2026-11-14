#!/usr/bin/env python3
"""Print (or write) the ROOT digest of a checkout: what zuck pins once on the box, and again
after he himself merges any ROOT change. The authority and the gate act only while LIVE's digest
equals the pin.

    python ops/release/authority/pin_root.py                 # print the digest of this checkout
    python ops/release/authority/pin_root.py --write C:\\opt\\authority\\ROOT_PIN.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write")
    a = ap.parse_args(argv)
    spec = importlib.util.spec_from_file_location("authority_service", HERE / "authority.py")
    assert spec is not None and spec.loader is not None
    auth = importlib.util.module_from_spec(spec)
    sys.modules["authority_service"] = auth
    spec.loader.exec_module(auth)
    digest = auth.tree_digest("HEAD", auth.pol.load_policy())
    print(digest)
    if a.write:
        import subprocess

        commit = subprocess.run(
            ["git", "-C", str(HERE), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        doc = {"digest": digest, "commit": commit, "pinned_at": datetime.now(UTC).isoformat()}
        Path(a.write).write_text(json.dumps(doc), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
