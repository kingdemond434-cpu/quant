"""ORDER-SENSITIVE DECAY VERDICTS on every LIVE and forward-clock sleeve (R0312, SARES archaeology).

WHAT WAS MISSING. `libs/research/order_sensitive_decay.py` is implemented and tested -- the exact
Irwin-Hall CDF, Edgington's mean-p, the R0467 null band that makes STABLE reachable -- and NOTHING
CALLED IT. Every statistic the desk applies to a sleeve's realised record (n, exp_r, forward t,
DSR, the e-process) is invariant to the ORDER of the trades: shuffle the ledger and none of them
moves. "The first half carried it and the second half is dead" and "it earned evenly" are the
same distribution and completely different edges. This leg is the order-sensitive half, run on
the records the desk already keeps, every hour.

THE SPLIT IS PRE-REGISTERED, IN CODE, AND THE SAME FOR EVERY SLEEVE. A published exploit of the
mean-p metric improves it by four orders of magnitude by deleting a losing sub-period; choosing
the cut per sleeve after seeing its record is the same exploit with better manners. So:

  * the record is the sleeve's realised R series in trade order (oldest first, by the row's own
    time stamp, ties kept in file order);
  * it is cut into SUB_PERIODS = 4 EQUAL-COUNT blocks BY TRADE INDEX -- block i holds trades
    [round(i*n/4), round((i+1)*n/4)) -- decided by n alone, never by the values;
  * each block gets a genuine one-sided p-value (Student t, H1: mean R > 0), and
    `order_sensitive_decay.decay_verdict` compares the early half of the blocks against the late
    half at its own frozen `_SPLIT` (0.5), with its own frozen null band;
  * fewer than MIN_TRADES_PER_PERIOD trades per block (n < 20, the same n the decay monitor and
    the promoter require before any verdict) is UNMEASURED_TOO_FEW_TRADES, by name. Too few
    trades is never a clean verdict (L1.28a).

WHICH RECORD. A LIVE roster row (`data/sleeves.json`, status LIVE) is judged on its live deals
(the audited live ledger the decay monitor reads, every closed deal tagged with the sleeve, with
the same unreconstructible-R exclusions). A forward clock (`reports/shadow/*_state.json`, every
row that is not KILL) is judged on the FORWARD-phase rows of its own ledger -- the historical
rows predate pre-registration and were visible while the cell was being selected, so they are
the in-sample record, not the decay evidence.

THE FORWARD BOUNDARY IS THE CLOCK'S OWN, ALWAYS (audit of 61b2e2408, look-ahead). A row is
forward evidence for clock K only when its entry is at or after K's OWN `forward_start` plus
K's `broker_offset_h` -- the exact boundary `shadow_forward` cuts at (bar stamps are on the
broker clock, `forward_start` is true UTC). The row's `phase` tag is NOT enough on its own: it
was set against whichever clock last wrote the file, and a ledger written before phases existed
has no tag at all. So the boundary filter runs on every row of every ledger, tagged or not, and
stays on after per-key ledgers land; a tagged row must ALSO say `forward`. A clock with no
`forward_start` has no forward record yet: UNMEASURED_NO_FORWARD_START.

A LEDGER ANOTHER CLOCK MAPS TO IS NO CLOCK'S SERIES. `shadow_forward` named ledgers by symbol,
family and window only, so every parameterisation of a cell (`#rr=...`, `@M5`, `.SHORT`) and its
base key wrote ONE file and the last clock replayed owned it. Measured by the audit: the base
`XAUUSD.asia` (forward_start 10-01) was judged DECAYING n=40 on a variant's 40 "forward" rows,
every one of which predates the base's own forward_start. A ledger that more than one clock key
(dead or alive -- a killed clock's pass still wrote the file) maps to is
UNMEASURED_SHARED_LEDGER, named with its co-tenants. Each clock reads its OWN ledger through
`libs/research/forward_ledger.py` (the per-key file, or the base key's `#own` file once its legacy
name is frozen). A clock whose ledger cannot be found is UNMEASURED_NO_LEDGER with the path it
looked for.

WHAT THIS IS FOR, AND WHAT IT IS NOT. A demote/shrink INPUT, nothing more. It changes no size,
opens or closes no door, moves no gate and touches no roster. `decay_input(key)` is the reader
an allocator can call later; the sizing hook itself is owned by the Max-growth thread and is
stated as NOT_WIRED in the artifact so nobody mistakes a published verdict for an applied one.
GROWTH_GOVERNANCE Rule 1 applies to whoever wires it: a shrink driven by this verdict must prove
it raises robust forward E[log W]; a STRENGTHENING verdict is the two-sided half of that input.

    python desks/mt5/research/decay_verdicts.py         # writes reports/DECAY_VERDICTS.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import order_sensitive_decay as osd  # noqa: E402

OUT = DESK / "reports" / "DECAY_VERDICTS.json"
SHADOW = DESK / "reports" / "shadow"
SLEEVES_FILE = DESK / "data" / "sleeves.json"
LANE_FILES: dict[str, str] = {"main": "shadow_state.json", "qquant": "qquant_shadow_state.json",
                              "scalp": "scalp_shadow_state.json",
                              "external": "external_shadow_state.json"}
SCHEMA = 1

#: PRE-REGISTERED SPLIT RULE (frozen 2026-10-14, before any sleeve was scored with it). Changing
#: either constant after reading a verdict is the window-shopping exploit R0312 documents.
SUB_PERIODS = 4
MIN_TRADES_PER_PERIOD = 5
MIN_TRADES = SUB_PERIODS * MIN_TRADES_PER_PERIOD   # 20 == decay_monitor.N_MIN_VERDICT

UNMEASURED_TOO_FEW = "UNMEASURED_TOO_FEW_TRADES"
UNMEASURED_NO_LEDGER = "UNMEASURED_NO_LEDGER"
UNMEASURED_NO_SOURCE = "UNMEASURED_NO_SOURCE"
UNMEASURED_SHARED_LEDGER = "UNMEASURED_SHARED_LEDGER"
UNMEASURED_NO_FORWARD_START = "UNMEASURED_NO_FORWARD_START"
UNMEASURED_NO_ENTRY_TIME = "UNMEASURED_NO_ENTRY_TIME"
#: Lane stores keep a retired clock's key in this tombstone map after evacuating its row
#: (research/retired_clocks.py). The key once wrote a ledger, so it is still a co-tenant.
TOMBSTONE = "retired_clocks"
#: Forward-clock statuses that are no longer a clock: a killed clock accrues nothing.
DEAD_CLOCK = frozenset({"KILL", "KILLED", "RETIRED"})

SIZING_HOOK = {
    "status": "NOT_WIRED",
    "owner": "Max-growth thread",
    "reader": "desks/mt5/research/decay_verdicts.py::decay_input",
    "note": ("a demote/shrink INPUT only: no size, door, gate or roster reads this today. "
             "Whoever wires it owes the Rule-1 proof (robust forward E[log W] rises) and the "
             "two-sided half (STRENGTHENING may raise, not only DECAYING lower)."),
}

COMPANIONS = {
    "decline_detector": {
        "path": "libs/research/decline_detector.py",
        "wired_here": False,
        "why": ("a PRICE-SERIES event detector that feeds the rebound book and a per-bar Stage-A "
                "signal; it reads OHLCV, not a sleeve's realised R, so it has nothing to say about "
                "a sleeve's decay. Its consumer is scripts/run_opportunity_books.py "
                "(drawdown_rebound section), which still builds no DeclineEvent from bars -- that "
                "is where it belongs, not in this report."),
    },
    "capacity_frontier": {
        "path": "desks/mt5/research/capacity_frontier.py",
        "wired_here": False,
        "why": ("already scheduled: ops/run_frontier_audit.cmd (box task MT5-FrontierAudit, "
                "daily) runs it with --apply and ops/organ_contract.py holds it to "
                "reports/CAPACITY_FRONTIER.json at a 1,560-minute lease. It sweeps the canonical "
                "evaluator over bars per family, so it is too heavy for an hourly core leg and is "
                "not caller-less."),
    },
}


# ------------------------------------------------------------------------------- the statistic
def splits(n: int, k: int = SUB_PERIODS) -> list[tuple[int, int]]:
    """Equal-count [start, end) blocks by trade index, decided by n alone."""
    edges = [round(i * n / k) for i in range(k + 1)]
    return [(edges[i], edges[i + 1]) for i in range(k)]


def one_sided_p(rs: list[float]) -> float:
    """One-sided Student-t p-value for H1: mean R > 0. A genuine p in [0, 1]."""
    n = len(rs)
    if n < 2:
        raise ValueError("a block needs at least two trades")
    mean = sum(rs) / n
    var = sum((x - mean) ** 2 for x in rs) / (n - 1)
    if var <= 0.0:
        # Zero variance is the degenerate certainty, as in decay_monitor.stats: identical wins
        # are as strong as evidence gets, identical losses as weak, identical zeros say nothing.
        return 0.0 if mean > 0 else (1.0 if mean < 0 else 0.5)
    from scipy.stats import t as _t
    p = float(_t.sf(mean / math.sqrt(var / n), df=n - 1))
    return min(1.0, max(0.0, p))


def verdict_for(rs: list[float]) -> dict[str, Any]:
    """The decay verdict for one realised R series under the pre-registered split."""
    n = len(rs)
    out: dict[str, Any] = {"n": n, "min_trades": MIN_TRADES, "sub_periods": SUB_PERIODS}
    if n < MIN_TRADES:
        out.update(verdict=UNMEASURED_TOO_FEW, p_values=None, splits=None,
                   why=(f"{n} realised trade(s) < {MIN_TRADES} pre-registered minimum "
                        f"({SUB_PERIODS} blocks x {MIN_TRADES_PER_PERIOD}); a decay call on this "
                        "record would be a story about noise"))
        return out
    cuts = splits(n)
    pvals = [round(one_sided_p(rs[a:b]), 6) for a, b in cuts]
    v = osd.decay_verdict(pvals)
    out.update(verdict=v["verdict"], p_values=pvals, splits=[list(c) for c in cuts],
               block_mean_r=[round(sum(rs[a:b]) / (b - a), 4) for a, b in cuts],
               error_rate_early=v.get("error_rate_early"), error_rate_late=v.get("error_rate_late"),
               diff=v.get("diff"), null_band=v.get("null_band"), split_at_block=v.get("split_at"))
    return out


# ------------------------------------------------------------------------------- the records
def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _decay_monitor() -> Any:
    import decay_monitor as dm  # type: ignore[import-not-found]
    return dm


def _ordered_r(rows: list[dict[str, Any]], dm: Any) -> list[float]:
    """R values oldest first by the row's own stamp; rows with no R are skipped, never zero."""
    keyed: list[tuple[float, int, float]] = []
    for i, r in enumerate(rows):
        rv = dm._row_r(r)
        if rv is None or not math.isfinite(rv):
            continue
        ts = dm._row_time(r)
        keyed.append((ts.timestamp() if ts is not None else float("-inf"), i, rv))
    keyed.sort()
    return [x[2] for x in keyed]


def live_series(names: list[str], ledger: Path | None = None) -> tuple[dict[str, list[float]], str]:
    """name -> live realised R, oldest first, with decay_monitor's exclusions. ('' or why-not)."""
    dm = _decay_monitor()
    path = Path(ledger or dm.LEDGER)
    out: dict[str, list[dict[str, Any]]] = {n: [] for n in names}
    stems = {n[:dm.LEDGER_NAME_MAX]: n for n in names}
    try:
        fh = path.open("r", encoding="utf-8", errors="replace")
    except OSError as exc:
        return {}, f"{path} unreadable: {exc.__class__.__name__}"
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict):
                continue
            s = r.get("sleeve")
            name = s if s in out else stems.get(str(s))
            if name is None or not isinstance(r.get("r_multiple"), (int, float)):
                continue
            if r.get("r_unreconstructible") is True:
                continue
            rq = r.get("risk_quote")
            if isinstance(rq, (int, float)) and rq <= 0:
                continue
            out[name].append(r)
    return {n: _ordered_r(rows, dm) for n, rows in out.items()}, ""


def clock_rows(shadow: Path | None = None
               ) -> tuple[dict[str, tuple[str, dict[str, Any]]], dict[str, Any]]:
    """key -> (lane, state row) for every forward clock that is not dead, plus a census."""
    root = Path(shadow or SHADOW)
    rows: dict[str, tuple[str, dict[str, Any]]] = {}
    census: dict[str, Any] = {"lanes_read": [], "lanes_absent": [], "dead_clocks_skipped": 0}
    for lane, name in LANE_FILES.items():
        doc = _read(root / name)
        if not isinstance(doc, dict):
            census["lanes_absent"].append(name)
            continue
        census["lanes_read"].append(name)
        items = list(doc.items())
        if isinstance(doc.get("sleeves"), dict):
            items += list(doc["sleeves"].items())
        for key, row in items:
            if not isinstance(row, dict) or "status" not in row:
                continue
            if str(row.get("status") or "").upper() in DEAD_CLOCK:
                census["dead_clocks_skipped"] += 1
                continue
            rows[str(key)] = (lane, row)
    return rows, census


def all_clock_keys(shadow: Path | None = None) -> set[str]:
    """Every clock key in every lane file, KILLED clocks and the `retired_clocks` tombstones of
    evacuated ones included: a file a dead clock's pass once wrote is still shared, so collisions
    are judged over all of them."""
    root = Path(shadow or SHADOW)
    keys: set[str] = set()
    for name in LANE_FILES.values():
        doc = _read(root / name)
        if not isinstance(doc, dict):
            continue
        items = list(doc.items())
        if isinstance(doc.get("sleeves"), dict):
            items += list(doc["sleeves"].items())
        keys |= {str(k) for k, v in items if isinstance(v, dict) and "status" in v}
        stones = doc.get(TOMBSTONE)
        if isinstance(stones, dict):
            keys |= {str(k) for k in stones}
    return keys


def ledger_name(key: str) -> str | None:
    """The legacy file `shadow_forward` wrote for a clock before per-key ledgers (symbol, family
    and window only) -- `libs.research.forward_ledger.legacy_name`."""
    from libs.research import forward_ledger as fl
    return fl.legacy_name(str(key))


def shared_ledgers(keys: set[str] | list[str]) -> dict[str, list[str]]:
    """legacy file -> the distinct clock keys that map to it, for every file with more than one
    (`forward_ledger.collisions`)."""
    from libs.research import forward_ledger as fl
    return fl.collisions(keys)


def forward_boundary(row: dict[str, Any]) -> datetime | None:
    """The clock's OWN forward boundary on the bar clock, exactly as `shadow_forward` cuts it:
    `forward_start` read as UTC wall time, plus `broker_offset_h`. None if it has none."""
    fs = row.get("forward_start")
    if not fs:
        return None
    try:
        start = datetime.fromisoformat(str(fs).replace("Z", "+00:00")).replace(tzinfo=UTC)
        return start + timedelta(hours=float(row.get("broker_offset_h") or 0.0))
    except (TypeError, ValueError):
        return None


def _entry_time(r: dict[str, Any]) -> datetime | None:
    """The row's ENTRY stamp: `entry_time` (shadow engine) or `opened_at` (the scalp and external
    lanes write that schema). Exit-side stamps are never used: the boundary is on entry."""
    v = r.get("entry_time")
    if not isinstance(v, str) or not v.strip():
        v = r.get("opened_at")
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        ts = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts.astimezone(UTC) if ts.tzinfo else ts.replace(tzinfo=UTC)


def forward_rows(rows: list[dict[str, Any]], boundary: datetime
                 ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rows that are forward evidence for THIS clock: entry at or after its own boundary, and,
    where the row carries a `phase`, tagged `forward` as well. Rows with no readable entry time
    are dropped and counted, never admitted."""
    kept: list[dict[str, Any]] = []
    notes: dict[str, Any] = {"rows": len(rows), "before_own_forward_start": 0,
                             "no_entry_time": 0, "tagged_historical_after_boundary": 0}
    for r in rows:
        et = _entry_time(r)
        if et is None:
            notes["no_entry_time"] += 1
            continue
        if et < boundary:
            notes["before_own_forward_start"] += 1
            continue
        if "phase" in r and r.get("phase") != "forward":
            notes["tagged_historical_after_boundary"] += 1
            continue
        kept.append(r)
    return kept, notes


def clock_series(key: str, dirs: tuple[Path, ...] | None = None,
                 shared: dict[str, list[str]] | None = None,
                 state: dict[str, Any] | None = None
                 ) -> tuple[list[float] | None, str, str, dict[str, Any]]:
    """(forward R oldest first | None, basis, ledger path or why, filter notes).

    The ledger is the clock's OWN, resolved by `libs.research.forward_ledger` (the per-key file,
    or the base key's `#own` file once its legacy name is frozen), never a sibling's: a legacy
    file several keys map to is `shared_legacy`. Its rows then pass the clock's own forward
    boundary, which is applied to every ledger, per-key or not.
    basis is `shadow_forward` / `shadow_unphased` when judged, else `shared_legacy`,
    `no_forward_start` or `none` -- each an UNMEASURED reason, never a series.
    """
    from libs.research import forward_ledger as fl
    dm = _decay_monitor()
    looked = dirs if dirs is not None else tuple(dm.SHADOW_LEDGER_DIRS)
    rows, status, where = fl.read_rows(str(key), looked, shared)
    if rows is None:
        if status == fl.UNMEASURED_SHARED_LEDGER:
            co = [k for k in (shared or {}).get(ledger_name(key) or "", []) if k != str(key)]
            return None, "shared_legacy", where + (
                f" (co-tenants: {', '.join(co[:5])}{', ...' if len(co) > 5 else ''})"
                if co else ""), {}
        return None, "none", where, {}
    boundary = forward_boundary(state or {})
    if boundary is None:
        return None, "no_forward_start", (
            f"clock {key} has no readable forward_start, so no row of {where} is forward "
            "evidence (shadow_forward counts none either)"), {}
    phased = any("phase" in r for r in rows)
    kept, notes = forward_rows(rows, boundary)
    notes["boundary"] = boundary.isoformat()
    if rows and notes["no_entry_time"] == len(rows):
        return None, "no_entry_time", (
            f"none of the {len(rows)} row(s) of {where} carries an entry stamp (entry_time or "
            "opened_at), so no row can be placed against the forward boundary"), notes
    return _ordered_r(kept, dm), ("shadow_forward" if phased else "shadow_unphased"), where, notes


# ------------------------------------------------------------------------------- the report
def build(*, now: datetime | None = None, shadow: Path | None = None,
          sleeves_file: Path | None = None, live_ledger: Path | None = None,
          ledger_dirs: tuple[Path, ...] | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    out_rows: dict[str, dict[str, Any]] = {}
    sources: dict[str, Any] = {}

    # LIVE roster rows, judged on live deals.
    dm = _decay_monitor()
    roster_path = Path(sleeves_file or SLEEVES_FILE)
    roster = _read(roster_path)
    live_names: list[str] = []
    if roster is None:
        sources["roster"] = {"status": "UNMEASURED", "path": str(roster_path),
                             "why": "absent or unreadable: the live roster is UNKNOWN, not empty"}
    else:
        live_names = [n for n, r in dm.roster_rows(roster).items()
                      if str(r.get("status") or "").upper() == "LIVE"]
        sources["roster"] = {"status": "READ", "path": str(roster_path), "live": len(live_names)}
    if live_names:
        series, why = live_series(live_names, live_ledger)
        sources["live_ledger"] = ({"status": "UNMEASURED", "why": why} if why
                                  else {"status": "READ", "path": str(live_ledger or dm.LEDGER)})
        for name in live_names:
            key = f"live:{name}"
            if why:
                out_rows[key] = {"lane": "live", "sleeve": name, "basis": "live_ledger",
                                 "verdict": UNMEASURED_NO_SOURCE, "n": None, "why": why}
                continue
            out_rows[key] = {"lane": "live", "sleeve": name, "basis": "live_ledger",
                             **verdict_for(series.get(name, []))}

    # Forward clocks, judged on their forward-phase ledger rows.
    clocks, census = clock_rows(shadow)
    shared = shared_ledgers(all_clock_keys(shadow))
    sources["forward_clocks"] = {
        **census, "clocks": len(clocks), "shared_legacy_ledgers": len(shared),
        "boundary_rule": ("a row is forward evidence for a clock only at or after that clock's "
                          "OWN forward_start + broker_offset_h, and only if any phase tag "
                          "says forward; a ledger several clock keys map to is no clock's "
                          "series")}
    unmeasured_for = {"shared_legacy": UNMEASURED_SHARED_LEDGER,
                      "no_forward_start": UNMEASURED_NO_FORWARD_START,
                      "no_entry_time": UNMEASURED_NO_ENTRY_TIME}
    for key, (lane, row) in sorted(clocks.items()):
        rs, basis, where, notes = clock_series(key, ledger_dirs, shared, row)
        base = {"lane": lane, "sleeve": key, "basis": basis, "clock_status": row.get("status"),
                "sleeve_id": row.get("sleeve_id"), "forward_start": row.get("forward_start")}
        if rs is None:
            out_rows[f"clock:{key}"] = {**base, "n": None, "why": where,
                                        "verdict": unmeasured_for.get(basis,
                                                                      UNMEASURED_NO_LEDGER)}
            continue
        out_rows[f"clock:{key}"] = {**base, "ledger": where, "row_filter": notes,
                                    **verdict_for(rs)}

    counts = Counter(str(r.get("verdict")) for r in out_rows.values())
    n_measured = sum(1 for r in out_rows.values()
                     if not str(r.get("verdict") or "").startswith("UNMEASURED"))
    return {
        "generated_utc": t.isoformat(timespec="seconds"),
        "schema": SCHEMA,
        "organ": "desks/mt5/research/decay_verdicts.py (hourly_cycle:decay_verdicts)",
        "statistic": ("libs/research/order_sensitive_decay.py (R0312, R0467): Edgington mean-p "
                      "of the early blocks against the late blocks, exact Irwin-Hall, frozen "
                      "null band"),
        "split_rule": {"sub_periods": SUB_PERIODS, "min_trades_per_period": MIN_TRADES_PER_PERIOD,
                       "min_trades": MIN_TRADES, "by": "trade index, equal count, oldest first",
                       "block_i": "[round(i*n/k), round((i+1)*n/k))",
                       "early_vs_late_split": osd._SPLIT,
                       "p_value": "one-sided Student t per block, H1: mean R > 0",
                       "pre_registered": "frozen in code 2026-10-14; identical for every sleeve"},
        "role": "demote/shrink INPUT only -- sizes nothing, gates nothing, edits no roster",
        "sizing_hook": SIZING_HOOK,
        "counts": dict(sorted(counts.items())),
        "n_sleeves": len(out_rows),
        "n_measured": n_measured,
        "measured_share": round(n_measured / len(out_rows), 4) if out_rows else None,
        "sources": sources,
        "companions": COMPANIONS,
        "sleeves": out_rows,
    }


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = Path(path or OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    # PUBLISHED (sync_shadow_to_git): no absolute box path leaves the box (audit HOLD on #1161).
    from libs.research.forward_ledger import public_doc
    tmp.write_text(json.dumps(public_doc(json.loads(json.dumps(doc, default=str))), indent=1),
                   "utf-8")
    tmp.replace(p)
    return p


def decay_input(sleeve: str, path: Path | None = None) -> dict[str, Any]:
    """The verdict row an allocator may read for one sleeve: `live:<name>`, `clock:<key>`, or a
    bare name (live first, then clock). Never raises; an absent artifact or row is UNMEASURED.

    `demote_input` / `strengthen_input` are booleans for a consumer that wants the direction
    only; both are False for STABLE and for every UNMEASURED_* verdict.
    """
    doc = _read(Path(path or OUT))
    if not isinstance(doc, dict) or not isinstance(doc.get("sleeves"), dict):
        return {"verdict": "UNMEASURED", "why": f"{Path(path or OUT).name} absent or unreadable",
                "demote_input": False, "strengthen_input": False}
    rows = doc["sleeves"]
    row = rows.get(sleeve) or rows.get(f"live:{sleeve}") or rows.get(f"clock:{sleeve}")
    if not isinstance(row, dict):
        return {"verdict": "UNMEASURED", "why": f"no decay row for {sleeve}",
                "demote_input": False, "strengthen_input": False}
    v = str(row.get("verdict"))
    return {**row, "generated_utc": doc.get("generated_utc"),
            "demote_input": v == osd.DECAYING, "strengthen_input": v == osd.STRENGTHENING}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    doc = build()
    p = write(doc, a.out)
    print(f"decay verdicts: {doc['n_sleeves']} sleeve(s) {doc['counts']}")
    for k, r in doc["sleeves"].items():
        if r.get("verdict") in (osd.DECAYING, osd.STRENGTHENING):
            print(f"  {r['verdict']:<13} {k}  n={r.get('n')}  p={r.get('p_values')}")
    print(f"written: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
