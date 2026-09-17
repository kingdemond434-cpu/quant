"""Q10 -- THE SEARCH SPACE IS ITSELF A HYPOTHESIS, and this is the organ that tests it.

THE PRINCIPAL, 2026-09-16: the machine must search OVER the search space, not only within it.

`axis_registry` holds ten axes and every cell the desk has judged is a point on that grid. The
grid was drawn BY HAND, which has one failure mode nothing else here can see: a direction missing
from the LEGEND is not reported as unexplored ground, it is not reported at all. L1.51 wants
per-axis evidence before anyone says "exhausted"; the honest reading is that the AXIS LIST is a
claim the desk never tested. Balance-sheet constraint, liquidity-provider inventory state,
information diffusion speed -- if one of those is what sorts the desk's unexplained P&L, ten
perfectly measured axes will keep saying the ground is covered while the residual sits there.

SO AN AXIS IS PROPOSED THE WAY A HYPOTHESIS IS. A candidate is a RULE that buckets
instrument-days. It is tested against the one thing the existing axes already failed to account
for -- the daily residual after the dollar/gold/equity factors, which is what standing question Q3
regresses -- and tested OUT OF SAMPLE against a block permutation of the bucket LABELS. Four rules
make that a measurement rather than a feature mine:

  LAGGED BY CONSTRUCTION. Every label is knowable at the PREVIOUS close (the calendar one years
  ahead; the exogenous ones at their own knowable_at). A signed same-day function of the target's
  own return is refused by name: it would "explain" the residual by BEING it, and an axis nobody
  can know before the day starts cannot tag a cell in advance, which is all an axis is for.

  FITTED ON THE FIRST HALF, SCORED ON THE SECOND -- the tercile cuts too, because they are part of
  the definition and a cut taken over the whole sample is lookahead wearing a bucket's clothes.

  THE NULL PERMUTES LABELS IN BLOCKS. An i.i.d. shuffle of an autocorrelated label sequence gives
  a null far too tight and every regime-shaped candidate then looks significant.

  REDUNDANCY IS REFUSED, NOT RANKED. Of the ten registered axes exactly two vary across
  instrument-DAYS -- `session` and `regime`; the other eight describe the CELL, so a day-level rule
  cannot be a relabelling of them. Cramer's V > 0.90 against either is REDUNDANT however well the
  candidate scored: a new name for an axis the desk has spends multiplicity budget and buys nothing.

REGISTRATION TAKES TWO CONSECUTIVE RUNS. `data/axis_proposals.jsonl` is the append-only evidence
ledger; a candidate that PASSES here and PASSED on its previous row is written to
`data/axis_registry_extensions.json`, which `axis_registry` may read as EXTRA TAGS. THIS ORGAN
NEVER EDITS `axis_registry`: the contract is a file plus two functions (`extension_axes`,
`axis_tag`), so the registry gains a coordinate without this organ gaining a write on it. A
registered axis is never silently removed -- a later FAIL lands as `last_verdict` and retiring one
is the principal's act. UNMEASURED IS A VERDICT (L1.28a): an absent, too-short or one-bucket
series is UNMEASURED with its reason, never FAIL, which would claim the desk looked.

    python desks/mt5/research/axis_proposer.py [--dry-run] [--symbols 20] [--budget-s 240]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = DESK / "data" / "universe"
AXES_DIR = DESK / "data" / "axes"
FORCED_FLOW = DESK / "data" / "forced_flow_calendar.json"
SLEEVES = DESK / "data" / "sleeves.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
STANDING = DESK / "reports" / "STANDING_QUESTIONS.json"
REPRESENTATION = DESK / "reports" / "REPRESENTATION_DISCOVERY.json"
RESIDUAL_REPORT = DESK / "reports" / "RESIDUAL_QUEUE.json"
RESIDUAL_LEDGER = DESK / "data" / "residual_queue.jsonl"
OUT_REPORT = DESK / "reports" / "AXIS_PROPOSER.json"
PROPOSALS = DESK / "data" / "axis_proposals.jsonl"
EXTENSIONS = DESK / "data" / "axis_registry_extensions.json"

#: The factor set the residual is taken AFTER -- imported wherever the standing questions can be
#: reached, because two definitions of one dollar basket is how two organs come to disagree about
#: the same residual. The literals below only keep this organ standalone.
USD_BASKET: dict[str, int] = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1,
                              "USDJPY": 1, "USDCAD": 1, "USDCHF": 1}
GOLD = "XAUUSD"
EQUITY_PROXIES: tuple[str, ...] = ("US500", "SPX500", "USTEC", "NAS100", "US30", "GER40", "DE40")
with contextlib.suppress(Exception):    # indented: a guarded import, not a second definition
    from research.standing_questions import EQUITY_PROXIES, GOLD, USD_BASKET

DEFAULT_SYMBOLS, DEFAULT_BUDGET_S = 20, 240
MIN_DAYS = 160              # aligned days before a candidate is testable at all
MIN_LIVE_DAYS = 60          # the floor the standing questions use for one correlation
MIN_PER_BUCKET = 15         # per bucket, in BOTH halves, before the bucket counts as observed
NULL_DRAWS, NULL_BLOCK = 200, 5
P_MAX, MIN_INSTRUMENTS, REDUNDANT_AT = 0.05, 3, 0.90
MAX_HARVEST = 4             # per source; trial count is a shared cost on this desk
AXIS_MAX_BYTES = 32_000_000  # bis.json is 81 MB and the box holding the live terminal has 8 GB
SEED = 20260917

VERDICTS = ("PASS", "FAIL", "REDUNDANT", "UNMEASURED")
RULE = ("the search space itself evolves; an axis enters only after it explains unexplained "
        "residual out of sample twice")
CONTRACT = (
    "axis_registry may read data/axis_registry_extensions.json WITHOUT importing this organ: "
    "`axes` is a list of EXTRA tag definitions, each {axis_id, name, definition, registered_at, "
    "evidence}. To tag a cell, append axis_id to the ten axes of `axis_cell` and take the value "
    "from axis_proposer.axis_tag(axis_id, symbol) -- the modal bucket over the instrument's own "
    "days, or UNMEASURED when the defining series is absent. An extension is an EXTRA coordinate: "
    "it never changes an existing axis, a cell_id or a proposal, and a cell with no value on it "
    "is UNMEASURED, which is a state rather than a blank."
)
#: Ontology observables that have a measurement ON THIS DESK. The rest are crypto-exchange-native
#: (funding, liquidations, book depth, cross-venue) and are recorded as unmeasurable here rather
#: than hunted -- the MT5 mandate is enforced at the door, not apologised for downstream.
OBSERVABLE_DAILY = ("spread", "volume", "dispersion", "activity", "range", "open_interest")
REFUSED = {"return": "a signed same-day function of the target's own return IS the residual"}

_BARS: dict[str, pd.DataFrame | None] = {}
_CACHE: dict[str, Any] = {}


# --------------------------------------------------------------------------------- plumbing
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    """Tolerant: a BOM, a missing file, a half-written one and one over the memory budget are all
    'that source produced nothing', and the caller names which."""
    try:
        return None if path.stat().st_size > AXIS_MAX_BYTES else json.loads(
            path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _read_rows(path: Path, limit: int = 200_000) -> list[dict]:
    try:
        lines = path.read_text("utf-8-sig", "replace").splitlines()[:limit]
    except OSError:
        return []
    out: list[dict] = []
    for line in lines:
        with contextlib.suppress(ValueError):
            row = json.loads(line) if line.strip() else None
            if isinstance(row, dict):
                out.append(row)
    return out


def _logret(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce").astype("float64").to_numpy()
    with np.errstate(all="ignore"):
        r = np.log(v[1:] / v[:-1])
    return pd.Series(np.where(np.isfinite(r), r, np.nan), index=s.index[1:])


def _bars(symbol: str) -> pd.DataFrame | None:
    """The instrument's H1 bars, or None. Cached per run; `build()` clears the cache."""
    if symbol not in _BARS:
        out = None
        try:
            df = pd.read_parquet(UNIVERSE / f"{symbol}_H1.parquet")
            df.columns = [str(c).lower() for c in df.columns]
            if isinstance(df.index, pd.DatetimeIndex) and "close" in df and len(df) >= MIN_DAYS:
                out = df[~df.index.duplicated(keep="last")].sort_index()
        except Exception:
            out = None
        _BARS[symbol] = out
    return _BARS[symbol]


def _lane_ok(symbol: str) -> bool:
    """FAILS CLOSED: an unreadable registry hunts nothing, because absence is not permission."""
    try:
        from research.universe_policy import may_hypothesise
        return bool(may_hypothesise(symbol))
    except Exception:                                                   # pragma: no cover
        return False


def select_symbols(n: int) -> list[str]:
    """The instruments this pass asks about: the book's own first, then the hypothesis lane."""
    have = sorted({p.name.rsplit("_", 1)[0] for p in UNIVERSE.glob("*_H1.parquet")})
    doc = _read_json(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    book = [s for s in dict.fromkeys(str((r or {}).get("symbol") or "")
                                     for r in (rows if isinstance(rows, list) else []))
            if s in have]
    ranked = [s for s in book if _lane_ok(s)]
    ranked += [s for s in have if s not in ranked and _lane_ok(s)]
    return ranked[:max(int(n), 1)]


# --------------------------------------------------------------- the unexplained residual
def _daily(symbol: str) -> pd.Series | None:
    df = _bars(symbol)
    if df is None:
        return None
    with np.errstate(all="ignore"):
        out = np.log(df["close"].resample("1D").last().dropna()).diff().dropna()
    return out if len(out) >= MIN_DAYS else None


def residual_frame(symbols: list[str]) -> tuple[pd.DataFrame | None, list[str], str]:
    """(daily returns aligned on the factor days, the factor columns, why-not).

    A MINIMAL Q3: dollar basket, gold, an equity index, on daily log returns. No latent factor --
    Q3 fits one and publishes it, and a second differently-fitted pc1 here would mean the two
    artifacts disagree about what "unexplained" means for the same day.
    """
    daily = {s: v for s in dict.fromkeys([*symbols, GOLD, *USD_BASKET, *EQUITY_PROXIES])
             if (v := _daily(s)) is not None}
    members = [s for s in USD_BASKET if s in daily]
    if len(members) < 3:
        return None, [], (f"the dollar basket needs 3 of {sorted(USD_BASKET)}; {len(members)} "
                          f"carry {MIN_DAYS} daily closes")
    if GOLD not in daily:
        return None, [], f"the factor set needs {GOLD}; it has no {MIN_DAYS}-day history"
    frame = pd.DataFrame(daily)
    frame["_usd"] = pd.concat([frame[s] * USD_BASKET[s] for s in members], axis=1).mean(axis=1)
    equity = next((s for s in EQUITY_PROXIES if s in daily), None)
    cols = ["_usd", GOLD] + ([equity] if equity else [])
    frame = frame.dropna(subset=cols)
    if len(frame) < MIN_DAYS:
        return None, [], f"{len(frame)} aligned daily rows across the factors; {MIN_DAYS} needed"
    return frame, cols, ""


def residual_of(frame: pd.DataFrame, cols: list[str], symbol: str) -> pd.Series | None:
    """The symbol's daily return after the factors, cached per run. The factor that IS the symbol
    is DROPPED: regressing gold on gold leaves a residual of zero and an axis with nothing to
    explain."""
    key = f"resid:{symbol}"
    if key not in _CACHE:
        _CACHE[key] = None
        if symbol in frame.columns:
            use = [c for c in cols if c != symbol]
            y = frame[symbol].to_numpy(dtype="float64")
            ok = np.isfinite(y)
            for c in use:
                ok &= np.isfinite(frame[c].to_numpy(dtype="float64"))
            if int(ok.sum()) >= MIN_DAYS:
                x = np.column_stack([np.ones(int(ok.sum()))]
                                    + [frame[c].to_numpy(dtype="float64")[ok] for c in use])
                beta, *_ = np.linalg.lstsq(x, y[ok], rcond=None)
                _CACHE[key] = pd.Series(y[ok] - x @ beta, index=frame.index[ok])
    return _CACHE[key]


# ------------------------------------------------------------------------- exogenous axes
def axis_series() -> dict[str, pd.Series]:
    """Every exogenous axis as a daily series keyed `<axis>:<name>`, at its KNOWABLE date.

    Two publisher shapes, as `standing_questions` found them: fred/ecb carry
    `series[id].points [{d, v}]`; cot/bis carry flat `rows` stamped `knowable_at`, the only date a
    joiner may use. A file over the memory budget is skipped BY NAME.
    """
    if "axes" in _CACHE:
        return _CACHE["axes"]
    out: dict[str, pd.Series] = {}
    skipped: dict[str, str] = {}
    for path in (sorted(AXES_DIR.glob("*.json")) if AXES_DIR.exists() else []):
        axis, doc = path.stem, _read_json(path)
        if not isinstance(doc, dict):
            skipped[axis] = "absent, unreadable, or over the memory budget"
            continue
        for sid, spec in (doc.get("series") or {}).items():
            s = pd.Series(pd.to_numeric([p.get("v") for p in (spec or {}).get("points") or []],
                                        errors="coerce"),
                          index=pd.to_datetime([p.get("d") for p in (spec or {}).get("points")
                                                or []], errors="coerce", utc=True)).dropna()
            if len(s) >= MIN_LIVE_DAYS:
                out[f"{axis}:{sid}"] = s[~s.index.duplicated(keep="last")].sort_index()
        rows = doc.get("rows") or []
        frame = pd.DataFrame(rows) if isinstance(rows, list) and rows else pd.DataFrame()
        fields = [c for c in ("net_pct_oi", "comm_pct_oi", "open_interest", "carry_differential")
                  if c in frame.columns]
        if fields and {"knowable_at", "symbol"} <= set(frame.columns):
            frame["_d"] = pd.to_datetime(frame["knowable_at"], errors="coerce", utc=True)
            for sym, grp in frame.dropna(subset=["_d"]).groupby("symbol"):
                for field in fields:
                    s = pd.to_numeric(grp.set_index("_d")[field], errors="coerce").dropna()
                    s = s[~s.index.duplicated(keep="last")].sort_index()
                    if len(s) >= MIN_LIVE_DAYS // 2:
                        out[f"{axis}:{sym}.{field}"] = s
        del doc
    _CACHE["axes"], _CACHE["axes_skipped"] = out, skipped
    return out


def _asof(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Carried forward from its own knowable date onto the trading days -- never interpolated
    backwards. A value the desk could not have held on the day is not a bucket."""
    return series.reindex(series.index.union(index)).ffill().reindex(index)


# ------------------------------------------------------------------------------ labellers
def _own_observable(symbol: str, defn: dict, index: pd.DatetimeIndex) -> tuple[Any, str]:
    """A daily statistic of the instrument's own bars, LAGGED one day, so the label is a state the
    day opens in rather than a description of how it went."""
    df = _bars(symbol)
    if df is None:
        return None, f"no H1 bars for {symbol}"
    name = str(defn.get("observable"))
    day, ret = df.index.normalize(), _logret(df["close"])
    vol = df["tick_volume"].astype(float) if "tick_volume" in df.columns else None
    spr = df["spread"].astype(float) if "spread" in df.columns else None
    wide = spr is not None and float(pd.to_numeric(spr, errors="coerce").std() or 0.0) > 0.0
    if name == "spread_over_activity":
        if vol is None:
            return None, f"{symbol} publishes no tick volume to price flow against"
        flow = vol.groupby(day).mean().replace(0, np.nan)
        s = (spr.groupby(day).mean() / flow) if wide else (1.0 / flow)
    elif name in ("spread", "volume", "activity"):
        if name == "spread" and not wide:
            return None, f"{symbol}'s spread column is constant; it buckets nothing"
        if name != "spread" and vol is None:
            return None, f"{symbol} publishes no tick volume"
        s = (spr if name == "spread" else vol).groupby(day).mean()
        if name == "activity":
            s = s / s.rolling(20, min_periods=5).mean()
    elif name == "dispersion":
        s = ret.groupby(ret.index.normalize()).std()
    elif name == "range":
        s = ((df["high"].astype(float) - df["low"].astype(float))
             / df["close"].astype(float)).groupby(day).mean()
    else:
        return None, REFUSED.get(name, f"{name!r} has no measurement on this desk")
    return s.dropna().shift(1).reindex(index), ""


def _cot_percentile(symbol: str, defn: dict, index: pd.DatetimeIndex) -> tuple[Any, str]:
    """The reporting speculator's position as a share of open interest, at its knowable date."""
    key = f"cot:{symbol}.{defn.get('field', 'net_pct_oi')}"
    series = axis_series().get(key)
    if series is None:
        return None, f"no {key} under data/axes -- the CFTC does not report {symbol}"
    return _asof(series, index), ""


def _exogenous(symbol: str, defn: dict, index: pd.DatetimeIndex) -> tuple[Any, str]:
    """A named exogenous series as its FIRST DIFFERENCE. Bucketing on a LEVEL manufactures
    structure out of two trends, and has done so on this desk before."""
    key = str(defn.get("series"))
    series = axis_series().get(key)
    if series is None:
        return None, f"{key} is not published under data/axes on this box"
    return _asof(series, index).diff(), ""


def _diffusion_speed(symbol: str, defn: dict, index: pd.DatetimeIndex) -> tuple[Any, str]:
    """How fast this instrument LAST diffused information: on the forced-flow calendar's own event
    days, the share of the day left when the intraday path first reached `converged_at` of its
    close-to-close move. Carried forward from the last such event, so it is an instrument STATE
    the day opens in and never an outcome of it."""
    df = _bars(symbol)
    if df is None:
        return None, f"no H1 bars for {symbol}"
    if "forced_flow" not in _CACHE:
        cal: dict[str, set[str]] = {}
        for ev in (_read_json(FORCED_FLOW) or {}).get("events") or []:
            for sym in (ev.get("instruments") or []):
                cal.setdefault(str(sym), set()).add(str(ev.get("date") or "")[:10])
        _CACHE["forced_flow"] = cal
    days = _CACHE["forced_flow"].get(symbol) or set()
    if not days:
        return None, f"the forced-flow calendar names no event for {symbol}"
    ret = _logret(df["close"]).dropna()
    target = float(defn.get("converged_at", 0.8))
    speeds: dict[Any, float] = {}
    for stamp, grp in ret.groupby(ret.index.normalize()):
        if str(pd.Timestamp(stamp).date()) not in days or len(grp) < 4:
            continue
        cum = grp.to_numpy().cumsum()
        if abs(float(cum[-1])) <= 0.0:
            continue
        reached = np.flatnonzero(cum / float(cum[-1]) >= target)
        k = int(reached[0]) if reached.size else len(cum) - 1
        speeds[stamp] = 1.0 - k / max(len(cum) - 1, 1)
    if len(speeds) < MIN_LIVE_DAYS // 2:
        return None, f"{len(speeds)} forced-flow event days measurable on {symbol}"
    return _asof(pd.Series(speeds).sort_index().shift(1), index), ""


def _calendar_proximity(symbol: str, defn: dict, index: pd.DatetimeIndex) -> tuple[Any, str]:
    """Month- and quarter-end proximity, counted in the instrument's OWN trading days so no
    business-day calendar has to be guessed. Knowable years ahead, which is the point."""
    if len(index) < MIN_DAYS:
        return None, f"{len(index)} days is under the {MIN_DAYS}-day floor"
    # month as year*12+month rather than a Period: `to_period` drops the tz and warns, and this
    # desk runs with `filterwarnings = error`.
    month = np.asarray(index.month)
    ym = pd.Series(np.asarray(index.year) * 12 + month, index=index)
    left = ym.groupby(ym).cumcount(ascending=False).to_numpy()
    quarter = np.isin(month, (3, 6, 9, 12))
    out = np.where(left < int(defn.get("within_days", 2)),
                   np.where(quarter, "quarter_end", "month_end"), "mid_month")
    return pd.Series(out, index=index, dtype=object), ""


LABELLERS = {"own_observable": _own_observable, "cot_percentile": _cot_percentile,
             "exogenous": _exogenous, "diffusion_speed": _diffusion_speed,
             "calendar_proximity": _calendar_proximity}

#: THE DECLARED LIBRARY. Four axes no cell on this tree can currently be placed on, each with a
#: PAYER behind it: a dealer carrying inventory, a speculator at a positioning extreme, a market
#: that reprices slowly, a balance sheet that must be flat on a date.
DECLARED: list[dict[str, Any]] = [
    {"axis_id": "liquidity_state", "name": "liquidity-provider inventory state",
     "source": "declared", "definition": {
         "kind": "own_observable", "observable": "spread_over_activity", "lag_days": 1,
         "buckets": ["deep", "mid", "thin"],
         "why": "cost per unit of flow -- what a dealer charges to warehouse the next unit, which "
                "is what an inventory state looks like from outside"}},
    {"axis_id": "positioning_extreme", "name": "speculative positioning extreme",
     "source": "declared", "definition": {
         "kind": "cot_percentile", "field": "net_pct_oi", "cuts": [0.2, 0.8],
         "buckets": ["short_extreme", "neutral", "long_extreme"],
         "why": "a crowded speculator is a forced future seller of his own position"}},
    {"axis_id": "information_diffusion_speed", "name": "information diffusion speed",
     "source": "declared", "definition": {
         "kind": "diffusion_speed", "converged_at": 0.8, "lag_days": 1,
         "buckets": ["slow", "mid", "fast"],
         "why": "how long this instrument took to finish repricing at its last dated, forced, "
                "publicly calendared flow"}},
    {"axis_id": "balance_sheet_constraint", "name": "balance-sheet constraint proximity",
     "source": "declared", "definition": {
         "kind": "calendar_proximity", "within_days": 2,
         "buckets": ["quarter_end", "month_end", "mid_month"],
         "why": "a balance sheet that must be reported flat on a date is a forced participant on "
                "a calendar everyone can read"}},
]


# ------------------------------------------------------------------------------- harvesting
def _push(out: list[dict[str, Any]], axis_id: str, name: str, source: str,
          defn: dict[str, Any], cap: int) -> bool:
    """Add a harvested candidate unless it is a duplicate or the source's budget is spent."""
    if any(c["axis_id"] == axis_id for c in out) or sum(
            1 for c in out if c["source"] == source) >= cap:
        return False
    out.append({"axis_id": axis_id, "name": name, "source": source, "definition": defn})
    return True


def harvest(note: dict[str, str]) -> list[dict[str, Any]]:
    """Candidates the desk's own artifacts already point at. SELECTED ON IN-SAMPLE EVIDENCE, which
    is why they are tested here rather than believed: Q3's correlate was chosen because it
    correlated, so its only honest next test is out of sample against a permutation null."""
    out: list[dict[str, Any]] = []
    q3 = (((_read_json(STANDING) or {}).get("questions") or {}).get("Q3") or {}).get("findings")
    for row in q3 or []:
        key = str((row or {}).get("axis") or "")
        if key and float((row or {}).get("p_bonf", 1.0)) <= P_MAX:
            _push(out, f"q3_correlate::{key}", f"residual correlate {key}",
                  "STANDING_QUESTIONS.json Q3",
                  {"kind": "exogenous", "series": key, "buckets": ["falling", "flat", "rising"],
                   "why": f"Q3 measured {row.get('symbol')}'s residual against {key} at "
                          f"r={row.get('corr')}"}, MAX_HARVEST)
    if not q3:
        note["STANDING_QUESTIONS.json"] = "absent, or Q3 carries no significant residual correlate"

    rep = _read_json(REPRESENTATION) or {}
    winners = (rep.get("directional") or []) + (rep.get("beat_own_null") or [])
    for row in winners:
        name = str((row or {}).get("name") or "")
        obs = {"activity": "activity", "flow": "activity", "range": "range", "spread": "spread",
               "vol24": "dispersion", "vol120": "dispersion"}.get(name)
        if obs is None:
            note.setdefault("REPRESENTATION_DISCOVERY.json",
                            f"{name!r} is a learned composite this organ cannot rebuild from bars "
                            "-- the report publishes its score, not its expression")
            continue
        _push(out, f"learned::{obs}", f"learned representation {obs}",
              "REPRESENTATION_DISCOVERY.json",
              {"kind": "own_observable", "observable": obs, "lag_days": 1,
               "buckets": ["low", "mid", "high"],
               "why": f"{name} beat its own permutation null on forward returns"}, MAX_HARVEST)
    if not winners:
        note.setdefault("REPRESENTATION_DISCOVERY.json",
                        "absent -- no learned representation has been scored on this box")

    try:
        from libs.research.mechanism_ontology import CORE_MECHANISMS
        observables = sorted({o for m in CORE_MECHANISMS.values() for o in m.observables})
    except Exception:                                                   # pragma: no cover
        observables, note["mechanism_ontology"] = [], "unimportable"
    off_desk = [o for o in observables if o not in OBSERVABLE_DAILY and o not in REFUSED]
    for obs in observables:
        if obs in REFUSED:
            note[f"observable:{obs}"] = REFUSED[obs]
        elif obs in OBSERVABLE_DAILY:
            kind = "cot_percentile" if obs == "open_interest" else "own_observable"
            defn = {"kind": kind, "buckets": ["low", "mid", "high"], "lag_days": 1,
                    "why": f"{obs} is a declared observable of a mechanism in the ontology"}
            defn["field" if kind == "cot_percentile" else "observable"] = obs
            _push(out, f"mechanism::{obs}", f"mechanism observable {obs}",
                  "libs/research/mechanism_ontology.py", defn, MAX_HARVEST)
    if off_desk:
        note["mechanism_observables_off_desk"] = (
            f"{', '.join(off_desk)}: crypto-exchange-native observables with no MT5 measurement "
            "-- recorded as unmeasurable here rather than hunted")
    return out


def candidates(note: dict[str, str]) -> list[dict[str, Any]]:
    """The declared library plus what the artifacts point at, deduplicated by axis_id."""
    out: list[dict[str, Any]] = []
    for cand in [*DECLARED, *harvest(note)]:
        if not any(c["axis_id"] == cand["axis_id"] for c in out):
            out.append(cand)
    return out


# ------------------------------------------------------------------------- bucketing + test
def _bucketise(values: pd.Series, names: list[str], cuts: list[float] | None,
               n_train: int) -> pd.Series:
    """Quantile cuts fitted on the FIRST `n_train` rows and applied to all of them."""
    q = np.asarray(cuts if cuts else np.linspace(0.0, 1.0, len(names) + 1)[1:-1], dtype=float)
    train = values.to_numpy(dtype="float64")[:n_train]
    edges = np.unique(np.quantile(train, q)) if train.size else np.asarray([])
    idx = np.clip(np.searchsorted(edges, values.to_numpy(dtype="float64"), side="right"),
                  0, len(names) - 1)
    return pd.Series([names[int(i)] for i in idx], index=values.index, dtype=object)


def bucket_labels(cand: dict[str, Any], symbol: str, index: pd.DatetimeIndex,
                  min_days: int = MIN_DAYS) -> tuple[pd.Series | None, str]:
    """One candidate's label per instrument-day, or None and the reason there is none. The live
    lane passes a SHORTER floor: a live-loss residual is a young series by nature, and holding it
    to the tape's floor would retire the gate rather than measure it."""
    defn = cand.get("definition") or {}
    fn = LABELLERS.get(str(defn.get("kind")))
    if fn is None:
        return None, f"no labeller for definition kind {defn.get('kind')!r}"
    try:
        series, why = fn(symbol, defn, index)
    except Exception as exc:                                            # pragma: no cover
        return None, f"labeller raised {type(exc).__name__}"
    if series is None:
        return None, why
    series = pd.Series(series).reindex(index).dropna()
    if len(series) < min_days:
        return None, f"{len(series)} labelled days; {min_days} needed"
    if series.dtype == object:
        return series.astype(str), ""
    names = list(defn.get("buckets") or ["low", "mid", "high"])
    return _bucketise(series, names, defn.get("cuts"), len(series) // 2), ""


def _oos_share(y: np.ndarray, codes: np.ndarray, k: int, n_tr: int) -> float:
    """Bucket means fitted on the first half, explained share scored on the second. Negative is a
    real answer: a bucket predicting worse than the test mean has explained nothing."""
    ctr, cte, ytr, yte = codes[:n_tr], codes[n_tr:], y[:n_tr], y[n_tr:]
    cnt = np.bincount(ctr, minlength=k).astype(float)
    mu = np.where(cnt > 0, np.bincount(ctr, weights=ytr, minlength=k) / np.where(cnt > 0, cnt, 1.0),
                  float(ytr.mean()))
    ss_tot = float(((yte - yte.mean()) ** 2).sum())
    return float("nan") if ss_tot <= 0.0 else float(
        1.0 - ((yte - mu[cte]) ** 2).sum() / ss_tot)


def _block_permute(codes: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    n = len(codes)
    nb = int(np.ceil(n / block))
    pad = nb * block - n
    padded = np.concatenate([codes, codes[:pad]]) if pad else codes
    return padded.reshape(nb, block)[rng.permutation(nb)].reshape(-1)[:n]


def test_labels(resid: pd.Series, labels: pd.Series | None, rng: np.random.Generator,
                min_days: int = MIN_DAYS) -> dict[str, Any]:
    """The OOS explained share and its block-permutation p, or UNMEASURED with the reason."""
    if labels is None:
        return {"status": "UNMEASURED", "why": "no labels"}
    pair = pd.DataFrame({"y": resid, "b": labels}).dropna()
    if len(pair) < min_days:
        return {"status": "UNMEASURED", "why": f"{len(pair)} aligned days; {min_days} needed"}
    codes, names = pd.factorize(pair["b"].astype(str))
    k, n_tr = len(names), len(pair) // 2
    seen = ((np.bincount(codes[:n_tr], minlength=k) >= MIN_PER_BUCKET)
            & (np.bincount(codes[n_tr:], minlength=k) >= MIN_PER_BUCKET))
    if int(seen.sum()) < 2:
        return {"status": "UNMEASURED",
                "why": f"{int(seen.sum())} of {k} buckets carry {MIN_PER_BUCKET} days in BOTH "
                       "halves; a one-bucket axis buckets nothing"}
    y = pair["y"].to_numpy(dtype="float64")
    obs = _oos_share(y, codes, k, n_tr)
    if not np.isfinite(obs):
        return {"status": "UNMEASURED", "why": "the test half's residual has no variance"}
    ge = sum(int(np.isfinite(v) and v >= obs) for v in
             (_oos_share(y, _block_permute(codes, NULL_BLOCK, rng), k, n_tr)
              for _ in range(NULL_DRAWS)))
    return {"status": "OK", "oos_share": round(obs, 6),
            "p_perm": round((1.0 + ge) / (NULL_DRAWS + 1.0), 6), "n": len(pair), "n_train": n_tr,
            "buckets": int(seen.sum()), "bucket_names": [str(x) for x in names]}


# ------------------------------------------------------------------------------- redundancy
def cramers_v(a: pd.Series, b: pd.Series) -> float:
    """Association between two label vectors in [0,1] -- the categorical reading of "correlation
    of bucket labels" the redundancy rule asks for."""
    tab = pd.crosstab(a.astype(str), b.astype(str)).to_numpy(dtype="float64")
    n = float(tab.sum())
    if min(tab.shape) < 2 or n <= 0.0:
        return 0.0
    exp = np.outer(tab.sum(axis=1), tab.sum(axis=0)) / n
    chi2 = float((((tab - exp) ** 2) / np.where(exp > 0, exp, 1.0)).sum())
    return float(np.sqrt(max(chi2 / n, 0.0) / (min(tab.shape) - 1)))


def reference_labels(symbol: str, index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """Every axis that already EXISTS and varies across instrument-days: `session` (which session
    carried the day's largest move), `regime` (terciles of trailing realised vol, lagged) and
    every axis a previous run REGISTERED. The other eight registered axes describe the CELL, so a
    day-level rule cannot be a relabelling of them."""
    key = f"ref:{symbol}"
    if key in _CACHE:
        return _CACHE[key]
    out: dict[str, pd.Series] = {}
    df = _bars(symbol)
    ret = _logret(df["close"]).dropna() if df is not None else pd.Series(dtype="float64")
    if not ret.empty:
        peak = ret.abs().groupby(ret.index.normalize()).idxmax().dropna()
        hours = pd.DatetimeIndex(peak.to_numpy()).hour
        out["session"] = pd.Series(np.select([hours < 8, hours < 14, hours < 22],
                                             ["asia", "london", "ny"], default="late"),
                                   index=peak.index, dtype=object).reindex(index).dropna()
        vol = ret.groupby(ret.index.normalize()).std().rolling(20, min_periods=5).mean()
        vol = vol.shift(1).reindex(index).dropna()
        if len(vol) >= MIN_DAYS:
            out["regime"] = _bucketise(vol, ["low_vol", "mid_vol", "high_vol"], None, len(vol) // 2)
    for ext in extension_axes():
        labels, _ = bucket_labels(ext, symbol, index)
        if labels is not None:
            out[str(ext["axis_id"])] = labels
    _CACHE[key] = out
    return out


def resemblance(labels: pd.Series, refs: dict[str, pd.Series]) -> tuple[float, str]:
    """(Cramer's V, the registered axis it is closest to). Aligned pairwise -- two label vectors
    on different indices are not a contingency table."""
    best = (0.0, "none")
    for name, ref in refs.items():
        pair = pd.DataFrame({"a": labels, "b": ref}).dropna()
        v = cramers_v(pair["a"], pair["b"]) if len(pair) >= MIN_PER_BUCKET * 2 else 0.0
        if v > best[0]:
            best = (v, name)
    return best


# ---------------------------------------------------------------------------- the live losses
def live_loss_series(note: dict[str, str]) -> dict[str, pd.Series]:
    """The daily realised R of the sleeves whose loss the residual queue could not explain. THIS
    is the residual that matters: a candidate axis that sorts backtest residual and not the desk's
    own unexplained P&L has explained the tape, not the book."""
    queue = (_read_json(RESIDUAL_REPORT) or {}).get("top") or _read_rows(RESIDUAL_LEDGER)
    wanted = {str(r.get("symbol") or "").upper() for r in queue
              if isinstance(r, dict) and str(r.get("level")) == "strategy_loss"} - {""}
    if not wanted:
        note["residual_queue"] = "no strategy_loss row -- the live-loss gate does not apply"
        return {}
    rows = _read_rows(LIVE_LEDGER)
    frame = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not {"time", "symbol"} <= set(frame.columns):
        note["live_ledger"] = f"strategy_loss rows on {sorted(wanted)} but no readable live ledger"
        return {}
    frame["_d"] = pd.to_datetime(frame["time"], errors="coerce", utc=True).dt.normalize()

    def _col(name: str) -> pd.Series:
        return (pd.to_numeric(frame[name], errors="coerce").fillna(0.0) if name in frame.columns
                else pd.Series(0.0, index=frame.index))

    # R first, quote P&L only where the ledger could not reconstruct R -- never both, or the two
    # units would be summed into a number in neither.
    value = _col("r_multiple")
    frame["_v"] = value if float(value.abs().sum()) > 0.0 else _col("pl_quote")
    out: dict[str, pd.Series] = {}
    for sym, grp in frame.dropna(subset=["_d"]).groupby(frame["symbol"].astype(str).str.upper()):
        if str(sym) not in wanted:
            continue
        daily = grp.groupby("_d")["_v"].sum().sort_index()
        if len(daily) >= MIN_LIVE_DAYS:
            out[str(sym)] = daily
        else:
            note[f"live_loss:{sym}"] = (f"{len(daily)} days of realised P&L; {MIN_LIVE_DAYS} "
                                        "needed before a bucket can be scored on it")
    if not out:
        note["live_loss_gate"] = ("UNMEASURED: strategy_loss rows exist but no sleeve carries "
                                  f"{MIN_LIVE_DAYS} days of realised P&L, so the gate stands down "
                                  "rather than passing candidates it never applied")
    return out


# ----------------------------------------------------------------------------------- the run
def judge(cand: dict[str, Any], frame: pd.DataFrame, cols: list[str], symbols: list[str],
          live: dict[str, pd.Series], rng: np.random.Generator,
          deadline: float) -> dict[str, Any]:
    """One candidate against every instrument in the pass, then the verdict."""
    per: list[dict[str, Any]] = []
    unmeasured: list[dict[str, str]] = []
    vs: list[float] = []
    closest, probe = "none", None
    for sym in symbols:
        if time.monotonic() > deadline:
            unmeasured.append({"symbol": sym, "why": "wall budget spent before this instrument"})
            continue
        resid = residual_of(frame, cols, sym)
        if resid is None:
            unmeasured.append({"symbol": sym, "why": "no residual: too few aligned factor days"})
            continue
        labels, why = bucket_labels(cand, sym, resid.index)
        got = test_labels(resid, labels, rng)
        if got["status"] != "OK":
            unmeasured.append({"symbol": sym, "why": why or got["why"]})
            continue
        # A registered axis never resembles ITSELF into redundancy on a later run.
        refs = {k: v for k, v in reference_labels(sym, resid.index).items()
                if k != cand["axis_id"]}
        v, name = resemblance(labels, refs)
        vs.append(v)
        closest = name if v >= max(vs) else closest
        if probe is None:
            probe = (sym, labels)
        per.append({"symbol": sym, **got, "resembles": name, "resemblance": round(v, 4),
                    "passed": bool(got["oos_share"] > 0.0 and got["p_perm"] < P_MAX)})

    live_rows: list[dict[str, Any]] = []
    for sym, series in live.items():
        labels, why = bucket_labels(cand, sym, pd.DatetimeIndex(series.index), MIN_LIVE_DAYS)
        got = test_labels(series, labels, rng, MIN_LIVE_DAYS)
        live_rows.append({"symbol": sym, **got, "why": why or got.get("why", ""),
                          "passed": bool(got["status"] == "OK" and got["oos_share"] > 0.0
                                         and got["p_perm"] < P_MAX)})
    passed = [r for r in per if r["passed"]]
    med_v = float(np.median(vs)) if vs else 0.0
    live_ok = any(r["passed"] for r in live_rows) if live_rows else True
    if not per:
        verdict = "UNMEASURED"
    elif med_v > REDUNDANT_AT:
        verdict = "REDUNDANT"
    elif len(passed) >= MIN_INSTRUMENTS and live_ok:
        verdict = "PASS"
    else:
        verdict = "FAIL"
    return {"axis_id": cand["axis_id"], "name": cand["name"], "source": cand.get("source", ""),
            "definition": cand["definition"], "verdict": verdict,
            "instruments_tested": len(per), "instruments_passed": len(passed),
            "oos_share_median": round(float(np.median([r["oos_share"] for r in per])), 6)
            if per else None,
            "p_median": round(float(np.median([r["p_perm"] for r in per])), 6) if per else None,
            "resembles": closest, "resemblance": round(med_v, 4),
            "live_loss_tested": len(live_rows),
            "live_loss_passed": sum(1 for r in live_rows if r["passed"]),
            "live_loss": live_rows, "per_instrument": per, "unmeasured": unmeasured,
            "_probe": probe}


def dedupe(results: list[dict[str, Any]]) -> None:
    """TWO CANDIDATES CAN BE ONE STATE UNDER TWO NAMES, and registering both would hang two tags
    on every cell for one fact. Measured on the synthetic desk: a planted liquidity state is found
    both by `spread/volume` and by the ontology's bare `spread`, at identical p. The keeper is the
    one with a declared mechanism behind it, then the smaller p, then the larger share, then the
    name; the rest are REDUNDANT against their twin, which the report names."""
    order = sorted((r for r in results if r["verdict"] == "PASS" and r["_probe"]),
                   key=lambda r: (r["source"] != "declared", r["p_median"],
                                  -(r["oos_share_median"] or 0.0), r["axis_id"]))
    kept: list[dict[str, Any]] = []
    for res in order:
        sym, labels = res["_probe"]
        twin = next(((round(v, 4), k["axis_id"]) for k in kept if k["_probe"][0] == sym
                     and (v := resemblance(labels, {k["axis_id"]: k["_probe"][1]})[0])
                     > REDUNDANT_AT), None)
        if twin is None:
            kept.append(res)
        else:
            res.update({"verdict": "REDUNDANT", "resembles": twin[1], "resemblance": twin[0]})


def _prior_verdicts() -> dict[str, str]:
    """Each candidate's verdict on its LAST recorded run -- consecutive means consecutive."""
    return {str(r.get("axis_id")): str(r.get("verdict") or "")
            for r in _read_rows(PROPOSALS) if r.get("axis_id")}


def register(results: list[dict[str, Any]], prior: dict[str, str],
             at: str) -> tuple[dict[str, Any], list[str]]:
    """Merge this run's SECOND consecutive passes into the extensions file. Never removes an
    entry: a later FAIL lands as `last_verdict` and retiring an axis is the principal's act."""
    doc = _read_json(EXTENSIONS) or {}
    axes = {str(a.get("axis_id")): dict(a) for a in (doc.get("axes") or [])
            if isinstance(a, dict) and a.get("axis_id")}
    newly: list[str] = []
    for res in results:
        axis_id, verdict = res["axis_id"], res["verdict"]
        evidence = {k: res[k] for k in ("instruments_tested", "instruments_passed",
                                        "oos_share_median", "p_median", "resembles",
                                        "resemblance", "live_loss_tested", "live_loss_passed")}
        if axis_id in axes:
            axes[axis_id].update({"last_verdict": verdict, "last_seen_at": at})
            if verdict == "PASS":
                axes[axis_id]["evidence"] = {**evidence, "at": at}
        elif verdict == "PASS" and prior.get(axis_id) == "PASS":
            axes[axis_id] = {"axis_id": axis_id, "name": res["name"],
                             "definition": res["definition"], "registered_at": at,
                             "last_verdict": "PASS", "last_seen_at": at,
                             "evidence": {**evidence, "at": at, "source": res["source"],
                                          "runs": ["the previous run", at]}}
            newly.append(axis_id)
    return ({"at": at, "contract": CONTRACT, "rule": RULE, "n_axes": len(axes),
             "axes": sorted(axes.values(), key=lambda a: str(a["axis_id"]))}, newly)


# ------------------------------------------------------------------- the registry's contract
def extension_axes() -> list[dict[str, Any]]:
    """Every REGISTERED extra axis. This is the whole read side of the contract."""
    return [a for a in ((_read_json(EXTENSIONS) or {}).get("axes") or [])
            if isinstance(a, dict) and a.get("axis_id")]


def axis_tag(axis_id: str, symbol: str, days: Any = None) -> str:
    """One extra axis's value for one instrument: the modal bucket over its own days, or
    UNMEASURED -- a STATE, exactly as it is on the ten registered axes."""
    cand = next((c for c in [*DECLARED, *extension_axes()] if c.get("axis_id") == axis_id), None)
    df = _bars(symbol) if cand else None
    if df is None:
        return "UNMEASURED"
    index = pd.DatetimeIndex(df["close"].resample("1D").last().dropna().index)
    labels, _ = bucket_labels(cand, symbol, index)
    if labels is not None and days is not None:
        labels = labels.reindex(pd.DatetimeIndex(days)).dropna()
    return "UNMEASURED" if labels is None or labels.empty else str(labels.mode().iloc[0])


# ------------------------------------------------------------------------------ build + write
def build(n_symbols: int = DEFAULT_SYMBOLS,
          budget_s: float = DEFAULT_BUDGET_S) -> tuple[dict[str, Any], dict[str, Any]]:
    """(report, extensions). Reads everything tolerantly; never raises on a missing input."""
    _BARS.clear()
    _CACHE.clear()
    started, at = time.monotonic(), _now()
    rng = np.random.default_rng(SEED)
    note: dict[str, str] = {}
    cands = candidates(note)
    symbols = select_symbols(n_symbols)
    frame, cols, why = residual_frame(symbols)
    base = {"at": at, "n_candidates": len(cands), "rule": RULE, "contract": CONTRACT,
            "symbols": symbols}
    if frame is None:
        note["residual"] = why
        return ({**base, "tested": [], "registered": [], "newly_registered": [],
                 "pending_second_pass": [], "unmeasured": note, "status": "UNMEASURED",
                 "results": [], "elapsed_s": round(time.monotonic() - started, 2)},
                _read_json(EXTENSIONS) or {"at": at, "contract": CONTRACT, "axes": []})

    live = live_loss_series(note)
    prior = _prior_verdicts()
    deadline = started + float(budget_s)
    results = [judge(c, frame, cols, symbols, live, rng, deadline) for c in cands]
    dedupe(results)
    for res in results:
        res.pop("_probe", None)         # label vectors, not evidence: never written anywhere
    extensions, newly = register(results, prior, at)
    for res in results:
        if res["verdict"] == "UNMEASURED":
            note[res["axis_id"]] = (res["unmeasured"][0]["why"] if res["unmeasured"]
                                    else "no instrument produced a testable bucketing")
    note.update({f"axes/{k}.json": v for k, v in (_CACHE.get("axes_skipped") or {}).items()})
    registered = sorted(str(a["axis_id"]) for a in extensions["axes"])
    return ({**base,
             "tested": [{k: r[k] for k in ("axis_id", "name", "source", "verdict",
                                           "instruments_tested", "instruments_passed",
                                           "oos_share_median", "p_median", "resembles",
                                           "resemblance", "live_loss_tested", "live_loss_passed")}
                        for r in sorted(results, key=lambda r: (VERDICTS.index(r["verdict"]),
                                                                -r["instruments_passed"]))],
             "registered": registered, "newly_registered": sorted(newly),
             "pending_second_pass": sorted(r["axis_id"] for r in results
                                           if r["verdict"] == "PASS"
                                           and r["axis_id"] not in registered),
             "unmeasured": note,
             "protocol": {"split": "the first half fits the bucket means AND the tercile cuts; "
                                   "the second half scores",
                          "null": f"{NULL_DRAWS} block permutations of the bucket labels, block "
                                  f"{NULL_BLOCK} days",
                          "p_max": P_MAX, "min_instruments": MIN_INSTRUMENTS,
                          "min_days": MIN_DAYS, "min_per_bucket": MIN_PER_BUCKET,
                          "redundant_at": REDUNDANT_AT, "seed": SEED,
                          "factors": ["dollar basket", GOLD, "equity index"],
                          "lag": "every label is knowable at the previous close",
                          "medians": "oos_share_median and p_median are over EVERY instrument "
                                     "tested; the VERDICT is per-instrument (share > 0 and "
                                     f"p < {P_MAX} on {MIN_INSTRUMENTS}+ of them). A PASS beside "
                                     "a negative median means the effect is CONCENTRATED in a few "
                                     "instruments -- a fact about the axis, not a contradiction"},
             "trial_cost": f"{len(cands)} candidate axes x {len(symbols)} instruments were "
                           "EXAMINED; trial count is a shared cost on this desk, so it is "
                           "published rather than buried",
             "n_days": len(frame), "live_loss_symbols": sorted(live), "results": results,
             "status": "OK", "elapsed_s": round(time.monotonic() - started, 2)},
            extensions)


def summary(report: dict[str, Any]) -> list[str]:
    """Six lines: what was proposed, what was measured, what passed, what entered the registry."""
    counts = {v: sum(1 for r in report["tested"] if r["verdict"] == v) for v in VERDICTS}
    top = [r for r in report["tested"] if r["verdict"] in ("PASS", "FAIL")][:3]
    return [
        f"AXIS PROPOSER {report['at']}  status={report['status']}  {report['n_candidates']} "
        f"candidate axes x {len(report.get('symbols') or [])} instruments",
        "  verdicts  " + "  ".join(f"{v}={counts[v]}" for v in VERDICTS),
        "  " + ("  |  ".join(f"{r['axis_id']} {r['verdict']} {r['instruments_passed']}"
                             f"/{r['instruments_tested']} share={r['oos_share_median']} "
                             f"p={r['p_median']} ~{r['resembles']}" for r in top)
                or "nothing testable this pass"),
        f"  registered {len(report['registered'])} (new "
        f"{len(report.get('newly_registered') or [])}): "
        + (", ".join(report["registered"]) or "none"),
        "  pending a second pass: " + (", ".join(report["pending_second_pass"]) or "none"),
        f"  unmeasured {len(report['unmeasured'])}  elapsed {report.get('elapsed_s')}s  "
        f"rule: {RULE}",
    ]


def write(report: dict[str, Any], extensions: dict[str, Any]) -> None:
    """Report, append-only evidence ledger, extensions -- atomic, in that order."""
    _atomic(OUT_REPORT, json.dumps(report, indent=1, default=str))
    rows = "".join(json.dumps({"at": report["at"], **r}, default=str) + "\n"
                   for r in report.get("results") or [])
    if rows:
        PROPOSALS.parent.mkdir(parents=True, exist_ok=True)
        with PROPOSALS.open("a", encoding="utf-8") as fh:
            fh.write(rows)
    _atomic(EXTENSIONS, json.dumps(extensions, indent=1, default=str))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="propose, test and register NEW search-space axes")
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    ap.add_argument("--symbols", type=int, default=DEFAULT_SYMBOLS,
                    help=f"instruments in the pass (default {DEFAULT_SYMBOLS}, non-equity)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S,
                    help=f"wall budget in seconds (default {DEFAULT_BUDGET_S})")
    args = ap.parse_args(argv)
    report, extensions = build(args.symbols, args.budget_s)
    for line in summary(report):
        print(line)
    if args.dry_run:
        print("  DRY RUN: nothing written, nothing registered")
        return 0
    write(report, extensions)
    print(f"  -> {OUT_REPORT}  -> {PROPOSALS}  -> {EXTENSIONS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
