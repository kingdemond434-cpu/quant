"""THE BAR CLOCK, MEASURED ON THE BOX THAT HOLDS THE BARS: broker server time against UTC.

    python desks/mt5/research/bar_clock_probe.py               # capture (if a terminal), publish
    python desks/mt5/research/bar_clock_probe.py --no-capture  # publish from the ledger only

WHY IT EXISTS (2026-10-21, judge dead-families v4 follow-up). `family_event_reaction` places every
UTC-stamped calendar event on the broker-stamped bar index through `libs/research/bar_clock`, and
with no `desks/mt5/reports/BAR_CLOCK.json` it drops every event, correctly. On the tree the judge
ran on, the file was absent, the release-spike reading refused summer (one non-USD voter, and that
one sat on the adjacency rule), and the family read NEEDS_DATA(bar_clock): 199 events, 0 fire
days. The answer is not to loosen the rule. It is to MEASURE the clock where the clock lives.

WHAT IT MEASURES. Each hourly pass, where an MT5 terminal is attached, it reads for a few liquid
symbols the newest tick's `time_msc` (the server's own stamp, broker wall time encoded as epoch
milliseconds, the same clock the H1 index carries) and the current H1 bar's open time, and pairs
them with the box's UTC clock at the moment of the call. A fresh tick puts `server - utc` within
seconds of a whole number of hours, and that number is the offset; the current bar must then open
at `floor_hour(utc + offset)`, so the BAR INDEX itself confirms it. Every reading is appended to
`desks/mt5/data/bar_clock_probes.jsonl` (state the box keeps and carries), and the tick recorder's
own `clock_probe` rows (`<tape root>/clock/*.jsonl`) are read too when a tape exists.

WHAT IT PUBLISHES -- dated SPANS, never a rule. A span is a maximal run of capture instants that
agree on one offset with no gap longer than MAX_PROBE_GAP_H. `bar_clock.to_bar_time` converts an
instant inside a span, including a shoulder-month instant, because there the offset was READ, not
inferred. Between two spans with different offsets lies a measured changeover; an instant inside
it is UNMEASURED. DST is handled by measuring it: the broker is +3 in summer and +2 in winter, and
which day it switches -- the EU's last Sunday of October or the US's first Sunday of November,
whose gap in 2026 is 10-26..10-30 -- is read off the spans and reported as `dst_watch`, never
assumed.

SECOND OPINIONS, and what they can do. The release-spike reading (`bar_clock_release`: the bar at
release+k hours carries the day's range spike only at the true offset) is compared with every span
it overlaps; a resolved disagreement, or MIN_VOTES instrument votes none of which agree, marks the
span CONFLICT and it converts nothing. The cross-venue reading of `research/futures_lead_lag.py`
(COMEX against the CFD, epoch-second stamps) is the one multi-year source, so it alone may publish
a season-wide `per_season` offset -- and only when no measured span or release reading in that
season disagrees.

WHAT IT NEVER DOES. It never writes an offset it did not read: no evidence means `status:
UNMEASURED`, with every season offset None and the reason named. It never uses
`broker_clock_measured.json`'s scalar (one number for both seasons; recorded beside the verdict
as `stored_scalar` only). It never moves a bar, never sends an order, never touches sizing.
Zero promotion authority: it reads a terminal and publishes one report and one ledger.
"""
from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA = 2
MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
CONFLICT = "CONFLICT"

CLOCK_REL = "desks/mt5/reports/BAR_CLOCK.json"
LEDGER_REL = "desks/mt5/data/bar_clock_probes.jsonl"
FUTURES_REL = "desks/mt5/reports/FUTURES_LEAD_LAG.json"
STORED_REL = "desks/mt5/data/broker_clock_measured.json"

#: Liquid around the clock five days a week, so a tick is seconds old whenever the market is open.
PROBE_SYMBOLS: tuple[str, ...] = ("EURUSD", "USDJPY", "GBPUSD", "XAUUSD", "AUDUSD")

HOUR_MS = 3_600_000
#: A tick is FRESH when `server - utc` lies this close to a whole hour. A stale tick (weekend,
#: session break, dead feed) lands between hours and is rejected, never rounded.
FRESH_TOL_MS = 120_000
#: Offsets a broker could plausibly run; anything outside is a broken reading, not a timezone.
OFFSET_MIN, OFFSET_MAX = -12, 14
#: Capture instants a span needs before it converts anything.
MIN_SPAN_PROBES = 3
#: Longest silence a span may bridge. A weekend is ~49h of closed market; a DST changeover falls
#: inside one, and is caught because the offsets on its two sides differ.
MAX_PROBE_GAP_H = 72
#: Instrument votes from the release-spike reading that, all disagreeing, refuse a span.
MIN_VOTES = 3

SEASONS: tuple[tuple[str, int, int], ...] = (("summer", 501, 915), ("winter", 1201, 215))


# ----------------------------------------------------------------------------- capture --
def _now_ms() -> int:
    return int(time.time() * 1000)


def capture(symbols: tuple[str, ...] = PROBE_SYMBOLS) -> tuple[list[dict[str, Any]], str]:
    """One reading per symbol from the desk's terminal, or ([], why). Read-only.

    Attaches the way shadow_cycle and h1_source do, through `mt5_session.attach_or_initialize`,
    which refuses from Windows Session 0 and whenever a terminal in another session would be
    competed with; a host it refuses simply contributes no reading this hour. (Its
    `allow_autostart=False` form cannot attach from a fresh process at all, because
    `terminal_info()` is None until `initialize` is called.)
    """
    try:
        import MetaTrader5 as mt5  # the vendor's own casing
    except ImportError:
        return [], "NO_TERMINAL: MetaTrader5 is not importable on this host"
    try:
        from research.mt5_session import attach_or_initialize
        path: str | None = None
        with contextlib.suppress(Exception):
            from mt5desk.config import terminal_path
            path = terminal_path()
        if not attach_or_initialize(mt5, path=path, timeout=15_000):
            return [], ("NO_TERMINAL: attach refused or failed (Session 0, a competing "
                        "terminal, or none running)")
    except Exception as exc:
        return [], f"NO_TERMINAL: {type(exc).__name__}: {str(exc)[:120]}"
    rows: list[dict[str, Any]] = []
    for sym in symbols:
        try:
            before = _now_ms()
            tick = mt5.symbol_info_tick(sym)
            after = _now_ms()
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 1)
        except Exception:
            continue
        server_ms = int(getattr(tick, "time_msc", 0) or 0) if tick is not None else 0
        if server_ms <= 0:
            continue
        bar_ms: int | None = None
        with contextlib.suppress(Exception):
            if rates is not None and len(rates):
                bar_ms = int(rates[0]["time"]) * 1000
        local_ms = (before + after) // 2
        rows.append({"at": datetime.fromtimestamp(local_ms / 1000, tz=UTC)
                     .isoformat(timespec="seconds"),
                     "source": "terminal", "symbol": sym, "local_ms": local_ms,
                     "server_ms": server_ms, "bar_open_ms": bar_ms,
                     "call_ms": after - before})
    return rows, (f"{len(rows)} of {len(symbols)} symbols read" if rows
                  else "terminal attached but no symbol returned a tick")


def append_ledger(root: Path, rows: list[dict[str, Any]]) -> str | None:
    """Append, or say why not. The ledger is evidence; a failed write is reported, never hidden."""
    if not rows:
        return None
    path = root / Path(*LEDGER_REL.split("/"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


# ----------------------------------------------------------------------------- reading --
def _jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows, bad = [], 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
            else:
                bad += 1
    return rows, bad


def tape_clock_dir() -> Path:
    """The tick recorder's clock rows, at the root the recorder itself would use."""
    env = os.environ.get("MT5_TAPE_ROOT", "")
    if env:
        return Path(env) / "clock"
    with contextlib.suppress(Exception):
        from recorders.tick_recorder import DEFAULT_TAPE_ROOT
        return Path(DEFAULT_TAPE_ROOT) / "clock"
    return BASE / "data" / "tape_bronze" / "clock"


def load_probes(root: Path, tape_clock: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every probe row on disk, tagged with its source, plus an account of what was read."""
    rows: list[dict[str, Any]] = []
    acct: dict[str, Any] = {"ledger": LEDGER_REL, "ledger_rows": 0, "tape_rows": 0,
                            "unparseable_lines": 0, "unreadable": []}
    ledger = root / Path(*LEDGER_REL.split("/"))
    if ledger.exists():
        try:
            got, bad = _jsonl(ledger)
            rows.extend({**r, "source": r.get("source") or "terminal"} for r in got)
            acct["ledger_rows"], acct["unparseable_lines"] = len(got), bad
        except OSError as exc:
            acct["unreadable"].append(f"{LEDGER_REL}: {type(exc).__name__}")
    if tape_clock is not None and tape_clock.is_dir():
        acct["tape_clock_dir"] = str(tape_clock)
        for path in sorted(tape_clock.glob("*.jsonl")):
            try:
                got, bad = _jsonl(path)
            except OSError as exc:
                acct["unreadable"].append(f"{path.name}: {type(exc).__name__}")
                continue
            rows.extend({**r, "source": "tape_clock_probe", "bar_open_ms": None} for r in got)
            acct["tape_rows"] += len(got)
            acct["unparseable_lines"] += bad
    return rows, acct


def read_probe(row: dict[str, Any]) -> tuple[int | None, str]:
    """(offset_h, verdict) for one probe row. The offset is READ or it is None -- never rounded
    out of a stale tick."""
    try:
        local_ms, server_ms = int(row["local_ms"]), int(row["server_ms"])
    except (KeyError, TypeError, ValueError):
        return None, "MALFORMED"
    skew = server_ms - local_ms
    k = round(skew / HOUR_MS)
    if abs(skew - k * HOUR_MS) > FRESH_TOL_MS:
        return None, "STALE"
    if not OFFSET_MIN <= k <= OFFSET_MAX:
        return None, "IMPLAUSIBLE"
    bar = row.get("bar_open_ms")
    if bar is not None:
        try:
            lead = local_ms + k * HOUR_MS - int(bar)
        except (TypeError, ValueError):
            return None, "MALFORMED"
        # The current H1 bar must have opened within the last hour of SERVER time. A bar index on
        # a different clock from the ticks would fail here, and so would a mis-read offset.
        if not 0 <= lead < HOUR_MS + FRESH_TOL_MS:
            return None, "BAR_DISAGREES"
    return int(k), ("FRESH_TICK_AND_BAR" if bar is not None else "FRESH_TICK")


def instants(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Group readings into capture instants (source, minute); an instant needs every fresh
    symbol to agree, or it is rejected as SYMBOLS_DISAGREE."""
    verdicts: dict[str, int] = {}
    groups: dict[tuple[str, int], list[tuple[int, int, str]]] = {}
    for r in rows:
        off, verdict = read_probe(r)
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        if off is None:
            continue
        lm = int(r["local_ms"])
        groups.setdefault((str(r.get("source")), lm // 60_000), []).append(
            (lm, off, str(r.get("symbol") or "")))
    out: list[dict[str, Any]] = []
    for (source, _minute), got in sorted(groups.items(), key=lambda kv: kv[0][1]):
        offs = {o for _, o, _ in got}
        if len(offs) != 1:
            verdicts["SYMBOLS_DISAGREE"] = verdicts.get("SYMBOLS_DISAGREE", 0) + 1
            continue
        out.append({"ms": min(lm for lm, _, _ in got), "offset_h": offs.pop(),
                    "source": source, "symbols": sorted({s for _, _, s in got})})
    out.sort(key=lambda x: x["ms"])
    return out, verdicts


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat(timespec="seconds")


def spans(points: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(kept spans, short runs). A run breaks on a new offset or a gap over MAX_PROBE_GAP_H."""
    runs: list[list[dict[str, Any]]] = []
    for p in points:
        if runs and runs[-1][-1]["offset_h"] == p["offset_h"] \
                and p["ms"] - runs[-1][-1]["ms"] <= MAX_PROBE_GAP_H * HOUR_MS:
            runs[-1].append(p)
        else:
            runs.append([p])
    kept: list[dict[str, Any]] = []
    short: list[dict[str, Any]] = []
    for run in runs:
        block = {"first": _iso(run[0]["ms"]), "last": _iso(run[-1]["ms"]),
                 "offset_h": run[0]["offset_h"], "n": len(run),
                 "sources": sorted({p["source"] for p in run}),
                 "symbols": sorted({s for p in run for s in p["symbols"]})}
        (kept if len(run) >= MIN_SPAN_PROBES else short).append(block)
    return kept, short


def _last_sunday(year: int, month: int) -> datetime:
    d = datetime(year, month + 1, 1, tzinfo=UTC) - timedelta(days=1) if month < 12 \
        else datetime(year, 12, 31, tzinfo=UTC)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _nth_sunday(year: int, month: int, n: int) -> datetime:
    d = datetime(year, month, 1, tzinfo=UTC)
    return d + timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))


def changeovers(year: int) -> dict[str, datetime]:
    """The two rule books' changeover instants, in UTC. DIAGNOSTIC ONLY: they name which rule a
    MEASURED transition matches; nothing is ever converted from them."""
    return {
        "eu_spring": _last_sunday(year, 3) + timedelta(hours=1),
        "eu_autumn": _last_sunday(year, 10) + timedelta(hours=1),
        "us_spring": _nth_sunday(year, 3, 2) + timedelta(hours=7),
        "us_autumn": _nth_sunday(year, 11, 1) + timedelta(hours=6),
    }


def transitions(kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for a, b in itertools.pairwise(kept):
        if a["offset_h"] == b["offset_h"]:
            continue
        lo, hi = datetime.fromisoformat(a["last"]), datetime.fromisoformat(b["first"])
        rules = [name for year in {lo.year, hi.year}
                 for name, at in changeovers(year).items() if lo < at <= hi]
        out.append({"after": a["last"], "before": b["first"], "from_h": a["offset_h"],
                    "to_h": b["offset_h"], "rule_match": sorted(set(rules)) or ["neither"]})
    return out


def dst_watch(kept: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """The autumn days on which the EU and US rules disagree (2026: 10-26..10-30), and what was
    READ there. Which rule the broker follows is a measurement or it is UNMEASURED."""
    co = changeovers(now.year)
    lo, hi = co["eu_autumn"], co["us_autumn"]
    seen = sorted({s["offset_h"] for s in kept
                   if datetime.fromisoformat(s["first"]) < hi
                   and datetime.fromisoformat(s["last"]) > lo})
    rule = (UNMEASURED if not seen else
            "us" if seen == [3] else "eu" if seen == [2] else CONFLICT)
    return {"between": [lo.isoformat(), hi.isoformat()], "offsets_read": seen,
            "broker_follows": rule,
            "why": ("between the EU and US autumn changeovers a broker on the EU rule reads +2 "
                    "and one on the US (New York close) rule still reads +3; this is answered "
                    "only by spans that cover those days")}


# ----------------------------------------------------------------------- second opinions --
def _season_of(when: datetime) -> str | None:
    mmdd = when.month * 100 + when.day
    for name, lo, hi in SEASONS:
        if (lo <= mmdd <= hi) if lo <= hi else (mmdd >= lo or mmdd <= hi):
            return name
    return None


def release_opinion(root: Path) -> dict[str, Any]:
    try:
        from libs.research import bar_clock_release
        return bar_clock_release.reading(root)
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:160]}"}


def judge_span(span: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]:
    """Compare one span with the release-spike reading; CONFLICT refuses it."""
    lo, hi = datetime.fromisoformat(span["first"]), datetime.fromisoformat(span["last"])
    votes: dict[str, int] = {}
    resolved: list[tuple[str, int]] = []
    for season, block in (release.get("per_season") or {}).items():
        if not isinstance(block, dict):
            continue
        win = block.get("window") or {}
        off = block.get("offset_h")
        if isinstance(off, int) and win.get("first") and win.get("last"):
            with contextlib.suppress(TypeError, ValueError):
                if datetime.fromisoformat(str(win["first"])) <= hi \
                        and datetime.fromisoformat(str(win["last"])) >= lo:
                    resolved.append((season, off))
        for sym, reading in (block.get("readings") or {}).items():
            if not isinstance(reading, dict) or not isinstance(reading.get("offset_h"), int):
                continue
            stamps = []
            for raw in reading.get("releases") or []:
                with contextlib.suppress(TypeError, ValueError):
                    stamps.append(datetime.fromisoformat(str(raw)))
            if any(lo <= t <= hi for t in stamps):
                votes[sym] = int(reading["offset_h"])
    off = span["offset_h"]
    against = [s for s, o in resolved if o != off]
    agree_votes = sum(1 for o in votes.values() if o == off)
    if against:
        verdict, why = CONFLICT, (f"the release-spike reading resolved {against} to a different "
                                  f"offset than the {off:+d}h read off the terminal")
    elif len(votes) >= MIN_VOTES and agree_votes == 0:
        verdict, why = CONFLICT, (f"{len(votes)} release-spike instrument votes inside the span, "
                                  f"none at {off:+d}h")
    elif resolved or agree_votes:
        verdict, why = "AGREES", (f"release-spike: {agree_votes} of {len(votes)} instrument "
                                  f"votes at {off:+d}h, resolved seasons {resolved}")
    else:
        verdict, why = "UNCORROBORATED", ("no release-spike reading overlaps the span; the "
                                          "terminal reading stands on its own evidence")
    return {"verdict": verdict, "votes": votes, "resolved": resolved, "why": why}


def futures_opinion(root: Path) -> dict[str, Any]:
    try:
        doc = json.loads((root / Path(*FUTURES_REL.split("/"))).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": UNMEASURED, "why": f"{FUTURES_REL} is absent or unreadable"}
    clock = doc.get("clock") if isinstance(doc, dict) else None
    if not isinstance(clock, dict):
        return {"status": UNMEASURED, "why": f"{FUTURES_REL} carries no clock block"}
    return {"status": MEASURED, "at": doc.get("at"), "per_season": clock.get("per_season") or {}}


def per_season(kept: list[dict[str, Any]], release: dict[str, Any],
               futures: dict[str, Any]) -> dict[str, Any]:
    """A season-wide offset is published ONLY from the multi-year cross-venue reading, and only
    when no measured span or release reading inside that season disagrees."""
    out: dict[str, Any] = {}
    for name, _, _ in SEASONS:
        fut = (futures.get("per_season") or {}).get(name) or {}
        fo = fut.get("offset_h") if fut.get("agrees_across_pairs") else None
        span_offs = sorted({s["offset_h"] for s in kept if s.get("status") == MEASURED
                            and name in (_season_of(datetime.fromisoformat(s["first"])),
                                         _season_of(datetime.fromisoformat(s["last"])))})
        ro = ((release.get("per_season") or {}).get(name) or {}).get("offset_h")
        disagree = [x for x in [*span_offs, ro] if isinstance(x, int) and x != fo]
        if not isinstance(fo, int):
            off, why = None, ("no multi-year cross-venue reading for this season; dated spans "
                              "convert only the days they cover")
        elif disagree:
            off, why = None, (f"{CONFLICT}: cross-venue {fo:+d}h against measured {disagree}")
        else:
            off, why = fo, "cross-venue multi-year reading, not contradicted by any span"
        out[name] = {"offset_h": off, "agrees_across_pairs": off is not None,
                     "cross_venue_h": fo, "span_offsets_h": span_offs, "release_spike_h": ro,
                     "why": why}
    return out


# ----------------------------------------------------------------------------- publish --
def build(root: Path, *, tape_clock: Path | None = None, now: datetime | None = None,
          capture_note: str = "capture not attempted") -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows, acct = load_probes(root, tape_clock)
    points, verdicts = instants(rows)
    kept, short = spans(points)
    release = release_opinion(root)
    for s in kept:
        s["second_opinion"] = judge_span(s, release)
        s["status"] = CONFLICT if s["second_opinion"]["verdict"] == CONFLICT else MEASURED
    usable = [s for s in kept if s["status"] == MEASURED]
    futures = futures_opinion(root)
    seasons = per_season(kept, release, futures)
    stored = None
    with contextlib.suppress(OSError, ValueError, AttributeError):
        stored = json.loads((root / Path(*STORED_REL.split("/"))).read_text("utf-8")) \
            .get("utc_offset_hours")
    measured = bool(usable) or any(v["offset_h"] is not None for v in seasons.values())
    summer, winter = seasons["summer"]["offset_h"], seasons["winter"]["offset_h"]
    span_offs = {s["offset_h"] for s in usable}
    return {
        "schema": SCHEMA,
        "status": MEASURED if measured else UNMEASURED,
        "measured_at": now.isoformat(timespec="seconds"),
        "at": now.isoformat(timespec="seconds"),
        "measured_by": ("broker server time (newest tick time_msc, confirmed by the current H1 "
                        "bar's open) against the box's UTC clock at the moment of the call; "
                        "release-spike and cross-venue readings as second opinions"),
        "evidence": {**acct, "n_probe_rows": len(rows), "n_instants": len(points),
                     "verdicts": verdicts, "n_spans": len(kept), "n_spans_usable": len(usable),
                     "first": usable[0]["first"] if usable else None,
                     "last": usable[-1]["last"] if usable else None,
                     "capture": capture_note},
        "spans": kept,
        "short_runs": short,
        "transitions": transitions(usable),
        "dst_watch": dst_watch(usable, now),
        "per_season": seasons,
        "varies_with_dst": (len(span_offs) > 1 or (summer is not None and winter is not None
                                                   and summer != winter)),
        "stored_scalar": stored,
        "second_opinions": {"release_spike": {k: release.get(k) for k in
                                              ("status", "n_releases", "why") if k in release},
                            "cross_venue": {k: futures.get(k) for k in ("status", "at", "why")
                                            if k in futures}},
        "rules": {"fresh_tol_ms": FRESH_TOL_MS, "min_span_probes": MIN_SPAN_PROBES,
                  "max_probe_gap_h": MAX_PROBE_GAP_H, "min_votes": MIN_VOTES},
        "why": ("no offset is ever written that was not read: with no fresh probe and no "
                "cross-venue reading every season is None and status is UNMEASURED"
                if not measured else
                "a span converts only the days it covers; a season-wide offset needs the "
                "multi-year cross-venue reading and no measured disagreement"),
    }


def write(root: Path, doc: dict[str, Any]) -> Path:
    out = root / Path(*CLOCK_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    payload = json.dumps(doc, indent=1, default=str)
    tmp.write_text(payload, encoding="utf-8")
    try:
        os.replace(tmp, out)
    except PermissionError:          # Windows: a reader holding the file; write in place
        out.write_text(payload, encoding="utf-8")
        with contextlib.suppress(OSError):
            tmp.unlink()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="measure the broker bar clock against UTC")
    ap.add_argument("--no-capture", action="store_true", help="publish from the ledger only")
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    note = "capture skipped (--no-capture)"
    if not args.no_capture:
        got, note = capture()
        failed = append_ledger(args.root, got)
        if failed:
            note += f"; LEDGER WRITE FAILED: {failed}"
    doc = build(args.root, tape_clock=tape_clock_dir(), capture_note=note)
    write(args.root, doc)
    ev = doc["evidence"]
    print(f"BAR CLOCK {doc['status']}  spans {ev['n_spans_usable']}/{ev['n_spans']}  "
          f"instants {ev['n_instants']} of {ev['n_probe_rows']} rows  {ev['first']}..{ev['last']}"
          f"  summer {doc['per_season']['summer']['offset_h']} winter "
          f"{doc['per_season']['winter']['offset_h']}  dst {doc['dst_watch']['broker_follows']}")
    print(f"  capture: {note}")
    print(f"written: {CLOCK_REL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
