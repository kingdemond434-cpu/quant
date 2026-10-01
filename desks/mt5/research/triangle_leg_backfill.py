"""TRIANGLE LEG BACKFILL: name the two legs of every legless `triangle` row ALREADY in the docket.

WHY (measured 2026-09-30 on the docket committed 2026-09-29, 57,538 rows). All 1,796 `triangle`
rows carried no `leg_b_symbol` / `leg_c_symbol` -- every one from `miner_candidates.json` -- and
`family_triangle` returns [] without both legs, so each reached the judge as UNKNOWN / "never
fires" and not one triangle cell was judgeable. `discovery_compiler.complete_inputs` now names
the legs, but only for rows the compiler mints from here on; the 1,796 already banked would have
stayed legless for ever, because the docket re-admits its bank verbatim every hour.

WHAT IT DOES. The docket's own writer (`merge_hypotheses`, the ONLY writer of
external_survivors.json) calls `backfill` on the merged rows every hour, just before it orders
and writes them, so a legless row arriving later is filled on the pass it arrives. The legs are
chosen by exactly the compiler's rule -- `discovery_compiler.complete_inputs`: the target's two
currencies joined through the first pivot (`TRIANGLE_PIVOTS`, then the rest alphabetically) whose
two connecting pairs are hypothesis-lane instruments holding bars on the row's own chart, with
`triangle_miner.orient` deriving `sign_b` / `sign_c` from the symbols' names.

THE CONTRACT.
* NEVER DELETES A ROW. A filled row is the same row with its legs added; a row that cannot be
  filled stays exactly as it was, with the reason recorded on it.
* RECORDS WHAT IT DID, PER ROW, under `legs_backfill`: `FILLED` with the four params it added,
  the chart and the params it had before; or `UNFILLED` with the reason (not an FX pair; no
  hypothesis-lane instrument holds bars on the chart; the quote set closes the triangle but not
  with bars on the chart; the quote set cannot close it; the filled spec is already a docket row).
* IDEMPOTENT. A row that names both legs is never touched again, and an unfilled row's record is
  rewritten only when its reason changes, so a pass over an unchanged docket changes nothing.
* NEVER DUPLICATES. A fill whose executable identity is already a docket row is not made (that
  row is the filled cell); the legless row stays and says so.

`OUT` is the pass's report (counts by status and reason). `python research/triangle_leg_backfill.py`
measures the docket read-only and writes only that report; the docket is written by its owner.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
HYP = BASE / "data" / "hypotheses"
DOCKET = HYP / "external_survivors.json"
#: The pass's report, written beside the docket by the docket's writer (so it follows `HYP`).
OUT = HYP / "triangle_leg_backfill.json"
FAMILY = "triangle"
LEG_KEYS = ("leg_b_symbol", "leg_c_symbol")
RECORD = "legs_backfill"
BY = "triangle_leg_backfill"


def _paths() -> None:
    for p in (str(BASE), str(BASE.parents[1])):
        if p not in sys.path:
            sys.path.insert(0, p)


def chart_of(row: dict[str, Any]) -> str:
    """The row's chart as the judge reads it: params first, then the row, H1 by default."""
    params = row.get("params") or {}
    return str(params.get("timeframe") or row.get("timeframe") or row.get("chart")
               or "H1").upper()


def legless(row: Any) -> bool:
    if not isinstance(row, dict) or str(row.get("family") or "") != FAMILY:
        return False
    params = row.get("params") or {}
    return not all(params.get(k) for k in LEG_KEYS)


def _why_unfilled(sym: str, chart: str, ctx: Any, meta: dict[str, Any]) -> str:
    """Name why the compiler's rule found no legs for `sym` on `chart`."""
    from research import discovery_compiler as dc
    from research.triangle_miner import fx_pairs
    pairs = fx_pairs(dict(meta))
    if sym not in pairs:
        return "not_an_fx_pair"
    pool = sorted({s for syms in ctx.instruments.values() for s in syms
                   if str(s).upper() != sym.upper() and ctx.hypothesis_lane(s)
                   and ctx.has_bars(s, chart)})
    if not pool:
        return f"no_hypothesis_lane_bars_on_{chart}"
    if dc._triangle_legs(sym, sorted(pairs), meta) is not None:
        return f"legs_exist_but_hold_no_bars_on_{chart}"
    return "quote_set_cannot_close_the_triangle"


def backfill(rows: list[dict[str, Any]], *, identity: Callable[[dict[str, Any]], str],
             ctx: Any = None, meta: dict[str, Any] | None = None,
             now: datetime | None = None) -> dict[str, Any]:
    """Fill the legs of every legless triangle row in `rows`, IN PLACE; return the report.

    `identity` is the docket writer's own executable identity, so a fill never makes a row
    that is already there. `ctx` / `meta` default to the compiler's own context and registry."""
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    targets = [r for r in rows if legless(r)]
    report: dict[str, Any] = {
        "at": stamp, "rows": len(rows),
        "triangle_rows": sum(1 for r in rows if isinstance(r, dict)
                             and str(r.get("family") or "") == FAMILY),
        "legless_before": len(targets), "filled": 0, "unfilled": 0, "changed_records": 0,
        "unfilled_by_reason": {}, "filled_by_chart": {}, "rule": (
            "discovery_compiler.complete_inputs: first pivot (TRIANGLE_PIVOTS, then the rest) "
            "whose two pairs are hypothesis-lane with bars on the row's chart; "
            "triangle_miner.orient signs")}
    if not targets:
        report["legless_after"] = 0
        report["status"] = "NOTHING_TO_FILL"
        return report
    _paths()
    from research import discovery_compiler as dc
    ctx = ctx if ctx is not None else dc.build_context()
    meta = dict(meta) if meta is not None else dc._universe_meta()
    present = {identity(r) for r in rows if isinstance(r, dict)}
    why_counts: Counter[str] = Counter()
    by_chart: Counter[str] = Counter()
    # The legs depend on (symbol, chart) alone, so the rule runs once per pair, not per row.
    legs: dict[tuple[str, str], dict[str, Any] | str] = {}
    for row in targets:
        sym = str(row.get("symbol") or row.get("sym") or "")
        chart = chart_of(row)
        before = dict(row.get("params") or {})
        if (sym, chart) not in legs:
            child = dc.complete_inputs({"symbol": sym, "family": FAMILY, "params": {},
                                        "chart": chart}, ctx, meta)
            got = dict(child.get("params") or {})
            legs[(sym, chart)] = (
                {k: got[k] for k in (*LEG_KEYS, "sign_b", "sign_c") if k in got}
                if child.get("input_completed") and all(got.get(k) for k in LEG_KEYS)
                else _why_unfilled(sym, chart, ctx, meta))
        found = legs[(sym, chart)]
        why = found if isinstance(found, str) else ""
        filled = isinstance(found, dict)
        params = {**before, **found} if isinstance(found, dict) else before
        if filled and identity({**row, "params": params}) in present:
            why, filled = "filled_spec_already_in_docket", False
        if filled and isinstance(found, dict):
            added = dict(found)
            present.discard(identity(row))
            row["params"] = params
            row["input_completed"] = LEG_KEYS[0]
            row[RECORD] = {"status": "FILLED", "filled": added, "chart": chart,
                           "params_before": before, "at": stamp, "by": BY}
            present.add(identity(row))
            report["filled"] += 1
            report["changed_records"] += 1
            by_chart[chart] += 1
            continue
        prior = row.get(RECORD)
        if not (isinstance(prior, dict) and prior.get("status") == "UNFILLED"
                and prior.get("why") == why and prior.get("chart") == chart):
            row[RECORD] = {"status": "UNFILLED", "why": why, "chart": chart, "at": stamp,
                           "by": BY}
            report["changed_records"] += 1
        report["unfilled"] += 1
        why_counts[why] += 1
    report["unfilled_by_reason"] = dict(why_counts.most_common())
    report["filled_by_chart"] = dict(by_chart.most_common())
    report["legless_after"] = sum(1 for r in rows if legless(r))
    report["status"] = "APPLIED"
    return report


def publish(report: dict[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1, default=str), "utf-8")


def _iter_docket(path: Path) -> Iterable[dict[str, Any]]:
    doc = json.loads(path.read_text("utf-8"))
    return [r for r in doc if isinstance(r, dict)] if isinstance(doc, list) else []


def main(argv: list[str] | None = None) -> int:
    """Measure the docket READ-ONLY: what a pass would fill, written to `--out` (default OUT).
    The docket itself is filled only by its writer, `merge_hypotheses`."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--docket", type=Path, default=DOCKET)
    ap.add_argument("--out", type=Path, default=None,
                    help="write the measured report here (OUT is the docket writer's pass report)")
    a = ap.parse_args(argv)
    _paths()
    from research.merge_hypotheses import _identity
    rows = list(_iter_docket(a.docket)) if a.docket.exists() else []
    report = backfill(rows, identity=_identity)
    report["mode"] = "measured_read_only"
    report["docket"] = str(a.docket)
    if a.out:
        publish(report, a.out)
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
