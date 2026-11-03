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

WHY A DRIVER AND NOT AN EDIT TO `axis_ingest.py`. The trading box's copy of that file is 438
lines AHEAD of this tree -- it has had work done on it that has not reached here. Editing it from
here would have reverted that work, which is the exact failure the moneypath guard exists to stop
(1,078 lines once vanished from gateway.py this way). So this IMPORTS whatever version is
present and drives its own `INGESTERS` table. New axes added there are picked up here for free,
with no second list to keep in sync.

FAILURE IS PER-AXIS AND NEVER FATAL. FRED timed out and reset from this box's IP (7/7,
measured 2026-09-12, the fredgraph.csv website host; the ingester now reads the keyed API
first). That is a fact about one publisher's edge network, not about the axis lane, and it must
never stop COT, BIS or ECB from refreshing. Each ingester is caught individually and recorded as
UNMEASURED with its error -- a failed fetch is not evidence that an axis is barren (L1.28a).

    python desks/mt5/research/axis_ingest_all.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
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

    RED when any streak exceeds `RED_AFTER_RUNS`; GREEN when none does; UNMEASURED when this pass
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
    return {
        "at": now.isoformat(timespec="seconds"),
        "check": "dependency_liveness",
        "rule": (f"RED when any external source or series delivers no data for more than "
                 f"{RED_AFTER_RUNS} consecutive MT5-AxisIngest passes"),
        "red_after_runs": RED_AFTER_RUNS,
        "verdict": "UNMEASURED" if not deps else ("RED" if red else "GREEN"),
        "n_dependencies": len(deps),
        "n_red": len(red),
        "red": red,
        "dependencies": deps,
        # HOW EACH SOURCE WAS READ THIS PASS: whether a key was held (a boolean, never the key)
        # and which transport delivered each series -- the two facts only the box can tell.
        "sources": {name: {k: axes[name][k] for k in ("key_present", "transport")
                           if k in axes[name]}
                    for name in EXTERNAL_AXES if isinstance(axes.get(name), dict)},
    }


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
            target = OUT_DIR / f"{name}.json"
            if not n and _count(_read(target)):
                # AN EMPTY PASS NEVER OVERWRITES DATA. The previous file holds real, dated rows;
                # replacing it with zero would turn one publisher's bad hour into an axis that
                # reads barren to every family that conditions on it (L1.28a).
                axes[name]["kept_previous"] = True
                continue
            target.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    ok = [k for k, v in axes.items() if v.get("state") == "OK"]
    return {
        "at": now.isoformat(timespec="seconds"),
        "driver": "axis_ingest_all -- every axis, every pass",
        "n_axes": len(axes),
        "n_ok": len(ok),
        "n_unmeasured": sum(1 for v in axes.values() if v.get("state") == "UNMEASURED"),
        "n_empty": sum(1 for v in axes.values() if v.get("state") == "EMPTY"),
        "total_rows": sum(int(v.get("n") or 0) for v in axes.values()),
        "axes": axes,
        "rule": ("every axis runs on every pass and each writes its own file. The shared report "
                 "is a UNION, never the last writer's result -- a board that shows one lane's "
                 "worst pass and hides three healthy ones teaches the reader to stop looking."),
        "boundary": ("ingestion is not conditioning. A row here is a dated series a family COULD "
                     "condition on; whether it earns anything is the gauntlet's verdict."),
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
            print(f"  {name:<10} {v['state']:<10} n={v['n']:<8} symbols={v['n_symbols']}{extra}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {REPORT}")
    live = update_liveness(_read(LIVENESS), doc["axes"], datetime.now(tz=UTC))
    LIVENESS.write_text(json.dumps(live, indent=1), encoding="utf-8")
    print(f"dependency liveness: {live['verdict']}  ({live['n_red']} RED of "
          f"{live['n_dependencies']}){'  ' + ', '.join(live['red']) if live['red'] else ''}")
    print(f"-> {LIVENESS}")
    # NON-ZERO ONLY IF EVERY AXIS FAILED. One publisher down is a normal day.
    return 0 if doc["n_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
