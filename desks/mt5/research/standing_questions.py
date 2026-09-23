"""SIX QUESTIONS THE DESK ASKS ITS OWN DATA EVERY HOUR, FOREVER -- the unknown-unknown generator.

Every other organ here tests a hypothesis somebody already had. The miners read what other people
wrote, the sweeps enumerate families the registry already holds, the gauntlet judges what was
handed to it. All of that searches a space whose shape was decided in advance, which is exactly
the search that cannot find the thing nobody thought to look for.

A STANDING QUESTION IS THE OTHER SHAPE. It is not a hypothesis and it is never certified. It is a
question the desk re-asks its OWN recorded reality on every pass, phrased so the answer is a
ranked list of measurements rather than a verdict -- and phrased so the desk need not guess in
advance which instrument, which hour or which exogenous series the answer is about. The questions
do not change; the answers do, and a changed answer is a lead. Six of them:

  Q1 pre_vol_precursors      what rises in the 24 bars BEFORE a realised-vol spike
  Q2 first_responder_to_usd  which instrument's hour moves BEFORE the dollar basket does
  Q3 unexplained_residual    what the residual, after the named factors, still correlates with
  Q4 overnight_drift_census  which symbol/session cells carry a drift that will not go away
  Q5 unexplained_live_losses which live losses the desk's OWN factors cannot explain
  Q6 forced_actor_coverage   which forced-flow events no family in the book trades at all

A LEAD, NEVER A CLAIM. A finding here has a statistic and a p-value and nothing else: no cost
model, no out-of-sample, no deflation against the desk's whole trial budget. So it leaves as a
STRUCTURED hypothesis row naming a REGISTERED family and its parameters, into the same intake a
row mined off a Chinese futures forum uses, and the ten gates decide. Nothing here promotes or
sizes anything.

THE EXCLUSION RULE, AND IT IS THE POINT OF Q1. A precursor that is a function of the target's own
price path -- true range, ATR, close-to-close return, band width, RSI, body, wick -- is not an
unknown unknown: `volatility_squeeze`, `vol_transition`, `mean_reversion_rsi`,
`session_range_breakout`, `pin_bar_reversal` and the rest of `OWN_PRICE_FAMILIES` already read
precisely those columns, and a tenth measurement of them is a re-description of the book. Q1
admits ONLY what those families do not consume: other instruments' moves, the target's own VOLUME
and SPREAD (execution-side, not price), the calendar clock, and the exogenous axes. The rule is
written onto the artifact so a later reader can argue with it instead of guessing it.

Q5 DONATES NOTHING, ON PURPOSE: an unexplained live loss is a defect in a funded sleeve, whose
address is the promoter and the forensics. Minting a hypothesis from one would launder an
execution failure into an edge, so each Q5 finding is recorded under `no_family` with that reason.

AN ABSENT INPUT IS UNMEASURED, by name, with the path that was missing -- never zero and never
OK-with-nothing (L1.28a). A question whose wall budget ran out before it started is UNMEASURED
with the budget named, and listed in `skipped` so the next pass can be read against this one.

LANE. `research.universe_policy` routes: single-name equities are traded on disclosure, never
hunted statistically (principal 2026-09-06), so no equity reaches a feature set, a factor, a
finding or a donation here, and a symbol the broker's registry does not classify is hunted by
nothing. Absence is not a permission.

    python desks/mt5/research/standing_questions.py [--dry-run] [--symbols 25] [--budget-s 240]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = DESK / "data" / "universe"
AXES = DESK / "data" / "axes"
LEDGER = DESK / "data" / "live_ledger.jsonl"
SLEEVES = DESK / "data" / "sleeves.json"
FORCED_FLOW = DESK / "data" / "forced_flow_calendar.json"
REPORT = DESK / "reports" / "STANDING_QUESTIONS.json"
INTEL = DESK / "data" / "intelligence" / "standing_questions"

SOURCE = "standing_questions"
#: The dollar basket and each member's sign: +1 where USD is the BASE (a rise is a stronger
#: dollar), -1 where it is the quote. Equally weighted -- a trade-weighted index would be a better
#: dollar and a worse measurement, because the weights would be somebody else's choice.
USD_BASKET: dict[str, int] = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1,
                              "USDJPY": 1, "USDCAD": 1, "USDCHF": 1}
GOLD = "XAUUSD"
EQUITY_PROXIES = ("US500", "SPX500", "USTEC", "NAS100", "US30", "GER40", "DE40")
MAX_DONATIONS = 10          # per question, per run
N_PERM = 199                # circular-shift permutations; p bottoms out at 1/200
SEED = 20260916             # a p-value that moves when nothing else did is not a measurement
PRE_BARS = 24               # the window Q1 looks back over, in H1 bars
Q1_MAX_BARS = 20_000        # ~2.3 years of H1; the permutation cost is linear in this
Q1_PEERS, Q1_AXES, Q1_TARGETS = 8, 8, 11
CENSUS_DAYS = 250
AXIS_MAX_BYTES = 128_000_000    # bis.json is 81 MB and costs ~270 MB resident; the box has 8 GB
MIN_N = 60

OWN_PRICE_FAMILIES = ("volatility_squeeze", "vol_transition", "momentum_volgate",
                      "mean_reversion_bollinger", "mean_reversion_rsi", "session_range_breakout",
                      "level_breakout", "failed_breakout", "pin_bar_reversal",
                      "engulfing_reversal", "trend_ma_cross", "pullback_entry", "jump")
RULE = (
    "Q1 admits a feature only where no registered family already reads it: every function of the "
    "TARGET's own price path (true range, ATR, close-to-close return, band width, RSI, body, "
    f"wick) is excluded because {', '.join(OWN_PRICE_FAMILIES)} consume exactly those columns. "
    "Admitted: other instruments' |return| and range, the target's own volume and spread "
    "(execution-side, not price), the calendar clock, and the exogenous axes. A finding leaves "
    "only against a family the registry actually holds; one that maps to none is recorded as "
    "no_family and is never given an invented one."
)

#: The ONLY parameters named for a family rather than measured by a question: the ones whose own
#: default leaves the rule INERT (`clock_transition` with no catalogue `label`, `carry` and
#: `event_reaction` with no `symbol`), which would donate a cell that can only produce zero
#: signals. Every other default is left to the family, on purpose -- one restated here is right
#: the day it is written and forks silently the day the family changes, the exact failure
#: `miner_candidate_compiler` records against `cross_asset_residual`. Only what was MEASURED (a
#: lag, a side, a stamp hour, a driver) is ever written onto a cell.
NEEDS_SYMBOL = frozenset({"carry", "event_reaction"})
INERT_AT_DEFAULTS: dict[str, dict[str, Any]] = {
    "clock_transition": {"label": "broker_rollover", "stamp_hour": 23},
}

try:
    from mt5desk.family_call import SESSIONS as _FC
    SESSIONS: dict[str, tuple[int, int]] = {k: v for k, v in _FC.items() if v is not None}
except Exception:                                                       # pragma: no cover
    SESSIONS = {"asia": (0, 8), "london": (8, 16), "ny": (14, 22)}

_BARS: dict[tuple[str, str], pd.DataFrame | None] = {}
_CACHE: dict[str, Any] = {}


# ------------------------------------------------------------------------------- primitives
def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _unmeasured(why: str, n: int = 0) -> dict:
    """The only shape an unanswered question leaves here: a named reason, never a clean zero."""
    return {"status": "UNMEASURED", "n": n, "findings": [], "why": why}


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def _ts(value: Any) -> pd.Timestamp | None:
    """Any stamp a publisher writes, as an aware UTC Timestamp, or None."""
    try:
        t = pd.Timestamp(str(value))
    except (ValueError, TypeError):
        return None
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _bars(symbol: str, tf: str = "H1") -> pd.DataFrame | None:
    """The instrument's bars, or None. Cached per run; `run()` clears the cache."""
    key = (symbol, tf)
    if key in _BARS:
        return _BARS[key]
    out: pd.DataFrame | None = None
    try:
        df = pd.read_parquet(UNIVERSE / f"{symbol}_{tf}.parquet")
        df.columns = [str(c).lower() for c in df.columns]
        if isinstance(df.index, pd.DatetimeIndex) and len(df) >= MIN_N and "close" in df:
            out = df[~df.index.duplicated(keep="last")].sort_index()
    except Exception:
        out = None
    _BARS[key] = out
    return out


def _logret(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce").astype("float64").to_numpy()
    with np.errstate(all="ignore"):
        r = np.log(v[1:] / v[:-1])
    return pd.Series(np.where(np.isfinite(r), r, np.nan), index=s.index[1:])


def _rank01(a: np.ndarray) -> np.ndarray:
    """Sample rank in [0,1], NaN -> 0.5. A DESCRIPTION of the past: the rank sees the whole
    sample, so a Q1 lift is never a tradable signal -- it is a lead for the gauntlet, which is
    the only organ on this desk allowed to look forward."""
    return np.nan_to_num(pd.Series(a, dtype="float64").rank(pct=True).to_numpy(), nan=0.5)


def _corr(a: np.ndarray, b: np.ndarray) -> tuple[float, int] | None:
    """Pearson r and n over the pairwise-complete rows; None when either side is constant."""
    m = np.isfinite(a) & np.isfinite(b)
    n = int(m.sum())
    if n < MIN_N:
        return None
    x, y = a[m] - a[m].mean(), b[m] - b[m].mean()
    dx, dy = float(np.sqrt((x * x).sum())), float(np.sqrt((y * y).sum()))
    if dx <= 0.0 or dy <= 0.0:
        return None
    return float((x * y).sum() / (dx * dy)), n


def _p_two_sided(t: float) -> float:
    return float(2.0 * (1.0 - NormalDist().cdf(abs(t))))


def _t_of_corr(r: float, n: int) -> float:
    return float(abs(r) * math.sqrt(max(n - 2, 1) / max(1.0 - r * r, 1e-18)))


def _lift(feat: np.ndarray, mask: np.ndarray,
          rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Each column's mean inside `mask` over its own unconditional mean, and a circular-shift
    permutation p. The MASK is shifted, not the features: that keeps every feature's
    autocorrelation and the mask's own block structure, which is the only null worth testing --
    "these same bars, somewhere else on the same tape"."""
    k = max(float(mask.sum()), 1.0)
    with np.errstate(all="ignore"):
        base = np.where(np.abs(feat.mean(axis=0)) < 1e-12, np.nan, feat.mean(axis=0))
        obs = (mask.astype(np.float64) @ feat) / k / base
        ge = np.zeros(feat.shape[1], dtype=np.int64)
        for shift in rng.integers(1, feat.shape[0], size=N_PERM):
            p = (np.roll(mask, int(shift)).astype(np.float64) @ feat) / k / base
            ge += (p >= obs).astype(np.int64)
    return obs, (1.0 + ge) / (N_PERM + 1.0)


# ------------------------------------------------------------------------------- universe
def _lane_ok(symbol: str) -> bool:
    """True only where the edge is sought statistically. FAILS CLOSED: an unreadable registry
    hunts nothing, because absence of a rule is not a permission."""
    try:
        from research.universe_policy import may_hypothesise
        return bool(may_hypothesise(symbol))
    except Exception:                                                   # pragma: no cover
        return False


def select_symbols(n: int) -> list[str]:
    """The n instruments this pass asks about: the book's own, most-traded first, then the rest
    of the hypothesis lane. A desk asking its questions about instruments it never trades is
    asking about somebody else's book."""
    have = {p.name.rsplit("_", 1)[0] for p in UNIVERSE.glob("*_H1.parquet")}
    counts: dict[str, int] = {}
    with contextlib.suppress(Exception):
        for line in LEDGER.read_text("utf-8").splitlines():
            sym = str(json.loads(line).get("symbol") or "")
            if sym:
                counts[sym] = counts.get(sym, 0) + 1
    with contextlib.suppress(Exception):
        for s in json.loads(SLEEVES.read_text("utf-8")).get("sleeves", []):
            if s.get("symbol"):
                counts.setdefault(str(s["symbol"]), 1)
    ranked = [s for s, _ in sorted(counts.items(), key=lambda kv: -kv[1])
              if s in have and _lane_ok(s)]
    ranked += [s for s in sorted(have) if s not in ranked and _lane_ok(s)]
    return ranked[:max(int(n), 1)]


def _basket() -> tuple[pd.Series | None, str]:
    """(dollar-basket H1 return, why-not). Equal-weighted, positive = stronger USD."""
    parts = [_logret(df["close"]).rename(sym) * w
             for sym, w in USD_BASKET.items() if (df := _bars(sym)) is not None]
    if len(parts) < 3:
        return None, f"the dollar basket needs 3 of {sorted(USD_BASKET)}; {len(parts)} have bars"
    return pd.concat(parts, axis=1, join="inner").mean(axis=1), ""


def _axis_series() -> dict[str, pd.Series]:
    """Every exogenous axis as a daily series keyed `<axis>:<name>`.

    Two shapes, because the publishers differ: fred/ecb carry `series[id].points [{d, v}]`; cot
    and bis carry flat `rows` stamped `knowable_at` -- the POINT-IN-TIME date, which is the only
    one a joiner may use. The release's own as_of is never read.
    """
    if "axes" in _CACHE:
        return _CACHE["axes"]
    out: dict[str, pd.Series] = {}
    skipped: dict[str, str] = {}
    for path in (sorted(AXES.glob("*.json")) if AXES.exists() else []):
        axis = path.stem
        try:
            if path.stat().st_size > AXIS_MAX_BYTES:
                skipped[axis] = f"{path.stat().st_size / 1e6:.0f} MB over the memory budget"
                continue
            doc = json.loads(path.read_text("utf-8"))
        except Exception as exc:
            skipped[axis] = f"unreadable ({type(exc).__name__})"
            continue
        for sid, spec in (doc.get("series") or {}).items():
            pts = (spec or {}).get("points") or []
            s = pd.Series(pd.to_numeric([p.get("v") for p in pts], errors="coerce"),
                          index=pd.to_datetime([p.get("d") for p in pts], errors="coerce",
                                               utc=True)).dropna()
            if len(s) >= MIN_N:
                out[f"{axis}:{sid}"] = s[~s.index.duplicated(keep="last")].sort_index()
        rows = doc.get("rows") or []
        frame = pd.DataFrame(rows) if isinstance(rows, list) and rows else pd.DataFrame()
        fields = [c for c in ("net_pct_oi", "comm_pct_oi", "carry_differential")
                  if c in frame.columns]
        if fields and {"knowable_at", "symbol"} <= set(frame.columns):
            frame["_d"] = pd.to_datetime(frame["knowable_at"], errors="coerce", utc=True)
            for sym, grp in frame.dropna(subset=["_d"]).groupby("symbol"):
                for field in fields:
                    s = pd.to_numeric(grp.set_index("_d")[field], errors="coerce").dropna()
                    s = s[~s.index.duplicated(keep="last")].sort_index()
                    if len(s) >= MIN_N:
                        out[f"{axis}:{sym}.{field}"] = s
        del doc
    _CACHE["axes"], _CACHE["axes_skipped"] = out, skipped
    return out


# ------------------------------------------------------------------------------- donations
def registered_families() -> set[str]:
    """Every family the desk can actually call, minus the banned -- read off the registries
    themselves, the way `research/breadth_sweep.default_families` reads them."""
    if "fams" in _CACHE:
        return _CACHE["fams"]
    names: set[str] = set()
    with contextlib.suppress(Exception):
        from mt5desk import families as fam_mod
        from mt5desk import families_orthogonal as fo
        names |= {str(k) for k in getattr(fam_mod, "FAMILY_REGISTRY", {})}
        names |= {str(k) for k in getattr(fo, "ORTHOGONAL_FAMILIES", {})}
    with contextlib.suppress(Exception):
        from research.family_policy import family_banned
        names = {n for n in names if not family_banned(n)}
    _CACHE["fams"] = names
    return names


class Donor:
    """Collects donation rows, refusing any family the registry does not hold."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.no_family: list[dict] = []
        self.known = registered_families()

    def refuse(self, q: str, why: str, symbols: list[str], reason: str,
               family: str | None = None) -> None:
        self.no_family.append({"question": q, "why": why, "symbols": symbols,
                               "proposed_family": family, "reason": reason})

    def offer(self, q: str, family: str | None, symbols: list[str], params: dict, why: str,
              *, timeframe: str = "H1", session: str = "all") -> bool:
        syms = [s for s in dict.fromkeys(symbols) if s and _lane_ok(s)]
        if not family or family not in self.known:
            self.refuse(q, why, syms, family=family,
                        reason=("no registered family expresses this finding" if not family
                                else f"'{family}' is not in the registry, or is banned"))
            return False
        if not syms:
            self.refuse(q, why, [], family=family,
                        reason="every instrument in the finding is outside the hypothesis lane")
            return False
        if sum(1 for r in self.rows if r["source"].endswith(q)) >= MAX_DONATIONS:
            return False
        self.rows.append({"kind": "hypothesis", "family": family, "symbols": syms,
                          "params": dict(params), "timeframe": timeframe,
                          "session": session, "source": f"{SOURCE}:{q}", "why": why,
                          "title": f"{q} {family} {'/'.join(syms[:3])}",
                          "mechanism": why, "mechanism_tags": [family, q]})
        return True


# ------------------------------------------------------------------------------- Q1
def q1_pre_vol_precursors(syms: list[str], deadline: float) -> dict:
    """What rises in the 24 bars before a realised-vol spike, excluding what the families read.

    Spikes are FIRST CROSSINGS into the top decile of 24-bar realised vol, so a week-long
    high-vol regime is one event and not two hundred. Every admitted feature is reduced to its
    sample rank, so a lift compares like with like and one 8-sigma print cannot manufacture a
    precursor. The clock is asked about the EVENT bar, not the window before it: every 24-bar
    window holds every hour exactly once, so a pre-window lift on an hour indicator is 1.0 by
    construction and says nothing.
    """
    targets = list(dict.fromkeys(([GOLD] if GOLD in syms else []) + syms))[:Q1_TARGETS]
    rng = np.random.default_rng(SEED)
    axes = list(_axis_series().items())[:Q1_AXES]
    findings: list[dict] = []
    tested = 0
    for target in targets:
        if time.monotonic() > deadline:
            break
        df = _bars(target)
        if df is None:
            continue
        df = df.iloc[-Q1_MAX_BARS:]
        ret = _logret(df["close"])
        idx = ret.index
        rv = ret.rolling(PRE_BARS).std()
        if int(rv.notna().sum()) < MIN_N:
            continue
        hot = (rv >= float(rv.quantile(0.90))).to_numpy()
        ev = np.flatnonzero(hot & ~np.roll(hot, 1))
        ev = ev[ev >= PRE_BARS]
        if ev.size < 20:
            continue
        cols: list[tuple[str, str]] = []
        vals: list[np.ndarray] = []
        for peer in [p for p in syms if p != target][:Q1_PEERS]:
            pdf = _bars(peer)
            if pdf is None:
                continue
            with np.errstate(all="ignore"):
                rg = ((pdf["high"] - pdf["low"]) / pdf["close"].abs()).replace(
                    [np.inf, -np.inf], np.nan)
            cols += [(f"absret_{peer}", "peer"), (f"range_{peer}", "peer")]
            vals += [_rank01(_logret(pdf["close"]).abs().reindex(idx).ffill().to_numpy()),
                     _rank01(rg.reindex(idx).ffill().to_numpy())]
        for col, label in (("tick_volume", "volume"), ("real_volume", "volume"),
                           ("spread", "spread")):
            v = pd.to_numeric(df.get(col), errors="coerce") if col in df.columns else None
            if v is not None and float(v.std() or 0.0) > 0.0:
                cols.append((f"own_{col}", label))
                vals.append(_rank01(v.reindex(idx).to_numpy(dtype="float64")))
        for name, s in axes:
            a = s.reindex(s.index.union(idx)).ffill().reindex(idx)
            if float(a.std() or 0.0) > 0.0:
                cols.append((f"axis_{name}", "axis"))
                vals.append(_rank01(a.to_numpy(dtype="float64")))
        if not cols:
            continue
        pre = np.zeros(len(idx), dtype=bool)
        for i in ev:
            pre[max(0, int(i) - PRE_BARS):int(i)] = True
        lifts, ps = _lift(np.column_stack(vals), pre, rng)
        emask = np.zeros(len(idx), dtype=bool)
        emask[ev] = True
        hours, dows = np.asarray(idx.hour), np.asarray(idx.dayofweek)
        onehot = np.column_stack([(hours == h).astype(np.float64) for h in range(24)]
                                 + [(dows == d).astype(np.float64) for d in range(5)])
        clift, cps = _lift(onehot, emask, rng)
        cols += [(f"clock_hour_{h:02d}", "clock") for h in range(24)]
        cols += [(f"clock_dow_{d}", "clock") for d in range(5)]
        tested += len(cols)
        for (name, cat), lift, p in zip(cols, np.r_[lifts, clift], np.r_[ps, cps], strict=True):
            if math.isfinite(float(lift)) and float(lift) > 1.0:
                findings.append({"target": target, "feature": name, "category": cat,
                                 "lift": round(float(lift), 4), "p_perm": round(float(p), 4),
                                 "n_events": int(ev.size), "n_bars": len(idx)})
    if not tested:
        return _unmeasured("no instrument in the pass carries 20+ vol-spike events under "
                           f"{UNIVERSE}")
    findings.sort(key=lambda f: (f["p_perm"], -f["lift"]))
    return {"status": "OK", "n": tested, "findings": findings[:40],
            "excluded_feature_families": list(OWN_PRICE_FAMILIES),
            "why": f"{tested} admitted feature/target tests over {len(targets)} targets; "
                   f"{len(findings)} carry a lift above 1"}


def q1_donate(res: dict, donor: Donor) -> None:
    fam = {"peer": "vol_transition", "axis": "vol_transition", "volume": "volume_spike",
           "spread": "spread_state"}
    for f in res["findings"]:
        if f["p_perm"] > 0.05 or f["lift"] < 1.05:
            continue
        why = (f"{f['feature']} sits at {f['lift']:.2f}x its own average rank in the 24 bars "
               f"before {f['target']} realised-vol spikes (n={f['n_events']} first crossings, "
               f"permutation p={f['p_perm']})")
        if f["category"] == "clock":
            donor.refuse("Q1", why, [f["target"]],
                         "a vol-spike clock concentration names a WHEN and no side; every "
                         "registered clock family takes a side this measurement does not hold")
        else:
            donor.offer("Q1", fam.get(f["category"]), [f["target"]], {}, why)


# ------------------------------------------------------------------------------- Q2
def q2_first_responder_to_usd(syms: list[str], deadline: float) -> dict:
    """Whose hour moves before the dollar's, measured only on the days the dollar moved.

    Lead correlation at lags 1..6, restricted to bars on top-decile |daily dollar move| days: on
    a quiet day the basket is microstructure, and a lead correlation there measures the quote
    feed. The p is Bonferroni-charged for every (symbol, lag) pair this pass tried.
    """
    usd, why = _basket()
    if usd is None:
        return _unmeasured(why)
    day = usd.groupby(usd.index.floor("D")).transform("sum").abs()
    keep = (day >= day.quantile(0.90)).to_numpy()
    if int(keep.sum()) < MIN_N:
        return _unmeasured(f"only {int(keep.sum())} bars fall on large-dollar days; {MIN_N} needed")
    u = usd.to_numpy(dtype="float64")
    rows: list[dict] = []
    tested = 0
    for sym in syms:
        if time.monotonic() > deadline:
            break
        df = _bars(sym)
        if sym in USD_BASKET or df is None:
            continue
        r = _logret(df["close"]).reindex(usd.index).to_numpy(dtype="float64")
        best: tuple[float, int, int] | None = None
        for lag in range(1, 7):
            b = np.roll(np.where(keep, u, np.nan), -lag)
            b[-lag:] = np.nan
            got = _corr(np.where(keep, r, np.nan), b)
            tested += 1
            if got and (best is None or abs(got[0]) > abs(best[0])):
                best = (got[0], got[1], lag)
        if best is not None:
            rows.append({"symbol": sym, "lead_bars": best[2], "corr": round(best[0], 4),
                         "n": best[1], "t": round(_t_of_corr(best[0], best[1]), 3),
                         "p_raw": _p_two_sided(_t_of_corr(best[0], best[1]))})
    if not rows:
        return _unmeasured("no non-basket instrument in the pass has bars aligned to the basket")
    for row in rows:
        row["p_bonf"] = round(min(1.0, row["p_raw"] * max(tested, 1)), 6)
        row["p_raw"] = round(row["p_raw"], 6)
    rows.sort(key=lambda r: -abs(r["corr"]))
    return {"status": "OK", "n": tested, "findings": rows[:25],
            "why": f"{tested} (symbol, lag) lead correlations on {int(keep.sum())} large-dollar "
                   f"bars; Bonferroni charged over {tested}"}


def q2_donate(res: dict, donor: Donor) -> None:
    for f in res["findings"]:
        if f.get("p_bonf", 1.0) > 0.05 or abs(f["corr"]) < 0.05:
            continue
        why = (f"{f['symbol']} leads the dollar basket by {f['lead_bars']} H1 bar(s) on "
               f"large-dollar days (r={f['corr']:+.3f}, n={f['n']}, "
               f"Bonferroni p={f['p_bonf']})")
        for member, w in USD_BASKET.items():
            donor.offer("Q2", "lead_lag", [member],
                        {"driver_symbol": f["symbol"], "lag": int(f["lead_bars"]),
                         "direction": "same" if f["corr"] * w > 0 else "opposite",
                         "hold_bars": int(f["lead_bars"])}, why)


# ------------------------------------------------------------------------------- Q3
def _pc1(mat: np.ndarray) -> np.ndarray | None:
    """The first latent factor, via `libs.portfolio.latent_factors`. Reused rather than
    re-derived: that module already decides what a common factor IS on this desk, and two
    definitions of one factor is how two organs come to disagree about the same book."""
    try:
        from libs.portfolio.latent_factors import factor_model
    except Exception:                                                   # pragma: no cover
        return None
    if mat.shape[0] < MIN_N or mat.shape[1] < 5:
        return None
    sd = mat.std(axis=0)
    if float(sd.min()) <= 0.0:
        return None
    z = (mat - mat.mean(axis=0)) / sd
    b = factor_model(z, k=1)["loadings"][:, 0]
    denom = float((b * b).sum())
    return None if denom <= 0.0 else np.asarray(z @ b / denom)


def q3_unexplained_residual_correlates(syms: list[str], deadline: float) -> dict:
    """What the residual still knows once the named factors have had their say.

    Daily returns on [dollar basket, gold, equity index, first latent factor]; the residual then
    against every exogenous axis AS-OF -- carried forward from its own knowable date, never
    interpolated backwards. Axes enter as first DIFFERENCES: correlating a return against a LEVEL
    manufactures significance out of two trends, and has done so on this desk before.
    """
    usd, why = _basket()
    if usd is None:
        return _unmeasured(why)
    daily: dict[str, pd.Series] = {}
    for sym in dict.fromkeys([*syms, GOLD, *USD_BASKET]):
        df = _bars(sym)
        if df is None:
            continue
        d = df["close"].resample("1D").last().dropna()
        if len(d) >= MIN_N:
            with np.errstate(all="ignore"):
                daily[sym] = np.log(d).diff().dropna().iloc[-CENSUS_DAYS * 2:]
    if GOLD not in daily or len(daily) < 3:
        return _unmeasured(f"the daily factor set needs {GOLD} and 3+ instruments; "
                           f"{len(daily)} carry {MIN_N} daily closes")
    equity = next((s for s in EQUITY_PROXIES if s in daily), None)
    frame = pd.DataFrame(daily)
    frame["_usd"] = usd.groupby(usd.index.floor("D")).sum().reindex(frame.index)
    cols = ["_usd", GOLD] + ([equity] if equity else [])
    frame = frame.dropna(subset=cols)
    if len(frame) < MIN_N:
        return _unmeasured(f"{len(frame)} aligned daily rows across the factors; {MIN_N} needed")
    pc = _pc1(frame[[c for c in frame.columns if c != "_usd"]].fillna(0.0)
              .to_numpy(dtype="float64"))
    base = [np.ones(len(frame))] + [frame[c].to_numpy(dtype="float64") for c in cols]
    x = np.column_stack(base + ([pc] if pc is not None else []))
    axes = _axis_series()
    rows: list[dict] = []
    tested = 0
    for sym in syms:
        if time.monotonic() > deadline:
            break
        if sym not in frame.columns:
            continue
        y = frame[sym].to_numpy(dtype="float64")
        ok = np.isfinite(y)
        if int(ok.sum()) < MIN_N:
            continue
        beta, *_ = np.linalg.lstsq(x[ok], y[ok], rcond=None)
        resid = np.full(len(y), np.nan)
        resid[ok] = y[ok] - x[ok] @ beta
        for name, s in axes.items():
            a = s.reindex(s.index.union(frame.index)).ffill().reindex(frame.index)
            got = _corr(resid, a.diff().to_numpy(dtype="float64"))
            tested += 1
            if got:
                rows.append({"symbol": sym, "axis": name, "corr": round(got[0], 4), "n": got[1],
                             "p_raw": _p_two_sided(_t_of_corr(got[0], got[1]))})
    if not tested:
        return _unmeasured(f"no exogenous axis series with {MIN_N}+ points under {AXES}")
    for r in rows:
        r["p_bonf"] = round(min(1.0, r["p_raw"] * tested), 6)
        r["p_raw"] = round(r["p_raw"], 6)
    rows.sort(key=lambda r: -abs(r["corr"]))
    named = ["dollar basket", GOLD] + ([equity] if equity else []) + (["pc1"] if pc is not None
                                                                     else [])
    return {"status": "OK", "n": tested, "findings": rows[:20],
            "why": f"{tested} residual-vs-axis correlations over {len(frame)} aligned days; "
                   f"factors = {', '.join(named)}; Bonferroni charged over {tested}"}


def q3_donate(res: dict, donor: Donor) -> None:
    for f in res["findings"]:
        if f.get("p_bonf", 1.0) > 0.05:
            continue
        axis = str(f["axis"])
        why = (f"after the dollar/gold/equity factors {f['symbol']}'s daily residual still "
               f"correlates {f['corr']:+.3f} (n={f['n']}, Bonferroni p={f['p_bonf']}) with "
               f"{axis}")
        if axis.startswith("cot:"):
            donor.offer("Q3", "cot_positioning", [f["symbol"]], {}, why)
        elif axis.startswith("bis:"):
            donor.offer("Q3", "carry", [f["symbol"]], {"symbol": f["symbol"]}, why)
        else:
            donor.offer("Q3", "macro_conditional", [f["symbol"]],
                        {"side_in_high": 1 if f["corr"] > 0 else -1}, why)


# ------------------------------------------------------------------------------- Q4
def q4_overnight_drift_census(syms: list[str], deadline: float) -> dict:
    """Every (symbol, session) cell's close-to-open and in-session drift, with its t.

    Hours are read off the bar as the SERVER clock -- the convention `family_call.SESSIONS`, the
    gold windows and the live executor already share. The CENSUS is the point: a t of 2.5 found
    after one cell and a t of 2.5 found after four hundred are different measurements, so the
    cell count is charged here and the surviving threshold rides on the artifact.
    """
    rows: list[dict] = []
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=CENSUS_DAYS)
    for sym in syms:
        if time.monotonic() > deadline:
            break
        df = _bars(sym)
        if df is None:
            continue
        df = df[df.index >= cutoff]
        if len(df) < MIN_N:
            continue
        op = df["open"].to_numpy(dtype="float64") if "open" in df else None
        cl = df["close"].to_numpy(dtype="float64")
        if op is None:
            continue
        hour, days = np.asarray(df.index.hour), df.index.floor("D")
        for name, (lo, hi) in SESSIONS.items():
            sel = (hour >= lo) & (hour < hi)
            pos = np.flatnonzero(sel)
            if pos.size < MIN_N:
                continue
            g = pd.Series(pos, index=days[sel]).groupby(level=0)
            first, last = g.first().to_numpy(), g.last().to_numpy()
            ok = first > 0
            first, last = first[ok], last[ok]
            with np.errstate(all="ignore"):
                measures = (("close_to_open", np.log(op[first] / cl[first - 1])),
                            ("session_drift", np.log(cl[last] / op[first])))
            for measure, series in measures:
                v = series[np.isfinite(series)]
                if v.size < 30 or float(v.std(ddof=1)) <= 0.0:
                    continue
                t = float(v.mean() / (v.std(ddof=1) / math.sqrt(v.size)))
                rows.append({"symbol": sym, "session": name, "measure": measure,
                             "mean_bp": round(float(v.mean()) * 1e4, 3), "t": round(t, 3),
                             "n_days": int(v.size), "p_raw": _p_two_sided(t)})
    if not rows:
        return _unmeasured(f"no instrument carries {CENSUS_DAYS} days of session bars under "
                       f"{UNIVERSE}")
    cells = len(rows)
    crit = NormalDist().inv_cdf(1.0 - 0.025 / cells)
    for r in rows:
        r["p_bonf"] = round(min(1.0, r["p_raw"] * cells), 6)
        r["p_raw"] = round(r["p_raw"], 6)
        r["survives_deflation"] = bool(abs(r["t"]) >= crit)
    rows.sort(key=lambda r: -abs(r["t"]))
    return {"status": "OK", "n": cells, "findings": rows[:30], "t_threshold": round(crit, 3),
            "why": f"{cells} (symbol, session, measure) cells over {CENSUS_DAYS} days; a cell "
                   f"needs |t| >= {crit:.2f} to survive the census's own multiplicity"}


def q4_donate(res: dict, donor: Donor) -> None:
    label = {"asia": "tokyo_open", "london": "london_open", "ny": "ny_open"}
    for f in res["findings"]:
        if not f.get("survives_deflation"):
            continue
        lo = int(SESSIONS.get(f["session"], (0, 8))[0])
        why = (f"{f['symbol']} {f['session']} {f['measure']} averages {f['mean_bp']:+.2f} bp over "
               f"{f['n_days']} days (t={f['t']:+.2f}, Bonferroni p={f['p_bonf']} over "
               f"{res['n']} cells)")
        if f["measure"] == "close_to_open":
            donor.offer("Q4", "overnight_drift", [f["symbol"]], {"anchor_hour": lo}, why,
                        session=f["session"])
        elif f["session"] in label:
            donor.offer("Q4", "clock_transition", [f["symbol"]],
                        {"label": label[f["session"]], "stamp_hour": lo,
                         "side": 1 if f["mean_bp"] > 0 else -1}, why, session=f["session"])
        else:
            donor.refuse("Q4", why, [f["symbol"]],
                         f"'{f['session']}' is not a moment in the clock_transition catalogue, "
                         f"and a plumbing cell with no named cause is a time-of-day curve fit")


# ------------------------------------------------------------------------------- Q5
def _sleeve_families() -> dict[str, str]:
    try:
        doc = json.loads(SLEEVES.read_text("utf-8"))
        return {str(s.get("name")): str(s.get("family") or "unknown")
                for s in doc.get("sleeves", []) if isinstance(s, dict)}
    except Exception:
        return {}


def _bar_ret(symbol: str, ts: pd.Timestamp) -> float:
    df = _bars(symbol)
    if df is None or ts not in df.index:
        return float("nan")
    try:
        j = int(df.index.get_loc(ts))
    except (KeyError, TypeError):
        return float("nan")
    if j <= 0:
        return float("nan")
    with np.errstate(all="ignore"):
        v = float(np.log(df["close"].iloc[j] / df["close"].iloc[j - 1]))
    return v if math.isfinite(v) else float("nan")


def q5_unexplained_live_losses(deadline: float) -> dict:
    """How much of the book's realised R the desk's own factors cannot explain.

    R is regressed on what the desk BELIEVES moves it -- the instrument's own hour, the dollar,
    gold, the session and the sleeve's family -- and what is left is, by construction, loss the
    desk has no account of. DONATES NOTHING, deliberately (see the module docstring).
    """
    try:
        raw = [json.loads(ln) for ln in LEDGER.read_text("utf-8").splitlines() if ln.strip()]
    except Exception as exc:
        return _unmeasured(f"{LEDGER} absent or unreadable ({type(exc).__name__})")
    usd, _ = _basket()
    fams = _sleeve_families()
    recs: list[dict] = []
    for row in raw:
        ts = _ts(row.get("time"))
        try:
            r = float(row.get("r_multiple"))
        except (TypeError, ValueError):
            continue
        if ts is None or not math.isfinite(r) or r == 0.0:
            continue
        ts = ts.floor("h")
        sleeve = str(row.get("sleeve") or "unknown")
        recs.append({"r": r, "sym_ret": _bar_ret(str(row.get("symbol") or ""), ts),
                     "usd_ret": float(usd.get(ts, float("nan"))) if usd is not None else np.nan,
                     "gold_ret": _bar_ret(GOLD, ts), "sleeve": sleeve,
                     "family": fams.get(sleeve, "unknown"), "hour": int(ts.hour),
                     "session": next((n for n, (lo, hi) in SESSIONS.items()
                                      if lo <= ts.hour < hi), "other")})
        if time.monotonic() > deadline:
            break
    if len(recs) < 20:
        return _unmeasured(f"{len(recs)} usable closed trades in {LEDGER}; 20 needed to "
                           "regress", len(recs))
    tf = pd.DataFrame(recs)
    y = tf["r"].to_numpy(dtype="float64")
    parts, names = [np.ones(len(tf))], ["const"]
    for col in ("sym_ret", "usd_ret", "gold_ret"):
        v = np.nan_to_num(tf[col].to_numpy(dtype="float64"), nan=0.0)
        if float(v.std()) > 0.0:
            parts.append(v)
            names.append(col)
    for col in ("session", "family"):
        for lv in sorted(tf[col].dropna().unique())[1:9]:
            parts.append((tf[col] == lv).to_numpy(dtype="float64"))
            names.append(f"{col}={lv}")
    beta, *_ = np.linalg.lstsq(x := np.column_stack(parts), y, rcond=None)
    tf["resid"] = resid = y - x @ beta
    loss = y < 0
    denom = float(((y[loss] - y[loss].mean()) ** 2).sum()) if int(loss.sum()) > 1 else 0.0
    share = float((resid[loss] ** 2).sum() / denom) if denom > 0.0 else None
    ss_tot = float(((y - y.mean()) ** 2).sum())
    findings: list[dict] = []
    for kind, key, head in (("sleeve", "sleeve", 8), ("hour", "hour", 6), ("session", "session",
                                                                          6)):
        agg = tf[loss].groupby(key)["resid"].agg(["sum", "count", "mean"]).sort_values("sum")
        findings += [{"kind": kind, "name": str(i), "unexplained_r": round(float(r["sum"]), 3),
                      "n": int(r["count"]), "mean_r": round(float(r["mean"]), 3)}
                     for i, r in agg.head(head).iterrows()]
    return {"status": "OK", "n": len(tf), "findings": findings, "regressors": names,
            "n_losses": int(loss.sum()), "donates": "nothing, by design",
            "unexplained_loss_variance_share": None if share is None else round(share, 4),
            "r_squared_all": (round(1.0 - float((resid ** 2).sum()) / ss_tot, 4)
                              if ss_tot > 0.0 else None),
            "why": f"{len(tf)} closed trades regressed on {len(names)} known factors; "
                   f"{int(loss.sum())} losses carry "
                   f"{'n/a' if share is None else format(share, '.1%')} unexplained variance"}


def q5_donate(res: dict, donor: Donor) -> None:
    for f in res["findings"][:MAX_DONATIONS]:
        donor.refuse("Q5", f"{f['kind']} {f['name']} carries {f['unexplained_r']}R of loss the "
                           f"desk's own factors do not explain over {f['n']} trades", [],
                     "an unexplained live loss is a defect in a funded sleeve, not a hypothesis "
                     "about an instrument; it routes to the promoter and the forensics, and "
                     "minting a family from it would launder an execution failure into an edge")


# ------------------------------------------------------------------------------- Q6
#: Forced-flow event kind -> the registered family that would trade it, matched on the LONGEST
#: phrase contained in the kind string. A kind matching nothing is uncovered AND unmapped, which
#: is a different and more interesting answer than uncovered-but-known.
KIND_FAMILY: tuple[tuple[str, str], ...] = (
    ("option_expiry", "liquidity_gamma_reversal"), ("ny_cut", "liquidity_gamma_reversal"),
    ("gamma", "liquidity_gamma_reversal"), ("london_fix", "fx_fixing_reversal"),
    ("wm_fix", "fx_fixing_reversal"), ("fixing", "fx_fixing_reversal"),
    ("fix", "fx_fixing_reversal"), ("index_rebalance", "hedging_demand_close"),
    ("rebalance", "hedging_demand_close"), ("cash_close", "hedging_demand_close"),
    ("closing_auction", "hedging_demand_close"), ("comex", "comex_settlement"),
    ("settlement", "comex_settlement"), ("month_end", "turn_of_month"),
    ("turn_of_month", "turn_of_month"), ("quarter_end", "turn_of_month"),
    ("rollover", "clock_transition"), ("roll", "clock_transition"),
    ("cot", "cot_positioning"), ("positioning", "cot_positioning"), ("carry", "carry"),
    ("swap", "carry"), ("cpi", "event_reaction"), ("nfp", "event_reaction"),
    ("central_bank", "event_reaction"), ("rate_decision", "event_reaction"),
    ("release", "event_reaction"),
)


def _kind_family(kind: str) -> str | None:
    k = kind.lower().replace(" ", "_").replace("-", "_")
    hits = [(len(p), f) for p, f in KIND_FAMILY if p in k]
    return max(hits)[1] if hits else None


def q6_forced_actor_coverage() -> dict:
    """Which forced-flow events nobody in the book is on the other side of.

    The calendar is built by its own organ and read tolerantly here: a bare list, or any of
    `events|calendar|rows|flows`; any of `kind|event_kind|type|name` for the kind and any of
    `at|date|time|when|knowable_at` for the stamp. An absent calendar is UNMEASURED -- the
    coverage of a calendar that does not exist is not zero, it is unknown.
    """
    try:
        doc = json.loads(FORCED_FLOW.read_text("utf-8"))
    except Exception as exc:
        return _unmeasured(f"{FORCED_FLOW} absent or unreadable ({type(exc).__name__}); the "
                       f"forced-flow calendar is built by its own organ and this question "
                       f"measures nothing until it lands")
    events = doc if isinstance(doc, list) else next(
        (v for k, v in doc.items()
         if k in ("events", "calendar", "rows", "flows") and isinstance(v, list)), [])
    traded = {str(f) for f in _sleeve_families().values()}
    known = registered_families()
    kinds: dict[str, dict] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        kind = next((str(ev[k]) for k in ("kind", "event_kind", "type", "name") if ev.get(k)), "")
        if not kind:
            continue
        row = kinds.setdefault(kind, {"events": 0, "symbols": set(), "first": None,
                                      "last": None, "actor": ""})
        row["events"] += 1
        row["actor"] = row["actor"] or str(ev.get("forced_actor") or ev.get("mechanism") or "")
        named = next((ev[k] for k in ("symbols", "instruments", "symbol", "instrument")
                      if ev.get(k)), [])
        for s in ([named] if isinstance(named, str) else named):
            if _lane_ok(str(s)):
                row["symbols"].add(str(s))
        ts = next((_ts(ev[k]) for k in ("at", "date", "time", "when", "knowable_at",
                                        "window_start_utc") if ev.get(k)), None)
        if ts is not None:
            row["first"] = ts if row["first"] is None else min(row["first"], ts)
            row["last"] = ts if row["last"] is None else max(row["last"], ts)
    if not kinds:
        return _unmeasured(f"{FORCED_FLOW} holds no readable event rows")
    findings = []
    for kind, row in kinds.items():
        fam = _kind_family(kind)
        span = ((row["last"] - row["first"]).days / 91.3
                if row["first"] is not None and row["last"] is not None else 1.0)
        findings.append({"kind": kind, "family": fam, "registered": bool(fam and fam in known),
                         "covered": bool(fam and fam in traded), "events": row["events"],
                         "events_per_quarter": round(row["events"] / max(span, 1.0), 2),
                         "forced_actor": row["actor"][:180],
                         "symbols": sorted(row["symbols"])[:8]})
    findings.sort(key=lambda f: (f["covered"], -f["events_per_quarter"]))
    uncovered = [f["kind"] for f in findings if not f["covered"]]
    return {"status": "OK", "n": len(findings), "findings": findings, "uncovered": uncovered,
            "why": f"{len(findings)} event kinds over {sum(f['events'] for f in findings)} "
                   f"events; {len(uncovered)} carry no family the book trades"}


def q6_donate(res: dict, donor: Donor) -> None:
    for f in res["findings"]:
        if f["covered"]:
            continue
        why = (f"forced-flow kind '{f['kind']}' carries {f['events_per_quarter']} events per "
               f"quarter and no family in data/sleeves.json trades it"
               + (f"; forced actor: {f['forced_actor']}" if f.get("forced_actor") else ""))
        if f["family"] in NEEDS_SYMBOL:
            for sym in f["symbols"][:4]:
                donor.offer("Q6", f["family"], [sym], {"symbol": sym}, why)
        else:
            donor.offer("Q6", f["family"], f["symbols"][:4],
                        dict(INERT_AT_DEFAULTS.get(str(f["family"]), {})), why)


# ------------------------------------------------------------------------------- run
def _seat_questions(asked: list[str]) -> dict[str, Any]:
    """THE PROPOSER SEAT, OPTIONAL: a SEVENTH question worth asking the desk's own data.

    The six questions here are hard-coded on purpose -- they are the unknown-unknown generator,
    and a question that changes every hour measures nothing. So a proposed question is published
    in the report as a CANDIDATE for a human or a later builder to implement: it runs nothing,
    donates nothing, and cannot add a row to this pass. That is the correct weight for a
    suggestion about what to measure next. {} on a box with no panel.
    """
    try:
        from libs.research import proposer_seat as ps
        return ps.ask(
            "standing_questions", "terms",
            task=("Propose a question a quant desk could ask its OWN hourly bar and tape data "
                  "that would surface an effect nobody looked for. One clause each, no sites."),
            context=[f"already asked every hour: {q}" for q in asked[:12]],
            n=6).to_row()
    except Exception as exc:                              # pragma: no cover - optional seat
        return {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


def run(*, n_symbols: int = 25, budget_s: float = 240.0, dry_run: bool = False) -> dict:
    _BARS.clear()
    _CACHE.clear()
    started = time.monotonic()
    deadline = started + float(budget_s)
    syms = select_symbols(n_symbols)
    donor = Donor()
    out: dict[str, dict] = {}
    skipped: list[str] = []
    plan: list[tuple[str, Any, Any]] = [
        ("Q1", lambda: q1_pre_vol_precursors(syms, deadline), q1_donate),
        ("Q2", lambda: q2_first_responder_to_usd(syms, deadline), q2_donate),
        ("Q3", lambda: q3_unexplained_residual_correlates(syms, deadline), q3_donate),
        ("Q4", lambda: q4_overnight_drift_census(syms, deadline), q4_donate),
        ("Q5", lambda: q5_unexplained_live_losses(deadline), q5_donate),
        ("Q6", q6_forced_actor_coverage, q6_donate),
    ]
    for name, fn, donate in plan:
        if time.monotonic() > deadline:
            skipped.append(name)
            out[name] = {"status": "UNMEASURED", "n": 0, "findings": [],
                         "why": f"the {budget_s:g}s wall budget was exhausted before {name} "
                                f"started; UNMEASURED this pass, not clean"}
            continue
        if not syms and name != "Q6":
            out[name] = {"status": "UNMEASURED", "n": 0, "findings": [],
                         "why": f"no hypothesis-lane instrument with H1 bars under {UNIVERSE}"}
            continue
        try:
            res = fn()
        except Exception as exc:
            res = {"status": "UNMEASURED", "n": 0, "findings": [],
                   "why": f"{name} raised {type(exc).__name__}: {exc}"}
        out[name] = res
        if res.get("status") == "OK":
            donate(res, donor)
    donated_path = None
    if donor.rows and not dry_run:
        donated_path = INTEL / f"discoveries_{datetime.now(tz=UTC):%Y%m%dT%H%M%S}.json"
        _atomic_json(donated_path, {"source": SOURCE, "generated_at": _now(), "rule": RULE,
                                    "discoveries": donor.rows})
    report = {"at": _now(), "questions": out, "donated": len(donor.rows),
              "no_family": donor.no_family[:40], "rule": RULE, "skipped": skipped,
              "symbols": syms, "budget_s": float(budget_s),
              "elapsed_s": round(time.monotonic() - started, 2),
              "donation_file": str(donated_path) if donated_path else None,
              "proposer_seat": _seat_questions(list(out)),
              "axes_skipped": _CACHE.get("axes_skipped", {})}
    if not dry_run:
        _atomic_json(REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the desk's six standing questions")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--symbols", type=int, default=25, help="how many instruments to ask about")
    ap.add_argument("--budget-s", type=float, default=240.0, help="wall budget for the pass")
    a = ap.parse_args(argv)
    r = run(n_symbols=a.symbols, budget_s=a.budget_s, dry_run=a.dry_run)
    print(f"STANDING QUESTIONS  {len(r['symbols'])} instruments, {r['elapsed_s']}s of "
          f"{r['budget_s']:g}s budget")
    for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6"):
        d = r["questions"].get(q, {})
        print(f"  {q} {d.get('status')!s:10s} n={d.get('n')!s:>7s}  {str(d.get('why'))[:86]}")
    print(f"  donated {r['donated']} row(s) to the intake; {len(r['no_family'])} finding(s) map "
          f"to no registered family")
    print(f"  skipped: {r['skipped'] or 'none'}")
    print("  " + (f"donation: {r['donation_file']}" if r["donation_file"]
                  else ("dry run, nothing written" if a.dry_run else f"report: {REPORT}")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
