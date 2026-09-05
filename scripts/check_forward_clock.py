"""The forward clock must move forward. Watch it, and repair it when it does not.

WHY THIS EXISTS (measured 2026-08-29T14:01)

Three scalp sleeves held 14, 27 and 34 forward trades and carried a `forward_start` stamped four
minutes earlier. The dashboard rendered them as `day 0/14`, which is what the data said and what
nobody questioned, because "day 0" looks like a new sleeve rather than a broken one.

They were not new. Something upstream retires these rows as orphans on a key-shape inference
every pass, `forward_reconcile` revives them every pass because they hold a live certificate, and
the revival stamped a FRESH clock every time. A clock restamped every cycle never reaches day 14.
No sleeve on this desk could ever have certified -- not slowly, not eventually, never -- and the
symptom was a number that looked merely early.

THE INVARIANT. A sleeve's `forward_start` may only move in two circumstances: it is being set for
the first time, or its frozen identity changed (new strategy, new clock, by law). Any other
movement is evidence destruction. Specifically, `forward_start` must never be LATER than the
first trade the sleeve has already recorded -- a clock cannot start after the evidence it counts.
That one comparison catches the entire failure class without needing a previous snapshot.

WHY IT NO LONGER REPAIRS (2026-08-30). It used to move `forward_start` back to the row's first
recorded entry, calling that "exactly determined". Three measurements retired the repair:

  1. IT BACKDATED THE FORWARD WINDOW. `first_entry` is a REPLAYED trade, and `shadow_forward`
     replays from SHADOW_START on every pass -- deliberately, keeping history as history. Its
     own words: "THE CLOCK STARTS AT PRE-REGISTRATION, NOT AT THE FIRST TRADE EVER TAKEN ...
     that is the precise leakage the two-stage law exists to stop." Moving the boundary back to
     a replayed trade hands the row evidence gathered while it was still being SELECTED. L1.58
     is unconditional: the forward window is never compressed, BACKDATED or waived. On the live
     book this would have handed 46 clocks up to 227.4h -- 9.5 days -- of selection-era trades.
  2. THE WRITE WAS INERT, AND SAID OTHERWISE. `desks/mt5/reports/shadow/*.json` is a REPLICA:
     `ops/pull_desk_state.sh` scp's all four ledgers from the trading box every two minutes, and
     the authoritative writer is there. Measured 2026-08-30: a repair written at 04:53:58 was
     gone by 04:55:29, `forward_start_repaired_at` and all. Every "REPAIRED" line this has ever
     printed was false, and it printed 46 of them a night.
  3. THE TRANSIENT WRITE POISONED THE REAL FENCE. `check_forward_clock_ratchet` samples these
     same ledgers, and in the window between the write and the next pull it recorded the
     backdated boundary as the floor -- which by construction may only move EARLIER, so the
     corruption is permanent. Three keys (CHFNOK.carry.asia, EURZAR/USDZAR.overnight_gap_decay)
     carry exact-hour BAR TIMES as their floor where every honest stamp carries microseconds,
     and the ratchet reports all three as SILENT_REBASE breaches that never happened.

So it reports, and the reporting is the whole job. A boundary that genuinely moved forward is
already caught by `check_forward_clock_ratchet` against the desk's OWN recorded stamps -- a
source that cannot backdate, because every value in it is a boundary the desk once declared.

WHAT IT WILL NOT DO. It writes nothing into any ledger: not `forward_start`, not status, not a
repair marker. It does not resurrect a retired sleeve. Rows in a terminal state are not measured
at all -- their clocks are frozen by design and their `first_entry` predates the boundary filter
that `shadow_forward` now applies, so holding them to this comparison produced 31 false hits out
of 46 and buried the 15 real ones.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHADOW = ROOT / "desks" / "mt5" / "reports" / "shadow"
OUT = ROOT / "data" / "forward_clock_health.json"

LEDGERS = ("shadow_state.json", "qquant_shadow_state.json",
           "scalp_shadow_state.json", "external_shadow_state.json")

#: Fields a row may carry its first observation in. Engines differ and always have; reading only
#: one of them would silently pass every row written by the other two.
_FIRST_TRADE_FIELDS = ("first_entry", "first_trade_at", "first_entry_time")

#: A clock this much newer than its own first trade is churn, not clock skew. One hour absorbs
#: broker-offset conversion (Fusion runs +3h and the boundary is converted at read time) without
#: absorbing a genuine restamp, which lands hours-to-days late.
_SKEW_TOLERANCE_H = 1.0

#: A clock in one of these states is frozen by design and is not measured here. Kept identical to
#: `check_forward_clock_ratchet.TERMINAL` on purpose: two fences reading the same ledgers with
#: different ideas of which rows are live is how one of them ends up reporting the other's normal.
_TERMINAL = {"KILL", "KILLED", "PROMOTED", "DEAD", "REJECTED", "RETIRED", "RETIRED_ORPHAN",
             "RETIRED_GATE_FAIL", "RETIRED_UNRECONSTRUCTIBLE", "QUARANTINED_UNCERTIFIED",
             "IDENTITY_BROKEN"}


def _rows(path: Path) -> dict:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("sleeves", data) if isinstance(data, dict) else {}


def _parse(ts: object) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _first_trade(row: dict) -> datetime | None:
    for f in _FIRST_TRADE_FIELDS:
        d = _parse(row.get(f))
        if d is not None:
            return d
    return None


def main() -> int:
    now = datetime.now(tz=UTC)
    report: dict = {"checked_at": now.isoformat(timespec="seconds"),
                    "churned": [], "repaired": [], "unrepairable": [], "healthy": 0,
                    "skipped_terminal": 0,
                    "writes": "NONE -- these ledgers are replicas of the trading box, re-copied "
                              "by ops/pull_desk_state.sh every ~2 minutes; and `first_entry` is a "
                              "REPLAYED trade, so moving a boundary back to it would backdate the "
                              "forward window (L1.58). Repair belongs to the writer on the box.",
                    "repair_authority": False}

    print(f"FORWARD CLOCK {now.isoformat(timespec='seconds')}")

    for name in LEDGERS:
        path = SHADOW / name
        if not path.exists():
            continue
        try:
            json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # An unreadable ledger is UNMEASURED, never "no churn found" (L1.28a). These files
            # are scp'd in every two minutes, so a torn read is a live possibility and reading it
            # as a clean pass is exactly how a stopped book reports healthy.
            report["unrepairable"].append(
                {"ledger": name, "key": None, "n": 0,
                 "why": f"ledger unreadable ({type(exc).__name__}: {exc}); no clock in it was "
                        f"measured this pass"})
            continue
        rows = _rows(path)

        for key, row in rows.items():
            if not isinstance(row, dict):
                continue
            if str(row.get("status") or "").upper() in _TERMINAL:
                report["skipped_terminal"] += 1
                continue                      # frozen by design; see the module docstring
            n = int(row.get("n") or 0)
            if n <= 0:
                continue                      # no evidence yet: any clock is defensible
            start = _parse(row.get("forward_start"))
            first = _first_trade(row)
            if start is None:
                continue                      # unstamped fails the day gate closed already
            if first is None:
                # A row with trades but no first-trade stamp cannot prove when its clock began,
                # and inventing one would be exactly the fabrication this exists to prevent.
                if (now - start).total_seconds() < 3600 and n >= 5:
                    report["unrepairable"].append(
                        {"ledger": name, "key": key, "n": n,
                         "why": f"clock stamped {start.isoformat()} but row records no first "
                                f"trade time -- cannot prove the true start"})
                continue

            drift_h = (start - first).total_seconds() / 3600.0
            if drift_h <= _SKEW_TOLERANCE_H:
                report["healthy"] += 1
                continue

            # The clock starts AFTER evidence it is already counting. Impossible; it was restamped.
            report["churned"].append({"ledger": name, "key": key, "n": n,
                                      "forward_start": start.isoformat(),
                                      "first_trade": first.isoformat(),
                                      "evidence_lost_hours": round(drift_h, 1),
                                      "repair_owner": "the writer on the trading box; this "
                                                      "process holds a replica and cannot fix it"})
            print(f"  CHURNED {key}: clock is {drift_h:.1f}h AFTER its own first trade "
                  f"(n={n}); NOT repaired here -- see the module docstring")

    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"  healthy {report['healthy']}, churned {len(report['churned'])}, "
          f"skipped-terminal {report['skipped_terminal']}, "
          f"unrepairable {len(report['unrepairable'])}")
    for u in report["unrepairable"][:6]:
        print(f"    UNREPAIRABLE {u['key']}: {u['why']}")
    print(f"  -> {OUT}")
    # Churn is the defect; repairing it here does not make the cycle that caused it healthy, so
    # a repaired run still reports failure and stays visible until the cause upstream stops.
    return 1 if (report["churned"] or report["unrepairable"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
