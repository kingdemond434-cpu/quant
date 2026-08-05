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
  UNMEASURED-BIRTHS births cannot be counted DECISIVELY. Two ways in: no dated promotion history
                    exists at all, or the dated count is a lower bound (undated rows for clocks
                    already running when the record opened) that sits BELOW deaths and could
                    therefore flip the verdict. Reported as a defect, NEVER as DYING: "cannot
                    count births" and "there are no births" are different claims and only one is
                    evidence. A lower bound at or above deaths needs no such care -- OK stands.
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


def _graveyard(root: Path, since: datetime) -> tuple[int, int, list[str]]:
    """(deaths_in_window, total_entries, windowed_entry_lines).

    Entries are '### <name> -- KILLED/RETIRED <date>'. The lines come back so that a forward
    clock retired in the same window can be deduped against its own graveyard entry rather than
    counted twice.
    """
    p = root / "docs/graveyard.md"
    if not p.exists():
        return 0, 0, []
    entries = [ln for ln in p.read_text("utf-8", errors="ignore").splitlines()
               if ln.startswith("### ")]
    in_win = []
    for ln in entries:
        ds = _dates_in(ln)
        if ds and max(ds) >= since:
            in_win.append(ln)
    return len(in_win), len(entries), in_win


def _history(root: Path) -> tuple[list[dict[str, Any]] | None, int]:
    """(promotion history | None when it has never been written, live_forward_clocks)."""
    p = root / "data/promotion_queue.json"
    try:
        d = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None, 0
    slots = d.get("slots", {}) if isinstance(d.get("slots"), dict) else {}
    live = int(slots.get("occupied", 0) or 0)
    history = d.get("promotion_history")            # the append-only store (libs.research.
    if not isinstance(history, list):               # promotion_history, written by
        return None, live                           # scripts/run_promotion_queue.py)
    return [r for r in history if isinstance(r, dict)], live


def _count_births(history: list[dict[str, Any]], since: datetime) -> tuple[int, int]:
    """(dated births in window, undated rows).

    A BIRTH is an edge reaching forward-evidence status -- never a screen hit (L1.6).

    UNDATED ROWS ARE NOT ZERO-DATED ROWS. A clock already running when the history was first
    written carries no derivable start, so `promoted_at` is None and it is excluded here. That
    makes the count a LOWER BOUND, and the caller is handed `undated` so it can refuse to
    publish DYING on a bound that the undated rows could flip. Treating an undated row as
    "born now" would be the phantom-birth bug in the complacent direction; treating the
    resulting shortfall as evidence of death would be the same bug pointed the other way.
    """
    births, undated = 0, 0
    for r in history:
        raw = str(r.get("promoted_at") or r.get("at") or "")
        ds = _dates_in(raw)
        if not ds:
            undated += 1
            continue
        if max(ds) >= since:
            births += 1
    return births, undated


def _count_retirements(history: list[dict[str, Any]], since: datetime,
                       graveyard_lines: list[str]) -> int:
    """Forward clocks retired in the window and NOT already counted as a graveyard entry.

    Deaths are 'graveyard kills + retirements + forward clocks that failed out'. Counting the
    graveyard alone understates deaths, which OVERSTATES the replacement rate -- the complacent
    direction, and the one this fence exists to prevent. Deduped by name against the windowed
    graveyard lines so a clock that was both retired and graveyarded dies once.
    """
    n = 0
    for r in history:
        ds = _dates_in(str(r.get("retired_at") or ""))
        if not ds or max(ds) < since:
            continue
        edge = str(r.get("edge", "")).strip()
        if edge and any(edge in ln for ln in graveyard_lines):
            continue
        n += 1
    return n


def build_report(root: Path | None = None, window_days: int = 90,
                 now: datetime | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    since = now - timedelta(days=window_days)
    graveyard_deaths, graveyard_total, graveyard_lines = _graveyard(root, since)
    history, live_clocks = _history(root)

    births: int | None
    undated = 0
    if history is None:
        births, deaths, retired = None, graveyard_deaths, 0
    else:
        births, undated = _count_births(history, since)
        retired = _count_retirements(history, since, graveyard_lines)
        deaths = graveyard_deaths + retired

    if births is None:
        # Cannot count births -> cannot claim the book is dying. Unmeasured ranks as a defect
        # (L1.28a) but never masquerades as a measured verdict.
        status = "UNMEASURED-BIRTHS"
    elif births < deaths and undated:
        # THE BOUND COULD FLIP THE VERDICT, so the verdict is not established. `births` here is a
        # LOWER bound (undated rows are real clocks with unknown start dates), and a lower bound
        # below `deaths` is consistent with both DYING and OK. Publishing DYING off it would be
        # the same error as the phantom-key births=0 this fence was rebuilt to stop, pointed the
        # other way -- and "the book is dying" is not a claim to make on an incomplete count.
        # When births >= deaths the bound already clears the bar and OK stands regardless.
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
        # A count that excludes undated rows is a FLOOR, not the number. Published as its own
        # field so no consumer has to infer completeness from a bare integer (L1.28a).
        "births_are_lower_bound": bool(undated),
        "births_undated": undated,
        "deaths_graveyard": graveyard_deaths,
        "deaths_retired_clocks": retired,
        "live_forward_clocks": live_clocks,
        "graveyard_entries_total": graveyard_total,
        "detail": (
            f"births UNCOUNTABLE (no dated promotion history) vs {deaths} death(s) in "
             f"{window_days}d; {live_clocks} live forward clock(s) occupied of 12"
             if births is None else
             f"{'>=' if undated else ''}{births} birth(s) vs {deaths} death(s) "
             f"({graveyard_deaths} graveyard + {retired} retired clock(s)) in {window_days}d; "
             f"{live_clocks} live forward clock(s)"
             + (f"; {undated} history row(s) undated (clocks already running when the record "
                f"opened) -> births is a FLOOR" if undated else "")),
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
