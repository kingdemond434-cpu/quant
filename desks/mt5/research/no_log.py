"""THE NO-LOG -- what did the desk DECLINE this week, and why.

WHY THIS ORGAN EXISTS, in one measured outage. Between 2026-09-14 and 2026-09-15 the gateway
wrote `RELEASE IDENTITY refuses NEW risk` on EVERY pass -- 1,780 times. The refusal was correct,
it named its own cause (two `.ps1` paths a session had committed without re-sealing), and it was
written to a file. Nothing read it. For that whole period gold logged `bracket NOT placed` and
not one of the 444 forex signals the families produced could reach the venue. The desk was not
broken and it was not mis-designed: it was REFUSING, clearly and in writing, and no organ's job
was to notice that a refusal had stopped being a decision and become an outage.

THE DISTINCTION THIS FILE MEASURES, because it is the whole point:

  A DECISION is a refusal that LIFTS. `no signal on this bar` is the system working -- it fires
  on the next bar that qualifies. Counting those is noise.

  An OUTAGE is a refusal that NEVER lifts. The same reason, unbroken, across every pass for
  hours or days, on a path that blocks NEW RISK. That is not the desk declining an opportunity,
  it is the desk having stopped, and the only thing separating the two in the log is whether the
  reason ever changed.

So the ledger keys on the refusal's REASON CLASS (SHAs, symbols, counts and timestamps stripped),
and the verdict is driven by CONTINUITY, not by volume. A loud refusal that lifts every bar is
healthy. A quiet one that has held since Tuesday is the thing that costs a week of trading.

AND IT MUST NOT BECOME THE FILE NOBODY READS. That failure mode is exactly what it was built to
catch, so it does not merely publish: `proposals()` converts every OUTAGE-class row into a CEO
proposal carrying its own experiment and falsifier, and `frontier_ceo` folds them into the daily
docket where a decision is REQUIRED. A refusal that survives a week becomes an agenda item.

    python desks/mt5/research/no_log.py [--days 7] [--apply]

Artifact: desks/mt5/reports/NO_LOG.json
"""
from __future__ import annotations

import argparse
import json
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

GATEWAY_LOG = DESK / "logs" / "gateway.log"
E8_EXEC = DESK / "reports" / "E8_EXEC.json"
OUT = DESK / "reports" / "NO_LOG.json"

#: How long one reason must hold UNBROKEN before a refusal stops being a decision. Six hours is
#: six H1 bars: long enough that an ordinary quiet stretch does not trip it, short enough that a
#: fence stuck overnight is named the next morning rather than the next week.
OUTAGE_HOURS = 6.0

#: Reason classes that block NEW RISK when they hold. A refusal that only declines ONE sleeve is
#: a decision however long it lasts; a refusal that closes the whole venue path is an outage the
#: moment it stops lifting. The distinction is which of these two lists it lands in.
BLOCKS_NEW_RISK = (
    "release identity refuses new risk",
    "bracket not placed",
    "not armed",
    "guard stood down",
    "daily floor",
    "trade_allowed false",
    "terminal unreachable",
)

#: Refusals that are the system WORKING. Recorded and counted -- never promoted to an outage,
#: because a strategy that declines a bar is a strategy, not a fault.
HEALTHY = (
    "no signal on this bar",
    "no signal bar due",
    "sleeves net to flat",
    "already_open",
    "no_signal",
)

_TS = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d|Z)?)\s+(.*)$")


def _normalise(msg: str) -> str:
    """A refusal's REASON CLASS: the same fault worded for two different sleeves is one row.

    Everything that varies pass to pass is erased -- hex SHAs, bracketed sleeve names, digits,
    quoted paths and list bodies -- because the question this file answers is "has the reason
    changed", and a reason that only differs by which symbol it declined has not changed.
    """
    s = msg.strip()
    s = re.sub(r"^\[[^\]]+\]\s*", "", s)               # [gold_london_am] ...
    s = re.sub(r"\b[0-9a-f]{7,40}\b", "<sha>", s)      # commit SHAs
    s = re.sub(r"\[[^\]]*\]", "<list>", s)             # ['a.ps1', 'b.ps1']
    s = re.sub(r"'[^']*'", "<q>", s)                   # quoted names
    s = re.sub(r"[-+]?\d[\d,._]*", "<n>", s)           # every number
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s[:180]


def _is_refusal(msg: str) -> bool:
    low = msg.lower()
    return any(k in low for k in (
        "refuses", "refused", "not placed", "skipped", "withheld", "declin",
        "cannot", "unavailable", "blocked", "stood down", "no signal", "net to flat",
        "not_listed", "unmeasured",
    ))


def _classify(reason: str) -> str:
    low = reason.lower()
    if any(k in low for k in HEALTHY):
        return "healthy"
    if any(k in low for k in BLOCKS_NEW_RISK):
        return "blocks_new_risk"
    return "narrows_book"


def scan_gateway(days: float = 7.0, path: Path = GATEWAY_LOG) -> dict[str, dict[str, Any]]:
    """Every refusal the gateway wrote in the window, grouped by reason class."""
    if not path.exists():
        return {}
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    rows: dict[str, dict[str, Any]] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    for ln in text.splitlines():
        m = _TS.match(ln)
        if not m:
            continue
        raw_ts, msg = m.group(1), m.group(2)
        if not _is_refusal(msg):
            continue
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts < cutoff:
            continue
        key = _normalise(msg)
        r = rows.get(key)
        if r is None:
            rows[key] = {"reason": key, "n": 1, "first": ts, "last": ts,
                         "example": msg[:240], "source": "gateway"}
        else:
            r["n"] += 1
            if ts < r["first"]:
                r["first"] = ts
            if ts > r["last"]:
                r["last"] = ts
    return rows


def scan_e8(path: Path = E8_EXEC) -> dict[str, dict[str, Any]]:
    """The prop lane's refusals, which live in an artifact rather than a log.

    E8's executor published `NOT_LISTED` for eight sleeves on every pass for days -- a third of
    the book, unable to fill, stated plainly in JSON. It is included here for the same reason the
    gateway log is: the refusal was never the problem.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    try:
        ts = datetime.fromisoformat(str(doc.get("at")))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        ts = datetime.now(tz=UTC)
    rows: dict[str, dict[str, Any]] = {}
    for s in doc.get("sleeves") or []:
        status = str(s.get("status") or "")
        if status in ("OK", "SENT", "WOULD_SEND"):
            continue
        key = _normalise(f"e8 {status}: {s.get('why') or ''}")
        r = rows.get(key)
        if r is None:
            example = f"E8 {status} {s.get('symbol')} {s.get('family')}"
            rows[key] = {"reason": key, "n": 1, "first": ts, "last": ts,
                         "example": example[:240], "source": "e8"}
        else:
            r["n"] += 1
    return rows


def review(days: float = 7.0) -> dict[str, Any]:
    """The week's refusals, ranked by how long each one has held UNBROKEN."""
    now = datetime.now(tz=UTC)
    rows = scan_gateway(days)
    for k, v in scan_e8().items():
        rows.setdefault(k, v)
    out: list[dict[str, Any]] = []
    for r in rows.values():
        held_h = (r["last"] - r["first"]).total_seconds() / 3600.0
        silent_h = (now - r["last"]).total_seconds() / 3600.0
        kind = _classify(r["reason"])
        # AN OUTAGE IS A REFUSAL THAT NEVER LIFTED AND IS STILL LIVE. `silent_h` is what
        # separates "this held for nine hours on Tuesday and cleared" from "this has held for
        # nine hours and the last pass still said it".
        outage = bool(kind == "blocks_new_risk" and held_h >= OUTAGE_HOURS and silent_h <= 1.0)
        out.append({
            "reason": r["reason"], "kind": kind, "source": r["source"],
            "n": r["n"],
            "first_utc": r["first"].isoformat(timespec="seconds"),
            "last_utc": r["last"].isoformat(timespec="seconds"),
            "held_hours": round(held_h, 2),
            "silent_hours": round(silent_h, 2),
            "verdict": "OUTAGE" if outage else ("STANDING" if held_h >= OUTAGE_HOURS else "LIFTS"),
            "example": r["example"],
        })
    out.sort(key=lambda d: (d["verdict"] != "OUTAGE", d["verdict"] != "STANDING",
                            -d["held_hours"], -d["n"]))
    return {
        "at": now.isoformat(timespec="seconds"),
        "window_days": days,
        "outage_hours_threshold": OUTAGE_HOURS,
        "n_reason_classes": len(out),
        "n_refusals": sum(d["n"] for d in out),
        "n_outage": sum(1 for d in out if d["verdict"] == "OUTAGE"),
        "n_standing": sum(1 for d in out if d["verdict"] == "STANDING"),
        "n_healthy": sum(1 for d in out if d["kind"] == "healthy"),
        "rows": out,
        "rule": (
            "A refusal that LIFTS is a decision and is counted, never escalated. A refusal whose "
            "reason has held unbroken for >= OUTAGE_HOURS on a path that blocks NEW RISK, and "
            "which the most recent pass still wrote, is an OUTAGE: the desk has stopped rather "
            "than declined. Volume is not the signal -- continuity is."),
    }


def proposals(days: float = 7.0) -> list[dict[str, Any]]:
    """Every OUTAGE becomes a CEO agenda item, with its own falsifier.

    This is the half that keeps the NO-log from becoming the thing it was built to catch.
    """
    doc = review(days)
    out = []
    for r in doc["rows"]:
        if r["verdict"] != "OUTAGE":
            continue
        ident = re.sub(r"[^a-z0-9]+", "_", r["reason"])[:44].strip("_")
        out.append({
            "id": f"no_log.outage.{ident}",
            "kind": "refusal_outage",
            "cost": "low",
            "claim": (f"The desk has been refusing NEW RISK for {r['held_hours']:.1f}h with one "
                      f"unchanging reason ({r['n']} passes): {r['example']}"),
            "experiment": ("Clear the named cause, then confirm the next gateway pass writes no "
                           "line of this reason class and that new risk reaches the venue."),
            "refuted_if": ("The reason class reappears on the following pass, meaning the cause "
                           "diagnosed was not the cause acting."),
            "source": r["source"],
            "held_hours": r["held_hours"],
        })
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=float, default=7.0, help="review window (default 7)")
    ap.add_argument("--apply", action="store_true", help="write the artifact")
    a = ap.parse_args(argv)
    doc = review(a.days)
    print(f"NO-LOG {doc['at'][:10]}: {doc['n_refusals']} refusal(s) in "
          f"{doc['n_reason_classes']} reason class(es) over {a.days:g}d")
    print(f"  {doc['n_outage']} OUTAGE | {doc['n_standing']} standing | "
          f"{doc['n_healthy']} healthy")
    for r in doc["rows"][:12]:
        print(f"  {r['verdict']:8} {r['held_hours']:7.1f}h x{r['n']:<6} {r['kind']:15} "
              f"{r['example'][:70]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
