#!/usr/bin/env python3
"""HUNT THE UNWIRED, EVERY DAY, SO NOBODY HAS TO REMEMBER (III.16).

THE CLASS THIS EXISTS FOR. A public function that is written, tested, correct -- and CALLED BY
NOTHING. It is invisible to every instrument the desk already runs: ruff sees valid code, mypy sees
valid types, the suite sees green tests, and a module count sees a module. The only question that
separates an unwired capability from a working one is WHAT RAN IT, and that question is never asked
by accident.

MEASURED IN ONE DAY, all four found by hand and none by any check:

    auto_promotion.decide()          ruled on whether a candidate gets LIVE CAPITAL -- zero callers
                                     on the day capital was being deposited
    capital_basis.declare()          the fence named it in its own error message; no producer imported it
    information rate / regime_penalty no callers outside their own module, so every clock sat at
                                     half rate for a fact nobody had measured
    run_golive_preflight             built and wired to nothing, in the session that criticised
                                     exactly this pattern

WHAT IT DOES NOT CLAIM. This is a CALL-SITE scan, not a proof of reachability. Dynamic dispatch,
getattr, and registries that call by string all defeat it, so a name reported here may be reached
by a path the scan cannot see. That is why the output is a RANKED SUSPICION with the evidence
attached, and why `--fail` is opt-in: a hunter that blocked a push on a false positive would be
switched off within a week, and then the real instances come back with the alarm already disabled.

THE ASYMMETRY IT RELIES ON. A false positive costs one person one minute of reading. A false
negative costs a capability that silently does nothing -- and on the promotion path, that is a desk
that believes it is automated and is not. So it is tuned to over-report and say so.

    python scripts/check_unwired_capability.py            # report
    python scripts/check_unwired_capability.py --fail     # non-zero when suspects exist
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_OUT = Path("data/unwired_capability.json")
_WEB = Path("web/unwired_capability.json")

#: Names whose absence from a call site says nothing. Dunders, and the conventional entry points
#: every organ defines and the cycle invokes by path rather than by import.
_EXEMPT_NAMES = frozenset({"main", "run", "build", "register", "setup"})

#: Packages whose members are legitimately called by string, by a registry or by a framework, so a
#: call-site scan cannot see them. Named rather than silently skipped: an exemption nobody can read
#: is indistinguishable from a bug.
_EXEMPT_PKGS: dict[str, str] = {
    "libs.ict": "detectors registered into a feature registry and invoked by name",
    "libs.data": "adapters selected by configuration string",
}


def _public_defs(py: Path) -> list[tuple[str, int]]:
    """Public top-level functions in a module: (name, lineno). Underscore names are private and a
    private helper with no caller is dead code rather than an unwired capability -- a different and
    much cheaper defect."""
    try:
        tree = ast.parse(py.read_text("utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return []
    return [(n.name, n.lineno) for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_") and n.name not in _EXEMPT_NAMES]


def _called_names(py: Path) -> set[str]:
    """Every name this file CALLS or imports. Imports count: importing a symbol without calling it
    is still a wire in progress, and reporting it would flood the output with false suspicion."""
    try:
        tree = ast.parse(py.read_text("utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return set()
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                out.add(a.asname or a.name)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)          # attribute ACCESS counts: a value read is a use
    return out


def scan(root: Path) -> dict[str, Any]:
    scripts = sorted((root / "scripts").rglob("*.py"))
    libs = sorted((root / "libs").rglob("*.py"))
    tests = sorted((root / "tests").rglob("*.py"))

    # THE LIVE SURFACE IS scripts/ AND libs/, NEVER tests/. A capability called only by its own
    # test is the exact defect being hunted: green, correct, and reaching nothing. Tests are read
    # separately so the report can say "tested but unwired", which is the most common shape.
    live_calls: set[str] = set()
    for py in scripts + libs:
        live_calls |= _called_names(py)
    test_calls: set[str] = set()
    for py in tests:
        test_calls |= _called_names(py)

    suspects: list[dict[str, Any]] = []
    for py in libs:
        mod = str(py.relative_to(root))[:-3].replace("/", ".")
        skip = next((why for pkg, why in _EXEMPT_PKGS.items() if mod.startswith(pkg)), None)
        if skip:
            continue
        for name, line in _public_defs(py):
            if name in live_calls:
                continue
            suspects.append({
                "module": str(py.relative_to(root)),
                "name": name,
                "line": line,
                "tested": name in test_calls,
                "why": ("public, and called from no file under scripts/ or libs/. "
                        + ("Its TEST calls it, which is the most common shape of this defect: "
                           "green, correct, and reaching nothing."
                           if name in test_calls else
                           "Nothing calls it anywhere, including its own tests.")),
            })

    # TESTED-BUT-UNWIRED FIRST. Something with a test is something somebody meant to finish, which
    # makes it likelier to be a real dropped wire than an abandoned draft.
    suspects.sort(key=lambda s: (not s["tested"], s["module"], s["name"]))
    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "n_suspects": len(suspects),
        "n_tested_but_unwired": sum(1 for s in suspects if s["tested"]),
        "exempt_packages": _EXEMPT_PKGS,
        "suspects": suspects,
        "note": ("A CALL-SITE SCAN, not a reachability proof: dynamic dispatch, getattr and "
                 "string-keyed registries defeat it, so a name here may be reached by a path the "
                 "scan cannot see. Tuned to OVER-REPORT deliberately -- a false positive costs one "
                 "minute of reading, a false negative costs a capability that silently does "
                 "nothing, and on the promotion path that is a desk which believes it is automated "
                 "and is not (III.16)."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fail", action="store_true",
                    help="exit non-zero when suspects exist (opt-in: a hunter that blocks a push "
                         "on a false positive gets switched off, and then the real instances "
                         "return with the alarm already disabled)")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    rep = scan(_ROOT)
    for p in (_OUT, _WEB):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, indent=1), "utf-8")

    print(f"unwired-capability (III.16): {rep['n_suspects']} suspect(s), "
          f"{rep['n_tested_but_unwired']} TESTED but unwired")
    for s in rep["suspects"][:args.limit]:
        flag = "TESTED " if s["tested"] else "       "
        print(f"  {flag} {s['module']}:{s['line']}  {s['name']}()")
    if rep["n_suspects"] > args.limit:
        print(f"  ... {rep['n_suspects'] - args.limit} more in {_OUT}")
    print(f"-> {_OUT} and {_WEB}")
    return 1 if (args.fail and rep["n_suspects"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
