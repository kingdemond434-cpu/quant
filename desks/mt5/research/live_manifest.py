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
    sleeve_registry  what is frozen, live, retired
    code             git HEAD

and, since 2026-09-05, the deployment attestation around them:

    release          the release identity verdict -- is `code` the SEALED code, or was the
                     gateway refusing new risk on this pass (mt5desk.release_identity)
    data_schema      the FIELD NAMES of the cost universe and the sleeve registry, hashed apart
                     from their contents: a row whose content hash moved because a spread was
                     refreshed is routine, a row whose schema hash moved means a producer changed
                     shape under every consumer
    allocator_certificate  the proof's own digest, whether it passed, and when
    health           the shadow cycle's summary (status, blocked, errors, armed)

`verify()` walks the chain and reports the first link that does not hash to its successor's
`prev`. A desk that cannot prove what it was running cannot attribute anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
CHAIN = BASE / "data" / "LIVE_MANIFEST.jsonl"
HEALTH = BASE / "reports" / "shadow" / "shadow_health.json"

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


def _release() -> dict:
    """The identity verdict, without writing its own file (the gateway and the smoke test own
    data/release_identity.json). A verdict that cannot be produced is recorded as unmeasured:
    the row must still be written, and "unknown" is a fact worth chaining."""
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from mt5desk import release_identity
        d = release_identity.verdict(root=ROOT, write=False).to_dict()
        return {k: d.get(k) for k in ("verdict", "ok", "allows_new_risk", "running_sha",
                                      "release_sha", "release_id", "reason", "age_h", "stale")}
    except Exception as exc:
        return {"verdict": "UNMEASURED", "ok": None, "allows_new_risk": False,
                "reason": f"{type(exc).__name__}: {exc}"}


def _load(path: Path) -> dict | None:
    try:
        d = json.loads(path.read_text("utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _data_schema() -> dict:
    """Field names, not values: the union of per-symbol keys in the cost universe, the union of
    per-sleeve keys and identity keys in the sleeve registry, and the identity schema tags."""
    uni = _load(TRACKED["cost_fields"]) or {}
    reg = _load(TRACKED["sleeve_registry"]) or {}
    u_fields: set[str] = set()
    for row in uni.values():
        if isinstance(row, dict):
            u_fields.update(str(k) for k in row)
    sleeves = reg.get("sleeves") if isinstance(reg.get("sleeves"), dict) else {}
    s_fields: set[str] = set()
    i_fields: set[str] = set()
    schemas: set[str] = set()
    for s in sleeves.values():
        if not isinstance(s, dict):
            continue
        s_fields.update(str(k) for k in s)
        if isinstance(s.get("identity"), dict):
            i_fields.update(str(k) for k in s["identity"])
        if s.get("identity_schema"):
            schemas.add(str(s["identity_schema"]))
    body = {"universe": sorted(u_fields), "sleeve": sorted(s_fields),
            "identity": sorted(i_fields), "identity_schemas": sorted(schemas)}
    return {"hash": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16],
            "universe_fields": len(u_fields), "sleeve_fields": len(s_fields),
            "identity_fields": len(i_fields), "identity_schemas": sorted(schemas)}


def _certificate() -> dict:
    h = _sha(TRACKED["allocator_proof"])
    if h is None:
        return {"hash": None, "passed": None, "at": None}
    doc = _load(TRACKED["allocator_proof"]) or {}
    return {"hash": h[:16], "passed": doc.get("passed"), "at": doc.get("at")}


def _health() -> dict:
    doc = _load(HEALTH)
    if doc is None:
        return {"status": None}
    errs = doc.get("errors")
    return {"status": doc.get("status"), "updated_at": doc.get("updated_at"),
            "configured_sleeves": doc.get("configured_sleeves"),
            "evidence_blocked_sleeves": doc.get("evidence_blocked_sleeves"),
            "missing_sleeves": doc.get("missing_sleeves"),
            "n_errors": len(errs) if isinstance(errs, list | dict) else errs,
            "gateway_armed": doc.get("gateway_armed")}


def write() -> dict:
    entry = {"at": datetime.now(tz=UTC).isoformat(), "prev": _prev_hash(), "code": _git_head(),
             "files": {k: _sha(p) for k, p in TRACKED.items()},
             "state_vector_id": _state_vector_id(), "armed": _armed(),
             "forecast": _last_forecast(), "release": _release(),
             "data_schema": _data_schema(), "allocator_certificate": _certificate(),
             "health": _health()}
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
          f"armed={e['armed'].get('armed')}  sv={e['state_vector_id']}  "
          f"release={e['release'].get('verdict')}  schema={e['data_schema'].get('hash')}")
    changed = diff_last_two()
    if changed:
        print("  changed since last pass: " + ", ".join(sorted(changed)))
    print(json.dumps(verify()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
