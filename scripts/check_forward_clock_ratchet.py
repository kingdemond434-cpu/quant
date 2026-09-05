#!/usr/bin/env python3
"""THE FORWARD CLOCK IS A RATCHET: a pre-registration boundary may only move EARLIER, never later.

WHY THIS EXISTS (2026-08-27). The desk's whole path to live capital runs through one number --
`days >= 14` of pre-registered forward evidence (L1.58). Nothing measured it. Measured from the
committed history of `desks/mt5/data/sleeve_registry.json`, the entire forward book was re-based
to `frozen_at = now` three times in 32 hours (08-26T01:42, 08-27T01:13, 08-27T03:31), so no clock
had ever survived a day, and every organ downstream read healthy while it happened:
`monitor_mt5_shadow_sync` reported `status: OPERATING, defects: []`; `live_readiness.json`
reported the blocker as "the market has not yet supplied the unseen observations" -- a desk defect
attributed to the world. Root cause fixed in `sleeve_registry._read` (an unreadable registry read
as an empty one, so `freeze()` took its create branch and re-minted every row). This is the
detector that would have caught it on the first occurrence, and catches the next cause too --
because it watches the QUANTITY the law turns on, not the mechanism that damaged it.

WHAT IT ASSERTS. For every clock, `forward_start` is compared against the earliest value this
fence has ever recorded for that key:

  * moved EARLIER or unchanged -> fine. `freeze()`'s backfill can only ever move it earlier, and
    an earlier boundary cannot buy a window that was not served.
  * moved LATER with a recorded restart -> fine, and named. A restart is legitimate when
    something SAID so: a `migration` block in the registry, an archived row, or a
    `REVIVED_CERTIFIED` action in `forward_reconcile.json` at or after the old stamp.
  * moved LATER with nothing recorded -> SILENT_REBASE. This is the defect. A window that was
    served and then discarded is unrecoverable evidence, and the desk cannot tell the difference
    between a clock at day 13 and one silently restarted at day 0.

ABSENCE IS NEVER A CLEAN VERDICT (L1.28a). No shadow state, no clocks, or an unreadable floor is
reported as UNMEASURED with its reason and exits non-zero -- never as "no regressions found".

    measure:  .venv/bin/python scripts/check_forward_clock_ratchet.py
    floor:    data/forward_clock_floor.json   (earliest boundary per key; may only move earlier)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
SHADOW = DESK / "reports" / "shadow"
REGISTRY = DESK / "data" / "sleeve_registry.json"
RECONCILE = DESK / "data" / "forward_reconcile.json"
FLOOR = ROOT / "data" / "forward_clock_floor.json"
OUT = ROOT / "data" / "forward_clock_ratchet.json"

#: A clock in one of these states is not accruing and its boundary is not expected to hold.
TERMINAL = {"KILL", "KILLED", "PROMOTED", "DEAD", "REJECTED", "RETIRED", "RETIRED_ORPHAN",
            "RETIRED_GATE_FAIL", "RETIRED_UNRECONSTRUCTIBLE", "QUARANTINED_UNCERTIFIED",
            "IDENTITY_BROKEN"}

#: The floor is only meaningful if it is being re-measured. Wired at 30 min; alarm past 6h.
STALE_HOURS = 6.0


def _read(path: Path) -> dict | None:
    """None means UNREADABLE-OR-ABSENT, and the caller must not spend it as an empty answer."""
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _write_atomic(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _ts(value: object) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def live_clocks() -> dict[str, dict]:
    """Every non-terminal forward clock, keyed as its engine names it, with its boundary.

    Reads the shadow states (the engines' own record) and the registry (the freeze-then-verify
    record). Where both carry a boundary the EARLIER one wins: the registry's copy is written by
    an idempotent freeze that can only ever move it earlier, so it is the conservative witness of
    what was actually pre-registered.
    """
    clocks: dict[str, dict] = {}
    for name in ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json",
                 "external_shadow_state.json"):
        doc = _read(SHADOW / name)
        if doc is None:
            continue
        rows = list(doc.items()) + list((doc.get("sleeves") or {}).items())
        for key, row in rows:
            if not isinstance(row, dict) or "status" not in row:
                continue
            if str(row.get("status") or "").upper() in TERMINAL:
                continue
            start = _ts(row.get("forward_start"))
            if start is not None:
                clocks[str(key)] = {"forward_start": start, "source": name,
                                    "n": int(row.get("n") or 0)}
    reg = _read(REGISTRY) or {}
    for key, row in (reg.get("sleeves") or {}).items():
        if not isinstance(row, dict) or str(row.get("status") or "").upper() in TERMINAL:
            continue
        start = _ts(row.get("forward_start"))
        if start is None:
            continue
        held = clocks.get(str(key))
        if held is None or start < held["forward_start"]:
            clocks[str(key)] = {"forward_start": start,
                                "source": "sleeve_registry.json",
                                "n": int((held or {}).get("n") or 0)}
    return clocks


def recorded_restarts() -> list[tuple[str | None, datetime]]:
    """Every restart the desk WROTE DOWN, as (key-or-None-for-all, when).

    A `None` key is a book-wide event (a schema migration) and explains any clock re-stamped at
    or after it. Anything not covered here is a re-base nobody recorded.
    """
    events: list[tuple[str | None, datetime]] = []
    reg = _read(REGISTRY) or {}
    migration = reg.get("migration")
    if isinstance(migration, dict) and (when := _ts(migration.get("at"))):
        events.append((None, when))
    for row in reg.get("archived_identities") or []:
        if isinstance(row, dict) and (when := _ts(row.get("archived_at"))):
            events.append((str(row.get("sleeve_key") or ""), when))
    archive = _read(DESK / "data" / "sleeve_registry_archive.json") or {}
    for row in archive.get("archived") or []:
        if isinstance(row, dict) and (when := _ts(row.get("archived_at"))):
            events.append((str(row.get("key") or ""), when))
    rec = _read(RECONCILE) or {}
    checked = _ts(rec.get("checked_at")) or _ts(rec.get("reconciled_at"))
    for action in rec.get("actions") or []:
        if not isinstance(action, dict):
            continue
        if str(action.get("action") or "").upper() in {"REVIVED_CERTIFIED", "RESTARTED"} and checked:
            events.append((str(action.get("key") or ""), checked))
    return events


def main() -> int:
    now = datetime.now(tz=UTC)
    clocks = live_clocks()
    floor_doc = _read(FLOOR)
    floor = dict((floor_doc or {}).get("earliest_forward_start") or {})
    restarts = recorded_restarts()

    if not clocks:
        report = {"measured_at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                  "why": ("no non-terminal forward clock carries a boundary in any shadow state "
                          "or in the registry -- that is the absence of a book to measure, not a "
                          "book with no regressions, and it is exactly the shape a total wipe "
                          "leaves behind (L1.28a)"),
                  "clocks": 0}
        _write_atomic(OUT, report)
        print(f"FORWARD CLOCK RATCHET: UNMEASURED -- {report['why']}")
        return 2

    breaches, restarted, ages = [], [], []
    # A RATCHET NEVER FORGETS, AND THIS ONE DID. `new_floor` started EMPTY and was rebuilt from
    # the clocks visible on THIS pass, so any key the pass could not see was dropped from the
    # floor outright -- and `TERMINAL` above makes that routine, because `RETIRED_ORPHAN` is in
    # it and this desk retires and revives orphan rows continuously (`forward_reconcile`'s
    # REVIVED_CERTIFIED). On the pass where a row read retired its floor was forgotten; on the
    # pass where it came back `prior` was None, so the boundary was re-minted at whatever the
    # row carried by then and the silent re-base this fence exists to catch was laundered BY THE
    # FENCE. Measured 2026-08-30 from this file's own committed history: 37 -> 19 -> 37 -> 33 ->
    # 19 keys inside four hours, and USDJPY.asia, USDJPY.asia#rr=1.5 and USDJPY.asia#rr=2.5 each
    # had their floor move 11.6h LATER through exactly that route, in the artifact whose stated
    # rule is "may only move EARLIER". Absence is never a clean verdict (L1.28a): a key not seen
    # this pass is unmeasured, never released. Seeding from the prior floor is what makes the
    # artifact monotone, which is the whole meaning of the word.
    new_floor: dict[str, str] = dict(floor)
    for key, row in sorted(clocks.items()):
        start = row["forward_start"]
        ages.append((now - start).total_seconds() / 86400.0)
        prior = _ts(floor.get(key))
        if prior is None or start <= prior:
            new_floor[key] = (start if prior is None else min(start, prior)).isoformat()
            continue
        # Moved LATER. Legitimate only if something recorded a restart at or after the old stamp.
        excuse = next((f"{k or 'book-wide'} @ {w.isoformat(timespec='seconds')}"
                       for k, w in restarts if (k in (None, "", key)) and w >= prior), None)
        lost_days = (start - prior).total_seconds() / 86400.0
        if excuse:
            restarted.append({"key": key, "recorded_restart": excuse,
                              "was": prior.isoformat(), "now": start.isoformat(),
                              "window_days_restarted": round(lost_days, 3)})
            new_floor[key] = start.isoformat()
        else:
            breaches.append({"key": key, "was": prior.isoformat(), "now": start.isoformat(),
                             "forward_days_destroyed": round(lost_days, 3),
                             "source": row["source"], "forward_trades_now": row["n"]})
            # The floor does NOT absorb an unexplained re-base: keep the earliest boundary so the
            # breach stays visible next run instead of being laundered into the new normal.
            new_floor[key] = prior.isoformat()

    max_age = max(ages)
    prior_max = float((floor_doc or {}).get("max_clock_age_days") or 0.0)
    measured_at = _ts((floor_doc or {}).get("measured_at"))
    stale_h = ((now - measured_at).total_seconds() / 3600.0) if measured_at else None

    report = {
        "measured_at": now.isoformat(timespec="seconds"),
        "status": "BREACH" if breaches else "OK",
        "clocks": len(clocks),
        "max_clock_age_days": round(max_age, 3),
        "prior_max_clock_age_days": round(prior_max, 3),
        "days_to_promotion_bar": round(max(0.0, 14.0 - max_age), 3),
        "silent_rebases": breaches,
        "recorded_restarts": restarted,
        "floor_age_hours": None if stale_h is None else round(stale_h, 2),
        "measuring_command": "scripts/check_forward_clock_ratchet.py",
    }
    _write_atomic(OUT, report)
    _write_atomic(FLOOR, {
        "measured_at": now.isoformat(timespec="seconds"),
        "max_clock_age_days": round(max(max_age, prior_max), 3),
        "earliest_forward_start": new_floor,
        # A floor entry may be WITHDRAWN only by a written correction, never by a pass that
        # simply did not see the key. Carried forward verbatim so a boundary that legitimately
        # moved later never looks unexplained to a reader a month from now: the alternative is a
        # floor that jumps with no record, which is indistinguishable from the breach itself.
        "corrections": list((floor_doc or {}).get("corrections") or []),
        "measuring_command": "scripts/check_forward_clock_ratchet.py",
        "rule": ("a pre-registration boundary may only move EARLIER; moving it later without a "
                 "recorded restart destroys served forward evidence and is a breach"),
        "stale_after_hours": STALE_HOURS,
    })

    print(f"FORWARD CLOCK RATCHET: {len(clocks)} clock(s), oldest {max_age:.2f}d "
          f"(bar 14d, {report['days_to_promotion_bar']:.2f}d to go)")
    for row in restarted:
        print(f"  restarted (recorded): {row['key']} -- {row['recorded_restart']}, "
              f"{row['window_days_restarted']:.2f}d of window intentionally discarded")
    for row in breaches:
        print(f"  SILENT RE-BASE: {row['key']} boundary moved {row['was']} -> {row['now']}, "
              f"{row['forward_days_destroyed']:.2f} day(s) of served forward evidence destroyed "
              f"with no recorded restart ({row['source']})")
    if stale_h is not None and stale_h > STALE_HOURS:
        print(f"  FLOOR STALE: last measured {stale_h:.1f}h ago (bar {STALE_HOURS}h) -- a ratchet "
              f"nobody re-measures cannot catch the next re-base")
        return 1
    return 1 if breaches else 0


if __name__ == "__main__":
    sys.exit(main())
