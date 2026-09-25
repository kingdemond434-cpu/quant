#!/usr/bin/env python3
"""BAR COVERAGE RATCHETS: instruments-by-timeframe goes UP and never down.

WHAT NOTHING GUARDED UNTIL NOW. `check_bar_history_floor.py` ratchets how DEEP each symbol's H1
is, and `check_bar_coverage.py` asks whether a traded symbol has bars at all. Neither watches the
GRID -- how many instruments hold each of the seven charts -- so the whole M1 ladder could go from
248 files to four and every fence would stay green. That is not hypothetical: the build box holds
four M15 parquets against the trading box's 248, and for weeks the desk read the thin side as "the
broker keeps less M1 than H1" rather than as a collection failure.

MEASURED 2026-09-24 on the trading box: 248 instruments, and after `fill_bar_gaps` all seven
charts on all 248 -- 1,736 of 1,736 cells. That is the mark this ratchet seals.

THREE THINGS IT DOES THAT A NAIVE COUNT WOULD GET WRONG.

  PER HOST, ALWAYS. The build box and the trading box hold different universes because only one
  of them has a terminal. One shared mark would either fail forever on the build box or seal the
  build box's four-file M15 as the desk's high water and let the trading box lose 244 charts in
  silence. The mark is keyed by hostname, and a host with no mark yet SEALS rather than passes --
  a ratchet with no memory is not one.

  THE DENOMINATOR IS RATCHETED TOO, WHICH IS THE SUBTLE ONE. Coverage as a percentage can be
  raised by RETIRING instruments instead of fetching bars: drop three delisted rows and the
  fraction rises without a single new file. So the mark holds the COUNT of instruments as well
  as the per-chart counts, and a fall in the instrument count is itself a regression to explain.

  A VENUE LIMIT IS NOT A DEFECT AND IS NOT A PASS EITHER. `bar_coverage_verdicts.json` records
  what MetaTrader said about every cell the desk does not hold. A cell the venue will not serve
  is EXCUSED by name and counted separately; a cell with no verdict at all is a hole nobody has
  looked at, and that is the row this fence exists to surface. Absence never resolves to a clean
  verdict (L1.28a).

IT LOWERS NOTHING AND IT FETCHES NOTHING. Read-only over the parquet directory and two JSON
files. `--init` seals a first mark and REFUSES to overwrite one: the only way a mark goes down is
a person editing the file with a reason.

    python scripts/check_bar_coverage_ratchet.py            # measure, compare, raise, verdict
    python scripts/check_bar_coverage_ratchet.py --init     # seal this host's first mark
    python scripts/check_bar_coverage_ratchet.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "desks" / "mt5" / "data" / "universe"
VERDICTS = ROOT / "desks" / "mt5" / "data" / "bar_coverage_verdicts.json"
HIGH_WATER = ROOT / "desks" / "mt5" / "data" / "bar_coverage_high_water.json"
REPORT = ROOT / "desks" / "mt5" / "reports" / "BAR_COVERAGE_RATCHET.json"

#: A chart can lose a file to a mid-write crash or a symbol the venue drops for a session. One
#: file in a hundred is noise; a floor that fires on noise gets deleted, which is worse than a
#: floor one file low. Anything past this is named and fails.
TOLERANCE_FRAC = 0.02
#: Verdicts that EXCUSE a missing cell: the venue was asked and will not serve it.
EXCUSED = frozenset({"NOT_OFFERED", "BROKER_SERVES_NOTHING", "NO_SUCH_TIMEFRAME", "BELOW_FLOOR"})


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def host() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname() or "unknown"


def timeframes() -> tuple[str, ...]:
    """The canonical ladder, imported and never spelled here (four spellings already drift)."""
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from mt5desk.universe_registry import TIMEFRAMES
    return tuple(TIMEFRAMES)


def measure(universe: Path | None = None, verdicts: Path | None = None) -> dict[str, Any]:
    """This host's coverage grid right now. Pure: reads two paths, decides nothing."""
    base = universe or UNIVERSE
    ladder = timeframes()
    have: dict[str, set[str]] = defaultdict(set)
    pattern = re.compile(rf"^(.*)_({'|'.join(ladder)})$")
    for path in base.glob("*.parquet"):
        got = pattern.match(path.stem)
        if got:
            have[got.group(1)].add(got.group(2))
    by_tf = {tf: sum(1 for s in have if tf in have[s]) for tf in ladder}
    excused, unexplained = _excuses(have, ladder, verdicts or VERDICTS)
    return {
        "at": _now(), "host": host(), "ladder": list(ladder),
        "n_instruments": len(have),
        "by_timeframe": by_tf,
        "n_cells_held": sum(by_tf.values()),
        "n_cells_possible": len(have) * len(ladder),
        "n_full_ladder": sum(1 for s in have if set(ladder) <= have[s]),
        "n_cells_excused": len(excused),
        "cells_excused": excused[:40],
        "n_cells_unexplained": len(unexplained),
        "cells_unexplained": unexplained[:40],
    }


def _excuses(have: dict[str, set[str]], ladder: tuple[str, ...],
             path: Path) -> tuple[list[str], list[str]]:
    """Missing cells split into (the venue was asked and said no, nobody asked)."""
    try:
        doc = json.loads(path.read_text("utf-8-sig", errors="replace"))
        rows = doc.get("cells") if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        rows = {}
    rows = rows if isinstance(rows, dict) else {}
    excused: list[str] = []
    unexplained: list[str] = []
    for sym in sorted(have):
        for tf in ladder:
            if tf in have[sym]:
                continue
            key = f"{sym}_{tf}"
            verdict = str((rows.get(key) or {}).get("verdict") or "")
            (excused if verdict in EXCUSED else unexplained).append(
                f"{key}:{verdict or 'NO_VERDICT'}")
    return excused, unexplained


def read_marks() -> dict[str, Any]:
    """The sealed marks. A MISSING FILE IS A FAILURE, NEVER AN EMPTY DICT.

    An empty default is how a ratchet quietly compares every run against zero and reports green
    forever; `check_mt5_coverage_floor` records that exact incident and this file refuses to
    repeat it.
    """
    try:
        doc = json.loads(HIGH_WATER.read_text("utf-8-sig"))
    except OSError as exc:
        raise SystemExit(
            f"FAIL: {HIGH_WATER} is absent ({exc.strerror}). A ratchet with no memory is not a "
            f"ratchet -- it would compare this run against nothing and pass. Seal this host's "
            f"first mark with: python scripts/check_bar_coverage_ratchet.py --init") from exc
    except ValueError as exc:
        raise SystemExit(f"FAIL: {HIGH_WATER} is not readable JSON: {exc}") from exc
    return doc if isinstance(doc, dict) else {}


def evaluate(now: dict[str, Any], marks: dict[str, Any],
             tolerance: float = TOLERANCE_FRAC) -> dict[str, Any]:
    """Compare, raise what rose, and name every fall. PURE -- writes nothing, so a test can
    assert on it without a disk."""
    raw_hosts = marks.get("hosts")
    hosts: dict[str, Any] = raw_hosts if isinstance(raw_hosts, dict) else {}
    raw_prior = hosts.get(now["host"])
    prior: dict[str, Any] | None = raw_prior if isinstance(raw_prior, dict) else None
    failures: list[str] = []
    raised: list[str] = []
    new = {"sealed_at": (prior.get("sealed_at") if prior else None) or now["at"],
           "measured_at": now["at"],
           "n_instruments": int(now["n_instruments"]),
           "by_timeframe": dict(now["by_timeframe"]),
           "n_full_ladder": int(now["n_full_ladder"])}
    if prior is None:
        return {"verdict": "SEALED", "failures": [], "raised": [],
                "why": (f"no mark for host {now['host']}: this measurement is the first and is "
                        f"floored here. A first measurement is never a pass and never a fail"),
                "marks": {**marks, "hosts": {**hosts, now["host"]: new}}}

    def _cmp(label: str, was: Any, is_now: int) -> None:
        if not isinstance(was, (int, float)):
            return
        if is_now + 1e-9 < float(was) * (1.0 - tolerance):
            failures.append(f"{label}: {is_now} fell more than {tolerance:.0%} below its "
                            f"high-water {int(was)}")
        elif is_now > float(was):
            raised.append(f"{label}: {int(was)} -> {is_now}")

    _cmp("instruments", prior.get("n_instruments"), int(now["n_instruments"]))
    _cmp("full_ladder", prior.get("n_full_ladder"), int(now["n_full_ladder"]))
    was_tf: dict[str, Any] = prior.get("by_timeframe") or {}
    now_tf: dict[str, Any] = now.get("by_timeframe") or {}
    for tf in now["ladder"]:
        # A RUNG THIS RUN DID NOT MEASURE IS NOT A RUNG THAT FELL TO ZERO. Reading an absent
        # key as 0 would report the ladder's worst possible regression every time the measurer
        # skipped a chart -- absence never resolves to a verdict (L1.28a).
        if tf not in now_tf:
            continue
        _cmp(f"tf:{tf}", was_tf.get(tf), int(now_tf[tf]))
    # A MARK ONLY EVER RISES. Keeping the max explicitly means a regression never writes itself
    # in as the new mark on the very run that reported it.
    new["n_instruments"] = max(int(now["n_instruments"]),
                               int(prior.get("n_instruments") or 0))
    new["n_full_ladder"] = max(int(now["n_full_ladder"]),
                               int(prior.get("n_full_ladder") or 0))
    new["by_timeframe"] = {tf: max(int(now_tf[tf]), int(was_tf.get(tf) or 0))
                           for tf in now["ladder"] if tf in now_tf}
    # A timeframe the mark knows and this run does not measure at all is kept, not dropped: a
    # ladder that loses a rung must not lose its mark with it.
    for tf, was in was_tf.items():
        new["by_timeframe"].setdefault(tf, int(was))
    return {"verdict": "FAIL" if failures else "OK", "failures": failures, "raised": raised,
            "why": "", "marks": {**marks, "hosts": {**hosts, now["host"]: new}}}


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--init", action="store_true", help="seal this host's first mark")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE_FRAC)
    a = ap.parse_args(argv)

    now = measure()
    if a.init and HIGH_WATER.exists():
        marks = read_marks()
        if (marks.get("hosts") or {}).get(now["host"]):
            print(f"REFUSED: {HIGH_WATER} already holds a mark for {now['host']}. A re-seal is "
                  f"how a ratchet is silently lowered; the only way down is a person editing "
                  f"that file with a reason.")
            return 1
    # A HOST THAT HAS NEVER SEALED BOOTSTRAPS; A HOST THAT HAS, NEVER RE-SEALS. The marks live
    # under `desks/mt5/data/`, which is BOX STATE and not a committed baseline -- so an absent
    # file on a fresh host is expected rather than tampering, and dying on it would mean this
    # fence fails forever on every machine but the one that ran `--init`. The bootstrap verdict
    # is SEALED, which is explicitly not a pass; what can never happen is a mark that already
    # exists being written DOWN, and that is enforced above and in `evaluate`.
    marks = ({"_": ("HIGH-WATER MARKS for bar coverage, PER HOST. Instruments-by-timeframe and "
                    "the instrument count itself only ever rise. Sealed on a host's first run, "
                    "raised by the fence when a run measures higher, NEVER lowered by code: "
                    "nothing lowers a mark but a person editing this file with a reason."),
              "tolerance": TOLERANCE_FRAC, "hosts": {}}
             if not HIGH_WATER.exists() else read_marks())
    got = evaluate(now, marks, tolerance=a.tolerance)
    _write(HIGH_WATER, got["marks"])
    _write(REPORT, {**now, "verdict": got["verdict"], "failures": got["failures"],
                    "raised": got["raised"], "why": got["why"],
                    "tolerance": a.tolerance, "marks_path": str(HIGH_WATER)})
    if a.json:
        print(json.dumps({**now, "verdict": got["verdict"], "failures": got["failures"],
                          "raised": got["raised"]}, indent=1))
        return 1 if got["verdict"] == "FAIL" else 0
    print(f"bar coverage ratchet on {now['host']}: {got['verdict']}")
    print(f"  {now['n_instruments']} instrument(s); {now['n_cells_held']}/"
          f"{now['n_cells_possible']} cell(s); {now['n_full_ladder']} hold the full ladder")
    print("  " + "  ".join(f"{tf}:{now['by_timeframe'][tf]}" for tf in now["ladder"]))
    if now["n_cells_excused"]:
        print(f"  {now['n_cells_excused']} missing cell(s) EXCUSED by a venue verdict: "
              f"{now['cells_excused'][:6]}")
    if now["n_cells_unexplained"]:
        print(f"  {now['n_cells_unexplained']} missing cell(s) with NO verdict -- nobody asked "
              f"the venue: {now['cells_unexplained'][:6]}")
    for line in got["raised"]:
        print(f"  raised  {line}")
    for line in got["failures"]:
        print(f"  FAIL    {line}")
    if got["why"]:
        print(f"  {got['why']}")
    return 1 if got["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
