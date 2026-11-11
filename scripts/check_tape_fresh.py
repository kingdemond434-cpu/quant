"""Is the tick tape still moving? Judged PER SYMBOL, against each symbol's own session.

WHY (2026-10-14). MT5-TickRecorder returned 1 at 2026-10-12 19:56 box time and was never run
again: its only triggers were boot and logon, and the scheduler's restart-on-failure does not
fire on a non-zero exit. process_health named it FAILING for two days and nothing acted. Origin's
`tape_state.json` reads 2026-09-04, but that file was never on the box's publish allowlist, so its
date says nothing about the box. This fence reads each tape's OWN tick stamps on the box that
writes them, and publishes the verdict.

PER SYMBOL, PER SESSION (audit 2026-10-20). The first version took the newest tick over every
symbol and an FX calendar: one live symbol hid 244 dead ones, and it read GREEN all weekend while
the crypto CFDs trade. Now every registry symbol is judged on its own newest tick, and only while
ITS session is open. Each tape is judged on the symbols it enrolled (registry symbols it never
carried are counted beside the verdict as `not_enrolled`). A symbol's session is the set of (weekday, hour) slots on the venue clock in
which its own H1 bars appeared in at least half of the last eight weeks
(`data/universe/<SYM>_H1.parquet`, cached daily in reports/TAPE_SESSIONS.json). With no bars the
registry's class decides: Crypto trades every slot, everything else the FX week (venue Monday
00:00 to Saturday 00:00, which is New York Sunday 17:00 to Friday 17:00 in either DST phase). No
symbol list appears in this file.

THE TWO TAPES:

    bronze  reports/TAPE_RECORDER.json  `symbols_last_tick_ms`  recorders/tick_recorder.py
    silver  data/tape/tape_state.json   per-symbol `last_tick_ms`  hourly `tape` leg

Stamps are the venue clock (New York + 7 h); `now` is moved onto that clock with
`libs.regime.session_clock.utc_offset_h`, so ages compare like with like.

VERDICTS, per symbol and then per tape (the tape takes its worst open symbol):
    FRESH          newest tick within 2 h of now, or of its session's open if that is later
    STALE          over 2 h inside its own session -- RED
    CLOSED         its session is shut now
    UNMEASURED     no stamp, or stamped in the future -- RED; an absent tape is UNMEASURED too

WHY A RED TAPE IS RED. The report names the most likely CAUSE beside it, read from the box's own
evidence: the terminal link first (`data/terminal_boot_ok.json`, which MT5-TerminalBoot writes
only when its read-only IPC probe passes -- from 2026-10-18 the box returned "No IPC connection"),
then the bronze recorder's own pause reason and source errors, then "the recorder is not running".
The cause never changes the verdict.

    python scripts/check_tape_fresh.py      # writes the report; exit 1 when RED
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "TAPE_FRESHNESS.json"

MAX_AGE_H = 2.0
#: MT5-TerminalBoot's probe stamp and how old it may be (its organ contract: 180 min).
TERMINAL_OK = "data/terminal_boot_ok.json"
TERMINAL_MAX_AGE_H = 3.0
#: A stamp more than this far past now is a clock defect, never a fresh tape.
FUTURE_SLACK = timedelta(minutes=5)
#: How many weeks of a symbol's own H1 bars define its session, and where that map is cached.
SESSION_WEEKS = 8
SESSION_CACHE = "reports/TAPE_SESSIONS.json"

#: (name, artifact under desks/mt5, producer)
TAPES: tuple[tuple[str, str, str], ...] = (
    ("bronze", "reports/TAPE_RECORDER.json", "MT5-TickRecorder: recorders/tick_recorder.py"),
    ("silver", "data/tape/tape_state.json", "hourly_cycle `tape` leg: mt5desk/tape.py"),
)


def venue_lead(now: datetime) -> timedelta:
    """How far the venue clock runs ahead of UTC at `now` (3 h in US summer, else 2)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from libs.regime.session_clock import utc_offset_h
    return timedelta(hours=int(utc_offset_h(now)))


def venue_dt(ms: int) -> datetime:
    """A venue `time_msc` as a naive venue-clock datetime."""
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=UTC).replace(tzinfo=None)


def _slot(t: datetime) -> int:
    return t.weekday() * 24 + t.hour


def class_slots(asset_class: str | None) -> set[int]:
    """The registry-class fallback: Crypto every slot, else the FX week (venue Mon-Fri)."""
    if "crypto" in str(asset_class or "").lower():
        return set(range(168))
    return set(range(5 * 24))


def bar_slots(path: Path, weeks: int = SESSION_WEEKS) -> set[int] | None:
    """Slots (weekday*24 + hour, venue clock) in which this symbol's own H1 bars appeared in at
    least half of its last `weeks` weeks. None when there are no readable bars."""
    try:
        import pandas as pd
        idx = pd.DatetimeIndex(pd.read_parquet(path, columns=[]).index)
    except Exception:
        return None
    if idx.empty:
        return None
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    idx = idx[idx > idx.max() - pd.Timedelta(weeks=weeks)]
    slots = idx.weekday * 24 + idx.hour
    weeks_seen = max(1, len(set(idx.isocalendar().week.tolist())))
    counts = pd.Series(1, index=slots).groupby(level=0).size()
    return {int(k) for k, v in counts.items() if v >= weeks_seen / 2}


def sessions(desk: Path, now: datetime) -> dict[str, set[int]]:
    """symbol -> open slots, for every registry symbol. Cached a day in reports/."""
    cache = desk / SESSION_CACHE
    doc = _read(cache)
    if isinstance(doc, dict):
        try:
            age = now - datetime.fromisoformat(str(doc.get("at")))
            if timedelta(0) <= age < timedelta(hours=24):
                return {k: set(v) for k, v in (doc.get("symbols") or {}).items()}
        except (TypeError, ValueError):
            pass
    reg = _read(desk / "data" / "universe" / "universe.json")
    out: dict[str, set[int]] = {}
    for sym, meta in (reg.items() if isinstance(reg, dict) else []):
        bars = bar_slots(desk / "data" / "universe" / f"{sym}_H1.parquet")
        out[sym] = bars if bars else class_slots(
            meta.get("asset_class") if isinstance(meta, dict) else None)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"at": now.isoformat(), "symbols": {
            k: sorted(v) for k, v in sorted(out.items())}}), encoding="utf-8")
    except OSError:
        pass
    return out


def session_open(slots: set[int], v_now: datetime) -> datetime | None:
    """The venue time the current open run of slots began, or None when shut now."""
    if _slot(v_now) not in slots:
        return None
    t = v_now.replace(minute=0, second=0, microsecond=0)
    for _ in range(168):
        prev = t - timedelta(hours=1)
        if _slot(prev) not in slots:
            return t
        t = prev
    return t - timedelta(days=7)                    # open all week: no session edge


def judge_symbol(ms: Any, slots: set[int], v_now: datetime) -> dict[str, Any]:
    opened = session_open(slots, v_now)
    try:
        iv = int(ms)
    except (TypeError, ValueError):
        iv = 0
    if iv <= 0:
        if opened is None:
            return {"status": "CLOSED"}
        return {"status": "UNMEASURED", "why": "no tick stamp for this symbol"}
    last = venue_dt(iv)
    row: dict[str, Any] = {"last_tick_ms": iv,
                           "age_h": round((v_now - last).total_seconds() / 3600, 2)}
    if last > v_now + FUTURE_SLACK:
        return {**row, "status": "UNMEASURED", "why": "stamped in the future -- a clock defect"}
    if opened is None:
        return {**row, "status": "CLOSED"}
    open_age = round((v_now - max(last, opened)).total_seconds() / 3600, 2)
    row["open_age_h"] = open_age
    if open_age > MAX_AGE_H:
        return {**row, "status": "STALE",
                "why": f"no tick for {open_age:g} h of its own open session"}
    return {**row, "status": "FRESH"}


def stamps(doc: Any) -> dict[str, Any] | None:
    """symbol -> newest stamp, from either tape's shape; None when the tape carries none."""
    if not isinstance(doc, dict):
        return None
    per = doc.get("symbols_last_tick_ms")
    if isinstance(per, dict):
        return dict(per)
    if "last_tick_ms" in doc or "state" in doc:     # a bronze status without per-symbol stamps
        return None
    rows = {k: r.get("last_tick_ms") for k, r in doc.items() if isinstance(r, dict)}
    return rows or None


def judge(path: Path, sess: dict[str, set[int]], now: datetime) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"status": "UNMEASURED", "why": "tape artifact absent"}
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "why": f"unreadable ({type(exc).__name__})"}
    per = stamps(doc)
    if not per or not any(isinstance(v, int) and v > 0 for v in per.values()):
        return {"status": "UNMEASURED", "why": "no per-symbol tick stamps in the tape"}
    v_now = now.replace(tzinfo=None) + venue_lead(now)
    # The tape's OWN enrolment is judged: a symbol the tape never carried is a coverage
    # question, not a freshness one, and is counted beside the verdict, never hidden.
    # AN UNREGISTERED SYMBOL HAS NO KNOWN SESSION (audit 2026-10-29, S4). It used to get the FX
    # week, so a dead crypto CFD missing from universe.json read CLOSED on Saturday and the tape
    # read FRESH: a false all-clear. It is judged 24/7 now -- FRESH when it is live, and when it
    # is not, UNMEASURED (RED) with the reason, never a silent CLOSED.
    rows: dict[str, dict[str, Any]] = {}
    for sym in sorted(per):
        if sym in sess:
            rows[sym] = judge_symbol(per.get(sym), sess.get(sym) or class_slots(None), v_now)
            continue
        r = judge_symbol(per.get(sym), set(range(168)), v_now)
        if r["status"] != "FRESH":
            r = {**r, "status": "UNMEASURED",
                 "why": ("not in data/universe/universe.json, so its session cannot be judged, "
                         "and it has no tick within the last "
                         f"{MAX_AGE_H:g} h -- register it or it stays RED")}
        rows[sym] = {**r, "unregistered": True}
    not_enrolled = sorted(set(sess) - set(per))
    by: dict[str, list[str]] = {}
    for sym, r in rows.items():
        by.setdefault(r["status"], []).append(sym)
    newest = max(int(v) for v in per.values() if isinstance(v, int) and v > 0)
    out: dict[str, Any] = {"n_symbols": len(rows), "n_not_enrolled": len(not_enrolled),
                           "not_enrolled": not_enrolled[:60],
                           "counts": {k: len(v) for k, v in sorted(by.items())},
                           "newest_tick_venue": venue_dt(newest).isoformat(),
                           "stale": by.get("STALE", [])[:60],
                           "unmeasured": by.get("UNMEASURED", [])[:60],
                           "symbols": {k: v for k, v in rows.items() if v["status"] != "CLOSED"}}
    bad = len(by.get("STALE", [])) + len(by.get("UNMEASURED", []))
    if bad:
        return {**out, "status": "STALE",
                "why": f"{bad} of {len(rows) - len(by.get('CLOSED', []))} open symbol(s) have "
                       f"no tick within {MAX_AGE_H:g} h of their own session"}
    if not by.get("FRESH"):
        return {**out, "status": "MARKET_CLOSED", "why": "every symbol's session is shut"}
    return {**out, "status": "FRESH", "why": ""}


def _read(path: Path) -> Any:
    try:
        # utf-8-sig: Windows PowerShell's `Set-Content -Encoding UTF8` writes a BOM.
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def terminal_link(desk: Path, now: datetime) -> dict[str, Any]:
    """Is the MT5 terminal's Python link up? From MT5-TerminalBoot's passed-probe stamp."""
    doc = _read(desk / TERMINAL_OK)
    raw = doc.get("at") if isinstance(doc, dict) else None
    try:
        at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return {"status": "UNMEASURED",
                "why": f"desks/mt5/{TERMINAL_OK} absent or unstamped -- the IPC probe has not "
                       f"passed on this box, or MT5-TerminalBoot has never run"}
    at = at if at.tzinfo else at.replace(tzinfo=UTC)
    age = round((now - at).total_seconds() / 3600, 2)
    if age > TERMINAL_MAX_AGE_H:
        return {"status": "DOWN", "last_ok": at.isoformat(), "age_h": age,
                "why": f"the terminal's IPC probe last passed {age:g} h ago (MT5-TerminalBoot): "
                       f"the MT5 Python link is down, so no recorder can pull ticks"}
    return {"status": "UP", "last_ok": at.isoformat(), "age_h": age, "why": ""}


def cause(desk: Path, link: dict[str, Any]) -> str:
    """The most likely reason a tape is not fresh, in the order the evidence is decisive."""
    if link["status"] != "UP":
        return link["why"]
    status = _read(desk / TAPES[0][1])
    if isinstance(status, dict):
        if status.get("paused_reason"):
            return f"the bronze recorder is PAUSED: {status['paused_reason']}"
        errs = status.get("errors") or {}
        if isinstance(errs, dict) and errs.get("_alive"):
            return f"the bronze recorder cannot reach the terminal: {errs['_alive']}"
    return ("the terminal link is up and the recorder reports no pause: it is not running or "
            "not advancing -- read desks/mt5/logs/MT5-TickRecorder.log")


def build(desk: Path = DESK, now: datetime | None = None,
          sess: dict[str, set[int]] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    sess = sessions(desk, now) if sess is None else sess
    rows = [{"tape": name, "artifact": f"desks/mt5/{rel}", "producer": producer,
             **judge(desk / rel, sess, now)} for name, rel, producer in TAPES]
    red = [r["tape"] for r in rows if r["status"] in ("STALE", "UNMEASURED")]
    link = terminal_link(desk, now)
    return {"schema": "tape_freshness/2", "generated_at": now.isoformat(timespec="seconds"),
            "max_age_h": MAX_AGE_H, "status": "RED" if red else "GREEN", "red": red,
            "n_red": len(red),
            "n_unmeasured": sum(1 for r in rows if r["status"] == "UNMEASURED"),
            "cause": cause(desk, link) if red else "", "terminal_link": link, "tapes": rows}


def main(argv: list[str] | None = None) -> int:
    rep = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    for r in rep["tapes"]:
        print(f"  {r['status']:<14} {r['tape']:<7} {r.get('counts', '-')}  {r['why']}")
    if rep["cause"]:
        print(f"  cause: {rep['cause']}")
    print(f"tape: {rep['status']} -> {OUT}")
    return 1 if rep["red"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
