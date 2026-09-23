"""SUPERSEDED COPY -- the live projection is `desks/mt5/research/portfolio_projection.py`.

This file is a stale duplicate. Nothing imports it, nothing schedules it, and it has diverged:
the live module grew `build_sleeves()` and `build_daily()` (which `research/orthogonality.py`
imports) and this copy never did. Its history is one commit plus a fix applied to it by mistake;
the live one carries the VPS's hourly `mt5 desk hourly sync` commits.

**IT WAS ALSO BROKEN IN A WAY THAT LOOKED LIKE THE LIVE FILE'S BUG, AND THAT COST A ROUND TRIP.**
`BASE = Path(__file__).resolve().parent.parent` is correct from `research/` and resolves to
`desks/` from here, so this copy died on its first data read while the live one ran fine. Reading
the failure here and concluding "the projection is unrunnable" was wrong, and the correction is
the point of this file: a duplicate at the wrong depth reproduces a path bug that does not exist
in the original.

Six files sit at both depths (`mech_battery`, `mech_split`, `portfolio_projection`,
`run_gateway_loop`, `run_hunt11`, `run_hunt12`); `run_hunt12` diverges most -- the missing-import
repair of 2026-08-19 landed in `research/` only. Rowed as GAP 116 for a proper sweep rather than
deleted here, because deleting six tracked files is not this change's business.

Refusing rather than running: a stale duplicate that still executes is the trap. One that names
its replacement is a signpost.
"""

from __future__ import annotations

import sys

_LIVE = "desks/mt5/research/portfolio_projection.py"

if __name__ == "__main__":
    print(f"REFUSING: this is a superseded duplicate. The live projection is {_LIVE}.\n"
          "  cd desks/mt5 && python research/portfolio_projection.py\n"
          "It needs reports/hunt12_partial.json, which is gitignored and absent on both this "
          "clone and the VPS -- regenerate it with `python research/run_hunt12.py` first, and "
          "note that run_hunt12 was itself dead with a missing import until 2026-08-19.",
          file=sys.stderr)
    raise SystemExit(2)
