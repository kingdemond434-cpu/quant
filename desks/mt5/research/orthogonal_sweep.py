"""ORTHOGONAL SWEEP -- every non-breakout family, on every chart, across the universe.

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

    peer / factors     other symbols, ON THE SAME CHART, in data/universe
    spread series      the tick tape's own bid/ask, resampled to the bar clock
    flow imbalance     tick upticks vs downticks, from the same tape
    macro              data/macro_state.json
    COT                data/cot*.json

An input that genuinely is not there is reported as an ACQUISITION gap, which is a different and
more actionable statement than "this family produced nothing".

EVERY CHART, NOT ONE (principal 2026-09-05: "m1 m5 m15 m30 h1 h4 d1 all possible every type of
mechanism n chart for all always ... this was a serious flaw we had abt the h1 only"). This swept
`*_H1.parquet` and nothing else, on ~250 instruments. Gold alone had M1/M5/M15, and only because
`research/fetch_gold_scalp.py` was hand-written for that one symbol. The cost was structural: no
family could express an intraday mechanism on anything but gold, the scalp lane existed on XAUUSD
alone because it was the only symbol with fine bars, and every sub-hour question -- including
"was this event already priced?" -- resolved to UNMEASURABLE for want of bars fine enough to see
the answer in. The unit of the sweep is now the (SYMBOL, CHART) pair, taken from the registry's
own `timeframes` list per symbol.

AND THE CHART IS PART OF THE CELL'S IDENTITY, which is the whole reason this is a careful change
rather than a find-and-replace. The gauntlet's series cache is content-addressed and the
certificate key is derived from cell identity, so an identity that does not name the chart makes
`XAUUSD.carry` on M5 and on H1 THE SAME CELL: the cache serves one result for the other and a
certificate minted on one is claimed by the other, with every number in the record internally
consistent and no gate able to see it. `timeframe` therefore rides in the candidate's `params`
(the desk's existing spelling -- `scalp_gauntlet.recipe` has always written it there) and is
absent only for H1, which keeps every id, certificate and clock this desk already holds
byte-identical. `frontier_identity.cell_id` renders it as an `@M5` suffix on the cell name.

NO GATE MOVES BECAUSE THE SWEEP GOT WIDER. `policy/gate_spec.yaml` pins `fixed_trial_count` and
`fixed_variance_of_sharpes` precisely so "a candidate must not face a higher bar for having been
scheduled into a wider sweep" -- the spec records sr0 running 0.3786 at 597 charged trials and
1.3593 at 5,963 for the SAME cell. Seven charts is therefore strictly more candidates at an
unchanged bar. The screens here (MIN_TRADES, MIN_EXP_R, MIN_TRADE_DAYS) are untouched, and
MIN_TRADE_DAYS counts TRADING DAYS, which is chart-independent by construction.
"""
from __future__ import annotations

import json
import sys
from collections import OrderedDict
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

# THE LADDER COMES FROM THE REGISTRY MODULE, NEVER FROM A LIST HERE. A second spelling of which
# charts exist is how a sweep quietly stops hunting one of them; `universe_registry` is the same
# authority `expand_universe` fetches against and `families` reads bar spans from.
from mt5desk.universe_registry import REFERENCE_TIMEFRAME as _REFERENCE_TF  # noqa: E402
from mt5desk.universe_registry import TIMEFRAMES as _LADDER  # noqa: E402

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

#: Bars an HOURLY chart must carry before this sweep will look at it. Unchanged, and deliberately
#: looser than the universe's own 3,000-bar admission floor: this is a screen, not a door.
#:
#: THE SAME NUMBER ON SEVEN CHARTS IS SEVEN DIFFERENT RULES. 2,000 bars is four months of H1 and
#: EIGHT YEARS of D1, so a flat floor would have silently emptied the daily lane on every symbol
#: -- the swing lane, which is the one the principal named -- while reading in the source like a
#: single uniform rule. `min_bars_for` re-expresses this span on each chart and is the identity
#: at H1, so the hourly sweep sees exactly the universe it saw before.
SWEEP_MIN_H1_BARS = 2000


def _min_bars(timeframe: str) -> int:
    from mt5desk.universe_registry import min_bars_for
    return min_bars_for(timeframe, h1_floor=SWEEP_MIN_H1_BARS)


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


# MEMORY IS A THROUGHPUT RAIL, NOT A UNIVERSE LIMIT.  ``maxsize=None`` retained every complete
# H1 dataframe in the 293-symbol sweep.  The process climbed until Windows terminated it after
# ~23 minutes, before OUT was written, so the gauntlet kept consuming yesterday's artifact.
#
# A FRAME COUNT IS THE WRONG UNIT ONCE THERE ARE SEVEN CHARTS, and this is the re-derivation the
# ladder forces. `lru_cache(maxsize=16)` was sized as "the current symbol plus the twelve-factor
# working set" and that arithmetic was sound while every frame was H1: six years of hourly bars
# is ~54,000 rows (measured on this tree: EURUSD_H1 is 53,899), so sixteen frames is ~34 MB and
# the job's measured 1,157 MB peak sat comfortably inside its 1,250 MB admission. The same
# sixteen frames of M1 would be ~1.4 GB -- more than the whole job is admitted for -- because an
# M1 frame holds sixty bars per H1 bar. A cache that counts FRAMES therefore stops being a
# constant and becomes a function of which chart the sweep happens to be on.
#
# So the budget is counted in BARS, which is what actually costs memory, and it is derived from
# the largest legitimate working set rather than picked:
#
#     the swept symbol                                    1 frame
#     its peer (relative_value, correlation_regime)       1 frame
#     the factor basket (FACTOR_BASKET_MAX)               8 frames
#                                                        -----------
#                                                        10 frames
#
#     10 frames x ~54,000 H1 rows                    = 540,000 rows
#     rounded, with room for the next symbol's peer  = 600,000 rows
#
# At H1 that is the same residency the sixteen-frame cache had, so nothing about the hourly sweep
# changes. On M1 a single frame can exceed the whole budget, so the cache holds it ALONE -- which
# is correct, because the peer and factor families are declared H1-and-slower in
# `families_orthogonal.FAMILY_TIMEFRAMES` (a bar-for-bar join below the hour measures
# non-synchronous quoting, not a common factor), so on the fine charts the working set genuinely
# IS one frame. The most-recently-used entry is never evicted for exceeding the budget on its
# own: evicting it would re-read the parquet on the very next call, which is precisely the silent
# thrash an under-sized cache causes.
BAR_CACHE_ROWS = 600_000
_BAR_CACHE: OrderedDict[tuple[str, str], object] = OrderedDict()


def _cache_rows(frame) -> int:
    try:
        return int(len(frame))
    except TypeError:
        return 0


def _held_rows() -> int:
    """Rows resident, COUNTED rather than tracked. A running total and the dict it describes are
    two records of one fact, and this desk has paid for that shape before: a caller that clears
    the cache without resetting the counter leaves the cache evicting to one entry forever, which
    presents as a slow box and nothing else. The dict holds a handful of frames, so counting is
    free."""
    return sum(_cache_rows(f) for f in _BAR_CACHE.values())


def _bars(symbol: str, timeframe: str = "H1"):
    """`<SYM>_<TF>.parquet`, or None. The CHART IS PART OF THE KEY -- see the essay above.

    `timeframe` defaults to H1 so every existing caller (`family_inputs.resolve`,
    `external_gauntlet.build_cell`, `edge_search`) keeps its exact behaviour until it passes one.
    """
    import pandas as pd
    key = (str(symbol), str(timeframe).upper())
    if key in _BAR_CACHE:
        _BAR_CACHE.move_to_end(key)
        return _BAR_CACHE[key]
    path = UNIVERSE / f"{key[0]}_{key[1]}.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return None
    _BAR_CACHE[key] = frame
    while len(_BAR_CACHE) > 1 and _held_rows() > BAR_CACHE_ROWS:
        _BAR_CACHE.popitem(last=False)
    return frame


def _resample_rule(timeframe: str) -> str:
    """The pandas offset for one bar of `timeframe`. `'60min'` and `'1h'` are the same rule."""
    from mt5desk.universe_registry import timeframe_minutes
    return f"{timeframe_minutes(timeframe)}min"


@lru_cache(maxsize=1)
def _ticks(symbol: str):
    """This symbol's recent tick tape as one indexed frame, or None. ONE symbol resident.

    Read once per SYMBOL rather than once per (symbol, chart). The concat of thirty tick vintages
    is the expensive half of `_tape_series` and it is chart-independent -- only the resample rule
    differs -- so a sweep that now visits a symbol on up to seven charts would otherwise re-read
    and re-parse the same thirty files seven times. `maxsize=1` because the sweep finishes a
    symbol's charts before moving on and a tick frame is far larger than a bar frame.
    """
    import pandas as pd
    d = TAPE / symbol
    if not d.exists():
        return None
    frames = []
    for f in sorted(d.glob("*.parquet"))[-30:]:
        try:
            frames.append(pd.read_parquet(f, columns=["ts", "bid", "ask"]))
        except Exception:
            continue
    if not frames:
        return None
    t = pd.concat(frames, ignore_index=True)
    t["ts"] = pd.to_datetime(t["ts"], utc=True)
    return t.dropna(subset=["bid", "ask"]).sort_values("ts").set_index("ts")


def _tape_series(symbol: str, index, timeframe: str = "H1"):
    """(spread, flow) on the bar clock, from the venue's own ticks. (None, None) if no tape.

    THE TAPE IS RESAMPLED ONTO THE CELL'S OWN CHART. This hardcoded `resample("1h")` and then
    reindexed onto whatever index it was handed, so an M5 cell would have received an HOURLY mean
    spread forward-filled across twelve bars -- a flat conditioning variable that cannot fire the
    family's own z-score, dressed as a measurement of the M5 book. The whole thesis of
    `liquidity_regime` and `orderflow_imbalance` is that the book moves faster than price does,
    which is exactly the claim a fine chart exists to test.
    """
    t = _ticks(symbol)
    if t is None:
        return None, None
    rule = _resample_rule(timeframe)
    spread = (t["ask"] - t["bid"]).resample(rule).mean()
    mid = ((t["ask"] + t["bid"]) / 2.0)
    # Flow proxy: net sign of mid changes within the bar. Not true aggressor data -- the tape has
    # no trade side -- so it is labelled a proxy rather than passed off as order flow.
    step = mid.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    flow = step.resample(rule).sum()
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


def timeframes_of(symbol: str, meta: dict) -> list[str]:
    """Charts this symbol actually has, ASKED rather than assumed.

    The registry is the authority: `expand_universe` records `timeframes` (written) and
    `timeframes_thin` (fetched, too short for the gates, with its bar count) per symbol, so a
    family that needs M5 asks instead of discovering a missing file at gauntlet time. A row that
    predates the ladder carries neither field; H1 is the honest answer for it, because H1 is the
    admission chart and its parquet is the reason the symbol is in the registry at all.

    The FILES still get the last word. A registry that claims a chart whose parquet is absent
    would send the sweep to read a file that is not there once per family; a parquet present but
    unclaimed (the hand-written gold M1/M5/M15, which predate the registry field) is real data
    and is swept.
    """
    row = meta.get(symbol) if isinstance(meta, dict) else None
    claimed = (row or {}).get("timeframes") if isinstance(row, dict) else None
    have = {tf for tf in _LADDER if (UNIVERSE / f"{symbol}_{tf}.parquet").exists()}
    if isinstance(claimed, list) and claimed:
        have |= {str(tf).upper() for tf in claimed
                 if (UNIVERSE / f"{symbol}_{str(tf).upper()}.parquet").exists()}
    return [tf for tf in _LADDER if tf in have]


def sweep_pairs(meta: dict) -> list[tuple[str, str]]:
    """Every (symbol, chart) this sweep may visit, ordered so any PREFIX is well spent.

    THE UNIT OF THE SWEEP IS THE PAIR, and the ordering has to distribute over both of its axes.
    `trial_allocator.order_symbols` already interleaves by measured certification yield so that a
    run cut short -- and every run here is, at a stage timeout or a memory budget -- has spent
    itself on the ground the ten gates actually reward. It buckets by a class function, so the
    class handed to it is `<asset class>|<chart>`: every prefix is then distributed across asset
    classes AND across charts, and a truncated sweep can no longer finish M1 and never reach D1.

    The desk has no measured per-CHART yield yet, so the timeframe axis interleaves evenly. That
    is the explore default, and it is the honest one: "never tested" and "tested and dead" are
    opposite facts (trial_allocator's own rule 4), and pre-weighting charts nobody has measured
    would freeze this module's first guess into the data that justifies it.
    """
    symbols = sorted({p.stem.rsplit("_", 1)[0] for p in UNIVERSE.glob("*.parquet")}
                     | {s for s in (meta or {}) if (UNIVERSE / f"{s}_H1.parquet").exists()})
    pairs = [(sym, tf) for sym in symbols for tf in timeframes_of(sym, meta)]
    try:
        import trial_allocator as _ta
        weights = _ta.class_weights(_ta.observed())
        ordered = _ta.order_symbols(
            pairs, weights or None,
            class_of=lambda pair: f"{_ta.asset_class_of(pair[0])}|{pair[1]}")
        if weights:
            print("  yield-ordered sweep: "
                  + ", ".join(f"{c}={weights[c]:.0%}" for c in sorted(weights)))
        return list(ordered)
    except Exception as exc:                       # a measurement outage must not stop the sweep
        # NAME THE FALLBACK, or nobody reading a log can tell an unordered sweep from an ordered
        # one -- and the yield ordering is the only thing that decides what a truncated run
        # reaches. Unordered here is registry order: symbols alphabetical, charts in ladder order.
        print(f"  yield ordering unavailable ({type(exc).__name__}: {exc}); falling back to "
              f"registry order -- symbols alphabetical, charts in ladder order")
        return pairs


def sweep() -> dict:
    from mt5desk.engine import Costs, run_backtest
    from mt5desk.families_orthogonal import (
        FAMILY_INPUTS,
        ORTHOGONAL_FAMILIES,
        timeframe_overrides,
        timeframe_refusal,
    )

    meta = _read(UNIVERSE / "universe.json") or {}
    pairs = sweep_pairs(meta)
    symbols = sorted({sym for sym, _ in pairs})
    hypotheses: list[dict] = []
    gaps: dict[str, int] = {}
    errors: dict[str, int] = {}
    ran: dict[str, int] = {}
    untestable: dict[str, int] = {}
    #: "<family>:not-on-<chart> (reason)" -> count. Declared refusals, never silent skips.
    off_chart: dict[str, int] = {}
    #: chart -> (symbol, chart) pairs actually reached, so coverage is reported and not inferred.
    charts: dict[str, int] = {}
    #: family -> pooled observations from cells individually short of MIN_TRADE_DAYS.
    pooled: dict[str, dict] = {}

    # ONE BASKET FOR THE SWEEP, chosen before the loop. Rebuilding a factor set per symbol reread
    # the same parquets 297 times; this loads them once and keeps them resident in `_bars`' cache.
    factor_syms = _factor_symbols(symbols, meta)

    # WHICH CHARTS EVEN WANT A PEER OR A FACTOR BASKET. Loading them is not free -- the basket is
    # eight frames -- and on a chart where every family that takes them is declared out of domain
    # it is eight frames loaded so they can be passed to nobody. That is not a tidiness point: the
    # residual families are the ones restricted to H1-and-slower, so an unguarded load would put
    # eight M1 frames (sixty bars per H1 bar each) in a cache budgeted for ten hourly ones, which
    # is precisely the memory the ladder had to be designed around. Computed once, from the same
    # declaration the family loop enforces, so the two can never disagree.
    _PEER_FAMS = ("relative_value", "correlation_regime")
    _FACTOR_FAMS = ("cross_asset_residual", "pca_residual")
    peer_charts = {t for t in _LADDER
                   if any(timeframe_refusal(f, t) is None for f in _PEER_FAMS)}
    factor_charts = {t for t in _LADDER
                     if any(timeframe_refusal(f, t) is None for f in _FACTOR_FAMS)}

    for _pair_i, (sym, tf) in enumerate(pairs):
        # CHECKPOINT WHAT IS ALREADY DONE. See _write_report: the stage timeout is shorter than
        # a full sweep, so anything not written by now is written by nobody.
        if _pair_i:
            _write_report(_build_report(pairs[:_pair_i], ran, gaps, errors, untestable,
                                        hypotheses, off_chart, charts), partial=True)
        df = _bars(sym, tf)
        # THE SCREEN IS A MARKET-TIME SCREEN, NOT A BAR COUNT. A flat 2,000 bars is four months
        # of H1 and eight YEARS of D1, so it would have silently emptied the daily lane -- the
        # swing lane -- on every symbol while reading like one rule. `min_bars_for` re-expresses
        # this same span on each chart and is the identity at H1.
        if df is None or len(df) < _min_bars(tf):
            continue
        charts[tf] = charts.get(tf, 0) + 1
        # THE PEER IS THE RELATED INSTRUMENT, THE FACTORS ARE THE UNIVERSE. Both were
        # alphabetical before (`[s for s in symbols if s != sym][:12]`), which paired XAUUSD with
        # 3M and handed the residual families two arbitrary neighbours; `pca_residual` was handed
        # nothing at all and returned [] on all 297 symbols. See _peer_symbol / _factor_symbols.
        #
        # AND THEY ARE LOADED ON THE CELL'S OWN CHART. A peer or factor frame on a different
        # clock does not raise -- the families join `how="inner"`, so an H1 peer against an M5
        # instrument silently reduces the cell to its twelve-times-sparser H1 stamps and calls the
        # result an M5 residual. Same chart both sides, or the join is measuring the mismatch.
        peer_sym = _peer_symbol(sym, symbols, meta) if tf in peer_charts else None
        peer_df = _bars(peer_sym, tf) if peer_sym else None
        factor_names = [s for s in factor_syms if s != sym] if tf in factor_charts else []
        factor_dfs = [f for f in (_bars(s, tf) for s in factor_names) if f is not None]
        spread, flow = _tape_series(sym, df.index, tf)
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
            kw = dict(kwargs_by_family.get(fam, {}))
            if fam in NOT_SOURCED_HERE:
                key = f"{fam}:not-sourced-here ({NOT_SOURCED_HERE[fam]})"
                gaps[key] = gaps.get(key, 0) + 1
                continue
            # A CHART THIS FAMILY CANNOT SPEAK ON IS DECLARED, NOT DISCOVERED. `hedging_demand_close`
            # gates on a broker stamp-hour, so on D1 it would return [] on every symbol and be
            # filed under `input_gaps` as though the desk were missing a feed -- absence read as a
            # clean verdict (WS-005). `FAMILY_TIMEFRAMES` carries the reason and it is counted in
            # its own bucket, so "this family does not run here" never reads as "no data".
            if (refusal := timeframe_refusal(fam, tf)):
                key = f"{fam}:not-on-{tf} ({refusal})"
                off_chart[key] = off_chart.get(key, 0) + 1
                continue
            # WALL-CLOCK DEFAULTS, RE-EXPRESSED ON THIS CHART. Empty at H1 by construction, so no
            # hourly cell moves by a parameter. Passed explicitly rather than left to the family's
            # H1-written default, and carried into the candidate's identity below, so the
            # certificate says exactly what ran and the gauntlet rebuilds THAT.
            overrides = timeframe_overrides(fam, tf)
            kw.update(overrides)
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
                _pool["members"].append(f"{sym}@{tf}:{_days}d")
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
            # THE CHART TRAVELS IN THE PARAMS, AND ONLY WHEN IT IS NOT H1. `params` is what the
            # cache key, the cell id, the certificate and the forward clock are all derived from,
            # so this is the one place the chart has to be recorded for every one of them to be
            # right at once. H1 stays absent so that every id this desk already holds is
            # byte-identical -- the same asymmetry `sleeve_key` applies to direction.
            _params = dict(identity_by_family.get(fam, {}))
            _params.update(overrides)
            if tf != _REFERENCE_TF:
                _params["timeframe"] = tf
            hypotheses.append({
                "symbol": sym, "family": fam, "timeframe": tf, "params": _params,
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

    return _build_report(pairs, ran, gaps, errors, untestable, hypotheses, off_chart, charts)


def _build_report(pairs, ran, gaps, errors, untestable, hypotheses,
                  off_chart=None, charts=None) -> dict[str, object]:
    return {"swept_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "symbols": len({p[0] for p in pairs}),
            "symbol_chart_pairs": len(pairs),
            # COVERAGE IS REPORTED, NOT INFERRED. "the sweep ran" is not "the sweep reached D1":
            # a chart whose parquets are absent, or whose bars are too short for the gates on
            # every symbol, contributes zero pairs and must say so rather than be read off a
            # families_ran count that cannot distinguish charts.
            "charts_swept": dict(sorted((charts or {}).items())),
            "off_chart_by_family": dict(sorted((off_chart or {}).items())),
            "off_chart_note": (
                "families DECLARED inexpressible on a chart (families_orthogonal."
                "FAMILY_TIMEFRAMES), with the reason. Kept apart from input_gaps on purpose: a "
                "session-hour family on a daily bar returns [] for a reason that is not a "
                "missing feed, and folding the two together is how absence reads as a clean "
                "verdict. Nothing here is a gate -- a cell that runs faces the identical ten."),
            "families_ran": ran,
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
    """Write the sweep artifact, atomically. Called after every (symbol, chart), not at the end.

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
    print(f"orthogonal sweep: {report['symbols']} symbol(s) x "
          f"{len(report['charts_swept'])} chart(s) = {report['symbol_chart_pairs']} pair(s), "
          f"{len(report['families_ran'])} family(ies) produced signals, "
          f"{len(hyp)} candidate(s) passed the loose screen")
    print("  charts reached: "
          + (", ".join(f"{tf}={n}" for tf, n in report["charts_swept"].items()) or "NONE"))
    for fam, n in sorted(report["families_ran"].items()):
        got = sum(1 for h in hyp if h["family"] == fam)
        print(f"   {fam:24} ran on {n:>3} chart-symbol(s) -> {got} candidate(s)")
    if report["off_chart_by_family"]:
        print("  declared off-chart (NOT a data gap -- families_orthogonal.FAMILY_TIMEFRAMES):")
        for k, n in sorted(report["off_chart_by_family"].items())[:6]:
            print(f"   {k[:150]}  x{n}")
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
