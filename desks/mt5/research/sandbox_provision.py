"""THE SANDBOX PROVISIONER -- the federation's supply line (LAWS 5h/5m), hourly.

WHY IT EXISTS. `research/sandbox_runner.py` plans 63 systems and could run 7: the other 56 read
UNMEASURED because their library is not importable on this interpreter, each carrying an INSTALL
TASK that nothing executed. A task nobody runs is an idle organ (LAWS 7), so this leg IS the
thing that runs them: it installs the pinned requirement, proves the module imports, reads the
licence at the same pin the wheel came from, and records the result so the runner's next pass
plans the system RUNNABLE instead of UNMEASURED.

ONE SHARED ENVIRONMENT, NOT FIFTY-EIGHT. Per-system venvs would each re-install numpy, pandas,
scipy and scikit-learn; measured on this host that is ~500 MB apiece against a measured free
disk, so the supply line would stop on disk long before it stopped on capability. The
provisioner therefore builds ONE venv at `<sandbox root>/_shared/venv` with
`--system-site-packages` -- the desk's own interpreter and its own numpy/pandas/scipy, plus
whatever upstream needs on top -- and never touches the interpreter the gateway imports from.
`libs.research.sandbox.shared_python` is what the runner executes adapters with.

A FAILURE IS A MEASUREMENT, AND SOME FAILURES ARE FINAL. pip's own words are classified: "no
matching distribution", "requires a different Python", a resolution conflict, or a source build
that needs a compiler this host does not have are PERMANENTLY_UNAVAILABLE -- recorded once with
the exact error and never retried, because retrying an interpreter incompatibility every hour
forever is a lie about effort. A timeout or a network error is RETRYABLE and comes back with
backoff. Every terminal row names its cover: the adapter's numpy fallback, or a REBUILT task.

ARTIFACT `reports/SANDBOX_PROVISION.json` and the lifetime ledger
`data/sandbox_install_ledger.json` (per system: requirement, status, the exact error, attempts,
seconds, the measured import and its version). CONSUMERS: `research/sandbox_runner.py`
(availability and the interpreter it runs adapters with), `research/sandbox_roster.py` (the
disposition column), `scripts/check_sandbox_liveness.py` (an UNMEASURED reason that has not
moved in a week with no install task moving is a fence failure).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import adapters as A  # noqa: E402
from libs.research import external_federation as fed  # noqa: E402
from libs.research import licence_reader as LR  # noqa: E402
from libs.research import sandbox as SB  # noqa: E402

GENERATOR = "sandbox_provision"
REPORT = DESK / "reports" / "SANDBOX_PROVISION.json"
LEDGER = DESK / "data" / "sandbox_install_ledger.json"
FED_STATE = DESK / "data" / "external_federation.json"
RUNNER_STATE = DESK / "data" / "sandbox_runner_state.json"

INSTALLED = "INSTALLED"
PERMANENT = "PERMANENTLY_UNAVAILABLE"
RETRYABLE = "RETRYABLE"
NO_PIN = "NO_DISTRIBUTION_PINNED"
#: A retryable row waits this long between attempts, doubling to a week, so a flaky index is
#: retried soon and a stubborn one stops costing the hour.
RETRY_BASE_S = 30 * 60
RETRY_MAX_S = 7 * 24 * 3600
#: Free-disk headroom REQUIRED before an attempt, measured on the sandbox root's volume. Derived
#: from the weight the spec declares, never from a remembered machine size.
DISK_NEED_MB = {"light": 700.0, "heavy": 4500.0}
LAW = ("LAWS 5h/5m: upstream code runs only in a sandbox, at a pin, under a licence that was "
       "READ; a library that cannot be provisioned is a recorded measurement with its cover, "
       "never a silent gap.")
CONSUMERS = ("research/sandbox_runner.py (availability + the interpreter adapters run on)",
             "research/sandbox_roster.py (disposition and licence columns)",
             "scripts/check_sandbox_liveness.py (a stale UNMEASURED reason is a fence failure)")

#: pip's own words for a failure that this interpreter/platform can never resolve. Retrying any
#: of these on the next hour would burn the budget forever and change nothing.
_FINAL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"no matching distribution found",
     "no distribution for this interpreter/platform at the pinned version"),
    (r"could not find a version that satisfies",
     "no released version satisfies the pin on this interpreter"),
    (r"requires a different python",
     "the distribution declares a Requires-Python this interpreter does not satisfy"),
    (r"resolutionimpossible|conflict is caused by",
     "dependency resolution is impossible against the desk's pinned core"),
    (r"microsoft visual c\+\+|vcvarsall|cl\.exe|command 'gcc'|command 'cc'|unable to find "
     r"vswhere",
     "the wheel is source-only and this host has no C toolchain"),
    (r"metadata-generation-failed|failed building wheel|error: subprocess-exited-with-error",
     "the source build failed on this host"),
    (r"only-binary|no binary distribution", "no binary distribution is published"),
)
_RETRY_PATTERNS = re.compile(
    r"read timed out|connection|temporary failure|timed out|proxy|ssl|network|503|502|429",
    re.I)


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def free_disk_mb(path: Path) -> float | None:
    """Measured free space on the volume the sandboxes live on, or None when unreadable."""
    try:
        target = path
        while not target.exists() and target != target.parent:
            target = target.parent
        return float(shutil.disk_usage(str(target)).free) / (1024 * 1024)
    except (OSError, ValueError):
        return None


def classify(text: str) -> tuple[str, str]:
    """pip's output -> (status, reason). Final failures are named; everything else retries."""
    low = (text or "").lower()
    for pattern, reason in _FINAL_PATTERNS:
        if re.search(pattern, low):
            return PERMANENT, reason
    if _RETRY_PATTERNS.search(low):
        return RETRYABLE, "the index or the network did not answer"
    return RETRYABLE, "pip failed for a reason this host has not classified as final"


def _age_s(stamp: str | None) -> float:
    try:
        return max(0.0, (datetime.now(tz=UTC)
                         - datetime.fromisoformat(str(stamp))).total_seconds())
    except (TypeError, ValueError):
        return float("inf")


def retry_due(row: dict[str, Any]) -> bool:
    """A RETRYABLE row is due when its backoff (30 min doubling to a week) has elapsed."""
    attempts = max(1, int(row.get("attempts") or 1))
    wait = float(min(RETRY_MAX_S, RETRY_BASE_S * (2 ** (attempts - 1))))
    return _age_s(row.get("last_attempt_at")) >= wait


def ensure_shared(root: Path, *, timeout_s: int = 300) -> tuple[Path, str]:
    """The shared interpreter, created from THIS desk's python with the desk's own numpy and
    pandas visible. Returns (python, why)."""
    py = SB.shared_python(root)
    if py.exists():
        return py, "shared venv already present"
    base = (root / SB.SHARED_ID)
    base.mkdir(parents=True, exist_ok=True)
    try:
        made = subprocess.run(
            [sys.executable, "-m", "venv", "--system-site-packages", str(base / "venv")],
            env=SB.scrub_env(), capture_output=True, text=True, timeout=timeout_s, check=False,
            cwd=str(base))
    except (subprocess.TimeoutExpired, OSError) as exc:
        return py, f"venv creation failed: {type(exc).__name__}: {exc}"
    if made.returncode != 0 or not py.exists():
        return py, f"venv creation failed: {(made.stderr or made.stdout)[-200:]}"
    return py, "shared venv created with --system-site-packages"


def verify(py: Path, module: str, *, timeout_s: int = 180) -> tuple[bool, str, str]:
    """Prove the module imports in the shared venv. Returns (ok, version, error)."""
    if not module:
        return False, "", "the spec names no module to import"
    code = ("import importlib,importlib.metadata as M\n"
            f"m=importlib.import_module({module!r})\n"
            "v=getattr(m,'__version__','')\n"
            "print('OK',v)\n")
    try:
        proc = subprocess.run([str(py), "-c", code], env=SB.scrub_env(),
                              capture_output=True, text=True, timeout=timeout_s, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, "", f"{type(exc).__name__}: {exc}"[:300]
    out = (proc.stdout or "").strip()
    if proc.returncode == 0 and out.startswith("OK"):
        return True, out[3:].strip(), ""
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
    return False, "", " | ".join(t[:200] for t in tail)[:400]


def pip_install(py: Path, requirement: str, *, timeout_s: int) -> tuple[bool, str, float]:
    t0 = time.monotonic()
    argv = [str(py), "-m", "pip", "install", "--no-input", "--disable-pip-version-check",
            "--progress-bar", "off", "--no-warn-script-location", requirement]
    try:
        proc = subprocess.run(argv, env=SB.scrub_env(), capture_output=True,
                              text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return False, f"pip install timed out after {timeout_s}s", round(
            time.monotonic() - t0, 1)
    except OSError as exc:
        return False, f"pip failed to start: {type(exc).__name__}: {exc}", 0.0
    seconds = round(time.monotonic() - t0, 1)
    if proc.returncode == 0:
        return True, "installed", seconds
    body = (proc.stderr or "") + "\n" + (proc.stdout or "")
    tail = [ln for ln in body.strip().splitlines() if ln.strip()][-6:]
    return False, " | ".join(t[:200] for t in tail)[:800], seconds


def cover_of(sid: str) -> str:
    """What carries this system's capability while its library cannot be provisioned."""
    spec = A.SPECS.get(sid)
    family = A.FAMILY_OF.get(sid, "data_tooling")
    try:
        from research import sandboxes as CELLS
        cells = [c for c in CELLS.CELLS
                 if sid in tuple(getattr(CELLS.load_cell(c), "UPSTREAM", ()))]
    except Exception:
        cells = []
    if cells:
        return f"REBUILT cell(s): {', '.join('cell:' + c for c in cells)}"
    try:
        mod = __import__(f"libs.research.adapters.{sid}", fromlist=["run"]) if spec else None
    except Exception:
        mod = None
    if mod is not None and bool(getattr(mod, "RUNS_WITHOUT_LIBRARY", False)):
        return f"the adapter's own numpy implementation ({family}); no library is needed"
    return (f"UNCOVERED: capability family {family!r} needs a REBUILT cell under "
            f"research/sandboxes/ whose UPSTREAM names {sid}")


def priority(sid: str, roi: dict[str, Any], ledger: dict[str, Any]) -> tuple[float, str]:
    """ROI order: measured ROI when the federation has one, otherwise the declared yield --
    candidates and datasets reach the gauntlet directly and outrank a representation -- and a
    light wheel outranks a heavy one because it buys the same hour more systems."""
    spec = A.SPECS.get(sid)
    if spec is None:
        return 0.0, "no spec"
    measured = roi.get(sid, {}).get("roi")
    score = float(measured) if isinstance(measured, int | float) else 0.0
    why = f"measured ROI {score:.2f}" if score else "no measured ROI yet"
    yields = set(spec.yields)
    score += 3.0 * len(yields & {"candidates"}) + 2.0 * len(yields & {"datasets", "mechanisms"})
    score += 1.0 * len(yields & {"representations", "research_methods"})
    score += 2.0 if spec.weight == "light" else 0.0
    row = ledger.get(sid) or {}
    score -= 0.5 * float(row.get("attempts") or 0)
    return score, f"{why}; yields {sorted(yields)}; weight {spec.weight}"


def candidates_for(ledger: dict[str, Any], *, only: list[str] | None,
                   force: bool) -> list[str]:
    """Systems worth an attempt this pass: never installed, or RETRYABLE and due. A
    PERMANENTLY_UNAVAILABLE row is never retried -- that is the whole point of recording it."""
    out = []
    for sid, spec in A.SPECS.items():
        if only and sid not in only:
            continue
        row = ledger.get(sid) or {}
        status = str(row.get("status") or "")
        if not spec.requirement or "==" not in spec.requirement:
            continue
        if status == INSTALLED and not force:
            continue
        if status == PERMANENT and not force:
            continue
        if status == RETRYABLE and not force and not retry_due(row):
            continue
        out.append(sid)
    return out


def read_licence(sid: str, rows: dict[str, dict[str, Any]], root: Path) -> dict[str, Any]:
    """Read the licence at the SAME pin the wheel came from and record it on the roster row, so
    the runner's `refuse_reason` stops refusing a system whose terms are now known."""
    base = fed.SEED_BY_ID.get(sid)
    if base is None:
        return {"system": sid, "licence": "UNVERIFIED", "why": "system is not on the roster"}
    row = rows.setdefault(sid, {})
    if str(row.get("licence") or "UNVERIFIED") not in ("UNVERIFIED", "", "UNMEASURED"):
        return {"system": sid, "licence": row["licence"], "why": "already read"}
    try:
        reading = LR.read(base, root=root)
    except Exception as exc:  # a licence read never breaks the supply line
        return {"system": sid, "licence": "UNVERIFIED",
                "why": f"{type(exc).__name__}: {exc}"[:200]}
    LR.apply(row, reading)
    disposition, why = LR.dispose(base, reading)
    if reading.read:
        row["disposition"], row["why"] = disposition, why
    return {"system": sid, **reading.record(), "disposition": disposition}


def provision_pass(*, budget_s: float = 900.0, root: Path | None = None,
                   max_installs: int | None = None, only: list[str] | None = None,
                   force: bool = False, dry_run: bool = False,
                   ledger_path: Path = LEDGER, report_path: Path = REPORT,
                   fed_state_path: Path = FED_STATE,
                   runner_state_path: Path = RUNNER_STATE) -> dict[str, Any]:
    t0 = time.monotonic()
    root = root or SB.SANDBOX_ROOT
    deadline = t0 + max(20.0, budget_s * 0.95)
    ledger = _read(ledger_path, {}) or {}
    rows_ledger: dict[str, Any] = dict(ledger.get("systems") or {})
    runner_state = _read(runner_state_path, {}) or {}
    roi = {k: v for k, v in (runner_state.get("systems") or {}).items() if isinstance(v, dict)}
    fed_state = _read(fed_state_path, {}) or {}
    fed_rows = {str(k): dict(v) for k, v in (fed_state.get("systems") or {}).items()
                if isinstance(v, dict)}

    py, venv_why = ("", "dry run: no venv created") if dry_run else ensure_shared(root)
    order = sorted(candidates_for(rows_ledger, only=only, force=force),
                   key=lambda s: -priority(s, roi, rows_ledger)[0])
    if max_installs:
        order = order[:max_installs]
    attempted: list[dict[str, Any]] = []
    licence_reads: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for sid in order:
        spec = A.SPECS[sid]
        left = deadline - time.monotonic()
        if left <= 15:
            skipped.append({"system": sid, "why": "budget exhausted"})
            continue
        disk = free_disk_mb(root)
        need = DISK_NEED_MB.get(spec.weight, DISK_NEED_MB["light"])
        if disk is not None and disk < need:
            skipped.append({"system": sid, "why": f"measured free disk {disk:.0f} MB < the "
                                                  f"{need:.0f} MB a {spec.weight} wheel needs"})
            continue
        row = dict(rows_ledger.get(sid) or {})
        score, why_rank = priority(sid, roi, rows_ledger)
        rec: dict[str, Any] = {"system": sid, "requirement": spec.requirement,
                               "module": spec.module, "weight": spec.weight,
                               "rank_score": round(score, 3), "rank_why": why_rank,
                               "attempts": int(row.get("attempts") or 0) + 1,
                               "first_seen": row.get("first_seen") or now(),
                               "last_attempt_at": now(),
                               "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                               "platform": sys.platform}
        if dry_run:
            rec.update({"status": "PLANNED", "why": "dry run"})
            attempted.append(rec)
            continue
        ok_already, version_already, _ = verify(Path(py), spec.module, timeout_s=60)
        if ok_already and not force:
            rec.update({"status": INSTALLED, "why": "already importable in the shared venv",
                        "version": version_already, "seconds": 0.0})
        else:
            ok, why, seconds = pip_install(Path(py), spec.requirement,
                                           timeout_s=int(min(left, 900)))
            if not ok:
                status, reason = classify(why)
                rec.update({"status": status, "why": reason, "error": why, "seconds": seconds,
                            "cover": cover_of(sid)})
            else:
                imported, version, err = verify(Path(py), spec.module)
                if imported:
                    rec.update({"status": INSTALLED, "why": "installed and imported",
                                "version": version, "seconds": seconds})
                else:
                    rec.update({"status": PERMANENT, "seconds": seconds, "error": err,
                                "why": "the wheel installed but the module does not import on "
                                       "this host", "cover": cover_of(sid)})
        if rec["status"] == INSTALLED:
            licence_reads.append(read_licence(sid, fed_rows, root))
        attempted.append(rec)
        rows_ledger[sid] = rec

    for sid, spec in A.SPECS.items():
        if sid in rows_ledger:
            continue
        if not spec.requirement or "==" not in spec.requirement:
            rows_ledger[sid] = {
                "system": sid, "requirement": spec.requirement, "module": spec.module,
                "weight": spec.weight, "status": NO_PIN, "attempts": 0,
                "first_seen": now(), "last_attempt_at": None,
                "why": "no wheel was resolved on this interpreter: pin a commit or a wheel "
                       "before a sandbox may install it (LAWS 5m forbids a floating pin)",
                "cover": cover_of(sid)}

    modules = {sid: str(r.get("version") or "")
               for sid, r in rows_ledger.items() if r.get("status") == INSTALLED}
    counts = {
        "specs": len(A.SPECS), "attempted": len(attempted),
        "installed_total": len(modules),
        "installed_this_pass": sum(1 for r in attempted if r.get("status") == INSTALLED),
        "permanently_unavailable": sum(1 for r in rows_ledger.values()
                                       if r.get("status") == PERMANENT),
        "retryable": sum(1 for r in rows_ledger.values() if r.get("status") == RETRYABLE),
        "no_distribution_pinned": sum(1 for r in rows_ledger.values()
                                      if r.get("status") == NO_PIN),
        "skipped": len(skipped),
    }
    doc = {
        "at": now(), "seconds": round(time.monotonic() - t0, 1), "budget_s": budget_s,
        "generator": GENERATOR, "law": LAW, "dry_run": dry_run,
        "shared_venv": {"python": str(py), "why": venv_why,
                        "free_disk_mb": free_disk_mb(root),
                        "disk_need_mb": DISK_NEED_MB},
        "attempted": attempted, "skipped": skipped, "licence_reads": licence_reads,
        "counts": counts,
        "permanently_unavailable": [
            {"system": s, "requirement": r.get("requirement"), "why": r.get("why"),
             "error": str(r.get("error") or "")[:300], "cover": r.get("cover")}
            for s, r in sorted(rows_ledger.items()) if r.get("status") == PERMANENT],
        "consumers": list(CONSUMERS),
        "rule": ("one shared venv over the desk's own interpreter; ROI order; a final pip "
                 "failure is recorded once with its exact error and never retried, and its "
                 "capability is covered by a fallback or a REBUILT task"),
    }
    if not dry_run:
        _write(ledger_path, {"at": doc["at"], "generator": GENERATOR, "counts": counts,
                             "systems": rows_ledger})
        _write(root / SB.SHARED_ID / "modules.json",
               {"at": doc["at"], "python": str(py), "modules": modules})
        if licence_reads:
            fed_state["systems"] = {**{str(k): dict(v) for k, v in
                                       (fed_state.get("systems") or {}).items()
                                       if isinstance(v, dict)}, **fed_rows}
            fed_state.setdefault("at", doc["at"])
            _write(fed_state_path, fed_state)
        _write(report_path, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--max-installs", type=int, default=None)
    ap.add_argument("--only", default="", help="comma-separated system ids")
    ap.add_argument("--force", action="store_true", help="retry rows the ledger has settled")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=None)
    a = ap.parse_args(argv)
    doc = provision_pass(budget_s=a.budget_s, max_installs=a.max_installs,
                         only=[s for s in a.only.split(",") if s] or None,
                         force=a.force, dry_run=a.dry_run,
                         root=Path(a.root) if a.root else None)
    c = doc["counts"]
    print(f"sandbox provision: +{c['installed_this_pass']} this pass | {c['installed_total']}/"
          f"{c['specs']} importable | permanent {c['permanently_unavailable']} | retryable "
          f"{c['retryable']} | unpinned {c['no_distribution_pinned']} | {doc['seconds']}s")
    return 0


if __name__ == "__main__":
    _ = timedelta
    raise SystemExit(main())
