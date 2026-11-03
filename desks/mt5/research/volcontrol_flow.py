"""VOL-CONTROL AND RISK-PARITY DELEVERAGING ESTIMATOR -- pure price, from the bars on disk.

    python desks/mt5/research/volcontrol_flow.py --once

THE PLAYER. Volatility-target funds, risk-control index products and risk-parity books hold an
exposure set by a rule, not by a view: exposure = target vol / realised vol, capped at a maximum
leverage, and re-set every day. When realised vol jumps their rule forces them to sell, whatever
they think; when it decays the same rule forces them to buy back. The rule and its usual
parameters are public (risk-control index methodologies publish their target, cap and lookbacks),
so the flow they must do tomorrow is computable today from price alone. That is the whole
mechanism, and it is why nothing here needs data the desk does not already hold.

WHAT IT ESTIMATES, per equity-index CFD in the Fusion registry with bars on disk:

  vol_1m, vol_3m    EWMA realised vol of daily log returns, half-lives 21 and 63 trading days,
                    annualised (sqrt 252). The two lookbacks bracket the published methodologies.
  exposure          mean over the two lookbacks of min(LEVERAGE_CAP, TARGET_VOL / vol_k).
  flow              exposure_t - exposure_{t-1}: the day's implied forced trade, as a fraction of
                    the strategy's capital (negative = forced selling).
  flow_z            flow z-scored against its own trailing year.
  rp_equity_exposure, rp_flow   (only when bonds AND gold bars are on disk) the equity sleeve of
                    a naive inverse-vol risk-parity book (index, UST10Y / UKGILT, XAUUSD) levered
                    to TARGET_VOL with the EWMA covariance; its day-on-day change is the
                    risk-parity deleveraging flow.

PIT. Every value at day t uses returns up to and including day t's close only (EWMA and rolling
windows are causal). `available_time` is the daily bar's CLOSE on the broker clock minus two
hours -- the broker runs UTC+2 in winter and UTC+3 in summer, so this is never earlier than the
true UTC close -- and the hypotheses carry `lag_hours = 3` on top, applied by the family before
any join. The frame is a deterministic function of the bars and is rebuilt each pass; the latest
row per symbol is ALSO appended to `volcontrol_flow_vintages.csv`, append-only, so what the desk
saw on each day is kept even if a bar is later revised.

ARTIFACTS:
  data/lake/series/volcontrol_flow.csv        wide, one row per day: `<SYM>__flow`,
                                              `<SYM>__exposure`, `<SYM>__flow_z`, ... + available_time
  data/lake/series/volcontrol_flow.pit.json   the PIT sidecar
  data/lake/series/volcontrol_flow_vintages.csv  append-only daily vintages
  reports/VOLCONTROL_FLOW.json                features now, per symbol, and the hypothesis ledger
  data/intelligence/volcontrol_flow/          EXACT_RECIPE donations, each hypothesis ONCE

HYPOTHESES, PRE-REGISTERED, CHARGED ONCE (`data/volcontrol/emitted.jsonl` is the once-ledger):
  per index      follow the forced flow (exogenous_conditioner on `<SYM>__flow`, level_z >= 2,
                 side +1: forced buying lifts, forced selling presses) and the exposure-rebuild
                 (on `<SYM>__exposure`, level_z, side -1: a book sold out after a vol spike must
                 buy back as vol decays, so depleted exposure leans long).
  related FX     USDJPY and AUDJPY on US500's forced flow (side +1: equity deleveraging is risk
                 reduction, which buys the yen).
  risk parity    US500 on the risk-parity equity flow, side +1, when that sleeve is measurable.
A symbol with no bars is UNMEASURED by name and gets no hypothesis; nothing is ever re-donated.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE = UNIVERSE_DIR / "universe.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
SOURCE = "volcontrol_flow"
SERIES = SERIES_DIR / f"{SOURCE}.csv"
SIDECAR = SERIES_DIR / f"{SOURCE}.pit.json"
VINTAGES = SERIES_DIR / f"{SOURCE}_vintages.csv"
STATE_DIR = DESK / "data" / "volcontrol"
EMITTED = STATE_DIR / "emitted.jsonl"
INTEL = DESK / "data" / "intelligence" / SOURCE
OUT = DESK / "reports" / "VOLCONTROL_FLOW.json"

TARGET_VOL = 0.10            # the common published risk-control target
LEVERAGE_CAP = 1.5           # the common published maximum exposure
HALF_LIVES = {"1m": 21, "3m": 63}
ANNUAL = 252
MIN_DAYS = 300               # a year of history plus warm-up before any value is published
FLOW_Z_WINDOW = 252
BROKER_UTC_MIN_OFFSET_H = 2  # winter offset; the summer offset (3) makes this conservative
LAG_HOURS = 3
BOND_PROXIES = ("UST10Y", "UKGILT", "UST05Y")
GOLD = "XAUUSD"
FX_RELATED = ("USDJPY", "AUDJPY")
FX_DRIVER = "US500"
EXCLUDE_INDEX = frozenset({"USDX"})   # a dollar index, not an equity book

Loader = Callable[[str], Any]


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _read_json(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, p)
    finally:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()


def index_symbols(path: Path = UNIVERSE) -> list[str]:
    """Equity-index CFDs from the registry's own asset class (never a hard-coded list)."""
    doc = _read_json(path, {}) or {}
    return sorted(k for k, v in doc.items() if isinstance(v, dict)
                  and str(v.get("asset_class") or "").strip().lower() in {"indices", "index"}
                  and k not in EXCLUDE_INDEX)


def load_daily_close(symbol: str, universe_dir: Path = UNIVERSE_DIR) -> Any:
    """Daily closes from the densest chart on disk (D1, else H4, else H1), or None."""
    import pandas as pd
    for tf in ("D1", "H4", "H1"):
        p = universe_dir / f"{symbol}_{tf}.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p, columns=["close"])
        except Exception:
            continue
        if df.empty:
            continue
        s = pd.to_numeric(df["close"], errors="coerce")
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        s.index = idx
        s = s[s > 0].dropna().sort_index()
        s = s[~s.index.duplicated(keep="last")]
        daily = s.groupby(s.index.floor("D")).last()
        return daily if len(daily) else None
    return None


# ------------------------------------------------------------------ the model (pure)
def ewma_vol(returns: Any, half_life: int) -> Any:
    """Causal EWMA vol of daily log returns, annualised."""
    import numpy as np
    var = (returns ** 2).ewm(halflife=half_life, min_periods=max(10, half_life)).mean()
    return np.sqrt(var * ANNUAL)


def vol_target_exposure(vol: Any, target: float = TARGET_VOL, cap: float = LEVERAGE_CAP) -> Any:
    import numpy as np
    return (target / vol.replace(0.0, np.nan)).clip(upper=cap)


def estimate(close: Any, *, target: float = TARGET_VOL, cap: float = LEVERAGE_CAP) -> Any:
    """Daily frame: vol_1m, vol_3m, exposure_1m, exposure_3m, exposure, flow, flow_z."""
    import numpy as np
    import pandas as pd
    r = np.log(close).diff()
    out = pd.DataFrame(index=close.index)
    exps = []
    for k, hl in HALF_LIVES.items():
        v = ewma_vol(r, hl)
        out[f"vol_{k}"] = v
        e = vol_target_exposure(v, target, cap)
        out[f"exposure_{k}"] = e
        exps.append(e)
    out["exposure"] = pd.concat(exps, axis=1).mean(axis=1, skipna=False)
    out["flow"] = out["exposure"].diff()
    mu = out["flow"].rolling(FLOW_Z_WINDOW, min_periods=60).mean()
    sd = out["flow"].rolling(FLOW_Z_WINDOW, min_periods=60).std(ddof=0)
    out["flow_z"] = (out["flow"] - mu) / sd.replace(0.0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def risk_parity(closes: dict[str, Any], *, equity: str, target: float = TARGET_VOL,
                cap: float = 3.0, half_life: int = 63) -> Any:
    """Equity sleeve of an inverse-vol book levered to `target` with the EWMA covariance.

    Weights w_i ∝ 1/vol_i; portfolio vol sqrt(w' Σ w); leverage = min(cap, target / that).
    Returns a frame with rp_equity_exposure and rp_flow, causal at every row."""
    import numpy as np
    import pandas as pd
    rets = pd.DataFrame({k: np.log(v).diff() for k, v in closes.items()}).dropna(how="any")
    if len(rets) < MIN_DAYS or equity not in rets.columns:
        return None
    cov = rets.ewm(halflife=half_life, min_periods=half_life).cov() * ANNUAL
    names = list(rets.columns)
    exp_eq = []
    for t in rets.index:
        try:
            m = cov.loc[t].reindex(index=names, columns=names).to_numpy(dtype=float)
        except KeyError:
            exp_eq.append(np.nan)
            continue
        if not np.all(np.isfinite(m)):
            exp_eq.append(np.nan)
            continue
        vol = np.sqrt(np.clip(np.diag(m), 1e-12, None))
        w = (1.0 / vol) / np.sum(1.0 / vol)
        pv = math.sqrt(max(float(w @ m @ w), 1e-12))
        lev = min(cap, target / pv)
        exp_eq.append(float(w[names.index(equity)] * lev))
    out = pd.DataFrame({"rp_equity_exposure": exp_eq}, index=rets.index)
    out["rp_flow"] = out["rp_equity_exposure"].diff()
    return out


# ------------------------------------------------------------------ the frame
def available_time(day_index: Any) -> Any:
    """A daily bar labelled D (broker clock) closes at D+1 00:00 broker; minus the SMALLER
    broker offset is never earlier than the true UTC close."""
    import pandas as pd
    return day_index + pd.Timedelta(days=1) - pd.Timedelta(hours=BROKER_UTC_MIN_OFFSET_H)


def build(symbols: Iterable[str], loader: Loader = load_daily_close
          ) -> tuple[Any, dict[str, dict[str, Any]], dict[str, str]]:
    """(wide frame, per-symbol latest features, per-symbol UNMEASURED reasons)."""
    import pandas as pd
    cols: dict[str, Any] = {}
    latest: dict[str, dict[str, Any]] = {}
    missing: dict[str, str] = {}
    closes: dict[str, Any] = {}
    for sym in symbols:
        c = loader(sym)
        if c is None or len(c) < MIN_DAYS:
            missing[sym] = ("no bars on disk" if c is None
                            else f"{len(c)} daily closes < {MIN_DAYS}")
            continue
        closes[sym] = c
        est = estimate(c)
        for k in ("exposure", "flow", "flow_z", "vol_1m", "vol_3m"):
            cols[f"{sym}__{k}"] = est[k]
        last = est.dropna(subset=["exposure"]).tail(1)
        if not last.empty:
            row = last.iloc[0]
            latest[sym] = {"day": last.index[0].date().isoformat(),
                           **{k: (None if pd.isna(row[k]) else round(float(row[k]), 6))
                              for k in ("vol_1m", "vol_3m", "exposure", "flow", "flow_z")}}
    # RISK PARITY: US500 (or the first index measured) with a bond proxy and gold.
    eq = FX_DRIVER if FX_DRIVER in closes else next(iter(sorted(closes)), None)
    bond, bond_close = None, None
    for b in BOND_PROXIES:
        bond_close = loader(b)
        if bond_close is not None:
            bond = b
            break
    gold = loader(GOLD)
    rp_state = "UNMEASURED"
    if eq and bond and gold is not None:
        rp = risk_parity({eq: closes[eq], bond: bond_close, GOLD: gold}, equity=eq)
        if rp is not None:
            cols["RP__equity_exposure"] = rp["rp_equity_exposure"]
            cols["RP__equity_flow"] = rp["rp_flow"]
            rp_state = f"OK ({eq} / {bond} / {GOLD})"
    if not eq or not bond or gold is None:
        missing["RP"] = (f"risk parity needs an index, a bond proxy {BOND_PROXIES} and {GOLD} "
                         f"bars; have index={eq}, bond={bond}, gold={gold is not None}")
    if not cols:
        return None, latest, missing
    wide = pd.DataFrame(cols).sort_index()
    wide = wide.dropna(how="all")
    wide.insert(0, "available_time", [t.isoformat() for t in available_time(wide.index)])
    latest["_risk_parity"] = {"state": rp_state}
    return wide.reset_index(drop=True), latest, missing


def write_outputs(wide: Any, latest: dict[str, dict[str, Any]], now: datetime, *,
                  series: Path = SERIES, vintages: Path = VINTAGES, sidecar: Path = SIDECAR
                  ) -> int:
    _write_atomic(series, wide.to_csv(index=False))
    side = {"series": SOURCE, "layout": "wide", "clock": "utc (upper bound)",
            "available_time_rule": ("daily bar close on the broker clock minus "
                                    f"{BROKER_UTC_MIN_OFFSET_H}h: never earlier than the true UTC "
                                    "close; every value uses returns to that close only"),
            "rebuilt_each_pass": True, "vintages": vintages.name,
            "model": {"target_vol": TARGET_VOL, "leverage_cap": LEVERAGE_CAP,
                      "ewma_half_lives_days": HALF_LIVES, "flow_z_window_days": FLOW_Z_WINDOW},
            "lag_hours_in_hypotheses": LAG_HOURS, "writer": "desks/mt5/research/volcontrol_flow.py"}
    _write_atomic(sidecar, json.dumps(side, indent=1) + "\n")
    rows = [{"recorded_at": _iso(now), "symbol": s, **v} for s, v in latest.items()
            if not s.startswith("_")]
    if not rows:
        return 0
    fields = ["recorded_at", "symbol", "day", "vol_1m", "vol_3m", "exposure", "flow", "flow_z"]
    new = not vintages.exists() or vintages.stat().st_size == 0
    seen = set()
    if not new:
        with contextlib.suppress(OSError), vintages.open("r", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                seen.add((r.get("symbol"), r.get("day")))
    fresh = [r for r in rows if (r["symbol"], r["day"]) not in seen]
    vintages.parent.mkdir(parents=True, exist_ok=True)
    with vintages.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in fresh:
            w.writerow(r)
    return len(fresh)


# ------------------------------------------------------------------ hypotheses, charged once
def hypothesis_id(symbol: str, family: str, params: dict[str, Any]) -> str:
    blob = json.dumps({"s": symbol, "f": family, "p": params}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def _cond(signal: str, side: int, threshold: float, ttl: int) -> dict[str, Any]:
    return {"source": SOURCE, "signal": signal, "transform": "level_z", "threshold": threshold,
            "side_when_high": side, "lag_hours": LAG_HOURS, "z_window": FLOW_Z_WINDOW,
            "ttl_bars": ttl}


def specs(columns: Iterable[str], hypothesis_lane: Callable[[str], bool]) -> list[dict[str, Any]]:
    cols = set(columns)
    out: list[dict[str, Any]] = []

    def add(sym: str, key: str, params: dict[str, Any], mech: str) -> None:
        if params["signal"] in cols and hypothesis_lane(sym):
            fam = "exogenous_conditioner"
            out.append({"id": hypothesis_id(sym, fam, params), "key": key, "symbol": sym,
                        "family": fam, "params": params, "mechanism": mech})

    for c in sorted(cols):
        if not c.endswith("__flow") or c.startswith("RP__"):
            continue
        sym = c[: -len("__flow")]
        add(sym, "volcontrol_flow_follow", _cond(f"{sym}__flow", +1, 2.0, 24),
            "vol-target funds must trade exposure = target/realised vol; a 2-sigma forced flow "
            "presses price in its own direction")
        add(sym, "volcontrol_exposure_rebuild", _cond(f"{sym}__exposure", -1, 1.5, 120),
            "depleted vol-target exposure after a vol spike must be bought back as vol decays; "
            "high exposure has only selling left to do")
    for fx in FX_RELATED:
        add(fx, "volcontrol_fx_riskoff", _cond(f"{FX_DRIVER}__flow", +1, 2.0, 24),
            "forced equity deleveraging is risk reduction and buys the yen; forced re-leveraging "
            "sells it")
    add(FX_DRIVER, "riskparity_flow_follow", _cond("RP__equity_flow", +1, 2.0, 24),
        "a risk-parity book levered to a vol target sheds its equity sleeve when covariance "
        "rises; the forced flow presses price in its direction")
    return out


def _lane(sym: str) -> bool:
    try:
        import universe_policy as up
        return bool(up.lane(sym) == up.HYPOTHESIS)
    except Exception:
        return False


def _emitted(path: Path) -> set[str]:
    ids: set[str] = set()
    with contextlib.suppress(OSError), path.open("r", encoding="utf-8") as fh:
        for line in fh:
            with contextlib.suppress(ValueError):
                ids.add(str(json.loads(line).get("id") or ""))
    ids.discard("")
    return ids


def emit(all_specs: list[dict[str, Any]], now: datetime, *, emitted_path: Path = EMITTED,
         intel_dir: Path = INTEL) -> dict[str, Any]:
    done = _emitted(emitted_path)
    new = [s for s in all_specs if s["id"] not in done]
    f = None
    if new:
        rows = [{"source": SOURCE, "kind": "hypothesis", "family": s["family"],
                 "params": s["params"], "symbols": [s["symbol"]],
                 "title": f"{s['symbol']} {s['key']} (vol-control estimator, pre-registered)",
                 "text": s["mechanism"], "mechanism": s["mechanism"],
                 "url": "desks/mt5/data/lake/series/volcontrol_flow.csv",
                 "hypothesis_id": s["id"], "found_at": _iso(now), "available_time": _iso(now)}
                for s in new]
        sc = str(DESK / "side_channels")
        if sc not in sys.path:
            sys.path.insert(0, sc)
        from discovery_io import write_discoveries
        p = intel_dir / f"discoveries_{now.strftime('%Y%m%d_%H%M%S')}.json"
        write_discoveries(p, rows)
        f = str(p)
        emitted_path.parent.mkdir(parents=True, exist_ok=True)
        with emitted_path.open("a", encoding="utf-8") as fh:
            for s in new:
                fh.write(json.dumps({"id": s["id"], "symbol": s["symbol"], "key": s["key"],
                                     "params": s["params"], "emitted_at": _iso(now)}) + "\n")
    return {"specified": len(all_specs), "donated": len(new), "already_emitted":
            len(all_specs) - len(new), "donated_file": f,
            "charge_rule": ("one trial per hypothesis id, donated once; emitted.jsonl is the "
                            "ledger and no pass re-donates an id in it")}


def run(*, now: datetime | None = None, loader: Loader = load_daily_close,
        symbols: list[str] | None = None, out_path: Path = OUT) -> dict[str, Any]:
    t0 = time.time()
    at = now or _now()
    idx = symbols if symbols is not None else index_symbols()
    wide, latest, missing = build(idx, loader)
    doc: dict[str, Any] = {"generated_at": _iso(at), "writer": "research/volcontrol_flow.py",
                           "indices_in_registry": idx, "unmeasured": missing,
                           "model": {"target_vol": TARGET_VOL, "leverage_cap": LEVERAGE_CAP,
                                     "half_lives": HALF_LIVES}}
    if wide is None:
        doc |= {"status": "UNMEASURED", "why": "no index has enough daily bars on this host",
                "hypotheses": {"specified": 0, "donated": 0}}
    else:
        doc["vintages_appended"] = write_outputs(wide, latest, at)
        doc["latest"] = latest
        doc["deleveraging_now"] = sorted(s for s, v in latest.items()
                                         if not s.startswith("_") and (v.get("flow_z") or 0) <= -2)
        doc["hypotheses"] = emit(specs(wide.columns, _lane), at)
        doc["status"] = "OK"
        doc["series"] = str(SERIES.relative_to(DESK))
    doc["elapsed_s"] = round(time.time() - t0, 2)
    _write_atomic(out_path, json.dumps(doc, indent=1, default=str) + "\n")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.parse_args(argv)
    doc = run()
    h = doc.get("hypotheses") or {}
    print(f"volcontrol_flow: status={doc['status']} measured={len(doc.get('latest') or {})} "
          f"unmeasured={len(doc['unmeasured'])} donated={h.get('donated', 0)} "
          f"deleveraging_now={doc.get('deleveraging_now', [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
