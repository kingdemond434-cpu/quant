"""THE FAST ADMISSION SCREEN: raw intake is not a test population, and the desk conflated them.

WHAT THIS EXISTS FOR (principal 2026-09-24: "the bottleneck is OUTPUT of orthogonal candidates to
the gauntlet"). `data/hypotheses/external_survivors.json` is a BANK, not a snapshot -- every row
the desk has ever minted for the judge accumulates there. Measured on the trading box 2026-09-24
it held 244,275 rows, which reads on every dashboard as a 244k-cell backlog waiting for the ten
gates. It is not. 30,331 of those rows can NEVER pass, by facts the desk already owns:

    12,562  untradeable_symbol   -- absent from the registry, no parquet, or CLOSE_ONLY
    17,769  no_economic_prior    -- no falsifiable mechanism the first canonical gate accepts
     1,020  off_hypothesis_lane  -- single-name equities, which the two-lane standing order
                                    (2026-09-06) says are traded on news and NEVER hunted for
                                    statistical hypotheses

The ADMISSIBLE population -- the one that is actually a test subject -- was 212,924. Publishing
one number where there are two is how a desk mistakes a bank for a queue.

THE HARD RULE, AND IT IS THE WHOLE DESIGN: THIS SCREEN MAY ONLY REFUSE WHAT THE GATES COULD NEVER
PASS. It is not a second judge. It carries no score, no rank, no threshold and no statistic; the
ten gates in `desks/mt5/policy/gate_spec.yaml` are the only thing that certifies, and if this
screen ever refused a cell the gates would have JUDGED it would be a gate in disguise and it would
be wrong. `REASONS` is a closed vocabulary of four, each one a FACT about the instrument or the
mechanism rather than a measurement of the edge, and `tests/test_fast_admission.py` pins it shut.

HOW IT KEEPS THAT PROMISE: it does not implement the rule, it DELEGATES it. Tradeability and the
economic prior are `external_gauntlet.partition_at_economic_prior` -- the sealed judge's own
gate 0, imported and called, not re-spelled. A second spelling of a rule is how four pens came to
have four different ones on this desk before. The lane limb is `research/universe_policy.lane`,
which routes by MetaTrader's own asset class and never by a symbol list.

WHAT IT NEVER DOES: it never deletes a row, never rewrites the bank, never shrinks a budget and
never caps anything (GROWTH_GOVERNANCE Rule 1). The bank keeps every row it has ever held. This
organ reads it, publishes the two populations separately and permanently, and writes the
admissible docket beside the raw one. Removal from the bank belongs to the bank's writer
(`research/merge_hypotheses.py`), and the report names it per reason so the finding is actionable
rather than filed.

WHY THE JUDGE'S BATTERY TIME IS ALREADY CLEAN, stated because an audit found otherwise and the
measurement disagrees: `external_gauntlet.main` calls `partition_at_economic_prior` at line 2704,
BEFORE the cell-build loop at 2711, so an untradeable cell is refused before a single bar is read.
The ten expensive gates therefore spend 0.00% of their time on cells that could never trade, and
that was true before this organ existed. What the never-passable population DOES cost is the
pre-battery pass -- 30,331 of 244,275 unique cells, 12.42%, re-screened on every sweep -- plus
every upstream backtest that produced them. Naming the true cost is worth more than inflating it.

    python desks/mt5/research/fast_admission.py [--json] [--docket PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RAW_DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
ADMISSIBLE_DOCKET = DESK / "data" / "hypotheses" / "admissible_docket.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
OUT = DESK / "reports" / "ADMISSION_SCREEN.json"

#: THE CLOSED VOCABULARY. Four reasons, every one a fact the desk already holds about the
#: instrument or the mechanism, none of them a measurement of the candidate's edge. Adding a fifth
#: is a governance act: it has to be a class of cell the ten gates could NEVER pass, and the test
#: that pins this tuple is the thing that makes that explicit rather than incidental.
REASONS: tuple[str, ...] = (
    "no_symbol_or_family",
    "untradeable_symbol",
    "no_economic_prior",
    "off_hypothesis_lane",
)

#: Which organ owns the removal of each refused class from the bank. A census that names a
#: population and no owner is a queue with extra steps (LAWS, nothing is queued).
OWNER: dict[str, str] = {
    "no_symbol_or_family": "research/merge_hypotheses.py (the bank's writer)",
    "untradeable_symbol": "research/merge_hypotheses.py (it already filters fresh and banked "
                          "rows; the residue is rows whose symbol went CLOSE_ONLY or lost its "
                          "parquet after banking)",
    "no_economic_prior": "research/merge_hypotheses.py -- no limb filters this today",
    "off_hypothesis_lane": "side_channels/run_external_backtest.py route_by_lane keeps them out "
                           "of new dockets; the residue is rows banked before the two-lane order "
                           "of 2026-09-06",
}

#: Why each reason is a fact and not a judgement. Published in the artifact so a reader can audit
#: the promise ("only what the gates could never pass") without reading this file.
WHY_NEVER_PASSABLE: dict[str, str] = {
    "no_symbol_or_family": "external_gauntlet.main skips a row with no symbol or no family when "
                           "it builds its cell map; such a row never becomes a cell, so no gate "
                           "ever sees it",
    "untradeable_symbol": "external_gauntlet.symbol_is_tradeable: absent from universe.json, no "
                          "<sym>_H1.parquet for a clock to replay, or CLOSE_ONLY on this account. "
                          "A certificate here could never open the position it certifies",
    "no_economic_prior": "research/frontier_identity.economic_prior, the FIRST canonical gate. A "
                         "cell that fails it is a terminal reject in the judge's own sweep",
    "off_hypothesis_lane": "research/universe_policy.lane != hypothesis. The principal's standing "
                           "order of 2026-09-06: single-name equities are traded on news and "
                           "never hunted for statistical hypotheses. Routing is by MetaTrader's "
                           "asset class, never a symbol list",
}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    """Write-and-rename. A reader never sees a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


def _cell_key(row: dict[str, Any], timeframe_of: Any) -> tuple[str, dict[str, Any]]:
    """The judge's own cell identity, so the two populations are counted in the same units.

    `external_gauntlet.main` folds the docket into unique (sym, chart, family, params) cells
    before gate 0 runs. Counting ROWS here and CELLS there would make the split unreadable, so
    this mirrors that fold exactly -- including the chart, which a proposer may carry on the row
    rather than inside params.
    """
    params = dict(row.get("params") or {})
    row_tf = str(row.get("timeframe") or "").upper()
    if row_tf and row_tf != "H1" and "timeframe" not in params:
        params["timeframe"] = row_tf
    spec = {
        "sym": row.get("symbol") or row.get("sym"),
        "family": row.get("family"),
        "params": params,
        "timeframe": timeframe_of(params, str(row.get("family") or "")),
    }
    key = f"{spec['sym']}.{spec['family']}.{json.dumps(params, sort_keys=True)}"
    return key, spec


def screen(rows: list[Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Split raw intake into ADMISSIBLE and REFUSED, by named reason. Judges nothing.

    Returns the census plus the admissible specs. Every refusal carries the reason's name, and
    every reason is in `REASONS` -- there is no path that refuses on anything else.
    """
    from external_gauntlet import partition_at_economic_prior, timeframe_of

    t0 = time.time()
    cells: dict[str, dict[str, Any]] = {}
    refused: Counter[str] = Counter()
    refused_symbols: dict[str, Counter[str]] = {r: Counter() for r in REASONS}
    raw_rows = 0
    for row in rows:
        raw_rows += 1
        if not isinstance(row, dict) or not (row.get("symbol") or row.get("sym")) \
                or not row.get("family"):
            refused["no_symbol_or_family"] += 1
            continue
        key, spec = _cell_key(row, timeframe_of)
        cells.setdefault(key, spec)
    t_group = time.time() - t0

    # GATE 0, DELEGATED. This is the sealed judge's own call, on the sealed judge's own specs.
    # It cannot refuse anything the judge would have judged, because it IS what the judge runs.
    t0 = time.time()
    eligible, rejected = partition_at_economic_prior(list(cells.values()), meta)
    t_gate0 = time.time() - t0
    for rej in rejected:
        gate = str(rej.get("terminal_gate") or "")
        reason = "untradeable_symbol" if gate == "symbol_eligibility" else "no_economic_prior"
        refused[reason] += 1
        refused_symbols[reason][str(rej.get("sym") or "?")] += 1

    # THE TWO-LANE STANDING ORDER. A single-name equity cell is not a weak hypothesis, it is a
    # hypothesis the desk has forbidden itself to mint -- and every one of them spends the same
    # family-wise error budget the FX and metals cells have to clear.
    t0 = time.time()
    admissible: list[dict[str, Any]] = []
    try:
        from universe_policy import HYPOTHESIS, lane
    except ImportError:                                  # pragma: no cover - import-context dep
        from research.universe_policy import HYPOTHESIS, lane  # type: ignore[no-redef]
    for spec in eligible:
        sym = str(spec.get("sym") or "")
        if lane(sym) != HYPOTHESIS:
            refused["off_hypothesis_lane"] += 1
            refused_symbols["off_hypothesis_lane"][sym] += 1
            continue
        admissible.append(spec)
    t_lane = time.time() - t0

    total_refused = sum(refused.values())
    return {
        "raw_rows": raw_rows,
        "raw_cells": len(cells),
        "admissible_cells": len(admissible),
        "refused_cells": total_refused,
        "refused_by_reason": {r: int(refused.get(r, 0)) for r in REASONS},
        "refused_share": (round(total_refused / len(cells), 6) if cells else None),
        "top_refused_symbols": {
            r: [[s, n] for s, n in refused_symbols[r].most_common(12)] for r in REASONS
        },
        "seconds": {"group": round(t_group, 2), "gate0": round(t_gate0, 2),
                    "lane": round(t_lane, 2)},
        "admissible": admissible,
    }


def build(docket: Path = RAW_DOCKET, universe: Path = UNIVERSE) -> dict[str, Any]:
    """Read the bank, screen it, and return the artifact. UNMEASURED is a real answer (L1.28a)."""
    stamp = datetime.now(UTC).isoformat()
    base: dict[str, Any] = {
        "measured_at": stamp,
        "raw_docket": str(docket),
        "admissible_docket": str(ADMISSIBLE_DOCKET),
        "reasons": list(REASONS),
        "why_never_passable": WHY_NEVER_PASSABLE,
        "removal_owner": OWNER,
        "contract": ("THE SCREEN MAY ONLY REFUSE WHAT THE GATES COULD NEVER PASS. It carries no "
                     "score, rank, threshold or statistic. Tradeability and the economic prior "
                     "are external_gauntlet.partition_at_economic_prior -- the sealed judge's "
                     "own gate 0, called, not re-spelled. The lane limb is the principal's "
                     "two-lane standing order routed by MetaTrader's asset class."),
        "never_deletes": ("this organ writes reports/ADMISSION_SCREEN.json and "
                          "data/hypotheses/admissible_docket.json and nothing else. The bank "
                          "keeps every row it has ever held."),
    }
    t0 = time.time()
    try:
        raw = json.loads(docket.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {**base, "status": "UNMEASURED",
                "why": f"{docket} unreadable: {type(exc).__name__}: {exc}"}
    if not isinstance(raw, list):
        return {**base, "status": "UNMEASURED",
                "why": f"{docket} is {type(raw).__name__}, not the list of rows the judge reads"}
    t_load = time.time() - t0
    try:
        meta = json.loads(universe.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {**base, "status": "UNMEASURED",
                "why": (f"{universe} unreadable: {type(exc).__name__}: {exc}. Without the "
                        "registry the tradeability limb cannot run, and guessing it would "
                        "refuse cells the gates could have judged.")}

    census = screen(raw, meta if isinstance(meta, dict) else {})
    admissible = census.pop("admissible")
    census["seconds"]["load"] = round(t_load, 2)
    census["seconds"]["total"] = round(sum(census["seconds"].values()), 2)
    return {**base, "status": "MEASURED", **census,
            "docket_bytes": docket.stat().st_size,
            "battery_time_on_never_tradeable": {
                "share": 0.0,
                "why": ("the sealed judge calls partition_at_economic_prior BEFORE its "
                        "cell-build loop (external_gauntlet.py:2704 then :2711), so a cell that "
                        "can never trade is refused before a bar is read. The ten expensive "
                        "gates spend none of their time on it, and did not before this organ "
                        "existed. The cost these cells DO carry is the pre-battery pass and "
                        "every upstream backtest that produced them."),
            },
            "_admissible_rows": admissible}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the artifact")
    ap.add_argument("--docket", type=Path, default=RAW_DOCKET)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    doc = build(args.docket)
    admissible = doc.pop("_admissible_rows", [])
    _atomic_json(args.out, doc)
    if doc.get("status") == "MEASURED":
        _atomic_json(ADMISSIBLE_DOCKET, {
            "n": len(admissible),
            "screened_at": doc["measured_at"],
            "from_docket": str(args.docket),
            "note": ("the ADMISSIBLE population: cells the ten gates could actually judge. Not a "
                     "replacement for the bank and never read by the sealed judge, which applies "
                     "the identical gate 0 itself. This file exists so raw intake and test "
                     "subjects are two published numbers instead of one."),
            "cells": admissible,
        })
        print(f"admission screen: raw {doc['raw_rows']} rows -> {doc['raw_cells']} cells; "
              f"ADMISSIBLE {doc['admissible_cells']}; refused {doc['refused_cells']} "
              f"({doc['refused_by_reason']}) in {doc['seconds']['total']}s -> {args.out.name}")
    else:
        print(f"admission screen: {doc['status']} -- {doc.get('why')}")
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
