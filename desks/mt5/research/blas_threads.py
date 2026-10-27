"""SINGLE-THREADED BLAS FOR THE JUDGE'S WORKERS: OFF unless a proof says IDENTICAL.

WHY THIS IS A SWITCH AND NOT A SETTING

The judge's workers (the pre-warm pool, the `build`/`rule` shard children, the merging sweep
process that computes the trial census, and the MT5-CacheWarm builder that fills the same series
cache) each load OpenBLAS/MKL with one thread per core. Eighteen workers on an eighteen-core box
then ask for 18 x 18 BLAS threads: oversubscription, not throughput. Pinning BLAS to one thread
per worker is the obvious fix -- but `numpy.linalg.eigvalsh` and the GEMMs in `mt5desk.canonical`
(and the lstsq/eigh/solve inside some family builds) can return different low-order bits at a
different thread count, and the census they feed sets `trial_census`, the `dsr_inputs` rho, the
rounded-up DSR trial charge and the DSR bar: sealed gauntlet output. A throughput change that
moved one verdict bit would be a gate change by the back door.

So the switch takes effect only on EVIDENCE. `scripts/blas_thread_differential.py` (hourly leg
`blas_differential`, which runs only when the proof is missing or lapsed) re-judges a recorded
sweep's cells in fresh processes -- single-threaded, default, and a default control -- rebuilds a
family-stratified sample through the pre-warm worker, and writes `reports/BLAS_DIFFERENTIAL.json`.
`decide()` honours `data/BLAS_SINGLE_THREAD.json` (`{"enabled": true}`) only while that report:

  * is of this schema and harness version, its `content_sha256` recomputes, it is BOUND TO A
    HARNESS RUN (its run id and digest are the latest row of `data/blas_differential_runs.jsonl`),
    and, on a box that holds the release-signing key, its HMAC under that key verifies -- so a
    hand-built report licenses nothing;
  * clears the EVIDENCE FLOOR: >= MIN_SAMPLE sampled cells and >= MIN_SAMPLE judged in every arm,
    the census ran in every arm, the thread contrast was measured (`thread_evidence.differed`),
    the control arm ran and matched the default byte for byte, zero differences, and the
    rebuild covered every family stratum it was asked to with >= MIN_REBUILT cells rebuilt;
  * says IDENTICAL (never DIFFERS, never UNMEASURED);
  * was measured on THIS release (`data/RELEASE.json` `release_id`), core count, numpy, Python,
    BLAS build (the BLAS libraries numpy's own RECORD ships, digest included) and CPU model --
    a proof from another tree, box, library or processor is a claim about something else;
  * is younger than `MAX_PROOF_AGE_S`.

Anything else leaves the thread variables UNSET, i.e. BLAS's own default. A failed proof falls
back to the behaviour that was there before; it never invents a third one.

ALL THREE OR NONE. If any of the three variables is already present (an operator export, in the
target env or this process), the switch adds none of them, so a worker never runs a mixed set.

THIS MODULE MUST NOT IMPORT NUMPY. BLAS reads its thread count once, when it is loaded, so the
decision has to be taken before the first `import numpy` of the process it governs. The BLAS
build is therefore identified from numpy's installed RECORD, never by loading it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import sys
from collections.abc import Mapping, MutableMapping
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
FLAG = DESK / "data" / "BLAS_SINGLE_THREAD.json"
PROOF = DESK / "reports" / "BLAS_DIFFERENTIAL.json"
RELEASE = DESK / "data" / "RELEASE.json"
#: The OLDER switch run_sharded_gauntlet shipped on 2026-10-20 (2bca88f00), armed by exactly
#: {"enabled": true}. Still read, so nobody's file breaks, but since v1.1 it takes effect only
#: under the same proof as FLAG and sets all three variables or none (`legacy`).
LEGACY_FLAG = DESK / "data" / "JUDGE_BLAS_SINGLE_THREAD.json"
#: One row per harness run that published a report: the binding a hand-built report lacks.
RUN_LOG = DESK / "data" / "blas_differential_runs.jsonl"

#: The variables BLAS/OpenMP read at load. All three are set together or none is.
THREAD_VARS = ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS")
SCHEMA = "blas_differential/v2"
#: Bumped whenever the harness's evidence changes meaning; an older report licenses nothing.
HARNESS_VERSION = "1.1"
IDENTICAL, DIFFERS, UNMEASURED = "IDENTICAL", "DIFFERS", "UNMEASURED"
#: THE EVIDENCE FLOOR. Below this many sampled and judged cells the census matrix is too small
#: for BLAS to thread at all, so an IDENTICAL there says nothing about the production sweep.
MIN_SAMPLE = 200
#: Fewest cells the pre-warm rebuild must actually rebuild (a skipped build is lost coverage).
MIN_REBUILT = 10
#: The arms that must all be present: default, single-threaded, and the default control.
REQUIRED_ARMS = ("default", "single", "control")
#: A proof older than this is re-measured before it is trusted, even on an unchanged release.
MAX_PROOF_AGE_S = 7 * 86400
#: Clock skew tolerated before a proof dated in the future is refused.
FUTURE_SKEW_S = 300
#: The HMAC domain, so this key's MAC over a proof can never be replayed as another record's.
_HMAC_DOMAIN = b"blas_differential/proof:"


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


_BLAS_SUFFIX = (".so", ".dll", ".dylib", ".pyd")


def blas_build() -> dict[str, Any]:
    """The BLAS libraries numpy ships, from its installed RECORD (name, recorded hash, size).

    Read without loading numpy, so it can be compared before BLAS reads its thread count. A
    numpy linked against a system BLAS ships none and reads `system` -- still a fact, and one a
    proof measured on a bundled build will not match.
    """
    try:
        files = metadata.files("numpy") or []
    except metadata.PackageNotFoundError:
        return {"libs": [], "digest": "absent"}
    libs = []
    for f in files:
        name = str(f).replace("\\", "/")
        low = name.lower().rsplit("/", 1)[-1]
        if ("blas" in low or "mkl" in low or "lapack" in low) and (
                low.endswith(_BLAS_SUFFIX) or ".so." in low):
            libs.append({"name": name.rsplit("/", 1)[-1],
                         "hash": f.hash.value if f.hash else None, "size": f.size})
    libs.sort(key=lambda r: str(r["name"]))
    digest = hashlib.sha256(json.dumps(libs, sort_keys=True).encode()).hexdigest()[:16] \
        if libs else "system"
    return {"libs": libs, "digest": digest}


def cpu_model() -> str:
    """The processor model: OpenBLAS's DYNAMIC_ARCH picks its kernels from it."""
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text("utf-8", "replace").splitlines():
                if line.lower().startswith("model name"):
                    return f"{platform.machine()} {line.split(':', 1)[1].strip()}"
        except OSError:
            pass
    return f"{platform.machine()} {platform.processor()}".strip()


def identity(release_path: Path | None = None) -> dict[str, Any]:
    """What a proof is bound to: release, cores, numpy, Python, BLAS build and CPU model."""
    return {"release_id": release_id(release_path), "cores": os.cpu_count() or 1,
            "numpy": _numpy_version(), "python": platform.python_version(),
            "blas_build": blas_build()["digest"], "cpu": cpu_model()}


IDENTITY_KEYS = ("release_id", "cores", "numpy", "python", "blas_build", "cpu")


def content_sha256(doc: Mapping[str, Any]) -> str:
    """Canonical digest of a proof without its own digest and MAC fields."""
    body = {k: v for k, v in doc.items() if k not in ("content_sha256", "proof_hmac")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _signing_key() -> bytes | None:
    """The desk's release-signing key (never printed, never leaves the box), or None."""
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from libs.ops.release_signing import load_key
        return load_key()
    except Exception:
        return None


def proof_hmac(content_sha: str, key: bytes | None = None) -> str | None:
    """HMAC-SHA256 of a proof's digest under the signing key; None when this box holds none."""
    key = _signing_key() if key is None else key
    if not key:
        return None
    return hmac.new(key, _HMAC_DOMAIN + content_sha.encode("ascii"), hashlib.sha256).hexdigest()


def _last_run(path: Path | None = None) -> dict[str, Any] | None:
    try:
        lines = Path(path or RUN_LOG).read_text("utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            return row
    return None


def _parse(ts: Any) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _int(x: Any) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def evidence_floor(doc: Mapping[str, Any]) -> list[str]:
    """Every way the report's evidence falls short of licensing the switch (empty = clears)."""
    short: list[str] = []
    inp = doc.get("input") if isinstance(doc.get("input"), Mapping) else {}
    if _int(inp.get("sampled_cells")) < MIN_SAMPLE:
        short.append(f"sampled_cells {inp.get('sampled_cells')} < {MIN_SAMPLE}")
    arms = doc.get("arms") if isinstance(doc.get("arms"), Mapping) else {}
    for name in REQUIRED_ARMS:
        arm = arms.get(name)
        if not isinstance(arm, Mapping):
            short.append(f"arm {name} absent")
            continue
        if _int(arm.get("n_judged")) < MIN_SAMPLE:
            short.append(f"arm {name} judged {arm.get('n_judged')} < {MIN_SAMPLE}")
        if _int(arm.get("census_calls")) < 1:
            short.append(f"arm {name}: the census never ran")
    ev = doc.get("thread_evidence") if isinstance(doc.get("thread_evidence"), Mapping) else {}
    if ev.get("differed") is not True:
        short.append("thread_evidence.differed is not true")
    if doc.get("n_differences") != 0 or doc.get("differences"):
        short.append(f"n_differences {doc.get('n_differences')} != 0")
    if doc.get("control_differences") != 0:
        short.append(f"control arm differences {doc.get('control_differences')} != 0")
    rb = doc.get("rebuild_coverage") if isinstance(doc.get("rebuild_coverage"), Mapping) else {}
    if _int(rb.get("rebuilt")) < MIN_REBUILT:
        short.append(f"rebuilt {rb.get('rebuilt')} < {MIN_REBUILT} (skipped builds are lost "
                     "coverage)")
    if rb.get("strata_unrebuilt"):
        short.append(f"family strata never rebuilt: {rb.get('strata_unrebuilt')}")
    return short


def proof_status(proof_path: Path | None = None, *, release_path: Path | None = None,
                 run_log: Path | None = None, now: datetime | None = None) -> tuple[bool, str]:
    """(valid, why) for the differential report as a licence for single-threaded BLAS."""
    path = Path(proof_path or PROOF)
    doc = _read(path)
    if not isinstance(doc, dict):
        return False, f"{path.name} absent or unreadable"
    if doc.get("schema") != SCHEMA:
        return False, f"{path.name} schema {doc.get('schema')!r} != {SCHEMA}"
    if doc.get("harness_version") != HARNESS_VERSION:
        return False, (f"{path.name} harness {doc.get('harness_version')!r} != "
                       f"{HARNESS_VERSION}")
    try:
        sha = content_sha256(doc)
    except (TypeError, ValueError) as exc:
        return False, f"{path.name} cannot be digested ({type(exc).__name__})"
    if doc.get("content_sha256") != sha:
        return False, f"{path.name} content_sha256 does not recompute"
    run = _last_run(run_log)
    if not run or run.get("run_id") != doc.get("run_id") or run.get("content_sha256") != sha:
        return False, (f"{path.name} is not the latest harness run in {RUN_LOG.name} (run "
                       f"{doc.get('run_id')!r}); a report no run wrote licenses nothing")
    key = _signing_key()
    if key is not None:
        want = proof_hmac(sha, key)
        if not hmac.compare_digest(str(doc.get("proof_hmac") or ""), str(want)):
            return False, f"{path.name} proof_hmac does not verify under this box's key"
    if doc.get("verdict") != IDENTICAL:
        return False, f"{path.name} verdict is {doc.get('verdict')!r}, not {IDENTICAL}"
    short = evidence_floor(doc)
    if short:
        return False, f"{path.name} below the evidence floor: {'; '.join(short)}"
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
    for k in IDENTITY_KEYS:
        if proved.get(k) != here[k]:
            return False, (f"{path.name} proved {k}={proved.get(k)!r}; this process runs "
                           f"{k}={here[k]!r}")
    if here["release_id"] == "unreleased":
        return False, "no release_id on this tree, so no proof can be bound to it"
    return True, (f"{path.name} IDENTICAL on release {here['release_id']} "
                  f"({'keyed' if key is not None else 'run-bound, no signing key on this box'})")


def decide(flag_path: Path | None = None, proof_path: Path | None = None, *,
           release_path: Path | None = None, run_log: Path | None = None,
           now: datetime | None = None) -> dict[str, Any]:
    """Whether the judge's workers run single-threaded BLAS, and why. Never raises."""
    flag = _read(Path(flag_path or FLAG))
    enabled = isinstance(flag, dict) and flag.get("enabled") is True
    try:
        ok, why = proof_status(proof_path, release_path=release_path, run_log=run_log, now=now)
    except Exception as exc:             # a broken proof reader is a failed proof, never a crash
        ok, why = False, f"proof unreadable ({type(exc).__name__})"
    if not enabled:
        return {"active": False, "enabled": False, "proof_valid": ok,
                "why": f"BLAS_SINGLE_THREAD.json absent or not enabled (proof: {why})", "env": {}}
    if not ok:
        return {"active": False, "enabled": True, "proof_valid": False,
                "why": f"enabled, but the proof does not hold: {why}", "env": {}}
    return {"active": True, "enabled": True, "proof_valid": True, "why": why,
            "env": dict.fromkeys(THREAD_VARS, "1")}


def apply(env: MutableMapping[str, str], **kw: Any) -> dict[str, str]:
    """Add all three single-thread variables to `env` when `decide()` allows, or none.

    None when ANY of the three is already present in `env` or in this process: an operator's
    export is never overwritten, and a worker never runs a mixed set.
    """
    d = decide(**kw)
    if not d["env"]:
        return {}
    present = [k for k in THREAD_VARS if k in env or k in os.environ]
    if present:
        return {}
    for k, v in d["env"].items():
        env[k] = v
    return dict(d["env"])


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key in the BLAS switch file")
    return dict(pairs)


def legacy_armed(path: Path | None = None) -> bool:
    """The old switch file's own strict reading, unchanged: exactly {"enabled": true} (one key,
    the JSON literal true, no duplicate keys). Anything else, or no file, is not armed."""
    try:
        doc = json.loads(Path(path or LEGACY_FLAG).read_text("utf-8"),
                         object_pairs_hook=_no_duplicate_keys)
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and set(doc) == {"enabled"} and doc["enabled"] is True


def legacy(env: Mapping[str, str], path: Path | None = None, **kw: Any) -> dict[str, Any]:
    """What JUDGE_BLAS_SINGLE_THREAD.json may do to a sweep env. Never raises, never mutates.

    Armed is no longer enough (audit of 5d4d0279f): it takes effect only when `proof_status()`
    holds -- the same run-bound, floor-clearing IDENTICAL proof BLAS_SINGLE_THREAD.json needs --
    and then sets all three variables, or none when any is already in `env` (an operator's
    export, or BLAS_SINGLE_THREAD.json having applied them first). Otherwise the env keeps its
    defaults and `why` says which condition failed."""
    where = _rel(Path(path or LEGACY_FLAG))
    armed = legacy_armed(path)
    out: dict[str, Any] = {"flag": where, "armed": armed, "applied": False, "env": {}}
    if not armed:
        out["why"] = f"{where} absent or not exactly {{\"enabled\": true}}: defaults"
        return out
    present = {k: env[k] for k in THREAD_VARS if k in env}
    if present:
        out["why"] = (f"{where} armed, but {sorted(present)} already set: all three or none, "
                      "so nothing added")
        out["in_force"] = present
        return out
    try:
        ok, why = proof_status(**kw)
    except Exception as exc:
        ok, why = False, f"proof unreadable ({type(exc).__name__})"
    out["proof_valid"] = ok
    if not ok:
        out["why"] = f"{where} armed, but the proof does not hold: {why}; defaults"
        return out
    out.update(applied=True, env=dict.fromkeys(THREAD_VARS, "1"),
               why=f"{where} armed and the proof holds: {why}")
    return out


def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(p)


def status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """The switch's state for a publisher: the decision, its reason, and what is in force."""
    d = decide()
    src = os.environ if env is None else env
    present = {k: src.get(k) for k in THREAD_VARS if k in src}
    return {"active": d["active"], "enabled": d.get("enabled"),
            "proof_valid": d.get("proof_valid"), "why": d["why"],
            "flag": _rel(FLAG), "proof": _rel(PROOF), "run_log": _rel(RUN_LOG),
            "in_force": present,
            "mixed_operator_set": 0 < len(present) < len(THREAD_VARS),
            "probe_raw_diff": probe_raw_diff(),
            "legacy_switch": {k: v for k, v in legacy(src).items() if k != "env"},
            "identity": identity()}


def probe_raw_diff(proof_path: Path | None = None) -> dict[str, Any]:
    """The proof's recorded raw-probe movement (max ULP / max abs), for the publisher.

    Not binding -- the harness lets only judge outputs and the rounded eigvalsh branch decide
    the verdict -- but published so a reader sees how far the unrounded census moved."""
    path = PROOF if proof_path is None else proof_path
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {"state": "UNMEASURED", "why": f"{_rel(path)} absent or unreadable"}
    prd = doc.get("probe_raw_diff") if isinstance(doc, dict) else None
    if not isinstance(prd, dict):
        return {"state": "UNMEASURED", "why": "the proof records no probe_raw_diff"}
    return {"state": "MEASURED", "verdict": doc.get("verdict"), "run_id": doc.get("run_id"),
            **{k: prd.get(k) for k in ("binding", "n_paths", "eigvalsh_moved", "max_ulp",
                                       "max_abs", "also_in_control")}}
