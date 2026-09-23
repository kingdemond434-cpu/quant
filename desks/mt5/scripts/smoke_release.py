#!/usr/bin/env python3
"""Box-side smoke test: after every code arrival, before the next pass is trusted.

    python desks/mt5/scripts/smoke_release.py            # rc 1 on any failure
    python desks/mt5/scripts/smoke_release.py --json

WHY A SMOKE TEST ON THE BOX AT ALL. CI proves the suite on a Linux worker; the Windows box then
merges that code into a tree with hundreds of dirty artifacts, a different Python, and a
MetaTrader5 that only exists here. What actually arrived is a different question from what was
tested, and it has been answered wrong before: a `ModuleNotFoundError` that recorded no ticks for
five days, a hardcoded interpreter path that never launched anything and reported success. This
answers it in under twenty seconds, with no network:

    1. every money-path module byte-compiles (a syntax error found here is not found by the
       gateway at the next signal);
    2. every money-path module imports -- the gateway itself only where MetaTrader5 is
       importable, and it says so when it is not, rather than failing a Linux tree for being
       Linux;
    3. the release identity holds (mt5desk.release_identity) -- the box is running the code the
       release sealed, or it is not and new risk is refused;
    4. the signed judge manifest still matches the files it signed
       (scripts/check_immutable_evaluator.check, the same function the CI fence calls).

The report goes to reports/release_smoke.json {ok, sha, failures, skipped, checks, at}. Exit
status is non-zero on any failure, so the hourly cycle's record of this run is a number and not
a sentence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: Import name -> path. gateway.py first: it is the one that needs the broker library.
MODULES: tuple[tuple[str, str], ...] = (
    ("mt5desk.gateway", "desks/mt5/mt5desk/gateway.py"),
    # The gateway's decisions. This smoke skips importing `mt5desk.gateway` off Windows, so the
    # core is the ONLY part of the gateway's logic it can actually import there -- which makes it
    # the one money-path module this check can genuinely exercise on the VPS.
    ("mt5desk.decision_core", "desks/mt5/mt5desk/decision_core.py"),
    ("mt5desk.sizing", "desks/mt5/mt5desk/sizing.py"),
    ("mt5desk.gateway_config_fallback", "desks/mt5/mt5desk/gateway_config_fallback.py"),
    ("mt5desk.scalp_exec", "desks/mt5/mt5desk/scalp_exec.py"),
    ("mt5desk.netting", "desks/mt5/mt5desk/netting.py"),
    ("mt5desk.execution_policy", "desks/mt5/mt5desk/execution_policy.py"),
    ("mt5desk.execution_registry", "desks/mt5/mt5desk/execution_registry.py"),
    ("mt5desk.families", "desks/mt5/mt5desk/families.py"),
    ("mt5desk.engine", "desks/mt5/mt5desk/engine.py"),
    ("research.promoter", "desks/mt5/research/promoter.py"),
    ("research.shadow_forward", "desks/mt5/research/shadow_forward.py"),
    ("research.scalp_shadow", "desks/mt5/research/scalp_shadow.py"),
    ("research.pf_allocator", "desks/mt5/research/pf_allocator.py"),
    ("research.forward_verdict", "desks/mt5/research/forward_verdict.py"),
    ("research.sleeve_registry", "desks/mt5/research/sleeve_registry.py"),
)
BROKER_LIB = "MetaTrader5"
REPORT_REL = "desks/mt5/reports/release_smoke.json"
IMMUTABLE_SCRIPT = "scripts/check_immutable_evaluator.py"


def _compile_all(root: Path) -> tuple[list[dict[str, Any]], int]:
    """In-memory byte-compile: proves the source parses without writing a .pyc anywhere."""
    failures = []
    n = 0
    for _name, rel in MODULES:
        p = root / Path(*rel.split("/"))
        try:
            compile(p.read_bytes(), str(p), "exec")
            n += 1
        except (OSError, SyntaxError, ValueError) as exc:
            failures.append({"check": "compile", "module": rel,
                             "why": f"{type(exc).__name__}: {exc}"})
    return failures, n


def _import_all() -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    failures, skipped = [], []
    n = 0
    broker = importlib.util.find_spec(BROKER_LIB) is not None
    for name, rel in MODULES:
        if name == "mt5desk.gateway" and not broker:
            skipped.append({"check": "import", "module": name,
                            "why": f"{BROKER_LIB} is not importable on this host; gateway.py "
                                   f"byte-compiled only (the broker library exists on the "
                                   f"Windows box, nowhere else)"})
            continue
        try:
            importlib.import_module(name)
            n += 1
        except BaseException as exc:  # a SystemExit at import time is a failure too
            failures.append({"check": "import", "module": name, "path": rel,
                             "why": f"{type(exc).__name__}: {exc}"[:400]})
    return failures, skipped, n


def _identity(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from mt5desk import release_identity
        ident = release_identity.verdict(root=root).to_dict()
    except Exception as exc:
        ident = {"verdict": "UNMEASURED", "allows_new_risk": False,
                 "reason": f"release_identity failed: {type(exc).__name__}: {exc}"}
    if ident.get("allows_new_risk"):
        return [], ident
    return [{"check": "identity", "why": f"{ident.get('verdict')}: {ident.get('reason')}"}], ident


def _immutable(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The judge fence, by its own function. A breach that is ONLY a CRLF checkout of the same
    bytes is reported as such and not failed: the fence hashes raw bytes, the box converts line
    endings, and a smoke test that fails every hour for that reason is a smoke test nobody
    reads. The checker is loaded from THIS desk; the tree it checks is `root`."""
    path = ROOT / Path(*IMMUTABLE_SCRIPT.split("/"))
    spec = importlib.util.spec_from_file_location("check_immutable_evaluator", path)
    if spec is None or spec.loader is None:
        return [{"check": "immutable", "why": f"{IMMUTABLE_SCRIPT} not loadable"}], {}
    cie = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(cie)
        cie.ROOT = root
        cie.MANIFEST = root / "desks" / "mt5" / "data" / "IMMUTABLE_MANIFEST.json"
        findings = list(cie.check())
    except Exception as exc:
        return [{"check": "immutable", "why": f"{type(exc).__name__}: {exc}"}], {}
    try:
        signed = json.loads(cie.MANIFEST.read_text("utf-8")).get("files") or {}
    except (OSError, ValueError):
        signed = {}
    real, crlf_only = [], []
    for f in findings:
        rel = f.get("file", "")
        try:
            b = (root / Path(*rel.split("/"))).read_bytes()
        except OSError:
            real.append(f)
            continue
        if signed.get(rel) == hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16]:
            crlf_only.append(rel)
        else:
            real.append(f)
    out = {"ok": not real, "breaches": real, "crlf_only": crlf_only,
           "n_signed": len(signed)}
    return ([{"check": "immutable", "why": f"{len(real)} breach(es): "
              + "; ".join(f"{x.get('file')}: {x.get('why')}" for x in real[:4])}] if real else []
            ), out


def run(root: Path, out: Path | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    failures: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}

    c_fail, n_compiled = _compile_all(root)
    failures += c_fail
    checks["compile"] = {"ok": not c_fail, "n": n_compiled}

    i_fail, skipped, n_imported = _import_all()
    failures += i_fail
    checks["imports"] = {"ok": not i_fail, "n": n_imported, "skipped": len(skipped)}

    id_fail, ident = _identity(root)
    failures += id_fail
    checks["identity"] = ident

    im_fail, imm = _immutable(root)
    failures += im_fail
    checks["immutable"] = imm

    rep = {"ok": not failures, "sha": ident.get("running_sha"),
           "release_sha": ident.get("release_sha"), "failures": failures, "skipped": skipped,
           "checks": checks, "elapsed_s": round(time.monotonic() - t0, 3),
           "at": datetime.now(tz=UTC).isoformat(timespec="seconds")}
    target = out or (root / Path(*REPORT_REL.split("/")))
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    except OSError as exc:
        rep["report_write_error"] = f"{type(exc).__name__}: {exc}"
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="box-side release smoke test")
    ap.add_argument("--root", type=Path, default=ROOT,
                    help="repository root for the identity/immutable checks (modules always "
                         "import from this desk)")
    ap.add_argument("--out", type=Path, default=None, help="report path (default reports/)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = run(a.root.resolve(), a.out)
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        sha = str(rep.get("sha") or "?")[:12]
        print(f"release smoke {'OK' if rep['ok'] else 'FAILED'} sha={sha} "
              f"compiled={rep['checks']['compile']['n']} imported={rep['checks']['imports']['n']} "
              f"skipped={len(rep['skipped'])} identity={rep['checks']['identity'].get('verdict')} "
              f"immutable={'ok' if rep['checks']['immutable'].get('ok') else 'BREACH'} "
              f"in {rep['elapsed_s']}s")
        for s in rep["skipped"]:
            print(f"  skipped {s['module']}: {s['why']}")
        for f in rep["failures"]:
            print(f"  FAIL {f['check']} {f.get('module', '')}: {f['why']}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
