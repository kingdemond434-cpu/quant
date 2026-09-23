"""The Digital Twin organ: one calibrated posterior of worlds per hunt-universe instrument, and
every sleeve and queued candidate judged across it (LAWS 5m; ledger U29/U30).

    python desks/mt5/research/digital_twin.py --once [--budget-s 600] [--dry-run] [--symbol X]

WHAT ONE PASS DOES (hourly cycle, execution department, 600 s). It walks the hypothesis-lane
universe (`universe_policy.may_hypothesise`, never a symbol list) from the rotation cursor, and
for each instrument the budget reaches: reads the newest window of bars (M5 where the desk holds
it, else H1) and, where the tick tape holds the same days, the per-bar spread, order-flow
imbalance and quote flicker; summarises the window; runs ABC-SMC over the latent worlds
(`libs.research.digital_twin.infer`); runs the posterior predictive checks group by group and
publishes the twin-vs-reality CALIBRATION SCORE (the share of measurable statistics the posterior
reproduces); PRE-REGISTERS the three canonical mechanisms (expected effect size per event, its
90% band, the events one window yields and the events a test needs at 80% power); and stores it
all under `data/digital_twin/<symbol>.json`. Then every LIVE/STANDBY sleeve and the newest
queued candidates whose instrument has a twin are run across the SAME sampled posterior worlds
at zero, actual and doubled spread -- the distribution of their outcome and the counterfactual
execution cost under the posterior -- and written to the registry as a `twin_robustness` memory
row and, for a candidate, into the `posterior_world_robustness` column the UniversalCell law
names.

UNMEASURED IS A VALUE. A twin whose posterior fails a predictive check is stored with its verdict
and the failing statistic, and no candidate gets a robustness number from a world that could not
reproduce the tape: the column stays NULL and the row says which statistic failed. A window too
short, a tape with no ticks, a family the twin cannot call -- each is named in the report.

MEMORY-SAFE ON 8 GB. Worlds per batch are DERIVED from measured free physical memory
(`libs.research.digital_twin.capacity`, the compiler's own rule), floored so an unreadable
counter changes nothing and capped so one twin cannot spend the hour.

THE TWIN ROUTES RESEARCH AND SIZES NOTHING. It never touches a fraction, a floor, a lot or a
sleeve's status; it publishes where a rule lives and where it dies, and the allocator remains
the organ that decides capital.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Callable
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

from libs.research import digital_twin as dt  # noqa: E402

UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE_JSON = UNIVERSE_DIR / "universe.json"
TICKS = DESK / "data" / "tape" / "ticks"
SLEEVES = DESK / "data" / "sleeves.json"
STORE = DESK / "data" / "digital_twin"
CURSOR = DESK / "data" / "digital_twin_cursor.json"
REPORT = DESK / "reports" / "DIGITAL_TWIN.json"

RULE = "the twin routes research and sizes nothing; a world that fails its check is UNMEASURED"
#: Bars per calibration window and simulator steps per bar, by chart. 30 days of H1; 3 of M5.
WINDOW_BARS: dict[str, int] = {"H1": 720, "M5": 864}
STEPS_PER_BAR: dict[str, int] = {"H1": 4, "M5": 2}
MIN_BARS = 200
#: Newest tick-day files read per instrument (bounded: the tape is per day, ~1 MB each).
MAX_TICK_DAYS = 6
N_ROUNDS = 3
PPC_DRAWS = 64
ROBUST_WORLDS = 32
MECHANISM_WORLDS = 32
MAX_TWINS_PER_PASS = 8
MAX_SLEEVE_EVALS = 16
MAX_CANDIDATES = 12
#: Share of the budget spent calibrating before the pass turns to evaluations.
CALIBRATION_SHARE = 0.6
SLEEVE_STATES = frozenset({"LIVE", "STANDBY"})
#: Family-name vocabulary -> proxy rule, when the desk's own family cannot run inside a world.
PROXY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("revers", "fade", "anti_", "gap_decay", "range_filter", "settlement", "close_"),
     "mean_reversion"),
    (("momentum", "trend", "lead_lag", "carry", "drift"), "momentum"),
    (("breakout", "donchian", "range_break"), "breakout"),
)
MECHANISMS: tuple[dt.Mechanism, ...] = (dt.mean_reversion_mechanism(), dt.momentum_mechanism(),
                                        dt.liquidation_cascade_mechanism())


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        # legal on POSIX, WinError 5 on the box that trades; the port that broke it is recorded
        path.chmod(0o644)
        os.replace(tmp, path)


def _free_phys_bytes() -> int | None:
    """Physical memory actually free, or None when the counter cannot be read (the floor then)."""
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


# ---------------------------------------------------------------------------- the universe

def _may_hypothesise(symbol: str) -> bool:
    """The lane fence, from MetaTrader's own registry via `universe_policy`; never a list."""
    try:
        from universe_policy import may_hypothesise
        return bool(may_hypothesise(symbol))
    except ImportError:
        return False


def hunt_universe() -> list[str]:
    doc = _read_json(UNIVERSE_JSON) or {}
    return sorted(str(s) for s in doc if isinstance(doc.get(s), dict) and _may_hypothesise(str(s)))


def universe_meta(symbol: str) -> dict[str, Any]:
    doc = _read_json(UNIVERSE_JSON) or {}
    row = doc.get(symbol)
    return dict(row) if isinstance(row, dict) else {}


def rotation(symbols: list[str], cursor: dict[str, Any] | None) -> list[str]:
    """The universe from the cursor's next index onward, wrapping: least recently calibrated
    first, in one fixed order on both boxes."""
    if not symbols:
        return []
    start = int((cursor or {}).get("next_index") or 0) % len(symbols)
    return symbols[start:] + symbols[:start]


# ---------------------------------------------------------------------------- the tape

def _tick_features(symbol: str, index: pd.DatetimeIndex, freq: str) -> dict[str, Any] | None:
    """Per-bar relative spread, order-flow imbalance (sided quote changes, unit size) and quote
    flicker from the newest tick-day files; None when the tape holds no ticks for the window."""
    tdir = TICKS / symbol
    if not tdir.is_dir():
        return None
    files = sorted(p for p in tdir.glob("*.parquet"))[-MAX_TICK_DAYS:]
    if not files:
        return None
    frames: list[pd.DataFrame] = []
    for p in files:
        try:
            frames.append(pd.read_parquet(p, columns=["time_msc", "bid", "ask"]))
        except (OSError, ValueError, KeyError):
            continue
    if not frames:
        return None
    t = pd.concat(frames, ignore_index=True)
    t = t[(t["bid"] > 0) & (t["ask"] >= t["bid"])]
    if t.empty:
        return None
    stamps = pd.to_datetime(t["time_msc"].to_numpy(dtype="int64"), unit="ms", utc=True)
    bar = stamps.floor(freq)
    bid = t["bid"].to_numpy(dtype=float)
    ask = t["ask"].to_numpy(dtype=float)
    mid = 0.5 * (bid + ask)
    rel = (ask - bid) / mid
    d_bid = np.sign(np.diff(bid, prepend=bid[0]))
    d_ask = np.sign(np.diff(ask, prepend=ask[0]))
    ofi = d_bid + d_ask
    d_mid = np.diff(mid, prepend=mid[0])
    nz = d_mid != 0
    sgn = np.sign(d_mid)
    prev = np.concatenate([[0.0], sgn[:-1]])
    flip = (nz & (prev != 0) & (sgn * prev < 0)).astype(float)
    df = pd.DataFrame({"bar": bar, "rel": rel, "ofi": ofi, "flip": flip, "nz": nz.astype(float)})
    g = df.groupby("bar")
    agg = pd.DataFrame({"rel": g["rel"].mean(), "ofi": g["ofi"].sum(),
                        "flip": g["flip"].sum(), "nz": g["nz"].sum()})
    agg = agg.reindex(index)
    covered = int(agg["rel"].notna().sum())
    if covered < max(24, len(index) // 10):
        return None
    with np.errstate(invalid="ignore", divide="ignore"):
        flicker = np.where(agg["nz"].to_numpy() > 4, agg["flip"].to_numpy() / agg["nz"].to_numpy(),
                           np.nan)
    return {"spread": agg["rel"].to_numpy(dtype=float), "flow": agg["ofi"].to_numpy(dtype=float),
            "flicker": flicker, "bars_covered": covered, "tick_days": [p.name for p in files]}


def load_window(symbol: str) -> tuple[dt.SimBars, dict[str, Any]] | None:
    """The newest calibration window and its provenance; None (with no exception) when the desk
    holds too few bars for a summary to mean anything."""
    tf = "M5" if (UNIVERSE_DIR / f"{symbol}_M5.parquet").exists() else "H1"
    path = UNIVERSE_DIR / f"{symbol}_{tf}.parquet"
    if not path.exists():
        return None
    try:
        bars = pd.read_parquet(path)
    except (OSError, ValueError):
        return None
    bars = bars.tail(WINDOW_BARS[tf])
    if len(bars) < MIN_BARS or not {"open", "high", "low", "close"} <= set(bars.columns):
        return None
    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    tod = ((idx.hour + idx.minute / 60.0) / 24.0).to_numpy(dtype=float)
    vol_col = "tick_volume" if "tick_volume" in bars.columns else None
    volume = bars[vol_col].to_numpy(dtype=float) if vol_col else np.full(len(bars), np.nan)
    ticks = _tick_features(symbol, idx, "1h" if tf == "H1" else "5min")
    spread = flow = flicker = None
    unmeasured: list[str] = []
    if ticks is not None:
        spread, flow, flicker = ticks["spread"], ticks["flow"], ticks["flicker"]
    else:
        meta = universe_meta(symbol)
        digits = meta.get("digits")
        if "spread" in bars.columns and isinstance(digits, int | float) and digits > 0:
            pts = bars["spread"].to_numpy(dtype=float)
            if np.nanmedian(pts) > 0:
                spread = pts * (10.0 ** -float(digits)) / bars["close"].to_numpy(dtype=float)
                spread = np.where(spread > 0, spread, np.nan)
        unmeasured += ["flow", "flicker"] + ([] if spread is not None else ["spread"])
    window = dt.tape_window(bars["open"].to_numpy(dtype=float), bars["high"].to_numpy(dtype=float),
                            bars["low"].to_numpy(dtype=float), bars["close"].to_numpy(dtype=float),
                            volume, tod, spread=spread, flow=flow, flicker=flicker,
                            steps_per_bar=STEPS_PER_BAR[tf])
    meta_out = {"timeframe": tf, "n_bars": len(bars), "start": idx[0].isoformat(),
                "end": idx[-1].isoformat(), "tick_days": (ticks or {}).get("tick_days") or [],
                "tick_bars_covered": (ticks or {}).get("bars_covered") or 0,
                "unmeasured_fields": unmeasured,
                "index": [int(v) for v in idx.asi8], "price_scale": float(bars["close"].iloc[0]),
                "volume_scale": float(np.nanmean(volume)) if np.isfinite(volume).any() else 1.0}
    return window, meta_out


# ---------------------------------------------------------------------------- calibration

def calibrate(symbol: str, window: dt.SimBars, meta: dict[str, Any], *, rng: np.random.Generator,
              n_particles: int, deadline: Callable[[], bool]) -> dict[str, Any]:
    """One instrument's twin: summary, posterior, predictive checks, mechanisms, participant mix."""
    started = time.monotonic()
    obs = dt.summarise(window)[0]
    tod = window.tod
    post = dt.infer(obs, dt.Prior(), n_bars=window.n_bars, steps_per_bar=window.steps_per_bar,
                    tod=tod, rng=rng, n_particles=n_particles, n_rounds=N_ROUNDS,
                    deadline=deadline)
    check = dt.ppc(post, obs, tod=tod, rng=rng, n_draws=PPC_DRAWS)
    score = dt.calibration_score(check)
    mean_world = np.array([[post.mean()[n] for n in dt.PARAM_NAMES]])
    mix = dt.participant_mix(dt.simulate(mean_world, window.n_bars, window.steps_per_bar, tod,
                                         rng, attribution=True))
    # the pre-registration: what a test of each canonical mechanism should expect on this
    # instrument BEFORE it runs -- effect size, its band, and the sample the power needs
    prereg: dict[str, dict[str, Any]] = {}
    for mech in MECHANISMS:
        if deadline():
            prereg[mech.name] = {"mechanism": mech.name, "verdict": "UNMEASURED", "why": "budget"}
            continue
        prereg[mech.name] = dt.preregister(mech, post, MECHANISM_WORLDS, tod=tod, rng=rng,
                                           deadline=deadline).to_dict()
    unmeasured_stats = [n for n, v in zip(dt.STAT_NAMES, obs, strict=True) if not np.isfinite(v)]
    return {
        "symbol": symbol, "calibrated_at": now_iso(), "rule": RULE,
        "window": {k: v for k, v in meta.items() if k != "index"},
        "index": meta.get("index"),
        "observed": {n: (None if not np.isfinite(v) else float(v))
                     for n, v in zip(dt.STAT_NAMES, obs, strict=True)},
        "unmeasured_statistics": unmeasured_stats,
        "posterior": post.to_dict(), "ppc": check.to_dict(), "verdict": check.verdict,
        "failing_statistics": check.failing, "calibration": score.to_dict(),
        "calibration_score": score.score, "participant_mix": mix,
        "preregistrations": prereg,
        "mechanisms": {k: v.get("verdict") for k, v in prereg.items()},
        "n_particles": n_particles, "elapsed_s": round(time.monotonic() - started, 1),
    }


def twin_path(symbol: str) -> Path:
    return STORE / f"{symbol}.json"


def load_twin(symbol: str) -> dict[str, Any] | None:
    doc = _read_json(twin_path(symbol))
    return doc if isinstance(doc, dict) and "posterior" in doc else None


def stored_twins() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if STORE.is_dir():
        for p in sorted(STORE.glob("*.json")):
            doc = _read_json(p)
            if isinstance(doc, dict) and "posterior" in doc:
                out[str(doc.get("symbol") or p.stem)] = doc
    return out


# ---------------------------------------------------------------------------- the rules

def _family_engine() -> Any:
    """The desk's own family registry and replay, through `synthetic_regimes` (one place answers
    "can this desk still call the thing it certified"); None when unreachable here."""
    try:
        import synthetic_regimes as sr
        return sr
    except ImportError:
        return None


RuleAt = Callable[[float], dt.StrategyRule]


def proxy_rule(family: str) -> tuple[RuleAt | None, str]:
    """A vocabulary proxy for a family the twin cannot call; the spread is charged by the twin,
    so the cost multiplier is the caller's and the rule ignores it."""
    fam = str(family or "").lower()
    for words, kind in PROXY_RULES:
        if any(w in fam for w in words):
            if kind == "mean_reversion":
                rule = dt.mean_reversion_rule(3)
            elif kind == "momentum":
                rule = dt.momentum_rule(5)
            else:
                rule = dt.breakout_rule(20)
            return (lambda _m, r=rule: r), f"proxy:{kind}"
    return None, "UNMEASURED:no rule vocabulary for family " + repr(family)


def rule_for(symbol: str, family: str, params: dict[str, Any], side: int, selector: str,
             twin: dict[str, Any]) -> tuple[RuleAt | None, str]:
    """The strategy as something a world can run, as a factory over the cost multiplier: the
    desk's family through its own replay when the family is price-only and callable here, else a
    vocabulary proxy, else UNMEASURED."""
    sr = _family_engine()
    fn = sr.family_fn(family) if sr is not None else None
    index = twin.get("index")
    if fn is None or not index:
        return proxy_rule(family)
    idx = pd.DatetimeIndex(np.asarray(index, dtype="int64"), tz="UTC")
    real = None
    tf = str((twin.get("window") or {}).get("timeframe") or "H1")
    path = UNIVERSE_DIR / f"{symbol}_{tf}.parquet"
    if path.exists():
        try:
            real = pd.read_parquet(path).tail(len(idx))
        except (OSError, ValueError):
            real = None
    try:
        from mt5desk.family_inputs import resolve, strip_identity_keys
        extra, why = resolve(symbol, family, params, real)
    except Exception as exc:
        return None, f"UNMEASURED:family inputs unavailable: {type(exc).__name__}"
    if extra is None:
        return None, f"UNMEASURED:inputs unresolvable: {why}"
    if extra:
        return None, "UNMEASURED:family needs inputs outside the twin: " + ",".join(sorted(extra))
    call_params = dict(strip_identity_keys(family, params))
    meta = universe_meta(symbol)
    cost_px = float(sr._per_unit_cost(meta, 1.0)) if meta else 0.0
    price_scale = float((twin.get("window") or {}).get("price_scale") or 1.0)
    volume_scale = float((twin.get("window") or {}).get("volume_scale") or 1.0)
    digits = meta.get("digits")
    point = 10.0 ** -float(digits) if isinstance(digits, int | float) and digits > 0 else 1e-5

    def rule_at(cost_mult: float) -> dt.StrategyRule:
        def rule(world: dt.WorldBars) -> float:
            n = min(len(idx), world.close.size)
            vol = world.volume[:n]
            vscale = volume_scale / max(float(np.mean(vol)), 1e-9)
            df = pd.DataFrame({
                "open": world.open[:n] * price_scale, "high": world.high[:n] * price_scale,
                "low": world.low[:n] * price_scale, "close": world.close[:n] * price_scale,
                "tick_volume": np.rint(vol * vscale).astype("int64"),
                "spread": np.rint(np.nan_to_num(world.spread[:n]) * world.close[:n] * price_scale
                                  / point).astype("int64"),
                "real_volume": np.zeros(n, dtype="int64")}, index=idx[:n])
            sigs = sr._signals(fn, df, side, call_params, selector)
            if not sigs:
                return 0.0
            rs = sr._minimal_replay(df, sigs, cost_px * cost_mult)
            return float(sum(rs)) if rs else 0.0
        return rule

    return rule_at, "family_engine"


# ---------------------------------------------------------------------------- the subjects

def sleeve_subjects() -> list[dict[str, Any]]:
    doc = _read_json(SLEEVES) or {}
    out = []
    for row in doc.get("sleeves") or []:
        if str(row.get("status") or "").upper() not in SLEEVE_STATES:
            continue
        sym, fam = str(row.get("symbol") or ""), str(row.get("family") or "")
        if not sym or not fam:
            continue
        side = -1 if str(row.get("side") or "").upper() in {"SHORT", "-1"} else 1
        out.append({"name": str(row.get("name") or ""), "kind": "sleeve", "symbol": sym,
                    "family": fam, "params": dict(row.get("params") or {}), "side": side,
                    "selector": str(row.get("session") or row.get("selector") or ""),
                    "status": str(row.get("status")).upper()})
    return out


def candidate_subjects(limit: int) -> list[dict[str, Any]]:
    """The newest queued candidates, straight from the registry."""
    try:
        from libs.moat import registry as R
        conn = R.connect()
    except Exception:
        return []
    try:
        rows = conn.execute(
            "SELECT id, family, symbol, params_json, session, created_at FROM research_candidates "
            "WHERE status='queued' ORDER BY created_at DESC LIMIT ?", (int(limit),)).fetchall()
    except Exception:
        return []
    finally:
        conn.close()
    out = []
    for r in rows:
        try:
            params = json.loads(r["params_json"] or "{}")
        except ValueError:
            params = {}
        out.append({"name": str(r["id"]), "kind": "candidate", "symbol": str(r["symbol"] or ""),
                    "family": str(r["family"] or ""), "params": params if isinstance(params, dict)
                    else {}, "side": 1, "selector": str(r["session"] or ""),
                    "created_at": str(r["created_at"] or "")})
    return out


def evaluate(subject: dict[str, Any], twin: dict[str, Any], *, rng: np.random.Generator,
             deadline: Callable[[], bool]) -> dict[str, Any]:
    """One subject across one twin's posterior worlds. The robustness number is carried only
    when the twin reproduces the tape (a REALISTIC verdict, partial or not)."""
    post = dt.Posterior.from_dict(twin["posterior"])
    tod = np.asarray([((pd.Timestamp(v, tz="UTC").hour + pd.Timestamp(v, tz="UTC").minute / 60.0)
                       / 24.0) for v in (twin.get("index") or [])], dtype=float)
    if tod.shape[0] != post.n_bars:
        tod = (np.arange(post.n_bars) % 24) / 24.0
    rule_at, basis = rule_for(subject["symbol"], subject["family"], subject["params"],
                              int(subject["side"]), subject["selector"], twin)
    row: dict[str, Any] = {"name": subject["name"], "kind": subject["kind"],
                           "symbol": subject["symbol"], "family": subject["family"],
                           "basis": basis, "twin_verdict": twin.get("verdict"),
                           "twin_failing": twin.get("failing_statistics") or [],
                           "twin_calibration_score": twin.get("calibration_score"),
                           "evaluated_at": now_iso(), "posterior_world_robustness": None}
    if rule_at is None:
        row["robustness"] = {"verdict": "UNMEASURED"}
        row["execution_cost"] = {"verdict": "UNMEASURED"}
        return row
    # one set of worlds for everything below: the robustness at actual cost, and the same rule
    # at zero and doubled spread -- the counterfactual execution cost under the posterior
    bars = dt.simulate_posterior(post, ROBUST_WORLDS, tod=tod, rng=rng)
    rb = dt.robustness(rule_at(1.0), post, ROBUST_WORLDS, tod=tod, rng=rng, deadline=deadline,
                       bars=bars)
    row["robustness"] = rb.to_dict()
    ec = dt.execution_cost(rule_at, post, ROBUST_WORLDS, tod=tod, rng=rng, deadline=deadline,
                           bars=bars)
    row["execution_cost"] = ec.to_dict()
    # the pre-registered expectation for this subject's own test: the outcome band across
    # worlds, stated before the forward tape has spoken
    row["expected_outcome"] = ({"mean": rb.mean, **rb.quantiles} if rb.n_worlds else None)
    realistic = str(twin.get("verdict") or "").startswith("REALISTIC")
    if realistic and rb.verdict != "UNMEASURED":
        row["posterior_world_robustness"] = rb.p_positive
    elif rb.verdict != "UNMEASURED":
        row["robustness"]["carried"] = False
        row["robustness"]["why"] = f"twin {twin.get('verdict')}: no number from a world that " \
                                   f"could not reproduce the tape"
    return row


def record(rows: list[dict[str, Any]]) -> int:
    """The registry rows: one `twin_robustness` memory per subject (an upsert on its key) and
    the candidate columns. Returns rows written; never raises into the pass."""
    if not rows:
        return 0
    try:
        from libs.moat import registry as R
    except Exception:
        return 0
    n = 0
    try:
        conn = R.connect()
    except Exception:
        return 0
    try:
        for row in rows:
            rb = row.get("robustness") or {}
            verdict = str(rb.get("verdict") or "UNMEASURED")
            pwr = row.get("posterior_world_robustness")
            statement = (f"{row['kind']} {row['name']} on {row['symbol']} across the "
                         f"{row['symbol']} twin ({row.get('twin_verdict')}): {verdict}"
                         + (f", p_positive={pwr}" if pwr is not None else ", UNMEASURED"))
            R.remember("digital_twin", statement, kind="twin_robustness",
                       memory_key=f"twin_robustness:{row['kind']}:{row['name']}",
                       result=verdict,
                       metrics={"posterior_world_robustness": pwr, "n_worlds": rb.get("n_worlds"),
                                "mean": rb.get("mean"), "cvar_10": rb.get("cvar_10")},
                       payload=row, conn=conn)
            n += 1
            if row["kind"] == "candidate":
                conn.execute("UPDATE research_candidates SET posterior_world_robustness=?, "
                             "simulator_family=? WHERE id=?",
                             (pwr, f"digital_twin:{row.get('twin_verdict')}", row["name"]))
        conn.commit()
    except Exception as exc:
        print(f"digital_twin: registry rows not written: {type(exc).__name__}: {exc}", flush=True)
    finally:
        conn.close()
    return n


# ---------------------------------------------------------------------------- the pass

def run(*, budget_s: float = 600.0, dry_run: bool = False,
        symbols: list[str] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    calib_deadline = started + budget_s * CALIBRATION_SHARE
    hard_deadline = started + budget_s
    rng = np.random.default_rng(int(time.time()) % (2 ** 31))
    universe = hunt_universe()
    cursor = _read_json(CURSOR) if CURSOR.exists() else None
    cursor = cursor if isinstance(cursor, dict) else {}
    order = rotation(universe, cursor)
    if symbols:
        wanted = {s.upper() for s in symbols}
        order = [s for s in order if s.upper() in wanted]
    free = _free_phys_bytes()
    n_particles = dt.capacity(free, WINDOW_BARS["H1"], STEPS_PER_BAR["H1"])

    calibrated: list[dict[str, Any]] = []
    unmeasured: list[dict[str, Any]] = []
    fresh: dict[str, dict[str, Any]] = {}
    next_index = int(cursor.get("next_index") or 0) % max(len(universe), 1)
    for sym in order:
        if len(calibrated) >= MAX_TWINS_PER_PASS or time.monotonic() > calib_deadline:
            break
        loaded = load_window(sym)
        if loaded is None:
            unmeasured.append({"symbol": sym, "why": f"fewer than {MIN_BARS} bars or no chart"})
            if not symbols:
                next_index = (universe.index(sym) + 1) % len(universe)
            continue
        window, meta = loaded
        doc = calibrate(sym, window, meta, rng=rng, n_particles=n_particles,
                        deadline=lambda: time.monotonic() > calib_deadline)
        if not dry_run:
            _atomic(twin_path(sym), doc)
        calibrated.append({"symbol": sym, "timeframe": meta["timeframe"], "n_bars": meta["n_bars"],
                           "verdict": doc["verdict"], "failing": doc["failing_statistics"],
                           "calibration_score": doc["calibration_score"],
                           "calibration": doc["calibration"],
                           "unmeasured_statistics": doc["unmeasured_statistics"],
                           "n_particles": n_particles,
                           "posterior_n": len(doc["posterior"]["particles"]),
                           "elapsed_s": doc["elapsed_s"], "mechanisms": doc["mechanisms"],
                           "preregistrations": doc["preregistrations"],
                           "participant_mix": doc["participant_mix"]})
        fresh[sym] = doc
        if not symbols:
            next_index = (universe.index(sym) + 1) % len(universe)

    # the twins on disk plus, on a dry run, the ones just built in memory (nothing is written)
    twins = stored_twins()
    twins.update(fresh)
    previous = _read_json(REPORT) if REPORT.exists() else None
    prev_eval: dict[str, str] = {}
    if isinstance(previous, dict):
        for r in previous.get("evaluations") or []:
            prev_eval[f"{r.get('kind')}:{r.get('name')}"] = str(r.get("evaluated_at") or "")
    subjects = [s for s in sleeve_subjects() if s["symbol"] in twins]
    subjects.sort(key=lambda s: (prev_eval.get(f"sleeve:{s['name']}", ""), s["name"]))
    subjects = subjects[:MAX_SLEEVE_EVALS]
    cands = [c for c in candidate_subjects(MAX_CANDIDATES * 4) if c["symbol"] in twins]
    subjects += cands[:MAX_CANDIDATES]
    evaluations: list[dict[str, Any]] = []
    for subj in subjects:
        if time.monotonic() > hard_deadline:
            break
        try:
            evaluations.append(evaluate(subj, twins[subj["symbol"]], rng=rng,
                                        deadline=lambda: time.monotonic() > hard_deadline))
        except Exception as exc:
            evaluations.append({**{k: subj[k] for k in ("name", "kind", "symbol", "family")},
                                "basis": f"UNMEASURED:evaluation raised {type(exc).__name__}",
                                "robustness": {"verdict": "UNMEASURED"},
                                "posterior_world_robustness": None, "evaluated_at": now_iso()})
    n_rows = 0 if dry_run else record(evaluations)

    verdicts: dict[str, int] = {}
    scores: list[float] = []
    for doc in twins.values():
        key = str(doc.get("verdict") or "UNMEASURED").split(":", 1)[0]
        verdicts[key] = verdicts.get(key, 0) + 1
        sc = doc.get("calibration_score")
        if isinstance(sc, int | float) and math.isfinite(float(sc)):
            scores.append(float(sc))
    # THE PUBLISHED TWIN-VS-REALITY SCORE: across every stored twin, the share of measurable
    # statistics the posterior reproduces. A universe with no scored twin publishes None.
    calibration = {
        "score_mean": round(float(np.mean(scores)), 4) if scores else None,
        "score_min": round(float(np.min(scores)), 4) if scores else None,
        "score_median": round(float(np.median(scores)), 4) if scores else None,
        "n_scored": len(scores), "n_twins": len(twins),
        "n_realistic": sum(1 for d in twins.values()
                           if str(d.get("verdict") or "").startswith("REALISTIC")),
        "worst": sorted(((d.get("calibration") or {}).get("worst_statistic"), s)
                        for s, d in twins.items() if d.get("calibration"))[:5],
    }
    report = {
        "at": now_iso(), "rule": RULE, "budget_s": budget_s, "dry_run": dry_run,
        "elapsed_s": round(time.monotonic() - started, 1),
        "memory": {"free_mb": None if free is None else round(free / 1e6),
                   "worlds_per_batch": n_particles, "derived_from": "measured free physical memory"
                   if free is not None else "unreadable counter: the floor"},
        "universe": {"hunt": len(universe), "with_twin": len(twins),
                     "cursor_next_index": next_index,
                     "next_symbol": universe[next_index] if universe else None},
        "calibrated": calibrated, "unmeasured": unmeasured,
        "calibration": calibration,
        "twins": {s: {"verdict": d.get("verdict"), "failing": d.get("failing_statistics") or [],
                      "calibration_score": d.get("calibration_score"),
                      "calibrated_at": d.get("calibrated_at"),
                      "timeframe": (d.get("window") or {}).get("timeframe"),
                      "mechanisms": d.get("mechanisms") or {}}
                  for s, d in sorted(twins.items())},
        "twin_verdicts": verdicts,
        "evaluations": evaluations,
        "evaluation_counts": {
            "sleeves": sum(1 for e in evaluations if e["kind"] == "sleeve"),
            "candidates": sum(1 for e in evaluations if e["kind"] == "candidate"),
            "carried": sum(1 for e in evaluations
                           if e.get("posterior_world_robustness") is not None),
            "unmeasured": sum(1 for e in evaluations
                              if (e.get("robustness") or {}).get("verdict") == "UNMEASURED"),
        },
        "registry_rows": n_rows,
    }
    if not dry_run:
        _atomic(CURSOR, {"next_index": next_index, "updated_at": now_iso(),
                         "universe_n": len(universe),
                         "last_calibrated": [c["symbol"] for c in calibrated]})
        _atomic(REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode; the clock is "
                                                        "the hourly cycle's validate department)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="calibrate and print; write nothing")
    ap.add_argument("--symbol", action="append", default=None,
                    help="restrict to these symbols (diagnosis)")
    args = ap.parse_args(argv)
    report = run(budget_s=args.budget_s, dry_run=args.dry_run, symbols=args.symbol)
    print(f"digital twin: {len(report['calibrated'])} twin(s) calibrated this pass, "
          f"{report['universe']['with_twin']}/{report['universe']['hunt']} instruments with a "
          f"twin, calibration score mean {report['calibration']['score_mean']}, "
          f"{report['evaluation_counts']['sleeves']} sleeve(s) and "
          f"{report['evaluation_counts']['candidates']} candidate(s) judged, "
          f"{report['evaluation_counts']['carried']} carried, {report['registry_rows']} registry "
          f"row(s), worlds/batch {report['memory']['worlds_per_batch']}, {report['elapsed_s']}s")
    for c in report["calibrated"]:
        print(f"    {c['symbol']:<10}{c['timeframe']:>4}  {c['verdict']:<28} score="
              f"{c['calibration_score']} {c['elapsed_s']:>7.1f}s  mechanisms={c['mechanisms']}")
    for e in report["evaluations"][:12]:
        rb = e.get("robustness") or {}
        print(f"    {e['kind']:<9} {e['name'][:40]:<40} {e['symbol']:<8} {rb.get('verdict')}"
              f" p+={e.get('posterior_world_robustness')} ({e.get('basis')})")
    if args.dry_run:
        print("--dry-run: nothing written, no store, no cursor, no registry row")
        return 0
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
