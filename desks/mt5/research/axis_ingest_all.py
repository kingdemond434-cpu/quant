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

FAILURE IS PER-AXIS AND NEVER FATAL. FRED's resets were its edge refusing the client token (see
`axis_ingest.FRED_UA`); the ingester also reads the keyed API first. Either way one publisher's
outage must never stop COT, BIS or ECB from refreshing. Each ingester is caught individually and
recorded as UNMEASURED with its error -- a failed fetch is not evidence that an axis is barren
(L1.28a).

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
LIVENESS = DESK / "reports" / "DEPENDENCY_LIVENESS.json"

#: THE DEPENDENCY-LIVENESS RED CHECK (Rule 23, 2026-10-29). FRED came back with nothing on every
#: pass from 2026-09-12 to 2026-10-29 and the task still exited 0 -- `run_all` returns 0 when ANY
#: axis is OK, so process_health read MT5-AxisIngest as OK for seven weeks while one of its four
#: publishers delivered zero rows. A per-pass verdict cannot see that; a streak can. Every external
#: source and every series it names carries a count of consecutive passes that returned no data
#: (empty, error, refused or unreachable alike -- each is "no data arrived"), and any count ABOVE
#: this many is RED. `ops/process_health.py` reads the verdict, so a RED dependency raises the
#: board's ATTENTION on the clock that already watches every organ.
RED_AFTER_RUNS = 2
#: The axes that are a publisher on the far end of a network. The learned-forecast axes are the
#: desk's own outputs; an empty one is a model question, not a dependency outage.
EXTERNAL_AXES = ("bis", "cot", "ecb", "fred")


def _count(doc: dict[str, Any]) -> int:
    """Rows for a tabular axis, series for a time-series one. Both are 'how much landed'."""
    for k in ("n_rows", "n_series"):
        v = doc.get(k)
        if isinstance(v, int):
            return v
    return 0


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _outcomes(axes: dict[str, Any]) -> dict[str, tuple[bool, str]]:
    """(delivered data?, reason) for every external source and every series it names."""
    out: dict[str, tuple[bool, str]] = {}
    for name in EXTERNAL_AXES:
        v = axes.get(name)
        if not isinstance(v, dict):
            continue
        if v.get("state") == "UNMEASURED":
            out[name] = (False, str(v.get("error") or "UNMEASURED")[:240])
            continue
        out[name] = (bool(v.get("n")), "" if v.get("n") else "EMPTY: 0 rows/series this pass")
        failed = v.get("failed") or {}
        for sid, st in (v.get("series_state") or {}).items():
            ok = st == "OK"
            out[f"{name}/{sid}"] = (ok, "" if ok else str(failed.get(sid) or st)[:240])
    return out


def update_liveness(prev: dict[str, Any] | None, axes: dict[str, Any],
                    now: datetime) -> dict[str, Any]:
    """Advance every dependency's consecutive-no-data streak by one pass and judge it.

    RED when any streak exceeds `RED_AFTER_RUNS`; AMBER when none does but some dependency missed
    this pass (a streak of 1..RED_AFTER_RUNS is not a clean bill of health, so the top line may
    not read GREEN over it); GREEN only when every dependency delivered; UNMEASURED when this pass
    read no external source at all (an ingest that never ran is not a clean bill of health)."""
    old = (prev or {}).get("dependencies") or {}
    outcomes = _outcomes(axes)
    # A SOURCE THAT FAILED WHOLE STILL OWES ITS SERIES A PASS. When the ingester raised, no series
    # was asked, and dropping their streaks would reset a run of empties to nothing.
    for key in old:
        src = key.split("/", 1)[0]
        if "/" in key and key not in outcomes and src in outcomes and not outcomes[src][0]:
            outcomes[key] = (False, f"source failed whole: {outcomes[src][1]}"[:240])
    deps: dict[str, Any] = {}
    for key, (ok, reason) in sorted(outcomes.items()):
        was = old.get(key) or {}
        streak = 0 if ok else int(was.get("empty_streak") or 0) + 1
        deps[key] = {
            "empty_streak": streak,
            "verdict": "RED" if streak > RED_AFTER_RUNS else ("GREEN" if ok else "AMBER"),
            "last_ok_at": now.isoformat(timespec="seconds") if ok else was.get("last_ok_at"),
            "first_empty_at": (None if ok else
                               (was.get("first_empty_at") if streak > 1 else
                                now.isoformat(timespec="seconds"))),
            "last_reason": reason,
        }
    red = sorted(k for k, d in deps.items() if d["verdict"] == "RED")
    amber = sorted(k for k, d in deps.items() if d["verdict"] == "AMBER")
    return {
        "at": now.isoformat(timespec="seconds"),
        "check": "dependency_liveness",
        "rule": (f"RED when any external source or series delivers no data for more than "
                 f"{RED_AFTER_RUNS} consecutive MT5-AxisIngest passes"),
        "red_after_runs": RED_AFTER_RUNS,
        "verdict": ("UNMEASURED" if not deps else
                    "RED" if red else "AMBER" if amber else "GREEN"),
        "n_dependencies": len(deps),
        "n_red": len(red),
        "red": red,
        "n_amber": len(amber),
        "amber": amber,
        "dependencies": deps,
        # HOW EACH SOURCE WAS READ THIS PASS: whether a key was held (a boolean, never the key)
        # and which transport delivered each series -- the two facts only the box can tell.
        "sources": {name: {k: axes[name][k] for k in ("key_present", "transport")
                           if k in axes[name]}
                    for name in EXTERNAL_AXES if isinstance(axes.get(name), dict)},
    }


def _on_disk(path: Path) -> int:
    """How much the axis ALREADY holds. Unreadable is 0, and that is the safe direction here:
    a file this driver cannot parse is not evidence of data worth protecting, and refusing to
    refresh an axis because its previous document is corrupt would freeze the lane permanently."""
    return _count(_read(path))


#: Windows refuses `os.replace` with PermissionError while another process holds the destination
#: open (a reader mid-`read_text`, an indexer, AV). Retried briefly, then written in place: a
#: non-atomic write that lands beats an atomic one that never does. A destination that cannot be
#: written at all (read-only, WinError 5 on both routes) still raises, and the caller records it.
REPLACE_RETRIES = 3
REPLACE_BACKOFF_S = 0.2


def atomic_write_text(path: Path, text: str) -> str:
    """tmp + `os.replace`; on a Windows PermissionError, retry, then fall back to a direct write.

    Returns how it landed ("atomic" or "direct_fallback"). The temp file never survives."""
    import time
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        for attempt in range(REPLACE_RETRIES):
            try:
                os.replace(tmp, path)
                return "atomic"
            except PermissionError:
                if attempt + 1 < REPLACE_RETRIES:
                    time.sleep(REPLACE_BACKOFF_S)
        path.write_text(text, encoding="utf-8")
        return "direct_fallback"
    finally:
        with suppress(OSError):
            tmp.unlink()


def _carry_stale(doc: dict[str, Any], prior: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """A PARTIAL PASS NEVER ERASES WHAT IT DID NOT REFRESH.

    Every series this pass ASKED for (its `series_state`) that did not land, but the previous file
    holds, is carried forward marked `stale` with the time it last refreshed -- so one DGS2 failure
    does not erase T10Y2Y. Only asked-for ids are carried: a series the ingester has since dropped
    (the IDEAS_ONLY copyrighted ones) must not ride back into live input on an old file. The
    series' `series_state` keeps this pass's failure, so the liveness streak still advances."""
    fresh, asked, old = doc.get("series"), doc.get("series_state"), prior.get("series")
    if not (isinstance(fresh, dict) and isinstance(asked, dict) and isinstance(old, dict)):
        return doc, []
    out = {**doc, "series": dict(fresh)}
    carried = []
    for sid in asked:
        prev = old.get(sid)
        if sid in fresh or not isinstance(prev, dict) or not prev.get("points"):
            continue
        out["series"][sid] = {**prev, "stale": True,
                              "stale_since": prev.get("stale_since") or prior.get("at")}
        carried.append(sid)
    if carried:
        out["stale_series"] = sorted(carried)
        out["n_stale"] = len(carried)
    return out, sorted(carried)


def _write_axis(path: Path, doc: dict[str, Any], n: int) -> dict[str, Any]:
    """Write one axis, and REFUSE when the write would replace data with nothing.

    Returns the fields the report carries for this axis's write. Never raises: an axis whose file
    cannot be replaced must not take the other three down with it.
    """
    prior = _read(path)
    prev = _count(prior)
    if n == 0 and prev > 0:
        # THE RULE. A fetch that came back empty is a fact about this pass, never a new state of
        # the world, and the previous document is the better estimate of the axis until a
        # non-empty fetch says otherwise (L1.28a).
        return {"written": False, "write_state": "EMPTY_REFUSED_OVERWRITE", "preserved_n": prev,
                "why": (f"this pass returned 0 and the file on disk holds {prev}; an empty fetch "
                        "never overwrites a populated axis")}
    carried: list[str] = []
    if n and prior:
        doc, carried = _carry_stale(doc, prior)
    # ATOMIC. A direct `write_text` that dies mid-stream truncates the axis, which is the same
    # loss by a slower route. `os.replace` is atomic on NTFS and POSIX alike.
    try:
        how = atomic_write_text(path, json.dumps(doc, indent=1))
    except OSError as exc:
        # Measured lesson (CLAUDE.md): `os.replace` onto a read-only destination is legal on
        # POSIX and raises WinError 5 here. Report it; never crash the lane.
        return {"written": False, "write_state": "WRITE_FAILED",
                "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
    out: dict[str, Any] = {"written": True,
                           "write_state": "WRITTEN" if n else "WRITTEN_FIRST_RECORD",
                           "preserved_n": prev, "write_mode": how}
    if carried:
        out["stale_carried"] = carried
    return out


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
            "failed": {k: str(v)[:240] for k, v in (doc.get("failed") or {}).items()},
        }
        if isinstance(doc.get("series_state"), dict):
            axes[name]["series_state"] = dict(doc["series_state"])
        for k in ("key_present", "transport", "ideas_only"):
            if k in doc:
                axes[name][k] = doc[k]
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
    atomic_write_text(REPORT, json.dumps(doc, indent=1))
    print(f"-> {REPORT}")
    live = update_liveness(_read(LIVENESS), doc["axes"], datetime.now(tz=UTC))
    atomic_write_text(LIVENESS, json.dumps(live, indent=1))
    print(f"dependency liveness: {live['verdict']}  ({live['n_red']} RED, "
          f"{live['n_amber']} AMBER of {live['n_dependencies']})"
          f"{'  ' + ', '.join(live['red']) if live['red'] else ''}")
    print(f"-> {LIVENESS}")
    # NON-ZERO ONLY IF EVERY AXIS FAILED. One publisher down is a normal day.
    return 0 if doc["n_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
