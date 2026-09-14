"""Record WHICH COMMIT the gates were green on, so a release can cite it.

WHY THIS EXISTS. `release_identity` sealed a `release_sha` and nothing else. Asked what had been
TESTED against that seal it had no answer -- not "null", but no field at all -- so "the box runs
the sealed code" and "the sealed code passed its gates" were two claims with only the first
measured. A seal without an attestation is provenance for the bytes and none for the judgement.

WHAT IT DOES AND DOES NOT CLAIM. It records the HEAD sha at the moment a gate run finished, which
gates ran, and whether they passed. It does NOT claim the working tree equalled that commit: a
gate run over a dirty tree tested something no commit contains, so `tree_clean` is recorded and a
consumer that needs a hard guarantee must require it. Saying so is the point -- an attestation
that overstates itself is worse than none, because it is believed.

    python scripts/gate_attestation.py --gates fast --result pass
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "gate_attestation.json"


def _git(*args: str) -> str:
    """UTF-8 explicitly: `text=True` alone decodes with the locale and dies in a reader thread."""
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def attest(gates: str, result: str) -> dict[str, object]:
    sha = _git("rev-parse", "HEAD")
    # `--` guards a repo whose HEAD is a path-shaped ref; porcelain is empty exactly when clean.
    dirty = [ln for ln in _git("status", "--porcelain").splitlines() if ln.strip()]
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tested_sha": sha or None,
        "gates": gates,
        "result": result,
        "tree_clean": not dirty,
        "dirty_paths": len(dirty),
        "note": ("tested_sha is HEAD when the run finished. tree_clean false means the run tested "
                 "a tree no commit contains, so the sha names a neighbourhood, not the subject"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gates", default="fast", help="which gate set ran (fast|full)")
    ap.add_argument("--result", default="pass", choices=("pass", "fail"))
    args = ap.parse_args(argv)
    doc = attest(args.gates, args.result)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"gate attestation: {args.gates} {args.result} on "
          f"{str(doc['tested_sha'])[:12]} (tree_clean={doc['tree_clean']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
