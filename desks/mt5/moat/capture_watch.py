"""SAME-DAY CAPTURE COMPLETENESS -- the only moat failure that can never be undone.

THE PRINCIPAL, 2026-09-12: "maximise capture to 100 percent".

WHAT THE EXISTING FENCE CANNOT SEE. `moat_fence.py` watches LIVENESS: heartbeat age, paused
recorder, symbol floor, tick floor. Every one of those answers "is the recorder down RIGHT NOW".
None of them answers "did yesterday capture every symbol", and that is a different failure with a
different signature -- the recorder healthy, the heartbeat fresh, `gaps: 0`, and a third of the
day's symbols simply never written.

Measured on this box the day this was written, against a 377-file complete weekday:

    2026-09-07   261 files   (116 short)
    2026-09-10   263 files   (114 short)
    2026-09-11   260 files   (117 short)   <- YESTERDAY, and nothing had reported it

Three short days in five trading days, none of them noticed, while every liveness reading was
green. That is roughly 30% of three days of proprietary tape, and tape is the one asset on this
desk that CANNOT be rebuilt later: 2029 cannot re-record 2026. Every other defect here costs
time; this one costs the thing time was buying.

WHY SAME-DAY IS THE WHOLE POINT. MT5's `copy_ticks_range` serves what the broker still holds, so
a gap found within hours is often re-pullable and a gap found next month never is. A detector
that runs weekly would be an archaeologist. This runs on the recorder's own cadence and names the
missing SYMBOLS, so the repair is a targeted re-pull rather than a shrug.

THE BASELINE IS MEASURED, NOT HARDCODED. "Complete" is the median file count of recent complete
trading days, so the bar follows the universe as it grows or shrinks and no constant goes stale.
A hardcoded 377 would have to be edited every time Fusion lists an instrument, and an unedited
constant silently becomes a lower bar -- which is the failure mode that lets coverage rot.

IT NEVER CRIES WOLF ON A CLOSED MARKET OR ON TODAY. Weekends legitimately show ~28 files and the
current day is partial by construction until its session ends; flagging either would teach the
operator to ignore the board, which is how the three real short days above went unread.

    python desks/mt5/moat/capture_watch.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "MOAT_CAPTURE.json"

#: Where the recorder writes. Overridable because the moat deliberately does not live inside the
#: repository -- it is the one store that must survive a checkout being blown away.
MOAT = Path(os.environ.get("MOAT_ROOT", r"C:\moat"))
BRONZE = MOAT / "bronze"

#: Subtrees whose per-day completeness is worth judging. `symbol_specs` and `terminal_health`
#: write one row a day by design, so counting them as "short" would be nonsense.
WATCHED = ("mt5_ticks", "mt5_dom")

#: A day at or below this fraction of the complete baseline is treated as MARKET CLOSED rather
#: than short. Weekends here run ~28/377 = 7%, and the lowest real trading day seen is 69%, so
#: the gap between the two populations is enormous and 25% sits safely inside it.
CLOSED_FRACTION = 0.25

#: A trading day below this fraction of baseline is SHORT. Set just under the smallest normal
#: fluctuation: complete days cluster at 377 with the occasional 360 (95%), so 0.90 flags a real
#: loss without firing on ordinary variation.
SHORT_FRACTION = 0.90

#: A missing set this concentrated in ONE asset class is more likely a venue holiday than a
#: recorder fault. 2026-09-07 was US Labor Day and 102 of its 114 missing names (89%) were
#: equities; 2026-09-11's DOM loss spanned six classes and was a genuine outage. The threshold
#: separates those two populations, and the row stays SHORT either way -- this explains, it never
#: excuses, because if the venue really was shut the re-pull returns nothing and costs one call.
DOMINANT_CLASS_FRACTION = 0.80

#: How long a gap stays worth chasing. The broker serves a bounded window of tick history, so
#: past this the tape is simply gone and the row becomes a permanent record rather than a task.
REPULLABLE_DAYS = 7

_DATE_RE = re.compile(r"(20\d{2})(\d{2})(\d{2})")


def _day_of(name: str) -> str | None:
    m = _DATE_RE.search(name)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}{mo:02d}{d:02d}"


def _classify(symbols: list[str]) -> dict[str, int]:
    """Asset-class histogram of a missing set, via the desk's own registry classifier.

    WHY THE COMPOSITION AND NOT JUST THE COUNT. "114 symbols missing" is an alarm; "all 114 are
    US share CFDs" is a diagnosis, and the two lead to completely different actions. It degrades
    to `unclassified` rather than failing: this is a monitor, and a monitor that dies because a
    classifier moved is worse than one that reports a coarser answer.
    """
    try:
        import sys
        for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
            if _p not in sys.path:
                sys.path.insert(0, _p)
        from universe_policy import asset_class_of
    except Exception:
        return {"unclassified": len(symbols)}
    hist: dict[str, int] = {}
    for s in symbols:
        try:
            cls = asset_class_of(s) or "unclassified"
        except Exception:
            cls = "unclassified"
        hist[cls] = hist.get(cls, 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: -kv[1]))


def scan(root: Path = BRONZE) -> dict[str, dict[str, Any]]:
    """Per-day file counts and the SYMBOLS seen, per watched subtree.

    The symbol set is what makes a repair actionable: a count says a third of the day is missing,
    a set says which third, and only the second can be re-pulled.
    """
    out: dict[str, dict[str, Any]] = {}
    for sub in WATCHED:
        base = root / sub
        days: dict[str, set[str]] = defaultdict(set)
        sizes: dict[str, int] = defaultdict(int)
        if not base.exists():
            out[sub] = {"state": "ABSENT", "days": {}, "sizes": {}}
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            day = _day_of(p.name) or _day_of(p.parent.name)
            if day is None:
                continue
            # The symbol is whichever path part is not the date. Recorders differ on whether they
            # key by directory or by filename, so both shapes are accepted rather than assumed.
            sym = p.parent.name if _day_of(p.name) else p.name
            sym = _DATE_RE.sub("", sym).strip("._-") or p.stem
            days[day].add(sym)
            sizes[day] += p.stat().st_size
        out[sub] = {"state": "PRESENT",
                    "days": {d: sorted(s) for d, s in days.items()},
                    "sizes": dict(sizes)}
    return out


def judge(scanned: dict[str, dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    now_day = today or datetime.now(tz=UTC).date()
    report: dict[str, Any] = {}
    worst = "OK"
    actionable: list[dict[str, Any]] = []

    for sub, data in scanned.items():
        if data["state"] != "PRESENT":
            report[sub] = {"state": "ABSENT",
                           "why": f"{BRONZE / sub} does not exist -- nothing is being recorded "
                                  f"here, which is UNMEASURED rather than complete"}
            worst = "ATTENTION"
            continue
        days: dict[str, list[str]] = data["days"]
        if not days:
            report[sub] = {"state": "EMPTY", "why": "no dated files at all"}
            worst = "ATTENTION"
            continue

        counts = {d: len(v) for d, v in days.items()}
        # BASELINE FROM COMPLETE DAYS ONLY, and computed BEFORE anything is classified, so a run
        # of short days cannot drag the bar down to meet them. That self-lowering bar is exactly
        # how a coverage floor rots into a rubber stamp.
        peak = max(counts.values())
        complete = [n for n in counts.values() if n >= peak * SHORT_FRACTION]
        baseline = int(statistics.median(complete)) if complete else peak

        rows = []
        union: set[str] = set()
        for v in days.values():
            union |= set(v)
        # CROSS-SUBTREE EVIDENCE. A subtree sitting at closed-market levels on a day when ANOTHER
        # subtree recorded a full session did not meet a closed market -- it failed. Without this,
        # 2026-09-11 read MARKET_CLOSED for mt5_dom (13/130) on a Friday when mt5_ticks was
        # 245/245, which would have filed a real DOM outage as a holiday.
        others = {d: len(v) for sub2, dd in scanned.items() if sub2 != sub
                  and dd.get("state") == "PRESENT" for d, v in dd["days"].items()}
        other_peak = max(others.values()) if others else 0
        for d in sorted(counts):
            n = counts[d]
            frac = n / baseline if baseline else 0.0
            dt_d = datetime.strptime(d, "%Y%m%d").replace(tzinfo=UTC).date()
            age_days = (now_day - dt_d).days
            other_open = bool(other_peak) and others.get(d, 0) > other_peak * SHORT_FRACTION
            if age_days <= 0:
                state = "IN_PROGRESS"
            elif frac <= CLOSED_FRACTION and not other_open:
                state = "MARKET_CLOSED"
            elif (frac <= CLOSED_FRACTION and other_open) or frac < SHORT_FRACTION:
                state = "SHORT"
            else:
                state = "COMPLETE"
            row = {"day": d, "files": n, "baseline": baseline, "fraction": round(frac, 3),
                   "state": state, "age_days": age_days,
                   "megabytes": round(data["sizes"].get(d, 0) / 1e6, 1)}
            if state == "SHORT":
                missing = sorted(union - set(days[d]))
                row["n_missing"] = len(missing)
                row["missing_symbols"] = missing[:60]
                row["repullable"] = age_days <= REPULLABLE_DAYS
                row["missing_by_class"] = _classify(missing)
                # A WHOLE ASSET CLASS ABSENT IS A DIFFERENT FACT FROM A CAPTURE FAILURE. When
                # every missing symbol belongs to one class and nothing else is short, the far
                # likelier explanation is that class's market was shut -- 2026-09-07 was US
                # Labor Day and all 114 missing names were US share CFDs. Saying so is not the
                # same as excusing it: the row stays SHORT and re-pullable, because if the venue
                # really was closed the re-pull simply returns nothing and costs one request.
                hist = row["missing_by_class"]
                top, top_n = next(iter(hist.items()))
                share = top_n / max(len(missing), 1)
                if share >= DOMINANT_CLASS_FRACTION:
                    row["likely_cause"] = (
                        f"{top_n} of {len(missing)} missing symbols ({share:.0%}) are {top!r} -- "
                        f"a single venue's session, so a market holiday is the likelier "
                        f"explanation than a recorder fault. Verify with a re-pull: it costs one "
                        f"request and settles it either way.")
                else:
                    row["likely_cause"] = (
                        f"missing symbols span {len(hist)} asset classes "
                        f"({', '.join(f'{k} {v}' for k, v in list(hist.items())[:4])}) -- no "
                        f"single venue explains this, so it is a RECORDER fault rather than a "
                        f"closed market, and it is the kind that repeats until it is fixed.")
                row["why"] = (
                    f"{baseline - n} of {baseline} symbol-files never written while the recorder "
                    f"reported healthy. " + (
                        f"Still inside the {REPULLABLE_DAYS}-day window the broker serves, so a "
                        f"targeted copy_ticks_range re-pull can still recover it."
                        if age_days <= REPULLABLE_DAYS else
                        "Past the re-pull window: this tape is permanently gone and this row is "
                        "a record, not a task."))
                worst = "ATTENTION"
                if age_days <= REPULLABLE_DAYS:
                    actionable.append({"subtree": sub, **{k: row[k] for k in
                                       ("day", "files", "baseline", "n_missing")},
                                       "missing_symbols": missing[:60]})
            rows.append(row)

        report[sub] = {"state": "PRESENT", "baseline": baseline, "days": rows,
                       "n_short": sum(1 for r in rows if r["state"] == "SHORT")}

    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "moat_root": str(MOAT),
        "status": worst,
        "subtrees": report,
        "actionable_repulls": actionable,
        "n_actionable": len(actionable),
        "rule": ("COMPLETE is the median of complete days, measured every run, never a constant. "
                 "A closed market and a partial current day are states, not failures -- an alarm "
                 "that fires on either is one an operator learns to scroll past."),
        "why_it_matters": ("Tape is the only asset here that calendar time cannot give back. "
                          "Every other defect on this desk costs time; an unrecorded day costs "
                          "the thing the time was buying."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--days", type=int, default=21, help="how many recent days to print")
    a = ap.parse_args(argv)
    doc = judge(scan())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(doc, indent=1))
        return 0 if doc["status"] == "OK" else 1

    print(f"moat capture: {doc['status']}   root {doc['moat_root']}")
    for sub, r in doc["subtrees"].items():
        if r.get("state") != "PRESENT":
            print(f"  {sub:<12} {r.get('state')}  {r.get('why','')[:70]}")
            continue
        print(f"  {sub:<12} baseline {r['baseline']} file(s)/day, {r['n_short']} short day(s)")
        for row in r["days"][-a.days:]:
            mark = {"COMPLETE": "  ", "SHORT": "!!", "MARKET_CLOSED": "--",
                    "IN_PROGRESS": ".."}.get(row["state"], "??")
            print(f"     {mark} {row['day']}  {row['files']:>4}/{row['baseline']:<4} "
                  f"{row['fraction']*100:5.1f}%  {row['megabytes']:>7.1f} MB  {row['state']}")
    if doc["n_actionable"]:
        print(f"\n  RE-PULLABLE NOW -- {doc['n_actionable']} day(s) still inside the broker's "
              f"window:")
        for r in doc["actionable_repulls"]:
            print(f"     {r['day']}  {r['subtree']}  {r['n_missing']} symbol(s) missing")
            print(f"        e.g. {', '.join(r['missing_symbols'][:10])}")
    print(f"\n-> {OUT}")
    return 0 if doc["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
