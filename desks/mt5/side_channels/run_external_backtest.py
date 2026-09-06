"""Run external discovery hypotheses through the backtest pipeline.
Reads test_grid.json, runs each cell, saves results + survivors.
"""
from __future__ import annotations

import inspect
import json
import multiprocessing as mp
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

_h1_cache: dict = {}
_uni = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))

def _family_funcs() -> dict:
    """EVERY registered family, discovered -- never a hand-typed whitelist.

    This was a frozen list of EIGHT names while FAMILY_REGISTRY auto-registers every family_*
    function and families_orthogonal adds fifteen more. A hypothesis naming carry, cot
    positioning, cross-asset residual, gap decay or anything else simply returned None here and
    vanished: the stage reported "cells tested" while whole mechanism classes were unreachable
    from this door (principal 2026-08-28: "no hardcoded exclusion stuck to certain families or
    trading types"). Discovery costs nothing and a family added tomorrow is testable today.
    """
    funcs: dict = {}
    for name in dir(families):
        if name.startswith("family_"):
            fn = getattr(families, name, None)
            if callable(fn):
                funcs[name[len("family_"):]] = fn
    try:
        from mt5desk import families_orthogonal as _fo
        funcs.update(dict(_fo.ORTHOGONAL_FAMILIES))
    except ImportError:
        pass
    return funcs


FAMILY_FUNCS = _family_funcs()

#: Worker processes for the cell sweep. One less than the core count so the box stays responsive
#: while this runs -- it shares the machine with the MT5 gateway, which must never queue behind a
#: research sweep. `EXTERNAL_BACKTEST_WORKERS=1` forces the serial path, which is also what a
#: single-core host gets automatically; the two produce identical results, only slower.
WORKERS = max(1, int(os.environ.get("EXTERNAL_BACKTEST_WORKERS")
                     or max(1, (os.cpu_count() or 2) - 1)))


def normalize_grid(grid: list[dict]) -> tuple[list[dict], int]:
    """Keep only executable family parameters and collapse identities made equal by repair."""
    normalized: list[dict] = []
    seen: set[str] = set()
    removed = 0
    for cell in grid:
        func = FAMILY_FUNCS.get(cell.get("family"))
        if func is None:
            continue
        signature = inspect.signature(func)
        accepts_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()
        )
        raw = dict(cell.get("params") or {})
        legal = raw if accepts_kwargs else {k: v for k, v in raw.items()
                                             if k in signature.parameters}
        removed += len(raw) - len(legal)
        repaired = {**cell, "params": legal}
        identity = json.dumps({k: repaired.get(k) for k in ("symbol", "family", "params")},
                              sort_keys=True, default=str)
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(repaired)
    return normalized, removed


def h1(sym: str) -> pd.DataFrame:
    if sym not in _h1_cache:
        _h1_cache[sym] = families._h1(pd.read_parquet(
            BASE / "data" / "universe" / f"{sym}_H1.parquet"))
    return _h1_cache[sym]


def run_cell(cell: dict) -> dict | None:
    sym = cell["symbol"]
    family_name = cell["family"]
    params = cell["params"]
    func = FAMILY_FUNCS.get(family_name)
    if not func:
        return None
    try:
        meta = _uni.get(sym, {})
        if not meta:
            return None
        df = h1(sym)
        costs = Costs.from_symbol(meta)
        sigs = list(func(df, **params))
        if len(sigs) < 20:
            return None
        result = run_backtest(df, sigs, costs=costs)
        st = result.stats()
        if st["n"] < 20:
            return None
        return {
            "symbol": sym, "family": family_name, "params": params,
            "n": st["n"], "exp_r": round(st["expectancy_r"], 4),
            "max_dd_r": round(st["max_dd_r"], 2), "t_stat": round(st["t_stat"], 2),
            "profit_factor": round(st["profit_factor"], 3),
            "win_rate": round(st["win_rate"], 4),
            "source": cell.get("source_hypothesis", ""),
            "url": cell.get("source_url", ""),
        }
    except Exception as e:
        print(f"  ERR {sym}.{family_name}: {e}")
        return None


def _docket_rows() -> list[dict]:
    """THE DOCKET, which is the population this stage was always supposed to test.

    THE DEFECT THIS ENDS. This function did not exist; `run_all` read `test_grid.json` and
    nothing else. Measured 2026-09-06:

        external_survivors.json   23,465 candidates   (the docket, rewritten hourly by merge)
        test_grid.json               162 rows         (2 families, last written Sep 4)
        external_backtest_results    147 rows         (what survived those 162)

    So the desk mined, compiled and merged 23,465 candidates an hour and then backtested a
    two-day-old hand-bridged grid of 162, in two families, forever. The dashboard read "Reached
    a backtest: 147 (0.75%)" and the funnel looked like a conversion problem. It was not: the
    docket was never connected to the thing that tests it.

    Every docket row is executable -- family present on 23,465/23,465, symbol on 23,465/23,465,
    params on 22,664 -- and all 22 families resolve to a constructor, so nothing here is being
    stretched to fit. `normalize_grid` still has the final say on each row.

    `test_grid.json` is KEPT AND MERGED rather than dropped: it is `bridge_to_hunt`'s product
    and carries source URLs the docket rows do not. Losing a source of candidates while fixing a
    throughput bug would be a strange trade.
    """
    rows: list[dict] = []
    for rel, label in (("external_survivors.json", "docket"), ("test_grid.json", "bridge")):
        path = BASE / "data" / "hypotheses" / rel
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"  {label}: {rel} absent")
            continue
        except (OSError, json.JSONDecodeError) as exc:
            # NAMED, NOT SWALLOWED. A docket that fails to parse and is silently treated as empty
            # returns this stage to exactly the 162-row world it just left, with no line saying so.
            print(f"  {label}: {rel} UNREADABLE ({type(exc).__name__}: {exc})")
            continue
        got = doc if isinstance(doc, list) else (doc.get("candidates") or doc.get("rows") or [])
        got = [r for r in got if isinstance(r, dict)]
        print(f"  {label}: {len(got):,} row(s) from {rel}")
        rows.extend(got)
    return rows


def hold_uncoverable(grid: list[dict]) -> tuple[list[dict], dict]:
    """Split the grid into what this host can honestly test and what it cannot, BY CAUSE.

    ONE FACT PER SYMBOL, NOT TEN THOUSAND ERRORS. Without this, `run_cell` lets `pd.read_parquet`
    raise and prints `ERR <sym>.<family>` per cell -- measured 2026-09-06, 10,961 identical lines
    in one run, which buries every real failure and costs a worker dispatch each. Not a silent
    skip either: the counts and the symbol names are returned and printed, because a skip nobody
    can see is indistinguishable from a cell that passed (L1.28a).

    TWO CAUSES, TWO OWNERS, AND THEY MUST NOT BE POOLED:

        no H1 parquet        the bars were never downloaded  -> fix by fetching the symbol
        no universe metadata bars exist, cost model does not -> fix by extending universe.json
                             from the terminal's own symbol info

    Measured on this host: 297 distinct docket symbols, of which 36 have both, 198 lack bars
    (10,961 cells) and 63 have bars but no costs (5,221 cells -- almost entirely US share CFDs:
    AAPL, ABBV, ACN and the rest). Pooling those into one "held" number would send someone to
    download bars that are already on disk.

    COSTS ARE NEVER SYNTHESISED TO UNBLOCK A CELL. `Costs.from_symbol` is the money path: a
    guessed spread turns an unprofitable cell into a certified one, which is the single most
    expensive lie this pipeline could tell. A symbol without a cost model is held, named, and
    reported -- never costed by analogy to a "similar" instrument.
    """
    have_bars = {p.stem.removesuffix("_H1").upper()
                 for p in (BASE / "data" / "universe").glob("*_H1.parquet")}
    have_costs = {str(s).upper() for s in _uni}
    if not have_bars:
        # An empty universe directory is not a desk whose every symbol is uncoverable -- it is a
        # host that has not synced its bars. Holding all 22,571 cells and reporting "no bars for
        # 297 symbols" would be technically true and useless; say the real thing instead.
        return grid, {"status": "NO_UNIVERSE_DIR", "tested": 0, "held": len(grid),
                      "why": "data/universe holds no *_H1.parquet at all on this host"}
    def _sym(c: dict) -> str:
        return str(c.get("symbol") or "").upper()
    testable = [c for c in grid if _sym(c) in have_bars and _sym(c) in have_costs]
    no_bars = sorted({_sym(c) for c in grid if _sym(c) not in have_bars})
    no_costs = sorted({_sym(c) for c in grid
                       if _sym(c) in have_bars and _sym(c) not in have_costs})
    n_no_bars = sum(1 for c in grid if _sym(c) not in have_bars)
    n_no_costs = sum(1 for c in grid if _sym(c) in have_bars and _sym(c) not in have_costs)
    if no_bars:
        print(f"  {n_no_bars:,} cell(s) HELD -- no H1 parquet for {len(no_bars)} symbol(s): "
              f"{', '.join(no_bars[:10])}{' ...' if len(no_bars) > 10 else ''}")
    if no_costs:
        print(f"  {n_no_costs:,} cell(s) HELD -- bars exist but universe.json carries no cost "
              f"model for {len(no_costs)} symbol(s): {', '.join(no_costs[:10])}"
              f"{' ...' if len(no_costs) > 10 else ''}")
    coverage = {
        "status": "MEASURED",
        "docket_symbols": len({_sym(c) for c in grid}),
        "tested": len(testable), "held": len(grid) - len(testable),
        "held_no_bars": n_no_bars, "held_no_costs": n_no_costs,
        "symbols_no_bars": no_bars, "symbols_no_costs": no_costs,
        "why": ("A cell is testable only where BOTH the H1 bars and the universe cost model "
                "exist. Costs are never synthesised: a guessed spread can certify an "
                "unprofitable cell."),
    }
    return testable, coverage


def run_all() -> list[dict]:
    raw_grid = _docket_rows()
    if not raw_grid:
        print("No candidates: neither the docket nor test_grid.json yielded a row.")
        return []
    grid, removed = normalize_grid(raw_grid)
    grid, coverage = hold_uncoverable(grid)
    print(f"Running {len(grid):,} executable test cells ({len(raw_grid):,} submitted; "
          f"{removed} unsupported parameter occurrence(s) removed)...")

    # SORTED BY SYMBOL BEFORE THE SPLIT, and that is a throughput decision rather than tidiness.
    # `h1()` memoises a symbol's parquet in a per-process dict, so a worker handed a contiguous
    # run of one symbol's cells loads those bars ONCE. Interleaved symbols would make every
    # chunk boundary a fresh parquet read in every worker -- the reason a naive parallelisation
    # of this stage can end up slower than the serial loop it replaced.
    grid.sort(key=lambda c: (str(c.get("symbol")), str(c.get("family"))))
    results = []
    t0 = time.time()
    if WORKERS > 1 and len(grid) > WORKERS:
        # ONE CORE WAS THE BINDING CONSTRAINT AT THIS STAGE. This was a serial `for` loop while
        # `qquant_gates` next door has run its ten gates on a worker pool for weeks -- so the
        # gauntlet judged 6,781 cells in a pass while the backtest that FEEDS it managed 147
        # against a docket of 19,632 (measured off the live dashboard, 2026-09-06). Supply was
        # never the shortage; this loop was.
        #
        # NOTHING STATISTICAL CHANGES. Every cell is independent -- `run_cell` reads the grid
        # row and the symbol's bars and returns its own stats -- so the pool computes the same
        # numbers in a different order, and the results are re-sorted below so the artifact is
        # byte-comparable across worker counts. No gate, threshold or survivor rule is touched
        # here: `exp_r > 0.05` and `max_dd_r > -30` are exactly as they were.
        with mp.Pool(WORKERS) as pool:
            for k, r in enumerate(pool.imap_unordered(run_cell, grid, chunksize=8)):
                if r:
                    results.append(r)
                    if r["exp_r"] > 0.05:
                        print(f"  PASS {r['symbol']:8s}.{r['family']:25s} n={r['n']:4d} "
                              f"exp={r['exp_r']:+.4f}R maxDD={r['max_dd_r']:+.1f}R "
                              f"PF={r['profit_factor']:.2f}", flush=True)
                if (k + 1) % 100 == 0:
                    el = time.time() - t0
                    print(f"  [{k+1}/{len(grid)}] {el:.0f}s elapsed, "
                          f"{(k+1)/max(el, 1e-9)*3600:,.0f} cells/hour", flush=True)
    else:
        for i, cell in enumerate(grid):
            r = run_cell(cell)
            if r:
                results.append(r)
                if r["exp_r"] > 0.05:
                    print(f"  PASS {r['symbol']:8s}.{r['family']:25s} n={r['n']:4d} "
                          f"exp={r['exp_r']:+.4f}R maxDD={r['max_dd_r']:+.1f}R "
                          f"PF={r['profit_factor']:.2f}")
            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(grid)}] {time.time()-t0:.0f}s elapsed")

    # DETERMINISTIC ORDER FROM AN UNORDERED POOL. `imap_unordered` returns by completion, so
    # without this the artifact's row order depends on scheduling -- which turns every rerun
    # into a spurious diff and makes two hosts' results impossible to compare by eye.
    results.sort(key=lambda r: (r["symbol"], r["family"],
                                json.dumps(r["params"], sort_keys=True, default=str)))
    elapsed = time.time() - t0
    out = BASE / "data" / "hypotheses" / "external_backtest_results.json"
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    survivors = [r for r in results if r["exp_r"] > 0.05 and r["max_dd_r"] > -30]

    # THE COVERAGE GAP IS PUBLISHED, not just printed. A number that exists only in a service
    # log is a number nobody acts on -- which is how a 162-row grid ran unnoticed beside a
    # 23,465-row docket for days. The issue board and the dashboard read this file, so "5,221
    # cells cannot be tested because 63 symbols have no cost model" becomes a work item with a
    # symbol list instead of a silence.
    coverage.update({"cells_submitted": len(raw_grid), "cells_run": len(grid),
                     "cells_produced_result": len(results), "survivors": len(survivors),
                     "elapsed_s": round(elapsed, 1), "workers": WORKERS,
                     "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    cov_path = BASE / "reports" / "BACKTEST_COVERAGE.json"
    cov_path.parent.mkdir(parents=True, exist_ok=True)
    cov_path.write_text(json.dumps(coverage, indent=2, default=str), encoding="utf-8")

    print(f"\n{len(results)} cells tested, {len(survivors)} survivors in {elapsed:.0f}s")
    for s in sorted(survivors, key=lambda x: -x["exp_r"]):
        print(f"  {s['symbol']:8s} {s['family']:25s} n={s['n']:4d} exp={s['exp_r']:+.4f}R "
              f"maxDD={s['max_dd_r']:+.1f}R PF={s['profit_factor']:.2f}")

    # ONE PRODUCER PER FILE. This used to ALSO write external_survivors.json directly, which
    # clobbered the merged docket with just this stage's rows at :06 every hour -- measured
    # 2026-08-27: the 00:47 merge shipped 122 candidates, stage 2 overwrote them with its own
    # 0 stage-A passes at 01:06, and the docket sat empty until the next merge. Merge
    # (merge_hypotheses.py) is the only writer of external_survivors.json; this stage's product
    # is external_backtest_results.json above, which merge consumes like every other source.
    return survivors


if __name__ == "__main__":
    run_all()
