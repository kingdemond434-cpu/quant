#!/usr/bin/env python3
"""One tree's half of the replay shadow's ALLOCATOR LEG: run desks/mt5/research/pf_allocator.py
over a frozen, synthetic evidence snapshot and write the book it decides.

Started by ops/release/replay_shadow.py as `python -I replay_allocator.py <tree> <fixture.json>
<out.json>` from an empty working directory, once on the base tree and once on the PR's, only
when a PR changes the allocator. It imports `pf_allocator` from <tree>, points every path the
tree's modules hold under <tree> into a sandbox in the working directory (so the two trees never
share a file and nothing is written into either tree), writes the fixture's daily-R matrix where
the fast clock reads its evidence cache, and runs `run("fast", seed=0)`. MetaTrader5 is made
unimportable, so the margin reader can never reach a terminal.

It records every line of pf_allocator.py the pass executed, so the parent can say whether the
lines a PR changed were ever run: an identical book from code that never ran is not a measurement.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import json
import sys
import threading
import types
from pathlib import Path
from typing import Any

ALLOCATOR = "desks/mt5/research/pf_allocator.py"


def main(tree: Path, fixture: dict[str, Any], out_path: Path) -> int:
    tree = tree.resolve()
    box = Path.cwd().resolve() / "sandbox"
    desk = tree / "desks" / "mt5"
    sys.path[:0] = [str(desk), str(desk / "research"), str(tree)]
    sys.modules["MetaTrader5"] = None  # type: ignore[assignment]  # import raises: no terminal

    def reroot(mod: types.ModuleType) -> None:
        for k, v in list(vars(mod).items()):
            if isinstance(v, Path) and v.is_absolute():
                try:
                    rel = v.resolve().relative_to(tree)
                except (ValueError, OSError):
                    continue
                setattr(mod, k, box / rel)

    class Sandboxed(importlib.abc.MetaPathFinder):
        """Every module loaded from <tree> has its module-level paths re-rooted once loaded."""

        def find_spec(self, name: str, path: Any, target: Any = None) -> Any:
            spec = importlib.machinery.PathFinder.find_spec(name, path)
            if spec is None or not spec.origin or spec.loader is None:
                return spec
            if not str(spec.origin).startswith(str(tree) + "/"):
                return spec
            loader: Any = spec.loader
            run_module = loader.exec_module

            def exec_module(m: types.ModuleType) -> None:
                run_module(m)
                reroot(m)

            loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, Sandboxed())

    import pandas as pd

    ev = fixture["daily_r"]
    cache = box / "desks" / "mt5" / "data" / "pf_allocator_cache"
    cache.mkdir(parents=True)
    pd.DataFrame(ev["data"], index=ev["index"], columns=ev["columns"]).to_parquet(
        cache / "daily_r.parquet"
    )

    target = str(tree / ALLOCATOR)
    ran: set[int] = set()

    def lines(frame: Any, event: str, arg: Any) -> Any:
        if event == "line":
            ran.add(frame.f_lineno)
        return lines

    def calls(frame: Any, event: str, arg: Any) -> Any:
        if frame.f_code.co_filename == target:
            ran.add(frame.f_lineno)
            return lines
        return None

    sys.settrace(calls)
    threading.settrace(calls)
    doc: Any = None
    error = None
    try:
        import pf_allocator  # type: ignore[import-not-found]  # from <tree>, at run time

        doc = pf_allocator.run("fast", seed=int(fixture.get("seed", 0)))
    except Exception as exc:  # the parent judges it: UNMEASURED on the base, FAIL on the PR
        error = f"{type(exc).__name__}: {exc}"
    finally:
        sys.settrace(None)
        threading.settrace(None)  # type: ignore[arg-type,unused-ignore]
    imported = sorted(
        str(Path(f).resolve())
        for m in list(sys.modules.values())
        if (f := getattr(m, "__file__", None))
    )
    # the sandbox and the tree are where this run happened, never what it decided
    text = json.dumps({"doc": doc, "error": error}, default=str)
    text = text.replace(str(box), "<sandbox>").replace(str(tree), "<tree>")
    out = {**json.loads(text), "lines": sorted(ran), "imported": imported}
    out_path.write_text(json.dumps(out), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text("utf-8")), Path(sys.argv[3]))
    )
