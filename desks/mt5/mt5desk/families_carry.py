"""THREE FX CARRY BOOKS ON THE BROKER'S OWN SWAP HISTORY, FORWARD ONLY (2026-10-06).

The carry rows the EliteQuant/Roman lists name, built as class books on the panel
`families_cross_sectional` already loads, one leg per cell:

    fx_swap_carry_rank   Lustig & Verdelhan (2007) / Menkhoff et al. (2012) carry sorts: long
        the members of the FX class whose broker swap pays most for the long side, short those
        whose swap charges most. Payer: the low-yield funder and the hedger who pays to hold.
    dollar_carry_basket  Lustig, Roussanov & Verdelhan (2014), "Countercyclical currency risk
        premia": long every foreign currency against the dollar while the class's AVERAGE carry
        against the dollar is positive, long the dollar while it is negative. One timing signal
        for the whole fx_usd class; the cell is its leg in `symbol`.
    good_bad_carry       Bekaert & Panayotov (2020), "Good carry, bad carry": the carry sort
        split by crash risk. `book="good"` ranks carry among the members whose trailing daily
        skew is at or above the class median that day, `book="bad"` among those below it. Both
        books are cells, so the claim (good carry earns the premium without the crash) is tested
        against its own complement, not asserted.

THE INPUT IS THE BROKER'S SWAP AT THE INSTANT THE TERMINAL REPORTED IT, AND NOTHING ELSE. A row
is read only when it carries its own `observed_at` (the honesty marker #244 added): the
`contract_terms` tape `mt5desk.tape --terms-only` writes hourly on the box, and the `swap_table`
rows of the broker_swaps panel written by the same run. Panel rows without `observed_at` were
stamped with the time a git copy of the registry was made, so old swaps read as fresh; they are
counted in `history_status()` and never used. TODAY'S SWAPS ARE NEVER BACKFILLED: a bar before a
row's knowable instant sees no carry at all and emits nothing, so a backtest of these books starts
where the honest history starts and its holdout lies inside it.

KNOWABLE_AT. A row observed at UTC instant u is used on a bar stamped in broker time at or after
u + 3 h. The venue is UTC+3 in summer and UTC+2 in winter, so the +3 h lead is the later of the
two and can only make a row usable later than the terminal knew it, never earlier. A row older
than `max_panel_age_h` at the decision bar is stale and reads as no carry.

UNITS. Carry is the annual financing yield on notional: mode 5 (INTEREST_CURRENT) is already an
annual percent; mode 1 (POINTS) is swap * point per night on a price, so swap * point * 360 /
price; mode 0 is zero; any other mode is unknown and reads NaN. The `swap_mode` and `point` come
from the row itself, then from `data/carry_state.json` (units only; never its values).

ENTERING THE GAUNTLET. `history_status()` counts the distinct UTC dates holding an honest row
and compares them with the gauntlet's lockbox floor (`research.gate_policy.LOCKBOX_MIN_DAYS`,
never lowered here). `research/elitequant_breadth.py` seeds these families only once that count
reaches the floor and reports PENDING_HISTORY with the count until then, so the cells enter on
their own the hour the history is long enough, and charge no trial before.
"""
from __future__ import annotations

import gzip
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk import families_class_moments as cm
from mt5desk import families_cross_sectional as xs
from mt5desk.families import Signal

DATA = Path(__file__).resolve().parents[1] / "data"
TERMS_DIR = DATA / "tape" / "contract_terms"
PANEL_DIR = DATA / "intelligence" / "broker_swaps"
UNITS = DATA / "carry_state.json"

DATA_SOURCE = "mt5:broker_swaps"
DAY_COUNT = 360.0
BROKER_LEAD_NS = 3 * 3_600_000_000_000
FX_CLASSES = ("fx_usd", "fx_cross")
HOUR_NS = 3_600_000_000_000

_CACHE: dict[str, Any] = {"key": None, "hist": None, "stats": None}


def _ns(stamp: Any) -> int | None:
    try:
        t = pd.Timestamp(stamp)
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.value)


def _units() -> dict[str, dict[str, Any]]:
    try:
        sy = json.loads(UNITS.read_text("utf-8")).get("symbols") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for sym, row in sy.items():
        if isinstance(row, dict):
            out[str(sym)] = {"swap_mode": row.get("swap_mode")}
    return out


def _tick_size(sym: str) -> float | None:
    try:
        reg = json.loads((DATA / "universe" / "universe.json").read_text("utf-8"))
        v = float((reg.get(sym) or {}).get("tick_size") or 0.0)
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    return v if v > 0 else None


def _panel_rows(path: Path) -> list[dict[str, Any]]:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]
        rows = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, EOFError):
        return []
    return rows if isinstance(rows, list) else []


def _files() -> list[Path]:
    out: list[Path] = []
    if TERMS_DIR.is_dir():
        out += sorted(TERMS_DIR.glob("*.parquet"))
    if PANEL_DIR.is_dir():
        out += sorted(PANEL_DIR.glob("*.json")) + sorted(PANEL_DIR.glob("*.jsonl.gz"))
    return out


def swap_history() -> tuple[dict[str, dict[str, np.ndarray]], dict[str, Any]]:
    """{symbol: {"t": knowable broker ns, "lo", "sh", "mode", "point"}} and the read's counts.

    Every row carries its own observation instant; rows without one are counted, never used."""
    files = _files()
    key = tuple((str(f), f.stat().st_mtime_ns, f.stat().st_size) for f in files)
    if _CACHE["key"] == key:
        return _CACHE["hist"], _CACHE["stats"]
    units = _units()
    raw: dict[str, dict[int, tuple[float, float, float, float]]] = {}
    stats = {"terms_rows": 0, "panel_rows_honest": 0, "panel_rows_unstamped": 0}

    def add(sym: str, obs: Any, lo: Any, sh: Any, mode: Any, point: Any) -> bool:
        t = _ns(obs)
        if t is None or lo is None or sh is None:
            return False
        if mode is None:
            mode = (units.get(sym) or {}).get("swap_mode")
        try:
            m = float(mode) if mode is not None else math.nan
            p = float(point) if point else (_tick_size(sym) or math.nan)
            raw.setdefault(sym, {})[t + BROKER_LEAD_NS] = (float(lo), float(sh), m, p)
        except (TypeError, ValueError):
            return False
        return True

    for f in files:
        if f.suffix == ".parquet":
            try:
                df = pd.read_parquet(f)
            except (OSError, ValueError):
                continue
            for r in df.to_dict("records"):
                stats["terms_rows"] += add(str(r.get("symbol")), r.get("observed_at"),
                                           r.get("swap_long"), r.get("swap_short"),
                                           r.get("swap_mode"), r.get("point"))
            continue
        for r in _panel_rows(f):
            if not isinstance(r, dict) or r.get("kind") != "swap_table" or not r.get("symbols"):
                continue
            if not r.get("observed_at"):
                stats["panel_rows_unstamped"] += 1
                continue
            stats["panel_rows_honest"] += add(str(r["symbols"][0]), r["observed_at"],
                                              r.get("swap_long"), r.get("swap_short"),
                                              r.get("swap_mode"), r.get("point"))
    hist: dict[str, dict[str, np.ndarray]] = {}
    for sym, rows in raw.items():
        ts = np.array(sorted(rows), dtype="int64")
        vals = np.array([rows[int(t)] for t in ts], dtype="float64")
        hist[sym] = {"t": ts, "lo": vals[:, 0], "sh": vals[:, 1], "mode": vals[:, 2],
                     "point": vals[:, 3]}
    _CACHE.update(key=key, hist=hist, stats=stats)
    return hist, stats


def _yield(swap: np.ndarray, mode: np.ndarray, point: np.ndarray,
           price: np.ndarray) -> np.ndarray:
    """Annual financing yield on notional for one side; NaN where the unit is unknown."""
    out = np.full(swap.shape, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        pts = swap * point * DAY_COUNT / price
    out = np.where(mode == 1, pts, out)
    out = np.where(mode == 5, swap / 100.0, out)
    out = np.where(mode == 0, 0.0, out)
    return np.where(np.isfinite(price) & (price > 0), out, np.nan)


def carry_at(symbol: str, stamps: np.ndarray, price: np.ndarray, orient: int,
             max_age_h: float) -> np.ndarray:
    """Oriented carry (half the long-minus-short yield of the oriented long) at each broker stamp,
    from the newest row knowable at that stamp and no older than `max_age_h`; NaN otherwise."""
    hist, _ = swap_history()
    h = hist.get(symbol)
    out = np.full(stamps.size, np.nan)
    if h is None or stamps.size == 0:
        return out
    j = np.searchsorted(h["t"], stamps, side="right") - 1
    has = j >= 0
    jj = np.where(has, j, 0)
    fresh = has & ((stamps - h["t"][jj]) <= float(max_age_h) * HOUR_NS)
    lo = _yield(h["lo"][jj], h["mode"][jj], h["point"][jj], price)
    sh = _yield(h["sh"][jj], h["mode"][jj], h["point"][jj], price)
    d = 0.5 * (lo - sh) * (1 if orient >= 0 else -1)
    out[fresh] = d[fresh]
    return out


def _carry_panel(d: pd.DataFrame, panel: dict, max_age_h: float) -> np.ndarray:
    """(rows, members) oriented carry on the panel's decision stamps."""
    stamps = d.index.asi8[panel["pos"]]
    cols = []
    for k, sym in enumerate(panel["members"]):
        o = xs.orientation(sym, panel["klass"])
        price = np.exp(panel["logv"][:, k] * o)
        cols.append(carry_at(sym, stamps, price, o, max_age_h))
    return np.column_stack(cols)


def _prepare(df: pd.DataFrame, symbol: str, decision_hour: int, max_stale_h: float,
             classes: tuple[str, ...]) -> tuple[pd.DataFrame, dict] | None:
    if xs.class_of(symbol) not in classes:
        return None
    return xs._prepare(df, symbol, decision_hour, max_stale_h)


def family_fx_swap_carry_rank(
    df: pd.DataFrame, *, symbol: str = "", quantile: float = 1 / 3, hold_d: int = 5,
    max_panel_age_h: float = 48.0, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s oriented carry ranks in the top `quantile` of its FX class, short
    while it ranks in the bottom, on the swap knowable at each decision bar."""
    if not xs._valid_common(quantile, hold_d, stop_sd, rr):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h, FX_CLASSES)
    if got is None:
        return []
    d, panel = got
    side = xs._rank_sides(_carry_panel(d, panel, max_panel_age_h), panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"fx_carry_rank:{panel['klass']}")


def family_dollar_carry_basket(
    df: pd.DataFrame, *, symbol: str = "", min_afd: float = 0.0, hold_d: int = 5,
    max_panel_age_h: float = 48.0, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long the foreign leg of `symbol` against the dollar while the fx_usd class's average carry
    against the dollar exceeds `min_afd` (annual), long the dollar while it is below -min_afd."""
    if not xs._valid_common(0.5, hold_d, stop_sd, rr) or float(min_afd) < 0:
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h, ("fx_usd",))
    if got is None:
        return []
    d, panel = got
    c = _carry_panel(d, panel, max_panel_age_h)
    n = np.isfinite(c).sum(axis=1)
    with np.errstate(invalid="ignore"):
        afd = np.where(n >= xs.MIN_MEMBERS, np.nansum(c, axis=1) / np.maximum(n, 1), np.nan)
    ok = np.isfinite(afd) & np.isfinite(c[:, panel["own"]])
    side = np.zeros(afd.size, dtype="int64")
    side[ok & (afd > float(min_afd))] = 1
    side[ok & (afd < -float(min_afd))] = -1
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag="dollar_carry")


def family_good_bad_carry(
    df: pd.DataFrame, *, symbol: str = "", book: str = "good", skew_window: int = 120,
    quantile: float = 1 / 3, hold_d: int = 5, max_panel_age_h: float = 48.0,
    decision_hour: int = 22, max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """The carry rank restricted to the members whose trailing daily skew (read yesterday) is at
    or above the class median (`book="good"`) or below it (`book="bad"`)."""
    if (not xs._valid_common(quantile, hold_d, stop_sd, rr) or book not in ("good", "bad")
            or int(skew_window) < 20):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h, FX_CLASSES)
    if got is None:
        return []
    d, panel = got
    c = _carry_panel(d, panel, max_panel_age_h)
    r = xs._returns(panel["logv"])
    skew = np.column_stack([cm._column_stats(r[:, k], int(skew_window), 2.0, 0.8)[0]
                            for k in range(r.shape[1])])
    skew = xs._shift(skew, 1)
    with np.errstate(invalid="ignore"):
        valid = np.isfinite(skew) & np.isfinite(c)
        med = np.array([np.median(row[v]) if v.sum() else np.nan
                        for row, v in zip(skew, valid, strict=True)])
        keep = valid & ((skew >= med[:, None]) if book == "good" else (skew < med[:, None]))
    side = xs._rank_sides(np.where(keep, c, np.nan), panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"{book}_carry:{panel['klass']}")


def family_commodity_basis_carry(
    df: pd.DataFrame, *, symbol: str = "", mode: str = "level", quantile: float = 1 / 3,
    q: float = 0.05, hold_d: int = 20, max_panel_age_h: float = 48.0, decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """ROMAN-0842 on the venue's own terms: the swap on a rolling commodity CFD is the broker's
    pass-through of the futures curve, so its long-minus-short yield is the implied basis (roll
    yield). `mode="level"` ranks the class on it (Gorton, Hayashi & Rouwenhorst 2013:
    backwardated contracts earn the premium); `mode="residual"` ranks on the basis minus its
    adaptive fair value, the one-step Kalman prediction from `state_space.local_level` (each
    member's filter reads only its own earlier stamped rows), so the cell mines the basis
    surprise rather than its level."""
    if not xs._valid_common(quantile, hold_d, stop_sd, rr) or mode not in ("level", "residual"):
        return []
    got = _prepare(df, symbol, decision_hour, max_stale_h, ("commodity",))
    if got is None:
        return []
    d, panel = got
    c = _carry_panel(d, panel, max_panel_age_h)
    if mode == "residual":
        from libs.research import state_space as ss
        score = np.full(c.shape, np.nan)
        for k in range(c.shape[1]):
            col = c[:, k]
            ok = np.isfinite(col)
            if ok.sum() < 10:
                continue
            # observation noise from the MAD of the stamped changes, so one repricing jump does
            # not set the filter's scale; a flat history falls back to a tiny positive floor
            dif = np.diff(col[ok])
            mad = float(np.median(np.abs(dif - np.median(dif)))) * 1.4826
            r = mad * mad if mad > 0 else max(float(np.var(dif)), 1e-8)
            pred = ss.local_level(col, float(q) * r, r).pred
            score[:, k] = col - pred
    else:
        score = c
    side = xs._rank_sides(score, panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"basis_carry:{mode}")


CARRY_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "fx_swap_carry_rank": family_fx_swap_carry_rank,
    "dollar_carry_basket": family_dollar_carry_basket,
    "good_bad_carry": family_good_bad_carry,
    "commodity_basis_carry": family_commodity_basis_carry,
}

PARAM_GRID: dict[str, dict[str, list]] = {
    "fx_swap_carry_rank": {"quantile": [0.2, 1 / 3], "hold_d": [5, 20]},
    "dollar_carry_basket": {"min_afd": [0.0, 0.01], "hold_d": [5, 20]},
    "good_bad_carry": {"book": ["good", "bad"], "hold_d": [5, 20]},
    "commodity_basis_carry": {"mode": ["level", "residual"], "hold_d": [5, 20]},
}

CLASS_ONLY: dict[str, frozenset[str]] = {
    "fx_swap_carry_rank": frozenset(FX_CLASSES), "good_bad_carry": frozenset(FX_CLASSES),
    "dollar_carry_basket": frozenset({"fx_usd"}),
    "commodity_basis_carry": frozenset({"commodity"}),
}

#: The index that lists these strategies (FX carry, dollar carry) and the papers they rest on.
ORIGIN: dict[str, str] = dict.fromkeys(
    CARRY_FAMILIES, "github.com/paperswithbacktest/awesome-systematic-trading (no licence; "
                    "rewritten from the papers)")
PAPERS: dict[str, str] = {
    "fx_swap_carry_rank": "Lustig & Verdelhan (2007); Menkhoff, Sarno, Schmeling & Schrimpf (2012)",
    "dollar_carry_basket": "Lustig, Roussanov & Verdelhan (2014)",
    "good_bad_carry": "Bekaert & Panayotov (2020)",
    "commodity_basis_carry": "Gorton, Hayashi & Rouwenhorst (2013); Roman blueprint row 0842",
}

_CARRY = {"source_culture": "academic/en", "participant_structure": "institutional_fx",
          "crowding_prior": "high"}
CULTURE: dict[str, dict[str, str]] = {
    "fx_swap_carry_rank": {**_CARRY, "failure_mode_hypothesis": (
        "fails in a funding-currency squeeze: carry unwinds together, so the long high-yielders "
        "and the short funders lose on the same day")},
    "dollar_carry_basket": {**_CARRY, "failure_mode_hypothesis": (
        "fails when the dollar rallies on a global shock while foreign rates still sit above "
        "the US, the countercyclical premium paid in the wrong state")},
    "good_bad_carry": {**_CARRY, "failure_mode_hypothesis": (
        "fails if trailing skew does not forecast the next crash, so the good and bad books "
        "carry the same crash risk and the split earns nothing")},
    "commodity_basis_carry": {**_CARRY, "participant_structure": "institutional_futures",
                              "crowding_prior": "medium", "failure_mode_hypothesis": (
        "fails when the broker's swap is a flat financing charge rather than a pass-through of "
        "the curve, so the 'basis' is the broker's markup and ranks nothing")},
}


def history_status(floor_days: int | None = None,
                   classes: tuple[str, ...] = FX_CLASSES) -> dict[str, Any]:
    """Whether the honest swap history has reached the lockbox floor, with the count.

    The floor is the gauntlet's own; an unreadable floor is UNMEASURED and seeds nothing."""
    if floor_days is None:
        try:
            from research.gate_policy import LOCKBOX_MIN_DAYS
            floor_days = int(LOCKBOX_MIN_DAYS)
        except Exception as exc:                     # pragma: no cover - import guard
            return {"status": "UNMEASURED", "ready": False,
                    "why": f"lockbox floor unreadable: {type(exc).__name__}"}
    hist, stats = swap_history()
    fx = {s: h for s, h in hist.items() if xs.class_of(s) in classes}
    days = sorted({datetime.fromtimestamp((int(t) - BROKER_LEAD_NS) / 1e9, UTC).date().isoformat()
                   for h in fx.values() for t in h["t"]})
    ready = len(days) >= int(floor_days)
    return {"status": "READY" if ready else "PENDING_HISTORY", "ready": ready,
            "honest_days": len(days), "floor_days": int(floor_days),
            "first_day": days[0] if days else None, "last_day": days[-1] if days else None,
            "symbols": len(fx), "classes": list(classes), "data_source": DATA_SOURCE, **stats,
            "why": ("the cells enter the gauntlet when the honest history reaches the lockbox "
                    "floor; nothing before a row's knowable instant is ever filled")}


def _commodity_status() -> dict[str, Any]:
    return history_status(classes=("commodity",))


#: Each family's history gate, read by the seeder before it plans a pass.
GATES: dict[str, Callable[[], dict[str, Any]]] = {
    **dict.fromkeys(("fx_swap_carry_rank", "dollar_carry_basket", "good_bad_carry"),
                    history_status),
    "commodity_basis_carry": _commodity_status,
}
