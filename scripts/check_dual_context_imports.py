"""A module imported two ways must import two ways. Find every one that does not.

WHY THIS EXISTS (measured three times on 2026-08-29)

This desk imports the same modules under two different names:

    VPS checks       import them as `research.edge_search`, `mt5desk.family_inputs`
    the trading box  puts `desks/mt5/research` and `desks/mt5` DIRECTLY on sys.path and
                     imports them top-level, so `__package__` is ""

A relative import (`from .carry_state import ...`) has no parent package to resolve against in
the second case and raises ModuleNotFoundError. The module imports perfectly here and fails on
the box that trades -- which is the worst possible place for the difference to appear, because
the VPS's own tests all pass.

THREE TIMES, EACH COSTING REAL EVIDENCE:

    family_inputs           34 forward clocks blocked at once
    shadow_admission.run_key  reported 34 of 35 certificates as having no clock
    edge_search.carry_state   SEVEN EURCHF sleeves blocked from gathering any evidence,
                              wearing a stale error that named the wrong module entirely

The pattern is always the same and the fix is always the same: try the package form, fall back
to the bare form. So the fix is not another patch, it is this check.

WHAT COUNTS AS DUAL-CONTEXT. A module under a directory that something puts on sys.path directly
AND that lives inside a package. Those are exactly the files that can be reached both ways, and
they are the only ones where a single-form import is a latent box-only failure.

WHY IT DOES NOT AUTO-FIX. Rewriting an import changes what a module binds at runtime, and a
wrong rewrite fails in the same box-only way it is meant to prevent. It reports with the exact
replacement text; a human applies it once and the fence keeps it fixed.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dual_context_imports.json"

#: Directories something puts on sys.path DIRECTLY, so their modules are importable top-level as
#: well as through their package. Sourced from the real `sys.path.insert` calls in the tree.
_DUAL_ROOTS = (
    "desks/mt5",
    "desks/mt5/research",
    "desks/mt5/mt5desk",
    "scripts",
)


def _relative_imports(path: Path) -> list[tuple[int, str, str]]:
    """(lineno, module, names) for every `from .x import y` in this file."""
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except (OSError, SyntaxError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
            mod = node.module or ""
            names = ", ".join(a.name for a in node.names)
            out.append((node.lineno, mod, names))
    return out


def _already_guarded(src: str, lineno: int) -> bool:
    """Is this relative import already inside a try/except ImportError?

    Read the surrounding lines rather than the AST: the guard is idiomatically a `try:` two lines
    above with an `except ImportError` below, and matching that text is both simpler and harder
    to get subtly wrong than reconstructing scope from the tree.
    """
    lines = src.splitlines()
    lo, hi = max(0, lineno - 4), min(len(lines), lineno + 4)
    window = "\n".join(lines[lo:hi])
    return "try:" in window and "ImportError" in window


def main() -> int:
    now = datetime.now(tz=UTC)
    offenders: list[dict[str, Any]] = []
    checked = 0

    for root in _DUAL_ROOTS:
        base = ROOT / root
        if not base.exists():
            continue
        # Only files DIRECTLY under a dual root are importable top-level from it; a file in a
        # subdirectory is not reachable as a bare module name and cannot hit this failure.
        for path in sorted(base.glob("*.py")):
            if path.name == "__init__.py":
                continue
            checked += 1
            try:
                src = path.read_text("utf-8")
            except OSError:
                continue
            for lineno, mod, names in _relative_imports(path):
                if _already_guarded(src, lineno):
                    continue
                rel = str(path.relative_to(ROOT))
                offenders.append({
                    "file": rel, "line": lineno, "module": mod, "names": names,
                    "fix": (f"try:\n    from .{mod} import {names}\n"
                            f"except ImportError:\n    from {mod} import {names}"),
                    "why": (f"{rel} sits under {root}, which something puts on sys.path directly, "
                            f"so it is imported BOTH as a package member and top-level. When "
                            f"top-level, __package__ is '' and this relative import raises "
                            f"ModuleNotFoundError on the box while passing every test here."),
                })

    report = {"checked_at": now.isoformat(timespec="seconds"),
              "modules_checked": checked, "offenders": offenders}
    OUT.write_text(json.dumps(report, indent=1), "utf-8")

    print(f"DUAL-CONTEXT IMPORTS {now.isoformat(timespec='seconds')}")
    print(f"  {checked} module(s) under dual-import roots checked")
    if not offenders:
        print("  every relative import in a dual-context module is guarded")
    else:
        print(f"\n  UNGUARDED ({len(offenders)}) -- these import here and fail on the box:")
        for o in offenders[:12]:
            print(f"    {o['file']}:{o['line']}  from .{o['module']} import {o['names']}")
        print("\n  Apply the try/except ImportError form; the exact text is in the artifact.")
    print(f"  -> {OUT}")
    return 1 if offenders else 0


if __name__ == "__main__":
    raise SystemExit(main())
