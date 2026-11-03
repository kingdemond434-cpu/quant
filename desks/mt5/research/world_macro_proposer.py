"""Mint `world_macro_state` cells from the world dataset hunter's series -- the hunter's consumer.

`world_dataset_hunter` ingests thousands of official statistics and maps each to the MT5
instruments it is about. This proposer turns that mapping into judged cells: for each
hypothesis-lane symbol (a rotating cursor, so the whole mapped universe is reached over hours),
for each series the hunter exposes to it (a stable core plus a daily rotating window), it runs
`family_world_macro_state` over a small declared grid (z band x direction x hold), screens every
variant net of the round trip with the shared proposer screen, deflates by everything it tried,
and donates one best variant per (symbol, series) through `proposer_common.donate`. From there
`miner_candidate_compiler` admits it as an EXACT_RECIPE (the family is in ORTHOGONAL_FAMILIES) and
the sealed gauntlet judges it: `build_cell` finds the family in `ORTHOGONAL_FAMILIES`, no input
branch touches it, and the family reloads its series from `series_key` on the recipe.

The screen is not the gauntlet: it only keeps the gauntlet from being handed every variant.

    python desks/mt5/research/world_macro_proposer.py --once --budget-s 900
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.family_world_macro import family_world_macro_state  # noqa: E402

from research import proposer_common as pc  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

SOURCE = "world_macro_state"
FAMILY = "world_macro_state"
REPORT = DESK / "reports" / "WORLD_MACRO_PROPOSER.json"
UNMEASURED = "UNMEASURED"
DEFAULT_BUDGET_S = 900.0

#: The declared grid. Bands are finite so every param is JSON-exact; 99 is "no upper bound".
BANDS: tuple[tuple[float, float], ...] = ((-99.0, -1.5), (-1.5, -0.5), (0.5, 1.5), (1.5, 99.0))
DIRECTIONS: tuple[str, ...] = ("long", "short")
HOLDS: tuple[int, ...] = (24, 72)
Z_OBS = 24


def _cursor_path() -> Path:
    return W.STORE / "proposer_cursor.json"


def _symbols(doc: dict[str, Any]) -> list[str]:
    from research import universe_policy as up
    return [s for s in sorted((doc.get("symbols") or {}).keys()) if up.may_hypothesise(s)]


def _label(key: str) -> str:
    loc = W._key_location(key)
    if loc is None:
        return key
    meta = W._read_json(W.meta_path(loc[0], loc[1]), {}) or {}
    name = ((meta.get("series") or {}).get(loc[2]) or {}).get("name") or loc[2]
    return f"{loc[0]}/{loc[1]}:{name}"[:160]


def run(*, budget_s: float = DEFAULT_BUDGET_S, now: datetime | None = None,
        donate: bool = True) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    doc = W._exposure_doc()
    syms = _symbols(doc)
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "organ": "desks/mt5/research/world_macro_proposer.py",
                           "family": FAMILY, "consumes": "world_dataset_hunter exposure"}
    if not syms:
        rep.update({"status": UNMEASURED, "why": "the hunter has exposed no series to any "
                    "hypothesis-lane symbol yet", "tests_run": UNMEASURED,
                    "cells_proposed": UNMEASURED})
        W.write_json(REPORT, rep)
        return rep
    cur = W._read_json(_cursor_path(), {}) or {}
    start = int(cur.get("next", 0)) % len(syms)
    order = syms[start:] + syms[:start]
    meta = pc.universe_meta()
    rows: list[dict[str, Any]] = []
    swept: list[str] = []
    skipped: dict[str, str] = {}
    for sym in order:
        if time.monotonic() - t0 > budget_s:
            break
        d = pc.bars(sym)
        if d is None or len(d) < 2000:
            skipped[sym] = "no or too few H1 bars"
            swept.append(sym)
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms"
            swept.append(sym)
            continue
        unf = pc.artifact_hours(d)
        for key in W.exposed_keys(sym, now=now, doc=doc):
            for lo, hi in BANDS:
                for direction in DIRECTIONS:
                    for hold in HOLDS:
                        params = {"series_key": key, "z_obs": Z_OBS, "z_lo": lo, "z_hi": hi,
                                  "direction": direction, "hold_bars": hold}
                        sig = family_world_macro_state(d, **params)
                        sc = pc.screen(d, sig, cost, unf)
                        if sc is None:
                            continue
                        rows.append({"cell": f"{sym}.{FAMILY}.{key}", "symbol": sym,
                                     "params": params, **sc})
        swept.append(sym)
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"{_label(r['params']['series_key'])} sits in z band "
                   f"[{r['params']['z_lo']}, {r['params']['z_hi']}) against its own last "
                   f"{Z_OBS} prints: the flows that official statistic describes lean "
                   f"{r['params']['direction']} on {r['symbol']} for "
                   f"{r['params']['hold_bars']} bars"),
        title=f"{r['cell']} z[{r['params']['z_lo']},{r['params']['z_hi']}) "
              f"{r['params']['direction']} h{r['params']['hold_bars']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep")}) for r in proposals]
    donated = None
    if donate and cands:
        donated = pc.donate(SOURCE, cands, len(rows))
    W.write_json(_cursor_path(), {"next": (start + len(swept)) % len(syms),
                                  "at": now.isoformat(timespec="seconds")})
    rep.update({"status": "OK", "symbols_available": len(syms), "symbols_swept": len(swept),
                "cursor_start": start, "tests_run": len(rows),
                "cells_proposed": len(proposals),
                "donated": len(cands) if donated else 0, "donation_path": str(donated or ""),
                "donation_refusals": dict(pc.LAST_DONATION) if donated is None and cands
                else None,
                "skipped": skipped, "elapsed_s": round(time.monotonic() - t0, 1),
                "proposals": proposals[:50]})
    W.write_json(REPORT, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    a = ap.parse_args(argv)
    r = run(budget_s=a.budget_s)
    print(f"world_macro_proposer: status={r['status']} swept={r.get('symbols_swept', 0)} "
          f"tests={r['tests_run']} proposed={r['cells_proposed']} "
          f"donated={r.get('donated', 0)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
