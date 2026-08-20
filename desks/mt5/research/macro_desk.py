"""MACRO DESK (meta item 5: policy-path; also unblocks SALEH_017 anchors).

Perpetual supervised desk. Every cycle:
  1. FRED keyless fetch of policy/rates/inflation/growth/liquidity/credit/gold/oil
  2. point-in-time vintage lake (ALFRED) for PAYEMS/CPIAUCSL/DGS10, progressive
     monthly backfill from 2018-01 (one vintage per cycle)
  3. state vector (z vs 5y + 1y momentum + differentials US/EU/JP)
  4. cross-asset anchor series for SALEH_017 (DXY/yields/gold/oil/VIX/SPX)
     -> data/cross_asset_anchors.pkl (daily, aligned)
  5. data/macro_state.json <- consumed by desks and the reaction atlas

No marker: perpetual watcher (supervisor keeps alive like research_loop).
"""

from __future__ import annotations

import json
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import free_data as fd

BASE = Path(__file__).resolve().parent.parent
STATE_F = BASE / "data" / "macro_state.json"
ANCHORS_F = BASE / "data" / "cross_asset_anchors.pkl"
PIT_DIR = BASE / "data" / "macro_pointintime"
LOG = BASE / "logs" / "macro_desk.log"

PIT_SERIES = ["PAYEMS", "CPIAUCSL", "DGS10"]
PIT_START = "2018-01-01"

GROWTH = ["PAYEMS", "UNRATE", "INDPRO", "RETAILSMxSA", "UMCSENT"]
INFLATION = ["CPIAUCSL", "CPILFESL", "T10YIE", "T5YIE"]
POLICY = ["DFEDTARU", "DFF", "SOFR", "DGS2", "DGS10", "T10Y2Y", "RRPONTSYD", "WALCL"]
RISK = ["BAMLH0A0HYM2", "VIXCLS"]
COMMOD = ["GOLDAMGBD228NLBM", "DCOILWTICO"]
DOLLAR = ["DTWEXBGS"]


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _z(x: pd.Series) -> float | None:
    s = x.dropna()
    if len(s) < 120 or s.std(ddof=0) == 0:
        return None
    return float((s.iloc[-1] - s.mean()) / s.std(ddof=0))


def _mom(x: pd.Series, yoy: bool = False) -> float | None:
    s = x.dropna()
    if len(s) < 260:
        return None
    look = 252 if yoy else 252
    if s.iloc[-1] == 0 or np.isnan(s.iloc[-look]):
        return None
    base = s.iloc[-look]
    if base == 0:
        return None
    return float((s.iloc[-1] - base) / abs(base))


def series_state(series_id: str) -> dict:
    d = fd.fred_series(series_id)
    if not d:
        return {"series": series_id, "ok": False}
    s = pd.Series(d).sort_index()
    s.index = pd.to_datetime(s.index)
    out = {"series": series_id, "ok": True, "last": float(s.iloc[-1]),
           "last_date": str(s.index[-1].date()), "z": _z(s)}
    if series_id in ("CPIAUCSL", "CPILFESL", "CP0000EZ19M086NEST", "JPNCPIALLMINMEI"):
        out["mom_yoy"] = _mom(s, yoy=True)
    elif series_id in ("PAYEMS", "INDPRO", "RETAILSMxSA", "WALCL",
                       "GOLDAMGBD228NLBM", "DCOILWTICO", "BAMLH0A0HYM2",
                       "DTWEXBGS", "VIXCLS"):
        out["mom"] = _mom(s)
    return out


def pit_backfill() -> None:
    PIT_DIR.mkdir(parents=True, exist_ok=True)
    bf = PIT_DIR / "backfill.json"
    done = {}
    if bf.exists():
        try:
            done = json.loads(bf.read_text("utf-8"))
        except Exception:
            pass
    start = datetime(2018, 1, 31)
    vintages = []
    today = datetime.now(timezone.utc).date()
    v = start
    while v.date() <= today.replace(day=1):
        vintages.append(v.strftime("%Y-%m-%d"))
        v = (v + timedelta(days=32)).replace(day=28)
    for sid in PIT_SERIES:
        got = done.get(sid, [])
        want = [vd for vd in vintages if vd not in got and vd <= today.strftime("%Y-%m-%d")]
        if want:
            vd = want[-1]  # latest missing first (cheapest to trust)
            lake = fd.fred_vintage_series(sid, [vd])
            if lake:
                f = PIT_DIR / f"{sid}.json"
                cur = {}
                if f.exists():
                    try:
                        cur = json.loads(f.read_text("utf-8"))
                    except Exception:
                        pass
                cur.update(lake)
                f.write_text(json.dumps(cur), "utf-8")
                done[sid] = got + [vd]
                bf.write_text(json.dumps(done), "utf-8")
                log(f"PIT {sid} vintage {vd} stored ({len(lake[sid])} obs)")
                return  # one vintage per cycle
    log("PIT lake current")


def anchors() -> None:
    """Daily cross-asset anchors for SALEH_017 (DXY/yields/gold/oil/VIX/SPX)."""
    cols: dict[str, pd.Series] = {}

    def fred_col(sid: str) -> None:
        d = fd.fred_series(sid)
        if d:
            s = pd.Series(d).sort_index()
            s.index = pd.to_datetime(s.index)
            cols[sid] = s

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(fred_col, ["DTWEXBGS", "DGS10", "T10YIE",
                               "GOLDAMGBD228NLBM", "DCOILWTICO", "VIXCLS"]))

    def yhoo(ticker: str, name: str) -> None:
        d = fd.yahoo_daily(ticker)
        if d:
            s = pd.Series(d).sort_index()
            s.index = pd.to_datetime(s.index)
            cols[name] = s

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda t: yhoo(t[0], t[1]),
                    [("DX-Y.NYB", "DXY"), ("^VIX", "VIX"), ("^TNX", "TNX"),
                     ("GC=F", "GC"), ("CL=F", "CL"), ("^GSPC", "SPX")]))

    if not cols:
        log("anchors: no series fetched (network issue)")
        return
    df = pd.DataFrame(cols).sort_index()
    prev = None
    if ANCHORS_F.exists():
        try:
            prev = pd.read_pickle(ANCHORS_F)
            prev = prev[~prev.index.isin(df.index)]
        except Exception as e:
            log(f"anchors: prior pickle unreadable, replacing ({e!r})")
    if prev is not None and not prev.empty:
        df = pd.concat([prev, df]).sort_index()
        df = df[~df.index.duplicated(keep="last")]
    df.to_pickle(ANCHORS_F)
    log(f"anchors saved {df.shape[0]} daily rows x {df.shape[1]} cols "
        f"(last {df.index[-1].date()})")
    for c in ["T10YIE", "DTWEXBGS", "DCOILWTICO", "GOLDAMGBD228NLBM"]:
        if c not in df.columns or df[c].dropna().empty:
            log(f"anchors WARNING: {c} missing/empty (families will emit no "
                f"signals and gates will fail closed)")


def build_state() -> None:
    state: dict = {"updated": fd.now_iso(), "series": {}, "states": {},
                   "differentials": {}}

    def fetch(sid: str) -> None:
        state["series"][sid] = series_state(sid)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(fetch, GROWTH + INFLATION + POLICY + RISK + COMMOD + DOLLAR))

    def zz(sid: str) -> float | None:
        return state["series"].get(sid, {}).get("z")

    def lv(sid: str) -> float | None:
        return state["series"].get(sid, {}).get("last")

    growth = [zz(s) for s in GROWTH if zz(s) is not None]
    infl = [zz(s) for s in ["CPILFESL", "T10YIE", "T5YIE"] if zz(s) is not None]
    liq = [zz(s) for s in ["WALCL", "RRPONTSYD"] if zz(s) is not None]
    risk = [zz(s) for s in RISK if zz(s) is not None]
    dol = [zz(s) for s in ["DTWEXBGS"] if zz(s) is not None]

    state["states"] = {
        "GROWTH_STATE": round(float(np.mean(growth)), 3) if growth else None,
        "INFLATION_STATE": round(float(np.mean(infl)), 3) if infl else None,
        "LIQUIDITY_STATE": round(float(np.mean(liq)), 3) if liq else None,
        "RISK_STATE": round(float(np.mean(risk)), 3) if risk else None,
        "DOLLAR_STATE": round(float(np.mean(dol)), 3) if dol else None,
        "POLICY_RATE": lv("DFEDTARU"),
        "EFF_RATE": lv("DFF"),
        "CURVE_T10Y2Y": lv("T10Y2Y"),
        "GOLD_USD": lv("GOLDAMGBD228NLBM"),
        "WTI": lv("DCOILWTICO"),
    }

    # policy path: rate level + curve slope + policy stance z
    stance = zz("DFEDTARU")
    state["states"]["POLICY_STATE"] = (round(float(stance), 3)
                                       if stance is not None else None)
    state["states"]["POLICY_PATH_HAWKISH"] = bool(
        state["states"]["CURVE_T10Y2Y"] is not None
        and state["states"]["CURVE_T10Y2Y"] < 0)

    # differentials (inflation YOY, US vs EU/JP)
    us_cpi = state["series"].get("CPIAUCSL", {}).get("mom_yoy")
    eu = fd.fred_series("CP0000EZ19M086NEST")
    jp = fd.fred_series("JPNCPIALLMINMEI")
    eu_yoy = jp_yoy = None
    if eu:
        s = pd.Series(eu).sort_index()
        s.index = pd.to_datetime(s.index)
        eu_yoy = _mom(s, yoy=True)
    if jp:
        s = pd.Series(jp).sort_index()
        s.index = pd.to_datetime(s.index)
        jp_yoy = _mom(s, yoy=True)
    if us_cpi is not None and eu_yoy is not None:
        state["differentials"]["US_MINUS_EU_CPI_YOY"] = round(us_cpi - eu_yoy, 3)
    if us_cpi is not None and jp_yoy is not None:
        state["differentials"]["US_MINUS_JP_CPI_YOY"] = round(us_cpi - jp_yoy, 3)
    state["differentials"]["US10Y"] = lv("DGS10")

    STATE_F.write_text(json.dumps(state, indent=1), "utf-8")
    log(f"macro_state written: G={state['states']['GROWTH_STATE']} "
        f"I={state['states']['INFLATION_STATE']} "
        f"L={state['states']['LIQUIDITY_STATE']} "
        f"P={state['states']['POLICY_STATE']} "
        f"R={state['states']['RISK_STATE']} D={state['states']['DOLLAR_STATE']}")


def main() -> None:
    log("macro desk started (FRED keyless + ALFRED vintages + Yahoo anchors)")
    while True:
        t0 = time.time()
        try:
            anchors()          # first: hunt23 depends on the pkl
            build_state()
            pit_backfill()
        except Exception as e:
            log(f"cycle error: {e!r}")
        time.sleep(max(60, 3600 - (time.time() - t0)))


if __name__ == "__main__":
    main()