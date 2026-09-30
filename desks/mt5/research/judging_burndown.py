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
UNMEASURED with its reason, never a zero (L1.28a).

Clock: leg `judging_burndown` in `research/hourly_cycle.py` (department validate). It only reads.

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


def classify(row: dict[str, Any]) -> str:
    """'ruled' (a real verdict), 'unknown' (no terminal gate) or 'not_run' (never computed)."""
    if str(row.get("downstream_status") or "").startswith(NOT_JUDGED_PREFIX):
        return "not_run"
    gate = str(row.get("terminal_gate") or "")
    if row.get("passed") is True or (gate and gate != "UNKNOWN"):
        return "ruled"
    return "unknown"


def drain(now: datetime, path: Path | None = None) -> dict[str, Any]:
    """First rulings and rows by kind per window, streamed from the judge's own ledger.

    A cell counts as a FIRST ruling in a window when its earliest real verdict in the whole
    ledger lands inside it. The ledger is append-only in sweep order; a cell ruled before the
    window is remembered and never counted again, however many rows it gathers later.
    """
    p = GATE_LEDGER if path is None else path
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p.name} absent: the drain is UNMEASURED"}
    cuts = {w: (now - timedelta(hours=h)).isoformat(timespec="seconds")
            for w, h in WINDOWS_H.items()}
    earliest = min(cuts.values())
    ruled_before: set[str] = set()
    first: dict[str, int] = dict.fromkeys(cuts, 0)
    rows: dict[str, dict[str, int]] = {w: {"ruled": 0, "unknown": 0, "not_run": 0} for w in cuts}
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
                    continue
                for w, cut in cuts.items():
                    if at >= cut:
                        rows[w][kind] += 1
                if kind == "ruled" and cell and cell not in ruled_before:
                    ruled_before.add(cell)
                    for w, cut in cuts.items():
                        if at >= cut:
                            first[w] += 1
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return {"status": "MEASURED", "rows_total": total, "first_rulings": first, "rows": rows,
            "first_rulings_per_hour": {w: round(first[w] / WINDOWS_H[w], 3) for w in cuts}}


def inflow(now: datetime, path: Path | None = None) -> dict[str, Any]:
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
    return {"status": "MEASURED", "stamped_rows": n, "created": counts,
            "created_per_hour": {w: round(counts[w] / WINDOWS_H[w], 3) for w in cuts}}


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
            "equivalent_followers", "warmed", "failed", "cells_per_min", "workers", "seconds")
    return {"status": "MEASURED", "at": doc.get("at"),
            **{k: last.get(k, UNMEASURED) for k in keys}}


def verdict(b: dict[str, Any], d: dict[str, Any], i: dict[str, Any],
            window: str = "7d") -> dict[str, Any]:
    """Net drain per day, days to zero (or GROWING) and the rate that would clear it."""
    if b.get("status") != "MEASURED" or d.get("status") != "MEASURED" \
            or i.get("status") != "MEASURED":
        why = "; ".join(str(x.get("why")) for x in (b, d, i) if x.get("status") != "MEASURED")
        return {"status": UNMEASURED, "why": why}
    out_h = float(d["first_rulings_per_hour"][window])
    in_h = float(i["created_per_hour"][window])
    n = int(b["unjudged"])
    net_day = round((out_h - in_h) * 24.0, 1)
    need_h = round(in_h + n / (TARGET_DAYS * 24.0), 1)
    doc: dict[str, Any] = {"window": window, "first_rulings_per_hour": out_h,
                           "created_per_hour": in_h, "net_per_day": net_day,
                           "needed_first_rulings_per_hour": need_h,
                           "needed_multiple_of_today": (round(need_h / out_h, 2) if out_h > 0
                                                        else None),
                           "target_days": TARGET_DAYS}
    if n == 0:
        doc.update(status="DRAINED", days_to_zero=0.0)
    elif net_day > 0:
        doc.update(status="DRAINING", days_to_zero=round(n / net_day, 1))
    else:
        doc.update(status="GROWING", days_to_zero=None,
                   why=(f"{out_h:.1f} first rulings/h against {in_h:.1f} new cells/h: the "
                        f"backlog grows {-net_day:.0f} cells a day at this rate"))
    return doc


def build(now: datetime | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    b, d, i, w = backlog(), drain(t), inflow(t), warm_side()
    return {"at": t.isoformat(timespec="seconds"), "backlog": b, "drain": d, "inflow": i,
            "warm_side": w, "burn_down": verdict(b, d, i, "7d"),
            "burn_down_24h": verdict(b, d, i, "24h"),
            "rule": ("drain = cells whose FIRST real verdict landed in the window (UNKNOWN and "
                     "NOT_RUN rows are not rulings; a re-judge is not a drain); inflow = docket "
                     "rows first seen in the window; nothing here throttles a miner")}


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
          f"out/h={bd.get('first_rulings_per_hour')} in/h={bd.get('created_per_hour')} "
          f"net/day={bd.get('net_per_day')} days_to_zero={bd.get('days_to_zero')} "
          f"needed/h={bd.get('needed_first_rulings_per_hour')}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
