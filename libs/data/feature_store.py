"""Immutable, hashed feature blocks so a million experiments share one computation.

    FeatureID = hash(name, code_version, params, data_hash)

The High-Flyer lesson stripped to what one VPS can use: every research worker reuses common
feature matrices instead of recomputing them, and a feature's identity is what produced it --
the code version, the parameters and the bars it was computed from -- never its filename. A
feature block with the same id IS the same numbers, so a cache hit is exact, and a changed bar
history or a changed formula produces a different id rather than a silently different block
under the same name.

WHAT IS STORED. Numpy arrays keyed by id under `data/features/`, with a JSON sidecar carrying the
inputs, the unit, the availability rule (a feature at bar t uses bars <= t; the store refuses a
compute function that is not causal, tested by recomputing on a truncated frame) and the ROI
line the feature ledger fills in later.

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
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "desks" / "mt5" / "data" / "features"
CODE_VERSION = "2026-09-04.1"

Compute = Callable[[pd.DataFrame, dict[str, Any]], np.ndarray]
#: Identity of a feature's inputs OUTSIDE the bars (files on disk), as a function of params.
External = Callable[[dict[str, Any]], str]

#: Why the last compute of a participant-flow feature degraded, by feature name. A feature that
#: cannot be built returns all-NaN and writes its reason here; a feature that succeeds clears
#: its entry and writes what it used to `LAST_DETAIL`.
LAST_REASON: dict[str, str] = {}
LAST_DETAIL: dict[str, str] = {}

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


REGISTRY: dict[str, FeatureSpec] = {}


def register(name: str, unit: str, description: str = "",
             external: External | None = None) -> Callable[[Compute], Compute]:
    def deco(fn: Compute) -> Compute:
        REGISTRY[name] = FeatureSpec(name, fn, unit, description, external)
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


def _ok(name: str, detail: str) -> None:
    LAST_REASON.pop(name, None)
    LAST_DETAIL[name] = detail


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
    _ok(name, f"{sym}: {field}={val}")
    return np.full(len(df), val)


@register("swap_diff", "broker_swap", "swap_long - swap_short for the symbol (universe.json): "
          "the financing asymmetry the desk pays, a static level per instrument",
          external=_universe_external)
def _f_swap_diff(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    return _swap(df, p, "swap_diff", "swap_diff")


@register("swap_long", "broker_swap", "the broker's overnight swap on a long (universe.json)",
          external=_universe_external)
def _f_swap_long(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    return _swap(df, p, "swap_long", "swap_long")


@register("swap_short", "broker_swap", "the broker's overnight swap on a short (universe.json)",
          external=_universe_external)
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


@register("cot_z", "sigma",
          "z-score over w weekly reports of the net speculative position in the symbol's CFTC "
          "market(s), forward-filled onto the bars point-in-time (a report is knowable only "
          "from its release, Friday evening after its Tuesday date); pairs are base minus quote",
          external=_cot_external)
def _f_cot_z(df: pd.DataFrame, p: dict[str, Any]) -> np.ndarray:
    sym = str(p.get("symbol") or "")
    w = int(p.get("w", 52))
    legs = cot_legs(sym)
    if not legs:
        return _degrade("cot_z", len(df), f"{sym!r}: no CFTC market mapped for this symbol")
    bars_ns = _utc_ns(_utc_index(df))
    total = np.zeros(len(df))
    used: list[str] = []
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
    if not np.isfinite(total).any():
        return _degrade("cot_z", len(df), f"{sym}: no report available before any bar "
                        f"(legs {', '.join(used)}, w={w})")
    _ok("cot_z", f"{sym}: legs {', '.join(used)}, w={w}, release lag {COT_RELEASE_LAG}")
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
               code_version: str = CODE_VERSION, external: str | None = None) -> str:
    """The id. `external` (inputs outside the bars) is folded in ONLY when the feature declares
    one, so every id that existed before the participant-flow layer is unchanged."""
    body: dict[str, Any] = {"n": name, "p": params, "d": dhash, "c": code_version}
    if external is not None:
        body["x"] = external
    payload = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


# --------------------------------------------------------------------------- the store
class FeatureStore:
    def __init__(self, root: Path = STORE) -> None:
        self.root = root
        self.hits = 0
        self.misses = 0

    def _paths(self, fid: str) -> tuple[Path, Path]:
        return self.root / f"{fid}.npy", self.root / f"{fid}.json"

    def get(self, name: str, df: pd.DataFrame, params: dict[str, Any] | None = None,
            *, check_causal: bool = False) -> np.ndarray:
        spec = REGISTRY[name]
        params = dict(params or {})
        external = spec.external(params) if spec.external is not None else None
        fid = feature_id(name, params, data_hash(df), external=external)
        arr_p, meta_p = self._paths(fid)
        if arr_p.exists():
            self.hits += 1
            out: np.ndarray = np.load(arr_p)
            return out
        self.misses += 1
        arr = np.asarray(spec.compute(df, params), dtype=float)
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
        meta_p.write_text(json.dumps({
            "id": fid, "name": name, "params": params, "unit": spec.unit,
            "code_version": CODE_VERSION, "data_hash": data_hash(df), "n": int(arr.shape[0]),
            "event_time_rule": "feature at bar t uses bars <= t only",
            "computed_at": datetime.now(tz=UTC).isoformat(),
            "finite_frac": round(float(np.isfinite(arr).mean()), 4),
            "external": external,
            "degraded": LAST_REASON.get(name),
        }, indent=1, default=str), "utf-8")
        return arr

    def matrix(self, df: pd.DataFrame, specs: list[tuple[str, dict[str, Any]]]) -> np.ndarray:
        """Columns = features, aligned to the bars; the shared design matrix for co-evolution."""
        cols = [self.get(n, df, p) for n, p in specs]
        return np.column_stack(cols) if cols else np.empty((len(df), 0))

    def census(self) -> dict[str, Any]:
        metas = []
        for p in self.root.glob("*.json"):
            try:
                metas.append(json.loads(p.read_text("utf-8")))
            except (OSError, ValueError):
                continue
        by_name: dict[str, int] = {}
        for m in metas:
            by_name[str(m.get("name"))] = by_name.get(str(m.get("name")), 0) + 1
        return {"blocks": len(metas), "by_name": by_name, "hits": self.hits,
                "misses": self.misses}
