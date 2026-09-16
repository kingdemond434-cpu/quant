"""ALPHA DECAY / HAZARD ENGINE -- P(this edge is dead in twenty more trades | the state it is in).

WHAT THE DESK ALREADY HAD, AND WHY IT IS NOT THIS. `decay_monitor` judges an alpha the moment the
evidence of harm is in: trailing t <= 0 at n >= 20 fades it, t <= -2.5 retires it, a -25R drawdown
retires it at any n, a losing family pool fades every sleeve in it. Those rules are CORRECT, they
are the desk's own definition of death -- and they are, by construction, a POST-MORTEM. The
verdict lands on the trade that crosses the bar; the capital rode every trade before it. The
model half of that file fits a half-life in CALENDAR days, which answers "how fast is the
expectancy sliding" and not "what is the chance the bar itself is crossed in the next twenty
fills" -- the question the successor search actually needs answered.

THIS FILE ANSWERS THAT ONE, as a DISCRETE-TIME HAZARD fitted on the desk's own history of dying
and surviving. Every shadow ledger is sliced into windows; each window ALIVE at its start is one
training row -- features then, label = did the rule fire within the next k=20 observations. The
rule is not a new bar invented here: the constants come from `decay_monitor` BY IMPORT, copied
with attribution only where this module cannot import it. The fit is a ridge logistic in numpy
alone, intercept unpenalised, features z-scored on the training set. Below MIN_TRAIN_ROWS rows,
or without both classes present, there is NO fit: the fallback is the ANALYTIC chance the
trailing t drifts to or below zero over k more draws at the observed variance, and every card
carries its `basis`, because a number whose provenance is invisible gets read as a measurement.

WHAT IT MAY NOT DO, AND DOES NOT DO: size, fade, retire, veto or delay anything -- no roster
write, no risk_frac, no close queue. GROWTH GOVERNANCE Rule 1 says a risk reduction must first
prove it raises robust forward E[log W]; this file proves nothing of the sort and so reduces
nothing. It REPORTS (reports/ALPHA_HAZARD.json) and it QUEUES
(data/hypotheses/successor_queue.jsonl): an AMBER or RED reading starts the hunt for a successor
WHILE THE INCUMBENT IS STILL EARNING -- more independent bets inside the same heat, never a
smaller book. The kill stays in `decay_monitor`, on its unchanged bars. And absence is a reading:
a missing roster, an unparseable state, an alpha with no trades is an UNMEASURED card with its n,
never a clean GREEN and never a crash (L1.28a).

CLI: `python hazard_engine.py` writes and queues; `--dry-run` prints only; `--k N` sets the
horizon (20 = N_MIN_VERDICT, the n at which the desk's own verdict becomes sayable at all).
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
DECAY_ACTIONS = BASE / "data" / "decay_actions.jsonl"
SHADOW_DIR = BASE / "reports" / "shadow"
SHADOW_STATE = SHADOW_DIR / "shadow_state.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
COST_SURFACE = BASE / "data" / "cost_surface.json"
REGIME_STATE = BASE / "data" / "regime_state.json"
OUT = BASE / "reports" / "ALPHA_HAZARD.json"
QUEUE = BASE / "data" / "hypotheses" / "successor_queue.jsonl"

try:
    # imported as research.hazard_engine
    from research import decay_monitor as _dm
except ImportError:
    try:
        # run from inside desks/mt5/research
        import decay_monitor as _dm  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - no desk on the path
        _dm = None  # type: ignore[assignment]

if _dm is not None:
    N_MIN_VERDICT, T_PROMOTE, DD_HARD_R = _dm.N_MIN_VERDICT, _dm.T_PROMOTE, _dm.DD_HARD_R
    POOL_FADE_N, POOL_FADE_T = _dm.POOL_FADE_N, _dm.POOL_FADE_T
    TRAIL_MAX_TRADES = _dm.TRAIL_MAX_TRADES
    CONSTANTS_BASIS = "imported from research.decay_monitor"
else:  # pragma: no cover - copied from research/decay_monitor.py, which stays the authority
    N_MIN_VERDICT, T_PROMOTE, DD_HARD_R = 20, 2.5, -25.0
    POOL_FADE_N, POOL_FADE_T, TRAIL_MAX_TRADES = 20, -1.5, 60
    CONSTANTS_BASIS = "copied from research/decay_monitor.py (import unavailable)"

#: The horizon in observations: N_MIN_VERDICT, so "within the next k" is "before the next verdict".
K_DEFAULT = 20
#: Bands on p_die_k -- bands, not actions. Nothing downstream may size on them.
RED_P, AMBER_P = 0.5, 0.25
#: Posterior shrink on mean R: n/(n+30). Promotion wants 50 trades (or 20 at t >= +2.5), so a
#: 30-trade record is pulled halfway to zero and a 5-trade one nearly all the way.
SHRINK_N = 30
#: Fit floors: below either, the fit is REFUSED and the empirical rule is labelled on every card.
MIN_TRAIN_ROWS, MIN_TRAIN_POS = 40, 5
#: Trades of history a window start needs before its trailing t means anything; ridge strength.
MIN_HIST_TRADES, L2 = 8, 1.0
#: Timestamp/R keys, mirrored from decay_monitor: the live ledger stamps `time`, forward ledgers
#: `exit_time`, the scalp lane `closed_at`. The close is preferred: the R is realised there.
_TIME_KEYS = ("time", "close_time", "exit_time", "closed_at", "entry_time", "opened_at")
_R_KEYS = ("r_multiple", "r", "R")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
#: The features every alpha has; the optional ones join only when their input file parses.
BASE_FEATURES = ("trailing_t", "mean_r", "drawdown_r", "age_trades", "family_pooled_t")


# --------------------------------------------------------------------------- tolerant readers
def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return default


def _read_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text("utf-8-sig").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else None
        except ValueError:
            row = None
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _row_time(row: dict) -> datetime | None:
    for key in _TIME_KEYS:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    return None


def _row_r(row: dict) -> float | None:
    for key in _R_KEYS:
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _pairs(rows: list[dict]) -> list[tuple[datetime, float]]:
    """(time, R) oldest first. A row whose R cannot be reconstructed is dropped, never zeroed."""
    out = [(_row_time(r) or _EPOCH, _row_r(r)) for r in rows if isinstance(r, dict)]
    return sorted([(t, float(r)) for t, r in out if r is not None], key=lambda p: p[0])


# ------------------------------------------------------------------ the desk's own death rule
def stats(rs: list[float]) -> dict:
    """n, mean R, t, and drawdown from peak cumulative R. Mirrored from `decay_monitor.stats`,
    degenerate case included: zero variance with a nonzero mean is CERTAINTY, not insignificance
    (25 identical losses is as significant as evidence gets)."""
    n = len(rs)
    out = {"n": n, "mean_r": 0.0, "t": 0.0, "dd_r": 0.0, "cum_r": 0.0}
    if not n:
        return out
    cum = peak = dd = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    mean = sum(rs) / n
    out.update({"mean_r": mean, "cum_r": cum, "dd_r": dd})
    if n >= 2:
        var = sum((x - mean) ** 2 for x in rs) / (n - 1)
        if var > 0:
            out["t"] = mean / math.sqrt(var / n)
        elif mean != 0.0:
            out["t"] = 99.0 if mean > 0 else -99.0
    return out


def dies(rs: list[float]) -> tuple[bool, str]:
    """Does the desk's own demotion rule fire on this trailing window? `decay_monitor`'s
    FADE/RETIRE ladder, minus its EARLY_FADE rung (a size action below the statistical bar, not a
    death) and minus the pooled verdict, which is a property of the FAMILY and is checked against
    the pool index instead of this one series."""
    s = stats(rs[-TRAIL_MAX_TRADES:])
    if s["dd_r"] <= DD_HARD_R:
        return True, f"trailing maxDD {s['dd_r']:.1f}R breaches the {DD_HARD_R}R hard rail"
    if s["n"] >= N_MIN_VERDICT and (s["t"] <= 0.0 or s["mean_r"] < 0.0):
        return True, (f"trailing t={s['t']:.2f}, exp={s['mean_r']:.3f}R over n={s['n']} >= "
                      f"{N_MIN_VERDICT}: the edge is statistically absent")
    return False, ""


def pool_dies(pool_n: int, pool_t: float) -> bool:
    """`decay_monitor`'s pooled fade: a family at POOL_FADE_N with t <= POOL_FADE_T fades every
    live sleeve in it, whatever any single sleeve's own thin record says."""
    return pool_n >= POOL_FADE_N and pool_t <= POOL_FADE_T


class Pool:
    """Prefix sums of R by family and by clock, so the pooled t of a family at any instant -- with
    or without one of its own clocks -- is a bisect and a subtraction. The training loop asks at
    every window start, and a leak-free pooled feature is worth the lines: the lazy alternative,
    pooling the family's WHOLE record into a historical row, tells the model the future."""

    def __init__(self) -> None:
        self._fam: dict[str, tuple] = {}
        self._clock: dict[tuple[str, str], tuple] = {}

    @staticmethod
    def _index(rows: list[tuple[datetime, float]]) -> tuple[list, list, list, list]:
        times, ns, s1, s2 = [], [0], [0.0], [0.0]
        for t, r in sorted(rows, key=lambda p: p[0]):
            times.append(t)
            ns.append(ns[-1] + 1)
            s1.append(s1[-1] + r)
            s2.append(s2[-1] + r * r)
        return times, ns, s1, s2

    @classmethod
    def build(cls, series_by_id: dict[str, dict]) -> Pool:
        pool, by_fam = cls(), {}
        for clock_id, entry in series_by_id.items():
            fam = str(entry.get("family") or "?")
            rows = list(entry.get("series") or [])
            by_fam.setdefault(fam, []).extend(rows)
            pool._clock[(fam, clock_id)] = cls._index(rows)
        pool._fam = {fam: cls._index(rows) for fam, rows in by_fam.items()}
        return pool

    @staticmethod
    def _cum(idx: tuple | None, at: datetime) -> tuple[int, float, float]:
        if not idx:
            return 0, 0.0, 0.0
        i = bisect.bisect_right(idx[0], at)
        return idx[1][i], idx[2][i], idx[3][i]

    def pooled(self, family: str, clock_id: str, at: datetime,
               exclude_own: bool = True) -> tuple[int, float]:
        """(n, t) over the family's trades at or before `at`, optionally without `clock_id`'s."""
        n, s1, s2 = self._cum(self._fam.get(family), at)
        if exclude_own:
            cn, c1, c2 = self._cum(self._clock.get((family, clock_id)), at)
            n, s1, s2 = n - cn, s1 - c1, s2 - c2
        if n < 2:
            return n, 0.0
        mean = s1 / n
        var = max(0.0, (s2 - n * mean * mean) / (n - 1))
        if var <= 0.0:                      # degenerate certainty, as decay_monitor reads it
            return n, (99.0 if mean > 0 else (-99.0 if mean < 0 else 0.0))
        return n, mean / math.sqrt(var / n)


# ----------------------------------------------------------------------------- series and alphas
def _ledger_index(directory: Path | None = None) -> dict[str, Path]:
    """Lowercased basename -> path for every shadow ledger. Case matters in the ledger names
    (`ledger_EURGBP_discovered_asia.json`) and not in the roster's sleeve names."""
    try:
        return {p.name.lower(): p for p in (directory or SHADOW_DIR).glob("ledger_*.json")}
    except OSError:
        return {}


def clock_ident(key: str) -> tuple[str, str, str]:
    """(symbol, family, window) from a shadow_state key. `XAUUSD.asia` is the desk's own
    session_range_breakout naming, `#params` is a variant suffix on the same mechanism."""
    parts = [p for p in str(key).split("#", 1)[0].split(".") if p]
    if not parts:
        return "", "?", ""
    if len(parts) == 1:
        return parts[0], "?", ""
    if len(parts) == 2:
        return parts[0], "session_range_breakout", parts[1]
    return parts[0], parts[1], parts[2]


def ledger_basename(symbol: str, family: str, window: str) -> str:
    """`shadow_forward`'s own file naming, mirrored (shadow_forward.py:729-730)."""
    if family in ("session_range_breakout", "", "?"):
        return f"ledger_{symbol}_{window}.json"
    return f"ledger_{symbol}_{family}_{window}.json"


def roster_rows(doc: Any) -> dict[str, dict]:
    """Every roster row by name, in BOTH shapes -- the promoter writes a list, older organs a
    dict. Mirrored from `decay_monitor.roster_rows`: the shapes are the file's, not this file's."""
    if not isinstance(doc, dict):
        return {}
    sl = doc.get("sleeves")
    if isinstance(sl, list):
        return {str(r["name"]): r for r in sl if isinstance(r, dict) and r.get("name")}
    if isinstance(sl, dict):
        return {str(k): v for k, v in sl.items() if isinstance(v, dict)}
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)}


def _ledger_series(path: Path) -> tuple[list[tuple[datetime, float]], str]:
    rows = _read_json(path, [])
    if not isinstance(rows, list):
        return [], "unreadable"
    fwd = _pairs([r for r in rows if isinstance(r, dict) and r.get("phase") == "forward"])
    if len(fwd) >= MIN_HIST_TRADES:
        return fwd, "shadow_forward"
    every = _pairs([r for r in rows if isinstance(r, dict)])
    return (every, "shadow_all") if len(every) > len(fwd) else (fwd, "shadow_forward")


def collect_series() -> dict[str, dict]:
    """Every R series the desk holds, by clock id: one per shadow ledger, plus one per live sleeve
    whose own fills are the better record. Training, the pool index and the cards all read this
    one dict, so no series is counted twice and no file is read twice."""
    out: dict[str, dict] = {}
    state = _read_json(SHADOW_STATE, {})
    by_file: dict[str, tuple[str, str, str]] = {}
    for key, row in (state if isinstance(state, dict) else {}).items():
        if isinstance(row, dict):
            sym, fam, win = clock_ident(key)
            by_file.setdefault(ledger_basename(sym, fam, win).lower(), (sym, fam, win))
    for lname, path in sorted(_ledger_index().items()):
        sym, fam, win = by_file.get(lname, ("", "?", ""))
        if not sym:  # a ledger with no clock of its own: read its identity off the filename
            parts = lname[len("ledger_"):-len(".json")].split("_")
            sym, win = parts[0].upper(), (parts[-1] if len(parts) > 1 else "")
            fam = "_".join(parts[1:-1]) or ("session_range_breakout" if len(parts) > 1 else "?")
        series, basis = _ledger_series(path)
        out[lname] = {"symbol": sym, "family": fam, "window": win, "basis": basis,
                      "series": series}
    live_rows = _read_jsonl(LIVE_LEDGER)
    for name, row in roster_rows(_read_json(SLEEVES_FILE, {})).items():
        # The venue truncates the order comment to 29 chars ("DW" + 27), so a long roster name
        # reaches the ledger as its stem and is judged on zero trades unless both are matched.
        series = _pairs([r for r in live_rows
                         if str(r.get("sleeve") or "") in (name, str(name)[:27])])
        if series:
            out[f"live:{name}"] = {"symbol": str(row.get("symbol") or ""),
                                   "family": str(row.get("family") or "?"),
                                   "window": str(row.get("session") or ""),
                                   "basis": "live_ledger", "series": series}
    return out


def _match_ledger(name: str, symbol: str, ledgers: dict[str, Path]) -> str:
    """The forward ledger a roster row belongs to when the row does not name its own window.

    A JOIN BY DERIVED IDENTITY (L0346), because the promoter's sleeve names carry the mechanism
    and the window (`usdjpy_session_range_breakout_asia_5_wb_12`) while the roster row it writes
    often carries a null `session` -- and the desk's ledger files carry both too. The longest
    ledger tail that appears in the sleeve name wins, so `discovered_asia` beats a bare `asia`.
    A join is a guess: the card publishes `series_id` and `series_basis` so a wrong one is
    visible rather than silently attributing another clock's trades to this sleeve."""
    low, best, best_len = str(name).lower(), "", 0
    for lname in ledgers:
        sym_part, _, rest = lname[len("ledger_"):-len(".json")].partition("_")
        if sym_part != symbol.lower() or not rest:
            continue
        if rest in low and len(rest) > best_len:
            best, best_len = lname, len(rest)
    return best


def collect_alphas(series_by_id: dict[str, dict]) -> list[dict]:
    """Every LIVE/STANDBY sleeve (lane `live`) and every ACTIVE forward clock (lane `forward`),
    each bound to the series that is its own best record."""
    alphas: list[dict] = []
    ledgers = _ledger_index()
    for name, row in sorted(roster_rows(_read_json(SLEEVES_FILE, {})).items()):
        if str(row.get("status") or "").upper() not in ("LIVE", "STANDBY"):
            continue
        sym, fam = str(row.get("symbol") or ""), str(row.get("family") or "?")
        win = str(row.get("session") or "")
        clock_id = f"live:{name}" if f"live:{name}" in series_by_id else ""
        for cand in () if clock_id else (f"ledger_{name}.json", ledger_basename(sym, fam, win),
                                         ledger_basename(sym, "?", win),
                                         _match_ledger(name, sym, ledgers)):
            if cand and cand.lower() in ledgers and cand.lower() in series_by_id:
                clock_id = cand.lower()
                break
        alphas.append({"name": name, "lane": "live", "symbol": sym, "family": fam, "window": win,
                       "clock_id": clock_id, "row": row})
    state = _read_json(SHADOW_STATE, {})
    for key, row in sorted((state if isinstance(state, dict) else {}).items()):
        if not isinstance(row, dict) or str(row.get("status") or "").upper() != "ACTIVE":
            continue
        sym, fam, win = clock_ident(key)
        lname = ledger_basename(sym, fam, win).lower()
        alphas.append({"name": key, "lane": "forward", "symbol": sym, "family": fam,
                       "window": win, "clock_id": lname if lname in series_by_id else "",
                       "row": row})
    return alphas


# ------------------------------------------------------------------------------------- features
def optional_features() -> tuple[tuple[str, ...], dict[str, Any]]:
    """Which optional features this run has inputs for, and the inputs. A feature whose file is
    absent or unreadable is OMITTED for the whole run -- train and score must see the same
    columns, and a silently-zeroed column is a lie about what was measured."""
    names: list[str] = []
    ctx: dict[str, Any] = {}
    syms = (_read_json(COST_SURFACE, {}) or {}).get("symbols")
    if isinstance(syms, dict) and any(isinstance(v, dict) and "stress_p90_over_p50" in v
                                      for v in syms.values()):
        ctx["cost"] = syms
        names.append("cost_stress")
    sleeves = (_read_json(REGIME_STATE, {}) or {}).get("sleeves")
    if isinstance(sleeves, dict) and sleeves:
        ctx["regime"] = sleeves
        names.append("regime_flagged")
    return tuple(names), ctx


def feature_row(series: list[tuple[datetime, float]], at: int, family: str, clock_id: str,
                symbol: str, window: str, pool: Pool, optional: tuple[str, ...],
                ctx: dict[str, Any]) -> dict[str, float]:
    """The state of one alpha at observation `at` (exclusive), in the model's own units."""
    rs = [r for _, r in series[:at]]
    trail, whole = stats(rs[-N_MIN_VERDICT:]), stats(rs)
    pool_n, pool_t = pool.pooled(family, clock_id, series[at - 1][0] if at else _EPOCH)
    row = {"trailing_t": trail["t"], "mean_r": trail["mean_r"], "drawdown_r": whole["dd_r"],
           "age_trades": float(at), "family_pooled_t": pool_t if pool_n >= 2 else 0.0}
    if "cost_stress" in optional:
        entry = (ctx.get("cost") or {}).get(symbol)
        value = entry.get("stress_p90_over_p50") if isinstance(entry, dict) else None
        row["cost_stress"] = float(value) if isinstance(value, (int, float)) else 1.0
    if "regime_flagged" in optional:
        key = f"{symbol}|{family}_{window}" if window else f"{symbol}|{family}"
        entry = (ctx.get("regime") or {}).get(key)
        flag = str(entry.get("flag") or "ok") if isinstance(entry, dict) else "ok"
        row["regime_flagged"] = 0.0 if flag in ("ok", "") else 1.0
    return row


# ------------------------------------------------------------------------------------- training
def _recorded_deaths(name: str, series: list[tuple[datetime, float]]) -> set[int]:
    """Indices at which the desk ACTUALLY faded or retired this alpha, from decay_actions.jsonl.
    The only labels here that are not inferred from the rule."""
    out: set[int] = set()
    times = [t for t, _ in series]
    for row in _read_jsonl(DECAY_ACTIONS):
        if str(row.get("sleeve") or "") != name:
            continue
        if str(row.get("action") or "").upper() not in ("FADE", "RETIRE"):
            continue
        when = _row_time({"time": row.get("at")})
        idx = bisect.bisect_left(times, when) if when else -1
        if 0 < idx <= len(series):
            out.add(idx)
    return out


def _fires_within(series: list[tuple[datetime, float]], at: int, k: int, family: str,
                  clock_id: str, pool: Pool, deaths: set[int]) -> bool:
    """Did the rule fire on any of the next k observations -- own ladder, pooled family fade, or a
    RECORDED demotion landing inside the window?"""
    for j in range(at + 1, min(at + k, len(series)) + 1):
        if j in deaths or dies([r for _, r in series[:j]])[0]:
            return True
        if pool_dies(*pool.pooled(family, clock_id, series[j - 1][0], exclude_own=False)):
            return True
    return False


def training_rows(series_by_id: dict[str, dict], alphas: list[dict], pool: Pool, k: int,
                  optional: tuple[str, ...], ctx: dict[str, Any]
                  ) -> tuple[list[dict], list[int], dict]:
    """One row per window ALIVE at its start: features then, label = did the rule fire within k.
    A window already dead at its start is dropped -- the hazard is conditional on being alive, and
    a dead alpha's next twenty trades are evidence about nothing."""
    names = {a["clock_id"]: a["name"] for a in alphas if a["clock_id"]}
    xs: list[dict] = []
    ys: list[int] = []
    n_recorded = 0
    for clock_id, entry in sorted(series_by_id.items()):
        series, fam = entry["series"], str(entry.get("family") or "?")
        deaths = _recorded_deaths(names.get(clock_id, ""), series) if clock_id in names else set()
        n_recorded += len(deaths)
        for at in range(MIN_HIST_TRADES, len(series) - k + 1):
            if dies([r for _, r in series[:at]])[0]:
                continue
            xs.append(feature_row(series, at, fam, clock_id, str(entry.get("symbol") or ""),
                                  str(entry.get("window") or ""), pool, optional, ctx))
            ys.append(int(_fires_within(series, at, k, fam, clock_id, pool, deaths)))
    meta = {"n_rows": len(xs), "n_positive": sum(ys), "n_clocks": len(series_by_id),
            "n_recorded_actions": n_recorded, "horizon_k": k,
            "window_floor_trades": MIN_HIST_TRADES}
    return xs, ys, meta


# ---------------------------------------------------------------------------------- the model
def fit_logistic(xm: np.ndarray, y: np.ndarray, l2: float = L2,
                 iters: int = 60) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ridge logistic regression by Newton steps. Returns (w, mu, sd): the weights act on the
    z-scored design, so a caller must standardise with the SAME mu/sd. The intercept is
    unpenalised; a zero-variance column gets sd 1 and contributes nothing, which is what a column
    that never varied is worth."""
    mu, sd = xm.mean(axis=0), xm.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    z = np.hstack([np.ones((len(xm), 1)), (xm - mu) / sd])
    w = np.zeros(z.shape[1])
    ridge = np.eye(z.shape[1]) * l2
    ridge[0, 0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(z @ w, -30.0, 30.0)))
        grad = z.T @ (p - y) + ridge @ w
        hess = (z * np.clip(p * (1.0 - p), 1e-6, None)[:, None]).T @ z + ridge
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:  # pragma: no cover - the ridge makes this all but unreachable
            step = np.linalg.lstsq(hess, grad, rcond=None)[0]
        if not np.all(np.isfinite(step)):  # pragma: no cover - guarded by the ridge
            break
        w, done = w - step, float(np.max(np.abs(step))) < 1e-9
        if done:
            break
    return w, mu, sd


def predict(w: np.ndarray, mu: np.ndarray, sd: np.ndarray, x: dict,
            names: tuple[str, ...]) -> float:
    vec = np.array([float(x.get(n, 0.0)) for n in names], dtype=float)
    z = float(np.clip(np.concatenate([[1.0], (vec - mu) / sd]) @ w, -30.0, 30.0))
    return float(1.0 / (1.0 + math.exp(-z)))


def empirical_p_die(t: float, n: int, k: int) -> float:
    """THE FALLBACK, and it is arithmetic rather than a model: the chance the trailing t is at or
    below zero at some point within k more draws, at the observed variance.

    Future draws are iid with the POSTERIOR mean (mean R shrunk n/(n+SHRINK_N)) and the observed
    variance s^2; the true mean carries its own s^2/n of uncertainty. The trailing mean after j
    more draws is then Normal, and s cancels to leave a function of t, n and j alone:

        z_j = t * n * (1 + j/(n+SHRINK_N)) / sqrt(j*(n+j)),   P(t_j <= 0) = Phi(-z_j)

    WITHIN k, NOT AT k, and the difference is the whole point: the desk's rule fires the first
    time the bar is crossed, so the horizon may only ever RAISE the hazard. The largest
    single-horizon crossing probability inside the window is taken -- a lower bound on the true
    first-passage probability (it ignores the other paths that cross and come back), monotone in
    k the way a within-k hazard must be, and never above the max of terms it is drawn from. A
    horizon too short for the bar to be reachable (n + j < N_MIN_VERDICT) contributes nothing:
    the rule cannot fire there, and a hazard for an event that cannot happen is not a small
    number, it is zero."""
    if n < 1 or k < 1:
        return 0.0
    best = 0.0
    for j in range(1, k + 1):
        if n + j < N_MIN_VERDICT:
            continue
        z = t * (n * (1.0 + j / (n + SHRINK_N))) / math.sqrt(j * (n + j))
        best = max(best, 0.5 * (1.0 + math.erf(-z / math.sqrt(2.0))))
    return best


def calibration(ps: list[float], ys: list[int]) -> dict:
    """In-sample only, and labelled as such: Brier against the base rate's Brier. A model that
    cannot beat "always predict the base rate" on its own training data has learned nothing."""
    if not ys:
        return {"scope": "in_sample", "n": 0, "brier": None, "base_rate": None, "skill": None}
    base = sum(ys) / len(ys)
    brier = sum((p - y) ** 2 for p, y in zip(ps, ys, strict=True)) / len(ys)
    base_brier = sum((base - y) ** 2 for y in ys) / len(ys)
    return {"scope": "in_sample", "n": len(ys), "brier": round(brier, 5),
            "base_rate": round(base, 4), "base_brier": round(base_brier, 5),
            "skill": None if base_brier <= 0 else round(1.0 - brier / base_brier, 4)}


# --------------------------------------------------------------------------------- the cards
def health_of(p: float | None) -> str:
    if p is None:
        return "UNMEASURED"
    return "RED" if p >= RED_P else ("AMBER" if p >= AMBER_P else "GREEN")


def _asset_class(symbol: str) -> str:
    """`universe_policy`'s asset class, "" when the desk cannot classify the symbol. Wrapped so
    the import cannot take a report down, and so a test can point it at its own registry."""
    if not symbol:
        return ""
    try:
        try:
            from research.universe_policy import asset_class_of
        except ImportError:
            from universe_policy import asset_class_of  # type: ignore[no-redef]
        return str(asset_class_of(symbol) or "")
    except Exception:  # never crash a report over a classifier
        return ""


def replacement_candidates(symbol: str, family: str, taken: set[tuple[str, str]],
                           survivors: dict, limit: int = 3) -> list[dict]:
    """Up to `limit` certified cells in the same ASSET CLASS (universe_policy's answer, never a
    symbol list) carrying a DIFFERENT family and not already live or forward. A re-parameterised
    incumbent is not a successor: the payer IT monetised is the one drying up."""
    klass = _asset_class(symbol)
    if not klass:
        return []
    out: list[dict] = []
    for key, row in sorted(survivors.items()):
        spec = (row.get("shadow_spec") or {}) if isinstance(row, dict) else {}
        sym = str(spec.get("symbol") or (row.get("sym") if isinstance(row, dict) else "") or "")
        fam = str(spec.get("family") or "")
        if not sym or not fam or fam == family or (sym, fam) in taken:
            continue
        if _asset_class(sym) != klass or any(c["symbol"] == sym and c["family"] == fam
                                             for c in out):
            continue
        out.append({"cell": key, "symbol": sym, "family": fam, "asset_class": klass,
                    "hunt": row.get("hunt"), "days": row.get("days")})
        if len(out) >= limit:
            break
    return out


def _capacity_note(row: dict, lane: str) -> str:
    if lane != "live":
        return "forward clock: carries no capital yet, so no capacity is at risk"
    lot, frac = row.get("lot"), row.get("risk_frac")
    if lot is None and frac is None:
        return "roster row carries neither lot nor risk_frac: capacity UNMEASURED"
    return f"lot={lot}, risk_frac={frac}{' (decay_faded)' if row.get('decay_faded') else ''}"


def _card(alpha: dict, series_by_id: dict[str, dict], pool: Pool, k: int, names: tuple[str, ...],
          optional: tuple[str, ...], ctx: dict[str, Any], fitted: tuple | None, basis: str,
          taken: set[tuple[str, str]], survivors: dict) -> dict:
    entry = series_by_id.get(alpha["clock_id"]) or {}
    series = list(entry.get("series") or [])
    fam = alpha["family"]
    card: dict[str, Any] = {
        "name": alpha["name"], "lane": alpha["lane"], "symbol": alpha["symbol"], "family": fam,
        "n": len(series), "trailing_t": None, "mean_r": None, "drawdown_r": None,
        "posterior_edge": None, "p_die_k": None, "k": k, "health": "UNMEASURED",
        "capacity": _capacity_note(alpha["row"], alpha["lane"]), "replacement_candidates": [],
        "basis": "", "series_basis": str(entry.get("basis") or "none"),
        "series_id": alpha["clock_id"] or None}
    if not series:
        card["basis"] = ("UNMEASURED: no trade series for this alpha (no live fills, no forward "
                         "ledger) -- absence is a reading, not a clean bill of health")
        return card
    rs = [r for _, r in series]
    trail, whole = stats(rs[-N_MIN_VERDICT:]), stats(rs)
    x = feature_row(series, len(series), fam, alpha["clock_id"], alpha["symbol"], alpha["window"],
                    pool, optional, ctx)
    pool_n, pool_t = pool.pooled(fam, alpha["clock_id"], series[-1][0], exclude_own=False)
    already, why = dies(rs)
    if not already and pool_dies(pool_n, pool_t):
        already, why = True, (f"pooled {fam}: t={pool_t:.2f} over n={pool_n}, at or under the "
                              f"{POOL_FADE_T} family bar")
    if already:
        p, how = 1.0, f"the desk's rule ALREADY fires: {why}"
    elif basis == "logistic" and fitted is not None:
        p = predict(fitted[0], fitted[1], fitted[2], x, names)
        how = f"logistic hazard over k={k} on {list(names)}"
    else:
        p = empirical_p_die(trail["t"], trail["n"], k)
        how = (f"empirical (analytic) rule over k={k}: t={trail['t']:.2f} at n={trail['n']}, "
               f"posterior shrink n/(n+{SHRINK_N})")
    card.update({
        "trailing_t": round(trail["t"], 3), "mean_r": round(trail["mean_r"], 4),
        "drawdown_r": round(whole["dd_r"], 3), "p_die_k": round(p, 4), "health": health_of(p),
        "posterior_edge": round(whole["mean_r"] * whole["n"] / (whole["n"] + SHRINK_N), 4),
        "basis": how, "family_pooled": {"n": pool_n, "t": round(pool_t, 3)},
        "features": {n: round(float(v), 4) for n, v in x.items()}})
    if card["health"] in ("AMBER", "RED"):
        card["replacement_candidates"] = replacement_candidates(alpha["symbol"], fam, taken,
                                                                survivors)
        if not card["replacement_candidates"]:
            # An empty list is a READING, not a shrug: measured 2026-09-16, all 28 certified
            # (symbol, family) pairs in UNIVERSAL_SURVIVORS were already live or forward, so
            # there was nothing on the shelf to swap in -- which is exactly why the hunt is
            # queued rather than a swap proposed.
            card["replacement_note"] = (
                f"no certified cell in asset class '{_asset_class(alpha['symbol']) or '?'}' "
                f"carries a family other than '{fam}' that is not already live or forward")
    return card


def build_cards(k: int = K_DEFAULT) -> tuple[list[dict], dict]:
    """Every card, and the model that priced them. Reads; writes nothing."""
    series_by_id = collect_series()
    alphas = collect_alphas(series_by_id)
    pool = Pool.build(series_by_id)
    optional, ctx = optional_features()
    names = (*BASE_FEATURES, *optional)
    xs, ys, meta = training_rows(series_by_id, alphas, pool, k, optional, ctx)
    model: dict[str, Any] = {
        "basis": "empirical", "n_train": len(xs), "features": list(names),
        "constants_basis": CONSTANTS_BASIS, "training": meta, "coefficients": None,
        "calibration": None,
        "rule": (f"p_die = max over j<=k of Phi(-t*n*(1 + j/(n+{SHRINK_N}))/sqrt(j*(n+j))): the "
                 f"analytic chance the trailing t drifts to or below zero WITHIN k more draws at "
                 f"the observed variance, floored at the horizons where n+j < {N_MIN_VERDICT} "
                 f"and the desk's bar cannot fire at all")}
    fitted = None
    if len(xs) >= MIN_TRAIN_ROWS and MIN_TRAIN_POS <= sum(ys) <= len(ys) - MIN_TRAIN_POS:
        xm = np.array([[float(x.get(n, 0.0)) for n in names] for x in xs], dtype=float)
        w, mu, sd = fit_logistic(xm, np.array(ys, dtype=float))
        fitted = (w, mu, sd)
        model.update({
            "basis": "logistic",
            "coefficients": {"intercept": round(float(w[0]), 5),
                             **{n: round(float(v), 5)
                                for n, v in zip(names, w[1:], strict=True)}},
            "standardisation": {n: [round(float(m), 5), round(float(s), 5)]
                                for n, m, s in zip(names, mu, sd, strict=True)},
            "calibration": calibration([predict(w, mu, sd, x, names) for x in xs], ys),
            "rule": (f"ridge logistic (l2={L2}, intercept unpenalised) on z-scored {list(names)}, "
                     f"fitted on {len(xs)} alive-at-start windows of the desk's own ledgers; "
                     f"label = the decay_monitor rule fires within k={k}")})
    else:
        model["why_empirical"] = (
            f"{len(xs)} training row(s) with {sum(ys)} positive(s): the fit needs "
            f"{MIN_TRAIN_ROWS} rows and {MIN_TRAIN_POS} of each class. The empirical rule is "
            f"LABELLED on every card -- a logistic fitted on this would be a decoration")
    survivors = (_read_json(SURVIVORS, {}) or {}).get("survivors")
    taken = {(a["symbol"], a["family"]) for a in alphas}
    cards = [_card(a, series_by_id, pool, k, names, optional, ctx, fitted, model["basis"], taken,
                   survivors if isinstance(survivors, dict) else {}) for a in alphas]
    return cards, model


# ---------------------------------------------------------------------------- the successor hunt
def queue_successors(cards: list[dict], now: str, path: Path | None = None) -> list[dict]:
    """One `successor_search` per AMBER/RED alpha, deduped by name per day. THE HUNT BEFORE THE
    KILL THRESHOLD: the incumbent keeps every unit of its capital and the desk starts looking for
    what replaces it while it is still earning."""
    p = path or QUEUE
    seen = {(str(r.get("for") or ""), str(r.get("at") or "")[:10]) for r in _read_jsonl(p)}
    rows = []
    for c in cards:
        if c["health"] not in ("AMBER", "RED") or (c["name"], now[:10]) in seen:
            continue
        seen.add((c["name"], now[:10]))
        rows.append({"kind": "successor_search", "for": c["name"], "symbol": c["symbol"],
                     "family": c["family"],
                     "why": (f"p_die(k={c['k']})={c['p_die_k']} [{c['health']}]: trailing "
                             f"t={c['trailing_t']} over n={c['n']}, mean {c['mean_r']}R, "
                             f"drawdown {c['drawdown_r']}R -- {c['basis']}"),
                     "at": now, "lane": c["lane"],
                     "replacement_candidates": c["replacement_candidates"],
                     "note": ("hunt only: nothing is faded, resized or retired by this row; the "
                              "kill stays with decay_monitor on its unchanged bars")})
    if rows:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
    return rows


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, "utf-8")
    try:
        os.replace(tmp, path)
    except OSError:  # pragma: no cover - read-only/locked target: legal on POSIX, WinError 5 here
        path.write_text(payload, "utf-8")
        tmp.unlink(missing_ok=True)


RULE = (f"p_die_k = P(the decay_monitor demotion rule fires within k observations | the state "
        f"now), the rule being its own: trailing t <= 0 or exp < 0 at n >= {N_MIN_VERDICT}, a "
        f"{DD_HARD_R}R trailing drawdown at any n, or a pooled family t <= {POOL_FADE_T} at "
        f"n >= {POOL_FADE_N}. RED at p >= {RED_P}, AMBER at p >= {AMBER_P}. This organ reports "
        f"and queues a successor hunt; it never sizes, fades or retires anything (GROWTH "
        f"GOVERNANCE Rule 1: a reduction must first prove it raises robust forward E[log W]).")


def main(k: int = K_DEFAULT, dry_run: bool = False) -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    cards, model = build_cards(k)
    by_health: dict[str, int] = {}
    for c in cards:
        by_health[c["health"]] = by_health.get(c["health"], 0) + 1
    queued = [] if dry_run else queue_successors(cards, now)
    if not dry_run:
        _atomic_json(OUT, {
            "at": now, "n_alphas": len(cards), "by_health": by_health, "model": model,
            "cards": cards, "queued": len(queued), "rule": RULE, "queue_path": str(QUEUE),
            "unchanged_because": None if cards else ("no alpha was readable, so identical bytes "
                                                     "are the correct output, not a stalled loop")})
    print(f"{'name':<44}{'lane':<9}{'n':>4}{'t':>8}{'p_die':>9}  health")
    for c in sorted(cards, key=lambda r: (-(r["p_die_k"] or 0.0), r["name"])):
        t = "      --" if c["trailing_t"] is None else f"{c['trailing_t']:>8.2f}"
        p = "       --" if c["p_die_k"] is None else f"{c['p_die_k']:>9.3f}"
        print(f"{c['name'][:43]:<44}{c['lane']:<9}{c['n']:>4}{t}{p}  {c['health']}")
    bands = ", ".join(f"{name}={count}" for name, count in sorted(by_health.items())) or "none"
    print(f"hazard engine: {len(cards)} alpha(s) [{bands}], basis={model['basis']} on "
          f"{model['n_train']} training row(s), {len(queued)} successor search(es) queued"
          f"{' (dry run: nothing written)' if dry_run else ''}")
    return 0


def cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Alpha decay / hazard engine (reports and queues)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the table and write neither the artifact nor the queue")
    ap.add_argument("--k", type=int, default=K_DEFAULT,
                    help=f"horizon in observations (default {K_DEFAULT} = N_MIN_VERDICT)")
    args = ap.parse_args(argv)
    return main(k=max(1, args.k), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(cli())
