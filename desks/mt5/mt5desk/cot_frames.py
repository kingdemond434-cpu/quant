"""Per-symbol CFTC positioning columns, point-in-time, oriented to the MT5 symbol.

WHY THIS EXISTS (2026-10-06). The `positioning_flow` alpha cluster held no certificate while
three CFTC report families sat in git under `desks/mt5/data/`: legacy (`cot/`, non-commercial and
commercial), Traders in Financial Futures (`cot_tff/`, leveraged money, asset managers, dealers)
and disaggregated (`cot_disagg/`, managed money and swap dealers). The sealed gauntlet's one COT
door, `orthogonal_sweep._cot_frame`, read only `data/cot_zcache.parquet` -- a gitignored z-score
cache of ONE column ("net", legacy non-commercial) that exists on the trading box alone -- so
every positioning-change hypothesis about any other trader class was unbuildable, and on a tree
without the cache even the level hypothesis built with `cot=None`.

This module turns the in-git parquets into the columns the family reads. It is a READER: it
fetches nothing and writes nothing.

THE CLOCK. Every report is as of TUESDAY and published the same week's FRIDAY at 15:30 ET. The
series are put on EXACTLY the label `_cot_frame` already uses for the cache -- resampled to
`W-FRI` and shifted by `orthogonal_sweep.COT_RELEASE_LAG_DAYS` -- so a column joined here can never
be read earlier than the "net" column beside it, and the reasoning for that lag (Monday is after
the release under every daylight-saving and broker-clock combination) is stated once, there.
A report the CFTC published LATE (a holiday or the 2025 shutdown backlog) is not modelled: the
parquets carry no release date, the same limitation the cache has.

THE SIGN. CFTC currency futures are quoted USD per foreign unit, so a long JPY future is a SHORT
USDJPY position. Every column is oriented so POSITIVE means the trader class is long the MT5
symbol; the reciprocal symbols are negated (the rule `scripts/refresh_cot_zcache.INVERT` applies).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
LEGACY = DATA / "cot"
TFF = DATA / "cot_tff"
DISAGG = DATA / "cot_disagg"

#: The z window of the cache's "net" column (`scripts/refresh_cot_zcache.ZWIN`), reproduced when
#: the cache is absent so the default family construction means the same thing on either tree.
ZWIN = 52
ZMIN = 12

#: symbols quoted USD per foreign unit: a long foreign-currency future is a SHORT position here.
INVERT = frozenset({"USDJPY", "USDCHF", "USDCAD"})

#: MT5 symbol -> (legacy slug, TFF slug + market-name prefixes, disaggregated slug). Explicit and
#: exact: a TFF file holds cross-rate contracts too (EURO FX/BRITISH POUND XRATE sits in both the
#: EUR and GBP files), so a market is admitted only on its own name's prefix.
SOURCES: dict[str, tuple[str | None, tuple[str, tuple[str, ...]] | None, str | None]] = {
    "EURUSD": (None, ("eur", ("EURO FX - ",)), None),
    "GBPUSD": ("gbp", ("gbp", ("BRITISH POUND - ", "BRITISH POUND STERLING - ")), None),
    "AUDUSD": ("aud", ("aud", ("AUSTRALIAN DOLLAR - ",)), None),
    "NZDUSD": ("nzd", ("nzd", ("NEW ZEALAND DOLLAR - ", "NZ DOLLAR - ")), None),
    "USDJPY": ("jpy", ("jpy", ("JAPANESE YEN - ",)), None),
    "USDCAD": ("cad", ("cad", ("CANADIAN DOLLAR - ",)), None),
    "USDCHF": ("chf", ("chf", ("SWISS FRANC - ",)), None),
    "XAUUSD": ("gold", None, "gold"),
    "XAGUSD": ("silver", None, "silver"),
}

#: column -> (report family, trader class). The positioning-change cells name these.
COLUMNS: dict[str, tuple[str, str]] = {
    "noncomm_net": ("legacy", "non-commercial (large speculators)"),
    "comm_net": ("legacy", "commercial (hedgers)"),
    "lev_net": ("tff", "leveraged money (hedge funds, CTAs)"),
    "am_net": ("tff", "asset managers (institutional)"),
    "dealer_net": ("tff", "dealers (sell side)"),
    "mm_net": ("disaggregated", "managed money"),
    "swap_net": ("disaggregated", "swap dealers"),
}


def release_lag_days() -> int:
    """The one lag the desk applies to a COT label. Read from the sweep so the two cannot drift."""
    try:
        from research.orthogonal_sweep import COT_RELEASE_LAG_DAYS
        return int(COT_RELEASE_LAG_DAYS)
    except Exception:
        return 3


def to_release_clock(series: pd.Series) -> pd.Series:
    """A Tuesday-dated weekly series, re-labelled at the first instant it was public.

    Identical to the cache path in `_cot_frame`: `W-FRI` (the Friday of the report's week) plus
    the release lag."""
    s = series.astype(float).dropna().sort_index()
    if s.empty:
        return s
    s = s[~s.index.duplicated(keep="last")]
    s = s.resample("W-FRI").last().dropna()
    s.index = s.index + pd.Timedelta(days=release_lag_days())
    return s


def _read(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if df.empty or "report_date" not in df.columns:
        return None
    df = df.copy()
    df["report_date"] = pd.to_datetime(df["report_date"], utc=True, errors="coerce")
    return df.dropna(subset=["report_date"])


def _net(df: pd.DataFrame, long_col: str, short_col: str) -> pd.Series | None:
    if long_col not in df.columns or short_col not in df.columns:
        return None
    net = (pd.to_numeric(df[long_col], errors="coerce")
           - pd.to_numeric(df[short_col], errors="coerce"))
    return net.groupby(df["report_date"]).sum(min_count=1).dropna()


def raw_columns(symbol: str) -> dict[str, pd.Series]:
    """{column: Tuesday-dated weekly net, oriented to `symbol`} for every source on disk."""
    spec = SOURCES.get(str(symbol or "").upper())
    if spec is None:
        return {}
    legacy, tff, disagg = spec
    out: dict[str, pd.Series] = {}
    if legacy:
        df = _read(LEGACY / f"{legacy}.parquet")
        if df is not None:
            for col, (lo, sh) in {
                    "noncomm_net": ("noncomm_positions_long_all", "noncomm_positions_short_all"),
                    "comm_net": ("comm_positions_long_all", "comm_positions_short_all")}.items():
                s = _net(df, lo, sh)
                if s is not None and len(s):
                    out[col] = s
    if tff:
        slug, prefixes = tff
        df = _read(TFF / f"{slug}.parquet")
        if df is not None and "market" in df.columns:
            mk = df["market"].astype(str).str.upper()
            df = df[mk.map(lambda m: any(m.startswith(p) for p in prefixes))]
            for col, (lo, sh) in {"lev_net": ("lm_l", "lm_s"), "am_net": ("am_l", "am_s"),
                                  "dealer_net": ("dealer_l", "dealer_s")}.items():
                s = _net(df, lo, sh)
                if s is not None and len(s):
                    out[col] = s
    if disagg:
        df = _read(DISAGG / f"{disagg}.parquet")
        if df is not None:
            for col, (lo, sh) in {
                    "mm_net": ("m_money_positions_long_all", "m_money_positions_short_all"),
                    "swap_net": ("swap_positions_long_all", "swap__positions_short_all")}.items():
                s = _net(df, lo, sh)
                if s is not None and len(s):
                    out[col] = s
    if symbol.upper() in INVERT:
        out = {k: -v for k, v in out.items()}
    return out


def zscore(net: pd.Series) -> pd.Series:
    """The cache's "net" semantics: a 52-week rolling z of the weekly net."""
    mu = net.rolling(ZWIN, min_periods=ZMIN).mean()
    sd = net.rolling(ZWIN, min_periods=ZMIN).std(ddof=0)
    return ((net - mu) / sd.where(sd > 0)).dropna()


def frame(symbol: str) -> pd.DataFrame | None:
    """Every positioning column for `symbol` on the release clock, or None when it has none.

    Includes "net" (the z of legacy non-commercial net) so a tree without the box's cache builds
    the family's default construction instead of refusing it."""
    cols = raw_columns(symbol)
    if not cols:
        return None
    out = {k: to_release_clock(v) for k, v in cols.items()}
    if "noncomm_net" in cols:
        out["net"] = to_release_clock(zscore(cols["noncomm_net"]))
    df = pd.DataFrame(out).sort_index()
    return df if not df.empty else None


def enrich(base: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """`base` (the cache's one-column frame) with every in-git column joined on the SAME label.

    The base's "net" is never replaced: the cache is the box's authority for that column."""
    extra = frame(symbol)
    if extra is None:
        return base
    extra = extra.drop(columns=[c for c in extra.columns if c in base.columns])
    if extra.empty:
        return base
    # LEFT, so the cache's own rows -- and therefore every default-construction cell already
    # judged on the box -- are byte-identical; a column is only ever ADDED beside them.
    return base.join(extra, how="left")


def available(symbol: str) -> list[str]:
    """Columns `frame(symbol)` will carry (positioning-change columns only, not "net")."""
    return sorted(raw_columns(symbol))
