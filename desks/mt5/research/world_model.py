"""THE GLOBAL PROBABILISTIC WORLD MODEL -- one model of the world, and what it cannot explain.

THE PRINCIPAL, 2026-09-17: *every datum enters -- PIT truth -> semantic/entity graph ->
representation forge -> World Model -> candidate generation -> cross-dataset interactions ->
gauntlet -> Forward Lab -> live attribution -- and feeds back source ROI, dataset ROI,
representation ROI, mechanism ROI and scientist ROI.* This organ is the fourth stage and the one
the whole chain was missing: a single predictive object over the hypothesis-discovery universe
that takes EVERY point-in-time series the desk holds, says what it expects, and -- the part that
matters more than the prediction -- publishes epsilon_t = y_t - yhat_t so the next organ can hunt
what the model repeatedly fails to explain.

WHAT IT PREDICTS. Forward log returns of every instrument in the hypothesis lane
(`universe_policy`: single-name equities stay in the event lane and are never hunted
statistically) at 1h, 4h, 1d and 5d, plus the desk's own regime vocabulary as a forecast rather
than a label. Nothing here allocates capital, sizes anything, or reaches the gateway. It is a
measurement organ, and the growth law is satisfied the honest way: a better conditional
distribution RAISES robust forward E[log W] by telling the allocator's inputs apart, and this
organ adds no veto, cap or shrink of its own (GROWTH_GOVERNANCE Rule 1).

THE ALIGNMENT IS THE WHOLE PRODUCT, AND IT IS STRICT. An input value is usable at decision time
t only if its own `available_time` (or `knowable_at`) is <= t, and the value used is the NEWEST
VINTAGE knowable at t -- never a later revision, however much better it is. The bar index on this
desk is BROKER time under a UTC tzinfo (+2 winter / +3 summer, `libs/research/bar_clock`), so
every external stamp is additionally padded by `CLOCK_PAD_H` hours before it is allowed to be
known: a join that is three hours optimistic inside a one-day publication lag is invisible in
every leak check the desk owns, because the RETURN series stays spotless while it happens.

THE MODEL IS TWO MODELS, ON PURPOSE. A ridge with purged expanding-window CV carries the linear
structure and is what the contributions are measured on -- a shrunk linear coefficient is a
number a human can argue with. A nonlinear residual learner (sklearn's gradient boosting where
importable, k-nearest-neighbours over the same features otherwise) then learns what the ridge
left, which is the only fair way to ask whether the remaining epsilon is STRUCTURE or NOISE. The
predictive distribution is the empirical quantiles of the out-of-sample epsilon, not a Gaussian
assumed into existence.

WHAT IT PUBLISHES. `reports/WORLD_MODEL.json` (per target: n, horizon, out-of-sample R2, per
dataset contribution, explained variance by dataset / region / information type, the regime
forecast, and the inputs that were UNMEASURED BY NAME), a residual store under
`data/world_model/residuals_<horizon>.parquet` that `residual_hunt` consumes, and dataset
contribution rows in the canonical registry (`source_yield` and `kpis`), which is how dataset ROI
stops being a word and becomes a number.

WHAT WAS AT THIS PATH BEFORE, AND WHERE IT WENT. Commit 5e208e9ad53 landed F3 here -- a
probabilistic model of NINE MARKET AXES (volatility, liquidity, trend/reversion, jumps, event
state, macro state, transmission, participant pressure, structural breaks), each estimated by two
methods that fail differently, keeping the DISAGREEMENT per axis instead of collapsing it into
one confidence scalar. It was EXISTS-DARK: no leg, no layer, no test, and U3 did not cite it. It
is now `desks/mt5/research/market_posteriors.py`, verbatim, writing `reports/MARKET_POSTERIORS.
json` instead of this organ's artifact -- two organs cannot own one module name or one artifact,
and a dark organ pointed at a scheduled organ's artifact means whichever ran last wins, silently.
Nothing of it was deleted; it is still dark, and wiring it is a judgement about the desk's hour
rather than a side effect of this build. The two models answer different questions and the axes
it estimates are exactly the kind of input this one should eventually read.

UNMEASURED IS A VERDICT (L1.28a). A symbol with too few bars, an axis whose stamps do not parse,
a horizon with no admissible rows -- each is named in the report with what would measure it.
None of them is a zero, and none of them is silently dropped.

    python desks/mt5/research/world_model.py [--once] [--budget-s 1200] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import representations as R  # noqa: E402

UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE_JSON = UNIVERSE_DIR / "universe.json"
AXES = DESK / "data" / "axes"
FRED = ROOT / "data" / "fred_macro.json"
REPRESENTATIONS = DESK / "data" / "representations"
MOAT_SERIES = DESK / "reports" / "MOAT_SERIES.json"
STORE = DESK / "data" / "world_model"
CURSOR = STORE / "cursor.json"
OUT = DESK / "reports" / "WORLD_MODEL.json"

#: horizon name -> H1 bars ahead. The desk's four decision clocks.
HORIZONS: dict[str, int] = {"1h": 1, "4h": 4, "1d": 24, "5d": 120}
#: Broker-clock padding on every external stamp, in hours. See the module docstring: the bar
#: index is +2/+3 against UTC and the direction that matters is the one that would let a print
#: reach a bar it could not have reached.
CLOCK_PAD_H = 4
#: The desk's session vocabulary, as `mt5desk.family_call.SESSIONS` declares it.
SESSION_WINDOWS: dict[str, tuple[int, int]] = {"asia": (0, 8), "london": (8, 16), "ny": (14, 22)}
VOL_WINDOW = 24
#: Prior readings before a tercile cut is honest -- `regime_router.PRE_MIN`, same reason.
VOL_PRE_MIN = 200
#: Bars between refits of the causal vol tercile. See `vol_regime`.
VOL_RECUT = 240
#: Residual rows kept per (symbol, horizon). The hunt clusters by regime x session x calendar
#: class x hour, so it needs depth per cell, not every bar the desk owns: the newest rows are the
#: ones a persistence test can still act on, and the store is bounded by measured memory anyway.
MAX_RESIDUAL_ROWS = 3_000
MIN_ROWS = 400
MIN_TRAIN = 200
FOLDS = 4
RIDGE_GRID = (1.0, 10.0, 100.0, 1000.0)
MAX_FEATURES = 48
MAX_BARS = 20_000
MIN_NONLINEAR = 600
#: A feature is CLIPPED at this many train-fold sd, and a column flatter than
#: DEAD_COLUMN_SD inside the training fold is zeroed. See `_standardise`.
STANDARD_CLIP = 8.0
DEAD_COLUMN_SD = 1e-9
KNN_K = 24
BYTES_PER_ROW = 512
FREE_MEMORY_SHARE = 0.10
MAX_ROWS_FLOOR = 200_000
#: DEPTH BOUNDS ON THE PIT INPUTS, and they are bounds rather than judgements. The BIS
#: axis alone holds 464,803 rows over 33 symbols (measured 2026-09-17); parsing every
#: one of them twice a pass costs more than the fit does, and a daily series from 1999
#: adds nothing to an H1 decision made today that its recent tail does not. The NEWEST
#: rows are kept -- a truncated head is depth the pass chose not to buy, and it is
#: reported in the artifact rather than hidden.
MAX_AXIS_ROWS = 120_000
MAX_POINTS_PER_SERIES = 4_000
SEED = 20260917

RULE = ("one model of the world over the hypothesis lane; strictly point-in-time inputs; "
        "epsilon published for the residual hunt; no capital is allocated here")


# ---------------------------------------------------------------------------- memory and clocks
def _free_phys_bytes() -> int | None:
    """Physical memory ACTUALLY FREE, or None when the counter cannot be read.

    Derived, never a constant, for the reason `miner_candidate_compiler._max_rows_per_pass`
    records: a bound sized for the other box either thrashes the machine that holds the live
    terminal or throws away work the larger one had room for. An unreadable counter keeps the
    historic floor exactly -- it is not permission.
    """
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):  # type: ignore[attr-defined]
            return None
        return int(st.ullAvailPhys)
    except Exception:
        try:
            text = Path("/proc/meminfo").read_text(encoding="utf-8")
            kb = next(int(ln.split()[1]) for ln in text.splitlines()
                      if ln.startswith("MemAvailable:"))
            return kb * 1024
        except Exception:
            return None


def max_store_rows() -> int:
    """The residual store's row bound, derived from measured free memory and floored."""
    free = _free_phys_bytes()
    if free is None:
        return MAX_ROWS_FLOOR
    return max(MAX_ROWS_FLOOR, int(free * FREE_MEMORY_SHARE / BYTES_PER_ROW))


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        # `os.replace` onto a read-only destination is legal on POSIX and WinError 5 here; the
        # box that trades is the Windows one, and a port that passed on the VPS broke it once.
        path.chmod(0o644)
        os.replace(tmp, path)


# ---------------------------------------------------------------------------- the PIT inputs
@dataclass(frozen=True)
class Prepared:
    """One PIT series as two sorted arrays: the instants it became knowable, and its values.

    The join is `searchsorted(avail, t, "right") - 1`, which is the anti-lookahead rule expressed
    as an index: the newest point whose availability does not exceed t, and nothing later. The
    first build did this with a Python pointer per series per row -- 19 million interpreter steps
    per instrument -- which is the difference between an hourly organ and an organ that is
    truncated at the same prefix every hour and never reaches the tail of the universe.
    """

    series_id: str
    dataset: str
    region: str
    information_type: str
    avail: np.ndarray
    values: np.ndarray


@dataclass
class Inputs:
    """Every point-in-time series the desk holds, plus what it does NOT hold, by name."""

    series: list[R.Series]
    unmeasured: list[dict[str, str]]
    arrays: list[Prepared]

    @property
    def datasets(self) -> list[str]:
        return sorted({s.dataset for s in self.series})

    def labels(self) -> dict[str, tuple[str, str]]:
        """dataset -> (region, information type), for attributing explained variance."""
        return {s.dataset: (s.region or "UNKNOWN", s.information_type or "unknown")
                for s in self.series}


def _prepare(series: list[R.Series]) -> list[Prepared]:
    out: list[Prepared] = []
    for one in series:
        points = one.sorted().points
        stamps: list[float] = []
        values: list[float] = []
        for point in points:
            parsed = R.parse_time(point.available_time)
            if parsed is None or not math.isfinite(point.value):
                continue
            stamps.append(parsed.timestamp())
            values.append(float(point.value))
        if len(stamps) < R.MIN_PRIOR:
            continue
        out.append(Prepared(series_id=one.series_id, dataset=one.dataset, region=one.region,
                            information_type=one.information_type,
                            avail=np.asarray(stamps, dtype=float),
                            values=np.asarray(values, dtype=float)))
    return out


def _axis_region(axis_id: str) -> str:
    text = axis_id.lower()
    for prefix, region in (("kr_", "KR"), ("jp_", "JP"), ("cn_", "CN"), ("br_", "BR"),
                           ("za_", "ZA"), ("sa_", "SA"), ("cl_", "CL"), ("ecb", "EA"),
                           ("bis", "GLOBAL"), ("fred", "US"), ("cftc", "US"), ("cot", "US")):
        if text.startswith(prefix) or prefix in text:
            return region
    return "UNKNOWN"


def _points_from_rows(rows: list[Any], value_key: str, time_keys: tuple[str, ...]
                      ) -> list[R.Point]:
    out: list[R.Point] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_value = row.get(value_key)
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        stamp = next((str(row[k]) for k in time_keys if row.get(k)), "")
        parsed = R.parse_time(stamp)
        if parsed is None or not math.isfinite(value):
            continue
        period = str(row.get("period_time") or row.get("d") or row.get("as_of") or stamp)
        available = (parsed + timedelta(hours=CLOCK_PAD_H)).isoformat()
        out.append(R.Point(available_time=available, period_time=period, value=value,
                           vintage_id=row.get("vintage_id")))
    return out


def load_inputs(*, max_series: int = 240) -> Inputs:
    """Every PIT series: the axes, FRED, the country data planes and the forge's own store.

    A series that cannot be read, cannot be stamped, or is too short to carry a prior is named in
    `unmeasured` with the reason and what would measure it. It is never imputed and never zero.
    """
    series: list[R.Series] = []
    unmeasured: list[dict[str, str]] = []

    for path in sorted(AXES.glob("*.json")) if AXES.exists() else []:
        doc = _read_json(path)
        if not isinstance(doc, dict):
            unmeasured.append({"name": f"axes:{path.stem}", "why": "unreadable or not an object",
                               "measured_by": "re-run the axis collector for this file"})
            continue
        axis_id = str(doc.get("id") or path.stem)
        region = _axis_region(axis_id)
        info = str(doc.get("axis") or "macro_state")
        sub = doc.get("series")
        if isinstance(sub, dict):
            for name, block in sub.items():
                pts = block.get("points") if isinstance(block, dict) else None
                if not isinstance(pts, list) or len(pts) < R.MIN_PRIOR:
                    unmeasured.append({"name": f"{axis_id}:{name}",
                                       "why": "fewer points than a prior needs",
                                       "measured_by": "a longer collection history"})
                    continue
                points = _points_from_rows(
                    pts[-MAX_POINTS_PER_SERIES:],
                    "v" if "v" in (pts[0] or {}) else "value",
                    ("available_time", "knowable_at", "d", "period_time"))
                if points:
                    series.append(R.Series(series_id=f"{axis_id}:{name}", points=tuple(points),
                                           dataset=f"axis:{axis_id}", region=region,
                                           information_type=info))
        rows = doc.get("rows")
        if isinstance(rows, list) and rows:
            by_symbol: dict[str, list[dict[str, Any]]] = {}
            numeric = [k for k, v in (rows[0] or {}).items()
                       if isinstance(v, (int, float)) and not isinstance(v, bool)]
            for row in rows[-MAX_AXIS_ROWS:]:
                if isinstance(row, dict) and row.get("symbol"):
                    by_symbol.setdefault(str(row["symbol"]), []).append(row)
            for symbol, srows in sorted(by_symbol.items()):
                for key in numeric[:2]:
                    points = _points_from_rows(srows[-MAX_POINTS_PER_SERIES:], key,
                                               ("available_time", "knowable_at", "as_of"))
                    if len(points) >= R.MIN_PRIOR:
                        series.append(R.Series(series_id=f"{axis_id}:{symbol}:{key}",
                                               points=tuple(points), dataset=f"axis:{axis_id}",
                                               region=region, information_type=info))

    fred = _read_json(FRED)
    if isinstance(fred, dict) and isinstance(fred.get("series"), dict):
        for name, rows in fred["series"].items():
            if not isinstance(rows, list) or len(rows) < R.MIN_PRIOR:
                continue
            points: list[R.Point] = []
            for row in rows[-MAX_POINTS_PER_SERIES:]:
                if not isinstance(row, (list, tuple)) or len(row) < 2:
                    continue
                stamp = R.parse_time(str(row[0]))
                try:
                    value = float(row[1])
                except (TypeError, ValueError):
                    continue
                if stamp is None or not math.isfinite(value):
                    continue
                # A daily market print is knowable the next day; the pad then covers the broker
                # clock. This is `libs/data/pit_stamp.DEFAULT_LAG_DAYS["daily"]`, not a guess.
                available = (stamp + timedelta(days=1, hours=CLOCK_PAD_H)).isoformat()
                points.append(R.Point(available_time=available, period_time=str(row[0]),
                                      value=value))
            if len(points) >= R.MIN_PRIOR:
                series.append(R.Series(series_id=f"fred:{name}", points=tuple(points),
                                       dataset="fred_macro", region="US",
                                       information_type="macro_state"))
    else:
        unmeasured.append({"name": "fred_macro", "why": "no series block in data/fred_macro.json",
                           "measured_by": "the hourly fred_macro leg"})

    manifest = _read_json(REPRESENTATIONS / "manifest.json")
    if isinstance(manifest, dict) and isinstance(manifest.get("representations"), list):
        for row in manifest["representations"]:
            if not isinstance(row, dict) or not row.get("file"):
                continue
            doc = _read_json(REPRESENTATIONS / str(row["file"]))
            pts = doc.get("points") if isinstance(doc, dict) else None
            if not isinstance(pts, list) or len(pts) < R.MIN_PRIOR:
                continue
            points = [R.Point(available_time=str(p.get("available_time")),
                              period_time=str(p.get("period_time")), value=float(p.get("value")))
                      for p in pts[-MAX_POINTS_PER_SERIES:]
                      if isinstance(p, dict) and p.get("available_time") is not None
                      and isinstance(p.get("value"), (int, float))]
            if len(points) >= R.MIN_PRIOR:
                series.append(R.Series(series_id=str(row.get("id") or row["file"]),
                                       points=tuple(points),
                                       dataset=f"representation:{row.get('family') or 'unknown'}",
                                       region=str(row.get("region") or "UNKNOWN"),
                                       information_type="representation"))
    else:
        unmeasured.append({"name": "representations",
                           "why": "no manifest under data/representations",
                           "measured_by": "the hourly representation_forge leg"})

    if not MOAT_SERIES.exists():
        unmeasured.append({"name": "moat_series", "why": "reports/MOAT_SERIES.json absent",
                           "measured_by": "the hourly moat_series leg"})

    series.sort(key=lambda s: (-len(s.points), s.series_id))
    kept = series[:max_series]
    return Inputs(series=kept, unmeasured=unmeasured, arrays=_prepare(kept))


# ---------------------------------------------------------------------------- the bars
def load_bars(symbol: str) -> tuple[np.ndarray, np.ndarray] | None:
    """(epoch seconds, close) for one symbol's H1 bars, newest `MAX_BARS` only."""
    path = UNIVERSE_DIR / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd

        frame = pd.read_parquet(path, columns=["close"])
    except Exception:
        return None
    if frame.empty or len(frame) < MIN_ROWS:
        return None
    frame = frame.tail(MAX_BARS)
    index = frame.index
    # The stored index is tz-aware, and its wall clock is the BROKER's (+2/+3 on UTC). Dropping
    # the tzinfo keeps those wall-clock hours, which is what the session windows and the gold
    # clocks are written in -- converting to true UTC would move every bar into another session.
    if getattr(index, "tz", None) is not None:
        index = index.tz_convert("UTC").tz_localize(None)
    try:
        stamps = index.to_numpy(dtype="datetime64[s]").astype("int64")
    except (TypeError, ValueError):
        return None
    closes = frame["close"].to_numpy(dtype=float)
    ok = np.isfinite(closes) & (closes > 0)
    return stamps[ok], closes[ok]


def session_of(hour: int) -> str:
    """The desk's session label for an hour of the broker clock; `overlap` when two claim it."""
    hits = [name for name, (lo, hi) in SESSION_WINDOWS.items() if lo <= hour < hi]
    if len(hits) > 1:
        return "overlap"
    return hits[0] if hits else "off"


def vol_regime(vol: np.ndarray) -> tuple[np.ndarray, tuple[float, float] | None]:
    """Causal vol terciles: each bar labelled against the cut fitted on bars STRICTLY before it.

    The labels are `regime_router`'s own vocabulary (low/mid/high, `UNMEASURED` until the prior
    is long enough), so a residual cluster names a state the rest of the desk already knows.
    """
    labels = np.full(vol.shape, 3, dtype=np.int8)      # 3 == UNMEASURED
    cuts: tuple[float, float] | None = None
    finite = np.isfinite(vol)
    # THE CUT IS REFITTED EVERY `VOL_RECUT` BARS, NOT EVERY BAR, and it is still causal: the bars
    # in a block are labelled by the cut fitted on everything before the block began. Per bar it
    # is a quantile over a growing array -- O(n^2 log n), 19,800 sorts on a five-year panel -- and
    # the organ would be killed at the same prefix every hour rather than be slow.
    for start in range(VOL_PRE_MIN, len(vol), VOL_RECUT):
        prior = vol[:start][finite[:start]]
        if prior.size < VOL_PRE_MIN:
            continue
        lo, hi = (float(v) for v in np.quantile(prior, [1 / 3, 2 / 3]))
        cuts = (lo, hi)
        stop = min(start + VOL_RECUT, len(vol))
        block = vol[start:stop]
        block_labels = np.where(block < lo, 0, np.where(block > hi, 2, 1)).astype(np.int8)
        labels[start:stop] = np.where(finite[start:stop], block_labels, 3)
    return labels, cuts


REGIME_NAMES = ("low", "mid", "high", "UNMEASURED")


@dataclass
class Design:
    """One target's design matrix, its labels, and the dataset each column belongs to."""

    X: np.ndarray
    y: np.ndarray
    times: np.ndarray
    regimes: np.ndarray
    sessions: list[str]
    columns: list[str]
    groups: list[str]
    vol_z: np.ndarray
    vol_cuts: tuple[float, float] | None
    unmeasured: list[str]


def build_design(symbol: str, horizon_bars: int, inputs: Inputs) -> Design | None:
    """Bars plus every knowable input, aligned STRICTLY point-in-time.

    The external join is a forward scan per series: a pointer walks the series' own points and
    stops before the first one whose `available_time` exceeds the decision instant, so the value
    at t is the newest vintage knowable at t and a later revision is unreachable by construction.
    """
    bars = load_bars(symbol)
    if bars is None:
        return None
    stamps, close = bars
    if len(close) < MIN_ROWS + horizon_bars + VOL_PRE_MIN:
        return None
    logc = np.log(close)
    r1 = np.diff(logc, prepend=logc[0])
    vol = np.full(r1.shape, np.nan)
    if len(r1) > VOL_WINDOW:
        cumsum = np.cumsum(np.insert(r1 ** 2, 0, 0.0))
        window = (cumsum[VOL_WINDOW:] - cumsum[:-VOL_WINDOW]) / VOL_WINDOW
        vol[VOL_WINDOW:] = np.sqrt(window[:len(vol) - VOL_WINDOW])
    regimes, cuts = vol_regime(vol)
    with np.errstate(invalid="ignore"):
        vol_mean = np.nanmean(vol)
        vol_sd = np.nanstd(vol)
    vol_z = (vol - vol_mean) / vol_sd if np.isfinite(vol_sd) and vol_sd > 0 else vol * 0.0

    n = len(close)
    idx = np.arange(n)
    usable = idx[(idx >= VOL_PRE_MIN) & (idx + horizon_bars < n)]
    if usable.size < MIN_ROWS:
        return None
    y = logc[usable + horizon_bars] - logc[usable]

    def _lagged(series: np.ndarray, lag: int) -> np.ndarray:
        return series[usable - lag]

    columns = ["r1", "r4", "r24", "vol_z", "vol_chg", "range_pos",
               "sess_asia", "sess_london", "sess_ny", "dow_sin", "dow_cos"]
    r4 = logc - np.roll(logc, 4)
    r24 = logc - np.roll(logc, 24)
    # Epoch arithmetic rather than 40,000 datetime objects per design. 1970-01-01 was a Thursday,
    # whose `weekday()` is 3, which is where the +3 comes from.
    hours = ((stamps[usable] // 3600) % 24).astype(int)
    dows = (((stamps[usable] // 86400) + 3) % 7).astype(int)
    lo120 = np.array([float(close[max(0, i - 120):i + 1].min()) for i in usable])
    hi120 = np.array([float(close[max(0, i - 120):i + 1].max()) for i in usable])
    span = np.where(hi120 - lo120 > 0, hi120 - lo120, np.nan)
    price_block = np.column_stack([
        _lagged(r1, 0), _lagged(r4, 0), _lagged(r24, 0), _lagged(vol_z, 0),
        _lagged(vol_z, 0) - _lagged(vol_z, VOL_WINDOW),
        (close[usable] - lo120) / span,
        (hours >= 0) & (hours < 8), (hours >= 8) & (hours < 16), (hours >= 14) & (hours < 22),
        np.sin(2 * np.pi * dows / 7), np.cos(2 * np.pi * dows / 7),
    ]).astype(float)
    groups = ["price"] * price_block.shape[1]

    decision = stamps[usable].astype(float)
    external: list[np.ndarray] = []
    unmeasured: list[str] = []
    for prepared in inputs.arrays:
        # THE ANTI-LOOKAHEAD JOIN, as one index: the newest point whose availability does not
        # exceed the decision instant. `side="right"` then `- 1` means a value stamped exactly at
        # t IS usable and anything after it is unreachable, which is the rule this organ exists
        # to keep. A row before the series' first point stays NaN and is never back-filled.
        position = np.searchsorted(prepared.avail, decision, side="right") - 1
        column = np.where(position >= 0, prepared.values[np.clip(position, 0, None)], np.nan)
        coverage = float(np.isfinite(column).mean())
        spread = float(np.nanstd(column)) if coverage > 0 else 0.0
        if coverage < 0.5 or not math.isfinite(spread) or spread <= 0:
            unmeasured.append(f"{prepared.series_id} (coverage {coverage:.0%})")
            continue
        external.append(column)
        columns.append(prepared.series_id)
        groups.append(prepared.dataset)
        if len(external) + price_block.shape[1] >= MAX_FEATURES:
            break

    blocks = [price_block, *[c.reshape(-1, 1) for c in external]]
    matrix = np.column_stack(blocks) if len(blocks) > 1 else price_block
    good = np.isfinite(matrix).all(axis=1) & np.isfinite(y)
    if int(good.sum()) < MIN_ROWS:
        return None
    return Design(X=matrix[good], y=y[good], times=stamps[usable][good],
                  regimes=regimes[usable][good],
                  sessions=[session_of(int(h)) for h in hours[good]],
                  columns=columns, groups=groups, vol_z=vol_z[usable][good], vol_cuts=cuts,
                  unmeasured=unmeasured)


# ---------------------------------------------------------------------------- the model
def _standardise(train: np.ndarray, other: np.ndarray,
                 stats: dict[str, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Standardise on the TRAIN fold, clip the tails, and silence columns the fold cannot fit.

    MEASURED ON THE REAL TREE 2026-09-17, and it is the difference between a report and a
    liability: with 58 forge representations in the input set (37 of them cross-dataset ratios),
    ADAUSD's 5d target scored an out-of-sample R2 of -1.2e7. The cause is not the model. A ratio
    feature that is nearly CONSTANT inside one training fold gets an sd of ~1e-9; the next fold's
    value is then thousands of standardised units away, and one column with a fitted coefficient
    multiplies it. The prediction leaves the range of anything the desk trades.

    Two fixes, both of which are statements about what the fold actually MEASURED:

      * a column whose train-fold sd is below `DEAD_COLUMN_SD` was constant while the model was
        fitted, so the fit knows nothing about it -- it is zeroed rather than divided by a floor
        of 1.0, which would have let an unfitted column dominate at test time;
      * everything else is clipped to +/- `STANDARD_CLIP` train sd. A test value forty sd from
        the training mean is out of distribution, and extrapolating a linear coefficient across
        that gap is not prediction, it is arithmetic.

    Both are applied to the TRAIN matrix too, so the fit and the prediction see the same space.
    """
    mu = train.mean(axis=0)
    raw_sd = train.std(axis=0)
    alive = raw_sd > DEAD_COLUMN_SD
    sd = np.where(alive, raw_sd, 1.0)
    z_train = np.clip((train - mu) / sd, -STANDARD_CLIP, STANDARD_CLIP)
    z_other_raw = (other - mu) / sd
    z_other = np.clip(z_other_raw, -STANDARD_CLIP, STANDARD_CLIP)
    z_train[:, ~alive] = 0.0
    z_other[:, ~alive] = 0.0
    if stats is not None and z_other_raw.size:
        clipped = float(np.abs(z_other_raw[:, alive]).max(initial=0.0)) if alive.any() else 0.0
        stats["dead_columns"] = max(stats.get("dead_columns", 0.0), float((~alive).sum()))
        stats["max_abs_z"] = max(stats.get("max_abs_z", 0.0), clipped)
        stats["clipped_frac"] = max(
            stats.get("clipped_frac", 0.0),
            float((np.abs(z_other_raw) > STANDARD_CLIP).mean()))
    return z_train, z_other


def ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    gram = X.T @ X + alpha * np.eye(X.shape[1])
    try:
        return np.linalg.solve(gram, X.T @ y)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(gram, X.T @ y, rcond=None)[0]


def _knn_residual(train_x: np.ndarray, train_r: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    """k-NN over the standardised features: the fallback residual learner when sklearn is absent.

    Chunked over the test rows on purpose -- the full pairwise distance matrix on a five-year H1
    panel is exactly the allocation that takes an 8 GB box down, and this organ shares the box
    with a live terminal.
    """
    k = min(KNN_K, max(2, len(train_x) // 20))
    out = np.zeros(len(test_x))
    chunk = 256
    for start in range(0, len(test_x), chunk):
        block = test_x[start:start + chunk]
        d = ((block[:, None, :] - train_x[None, :, :]) ** 2).sum(axis=2)
        near = np.argpartition(d, kth=k - 1, axis=1)[:, :k]
        out[start:start + chunk] = train_r[near].mean(axis=1)
    return out


def _nonlinear(train_x: np.ndarray, train_r: np.ndarray, test_x: np.ndarray) -> tuple[
        np.ndarray, str]:
    if len(train_x) < MIN_NONLINEAR:
        return np.zeros(len(test_x)), "SKIPPED_SHORT_TRAIN"
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor

        model = HistGradientBoostingRegressor(max_depth=3, max_iter=80, learning_rate=0.05,
                                              random_state=SEED)
        model.fit(train_x, train_r)
        return np.asarray(model.predict(test_x), dtype=float), "sklearn_hist_gbr"
    except Exception:
        try:
            return _knn_residual(train_x, train_r, test_x), "knn_residual"
        except Exception:
            return np.zeros(len(test_x)), "UNMEASURED_NONLINEAR"


def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        return float("nan")
    return float(1.0 - ((y - yhat) ** 2).sum() / sst)


@dataclass
class Fit:
    """One purged expanding-window fit: pooled OOS predictions and what produced them."""

    index: np.ndarray
    yhat_linear: np.ndarray
    yhat: np.ndarray
    r2_linear: float
    r2: float
    learner: str
    folds: int
    nonlinear_folds: int = 0
    nonlinear_helped: int = 0
    scaling: dict[str, float] = field(default_factory=dict)
    r2_ungated: float = float("nan")
    baseline_folds: int = 0


def purged_cv(X: np.ndarray, y: np.ndarray, purge: int, *, folds: int = FOLDS,
              nonlinear: bool = True) -> Fit | None:
    """Expanding-window CV with a PURGE GAP of one full horizon between train and test.

    Without the gap the last `horizon` training rows overlap the first test row's forward window
    and the fit is scored partly on its own target. The gap costs rows and buys the only R2 that
    means anything out of sample.
    """
    n = len(y)
    if n < MIN_TRAIN + purge + 50:
        return None
    edges = [int(n * (k + 1) / (folds + 1)) for k in range(folds + 1)]
    idx_parts: list[np.ndarray] = []
    lin_parts: list[np.ndarray] = []
    full_parts: list[np.ndarray] = []
    learner = "none"
    used = 0
    offered = 0
    helped = 0
    # THE NONLINEAR LEARNER MUST EARN ITS PLACE, FOLD BY FOLD, AND IT IS EARNED FORWARD.
    # MEASURED on the real tree 2026-09-17: with the boosted residual learner applied
    # unconditionally, AUDCAD's 1d target scored an out-of-sample R2 of -20.1 -- the learner
    # fitted the training residuals and destroyed a linear prediction that was merely weak. It is
    # now applied to fold k only if it IMPROVED fold k-1's squared error, which costs no extra
    # fit (the adjustment is computed anyway, to measure it) and cannot look ahead: the evidence
    # is strictly from earlier folds. A model that cannot beat its own linear part on the last
    # out-of-sample block does not get to speak on the next one.
    allow_nonlinear = False
    allow_linear = True
    baselined = 0
    ungated_parts: list[np.ndarray] = []
    scaling: dict[str, float] = {}
    for k in range(folds):
        train_end = max(0, edges[k] - purge)
        test_lo, test_hi = edges[k], edges[k + 1]
        if train_end < MIN_TRAIN or test_hi - test_lo < 10:
            continue
        train_x_raw, test_x_raw = X[:train_end], X[test_lo:test_hi]
        train_y, test_y = y[:train_end], y[test_lo:test_hi]
        train_x, test_x = _standardise(train_x_raw, test_x_raw, scaling)
        inner = max(MIN_TRAIN // 2, int(train_end * 0.75))
        best_alpha, best_score = RIDGE_GRID[0], -np.inf
        if inner < train_end - 10:
            in_x, ho_x = _standardise(train_x_raw[:inner], train_x_raw[inner:])
            for alpha in RIDGE_GRID:
                beta = ridge_fit(in_x, train_y[:inner] - train_y[:inner].mean(), alpha)
                pred = ho_x @ beta + train_y[:inner].mean()
                score = _r2(train_y[inner:], pred)
                if np.isfinite(score) and score > best_score:
                    best_alpha, best_score = alpha, score
        mean_y = float(train_y.mean())
        beta = ridge_fit(train_x, train_y - mean_y, best_alpha)
        ridge_pred = test_x @ beta + mean_y
        baseline = np.full(len(test_y), mean_y)
        # THE RIDGE MUST ALSO BEAT ITS OWN BASELINE, FOLD BY FOLD, FORWARD.
        # An out-of-sample R2 below zero means the model predicts WORSE than the training mean --
        # measured here on real FX at the 5d horizon, where it reached -4.7. That is a legitimate
        # finding about forecastability, but it poisons the thing this organ exists to publish:
        # epsilon = y - yhat then has MORE variance than y itself, so `residual_hunt` hunts the
        # model's own noise instead of the world's unexplained structure. When the previous fold's
        # ridge lost to the constant, this fold predicts the constant -- the residual is then
        # honestly "what a desk that knew only the mean could not explain", which is the weakest
        # claim the hunt can be built on and therefore the right one. `r2_ungated` still reports
        # what the ridge alone would have scored, so the finding is not hidden by the fix.
        pred_lin = ridge_pred if allow_linear else baseline
        if not allow_linear:
            baselined += 1
        allow_linear = float(((test_y - ridge_pred) ** 2).sum()) <= float(
            ((test_y - baseline) ** 2).sum())
        ungated_parts.append(ridge_pred)
        pred = pred_lin
        if nonlinear:
            train_resid = train_y - (train_x @ beta + mean_y)
            adjustment, learner = _nonlinear(train_x, train_resid, test_x)
            if np.any(adjustment):
                offered += 1
                sse_linear = float(((test_y - pred_lin) ** 2).sum())
                sse_adjusted = float(((test_y - (pred_lin + adjustment)) ** 2).sum())
                if allow_nonlinear:
                    pred = pred_lin + adjustment
                improved = sse_adjusted < sse_linear
                helped += int(improved)
                allow_nonlinear = improved
        idx_parts.append(np.arange(test_lo, test_hi))
        lin_parts.append(pred_lin)
        full_parts.append(pred)
        used += 1
    if not idx_parts:
        return None
    index = np.concatenate(idx_parts)
    yhat_lin = np.concatenate(lin_parts)
    yhat = np.concatenate(full_parts)
    ungated = np.concatenate(ungated_parts) if ungated_parts else yhat_lin
    return Fit(index=index, yhat_linear=yhat_lin, yhat=yhat,
               r2_linear=_r2(y[index], yhat_lin), r2=_r2(y[index], yhat),
               learner=learner, folds=used, nonlinear_folds=offered, nonlinear_helped=helped,
               scaling={k: round(v, 4) for k, v in scaling.items()},
               r2_ungated=_r2(y[index], ungated), baseline_folds=baselined)


def contributions(design: Design, purge: int) -> dict[str, float]:
    """Drop-one-DATASET refits: how much out-of-sample R2 each dataset group is worth.

    Measured by REFITTING without the group rather than by reading a coefficient, because a
    coefficient in a correlated design says nothing about what the model would do if the series
    were gone -- and "what if we never had this dataset" is exactly the question dataset ROI asks.
    """
    out: dict[str, float] = {}
    groups = sorted(set(design.groups))
    if len(groups) < 2:
        return out
    full = purged_cv(design.X, design.y, purge, nonlinear=False)
    if full is None:
        return out
    for group in groups:
        keep = [i for i, g in enumerate(design.groups) if g != group]
        if not keep:
            continue
        fit = purged_cv(design.X[:, keep], design.y, purge, nonlinear=False)
        if fit is None:
            continue
        out[group] = round(float(full.r2_linear - fit.r2_linear), 6)
    return out


def regime_forecast(design: Design, purge: int) -> dict[str, Any]:
    """The next-horizon vol bucket as a DISTRIBUTION, from the same machinery.

    The point forecast is a ridge on forward vol_z; the distribution is that forecast plus the
    empirical out-of-sample residuals, mapped through the SAME causal tercile cuts the regime
    labels use. A forecast without a distribution is a label, and the allocator's inputs need the
    spread more than the centre.
    """
    if design.vol_cuts is None:
        return {"status": "UNMEASURED", "why": "no causal tercile cut yet (prior too short)",
                "measured_by": f"{VOL_PRE_MIN} prior vol readings"}
    target = np.roll(design.vol_z, -purge)[:-purge] if purge < len(design.vol_z) else None
    if target is None or len(target) < MIN_ROWS:
        return {"status": "UNMEASURED", "why": "forward vol series shorter than the row floor",
                "measured_by": "more bars"}
    fit = purged_cv(design.X[:len(target)], target, purge, nonlinear=False)
    if fit is None:
        return {"status": "UNMEASURED", "why": "no admissible fold", "measured_by": "more bars"}
    resid = target[fit.index] - fit.yhat_linear
    last = float(fit.yhat_linear[-1])
    mean_vol = float(np.nanmean(design.vol_z))
    sd_vol = float(np.nanstd(design.vol_z)) or 1.0
    lo_z = (design.vol_cuts[0] - mean_vol) / sd_vol
    hi_z = (design.vol_cuts[1] - mean_vol) / sd_vol
    draws = last + resid
    total = max(1, len(draws))
    return {"status": "MEASURED", "r2_oos": round(fit.r2_linear, 6),
            "point_vol_z": round(last, 6), "n": int(total),
            "p_low": round(float((draws < lo_z).sum()) / total, 4),
            "p_mid": round(float(((draws >= lo_z) & (draws <= hi_z)).sum()) / total, 4),
            "p_high": round(float((draws > hi_z).sum()) / total, 4),
            "vocabulary": list(REGIME_NAMES)}


# ---------------------------------------------------------------------------- the pass
def _cursor() -> int:
    doc = _read_json(CURSOR)
    return int(doc.get("offset", 0)) if isinstance(doc, dict) else 0


def hypothesis_symbols() -> tuple[list[str], dict[str, int]]:
    registry = _read_json(UNIVERSE_JSON)
    if not isinstance(registry, dict):
        return [], {"hypothesis": 0, "event": 0, "unclassified": 0}
    try:
        import universe_policy as up
    except ImportError:                                                      # pragma: no cover
        from research import universe_policy as up  # type: ignore[no-redef]
    split = up.split(registry.keys())
    counts = {k: len(v) for k, v in split.items()}
    have = {p.stem.removesuffix("_H1") for p in UNIVERSE_DIR.glob("*_H1.parquet")}
    return sorted(s for s in split[up.HYPOTHESIS] if s in have), counts


def run(*, budget_s: float = 1200.0, dry_run: bool = False,
        symbols: list[str] | None = None) -> dict[str, Any]:
    """One pass: fit every target the budget reaches, publish epsilon, credit every dataset."""
    started = time.monotonic()
    deadline = started + budget_s
    inputs = load_inputs()
    labels = inputs.labels()
    universe, counts = (symbols, {"hypothesis": len(symbols)}) if symbols is not None \
        else hypothesis_symbols()
    offset = _cursor() % max(1, len(universe)) if universe else 0
    ordered = universe[offset:] + universe[:offset]

    targets: list[dict[str, Any]] = []
    residual_rows: dict[str, list[dict[str, Any]]] = {h: [] for h in HORIZONS}
    dataset_credit: dict[str, dict[str, float]] = {}
    modelled: list[str] = []
    skipped: list[dict[str, str]] = []
    reached = 0
    for symbol in ordered:
        if time.monotonic() >= deadline:
            break
        reached += 1
        designed = False
        for horizon, bars_ahead in HORIZONS.items():
            if time.monotonic() >= deadline:
                break
            design = build_design(symbol, bars_ahead, inputs)
            if design is None:
                skipped.append({"symbol": symbol, "horizon": horizon,
                                "why": "fewer admissible rows than the floor",
                                "measured_by": f"{MIN_ROWS} clean rows of H1 bars"})
                continue
            fit = purged_cv(design.X, design.y, bars_ahead)
            if fit is None:
                skipped.append({"symbol": symbol, "horizon": horizon,
                                "why": "no fold survived the purge gap",
                                "measured_by": "more bars than train floor + purge"})
                continue
            designed = True
            eps = design.y[fit.index] - fit.yhat
            contribution = contributions(design, bars_ahead)
            by_region: dict[str, float] = {}
            by_info: dict[str, float] = {}
            for dataset, delta in contribution.items():
                region, info = labels.get(dataset, ("UNKNOWN", "price" if dataset == "price"
                                                    else "unknown"))
                by_region[region] = round(by_region.get(region, 0.0) + delta, 6)
                by_info[info] = round(by_info.get(info, 0.0) + delta, 6)
            quantiles = {f"q{int(q * 100):02d}": round(float(np.quantile(eps, q)), 8)
                         for q in (0.05, 0.25, 0.5, 0.75, 0.95)}
            targets.append({
                "symbol": symbol, "horizon": horizon, "horizon_bars": bars_ahead,
                "n": len(fit.index), "n_rows_fitted": len(design.y),
                "r2_oos": round(fit.r2, 6), "r2_oos_linear": round(fit.r2_linear, 6),
                "r2_oos_ridge_ungated": round(fit.r2_ungated, 6),
                "folds_fell_back_to_baseline": fit.baseline_folds,
                "residual_learner": fit.learner, "folds": fit.folds,
                "nonlinear_folds_offered": fit.nonlinear_folds,
                "nonlinear_folds_that_helped": fit.nonlinear_helped,
                "feature_scaling": fit.scaling,
                "n_features": int(design.X.shape[1]),
                "contributions": contribution,
                "explained_variance": {"by_dataset": contribution, "by_region": by_region,
                                       "by_information_type": by_info},
                "predictive_distribution": quantiles,
                "epsilon_mean": round(float(eps.mean()), 8),
                "epsilon_sd": round(float(eps.std()), 8),
                "regime_forecast": regime_forecast(design, bars_ahead),
                "unmeasured_inputs": design.unmeasured[:40],
                "n_unmeasured_inputs": len(design.unmeasured),
            })
            for group, delta in contribution.items():
                row = dataset_credit.setdefault(group, {"targets": 0.0, "delta_r2": 0.0})
                row["targets"] += 1.0
                row["delta_r2"] += float(delta)
            for position in range(max(0, len(fit.index) - MAX_RESIDUAL_ROWS), len(fit.index)):
                row_index = int(fit.index[position])
                residual_rows[horizon].append({
                    "target": symbol, "symbol": symbol, "horizon": horizon,
                    "time": datetime.fromtimestamp(int(design.times[row_index]),
                                                   tz=UTC).isoformat(),
                    "y": float(design.y[row_index]), "yhat": float(fit.yhat[position]),
                    "epsilon": float(eps[position]),
                    "regime": REGIME_NAMES[int(design.regimes[row_index])],
                    "session": design.sessions[row_index],
                })
        if designed:
            modelled.append(symbol)

    elapsed = round(time.monotonic() - started, 2)
    store_stats: dict[str, Any] = {}
    if not dry_run:
        store_stats = write_residual_store(residual_rows, modelled)
        _atomic(CURSOR, {"offset": (offset + reached) % max(1, len(universe)),
                         "at": now_iso(), "universe": len(universe)})

    report: dict[str, Any] = {
        "at": now_iso(), "rule": RULE, "budget_s": budget_s, "elapsed_s": elapsed,
        "dry_run": dry_run,
        "universe": {**counts, "with_bars": len(universe), "reached_this_pass": reached,
                     "modelled": len(modelled), "cursor_offset": offset},
        "horizons": HORIZONS,
        "n_targets": len(targets),
        "median_r2_oos": round(float(np.median([t["r2_oos"] for t in targets])), 6)
        if targets else None,
        "targets": targets,
        "inputs": {"n_series": len(inputs.series), "datasets": inputs.datasets,
                   "unmeasured": inputs.unmeasured,
                   "clock_pad_h": CLOCK_PAD_H,
                   "depth_bound": {"max_points_per_series": MAX_POINTS_PER_SERIES,
                                   "max_axis_rows": MAX_AXIS_ROWS,
                                   "why": "the newest rows are kept; a truncated head is depth "
                                          "this pass chose not to buy, not depth that is absent"},
                   "alignment": "an input value is usable at t only if available_time <= t; the "
                                "newest vintage knowable at t, never a later revision"},
        "dataset_credit": {k: {"targets": int(v["targets"]),
                               "sum_delta_r2": round(v["delta_r2"], 6),
                               "mean_delta_r2": round(v["delta_r2"] / v["targets"], 6)
                               if v["targets"] else None}
                           for k, v in sorted(dataset_credit.items())},
        "skipped": skipped[:80], "n_skipped": len(skipped),
        "residual_store": store_stats,
        "memory": {"max_store_rows": max_store_rows(),
                   "free_phys_mb": round((_free_phys_bytes() or 0) / 2 ** 20, 1) or None,
                   "why": "the bound is derived from measured free memory, floored so an "
                          "unreadable counter changes nothing"},
        "allocates_capital": False,
    }
    if not dry_run:
        report["registry"] = record_registry(report)
        _atomic(OUT, report)
    return report


def write_residual_store(rows: dict[str, list[dict[str, Any]]],
                         refreshed: list[str]) -> dict[str, Any]:
    """Merge this pass's residuals into the per-horizon store, bounded by measured memory.

    MERGED, NOT OVERWRITTEN. A budget-bounded pass covers part of the universe, and a store
    rewritten from one pass would delete every symbol the hour did not reach -- turning a
    deliberate partial pass into data loss, which is the `enrol_clocks` failure in another
    costume. Rows for the symbols this pass refreshed are replaced; every other symbol stands.
    """
    STORE.mkdir(parents=True, exist_ok=True)
    cap = max_store_rows()
    out: dict[str, Any] = {}
    fresh = set(refreshed)
    for horizon, new_rows in rows.items():
        parquet = STORE / f"residuals_{horizon}.parquet"
        fallback = STORE / f"residuals_{horizon}.json"
        kept: list[dict[str, Any]] = []
        existing = read_residuals(horizon)
        kept = [r for r in existing if str(r.get("symbol")) not in fresh]
        merged = (kept + new_rows)[-cap:]
        written = "none"
        if merged:
            try:
                import pandas as pd

                frame = pd.DataFrame(merged)
                tmp = parquet.with_suffix(".parquet.tmp")
                frame.to_parquet(tmp, index=False)
                os.replace(tmp, parquet)
                written = "parquet"
            except Exception:
                _atomic(fallback, {"at": now_iso(), "horizon": horizon, "n": len(merged),
                                   "rows": merged})
                written = "json"
        out[horizon] = {"rows_new": len(new_rows), "rows_kept": len(kept),
                        "rows_total": len(merged), "format": written,
                        "path": str(parquet if written == "parquet" else fallback),
                        "cap": cap}
    return out


def read_residuals(horizon: str) -> list[dict[str, Any]]:
    """The residual store for one horizon, whichever form it was written in."""
    parquet = STORE / f"residuals_{horizon}.parquet"
    if parquet.exists():
        try:
            import pandas as pd

            return [dict(r) for r in pd.read_parquet(parquet).to_dict("records")]
        except Exception:
            return []
    doc = _read_json(STORE / f"residuals_{horizon}.json")
    rows = doc.get("rows") if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def record_registry(report: dict[str, Any]) -> dict[str, Any]:
    """Dataset contribution into `source_yield` and the pass's KPIs into `kpis`.

    Never fatal. A registry that can take down the organ measuring it would be removed within a
    week, correctly -- so every failure here is reported in the artifact and nothing else.
    """
    out: dict[str, Any] = {"kpis": 0, "sources": 0}
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unimportable: {type(exc).__name__}"}
    day = now_iso()[:10]
    try:
        conn = reg.connect()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unopenable: {type(exc).__name__}"}
    try:
        reg.kpi(day, "world_model.targets", float(report["n_targets"]),
                detail={"universe": report["universe"]}, conn=conn)
        if report.get("median_r2_oos") is not None:
            reg.kpi(day, "world_model.median_r2_oos", float(report["median_r2_oos"]), conn=conn)
        out["kpis"] += 2
        for dataset, row in report["dataset_credit"].items():
            reg.kpi(day, f"world_model.contribution.{dataset}",
                    float(row["mean_delta_r2"] or 0.0), detail=row, conn=conn)
            out["kpis"] += 1
            try:
                import source_frontier as sf

                sf.bump_source_yield(dataset, conn=conn, leads=float(row["targets"]))
                out["sources"] += 1
            except Exception:
                continue
    except Exception as exc:
        out["status"] = f"PARTIAL: {type(exc).__name__}"
    finally:
        conn.close()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode; the clock is "
                                                        "the hourly cycle)")
    ap.add_argument("--budget-s", type=float, default=1200.0)
    ap.add_argument("--dry-run", action="store_true", help="fit and print; write nothing")
    ap.add_argument("--symbol", action="append", default=None,
                    help="restrict to these symbols (diagnosis)")
    args = ap.parse_args(argv)

    report = run(budget_s=args.budget_s, dry_run=args.dry_run, symbols=args.symbol)
    print(f"world model: {report['n_targets']} target(s) over "
          f"{report['universe']['modelled']} instrument(s), median OOS R2 "
          f"{report['median_r2_oos']}, {report['inputs']['n_series']} PIT series, "
          f"{len(report['inputs']['unmeasured'])} unmeasured input(s), {report['elapsed_s']}s")
    for target in report["targets"][:8]:
        print(f"    {target['symbol']:<10}{target['horizon']:>4}  R2 {target['r2_oos']:>9.5f}  "
              f"n={target['n']:<6} learner={target['residual_learner']}")
    if args.dry_run:
        print("--dry-run: nothing written, no residual store, no registry row")
        return 0
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
