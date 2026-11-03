#!/usr/bin/env python3
"""One tree's half of replay-shadow's RESEARCH REACH: the allocator on the pinned slice, traced.

Started by ops/release/research_reach.py as `python -I research_child.py <tree> <slice> <spec.json>
<out.json>` from an empty working directory, once per tree. It builds a sandbox holding ONLY the
tree's Python (libs/ and desks/mt5/, never a data, report or test directory) with the pinned slice
laid over it, so both trees read exactly the same inputs and nothing the PR's tree carries as data
reaches the run. Then it runs the capital allocator (`research.pf_allocator.run`) once, with no
terminal, no network and a fixed seed, and writes:

- `money`: what the allocator decided (the book, the heat, the trade verdict), compared field by
  field against the other tree by the parent;
- `hits`: for each target file, every line executed inside a FUNCTION frame that was not running
  as part of an import. Module and class bodies never count, and neither does any frame whose
  caller chain passes through a module body (an import, or a comprehension evaluated at import):
  importing a file proves nothing about the change in it (#600 audit condition 1).

The slice is verified against its own manifest and against the digest the parent passes from the
base checkout's research_reach.SLICE_SHA256. A mismatch ends the run before anything executes.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import json
import os
import shutil
import socket
import sys
import time
import traceback
from pathlib import Path
from typing import Any

#: The tree's code that the sandbox copies: these roots, Python only.
CODE_ROOTS = ("libs", "desks/mt5")
#: Never copied, at any depth: data, reports and tests are inputs or harness, never code.
PRUNE = frozenset({"data", "reports", "tests", "__pycache__", ".git", "node_modules"})
MANIFEST = "SLICE.sha256"
CO_OPTIMIZED = 0x0001  # a function's code object; module and class bodies lack it


def slice_digest(slice_dir: Path) -> tuple[str, list[tuple[str, str]]]:
    """(sha256 of the manifest's bytes, [(sha, path)]); raises if any listed file differs."""
    raw = (slice_dir / MANIFEST).read_bytes()
    rows = []
    for ln in raw.decode("utf-8").splitlines():
        if not ln.strip():
            continue
        sha, rel = ln.split(None, 1)
        rel = rel.strip()
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise ValueError(f"slice path {rel!r} leaves the slice")
        got = hashlib.sha256((slice_dir / rel).read_bytes()).hexdigest()
        if got != sha:
            raise ValueError(f"slice file {rel} hashes {got}, the manifest pins {sha}")
        rows.append((sha, rel))
    listed = {rel for _, rel in rows}
    extra = sorted(
        p.relative_to(slice_dir).as_posix()
        for p in slice_dir.rglob("*")
        if p.is_file() and p.name != MANIFEST and p.name != "README.md"
        and p.relative_to(slice_dir).as_posix() not in listed
    )  # fmt: skip
    if extra:
        raise ValueError(f"slice files the manifest does not pin: {extra}")
    return hashlib.sha256(raw).hexdigest(), rows


def build_sandbox(tree: Path, slice_dir: Path, rows: list[tuple[str, str]], root: Path) -> None:
    for top in CODE_ROOTS:
        src_top = tree / top
        for dirpath, dirnames, filenames in os.walk(src_top):
            dirnames[:] = [d for d in dirnames if d not in PRUNE]
            for fn in filenames:
                if fn.endswith(".py"):
                    src = Path(dirpath) / fn
                    dst = root / src.relative_to(tree)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
    now = time.time()
    for _, rel in rows:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(slice_dir / rel, dst)
        os.utime(dst, (now, now))  # a cache the allocator would otherwise call stale


class _NoTerminal(importlib.abc.MetaPathFinder):
    """MetaTrader5 is never importable here, whatever the runner has installed."""

    def find_spec(self, name: str, path: Any = None, target: Any = None) -> None:
        if name == "MetaTrader5" or name.startswith("MetaTrader5."):
            raise ImportError("no terminal in research reach")


def _no_network(*_a: Any, **_k: Any) -> None:
    raise OSError("no network in research reach")


def main(tree: Path, slice_dir: Path, spec: dict[str, Any], out_path: Path) -> int:
    digest, rows = slice_digest(slice_dir)
    if digest != spec["slice_sha256"]:
        raise ValueError(f"slice manifest hashes {digest}, the base pins {spec['slice_sha256']}")
    root = Path.cwd() / "sandbox"
    build_sandbox(tree, slice_dir, rows, root)
    sys.meta_path.insert(0, _NoTerminal())
    socket.socket.connect = _no_network  # type: ignore[method-assign]
    socket.create_connection = _no_network  # type: ignore[assignment]
    desk = root / "desks" / "mt5"
    sys.path[:0] = [str(root), str(desk), str(desk / "research")]

    prefix = str(root) + os.sep
    targets = {str(root / t) for t in spec.get("targets") or []}
    hits: dict[str, set[int]] = {}

    def import_time(frame: Any) -> bool:
        f = frame
        while f is not None:
            code = f.f_code
            if not code.co_flags & CO_OPTIMIZED and code.co_filename.startswith(prefix):
                return True  # a module or class body of the sandbox is on the stack
            f = f.f_back
        return False

    def tracer(frame: Any, event: str, arg: Any) -> Any:
        code = frame.f_code
        if code.co_filename not in targets or not code.co_flags & CO_OPTIMIZED:
            return None
        if import_time(frame.f_back):
            return None
        seen = hits.setdefault(code.co_filename, set())
        seen.add(frame.f_lineno)

        def lines(fr: Any, ev: str, a: Any) -> Any:
            if ev == "line":
                seen.add(fr.f_lineno)
            return lines

        return lines

    err = None
    doc: dict[str, Any] = {}
    sys.settrace(tracer)
    try:
        from research import pf_allocator

        doc = pf_allocator.run("fast", seed=0)
    except Exception as exc:  # the run's verdict IS the exception: compared, not hidden
        err = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        sys.settrace(None)
    imported = sorted(
        Path(m.__file__).resolve().relative_to(root.resolve()).as_posix()
        for m in list(sys.modules.values())
        if getattr(m, "__file__", None)
        and str(Path(m.__file__).resolve()).startswith(str(root.resolve()) + os.sep)
    )
    text = json.dumps(
        {
            "slice_sha256": digest,
            "error": err,
            "doc": doc,
            "hits": {Path(f).relative_to(root).as_posix(): sorted(v) for f, v in hits.items()},
            "imported": imported,
        },
        default=str,
    )
    # sandbox paths differ per run and per tree; they are never a decision
    out_path.write_text(text.replace(json.dumps(str(root))[1:-1], "<sandbox>"), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(
            Path(sys.argv[1]).resolve(),
            Path(sys.argv[2]).resolve(),
            json.loads(Path(sys.argv[3]).read_text("utf-8")),
            Path(sys.argv[4]),
        )
    )
