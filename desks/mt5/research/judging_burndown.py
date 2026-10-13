"""THE BACKLOG'S BURN-DOWN, HOURLY: cells leaving the backlog per hour against cells joining it.

    "the backlog burned down faster than creation"                 -- the principal, 2026-09-30

WHY A SEPARATE COUNT. A verdict ROW is not a cell leaving the backlog. The sealed judge appends a
ledger row whenever a cell's terminal gate CHANGES, so a re-judge that moves one cell from
`cpcv` to `walk_forward` is a second row for a cell that left the backlog weeks ago; and a row
whose terminal gate is `UNKNOWN`, or whose downstream status is `NOT_RUN_*`, is a cell the judge
did NOT rule on. Measured on the trading box 2026-09-30: 43% of the last seven days' rows were
`UNKNOWN`. Dividing a backlog by rows/hour therefore answers a question nobody asked. The drain
is FIRST RULINGS: cells whose first real verdict (a named terminal gate, or a pass) landed in the
window. That is the only number that makes the backlog smaller.

THE INFLOW is the docket's own clock: rows whose `first_seen` falls in the window. Mining is never
throttled by anything here -- the inflow is the demand, and the answer to a growing backlog is more
judge (`scripts/warm_gauntlet_cache.py`, `research/judging_throughput.py`), never fewer cells.

THE WARM SIDE is what makes the drain possible without touching the sealed judge. A cell the
warmer has built is a cache hit for the next sweep, so the judge rules on it without spending its
own build budget. `WARM_GAUNTLET.json` publishes how many never-judged cells each round warmed and
how many builds exact equivalence saved; this organ reads those beside the drain so a reader can
see whether the warm side or the sweep is the binding stage.

PUBLISHED: `reports/JUDGING_BURNDOWN.json` -- per window (24h, 7d): first rulings, inflow, rows by
kind; the backlog (read from `JUDGE_COVERAGE.json`, which owns that count); the net drain per day;
days to zero, or GROWING with the net growth per day; and the first-rulings-per-hour needed to
clear the backlog inside `TARGET_DAYS` while still absorbing the inflow. Every missing input is
UNMEASURED with its reason, never a zero (L1.28a). Also `sweep` -- where the judge's last sweep
spent its wall clock (build pool vs the load-and-gate phase, per cell, and which stage binds) --
and `capacity`, the warm side's projected first rulings per day at its last measured rate.

Clock: leg `judging_burndown` in `research/hourly_cycle.py` (department validate). It only reads.
Consumers: `research/judging_throughput.py` (`_burndown`: GROWING is demand, raising cadence) and
`scripts/warm_gauntlet_cache.py` (`gate_room` sizes the warm set by `sweep_anatomy`).

    python desks/mt5/research/judging_burndown.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
COVERAGE = DESK / "reports" / "JUDGE_COVERAGE.json"
WARM = DESK / "reports" / "WARM_GAUNTLET.json"
OUT = DESK / "reports" / "JUDGING_BURNDOWN.json"
UNMEASURED = "UNMEASURED"

#: The horizon the "needed" rate is sized for: clear today's backlog inside this many days while
#: absorbing the measured inflow. A yardstick for the report, never a cap or a target anything
#: throttles toward.
TARGET_DAYS = 30.0
WINDOWS_H = {"24h": 24.0, "7d": 168.0}
NOT_JUDGED_PREFIX = "NOT_RUN"

_AT = re.compile(r'"at"\s*:\s*"([^"]+)"')
_FIRST_SEEN = re.compile(r'"first_seen"\s*:\s*"([^"]+)"')


def _read(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


#: The judge's UNKNOWN reasons that mean NOT TESTABLE on today's history, read from the ONE
#: table `judge_coverage.UNKNOWN_REASON_CLASS` owns (audit of PR #290: this module kept its own
#: set and the two organs disagreed in both directions). Every reason not classed `not_testable`
#: there -- `series_exception`, `no_series`, an unnamed or unlisted reason -- stays `unknown`:
#: a defect, never data scarcity, and never drain.
try:
    from judge_coverage import CONVERSION_HANDOFF, READMISSION_LOG, UNRUNNABLE_BANK
    from judge_coverage import NOT_TESTABLE_REASONS as NOT_TESTABLE_UNKNOWN
except ImportError:                                            # pragma: no cover - import context
    from research.judge_coverage import (  # type: ignore[no-redef]
        CONVERSION_HANDOFF,
        READMISSION_LOG,
        UNRUNNABLE_BANK,
    )
    from research.judge_coverage import (  # type: ignore[no-redef]
        NOT_TESTABLE_REASONS as NOT_TESTABLE_UNKNOWN,
    )


def classify(row: dict[str, Any]) -> str:
    """'ruled' (a real verdict), 'not_testable' (UNKNOWN for want of observations), 'unknown' (no
    terminal gate, any other cause) or 'not_run' (never computed)."""
    if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
        return "not_run"
    gate = str(row.get("terminal_gate") or "")
    if row.get("passed") is True or (gate and gate != "UNKNOWN"):
        return "ruled"
    if str(row.get("unknown_reason") or "") in NOT_TESTABLE_UNKNOWN:
        return "not_testable"
    return "unknown"


def _parked_cells(bank: Path | None = None) -> tuple[set[str], str]:
    """Cells the unrunnable bank holds with a NOT_TESTABLE reason, and where that came from."""
    p = UNRUNNABLE_BANK if bank is None else bank
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return set(), f"UNMEASURED: {p.name} unreadable ({type(exc).__name__})"
    if not isinstance(doc, dict):
        return set(), f"UNMEASURED: {p.name} is not a cell table"
    cells = {str(c) for c, r in doc.items()
             if isinstance(r, dict) and r.get("reason") in NOT_TESTABLE_UNKNOWN}
    return cells, f"{p.name}: {len(cells)} cell(s) parked not-testable"


def drain(now: datetime, path: Path | None = None,
          bank: Path | None = None) -> dict[str, Any]:
    """First rulings and rows by kind per window, streamed from the judge's own ledger.

    A cell counts as a FIRST ruling in a window when its earliest real verdict in the whole
    ledger lands inside it. The ledger is append-only in sweep order; a cell ruled before the
    window is remembered and never counted again, however many rows it gathers later.

    A NOT_TESTABLE reading is drain only when the bank actually holds that cell as not-testable
    (audit of PR #290): `judge_coverage` removes a cell from the backlog through the bank, so a
    ledger reading the bank never took is not drain. An unreadable bank counts no parking at
    all -- the drain is understated, never overstated, because an overstated drain reads as
    DRAINING and stops the judge gaining workers.
    """
    p = GATE_LEDGER if path is None else path
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p.name} absent: the drain is UNMEASURED"}
    banked, parking_basis = _parked_cells(bank)
    cuts = {w: (now - timedelta(hours=h)).isoformat(timespec="seconds")
            for w, h in WINDOWS_H.items()}
    earliest = min(cuts.values())
    ruled_before: set[str] = set()
    settled_before: set[str] = set()
    first: dict[str, int] = dict.fromkeys(cuts, 0)
    # FIRST SETTLED: a cell's first real ruling OR its first NOT_TESTABLE reading, counted once.
    # Both take a cell out of the backlog `judge_coverage` counts, so both are drain.
    settled: dict[str, int] = dict.fromkeys(cuts, 0)
    # PARKING, BY NAME: the part of `settled` that was a first NOT_TESTABLE reading, not a ruling.
    parked: dict[str, int] = dict.fromkeys(cuts, 0)
    rows: dict[str, dict[str, int]] = {w: {"ruled": 0, "not_testable": 0, "unknown": 0,
                                           "not_run": 0} for w in cuts}
    total = 0
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                total += 1
                m = _AT.search(line)
                at = m.group(1) if m else ""
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                kind = classify(row)
                cell = str(row.get("cell") or "")
                if at < earliest:
                    if kind == "ruled" and cell:
                        ruled_before.add(cell)
                    if cell and (kind == "ruled" or (kind == "not_testable"
                                                     and cell in banked)):
                        settled_before.add(cell)
                    continue
                for w, cut in cuts.items():
                    if at >= cut:
                        rows[w][kind] += 1
                if kind == "ruled" and cell and cell not in ruled_before:
                    ruled_before.add(cell)
                    for w, cut in cuts.items():
                        if at >= cut:
                            first[w] += 1
                if (kind == "ruled" or (kind == "not_testable" and cell in banked)) \
                        and cell and cell not in settled_before:
                    settled_before.add(cell)
                    for w, cut in cuts.items():
                        if at >= cut:
                            settled[w] += 1
                            if kind == "not_testable":
                                parked[w] += 1
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return {"status": "MEASURED", "rows_total": total, "first_rulings": first, "rows": rows,
            "parking_basis": parking_basis,
            "first_rulings_per_hour": {w: round(first[w] / WINDOWS_H[w], 3) for w in cuts},
            "first_settled": settled,
            "first_not_testable": parked,
            "first_not_testable_per_hour": {w: round(parked[w] / WINDOWS_H[w], 3) for w in cuts},
            "first_settled_per_hour": {w: round(settled[w] / WINDOWS_H[w], 3) for w in cuts}}


def inflow(now: datetime, path: Path | None = None,
           readmission_log: Path | None = None) -> dict[str, Any]:
    """Docket rows whose `first_seen` falls in each window -- the cells joining the queue.

    Streams the docket text for the stamp alone (the trading box's docket is over a million rows;
    decoding it whole is what `external_gauntlet.iter_json_array` exists to avoid)."""
    p = DOCKET if path is None else path
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p.name} absent: the inflow is UNMEASURED"}
    cuts = {w: (now - timedelta(hours=h)).isoformat(timespec="seconds")
            for w, h in WINDOWS_H.items()}
    counts = dict.fromkeys(cuts, 0)
    n = 0
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            carry = ""
            while True:
                chunk = fh.read(1 << 22)
                if not chunk:
                    break
                buf = carry + chunk
                # Cut before the LAST stamp so a stamp split across two reads is decoded whole;
                # with no stamp in the buffer, keep a tail long enough to hold a split one.
                cut_at = buf.rfind('"first_seen"')
                if cut_at <= 0:
                    cut_at = max(0, len(buf) - 96)
                head, carry = buf[:cut_at], buf[cut_at:]
                for m in _FIRST_SEEN.finditer(head):
                    n += 1
                    fs = _norm(m.group(1))
                    for w, cut in cuts.items():
                        if fs >= cut:
                            counts[w] += 1
            for m in _FIRST_SEEN.finditer(carry):
                n += 1
                fs = _norm(m.group(1))
                for w, cut in cuts.items():
                    if fs >= cut:
                        counts[w] += 1
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    readm = readmissions(now, readmission_log)
    out: dict[str, Any] = {"status": "MEASURED", "stamped_rows": n, "created": counts,
                           "created_per_hour": {w: round(counts[w] / WINDOWS_H[w], 3)
                                                for w in cuts},
                           "readmitted": readm}
    # A RE-ADMITTED CELL IS INFLOW: the bank returned it to the backlog this window, and the
    # outflow above already counted its first NOT_TESTABLE reading. Leaving it out would book
    # the parking as drain and never book the return.
    _rd = readm.get("readmitted") if readm.get("status") == "MEASURED" else None
    out["inflow_per_hour"] = {w: round((counts[w] + int((_rd or {}).get(w, 0))) / WINDOWS_H[w], 3)
                              for w in cuts}
    return out


#: The bank writes one log line on EVERY pass (zeros included) and runs hourly, so a newest line
#: older than this means the writer stopped and the zeros since are unknown, not zero.
READMISSION_LOG_STALE_H = 6.0


def readmissions(now: datetime, path: Path | None = None) -> dict[str, Any]:
    """Not-testable cells the bank returned to the backlog in each window
    (`judge_coverage.READMISSION_LOG`, one line per bank pass, zeros included).

    AN ABSENT OR STALE LOG IS UNMEASURED, NEVER ZERO (audit of PR #290, M1): a measured zero here
    understates inflow, which tips the burn-down toward DRAINING, which stops judging_throughput
    adding workers -- while up to 90 days of parked cells can return at once."""
    p = READMISSION_LOG if path is None else path
    cuts = {w: (now - timedelta(hours=h)).timestamp() for w, h in WINDOWS_H.items()}
    counts = dict.fromkeys(cuts, 0)
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p.name} absent: re-admissions are unknown"}
    newest: datetime | None = None
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                    at = datetime.fromisoformat(str(row["at"]).replace("Z", "+00:00"))
                    if at.tzinfo is None:
                        at = at.replace(tzinfo=UTC)
                    n = int(row.get("readmitted") or 0)
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
                newest = at if newest is None or at > newest else newest
                for w, cut in cuts.items():
                    if at.timestamp() >= cut:
                        counts[w] += n
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    age_h = None if newest is None else (now - newest).total_seconds() / 3600.0
    if age_h is None or age_h > READMISSION_LOG_STALE_H:
        return {"status": UNMEASURED,
                "why": (f"{p.name} has no readable line" if age_h is None else
                        f"{p.name} newest line is {age_h:.1f}h old (past "
                        f"{READMISSION_LOG_STALE_H:.0f}h): the bank stopped logging")}
    return {"status": "MEASURED", "readmitted": counts, "newest_at": newest.isoformat()}


def _norm(ts: str) -> str:
    """ISO stamps compare as strings only at one precision: trim to seconds, keep the offset."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC).isoformat(
            timespec="seconds")
    except ValueError:
        return ts


def backlog() -> dict[str, Any]:
    """The unjudged count, read from `JUDGE_COVERAGE.json`, which owns it. Never recomputed."""
    tot = _read(COVERAGE).get("totals")
    n = tot.get("unjudged_total") if isinstance(tot, dict) else None
    if not isinstance(n, int):
        return {"status": UNMEASURED,
                "why": f"{COVERAGE.name} carries no totals.unjudged_total: backlog UNMEASURED"}
    return {"status": "MEASURED", "unjudged": n, "source": COVERAGE.name}


def warm_side() -> dict[str, Any]:
    """What the warmer's last round did for the backlog, read from its own report."""
    doc = _read(WARM)
    rounds = doc.get("rounds") if isinstance(doc.get("rounds"), list) else []
    if not rounds:
        return {"status": UNMEASURED, "why": f"{WARM.name} absent or carries no round"}
    last = rounds[-1] if isinstance(rounds[-1], dict) else {}
    keys = ("never_judged", "never_judged_cold", "never_judged_warmed", "fanned_out",
            "equivalent_followers", "warmed", "failed", "hit_since_scan", "cells_per_min",
            "workers", "seconds", "held_for_gate_room")
    out: dict[str, Any] = {"status": "MEASURED", "at": doc.get("at"),
                           **{k: last.get(k, UNMEASURED) for k in keys}}
    cap = last.get("capacity") if isinstance(last.get("capacity"), dict) else {}
    out["idle_cores_at_start"] = cap.get("idle_cores", UNMEASURED)
    oc = last.get("order_census") if isinstance(last.get("order_census"), dict) else {}
    out["next_sweep_docket"] = oc.get("keep", UNMEASURED)
    out["next_sweep_never_judged"] = oc.get("keep_never_judged", UNMEASURED)
    return out


# ------------------------------------------------------------------ the sweep, taken apart
GATES_REPORT = DESK / "reports" / "universal_gates_external.json"
GAUNTLET_ORDER = DESK / "reports" / "GAUNTLET_ORDER.json"
_SCALARS = ("swept_at", "n_cells_advanced_beyond_economic_prior",
            "n_cells_deferred_build_budget", "n_cells_blocked_build_or_data", "workers")
_PREWARM_KEYS = ("submitted", "warmed", "hit", "failed", "unreached", "seconds")


def tail_scalars(path: Path, keys: tuple[str, ...] = _SCALARS,
                 chunk: int = 1 << 22) -> dict[str, str]:
    """The LAST value of each scalar `key` (and the `prewarm` block's counts) in a JSON file,
    streamed in chunks. The judge's report carries its per-cell verdict list FIRST and its census
    after it; on the trading box the list is a million rows, and decoding it whole to read a
    dozen numbers is the cost this avoids."""
    pats = {k: re.compile(r'"' + re.escape(k) + r'"\s*:\s*("([^"]*)"|[-0-9.eE+]+)') for k in keys}
    pre = re.compile(r'"prewarm"\s*:\s*\{([^{}]*)')
    out: dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            tail = ""
            while True:
                part = fh.read(chunk)
                if not part:
                    break
                buf = tail + part
                for k, p in pats.items():
                    for m in p.finditer(buf):
                        out[k] = m.group(2) if m.group(2) is not None else m.group(1)
                for m in pre.finditer(buf):
                    for pk in _PREWARM_KEYS:
                        mm = re.search(r'"' + pk + r'"\s*:\s*([-0-9.eE+]+)', m.group(1))
                        if mm:
                            out[f"prewarm.{pk}"] = mm.group(1)
                tail = buf[-4096:]
    except OSError:
        return {}
    return out


def _ts(v: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def sweep_anatomy() -> dict[str, Any]:
    """WHERE THE LAST SWEEP'S WALL CLOCK WENT, from the sealed judge's own two artifacts.

    `GAUNTLET_ORDER.json` is written when the sweep has ordered its docket and
    `universal_gates_external.json` when it has ruled, so their stamps bracket the sweep's build
    and gate phases; the report's `prewarm` block says how long the pool built and what it built.
    What is left is the loop that loads every cached cell plus the gate phase, per cell advanced.
    That per-cell figure is what `warm_gauntlet_cache.gate_room` sizes the warm set by, and the
    split says which stage binds: BUILD (cells deferred for the build budget) or GATE.
    """
    sc = tail_scalars(GATES_REPORT)
    order_at = _ts(_read(GAUNTLET_ORDER).get("at"))
    swept = _ts(sc.get("swept_at"))

    def _f(k: str) -> float | None:
        try:
            return float(sc[k])
        except (KeyError, ValueError):
            return None

    adv, pre_s = _f("n_cells_advanced_beyond_economic_prior"), _f("prewarm.seconds")
    if swept is None or order_at is None or swept <= order_at or not adv:
        return {"status": UNMEASURED,
                "why": "the last sweep's order/report pair is unreadable or out of step"}
    total = swept - order_at
    post = max(0.0, total - (pre_s or 0.0))
    deferred = _f("n_cells_deferred_build_budget")
    return {"status": "MEASURED", "swept_at": sc.get("swept_at"),
            "seconds_after_order": round(total, 1), "prewarm_seconds": pre_s,
            "post_build_seconds": round(post, 1), "cells_advanced": int(adv),
            "post_build_s_per_cell": round(post / adv, 5),
            "prewarm": {k: _f(f"prewarm.{k}") for k in _PREWARM_KEYS},
            "deferred_build_budget": deferred, "workers": _f("workers"),
            "binding_stage": ("BUILD" if deferred and deferred > 0 else "GATE"),
            "why": ("BUILD: cells were deferred for the build budget, so more warm cells mean "
                    "more verdicts; GATE: nothing was deferred, so the gate phase over the "
                    "cached docket is what the sweep's length is made of")}


def capacity(d: dict[str, Any], w: dict[str, Any], s: dict[str, Any]) -> dict[str, Any]:
    """The warm side's projected contribution per day, at its last measured rate.

    A PROJECTION, labelled as one: the warmer's last-round build rate held for a day, times the
    share of its builds that were first rulings. The measured drain beside it is what actually
    happened; the two together say whether the warm side is keeping up.
    """
    rate = w.get("cells_per_min")
    warmed, never = w.get("warmed"), w.get("never_judged_warmed")
    if not isinstance(rate, (int, float)) or not isinstance(warmed, int) or \
            not isinstance(never, int):
        return {"status": UNMEASURED, "why": "no measured warm round"}
    share = (never / warmed) if warmed else 0.0
    return {"status": "PROJECTED", "warm_builds_per_day": round(float(rate) * 1440.0),
            "never_judged_share_of_builds": round(share, 4),
            "first_rulings_per_day_from_warm_side": round(float(rate) * 1440.0 * share),
            "measured_first_rulings_per_day": (
                round(float(d["first_rulings_per_hour"]["24h"]) * 24.0, 1)
                if d.get("status") == "MEASURED" else UNMEASURED),
            "binding_stage": s.get("binding_stage", UNMEASURED)}


def awaiting_conversion(path: Path | None = None,
                        now: datetime | None = None) -> dict[str, Any]:
    """Parked cells handed to the converter and not yet back (`judge_coverage.CONVERSION_HANDOFF`).

    NO CELL ENDS UNTESTABLE (principal, 2026-10-13): a parked cell left the judge's backlog but is
    still owed a ruling once converted, so the backlog is never DRAINED while any wait here.
    """
    p = CONVERSION_HANDOFF if path is None else path
    doc = _read(p)
    if not isinstance(doc, dict) or not isinstance(doc.get("n"), int) or doc["n"] < 0:
        return {"status": UNMEASURED, "why": f"{p.name} is absent or unreadable"}
    # A handoff the coverage pass stopped rewriting is not today's count (audit of PR #290).
    gen = _ts(doc.get("generated_utc"))
    age_h = None if gen is None else ((now or datetime.now(tz=UTC)).timestamp() - gen) / 3600.0
    if age_h is None or age_h > READMISSION_LOG_STALE_H:
        return {"status": UNMEASURED,
                "why": (f"{p.name} is {'undated' if age_h is None else f'{age_h:.1f}h old'} "
                        f"(over {READMISSION_LOG_STALE_H:.0f}h): the coverage pass stopped "
                        "handing cells over")}
    return {"status": "MEASURED", "cells": doc["n"], "at": doc.get("generated_utc")}


def verdict(b: dict[str, Any], d: dict[str, Any], i: dict[str, Any],
            window: str = "7d", conv: dict[str, Any] | None = None) -> dict[str, Any]:
    """Net drain per day, days to zero (or GROWING) and the rate that would clear it."""
    if b.get("status") != "MEASURED" or d.get("status") != "MEASURED" \
            or i.get("status") != "MEASURED":
        why = "; ".join(str(x.get("why")) for x in (b, d, i) if x.get("status") != "MEASURED")
        return {"status": UNMEASURED, "why": why}
    # THE BACKLOG'S OWN OUTFLOW: first rulings plus first NOT_TESTABLE readings, because
    # `judge_coverage` takes both out of the count this is divided into. Older drains without
    # the field fall back to first rulings.
    # ONE UNIT ON BOTH SIDES (audit of PR #290): the outflow is SETTLED cells (rulings plus
    # parkings), so the "needed" rate and its multiple are settled cells too -- the old label said
    # first rulings over a settled divisor. The inflow is minted plus re-admitted cells.
    settled_rates = d.get("first_settled_per_hour")
    unit = "settled" if settled_rates else "first_rulings"
    out_h = float((settled_rates or d["first_rulings_per_hour"])[window])
    in_h = float((i.get("inflow_per_hour") or i["created_per_hour"])[window])
    n = int(b["unjudged"])
    net_day = round((out_h - in_h) * 24.0, 1)
    need_h = round(in_h + n / (TARGET_DAYS * 24.0), 1)
    doc: dict[str, Any] = {"window": window, "outflow_unit": unit,
                           "outflow_per_hour": out_h,
                           "first_settled_per_hour": out_h if settled_rates else None,
                           "first_rulings_per_hour": float(d["first_rulings_per_hour"][window]),
                           "first_not_testable_per_hour": (
                               (d.get("first_not_testable_per_hour") or {}).get(window)),
                           "created_per_hour": float(i["created_per_hour"][window]),
                           "inflow_per_hour": in_h, "net_per_day": net_day,
                           f"needed_{unit}_per_hour": need_h,
                           "needed_multiple_of_today": (round(need_h / out_h, 2) if out_h > 0
                                                        else None),
                           "target_days": TARGET_DAYS}
    readm = i.get("readmitted") if isinstance(i.get("readmitted"), dict) else {}
    if not isinstance(conv, dict):
        conv = {"status": UNMEASURED, "why": "not read"}
    doc["awaiting_conversion"] = conv.get("cells") if conv.get("status") == "MEASURED" else None
    if n == 0 and conv.get("status") != "MEASURED":
        doc.update(status=UNMEASURED, days_to_zero=None,
                   why=f"cells awaiting conversion unknown: {conv.get('why')}")
    elif n == 0 and int(conv.get("cells") or 0) > 0:
        doc.update(status="AWAITING_CONVERSION", days_to_zero=None,
                   why=(f"{conv.get('cells')} parked cell(s) are with the converter and still "
                        "owed a ruling; no cell ends untestable"))
    elif n == 0:
        doc.update(status="DRAINED", days_to_zero=0.0)
    elif net_day > 0 and readm.get("status") != "MEASURED":
        # The inflow above is a LOWER bound (re-admissions unknown), so "draining" is not shown.
        # GROWING on a lower bound stays GROWING; DRAINING on one is UNMEASURED.
        doc.update(status=UNMEASURED, days_to_zero=None,
                   why=f"inflow excludes re-admissions: {readm.get('why')}")
    elif net_day > 0:
        doc.update(status="DRAINING", days_to_zero=round(n / net_day, 1))
    else:
        doc.update(status="GROWING", days_to_zero=None,
                   why=(f"{out_h:.1f} {unit.replace('_', ' ')}/h against {in_h:.1f} new or "
                        f"re-admitted cells/h: the backlog grows {-net_day:.0f} cells a day "
                        "at this rate"))
    return doc


def build(now: datetime | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    b, d, i, w = backlog(), drain(t), inflow(t), warm_side()
    s = sweep_anatomy()
    c = awaiting_conversion(now=t)
    return {"at": t.isoformat(timespec="seconds"), "backlog": b, "drain": d, "inflow": i,
            "warm_side": w, "sweep": s, "capacity": capacity(d, w, s),
            "awaiting_conversion": c,
            "burn_down": verdict(b, d, i, "7d", c),
            "burn_down_24h": verdict(b, d, i, "24h", c),
            "rule": ("outflow = cells SETTLED for the first time in the window: a first real "
                     "verdict, or a first NOT_TESTABLE reading (judge_coverage."
                     "UNKNOWN_REASON_CLASS), each also published on its own; other UNKNOWN and "
                     "NOT_RUN rows are not settled and a re-judge is not a drain; inflow = docket "
                     "rows first seen in the window plus not-testable cells the bank re-admitted; "
                     "nothing here throttles a miner")}


def write(doc: dict[str, Any]) -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(f".json.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, OUT)
    return OUT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    bd = doc["burn_down"]
    print(f"judging burn-down: {bd.get('status')} backlog={doc['backlog'].get('unjudged')} "
          f"out/h={bd.get('outflow_per_hour')} ({bd.get('outflow_unit')}) "
          f"in/h={bd.get('inflow_per_hour')} "
          f"net/day={bd.get('net_per_day')} days_to_zero={bd.get('days_to_zero')} "
          f"needed/h={bd.get('needed_settled_per_hour', bd.get('needed_first_rulings_per_hour'))}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
