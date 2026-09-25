#!/usr/bin/env python3
"""THE SWALLOWED-WRITE FENCE -- a write that fails silently is a write that never happened.

    python scripts/check_bare_excepts.py [--json] [--all] [--fix-list]

WHY THIS EXISTS, in two of the eight silent failures of 2026-09-23:

    failure 5   the registry verdict sync died inside a 28 MB file at the FRONT of every pass,
                wrote no cursor, and stranded 3,368 verdicts. Nothing was logged, because the
                write sat inside a handler whose whole body was `pass`.
    failure 7   preregistration is dead desk-wide: `register` raises, `donate` swallows it in a
                BARE EXCEPT, and 0 of 107 sampled donation rows carry a `prereg_hash`.

Both are the same shape as the write-or-explain contract's SILENT_NO_OP, one layer down: an
exception that carried the only evidence the write failed was caught and discarded, so the organ
reported success and the artifact simply was not there.

WHAT COUNTS AS A SWALLOWED WRITE. All three must hold, which is what keeps this off the ~2,000
defensive handlers in the tree that are none of its business:

    1. the handler is BLIND      -- `except:` bare, or `except Exception`/`BaseException` with no
                                    `as exc` binding, so the error object is not even reachable
    2. the handler is MUTE       -- its body is only `pass` / `continue` / a bare `return` / `...`
                                    (a handler that logs, re-raises, records a defect or returns a
                                    reason is doing its job and is not counted)
    3. the try body WRITES       -- it calls a write or a donation on the paths this fence owns

SCOPE IS DELIBERATELY NARROW (the brief: "stay on the paths that hide a missing artifact").
Default scope is the artifact-writing and donation surface; `--all` widens to the whole tree for
a session that wants the full picture, and is not what the gate runs.

Exit: 2 when any swallowed write is found in scope; 0 clean. `--fix-list` prints one
`path:line` per finding for a session to work through.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import FAIL, fence_exit  # noqa: E402

_PASSING = frozenset({"CLEAN"})

#: The directories that hold artifact-writing and donation code.
SCOPE: tuple[str, ...] = ("libs", "desks/mt5/research", "desks/mt5/ops", "scripts",
                          "desks/mt5/side_channels", "desks/mt5/frontier_intel")
#: Directories never scanned: vendored code, tests that assert on swallowing, and debris.
SKIP_PARTS: frozenset[str] = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__",
                                        "scratch", "site-packages", "build", "dist", "_retired"})

#: Calls that PUT BYTES ON DISK. Deliberately does NOT include `append`, `save`, `write`,
#: `commit` or `flush` on their own: measured 2026-09-23, three of the first four `append()` hits
#: were `list.append` inside an optional-import guard, which is a handler doing its job. A fence
#: whose findings are mostly noise gets switched off (L1.43), so the list is the unarguable half.
_WRITE_ATTRS: frozenset[str] = frozenset({
    "write_text", "write_bytes", "writelines", "savez", "savez_compressed",
    "mkdir", "touch", "fsync", "atomic_write", "write_json", "save_json", "dump_json",
})
#: Names that mean a filesystem write ONLY IN THE RIGHT CALL SHAPE. Measured 2026-09-23:
#: `rename` and `to_json` matched pandas (`df.rename(columns=...)`, `dc.to_json()` returning a
#: string) and `replace` matched `str.replace(a, b)` -- four findings, none of them a write. The
#: shape separates them cleanly: `Path.replace(target)` / `Path.rename(target)` take exactly ONE
#: positional argument and no keywords, and `frame.to_csv(path)` needs a path to write to at all.
_PATH_MOVE: frozenset[str] = frozenset({"replace", "rename"})
_NEEDS_PATH_ARG: frozenset[str] = frozenset({"to_json", "to_csv", "to_parquet"})
#: `json.dump(obj, fh)` and `open(p, "w")` -- the two that need their arguments read.
_DUMP_NAMES: frozenset[str] = frozenset({"dump", "open"})
#: DONATION AND RECORDING calls: the second half of the brief. A donation that fails silently is
#: an artifact that never reaches the compiler, and `register` raising inside `donate`'s bare
#: except is failure 7 exactly.
_DONATE_FUNCS: frozenset[str] = frozenset({
    "donate", "register", "emit", "record", "publish", "persist", "close_run",
})


def _is_blind(handler: ast.ExceptHandler) -> bool:
    """A handler with no usable error object: bare, or broad with no `as` binding."""
    if handler.name:
        return False
    if handler.type is None:
        return True                                   # bare `except:`
    names: list[str] = []
    for node in ast.walk(handler.type):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    return bool(names) and all(n in {"Exception", "BaseException"} for n in names)


def _is_mute(handler: ast.ExceptHandler) -> bool:
    """A handler that says nothing anywhere: only pass / continue / bare return / ellipsis."""
    for stmt in handler.body:
        if isinstance(stmt, (ast.Pass, ast.Continue)):
            continue
        if isinstance(stmt, ast.Return) and (stmt.value is None
                                             or (isinstance(stmt.value, ast.Constant)
                                                 and stmt.value.value is None)):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                and stmt.value.value is Ellipsis:
            continue
        return False
    return True


def _opens_for_write(node: ast.Call) -> bool:
    """`open(p, "w")` / `open(p, mode="a")`. A read-mode open is not a write and never counts."""
    modes = [a for a in node.args[1:2] if isinstance(a, ast.Constant)]
    modes += [k.value for k in node.keywords
              if k.arg == "mode" and isinstance(k.value, ast.Constant)]
    return any(isinstance(m, ast.Constant) and isinstance(m.value, str)
               and any(c in m.value for c in "wax+") for m in modes)


def _writes(body: list[ast.stmt]) -> tuple[str, str]:
    """(kind, call) for the first write or donation in this try body; ("", "") if neither.

    `kind` is FILE_WRITE (bytes to disk) or DONATION (a row offered to another organ). They are
    reported apart because they fail differently: a swallowed FILE_WRITE loses an artifact, a
    swallowed DONATION loses the row before any artifact was ever going to exist.
    """
    for stmt in body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else "")
            if not name:
                continue
            if name in _WRITE_ATTRS:
                return "FILE_WRITE", name
            if (name in _PATH_MOVE and len(node.args) == 1 and not node.keywords
                    # ...and the target is not a STRING LITERAL. `tmp.replace(dest)` names a
                    # variable or a Path expression; `series.rename("net")` names a column.
                    and not (isinstance(node.args[0], ast.Constant)
                             and isinstance(node.args[0].value, str))):
                return "FILE_WRITE", name
            if name in _NEEDS_PATH_ARG and node.args:
                return "FILE_WRITE", name
            if name in _DUMP_NAMES:
                if name == "open" and not _opens_for_write(node):
                    continue
                return "FILE_WRITE", name
            if name in _DONATE_FUNCS:
                return "DONATION", name
    return "", ""


def scan_file(path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return []
    found: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        kind, wrote = _writes(node.body)
        if not kind:
            continue
        for handler in node.handlers:
            if _is_blind(handler) and _is_mute(handler):
                found.append({
                    "file": path.relative_to(_ROOT).as_posix(), "line": handler.lineno,
                    "kind": kind, "writes": wrote,
                    "handler": "bare except:" if handler.type is None else "except Exception:",
                    "why": (f"a {wrote}() in this try body can fail and the handler discards the "
                            f"error without logging, recording or re-raising it"),
                })
    return found


def _files(all_paths: bool) -> list[Path]:
    roots = [_ROOT] if all_paths else [_ROOT / p for p in SCOPE]
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if SKIP_PARTS & set(p.parts):
                continue
            out.append(p)
    return sorted(set(out))


def build_report(*, all_paths: bool = False) -> dict[str, Any]:
    files = _files(all_paths)
    findings: list[dict[str, Any]] = []
    for path in files:
        findings.extend(scan_file(path))
    by_file: dict[str, int] = {}
    for f in findings:
        by_file[f["file"]] = by_file.get(f["file"], 0) + 1
    n_write = sum(1 for f in findings if f["kind"] == "FILE_WRITE")
    n_donate = len(findings) - n_write
    rep: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "scope": "ALL" if all_paths else list(SCOPE),
        "files_scanned": len(files), "scanned": len(files),
        "n_swallowed_writes": len(findings),
        "n_file_write": n_write, "n_donation": n_donate,
        "worst_files": sorted(by_file.items(), key=lambda kv: -kv[1])[:15],
        "findings": findings,
        "status": "CLEAN" if not findings else "SWALLOWED",
    }
    rep["detail"] = (
        f"{len(findings)} blind-and-mute handler(s) across {len(by_file)} file(s) "
        f"({n_write} around a FILE_WRITE, {n_donate} around a DONATION), "
        f"out of {len(files)} files scanned"
        if findings else f"no swallowed writes in {len(files)} files")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="scan the whole tree, not just the "
                                                       "artifact-writing and donation surface")
    ap.add_argument("--fix-list", action="store_true", help="print path:line per finding")
    ap.add_argument("--file-writes-only", action="store_true",
                    help="gate on FILE_WRITE findings only (the class the audit took to zero); "
                         "DONATION findings are still reported, never silenced")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args(argv)
    rep = build_report(all_paths=bool(a.all))
    if a.file_writes_only:
        # A ONE-WAY RATCHET, NOT A LOWERED BAR (L1.50). The audit cleared every FILE_WRITE
        # swallower on 2026-09-23, so that class is fenced AT ZERO and any new one reddens the
        # gate immediately. The 25 DONATION findings stay in the report and in the count -- they
        # are not silenced, they are simply not this ratchet's population, because dumping them
        # red into a lane another builder owns is how a fence gets switched off (L1.43).
        rep["gated_on"] = "FILE_WRITE"
        rep["status"] = "CLEAN" if rep["n_file_write"] == 0 else "SWALLOWED"
        rep["detail"] = (
            f"{rep['n_file_write']} swallowed FILE_WRITE(s) -- the gated class; "
            f"{rep['n_donation']} DONATION finding(s) reported and not gated")
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    elif a.fix_list:
        for f in rep["findings"]:
            print(f"{f['file']}:{f['line']}  ({f['handler']} around {f['writes']}())")
    else:
        print(f"swallowed writes: {rep['status']} -- {rep['detail']}")
        for f in rep["findings"][:25]:
            print(f"  SWALLOWED {f['kind']:<10} {f['file']}:{f['line']} {f['handler']} around {f['writes']}()")
        if len(rep["findings"]) > 25:
            print(f"  ... and {len(rep['findings']) - 25} more (--fix-list for all)")
    if a.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING, fail=FAIL, scanned=rep["scanned"],
                      of="python files on the write/donation surface",
                      fence="check_bare_excepts.py")


if __name__ == "__main__":
    raise SystemExit(main())
