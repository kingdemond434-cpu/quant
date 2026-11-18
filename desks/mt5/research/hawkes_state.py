"""HAWKES STATE -- tick-arrival self-excitation per symbol, as a vol-burst state the judge can test.

WHAT IT MEASURES. Quote updates do not arrive as a Poisson stream: one update raises the chance
of the next, and a burst of updates is the microstructure face of a volatility burst. For every
hypothesis-lane symbol on the desk's tick tape, every complete broker hour is fitted with an
exponential-kernel Hawkes process

    lambda(t) = mu + n * beta * sum_{t_j < t} exp(-beta (t - t_j))

by maximum likelihood (EM for (mu, n) on a log grid of beta, profile likelihood across the grid).
`n` is the BRANCHING RATIO: the share of arrivals triggered by earlier arrivals rather than by
news from outside (n -> 1 is a market feeding on itself). `lambda_end` is the fitted conditional
intensity at the hour's close, and `intensity_z` is log(lambda_end) against the previous
`Z_WINDOW` hours of the same symbol -- strictly previous, never itself or later.

WHERE IT READS. The tape `mt5desk.tape` writes: `data/tape/ticks/<SYM>/<day>.parquet` (both
writers' naming conventions, through `tape.day_files`), the `time_msc` column only, de-duplicated
to unique milliseconds. Those stamps are the broker's wall clock; see `state_conditioner`.

NO LOOKAHEAD, BY CONSTRUCTION AND BY TEST. Hour h's row is a function of the ticks inside
[h, h+1h) and of earlier rows only; it is stamped `available_time` = the true UTC of h+1h.
`tests/research/test_hawkes_state.py` appends a violent burst AFTER an hour and asserts every
earlier row is byte-identical.

WHAT IT PUBLISHES, every pass (data department, hourly leg `hawkes_state`):

    reports/HAWKES_STATE.json                     latest branching ratio and intensity z per
                                                  symbol, what was set aside and why, the minting
    data/lake/series/hawkes_<SYM>.csv             the PIT series (exogenous_conditioner / alt:)
    data/lake/state/hawkes_state.json             per-symbol cursor and the minted cell ids

BOUNDED. A pass stops at `--budget-s`; each symbol advances at most `MAX_HOURS_PER_PASS` hours
from its cursor (stalest symbol first), each fit keeps at most `MAX_EVENTS` arrivals, and the
backfill never reaches deeper than `BACKFILL_HOURS`. Work not reached is reported, and resumed.

NOT MONEY PATH. It reads ticks and writes a report, a lake series and a donation. It sizes nothing.

    python desks/mt5/research/hawkes_state.py --once
    python desks/mt5/research/hawkes_state.py --once --dry-run      # compute, mint nothing
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import state_conditioner as sc  # noqa: E402

SEAT = "hawkes_state"
REPORT = sc.REPORTS / "HAWKES_STATE.json"
STATE = sc.STATE_DIR / "hawkes_state.json"
TICKS = DESK / "data" / "tape" / "ticks"

HOUR_MS = 3_600_000
#: Fewer arrivals than this in an hour is no fit at all (a closed market, a dead quote).
MIN_EVENTS = 30
#: The most recent arrivals kept per hour. The fit is O(events x grid); this keeps it to ~10 ms.
MAX_EVENTS = 2_000
#: Hours each symbol may advance per pass, and how deep a cold symbol starts (30 days).
MAX_HOURS_PER_PASS = 96
BACKFILL_HOURS = 24 * 30
#: Hours of the symbol's own history `intensity_z` is measured against, and the minimum.
Z_WINDOW = 168
Z_MIN = 24
#: Rows kept in a series file (about a year of trading hours).
MAX_ROWS = 24 * 270
#: Rows a series needs before its cells are minted: ~two trading weeks of hours.
MIN_ROWS_TO_MINT = 240
#: beta grid, as multiples of ln2 / median inter-arrival gap.
BETA_MULTS = tuple(2.0 ** k for k in range(-6, 4))
EM_ITERS = 60
COLUMNS = ("n_events", "branching_ratio", "mu", "beta", "halflife_s", "lambda_end",
           "excitation", "log_lambda_end", "intensity_z")


# ------------------------------------------------------------------------------------- the fit
def _excitation_sums(t: np.ndarray, beta: float) -> np.ndarray:
    """A_i = sum_{j<i} exp(-beta (t_i - t_j)) by the exact one-step recursion."""
    a = np.zeros(t.size)
    acc = 0.0
    prev = float(t[0])
    for i in range(1, t.size):
        ti = float(t[i])
        acc = math.exp(-beta * (ti - prev)) * (acc + 1.0)
        a[i] = acc
        prev = ti
    return a


def fit_hawkes(times_s: Sequence[float] | np.ndarray, horizon_s: float) -> dict[str, Any] | None:
    """MLE of (mu, n, beta) for arrivals in [0, horizon_s). None when there is nothing to fit."""
    t = np.asarray(times_s, dtype=float)
    t = t[np.isfinite(t)]
    if t.size < MIN_EVENTS:
        return None
    t = np.sort(t)
    t = t - t[0]
    horizon = float(max(horizon_s, t[-1] + 1e-3))
    n_ev = int(t.size)
    gaps = np.diff(t)
    gaps = gaps[gaps > 0]
    if gaps.size == 0:
        return None
    beta0 = math.log(2.0) / float(np.median(gaps))
    best: dict[str, Any] | None = None
    for mult in BETA_MULTS:
        beta = beta0 * mult
        a = _excitation_sums(t, beta)
        g = 1.0 - np.exp(-beta * (horizon - t))
        sum_g = float(g.sum())
        mu, n = 0.5 * n_ev / horizon, 0.5
        for _ in range(EM_ITERS):
            trig = n * beta * a
            lam = mu + trig
            p = trig / lam
            sp = float(p.sum())
            mu_new = max((n_ev - sp) / horizon, 1e-12)
            n_new = min(sp / sum_g, 0.999) if sum_g > 0 else 0.0
            done = abs(n_new - n) < 1e-6 and abs(mu_new - mu) < 1e-9 * max(mu, 1e-9)
            mu, n = mu_new, n_new
            if done:
                break
        lam = mu + n * beta * a
        ll = float(np.log(lam).sum() - mu * horizon - n * sum_g)
        if best is None or ll > best["loglik"]:
            a_end = float(np.exp(-beta * (horizon - t)).sum())
            lam_end = mu + n * beta * a_end
            best = {"n_events": n_ev, "branching_ratio": float(n), "mu": float(mu),
                    "beta": float(beta), "halflife_s": math.log(2.0) / beta,
                    "lambda_end": float(lam_end), "excitation": float(lam_end / mu),
                    "log_lambda_end": math.log(lam_end), "loglik": ll}
    return best


# ------------------------------------------------------------------------------------- the tape
def _read_ms(path: Path) -> np.ndarray:
    import pandas as pd
    try:
        df = pd.read_parquet(path, columns=["time_msc"])
        return pd.to_numeric(df["time_msc"], errors="coerce").dropna().to_numpy(dtype="int64")
    except Exception:
        pass
    try:
        df = pd.read_parquet(path, columns=["ts"])
        ts = pd.to_datetime(df["ts"], errors="coerce", utc=True).dropna()
        return (ts.astype("int64") // 1_000_000).to_numpy(dtype="int64")
    except Exception:
        return np.zeros(0, dtype="int64")


def day_files(symbol: str, root: Path) -> list[tuple[str, Path]]:
    try:
        from mt5desk.tape import day_files as _df
        return _df(symbol, root)
    except Exception:
        d = root / symbol
        out = []
        for p in d.glob("*.parquet") if d.is_dir() else []:
            s = p.stem
            if len(s) == 10 and s[4] == "-":
                out.append((s, p))
            elif len(s) == 8 and s.isdigit():
                out.append((f"{s[:4]}-{s[4:6]}-{s[6:]}", p))
        return sorted(out)


def load_ms(files: list[tuple[str, Path]], first_day: str, last_day: str) -> np.ndarray:
    """Unique, sorted broker-wall millisecond stamps from the day files in [first, last]."""
    parts = [_read_ms(p) for d, p in files if first_day <= d <= last_day]
    if not parts:
        return np.zeros(0, dtype="int64")
    return np.unique(np.concatenate(parts))


#: The tape's broker wall clock as NAIVE datetimes (it is not UTC; see state_conditioner).
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC).replace(tzinfo=None)


def _wall(ms: int) -> datetime:
    return _EPOCH + timedelta(milliseconds=int(ms))


def hour_rows(ms: np.ndarray, hours: Sequence[int]) -> list[dict[str, Any]]:
    """One row per hour start (broker ms) whose arrivals fit; uses ONLY ticks inside that hour."""
    rows: list[dict[str, Any]] = []
    for h in hours:
        lo = int(np.searchsorted(ms, h, side="left"))
        hi = int(np.searchsorted(ms, h + HOUR_MS, side="left"))
        seg = ms[lo:hi]
        if seg.size < MIN_EVENTS:
            continue
        seg = seg[-MAX_EVENTS:]
        horizon = (h + HOUR_MS - int(seg[0])) / 1000.0
        fit = fit_hawkes((seg - seg[0]) / 1000.0, horizon)
        if fit is None:
            continue
        end_utc = sc.broker_to_utc(_wall(h + HOUR_MS))
        rows.append({"event_time": sc.iso(end_utc), "available_time": sc.iso(end_utc),
                     "broker_hour": _wall(h).isoformat(timespec="seconds"),
                     **{k: fit[k] for k in COLUMNS if k in fit}})
    return rows


# ------------------------------------------------------------------------------------- one pass
def hypothesis_symbols(candidates: Sequence[str]) -> tuple[list[str], dict[str, int]]:
    try:
        from research.universe_policy import HYPOTHESIS, lane
    except Exception:
        return [], {"policy_unimportable": len(candidates)}
    keep: list[str] = []
    aside: dict[str, int] = {}
    for s in candidates:
        ln = lane(s)
        if ln == HYPOTHESIS:
            keep.append(s)
        else:
            aside[ln] = aside.get(ln, 0) + 1
    return keep, aside


def advance_symbol(sym: str, *, ticks: Path, series_root: Path | None, cursor: int | None,
                   now_broker_ms: int, now_utc: datetime) -> dict[str, Any]:
    """Fit every complete hour after `cursor` (bounded) and append it to the symbol's series."""
    files = day_files(sym, ticks)
    if not files:
        return {"status": "UNMEASURED", "why": "no tape day files"}
    last_ms = _read_ms(files[-1][1])
    if last_ms.size == 0:
        return {"status": "UNMEASURED", "why": "newest tape day file unreadable"}
    newest = min(int(last_ms.max()), now_broker_ms)
    current_hour = newest - newest % HOUR_MS          # the incomplete hour: never fitted
    floor_start = current_hour - BACKFILL_HOURS * HOUR_MS
    first_day = int((datetime.fromisoformat(files[0][0]) - _EPOCH)
                    .total_seconds() * 1000)
    # never walk hours before the tape's first day: a cold start fits from the first tick
    start = max(floor_start, first_day,
                (cursor + HOUR_MS) if cursor is not None else floor_start)
    hours = list(range(start, current_hour, HOUR_MS))[:MAX_HOURS_PER_PASS]
    sid = f"hawkes_{sym}"
    old = sc.read_series(sid, series_root)
    if not hours:
        return {"status": "CURRENT", "cursor": cursor, "rows": len(old), "new_rows": 0,
                "latest": old[-1] if old else None}
    ms = load_ms(files, _wall(hours[0]).date().isoformat(),
                 _wall(hours[-1] + HOUR_MS - 1).date().isoformat())
    new = hour_rows(ms, hours)
    hist = [_f(r.get("log_lambda_end")) for r in old]
    z = sc.trailing_z([*hist, *[r["log_lambda_end"] for r in new]], Z_WINDOW, Z_MIN)[len(hist):]
    stamp = sc.iso(now_utc)
    for r, zz in zip(new, z, strict=True):
        r["intensity_z"] = zz
        r["retrieval_time"] = stamp
        r["source_id"] = SEAT
    rows = [*old, *new][-MAX_ROWS:]
    if new:
        sc.write_series(sid, rows, ("broker_hour", "retrieval_time", *COLUMNS), series_root)
    return {"status": "MEASURED" if rows else "UNMEASURED", "cursor": hours[-1],
            "rows": len(rows), "new_rows": len(new), "hours_scanned": len(hours),
            "behind_hours": (current_hour - hours[-1]) // HOUR_MS - 1,
            "latest": rows[-1] if rows else None}


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def run(*, budget_s: float = 240.0, ticks: Path = TICKS, series_root: Path | None = None,
        state_path: Path = STATE, report: Path | None = REPORT, dry_run: bool = False,
        now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now_utc = now or datetime.now(UTC)
    now_broker_ms = int((sc.utc_to_broker(now_utc) - _EPOCH).total_seconds() * 1000)
    state = sc.load_json(state_path)
    cursors: dict[str, int] = {k: int(v) for k, v in (state.get("cursor") or {}).items()}
    tape_syms = sorted(d.name for d in ticks.iterdir() if d.is_dir()) if ticks.is_dir() else []
    syms, aside = hypothesis_symbols(tape_syms)
    syms.sort(key=lambda s: cursors.get(s, -1))      # stalest first, so backfill is shared fairly
    per: dict[str, Any] = {}
    unreached: list[str] = []
    for sym in syms:
        if time.monotonic() - t0 > budget_s:
            unreached.append(sym)
            continue
        try:
            res = advance_symbol(sym, ticks=ticks, series_root=series_root,
                                 cursor=cursors.get(sym), now_broker_ms=now_broker_ms,
                                 now_utc=now_utc)
        except Exception as exc:
            res = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}
        if res.get("cursor") is not None:
            cursors[sym] = int(res["cursor"])
        per[sym] = res
    state["cursor"] = cursors
    state["updated_utc"] = sc.iso(now_utc)
    if not dry_run:
        sc.write_json(state_path, {**sc.load_json(state_path), **state})
    # REGISTRATION: cells once per symbol whose series is long enough to be judged.
    grid: list[dict[str, Any]] = []
    for sym, res in per.items():
        if int(res.get("rows") or 0) >= MIN_ROWS_TO_MINT:
            grid += sc.cell_rows(SEAT, f"hawkes_{sym}", sym, ("intensity_z", "branching_ratio"),
                                 f"tick-arrival self-excitation of {sym} (Hawkes branching ratio "
                                 "and conditional intensity) as a volatility-burst state")
    minted = sc.mint_once(SEAT, grid, state_path, dry_run=dry_run)
    symbols: dict[str, Any] = {}
    for sym, res in sorted(per.items()):
        lt = res.get("latest") or {}
        symbols[sym] = {"status": res.get("status"), "why": res.get("why"),
                        "rows": res.get("rows"), "new_rows": res.get("new_rows"),
                        "behind_hours": res.get("behind_hours"),
                        "broker_hour": lt.get("broker_hour"),
                        "available_time": lt.get("available_time"),
                        **{k: _f(lt.get(k)) for k in COLUMNS},
                        "conditioner": sc.conditioner_specs(f"hawkes_{sym}", "intensity_z")}
    measured = sum(1 for v in symbols.values() if _f(v.get("branching_ratio")) is not None)
    verdict = ("UNMEASURED" if measured == 0 else
               "MEASURED" if measured == len(syms) and not unreached else "PARTIAL")
    doc = {"generated_utc": sc.iso(now_utc), "organ": SEAT, "verdict": verdict,
           "model": "exponential-kernel Hawkes, MLE: EM for (mu, n) on a beta log grid",
           "clock": ("broker-hour fits; available_time = true UTC of the hour's close; cells "
                     f"hold it back {sc.CELL_LAG_HOURS} h more"),
           "tape_symbols": len(tape_syms), "hypothesis_symbols": len(syms),
           "set_aside_by_lane": aside, "measured_symbols": measured,
           "unreached_in_budget": unreached,
           "branching_ratio_median": _median([v.get("branching_ratio") for v in symbols.values()]),
           "symbols": symbols, "minting": minted,
           "registered_as": {"lake_series": "data/lake/series/hawkes_<SYM>.csv",
                             "family": "exogenous_conditioner (signal intensity_z | "
                                       "branching_ratio)",
                             "second_axis": "params.conditioner = alt:hawkes_<SYM>:intensity_z:"
                                            "gt:2 (mt5desk.cell_modifiers)"},
           "elapsed_s": round(time.monotonic() - t0, 2), "budget_s": budget_s}
    if report is not None and not dry_run:
        sc.write_json(report, doc)
    return doc


def _median(xs: list[Any]) -> float | None:
    v = sorted(x for x in (_f(x) for x in xs) if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else 0.5 * (v[m - 1] + v[m])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run)
    print(f"hawkes_state: {doc['verdict']} measured={doc['measured_symbols']}/"
          f"{doc['hypothesis_symbols']} minted={doc['minting'].get('donated')} "
          f"elapsed={doc['elapsed_s']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
