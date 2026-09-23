"""ONE MINER SHAPE FOR A COUNTRY'S STRUCTURED DATA PLANE -- so a writer never runs on no clock.

MEASURED 2026-09-23, and the reason this file exists. Korea's `moat.build` -- the function that
WRITES the five moat stores -- had no caller on any clock, so `data/countries/kr/moat.json` had
never existed. Fixing Korea and stopping there would have missed the class: a sweep of all 71
country packages found THREE more with exactly that shape -- `ae`, `il` and `sa` each hold a
`data_plane.py` with a `run()` and a REPORT path, and NO `miners.py` at all, which is the one
thing `global_research_os` reads to find a country's own miners. None of AE_DATA_PLANE.json,
IL_DATA_PLANE.json or SA_DATA_PLANE.json existed on this box.

A writer with no clock is not a Korea problem. This module is the shared adapter so the three (and
any pack added later) reach the country lab through the same door the fifteen generic miners use,
and each country's `miners.py` is four lines rather than a copy of this one.

NO NETWORK BY DEFAULT: `no_fetch=True`, exactly as each data plane's own CLI defaults. A dry-run
context measures and writes nothing. A lane that cannot measure is reported by name, never hidden.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

UNMEASURED = "UNMEASURED"


def data_plane_miner(code: str, run: Callable[..., dict[str, Any]],
                     registry: Any, report: Any) -> Callable[..., dict[str, Any]]:
    """`MINERS['data_plane']` for one country pack.

    Accepts `(ctx)` (region_department) or `(pack, ctx)` (country_lab.load_custom_miners): the
    context is the LAST positional argument under both, which is the same trick `countries/kr`
    uses and for the same reason -- a department wired into one scheduler and inert under the
    other is a department that half-runs.
    """

    def mine(*args: Any, **kwargs: Any) -> dict[str, Any]:
        ctx = kwargs.get("ctx") if "ctx" in kwargs else (args[-1] if args else None)
        dry = bool(getattr(ctx, "dry_run", False))
        budget = float(getattr(ctx, "budget_s", 0.0) or 300.0)
        try:
            doc = run(budget_s=budget, no_fetch=True, dry_run=dry,
                      registry=registry, report_default=report)
        except Exception as exc:                      # pragma: no cover - a lane's own failure
            return {"agent": "data_plane", "region": code, "discoveries": [], "n_discoveries": 0,
                    "unmeasured": [{"what": f"{code}:data_plane", "verdict": UNMEASURED,
                                    "why": f"{type(exc).__name__}: {exc}"}],
                    "why": f"{code} data plane raised: {type(exc).__name__}"}
        lanes = doc.get("lanes") or []
        stored = sum(int(row.get("stored") or 0) for row in lanes if isinstance(row, dict))
        vintages = sum(int(row.get("vintages") or 0) for row in lanes if isinstance(row, dict))
        unmeasured = [u for row in lanes if isinstance(row, dict)
                      for u in (row.get("unmeasured") or [])]
        return {"agent": "data_plane", "region": code, "discoveries": [], "n_discoveries": 0,
                "unmeasured": unmeasured,
                "why": (f"{len(lanes)} lane(s), {stored} series stored, "
                        f"{vintages} vintage(s)"
                        + (" (dry run: nothing written)" if dry
                           else f" -> {getattr(report, 'name', report)}")),
                "lanes": lanes, "stored": stored, "vintages": vintages}

    mine.__name__ = f"mine_{code}_data_plane"
    mine.__qualname__ = mine.__name__
    return mine
