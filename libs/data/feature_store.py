"""Immutable, hashed feature blocks so a million experiments share one computation.

    FeatureID = hash(name, code_version, params, data_hash, source, availability_rule[, external])

The High-Flyer lesson stripped to what one VPS can use: every research worker reuses common
feature matrices instead of recomputing them, and a feature's identity is what produced it --
the code version, the parameters, the bars it was computed from, the SOURCE the numbers came
from and the RULE that says when each value became knowable -- never its filename. A feature
block with the same id IS the same numbers, so a cache hit is exact, and a changed bar history,
a changed formula, a changed source or a changed availability rule produces a different id
rather than a silently different block under the same name.

WHAT IS STORED. Numpy arrays keyed by id under `data/features/`, with a JSON sidecar that is the
feature's WAREHOUSE RECORD (principal's order, 2026-09-05): the five timestamps -- event_time
(the newest bar the block describes), published_time (when the producer released the newest
input), available_time (when the desk could have known the block's newest value), ingested_time
(when this store computed it), revision_time (when the input was last restated, if ever) --
plus source / provider / source_version / raw_hash / feature_code_hash, units / currency /
timezone, the quality flags (latency_s, freshness_s, coverage_frac, revision_status), the
lifecycle `status` and the `roi` line that `research/feature_roi.py` fills in daily. The
availability rule is per feature: a feature at bar t uses bars <= t and the store refuses a
compute function that is not causal, tested by recomputing on a truncated frame; an external
feature states its own rule (a COT report is knowable from its release, not its date).

MIGRATION (2026-09-05): FOLDING SOURCE AND AVAILABILITY INTO THE ID CHANGED EVERY ID. Blocks
written under the previous formula -- hash(name, code_version, params, data_hash[, external])
with `LEGACY_CODE_VERSION` -- are NOT invalidated: on a miss the store looks the legacy id up,
and when a legacy block exists it is ADOPTED -- its array is re-keyed under the new id and its new
sidecar carries `legacy_id` and `adopted_from_legacy: true`, so a warehouse built yesterday is
read through rather than recomputed, and the census reports how many blocks arrived that way.
`legacy_feature_id` is the old formula, byte for byte, kept so an old id is always readable.
Nothing deletes a legacy block; a person does, once the census shows zero adoptions.

THE REGISTRY is the common vocabulary: returns, volatility, ranges, ATR, session hour, activity
and spread percentiles, driver residuals, alpha-grammar expressions. Each entry is a pure
function of (bars, params) -> np.ndarray aligned to the bars' index.

THE PARTICIPANT-FLOW LAYER (2026-09-04). Price alone cannot say WHO is trading, and every
positioning story the desk has told so far was told from price. Four features name the
participants the desk can actually observe off-box: the broker's own tick flow (`tick_imbalance`,
`session_participation`), the broker's overnight financing (`swap_long` / `swap_short` /
`swap_diff` -- the carry the desk PAYS, from `universe.json`), and the CFTC's weekly speculative
positioning (`cot_z`) joined POINT-IN-TIME: a report dated Tuesday is public Friday evening, so a
bar may only see a report whose `available_time` is at or before the bar. Every one of them is
causal by construction and is refused by `check_causal` if it is not.

FEATURES WITH INPUTS OUTSIDE THE BARS declare an `external` identity -- a string naming the files
they read -- that is folded into the feature id. Without it a refreshed COT file or a re-quoted
swap would be served from the cache under the same id, which is exactly the "silently different
block under the same name" the id exists to prevent. Features that read only the bars carry no
external identity and their ids are unchanged.

DEGRADATION IS RECORDED, NEVER RAISED. A symbol with no COT market, a frame without
`tick_volume`, a symbol missing from the universe: each returns an all-NaN block and writes WHY
into `LAST_REASON[name]`, so a caller that sees a NaN column can read the reason instead of
guessing.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "desks" / "mt5" / "data" / "features"
CODE_VERSION = "2026-09-05.1"
#: The code version the pre-warehouse id formula was sealed under. `legacy_feature_id` uses it,
#: so a block written before source and availability were folded in is still findable.
LEGACY_CODE_VERSION = "2026-09-04.1"

#: The default source and availability rule: the broker's own H1 bars, knowable at each bar's
#: close. Every feature that reads only the bars carries these; external features declare theirs.
DEFAULT_SOURCE = "bars"
DEFAULT_PROVIDER = "fusion_markets_mt5"
DEFAULT_AVAILABILITY = "feature at bar t uses bars <= t only; knowable at the close of bar t"
DEFAULT_REVISION = ("none: broker bars are not restated; a refreshed history changes data_hash "
                    "and re-keys the block")
#: Lifecycle state every block is born in. `libs.data.feature_lifecycle` owns the transitions.
STATUS_NEW = "NEW"
#: Files larger than this are identified by size and mtime rather than hashed byte by byte.
RAW_HASH_MAX_BYTES = 64 * 1024 * 1024

Compute = Callable[[pd.DataFrame, dict[str, Any]], np.ndarray]
#: Identity of a feature's inputs OUTSIDE the bars (files on disk), as a function of params.
External = Callable[[dict[str, Any]], str]

#: Why the last compute of a participant-flow feature degraded, by feature name. A feature that
#: cannot be built returns all-NaN and writes its reason here; a feature that succeeds clears
#: its entry and writes what it used to `LAST_DETAIL`.
LAST_REASON: dict[str, str] = {}
LAST_DETAIL: dict[str, str] = {}
#: What an external feature's last compute knew about its inputs -- published_time,
#: source_version, raw_hash, revision_time -- so the sidecar records the producer's clock and
#: not only the store's. Bars-only features write nothing here; the store fills theirs from the
#: bars themselves.
LAST_PROVENANCE: dict[str, dict[str, Any]] = {}

_DESK_DATA = ROOT / "desks" / "mt5" / "data"
UNIVERSE_JSON = _DESK_DATA / "universe" / "universe.json"
#: COT sources in the order they are searched: the legacy report (longest history, non-commercial
#: = speculative), the Traders-in-Financial-Futures report (leveraged funds), the disaggregated
#: commodity report (managed money). Each carries the net-speculative column pair to use.
COT_SOURCES: tuple[tuple[Path, str, str], ...] = (
    (_DESK_DATA / "cot", "noncomm_positions_long_all", "noncomm_positions_short_all"),
    (_DESK_DATA / "cot_tff", "lm_l", "lm_s"),
    (_DESK_DATA / "cot_disagg", "m_money_positions_long_all", "m_money_positions_short_all"),
)
#: A CFTC report dated Tuesday is released Friday ~20:30 UTC. Availability is stamped as
#: report_date + 3 days at 21:00 UTC unless the row carries its own available_time/published_at.
COT_RELEASE_LAG = timedelta(days=3, hours=21)
#: Currency / metal / index codes -> COT file stem. USD is the numeraire of every CFTC currency
#: future and contributes no leg of its own (the dollar index is a separate market, `USDX`).
COT_MARKETS: dict[str, str] = {
    "XAU": "gold", "XAG": "silver",
    "AUD": "aud", "CAD": "cad", "CHF": "chf", "EUR": "eur", "GBP": "gbp", "JPY": "jpy",
    "NZD": "nzd",
    "US500": "sp500", "SPX500": "sp500", "NAS100": "nasdaq100", "USTEC": "nasdaq100",
    "USDX": "dxy", "DXY": "dxy",
}


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    compute: Compute
    unit: str
    description: str = ""
    external: External | None = None
    #: Where the numbers come from and who produces them. Part of the id: the same formula on a
    #: different source is a different feature.
    source: str = DEFAULT_SOURCE
    provider: str = DEFAULT_PROVIDER
    #: When each value became knowable, in the producer's own terms. Part of the id: a feature
    #: whose availability rule changed is a different feature, because its backtest is.
    availability: str = DEFAULT_AVAILABILITY
    #: Whether the producer restates history, and what the store does about it.
    revision_status: str = DEFAULT_REVISION
    #: The currency a MONEY-VALUED feature is denominated in. None means the block is a pure
    #: number -- a ratio, a z-score, a count, a broker point -- and converting it would be an
    #: error; the field exists so a future money-valued feature must declare rather than imply.
    currency: str | None = None


REGISTRY: dict[str, FeatureSpec] = {}


def register(name: str, unit: str, description: str = "",
             external: External | None = None, *, source: str = DEFAULT_SOURCE,
             provider: str = DEFAULT_PROVIDER, availability: str = DEFAULT_AVAILABILITY,
             revision_status: str = DEFAULT_REVISION,
             currency: str | None = None) -> Callable[[Compute], Compute]:
    def deco(fn: Compute) -> Compute:
        REGISTRY[name] = FeatureSpec(name, fn, unit, description, external, source, provider,
                                     availability, revision_status, currency)
        return fn
    return deco


# --------------------------------------------------------------------------- the vocabulary
def _close(df: pd.DataFrame) -> np.ndarray:
    out: np.ndarray = df["close"].to_numpy(dtype=float)
    return out


@register("log_return", "log_return", "log(close_t / close_{t-h})")
def _f_ret(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    h = int(p.get("h", 1))
    c = _close(df)
    out = np.full(c.size, np.nan)
    with np.errstate(all="ignore"):
        out[h:] = np.log(c[h:] / c[:-h])
    return out


@register("realised_vol", "log_return", "rolling std of 1-bar log returns over w bars")
def _f_vol(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    w = int(p.get("w", 24))
    r = pd.Series(_f_ret(df, {"h": 1}))
    out: np.ndarray = r.rolling(w, min_periods=w).std().to_numpy(dtype=float)
    return out


@register("range_frac", "fraction", "(high-low)/close")
def _f_range(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    with np.errstate(all="ignore"):
        out: np.ndarray = ((df["high"] - df["low"]) / df["close"]).to_numpy(dtype=float)
    return out


@register("atr", "price", "average true range over n bars")
def _f_atr(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    n = int(p.get("n", 20))
    h, lo, pc = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([(h - lo), (h - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)
    out: np.ndarray = tr.rolling(n, min_periods=n).mean().to_numpy(dtype=float)
    return out


@register("zscore", "sigma", "z-score of a base feature over w bars")
def _f_z(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    base = str(p.get("of", "log_return"))
    w = int(p.get("w", 240))
    v = pd.Series(REGISTRY[base].compute(df, dict(p.get("of_params") or {})))
    r = v.rolling(w, min_periods=w)
    out: np.ndarray = ((v - r.mean()) / r.std()).to_numpy(dtype=float)
    return out


@register("ts_rank", "fraction", "trailing percentile of a base feature over w bars")
def _f_rank(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    from numpy.lib.stride_tricks import sliding_window_view
    base = str(p.get("of", "range_frac"))
    w = int(p.get("w", 240))
    v = REGISTRY[base].compute(df, dict(p.get("of_params") or {}))
    out = np.full(v.size, np.nan)
    if v.size > w:
        win = sliding_window_view(v, w + 1)
        with np.errstate(invalid="ignore"):
            out[w:] = (win[:, :-1] <= win[:, -1:]).mean(axis=1)
    return out


@register("hour", "hours", "bar hour on the bars' own clock")
def _f_hour(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    out: np.ndarray = idx.hour.to_numpy(dtype=float)
    return out


@register("column", "count", "a raw bar column (spread, tick_volume) as float")
def _f_col(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    col = str(p.get("col", "spread"))
    if col not in df.columns:
        return np.full(len(df), np.nan)
    out: np.ndarray = df[col].to_numpy(dtype=float)
    return out


@register("expr", "sigma", "an alpha-grammar expression, z-scored over norm bars")
def _f_expr(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    from libs.research.alpha_grammar import evaluate, terminal_frames
    frames = terminal_frames(df, raw=df)
    v = evaluate(p.get("expr"), frames)
    w = int(p.get("norm", 240))
    r = v.rolling(w, min_periods=w)
    out: np.ndarray = ((v - r.mean()) / r.std()).to_numpy(dtype=float)
    return out


# --------------------------------------------------------------------------- participant flow
def _degrade(name: str, n: int, why: str) -> np.ndarray:
    """All-NaN with the reason on record. The block is still a block: same length, same id rule."""
    LAST_REASON[name] = why
    LAST_DETAIL.pop(name, None)
    return np.full(n, np.nan)


def _ok(name: str, detail: str, **provenance: Any) -> None:
    LAST_REASON.pop(name, None)
    LAST_DETAIL[name] = detail
    if provenance:
        LAST_PROVENANCE[name] = dict(provenance)
    else:
        LAST_PROVENANCE.pop(name, None)


def _raw_hash(paths: list[Path]) -> str:
    """sha256 over the bytes of every input file, in path order. A file over
    RAW_HASH_MAX_BYTES contributes its size and mtime instead, and says so in the digest input,
    so the hash still moves when the file does."""
    h = hashlib.sha256()
    for pth in paths:
        try:
            st = pth.stat()
        except OSError:
            h.update(f"{pth.name}:absent".encode())
            continue
        if st.st_size > RAW_HASH_MAX_BYTES:
            h.update(f"{pth.name}:size-only:{st.st_size}:{st.st_mtime_ns}".encode())
            continue
        h.update(pth.name.encode())
        try:
            h.update(pth.read_bytes())
        except OSError:
            h.update(b":unreadable")
    return h.hexdigest()[:24]


def _mtime_iso(pth: Path) -> str | None:
    try:
        return datetime.fromtimestamp(pth.stat().st_mtime, tz=UTC).isoformat()
    except OSError:
        return None


def _utc_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    """The bars' clock as UTC. A naive index is taken as UTC, matching the parquet convention."""
    return pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))


def _utc_ns(idx: pd.DatetimeIndex) -> np.ndarray:
    """Epoch nanoseconds. The parquets carry a MILLISECOND index and `asi8` reports the index's
    own unit, so the resolution is forced before any comparison with report times."""
    out: np.ndarray = idx.as_unit("ns").asi8
    return out


@register("tick_imbalance", "fraction",
          "rolling sum of sign(close-open) x tick_volume over w bars, over the rolling sum of "
          "|.|: net buying pressure in [-1, 1] as the broker's own tick flow shows it")
def _f_tick_imbalance(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    w = int(p.get("w", 24))
    if "tick_volume" not in df.columns:
        return _degrade("tick_imbalance", len(df), "tick_volume column absent from the bars")
    with np.errstate(all="ignore"):
        signed = pd.Series(np.sign(df["close"].to_numpy(dtype=float)
                                   - df["open"].to_numpy(dtype=float))
                           * df["tick_volume"].to_numpy(dtype=float))
        num = signed.rolling(w, min_periods=w).sum()
        den = signed.abs().rolling(w, min_periods=w).sum()
        out: np.ndarray = (num / den.where(den > 0)).to_numpy(dtype=float)
    _ok("tick_imbalance", f"w={w}")
    return out


@register("session_participation", "log_ratio",
          "log(tick_volume / trailing median of tick_volume at the SAME hour-of-day over its "
          "previous n occurrences): is this hour busier than this hour usually is")
def _f_session_participation(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    n = int(p.get("n", 20))
    if "tick_volume" not in df.columns:
        return _degrade("session_participation", len(df),
                        "tick_volume column absent from the bars")
    hour = _utc_index(df).hour.to_numpy(dtype=float)
    tv = pd.Series(df["tick_volume"].to_numpy(dtype=float))
    # Same-hour history only, and strictly BEFORE the bar: the reference for 14:00 is the median
    # of the previous n 14:00 bars, so the bar never compares itself with itself.
    ref = tv.groupby(hour).transform(
        lambda s: s.shift(1).rolling(n, min_periods=n).median())
    with np.errstate(all="ignore"):
        ratio = np.log(tv.to_numpy(dtype=float) / ref.to_numpy(dtype=float))
    out: np.ndarray = np.where(np.isfinite(ratio), ratio, np.nan)
    _ok("session_participation", f"n={n}")
    return out


_UNIVERSE_CACHE: dict[str, Any] = {"key": None, "doc": {}}


def _universe() -> dict[str, Any]:
    """`universe.json` as a dict, re-read only when the file changes. Empty when unreadable."""
    try:
        st = UNIVERSE_JSON.stat()
        key = (st.st_size, st.st_mtime_ns)
    except OSError:
        return {}
    if _UNIVERSE_CACHE["key"] != key:
        try:
            doc = json.loads(UNIVERSE_JSON.read_text("utf-8"))
        except (OSError, ValueError):
            doc = {}
        _UNIVERSE_CACHE["key"], _UNIVERSE_CACHE["doc"] = key, (doc if isinstance(doc, dict)
                                                               else {})
    out: dict[str, Any] = _UNIVERSE_CACHE["doc"]
    return out


def _file_identity(paths: list[Path]) -> str:
    """Size and mtime of each input file: cheap, and enough to invalidate a cached block."""
    parts = []
    for pth in paths:
        try:
            st = pth.stat()
            parts.append(f"{pth.name}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f"{pth.name}:absent")
    return "|".join(parts)


def _universe_external(p: dict[str, Any]) -> str:
    return _file_identity([UNIVERSE_JSON])


def _swap(df: pd.DataFrame, p: dict[str, Any], field: str, name: str) -> np.ndarray:
    """A static broker level per symbol, constant across bars. Unknown symbol -> NaN + reason."""
    sym = str(p.get("symbol") or "")
    entry = _universe().get(sym)
    if not sym or not isinstance(entry, dict):
        return _degrade(name, len(df), f"symbol {sym!r} not in {UNIVERSE_JSON.name}")
    try:
        long_, short = float(entry["swap_long"]), float(entry["swap_short"])
    except (KeyError, TypeError, ValueError):
        return _degrade(name, len(df), f"{sym}: swap_long/swap_short missing from the entry")
    val = {"swap_long": long_, "swap_short": short, "swap_diff": long_ - short}[field]
    _ok(name, f"{sym}: {field}={val}", published_time=_mtime_iso(UNIVERSE_JSON),
        revision_time=_mtime_iso(UNIVERSE_JSON), source_version=_file_identity([UNIVERSE_JSON]),
        raw_hash=_raw_hash([UNIVERSE_JSON]))
    return np.full(len(df), val)


#: The broker's swap is a static level re-quoted without history: the block is knowable from the
#: moment the universe file carried it, and a re-quote re-keys the block through its external
#: identity rather than restating the old one.
_SWAP_AVAILABILITY = ("static broker level as quoted in universe.json when the block was "
                      "computed, applied to every bar; a re-quote re-keys the block by file "
                      "identity")
_SWAP_REVISION = "re-quoted by the broker without history; re-keyed by file identity"


@register("swap_diff", "broker_swap", "swap_long - swap_short for the symbol (universe.json): "
          "the financing asymmetry the desk pays, a static level per instrument",
          external=_universe_external, source="universe.json", availability=_SWAP_AVAILABILITY,
          revision_status=_SWAP_REVISION)
def _f_swap_diff(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    return _swap(df, p, "swap_diff", "swap_diff")


@register("swap_long", "broker_swap", "the broker's overnight swap on a long (universe.json)",
          external=_universe_external, source="universe.json", availability=_SWAP_AVAILABILITY,
          revision_status=_SWAP_REVISION)
def _f_swap_long(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    return _swap(df, p, "swap_long", "swap_long")


@register("swap_short", "broker_swap", "the broker's overnight swap on a short (universe.json)",
          external=_universe_external, source="universe.json", availability=_SWAP_AVAILABILITY,
          revision_status=_SWAP_REVISION)
def _f_swap_short(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    return _swap(df, p, "swap_short", "swap_short")


def cot_legs(symbol: str) -> list[tuple[str, float]]:
    """(COT file stem, sign) for each leg of an MT5 symbol. A pair is base minus quote; USD is
    the numeraire and carries no leg; an index or the dollar index is one leg."""
    sym = str(symbol or "").upper()
    if sym in COT_MARKETS:
        return [(COT_MARKETS[sym], 1.0)]
    legs: list[tuple[str, float]] = []
    if len(sym) == 6:
        for code, sign in ((sym[:3], 1.0), (sym[3:], -1.0)):
            if code in COT_MARKETS:
                legs.append((COT_MARKETS[code], sign))
    return legs


def _cot_file(stem: str) -> tuple[Path, str, str] | None:
    for d, long_col, short_col in COT_SOURCES:
        pth = d / f"{stem}.parquet"
        if pth.exists():
            return pth, long_col, short_col
    return None


def _cot_external(p: dict[str, Any]) -> str:
    found = [f[0] for f in (_cot_file(stem) for stem, _ in cot_legs(str(p.get("symbol") or "")))
             if f is not None]
    return _file_identity(found) if found else "no-cot-file"


def _cot_market_rows(raw: pd.DataFrame) -> pd.DataFrame:
    """One market per file. The TFF files bundle cross-rate contracts and the same contract
    under two names across a rename; cross rates are dropped, a Consolidated aggregate is
    preferred when the file carries one, and a renamed contract's rows are unioned."""
    col = "market" if "market" in raw.columns else "contract_market_name"
    if col not in raw.columns:
        return raw
    names = raw[col].astype(str)
    keep = ~names.str.contains("XRATE", case=False, regex=False)
    keep &= ~names.str.contains("DIVIDEND|TOTAL RETURN|ADJUSTED", case=False, regex=True)
    sub = raw[keep]
    cons = sub[sub[col].astype(str).str.contains("Consolidated", case=False, regex=False)]
    return cons if len(cons) else sub


def _cot_available_ns(rep: pd.DataFrame) -> np.ndarray:
    """When each report became knowable, as UTC ns. The row's own stamp wins when present."""
    dates = pd.to_datetime(rep["report_date"], utc=True, errors="coerce")
    avail = dates + COT_RELEASE_LAG
    for col in ("available_time", "published_at"):
        if col in rep.columns:
            own = pd.to_datetime(rep[col], utc=True, errors="coerce")
            avail = own.where(own.notna(), avail)
            break
    out: np.ndarray = _utc_ns(pd.DatetimeIndex(avail))
    return out


def _cot_leg_z(pth: Path, long_col: str, short_col: str, w: int) -> pd.Series | None:
    """z-score of the net speculative position over the last w reports, indexed by the UTC ns
    at which each report became available. None when the file cannot be read as a COT table."""
    try:
        raw = pd.read_parquet(pth)
    except Exception:
        return None
    if "report_date" not in raw.columns or long_col not in raw.columns \
            or short_col not in raw.columns:
        return None
    rep = _cot_market_rows(raw).copy()
    rep["_avail"] = _cot_available_ns(rep)
    rep = rep.dropna(subset=["_avail"]).sort_values("_avail")
    rep = rep[~rep["_avail"].duplicated(keep="last")]
    if rep.empty:
        return None
    net = pd.Series(rep[long_col].to_numpy(dtype=float) - rep[short_col].to_numpy(dtype=float),
                    index=rep["_avail"].to_numpy(dtype="int64"))
    r = net.rolling(w, min_periods=w)
    with np.errstate(all="ignore"):
        z = (net - r.mean()) / r.std()
    return z.replace([np.inf, -np.inf], np.nan)


def _asof(bars_ns: np.ndarray, series: pd.Series) -> np.ndarray:
    """Forward-fill a report series onto bar times using only reports available AT OR BEFORE
    each bar: the last available report at every bar, NaN before the first."""
    avail = series.index.to_numpy(dtype="int64")
    vals = series.to_numpy(dtype=float)
    pos = np.searchsorted(avail, bars_ns, side="right") - 1
    out = np.full(bars_ns.size, np.nan)
    hit = pos >= 0
    out[hit] = vals[pos[hit]]
    return out


#: The CFTC's own clock, stated as the feature's availability rule so the sidecar carries it and
#: the id changes if the rule ever does. A report dated Tuesday is public Friday evening; reading
#: it from its DATE would hand the desk three days of hindsight every week.
_COT_AVAILABILITY = ("a CFTC report is knowable only from its release -- the row's own "
                     f"available_time/published_at when it carries one, else report_date + "
                     f"{COT_RELEASE_LAG}; a bar sees the last report available at or before it")
_COT_REVISION = ("the CFTC restates prior weeks; the vintage on disk is what the block was built "
                 "from and a refreshed file re-keys the block through its external identity "
                 "rather than restating the old block in place")


@register("cot_z", "sigma",
          "z-score over w weekly reports of the net speculative position in the symbol's CFTC "
          "market(s), forward-filled onto the bars point-in-time (a report is knowable only "
          "from its release, Friday evening after its Tuesday date); pairs are base minus quote",
          external=_cot_external, source="cftc_cot", provider="cftc",
          availability=_COT_AVAILABILITY, revision_status=_COT_REVISION)
def _f_cot_z(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    sym = str(p.get("symbol") or "")
    w = int(p.get("w", 52))
    legs = cot_legs(sym)
    if not legs:
        return _degrade("cot_z", len(df), f"{sym!r}: no CFTC market mapped for this symbol")
    bars_ns = _utc_ns(_utc_index(df))
    total = np.zeros(len(df))
    used: list[str] = []
    paths: list[Path] = []
    newest_ns = 0
    for stem, sign in legs:
        found = _cot_file(stem)
        if found is None:
            return _degrade("cot_z", len(df), f"{sym}: no COT file for market {stem!r} under "
                            f"{', '.join(d.name for d, _, _ in COT_SOURCES)}")
        pth, long_col, short_col = found
        z = _cot_leg_z(pth, long_col, short_col, w)
        if z is None:
            return _degrade("cot_z", len(df), f"{sym}: {pth.name} in {pth.parent.name} is not a "
                            f"COT table with report_date/{long_col}/{short_col}")
        total = total + sign * _asof(bars_ns, z)
        used.append(f"{'+' if sign > 0 else '-'}{pth.parent.name}/{pth.name}")
        paths.append(pth)
        if z.index.size:
            newest_ns = max(newest_ns, int(z.index.to_numpy(dtype="int64").max()))
    if not np.isfinite(total).any():
        return _degrade("cot_z", len(df), f"{sym}: no report available before any bar "
                        f"(legs {', '.join(used)}, w={w})")
    # PUBLISHED TIME IS THE NEWEST REPORT'S RELEASE, not the file's mtime: the producer's clock,
    # which is what a joiner must compare a decision time against.
    published = (datetime.fromtimestamp(newest_ns / 1e9, tz=UTC).isoformat()
                 if newest_ns else None)
    _ok("cot_z", f"{sym}: legs {', '.join(used)}, w={w}, release lag {COT_RELEASE_LAG}",
        published_time=published, revision_time=max((_mtime_iso(p_) or "" for p_ in paths),
                                                    default="") or None,
        source_version=_file_identity(paths), raw_hash=_raw_hash(paths))
    out: np.ndarray = total
    return out


# --------------------------------------------------------------------------- identity
def data_hash(df: pd.DataFrame) -> str:
    """Identity of the bars: index bounds, length and a hash of the close series."""
    idx = df.index
    c = df["close"].to_numpy(dtype=float)
    h = hashlib.sha256()
    h.update(f"{idx[0]}|{idx[-1]}|{len(df)}".encode())
    h.update(np.ascontiguousarray(np.nan_to_num(c)).tobytes())
    return h.hexdigest()[:16]


def feature_id(name: str, params: dict[str, Any], dhash: str,
               code_version: str = CODE_VERSION, external: str | None = None, *,
               source: str = DEFAULT_SOURCE,
               availability: str = DEFAULT_AVAILABILITY) -> str:
    """The id: hash(name, code_version, params, data_hash, source, availability_rule[, external]).

    SOURCE AND AVAILABILITY ARE IDENTITY, not metadata. The same formula on a different feed is a
    different feature, and the same numbers under a different rule about when they were knowable
    are a different BACKTEST -- so both belong in the hash rather than in a note beside it. A
    changed rule therefore misses the cache and recomputes instead of serving yesterday's block
    under a claim it no longer supports. `external` (inputs outside the bars) is folded in ONLY
    when the feature declares one.
    """
    body: dict[str, Any] = {"n": name, "p": params, "d": dhash, "c": code_version,
                            "s": source, "a": availability}
    if external is not None:
        body["x"] = external
    payload = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def legacy_feature_id(name: str, params: dict[str, Any], dhash: str,
                      code_version: str = LEGACY_CODE_VERSION,
                      external: str | None = None) -> str:
    """The PRE-WAREHOUSE formula, byte for byte, so a block written before source and
    availability were folded in is still findable. Kept, not deleted: an id nobody can compute
    any more is a warehouse the desk has to rebuild for no reason."""
    body: dict[str, Any] = {"n": name, "p": params, "d": dhash, "c": code_version}
    if external is not None:
        body["x"] = external
    payload = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


_CODE_HASH: dict[str, str] = {}


def feature_code_hash(spec: FeatureSpec) -> str:
    """sha256 of the compute function's own source. The code version says WHICH release; this
    says which FUNCTION, so a formula edited without bumping the version is still visible on the
    warehouse record. A function whose source cannot be read (a C extension, an exec'd lambda)
    hashes its qualified name instead, and says so."""
    key = spec.name
    got = _CODE_HASH.get(key)
    if got is None:
        try:
            body = inspect.getsource(spec.compute)
        except (OSError, TypeError):
            body = f"source-unavailable:{getattr(spec.compute, '__qualname__', spec.name)}"
        got = hashlib.sha256(body.encode()).hexdigest()[:16]
        _CODE_HASH[key] = got
    return got


def _iso(ts: Any) -> str | None:
    """A bar stamp or an ISO string as an aware-UTC ISO string; None when it is neither."""
    if ts is None:
        return None
    try:
        t = pd.Timestamp(ts)
    except (TypeError, ValueError):
        return None
    if t is pd.NaT or pd.isna(t):
        return None
    t = t.tz_localize(UTC) if t.tzinfo is None else t.tz_convert(UTC)
    return str(t.isoformat())


def _seconds_between(later: str | None, earlier: str | None) -> float | None:
    """`later - earlier` in seconds, or None when either end is missing/unparseable. Never
    negative: a clock that runs backwards is reported as zero lag, not as negative latency."""
    if not later or not earlier:
        return None
    try:
        a, b = datetime.fromisoformat(later), datetime.fromisoformat(earlier)
    except (TypeError, ValueError):
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=UTC)
    if b.tzinfo is None:
        b = b.replace(tzinfo=UTC)
    return round(max(0.0, (a - b).total_seconds()), 3)


# --------------------------------------------------------------------------- the store
class FeatureStore:
    def __init__(self, root: Path = STORE) -> None:
        self.root = root
        self.hits = 0
        self.misses = 0
        #: Blocks served from the pre-warehouse id and re-keyed under the new one. Counted
        #: separately from hits and misses: nothing was recomputed, but nothing was found under
        #: the id asked for either, and the migration is only finished when this reads zero.
        self.adopted = 0

    def _paths(self, fid: str) -> tuple[Path, Path]:
        return self.root / f"{fid}.npy", self.root / f"{fid}.json"

    def _record(self, *, fid: str, spec: FeatureSpec, params: dict[str, Any], dhash: str,
                arr: np.ndarray, external: str | None, df: pd.DataFrame, compute_s: float | None,
                legacy_id: str, adopted: bool) -> dict[str, Any]:
        """THE WAREHOUSE RECORD: every field the principal's order names, computed rather than
        asserted. The five timestamps are the producer's clock (published), the bars' clock
        (event), the join's clock (available) and this store's (ingested), with the restatement
        time when the producer has one."""
        prov = LAST_PROVENANCE.get(spec.name, {}) if not adopted else {}
        idx = _utc_index(df)
        event = _iso(idx[-1]) if len(idx) else None
        published = _iso(prov.get("published_time")) or event
        # KNOWABLE = THE LATER OF THE TWO CLOCKS. A block whose newest input was published after
        # its newest bar is knowable from the publication, not from the bar.
        available = max([t for t in (published, event) if t], default=None)
        ingested = datetime.now(tz=UTC).isoformat()
        return {
            "id": fid, "legacy_id": legacy_id, "name": spec.name, "params": params,
            "code_version": CODE_VERSION, "data_hash": dhash, "n": int(arr.shape[0]),
            # -------------------------------------------------- the five timestamps
            "event_time": event, "published_time": published, "available_time": available,
            "ingested_time": ingested, "revision_time": _iso(prov.get("revision_time")),
            # -------------------------------------------------- who produced it, from what
            "source": spec.source, "provider": spec.provider,
            "source_version": str(prov.get("source_version") or f"bars:{dhash}"),
            "raw_hash": str(prov.get("raw_hash") or dhash),
            "feature_code_hash": feature_code_hash(spec),
            # -------------------------------------------------- what the numbers mean
            "units": spec.unit, "currency": spec.currency, "timezone": "UTC",
            # -------------------------------------------------- quality flags
            "latency_s": _seconds_between(available, event),
            "freshness_s": _seconds_between(ingested, available),
            "coverage_frac": round(float(np.isfinite(arr).mean()), 4),
            "revision_status": spec.revision_status,
            # -------------------------------------------------- the rules and the lifecycle
            "availability_rule": spec.availability,
            "event_time_rule": "feature at bar t uses bars <= t only",
            "status": STATUS_NEW, "roi": None,
            "compute_s": compute_s,
            "external": external, "degraded": LAST_REASON.get(spec.name),
            "adopted_from_legacy": adopted,
            # `computed_at` and `finite_frac` are the pre-warehouse names for `ingested_time`
            # and `coverage_frac`, kept so a reader written against the old sidecar still works.
            "computed_at": ingested,
            "finite_frac": round(float(np.isfinite(arr).mean()), 4),
        }

    def get(self, name: str, df: pd.DataFrame, params: dict[str, Any] | None = None,
            *, check_causal: bool = False) -> np.ndarray:
        spec = REGISTRY[name]
        params = dict(params or {})
        external = spec.external(params) if spec.external is not None else None
        dhash = data_hash(df)
        fid = feature_id(name, params, dhash, external=external, source=spec.source,
                         availability=spec.availability)
        legacy = legacy_feature_id(name, params, dhash, external=external)
        arr_p, meta_p = self._paths(fid)
        if arr_p.exists():
            self.hits += 1
            out: np.ndarray = np.load(arr_p)
            return out
        # ADOPTION BEFORE RECOMPUTE. The old id addressed the same numbers; re-keying them costs
        # one file copy and saves the whole warehouse being rebuilt for a formula change that
        # did not change any value.
        legacy_arr_p, _ = self._paths(legacy)
        if legacy != fid and legacy_arr_p.exists():
            adopted_arr: np.ndarray = np.load(legacy_arr_p)
            if adopted_arr.shape[0] == len(df):
                self.adopted += 1
                self.root.mkdir(parents=True, exist_ok=True)
                np.save(arr_p, adopted_arr)
                meta_p.write_text(json.dumps(
                    self._record(fid=fid, spec=spec, params=params, dhash=dhash, arr=adopted_arr,
                                 external=external, df=df, compute_s=None, legacy_id=legacy,
                                 adopted=True), indent=1, default=str), "utf-8")
                return adopted_arr
        self.misses += 1
        started = time.monotonic()
        arr = np.asarray(spec.compute(df, params), dtype=float)
        compute_s = round(time.monotonic() - started, 6)
        if arr.shape[0] != len(df):
            raise ValueError(f"{name}: feature length {arr.shape[0]} != bars {len(df)}")
        if check_causal:
            cut = max(10, len(df) * 2 // 3)
            trunc = np.asarray(spec.compute(df.iloc[:cut], params), dtype=float)
            both = np.isfinite(arr[:cut]) & np.isfinite(trunc)
            if (np.isfinite(arr[:cut]) != np.isfinite(trunc)).any() or \
                    not np.allclose(arr[:cut][both], trunc[both], rtol=1e-9, atol=1e-12):
                raise ValueError(f"{name}: NOT CAUSAL -- values before the cut changed when "
                                 "later bars were removed; refused")
        self.root.mkdir(parents=True, exist_ok=True)
        np.save(arr_p, arr)
        meta_p.write_text(json.dumps(
            self._record(fid=fid, spec=spec, params=params, dhash=dhash, arr=arr,
                         external=external, df=df, compute_s=compute_s, legacy_id=legacy,
                         adopted=False), indent=1, default=str), "utf-8")
        return arr

    def matrix(self, df: pd.DataFrame, specs: list[tuple[str, dict[str, Any]]]) -> np.ndarray:
        """Columns = features, aligned to the bars; the shared design matrix for co-evolution."""
        cols = [self.get(n, df, p) for n, p in specs]
        return np.column_stack(cols) if cols else np.empty((len(df), 0))

    def sidecars(self) -> list[dict[str, Any]]:
        """Every warehouse record on disk, with `_path` beside it so a writer can find it again.
        The feature ledger reads this; unreadable sidecars are skipped, never guessed at."""
        out: list[dict[str, Any]] = []
        for p in sorted(self.root.glob("*.json")):
            try:
                doc = json.loads(p.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(doc, dict):
                doc["_path"] = str(p)
                out.append(doc)
        return out

    def set_status(self, name: str, status: str, roi: dict[str, Any] | None = None) -> int:
        """Write a lifecycle verdict and its ROI line onto every block of one feature.

        THE LEDGER JUDGES, THE STORE RECORDS. `feature_roi` computes; this is the only writer of
        `status` and `roi`, so a status on disk always came from a measurement and never from an
        organ's opinion of its own inputs. Returns how many sidecars were updated.
        """
        n = 0
        for doc in self.sidecars():
            if str(doc.get("name")) != name:
                continue
            path = Path(str(doc.pop("_path")))
            doc["status"] = status
            doc["roi"] = roi
            doc["status_at"] = datetime.now(tz=UTC).isoformat()
            try:
                path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
            except OSError:
                continue
            n += 1
        return n

    def census(self) -> dict[str, Any]:
        metas = self.sidecars()
        by_name: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for m in metas:
            by_name[str(m.get("name"))] = by_name.get(str(m.get("name")), 0) + 1
            st = str(m.get("status") or "UNRECORDED")
            by_status[st] = by_status.get(st, 0) + 1
        return {"blocks": len(metas), "by_name": by_name, "by_status": by_status,
                "hits": self.hits, "misses": self.misses, "adopted": self.adopted,
                "adopted_from_legacy": sum(1 for m in metas if m.get("adopted_from_legacy")),
                "warehouse_complete": sum(1 for m in metas if m.get("available_time"))}
