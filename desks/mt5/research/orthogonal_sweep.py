"""ORTHOGONAL SWEEP -- run every non-breakout family across the universe and emit candidates.

WHY THIS IS THE N_eff FIX AND NOT A NICE-TO-HAVE (principal 2026-08-26: "why don't u fix it
then"). Live readiness is blocked on two checks. One of them -- fourteen elapsed days -- nothing
can shorten. The OTHER, effective independent bets, is entirely fixable today and was being
treated as if it were also a waiting problem. It is not: N_eff is 0 because every certificate the
desk holds is the same mechanism, and it stays that way for exactly as long as nobody tests a
different one.

WHAT THIS DOES. Sweeps the fourteen orthogonal generators across every symbol with bars and every
input the box actually has, produces hypotheses in the SAME shape the external backtest emits, and
hands them to the SAME ten-gate gauntlet. No new door, no separate certification path, no relaxed
bar -- the only thing that changes is that the gauntlet finally has something to judge that is not
a session-range breakout.

WIRING THE INPUTS IS THE WORK. Most of these families refuse without their input, correctly, so a
sweep that does not FIND those inputs would report fourteen refusals and look like the families
were the problem. So this resolves each one from what the desk already records:

    peer / factors     other symbols' H1 in data/universe
    spread series      the tick tape's own bid/ask, resampled to the bar clock
    flow imbalance     tick upticks vs downticks, from the same tape
    macro              data/macro_state.json
    COT                data/cot*.json

An input that genuinely is not there is reported as an ACQUISITION gap, which is a different and
more actionable statement than "this family produced nothing".
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
# THE REPO ROOT TOO, or this entry point only works from one directory. The hourly pipeline runs
# it as `cd C:\opt\quant\desks\mt5 && py -3 research\orthogonal_sweep.py`, which puts
# `desks/mt5/research` on sys.path and NOT the root -- so `mt5desk.families_orthogonal` ->
# `mt5desk.families` -> `libs.research.bar_span` raised ModuleNotFoundError on the desk box, and
# the orthogonal falsification sweep contributed NOTHING to the docket for 14 consecutive hourly
# runs (measured 2026-08-27). It was invisible because the failure surfaced as
# "orthogonal frontier TIMED OUT after 25m", a resource story, while the log held an import
# traceback; and it never reproduced here, where the pipeline's own cwd IS the root.
# `parents[3]` is the repo root: parents are [research, mt5, desks, root].
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
UNIVERSE = BASE / "data" / "universe"
TAPE = BASE / "data" / "tape" / "ticks"
OUT = BASE / "data" / "hypotheses" / "orthogonal_candidates.json"

#: Screen bar, deliberately LOOSE. This is a screen, not a verdict -- the ten gates are the door,
#: and a tight screen here would pre-reject candidates the canonical policy never got to judge.
MIN_TRADES = 30
MIN_EXP_R = 0.0
#: THE GAUNTLET'S OWN NUMBER, quoted -- not a new bar (principal 2026-08-27: "it must all
#: always be redirected to testable candidates"). `external_gauntlet` drops any cell whose daily
#: series holds fewer than 60 observations, because CPCV with purge+embargo and the walk-forward
#: folds cannot judge less. A cell that cannot reach 60 TRADING DAYS is therefore untestable by
#: construction and proposing it spends the hour's compute on something no gate can ever rule on.
#: Trades are not days: measured 2026-08-27, event_reaction emitted 113 cells that all cleared
#: MIN_TRADES and every one died at under_60_days -- multiple trades per event, on ~70 event days
#: in six years. This routes the search to ground it can actually settle; it screens nothing on
#: quality and rejects nothing for being weak.
MIN_TRADE_DAYS = 60


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


# MEMORY IS A THROUGHPUT RAIL, NOT A UNIVERSE LIMIT.  ``maxsize=None`` retained every complete
# H1 dataframe in the 293-symbol sweep.  The process climbed until Windows terminated it after
# ~23 minutes, before OUT was written, so the gauntlet kept consuming yesterday's artifact.
# Sixteen holds the current symbol plus the twelve-factor working set; eviction changes only
# residency and every symbol is still loaded and tested in the same pass.
@lru_cache(maxsize=16)
def _bars(symbol: str):
    import pandas as pd
    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _tape_series(symbol: str, index):
    """(spread, flow) on the bar clock, from the venue's own ticks. (None, None) if no tape."""
    import pandas as pd
    d = TAPE / symbol
    if not d.exists():
        return None, None
    frames = []
    for f in sorted(d.glob("*.parquet"))[-30:]:
        try:
            frames.append(pd.read_parquet(f, columns=["ts", "bid", "ask"]))
        except Exception:
            continue
    if not frames:
        return None, None
    t = pd.concat(frames, ignore_index=True)
    t["ts"] = pd.to_datetime(t["ts"], utc=True)
    t = t.dropna(subset=["bid", "ask"]).sort_values("ts").set_index("ts")
    spread = (t["ask"] - t["bid"]).resample("1h").mean()
    mid = ((t["ask"] + t["bid"]) / 2.0)
    # Flow proxy: net sign of mid changes within the bar. Not true aggressor data -- the tape has
    # no trade side -- so it is labelled a proxy rather than passed off as order flow.
    step = mid.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    flow = step.resample("1h").sum()
    return spread.reindex(index).ffill(), flow.reindex(index).ffill()


#: FRED series usable WITHOUT vintages: market-observed daily prints whose publication lag is a
#: day. The monthly economic releases in the same file (UNRATE, CPIAUCSL, PAYEMS, INDPRO, ...) are
#: deliberately excluded -- their observation DATE precedes publication by weeks, so joining them
#: on that date conditions a 2019 bar on a number nobody had until 2019+30d. That is the
#: conditioning-variable look-ahead this desk has already paid for once, and it fails toward a
#: FALSE POSITIVE, which no gate downstream can catch. They become admissible only through
#: `data/vintages/` (ALFRED, revision-aware), which currently covers three series.
DAILY_MACRO_SERIES = ("DTWEXBGS", "DGS10", "DGS2", "T10Y2Y", "VIXCLS", "SOFR", "DFF",
                      "BAMLH0A0HYM2", "DCOILWTICO")
#: One day between a print and a bar that may condition on it. Never zero.
MACRO_PUBLICATION_LAG_D = 1
#: Observations before a trailing rank means anything. A rank over 20 points is noise wearing a
#: percentile.
MACRO_RANK_MIN_OBS = 250


def _macro_series(index, name: str | None = None):
    """A POINT-IN-TIME macro regime series on the bar clock, or None. Never a broadcast scalar.

    WHAT THIS REPLACES (measured 2026-08-28). The old reader took `desks/mt5/data/macro_state.json`
    and kept its top-level scalars -- but that file is nested (`updated`/`series`/`states`/
    `differentials`), so there were none, it returned None, and `macro_conditional` ran with
    `macro=None` and produced zero signals on all 297 symbols. That zero was filed as
    `no-signals (a macro state series)`, which reads as "the desk has no macro data" while
    `data/fred_macro.json` held 22 dated series and the FRED collector was appending to it daily.

    AND THE FALLBACK WAS WORSE THAN THE FAILURE. Had a top-level scalar existed, the reader would
    have broadcast TODAY's value across every bar in history: constant, so `macro > regime_high`
    puts every bar in one regime and the family degenerates to unconditional -- and it applies a
    2026 macro reading to a 2019 bar, which is a look-ahead in the conditioning variable.

    The regime is a TRAILING PERCENTILE RANK: each point ranked only against its own past, so the
    value is in [0,1] around the family's own 0.5 threshold and no future observation touches it.
    The series is then lagged by a publication day and forward-filled onto the bar clock, so a bar
    is conditioned only on prints that existed before it.
    """
    import pandas as pd
    doc = _read(BASE.parent.parent / "data" / "fred_macro.json")
    series_map = (doc or {}).get("series")
    if not isinstance(series_map, dict):
        return None
    for key in ((name,) if name else DAILY_MACRO_SERIES):
        rows = series_map.get(key)
        if not isinstance(rows, list) or len(rows) < MACRO_RANK_MIN_OBS:
            continue
        try:
            stamps = pd.to_datetime([r[0] for r in rows], utc=True, errors="coerce")
            values = pd.to_numeric([r[1] for r in rows], errors="coerce")
        except (TypeError, IndexError, ValueError):
            continue
        s = pd.Series(values, index=stamps).dropna().sort_index()
        s = s[~s.index.duplicated(keep="last")]
        if len(s) < MACRO_RANK_MIN_OBS:
            continue
        rank = s.expanding(min_periods=MACRO_RANK_MIN_OBS).rank(pct=True).dropna()
        if rank.empty:
            continue
        rank.index = rank.index + pd.Timedelta(days=MACRO_PUBLICATION_LAG_D)
        out = rank.reindex(rank.index.union(index)).ffill().reindex(index)
        return out if out.notna().sum() >= MACRO_RANK_MIN_OBS else None
    return None


def _macro_series_name() -> str | None:
    """Which series `_macro_series` will pick -- recorded in the candidate's identity so the
    gauntlet rebuilds the SAME conditioning variable rather than whatever is first today."""
    doc = _read(BASE.parent.parent / "data" / "fred_macro.json")
    series_map = (doc or {}).get("series")
    if not isinstance(series_map, dict):
        return None
    return next((k for k in DAILY_MACRO_SERIES
                 if isinstance(series_map.get(k), list)
                 and len(series_map[k]) >= MACRO_RANK_MIN_OBS), None)


@lru_cache(maxsize=32)
def _cot_frame(symbol: str | None = None):
    import pandas as pd

    # The repository already owns 26 years of point-in-time CFTC history. It was registered and
    # screened elsewhere but this gauntlet reader ignored it, so a COT miner could produce a real
    # candidate that always rebuilt with `cot=None`. Downsample the daily forward-filled cache to
    # one weekly observation; repeated daily values must not masquerade as independent reports.
    cache = BASE.parent.parent / "data" / "cot_zcache.parquet"
    if symbol and cache.exists():
        try:
            frame = pd.read_parquet(cache, columns=[symbol])
            series = frame[symbol].astype(float).dropna().resample("W-FRI").last().dropna()
            if len(series) >= 52:
                return series.rename("net").to_frame()
        except Exception:
            pass
    for name in ("cot_tff.json", "cot.json", "cot_disagg.json"):
        doc = _read(BASE / "data" / name)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        try:
            df = pd.DataFrame(rows)
            for tcol in ("date", "report_date", "as_of"):
                if tcol in df.columns:
                    df.index = pd.to_datetime(df[tcol], utc=True, errors="coerce")
                    break
            else:
                continue
            for ncol in ("net", "noncomm_net", "net_position"):
                if ncol in df.columns:
                    return df[[ncol]].rename(columns={ncol: "net"}).dropna()
        except Exception:
            continue
    return None


def _legs(symbol: str) -> tuple[str, str] | None:
    """(base, quote) for a six-letter FX/metal/crypto pair, else None. Names only, never prices."""
    return (symbol[:3], symbol[3:]) if len(symbol) == 6 and symbol.isalpha() \
        and symbol.isupper() else None


def _peer_symbol(sym: str, symbols: list[str], meta: dict) -> str | None:
    """The most RELATED instrument to `sym`, chosen structurally -- never alphabetically.

    THE DEFECT THIS REPLACES (measured 2026-08-28). The peer was `[s for s in symbols if s !=
    sym][:12]` over an alphabetically sorted universe, so `relative_value` and
    `correlation_regime` ran XAUUSD against **3M** -- the industrial conglomerate share CFD --
    and every FX cross against whichever of `3M / ADAUSD / ADP / AMD / AT&T` came first. Those two
    families "ran on 297 symbols" each, which read as healthy coverage; what they actually
    measured was ~590 economically arbitrary pairings. That is worse than wasted compute: a
    survivor out of XAUUSD-vs-3M is a spurious pairing that would consume a forward slot and
    corrupt the prior, and the real mechanism -- gold against its own currency and metal
    complex, a JPY cross against another JPY cross -- was never tested, so the family would
    eventually be graveyarded on evidence that was never about the mechanism. That is the FALSE
    NULL direction, the one no gate here catches, because a killed axis raises no alert.

    STRUCTURAL, SO THERE IS NOTHING TO LEAK. Selection reads only the symbol string and the
    registry's `asset_class` and `bars` -- no returns, no correlations, no full-sample anything.
    A peer picked by measured correlation would be a conditioning variable chosen with knowledge
    of the whole sample, which is exactly the look-ahead this desk has paid for before.

    Preference order: shares the non-USD leg (the leg that distinguishes the pair) > shares any
    leg > same asset class. Ties break on the longest history, so the peer has bars to give.
    """
    def _bars_of(s: str) -> int:
        row = meta.get(s) if isinstance(meta, dict) else None
        return int((row or {}).get("bars") or 0)

    others = [s for s in symbols if s != sym]
    legs = _legs(sym)
    if legs:
        base, quote = legs
        distinct = [leg for leg in (base, quote) if leg != "USD"] or [base, quote]
        for wanted in (distinct, [base, quote]):
            pool = [s for s in others
                    if (lg := _legs(s)) and any(leg in lg for leg in wanted)]
            if pool:
                return max(pool, key=_bars_of)
    cls = (meta.get(sym) or {}).get("asset_class") if isinstance(meta, dict) else None
    pool = [s for s in others
            if cls and (meta.get(s) or {}).get("asset_class") == cls]
    return max(pool, key=_bars_of) if pool else (max(others, key=_bars_of) if others else None)


#: Factor instruments for the residual families. Eight spans the latent forces the mechanism
#: names (USD, JPY, risk, rates, metals, energy) while staying inside `_bars`' 16-frame cache
#: beside the swept symbol and its peer -- the basket is loaded ONCE per sweep rather than
#: rebuilt per symbol, so this is strictly less resident memory than the code it replaces.
FACTOR_BASKET_MAX = 8


def _factor_symbols(symbols: list[str], meta: dict) -> list[str]:
    """One diversified factor basket for the whole sweep, spanning the asset classes present.

    `pca_residual` REFUSES below four factors on purpose ("a universe factor extracted from two
    peers is just a pair spread wearing a bigger name") and `cross_asset_residual` wants 2+.
    They were being handed two alphabetical neighbours and nothing at all respectively, so one
    family produced a pair spread under a grander name and the other returned [] on every symbol
    in the universe -- filed as `no-signals (4+ factor instruments' H1)`, a message that quotes
    the family's own requirement while the sweep held the data three lines away and never passed
    it. Absence read as a clean verdict, on the one family built to break the concentration that
    blocks N_eff.

    Latent factors must SPAN, so take the longest-history instrument from each asset class before
    deepening any one of them; classes are read from the registry, never listed here.
    """
    def _bars_of(s: str) -> int:
        row = meta.get(s) if isinstance(meta, dict) else None
        return int((row or {}).get("bars") or 0)

    # A THIN FACTOR TRUNCATES EVERY RESIDUAL. The factor matrix is an INTERSECTION -- one
    # 8,079-bar instrument in the basket threw away ~40,000 bars of XAUUSD history for every
    # symbol swept. Members must carry at least half the universe's median history; the floor is
    # derived from the data, so it moves as the universe does and hardcodes no horizon. A class
    # whose every member is thin loses its seat rather than costing everyone their history:
    # spanning is about the latent forces, and an instrument with no history carries none of them.
    depths = sorted(b for b in (_bars_of(s) for s in symbols) if b > 0)
    floor = (depths[len(depths) // 2] * 0.5) if depths else 0.0
    by_class: dict[str, list[str]] = {}
    for s in symbols:
        cls = str((meta.get(s) or {}).get("asset_class") or "") if isinstance(meta, dict) else ""
        by_class.setdefault(cls or "unclassified", []).append(s)
    basket: list[str] = []
    for cls in sorted(by_class):
        best = max(by_class[cls], key=_bars_of)
        if _bars_of(best) >= max(floor, 1.0):
            basket.append(best)
    # Deepen with the longest-history remainder only after every class has a representative.
    rest = sorted((s for s in symbols if s not in basket), key=_bars_of, reverse=True)
    basket.extend(rest[:max(0, FACTOR_BASKET_MAX - len(basket))])
    return sorted(basket[:FACTOR_BASKET_MAX], key=_bars_of, reverse=True)


#: Families this sweep deliberately does not source, and why. DECLARED, never silent: each of
#: these would otherwise return [] on every symbol and be filed as a data gap, which is how
#: `pca_residual` hid for its whole existence. An entry here is a statement that the input is not
#: this organ's to resolve -- not that the family is dead. Anything NOT listed and not wired is a
#: defect, and `test_every_family_needing_an_input_is_wired_to_one` fails on it.
NOT_SOURCED_HERE = {
    "discovered": "the primitive is named by edge_search at search time; this sweep enumerates "
                  "families, it does not run the search that would name one",
    "ensemble": "its members are named on the candidate by weak_signal_compiler, which chooses "
                "them from the gauntlet's own failed-on-power cells; a sweep that enumerated "
                "ensembles over bars would be inventing member lists, and the family refuses "
                "without a runner for exactly that reason",
    "formula": "the expression is named by alpha_evolution's genetic search, which charges every "
               "expression it tried; a sweep that enumerated expressions here would be a second "
               "uncharged search over the same grammar",
    "lead_lag": "the driver and the lag are measured by cross_asset_graph on the information "
                "graph; a sweep that paired every symbol with every other would be an uncharged "
                "search over pairs",
    "style_premia": "style_premia_sweep supplies the instrument's own rollover (broker_swaps) and "
                    "the risk driver and charges the whole style x instrument grid itself",
}


def _unsuppliable(fn, supplied: dict) -> str | None:
    """The required keyword-only args this sweep cannot supply, or None when it can run.

    A FAMILY THAT CRASHES IS NOT A FAMILY WITH NO DATA. `calendar_month` takes `active_month` and
    `side_bias` as REQUIRED keyword-only arguments -- its month and direction are source evidence,
    not searched parameters -- so calling it blind raised TypeError on all 297 symbols, and the
    handler filed those 297 crashes into `input_gaps` beside genuine acquisition gaps. A bug
    wearing an input-gap costume is a bug nobody investigates. Detected by signature rather than
    by a family list, so a new family with required evidence is classified the same way on day one.
    """
    import inspect
    missing = [name for name, p in inspect.signature(fn).parameters.items()
               if p.kind is p.KEYWORD_ONLY and p.default is p.empty and name not in supplied]
    return ", ".join(missing) if missing else None


@lru_cache(maxsize=1)
def _event_index():
    """Recover point-in-time event timestamps already persisted by the calendar miner."""
    import pandas as pd

    root = BASE / "data" / "intelligence" / "ff_calendar_vintage"
    values = []
    for path in sorted(root.glob("*.json*"))[-60:] if root.exists() else []:
        doc = _read(path)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows", [])
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            # `event_date` FIRST, because it is the key the calendar miner actually writes and
            # it was absent from this list -- so the reader parsed 56 vintage files and recovered
            # zero timestamps, and every event_reaction cell returned no signals with no error
            # (2026-08-28). The scheduled event time is the right anchor: `found_at`/`captured_at`
            # record when THIS DESK learned of the event, which is a fact about our polling, not
            # about the market.
            raw = next((row.get(k) for k in ("event_date", "date", "datetime", "timestamp",
                                             "time") if row.get(k)), None)
            if raw is not None:
                values.append(raw)
    idx = pd.to_datetime(values, utc=True, errors="coerce")
    return pd.DatetimeIndex(idx.dropna().unique()).sort_values() if len(idx) else None


def sweep() -> dict:
    from mt5desk.engine import Costs, run_backtest
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES

    meta = _read(UNIVERSE / "universe.json") or {}
    symbols = sorted(p.stem.replace("_H1", "") for p in UNIVERSE.glob("*_H1.parquet"))
    hypotheses: list[dict] = []
    gaps: dict[str, int] = {}
    errors: dict[str, int] = {}
    ran: dict[str, int] = {}
    untestable: dict[str, int] = {}
    #: family -> pooled observations from cells individually short of MIN_TRADE_DAYS.
    pooled: dict[str, dict] = {}

    # ONE BASKET FOR THE SWEEP, chosen before the loop. Rebuilding a factor set per symbol reread
    # the same parquets 297 times; this loads them once and keeps them resident in `_bars`' cache.
    factor_syms = _factor_symbols(symbols, meta)

    for _sym_i, sym in enumerate(symbols):
        # CHECKPOINT WHAT IS ALREADY DONE. See _write_report: the stage timeout is shorter than
        # a full sweep, so anything not written by now is written by nobody.
        if _sym_i:
            _write_report(_build_report(symbols[:_sym_i], ran, gaps, errors, untestable,
                                        hypotheses), partial=True)
        df = _bars(sym)
        if df is None or len(df) < 2000:
            continue
        # THE PEER IS THE RELATED INSTRUMENT, THE FACTORS ARE THE UNIVERSE. Both were
        # alphabetical before (`[s for s in symbols if s != sym][:12]`), which paired XAUUSD with
        # 3M and handed the residual families two arbitrary neighbours; `pca_residual` was handed
        # nothing at all and returned [] on all 297 symbols. See _peer_symbol / _factor_symbols.
        peer_sym = _peer_symbol(sym, symbols, meta)
        peer_df = _bars(peer_sym) if peer_sym else None
        factor_names = [s for s in factor_syms if s != sym]
        factor_dfs = [f for f in (_bars(s) for s in factor_names) if f is not None]
        spread, flow = _tape_series(sym, df.index)
        macro = _macro_series(df.index)
        cot = _cot_frame(sym)
        events = _event_index()

        kwargs_by_family = {
            "carry": {"symbol": sym},
            "relative_value": {"peer": peer_df},
            "correlation_regime": {"peer": peer_df},
            "cross_asset_residual": {"factors": factor_dfs},
            # NEVER PASSED BEFORE. Absent from this map, `pca_residual` ran with factors=None,
            # hit its own `len(factors) < 4` refusal and returned [] on every symbol in the
            # universe -- reported as a data gap while the data sat in `factor_dfs`.
            "pca_residual": {"factors": factor_dfs},
            "liquidity_regime": {"spread_series": spread},
            "orderflow_imbalance": {"flow": flow},
            "macro_conditional": {"macro": macro},
            "cot_positioning": {"cot": cot},
            "event_reaction": {"events": events},
        }
        # Runtime objects cannot be JSON identities. Persist exact provenance needed to rebuild
        # the same candidate in the universal gauntlet; an empty params object previously made
        # peer/factor candidates silently rebuild with no inputs and therefore no trades.
        identity_by_family = {
            "carry": {"input_symbol": sym},
            "relative_value": {"peer_symbol": peer_sym} if peer_sym else {},
            "correlation_regime": {"peer_symbol": peer_sym} if peer_sym else {},
            "cross_asset_residual": {"factor_symbols": factor_names},
            "pca_residual": {"factor_symbols": factor_names},
            "liquidity_regime": {"input_source": "fusion_tick_tape"},
            "orderflow_imbalance": {"input_source": "fusion_tick_tape"},
            # THE SERIES, NOT "macro_state". `input_source: macro_state` named a file the reader
            # no longer uses and did not say WHICH quantity conditioned the cell, so the gauntlet
            # could not rebuild the same candidate.
            "macro_conditional": {"input_source": f"fred:{_macro_series_name()}",
                                  "transform": "trailing_pct_rank",
                                  "publication_lag_d": MACRO_PUBLICATION_LAG_D},
            "cot_positioning": {"input_source": "cot_point_in_time"},
            "event_reaction": {"input_source": "ff_calendar_vintage"},
        }
        m = meta.get(sym, {}) if isinstance(meta, dict) else {}
        try:
            # ONE COST MODEL, AND from_symbol IS IT (2026-09-01). This built `Costs` by hand
            # and so carried the two defects external_gauntlet.costs_for already documents and
            # fixed on its own call site:
            #   * no `quote_per_account`, so commission was charged as though every symbol were
            #     quoted in the account's currency -- on this EUR account that is USDJPY 184.31x,
            #     CADJPY 8.21x, EURJPY 6.19x undercharged, i.e. every JPY cross in the live family;
            #   * commission_per_lot=3.50, a ROUND-TURN figure in a PER-SIDE field ($7.00 charged
            #     against a $4.50 contract). from_symbol's default is Fusion Zero's published
            #     USD 2.25 per lot per side.
            # A sweep that prices candidates differently from the gauntlet that judges them is two
            # brokers inside one pipeline: the sweep ranks and filters on numbers the certifying
            # door will never agree with. Same constructor, same numbers, one truth.
            costs = Costs.from_symbol(m)
        except (TypeError, ValueError):
            continue

        for fam, fn in sorted(ORTHOGONAL_FAMILIES.items()):
            kw = kwargs_by_family.get(fam, {})
            if fam in NOT_SOURCED_HERE:
                key = f"{fam}:not-sourced-here ({NOT_SOURCED_HERE[fam]})"
                gaps[key] = gaps.get(key, 0) + 1
                continue
            # ASK BEFORE CALLING. A family whose required evidence this sweep has no source for
            # is an acquisition gap, not a crash -- see _unsuppliable.
            if (need_args := _unsuppliable(fn, kw)):
                key = f"{fam}:needs-source-evidence ({need_args})"
                gaps[key] = gaps.get(key, 0) + 1
                continue
            try:
                sigs = fn(df, **kw)
            except Exception as exc:
                # ERRORS ARE THEIR OWN CATEGORY. Filed into `input_gaps` these read as missing
                # data and nobody looks; 297 identical TypeErrors sat there for exactly that
                # reason. A crash is a defect in this desk's code, and it says so here.
                key = f"{fam}:{type(exc).__name__}: {exc}"
                errors[key] = errors.get(key, 0) + 1
                continue
            if not sigs:
                need = FAMILY_INPUTS.get(fam, ("unknown", None))[0]
                key = f"{fam}:no-signals ({need})"
                gaps[key] = gaps.get(key, 0) + 1
                continue
            ran[fam] = ran.get(fam, 0) + 1
            try:
                res = run_backtest(df, sigs, costs)
            except Exception:
                continue
            trades = list(res.trades)
            if len(trades) < MIN_TRADES:
                continue
            # TESTABILITY, REPORTED BY FAMILY. Never silent: a family that is structurally
            # untestable at this parameterization is a fact about the SEARCH worth seeing.
            _days = len({t.entry_time.date() for t in trades})
            if _days < MIN_TRADE_DAYS:
                key = f"{fam}:untestable ({_days} trading days < {MIN_TRADE_DAYS} the gates need)"
                untestable[key] = untestable.get(key, 0) + 1
                # POOL IT INSTEAD OF DROPPING IT. The 60-day floor is the gauntlet's own CPCV
                # requirement and is not negotiable -- but it is a requirement about OBSERVATIONS,
                # and a cell is not the only unit that can carry them. Measured 2026-09-04: six
                # families were structurally untestable, every cell missing by 2-27 days
                # (pca_residual by TWO), while their cells sat on DIFFERENT SYMBOLS whose trading
                # days are largely disjoint. The observations existed; they were just split across
                # cells and thrown away one cell at a time.
                #
                # This is the same move family_evidence already makes for FORWARD verdicts,
                # applied to backtest: the FAMILY carries the evidence, members inherit. Pooling
                # weakens nothing -- CPCV still receives its 60+ distinct days, they simply come
                # from the family rather than from one parameterization.
                _pool = pooled.setdefault(fam, {"days": set(), "rs": [], "members": []})
                _pool["days"].update(t.entry_time.date() for t in trades)
                _pool["rs"].extend(t.r_multiple for t in trades)
                _pool["members"].append(f"{sym}:{_days}d")
                continue
            rs = [t.r_multiple for t in trades]
            exp = sum(rs) / len(rs)
            if exp <= MIN_EXP_R:
                continue
            cum, peak, dd = 0.0, 0.0, 0.0
            for r in rs:
                cum += r
                peak = max(peak, cum)
                dd = min(dd, cum - peak)
            hypotheses.append({
                "symbol": sym, "family": fam, "params": identity_by_family.get(fam, {}),
                "n": len(trades), "exp_r": round(exp, 4), "max_dd_r": round(dd, 2),
                "source": f"orthogonal_sweep:{fam}",
                "mechanism_status": "NAMED",
                "mechanism_note": FAMILY_INPUTS.get(fam, ("", None))[0],
            })

    # FAMILIES THE POOL RESCUES. Emitted as FAMILY-level candidates, never disguised as a cell:
    # `pooled: True` and the member list travel with them, so nothing downstream can mistake
    # family evidence for a single parameterization's certificate.
    for _fam, _p in sorted(pooled.items()):
        _nd = len(_p["days"])
        if _nd < MIN_TRADE_DAYS or not _p["rs"]:
            continue
        _exp = sum(_p["rs"]) / len(_p["rs"])
        if _exp <= MIN_EXP_R:
            continue
        _cum = _peak = _dd = 0.0
        for _r in _p["rs"]:
            _cum += _r
            _peak = max(_peak, _cum)
            _dd = min(_dd, _cum - _peak)
        hypotheses.append({
            "family": _fam, "symbol": "POOLED", "pooled": True,
            "members": _p["members"], "trades": len(_p["rs"]), "trade_days": _nd,
            "exp_r": round(_exp, 5), "max_dd_r": round(_dd, 3),
            "why": (f"{len(_p['members'])} cells individually below {MIN_TRADE_DAYS} trading days "
                    f"pool to {_nd} distinct days across different symbols. CPCV gets its "
                    f"observations from the FAMILY; members inherit, exactly as family_evidence "
                    f"already does for forward verdicts."),
        })

    return _build_report(symbols, ran, gaps, errors, untestable, hypotheses)


def _build_report(symbols, ran, gaps, errors, untestable, hypotheses) -> dict[str, object]:
    return {"swept_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "symbols": len(symbols), "families_ran": ran,
            "input_gaps": gaps,
            "family_errors": errors,
            "family_errors_note": (
                "exceptions raised BY THIS DESK'S CODE while calling a family. "
                "Distinct from input_gaps, which are data the box does not have: "
                "an error here is a defect to FIX, and folding the two together is "
                "how 297 identical TypeErrors read as a missing feed."),
            "untestable_by_family": untestable,
            "untestable_note": (
                f"cells that traded but on fewer than {MIN_TRADE_DAYS} distinct days -- the "
                f"gauntlet cannot judge them (CPCV purge+embargo and walk-forward folds need "
                f"the observations), so proposing them wastes the cycle. This is a TESTABILITY "
                f"route, not a quality screen: nothing here rejects a cell for being weak."),
            "hypotheses": hypotheses}


def _write_report(report: dict[str, object], *, partial: bool) -> None:
    """Write the sweep artifact, atomically. Called after every symbol, not only at the end.

    SAME DEFECT AS edge_search, SAME SHAPE. The sweep built its whole report and wrote it once
    after the symbol loop, while the pipeline allots the search a 20-minute remote stage that
    `timeout ssh` enforces by killing the client -- so a run longer than the slot left the
    artifact untouched no matter how much work it did. MEASURED 2026-09-03:
    orthogonal_candidates.json was 15.5 hours stale with orthogonal_sweep alive throughout, which
    the health report could only describe as "alive but has produced nothing".

    Temp-file-and-replace so a kill mid-write cannot leave a torn artifact for merge_hypotheses
    to read, and `partial` is stamped so a consumer can tell an interrupted sweep from a finished
    one rather than inferring it from a timestamp (L1.28a).
    """
    import os as _os
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = dict(report)
    body["partial"] = partial
    tmp = OUT.with_suffix(OUT.suffix + ".tmp")
    tmp.write_text(json.dumps(body, indent=1, default=str), "utf-8")
    _os.replace(tmp, OUT)


def main() -> int:
    report = sweep()
    _write_report(report, partial=False)
    hyp = report["hypotheses"]
    print(f"orthogonal sweep: {report['symbols']} symbol(s), "
          f"{len(report['families_ran'])} family(ies) produced signals, "
          f"{len(hyp)} candidate(s) passed the loose screen")
    for fam, n in sorted(report["families_ran"].items()):
        got = sum(1 for h in hyp if h["family"] == fam)
        print(f"   {fam:24} ran on {n:>3} symbol(s) -> {got} candidate(s)")
    if report["input_gaps"]:
        print("  input gaps (ACQUISITION tasks, not miner failures):")
        for k, n in sorted(report["input_gaps"].items())[:6]:
            print(f"   {k}  x{n}")
    if report["family_errors"]:
        print("  FAMILY ERRORS (defects in this desk's code -- fix, do not acquire):")
        for k, n in sorted(report["family_errors"].items())[:6]:
            print(f"   {k}  x{n}")
    return 0


def _cli_main() -> int:
    try:
        from research.job_lock import exclusive_job
    except ModuleNotFoundError:            # entrypoint put research/ on the path, not desks/mt5
        from job_lock import exclusive_job

    # TIGHTENED FROM AN OBSERVED RUN, which is what the previous note asked for. The admission
    # precondition was 800MB while the job's own measured peak was 1055MB RSS -- so it could be
    # admitted onto a box that could not hold it, which is precisely the OOM this gate exists to
    # prevent, and the box logged 221 OOM kills in three days (GAP 141). Re-measured 2026-08-28
    # on contabo-mt5 with the peer/factor wiring live (eight factor frames resident instead of a
    # per-symbol rebuild of two): peak 1157MB RSS, run completing. 1250 sits above that observed
    # peak rather than below it. Standing down is cheap by this module's own argument -- hourly
    # trigger, per-cell cache resumes rather than restarts -- while admission that does not fit
    # costs the hour AND the terminal holding live positions.
    with exclusive_job("orthogonal_sweep", need_mb=1250) as acquired:
        return main() if acquired else 75


if __name__ == "__main__":
    raise SystemExit(_cli_main())
