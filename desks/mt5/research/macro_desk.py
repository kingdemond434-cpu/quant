"""MACRO DESK (meta item 5: policy-path; also unblocks SALEH_017 anchors).

Perpetual supervised desk. Every cycle:
  1. FRED keyless fetch of policy/rates/inflation/growth/liquidity/credit/gold/oil
  2. point-in-time vintage lake (ALFRED) for PAYEMS/CPIAUCSL/DGS10, progressive
     monthly backfill from 2018-01 (one vintage per cycle)
  3. state vector (z vs 5y + 1y momentum + differentials US/EU/JP)
  4. cross-asset anchor series for SALEH_017 (DXY/yields/gold/oil/VIX/SPX)
     -> data/cross_asset_anchors.pkl (daily, aligned) + its provenance sidecar. The columns
     Yahoo used to serve come from licensed substitutes only (free_data.licensed_daily: MT5
     bars, FRED public-domain series); a column with none (VIX) is ABSENT and its sidecar row
     says UNMEASURED_NO_LICENSED_SOURCE with a missed_growth line -- never filled.
  5. data/macro_state.json <- consumed by desks and the reaction atlas

No marker: perpetual watcher (supervisor keeps alive like research_loop).
"""

from __future__ import annotations

import json
import os
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
#: Which licensed source each Yahoo-era column now comes from, its PIT lag, and the missed_growth
#: line of every cut input. A prior pickle column that this sidecar does not mark SUBSTITUTED was
#: Yahoo's, and is dropped rather than merged (a Yahoo history kept behind a substitute is still
#: Yahoo live input).
ANCHORS_PROV_F = BASE / "data" / "cross_asset_anchors.provenance.json"
#: The anchor columns Yahoo served, keyed by the Yahoo symbol (free_data.YAHOO_SUBSTITUTES).
YAHOO_ANCHORS: tuple[tuple[str, str], ...] = (("DX-Y.NYB", "DXY"), ("^VIX", "VIX"),
                                              ("^TNX", "TNX"), ("GC=F", "GC"),
                                              ("CL=F", "CL"), ("^GSPC", "SPX"))
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
    cut = fd.fred_refusal(series_id, "macro_desk.state")
    if cut:
        # a third-party FRED series (terms_fence fred_copyrighted): refused before any request,
        # UNMEASURED_NO_LICENSED_SOURCE with its missed-growth line -- never a zero, never filled
        return {"series": series_id, "ok": False, **cut}
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


def licensed_anchor_columns(cols: dict[str, pd.Series], **readers: object) -> dict[str, dict]:
    """Fill `cols` with the licensed substitute of every anchor Yahoo used to serve; return the
    per-column provenance (substitute, PIT lag, status, missed_growth line). A column with no
    licensed source, or whose substitute this host cannot read, is NOT added: it stays absent
    and its provenance says why (UNMEASURED_NO_LICENSED_SOURCE / UNMEASURED_*), never zero."""
    prov: dict[str, dict] = {}
    for ticker, name in YAHOO_ANCHORS:
        d, p = fd.licensed_daily(ticker, "macro_desk.anchors", **readers)  # type: ignore[arg-type]
        prov[name] = p
        if d:
            s = pd.Series(d).sort_index()
            s.index = pd.to_datetime(s.index)
            cols[name] = s
    return prov


def _prior_columns() -> dict[str, dict]:
    """The sidecar's `prior_columns` as the LAST pass left them ({} when none)."""
    try:
        got = json.loads(ANCHORS_PROV_F.read_text("utf-8")).get("prior_columns") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    return got if isinstance(got, dict) else {}


def purge_yahoo_columns(prev: pd.DataFrame, prior: dict[str, dict]) -> pd.DataFrame:
    """Drop every Yahoo-era column from a prior pickle unless a PRIOR pass's sidecar marked it as
    written by a licensed substitute. Yahoo history must not survive behind a substitute's tail."""
    drop = [name for _, name in YAHOO_ANCHORS if name in prev.columns
            and (prior.get(name) or {}).get("status") != "SUBSTITUTED"]
    if drop:
        log(f"anchors: Yahoo-era columns dropped from the prior pickle: {', '.join(drop)}")
    return prev.drop(columns=drop)


#: The anchor ids FRED serves but a third party owns (terms_fence fred_copyrighted). They are
#: never fetched, and a prior pickle's history of them is dropped (copyrighted history kept is
#: still live input). The gold level rides on `GC` (MT5 XAUUSD) under its own name.
FRED_COPYRIGHTED_ANCHORS: tuple[str, ...] = ("GOLDAMGBD228NLBM", "VIXCLS")
#: The realised-vol PROXY from the desk's own US500 bars. A SEPARATE series name, never VIX:
#: close-to-close realised vol (annualised %, 21 trading days) of the Fusion US500 CFD.
RV_PROXY = "US500_RV21"
RV_WINDOW = 21


def realised_vol_proxy(spx: pd.Series | None, window: int = RV_WINDOW) -> pd.Series | None:
    """Annualised close-to-close realised vol (%) of the MT5 US500 daily closes, or None when
    there are too few. Labelled as what it is -- realised, own bars -- and never stored as VIX."""
    if spx is None:
        return None
    s = pd.to_numeric(spx, errors="coerce").dropna().sort_index()
    s = s[s > 0]
    if len(s) <= window:
        return None
    rv = np.log(s).diff().rolling(window).std(ddof=1) * np.sqrt(252.0) * 100.0
    rv = rv.dropna()
    return rv if not rv.empty else None


def fred_copyrighted_columns(cols: dict[str, pd.Series]) -> dict[str, dict]:
    """The anchors' third-party FRED ids: each refused as live input with its missed-growth line,
    plus the realised-vol proxy computed from the SPX column (MT5 US500) when it was filled.
    Mutates `cols` only to add `US500_RV21`."""
    out: dict[str, dict] = {}
    for sid in FRED_COPYRIGHTED_ANCHORS:
        cut = fd.fred_refusal(sid, "macro_desk.anchors", substituted="GC" in cols)
        if cut:
            if sid == "GOLDAMGBD228NLBM":
                cut["carried_as"] = "GC" if "GC" in cols else None
            out[sid] = cut
    rv = realised_vol_proxy(cols.get("SPX"))
    if rv is not None:
        cols[RV_PROXY] = rv
        out[RV_PROXY] = {"status": "MEASURED_OWN_BARS", "route": "mt5_own_bars",
                         "series": "US500", "n_obs": int(rv.size),
                         "label": ("realised vol (close-to-close, annualised %, 21d) of the "
                                   "Fusion US500 CFD from the desk's own bars -- a PROXY, NOT "
                                   "VIX and not implied vol")}
    else:
        out[RV_PROXY] = {"status": "UNMEASURED_NO_BARS_ON_HOST", "route": "mt5_own_bars",
                         "series": "US500",
                         "label": "realised-vol proxy needs the MT5 US500 column (SPX) filled"}
    return out


def purge_copyrighted_columns(prev: pd.DataFrame) -> pd.DataFrame:
    """Drop every third-party FRED column from a prior pickle (they are never written again)."""
    drop = [c for c in FRED_COPYRIGHTED_ANCHORS if c in prev.columns]
    if drop:
        log(f"anchors: third-party FRED columns dropped from the prior pickle: {', '.join(drop)}")
    return prev.drop(columns=drop)


def _write_provenance(prov: dict[str, dict], prior: dict[str, dict],
                      fred_cut: dict[str, dict] | None = None) -> None:
    """The anchors' provenance sidecar. `prior_columns` records which pickle columns a licensed
    substitute has written (sticky: a pass whose substitute is unreachable keeps the record, so
    the substitute's own history is merged, never Yahoo's)."""
    sticky = {k: v for k, v in prior.items() if (v or {}).get("status") == "SUBSTITUTED"}
    sticky.update({k: {"status": "SUBSTITUTED", "substitute": v.get("substitute")}
                   for k, v in prov.items() if v.get("status") == "SUBSTITUTED"})
    doc = {"updated": fd.now_iso(), "rule": ("Yahoo is IDEAS_ONLY: every column it served is a "
                                             "licensed substitute or absent "
                                             f"({fd.UNMEASURED_NO_LICENSED_SOURCE})"),
           "pit": "cross_asset_anchors (data_os): 27h late-biased; H.10 FX weekly",
           "columns": prov, "prior_columns": sticky,
           "fred_copyrighted": fred_cut or {},
           "missed_growth": [v["missed_growth"] for v in (*prov.values(),
                                                          *(fred_cut or {}).values())
                             if isinstance(v.get("missed_growth"), dict)],
           "unmeasured_no_licensed_source": sorted(
               k for k, v in prov.items() if v.get("status") == fd.UNMEASURED_NO_LICENSED_SOURCE)}
    try:
        ANCHORS_PROV_F.parent.mkdir(parents=True, exist_ok=True)
        tmp = ANCHORS_PROV_F.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, ANCHORS_PROV_F)
    except OSError as e:
        log(f"anchors: provenance sidecar NOT written ({e!r})")


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
        # GOLDAMGBD228NLBM and VIXCLS are third-party FRED series: never fetched (see
        # fred_copyrighted_columns); gold rides on GC (MT5 XAUUSD), VIX is UNMEASURED
        list(ex.map(fred_col, ["DTWEXBGS", "DGS10", "T10YIE", "DCOILWTICO"]))

    prior = _prior_columns()                  # read BEFORE this pass rewrites the sidecar
    prov = licensed_anchor_columns(cols)
    fred_cut = fred_copyrighted_columns(cols)
    _write_provenance(prov, prior, fred_cut)

    prev = None
    if ANCHORS_F.exists():
        try:
            prev = pd.read_pickle(ANCHORS_F)
        except Exception as e:
            log(f"anchors: prior pickle unreadable, replacing ({e!r})")
    purged = False
    if isinstance(prev, pd.DataFrame) and not prev.empty:
        kept = purge_copyrighted_columns(purge_yahoo_columns(prev, prior))
        purged = kept.shape[1] != prev.shape[1]
        prev = kept
    if not cols:
        log("anchors: no series fetched (network issue)")
        if purged and isinstance(prev, pd.DataFrame):
            prev.to_pickle(ANCHORS_F)         # the Yahoo-era columns leave even on a dark pass
        return
    df = pd.DataFrame(cols).sort_index()
    if isinstance(prev, pd.DataFrame) and not prev.empty:
        # MERGE PER CELL, NEVER PER ROW. This used to drop every prior ROW whose date the new
        # fetch also carried and then append the new rows -- so a pass on which one FRED series
        # failed (the keyless endpoint is flaky) replaced that series' whole history with NaN
        # on every date another series did return. DGS10 comes back from 1962, so a single
        # failed T10YIE fetch erased T10YIE entirely: measured on the committed pickle
        # 2026-09-29, DGS10 16,157 values and T10YIE ZERO, which makes REAL_YIELD_10Y empty and
        # every macro-gold family emit nothing. A fresh value wins; a missing one never erases.
        missing = [c for c in prev.columns if c not in cols]
        if missing:
            log(f"anchors: not fetched this pass, prior history kept: {', '.join(missing)}")
        df = df.combine_first(prev).sort_index()
    df.to_pickle(ANCHORS_F)
    log(f"anchors saved {df.shape[0]} daily rows x {df.shape[1]} cols "
        f"(last {df.index[-1].date()})")
    for c in ["T10YIE", "DTWEXBGS", "DCOILWTICO", "GC"]:
        if c not in df.columns or df[c].dropna().empty:
            log(f"anchors WARNING: {c} missing/empty (families will emit no "
                f"signals and gates will fail closed)")


def _mt5_last(symbol: str) -> float | None:
    """The last daily close of `symbol` from the desk's own bars, or None (never a zero)."""
    d = fd.mt5_daily(symbol)
    return float(d[max(d)]) if d else None


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
        # the LBMA fix (GOLDAMGBD228NLBM) is a third-party series: gold is the desk's own XAUUSD
        "GOLD_USD": _mt5_last("XAUUSD"),
        "GOLD_USD_SOURCE": "mt5_own_bars:XAUUSD (spot CFD daily close, not the LBMA fix)",
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
    cut = {sid: {k: v for k, v in row.items() if k not in ("series", "ok")}
           for sid, row in state["series"].items() if row.get("policy_row") == "fred_copyrighted"}
    if "GOLDAMGBD228NLBM" in cut and state["states"]["GOLD_USD"] is not None:
        cut["GOLDAMGBD228NLBM"] = {**(fd.fred_refusal("GOLDAMGBD228NLBM", "macro_desk.state",
                                                      substituted=True) or {}),
                                   "carried_as": "GOLD_USD"}
    state["fred_copyrighted"] = cut
    state["unmeasured_no_licensed_source"] = sorted(
        k for k, v in cut.items() if v.get("status") == fd.UNMEASURED_NO_LICENSED_SOURCE)
    state["missed_growth"] = [v["missed_growth"] for v in cut.values()
                              if isinstance(v.get("missed_growth"), dict)]

    # ATOMIC. macro_state.json is read by the desks and the reaction atlas while this runs;
    # a partial write is a torn read, and json.loads of a half-file raises in the CONSUMER --
    # which is where it would be diagnosed, several organs away from its cause.
    _tmp = STATE_F.with_suffix(STATE_F.suffix + ".tmp")
    _tmp.write_text(json.dumps(state, indent=1), "utf-8")
    os.replace(_tmp, STATE_F)
    log(f"macro_state written: G={state['states']['GROWTH_STATE']} "
        f"I={state['states']['INFLATION_STATE']} "
        f"L={state['states']['LIQUIDITY_STATE']} "
        f"P={state['states']['POLICY_STATE']} "
        f"R={state['states']['RISK_STATE']} D={state['states']['DOLLAR_STATE']}")


def _code_fingerprint() -> tuple:
    """Bytes of this module and the fetch layer it calls: what a running copy is executing."""
    out = []
    for path in (Path(__file__), Path(getattr(fd, "__file__", "") or __file__)):
        try:
            out.append((str(path), path.read_bytes()))
        except OSError:
            out.append((str(path), None))
    return tuple(out)


def main() -> None:
    log("macro desk started (FRED keyless + ALFRED vintages + licensed anchors; Yahoo cut)")
    # A PERPETUAL WORKER NEVER SAW A RELEASE (2026-09-30). This loop is launched once by
    # research_supervisor and runs forever, so it executes the code that was on disk when it
    # STARTED. MT5-AdoptRelease lands new code in place and restarts only the gateway: the
    # per-cell anchor merge (97e21ce8f) that stops a flaky T10YIE fetch erasing REAL_YIELD_10Y
    # reached the box's disk and never this process, and the committed pickle stayed all-NaN.
    # When the code under it changes, the loop ends cleanly; the supervisor sees no live
    # macro_desk and respawns it on the new code within its 30 s tick.
    started_on = _code_fingerprint()
    while True:
        if _code_fingerprint() != started_on:
            log("macro desk: its code changed on disk since start -- exiting so the supervisor "
                "respawns it on the adopted release")
            return
        t0 = time.time()
        try:
            anchors()          # first: hunt23 depends on the pkl
            build_state()
            pit_backfill()
        except Exception as e:
            log(f"cycle error: {e!r}")
        time.sleep(max(60, 3600 - (time.time() - t0)))


def _cli_main() -> int:
    """SINGLE INSTANCE, because this one never exits and every launch is therefore permanent.

    MEASURED 2026-08-28: THREE macro_desk processes were alive at once -- 20, 20 and 23 hours,
    two orphaned to pid 1 -- each holding ~75MB on a 3.8GB box, all four states racing the same
    unlocked `macro_state.json`. This is a `while True` daemon with no marker and no lock, so a
    second launch from a supervisor, a controller or a shell never collides with the first: it
    just adds another permanent copy. The leak compounds at the PROCESS level and it is not
    self-limiting; it was a direct contributor to `quant-cadence.service` being OOM-killed 35
    times in 36 hours, which in turn left six deep-review duties owed for six weeks.

    `exclusive_job` was built, tested and already used by six other organs -- the defect was
    that nothing wired it here (III.16). A long-lived holder is safe under it only because
    `_owner_state` is a tri-state whose ALIVE verdict VETOES the 45-minute age rule; a boolean
    would have let the next hour's launch reclaim this lock from a working owner and reproduce
    the very duplication it is being wired to stop.
    """
    try:
        from research.job_lock import exclusive_job
    except ModuleNotFoundError:        # entrypoint put research/ on the path, not desks/mt5
        from job_lock import exclusive_job

    with exclusive_job("macro_desk") as acquired:
        if not acquired:
            log("macro desk: another copy already holds the lock -- standing down (not an error; "
                "a perpetual watcher only needs one instance)")
            return 0
        main()
        return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())