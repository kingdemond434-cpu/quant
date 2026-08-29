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

WHY IT REPAIRS RATHER THAN ONLY REPORTS. The repair is exactly determined: the earliest recorded
entry under the current identity IS the moment forward evidence began, so there is no judgement
to exercise and nothing to get wrong. Reporting alone would have left the desk with a correct
report and a clock still pinned at zero. It refuses to guess in the one case where the right
answer is unknowable -- a row whose trades carry no timestamps -- and says so.

WHAT IT WILL NOT DO. It never moves a clock FORWARD (that would erase evidence, which is the
disease), never resurrects a retired sleeve, and never writes status. Only `forward_start` moves,
only backwards, only to a timestamp the row's own trades prove.
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
                    "churned": [], "repaired": [], "unrepairable": [], "healthy": 0}

    print(f"FORWARD CLOCK {now.isoformat(timespec='seconds')}")

    for name in LEDGERS:
        path = SHADOW / name
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = _rows(path)
        dirty = False

        for key, row in rows.items():
            if not isinstance(row, dict):
                continue
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
                                      "evidence_lost_hours": round(drift_h, 1)})
            row["forward_start"] = first.isoformat()
            row["forward_start_repaired_at"] = now.isoformat(timespec="seconds")
            row["forward_start_repair_reason"] = (
                f"clock was {drift_h:.1f}h later than this row's own first trade; restored to "
                f"the first recorded entry (churn repair)")
            report["repaired"].append(f"{name}:{key}")
            dirty = True
            print(f"  REPAIRED {key}: clock was {drift_h:.1f}h AFTER its own first trade "
                  f"(n={n}) -> restored to {first.isoformat()}")

        if dirty:
            if isinstance(raw, dict) and "sleeves" in raw:
                raw["sleeves"] = rows
            else:
                raw = rows
            path.write_text(json.dumps(raw, indent=1), "utf-8")

    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"  healthy {report['healthy']}, churned {len(report['churned'])}, "
          f"repaired {len(report['repaired'])}, unrepairable {len(report['unrepairable'])}")
    for u in report["unrepairable"][:6]:
        print(f"    UNREPAIRABLE {u['key']}: {u['why']}")
    print(f"  -> {OUT}")
    # Churn is the defect; repairing it here does not make the cycle that caused it healthy, so
    # a repaired run still reports failure and stays visible until the cause upstream stops.
    return 1 if (report["churned"] or report["unrepairable"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
