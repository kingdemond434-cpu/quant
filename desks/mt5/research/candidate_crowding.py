"""CANDIDATE CROWDING: a crowding score on every docket row, and the desk's OWN measured
pre/post-publication decay -- H6 (GAP_MAP row 132), the candidate half.

WHAT WAS MISSING (measured 2026-11-13): `crowding_state.json` last written 09-12 by a watcher on
dead endpoints; 0 of 57,538 docket rows carried a crowding field; no post-publication decay in
code. The allocator half of H6 (sleeve-level comomentum, CFTC pressure x alignment, unwind
loss) is #1137; this is the half that looks at a CANDIDATE before it is ever judged.

WHY A TIER-1 DESK WANTS IT. An edge many people know and trade is smaller, shorter-lived and
crashes together (McLean & Pontiff 2016: anomaly returns fall ~26% out of sample and ~58% after
publication; Lou & Polk comomentum). Two candidates with the same backtest are not the same bet
if one is a 1987 journal anomaly also sold as a YouTube strategy and the other is a mechanism
only this desk's genome produced. Knowing which is which is information about the FUTURE edge.

THE SCORE (0 = nobody else, 1 = everybody), per docket row, from free signals the desk already
holds -- each component MEASURED or UNMEASURED, never a guessed zero:

  public_footprint   how many distinct PUBLIC seats (forums, video, code platforms, copy-trading,
                     literature) donated the row's family, as a percentile across families
  literature         the family has a published origin (FAMILY_LITERATURE): 1.0 academic,
                     0.8 book/practitioner classic, scaled up with years since publication
  retail_velocity    rows of the family arriving from retail/video/forum seats in the last 30
                     days against the prior 90 (a narrative gaining speed), squashed to [0,1]
  cot_concentration  for a symbol with CFTC positioning on the axis: how extreme speculators'
                     net % of open interest is against its own 3-year range (latest knowable)
  originality        (subtracts) the row's sources are internal generators only and its family
                     has no literature: nobody outside this desk can be in it

  score = weighted mean of the MEASURED components (weights in WEIGHTS), coverage reported.

THE EDGE TREND, MEASURED ON THE DESK'S OWN BARS, FOR EVERY FAMILY. Because most publication
dates predate the bars, the split below rarely measures; so every runnable family (published or
not, the most-docketed first) also gets its net mean per trade by calendar year, a trade-weighted
least-squares slope across years, and that slope's projection to the current year as a ratio to
the family's whole-history mean (bootstrap 90% interval, resampling trades within years). That is
the arbitrage-in-progress McLean-Pontiff describe, observed rather than borrowed, and it is
TWO-SIDED: an edge that is growing projects above 1.

THE DECAY, MEASURED ON THE DESK'S OWN BARS. For each family with a dated publication, the
family is run on its docket's most common parameterisation over the desk's own H1 history, its
trades are split at the publication date, and net-of-cost mean return per trade before vs after
is compared (decay = 1 - post/pre, with a bootstrap 90% interval). Most publications predate the
bar history, so most families read UNMEASURED_NO_PRE_PUBLICATION_BARS: that is the honest answer,
and the borrowed McLean-Pontiff prior stands for them, labelled BORROWED, until a measurement
exists. Budgeted per pass, cursor across passes, cached by (family, params, bars mtime).

THE MULTIPLIER IS TWO-SIDED AND REPORT-ONLY (Growth Governance Rule 1/2). Each mark carries an
`expected_edge_multiplier` in [MULT_FLOOR, MULT_CEIL]: below 1 for crowded/published edges
(measured decay where it exists, else the borrowed prior scaled by the score), ABOVE 1 where the
desk measured an edge that grew after publication. Nothing here vetoes, caps, re-orders the
sealed judge or sizes a trade; the allocator may adopt it only with a Rule-1 proof and its
missed-growth line, which is #1137's door.

OUTPUTS: data/hypotheses/crowding_marks.json ({genome_id or identity: mark}),
reports/CANDIDATE_CROWDING.json (coverage, distribution, crowded families, decay table, COT
extremes), data/crowding_decay_cache.json. Hourly leg `candidate_crowding`.

    python desks/mt5/research/candidate_crowding.py [--budget-s 300] [--no-write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
INTEL = DESK / "data" / "intelligence"
COT_AXIS = DESK / "data" / "axes" / "cot.json"
MARKS = DESK / "data" / "hypotheses" / "crowding_marks.json"
DECAY_CACHE = DESK / "data" / "crowding_decay_cache.json"
REPORT = DESK / "reports" / "CANDIDATE_CROWDING.json"

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
BORROWED = "BORROWED"
WEIGHTS = {"public_footprint": 0.30, "literature": 0.25, "retail_velocity": 0.15,
           "cot_concentration": 0.30}
ORIGINALITY_CREDIT = 0.25
#: McLean & Pontiff (2016, J. Finance 71(1)): -26% out of sample, -58% post-publication.
MP_POST_PUBLICATION_DECAY = 0.58
MP_OUT_OF_SAMPLE_DECAY = 0.26
MULT_FLOOR, MULT_CEIL = 0.30, 1.50
#: Trades on each side of the publication date before a decay is a number.
MIN_TRADES_EACH_SIDE = 30
#: The edge-trend study: calendar years with at least this many trades, and at least this many
#: such years, before a slope is a number.
MIN_TRADES_PER_YEAR = 20
MIN_YEARS = 4
#: Unpublished families measured for edge trend per pass (most-docketed first, cursor-cached).
TREND_FAMILIES_PER_PASS = 25
BOOTSTRAP = 400
MAX_INTEL_FILE_BYTES = 20_000_000

#: Seats whose donations are PUBLIC (somebody outside the desk can read the same idea).
PUBLIC_SEATS = frozenset({
    "forexfactory", "reddit", "youtube", "video_anchor_exit", "tradingview",
    "tradingview_scripts", "mql5", "mql5_signals", "mql5_survivors", "mql5_prospector",
    "quantconnect", "github", "github_topics", "literature", "academic", "arxiv_qfin",
    "myfxbook", "myfxbook_outlook", "collective2", "darwinex", "duplitrade", "followme_cn",
    "hfm_pamm", "instaforex_copy", "roboforex_copyfx", "share4you", "octa_masters",
    "equiti_copy", "litefinance", "forexpeacearmy", "forextsd_cdx", "quant_se", "seasonality",
    "trading_latam", "aaii", "investing", "propfirm_boards", "fund_playbook", "anomalies",
    "firm_mining", "minfx_jp", "readitrades_africa", "mylivefx_br", "korea", "china",
    "tradingview_ideas", "fxblue", "fxblue_public", "mql5_ru_community", "stocktwits_macro",
    "stocktwits", "google_trends", "baidu_index", "amarkets", "fbs_tape"})
#: Of those, the retail / video / forum ones whose arrival rate is a narrative's speed.
RETAIL_SEATS = frozenset({
    "forexfactory", "reddit", "youtube", "video_anchor_exit", "tradingview",
    "tradingview_scripts", "mql5", "mql5_signals", "myfxbook", "myfxbook_outlook",
    "forexpeacearmy", "trading_latam", "propfirm_boards", "followme_cn", "minfx_jp",
    "readitrades_africa", "mylivefx_br", "litefinance", "tradingview_ideas", "stocktwits_macro",
    "stocktwits", "mql5_ru_community", "fxblue_public"})

#: family -> (first public citation, year, kind). Journal year, or first edition for books.
#: A family absent here is UNMEASURED for literature, never "unpublished".
FAMILY_LITERATURE: dict[str, tuple[str, int, str]] = {
    "trend_ma_cross": ("Moskowitz, Ooi & Pedersen, Time series momentum, JFE", 2012, "academic"),
    "multi_speed_trend": ("Moskowitz, Ooi & Pedersen, Time series momentum, JFE", 2012,
                          "academic"),
    "htf_anchor_trend": ("Moskowitz, Ooi & Pedersen, Time series momentum, JFE", 2012,
                         "academic"),
    "momentum_volgate": ("Moskowitz, Ooi & Pedersen, Time series momentum, JFE", 2012,
                         "academic"),
    "carry": ("Lustig, Roussanov & Verdelhan, Common risk factors in currency markets, RFS",
              2011, "academic"),
    "overnight_drift": ("Lou, Polk & Skouras, A tug of war: overnight versus intraday expected "
                        "returns, JFE", 2019, "academic"),
    "turn_of_month": ("Ariel, A monthly effect in stock returns, JFE", 1987, "academic"),
    "cot_positioning": ("Bessembinder, Systematic risk, hedging pressure, and risk premiums in "
                        "futures markets, RFS", 1992, "academic"),
    "style_premia": ("Asness, Moskowitz & Pedersen, Value and momentum everywhere, JF", 2013,
                     "academic"),
    "pca_residual": ("Avellaneda & Lee, Statistical arbitrage in the US equities market, "
                     "Quantitative Finance", 2010, "academic"),
    "cross_asset_residual": ("Avellaneda & Lee, Statistical arbitrage in the US equities "
                             "market, Quantitative Finance", 2010, "academic"),
    "lead_lag": ("Lo & MacKinlay, When are contrarian profits due to stock market "
                 "overreaction?, RFS", 1990, "academic"),
    "event_reaction": ("Ball & Brown, An empirical evaluation of accounting income numbers, "
                       "JAR", 1968, "academic"),
    "london_close_momentum": ("Melvin & Prins, Equity hedging and exchange rates at the London "
                              "4 p.m. fix, JFM", 2015, "academic"),
    "mean_reversion_rsi": ("Wilder, New Concepts in Technical Trading Systems", 1978, "book"),
    "adx_channel_hybrid": ("Wilder, New Concepts in Technical Trading Systems", 1978, "book"),
    "mean_reversion_bollinger": ("Bollinger, Bollinger on Bollinger Bands", 2001, "book"),
    "volatility_squeeze": ("Carter, Mastering the Trade (TTM squeeze)", 2005, "book"),
    "session_range_breakout": ("Crabel, Day Trading with Short Term Price Patterns and Opening "
                               "Range Breakout", 1990, "book"),
    "pin_bar_reversal": ("Nison, Japanese Candlestick Charting Techniques", 1991, "book"),
    "engulfing_reversal": ("Nison, Japanese Candlestick Charting Techniques", 1991, "book"),
}
#: Families whose callables need inputs beyond their own bars; the decay study skips them.
NEEDS_INPUTS = frozenset({"carry", "relative_value", "correlation_regime", "lead_lag",
                          "cross_asset_residual", "pca_residual", "style_premia",
                          "cot_positioning", "macro_conditional", "event_reaction",
                          "usd_session_shock", "triangle", "formula", "exit_operated"})
_DROP_PARAMS = ("timeframe", "session", "input_symbol", "input_source", "peer_symbol",
                "factor_symbols", "mechanism_genome", "crossed_slot")


# --------------------------------------------------------------------------- readers
def _json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _seat(src: Any) -> str:
    """The donating seat of a source tag. Regional hunters nest it ("miner:asia:collective2"
    -> collective2), so a part that names a known public seat wins over the routing prefix."""
    s = str(src or "").strip().lower()
    if s.startswith("miner:"):
        s = s[len("miner:"):]
    if s.startswith("ext_"):
        s = s[4:].split("_", 1)[0]
    parts = [p for p in s.split(":") if p]
    for p in parts:
        if p in PUBLIC_SEATS:
            return p
    return parts[0] if parts else ""


def row_key(r: Mapping[str, Any]) -> str:
    gid = r.get("genome_id")
    if gid:
        return str(gid)
    blob = json.dumps([r.get("symbol"), r.get("family"), r.get("params")], sort_keys=True,
                      default=str)
    return "id:" + hashlib.sha256(blob.encode()).hexdigest()[:16]


def row_seats(r: Mapping[str, Any]) -> set[str]:
    out = {_seat(s) for s in (r.get("contributing_sources") or [])}
    out.add(_seat(r.get("source")))
    out.discard("")
    return out


def intel_family_seats(root: Path = INTEL, budget_s: float = 60.0) -> dict[str, set[str]]:
    """{family: public seats whose donated rows name it}, from data/intelligence/<seat>/."""
    out: dict[str, set[str]] = defaultdict(set)
    t0 = time.monotonic()
    if not root.is_dir():
        return out
    for seat_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        seat = seat_dir.name.lower()
        if seat not in PUBLIC_SEATS:
            continue
        for f in sorted(seat_dir.glob("*.json")):
            if time.monotonic() - t0 > budget_s:
                return out
            try:
                if f.stat().st_size > MAX_INTEL_FILE_BYTES:
                    continue
            except OSError:
                continue
            d = _json(f)
            rows = d if isinstance(d, list) else (
                next((v for v in d.values() if isinstance(v, list)), [])
                if isinstance(d, dict) else [])
            for r in rows:
                if isinstance(r, dict) and r.get("family"):
                    out[str(r["family"])].add(seat)
    return out


# --------------------------------------------------------------------------- components
def percentile_map(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        return {}
    xs = sorted(values.values())
    n = len(xs)
    import bisect
    return {k: (bisect.bisect_right(xs, v) - 0.5) / n for k, v in values.items()}


def literature_component(family: str, now: datetime) -> tuple[float | None, dict[str, Any]]:
    lit = FAMILY_LITERATURE.get(family)
    if lit is None:
        return None, {"status": UNMEASURED, "why": "no dated publication on record for family"}
    cite, year, kind = lit
    age = max(0, now.year - year)
    base = 1.0 if kind == "academic" else 0.8
    # older and published -> more fully arbitraged; saturates by ~10 years
    v = base * (0.5 + 0.5 * min(1.0, age / 10.0))
    return v, {"status": MEASURED, "citation": cite, "year": year, "kind": kind,
               "years_public": age}


def retail_velocity(docket: Sequence[Mapping[str, Any]], now: datetime) -> dict[str, float]:
    """{family: squashed ratio of retail-seat arrivals, last 30d rate / prior 90d rate}."""
    recent: Counter[str] = Counter()
    prior: Counter[str] = Counter()
    for r in docket:
        if not (row_seats(r) & RETAIL_SEATS):
            continue
        t = _ts(r.get("first_seen"))
        if t is None:
            continue
        age = (now - t).days
        if 0 <= age < 30:
            recent[str(r.get("family"))] += 1
        elif 30 <= age < 120:
            prior[str(r.get("family"))] += 1
    out = {}
    for fam in set(recent) | set(prior):
        rate_r = recent[fam] / 30.0
        rate_p = prior[fam] / 90.0
        ratio = (rate_r + 1e-3) / (rate_p + 1e-3)
        out[fam] = 1.0 - 1.0 / (1.0 + ratio)          # 0.5 = steady, ->1 accelerating
    return out


def cot_concentration(path: Path = COT_AXIS, now: datetime | None = None,
                      lookback_days: int = 3 * 365) -> dict[str, dict[str, Any]]:
    """{symbol: {extremeness in [0,1], percentile, knowable_at}} from the latest KNOWABLE
    CFTC row against the symbol's own 3-year range. Never reads a row not yet knowable."""
    now = now or datetime.now(UTC)
    doc = _json(path)
    rows = doc.get("rows") if isinstance(doc, dict) else None
    by: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        t = _ts(r.get("knowable_at"))
        try:
            v = float(r.get("net_pct_oi"))
        except (TypeError, ValueError):
            continue
        if t is None or t > now or not math.isfinite(v):
            continue
        by[str(r.get("symbol"))].append((t, v))
    out = {}
    for sym, pts in by.items():
        pts.sort()
        last_t, last_v = pts[-1]
        hist = [v for t, v in pts if t >= last_t - timedelta(days=lookback_days)]
        if len(hist) < 52:
            continue
        pct = sum(1 for v in hist if v <= last_v) / len(hist)
        out[sym] = {"extremeness": round(abs(pct - 0.5) * 2.0, 4), "percentile": round(pct, 4),
                    "net_pct_oi": last_v, "knowable_at": last_t.isoformat(),
                    "crowd_side": "long" if last_v > 0 else "short", "n_weeks": len(hist)}
    return out


# --------------------------------------------------------------------------- measured decay
def _family_fn(family: str) -> Callable[..., Any] | None:
    """The registered callable (FAMILY_REGISTRY first, as the gauntlet resolves it)."""
    try:
        from mt5desk import families
        entry = (getattr(families, "FAMILY_REGISTRY", {}) or {}).get(family)
        fn = entry.get("func") if isinstance(entry, dict) else entry
        if callable(fn):
            return fn  # type: ignore[no-any-return]
        fn = getattr(families, f"family_{family}", None)
        if callable(fn):
            return fn  # type: ignore[no-any-return]
        from mt5desk import families_orthogonal as fo
        return fo.ORTHOGONAL_FAMILIES.get(family)  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001 -- unresolvable is a named skip
        return None


def _signature_params(fn: Callable[..., Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """Filter to the knobs the signature names -- the gauntlet's own rule, so the decay study
    runs the same cell the docket holds, never a silently different one."""
    import inspect
    try:
        names = set(list(inspect.signature(fn).parameters)[1:])
    except (TypeError, ValueError):
        return dict(params)
    return {k: v for k, v in params.items() if k in names}


def split_decay(pnl: Sequence[float], times: Sequence[Any], pub: datetime,
                seed: int = 7) -> dict[str, Any]:
    """Net mean per trade before vs after `pub`, decay = 1 - post/pre, bootstrap 90% CI."""
    import numpy as np
    pre = np.array([p for p, t in zip(pnl, times, strict=False) if _as_dt(t) < pub], float)
    post = np.array([p for p, t in zip(pnl, times, strict=False) if _as_dt(t) >= pub], float)
    out: dict[str, Any] = {"n_pre": int(pre.size), "n_post": int(post.size)}
    if pre.size < MIN_TRADES_EACH_SIDE:
        out.update(status="UNMEASURED_NO_PRE_PUBLICATION_BARS" if pre.size == 0 else
                   "UNMEASURED_FEW_PRE_TRADES")
        return out
    if post.size < MIN_TRADES_EACH_SIDE:
        out.update(status="UNMEASURED_FEW_POST_TRADES")
        return out
    m_pre, m_post = float(pre.mean()), float(post.mean())
    out.update(mean_pre=m_pre, mean_post=m_post)
    if m_pre <= 0:
        out.update(status="UNMEASURED_NO_PRE_PUBLICATION_EDGE",
                   why="the family earned nothing net before publication on these bars")
        return out
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(BOOTSTRAP):
        a = rng.choice(pre, pre.size).mean()
        b = rng.choice(post, post.size).mean()
        if a > 0:
            boots.append(1.0 - b / a)
    out.update(status=MEASURED, decay=round(1.0 - m_post / m_pre, 4),
               ci90=[round(float(np.quantile(boots, 0.05)), 4),
                     round(float(np.quantile(boots, 0.95)), 4)] if boots else None)
    return out


def edge_trend(pnl: Sequence[float], times: Sequence[Any], now: datetime,
               seed: int = 11) -> dict[str, Any]:
    """Yearly net mean per trade, trade-weighted LS slope, projection to `now` / overall mean."""
    import numpy as np
    by_year: dict[int, list[float]] = defaultdict(list)
    for p, t in zip(pnl, times, strict=False):
        by_year[_as_dt(t).year].append(float(p))
    years = sorted(y for y, v in by_year.items() if len(v) >= MIN_TRADES_PER_YEAR)
    out: dict[str, Any] = {"years": {str(y): {"n": len(by_year[y]),
                                              "mean": round(float(np.mean(by_year[y])), 6)}
                                     for y in years}}
    if len(years) < MIN_YEARS:
        out["status"] = "UNMEASURED_FEW_YEARS"
        return out
    allv = np.concatenate([np.asarray(by_year[y], float) for y in years])
    overall = float(allv.mean())
    out["overall_mean"] = round(overall, 6)
    if overall <= 0:
        out.update(status="UNMEASURED_NO_EDGE",
                   why="the family earns nothing net on these bars; there is no edge to decay")
        return out

    def fit(groups: Mapping[int, np.ndarray]) -> tuple[float, float]:
        x = np.array(years, float)
        y = np.array([groups[yr].mean() for yr in years])
        w = np.array([groups[yr].size for yr in years], float)
        xm = float((w * x).sum() / w.sum())
        ym = float((w * y).sum() / w.sum())
        sl = float((w * (x - xm) * (y - ym)).sum() / max(1e-12, (w * (x - xm) ** 2).sum()))
        return sl, ym + sl * (now.year - xm)

    arrs = {y: np.asarray(by_year[y], float) for y in years}
    slope, proj = fit(arrs)
    rng = np.random.default_rng(seed)
    ratios = []
    for _ in range(BOOTSTRAP):
        bs = {y: rng.choice(a, a.size) for y, a in arrs.items()}
        bm = float(np.concatenate(list(bs.values())).mean())
        if bm > 0:
            ratios.append(fit(bs)[1] / bm)
    out.update(status=MEASURED, slope_per_year=round(slope, 7),
               relative_slope_per_year=round(slope / overall, 4),
               projected_ratio_now=round(proj / overall, 4),
               ci90=[round(float(np.quantile(ratios, 0.05)), 4),
                     round(float(np.quantile(ratios, 0.95)), 4)] if ratios else None,
               n_years=len(years))
    return out


def _as_dt(t: Any) -> datetime:
    import pandas as pd
    ts = pd.Timestamp(t)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.to_pydatetime()


def measure_decay(docket: Sequence[Mapping[str, Any]], *, budget_s: float,
                  cache: dict[str, Any], bars: Callable[[str], Any] | None = None,
                  max_symbols: int = 6, now: datetime | None = None) -> dict[str, Any]:
    """Per dated family: run its modal parameterisation on its most-docketed symbols, split
    trades at the publication date, pool, and record. Cached; budgeted."""
    from research import proposer_common as pc
    bars = bars or pc.bars
    meta = pc.universe_meta()
    t0 = time.monotonic()
    by_fam: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in docket:
        by_fam[str(r.get("family"))].append(r)
    out: dict[str, Any] = {}
    now = now or datetime.now(UTC)
    unpublished = [f for f, _n in Counter(str(r.get("family")) for r in docket).most_common()
                   if f not in FAMILY_LITERATURE and f not in NEEDS_INPUTS]
    todo: list[tuple[str, int | None]] = [(f, y) for f, (_c, y, _k) in
                                          sorted(FAMILY_LITERATURE.items())]
    todo += [(f, None) for f in unpublished[:TREND_FAMILIES_PER_PASS]]
    for fam, year in todo:
        if fam in NEEDS_INPUTS:
            out[fam] = {"status": "UNMEASURED_NEEDS_INPUTS",
                        "why": "family needs peer/axis inputs beyond its own bars"}
            continue
        rows = by_fam.get(fam) or []
        if not rows:
            out[fam] = {"status": "UNMEASURED_NOT_ON_DOCKET"}
            continue
        fn = _family_fn(fam)
        if fn is None:
            out[fam] = {"status": "UNMEASURED_NO_IMPLEMENTATION"}
            continue
        modal = Counter(json.dumps({k: v for k, v in (r.get("params") or {}).items()
                                    if k not in _DROP_PARAMS}, sort_keys=True, default=str)
                        for r in rows).most_common(1)[0][0]
        params = _signature_params(fn, json.loads(modal))
        syms = [s for s, _n in Counter(str(r.get("symbol")) for r in rows).most_common(
            max_symbols)]
        key = hashlib.sha256(json.dumps([fam, params, syms, year, now.year],
                                        sort_keys=True, default=str).encode()).hexdigest()[:16]
        if key in cache and cache[key].get("family") == fam:
            out[fam] = {**cache[key], "cached": True}
            continue
        if time.monotonic() - t0 > budget_s:
            out[fam] = {"status": "DEFERRED_BUDGET"}
            continue
        pnl: list[float] = []
        times: list[Any] = []
        used: list[str] = []
        for sym in syms:
            d = bars(sym)
            if d is None or len(d) < 500:
                continue
            cost = pc.cost_frac(sym, meta, d["close"])
            if cost is None:
                continue
            try:
                sig = fn(d, **params)
            except Exception:  # noqa: BLE001 -- a parameterisation the family refuses
                continue
            sc = pc.screen(d, sig, cost, pc.artifact_hours(d), detail=True)
            if not sc or not sc.get("pnl"):
                continue
            pnl += list(sc["pnl"])
            times += [d.index[i] for i in sc["entry_pos"]]
            used.append(sym)
        if not pnl:
            res: dict[str, Any] = {"status": "UNMEASURED_NO_TRADES"}
        elif year is None:
            res = {"status": "UNMEASURED_UNPUBLISHED",
                   "why": "no dated publication: nothing to split at; the trend stands alone"}
        else:
            res = split_decay(pnl, times, datetime(year, 1, 1, tzinfo=UTC))
        res["trend"] = edge_trend(pnl, times, now) if pnl else {"status": "UNMEASURED_NO_TRADES"}
        res.update(family=fam, params=params, symbols=used, publication_year=year,
                   bars_first=str(min(times)) if times else None)
        cache[key] = res
        out[fam] = res
    return out


# --------------------------------------------------------------------------- marks
#: Prior s.d. of (projected ratio - 1): edges do not usually halve or double in a few years.
TREND_PRIOR_SD = 0.5


def shrink_trend(trend: Mapping[str, Any]) -> tuple[float, float]:
    """Normal-normal shrinkage of the projected ratio toward 1 by its own bootstrap precision.

    A yearly slope over nine noisy years can project anything; its interval says how much. With
    se from the 90% interval, the posterior mean of (ratio - 1) is (ratio - 1) x tau^2/(tau^2 +
    se^2): a tight measurement moves the multiplier, a wide one barely does. Both directions.
    """
    m = float(trend["projected_ratio_now"])
    ci = trend.get("ci90")
    if not ci:
        return 1.0, 0.0
    se = max(1e-9, (float(ci[1]) - float(ci[0])) / 3.29)
    k = TREND_PRIOR_SD ** 2 / (TREND_PRIOR_SD ** 2 + se ** 2)
    return 1.0 + k * (m - 1.0), k


def multiplier(score: float | None, lit: dict[str, Any], decay: Mapping[str, Any] | None,
               now: datetime | None = None) -> tuple[float, str]:
    """Two-sided expected-edge multiplier and its basis. Report-only."""
    if decay and decay.get("status") == MEASURED:
        m = 1.0 - float(decay["decay"])
        return max(MULT_FLOOR, min(MULT_CEIL, m)), f"{MEASURED}: own pre/post-publication split"
    trend = (decay or {}).get("trend") or {}
    if trend.get("status") == MEASURED:
        m, _shrink = shrink_trend(trend)
        return max(MULT_FLOOR, min(MULT_CEIL, m)), (
            f"MEASURED_TREND: own yearly edge slope projected to {(now or datetime.now(UTC)).year}, "
            f"precision-shrunk toward 1")
    if lit.get("status") == MEASURED:
        base = MP_POST_PUBLICATION_DECAY if lit.get("kind") == "academic" else \
            MP_OUT_OF_SAMPLE_DECAY
        s = 0.5 if score is None else score
        m = 1.0 - base * (0.5 + 0.5 * s)
        return max(MULT_FLOOR, min(MULT_CEIL, m)), (
            f"{BORROWED}: McLean-Pontiff {'post-publication' if base > 0.3 else 'out-of-sample'}"
            f" decay x crowding score; replaced by the desk's own split when measurable")
    return 1.0, "no published origin and no measurement: neutral"


def mark_row(r: Mapping[str, Any], *, now: datetime, footprint_pct: Mapping[str, float],
             velocity: Mapping[str, float], cot: Mapping[str, Mapping[str, Any]],
             decay: Mapping[str, Any]) -> dict[str, Any]:
    fam = str(r.get("family") or "")
    sym = str(r.get("symbol") or "")
    comps: dict[str, Any] = {}
    lit_v, lit = literature_component(fam, now)
    comps["literature"] = lit_v
    comps["public_footprint"] = footprint_pct.get(fam)
    comps["retail_velocity"] = velocity.get(fam)
    c = cot.get(sym)
    comps["cot_concentration"] = c["extremeness"] if c else None
    measured = {k: v for k, v in comps.items() if v is not None}
    seats = row_seats(r)
    original = bool(seats) and not (seats & PUBLIC_SEATS) and lit_v is None
    if measured:
        w = sum(WEIGHTS[k] for k in measured)
        score: float | None = sum(WEIGHTS[k] * v for k, v in measured.items()) / w
        if original and score is not None:
            score = max(0.0, score - ORIGINALITY_CREDIT)
    else:
        score = None
    mult, basis = multiplier(score, lit, decay.get(fam), now)
    return {"symbol": sym, "family": fam,
            "crowding_score": None if score is None else round(score, 4),
            "status": MEASURED if score is not None else UNMEASURED,
            "components": {k: (None if v is None else round(float(v), 4))
                           for k, v in comps.items()},
            "coverage": f"{len(measured)}/{len(WEIGHTS)}", "original_mechanism": original,
            "public_seats": sorted(seats & PUBLIC_SEATS),
            "literature": lit if lit.get("status") == MEASURED else None,
            "cot": c, "expected_edge_multiplier": round(mult, 4), "multiplier_basis": basis}


def run(*, budget_s: float = 300.0, now: datetime | None = None,
        docket: list[dict[str, Any]] | None = None, write: bool = True,
        bars: Callable[[str], Any] | None = None,
        intel_root: Path = INTEL, cot_path: Path = COT_AXIS) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    if docket is None:
        got = _json(DOCKET)
        docket = got if isinstance(got, list) else []
    rows = [r for r in docket if isinstance(r, dict) and r.get("family")]
    seats_by_fam: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        seats_by_fam[str(r["family"])] |= row_seats(r) & PUBLIC_SEATS
    for fam, s in intel_family_seats(intel_root, budget_s=min(60.0, budget_s / 4)).items():
        seats_by_fam[fam] |= s
    footprint = percentile_map({f: float(len(s)) for f, s in seats_by_fam.items()})
    velocity = retail_velocity(rows, now)
    cot = cot_concentration(cot_path, now)
    cache = _json(DECAY_CACHE)
    cache = cache if isinstance(cache, dict) else {}
    remaining = max(0.0, budget_s - (time.monotonic() - t0))
    try:
        decay = measure_decay(rows, budget_s=remaining * 0.8, cache=cache, bars=bars, now=now)
    except Exception as exc:  # noqa: BLE001 -- the marks still stand on the other components
        decay = {"_error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    marks = {row_key(r): mark_row(r, now=now, footprint_pct=footprint, velocity=velocity,
                                  cot=cot, decay=decay) for r in rows}
    scored = [m for m in marks.values() if m["status"] == MEASURED]
    fam_scores: dict[str, list[float]] = defaultdict(list)
    for m in scored:
        fam_scores[m["family"]].append(float(m["crowding_score"]))
    fam_table = sorted(({"family": f, "n": len(v), "mean_score": round(sum(v) / len(v), 4),
                         "public_seats": len(seats_by_fam.get(f, ())),
                         "literature": (FAMILY_LITERATURE.get(f) or (None,))[0]}
                        for f, v in fam_scores.items()), key=lambda x: -x["mean_score"])
    hist = Counter(min(9, int(float(m["crowding_score"]) * 10)) for m in scored)
    # CROWDING-ADJUSTED SURVIVOR YIELD (the Hourly pass ALPHA RICHNESS metric): each docket row
    # counted at its expected-edge multiplier, so 1,000 copies of a 1987 anomaly do not read as
    # 1,000 units of future edge. Two-sided: a row whose edge measurably grew counts above 1.
    adj = sum(float(m["expected_edge_multiplier"]) for m in marks.values())
    adj_by_fam: dict[str, float] = defaultdict(float)
    for m in marks.values():
        adj_by_fam[m["family"]] += float(m["expected_edge_multiplier"])
    report = {
        "generated_at": now.isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/candidate_crowding.py", "gap_row": "H6 (GAP_MAP 132)",
        "docket_rows": len(rows), "rows_with_crowding_field": len(scored),
        "rows_unmeasured": len(rows) - len(scored),
        "coverage": round(len(scored) / len(rows), 4) if rows else UNMEASURED,
        "score_histogram_deciles": {f"{k / 10:.1f}": hist[k] for k in sorted(hist)},
        "original_mechanism_rows": sum(1 for m in marks.values() if m["original_mechanism"]),
        "crowding_adjusted_rows": round(adj, 1),
        "crowding_adjusted_share": round(adj / len(rows), 4) if rows else UNMEASURED,
        "crowding_adjusted_by_family": {f: round(v, 1) for f, v in sorted(
            adj_by_fam.items(), key=lambda kv: -kv[1])[:40]},
        "multiplier_basis_counts": dict(Counter(m["multiplier_basis"].split(":", 1)[0]
                                                for m in marks.values())),
        "families_most_crowded": fam_table[:25], "families_least_crowded": fam_table[-15:],
        "decay": decay,
        "decay_measured_families": sorted(f for f, v in decay.items()
                                          if isinstance(v, dict) and v.get("status") == MEASURED),
        "trend_measured_families": {
            f: {**{k: v["trend"].get(k) for k in ("projected_ratio_now", "ci90",
                                                  "relative_slope_per_year", "n_years")},
                "shrunk_multiplier": round(shrink_trend(v["trend"])[0], 4),
                "shrink_weight": round(shrink_trend(v["trend"])[1], 4)}
            for f, v in sorted(decay.items())
            if isinstance(v, dict) and (v.get("trend") or {}).get("status") == MEASURED},
        "cot_extremes": dict(sorted(cot.items(), key=lambda kv: -kv[1]["extremeness"])[:15]),
        "weights": WEIGHTS, "borrowed_prior": {
            "source": "McLean & Pontiff (2016), Does academic research destroy stock return "
                      "predictability?, J. Finance 71(1)",
            "post_publication_decay": MP_POST_PUBLICATION_DECAY,
            "out_of_sample_decay": MP_OUT_OF_SAMPLE_DECAY},
        "authority": ("REPORT-ONLY: the multiplier is two-sided and reaches no gate, judge order "
                      "or size; the allocator adopts it only with a Rule-1 proof and its "
                      "missed-growth line"),
        "status": "OK" if rows else UNMEASURED,
        "elapsed_s": round(time.monotonic() - t0, 1),
    }
    if write:
        _atomic(MARKS, {"generated_at": report["generated_at"],
                        "fields": list(COMPACT_FIELDS), "marks": compact_marks(marks)})
        _atomic(DECAY_CACHE, cache)
        _atomic(REPORT, report)
    report["_marks"] = marks
    return report


#: One row per docket row, positional, so 57k marks stay a few MB: the full per-component detail
#: lives per FAMILY in the report and is re-derivable per row with `mark_row`.
COMPACT_FIELDS = ("crowding_score", "expected_edge_multiplier", "coverage", "original_mechanism",
                  "basis", "cot_extremeness")


def compact_marks(marks: Mapping[str, Mapping[str, Any]]) -> dict[str, list[Any]]:
    out = {}
    for k, m in marks.items():
        c = m.get("cot") or {}
        out[k] = [m.get("crowding_score"), m.get("expected_edge_multiplier"), m.get("coverage"),
                  bool(m.get("original_mechanism")),
                  str(m.get("multiplier_basis") or "").split(":", 1)[0],
                  c.get("extremeness")]
    return out


def read_mark(key: str, path: Path = MARKS) -> dict[str, Any] | None:
    """A reader's door: one docket row's mark by genome_id (or `row_key` identity)."""
    doc = _json(path)
    if not isinstance(doc, dict):
        return None
    row = (doc.get("marks") or {}).get(key)
    if not isinstance(row, list):
        return None
    return dict(zip(doc.get("fields") or COMPACT_FIELDS, row, strict=False))


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, separators=(",", ":"), default=str), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    rep = run(budget_s=a.budget_s, write=not a.no_write)
    print(f"candidate_crowding: status={rep['status']} rows={rep['docket_rows']} "
          f"scored={rep['rows_with_crowding_field']} coverage={rep['coverage']} "
          f"adjusted_share={rep['crowding_adjusted_share']} "
          f"decay_measured={','.join(rep['decay_measured_families']) or '-'} "
          f"trend_measured={len(rep['trend_measured_families'])} "
          f"elapsed={rep['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
