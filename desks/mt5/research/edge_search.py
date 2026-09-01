"""GENERIC EDGE SEARCH -- no families, no templates, and diversity as the objective function.

WHY NO HARDCODED FAMILIES (principal 2026-08-26: "absolute 0 hardcoding n max diversity"). Every
family file, including the orthogonal ones written earlier tonight, encodes a human's guess about
where edges live. That guess is a CEILING: the desk can only ever certify strategies someone
already imagined, which is exactly how 95.2% of its certificates ended up being one mechanism.
This searcher has no strategy templates at all. It builds PRIMITIVES from whatever numeric series
the box has, enumerates conditions over them mechanically, and lets the data say which
combinations predict forward returns.

WHY DIVERSITY IS THE OBJECTIVE AND NOT A FILTER. Ranking candidates by edge strength and hoping
the winners differ is how you get twenty copies of the best idea -- the search finds the strongest
signal, then the next strongest, which is usually the same signal with a slightly different
threshold. So selection here is explicitly GREEDY ON MARGINAL INDEPENDENCE: a candidate's score is
its edge DISCOUNTED by how much its return series already resembles what has been selected. The
second copy of a good idea scores near zero however profitable it is on its own. That is the only
way the number the portfolio actually cares about -- effective independent bets -- goes up.

THE HONESTY THIS OWES, because an unconstrained search is a p-hacking machine if unaccounted:

  TRIALS ARE COUNTED, ALL OF THEM, AND HANDED TO THE GATES. The searcher reports how many
  (feature, band, horizon, direction) combinations it evaluated and writes that count into every
  hypothesis, so the canonical `deflated_sharpe` gate deflates against the real multiplicity. That
  is the ONLY place multiplicity is judged.

  THIS FILE NEVER SETS A BAR. The pipeline is fixed and singular: discovery -> backtest -> the ten
  gates -> certificate -> forward window -> live. A screen that rejects on its own threshold
  inserts an unsanctioned gate in front of that pipeline, and a private threshold is a policy
  change made by whoever wrote the screen. Everything discovered goes to the gauntlet; the gauntlet
  decides. There is no second bar, harsher or looser, anywhere in this file.

  NO ECONOMIC STORY IS INVENTED. A statistically discovered edge has no mechanism, and the
  canonical ten-gate policy requires `economic_prior`. Every hypothesis is emitted with
  `mechanism_status: STATISTICAL_ONLY`, which does NOT pass that gate -- it routes to review where
  a mechanism must be named or the candidate dies. Auto-passing economic_prior for a machine
  discovery would gut the one gate that separates a cause from a coincidence.

  OUT-OF-SAMPLE BY CONSTRUCTION. Edges are fit on the first portion and scored on the held-out
  remainder; the in-sample number is never the reported one. This is a screen, not a verdict --
  survivors go through the same ten gates and the same pre-registered forward window as
  everything else. No second door.
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import UTC, datetime
from functools import lru_cache
from itertools import combinations
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe"
OUT = BASE / "data" / "hypotheses" / "edge_search_results.json"

#: Forward horizons in bars. A grid, not a choice -- the data picks.
HORIZONS = (1, 3, 6, 12, 24, 48)
#: Conditioning bands per feature: which quantile slice of the feature we condition on.
BANDS = ((0.0, 0.1), (0.1, 0.25), (0.75, 0.9), (0.9, 1.0), (0.4, 0.6))
#: Fraction of history used to FIT; the rest is held out and is the only score reported.
FIT_FRACTION = 0.6
#: A candidate needs at least this many held-out observations to be scored at all.
MIN_OOS_OBS = 60
#: The gauntlet's own floor, quoted: fewer than 60 distinct TRADING DAYS and no gate can rule on
#: the cell. Bars are not days -- a band can fire 300 times inside 40 sessions and still be
#: unjudgeable -- so testability is measured in days at proposal time, never on quality.
MIN_TRADE_DAYS = 60
#: Correlation above this to an already-selected edge means it is the same bet.
REDUNDANCY_CORR = 0.5
#: How many edges to keep PER SYMBOL. This is not a quality bar -- the diversity selector already
#: refuses anything correlated with what it has taken, so raising it cannot admit near-duplicates,
#: only genuinely distinct structure. It was 25 because the gauntlet ran on a 4GB box; the
#: gauntlet now runs on the desk box, so the ceiling moves to where the diversity objective stops
#: finding independent edges rather than where a machine ran out of memory (principal 2026-08-26:
#: "maximum diversity, no limits, never exhausted").
SELECT_K = 120
#: Symbols searched per hourly run. A budget, not a boundary: the cursor below guarantees the
#: rest are covered on following runs and then covered again.
PER_RUN = 40


def _interaction_pool_size(n_rows: int, n_features: int) -> int:
    """Use the largest interaction pool current memory can support.

    This is deliberately resource-derived rather than a feature/family ceiling.  The old literal
    22 meant every primitive sorting after the first 22 was *never* combined with anything.  On
    the desk box that discarded most peer, tape, macro and COT interactions despite gigabytes of
    free memory; on the research VPS, blindly removing the cap OOM-killed the hourly service.
    """
    try:
        import psutil

        budget = int(psutil.virtual_memory().available * 0.12)
    except (ImportError, OSError):
        budget = 256 * 1024 * 1024
    # Two z-score temporaries plus the interaction and pandas overhead.
    bytes_per_pair = max(1, n_rows) * 8 * 5
    affordable_pairs = max(1, budget // bytes_per_pair)
    # n*(n-1)/2 <= affordable_pairs
    affordable_features = int((1 + math.sqrt(1 + 8 * affordable_pairs)) // 2)
    return max(2, min(n_features, affordable_features))


#: Big enough for the WHOLE offering, because that is what one search actually touches.
#: `resolve_inputs` walks every peer symbol for each symbol searched, so a cache smaller than the
#: universe does not bound memory -- it thrashes, evicting entries it is about to need again and
#: turning an O(N) pass into O(N^2) parquet reads. Measured 2026-08-28: a 64-entry cap made a
#: three-symbol backfill take most of an hour. 320 close series is roughly 140MB, nowhere near
#: the 4.3GB peak this was meant to address -- that peak came from build_primitives, not here.
#: The point was never "small", it was "bounded": memory must not scale without limit, and a
#: constant ceiling the working set fits inside is exactly that.
@lru_cache(maxsize=320)
def _close(symbol: str):
    """Load a close series once per run; all-peer discovery otherwise rereads N² parquet files.

    BOUNDED (2026-08-28). `@cache` never evicts, so all-peer discovery across the full offering
    pinned a close series per symbol for the life of the run -- one contributor to the 4.3GB peak
    that left an 8GB box, shared with the live terminal, at 0.3GB free. 64 series covers the peer
    set any single symbol actually correlates against, so the reread it exists to prevent still
    does not happen.
    """
    import pandas as pd

    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path, columns=["close"])
        return frame["close"].astype(float)
    except Exception:
        return None


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def build_primitives(df, symbol: str, extra: dict | None = None) -> dict:
    """Every numeric series derivable from the input, with NO strategy semantics attached.

    These are not signals and not families. They are measurements -- shape, dispersion, position
    in range, clock -- from which conditions are enumerated mechanically. Nothing here encodes a
    view about what should work; a breakout, a carry and a reversal are all just particular
    combinations this enumeration can reach, alongside combinations nobody has named.
    """
    import numpy as np
    import pandas as pd

    d = df.copy()
    for col in ("open", "high", "low", "close"):
        if col not in d.columns:
            return {}
    close = d["close"].astype(float)
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    openp = d["open"].astype(float)
    ret = np.log(close).diff()
    rng = (high - low)
    prim: dict = {}

    # --- shape / momentum over several scales (scales enumerated, not chosen) ---------------
    for n in (3, 6, 12, 24, 48, 96, 240):
        prim[f"ret_{n}"] = np.log(close).diff(n)
        prim[f"vol_{n}"] = ret.rolling(n).std(ddof=1)
        prim[f"rng_{n}"] = rng.rolling(n).mean()
        prim[f"skew_{n}"] = ret.rolling(n).skew()
        prim[f"kurt_{n}"] = ret.rolling(n).kurt()
        # position within the trailing range: 0 = at the low, 1 = at the high
        lo = low.rolling(n).min()
        hi = high.rolling(n).max()
        prim[f"pos_{n}"] = (close - lo) / (hi - lo).replace(0, np.nan)
        prim[f"dd_{n}"] = close / close.rolling(n).max() - 1.0
        prim[f"ru_{n}"] = close / close.rolling(n).min() - 1.0

        # Distant-domain primitives, expressed as measurements rather than strategy families:
        # information theory (directional entropy), control/signal processing (path efficiency),
        # and state persistence (serial dependence).  Their combinations with venue/macro/peer
        # inputs let the search discover mechanisms nobody named in advance.
        up = (ret > 0).astype(float).rolling(n).mean().clip(1e-9, 1 - 1e-9)
        prim[f"sign_entropy_{n}"] = -(up * np.log(up) + (1 - up) * np.log(1 - up))
        prim[f"path_efficiency_{n}"] = (
            np.log(close).diff(n).abs() / ret.abs().rolling(n).sum().replace(0, np.nan)
        )
        prim[f"serial_corr_{n}"] = ret.rolling(n).corr(ret.shift(1))

    # --- dispersion RATIOS: regime, not level -----------------------------------------------
    for fast, slow in ((6, 48), (12, 96), (24, 240)):
        prim[f"volratio_{fast}_{slow}"] = (ret.rolling(fast).std(ddof=1)
                                           / ret.rolling(slow).std(ddof=1))
        prim[f"rngratio_{fast}_{slow}"] = rng.rolling(fast).mean() / rng.rolling(slow).mean()

    # --- intrabar structure ------------------------------------------------------------------
    body = (close - openp).abs()
    prim["body_frac"] = body / rng.replace(0, np.nan)
    prim["upper_wick"] = (high - close.combine(openp, max)) / rng.replace(0, np.nan)
    prim["lower_wick"] = (close.combine(openp, min) - low) / rng.replace(0, np.nan)
    prim["gap"] = (openp - close.shift(1)) / rng.rolling(24).mean().replace(0, np.nan)

    # --- clock: derived from the index, never a named session --------------------------------
    idx = d.index
    prim["hour"] = pd.Series(idx.hour.astype(float), index=idx)
    prim["dow"] = pd.Series(idx.dayofweek.astype(float), index=idx)
    prim["dom"] = pd.Series(idx.day.astype(float), index=idx)
    prim["month"] = pd.Series(idx.month.astype(float), index=idx)

    # --- volume/spread when the feed carries them --------------------------------------------
    for col in ("tick_volume", "real_volume", "spread"):
        if col in d.columns:
            s = d[col].astype(float)
            prim[col] = s
            for n in (12, 48):
                prim[f"{col}_z_{n}"] = (s - s.rolling(n).mean()) / s.rolling(n).std(ddof=1)

    # --- any external series the caller supplies (macro, COT, peers, tape aggregates) --------
    for name, series in (extra or {}).items():
        try:
            aligned = series.reindex(d.index).ffill().astype(float)
        except Exception:
            continue
        prim[f"ext_{name}"] = aligned
        prim[f"ext_{name}_z"] = ((aligned - aligned.rolling(96).mean())
                                 / aligned.rolling(96).std(ddof=1))

    prim = {k: v for k, v in prim.items() if v is not None}

    # PAIRWISE INTERACTIONS. A single-feature condition can only express "when X is extreme".
    # Most real mechanisms are conditional -- "when volatility is low AND positioning is
    # stretched" -- and that structure is unreachable from single features however many you add.
    # Interactions are formed mechanically between a bounded set of the most-populated primitives
    # so the trial count stays honest and countable rather than exploding into millions.
    keys = [k for k in sorted(prim) if prim[k].notna().sum() > len(prim[k]) * 0.5]
    pool_size = _interaction_pool_size(len(d), len(keys))
    # Rank by population first, then name for deterministic ties. External/tape series with less
    # history no longer disappear merely because their names sort after OHLC transforms.
    keys = sorted(keys, key=lambda k: (-int(prim[k].notna().sum()), k))[:pool_size]
    for a, b in combinations(keys, 2):
        sa, sb = prim[a], prim[b]
        za = (sa - sa.rolling(240).mean()) / sa.rolling(240).std(ddof=1)
        zb = (sb - sb.rolling(240).mean()) / sb.rolling(240).std(ddof=1)
        prim[f"x_{a}__{b}"] = za * zb
    return prim



def _match_clock(series, index):
    """Put `series` on the same tz-awareness as `index` WITHOUT moving a single timestamp.

    THE UNIVERSE IS MIXED AND IT IS NOT COSMETIC. Measured 2026-09-01 on the live registry: 171
    of 251 H1 parquets carry a tz-naive index and 80 carry tz-aware UTC -- all 251 legitimate
    registry symbols, written by two different producers. `resolve_inputs` unions the base index
    with every peer, so ANY base symbol met a peer of the other kind and pandas raised
    "Cannot join tz-naive with tz-aware DatetimeIndex". build_cell catches that as INPUT-FAIL and
    returns None, so all 14,060 `ext_` discovered cells -- 69% of the docket -- were being
    discarded before a single gate ran, each after ~12s of work.

    THE COERCION IS VALUE-PRESERVING IN BOTH DIRECTIONS, which is why it is safe to apply to
    money-path inputs. Dropping a tz keeps the UTC wall clock; adding one labels a clock that is
    already UTC. The naive files ARE UTC: AUDCAD (aware) and 3M (naive) both end 2026-08-28
    22:00, and 3M's missing hours are equity session gaps, not an offset. Peers adopt the BASE
    index's convention rather than a fixed UTC so the returned features come back on exactly the
    index the caller handed in, and nothing downstream sees a different clock than it passed.
    """
    if series is None or not hasattr(series, "index"):
        return series
    want = getattr(index, "tz", None)
    have = getattr(series.index, "tz", None)
    if want is None and have is not None:
        return series.tz_localize(None)
    if want is not None and have is None:
        return series.tz_localize(want)
    if want is not None and have is not None and str(want) != str(have):
        return series.tz_convert(want)
    return series


#: SMALL, ORDERED CACHE -- NOT A BIG ONE, AND THE ORDER IS WHY IT WORKS.
#: `resolve_inputs` rebuilds residuals and rolling correlations against EVERY other instrument in
#: the registry, and external_gauntlet called it once per cell. Measured 2026-09-01 on the live
#: docket: 14,060 of the 20,341 `discovered` cells use an `ext_` feature and they span only 137
#: distinct symbols, so 13,923 of those calls (99.0%) rebuilt a universe that was already built
#: moments earlier for the same symbol.
#:
#: Memoising all 137 is not an option -- 137 symbols x ~250 peers x 2 series is tens of GB on a
#: box with 8GB and a live terminal. Two entries are enough PROVIDED the caller walks the docket
#: in symbol order, which external_gauntlet now does: every cell of a symbol is consecutive, so
#: depth 2 (current symbol + the one being finished) converts ~99% of the calls into hits at
#: O(1) memory. Unsorted, the same cache would thrash to a ~0% hit rate, which is exactly the
#: behaviour this replaces.
_RESOLVE_CACHE: OrderedDict[tuple, dict] = OrderedDict()
_RESOLVE_CACHE_DEPTH = 2


def _resolve_cache_key(symbol: str, index, all_symbols: list[str]) -> tuple:
    """Identity of the universe this call would build.

    Length plus both endpoints pins a time index: two different bar sets cannot share all three.
    The peer set is part of the identity because adding an instrument changes every residual.
    """
    return (symbol, len(index), str(index[0]) if len(index) else "",
            str(index[-1]) if len(index) else "", len(all_symbols))


def resolve_inputs(symbol: str, index, all_symbols: list[str]) -> dict:
    """Every external series this box can supply, as PRIMITIVES with no family semantics.

    This is what makes the search reach past the named families without naming anything. A carry
    edge is not "the carry family" here -- it is whatever the searcher finds conditioned on the
    swap-differential primitive. A relative-value edge is a condition on a peer-residual
    primitive. Positioning, liquidity and macro likewise. The mechanisms are the same; the
    difference is that nobody had to think of them first, and combinations nobody named are
    reachable by exactly the same enumeration.
    """
    import numpy as np
    import pandas as pd

    _ck = _resolve_cache_key(symbol, index, all_symbols)
    _hit = _RESOLVE_CACHE.get(_ck)
    if _hit is not None:
        _RESOLVE_CACHE.move_to_end(_ck)
        # A SHALLOW COPY, so a caller that adds or drops a key cannot corrupt the entry the next
        # cell will read. The Series inside are treated as read-only by every family.
        return dict(_hit)

    def _cl(sym: str):
        """Every close read in this function, already on the caller's clock.

        Bound once rather than coercing at each call site: the function reads closes from five
        separate places (peer residuals, the cross-sectional panel, FX triangles, and the
        swap/carry legs), and a single missed site re-raises the tz union error and discards the
        whole cell as INPUT-FAIL -- which is precisely how 69% of the docket was being lost.
        """
        return _match_clock(_close(sym), index)

    extra: dict = {}

    # --- peers: residuals and rolling correlations against several other instruments ---------
    # ALL registry instruments are potential peers. The previous [:4] silently made most of the
    # Fusion universe ineligible as a driver; caching makes full coverage cheaper than that cap.
    peers = [s for s in all_symbols if s != symbol]
    base_close = _cl(symbol)
    base = np.log(base_close) if base_close is not None else None
    if base is not None:
        for peer in peers:
            peer_close = _cl(peer)
            if peer_close is None:
                continue
            pc = np.log(peer_close)
            joined = pd.concat([base, pc], axis=1, join="inner").dropna()
            if len(joined) < 500:
                continue
            resid = joined.iloc[:, 0] - joined.iloc[:, 1]
            extra[f"resid_{peer}"] = resid
            extra[f"residz_{peer}"] = ((resid - resid.rolling(240).mean())
                                       / resid.rolling(240).std(ddof=1))
            extra[f"corr_{peer}"] = (joined.iloc[:, 0].diff()
                                     .rolling(120).corr(joined.iloc[:, 1].diff()))
            # Lead-lag is not contemporaneous correlation. Every lag uses information available
            # before the target decision and is separately trial-accounted downstream.
            for lag in (1, 3, 6, 12, 24):
                extra[f"lead_{peer}_{lag}"] = joined.iloc[:, 1].diff().shift(lag)

        # Cross-sectional state: dispersion and common motion across every available Fusion leg.
        peer_returns = []
        for peer in peers:
            pc = _cl(peer)
            if pc is not None:
                peer_returns.append(np.log(pc).diff().rename(peer))
        if peer_returns:
            panel = pd.concat(peer_returns, axis=1).reindex(index)
            extra["xsection_mean"] = panel.mean(axis=1)
            extra["xsection_dispersion"] = panel.std(axis=1, ddof=1)
            extra["xsection_breadth"] = (panel > 0).mean(axis=1)

        # Every executable FX triangle is derived from the registry, never from a literal pair
        # list. This tests residual convergence/continuation; it does NOT claim synchronized
        # three-leg arbitrage because H1 closes are not executable simultaneous quotes.
        if len(symbol) == 6 and symbol.isalpha():
            base_ccy, quote_ccy = symbol[:3], symbol[3:]

            def fx_log(a: str, b: str):
                direct = _cl(a + b)
                if direct is not None:
                    return np.log(direct)
                inverse = _cl(b + a)
                return -np.log(inverse) if inverse is not None else None

            currencies = sorted({s[:3] for s in all_symbols if len(s) == 6 and s.isalpha()}
                                | {s[3:] for s in all_symbols if len(s) == 6 and s.isalpha()})
            for bridge in currencies:
                if bridge in (base_ccy, quote_ccy):
                    continue
                left, right = fx_log(base_ccy, bridge), fx_log(quote_ccy, bridge)
                if left is None or right is None:
                    continue
                tri = pd.concat([base, left, right], axis=1, join="inner").dropna()
                if len(tri) >= 500:
                    extra[f"triangle_resid_{bridge}"] = tri.iloc[:, 0] - (
                        tri.iloc[:, 1] - tri.iloc[:, 2]
                    )

    # --- the venue's own book: spread and a signed-move proxy from the tick tape --------------
    tape_dir = BASE / "data" / "tape" / "ticks" / symbol
    if tape_dir.exists():
        frames = []
        for f in sorted(tape_dir.glob("*.parquet"))[-30:]:
            try:
                frames.append(pd.read_parquet(f, columns=["ts", "bid", "ask"]))
            except Exception:
                continue
        if frames:
            tk = pd.concat(frames, ignore_index=True).dropna(subset=["bid", "ask"])
            tk["ts"] = pd.to_datetime(tk["ts"], utc=True)
            tk = tk.sort_values("ts").set_index("ts")
            extra["book_spread"] = (tk["ask"] - tk["bid"]).resample("1h").mean()
            mid = (tk["ask"] + tk["bid"]) / 2.0
            extra["book_flow"] = np.sign(mid.diff()).resample("1h").sum()
            extra["book_ticks"] = mid.resample("1h").count()

    # --- swap/contract terms: the differential that a carry mechanism would condition on -----
    # THREE SEVERANCES IN THESE TWELVE LINES, all repaired 2026-08-29 and all silent:
    #   1. it globbed `*.json*`; `mt5desk.tape.record_contract_terms` writes `.parquet`, so this
    #      feature has NEVER been populated on any run -- an empty `vals` is indistinguishable
    #      from a symbol with no carry, and the second is what a reader assumes;
    #   2. it read `recorded_at`/`at`; the recorder stamps `observed_at`, so even against JSON
    #      `pd.Timestamp(None)` raised straight into the bare `except` and dropped every row;
    #   3. `swap_long - swap_short` on the RAW field is not one quantity. 110 symbols quote swap
    #      in POINTS and 138 as an ANNUAL PERCENT, so the raw difference mixes two dimensions
    #      across the universe and is scaled by the broker's decimal places within it. Repairing
    #      1 and 2 alone would have switched a mis-united conditioner ON for the first time,
    #      which is why the unit resolution is part of the repair and not a later improvement.
    # `float(row.get("swap_long", 0))` also defaulted an ABSENT field to zero -- the L1.28a
    # defect exactly: a symbol with no recorded swap read as a symbol with no carry.
    terms_dir = BASE / "data" / "tape" / "contract_terms"
    if terms_dir.exists():
        # DUAL-CONTEXT IMPORT. This module is imported BOTH ways: as `research.edge_search`
        # from the VPS checks, and as a top-level `edge_search` by the box's forward engine,
        # which puts `desks/mt5/research` directly on sys.path. In the second case __package__
        # is "" and a relative import has no parent to resolve against, so `from .carry_state`
        # raised ModuleNotFoundError -- which `family_inputs.resolve` caught and reported as
        # "runtime inputs unavailable", blocking all SEVEN EURCHF discovered sleeves from
        # gathering any forward evidence at all.
        #
        # Third time this desk has been bitten by a single-form import in a dual-context module
        # (family_inputs, shadow_admission.run_key, now this). The pattern is the fix.
        try:
            from .carry_state import money_per_lot_night
        except ImportError:
            from carry_state import money_per_lot_night  # type: ignore[no-redef]
        vals = []
        for f in sorted(terms_dir.glob("*.parquet"))[-60:]:
            try:
                rows = pd.read_parquet(f)
            except Exception:
                continue
            rows = rows[rows["symbol"].astype(str).str.upper() == symbol.upper()]
            for row in rows.to_dict("records"):
                if row.get("swap_long") is None or row.get("swap_short") is None:
                    continue
                # Account currency per lot per night, on BOTH sides, or the row stands aside.
                # Mode 5 needs a price this builder does not carry, so those symbols simply do
                # not get the feature -- absent, never zero.
                lo = money_per_lot_night(float(row["swap_long"]), row, None)[0]
                sh = money_per_lot_night(float(row["swap_short"]), row, None)[0]
                if lo is None or sh is None:
                    continue
                try:
                    vals.append((pd.Timestamp(row.get("observed_at"), tz="UTC"), lo - sh))
                except Exception:
                    continue
        if vals:
            s = pd.Series(dict(vals)).sort_index()
            extra["swap_diff"] = s

    # --- macro and positioning ---------------------------------------------------------------
    macro = _read(BASE / "data" / "macro_state.json")
    if isinstance(macro, dict):
        for k, v in list(macro.items())[:6]:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                extra[f"macro_{k}"] = pd.Series(float(v), index=index)
    for name in ("cot_tff.json", "cot.json", "cot_disagg.json"):
        doc = _read(BASE / "data" / name)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        try:
            cdf = pd.DataFrame(rows)
            tcol = next((c for c in ("date", "report_date", "as_of") if c in cdf.columns), None)
            ncol = next((c for c in ("net", "noncomm_net", "net_position")
                         if c in cdf.columns), None)
            if tcol and ncol:
                cdf.index = pd.to_datetime(cdf[tcol], utc=True, errors="coerce")
                extra["cot_net"] = cdf[ncol].astype(float).dropna()
                break
        except Exception:
            continue

    _RESOLVE_CACHE[_ck] = extra
    while len(_RESOLVE_CACHE) > _RESOLVE_CACHE_DEPTH:
        _RESOLVE_CACHE.popitem(last=False)
    return dict(extra)


def _forward_returns(close, horizons=HORIZONS) -> dict:
    import numpy as np
    out = {}
    logc = np.log(close.astype(float))
    for h in horizons:
        out[h] = logc.shift(-h) - logc
    return out


def mechanism_for_feature(feature: str) -> tuple[str, str]:
    """Name a falsifiable economic prior when the measured input genuinely supplies one.

    This does not infer profitability. It distinguishes mechanism-bearing discoveries (venue
    liquidity, carry, positioning, relative value, slow diffusion, scheduled flow or a declared
    state transition) from arbitrary price-shape correlations. Interactions are named only when
    both legs have a prior; a story for one half cannot launder an unexplained half.
    """
    if feature.startswith("x_") and "__" in feature:
        left, right = feature[2:].split("__", 1)
        ls, ln = mechanism_for_feature(left)
        rs, rn = mechanism_for_feature(right)
        if ls == rs == "NAMED":
            return "NAMED", f"conditional interaction: {ln}; jointly with {rn}"
        return "STATISTICAL_ONLY", "interaction includes at least one unexplained statistical leg"

    named = (
        (("ext_book_spread", "spread", "tick_volume"),
         "liquidity/inventory withdrawal changes price impact and subsequent recovery"),
        (("ext_book_flow", "ext_book_ticks"),
         "venue activity and signed mid-price pressure proxy short-lived execution flow"),
        (("ext_swap_diff",),
         "broker swap differential compensates inventory funding and carry demand"),
        (("ext_cot",),
         "reported positioning extremes create crowding and forced-unwind asymmetry"),
        # BEHAVIOURAL-FLOW CAUSES (added 2026-08-27, principal: "all miners hunt real
        # mechanisms"). These are not price-shape numerology: each names a documented flow with
        # an identifiable counterparty, and each is falsifiable -- the prior fails if the
        # counterparty flow is absent. Held to the same standard as the venue-data entries.
        (("dd_",),
         "distance below a rolling peak measures forced selling -- margin calls, stop cascades "
         "and risk-limit liquidations supply at prices unrelated to value; buying that supply "
         "earns the liquidity premium and fails when the decline is informed"),
        (("ru_",),
         "distance above a rolling trough measures chase intensity -- late-crowd entries whose "
         "stops sit below, an exhaustible flow with a known unwind path"),
        (("gap",),
         "an opening gap is a failed auction between sessions: participants trapped on the "
         "wrong side must trade out, driving fill-or-run dynamics"),
        (("hour", "dow"),
         "session opens, fixes, option cuts and settlement windows carry SCHEDULED institutional "
         "flow tied to the clock, not to price"),
        (("dom", "month"),
         "month-end rebalancing, payment cycles and seasonal production/demand are scheduled "
         "flows with identifiable counterparties"),
        (("volratio_", "rngratio_"),
         "a declared volatility/participation regime TRANSITION -- compression breaking into "
         "expansion is the moment resting-order behaviour stops paying and breakout flow starts"),
        (("ext_resid_", "ext_residz_", "ext_triangle_resid_"),
         "cross-instrument pricing residuals can converge when common risk is re-arbitraged"),
        (("ext_lead_",),
         "information diffuses from a leading Fusion instrument into a slower target"),
        (("ext_xsection_",),
         "cross-sectional dispersion/breadth identifies common-flow versus idiosyncratic states"),
        (("ext_macro_",),
         "point-in-time macro state changes discount-rate and risk-transfer demand"),
        (("hour", "dow", "dom", "month", "gap"),
         "scheduled settlement/rebalancing and liquidity cycles create clock-conditioned flow"),
        (("volratio_", "rngratio_", "sign_entropy_", "path_efficiency_", "serial_corr_"),
         "a measurable market-state transition changes continuation versus absorption odds"),
    )
    for prefixes, note in named:
        if feature.startswith(prefixes):
            return "NAMED", note
    return "STATISTICAL_ONLY", "no economic cause is encoded by this price-shape primitive"


def evaluate(prim: dict, fwd: dict, *, fit_end: int) -> tuple[list[dict], int]:
    """Enumerate every (feature, band, horizon, direction) and score it OUT OF SAMPLE.

    Returns the candidates and the TOTAL TRIAL COUNT -- the second value is not optional
    bookkeeping, it is what the deflated-Sharpe gate needs in order to be honest about a search
    this wide.
    """
    import numpy as np

    candidates: list[dict] = []
    trials = 0
    # Unconditional forward mean per horizon, on the SAME out-of-sample bars every candidate is
    # scored on. This is the benchmark a conditional edge must beat to be an edge at all.
    base_means: dict = {}
    fwd_values: dict = {}
    for h, fr in fwd.items():
        fv = fr.to_numpy(dtype="float64", na_value=np.nan)
        fwd_values[h] = fv
        oos_all = np.zeros(len(fv), dtype=bool)
        oos_all[fit_end:] = True
        sel = oos_all & np.isfinite(fv)
        base_means[h] = float(fv[sel].mean()) if sel.sum() >= MIN_OOS_OBS else np.nan

    for fname, series in prim.items():
        values = series.to_numpy(dtype="float64", na_value=np.nan)
        finite = np.isfinite(values)
        if finite.sum() < MIN_OOS_OBS * 4:
            continue
        fit_vals = values[:fit_end][np.isfinite(values[:fit_end])]
        if fit_vals.size < MIN_OOS_OBS:
            continue
        for lo_q, hi_q in BANDS:
            # Band edges come from the FIT window only -- using full-sample quantiles would leak
            # the future into the definition of the condition itself.
            lo, hi = np.quantile(fit_vals, lo_q), np.quantile(fit_vals, hi_q)
            if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
                continue
            mask = finite & (values >= lo) & (values <= hi)
            for h in fwd:
                trials += 2                       # both directions are a trial each
                fv = fwd_values[h]
                sel = mask & np.isfinite(fv)
                oos = sel.copy()
                oos[:fit_end] = False
                n_oos = int(oos.sum())
                if n_oos < MIN_OOS_OBS:
                    continue
                r_oos = fv[oos]
                mean = float(r_oos.mean())
                sd = float(r_oos.std(ddof=1))
                if not np.isfinite(sd) or sd <= 0:
                    continue

                # TWO CORRECTIONS, WITHOUT WHICH THIS SEARCHER IS A DRIFT DETECTOR.
                #
                # 1. CONDITIONAL vs UNCONDITIONAL, not vs zero. An instrument with a trend has a
                #    positive mean forward return under almost ANY condition, so scoring against
                #    zero rediscovers the drift once per feature. The first run of this file
                #    returned 25 "edges" that were all side=+1 at the same horizon -- gold's
                #    drift, found 25 ways. The question is whether CONDITIONING helps, so the
                #    benchmark is the unconditional forward return over the same out-of-sample
                #    bars at the same horizon.
                #
                # 2. OVERLAPPING WINDOWS destroy the sample size. At h=48 on hourly bars,
                #    consecutive observations share 47 of 48 hours: they are not independent, and
                #    dividing by sqrt(n) overstates significance by roughly sqrt(h) -- a factor of
                #    ~7 at h=48. Effective n is deflated by the overlap, which is the difference
                #    between t=20 and t=3.
                base = base_means.get(h)
                if base is None or not np.isfinite(base):
                    continue
                edge = mean - base
                n_eff = max(1.0, n_oos / float(h))
                t = edge / (sd / math.sqrt(n_eff))
                side = 1 if edge >= 0 else -1
                candidates.append({
                    "feature": fname, "band": [lo_q, hi_q], "horizon": h, "side": side,
                    "n_oos": n_oos, "n_effective": round(n_eff, 1),
                    "mean_fwd": mean, "unconditional_fwd": base, "edge_vs_unconditional": edge,
                    "t_stat": abs(t), "sharpe_like": abs(edge) / sd,
                    # Thousands of full boolean arrays were the searcher's largest avoidable
                    # allocation: 2,760 emitted candidates came from a much wider scored pool,
                    # and holding one byte per bar per candidate competed with the gauntlet for
                    # the desk box. Pack the exact mask losslessly (8x smaller); the selector
                    # reconstructs it only for the candidate currently under comparison.
                    "_mask_bits": np.packbits(oos, bitorder="little"),
                    "_mask_len": len(oos),
                    "_fwd": fv,
                })
    return candidates, trials


def select_diverse(candidates: list[dict], k: int = SELECT_K) -> list[dict]:
    """Greedy selection that maximises MARGINAL independence, not individual strength.

    Each pick is the candidate with the best edge among those not already explained by what has
    been selected. Redundancy is measured on the realised per-observation return series, so two
    candidates that are described differently but fire on the same bars are correctly recognised
    as one bet -- which is exactly the failure the family-based book fell into.
    """
    import numpy as np

    ranked = sorted(candidates, key=lambda c: c["t_stat"], reverse=True)
    chosen: list[dict] = []
    chosen_vectors: list = []
    for cand in ranked:
        if len(chosen) >= k:
            break
        mask = np.unpackbits(cand["_mask_bits"], bitorder="little")[:cand["_mask_len"]].astype(bool)
        vec = np.where(mask, cand["_fwd"] * cand["side"], 0.0)
        if not np.isfinite(vec).all():
            vec = np.nan_to_num(vec)
        redundant = False
        for prev in chosen_vectors:
            denom = (np.linalg.norm(vec) * np.linalg.norm(prev))
            if denom <= 0:
                continue
            corr = float(np.dot(vec, prev) / denom)
            if abs(corr) >= REDUNDANCY_CORR:
                redundant = True
                break
        if redundant:
            continue
        chosen.append(cand)
        chosen_vectors.append(vec)
    return chosen


def search_symbol(symbol: str, extra: dict | None = None) -> dict:
    import pandas as pd

    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        return {"symbol": symbol, "status": "NO_BARS"}
    df = pd.read_parquet(path)
    if len(df) < 2000:
        return {"symbol": symbol, "status": "TOO_FEW_BARS", "bars": len(df)}
    all_syms = sorted(p.stem.replace("_H1", "") for p in UNIVERSE.glob("*_H1.parquet"))
    resolved = dict(extra or {})
    try:
        resolved.update(resolve_inputs(symbol, df.index, all_syms))
    except Exception as exc:
        print(f"  {symbol}: input resolution partial ({type(exc).__name__}: {exc})")
    prim = build_primitives(df, symbol, resolved)
    if not prim:
        return {"symbol": symbol, "status": "NO_PRIMITIVES"}
    fwd = _forward_returns(df["close"])
    fit_end = int(len(df) * FIT_FRACTION)
    cands, trials = evaluate(prim, fwd, fit_end=fit_end)
    chosen = select_diverse(cands)
    # TESTABILITY ROUTE (principal 2026-08-27: "it must all always be redirected to testable
    # candidates"). `external_gauntlet` drops any cell whose daily series holds fewer than 60
    # observations -- CPCV with purge+embargo and the walk-forward folds cannot judge less. A
    # candidate whose selected events fall on fewer than 60 distinct DAYS therefore cannot be
    # ruled on by any gate, however strong the underlying effect: proposing it spends the cycle
    # on a question the desk has no way to answer. n_oos counts BARS, and bars cluster -- so the
    # count that matters is days. This screens nothing on quality: no candidate is dropped here
    # for being weak, and the number is the gauntlet's own, quoted rather than invented.
    import numpy as _np
    keep, untestable = [], 0
    for c in chosen:
        bits, mlen = c.get("_mask_bits"), c.get("_mask_len")
        if bits is None or not mlen or mlen > len(df.index):
            keep.append(c)                      # cannot measure: never guess, let it through
            continue
        m = _np.unpackbits(bits, count=int(mlen), bitorder="little").astype(bool)
        days = len({ts.date() for ts in df.index[:int(mlen)][m]})
        if days < MIN_TRADE_DAYS:
            untestable += 1
            continue
        c["n_days"] = days
        keep.append(c)
    chosen = keep
    rows = [{k: v for k, v in c.items() if not k.startswith("_")} for c in chosen]
    return {"symbol": symbol, "status": "OK", "bars": len(df),
            "primitives": len(prim), "trials": trials,
            "candidates_scored": len(cands),
            "untestable_dropped": untestable,
            "selected": rows}


def main(symbols: list[str] | None = None) -> int:
    now = datetime.now(tz=UTC)
    if symbols is None:
        symbols = sorted(p.stem.replace("_H1", "") for p in UNIVERSE.glob("*_H1.parquet"))
        # MINED GROUND FIRST. The miners and the moat spent the week pointing at particular
        # symbols; searching those before the rest is the entire conversion step that was
        # missing -- otherwise mining and searching run in the same desk and never meet, which
        # is how 22 miners were scored zero-yield for finding things nobody tested.
        targets = _read(BASE / "data" / "hypotheses" / "mined_targets.json") or {}
        known = set(symbols)
        ranked = [r.get("symbol") for r in (targets.get("targets") or [])
                  if r.get("symbol") in known]
        if ranked:
            seen = set(ranked)
            symbols = ranked + [s for s in symbols if s not in seen]
            print(f"  search order: {len(ranked)} mined-ground symbol(s) first")

        # NEVER EXHAUSTED, BY CONSTRUCTION. A search that walks the universe once and stops has
        # decided the universe is finished, which is the WS-005 error in a new costume: absence
        # of a fresh look read as absence of an edge. Instead a cursor advances every run, so
        # coverage is a CYCLE -- every symbol is re-searched on newer bars, forever, and a symbol
        # that had nothing last month gets looked at again with another month of data. Mined
        # ground still jumps the queue; the rotation governs everything behind it.
        cursor_file = BASE / "data" / "hypotheses" / "search_cursor.json"
        try:
            cursor = int((_read(cursor_file) or {}).get("cursor", 0))
        except (TypeError, ValueError):
            cursor = 0
        # CLASS-BALANCED ROTATION (principal 2026-08-28: "all miners always hunt all MT5
        # universe classes"). A flat cursor over 247 symbols spends its budget wherever the
        # alphabet happens to cluster -- measured the same day: 99 usable equities but 16 in the
        # docket, and BOND at ZERO coverage while four bond instruments sat tradable and
        # uncostable-by-nobody. Classes fail in different regimes by construction (a gilt
        # answers rate expectations, cocoa answers weather, a JPY cross answers carry), so
        # breadth across classes IS the diversification the desk cannot manufacture by adding
        # another parameterisation. The tail is interleaved round-robin BY CLASS so every class
        # is represented in every run's budget; within a class the cursor still rotates, so
        # nothing is ever declared exhausted.
        tail = symbols[len(ranked):]
        try:
            import sys as _sys
            _sys.path.insert(0, str(BASE))
            from mt5desk.universe import asset_class as _aclass
            by_class: dict[str, list[str]] = {}
            for s in tail:
                by_class.setdefault(_aclass(s), []).append(s)
            if len(by_class) > 1:
                order = sorted(by_class)
                woven: list[str] = []
                i = 0
                while len(woven) < len(tail):
                    for cls in order:
                        bucket = by_class[cls]
                        if i < len(bucket):
                            woven.append(bucket[i])
                    i += 1
                tail = woven
                print(f"  class-balanced rotation over {len(order)} asset class(es): "
                      f"{', '.join(order)}")
        except Exception as _exc:
            print(f"  class balancing unavailable ({type(_exc).__name__}); flat rotation")
        if tail:
            off = cursor % len(tail)
            symbols = ranked + tail[off:] + tail[:off]
            cursor_file.parent.mkdir(parents=True, exist_ok=True)
            cursor_file.write_text(json.dumps({
                "cursor": cursor + PER_RUN,
                "note": "rotation cursor -- coverage is a cycle, never a completed sweep",
            }), "utf-8")
        # THE BUDGET IS APPLIED, AND NOT APPLYING IT WAS COSTING THE WHOLE RUN (2026-08-26).
        # The previous comment here read "the desk box ... currently fits the complete Fusion
        # registry in one hourly run" and therefore refused to truncate. It does not fit. The
        # pipeline log records the consequence exactly:
        #     covering the complete registry: 295 symbol(s) this run
        #     File "...\research\edge_search.py", line 427, in evaluate
        #     MemoryError
        # The process died partway through, so `edge_search_results.json` was never written --
        # `family-free frontier pull FAILED` -- and the merge received NOTHING from the
        # family-free searcher. Measured while writing this: the artifact was 3.8h stale across
        # two completed pipeline runs, and the book is 95.2% one family (session_range_breakout,
        # 20 of 21 certificates) with eight target families absent. The organ whose whole job is
        # to break that concentration had been producing zero output.
        #
        # SLICING IS NOT TRUNCATION HERE, AND IT IS THE OPPOSITE OF TIMIDITY. Attempting 295
        # symbols completes ZERO of them; 40 that COMPLETE, on an hourly cursor, is ~960
        # symbol-searches a day against the current zero. Coverage stays a CYCLE, never a
        # finished sweep (RESEARCH 6c-bis): the cursor advances every run, so every symbol is
        # re-searched on newer bars forever, and mined ground still jumps the queue ahead of it.
        # PER_RUN IS A TOTAL, NOT AN ALLOWANCE ON TOP OF THE MINED HEAD. A first version of this
        # fix read `budget = PER_RUN + len(ranked)`, which bounded nothing: nearly every symbol
        # carries some miner attention (measured: `search order: 135 mined-ground symbol(s)
        # first`), so the head IS most of the registry and 295 became 175. The box climbed to
        # 2.68GB and was still climbing.
        #
        # AND THE SPLIT IS NOT COSMETIC. Spending the whole budget on the mined head would mean
        # the rotation tail is never reached while `ranked` exceeds PER_RUN -- the cursor would
        # advance over symbols no run ever searches, which is a coverage claim the desk could not
        # cash. So attention gets priority up to half the budget and the cursor gets the rest,
        # each taking the other's slack when it is short. Attention decides ORDER; the cursor
        # guarantees that every symbol still comes back (RESEARCH 6c-bis).
        if len(symbols) > PER_RUN:
            head_n = min(len(ranked), max(1, PER_RUN // 2))
            head = symbols[:head_n]
            tail_pick = [s for s in symbols[len(ranked):] if s not in set(head)][:PER_RUN - head_n]
            # Slack in either direction is taken by the other, so the budget is always spent.
            chosen = head + tail_pick
            if len(chosen) < PER_RUN:
                chosen += [s for s in symbols if s not in set(chosen)][:PER_RUN - len(chosen)]
            print(f"  budgeted slice: {len(chosen)} of {len(symbols)} symbol(s) this run "
                  f"({len(head)} by miner/moat attention + {len(tail_pick)} on the rotation "
                  f"cursor at {cursor}); every symbol returns on a later run, forever")
            symbols = chosen
        else:
            print(f"  covering {len(symbols)} symbol(s) this run (registry fits inside the "
                  f"{PER_RUN}-symbol budget)")
    results, hypotheses = [], []
    #: Strong effects whose cause the mechanism map cannot name. They are QUESTIONS for the
    #: research brains, never candidates: gate 1 would terminal-reject them, so shipping them
    #: to the docket spends the hour on something no gate can rule on. Naming one (with
    #: evidence) re-opens gate 1 for its whole feature class via the map.
    naming_queue: list[dict] = []
    total_trials = 0
    unsearched: list[dict[str, str]] = []
    for sym in symbols:
        try:
            res = search_symbol(sym)
        except MemoryError:
            # RECORDED, NEVER SWALLOWED. One symbol exhausting memory must not void the run's
            # other 39 -- that is how a whole hour of search produced nothing. But a skipped
            # symbol is NOT a searched symbol with no edge, and conflating the two is the
            # absence-read-as-verdict class: the symbol lands in `unsearched`, is reported, and
            # the cursor brings it back on a later run with different neighbours.
            unsearched.append({"symbol": sym, "reason": "MemoryError during evaluate"})
            print(f"  {sym}: MemoryError -- NOT searched, recorded and left to the cursor")
            continue
        results.append(res)
        total_trials += int(res.get("trials") or 0)
        for row in res.get("selected", []):
            mechanism_status, mechanism_note = mechanism_for_feature(str(row["feature"]))
            if mechanism_status != "NAMED":
                naming_queue.append({
                    "symbol": sym, "feature": row["feature"], "band": row.get("band"),
                    "horizon": row.get("horizon"), "side": row.get("side"),
                    "t_stat": row.get("t_stat"), "n_oos": row.get("n_oos"),
                    "asked_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "question": ("measured out-of-sample effect with no named cause; name it "
                                 "with evidence or refute it -- never trade it unnamed"),
                })
                continue
            hypotheses.append({
                "symbol": sym,
                "family": "discovered",
                "params": {"feature": row["feature"], "band": row["band"],
                           "horizon": row["horizon"], "side": row["side"]},
                "n": row["n_oos"], "t_stat": row["t_stat"],
                "exp_r": row["sharpe_like"],
                "source": f"edge_search:{row['feature']}",
                # Trial count lives in the REPORT for audit, never on a hypothesis: anything
                # attached to a row travels into the gates and becomes a bar.
                "mechanism_status": mechanism_status,
                "mechanism_note": mechanism_note,
            })
    # NO BAR HERE, AND NO DEFLATION INPUT LEAVES HERE (principal 2026-08-26: "never use or
    # consider the harsher bars ever"). An earlier version printed sqrt(2 ln N) as "context":
    # even unused
    # as a filter, a threshold sitting next to the results is one a reader -- or a later edit --
    # will start treating as a verdict, and it competes with the only pipeline this desk has:
    # discovery -> backtest -> ten gates -> certificate -> forward -> live. The trial count is
    # carried to the gauntlet, where deflation is the canonical policy's job and nobody else's.

    # THE QUESTIONS GO SOMEWHERE A BRAIN WILL MEET THEM. Appended (never truncated) so a run
    # that finds nothing new does not erase what earlier runs asked, and deduped on
    # (symbol, feature, band, horizon, side) so a recurring effect asks once.
    if naming_queue:
        nq_path = OUT.parent / "mechanism_naming_queue.json"
        try:
            existing = json.loads(nq_path.read_text("utf-8"))
            existing = existing if isinstance(existing, list) else []
        except (OSError, ValueError):
            existing = []
        seen = {json.dumps({k: r.get(k) for k in
                            ("symbol", "feature", "band", "horizon", "side")},
                           sort_keys=True, default=str) for r in existing}
        added = 0
        for r in naming_queue:
            key = json.dumps({k: r.get(k) for k in
                              ("symbol", "feature", "band", "horizon", "side")},
                             sort_keys=True, default=str)
            if key not in seen:
                existing.append(r)
                seen.add(key)
                added += 1
        nq_path.write_text(json.dumps(existing[-4000:], indent=1, default=str), "utf-8")
        print(f"  mechanism-naming queue: +{added} question(s) "
              f"({len(naming_queue)} unnamed effects this run, {len(existing)} banked)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "searched_at": now.isoformat(timespec="seconds"),
        "symbols": len(results), "symbols_offered": len(symbols),
        "unsearched": unsearched, "total_trials": total_trials,
        "hypotheses": hypotheses, "per_symbol": results,
        "naming_queue_written": len(naming_queue),
        "arbiter": ("the canonical ten-gate policy, and nothing else. This searcher discovers "
                    "and reports; it sets no threshold of its own. Pipeline: discovery -> "
                    "backtest -> ten gates -> certificate -> forward window -> live."),
        "honesty": {
            "trials_counted": total_trials,
            "why": ("every (feature, band, horizon, direction) combination evaluated is counted "
                    "and carried into each hypothesis, so deflated Sharpe deflates against the "
                    "real multiplicity of the search rather than a flattering subset"),
            "oos_only": f"scored on the held-out {int((1 - FIT_FRACTION) * 100)}% only; "
                        f"band edges derived from the fit window so the condition itself does "
                        f"not leak",
            "selection": f"greedy on marginal independence, |corr| < {REDUNDANCY_CORR} against "
                         f"everything already chosen -- diversity is the objective, not a filter",
        },
    }, indent=1, default=str), "utf-8")
    print(f"edge search: {len(symbols)} symbol(s), {total_trials:,} trials evaluated, "
          f"{len(hypotheses)} DIVERSE hypotheses emitted")
    print(f"  all {len(hypotheses)} go to the ten gates AS DEFINED -- no bar set here, no "
          f"deflation input attached")
    _untest = sum(int(r.get("untestable_dropped") or 0) for r in results)
    print(f"  ({total_trials:,} trials recorded in the report for audit only; "
          f"{_untest} candidate(s) dropped as UNTESTABLE -- fewer than 60 distinct trading "
          f"days, which no gate can rule on)")
    for h in hypotheses[:8]:
        p = h["params"]
        print(f"   {h['symbol']:8} {p['feature']:18} band={p['band']} h={p['horizon']:>3} "
              f"side={p['side']:+d} t={h['t_stat']:.2f} n={h['n']}")
    return 0


def _cli_main() -> int:
    # ENTRYPOINT-PROOF IMPORT. The desk runs this as `py -3 research\\edge_search.py` from the
    # desk root, so sys.path[0] is research/ -- `research.job_lock` is then unimportable and the
    # searcher died at startup. Measured 2026-08-27: BOTH search legs silent ~25h, the docket
    # running on miners alone the whole time, while the run looked like a clean exit.
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))       # research/
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # desks/mt5
    try:
        from research.job_lock import exclusive_job
    except ModuleNotFoundError:
        from job_lock import exclusive_job

    # Headroom from the MEASURED peak on 2026-08-28 (4347MB RSS), not a guess -- but a
    # FIRST estimate all the same: tighten it from observed successful runs, never from
    # another guess. Below this the box cannot fit the job beside the live terminal.
    with exclusive_job("edge_search", need_mb=2000) as acquired:
        return main() if acquired else 75


if __name__ == "__main__":
    raise SystemExit(_cli_main())
