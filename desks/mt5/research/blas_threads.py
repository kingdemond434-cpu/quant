"""SINGLE-THREADED BLAS FOR THE JUDGE'S WORKERS: OFF unless a proof says IDENTICAL.

WHY THIS IS A SWITCH AND NOT A SETTING

The judge's workers (the pre-warm pool and the `build`/`rule` shard children, and the merging
sweep process that computes the trial census) each load OpenBLAS/MKL with one thread per core.
Eighteen workers on an eighteen-core box then ask for 18 x 18 BLAS threads, which is
oversubscription, not throughput. Pinning BLAS to one thread per worker is the obvious fix --
but `numpy.linalg.eigvalsh` and the GEMMs in `mt5desk.canonical` can return different low-order
bits at a different thread count, and the census they feed sets `trial_census`, the `dsr_inputs`
rho, the rounded-up DSR trial charge and the DSR bar: every one of them sealed gauntlet output.
A throughput change that moved one verdict bit would be a gate change by the back door.

So the switch takes effect only on EVIDENCE. `scripts/blas_thread_differential.py` re-judges a
recorded sweep's cells twice in fresh processes -- single-threaded and default -- and writes
`reports/BLAS_DIFFERENTIAL.json`. `decide()` honours `data/BLAS_SINGLE_THREAD.json`
(`{"enabled": true}`) only while that report:

  * says IDENTICAL (never DIFFERS, never UNMEASURED);
  * was measured on THIS release (`data/RELEASE.json` `release_id`), on a machine with this many
    cores, under this numpy and this Python -- a proof from another tree, box or library is a
    claim about something else;
  * is younger than `MAX_PROOF_AGE_S` and its `content_sha256` recomputes (no hand edits).

Anything else -- flag absent, flag off, report absent, stale, foreign, edited or not IDENTICAL --
leaves the thread variables UNSET, i.e. BLAS's own default. A failed proof falls back to the
behaviour that was there before; it never invents a third one.

The variables are only ever ADDED: one an operator exported by hand is never overwritten.

THIS MODULE MUST NOT IMPORT NUMPY. BLAS reads its thread count once, when it is loaded, so the
decision has to be taken before the first `import numpy` of the process it governs.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
from collections.abc import Mapping, MutableMapping
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
FLAG = DESK / "data" / "BLAS_SINGLE_THREAD.json"
PROOF = DESK / "reports" / "BLAS_DIFFERENTIAL.json"
RELEASE = DESK / "data" / "RELEASE.json"

#: The variables BLAS/OpenMP read at load. All three are set together or none is.
THREAD_VARS = ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS")
SCHEMA = "blas_differential/v1"
IDENTICAL, DIFFERS, UNMEASURED = "IDENTICAL", "DIFFERS", "UNMEASURED"
#: A proof older than this is re-measured before it is trusted, even on an unchanged release.
MAX_PROOF_AGE_S = 7 * 86400
#: Clock skew tolerated before a proof dated in the future is refused.
FUTURE_SKEW_S = 300


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def release_id(path: Path | None = None) -> str:
    """The stamped release id of this tree, 'unreleased' when none can be read."""
    doc = _read(Path(path or RELEASE))
    rid = doc.get("release_id") if isinstance(doc, dict) else None
    return str(rid) if rid else "unreleased"


def _numpy_version() -> str:
    try:
        return metadata.version("numpy")      # never `import numpy`: see the module docstring
    except metadata.PackageNotFoundError:
        return "absent"


def identity(release_path: Path | None = None) -> dict[str, Any]:
    """What a proof is bound to: the release, the machine's core count, numpy and Python."""
    return {"release_id": release_id(release_path), "cores": os.cpu_count() or 1,
            "numpy": _numpy_version(), "python": platform.python_version()}


def content_sha256(doc: Mapping[str, Any]) -> str:
    """Canonical digest of a proof without its own digest field."""
    body = {k: v for k, v in doc.items() if k != "content_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _parse(ts: Any) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def proof_status(proof_path: Path | None = None, *, release_path: Path | None = None,
                 now: datetime | None = None) -> tuple[bool, str]:
    """(valid, why) for the differential report as a licence for single-threaded BLAS."""
    path = Path(proof_path or PROOF)
    doc = _read(path)
    if not isinstance(doc, dict):
        return False, f"{path.name} absent or unreadable"
    if doc.get("schema") != SCHEMA:
        return False, f"{path.name} schema {doc.get('schema')!r} != {SCHEMA}"
    try:
        if doc.get("content_sha256") != content_sha256(doc):
            return False, f"{path.name} content_sha256 does not recompute"
    except (TypeError, ValueError) as exc:
        return False, f"{path.name} cannot be digested ({type(exc).__name__})"
    if doc.get("verdict") != IDENTICAL:
        return False, f"{path.name} verdict is {doc.get('verdict')!r}, not {IDENTICAL}"
    at = _parse(doc.get("generated_utc"))
    now = now or datetime.now(UTC)
    if at is None:
        return False, f"{path.name} carries no generated_utc"
    age = (now - at).total_seconds()
    if age < -FUTURE_SKEW_S:
        return False, f"{path.name} is dated in the future ({doc.get('generated_utc')})"
    if age > MAX_PROOF_AGE_S:
        return False, f"{path.name} is {age / 86400:.1f} days old (max {MAX_PROOF_AGE_S // 86400})"
    proved = doc.get("identity") if isinstance(doc.get("identity"), dict) else {}
    here = identity(release_path)
    for key in ("release_id", "cores", "numpy", "python"):
        if proved.get(key) != here[key]:
            return False, (f"{path.name} proved {key}={proved.get(key)!r}; this process runs "
                           f"{key}={here[key]!r}")
    if here["release_id"] == "unreleased":
        return False, "no release_id on this tree, so no proof can be bound to it"
    return True, f"{path.name} IDENTICAL on release {here['release_id']}"


def decide(flag_path: Path | None = None, proof_path: Path | None = None, *,
           release_path: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Whether the judge's workers run single-threaded BLAS, and why. Never raises."""
    flag = _read(Path(flag_path or FLAG))
    if not (isinstance(flag, dict) and flag.get("enabled") is True):
        return {"active": False, "why": "BLAS_SINGLE_THREAD.json absent or not enabled",
                "env": {}}
    try:
        ok, why = proof_status(proof_path, release_path=release_path, now=now)
    except Exception as exc:             # a broken proof reader is a failed proof, never a crash
        ok, why = False, f"proof unreadable ({type(exc).__name__})"
    if not ok:
        return {"active": False, "why": f"enabled, but the proof does not hold: {why}",
                "env": {}}
    return {"active": True, "why": why, "env": dict.fromkeys(THREAD_VARS, "1")}


def apply(env: MutableMapping[str, str], **kw: Any) -> dict[str, str]:
    """Add the single-thread variables to `env` when `decide()` allows; never overwrite one."""
    d = decide(**kw)
    applied: dict[str, str] = {}
    for k, v in d["env"].items():
        if k in env:
            continue
        env[k] = v
        applied[k] = v
    return applied
