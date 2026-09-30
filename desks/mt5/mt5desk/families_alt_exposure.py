"""ALT-DATA EXPOSURE CLASS BOOKS: free alt-data releases ranked ACROSS the equity class on one date.

WHY (2026-09-30). `research/alt_proxies.py` publishes free substitutes for paid alt data (Korea's
20-day exports, TSA throughput, GDELT country tone ...) as point-in-time lake series, and its
equity hand-off (`data/digests/alt_proxies_equity_handoff.json`) names the share CFDs each series
bears on with a DECLARED prior sign. The first consumer of that hand-off traded it as single names:
one share, one series, one side -- a single-series time-series bet on a single name, which is
exactly what the two-lane order keeps off share CFDs, and a macro release is not company news, so
the news lane does not take it either (coordinator's ruling, 2026-09-30).

So the hand-off is traded here the only way the order admits for a share: as a CROSS-SECTIONAL
BOOK (principal's amendment, 2026-09-30 11:29, "do cross sectional add cross sectional and news").
On every decision date each share the hand-off maps is given one score -- the mean, over the
series that bear on it, of the series' own standardised reading times the declared prior sign --
and the share is RANKED against every other equity-class member carrying a score on THAT date.
The book is long the top `quantile` and short the bottom: long the names whose demand indicators
are surprising up relative to their peers', short the names whose indicators are surprising down.
It is market-neutral within the class, so a release that lifts every name the same way earns
nothing; only the DIFFERENCE between names' alt-data news is the bet.

ONE LEG PER CELL, BUILT FROM `symbol` ALONE, the class-book pattern of `families_cross_sectional`
and `families_quantamental`: the family loads the equity class's closes through
`families_cross_sectional.class_panel`, reads the hand-off and every mapped lake series itself,
and emits the leg's side on each decision bar, so the sealed gauntlet, the forward clock and the
executor all build the cell through the ordinary `fn(h1, **params)` call. The union of the legs
is the book.

THE FAMILIES AND THEIR PRIORS (written before any data was looked at):

  alt_exposure_pace_book      Slow diffusion of a public but unread datum: a share whose mapped
      alt-data PACE (the series' own year-on-year or anomaly transform) is high relative to its
      own history, signed by the prior, outperforms peers whose pace is low. Payer: the holder
      who does not read a Korean customs release or a TSA count; constraint: attention and the
      language/venue barrier (the hand-off roster's own mechanism fields).
  alt_exposure_release_book   The same payer, measured at the RELEASE: each share's latest
      first-vintage `surprise_z` within `window_d` days, signed by the prior and ranked across the
      class. This is where a macro release's reaction lives now that it is off the news lane.

NO LOOKAHEAD. A lake point is used only from its FIRST vintage's `available_time` (UTC), moved
into the bar index's broker frame (New York + 7h, `libs/regime/session_clock.py`); a point is
visible on a decision bar stamped at or after that instant and never earlier. Pace is standardised
against the series' own STRICTLY EARLIER points. A reading older than `max_age_d` (pace) or
`window_d` (release) days is absent from that day's cross-section, never carried forward.

HONEST LIMITS. A family returns [] when the symbol is not an equity-class share, the hand-off maps
no usable series to it, or fewer than `families_cross_sectional.MIN_MEMBERS` members carry a
finite score that day (that day ranks nobody). A member the hand-off does not map has NO score --
it is absent from the rank, never scored zero.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk import families_cross_sectional as xs
from mt5desk.families import Signal

BASE = Path(__file__).resolve().parent.parent
#: The hand-off and the lake. Module-level so a test can point them at synthetic files.
HANDOFF = BASE / "data" / "digests" / "alt_proxies_equity_handoff.json"
SERIES_DIR = BASE / "data" / "lake" / "series"

#: The peer class these rank within.
KLASS = "equity"
#: Strictly earlier points a pace reading needs before it is standardised against them.
PACE_MIN_HISTORY = 12
#: A standardised reading is clipped here so one outlier release cannot own the rank.
CLIP = 3.0

#: THE GRID IS THE TRIAL COUNT. One point per family: which share carries which series with which
#: sign is the hand-off's evidence, not a searched parameter, and the organ that mints these cells
#: (research/alt_equity_handoff.py) charges every point of this grid once per cell.
PARAM_GRID: dict[str, dict[str, list]] = {
    "alt_exposure_pace_book": {"hold_d": [20], "quantile": [1 / 3]},
    "alt_exposure_release_book": {"hold_d": [5], "quantile": [1 / 3]},
}

try:  # pragma: no cover - depends on the tree the family runs in
    from libs.regime.session_clock import SERVER_SHIFT_H, SERVER_TZ
except Exception:  # pragma: no cover
    SERVER_TZ, SERVER_SHIFT_H = "America/New_York", 7

_HANDOFF_CACHE: dict[tuple[str, int], dict[str, list[tuple[str, int]]]] = {}
_SERIES_CACHE: dict[tuple[str, int, str], tuple[np.ndarray, np.ndarray]] = {}


# ------------------------------------------------------------------------------ inputs ---
def exposures(path: Path | None = None) -> dict[str, list[tuple[str, int]]]:
    """{SHARE (upper): [(lake_file, prior_sign), ...]} from the hand-off's USABLE rows only.
    {} when the hand-off is absent or unreadable -- no book, never a guessed one."""
    p = Path(path or HANDOFF)
    try:
        key = (str(p), p.stat().st_mtime_ns)
    except OSError:
        return {}
    if key in _HANDOFF_CACHE:
        return _HANDOFF_CACHE[key]
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, list[tuple[str, int]]] = {}
    rows = doc.get("rows") if isinstance(doc, dict) else None
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or not r.get("usable"):
            continue
        lake = str(r.get("lake_file") or "")
        if not lake or any(c in lake for c in ("/", "\\", "..")):
            continue
        for sym, sign in (r.get("shares") or {}).items():
            try:
                s = 1 if int(sign) > 0 else -1
            except (TypeError, ValueError):
                continue
            out.setdefault(str(sym).upper(), []).append((lake, s))
    _HANDOFF_CACHE.clear()
    _HANDOFF_CACHE[key] = out
    return out


def to_broker_ns(avail_utc: pd.Series) -> np.ndarray:
    """Genuinely-UTC instants as the int64 ns stamps the broker's bar index carries."""
    ny = avail_utc.dt.tz_convert(SERVER_TZ).dt.tz_localize(None)
    shifted = ny + timedelta(hours=int(SERVER_SHIFT_H))
    return shifted.to_numpy(dtype="datetime64[ns]").astype("int64")


def points(lake: str, column: str, root: Path | None = None
           ) -> tuple[np.ndarray, np.ndarray] | None:
    """(broker-frame availability ns, standardised reading), FIRST vintage per period, oldest
    first. `pace` is z-scored against the series' own strictly earlier readings; `surprise_z`
    is already a z. Both clipped to +-CLIP. None when the series or the column is absent."""
    base = Path(root or SERIES_DIR)
    path = next((base / f"{lake}{s}" for s in (".parquet", ".csv")
                 if (base / f"{lake}{s}").exists()), None)
    if path is None:
        return None
    key = (str(path), path.stat().st_mtime_ns, column)
    if key in _SERIES_CACHE:
        return _SERIES_CACHE[key]
    try:
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception:
        return None
    if df is None or df.empty or column not in df.columns or "available_time" not in df.columns:
        return None
    avail = pd.to_datetime(df["available_time"], errors="coerce", utc=True)
    period = (df["event_time"].astype(str) if "event_time" in df.columns
              else avail.astype(str))
    frame = pd.DataFrame({"period": period, "at": avail,
                          "v": pd.to_numeric(df[column], errors="coerce")})
    frame = frame.dropna(subset=["at"]).sort_values("at", kind="stable")
    frame = frame.drop_duplicates("period", keep="first")
    frame = frame[np.isfinite(frame["v"].to_numpy(dtype="float64"))].reset_index(drop=True)
    if frame.empty:
        return None
    v = frame["v"].to_numpy(dtype="float64")
    if column == "pace":
        prior = pd.Series(v).shift(1)
        mean = prior.expanding(min_periods=PACE_MIN_HISTORY).mean().to_numpy()
        sd = prior.expanding(min_periods=PACE_MIN_HISTORY).std(ddof=1).to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            v = np.where(sd > 0, (v - mean) / sd, np.nan)
    v = np.clip(v, -CLIP, CLIP)
    out = (to_broker_ns(frame["at"]), v)
    if len(_SERIES_CACHE) > 64:
        _SERIES_CACHE.clear()
    _SERIES_CACHE[key] = out
    return out


def asof(pts: tuple[np.ndarray, np.ndarray], stamps: np.ndarray, max_age_d: float) -> np.ndarray:
    """The latest reading visible at each stamp, NaN when none or older than `max_age_d` days."""
    t, v = pts
    j = np.searchsorted(t, stamps, side="right") - 1
    has = j >= 0
    jj = np.where(has, j, 0)
    fresh = has & ((stamps - t[jj]) <= float(max_age_d) * 86_400_000_000_000)
    return np.where(fresh, v[jj], np.nan)


def score_matrix(panel: dict, column: str, max_age_d: float,
                 handoff: Path | None = None, root: Path | None = None) -> np.ndarray:
    """rows x members: each mapped member's mean of prior_sign x reading; NaN for an unmapped
    member or a day with no fresh reading (absent from the rank, never zero)."""
    stamps = panel["stamps"]
    expo = exposures(handoff)
    out = np.full(panel["logv"].shape, np.nan, dtype="float64")
    for j, member in enumerate(panel["members"]):
        legs = expo.get(str(member).upper())
        if not legs:
            continue
        cols = []
        for lake, sign in legs:
            pts = points(lake, column, root)
            if pts is not None:
                cols.append(sign * asof(pts, stamps, max_age_d))
        if not cols:
            continue
        stack = np.vstack(cols)
        n = np.isfinite(stack).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[:, j] = np.where(n > 0, np.nansum(np.where(np.isfinite(stack), stack, 0.0),
                                                  axis=0) / np.maximum(n, 1), np.nan)
    return out


# ---------------------------------------------------------------------------- families ---
def _run(df: pd.DataFrame, symbol: str, column: str, *, max_age_d: float, hold_d: int,
         quantile: float, decision_hour: int, max_stale_h: float, stop_sd: float, rr: float,
         tag: str, handoff: Any, series_root: Any) -> list[Signal]:
    if not xs._valid_common(quantile, hold_d, stop_sd, rr) or float(max_age_d) <= 0:
        return []
    if not symbol or xs.class_of(symbol) != KLASS:
        return []
    hp = Path(handoff) if handoff else None
    if str(symbol).upper() not in exposures(hp):
        return []                       # not a leg of this book: the hand-off maps it nothing
    got = xs._prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    score = score_matrix(panel, column, max_age_d, hp,
                         Path(series_root) if series_root else None)
    side = xs._rank_sides(score, panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr, tag=tag)


def family_alt_exposure_pace_book(
    df: pd.DataFrame, *, symbol: str = "", hold_d: int = 20, quantile: float = 1 / 3,
    max_age_d: float = 45.0, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0, handoff: Any = None, series_root: Any = None,
) -> list[Signal]:
    """Long while `symbol`'s prior-signed, self-standardised alt-data PACE ranks in the top
    `quantile` of the equity names the hand-off maps on that date, short while in the bottom."""
    return _run(df, symbol, "pace", max_age_d=max_age_d, hold_d=hold_d, quantile=quantile,
                decision_hour=decision_hour, max_stale_h=max_stale_h, stop_sd=stop_sd, rr=rr,
                tag="alt_exposure_pace_book", handoff=handoff, series_root=series_root)


def family_alt_exposure_release_book(
    df: pd.DataFrame, *, symbol: str = "", hold_d: int = 5, quantile: float = 1 / 3,
    window_d: float = 5.0, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0, handoff: Any = None, series_root: Any = None,
) -> list[Signal]:
    """Long while `symbol`'s prior-signed latest release SURPRISE (first vintage, within
    `window_d` days) ranks in the top `quantile` of the mapped equity names that day, short
    while in the bottom: the macro release's reaction, measured relative to the peers."""
    return _run(df, symbol, "surprise_z", max_age_d=window_d, hold_d=hold_d, quantile=quantile,
                decision_hour=decision_hour, max_stale_h=max_stale_h, stop_sd=stop_sd, rr=rr,
                tag="alt_exposure_release_book", handoff=handoff, series_root=series_root)


ALT_EXPOSURE_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "alt_exposure_pace_book": family_alt_exposure_pace_book,
    "alt_exposure_release_book": family_alt_exposure_release_book,
}

FAMILY_CLASSES: dict[str, tuple[str, ...]] = dict.fromkeys(ALT_EXPOSURE_FAMILIES, (KLASS,))

#: The organ that enumerates these families' cells. The members that carry a score are the
#: hand-off's evidence, so the generic class-book seeder (which walks every class member) would
#: measure and charge ~100 legs that can never fire; `class_books.families_for` skips them.
SEEDED_BY = "research/alt_equity_handoff.py"

TARGETS: dict[str, dict[str, str]] = {
    "alt_exposure_pace_book": {
        "cluster": "cross_sectional_equity",
        "prior": "a public but unread alt-data demand indicator diffuses slowly into the names it "
                 "bears on, so names whose prior-signed pace is high relative to their peers' "
                 "outperform (attention constraint; the alt_proxies roster's mechanism)"},
    "alt_exposure_release_book": {
        "cluster": "cross_sectional_equity",
        "prior": "a macro alt-data release's surprise is priced late in the names it bears on; "
                 "ranked across the equity class on the release date, the relative reaction is "
                 "the bet, not the market's"},
}

INPUTS: tuple[str, str] = (
    "the equity class's closes as of each decision bar, and each mapped share's alt-data lake "
    "series (first vintage at its available_time on the broker clock) named by the alt_proxies "
    "equity hand-off (research/alt_equity_handoff.py)",
    "data/universe/*_H1.parquet + data/digests/alt_proxies_equity_handoff.json + "
    "data/lake/series/alt_*.csv")
