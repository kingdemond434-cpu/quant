"""EVERY CONFIGURED SEAT DONATES, OR IT IS NAMED. Seat -> clock -> last donation, measured.

WHY THIS IS A DIFFERENT FENCE FROM THE TWO IT SITS BESIDE, because all three read the same
directory and answer different questions:

    check_producer_yield.py   is a producer PRODUCING relative to its peers? (DEAD / STARVED)
    check_organ_liveness.py   does an organ leave an artifact at all?
    this file                 is each seat donating ON ITS OWN CADENCE, and does it HAVE one?

THE FAILURE THIS EXISTS TO CATCH, measured on the trading box 2026-09-23: deepseek donated
0.1 hours ago and kimi 240 hours ago, and both read as "a seat in data/intelligence" to
everything that counted rows. The difference is a clock -- `quant-deepseek.timer` fires every
hour on the VPS and `kimi_hunter.py` had no box clock at all -- and no artifact anywhere said
so. A seat with no clock is not a slow seat; it is an unscheduled one, and the two have
completely different remedies (fix the organ vs. give it a clock).

SO A SEAT WITH NO CLOCK IS UNMEASURED, NEVER A PASS (L1.28a). It is counted, listed and named
with the fact that nothing schedules it. Reporting it as healthy because it has no cadence to
miss is the exact inversion that let four seats sit dark for eleven days.

AND A SEAT IS JUDGED ONLY WHERE ITS CLOCK RUNS. `quant-kimi-hunter.timer` is a VPS unit; this
checkout on the Windows box holds a MIRROR of what the VPS wrote, so "old" there is not "stale"
-- judging it here would fail the gate on every box for work that is happening correctly
somewhere else. Each seat's clock says which host owns it, `--strict` judges them all anyway,
and the host that is skipped is named rather than silently dropped.

    python scripts/check_seat_health.py
    python scripts/check_seat_health.py --strict --window-cadences 2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "SEAT_HEALTH.json"
RETIREMENTS = ROOT / "docs" / "research" / "retirements.jsonl"

INTEL_ROOTS = (ROOT / "data" / "intelligence", DESK / "data" / "intelligence")

UNMEASURED = "UNMEASURED"

#: How many of its own cadences a seat may miss before it is OVERDUE.
#:
#: NOT ONE. A free-tier route is rate-limited by design, a crawl can meet a 503, and a box can
#: reboot -- an hourly seat that missed a single hour is a seat working normally, and a fence
#: that called that a defect would be forced off within a week, which is how a fence stops being
#: read. Three consecutive misses is no longer noise: it is a seat that has stopped.
WINDOW_CADENCES = 3.0

#: And never less than this, however fast the clock. A ten-minute seat judged at thirty minutes
#: would fail on one slow crawl; the floor buys the same tolerance a slower seat gets for free.
MIN_WINDOW_H = 6.0

#: seat directory under data/intelligence -> the organ that fills it. DECLARED, because the
#: mapping is not inferable: `asia_plane` donates into `asia/`, `deepseek_cycle` into
#: `deepseek/`, and a checker that guessed would report a working seat as dead on a rename.
#: A seat absent from here is still measured -- it is discovered from its own directory -- but
#: it has no organ to look a clock up for, and therefore reads UNMEASURED with that said.
SEAT_ORGANS: dict[str, str] = {
    "kimi": "scripts/kimi_hunter.py",
    "deepseek": "ops/run_deepseek_factory.sh",
    "youtube": "scripts/collect_youtube_corpus.py",
    "world": "desks/mt5/side_channels/world_crawler.py",
    "asia": "desks/mt5/research/asia_plane.py",
    "deep_forest": "desks/mt5/research/deep_forest_miner.py",
    "github": "desks/mt5/research/github_miner.py",
    "mql5_signals": "desks/mt5/research/mql5_signals.py",
    "mql5_survivors": "desks/mt5/research/mql5_survivors.py",
    "fxblue": "desks/mt5/research/fxblue_harvest.py",
    "understanding_seat": "desks/mt5/research/understanding_seat.py",
    "discovery_compiler": "desks/mt5/research/discovery_compiler.py",
    "representation_forge": "desks/mt5/research/representation_forge.py",
    "proposer_seat": "libs/research/proposer_seat.py",
}

#: Seats whose organ CANNOT donate without an external-model credential.
#:
#: WHY THEY GET THEIR OWN RULE. `data/secrets/**` never leaves the box, so a build box, a CI
#: runner and a fresh clone all hold a panel file with empty keys -- and on those hosts
#: `kimi_hunter` exits with a recorded BLOCKER rather than a donation, correctly. Judging that
#: as OVERDUE would make this fence red on every machine that is not the trading box, which is
#: how a fence stops being run. The seat layer's presence is MEASURED (`llm_seat.seats()`) and
#: an absent panel makes these seats UNMEASURED with the blocker named -- never a pass, and
#: never a defect charged to the organ.
SEAT_NEEDS_PANEL: frozenset[str] = frozenset({"kimi", "deepseek", "proposer_seat",
                                              "understanding_seat"})

#: THE DEBT THIS FENCE INHERITED, named on the day it was written, and it only ever shrinks.
#:
#: Measured 2026-09-23 on VMI3500897 the first time this ran: five seats carry an hourly cycle
#: leg and had not donated for 130-160 hours (`deep_forest` never at all). Failing the law gate
#: on them the moment the fence landed would have made every builder's commit red for a defect
#: none of them introduced, and a fence that blocks work it cannot explain is a fence that gets
#: forced within a day. So the debt is DECLARED, by name, with its size -- and the gate is real
#: for everything else: an overdue seat that is NOT on this list fails immediately, and so does
#: a sixth one. The list may be shortened when a seat starts donating; it may never be extended
#: to accommodate a new failure (L1.50's ratchet, pointed the only way a debt can ratchet).
BASELINE_OVERDUE: dict[str, str] = {
    "asia": "hourly_cycle:asia_plane runs; the seat directory last changed 2026-09-16",
    "deep_forest": "hourly_cycle:deep_forest_miner runs and the seat directory has never existed",
    "discovery_compiler": "hourly_cycle:discovery_compiler runs; directory last changed 2026-09-17",
    "representation_forge": "hourly_cycle:representation_forge runs; last changed 2026-09-17",
    "world": "hourly_cycle:world_crawler runs; the seat directory last changed 2026-09-16",
}


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def retired_seats() -> dict[str, str]:
    """Seats retired on purpose, with the reason, from the desk's own retirement ledger.

    A RETIREMENT IS AN ANSWER. Silence is not: a seat that stopped donating because the desk
    decided it was superseded must read RETIRED with the decision attached, not DEAD forever --
    otherwise every future session re-investigates a question that was already settled.
    """
    out: dict[str, str] = {}
    if not RETIREMENTS.exists():
        return out
    try:
        lines = RETIREMENTS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        seat = str(row.get("seat") or "")
        if seat:
            out[seat] = str(row.get("reason") or "")[:300]
    return out


# ----------------------------------------------------------------------------------- clocks
_CADENCE_RE: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], float]], ...] = (
    (re.compile(r"every\s+(\d+)\s*minute", re.I), lambda m: float(m.group(1)) / 60.0),
    (re.compile(r"every\s+(\d+)\s*hour", re.I), lambda m: float(m.group(1))),
    (re.compile(r"\bhourly\b", re.I), lambda m: 1.0),
    (re.compile(r"\bdaily\b", re.I), lambda m: 24.0),
)


def _oncalendar_hours(spec: str) -> float | None:
    """Hours between firings of a systemd OnCalendar line, for the shapes the desk actually uses.

    Deliberately narrow. A full OnCalendar parser is a project; the desk writes `*:MM`,
    `*-*-* *:MM:SS`, `*:0/15` and `*-*-* HH:MM:SS`, and anything else returns None so the seat
    reads UNMEASURED rather than being judged against a cadence nobody computed correctly.
    """
    s = spec.strip()
    m = re.search(r"\*:0?/(\d+)", s)
    if m:
        return max(1, int(m.group(1))) / 60.0
    m = re.search(r"\*-\*-\*\s+\*:(\d{1,2})(?::\d{1,2})?", s)
    if m:
        return 1.0
    m = re.fullmatch(r"\*:(\d{1,2})", s)
    if m:
        return 1.0
    if re.search(r"\*-\*-\*\s+\d{1,2}:\d{1,2}", s) or re.fullmatch(r"\d{1,2}:\d{1,2}", s):
        return 24.0
    if re.search(r"\bdaily\b", s, re.I):
        return 24.0
    if re.search(r"\bhourly\b", s, re.I):
        return 1.0
    return None


def clock_index() -> dict[str, dict[str, Any]]:
    """script path -> {clock, host, cadence_h}. Every clock this repository actually declares.

    Read from the three registries the desk already maintains -- the systemd units, the box task
    manifest and the two cycles -- rather than from a table here, because a table here is a copy
    that rots the first time a unit moves and reports a live seat as unscheduled.
    """
    idx: dict[str, dict[str, Any]] = {}

    here = _host()

    def add(script: str, clock: str, host: str, cadence: float | None) -> None:
        """Record a clock for this script, preferring the one THIS HOST actually runs.

        A script can carry several clocks -- `kimi_hunter.py` has a VPS timer AND, since
        2026-09-23, an hourly leg on the box -- and picking whichever was scanned first would
        report the seat as belonging to the other machine and skip judging it forever. The
        others are kept in `also` so the report shows the whole set rather than one winner.
        """
        script = script.strip().lstrip("./").replace("\\", "/")
        if not script:
            return
        row = {"clock": clock, "host": host, "cadence_h": cadence}
        prev = idx.get(script)
        if prev is None:
            idx[script] = {**row, "also": []}
            return
        also = prev.get("also")
        if isinstance(also, list):
            also.append(f"{clock} [{host}]")
        mine = host in (here, "either")
        theirs = str(prev.get("host")) in (here, "either")
        better = (mine and not theirs) or (prev.get("cadence_h") is None and cadence is not None
                                           and mine >= theirs)
        if better:
            idx[script] = {**row, "also": also if isinstance(also, list) else []}

    ops = ROOT / "ops"
    for unit in sorted(ops.glob("quant-*.service")) if ops.is_dir() else []:
        try:
            svc = unit.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        timer = unit.with_suffix(".timer")
        cadence: float | None = None
        if timer.exists():
            try:
                for line in timer.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.strip().startswith("OnCalendar="):
                        cadence = _oncalendar_hours(line.split("=", 1)[1])
                        break
            except OSError:
                cadence = None
        for hit in re.findall(r"([\w./-]+\.(?:py|sh))", svc):
            add(hit.split("quant-platform/")[-1], timer.name if timer.exists() else unit.name,
                "vps", cadence)

    manifest = ROOT / "ops" / "crontab.manifest"
    if manifest.exists():
        try:
            for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.search(r'exec="([^"]+)"', line)
                if not m:
                    continue
                on = re.search(r'on="([^"]+)"', line)
                unit_m = re.search(r'unit="([^"]+)"', line)
                add(m.group(1).split()[0], unit_m.group(1) if unit_m else "crontab.manifest",
                    "vps", _oncalendar_hours(on.group(1)) if on else None)
        except OSError:
            pass

    tasks = DESK / "ops" / "box_tasks.manifest"
    if tasks.exists():
        try:
            for line in tasks.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.search(r'TASK name="([^"]+)".*?trigger="([^"]*)".*?runs="([^"]*)"', line)
                if not m:
                    continue
                cadence = None
                for rx, fn in _CADENCE_RE:
                    hit = rx.search(m.group(2))
                    if hit:
                        cadence = fn(hit)
                        break
                add(m.group(3), m.group(1), "box", cadence)
        except OSError:
            pass

    for name, cadence in (("hourly_cycle.py", 1.0), ("daily_cycle.py", 24.0)):
        src = DESK / "research" / name
        if not src.exists():
            continue
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for leg, script in re.findall(r'_producer\(\s*"([^"]+)"\s*,\s*"([^"]+)"', text):
            script = script if script.startswith(("desks/", "libs/", "scripts/", "ops/")) \
                else f"desks/mt5/{script}"
            add(script, f"{name.split('.')[0]}:{leg}", "either", cadence)
    return idx


def _host() -> str:
    return "box" if os.name == "nt" else "vps"


def panel_is_lit() -> bool | None:
    """Does an external-model seat resolve on THIS host? None when the seat layer is unreadable.

    No network call and no key ever printed -- `llm_seat.seats()` reads the environment and the
    roster file and returns objects this function only counts.
    """
    try:
        from libs.ops import llm_seat
        return bool(llm_seat.seats())
    except Exception:
        return None


# ------------------------------------------------------------------------------- donations
def last_donation() -> dict[str, float]:
    """seat -> age in hours of its NEWEST donation file, across both intelligence roots.

    MEASURED OFF FILE MTIME, exactly as `check_producer_yield` does: a seat that stopped writing
    is the thing being looked for, and a stale row's own internal timestamp would report it as
    alive.
    """
    now = time.time()
    out: dict[str, float] = {}
    for root in INTEL_ROOTS:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            newest = 0.0
            try:
                for f in child.iterdir():
                    if f.is_file():
                        newest = max(newest, f.stat().st_mtime)
            except OSError:
                continue
            if newest <= 0:
                continue
            age = (now - newest) / 3600.0
            out[child.name] = min(out.get(child.name, age), age)
    return out


def audit(*, strict: bool = False, window_cadences: float = WINDOW_CADENCES) -> dict[str, Any]:
    clocks = clock_index()
    ages = last_donation()
    retired = retired_seats()
    here = _host()
    lit = panel_is_lit()
    rows: list[dict[str, Any]] = []

    for seat in sorted(set(SEAT_ORGANS) | set(ages) | set(retired)):
        organ = SEAT_ORGANS.get(seat, "")
        clock = clocks.get(organ) if organ else None
        age = ages.get(seat)
        rec: dict[str, Any] = {
            "seat": seat, "organ": organ or None,
            "clock": (clock or {}).get("clock"),
            "clock_host": (clock or {}).get("host"),
            "cadence_h": (clock or {}).get("cadence_h"),
            "last_donation_age_h": None if age is None else round(age, 2),
        }
        if seat in retired:
            rec.update({"verdict": "RETIRED", "why": retired[seat]})
            rows.append(rec)
            continue
        if organ and not (ROOT / organ).exists():
            rec.update({"verdict": UNMEASURED,
                        "why": (f"declared organ {organ} does not exist in this tree -- the "
                                "seat's directory holds output nothing here can reproduce")})
            rows.append(rec)
            continue
        if clock is None:
            rec.update({"verdict": UNMEASURED,
                        "why": ("no clock: no systemd unit, box task or cycle leg runs this "
                                "seat's organ. Not a slow seat -- an unscheduled one, and the "
                                "remedy is a clock, not a fix" if organ else
                                "no organ declared in SEAT_ORGANS, so no clock can be looked "
                                "up. The directory is real output from something the desk no "
                                "longer names")})
            rows.append(rec)
            continue
        if seat in SEAT_NEEDS_PANEL and lit is not True:
            rec.update({"verdict": UNMEASURED,
                        "needs_panel": True,
                        "why": ("this seat's organ needs an external-model credential and no "
                                "seat resolves on this host (data/secrets/** never leaves the "
                                "box, so a build box and CI hold a panel with empty keys). The "
                                "organ records a BLOCKER rather than donating, which is correct "
                                "-- and unjudgeable here")})
            rows.append(rec)
            continue
        cadence = clock.get("cadence_h")
        if cadence is None:
            rec.update({"verdict": UNMEASURED,
                        "why": (f"clock {clock['clock']} declares a trigger this checker cannot "
                                "reduce to hours; a cadence nobody computed is not a bar to "
                                "judge against")})
            rows.append(rec)
            continue
        window = max(MIN_WINDOW_H, float(cadence) * float(window_cadences))
        rec["window_h"] = round(window, 2)
        owner = str(clock.get("host"))
        if not strict and owner in ("box", "vps") and owner != here:
            rec.update({"verdict": "UNMEASURED_HERE",
                        "why": (f"clock {clock['clock']} runs on the {owner}; this checkout on "
                                f"the {here} holds a mirror of what that host wrote, so an old "
                                "file here is not a stale seat. Run with --strict to judge it "
                                "anyway")})
            rows.append(rec)
            continue
        if age is None:
            rec.update({"verdict": "OVERDUE",
                        "why": (f"scheduled by {clock['clock']} every {cadence:g}h and has "
                                "NEVER donated: no file under either data/intelligence root")})
        elif age > window:
            rec.update({"verdict": "OVERDUE",
                        "why": (f"scheduled by {clock['clock']} every {cadence:g}h, last "
                                f"donation {age:.1f}h ago -- past {window_cadences:g} cadences "
                                f"({window:.1f}h)")})
        else:
            rec.update({"verdict": "FRESH",
                        "why": f"last donation {age:.1f}h ago, inside {window:.1f}h"})
        rows.append(rec)

    census = Counter(str(r["verdict"]) for r in rows)
    overdue = [r for r in rows if r["verdict"] == "OVERDUE"]
    for r in overdue:
        r["declared_debt"] = BASELINE_OVERDUE.get(str(r["seat"]))
    new_debt = [r["seat"] for r in overdue if str(r["seat"]) not in BASELINE_OVERDUE]
    breach = bool(new_debt) or len(overdue) > len(BASELINE_OVERDUE)
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("EVERY CONFIGURED SEAT DONATES ON ITS OWN CADENCE, OR IT IS NAMED. A seat with "
                "no clock is UNMEASURED and counted, never a pass; a seat whose clock belongs "
                "to the other host is UNMEASURED_HERE and named; a retired seat carries its "
                "reason."),
        "host": here, "strict": bool(strict), "window_cadences": float(window_cadences),
        "min_window_h": MIN_WINDOW_H,
        "n_seats": len(rows), "census": dict(census),
        "overdue": [r["seat"] for r in overdue],
        "declared_debt": sorted(BASELINE_OVERDUE),
        "overdue_outside_the_declared_debt": new_debt,
        "breach": breach,
        "verdict": ("OVERDUE" if overdue else
                    ("RAN" if census.get("FRESH") else UNMEASURED)),
        "seats": sorted(rows, key=lambda r: (str(r["verdict"]), str(r["seat"]))),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--strict", action="store_true",
                    help="judge every seat, including ones clocked on the other host")
    ap.add_argument("--window-cadences", type=float, default=WINDOW_CADENCES)
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    args = ap.parse_args(argv)

    doc = audit(strict=bool(args.strict), window_cadences=float(args.window_cadences))
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    except OSError as exc:
        print(f"seat health: artifact NOT written ({type(exc).__name__}: {exc})")

    print(f"seat health [{doc['host']}]: {doc['n_seats']} seat(s) -> {doc['census']}")
    for v in ("OVERDUE", UNMEASURED, "UNMEASURED_HERE"):
        rs = [r for r in doc["seats"] if r["verdict"] == v]
        if not rs:
            continue
        print(f"\n  {v} {len(rs)}:")
        for r in rs[:14]:
            print(f"    {str(r['seat'])[:24]:24} {str(r.get('why'))[:88]}")
    if doc["overdue"]:
        print(f"\n  overdue {len(doc['overdue'])} against a declared debt of "
              f"{len(BASELINE_OVERDUE)}; outside it: "
              f"{doc['overdue_outside_the_declared_debt'] or 'none'}")
    print(f"  -> {OUT}")
    if args.report_only:
        return 0
    return 1 if doc["breach"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
