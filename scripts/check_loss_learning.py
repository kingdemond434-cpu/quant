"""THE LOSS-LEARNING LOOP, MEASURED: do realised losses and missed trades become judged cells?

    python scripts/check_loss_learning.py            # write the report, exit 0
    python scripts/check_loss_learning.py --check    # write it, exit 1 when RED

WHY THIS EXISTS (2026-11-03). PRODUCER_YIELD measured both loss-lane producers DEAD for three
days -- `missed_trade_archaeologist` and `residual_queue`, 0 rows -- while the live book took a
-9.4R USDNOK loss and the gold_asia window missed about four days of trades in a floor pause.
Neither event became a cell. The two causes were filters, not clocks (both legs run hourly):
the archaeologist donated each non-fired (family, symbol, session) cell ONCE in its life and
parked every live loss whose sleeve wrote no `taken` decision row as UNMEASURED; the residual
queue built every `strategy_loss` item without a family and its own door refuses those.

THE FUNNEL, one stage per hop, each with its count in the window and its LAST NONZERO instant:

    losses_seen            live fills at or below -1R               (live ledger)
    missed_seen            qualified setups that did not trade, plus dug missed-move episodes
                                                                     (non_fired_setups.jsonl,
                                                                      MISSED_TRADES.json)
    tweak_cells_generated  rows the two loss seats donated            (data/intelligence/<seat>/)
    judged                 gate verdicts on a donated (family, symbol) after its donation
                                                                     (gate_verdict_ledger.jsonl)
    promoted               sleeves promoted on such a cell after its donation  (sleeves.json)
    replaced               promoted tweaks that BEAT their parent forward on the promoter's own
                           comparison (`vs_armed.margin_r`, else shadow_exp against the parent's,
                           by CHAMPION_MARGIN). This loop retires nothing: the promoter is the
                           only organ that moves capital, and its guards are untouched.

STATUS. A stage with no nonzero reading for STALE_DAYS (3) -- never-nonzero counts -- is RED
when work waited on it (its upstream moved after it last did), and QUIET when nothing reached
it (no loss to learn from is not a defect, and an alarm that fires on a good week is ignored
by the next). UNMEASURED when a stage's input is absent: absence is a verdict, never a clean
zero (L1.28a). The report is RED if any stage is, else UNMEASURED if any stage is, else GREEN.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "LOSS_LEARNING.json"

LIVE = DESK / "data" / "live_ledger.jsonl"
NON_FIRED = DESK / "data" / "non_fired_setups.jsonl"
MISSED = DESK / "reports" / "MISSED_TRADES.json"
INTEL_ROOTS = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")
SEATS: tuple[str, ...] = ("missed_trade_archaeologist", "residual_queue")
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SLEEVES = DESK / "data" / "sleeves.json"

UNMEASURED = "UNMEASURED"
STALE_DAYS = 3.0
WINDOW_DAYS = 3.0
ADVERSE_R = -1.0
#: The promoter's own margin (research/promoter.py CHAMPION_MARGIN); read from there when the
#: module imports, so the two can never disagree silently.
CHAMPION_MARGIN_FALLBACK = 0.02
#: The verdict ledger is ~400 MB; only its tail can hold verdicts on cells donated this week.
VERDICT_TAIL_BYTES = 64 * 1024 * 1024
STAGES: tuple[str, ...] = ("losses_seen", "missed_seen", "tweak_cells_generated", "judged",
                           "promoted", "replaced")


def _at(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _iso(t: datetime | None) -> str | None:
    return t.isoformat(timespec="seconds") if t else None


def _jsonl(path: Path, tail_bytes: int | None = None) -> list[dict[str, Any]] | None:
    """Rows, or None when the file is absent/unreadable (UNMEASURED, never empty)."""
    try:
        with path.open("rb") as fh:
            if tail_bytes is not None:
                size = fh.seek(0, os.SEEK_END)
                fh.seek(max(0, size - tail_bytes))
                if size > tail_bytes:
                    fh.readline()                      # drop the partial first line
            raw = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        try:
            r = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _margin() -> float:
    """CHAMPION_MARGIN as the promoter's source declares it. Parsed, not imported: importing the
    promoter pulls the whole gateway stack into a report leg."""
    try:
        src = (DESK / "research" / "promoter.py").read_text("utf-8")
        m = re.search(r"^CHAMPION_MARGIN\s*=\s*([0-9.]+)", src, re.M)
        return float(m.group(1)) if m else CHAMPION_MARGIN_FALLBACK
    except (OSError, ValueError):
        return CHAMPION_MARGIN_FALLBACK


def _stage(times: list[datetime] | None, now: datetime, why: str) -> dict[str, Any]:
    """One stage's reading. `times` is None when the stage's input is absent."""
    if times is None:
        return {"status": UNMEASURED, "n_window": UNMEASURED, "n_total": UNMEASURED,
                "last_nonzero_at": UNMEASURED, "why": why}
    cut = now - timedelta(days=WINDOW_DAYS)
    last = max(times) if times else None
    stale = last is None or (now - last) >= timedelta(days=STALE_DAYS)
    return {"status": "RED" if stale else "GREEN",
            "n_window": sum(1 for t in times if t >= cut), "n_total": len(times),
            "last_nonzero_at": _iso(last),
            "why": (f"no nonzero reading in {STALE_DAYS:g} day(s)" if stale else "moving")
            + f"; {why}"}


def donated_cells() -> tuple[list[dict[str, Any]] | None, str]:
    """Every row the loss seats donated: (family, symbol, at, parent). None when no seat
    directory exists on either root (the seats' output is UNREADABLE, not zero)."""
    found_dir = False
    out: list[dict[str, Any]] = []
    for root in INTEL_ROOTS:
        for seat in SEATS:
            d = root / seat
            if not d.is_dir():
                continue
            found_dir = True
            for f in sorted(glob.glob(str(d / "discoveries_*.json"))):
                doc = _json(Path(f))
                if not isinstance(doc, dict):
                    continue
                at = _at(doc.get("generated_at"))
                for r in doc.get("discoveries") or []:
                    if isinstance(r, dict) and at is not None:
                        out.append({"seat": seat, "at": at,
                                    "family": str(r.get("family") or ""),
                                    "symbol": str(r.get("symbol") or ""),
                                    "parent": (r.get("evidence") or {}).get("parent_sleeve")
                                    if isinstance(r.get("evidence"), dict) else None})
    if not found_dir:
        return None, "no loss-seat directory under data/intelligence on either root"
    return out, f"{len(out)} donated row(s) across {', '.join(SEATS)}"


#: Each flow stage's upstream. The two intake stages have none.
UPSTREAM: dict[str, tuple[str, ...]] = {
    "tweak_cells_generated": ("losses_seen", "missed_seen"),
    "judged": ("tweak_cells_generated",), "promoted": ("judged",), "replaced": ("promoted",)}


def gate_staleness(stages: dict[str, dict[str, Any]]) -> None:
    """A stale stage is RED only when work WAITED on it: an intake stage with no loss or miss in
    the window is QUIET (a loss-free week is not a learning failure), and a flow stage is RED
    when its upstream moved after this stage last did (or this stage never has). A stale flow
    stage whose upstream is itself quiet is QUIET. UNMEASURED is never rewritten."""
    for name in STAGES:
        st = stages[name]
        if st["status"] != "RED":
            continue
        ups = UPSTREAM.get(name)
        if not ups:
            st["status"] = "QUIET"
            continue
        own = _at(st.get("last_nonzero_at"))
        up_last = [t for u in ups if (t := _at(stages[u].get("last_nonzero_at"))) is not None]
        waiting = bool(up_last) and (own is None or max(up_last) > own)
        if not waiting:
            st["status"] = "QUIET"
        else:
            st["why"] += (f"; upstream moved at {_iso(max(up_last))} and this stage has not "
                          "since -- work is waiting")


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    stages: dict[str, dict[str, Any]] = {}

    live = _jsonl(LIVE)
    stages["losses_seen"] = _stage(
        None if live is None else
        [t for f in live if isinstance(f.get("r_multiple"), (int, float))
         and float(f["r_multiple"]) <= ADVERSE_R and (t := _at(f.get("time"))) is not None],
        now, f"live fills at or below {ADVERSE_R:g}R in {LIVE.name}")

    nf = _jsonl(NON_FIRED)
    missed_doc = _json(MISSED)
    if nf is None and not isinstance(missed_doc, dict):
        missed_times: list[datetime] | None = None
    else:
        missed_times = [t for r in (nf or []) if (t := _at(r.get("known_at"))) is not None]
        dug = missed_doc.get("dug") if isinstance(missed_doc, dict) else None
        for r in dug if isinstance(dug, list) else []:
            if isinstance(r, dict) and r.get("kind") == "missed_forward_move":
                t = _at(r.get("decision_time"))
                if t is not None:
                    missed_times.append(t)
    stages["missed_seen"] = _stage(missed_times, now,
                                   "non-fired setups plus dug missed-move episodes")

    cells, cells_why = donated_cells()
    stages["tweak_cells_generated"] = _stage(
        None if cells is None else [c["at"] for c in cells], now, cells_why)

    first_by_cell: dict[tuple[str, str], datetime] = {}
    for c in cells or []:
        k = (c["family"].lower(), c["symbol"].upper())
        if c["family"] and c["symbol"] and (k not in first_by_cell or c["at"] < first_by_cell[k]):
            first_by_cell[k] = c["at"]

    verdicts = _jsonl(VERDICTS, tail_bytes=VERDICT_TAIL_BYTES)
    if verdicts is None or cells is None:
        judged_times: list[datetime] | None = None
    else:
        judged_times = []
        for r in verdicts:
            k = (str(r.get("family") or "").lower(),
                 str(r.get("sym") or r.get("symbol") or "").upper())
            t = _at(r.get("at"))
            if t is not None and k in first_by_cell and t >= first_by_cell[k]:
                judged_times.append(t)
    stages["judged"] = _stage(judged_times, now,
                              "gate verdicts on a donated (family, symbol) after donation "
                              f"(last {VERDICT_TAIL_BYTES // 2**20} MB of the ledger)")

    sdoc = _json(SLEEVES)
    srows = (sdoc.get("sleeves") if isinstance(sdoc, dict) else sdoc) if sdoc else None
    margin = _margin()
    promoted_rows: list[dict[str, Any]] = []
    if isinstance(srows, list) and cells is not None:
        for r in srows:
            if not isinstance(r, dict):
                continue
            t = _at(r.get("promoted_at"))
            k = (str(r.get("family") or "").lower(), str(r.get("symbol") or "").upper())
            if t is not None and k in first_by_cell and t >= first_by_cell[k]:
                promoted_rows.append(r)
        stages["promoted"] = _stage([_at(r["promoted_at"]) for r in promoted_rows], now,  # type: ignore[misc]
                                    "sleeves promoted on a donated (family, symbol) after it")
        by_name = {str(r.get("name")): r for r in srows if isinstance(r, dict)}
        parents = {str(c["parent"]) for c in cells if c.get("parent")}
        replaced: list[datetime] = []
        for r in promoted_rows:
            vs = r.get("vs_armed") if isinstance(r.get("vs_armed"), dict) else None
            beat = None
            if vs and isinstance(vs.get("margin_r"), (int, float)):
                beat = float(vs["margin_r"]) > margin
            else:
                fam_sym = (str(r.get("family") or ""), str(r.get("symbol") or ""))
                pars = [by_name[p] for p in parents if p in by_name
                        and (str(by_name[p].get("family") or ""),
                             str(by_name[p].get("symbol") or "")) == fam_sym]
                pexp = [float(p["shadow_exp"]) for p in pars
                        if isinstance(p.get("shadow_exp"), (int, float))]
                if pexp and isinstance(r.get("shadow_exp"), (int, float)):
                    beat = float(r["shadow_exp"]) - max(pexp) > margin
            if beat:
                replaced.append(_at(r["promoted_at"]))  # type: ignore[arg-type]
        stages["replaced"] = _stage(replaced, now,
                                    f"promoted tweaks that beat their parent forward by "
                                    f"{margin:g}R (promoter CHAMPION_MARGIN)")
    else:
        why = ("sleeve registry absent" if not isinstance(srows, list)
               else "loss seats unreadable")
        stages["promoted"] = _stage(None, now, why)
        stages["replaced"] = _stage(None, now, why)

    gate_staleness(stages)
    states = {s["status"] for s in stages.values()}
    status = "RED" if "RED" in states else (UNMEASURED if UNMEASURED in states else "GREEN")
    return {
        "schema": "loss_learning/1",
        "generated_at": _iso(now),
        "status": status,
        "rule": (f"a stage zero for {STALE_DAYS:g} day(s) is RED when its upstream moved "
                 "after it (work waited), QUIET when nothing reached it; UNMEASURED when its "
                 "input is absent (never a clean zero)"),
        "window_days": WINDOW_DAYS,
        "producers": list(SEATS),
        "stages": {k: stages[k] for k in STAGES},
        "red_stages": [k for k in STAGES if stages[k]["status"] == "RED"],
        "unmeasured_stages": [k for k in STAGES if stages[k]["status"] == UNMEASURED],
        "replace_rule": ("a tweak replaces its parent only after beating it forward on the "
                         "promoter's comparison; this report measures that and moves nothing"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when the funnel is RED")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, OUT)
    print(f"loss learning: {doc['status']}")
    for k, s in doc["stages"].items():
        print(f"  {k:<22} {s['status']:<10} window={s['n_window']!s:>6} "
              f"last={s['last_nonzero_at']}")
    return 1 if (a.check and doc["status"] == "RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
