"""TAPE LIVENESS -- one RED/AMBER/GREEN answer to "is the tick moat recording, readable and judged?"

WHY A NEW CHECK, MEASURED 2026-10-29. The tape was declared dead since 09-04 by one reading and
alive to the minute by another, and both were right about different things:

  * `data/tape/tape_state.json` had 138 symbols ticking at 14:04Z the same day. The recorder was
    fine. The only 09-04 rows were Palantir and SpaceX, which the broker no longer lists.
  * Every tape READER opened the wrong files (see `mt5desk.tape_days`), so `_tape_series` was
    None for every symbol and 66k liquidity_regime / orderflow_imbalance cells had 0 verdicts.
  * Nothing compared the two, so a live recorder feeding a blind reader read as either "fine" or
    "dead" depending on which half a pass looked at.

This check walks the whole path -- writer, reader, judge -- and goes RED at the first break:

  RECORDER_DOWN      the freshest tick anywhere, or the crypto class (24/7), is > 2h old.
  SYMBOL_STALE       a universe symbol's last tick is > 2h old while its asset class has been
                     OPEN for at least 2h (most of its peers fresh, on this run and the runs
                     before). Closed markets go stale together and are not RED; a session that
                     just opened is not RED for its thin names; one dead symbol in a live class is.
  READER_BLIND       the shared tape reader (`mt5desk.tape_days`, which every research reader
                     uses) returns nothing for a probe symbol, or its newest tick is > 2h behind
                     what the recorder says it wrote.
  ZERO_SPREAD        every probe tick in the last hour has ask == bid: a feed that is quoting
                     nothing tradeable while looking alive.
  TAPE_NEVER_JUDGED  a tape family has mined cells and zero verdicts (principal 2026-10-14: the
                     tape must produce cells AND certificates).

AMBER, never GREEN, whenever something could not be MEASURED (L1.28a: absence is never a clean
verdict): no universe, no crypto class to prove the recorder on a weekend, a probe symbol with no
tape row, an absent or stale JUDGE_COVERAGE. Also AMBER: a universe symbol with no tape row at
all (`universe.json` can lag the broker) and a taped symbol the universe no longer lists.

    python desks/mt5/moat/tape_liveness.py            # writes reports/TAPE_LIVENESS.json
    exit 0 GREEN/AMBER, 2 RED -- the hourly `tape_liveness` leg books exit 2 as a VERDICT.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

STATE = DESK / "data" / "tape" / "tape_state.json"
TICKS = DESK / "data" / "tape" / "ticks"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
JUDGE_COVERAGE = DESK / "reports" / "JUDGE_COVERAGE.json"
OUT = DESK / "reports" / "TAPE_LIVENESS.json"

STALE_H = float(os.environ.get("TAPE_STALE_H", "2"))
#: A class is OPEN when at least this share of its taped symbols is fresh.
CLASS_OPEN_SHARE = 0.5
#: JUDGE_COVERAGE older than this is not a reading of the judge any more.
COVERAGE_STALE_H = 6.0
#: Read end to end through the shared reader every run. Gold first: it is the live book.
PROBES = ("XAUUSD", "EURUSD", "BTCUSD")
#: The probe reads this many tape days: enough for "did the newest hour land", not a 30-day load.
PROBE_DAYS = 2
TAPE_FAMILIES = ("liquidity_regime", "orderflow_imbalance", "execution_state")
#: Fewer probe ticks than this in the last hour is too few to call a spread zero.
ZERO_SPREAD_MIN_TICKS = 100


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ts(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _age_h(t: datetime | None, now: datetime) -> float | None:
    return None if t is None else round((now - t).total_seconds() / 3600.0, 2)


def recorder_block(state: dict[str, Any], universe: dict[str, Any], now: datetime,
                   prior: dict[str, Any] | None = None
                   ) -> tuple[dict[str, Any], list[str], list[str]]:
    """Writer side: per-symbol freshness against the symbol's own class. (block, red, amber).

    `prior` is the previous report's `recorder` block; each class's `open_since` is carried from
    it so a class counts as open only once it has been open for STALE_H.
    """
    red: list[str] = []
    amber: list[str] = []
    last: dict[str, datetime] = {}
    for sym, row in (state or {}).items():
        t = _ts((row or {}).get("last_tick_utc")) if isinstance(row, dict) else None
        if t is not None:
            last[sym] = t
    if not universe:
        amber.append("UNMEASURED: universe.json absent -- no asset classes, so no symbol can be "
                      "judged against its open peers and the 24/7 crypto proof is missing")
    retired = sorted(s for s in last if universe and s not in universe)
    untaped = sorted(s for s in (universe or {}) if s not in last)
    live = {s: t for s, t in last.items() if s not in retired}
    stale_cut = now - timedelta(hours=STALE_H)
    prior_classes = ((prior or {}).get("classes") or {}) if isinstance(prior, dict) else {}

    classes: dict[str, list[str]] = {}
    for sym in live:
        cls = str(((universe or {}).get(sym) or {}).get("asset_class") or "Unclassified")
        classes.setdefault(cls, []).append(sym)
    by_class: dict[str, dict[str, Any]] = {}
    stale_open: list[str] = []
    for cls, syms in sorted(classes.items()):
        fresh = [s for s in syms if live[s] >= stale_cut]
        is_open = len(fresh) >= CLASS_OPEN_SHARE * len(syms)
        was = prior_classes.get(cls) if isinstance(prior_classes.get(cls), dict) else {}
        open_since = (_ts(was.get("open_since")) or now) if is_open and was.get("open") else now
        settled = is_open and (now - open_since) >= timedelta(hours=STALE_H)
        stale = sorted(s for s in syms if live[s] < stale_cut)
        by_class[cls] = {"symbols": len(syms), "fresh": len(fresh), "open": is_open,
                         "open_since": open_since.isoformat() if is_open else None,
                         "settled": settled, "stale": stale if settled else [],
                         "newest_age_h": _age_h(max(live[s] for s in syms), now)}
        if settled:
            stale_open.extend(stale)

    newest = max(live.values()) if live else None
    newest_age = _age_h(newest, now)
    if newest_age is None or newest_age > STALE_H:
        red.append(f"RECORDER_DOWN: freshest tick anywhere is {newest_age}h old "
                   f"(tape_state.json) -- no symbol is recording")
    crypto = by_class.get("Crypto")
    if crypto is None:
        amber.append("UNMEASURED: no Crypto class taped -- the 24/7 proof that the recorder is "
                     "alive on a closed-market weekend is missing")
    elif not crypto["open"]:
        red.append(f"RECORDER_DOWN: crypto trades 24/7 and {crypto['symbols'] - crypto['fresh']}/"
                   f"{crypto['symbols']} crypto symbols are > {STALE_H}h stale")
    if stale_open:
        red.append(f"SYMBOL_STALE: {len(stale_open)} symbol(s) > {STALE_H}h stale while their "
                   f"class has been open > {STALE_H}h: {', '.join(sorted(stale_open)[:12])}")
    if untaped:
        amber.append(f"NOT_RECORDED: {len(untaped)} universe symbol(s) have no tape row: "
                     f"{', '.join(untaped[:12])}")
    if retired:
        amber.append(f"RETIRED: {len(retired)} taped symbol(s) no longer in the universe: "
                     f"{', '.join(retired)}")
    block = {
        "symbols_taped": len(live), "newest_tick_utc": newest.isoformat() if newest else None,
        "newest_age_h": newest_age, "stale_while_open": sorted(stale_open),
        "classes": by_class, "untaped_universe_symbols": untaped, "retired": retired,
        "last_tick_utc": {s: t.isoformat() for s, t in sorted(live.items())},
    }
    return block, red, amber


def _default_reader(symbol: str) -> Any:
    from mt5desk.tape_days import recent_quotes
    return recent_quotes(TICKS / symbol, PROBE_DAYS)


def reader_block(state: dict[str, Any], now: datetime,
                 reader: Callable[[str], Any] | None = None
                 ) -> tuple[dict[str, Any], list[str], list[str]]:
    """Reader side: does the shared reader see what the recorder wrote? (block, red, amber)."""
    read = reader or _default_reader
    red: list[str] = []
    amber: list[str] = []
    out: dict[str, Any] = {}
    for sym in PROBES:
        wrote = _ts(((state or {}).get(sym) or {}).get("last_tick_utc"))
        row: dict[str, Any] = {"recorder_last_tick_utc": wrote.isoformat() if wrote else None}
        try:
            frame = read(sym)
        except Exception as exc:  # the probe failing IS the finding, never a crash
            frame = None
            row["error"] = f"{type(exc).__name__}: {exc}"[:200]
        if frame is None or len(frame) == 0:
            row["verdict"] = "BLIND"
            if wrote is None:
                amber.append(f"UNMEASURED: probe {sym} has no tape row and the reader sees "
                             f"nothing -- cannot tell a blind reader from an untaped symbol")
            elif wrote >= now - timedelta(hours=STALE_H):
                red.append(f"READER_BLIND: {sym} tape was written at {wrote:%m-%d %H:%MZ} but "
                           f"the shared tape reader returns no ticks")
            else:
                amber.append(f"UNMEASURED: probe {sym} reader sees nothing and its last write "
                             f"({wrote:%m-%d %H:%MZ}) is too old to prove the reader against")
            out[sym] = row
            continue
        seen = frame.index.max()
        seen_dt = seen.to_pydatetime() if hasattr(seen, "to_pydatetime") else seen
        row["reader_rows"] = len(frame)
        row["reader_newest_utc"] = seen_dt.isoformat()
        if wrote is None:
            amber.append(f"UNMEASURED: probe {sym} has no tape_state row to compare the reader to")
        lag = (wrote - seen_dt).total_seconds() / 3600.0 if wrote is not None else None
        row["reader_lag_h"] = round(lag, 2) if lag is not None else None
        if lag is not None and lag > STALE_H:
            red.append(f"READER_BLIND: {sym} reader's newest tick is {lag:.1f}h behind the "
                       f"recorder -- readers and writers disagree about which files are the tape")
        recent = frame[frame.index >= seen - timedelta(hours=1)]
        if len(recent) >= ZERO_SPREAD_MIN_TICKS:
            zero = float(((recent["ask"] - recent["bid"]) <= 0).mean())
            row["zero_spread_share_1h"] = round(zero, 4)
            if zero >= 1.0:
                red.append(f"ZERO_SPREAD: every {sym} tick in its last hour has ask == bid")
        row["verdict"] = "OK"
        out[sym] = row
    return out, red, amber


def judge_block(cov: dict[str, Any] | None, now: datetime
                ) -> tuple[dict[str, Any], list[str], list[str]]:
    """Judge side: are tape cells being judged at all? (block, red, amber)."""
    red: list[str] = []
    amber: list[str] = []
    age = _age_h(_ts((cov or {}).get("at")), now)
    out: dict[str, Any] = {"coverage_at": (cov or {}).get("at"), "coverage_age_h": age}
    if not cov:
        amber.append("UNMEASURED: JUDGE_COVERAGE.json absent -- tape verdicts cannot be counted")
        return out, red, amber
    if age is None or age > COVERAGE_STALE_H:
        amber.append(f"UNMEASURED: JUDGE_COVERAGE.json is {age}h old (> {COVERAGE_STALE_H}h) -- "
                     f"its tape counts are not a reading of the judge now")
    fams = cov.get("families") or {}
    for fam in TAPE_FAMILIES:
        row = fams.get(fam)
        if not isinstance(row, dict):
            out[fam] = "UNMEASURED (absent from JUDGE_COVERAGE)"
            amber.append(f"UNMEASURED: {fam} absent from JUDGE_COVERAGE")
            continue
        keep = {k: row.get(k) for k in ("mined", "judged_window", "judged_total", "unjudged",
                                        "not_testable", "oldest_unjudged_age_h")}
        out[fam] = keep
        if (keep["mined"] or 0) > 0 and not keep["judged_total"]:
            red.append(f"TAPE_NEVER_JUDGED: {fam} has {keep['mined']} mined cells and 0 verdicts")
    return out, red, amber


def run(now: datetime | None = None, reader: Callable[[str], Any] | None = None,
        prior: dict[str, Any] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    state = _read(STATE) or {}
    universe = _read(UNIVERSE) or {}
    if prior is None:
        prior = (_read(OUT) or {}).get("recorder")
    rec, red, amber = recorder_block(state, universe, now, prior)
    rdr, red_r, amber_r = reader_block(state, now, reader)
    jdg, red_j, amber_j = judge_block(_read(JUDGE_COVERAGE), now)
    red += red_r + red_j
    amber += amber_r + amber_j
    verdict = "RED" if red else ("AMBER" if amber else "GREEN")
    return {"at": now.isoformat(timespec="seconds"), "verdict": verdict,
            "red": red, "amber": amber, "stale_h": STALE_H,
            "recorder": rec, "reader": rdr, "judge": jdg,
            "rule": "RED on the first break between writer, reader and judge; AMBER when any "
                    "part could not be measured; see module doc"}


def write_report(report: dict[str, Any], out: Path = OUT) -> None:
    """Atomic write. A failed replace (WinError 5 on a file a reader holds) never strands the
    temp file and never raises: the verdict is still printed and still sets the exit code."""
    tmp = out.with_suffix(f".{os.getpid()}.tmp")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(report, indent=1, default=str), "utf-8")
        os.replace(tmp, out)
    except OSError as exc:
        print(f"tape liveness: report NOT written ({type(exc).__name__}: {exc})", flush=True)
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


def main() -> int:
    report = run()
    write_report(report)
    print(f"tape liveness: {report['verdict']}")
    for line in report["red"] + report["amber"]:
        print(f"  {line}")
    return 2 if report["verdict"] == "RED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
