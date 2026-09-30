"""`residual_gate`: the MOUNT for C9's residual statistic. Publishes; never vetoes.

THE LIBRARY IS `libs/validation/residual_gate.py` AND IT HAS NO SIDE EFFECTS. This is the organ
that gives it a clock, an input and an artifact, in the shape the desk already proved with
`hostile` -> `blind_reviewer`: the row's own `next_step` asked for a stage inside
`external_gauntlet`, that file is SEALED, and a statistic that cannot be mounted where it was
drawn is mounted beside it rather than not at all.

WHAT IT READS. One frame: `data/pf_allocator_cache/daily_r.parquet`, the same per-sleeve daily-R
matrix `alpha_fitness.load_book` and the allocator itself read, joined to `reports/
pf_allocation.json`'s `book` so "funded" means what the allocator says it means this hour. The
FUNDED columns are the book; every OTHER column is a candidate -- a forward-lane clock, a shadow
sleeve, a retired window still recording. That is a real candidate set measured from the desk's
own state, not a synthetic one.

WHAT IT WRITES. `reports/RESIDUAL_GATE.json`: per candidate, the raw t, the t of the residual
after the book's latent factors and every funded sleeve are regressed out, the share of variance
the book explains, and the betas. Plus one registry event per measured cell so the statistic is
reachable from the row rather than only from the report.

WHAT IT NEVER DOES. Refuse, delay, cap, shrink or re-rank anything downward. The consumer is
`merge_hypotheses.breadth_order`, which uses the family-level residual t to BREAK TIES between
families that have been judged equally often -- it re-orders and removes nothing, which is the
only form an admission statistic may take under the standing order of 2026-09-08.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "RESIDUAL_GATE.json"
ALLOCATION = BASE / "reports" / "pf_allocation.json"
DAILY_R = BASE / "data" / "pf_allocator_cache" / "daily_r.parquet"
SLEEVES = ROOT / "data" / "sleeves.json"

#: Wall clock the leg gives this organ. Derived by the caller, defaulted here; nothing in this
#: module is sized off a machine's memory, because nothing here holds more than one daily frame.
DEFAULT_BUDGET_S = 180.0
#: Most candidate columns measured in one pass. The frame is small by construction (one column
#: per sleeve the desk has ever run forward); the cap exists so a pathological frame cannot make
#: an hourly leg unbounded.
MAX_CELLS = 400


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _registered_families() -> list[str]:
    """Every family name `mt5desk.families` registers, longest first. Empty when unimportable."""
    try:
        from mt5desk.families import FAMILY_REGISTRY
    except Exception:                                       # pragma: no cover - import env
        return []
    return sorted((str(f) for f in FAMILY_REGISTRY), key=len, reverse=True)


def _family_of(name: str, families: list[str]) -> str:
    """The REGISTERED family this sleeve name contains, or "" when it contains none.

    SPLITTING ON UNDERSCORES WAS WRONG AND THE FIRST PASS PROVED IT: `gold_london_am` became the
    family "london" and `CADJPY_asia_FAILED_BREAK` became "asia_FAILED", neither of which the
    desk has ever registered, so the tie-break would have keyed on families that do not exist.
    The registry is the only authority on what a family is called; longest match first so
    `overnight_gap_decay` is not read as `overnight_gap`. A forward-clock window such as
    `gold_asia` names no family and gets "", which keeps it out of the family table entirely
    rather than inventing a bucket for it.
    """
    low = str(name).lower()
    for fam in families:
        if fam.lower() in low:
            return fam
    # ABBREVIATED SLEEVE NAMES. The forward lanes shorten a family in the sleeve key --
    # `CADJPY_asia_FAILED_BREAK` is `failed_breakout`, and a plain substring test misses it and
    # returns "", which drops a real family out of the table silently. A contiguous run of the
    # name's tokens each of which PREFIXES the corresponding family token is the same family
    # abbreviated; requiring the run to be contiguous and in order keeps `break` from matching
    # `breakout_reversal` through an unrelated middle token.
    tokens = [t for t in low.split("_") if t]
    for fam in families:
        want = fam.lower().split("_")
        for start in range(len(tokens) - len(want) + 1):
            run = tokens[start:start + len(want)]
            if all(w.startswith(r) and len(r) >= 3 for r, w in zip(run, want, strict=True)):
                return fam
    return ""


def _load_frame() -> tuple[Any, str]:
    try:
        import pandas as pd
    except Exception as exc:                                # pragma: no cover - import env
        return None, f"pandas unimportable ({type(exc).__name__})"
    if not DAILY_R.exists():
        return None, (f"{DAILY_R.name} absent: the allocator's evidence cache has not been "
                      "written on this host, so there is no book to neutralise against")
    try:
        frame = pd.read_parquet(DAILY_R)
    except (OSError, ValueError, ImportError) as exc:
        return None, f"{DAILY_R.name} unreadable ({type(exc).__name__}: {str(exc)[:100]})"
    if getattr(frame, "empty", True):
        return None, f"{DAILY_R.name} is empty"
    return frame, f"{DAILY_R.name}: {frame.shape[0]} day(s) x {frame.shape[1]} sleeve(s)"


def _record_events(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One registry event per measured cell. Best effort: the report is the artifact.

    `record_event` appends; it changes no status and carries no verdict. This is the door that
    makes the statistic reachable from a row's own provenance rather than only from a JSON file.
    """
    out: dict[str, Any] = {"attempted": 0, "recorded": 0, "why": ""}
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        out["why"] = f"registry unimportable ({type(exc).__name__}); report-only this pass"
        return out
    for row in rows:
        if row.get("status") != "MEASURED":
            continue
        out["attempted"] = int(out["attempted"]) + 1
        with contextlib.suppress(Exception):
            reg.record_event(str(row.get("name") or "?"), "residual_alpha",
                             actor="residual_gate",
                             detail={"residual_t": row.get("residual_t"),
                                     "raw_t": row.get("raw_t"),
                                     "t_retained": row.get("t_retained"),
                                     "n": row.get("n_overlap"),
                                     "authority": "published, never a veto"})
            out["recorded"] = int(out["recorded"]) + 1
    if out["attempted"] and not out["recorded"]:
        out["why"] = "every record_event call was refused by the registry; report-only this pass"
    return out


def run(budget_s: float = DEFAULT_BUDGET_S) -> dict[str, Any]:
    started = time.monotonic()
    frame, frame_why = _load_frame()
    art = _read_json(ALLOCATION)
    raw_book = art.get("book")
    heats: dict[str, Any] = raw_book if isinstance(raw_book, dict) else {}
    doc: dict[str, Any] = {
        "at": _now(), "organ": "residual_gate", "source": frame_why,
        "budget_s": round(float(budget_s), 1),
        "rule": ("s = Bf + e for every candidate the desk records a daily series for, against "
                 "the funded book's latent factors and its survivor series; the admission "
                 "statistic is t of the intercept"),
        "authority": ("PUBLISHES, NEVER VETOES -- no cell is refused, delayed, capped or shrunk "
                      "by this number (standing order 2026-09-08). The sealed gauntlet and the "
                      "promoter remain the only judges"),
        "consumer": ("desks/mt5/research/merge_hypotheses.py residual_family_values -> "
                     "breadth_order (family tie-break inside the judging docket, removing "
                     "nothing); registry residual_alpha events on each measured row"),
        "blocking": False,
    }
    if frame is None:
        doc.update({"status": "UNMEASURED", "why": frame_why, "n_cells": 0, "rows": [],
                    "by_family": {}, "elapsed_s": round(time.monotonic() - started, 2)})
        return doc
    columns = [str(c) for c in frame.columns]
    funded = [c for c in columns if c in heats]
    if len(funded) < 2:
        # A one-sleeve book has no factor structure and no survivor set: neutralising against it
        # would subtract a single series and call the remainder a residual.
        doc.update({"status": "UNMEASURED",
                    "why": (f"{len(funded)} funded sleeve(s) join the daily-R frame "
                            f"({len(heats)} in the allocator's book, {len(columns)} columns): "
                            "a book of fewer than two sleeves has no latent factors to remove"),
                    "n_cells": 0, "rows": [], "by_family": {}, "funded": funded,
                    "elapsed_s": round(time.monotonic() - started, 2)})
        return doc
    candidates = [c for c in columns if c not in heats][:MAX_CELLS]
    if not candidates:
        doc.update({"status": "MEASURED", "why": ("every column of the daily-R frame is funded: "
                                                  "there is no unfunded candidate to neutralise "
                                                  "this hour, which is the measurement"),
                    "n_cells": 0, "rows": [], "by_family": {}, "funded": funded,
                    "elapsed_s": round(time.monotonic() - started, 2)})
        return doc
    from libs.validation import residual_gate as rg
    book = {c: frame[c].to_numpy(dtype=float) for c in funded}
    cells: dict[str, Any] = {}
    stopped = ""
    for c in candidates:
        if time.monotonic() - started > float(budget_s):
            stopped = f"budget {budget_s:g}s reached after {len(cells)} cell(s)"
            break
        cells[c] = frame[c].to_numpy(dtype=float)
    res = rg.run_all(cells, book)
    by_family: dict[str, dict[str, Any]] = {}
    families = _registered_families()
    for row in res["rows"]:
        fam = _family_of(str(row.get("name") or ""), families)
        if not fam or row.get("status") != "MEASURED":
            continue
        cur = by_family.setdefault(fam, {"n": 0, "best_residual_t": None})
        cur["n"] += 1
        t = row.get("residual_t")
        if isinstance(t, (int, float)) and (cur["best_residual_t"] is None
                                            or t > cur["best_residual_t"]):
            cur["best_residual_t"] = float(t)
    doc.update({
        "status": "MEASURED" if res["n_measured"] else "UNMEASURED",
        "why": ("" if res["n_measured"] else
                "no candidate cleared the overlap floor; every row says which"),
        "funded": funded, "n_candidates": len(candidates), "stopped_on_budget": stopped,
        "by_family": by_family,
        "registry": _record_events(res["rows"]),
        "elapsed_s": round(time.monotonic() - started, 2),
        **{k: res[k] for k in ("n_cells", "n_measured", "n_unmeasured", "book_sleeves",
                               "rows", "ranked")},
    })
    return doc


def _write(doc: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, OUT)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    args = ap.parse_args(argv)
    doc = run(budget_s=max(1.0, float(args.budget_s)))
    _write(doc)
    tail = f" -- {doc['why']}" if doc.get("why") else ""
    print(f"residual_gate: {doc['status']} -- {doc.get('n_measured', 0)} measured, "
          f"{doc.get('n_unmeasured', 0)} unmeasured{tail}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(main())
