"""Every symbol the desk claims to trade must have bars, or a recorded reason it does not.

WHY THIS EXISTS (measured 2026-08-29)

    universe registry:  248 symbols
    H1 parquets:        197
    difference:          54, with nothing anywhere saying why

Fifty-four symbols were untestable and invisible. The sweep enumerates `*_H1.parquet`, so a
symbol with no parquet is not refused, not reported and not counted as a gap -- it silently
ceases to exist, and every coverage number the desk prints is a percentage of the wrong
denominator. "This family was tested on the whole universe" was true of a universe quietly 22%
smaller than the registry said.

THREE CAUSES, THREE RESPONSES, AND THE WHOLE POINT IS TELLING THEM APART:

    NOT_OFFERED           the broker does not quote it on this account. Nothing to fetch; the
                          registry row is the defect and should be retired.
    INSUFFICIENT_HISTORY  real but too young for a walk-forward split. Nothing is wrong; it
                          becomes testable on its own, and re-fetching daily is the fix.
    NEVER_ATTEMPTED       no parquet AND no recorded skip. This is the only alarming one: the
                          fetcher never reached it, so nobody knows which of the other two it is.

Before this, all three looked identical -- an absent file. A watchdog that reported "54 missing"
without separating them would be technically correct and useless, because 51 of them may be
perfectly explained and 3 may be a broken fetch, and the response differs completely.

THE FIXER. It re-runs the universe fetch ON THE BOX, which is the only machine with a logged-in
terminal and therefore the only one that can obtain a bar. It does this ONLY when there is
something a fetch could actually change -- symbols never attempted, or young ones that may have
aged past the floor. Re-fetching for a list of NOT_OFFERED symbols would burn a terminal-bound
job every cycle to re-learn a fact that has not changed, so it does not.
"""
from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNI = ROOT / "desks" / "mt5" / "data" / "universe"
OUT = ROOT / "data" / "bar_coverage.json"
REMOTE = "contabo-mt5"

#: The fetch is terminal-bound and slow; running it every cycle would starve the box. Only fire
#: when the gap is something a fetch can close, and not more often than this.
_REFETCH_MIN_INTERVAL_H = 6.0


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return r.returncode, (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return 124, ""


def _registry_symbols() -> set[str]:
    p = UNI / "universe.json"
    try:
        reg = json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    rows = reg.get("symbols", reg) if isinstance(reg, dict) else reg
    if isinstance(rows, dict):
        return {str(k) for k in rows}
    out = set()
    for r in rows:
        name = r if isinstance(r, str) else (r.get("symbol") or r.get("name"))
        if name:
            out.add(str(name))
    return out


def _skip_ledger() -> dict:
    p = UNI / "bar_coverage_skips.json"
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _box_symbols() -> set[str] | None:
    """What the BOX already holds. None if it could not be asked."""
    rc, out = _run(["ssh", "-o", "ConnectTimeout=30", REMOTE,
                    "powershell -c \"Get-ChildItem "
                    "'C:\\opt\\quant\\desks\\mt5\\data\\universe\\*_H1.parquet' | "
                    "ForEach-Object { $_.BaseName }\""], timeout=180)
    if rc != 0:
        return None
    return {ln.strip().removesuffix("_H1") for ln in out.replace("\r", "").splitlines()
            if ln.strip()}


def _sync_from_box(symbols: list[str]) -> tuple[list[str], list[str]]:
    """Copy parquets the box already has. Returns (synced, failed).

    SYNC BEFORE FETCH, ALWAYS. Measured 2026-08-29: all 54 symbols this reported as missing were
    sitting on the box -- 299 parquets there against 197 here. Nothing was unfetched and nothing
    was unavailable; the two machines had simply drifted, and the VPS was analysing a universe
    22% smaller than the one the box mines on. A fetch would have occupied the terminal for half
    an hour to re-download data that was one scp away, and the first draft of this file did
    exactly that.
    """
    synced, failed = [], []
    for sym in symbols:
        rc, _ = _run(["scp", "-o", "ConnectTimeout=30", "-q",
                      f"{REMOTE}:C:/opt/quant/desks/mt5/data/universe/{sym}_H1.parquet",
                      str(UNI / f"{sym}_H1.parquet")], timeout=180)
        (synced if rc == 0 else failed).append(sym)
    return synced, failed


def _should_refetch(report: dict) -> tuple[bool, str]:
    """Is there anything a TERMINAL-BOUND FETCH could change that a sync could not?"""
    if report["never_attempted"]:
        return True, (f"{len(report['never_attempted'])} symbol(s) have no bars anywhere -- not "
                      f"here, not on the box -- and no recorded reason")
    if report["insufficient_history"]:
        return True, (f"{len(report['insufficient_history'])} symbol(s) were too young to test; "
                      f"they age into eligibility on their own and only a re-fetch notices")
    return False, "every gap is NOT_OFFERED: a re-fetch would re-learn an unchanged fact"


def main() -> int:
    now = datetime.now(tz=UTC)
    registry = _registry_symbols()
    have = {p.stem.removesuffix("_H1") for p in UNI.glob("*_H1.parquet")}
    missing = sorted(registry - have)

    ledger = _skip_ledger()
    reasons = ledger.get("reasons") or {}

    report: dict = {
        "checked_at": now.isoformat(timespec="seconds"),
        "registry_symbols": len(registry), "with_bars": len(have), "missing": len(missing),
        "coverage_pct": round(100.0 * len(have) / len(registry), 1) if registry else 0.0,
        "not_offered": [], "insufficient_history": [], "never_attempted": [],
        "skip_ledger_age": ledger.get("fetched_at"), "refetch": None, "sync": None,
    }

    for sym in missing:
        r = reasons.get(sym) or {}
        kind = r.get("reason")
        if kind == "NOT_OFFERED":
            report["not_offered"].append(sym)
        elif kind == "INSUFFICIENT_HISTORY":
            report["insufficient_history"].append(
                {"symbol": sym, "bars": r.get("bars"), "min_bars": r.get("min_bars")})
        else:
            report["never_attempted"].append(sym)

    print(f"BAR COVERAGE {now.isoformat(timespec='seconds')}")
    print(f"  registry {len(registry)}, with bars {len(have)} "
          f"({report['coverage_pct']}%), missing {len(missing)}")
    print(f"    NOT_OFFERED          {len(report['not_offered'])}  (broker does not quote)")
    print(f"    INSUFFICIENT_HISTORY {len(report['insufficient_history'])}  (too young; ages in)")
    print(f"    NEVER_ATTEMPTED      {len(report['never_attempted'])}  (nobody knows why)")

    if not ledger:
        print("    NOTE: no skip ledger exists yet, so EVERY gap reads as NEVER_ATTEMPTED. The "
              "next fetch on the box writes one and this resolves into real causes.")

    for sym in report["never_attempted"][:12]:
        print(f"      NEVER_ATTEMPTED {sym}")

    # SYNC FIRST. A gap the box can fill is a transfer, not a download.
    if missing:
        box = _box_symbols()
        if box is None:
            report["sync"] = {"ran": False, "why": "box unreachable; cannot compare holdings"}
            print("\n  SYNC: box unreachable -- cannot tell a sync gap from a data gap")
        else:
            recoverable = sorted(set(missing) & box)
            report["box_symbols"] = len(box)
            if recoverable:
                synced, failed = _sync_from_box(recoverable)
                report["sync"] = {"ran": True, "synced": len(synced), "failed": failed}
                print(f"\n  SYNCED {len(synced)} parquet(s) the box already had "
                      f"(box holds {len(box)}, this machine held {len(have)})")
                have |= set(synced)
                missing = sorted(set(missing) - set(synced))
                # Everything below must judge the state AFTER the sync, or it would fire a
                # terminal-bound fetch for symbols that just arrived.
                report["never_attempted"] = [x for x in report["never_attempted"]
                                             if x not in set(synced)]
                report["with_bars"] = len(have)
                report["missing"] = len(missing)
                report["coverage_pct"] = (round(100.0 * len(have) / len(registry), 1)
                                          if registry else 0.0)
                print(f"  coverage now {report['coverage_pct']}% "
                      f"({len(have)}/{len(registry)})")
            else:
                report["sync"] = {"ran": False, "why": "the box has none of the missing symbols "
                                                       "either; this is a real data gap"}

    want, why = _should_refetch(report)
    # RATE LIMIT, and it is not a nicety. The fetch is terminal-bound and takes tens of minutes
    # on the box that also runs the gateway; firing it on every timer tick would keep the
    # terminal permanently busy re-learning the same 54 symbols. The interval was declared in the
    # first version of this file and never enforced -- a constant that documents an intention
    # nothing implements is worse than no constant, because it reads as a guarantee.
    if want:
        prev_at = None
        if OUT.exists():
            try:
                prev = json.loads(OUT.read_text("utf-8"))
                r = prev.get("refetch") or {}
                if r.get("ran"):
                    prev_at = prev.get("checked_at")
            except (OSError, json.JSONDecodeError):
                prev_at = None
        if prev_at:
            try:
                last = datetime.fromisoformat(prev_at.replace("Z", "+00:00"))
                if not last.tzinfo:
                    last = last.replace(tzinfo=UTC)
                age_h = (now - last).total_seconds() / 3600.0
                if age_h < _REFETCH_MIN_INTERVAL_H:
                    want = False
                    why = (f"a refetch ran {age_h:.1f}h ago and the interval is "
                           f"{_REFETCH_MIN_INTERVAL_H}h; the gap is real but re-running now "
                           f"would only occupy the terminal")
            except ValueError:
                pass
    if want:
        print(f"\n  REFETCH: {why}")
        # The box is the only machine with a logged-in terminal, so it is the only place a bar
        # can be obtained. Failure here is reported, never retried in a loop: a terminal that is
        # logged out stays logged out, and hammering it would just bury the reason.
        rc, out = _run(["ssh", "-o", "ConnectTimeout=30", REMOTE,
                        # `py -3` is what the box's own scheduled tasks invoke; the venv path
                        # this first used does not exist there, so the fetch returned rc=1 with
                        # no output and the watchdog recorded a refetch that never ran.
                        "cd C:\\opt\\quant && py -3 "
                        "desks\\mt5\\research\\fetch_universe.py"], timeout=1800)
        tail = "\n".join(out.splitlines()[-4:])
        report["refetch"] = {"ran": True, "rc": rc, "tail": tail, "why": why}
        print(f"  refetch rc={rc}\n{tail}")
    else:
        report["refetch"] = {"ran": False, "why": why}
        print(f"\n  no refetch: {why}")

    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"  -> {OUT}")
    # NEVER_ATTEMPTED is the only state that means something is broken here. A NOT_OFFERED symbol
    # is a registry row to retire and a young one just needs time; failing on those would make
    # this check red forever and therefore ignored.
    return 1 if report["never_attempted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
