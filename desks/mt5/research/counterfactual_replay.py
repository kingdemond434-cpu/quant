"""The counterfactual world, once a day (and cheap enough to run hourly): the desk's own decisions
replayed against every alternative it could have chosen.

THE PRINCIPAL'S ORDER, in one organ. "For every decision store signal, trade/no-trade, size,
chosen execution, chosen exit, veto reason, state, portfolio context; simulate what if entered /
skipped / 0.5x / 1.0x / 1.5x / market / limit / delayed / fixed TP / trail / hold / partial;
estimate dElog_decision. This creates Veto Alpha, Sizing Alpha, Execution Alpha, Exit Alpha,
Missed-Trade Alpha from your own behaviour -- private by observation." `libs.research
.decision_dataset` assembles the row (eleven ledgers, eleven join rules, one key);
`libs.research.counterfactual_world` prices the arms; this organ is the clock, the files and the
watermark.

WHAT IT DOES EACH PASS. Reads the eleven append-only ledgers, joins every decision minute past
the watermark (plus the rows an earlier pass left PENDING, because a deal closes days after its
intent and a counterfactual cannot be priced until the bars arrive), prices every alternative
with the best of the desk's own cost posteriors -- the execution twin's live-fill recalibration,
then the fitted fill surface, then the registry spread at the honest baseline, and the row SAYS
which -- appends the priced rows to `data/decision_dataset.jsonl` (append-only, versioned, so a
re-run over unchanged ledgers writes zero lines) and writes `reports/COUNTERFACTUAL_WORLD.json`.

THE REPORT IS SIGNED THE SAME WAY THROUGHOUT: every alpha is the ALTERNATIVE minus the DESK.
Positive is a bill -- the road not taken was better -- and negative is the desk having been
right. A class that reads negative is printed exactly as loudly as one that reads positive,
because an organ that only reports its own bad news is an organ nobody can size on.

OFF THE BOX IT MEASURES NOTHING AND SAYS SO. This research container holds no gateway ledgers
(the trading box does), so the pass returns UNMEASURED with the reason, writes the report saying
that, and exits 0. An organ that fabricates an alpha because its inputs are missing is worse than
one that does not run.

    python3 research/counterfactual_replay.py [--budget-s N] [--symbols XAUUSD,EURUSD] [--no-write]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import counterfactual_world as cw  # noqa: E402
from libs.research import decision_dataset as dd  # noqa: E402

#: The desk root the eleven ledgers hang off. Named separately from BASE so a test can point the
#: whole join at a tmp tree without ever touching the box's real ledgers.
DESK = BASE
#: This organ's own three files: the versioned dataset, its watermark, and the report.
DATASET = BASE / "data" / "decision_dataset.jsonl"
WATERMARK = BASE / "data" / "decision_dataset_watermark.json"
REPORT = BASE / "reports" / "COUNTERFACTUAL_WORLD.json"
#: The cost posteriors, in the order `resolve_cost_model` prefers them.
TWIN = BASE / "reports" / "EXECUTION_TWIN.json"
SURFACE = BASE / "reports" / "FILL_SURFACE.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"

YIELD_PREFIX = "YIELD "
#: The counters the hourly pass reads off the report by name.
YIELD_KEYS = ("rows_joined", "rows_written", "rows_priced", "classes_measured")

#: The decisions listed by |dElog| -- where the desk's own behaviour actually moved money.
TOP_K = 25
#: A pass reads the whole ledger set and prices with bars; the budget bounds the pricing loop so
#: an hourly caller cannot be held by a box with a year of decisions and a cold parquet cache.
DEFAULT_BUDGET_S = 240.0


def _read_json(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _bars_for(symbol: str, cache: dict[str, list[cw.Bar]]) -> list[cw.Bar]:
    """The symbol's H1 bars as the pricer's own Bar list, read once per pass per symbol.

    `proposer_common.bars` is the desk's one bar reader (the parquet cache the whole research
    side shares), so the counterfactual runs on exactly the tape the gauntlet does rather than a
    second copy that can drift from it."""
    if symbol in cache:
        return cache[symbol]
    rows: list[cw.Bar] = []
    try:
        from research import proposer_common as pc

        df = pc.bars(symbol)
        if df is not None and not df.empty:
            need = ("open", "high", "low", "close")
            if all(c in df.columns for c in need):
                rows = cw.bars_from_rows(
                    [(ts, r.open, r.high, r.low, r.close) for ts, r in df.iterrows()])
    except Exception:
        # A missing, torn or unreadable parquet is NO_BARS for that symbol, never a failed pass:
        # one bad file must not cost the report every other symbol's alpha.
        rows = []
    cache[symbol] = rows
    return rows


def _cost_for(symbol: str, price: float | None, twin: dict[str, Any], surface: dict[str, Any],
              universe: dict[str, Any], cache: dict[str, cw.CostModel]) -> cw.CostModel:
    """The best available posterior for the symbol, resolved once per pass and stamped on every
    row it prices. Cached because the resolution is a lookup and the census in the report counts
    rows, not lookups."""
    if symbol in cache:
        return cache[symbol]
    meta = universe.get(symbol) if isinstance(universe.get(symbol), dict) else None
    model = cw.resolve_cost_model(symbol, twin=twin or None, surface=surface or None,
                                  meta=meta, price=price)
    cache[symbol] = model
    return model


def _unmeasured(why: str, *, write: bool, **extra: Any) -> dict[str, Any]:
    """UNMEASURED is a STATEMENT ABOUT THE HOST and is written down like any other. A report that
    disappears when its inputs do is indistinguishable from an organ that never ran, which is the
    exact ambiguity the freshness fence exists to remove."""
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "status": cw.UNMEASURED,
           "why": why, "alphas": {c: {"status": cw.UNMEASURED, "n": 0, "alpha": None, "reads": why}
                                  for c in cw.ALPHA_CLASSES},
           "rows_joined": 0, "rows_written": 0, "rows_priced": 0, "classes_measured": 0, **extra}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def run(symbols: list[str] | set[str] | None = None, budget_s: float | None = None,
        write: bool = True) -> dict[str, Any]:
    """One pass: join since the watermark, price, append, report. Returns the report."""
    t0 = time.monotonic()
    now = datetime.now(tz=UTC)
    budget = float(budget_s) if budget_s and budget_s > 0 else DEFAULT_BUDGET_S

    ledgers = dd.load_ledgers(DESK)
    counts = dd.ledger_counts(ledgers)
    if not any(counts.get(name, 0) for name in dd.PRIMARY):
        return _unmeasured(
            f"no decision or intent ledger under {DESK / 'data'}: the gateway has neither "
            "considered nor placed anything on this box, so there is no decision to replay "
            "(this research container has no ledgers; the trading box does)",
            write=write, ledger_rows=counts)

    mark = dd.Watermark.load(WATERMARK)
    if mark.unchanged(counts) and not symbols:
        return {"status": "UNCHANGED", "why": "no ledger grew and nothing was left pending",
                "ledger_rows": counts, "rows_joined": 0, "rows_written": 0,
                "rows_priced": 0, "classes_measured": 0}

    rows = dd.join(ledgers, since=mark.ledger_lines, pending=mark.pending, now=now)
    want = {str(s) for s in symbols} if symbols else None
    if want:
        rows = [r for r in rows if r.symbol in want]

    twin, surface, universe = _read_json(TWIN), _read_json(SURFACE), _read_json(UNIVERSE)
    bars_cache: dict[str, list[cw.Bar]] = {}
    cost_cache: dict[str, cw.CostModel] = {}
    priced = 0
    for row in rows:
        if time.monotonic() - t0 > budget:
            # The unpriced tail stays UNPRICED and is re-read next pass off the watermark's
            # pending list: a budget must cost latency, never a silently dropped decision.
            row.counterfactual_outcomes = {
                "status": cw.UNPRICED,
                "why": f"pass budget {budget:.0f}s spent before this row; retried next pass"}
            continue
        level = row.chosen_action.get("price")
        cost = _cost_for(row.symbol, float(level) if isinstance(level, int | float) else None,
                         twin, surface, universe, cost_cache)
        row.counterfactual_outcomes = cw.price_row(row.to_row(), _bars_for(row.symbol, bars_cache),
                                                   cost)
        if row.counterfactual_outcomes.get("status") == cw.PRICED:
            priced += 1

    written = dd.append(rows, DATASET) if write else 0
    # The dataset's LAST version per row is the truth, so the alphas are read back off the file
    # rather than off this pass's rows: a row priced three passes ago still counts, and a row
    # re-priced today counts once.
    latest = (list(dd.latest(DATASET).values()) if write and DATASET.exists()
              else [r.to_row() for r in rows])
    alphas = cw.aggregate(latest)
    top = cw.top_decisions(latest, TOP_K)
    measured = sum(1 for c in cw.ALPHA_CLASSES if alphas[c]["status"] == "MEASURED")

    report: dict[str, Any] = {
        "generated_utc": now.isoformat(), "status": cw.MEASURED if priced else cw.UNMEASURED,
        "why": ("" if priced else
                "decision rows exist but none could be priced: no bars cover their minutes on "
                "this host, or every bracket was NOT_TRIGGERED"),
        "ledger_rows": counts, "join_rules": dict(dd.JOIN_RULES),
        "dataset": {"path": str(DATASET), "schema_version": dd.SCHEMA_VERSION,
                    "rows_joined": len(rows), "rows_written": written,
                    "rows_priced": priced, "rows_on_file": len(latest),
                    "watermark": str(WATERMARK)},
        "alphas": alphas,
        "headline_by_class": {c: {"alpha": alphas[c]["alpha"], "n": alphas[c]["n"],
                                  "status": alphas[c]["status"], "reads": alphas[c]["reads"]}
                              for c in cw.ALPHA_CLASSES},
        "cost_models": {"resolved": {s: m.to_row() for s, m in sorted(cost_cache.items())},
                        "order": "execution_twin -> fill_surface -> registry honest baseline",
                        "census": alphas.get("cost_model_sources", {})},
        "top_decisions": top,
        "symbols_filter": sorted(want) if want else None,
        "budget_s": budget, "seconds": round(time.monotonic() - t0, 3),
        "rule": ("every alpha is the ALTERNATIVE minus the DESK: positive means the road not "
                 "taken was better and the desk's choice cost growth, negative means the desk "
                 "was right, and a class below its sample floor is UNMEASURED with its n. A "
                 "bracket the market never offered is NOT_TRIGGERED and enters no class"),
        "consumers": {
            "desks/mt5/research/missed_growth.py": (
                "measure_veto should read alphas.VETO_ALPHA.arms[<reason>] -- it carries "
                "n_vetoed_and_triggered / mean_avoided_r / filter_value_r / t / verdict under "
                "the names it already reads off FILTER_VALUE.json"),
            "status": "NOT WIRED -- advisory until missed_growth reads VETO_ALPHA",
        },
        # the yield counters, on the report so the hourly pass can count them by name
        "rows_joined": len(rows), "rows_written": written, "rows_priced": priced,
        "classes_measured": measured,
    }
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
        if not want:
            # A filtered run is a probe: it must not move the watermark, or the symbols it
            # skipped would be marked consumed and never joined again.
            mark.ledger_lines = counts
            mark.pending = dd.pending_ids(latest)
            mark.rows_written += written
            mark.runs += 1
            mark.last_run_utc = now.isoformat()
            mark.save(WATERMARK)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=None)
    ap.add_argument("--symbols", default="", help="comma-separated; a probe, moves no watermark")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()] or None
    d = run(symbols=syms, budget_s=a.budget_s, write=not a.no_write)
    status = d.get("status")
    if status in (cw.UNMEASURED, "UNCHANGED") and not d.get("rows_priced"):
        print(f"COUNTERFACTUAL WORLD  {status}: {d.get('why')}", flush=True)
    else:
        ds = d["dataset"]
        print(f"COUNTERFACTUAL WORLD  joined={ds['rows_joined']} written={ds['rows_written']} "
              f"priced={ds['rows_priced']} on_file={ds['rows_on_file']} -> {REPORT}", flush=True)
        for cls, row in d["headline_by_class"].items():
            alpha = row["alpha"]
            shown = f"{alpha:+.6f}" if isinstance(alpha, int | float) else "     --"
            print(f"  {cls:20s} n={row['n']:5d} alpha={shown} {row['status']:10s} "
                  f"{row['reads']}", flush=True)
    print(YIELD_PREFIX + json.dumps({k: int(d.get(k) or 0) for k in YIELD_KEYS}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
