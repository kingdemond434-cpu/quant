#!/usr/bin/env python3
"""ALPHA REPLACEMENT RATE (L1.30) -- edges die on their own schedule; only the pipeline decides
whether the book dies with them.

THE NUMBER THAT ACTUALLY SETS LONG-RUN CAGR, and which this desk has never computed. Every edge
decays -- crowding, regime change, microstructure drift -- on a half-life measured in months, not
years. So terminal wealth is NOT set by how good today's sleeves are; it is set by whether
VALIDATED BIRTHS keep pace with DEATHS. A book earning 80% on three edges with a replacement rate
of 0.3 is on a countdown nobody is watching: it looks healthy every single day right up until the
last edge dies. A book earning 30% with a replacement rate above 1.0 compounds forever.

    replacement_rate = births / deaths   over a trailing window

  births  = edges that reached FORWARD-EVIDENCE status in the window (Stage-B entries /
            promotion-queue promotions) -- the only births that count, because a screen hit is
            not an edge (L1.6: screens have zero promotion authority).
  deaths  = graveyard kills + retirements + forward clocks that failed out, in the same window.

STATUSES:
  DYING             deaths > births -- the countdown is running. Fence FAILS.
  UNMEASURED-BIRTHS no dated promotion history exists, so births cannot be counted. Reported as
                    a defect, NEVER as DYING: "cannot count births" and "there are no births"
                    are different claims and only one is evidence.
  UNMEASURED        no birth/death records at all -- counts as zero (L1.28a), never as fine.
  BOOTSTRAPPING  no deaths yet AND no births yet: pre-Gate-0 state, honestly named.
  OK             births >= deaths.

DELIBERATELY NOT A KILL SWITCH. A low replacement rate never justifies loosening a validation
bar to manufacture births -- that converts a real countdown into a fake reprieve and is the
exact failure L1.25/L1.6 forbid. The correct response is upstream: more axes, more screens,
more forward slots filled (L1.25a).

    python scripts/check_replacement_rate.py [--window-days N] [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402
_DATE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)")


def _dates_in(text: str) -> list[datetime]:
    out = []
    for y, m, d in _DATE.findall(text):
        try:
            out.append(datetime(int(y), int(m), int(d), tzinfo=UTC))
        except ValueError:
            continue
    return out


def _count_graveyard_deaths(root: Path, since: datetime) -> tuple[int, int]:
    """(deaths_in_window, total_entries). Entries are '### <name> -- KILLED/RETIRED <date>'."""
    p = root / "docs/graveyard.md"
    if not p.exists():
        return 0, 0
    entries = [ln for ln in p.read_text("utf-8", errors="ignore").splitlines()
               if ln.startswith("### ")]
    n_win = 0
    for ln in entries:
        ds = _dates_in(ln)
        if ds and max(ds) >= since:
            n_win += 1
    return n_win, len(entries)


def _count_births(root: Path, since: datetime) -> tuple[int | None, int]:
    """(births_in_window | None if unmeasurable, live_forward_clocks).

    A BIRTH is an edge reaching forward-evidence status -- never a screen hit (L1.6).

    HONESTY NOTE, and this fence's own first-run defect: the promotion queue records CURRENT
    slot occupancy, not a DATED history of entries, so births are not derivable from it. The
    first draft read absent list-keys, got [], and reported births=0 -- a phantom-key read
    published as a measurement, which is exactly the class this desk has been burned by. An
    unmeasurable birth count returns None and the status becomes UNMEASURED-BIRTHS; it must
    NEVER print DYING, because "we cannot count births" and "there are no births" are different
    claims and only one of them is evidence. Closing this needs an append-only promotion history
    (rowed) -- until then the fence reports what it can and refuses what it cannot."""
    p = root / "data/promotion_queue.json"
    try:
        d = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None, 0
    slots = d.get("slots", {}) if isinstance(d.get("slots"), dict) else {}
    live = int(slots.get("occupied", 0) or 0)
    history = d.get("promotion_history")            # the append-only store, once it exists
    if not isinstance(history, list):
        return None, live
    births = 0
    for r in history:
        if not isinstance(r, dict):
            continue
        ds = _dates_in(str(r.get("promoted_at") or r.get("at") or ""))
        if ds and max(ds) >= since:
            births += 1
    return births, live


def build_report(root: Path | None = None, window_days: int = 90,
                 now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    since = now - timedelta(days=window_days)
    deaths, graveyard_total = _count_graveyard_deaths(root, since)
    births, live_clocks = _count_births(root, since)

    if births is None:
        # Cannot count births -> cannot claim the book is dying. Unmeasured ranks as a defect
        # (L1.28a) but never masquerades as a measured verdict.
        status = "UNMEASURED-BIRTHS"
    elif graveyard_total == 0 and live_clocks == 0:
        status = "UNMEASURED"
    elif births == 0 and deaths == 0:
        status = "BOOTSTRAPPING"
    elif deaths > births:
        status = "DYING"
    else:
        status = "OK"
    rate = (None if births is None else
            (births / deaths) if deaths else (float("inf") if births else 0.0))
    return {
        "generated": now.isoformat(),
        "law": "L1.30 -- terminal wealth is set by whether validated births keep pace with "
               "deaths, not by how good today's sleeves are",
        "status": status,
        "window_days": window_days,
        "births": births, "deaths": deaths,
        "replacement_rate": (None if rate is None or rate == float("inf")
                             else round(rate, 3)),
        "births_measured": births is not None,
        "live_forward_clocks": live_clocks,
        "graveyard_entries_total": graveyard_total,
        "detail": (
            (f"births UNCOUNTABLE (no dated promotion history) vs {deaths} death(s) in "
             f"{window_days}d; {live_clocks} live forward clock(s) occupied of 12"
             if births is None else
             f"{births} birth(s) vs {deaths} death(s) in {window_days}d; "
             f"{live_clocks} live forward clock(s)")),
        "next_action": (
            "raise BIRTHS upstream -- more axes screened, more forward slots filled, "
            "resurrection queue consumed (L1.25a). NEVER loosen a validation bar to "
            "manufacture births: that turns a real countdown into a fake reprieve"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-days", type=int, default=90)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(window_days=args.window_days)
    out = _ROOT / "data/replacement_rate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"replacement rate (L1.30): {rep['status']} -- {rep['detail']}\n-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "DYING" else 0


if __name__ == "__main__":
    sys.exit(main())
