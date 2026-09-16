"""Walk the immutable research artifact chain and publish whether every hash and link holds.

libs/research/artifact_chain.py is append-only by construction; `verify()` is the only reader
that touches every line, and a chain nobody verifies is a chain nobody would notice broken.
This leg runs every core hour and writes reports/ARTIFACT_CHAIN.json {ok, n, first_break, ...}.
An empty or absent chain verifies ok with n=0 -- that is a measurement (nothing recorded yet),
never a pass on something.

    python scripts/verify_artifact_chain.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "desks" / "mt5" / "reports" / "ARTIFACT_CHAIN.json"


def build() -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from libs.research import artifact_chain
        v = artifact_chain.verify()
        d = asdict(v) if is_dataclass(v) else dict(v) if isinstance(v, dict) else {"raw": str(v)}
    except Exception as exc:
        return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"artifact_chain unavailable: {type(exc).__name__}: {exc}"}
    d["at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    d["status"] = "OK" if d.get("ok") else "BROKEN"
    d["rule"] = "every record's payload_hash, chain_hash and prev link recomputed; the first break named"
    return d


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"artifact chain: {doc.get('status')} n={doc.get('n')} first_break={doc.get('first_break')}")
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, OUT)
        print(f"-> {OUT}")
    return 0 if doc.get("status") != "BROKEN" else 2


if __name__ == "__main__":
    sys.exit(main())
