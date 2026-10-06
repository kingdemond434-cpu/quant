"""SHADOW-LEDGER DISCOVERY -- the desk's own unexplained P&L, mined as an alpha dataset.

THE PRINCIPAL, 2026-09-17 (ledger M5): *the desk's own unexplained P&L is an alpha dataset.* Every
shadow clock and every live sleeve has been writing trades for weeks, and the only question the
desk ever asked of them was "did this one work". That throws away the interesting half. A trade's
R is not one number -- it is the part the desk's own model already claims plus a remainder nobody
has explained, and the remainder is where the next hypothesis lives.

    R_i = KnownFactors_i + epsilon_i

KnownFactors is not invented here. `exposure_decomposition` already decides what a factor IS on
this desk and `standing_questions` Q3 already decides how a residual is taken (OLS on [dollar
basket, gold, equity index] with an intercept, `np.linalg.lstsq`, resid = y - X beta); both are
imported, because two definitions of one residual is how two organs come to disagree about the
same book. The intercept IS the sleeve's own mean, so epsilon is what is left once the sleeve is
allowed its average edge AND the three factors are allowed theirs.

THEN THE RESIDUAL IS INTERROGATED, nine ways, each with a PERMUTATION NULL of 200 draws and a
minimum group size -- epsilon is a small, noisy, hand-picked sample and a t-test on it would
manufacture findings at exactly the rate this desk cannot afford. session and regime take the MAX
|group mean - grand mean| and take the same max UNDER THE NULL, so the multiplicity across groups
is charged rather than ignored; event_proximity, streak, mae_mfe and decay are two-sample splits
whose null shuffles membership; time_since_signal, cross_strategy and correlation_change are
correlation statistics whose null shuffles the pairing, never the returns. Beside them rides one
descriptive reading the desk asked for by name: the MFE capture ratio, which says whether an exit
is leaving money on the table.

WHAT LEAVES, AND WHAT ONLY SITS. A pattern at p < 0.05 is a measurement. A pattern that RECURS --
the same (kind, key) significant on two or more sleeves, or reproducing with the same sign in both
halves of one sleeve's own record -- is a DISCOVERY, written to the canonical registry
(source_type `shadow_ledger`, origin MOAT, state UNPROCESSED) for the discovery compiler to close.
THIS ORGAN DONATES NO CELLS: one significant split on one sleeve is a coincidence with a p-value,
and the compiler exists so the desk converts discoveries in one place against its conversion debt.

`residual_queue` is the desk's ignorance ledger and is read here (its `strategy_loss` rows join by
`sleeve_shortfall:<name>`), but it exposes NO public append path -- `build()` recollects its whole
queue from a fixed producer plan every pass -- so nothing is appended to it, the artifact says so
rather than hiding it, and new ignorance is recorded where a discovery has a disposition.

UNMEASURED IS A REAL ANSWER (L1.28a): a sleeve under 20 aligned trades is named with its count, a
test whose input the ledger does not carry is named by test and sleeve, and a factor panel that
cannot be built degrades the model to the sleeve's own mean and says so.

NOT WIRED TO A CLOCK YET (III.16, stated rather than hidden): this ships with its test and no
scheduler leg -- it must be added as an hourly leg by the session that owns hourly_cycle, or it is
a defect. `python -m research.shadow_discovery` writes the artifact; `--dry-run` writes nothing and
records nothing; `--budget-s` bounds the pass. numpy here; pandas lives in the factor builder.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry  # noqa: E402
from research import exposure_decomposition as xd  # noqa: E402
from research import hazard_engine as hz  # noqa: E402
from research import posterior_alpha as pa  # noqa: E402

SLEEVES, LIVE_LEDGER = BASE / "data" / "sleeves.json", BASE / "data" / "live_ledger.jsonl"
SHADOW_DIR = BASE / "reports" / "shadow"
SHADOW_STATE, HAZARD = SHADOW_DIR / "shadow_state.json", BASE / "reports" / "ALPHA_HAZARD.json"
REGIME_STATE, CALENDAR = BASE / "data" / "regime_state.json", BASE / "data" / "forced_flow_calendar.json"  # noqa: E501
RESIDUAL_QUEUE, EXPOSURE = BASE / "data" / "residual_queue.jsonl", BASE / "reports" / "EXPOSURE_DECOMPOSITION.json"  # noqa: E501
OUT = BASE / "reports" / "SHADOW_DISCOVERY.json"

SOURCE, UNMEASURED = "shadow_discovery", pa.UNMEASURED
#: The named factors epsilon is taken against: Q3's set, in Q3's order.
FACTOR_NAMES = ("usd", "gold", "equity_beta")
#: Below this a sleeve is UNMEASURED BY NAME. 20 is the desk's own verdict floor
#: (decay_monitor.N_MIN_VERDICT): too thin for a verdict is too thin for a residual pattern.
MIN_TRADES, MIN_GROUP, PERM_DRAWS, ALPHA = 20, 8, 200, 0.05
MIN_WINDOW_N = 10             # trades per half before "it recurred in both windows" means a thing
CROSS_MIN_DAYS, CROSS_RHO, ROLL_WINDOW = 15, 0.5, 20
FLIP_BAND = 0.2               # a rolling corr wandering across zero is noise; a FLIP clears this
TOP_TAIL = 0.05               # the unexplained tail: |epsilon| in the top 5%
EVENT_DAYS, STREAK_K, BUDGET_S, SEED = 1, 2, 240.0, 20260917
#: A factor this far behind the freshest is dropped, rather than dragging every sleeve's last days
#: out of the fit.
PANEL_STALE_DAYS = 30
_MAE_KEYS, _MFE_KEYS = ("mae_r", "mae_R", "mae"), ("mfe_r", "mfe_R", "mfe")
_LAG_KEYS = ("bars_since_signal", "signal_lag_bars", "delay_bars", "bars_to_fill")
_SIGNAL_KEYS = ("signal_time", "signal_at", "signal_utc")

RULE = ("actual minus model is the research target; a recurring residual pattern is a discovery, "
        "not a tweak")
#: What a significant pattern SUGGESTS. A suggestion is not a cell: the compiler decides.
TRANSFORM = {
    "session": "condition entry on session {key}, or split the clock into a session-specific one",
    "regime": "gate the sleeve on regime {key} and test the complement as its own cell",
    "event_proximity": "add a forced-flow event proximity filter (+-1 day) to the entry",
    "time_since_signal": "add a staleness cut on the bars between signal and fill",
    "streak": "condition entry or size on the sleeve's own streak state ({key})",
    "mae_mfe": "re-specify the exit against the measured give-back ({key})",
    "decay": "re-fit or retire: the residual's two halves are not the same sleeve",
    "cross_strategy": "one shared driver behind two sleeves: model it as a factor, not two bets",
    "correlation_change": "make the factor loading conditional; its sign is not stable",
}


def _session_bands() -> tuple[tuple[int, int, str], ...]:
    """Disjoint hour bands DERIVED from the desk's own session table, never restated.

    `family_call.SESSIONS` overlaps by design (london 8-16, ny 14-22). Cutting at every declared
    boundary partitions the day: hours two sessions both claim are `overlap` -- the desk's own
    word for them -- and hours nobody claims are `off_session`.
    """
    try:
        from mt5desk.family_call import SESSIONS as table
    except ImportError:                                          # pragma: no cover - no desk here
        table = {"asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None}
    spans = {k: (int(v[0]), int(v[1])) for k, v in table.items()
             if isinstance(v, (tuple, list)) and len(v) == 2}
    out = []
    for lo, hi in pairwise(sorted({0, 24, *(h for s in spans.values() for h in s)})):
        named = sorted(k for k, (a, b) in spans.items() if a <= lo and hi <= b)
        out.append((lo, hi, named[0] if len(named) == 1
                    else ("overlap" if named else "off_session")))
    return tuple(out)


SESSION_BANDS = _session_bands()
SESSION_KEYS = tuple(dict.fromkeys(name for _, _, name in SESSION_BANDS))


@dataclass
class Trade:
    """One trade, in the only fields a residual pattern can read."""

    r: float
    at: datetime
    day: str
    session: str
    mae: float | None = None
    mfe: float | None = None
    lag: float | None = None
    lag_unit: str = ""


@dataclass
class Sleeve:
    name: str
    lane: str
    symbol: str
    status: str = ""
    trades: list[Trade] = field(default_factory=list)


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    return next((v for k in keys if (v := pa._num(row.get(k))) is not None), None)


def _lag_of(row: dict[str, Any], at: datetime) -> tuple[float | None, str]:
    """Bars between signal and fill where the ledger counts them, else hours where it stamps the
    signal. The UNIT travels with the number: a pattern in bars and one in hours are not the same
    finding, and pretending otherwise is a mixed-unit regression."""
    bars = _first(row, _LAG_KEYS)
    if bars is not None:
        return bars, "bars"
    entry = hz._row_time({"entry_time": str(row.get("entry_time") or row.get("opened_at") or "")})
    for key in _SIGNAL_KEYS:
        stamp = hz._row_time({"time": str(row.get(key) or "")})
        if stamp is not None:
            return ((entry or at) - stamp).total_seconds() / 3600.0, "hours"
    return None, ""


def _trade_of(row: Any) -> Trade | None:
    """A ledger row in either shape the desk writes -- entry_time/exit_time/r_multiple, or
    opened_at/closed_at/r -- through hazard_engine's own key tables."""
    if not isinstance(row, dict):
        return None
    at, value = hz._row_time(row), hz._row_r(row)
    if at is None or value is None:
        return None
    lag, unit = _lag_of(row, at)
    return Trade(float(value), at, at.date().isoformat(),
                 next((n for lo, hi, n in SESSION_BANDS if lo <= at.hour < hi), "off_session"),
                 _first(row, _MAE_KEYS), _first(row, _MFE_KEYS), lag, unit)


def collect(notes: list[dict[str, str]], stats: dict[str, Any]) -> dict[str, Sleeve]:
    """Both lanes, on posterior_alpha's rules: FORWARD-PHASE shadow rows only (historical rows
    predate pre-registration and the desk excludes them from every threshold), and an R stamped
    0.0 on a PAYING live fill is unreconstructed, not an observation of no edge."""
    out: dict[str, Sleeve] = {}
    state = pa._read_json(SHADOW_STATE)
    if not isinstance(state, dict):
        notes.append({"sleeve": "(forward lane)",
                      "why": f"forward clocks absent or unreadable: {SHADOW_STATE.name}"})
        state = {}
    skipped = 0
    for key, row in state.items():
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") not in pa.FORWARD_STATUSES:
            skipped += 1
            continue
        led = pa._read_json(SHADOW_DIR / f"ledger_{str(key).replace('.', '_')}.json", [])
        out[str(key)] = Sleeve(
            str(key), "forward", str(key).split(".")[0], str(row.get("status")),
            [t for r in (led if isinstance(led, list) else [])
             if isinstance(r, dict) and str(r.get("phase") or "") == "forward"
             and (t := _trade_of(r)) is not None])
    raw = pa._read_json(SLEEVES)
    rows = raw.get("sleeves") if isinstance(raw, dict) else raw
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("name"):
            st = str(row.get("status") or "")
            out[str(row["name"])] = Sleeve(str(row["name"]),
                                           "live" if st == "LIVE" else (st.lower() or "registry"),
                                           str(row.get("symbol") or ""), st)
    ledger = pa._read_jsonl(LIVE_LEDGER)
    if not ledger:
        notes.append({"sleeve": "(live lane)",
                      "why": f"live fills absent or unreadable: {LIVE_LEDGER.name}"})
    dropped, names = 0, list(out)
    for row in ledger:
        token = str(row.get("sleeve") or "").strip()
        if not token or token.startswith("["):
            continue                                        # a broker comment, not a sleeve
        value, pl = pa._num(row.get("r_multiple")), pa._num(row.get("pl_quote")) or 0.0
        if row.get("r_unreconstructible") or value is None or (value == 0.0 and pl != 0.0):
            dropped += 1
            continue
        name = pa._join_live(token, names)
        found = out.get(name)
        if found is None:
            found = out[name] = Sleeve(name, "live", str(row.get("symbol") or ""), "LEDGER_ONLY")
            names.append(name)
        found.symbol = found.symbol or str(row.get("symbol") or "")
        if (trade := _trade_of(row)) is not None:
            found.trades.append(trade)
    # A registry sleeve with NO live fills still has evidence: its own zero-capital shadow replay
    # (`ledger_<name>.json`), which keeps accruing while the sleeve is dark and which the regime
    # monitor already treats as forward evidence. Live fills win where both exist -- pooling a
    # replay with real fills would publish one series that is two different measurements.
    replayed = 0
    for sleeve in out.values():
        if sleeve.trades:
            continue
        led = pa._read_json(SHADOW_DIR / f"ledger_{sleeve.name}.json", [])
        rows_f = [t for r in (led if isinstance(led, list) else [])
                  if isinstance(r, dict) and str(r.get("phase") or "") == "forward"
                  and (t := _trade_of(r)) is not None]
        if rows_f:
            sleeve.trades, sleeve.lane = rows_f, "shadow_replay"
            replayed += 1
    stats.update(live_rows_dropped=dropped, forward_clocks_skipped=skipped,
                 sleeves_on_shadow_replay=replayed)
    return out


# ------------------------------------------------------------------------------ the known model
def factor_panel(notes: list[dict[str, str]]) -> tuple[dict[str, np.ndarray], list[str],
                                                       dict[str, Any]]:
    """day -> the factor vector, built by `exposure_decomposition` and nothing else. The panel is
    the INTERSECTION of the kept factors' days: a trade on a day one factor cannot price is
    dropped and counted, never priced off a forward-filled value."""
    meta = (pa._read_json(EXPOSURE, {}) or {}).get("factors") or {}
    try:
        series = xd.build_factors([]).get("series") or {}
    except Exception as exc:                            # a broken bar store is data, not a crash
        notes.append({"sleeve": "(factor panel)", "why": f"factor builder failed: {exc}"})
        return {}, [], {"basis": "unbuildable", "factors": []}
    fresh = max((s.index[-1] for s in series.values() if len(s)), default=None)
    names: list[str] = []
    for name in FACTOR_NAMES:
        ser = series.get(name)
        if ser is None or not len(ser):
            notes.append({"sleeve": "(factor panel)",
                          "why": f"factor {name} unmeasured on this box; the model is the rest"})
        elif (behind := (fresh - ser.index[-1]).days) > PANEL_STALE_DAYS:
            notes.append({"sleeve": "(factor panel)",
                          "why": f"factor {name} is {behind} days stale; dropped from the panel"})
        else:
            names.append(name)
    if not names:
        return {}, [], {"basis": "own_mean_only", "factors": [],
                        "fit": "no factor panel: epsilon is R minus the sleeve's own mean"}
    cols = {n: {ts.date().isoformat(): float(v)
                for ts, v in zip(series[n].index, series[n].to_numpy(), strict=False)
                if pa._num(float(v)) is not None} for n in names}
    days = set.intersection(*(set(c) for c in cols.values()))
    return ({d: np.asarray([cols[n][d] for n in names], dtype=float) for d in days}, names,
            {"basis": "exposure_decomposition.build_factors", "factors": names,
             "n_days": len(days), "first": min(days, default=None),
             "last": max(days, default=None),
             "factor_basis": {n: str((meta.get(n) or {}).get("basis") or UNMEASURED)
                              for n in names},
             "fit": "OLS with an intercept (the sleeve's own mean) on trade R aligned to the "
                    "trade's day, per standing_questions Q3"})


def fit_epsilon(trades: list[Trade], panel: dict[str, np.ndarray], n_factors: int
                ) -> tuple[list[Trade], np.ndarray, list[float], float | None]:
    """epsilon = R - (intercept + betas . factors), by lstsq. Returns the KEPT trades in time
    order, their epsilon, the coefficients (intercept first) and the fit's R^2."""
    kept = sorted((t for t in trades if not panel or t.day in panel), key=lambda t: t.at)
    if not kept:
        return [], np.empty(0), [], None
    y = np.asarray([t.r for t in kept], dtype=float)
    x = np.column_stack([np.ones(len(kept))]
                        + [np.asarray([panel[t.day][j] for t in kept], dtype=float)
                           for j in range(n_factors if panel else 0)])
    if len(kept) <= x.shape[1]:
        return kept, y - float(y.mean()), [round(float(y.mean()), 6)], None
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    eps = y - x @ beta
    tot = float(((y - y.mean()) ** 2).sum())
    return (kept, eps, [round(float(b), 6) for b in beta],
            None if tot <= 0 else round(float(np.clip(1.0 - float(eps @ eps) / tot, 0.0, 1.0)), 4))


# ------------------------------------------------------------------------- labels for the tests
def regime_labels(panel: dict[str, np.ndarray], names: list[str],
                  notes: list[dict[str, str]]) -> tuple[dict[str, str], str]:
    """day -> regime label. The monitor's own file first; failing that, the panel's own realised
    move split at its median, NAMED as derived so nobody reads it as the monitor's verdict."""
    doc = pa._read_json(REGIME_STATE, {}) or {}
    for key in ("by_day", "days", "history", "regimes"):
        block, rows = doc.get(key), {}
        items = (list(block.items()) if isinstance(block, dict)
                 else [(r.get("day") or r.get("date"), r) for r in block if isinstance(r, dict)]
                 if isinstance(block, list) else [])
        for day, value in items:
            label = (str(value.get("regime") or value.get("label") or value.get("flag") or "")
                     if isinstance(value, dict) else str(value))
            if day and label and label != "None":
                rows[str(day)[:10]] = label
        if rows:
            return rows, f"{REGIME_STATE.name}:{key}"
    if not panel or not names:
        notes.append({"sleeve": "(regime)",
                      "why": f"no dated regime labels in {REGIME_STATE.name} and no factor panel "
                             f"to derive a volatility state from"})
        return {}, UNMEASURED
    days = sorted(panel)
    moves = np.abs(np.asarray([panel[d][0] for d in days], dtype=float))
    cut = float(np.median(moves))
    return ({d: ("vol_high" if m > cut else "vol_low") for d, m in zip(days, moves, strict=False)},
            f"derived: |{names[0]}| daily move, split at its own median")


def event_days(notes: list[dict[str, str]]) -> dict[str, set[str]]:
    """symbol -> the days a forced-flow event touches it, widened by +-EVENT_DAYS."""
    doc = pa._read_json(CALENDAR, {}) or {}
    events = doc.get("events") if isinstance(doc, dict) else doc
    out: dict[str, set[str]] = defaultdict(set)
    for row in events if isinstance(events, list) else []:
        try:
            day = date.fromisoformat(str(row.get("date") or "")[:10])
        except (AttributeError, ValueError):
            continue
        near = {(day + timedelta(days=k)).isoformat() for k in range(-EVENT_DAYS, EVENT_DAYS + 1)}
        for sym in row.get("instruments") or []:
            out[str(sym)].update(near)
    if not out:
        notes.append({"sleeve": "(events)",
                      "why": f"no forced-flow events readable in {CALENDAR.name}"})
    return dict(out)


def residual_inputs() -> dict[str, list[dict[str, Any]]]:
    """The ignorance ledger's own unexplained strategy losses, keyed by the sleeve they name."""
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pa._read_jsonl(RESIDUAL_QUEUE):
        key = str(row.get("key") or "")
        if str(row.get("level") or "") == "strategy_loss" and key.startswith("sleeve_shortfall:"):
            out[key.split(":", 1)[1]].append(
                {k: row.get(k) for k in ("residual_id", "magnitude", "recurrence", "status")})
    return dict(out)


def hazard_reading() -> tuple[dict[str, float], str]:
    """p_die_k per sleeve, through posterior_alpha's own tolerant card reader, on OUR path."""
    saved = pa.HAZARD
    pa.HAZARD = HAZARD
    try:
        return pa.hazard_cards()
    finally:
        pa.HAZARD = saved


# ---------------------------------------------------------------------------- permutation core
def _perm_p(obs: float, null: np.ndarray, two_sided: bool = True) -> float:
    """(1 + #{null at least as extreme}) / (draws + 1). Never zero: 200 draws cannot license a
    p below 1/201, and printing one would be arithmetic the sample did not buy."""
    if not np.isfinite(obs) or null.size == 0:
        return 1.0
    hits = (np.abs(null) >= abs(obs) - 1e-12) if two_sided else (null >= obs - 1e-12)
    return round(float((1 + int(np.count_nonzero(hits))) / (null.size + 1)), 6)


def _group_stat(eps: np.ndarray, labels: np.ndarray, keys: tuple[str, ...]) -> tuple[str, float]:
    """The largest |group mean - grand mean| among groups of at least MIN_GROUP. The MAX is the
    statistic, so the same max is taken under the null and the multiplicity is charged."""
    grand, best, stat = float(eps.mean()), "", 0.0
    for key in keys:
        n = int(np.count_nonzero(mask := labels == key))
        if MIN_GROUP <= n < eps.size and abs(v := float(eps[mask].mean()) - grand) > abs(stat):
            best, stat = key, v
    return best, stat


def _key_stat(eps: np.ndarray, labels: np.ndarray, key: str) -> float | None:
    """The statistic for ONE named group. A window recurrence must be the SAME group, not merely
    whichever group happened to be largest there -- the max is for the test, not for the replay."""
    n = int(np.count_nonzero(mask := labels == key))
    return None if n < MIN_GROUP or n == eps.size else float(eps[mask].mean()) - float(eps.mean())


def _split_stat(eps: np.ndarray, mask: np.ndarray) -> float | None:
    n = int(np.count_nonzero(mask))
    return (None if n < MIN_GROUP or mask.size - n < MIN_GROUP
            else float(eps[mask].mean() - eps[~mask].mean()))


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    ca, cb = a - a.mean(), b - b.mean()
    den = float(np.sqrt(float(ca @ ca) * float(cb @ cb)))
    return 0.0 if den <= 0 else float(ca @ cb / den)


def _tested(key: str, stat: float, n: int, rng: np.random.Generator, size: int, fn: Any,
            null: str, two_sided: bool = True, **extra: Any) -> dict[str, Any]:
    """One statistic and its permutation null, drawn PERM_DRAWS times by reshuffling an index."""
    idx, draws = np.arange(size), np.empty(PERM_DRAWS)
    for i in range(PERM_DRAWS):
        rng.shuffle(idx)
        draws[i] = fn(idx)
    return {"key": key, "stat": round(stat, 6), "p": _perm_p(stat, draws, two_sided), "n": int(n),
            "null": f"{PERM_DRAWS} {null}", **extra}


def label_test(eps: np.ndarray, labels: np.ndarray, keys: tuple[str, ...],
               rng: np.random.Generator) -> dict[str, Any] | None:
    key, stat = _group_stat(eps, labels, keys)
    return None if not key else _tested(
        key, stat, int(np.count_nonzero(labels == key)), rng, eps.size,
        lambda i: _group_stat(eps[i], labels, keys)[1],
        "label permutations; statistic = max |group mean - grand mean|")


def two_sample(eps: np.ndarray, mask: np.ndarray, key: str,
               rng: np.random.Generator) -> dict[str, Any] | None:
    stat = _split_stat(eps, mask)
    n = int(np.count_nonzero(mask))
    return None if stat is None else _tested(
        key, stat, n, rng, eps.size, lambda i: float(eps[i][:n].mean() - eps[i][n:].mean()),
        "membership permutations; statistic = mean(in) - mean(out)")


def corr_test(a: np.ndarray, b: np.ndarray, key: str,
              rng: np.random.Generator) -> dict[str, Any] | None:
    if a.size < MIN_GROUP or a.size != b.size or min(float(a.std()), float(b.std())) <= 0:
        return None
    return _tested(key, _pearson(a, b), a.size, rng, a.size, lambda i: _pearson(a, b[i]),
                   "pairing permutations; statistic = Pearson r")


def _swing(a: np.ndarray, b: np.ndarray) -> tuple[float, int]:
    """(range of the rolling correlation, sign flips across the deadband)."""
    if a.size < ROLL_WINDOW:
        return 0.0, 0
    va = np.lib.stride_tricks.sliding_window_view(a, ROLL_WINDOW)
    vb = np.lib.stride_tricks.sliding_window_view(b, ROLL_WINDOW)
    ca, cb = va - va.mean(axis=1, keepdims=True), vb - vb.mean(axis=1, keepdims=True)
    den = np.sqrt((ca * ca).sum(axis=1) * (cb * cb).sum(axis=1))
    roll = np.divide((ca * cb).sum(axis=1), den, out=np.full(den.shape, np.nan), where=den > 0)
    live = roll[np.isfinite(roll)]
    if live.size < 2:
        return 0.0, 0
    signs = [1 if v >= FLIP_BAND else -1 for v in live if abs(v) >= FLIP_BAND]
    return float(live.max() - live.min()), sum(1 for x, y in pairwise(signs) if x != y)


def correlation_change(r: np.ndarray, factor: np.ndarray,
                       rng: np.random.Generator) -> dict[str, Any] | None:
    if r.size < ROLL_WINDOW + MIN_GROUP or float(factor.std()) <= 0:
        return None
    stat, flips = _swing(r, factor)
    return _tested(f"flips_{flips}", stat, r.size, rng, r.size,
                   lambda i: _swing(r, factor[i])[0],
                   f"pairing permutations; statistic = range of the rolling {ROLL_WINDOW}-trade "
                   f"correlation with the dominant factor", two_sided=False, flips=flips)


# ------------------------------------------------------------------------------ the sleeve pass
def streak_labels(trades: list[Trade]) -> np.ndarray:
    """What the book had just done when this trade opened: k wins, k losses, or neither."""
    out, wins, losses = [], 0, 0
    for trade in trades:
        out.append(f"after_{STREAK_K}_wins" if wins >= STREAK_K else
                   (f"after_{STREAK_K}_losses" if losses >= STREAK_K else "flat"))
        wins, losses = ((wins + 1, 0) if trade.r > 0
                        else ((0, losses + 1) if trade.r < 0 else (0, 0)))
    return np.asarray(out, dtype=object)


def mae_mfe_reading(trades: list[Trade]) -> dict[str, Any]:
    """Descriptive, not tested: how much of the favourable excursion the exit actually kept."""
    pairs = [(t.mfe, t.r) for t in trades if t.mfe is not None]
    if len(pairs) < MIN_GROUP:
        return {"n": len(pairs), "verdict": UNMEASURED,
                "why": f"{len(pairs)} row(s) carry MFE; {MIN_GROUP} needed"}
    mfe = np.asarray([p for p, _ in pairs], dtype=float)
    got = np.asarray([q for _, q in pairs], dtype=float)
    ratio = (float(np.median(got[mfe > 0] / mfe[mfe > 0])) if (mfe > 0).any() else float("nan"))
    mae = [t.mae for t in trades if t.mae is not None]
    return {"n": len(pairs), "capture_ratio": round(ratio, 4) if np.isfinite(ratio) else UNMEASURED,
            "give_back_mean_r": round(float(np.mean(mfe - got)), 6),
            "mae_mean_r": round(float(np.mean(mae)), 6) if mae else UNMEASURED,
            "verdict": "EXITS_LEAVE_MONEY" if np.isfinite(ratio) and ratio < 0.5 else "EXIT_KEEPS",
            "why": "median R / MFE over trades with a positive favourable excursion"}


def _halves_agree(n: int, stat_fn: Any, full: float) -> bool:
    """The same statistic, same sign, in BOTH halves of the sleeve's own record: the cheap form of
    "it recurs across >= 2 windows", with no second p-value to spend the error budget on."""
    half = n // 2
    if half < MIN_WINDOW_N or full == 0.0:
        return False
    first, second = stat_fn(slice(0, half)), stat_fn(slice(half, n))
    return bool(first is not None and second is not None
                and np.sign(first) == np.sign(second) == np.sign(full))


def sleeve_patterns(sleeve: Sleeve, trades: list[Trade], eps: np.ndarray,
                    panel: dict[str, np.ndarray], names: list[str], coeffs: list[float],
                    regimes: dict[str, str], events: dict[str, set[str]],
                    rng: np.random.Generator, notes: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Every pattern test on one sleeve's epsilon. Each row carries its own null and its own n."""
    found: list[dict[str, Any]] = []
    sess = np.asarray([t.session for t in trades], dtype=object)
    lab = np.asarray([regimes.get(t.day, "") for t in trades], dtype=object)
    rkeys = tuple(sorted({str(v) for v in lab if v}))
    near = np.asarray([t.day in events.get(sleeve.symbol, ()) for t in trades], dtype=bool)
    streaks = streak_labels(trades)
    skeys = (f"after_{STREAK_K}_wins", f"after_{STREAK_K}_losses")
    lags = [t.lag for t in trades]
    arr = np.asarray(lags, dtype=float) if lags and all(v is not None for v in lags) else None
    reading = mae_mfe_reading(trades)
    give = [t.mfe - t.r if t.mfe is not None else None for t in trades]
    gvec = np.asarray(give, dtype=float) if give and all(v is not None for v in give) else None
    gmask = None if gvec is None else gvec > float(np.median(gvec))
    r_sess = label_test(eps, sess, SESSION_KEYS, rng)
    r_reg = label_test(eps, lab, rkeys, rng) if rkeys else None
    r_streak = label_test(eps, streaks, skeys, rng)
    plan: list[tuple[str, dict[str, Any] | None, str, Any, dict[str, Any]]] = [
        ("session", r_sess, f"no session band holds {MIN_GROUP} trades",
         r_sess and (lambda sl: _key_stat(eps[sl], sess[sl], r_sess["key"])), {}),
        ("regime", r_reg,
         f"no regime label holds {MIN_GROUP} trades" if rkeys else "no dated regime labels",
         r_reg and (lambda sl: _key_stat(eps[sl], lab[sl], r_reg["key"])), {}),
        ("event_proximity", two_sample(eps, near, "near_event", rng),
         f"{int(near.sum())} of {near.size} trade(s) within +-{EVENT_DAYS}d of an event touching "
         f"{sleeve.symbol or '(no symbol)'}", lambda sl: _split_stat(eps[sl], near[sl]), {}),
        ("time_since_signal",
         None if arr is None else corr_test(eps, arr, f"{trades[0].lag_unit}_since_signal", rng),
         "the ledger rows carry no signal-to-fill lag" if arr is None else "the lag is constant",
         None if arr is None else
         (lambda sl: _pearson(eps[sl], arr[sl]) if float(arr[sl].std()) > 0 else None), {}),
        ("streak", r_streak, f"no streak state holds {MIN_GROUP} trades",
         r_streak and (lambda sl: _key_stat(eps[sl], streaks[sl], r_streak["key"])), {}),
        ("mae_mfe", None if gmask is None else two_sample(eps, gmask, "high_give_back", rng),
         str(reading.get("why")) if gmask is None else "the give-back is constant",
         None if gmask is None else (lambda sl: _split_stat(eps[sl], gmask[sl])),
         {"reading": reading}),
    ]
    if names and panel:
        col = int(np.argmax([abs(b) for b in coeffs[1:]])) if len(coeffs) > 1 else 0
        plan.append(("correlation_change",
                     correlation_change(np.asarray([t.r for t in trades], dtype=float),
                                        np.asarray([panel[t.day][col] for t in trades],
                                                   dtype=float), rng),
                     f"{len(trades)} trade(s); {ROLL_WINDOW + MIN_GROUP} needed for a rolling "
                     f"window", None, {"factor": names[col]}))
    for kind, res, absent, half, extra in plan:
        if res is None:
            notes.append({"sleeve": sleeve.name, "why": f"{kind}: {absent}"})
            continue
        found.append({"sleeve": sleeve.name, "lane": sleeve.lane, "symbol": sleeve.symbol,
                      "pattern": f"{kind}:{res['key']}", "kind": kind, "key": res["key"],
                      "stat": res["stat"], "p": res["p"], "n": res["n"], "null": res["null"],
                      "windows_agree": bool(half and _halves_agree(eps.size, half, res["stat"])),
                      "recurring": False, "discovery_id": None,
                      "suggested_transformation": TRANSFORM[kind].format(key=res["key"]), **extra})
    return found


def decay_row(sleeve: Sleeve, eps: np.ndarray, rng: np.random.Generator,
              hazard: dict[str, float]) -> dict[str, Any]:
    """First half against second, beside the hazard engine's own reading of the same sleeve."""
    half = eps.size // 2
    mask = np.zeros(eps.size, dtype=bool)
    mask[half:] = True
    res = two_sample(eps, mask, "second_half", rng)
    return {"sleeve": sleeve.name, "n": int(eps.size),
            "first_half_mean": round(float(eps[:half].mean()), 6) if half else UNMEASURED,
            "second_half_mean": round(float(eps[half:].mean()), 6) if half else UNMEASURED,
            "stat": res["stat"] if res else UNMEASURED, "p": res["p"] if res else UNMEASURED,
            "null": res["null"] if res else f"fewer than {MIN_GROUP} trades in a half",
            "hazard_p_die_k": hazard.get(sleeve.name, hazard.get(sleeve.symbol, UNMEASURED))}


def cross_strategy(daily: dict[str, dict[str, float]],
                   rng: np.random.Generator) -> list[dict[str, Any]]:
    """Two sleeves whose DAILY epsilon moves together are one bet the book has not named."""
    out, order = [], sorted(daily)
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            days = sorted(set(daily[a]) & set(daily[b]))
            if len(days) < CROSS_MIN_DAYS:
                continue
            res = corr_test(np.asarray([daily[a][d] for d in days], dtype=float),
                            np.asarray([daily[b][d] for d in days], dtype=float), b, rng)
            if res is None or abs(res["stat"]) <= CROSS_RHO:
                continue
            out.append({"sleeve": a, "other": b, "symbol": "", "lane": "cross",
                        "pattern": f"cross_strategy:{b}", "kind": "cross_strategy", "key": b,
                        "stat": res["stat"], "p": res["p"], "n": res["n"], "null": res["null"],
                        "windows_agree": False, "recurring": False, "discovery_id": None,
                        "suggested_transformation": TRANSFORM["cross_strategy"]})
    return out


def mark_recurring(patterns: list[dict[str, Any]]) -> None:
    """RECURRENCE, the only thing that turns a measurement into a discovery: the same (kind, key)
    significant on two or more sleeves, OR one sleeve's own two halves agreeing in sign."""
    live = [p for p in patterns if float(p["p"]) < ALPHA]
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in live:
        seen[(row["kind"], row["key"])].add(row["sleeve"])
    for row in patterns:
        if float(row["p"]) >= ALPHA:            # every row carries a disposition, never a gap
            row["recurring"], row["recurrence_basis"] = False, "not_significant"
            continue
        across = len(seen[(row["kind"], row["key"])]) >= 2
        row["recurring"] = bool(across or row.get("windows_agree"))
        row["recurrence_basis"] = ("sleeves" if across
                                   else ("windows" if row.get("windows_agree") else "none"))


def record(patterns: list[dict[str, Any]], apply: bool) -> int:
    """Every recurring pattern becomes ONE DiscoveryObject, UNPROCESSED, for the compiler."""
    n = 0
    for row in (p for p in patterns if p.get("recurring")):
        rule = str(row["suggested_transformation"])
        if not apply:
            row["discovery_id"] = "(dry-run)"
            n += 1
            continue
        did, created = registry.record_discovery(
            source_id=f"shadow_ledger:{row['sleeve']}", source_type="shadow_ledger",
            mechanism=(f"{row['sleeve']}: the residual after the desk's named factors is not flat "
                       f"in {row['kind']} ({row['key']}); stat {float(row['stat']):+.4f} on "
                       f"n={row['n']} at permutation p={row['p']}"),
            origin="MOAT", generator=SOURCE, assets=[row.get("symbol") or row["sleeve"]],
            exact_rule_if_known=rule, information="the desk's own realised P&L, after its own "
                                                  "factor model",
            sessions=[row["key"]] if row["kind"] == "session" else [],
            regimes=[row["key"]] if row["kind"] == "regime" else [],
            economic_rationale=RULE, confidence=round(1.0 - float(row["p"]), 6),
            falsifier=(f"the same split on the next {MIN_TRADES} trades of {row['sleeve']} "
                       f"reverses the sign of {float(row['stat']):+.4f}"),
            payload={"sleeve": row["sleeve"], "pattern": row["pattern"], "stat": row["stat"],
                     "n": row["n"], "suggested_transformation": rule})
        row["discovery_id"] = did
        n += int(created)
    return n


def remember(sleeve: Sleeve, kept: list[Trade], eps: np.ndarray, coeffs: list[float],
             names: list[str], r2: float | None, rows: list[dict[str, Any]],
             ignorance: list[dict[str, Any]], epoch: str) -> None:
    """One research_memory row per sleeve, and its epsilon series, so a LATER pass can measure the
    change rather than re-deriving today's number and calling it a trend."""
    live = [r for r in rows if float(r["p"]) < ALPHA]
    sd = round(float(eps.std(ddof=1)), 6) if eps.size > 1 else 0.0
    registry.remember(
        "residual",
        f"{sleeve.name}: epsilon over {eps.size} trades against "
        f"[{', '.join(names) or 'own mean only'}] -- mean {float(eps.mean()):+.4f} R, sd {sd}, "
        f"r2 {r2}; {len(live)} pattern(s) under p={ALPHA}"
        + (f" ({', '.join(r['pattern'] for r in live)})" if live else ""),
        kind="epsilon_structure", memory_key=f"epsilon:{sleeve.name}", result="MEASURED",
        lessons=RULE,
        metrics={"n": int(eps.size), "mean": round(float(eps.mean()), 6), "sd": sd, "r2": r2},
        payload={"sleeve": sleeve.name, "lane": sleeve.lane, "symbol": sleeve.symbol,
                 "factors": names, "coefficients": coeffs, "epoch_key": epoch,
                 "known_ignorance": ignorance,
                 "patterns": [{k: r[k] for k in ("pattern", "stat", "p", "n")} for r in live]},
        evidence={"first": kept[0].at.isoformat(), "last": kept[-1].at.isoformat(),
                  "source": SOURCE})
    if ("epsilon", epoch) not in {(k, e) for k, e, _ in registry.candidate_returns(sleeve.name)}:
        registry.record_candidate_returns(sleeve.name, "epsilon", epoch, eps, timeframe="trade")


# ------------------------------------------------------------------------------------ the pass
def run(budget_s: float = BUDGET_S, write: bool = True, apply: bool = True,
        seed: int = SEED) -> dict[str, Any]:
    started, rng = time.monotonic(), np.random.default_rng(seed)
    deadline = started + float(budget_s)
    notes: list[dict[str, str]] = []
    counts: dict[str, Any] = {}
    sleeves = collect(notes, counts)
    panel, names, model = factor_panel(notes)
    regimes, regime_basis = regime_labels(panel, names, notes)
    events, ignorance = event_days(notes), residual_inputs()
    hazard, hazard_state = hazard_reading()
    if hazard_state != "present":
        notes.append({"sleeve": "(decay)", "why": f"hazard card {hazard_state}: {HAZARD.name}"})
    patterns: list[dict[str, Any]] = []
    decay: list[dict[str, Any]] = []
    tails: list[dict[str, Any]] = []
    daily: dict[str, dict[str, float]] = {}
    epoch, measured = datetime.now(UTC).date().isoformat(), 0
    for name in sorted(sleeves, key=lambda k: (-len(sleeves[k].trades), k)):
        sleeve = sleeves[name]
        if len(sleeve.trades) < MIN_TRADES:
            notes.append({"sleeve": name, "why": f"{len(sleeve.trades)} trade(s); {MIN_TRADES} "
                                                 f"needed before a residual is a measurement"})
            continue
        if time.monotonic() > deadline:
            notes.append({"sleeve": name,
                          "why": f"budget of {budget_s:g}s spent before this sleeve was tested"})
            continue
        kept, eps, coeffs, r2 = fit_epsilon(sleeve.trades, panel, len(names))
        if len(kept) < MIN_TRADES:
            notes.append({"sleeve": name, "why": f"{len(kept)} of {len(sleeve.trades)} trade(s) "
                                                 f"align to a factor day; {MIN_TRADES} needed"})
            continue
        measured += 1
        rows = sleeve_patterns(sleeve, kept, eps, panel, names, coeffs, regimes, events, rng, notes)
        patterns.extend(rows)
        decay.append(decay_row(sleeve, eps, rng, hazard))
        day_sum: dict[str, float] = defaultdict(float)
        for trade, value in zip(kept, eps, strict=False):
            day_sum[trade.day] += float(value)
            tails.append({"sleeve": name, "symbol": sleeve.symbol, "lane": sleeve.lane,
                          "at": trade.at.isoformat(), "r": round(trade.r, 6),
                          "epsilon": round(float(value), 6), "session": trade.session,
                          "regime": regimes.get(trade.day, UNMEASURED), "mfe": trade.mfe,
                          "mae": trade.mae,
                          "near_event": trade.day in events.get(sleeve.symbol, ())})
        daily[name] = dict(day_sum)
        if apply:
            remember(sleeve, kept, eps, coeffs, names, r2, rows, ignorance.get(name, []), epoch)
    patterns.extend(cross_strategy(daily, rng))
    mark_recurring(patterns)
    recorded = record(patterns, apply)
    patterns.sort(key=lambda row: (float(row["p"]), -abs(float(row["stat"]))))
    tails.sort(key=lambda row: -abs(float(row["epsilon"])))
    top = tails[:max(1, round(len(tails) * TOP_TAIL))] if tails else []
    if apply:
        registry.generator_yield_update(SOURCE, generated=len(patterns), judged=measured,
                                        compute_s=round(time.monotonic() - started, 3))
    payload = {
        "at": datetime.now(UTC).isoformat(), "rule": RULE, "n_sleeves": len(sleeves),
        "n_measured": measured, "patterns": patterns,
        "unexplained_winners": [t for t in top if t["epsilon"] > 0],
        "unexplained_losers": [t for t in top if t["epsilon"] < 0],
        "decay": {"per_sleeve": decay, "hazard": hazard_state,
                  "basis": "mean(second half) - mean(first half) of epsilon with a permutation "
                           "null; p_die_k beside it where the hazard engine has a card"},
        "cross_strategy": [p for p in patterns if p["kind"] == "cross_strategy"],
        "discoveries_recorded": recorded, "unmeasured": notes, "regime_basis": regime_basis,
        "factor_model": {**model, "coefficients": "intercept first, then " + ", ".join(names)},
        "recurrence_rule": (f"p < {ALPHA} AND the same (kind, key) on >= 2 sleeves, or the same "
                            f"statistic agreeing in sign across both halves of one sleeve "
                            f"(>= {MIN_WINDOW_N} trades each)"),
        "thresholds": {"min_trades": MIN_TRADES, "min_group": MIN_GROUP, "draws": PERM_DRAWS,
                       "alpha": ALPHA, "top_tail": TOP_TAIL, "cross_min_days": CROSS_MIN_DAYS,
                       "cross_rho": CROSS_RHO, "roll_window": ROLL_WINDOW},
        "residual_queue": {"path": str(RESIDUAL_QUEUE),
                           "rows_read": sum(len(v) for v in ignorance.values()),
                           "append": "no documented append path; residual_queue.build() "
                                     "recollects its whole queue from a fixed producer plan, so "
                                     "new ignorance is recorded in the registry instead"},
        "counts": {**counts, "n_patterns": len(patterns),
                   "n_significant": sum(1 for p in patterns if float(p["p"]) < ALPHA),
                   "n_recurring": sum(1 for p in patterns if p["recurring"]),
                   "compute_s": round(time.monotonic() - started, 3)},
        "inputs": {str(p): ("present" if p.exists() else "absent")
                   for p in (SLEEVES, LIVE_LEDGER, SHADOW_STATE, HAZARD, REGIME_STATE, CALENDAR,
                             RESIDUAL_QUEUE, EXPOSURE)},
    }
    if write:
        pa._write_atomic(OUT, payload)
    return payload


def render(payload: dict[str, Any], limit: int = 20) -> str:
    """The table a human reads: the strongest patterns first, then the tails, then the absences."""
    live = sum(1 for p in payload["patterns"] if float(p["p"]) < ALPHA)
    lines = [f"SHADOW DISCOVERY  sleeves={payload['n_sleeves']} measured={payload['n_measured']} "
             f"patterns={len(payload['patterns'])} p<{ALPHA}={live} "
             f"recurring={payload['counts']['n_recurring']} "
             f"discoveries={payload['discoveries_recorded']}",
             f"  factors   {payload['factor_model'].get('factors') or '(own mean only)'}  "
             f"days={payload['factor_model'].get('n_days', 0)}  regime={payload['regime_basis']}"]
    lines += [f"  {str(r['sleeve'])[:28]:28s} {str(r['pattern'])[:32]:32s} "
              f"{float(r['stat']):>+9.4f} p={float(r['p']):<8.4f} n={int(r['n']):<4d} "
              f"{'RECURRING' if r['recurring'] else ''}" for r in payload["patterns"][:limit]]
    for kind, mark in (("unexplained_winners", "+"), ("unexplained_losers", "-")):
        lines += [f"  tail {mark} {str(r['sleeve'])[:24]:24s} eps {float(r['epsilon']):+.4f} "
                  f"R {float(r['r']):+.3f} {r['session']}/{r['regime']}"
                  f"{' near_event' if r['near_event'] else ''}" for r in payload[kind][:3]]
    lines += [f"  UNMEASURED  {n['sleeve']}: {n['why']}" for n in payload["unmeasured"][:limit]]
    if len(payload["unmeasured"]) > limit:
        lines.append(f"  ... {len(payload['unmeasured']) - limit} more UNMEASURED rows")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="mine the desk's own unexplained P&L for discoveries")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no artifact and record nothing")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S, help="wall-clock bound on the pass")
    ap.add_argument("--limit", type=int, default=20, help="rows in the printed table")
    ap.add_argument("--json", action="store_true", help="print the payload instead of the table")
    args = ap.parse_args(argv)
    payload = run(budget_s=args.budget_s, write=not args.dry_run, apply=not args.dry_run)
    print(json.dumps(payload, indent=1, default=str) if args.json
          else render(payload, limit=args.limit))
    print("(dry run: nothing written, nothing recorded)" if args.dry_run else f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
