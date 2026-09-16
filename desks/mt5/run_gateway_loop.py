"""LEGACY ENTRY POINT -- delegates to `research/run_gateway_loop.py`. ONE wrapper, ONE lock rule.

MEASURED 2026-09-16. This file carried its own copy of the loop with a pid-less "locked" lock
that any later pass would steal after five minutes, while `research/run_gateway_loop.py` holds a
pid lock and respects a living holder. `gateway_resident.py` imported THIS copy by accident of
sys.path order and the per-minute task ran the other, so whenever a pass took more than five
minutes the two ran concurrently and the same signal bar was sent twice. Two wrappers cannot
disagree about the lock again if there is only one; this shim is what any old invoker now gets.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_RESEARCH = Path(__file__).resolve().parent / "research" / "run_gateway_loop.py"
_spec = importlib.util.spec_from_file_location("run_gateway_loop_research", _RESEARCH)
if _spec is None or _spec.loader is None:                       # pragma: no cover
    raise ImportError(f"cannot load {_RESEARCH}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

LOCK = _mod.LOCK
main = _mod.main

if __name__ == "__main__":
    main()
