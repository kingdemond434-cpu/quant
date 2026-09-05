"""An immutable, hash-chained record of exactly what is armed, written every pass.

The desk's live behaviour is the product of a dozen files that each change on their own clock --
the canon, the allocator's book, the cost fields, the gateway state, the state vector, the code.
When a fill looks wrong a week later, "what was the desk actually running at that moment" has no
single answer anywhere. This gives it one: a manifest per pass, each carrying the hash of the
previous, so the chain cannot be edited after the fact without the break being visible.

Hashes, not contents, of the things that decide money:

    canon            which cells are certified
    allocator_proof  whether the optimiser had sizing authority
    gateway_state    what is actually at the broker
    cost_fields      what every gate priced against
    state_vector     the world the pass saw (by id)
    admission        which dimensions may condition
    code             git HEAD

`verify()` walks the chain and reports the first link that does not hash to its successor's
`prev`. A desk that cannot prove what it was running cannot attribute anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
CHAIN = BASE / "data" / "LIVE_MANIFEST.jsonl"

TRACKED = {
    "canon": BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json",
    "allocator_proof": BASE / "reports" / "ALLOCATOR_PROOF.json",
    "gateway_state": BASE / "data" / "gateway_state.json",
    "cost_fields": BASE / "data" / "universe" / "universe.json",
    "state_vector": BASE / "data" / "state_vector.json",
    "admission": BASE / "reports" / "STATE_ADMISSION.json",
    "sleeve_registry": BASE / "data" / "sleeve_registry.json",
}


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _last_forecast() -> dict:
    try:
        lines = (BASE / "data" / "pf_forecast_log.jsonl").read_text("utf-8").splitlines()
        row = json.loads(lines[-1])
        return {"t": row.get("t"), "total_heat": row.get("total_heat"),
                "book_sha": hashlib.sha256(json.dumps(row.get("book"), sort_keys=True,
                                                      default=str).encode()).hexdigest()[:16]}
    except (OSError, ValueError, IndexError):
        return {}


def _armed() -> dict:
    try:
        st = json.loads(TRACKED["gateway_state"].read_text("utf-8"))
        return {"armed": bool(st.get("armed")), "lot": st.get("lot"),
                "n_brackets": len(st.get("brackets") or {}), "equity": st.get("equity")}
    except (OSError, ValueError):
        return {}


def _state_vector_id() -> str | None:
    try:
        return json.loads(TRACKED["state_vector"].read_text("utf-8")).get("id")
    except (OSError, ValueError):
        return None


def _prev_hash() -> str:
    try:
        lines = [ln for ln in CHAIN.read_text("utf-8").splitlines() if ln.strip()]
        return json.loads(lines[-1])["hash"] if lines else "genesis"
    except (OSError, ValueError, KeyError, IndexError):
        return "genesis"


def _hash_of(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def write() -> dict:
    entry = {"at": datetime.now(tz=UTC).isoformat(), "prev": _prev_hash(), "code": _git_head(),
             "files": {k: _sha(p) for k, p in TRACKED.items()},
             "state_vector_id": _state_vector_id(), "armed": _armed(),
             "forecast": _last_forecast()}
    entry["hash"] = _hash_of(entry)
    CHAIN.parent.mkdir(parents=True, exist_ok=True)
    with CHAIN.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")
    return entry


def verify() -> dict:
    try:
        lines = [ln for ln in CHAIN.read_text("utf-8").splitlines() if ln.strip()]
    except OSError:
        return {"ok": True, "entries": 0, "note": "no manifest yet"}
    prev = "genesis"
    for i, ln in enumerate(lines):
        try:
            e = json.loads(ln)
        except ValueError:
            return {"ok": False, "entries": len(lines), "broken_at": i, "why": "unparseable"}
        if e.get("prev") != prev:
            return {"ok": False, "entries": len(lines), "broken_at": i,
                    "why": f"prev {str(e.get('prev'))[:12]} != expected {prev[:12]}"}
        if _hash_of(e) != e.get("hash"):
            return {"ok": False, "entries": len(lines), "broken_at": i,
                    "why": "entry does not hash to its recorded hash -- edited after writing"}
        prev = e["hash"]
    return {"ok": True, "entries": len(lines), "head": prev}


def diff_last_two() -> dict:
    """Which tracked inputs changed between the last two passes -- the answer to 'what moved'."""
    try:
        lines = [json.loads(ln) for ln in CHAIN.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return {}
    if len(lines) < 2:
        return {}
    a, b = lines[-2], lines[-1]
    return {k: {"before": (a["files"].get(k) or "")[:12], "after": (b["files"].get(k) or "")[:12]}
            for k in b.get("files", {}) if a.get("files", {}).get(k) != b["files"].get(k)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        print(json.dumps(verify(), indent=1))
        return 0
    e = write()
    print(f"LIVE MANIFEST {e['hash'][:16]}  prev={e['prev'][:12]}  code={e['code'][:10]}  "
          f"armed={e['armed'].get('armed')}  sv={e['state_vector_id']}")
    changed = diff_last_two()
    if changed:
        print("  changed since last pass: " + ", ".join(sorted(changed)))
    print(json.dumps(verify()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
