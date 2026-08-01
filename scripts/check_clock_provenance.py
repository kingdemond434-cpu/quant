#!/usr/bin/env python3
"""CLOCK PROVENANCE FENCE (L1.46) -- does the tape's time axis mean what its schema implies?

WHY THIS FENCE EXISTS. Every other data fence on this desk asks whether the COLLECTOR RAN. Gapless
collection was verified GOOD in the data-moat sweep on the same corpus that, measured here, is not
monotonic in its own `t` field. Nothing asked whether the TIMESTAMPS MEAN WHAT THE SCHEMA IMPLIES,
so a file could interleave two clocks under one field name and every liveness metric would read
green -- which is exactly what 7.5 GB of it does.

The cost is on the record three times over. kimchi_premium, the desk's flagship, was retracted as a
~73% timestamp artifact; coinbase_premium_timing was graveyarded as "close-timestamp
microstructure"; R0060 found leaky Upbit look-ahead copies surviving their own retraction. Three of
the most prominent kills in the graveyard are ONE defect class, and the institutional response was
a prose duty with no instrument ("DECLARE TIMESTAMP ALIGNMENT for every cross-source series ...
unstated alignment voids the screen"). This is the instrument.

WHAT IT MEASURES, and the second one is why the fence is not only about clocks: both are claims the
schema makes about the time axis that nobody was checking.
  WHICH CLOCK -- does each row declare the clock that stamped it, and do we retain the venue's own
      stamp wherever the venue offers one? Delta = t_recv - t_venue is structurally unbuyable (a
      vendor sells the venue's stamp or THEIR receipt, never when a message reached OURS) and it
      cannot be backfilled, so a day not recorded is a Delta day gone permanently.
  HOW OFTEN -- is the CONFIGURED poll period the one actually achieved? Measured 2026-08-01: the
      futures depth stream runs at 8.2s against _DEPTH_EVERY_S = 5.0, with p05 at 7.8s and nothing
      near 5.0 -- the loop cannot finish inside its own period, so the constant is a fiction that
      every consumer reading it instead of measuring inherits as truth.

FENCE STATUS (exit 2 on the first five -- a gate, not a report):
  NO-DATA       the corpus is absent or unreadable; there is no tape to check.
  UNMEASURED    files exist but no row could be classified -- never read as fine (L1.28a).
  MIXED-CLOCK   a stream carries rows on two different clocks with no marker declaring which.
                Worst status because a reader sorting the raw `t` silently REORDERS events, and
                that is the mechanism behind every timestamp artifact in the graveyard.
  RECV-ONLY     the venue publishes a stamp and we retain none, so Delta is unrecoverable for
                every row written this way. Streams where the venue genuinely offers nothing
                (Binance spot /api/v3/depth) are EXEMPT: a venue limitation must never read as a
                desk defect, or the fence cries wolf and gets switched off.
  PERIOD-DRIFT  the achieved sampling period exceeds its configured constant by >1.5x.
  OK            every live stream declares its clock, Delta is measurable wherever the venue
                offers a stamp, and the achieved cadence matches the configured one.

THE ONE THING THIS FENCE MAY NEVER DO is report OK because it found nothing to look at. An absent
corpus, an unparseable file and a stream nobody has classified are all LOUDER than a healthy desk.

    python scripts/check_clock_provenance.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: TTL-cached, pages but does not block -- a governance fault must never
# silence the only instrument that reports on the desk's largest dataset.
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research import clock_provenance as cp  # noqa: E402

#: Symbols sampled per venue, newest file each. The question is "is the tape being written
#: correctly RIGHT NOW", not "was it ever" -- every hour written wrong is an unrecoverable Delta
#: hour, so the fence must scream about today rather than average it into eight days of history.
_SAMPLE_SYMBOLS = 4
#: Rows read per sampled file. Read from the FRONT: gzip streams, so this stops early instead of
#: decompressing 7.5 GB on an hourly cron.
_SAMPLE_ROWS = 4000
#: Achieved period over configured before the constant counts as fiction rather than jitter.
#: Discriminating at 2026-08-01 values: futures 8.2/5.0 = 1.64x fires, Bybit 4.2/4.0 = 1.05x does
#: not. A gate that fires on everything or nothing carries zero information (GATE-OPTIMALITY).
_PERIOD_TOLERANCE = 1.5


def _sample_files(venue_dir: Path) -> list[Path]:
    """Newest file for each of the first _SAMPLE_SYMBOLS symbols that has one."""
    out: list[Path] = []
    for sym_dir in sorted(p for p in venue_dir.iterdir() if p.is_dir()):
        files = sorted(sym_dir.glob("*.jsonl.gz"))
        if files:
            out.append(files[-1])
        if len(out) >= _SAMPLE_SYMBOLS:
            break
    return out


def _read_rows(path: Path) -> list[dict[str, Any]]:
    """Rows from the front of a tape file. An unreadable file yields nothing and is COUNTED by the
    caller as unreadable -- never silently treated as an empty-but-healthy file."""
    rows: list[dict[str, Any]] = []
    try:
        with gzip.open(path, "rt") as fh:
            for line in fh:
                if len(rows) >= _SAMPLE_ROWS:
                    break
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except (OSError, EOFError, gzip.BadGzipFile):
        return []
    return rows


def _period_s(rows: list[dict[str, Any]], venue: str, kind: str) -> float | None:
    """Median achieved interval between consecutive rows of one kind, in seconds."""
    stamps = sorted(s for s in (cp.recv_ms(r, venue) or r.get("t")
                                for r in rows if r.get("k") == kind)
                    if isinstance(s, int))
    gaps = [(b - a) / 1000.0 for a, b in itertools.pairwise(stamps) if 0 < b - a < 600_000]
    return statistics.median(gaps) if len(gaps) >= 10 else None


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Pure: sample the tape, classify every stream, return the verdict. No writes -- tests call
    this directly, and a fence that could only be exercised through its side effects would be
    tested through its least interesting surface."""
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    moat = root / "data/moat"

    streams: dict[str, dict[str, Any]] = {}
    deltas: dict[str, list[int]] = {}
    # One achieved period per sampled file, collapsed to a median per stream below. Reporting a
    # row per file would put the same finding on screen four times and bury the streams that are
    # healthy -- a fence nobody reads to the end is a fence that catches nothing.
    period_samples: dict[str, tuple[float, list[float]]] = {}
    files_read = unreadable = rows_seen = 0

    venue_dirs = sorted(p for p in moat.iterdir() if p.is_dir()) if moat.is_dir() else []
    for venue_dir in venue_dirs:
        venue = venue_dir.name
        for path in _sample_files(venue_dir):
            rows = _read_rows(path)
            if not rows:
                unreadable += 1
                continue
            files_read += 1
            rows_seen += len(rows)
            kinds = {r.get("k") for r in rows if isinstance(r.get("k"), str)}
            for kind in sorted(k for k in kinds if k):
                sub = [r for r in rows if r.get("k") == kind]
                key = f"{venue}/{kind}"
                st = streams.setdefault(key, {
                    "venue": venue, "kind": kind, "rows": 0, "marked": 0,
                    "clocks": set(), "venue_stamped": 0, "delta_measurable": 0})
                st["rows"] += len(sub)
                st["marked"] += sum(1 for r in sub if isinstance(r.get(cp.MARKER), str))
                for r in sub:
                    st["clocks"].add(cp.clock_of(r, venue))
                    if cp.venue_ms(r, venue) is not None:
                        st["venue_stamped"] += 1
                    d = cp.delta_ms(r, venue)
                    if d is not None:
                        st["delta_measurable"] += 1
                        deltas.setdefault(venue, []).append(d)
                cfg = cp.CONFIGURED_PERIOD_S.get((venue, kind))
                measured = _period_s(sub, venue, kind) if cfg else None
                if cfg and measured:
                    period_samples.setdefault(key, (cfg, []))[1].append(measured)

    # ---- classify each stream -------------------------------------------------------------
    mixed: list[str] = []
    recv_only_defect: list[str] = []
    unknown_streams: list[str] = []
    for key, st in sorted(streams.items()):
        clocks = st.pop("clocks")
        st["clocks"] = sorted(clocks)
        real = {c for c in clocks if c != cp.CLOCK_UNKNOWN}
        st["fully_marked"] = st["marked"] == st["rows"]
        if cp.CLOCK_UNKNOWN in clocks:
            # Classify NOTHING about a stream whose clock we cannot name. Every finding below is
            # derived from knowing which clock stamped the row, so deriving one here would be
            # asserting a content verdict on an assumption -- the exact move this fence exists to
            # stop. It goes on unknown_streams and the ladder reports UNMEASURED.
            unknown_streams.append(key)
            continue
        # A file may legitimately multiplex clocks -- the defect is multiplexing them UNDECLARED.
        if len(real) > 1 and not st["fully_marked"]:
            mixed.append(key)
        exempt = (st["venue"], st["kind"]) in cp.RECV_ONLY_STREAMS
        st["venue_limit_exempt"] = exempt
        if not exempt and st["venue_stamped"] == 0 and cp.CLOCK_VENUE not in real:
            recv_only_defect.append(key)

    # Two streams written by the SAME recorder into the same file on different clocks are the
    # ambiguity even when each stream is internally consistent, so long as neither declares it.
    by_venue: dict[str, set[str]] = {}
    for st in streams.values():
        if not st["fully_marked"]:
            by_venue.setdefault(st["venue"], set()).update(
                c for c in st["clocks"] if c != cp.CLOCK_UNKNOWN)
    for venue, clocks in sorted(by_venue.items()):
        if len(clocks) > 1 and venue not in {k.split("/")[0] for k in mixed}:
            mixed.append(f"{venue}/* ({'+'.join(sorted(clocks))} undeclared in one file)")

    periods = [{"stream": key, "configured_s": cfg, "n_files": len(xs),
                "measured_s": round(statistics.median(xs), 2),
                "ratio": round(statistics.median(xs) / cfg, 2)}
               for key, (cfg, xs) in sorted(period_samples.items())]
    drift = [p for p in periods if p["ratio"] > _PERIOD_TOLERANCE]

    delta_stats = {}
    for venue, xs in sorted(deltas.items()):
        xs.sort()
        delta_stats[venue] = {
            "n": len(xs), "p50_ms": xs[len(xs) // 2],
            "p95_ms": xs[int(len(xs) * 0.95)], "max_ms": xs[-1],
            "negative_share": round(sum(1 for x in xs if x < 0) / len(xs), 4)}

    # ---- STATUS -- worst first, and every empty-input case ranks ABOVE OK (L1.28a) ---------
    if not venue_dirs or (files_read == 0 and unreadable == 0):
        status = "NO-DATA"
        detail = f"no tape under {moat} -- there is no corpus to check"
    elif files_read == 0:
        status = "NO-DATA"
        detail = f"all {unreadable} sampled files were unreadable -- the corpus cannot be parsed"
    elif not streams or rows_seen == 0:
        status = "UNMEASURED"
        detail = f"{files_read} files read but no row carried a usable kind -- nothing classified"
    elif unknown_streams:
        # An unclassified stream must never fall through to a CONTENT verdict. Before this branch
        # existed a brand-new venue reported RECV-ONLY -- a confident claim about a stream whose
        # clock we cannot name -- because `unknown_streams` was computed, reported, and never
        # consulted. Not knowing which clock stamped a row is an UNMEASURED time axis, and under
        # L1.28a that outranks any finding derived from assuming one.
        status = "UNMEASURED"
        detail = (f"{len(unknown_streams)} stream(s) nobody has classified: "
                  f"{', '.join(unknown_streams[:4])} -- teach them to "
                  f"clock_provenance._HISTORICAL before any verdict on them means anything")
    elif mixed:
        status = "MIXED-CLOCK"
        detail = (f"{len(mixed)} stream(s) mix clocks with no marker: {', '.join(mixed[:4])}"
                  f" -- a reader sorting raw `t` reorders events silently")
    elif recv_only_defect:
        status = "RECV-ONLY"
        detail = (f"{len(recv_only_defect)} stream(s) drop a venue stamp the venue DOES publish: "
                  f"{', '.join(recv_only_defect[:4])} -- Delta unrecoverable for every such row")
    elif drift:
        worst = max(drift, key=lambda p: p["ratio"])
        status = "PERIOD-DRIFT"
        detail = (f"{worst['stream']} samples every {worst['measured_s']}s against a configured "
                  f"{worst['configured_s']}s ({worst['ratio']}x) -- the constant is a fiction")
    else:
        status = "OK"
        detail = (f"{len(streams)} streams all declare their clock; Delta measurable on "
                  f"{sum(s['delta_measurable'] for s in streams.values())} sampled rows")

    return {
        "generated": now.isoformat(),
        "law": ("L1.46 -- a timestamp whose clock is undeclared is an assumption wearing a "
                "measurement's clothes; the tape declares which clock stamped it and retains the "
                "venue's own stamp beside ours, making alignment a measured number"),
        "status": status,
        "detail": detail,
        "files_read": files_read,
        "files_unreadable": unreadable,
        "rows_sampled": rows_seen,
        "streams": dict(sorted(streams.items())),
        "mixed_clock_streams": mixed,
        "recv_only_defects": recv_only_defect,
        "unknown_streams": unknown_streams,
        "period_checks": periods,
        "period_drift": drift,
        "delta_ms": delta_stats,
        "next_action": (
            "Start the recorders: there is no tape to measure"
            if status == "NO-DATA" else
            "Classify the sampled streams in libs/research/clock_provenance._HISTORICAL, reading "
            "the recorder source for which clock stamps each kind"
            if status == "UNMEASURED" else
            "Restart the recorders so new rows carry the `c` marker; historical rows stay "
            "readable through clock_provenance._HISTORICAL"
            if status == "MIXED-CLOCK" else
            "Retain the venue stamp in the named recorder(s) -- every hour without it is a "
            "Delta hour that cannot be backfilled"
            if status == "RECV-ONLY" else
            "Correct the configured period to the achieved one, or make the poll loop concurrent "
            "so it finishes inside its own period (R0275)"
            if status == "PERIOD-DRIFT" else
            "Delta is a first-class series now: join it to the free first-party Bybit archive on "
            "the venue stamp to measure our own information disadvantage per symbol"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/clock_provenance_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"clock provenance (L1.46): {rep['status']} -- {rep['detail']}")
        print(f"  files {rep['files_read']} read / {rep['files_unreadable']} unreadable | "
              f"rows {rep['rows_sampled']} | streams {len(rep['streams'])}")
        for key, st in rep["streams"].items():
            flag = "" if st["fully_marked"] else "  <- UNDECLARED"
            print(f"    {key:16s} rows={st['rows']:6d} marked={st['marked']:6d} "
                  f"clocks={'+'.join(st['clocks'])}{flag}")
        for p in rep["period_checks"]:
            print(f"    period {p['stream']:16s} {p['measured_s']}s vs {p['configured_s']}s "
                  f"configured ({p['ratio']}x)")
        for venue, d in rep["delta_ms"].items():
            print(f"    delta {venue:11s} n={d['n']} p50={d['p50_ms']}ms p95={d['p95_ms']}ms "
                  f"neg={d['negative_share']:.1%}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    return 0 if rep["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
