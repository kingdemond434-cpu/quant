"""INGEST EVERY AXIS, EVERY PASS -- and keep one report that shows all of them at once.

THE PRINCIPAL, 2026-09-12: "no make it ingest all there always bro".

WHAT WAS WRONG. `axis_ingest.py` takes `--axis` and runs exactly ONE ingester per invocation,
then writes BOTH a per-axis file and the shared `AXIS_INGEST.json`. The scheduled runner passed
`--axis cot`, so:

  * only one of the four axes was refreshed on the clock, and
  * the shared report carried whichever axis ran LAST -- measured 2026-09-12 it held FRED's
    result (0 series, 7 failed), which reads as "the axis lane is broken" while COT had in fact
    just ingested 4,060 rows across 22 MT5 symbols and BIS 464,803 rows across 33.

A report that shows one lane's worst pass and hides three healthy ones is worse than no report:
it is the shape that makes an operator distrust the board and stop reading it.

WHY A DRIVER AND NOT AN EDIT TO `axis_ingest.py`. This IMPORTS whatever version is present and
drives its own `INGESTERS` table, so a new axis added there is picked up here for free, with no
second list to keep in sync.

*(THE ORIGINAL REASON WAS WRONG AND COST TWELVE DAYS, so it is corrected here rather than
deleted. This docstring said the box's copy of `axis_ingest.py` was "438 lines AHEAD of this
tree", so editing it from here would revert box work. Measured 2026-09-24: the two files are
20,698 B on the box and 20,260 B here -- a difference of exactly 438 bytes, which is 438 CR
characters. The box's checkout is CRLF. Normalise the newlines and the SHA-256 of both is
`6652f3f6...`: the content is IDENTICAL and always was. A line-ending artifact was read as 438
lines of unmerged work, and that reading fenced off the one file where the FRED fetch could be
fixed at source. It has now been fixed there.)*

FAILURE IS PER-AXIS AND NEVER FATAL. Each ingester is caught individually and recorded as
UNMEASURED with its error -- a failed fetch is not evidence that an axis is barren (L1.28a).

AND AN EMPTY FETCH NEVER OVERWRITES A POPULATED AXIS. That rule is the whole of `_write_axis`
below, and it is the half of this file that was missing. `ingest_fred` swallows every per-series
exception, so it NEVER raises: it returns `{"n_series": 0}`, the `except` above it never fires,
`state` is computed as "EMPTY" by a line nothing consumes, and the write at the bottom of the
loop replaced the axis with the empty document anyway. Measured 2026-09-24:
`desks/mt5/data/axes/fred.json` was 893 bytes and thirty minutes old, refreshed faithfully every
hour, beside `bis.json` at 85.9 MB on the same clock. The lane was not idle -- it was diligently
rewriting a populated axis into an empty one, which is why nothing read as broken.

This is the shape LAWS calls absence resolving into a confident verdict, and the cost is not
hypothetical: seven series that nine `shadow_institutional` mechanisms condition on read
UNMEASURED for the axis's entire life. A refusal to write is recorded as
`EMPTY_REFUSED_OVERWRITE` with the count it preserved, so the non-write is a positive, dated
fact rather than a silence -- and an axis that has NEVER landed still writes its failure record,
because that record is the only evidence the next session gets (it is how this defect was found).

    python desks/mt5/research/axis_ingest_all.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_DIR = DESK / "data" / "axes"
REPORT = DESK / "reports" / "AXIS_INGEST.json"


def _count(doc: dict[str, Any]) -> int:
    """Rows for a tabular axis, series for a time-series one. Both are 'how much landed'."""
    for k in ("n_rows", "n_series"):
        v = doc.get(k)
        if isinstance(v, int):
            return v
    return 0


def _on_disk(path: Path) -> int:
    """How much the axis ALREADY holds. Unreadable is 0, and that is the safe direction here:
    a file this driver cannot parse is not evidence of data worth protecting, and refusing to
    refresh an axis because its previous document is corrupt would freeze the lane permanently."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return _count(doc) if isinstance(doc, dict) else 0


def _write_axis(path: Path, doc: dict[str, Any], n: int) -> dict[str, Any]:
    """Write one axis, and REFUSE when the write would replace data with nothing.

    Returns the fields the report carries for this axis's write. Never raises: an axis whose file
    cannot be replaced must not take the other three down with it.
    """
    prev = _on_disk(path)
    if n == 0 and prev > 0:
        # THE RULE. A fetch that came back empty is a fact about this pass, never a new state of
        # the world, and the previous document is the better estimate of the axis until a
        # non-empty fetch says otherwise (L1.28a).
        return {"written": False, "write_state": "EMPTY_REFUSED_OVERWRITE", "preserved_n": prev,
                "why": (f"this pass returned 0 and the file on disk holds {prev}; an empty fetch "
                        "never overwrites a populated axis")}
    # ATOMIC. A direct `write_text` that dies mid-stream truncates the axis, which is the same
    # loss by a slower route. `os.replace` is atomic on NTFS and POSIX alike.
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        # Measured lesson (CLAUDE.md): `os.replace` onto a read-only destination is legal on
        # POSIX and raises WinError 5 here. Report it; never crash the lane.
        with suppress(OSError):
            tmp.unlink()
        return {"written": False, "write_state": "WRITE_FAILED",
                "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return {"written": True,
            "write_state": "WRITTEN" if n else "WRITTEN_FIRST_RECORD",
            "preserved_n": prev}


def run_all(apply: bool) -> dict[str, Any]:
    import axis_ingest as ai

    now = datetime.now(tz=UTC)
    axes: dict[str, Any] = {}
    for name in sorted(ai.INGESTERS):
        try:
            doc = ai.INGESTERS[name]()
        except Exception as exc:
            # ONE PUBLISHER'S OUTAGE IS NOT THE LANE'S VERDICT. Recorded, then carry on.
            axes[name] = {"axis": name, "state": "UNMEASURED",
                          "error": f"{type(exc).__name__}: {exc}",
                          "why": ("a failed fetch is not evidence that the axis is barren; the "
                                  "previous per-axis file on disk still stands")}
            continue
        n = _count(doc)
        axes[name] = {
            "axis": name,
            "state": "OK" if n else "EMPTY",
            "n": n,
            "n_symbols": len(doc.get("symbols") or []),
            "n_failed": len(doc.get("failed") or {}),
            "failed": {k: str(v)[:120] for k, v in (doc.get("failed") or {}).items()},
        }
        if apply:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            axes[name].update(_write_axis(OUT_DIR / f"{name}.json", doc, n))

    ok = [k for k, v in axes.items() if v.get("state") == "OK"]
    refused = [k for k, v in axes.items()
               if v.get("write_state") == "EMPTY_REFUSED_OVERWRITE"]
    return {
        "at": now.isoformat(timespec="seconds"),
        "driver": "axis_ingest_all -- every axis, every pass",
        "n_axes": len(axes),
        "n_ok": len(ok),
        "n_unmeasured": sum(1 for v in axes.values() if v.get("state") == "UNMEASURED"),
        "n_empty": sum(1 for v in axes.values() if v.get("state") == "EMPTY"),
        "total_rows": sum(int(v.get("n") or 0) for v in axes.values()),
        "n_write_refused": len(refused),
        "write_refused": refused,
        "axes": axes,
        "rule": ("every axis runs on every pass and each writes its own file. The shared report "
                 "is a UNION, never the last writer's result -- a board that shows one lane's "
                 "worst pass and hides three healthy ones teaches the reader to stop looking."),
        "boundary": ("ingestion is not conditioning. A row here is a dated series a family COULD "
                     "condition on; whether it earns anything is the gauntlet's verdict."),
        "write_rule": ("an empty fetch NEVER overwrites a populated axis: a pass that returned 0 "
                       "against a file that holds data is recorded EMPTY_REFUSED_OVERWRITE with "
                       "the count it preserved. Writes are atomic, so a crash mid-write cannot "
                       "truncate an axis either. An axis that has never landed still writes its "
                       "failure record -- that record is the evidence the next session gets."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the per-axis files and the report")
    a = ap.parse_args(argv)
    doc = run_all(a.apply)
    print(f"axis ingest: {doc['n_ok']}/{doc['n_axes']} axis(es) OK, "
          f"{doc['total_rows']:,} row(s) total")
    for name, v in doc["axes"].items():
        if v.get("state") == "UNMEASURED":
            print(f"  {name:<10} UNMEASURED  {str(v.get('error'))[:70]}")
        else:
            extra = f"  ({v['n_failed']} sub-fetch failure(s))" if v.get("n_failed") else ""
            if v.get("write_state") == "EMPTY_REFUSED_OVERWRITE":
                extra += f"  WRITE REFUSED -- preserved {v.get('preserved_n')} on disk"
            elif v.get("write_state") == "WRITE_FAILED":
                extra += f"  WRITE FAILED -- {str(v.get('why'))[:60]}"
            print(f"  {name:<10} {v['state']:<10} n={v['n']:<8} symbols={v['n_symbols']}{extra}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {REPORT}")
    # NON-ZERO ONLY IF EVERY AXIS FAILED. One publisher down is a normal day.
    return 0 if doc["n_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
