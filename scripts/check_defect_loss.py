#!/usr/bin/env python3
"""WHAT DEFECTS COST, IN E[log W]: the trading windows a wiring or venue defect prevented.

    python scripts/check_defect_loss.py [--days 30] [--now <iso>] [--out <json>]

Clock: hourly leg `defect_loss` (desks/mt5/research/hourly_cycle.py, meta department).
Artifact: desks/mt5/reports/DEFECT_LOSS.json. Consumer: the CRO pass's question Q5 ("what did
stale information, costs or defects cost?"), whose `defect_loss_in_elog` part had no organ.

WHAT IS COUNTED. A decision the gateway qualified and did not trade for an OPERATIONAL reason
(`missed_trade_archaeologist.OPERATIONAL_REASONS`: the release identity refused the venue, the
terminal or connection was down, margin, not armed). No dataset changes those decisions; they
were missed for want of a working desk. The gateway retries inside a window, so one defect
writes many rows: the unit here is the PREVENTED WINDOW, one per (sleeve, UTC date) on which
the sleeve has at least one operational refusal and NO taken decision. A date on which a retry
got through is not a loss and is counted apart as `recovered_windows`.

HOW IT IS PRICED. Each prevented window is charged the sleeve's own measured growth per trade:
the mean of log(1 + f * r) over that sleeve's realised live R multiples (the audited ledger
view), with f the sleeve's fraction in the allocator's current book (reports/pf_allocation.json
`book`), or the book's mean fraction when the sleeve has none, which is said in `fraction_basis`
(the unit `missed_growth` prices a refusal in). The sign is kept: a defect that blocked a sleeve
whose realised growth is negative shows as a negative loss, and nothing here calls that a
reason to keep a defect.

WHAT IS NOT INVENTED (L1.28a). A sleeve with fewer than MIN_N realised trades is UNPRICED and
named with its count, never priced at zero. An absent or unreadable input makes the status
UNMEASURED with the reason. `defect_loss_elog` is the sum over priced windows only, and
`unpriced_windows` says how many it leaves out, so the number is a floor on what was measured
and never a claim about the rest.

It sizes, gates and vetoes nothing; it reads three files and writes one report.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.ops.live_ledger_view import ledger_path  # noqa: E402

DECISIONS = DESK / "data" / "decision_ledger.jsonl"
LIVE = DESK / "data" / "live_ledger.jsonl"
ALLOC = DESK / "reports" / "pf_allocation.json"
OUT = DESK / "reports" / "DEFECT_LOSS.json"
#: The desk's own floor for pricing anything from a sample (`missed_growth.MIN_N`).
MIN_N = 10
WINDOW_DAYS = 30.0
MEASURED, PARTIAL, UNMEASURED = "MEASURED", "PARTIAL", "UNMEASURED"
#: Kept identical to `missed_trade_archaeologist.OPERATIONAL_REASONS` (a test fences the two):
#: importing that module here would pull the whole archaeologist into a five-second read.
OPERATIONAL_REASONS: tuple[str, ...] = ("release_identity", "venue", "VENUE_UNAVAILABLE",
                                        "terminal", "not armed", "connection", "margin")


def _at(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _jsonl(path: Path) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Every decodable object row, or None with the reason the file could not be read."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return None, f"{path.name} unreadable ({type(exc).__name__})"
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows, None


def reason_of(d: dict[str, Any]) -> str:
    """Why the decision did not trade, read in the archaeologist's own order (`setup_class`)."""
    return str(d.get("veto_reason") or d.get("reason") or d.get("outcome") or "")


def operational(reason: str) -> bool:
    r = reason.lower()
    return any(k.lower() in r for k in OPERATIONAL_REASONS)


def defect_key(d: dict[str, Any]) -> str:
    """The short name a window's defect is filed under: the veto reason, else the outcome."""
    return reason_of(d) or "unnamed"


def prevented_windows(decisions: list[dict[str, Any]], since: datetime | None,
                      now: datetime) -> tuple[list[dict[str, Any]], int]:
    """One row per (sleeve, UTC date) a defect kept dark, and the count of dates it only delayed.

    A decision stamped after `now` is not evidence and is skipped. A sleeve-date with any taken
    decision is `recovered`: the retry got through, so the window was not lost.
    """
    refused: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    traded: set[tuple[str, str]] = set()
    for d in decisions:
        t = _at(d.get("decided_at") or d.get("time"))
        sleeve = str(d.get("sleeve") or d.get("strategy_id") or "")
        if t is None or not sleeve or t > now or (since is not None and t < since):
            continue
        key = (sleeve, t.astimezone(UTC).date().isoformat())
        if d.get("taken") or str(d.get("outcome") or "").upper() == "EXECUTED":
            traded.add(key)
        elif operational(reason_of(d)):
            refused[key][defect_key(d)] += 1
    windows = []
    for (sleeve, day), reasons in sorted(refused.items()):
        if (sleeve, day) in traded:
            continue
        top = max(sorted(reasons), key=lambda k: reasons[k])
        windows.append({"sleeve": sleeve, "date": day, "defect": top,
                        "refusals": sum(reasons.values())})
    recovered = sum(1 for k in refused if k in traded)
    return windows, recovered


def sleeve_r(live: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Each sleeve's realised R multiples; a row whose R could not be reconstructed is left out."""
    out: dict[str, list[float]] = defaultdict(list)
    for row in live:
        r = row.get("r_multiple")
        sleeve = row.get("sleeve")
        if (isinstance(sleeve, str) and sleeve and isinstance(r, (int, float))
                and not isinstance(r, bool) and math.isfinite(float(r))
                and not row.get("r_unreconstructible")):
            out[sleeve].append(float(r))
    return out


def book_fractions(alloc: Any) -> dict[str, float]:
    book = alloc.get("book") if isinstance(alloc, dict) else None
    if not isinstance(book, dict):
        return {}
    return {str(k): float(v) for k, v in book.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(float(v)) and float(v) > 0.0}


def growth_per_trade(rs: list[float], f: float) -> float | None:
    """Mean log(1 + f r) over the sleeve's realised trades; None when any trade would have taken
    the account to zero at that fraction (the log is not a number there, and it is not priced)."""
    if not rs or f <= 0.0 or any(1.0 + f * r <= 0.0 for r in rs):
        return None
    return sum(math.log1p(f * r) for r in rs) / len(rs)


def measure(decisions: list[dict[str, Any]] | None, live: list[dict[str, Any]] | None,
            alloc: Any, *, now: datetime, days: float = WINDOW_DAYS,
            why: list[str] | None = None) -> dict[str, Any]:
    missing = list(why or [])
    fractions = book_fractions(alloc)
    if decisions is None or live is None or not fractions:
        if decisions is not None and live is not None and alloc is not None:
            missing.append("pf_allocation.json carries no positive book fraction")
        return {"at": now.isoformat(), "status": UNMEASURED, "defect_loss_elog": None,
                "why": "; ".join(missing) or "an input is absent"}
    since = now - timedelta(days=days)
    windows, recovered = prevented_windows(decisions, since, now)
    all_time, _ = prevented_windows(decisions, None, now)
    rs_by = sleeve_r(live)
    mean_f = sum(fractions.values()) / len(fractions)
    by_sleeve: dict[str, dict[str, Any]] = {}
    by_defect: dict[str, dict[str, Any]] = {}
    total, unpriced = 0.0, 0
    for w in windows:
        s = w["sleeve"]
        row = by_sleeve.get(s)
        if row is None:
            rs = rs_by.get(s, [])
            f = fractions.get(s)
            basis = "sleeve's own book fraction" if f is not None else "book mean fraction"
            f = mean_f if f is None else f
            g = growth_per_trade(rs, f) if len(rs) >= MIN_N else None
            row = by_sleeve[s] = {
                "prevented_windows": 0, "n_realised_trades": len(rs), "fraction": round(f, 6),
                "fraction_basis": basis,
                "mean_r": round(sum(rs) / len(rs), 5) if rs else None,
                "elog_per_trade": None if g is None else round(g, 8),
                "priced": g is not None, "loss_elog": 0.0 if g is not None else None,
                "why_unpriced": (None if g is not None else
                                 f"{len(rs)} realised trade(s); {MIN_N} are needed to price"
                                 if len(rs) < MIN_N else
                                 "a realised trade is ruin at this fraction; log undefined")}
        row["prevented_windows"] += 1
        line = by_defect.setdefault(w["defect"], {"prevented_windows": 0, "priced_windows": 0,
                                                  "loss_elog": 0.0, "refusals": 0})
        line["prevented_windows"] += 1
        line["refusals"] += w["refusals"]
        if row["priced"]:
            g = float(row["elog_per_trade"])
            row["loss_elog"] = round(float(row["loss_elog"]) + g, 8)
            line["priced_windows"] += 1
            line["loss_elog"] = round(line["loss_elog"] + g, 8)
            total += g
        else:
            unpriced += 1
    priced = len(windows) - unpriced
    status = (MEASURED if unpriced == 0 else PARTIAL if priced else UNMEASURED)
    return {
        "at": now.isoformat(), "status": status, "window_days": days,
        "defect_loss_elog": round(total, 8) if (priced or not windows) else None,
        "prevented_windows": len(windows), "priced_windows": priced,
        "unpriced_windows": unpriced, "recovered_windows": recovered,
        "prevented_windows_all_time": len(all_time),
        "by_defect": dict(sorted(by_defect.items(), key=lambda kv: -kv[1]["prevented_windows"])),
        "by_sleeve": dict(sorted(by_sleeve.items(),
                                 key=lambda kv: -kv[1]["prevented_windows"])),
        "unpriced_sleeves": sorted(s for s, v in by_sleeve.items() if not v["priced"]),
        "basis": ("prevented window = (sleeve, UTC date) with an operational refusal and no "
                  "taken decision; priced at the sleeve's realised mean log(1 + f r) at its "
                  "book fraction; the sum covers priced windows only and is signed"),
        "why": (None if status == MEASURED else
                f"{unpriced} of {len(windows)} prevented window(s) belong to sleeves with "
                f"fewer than {MIN_N} realised trades and are not priced"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--days", type=float, default=WINDOW_DAYS)
    ap.add_argument("--now", default=None)
    ap.add_argument("--decisions", type=Path, default=DECISIONS)
    ap.add_argument("--live", type=Path, default=LIVE)
    ap.add_argument("--alloc", type=Path, default=ALLOC)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    now = _at(a.now) or datetime.now(UTC)
    why: list[str] = []
    decisions, w1 = _jsonl(a.decisions)
    live, w2 = _jsonl(ledger_path(a.live))
    try:
        alloc = json.loads(a.alloc.read_text(encoding="utf-8"))
        w3 = None
    except Exception as exc:
        alloc, w3 = None, f"{a.alloc.name} unreadable ({type(exc).__name__})"
    why.extend(w for w in (w1, w2, w3) if w)
    doc = measure(decisions, live, alloc, now=now, days=a.days, why=why)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(a.out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(a.out)
    print(json.dumps({k: doc.get(k) for k in ("status", "defect_loss_elog", "prevented_windows",
                                              "priced_windows", "unpriced_windows", "why")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
