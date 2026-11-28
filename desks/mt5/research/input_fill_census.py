"""Publish the spread column's leading fill era and every SUSPECT_CONSTANT_RUN, per bar file.

`alpha_grammar.terminal_frames` treats the leading fill era of a file's `spread` column as
undefined (`alpha_grammar.mask_leading_fill`, box read 2026-11-10 over 102 M30/H1 files). This
leg says, by name, what that rule did to each file the formula certificates trade, and names
every later run of one held spread value at least five trading days long as
SUSPECT_CONSTANT_RUN (start, end, bars). Those runs are NOT masked and judge nothing: whether a
2-point spread held for weeks on EURSGD or XAUUSD in 2024-26 is a quote or a feed fill is the
tick tape's question, not this module's.

It also counts the formula certificates the rule concerns: those reading `spread` (re-judged
under the masked input) and those reading only `activity` / `flow` (tick_volume was clean in
all 102 files, so the input hold on them is released).

Report only. Runs after each judge sweep (`run_sharded_gauntlet`), at most once per
MAX_AGE_H; never raises into its caller.
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPORT = DESK / "reports" / "INPUT_FILL_CENSUS.json"
UNIVERSE = DESK / "data" / "universe"
SURVIVOR_FILES = ("data/UNIVERSAL_SURVIVORS.canon.json", "reports/UNIVERSAL_SURVIVORS.json")
MAX_AGE_H = 6.0
SPREAD_TERMINALS = frozenset({"spread"})
TICK_TERMINALS = frozenset({"activity", "flow"})


def _expr_terminals(expr: Any) -> set[str] | None:
    from libs.research.alpha_grammar import from_str, terminals_in
    try:
        if isinstance(expr, str) and "(" in expr:
            expr = from_str(expr)
        return set(terminals_in(expr))
    except Exception:
        return None


def formula_reads(desk: Path = DESK) -> dict[str, Any]:
    """Formula certificates by which input column they read, and the symbols reading spread."""
    surv: dict[str, Any] = {}
    for rel in SURVIVOR_FILES:
        with contextlib.suppress(Exception):
            got = json.loads((desk / rel).read_text("utf-8")).get("survivors")
            if isinstance(got, dict):
                surv.update(got)
    n = unreadable = spread = ticks_only = 0
    syms: Counter[str] = Counter()
    for row in surv.values():
        spec = row.get("shadow_spec") if isinstance(row, dict) else None
        if not isinstance(spec, dict) or str(spec.get("family") or "") != "formula":
            continue
        n += 1
        params = spec.get("params") if isinstance(spec.get("params"), dict) else {}
        terms = _expr_terminals(params.get("expr"))
        if terms is None:
            unreadable += 1
            continue
        if terms & SPREAD_TERMINALS:
            spread += 1
            syms[str(spec.get("symbol") or row.get("sym") or "").upper()] += 1
        elif terms & TICK_TERMINALS:
            ticks_only += 1
    return {"formula_certificates": n, "expr_unreadable": unreadable,
            "reading_spread": spread, "reading_activity_or_flow_only_released": ticks_only,
            "spread_symbols": dict(syms.most_common())}


def _file_report(path: Path) -> dict[str, Any]:
    import pandas as pd

    from libs.research.alpha_grammar import input_fill_report
    df = pd.read_parquet(path)
    cols = {str(c).lower(): c for c in df.columns}
    if "time" in cols:
        df = df.set_index(cols["time"])
    if "spread" not in cols:
        return {"status": "NO_COLUMN"}
    return input_fill_report(df.rename(columns={cols["spread"]: "spread"}), "spread")


def build(desk: Path = DESK) -> dict[str, Any]:
    reads = formula_reads(desk)
    uni = desk / "data" / "universe"
    by_file: dict[str, Any] = {}
    for sym in sorted(reads["spread_symbols"]):
        for path in sorted(uni.glob(f"{sym}_*.parquet")):
            try:
                by_file[path.stem] = _file_report(path)
            except Exception as exc:
                by_file[path.stem] = {"status": "UNMEASURED",
                                      "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
    suspect = [{"file": k, **r} for k, v in by_file.items()
               for r in (v.get("suspect_constant_runs") or [])]
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **reads,
            "files": len(by_file),
            "files_with_fill_era": sum(1 for v in by_file.values()
                                       if v.get("fill_end_index")),
            "files_whole_column_held": sorted(k for k, v in by_file.items()
                                              if v.get("whole_column_held")),
            "files_unmeasured": sorted(k for k, v in by_file.items()
                                       if v.get("status") == "UNMEASURED"),
            "suspect_constant_runs": suspect, "n_suspect_constant_runs": len(suspect),
            "by_file": by_file}


def publish(desk: Path = DESK, *, max_age_h: float = MAX_AGE_H,
            now: float | None = None) -> str:
    """Write the census unless a fresh one exists. Returns WRITTEN / FRESH / FAILED: ..."""
    out = desk / "reports" / REPORT.name
    now = time.time() if now is None else now
    with contextlib.suppress(OSError):
        if now - out.stat().st_mtime < max_age_h * 3600.0:
            return "FRESH"
    try:
        doc = build(desk)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f"{out.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, out)
        return "WRITTEN"
    except Exception as exc:
        return f"FAILED: {type(exc).__name__}: {str(exc)[:160]}"


if __name__ == "__main__":
    print(publish(max_age_h=0.0))
