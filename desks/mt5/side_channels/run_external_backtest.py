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

from collections import Counter  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

_h1_cache: dict = {}
_uni = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))


def canonical_symbol(sym: str) -> str:
    """The BROKER's spelling of a symbol, given any casing of it.

    THE CELLS THIS WAS LOSING. Fusion names its share CFDs in mixed case -- `Apple`, `Berkshire`,
    `AlibabaGroup`, `Coca-Cola` -- 98 of the 251 symbols in the registry. The docket carries them
    uppercased, and the two eligibility checks in `hold_uncoverable` compare `sym.upper()` on both
    sides, so every one of those cells is admitted as testable. Then `bars()` built
    `f"{sym}_{tf}.parquet"` from the DOCKET's spelling and asked the filesystem for
    `ACCENTURE_H1.parquet` while the file on disk is `Accenture_H1.parquet`.

    So the cell passed the gate that exists to catch exactly this and died one function later, on
    a case-sensitive filesystem lookup, inside a worker whose failure is counted as "produced no
    result" rather than "was never runnable". MEASURED 2026-09-06: 8,057 cells run, 2,619 results.
    Every US share CFD on the docket was in the losing half, and the coverage report -- being
    case-insensitive itself -- listed none of them as held.

    CASE ONLY, DELIBERATELY. This maps `ACCENTURE` to `Accenture` and refuses to do anything more
    clever: `AAPL` must NEVER resolve to `Apple`. Case is not semantic in a broker's symbol table,
    so folding it recovers the same instrument with certainty; a ticker-to-name guess is a
    different instrument wearing a plausible label, and certifying a cell against the wrong one is
    the failure this whole stage exists to prevent. A symbol with no case-insensitive match is
    returned unchanged, so it goes on to fail visibly rather than silently becoming something else.
    """
    return _canonical_index().get(str(sym).strip().upper(), str(sym))


@lru_cache(maxsize=1)
def _canonical_index() -> dict[str, str]:
    """Uppercased symbol -> the broker's own spelling.

    The REGISTRY wins over a filename when both carry a symbol: universe.json is MetaTrader's own
    answer, and a parquet name is only ever a copy of it. Parquet stems are indexed too, because a
    symbol can have bars here before its registry row has synced -- and holding a cell whose chart
    is sitting on disk is the same idle-for-want-of-plumbing this desk keeps paying for.
    """
    index: dict[str, str] = {}
    for symbol in _uni:
        index.setdefault(str(symbol).upper(), str(symbol))
    for path in (BASE / "data" / "universe").glob("*_*.parquet"):
        stem = path.stem.rpartition("_")[0]
        if stem:
            index.setdefault(stem.upper(), stem)
    return index

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

# THE SHARED INPUT REBUILDER, imported once. Absent on a host without the orthogonal-sweep
# sources, in which case multi-input families are reported unrunnable BY NAME rather than
# raising per cell -- the same distinction `hold_uncoverable` draws for bars and costs.
try:
    from mt5desk.family_inputs import (
        IDENTITY_KEYS as _IDENTITY_KEYS,
        resolve as _resolve_inputs, strip_identity_keys, timeframe_of,
    )
except ImportError as _exc:                      # pragma: no cover - host-dependent
    _resolve_inputs = strip_identity_keys = timeframe_of = None
    _IDENTITY_KEYS = frozenset()
    print(f"family_inputs unavailable ({_exc}); multi-input families cannot be tested on this host")

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
        # IDENTITY KEYS SURVIVE THE SIGNATURE FILTER. `peer_symbol`, `factor_symbols`,
        # `input_symbol`, `input_source` and `timeframe` name an input or a chart to LOAD; by
        # construction none of them appears in any family signature, so filtering to the
        # signature deleted every one -- and `family_inputs.resolve`, which exists to load what
        # they name, then found nothing to load. Measured 2026-09-06: peer_symbol gone from all
        # 427 relative_value candidates, factor_symbols from all 780 cross_asset_residual,
        # input_symbol from all 248 carry, input_source from all 10 cot_positioning. Those five
        # families tested ZERO times while the breadth report listed them as REACHABLE, and the
        # deletion was logged as "2,207 unsupported parameter occurrence(s) removed".
        #
        # `strip_identity_keys` removes them again at CALL time, once `resolve` has used them, so
        # the family function still never sees a kwarg it cannot take.
        legal = raw if accepts_kwargs else {k: v for k, v in raw.items()
                                            if k in signature.parameters
                                            or k in _IDENTITY_KEYS}
        removed += len(raw) - len(legal)
        repaired = {**cell, "params": legal}
        identity = json.dumps({k: repaired.get(k) for k in ("symbol", "family", "params")},
                              sort_keys=True, default=str)
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(repaired)
    return normalized, removed


def bars(sym: str, timeframe: str = "H1") -> pd.DataFrame:
    """The cell's OWN chart, not H1 for everything.

    THE HARDCODE THIS REPLACES. This read `f"{sym}_H1.parquet"` unconditionally, so a cell
    certified on M5 was backtested here on hourly bars -- a different strategy wearing the same
    identity, and exactly the research/live semantic drift the mandate's §43 forbids. The desk
    already fixed this on the execution side (the universal family executor runs a certificate on
    its certified timeframe, M1 through D1); this stage was still hourly-only.

    NO FAMILY OR TIMEFRAME IS ENUMERATED HERE. The timeframe is whatever the cell declares and
    the file is whatever exists; a new chart added to the universe directory is usable the day it
    lands, with no edit to this function. Falling back to H1 is recorded in the exception text
    rather than done silently, because a cell quietly replayed on the wrong chart is worse than
    one that refuses: the refusal is visible, the wrong chart certifies.
    """
    tf = str(timeframe or "H1").upper()
    sym = canonical_symbol(sym)
    key = (sym, tf)
    if key not in _h1_cache:
        path = BASE / "data" / "universe" / f"{sym}_{tf}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"no {tf} bars for {sym} ({path.name} absent)")
        _h1_cache[key] = families._h1(pd.read_parquet(path))
    return _h1_cache[key]


def h1(sym: str) -> pd.DataFrame:
    """Backwards-compatible alias: this module's other callers ask for hourly bars by name."""
    return bars(sym, "H1")


def run_cell(cell: dict) -> dict | None:
    sym = cell["symbol"]
    family_name = cell["family"]
    params = cell["params"]
    func = FAMILY_FUNCS.get(family_name)
    if not func:
        return None
    try:
        # SAME CASE FOLD AS `bars()`, and the same reason. An uppercased `ACCENTURE` missed the
        # registry's `Accenture` here too and returned None -- the second of two silent kills on
        # the same cell, both counted downstream as "produced no result" rather than "could not
        # be looked up". A cell that is genuinely unknown to the broker still returns None below.
        meta = _uni.get(canonical_symbol(sym), {})
        if not meta:
            return None
        # THE CELL'S OWN CHART. `timeframe_of` reads it from the cell's params and defaults to
        # H1 when the cell does not declare one -- the docket's 23,465 rows are all undeclared
        # today, so this is a no-op for them and load-bearing for every M5/M15/H4/D1 cell the
        # miners and the scalp lane produce.
        df = bars(sym, timeframe_of(params) if timeframe_of is not None else "H1")
        costs = Costs.from_symbol(meta)
        # FAMILIES NEEDING MORE THAN THEIR OWN BARS WERE NEVER TESTED HERE, AND THAT IS WHY THE
        # BOOK HAS ONE MECHANISM. This called `func(df, **params)` with the symbol's own H1 and
        # nothing else, so every family whose signal needs a peer, a factor, a macro series or COT
        # positioning raised on the missing kwarg and was swallowed by the `except` below as an
        # ordinary error. Measured 2026-09-06, after connecting the docket: carry (248 docket
        # rows), relative_value (427), cross_asset_residual (780), event_reaction (113) and
        # cot_positioning (10) were tested ZERO times between them -- 1,578 candidates in the five
        # families the breadth report lists as REACHABLE and missing from the book. They were
        # reachable; nothing reached them.
        #
        # `mt5desk.family_inputs.resolve` is the SAME reconstruction `external_gauntlet.build_cell`
        # and `shadow_forward` use -- imported, not re-implemented, because a second rebuilder is
        # how a cell comes to be gauntleted on one set of inputs and forward-tested on another.
        # A cell whose inputs cannot be rebuilt on this host returns None WITH ITS REASON rather
        # than raising, so "no peer bars for this pair" stops looking like a code fault.
        call_params = dict(params)
        if _resolve_inputs is not None:
            extra, why = _resolve_inputs(sym, family_name, params, df)
            if extra is None:
                # RETURNED, NOT APPENDED TO A MODULE LIST. Workers are separate processes, so a
                # module-level accumulator would collect these in the child and vanish -- the
                # reason would exist nowhere, which is the silent-skip failure again. The
                # collector below counts these by family and never files them as results.
                return {"__skip__": f"{family_name}: {why}"}
            call_params = strip_identity_keys(family_name, params)
            call_params.update(extra)
        sigs = list(func(df, **call_params))
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


def available_timeframes() -> dict[str, list[str]]:
    """Every chart on disk, per symbol, discovered -- never a hardcoded list.

    `{"EURUSD": ["M5", "M15", "H1"], ...}`. A timeframe added to the universe directory is swept
    the next hour with no edit here, which is the whole point: the previous code named `H1` in a
    format string and no other chart could ever be reached, whatever the box downloaded.
    """
    out: dict[str, list[str]] = {}
    for p in (BASE / "data" / "universe").glob("*_*.parquet"):
        sym, _, tf = p.stem.rpartition("_")
        if sym and tf:
            out.setdefault(sym.upper(), []).append(tf.upper())
    for sym in out:
        out[sym] = sorted(set(out[sym]), key=lambda t: _TF_ORDER.get(t, 999))
    return out


#: Chart ordering for reporting only -- shortest first, so an intraday result reads before the
#: daily one. NOT a whitelist: a timeframe absent from this map still sweeps, it just sorts last.
_TF_ORDER = {"M1": 1, "M5": 2, "M15": 3, "M30": 4, "H1": 5, "H4": 6, "D1": 7, "W1": 8}


def expand_timeframes(grid: list[dict]) -> list[dict]:
    """One cell with no declared chart becomes one cell PER chart its symbol has.

    THE H1 DEFAULT WAS ITSELF THE DEFECT, and replacing a hardcoded `_H1.parquet` with a
    `timeframe or "H1"` fallback would have kept it: every one of the docket's 23,465 rows
    declares no timeframe, so the fallback IS the hardcode, one level down. A mechanism that
    works on M5 and not on H1 was unmineable either way.

    So an undeclared cell is not assigned a chart -- it is swept across all of them, and each
    sweep carries its own `timeframe` in params. That makes the chart part of the cell's
    IDENTITY: `EURUSD carry M5` and `EURUSD carry H1` are two candidates with two parameter sets,
    two gauntlet verdicts and two forward clocks, which is what the two-stage law requires. It is
    also how intraday edges enter a docket built entirely from hourly miners.

    A cell that DOES declare a timeframe is left exactly as it is. The declaration is the
    certified identity and this may not multiply it.
    """
    if timeframe_of is None:
        return grid
    charts = available_timeframes()
    out: list[dict] = []
    for cell in grid:
        params = dict(cell.get("params") or {})
        if params.get("timeframe"):
            out.append(cell)
            continue
        tfs = charts.get(str(cell.get("symbol") or "").upper(), [])
        if not tfs:
            # A SYMBOL WITH NO CHART AT ALL STILL GETS A ROW, and this branch is a defect I put
            # in and took out again. Emitting nothing here made the cell VANISH: the grid fell
            # from 22,571 to 13,480 and `held_no_bars` then read 0, so the bar-coverage gap --
            # 9,091 cells across 198 symbols -- disappeared from the report that exists to name
            # it. A silent drop that also silences the detector is strictly worse than the
            # original problem. The cell is kept with its chart undeclared; `hold_uncoverable`
            # holds it and names the symbol, which is where that fact belongs.
            out.append(cell)
            continue
        for tf in tfs:
            out.append({**cell, "params": {**params, "timeframe": tf}})
    return out


def route_by_lane(grid: list[dict]) -> tuple[list[dict], dict]:
    """Keep only the cells whose instrument's edge is sought STATISTICALLY.

    PRINCIPAL'S ORDER, 2026-09-06: single-name equities are traded on news, financial reports and
    earnings reaction, not hunted for statistical hypotheses. `research/universe_policy.py` holds
    the reasoning and the routing; this is where the gauntlet obeys it.

    THE TRIAL BUDGET IS THE POINT, not the CPU. Skipping these cells saves some hours, but the
    reason to do it is that `deflated_sharpe` and the program-level SPA/PBO tests spread one
    family-wise error budget across EVERY hypothesis the desk tested -- so each equity cell was
    raising the bar that every FX and metals cell had to clear. Measured on this docket: 10,575
    of 23,627 cells (44.8%) were single-name equities and 3,839 more were equity tickers from a
    non-Fusion vocabulary; about 61% of the multiple-testing charge was being spent on the asset
    class least suited to the method, and paid for by the classes best suited to it.

    ROUTED, NOT DROPPED, AND SAID OUT LOUD. These cells are reported by lane and symbol count in
    BACKTEST_COVERAGE.json. A cell that silently disappears between the docket and the runner is
    indistinguishable from one that was tested and failed -- which is the confusion this stage has
    already paid for twice today.
    """
    try:
        sys.path.insert(0, str(BASE / "research"))
        import universe_policy as policy
    except Exception as exc:                                            # noqa: BLE001
        # NO POLICY MEANS NO ROUTING, NOT SILENT ROUTING. Running the whole docket is the prior
        # behaviour and is safe; quietly discarding 61% of it because an import failed is not.
        return grid, {"status": f"UNAVAILABLE ({type(exc).__name__}: {exc})", "routed_out": 0}

    kept, by_lane, syms = [], Counter(), {}
    for cell in grid:
        sym = canonical_symbol(str(cell.get("symbol") or ""))
        lane = policy.lane(sym)
        by_lane[lane] += 1
        syms.setdefault(lane, set()).add(sym)
        if lane == policy.HYPOTHESIS:
            kept.append(cell)
    for lane, n in sorted(by_lane.items()):
        if lane == policy.HYPOTHESIS:
            continue
        why = ("traded on news, financial reports and earnings reaction -- not hunted statistically"
               if lane == policy.EVENT else
               "not in the broker's registry, so no asset class and no lane -- hunted by nothing "
               "until it is classified")
        print(f"  {n:,} cell(s) ROUTED OUT of hypothesis discovery [{lane}] across "
              f"{len(syms[lane])} symbol(s): {why}")
    return kept, {
        "status": "MEASURED",
        "kept_hypothesis": by_lane.get(policy.HYPOTHESIS, 0),
        "routed_event": by_lane.get(policy.EVENT, 0),
        "routed_unclassified": by_lane.get(policy.UNCLASSIFIED, 0),
        "symbols_event": sorted(syms.get(policy.EVENT, ())),
        "symbols_unclassified": sorted(syms.get(policy.UNCLASSIFIED, ())),
        "policy": "desks/mt5/research/universe_policy.py",
    }


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
    # PER (SYMBOL, CHART), not per symbol on H1. Globbing `*_H1.parquet` here would hold every
    # M5 cell the timeframe sweep just created, on the grounds that a DIFFERENT chart exists --
    # the same hardcode wearing a coverage check's clothes.
    charts = available_timeframes()
    have_costs = {str(s).upper() for s in _uni}
    if not charts:
        # An empty universe directory is not a desk whose every symbol is uncoverable -- it is a
        # host that has not synced its bars. Holding all 22,571 cells and reporting "no bars for
        # 297 symbols" would be technically true and useless; say the real thing instead.
        return grid, {"status": "NO_UNIVERSE_DIR", "tested": 0, "held": len(grid),
                      "why": "data/universe holds no *_H1.parquet at all on this host"}
    def _sym(c: dict) -> str:
        return str(c.get("symbol") or "").upper()

    def _has_bars(c: dict) -> bool:
        tf = str((c.get("params") or {}).get("timeframe") or "H1").upper()
        return tf in charts.get(_sym(c), ())

    testable = [c for c in grid if _has_bars(c) and _sym(c) in have_costs]
    no_bars = sorted({_sym(c) for c in grid if not _has_bars(c)})
    no_costs = sorted({_sym(c) for c in grid
                       if _has_bars(c) and _sym(c) not in have_costs})
    n_no_bars = sum(1 for c in grid if not _has_bars(c))
    n_no_costs = sum(1 for c in grid if _has_bars(c) and _sym(c) not in have_costs)
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
    before_tf = len(grid)
    grid = expand_timeframes(grid)
    if len(grid) != before_tf:
        print(f"  timeframe sweep: {before_tf:,} cell(s) -> {len(grid):,} "
              f"(each undeclared cell swept across every chart its symbol has)")
    grid, routing = route_by_lane(grid)
    grid, coverage = hold_uncoverable(grid)
    coverage["routing"] = routing
    print(f"Running {len(grid):,} executable test cells ({len(raw_grid):,} submitted; "
          f"{removed} unsupported parameter occurrence(s) removed)...")

    # SORTED BY SYMBOL BEFORE THE SPLIT, and that is a throughput decision rather than tidiness.
    # `h1()` memoises a symbol's parquet in a per-process dict, so a worker handed a contiguous
    # run of one symbol's cells loads those bars ONCE. Interleaved symbols would make every
    # chunk boundary a fresh parquet read in every worker -- the reason a naive parallelisation
    # of this stage can end up slower than the serial loop it replaced.
    grid.sort(key=lambda c: (str(c.get("symbol")), str(c.get("family"))))
    results = []
    skips: Counter = Counter()
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
                if r and "__skip__" in r:
                    skips[r["__skip__"].split(":", 1)[0]] += 1
                elif r:
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
            if r and "__skip__" in r:
                skips[r["__skip__"].split(":", 1)[0]] += 1
                r = None
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
