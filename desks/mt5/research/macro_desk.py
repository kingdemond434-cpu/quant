"""MACRO DESK (meta item 5: policy-path; also unblocks SALEH_017 anchors).

Perpetual supervised desk. Every cycle (CADENCE: hourly, under MT5-ResearchSupervisor, which
the box task manifest declares; `research_supervisor` keeps this worker alive):
  1. the macro series from their PRIMARY PUBLISHERS (`macro_sources`): BLS keyed by name
     (BLS_API_KEY), EIA and the ECB keyless, each behind terms, robots and a hard stop. Every
     FRED/ALFRED/stlouisfed route is refused (ruling 2026-11-13); the ids it used to serve are
     BLOCKED_ON_TERMS with their missed_growth, and read UNMEASURED
  2. point-in-time vintage lake (ALFRED): BLOCKED_ON_TERMS; the lake keeps what it holds
  3. state vector (z vs history + 1y momentum + differentials US/EU), each series judged by
     the age of its last observation against its frequency's ceiling: stale is not ok
  4. cross-asset anchor series for SALEH_017 -> data/cross_asset_anchors.pkl (daily, merged
     per cell; a column not fetched keeps its history)
  5. data/macro_state.json <- consumed by desks and the reaction atlas. It carries `updated`,
     `status` and its `cadence`; `read_state()` is how a reader judges it BY AGE: absent,
     unstamped or older than `cadence.max_age_h` is UNMEASURED, never clean. The box publishes
     it beside the anchors pickle (sync_shadow_to_git.ps1 $reportPaths).

No marker: perpetual watcher (supervisor keeps alive like research_loop).
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import macro_sources as ms
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
STATE_F = BASE / "data" / "macro_state.json"
ANCHORS_F = BASE / "data" / "cross_asset_anchors.pkl"
PIT_DIR = BASE / "data" / "macro_pointintime"
LOG = BASE / "logs" / "macro_desk.log"

#: THE DECLARED CADENCE. One pass an hour; a file older than MAX_AGE_H (five missed passes)
#: is UNMEASURED to every reader that judges it through `read_state`.
CYCLE_S = 3600
MAX_AGE_H = 6.0
CADENCE: dict[str, Any] = {
    "interval_s": CYCLE_S, "max_age_h": MAX_AGE_H,
    "runs_under": ("MT5-ResearchSupervisor (desks/mt5/ops/box_tasks.manifest) -> "
                   "research_supervisor.py worker 'macro_desk'"),
    "published_by": "desks/mt5/scripts/sync_shadow_to_git.ps1 $reportPaths",
}

PIT_SERIES = ["PAYEMS", "CPIAUCSL", "DGS10"]
PIT_START = "2018-01-01"

GROWTH = ["PAYEMS", "UNRATE", "INDPRO", "RSAFS", "UMCSENT"]
INFLATION = ["CPIAUCSL", "CPILFESL", "T10YIE", "T5YIE"]
POLICY = ["DFEDTARU", "DFF", "SOFR", "DGS2", "DGS10", "T10Y2Y", "RRPONTSYD", "WALCL"]
RISK = ["BAMLH0A0HYM2", "VIXCLS"]
COMMOD = ["DCOILWTICO"]
DOLLAR = ["DTWEXBGS"]
DIFF_INPUTS = ["CP0000EZ19M086NEST", "JPNCPIALLMINMEI"]

#: IDS REMOVED FROM THE DECLARED MAP, AND WHY. Written into macro_state.json under `dropped`.
DROPPED: dict[str, str] = {
    "GOLDAMGBD228NLBM": (
        "LBMA gold fix withdrawn from FRED (its PM sibling GOLDPMGBD228NLBM 404'd, measured "
        "2026-08-26 in research/fetch_sge_premium.py), and FRED is now refused for automated "
        "use in any case. No primary gold reader is permitted in the repo, so none is guessed: "
        "GOLD_USD stays null."),
    "RETAILSMxSA": (
        "not a FRED series id (no other organ or doc uses it; 14 straight null reads, "
        "2026-10-21). Its concept is RSAFS, the Census advance retail sales series, which is "
        "now in GROWTH and BLOCKED_ON_TERMS like every other id without a permitted reader."),
}
#: Observations one year back, by sampling frequency, for the 1y change in `_mom`.
YEAR_OBS: dict[str, int] = {"daily": 252, "weekly": 52, "monthly": 12, "quarterly": 4}
#: DECLARED SAMPLING FREQUENCY per series. An id absent here has its frequency inferred from
#: the median spacing of its own observations.
FREQ: dict[str, str] = {
    **dict.fromkeys(("DFEDTARU", "DFF", "SOFR", "DGS2", "DGS10", "T10Y2Y", "RRPONTSYD",
                     "T10YIE", "T5YIE", "BAMLH0A0HYM2", "VIXCLS", "DCOILWTICO", "DTWEXBGS"),
                    "daily"),
    "WALCL": "weekly",
    **dict.fromkeys(("PAYEMS", "UNRATE", "INDPRO", "RSAFS", "UMCSENT",
                     "CPIAUCSL", "CPILFESL", "CP0000EZ19M086NEST", "JPNCPIALLMINMEI"),
                    "monthly"),
}
#: Days past the last observation after which a series is STALE, by frequency: a holiday-long
#: gap for dailies, two missed prints for weeklies, a missed release plus its lag for monthlies.
#: Monthly periods are dated at the month's END by the publisher parsers, so 75 days still
#: lets a print released six weeks after its month count as fresh.
STALE_DAYS: dict[str, int] = {"daily": 10, "weekly": 21, "monthly": 75, "quarterly": 200}

#: This cycle's reads, shared by anchors() and build_state() so a route is asked once a pass.
_CYCLE: dict[str, ms.Fetched] | None = None


def log(msg: str) -> None:
    line = f"{datetime.now(UTC).isoformat()} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def begin_cycle() -> None:
    global _CYCLE
    _CYCLE = None


def _sources(now: datetime | None = None) -> dict[str, ms.Fetched]:
    global _CYCLE
    if _CYCLE is None:
        _CYCLE = ms.collect(now)
    return _CYCLE


def _z(x: pd.Series) -> float | None:
    s = x.dropna()
    if len(s) < 120 or s.std(ddof=0) == 0:
        return None
    return float((s.iloc[-1] - s.mean()) / s.std(ddof=0))


def _mom(x: pd.Series, yoy: bool = False, freq: str = "daily") -> float | None:
    """1-year change, looking back ONE YEAR OF OBSERVATIONS AT THE SERIES' OWN FREQUENCY.

    It used to look back 252 observations whatever the series: for a monthly CPI that is 21
    years, so every monthly YoY was None and the US/EU CPI differential was always empty.
    `yoy` is kept for callers; the lookback is the same 1 year either way."""
    s = x.dropna()
    look = YEAR_OBS.get(freq, 252)
    need = 260 if freq == "daily" else look + 1   # daily keeps its historic 260 floor
    if len(s) < need:
        return None
    base = s.iloc[-(look + 1)] if freq != "daily" else s.iloc[-look]
    if s.iloc[-1] == 0 or np.isnan(base) or base == 0:
        return None
    return float((s.iloc[-1] - base) / abs(base))


def _frequency(series_id: str, index: pd.DatetimeIndex) -> str:
    declared = FREQ.get(series_id)
    if declared:
        return declared
    if len(index) < 3:
        return "quarterly"            # too short to infer: the loosest ceiling, never a pass
    gap = float(pd.Series(index).diff().dt.days.dropna().tail(24).median())
    if gap <= 3:
        return "daily"
    if gap <= 10:
        return "weekly"
    if gap <= 45:
        return "monthly"
    return "quarterly"


def series_state(series_id: str, now: datetime | None = None,
                 got: ms.Fetched | None = None) -> dict:
    now = now or datetime.now(UTC)
    if got is None:
        got = _sources(now).get(series_id) or ms.Fetched(
            series_id, reason="UNMEASURED: no route declared for this id")
    src = got.entry()
    if not got.data:
        return {"series": series_id, "ok": False, "source": src, "status": got.status,
                "reason": f"{got.status}: {got.reason}"}
    s = pd.Series(got.data).sort_index()
    s.index = pd.to_datetime(s.index)
    freq = _frequency(series_id, s.index)
    last_date = s.index[-1].date()
    age_days = (now.date() - last_date).days
    ceiling = STALE_DAYS[freq]
    out = {"series": series_id, "ok": True, "source": src,
           "last": float(s.iloc[-1]), "last_date": str(last_date),
           "frequency": freq, "age_days": age_days}
    if age_days > ceiling:
        # STALE IS NOT OK. The level and date stay for the reader; the z and momentum do not,
        # so no state, differential or downstream scan can be built on a frozen print.
        out.update({"ok": False, "stale": True,
                    "reason": f"stale: last observation {last_date} is {age_days} days old, "
                              f"past the {ceiling}-day ceiling for a {freq} series"})
        return out
    out["z"] = _z(s)
    if series_id in ("CPIAUCSL", "CPILFESL", "CP0000EZ19M086NEST", "JPNCPIALLMINMEI"):
        out["mom_yoy"] = _mom(s, yoy=True, freq=freq)
    elif series_id in ("PAYEMS", "INDPRO", "RSAFS", "WALCL", "DCOILWTICO",
                       "BAMLH0A0HYM2", "DTWEXBGS", "VIXCLS"):
        out["mom"] = _mom(s, freq=freq)
    return out


def _safe_series_state(series_id: str, now: datetime | None = None,
                       got: ms.Fetched | None = None) -> dict:
    """One series failing never takes the file with it: its error is its entry."""
    try:
        return series_state(series_id, now, got)
    except Exception as exc:
        return {"series": series_id, "ok": False,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}"}


def pit_backfill() -> None:
    """ALFRED vintages: BLOCKED_ON_TERMS. Nothing is fetched; the lake keeps what it holds."""
    b = ms.BLOCKED_ROUTES["alfred_vintages"]
    log(f"PIT lake {ms.BLOCKED_ON_TERMS}: {b['why']}. {b['missed_growth']}")


def anchors() -> None:
    """Daily cross-asset anchors for SALEH_017. Only permitted primary routes advance a column
    (WTI from EIA); FRED and Yahoo columns are BLOCKED_ON_TERMS and keep their history."""
    cols: dict[str, pd.Series] = {}
    got = _sources()
    for sid in ("DCOILWTICO",):
        f = got.get(sid)
        if f is not None and f.data:
            s = pd.Series(f.data).sort_index()
            s.index = pd.to_datetime(s.index)
            cols[sid] = s
    log(f"anchors {ms.BLOCKED_ON_TERMS}: {ms.BLOCKED_ROUTES['yahoo_anchors']['why']}")
    if not cols:
        log("anchors: no permitted anchor series fetched this pass; pickle left as it is")
        return
    df = pd.DataFrame(cols).sort_index()
    prev = None
    if ANCHORS_F.exists():
        try:
            prev = pd.read_pickle(ANCHORS_F)
        except Exception as e:
            log(f"anchors: prior pickle unreadable, replacing ({e!r})")
    if isinstance(prev, pd.DataFrame) and not prev.empty:
        # MERGE PER CELL, NEVER PER ROW. A pass on which one series is not fetched must never
        # replace that series' history with NaN (measured 2026-09-29: one failed T10YIE fetch
        # erased T10YIE entirely). A fresh value wins; a missing one never erases.
        missing = [c for c in prev.columns if c not in cols]
        if missing:
            log(f"anchors: not fetched this pass, prior history kept: {', '.join(missing)}")
        df = df.combine_first(prev).sort_index()
    df.to_pickle(ANCHORS_F)
    log(f"anchors saved {df.shape[0]} daily rows x {df.shape[1]} cols "
        f"(last {df.index[-1].date()})")
    for c in ["T10YIE", "DTWEXBGS", "DCOILWTICO"]:
        if c not in df.columns or df[c].dropna().empty:
            log(f"anchors WARNING: {c} missing/empty (families will emit no "
                f"signals and gates will fail closed)")


def build_state(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    got = _sources(now)
    state: dict = {"updated": now.isoformat(), "cadence": dict(CADENCE), "series": {},
                   "states": {}, "differentials": {}}
    ids = GROWTH + INFLATION + POLICY + RISK + COMMOD + DOLLAR

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda sid: _safe_series_state(sid, now, got.get(sid)), ids))
    for sid, entry in zip(ids, results, strict=True):
        state["series"][sid] = entry

    def _ok(sid: str) -> dict:
        e = state["series"].get(sid, {})
        return e if e.get("ok") else {}

    def zz(sid: str) -> float | None:
        return _ok(sid).get("z")

    def lv(sid: str) -> float | None:
        return _ok(sid).get("last")

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
        "GOLD_USD": None,             # see DROPPED / `dropped`
        "WTI": lv("DCOILWTICO"),
    }

    # policy path: rate level + curve slope + policy stance z
    stance = zz("DFEDTARU")
    state["states"]["POLICY_STATE"] = (round(float(stance), 3)
                                       if stance is not None else None)
    state["states"]["POLICY_PATH_HAWKISH"] = bool(
        state["states"]["CURVE_T10Y2Y"] is not None
        and state["states"]["CURVE_T10Y2Y"] < 0)

    # differentials (inflation YOY, US vs EU/JP) -- through the same staleness rule
    us_cpi = _ok("CPIAUCSL").get("mom_yoy")
    diff_in = {sid: _safe_series_state(sid, now, got.get(sid)) for sid in DIFF_INPUTS}
    state["differential_inputs"] = diff_in
    eu = diff_in["CP0000EZ19M086NEST"]
    jp = diff_in["JPNCPIALLMINMEI"]
    eu_yoy = eu.get("mom_yoy") if eu.get("ok") else None
    jp_yoy = jp.get("mom_yoy") if jp.get("ok") else None
    if us_cpi is not None and eu_yoy is not None:
        state["differentials"]["US_MINUS_EU_CPI_YOY"] = round(us_cpi - eu_yoy, 3)
    if us_cpi is not None and jp_yoy is not None:
        state["differentials"]["US_MINUS_JP_CPI_YOY"] = round(us_cpi - jp_yoy, 3)
    state["differentials"]["US10Y"] = lv("DGS10")

    entries = list(state["series"].values())
    blocked = {sid: dict(b) for sid, b in ms.BLOCKED.items()}
    state["dropped"] = dict(DROPPED)
    state["blocked"] = {sid: {"status": ms.BLOCKED_ON_TERMS, **b} for sid, b in blocked.items()}
    state["sources"] = ms.routes_report(got)
    state["coverage"] = {
        "n": len(ids),
        "ok": sum(1 for e in entries if e.get("ok")),
        "stale": sorted(e["series"] for e in entries if e.get("stale")),
        "blocked_on_terms": sorted(s for s in ids if s in ms.BLOCKED),
        "unmeasured": sorted(e["series"] for e in entries
                             if not e.get("ok") and not e.get("stale")
                             and e["series"] not in ms.BLOCKED),
    }
    computed = [k for k, v in state["states"].items()
                if v is not None and k != "POLICY_PATH_HAWKISH"]
    # NOTHING MEASURED IS A VERDICT, NOT A QUIET FILE: a pass that could read no series says so.
    state["status"] = "MEASURED" if computed else ms.UNMEASURED
    if not computed:
        state["reason"] = "no state could be computed from a fresh, permitted series this pass"

    # ATOMIC. macro_state.json is read by the desks and the reaction atlas while this runs;
    # a partial write is a torn read, and json.loads of a half-file raises in the CONSUMER --
    # which is where it would be diagnosed, several organs away from its cause.
    _tmp = STATE_F.with_suffix(STATE_F.suffix + ".tmp")
    _tmp.write_text(json.dumps(state, indent=1), "utf-8")
    os.replace(_tmp, STATE_F)
    log(f"macro_state written ({state['status']}, {state['coverage']['ok']}/"
        f"{len(ids)} series ok): G={state['states']['GROWTH_STATE']} "
        f"I={state['states']['INFLATION_STATE']} "
        f"L={state['states']['LIQUIDITY_STATE']} "
        f"P={state['states']['POLICY_STATE']} "
        f"R={state['states']['RISK_STATE']} D={state['states']['DOLLAR_STATE']}")
    return state


def read_state(path: Path | None = None, now: datetime | None = None,
               max_age_h: float | None = None) -> dict[str, Any]:
    """How a reader judges macro_state.json: BY ITS OWN `updated` STAMP, never by mtime.

    Absent, unparseable, unstamped, future-stamped, older than its declared ceiling, or a file
    that itself says UNMEASURED -> status UNMEASURED with the reason; only a fresh, measured
    file is MEASURED and carries `doc`."""
    p = path or STATE_F
    now = now or datetime.now(UTC)
    try:
        doc = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        return {"status": ms.UNMEASURED, "reason": f"{p.name} absent", "age_h": None}
    except (OSError, ValueError) as exc:
        return {"status": ms.UNMEASURED, "reason": f"{p.name} unreadable ({type(exc).__name__})",
                "age_h": None}
    if not isinstance(doc, dict):
        return {"status": ms.UNMEASURED, "reason": "not a JSON object", "age_h": None}
    try:
        stamp = datetime.fromisoformat(str(doc.get("updated")).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
    except ValueError:
        return {"status": ms.UNMEASURED, "reason": "no readable `updated` stamp; age unprovable",
                "age_h": None}
    age_h = (now - stamp).total_seconds() / 3600.0
    ceiling = max_age_h
    if ceiling is None:
        cad = doc.get("cadence")
        try:
            ceiling = float((cad.get("max_age_h") if isinstance(cad, dict) else None)
                            or MAX_AGE_H)
        except (TypeError, ValueError):
            ceiling = MAX_AGE_H
    if age_h < -0.1:
        return {"status": ms.UNMEASURED, "reason": "`updated` is in the future", "age_h": age_h}
    if age_h > ceiling:
        return {"status": ms.UNMEASURED, "age_h": round(age_h, 2),
                "reason": f"stale: {age_h:.1f}h old, past the {ceiling:g}h ceiling"}
    if str(doc.get("status") or "MEASURED") != "MEASURED":
        return {"status": ms.UNMEASURED, "age_h": round(age_h, 2),
                "reason": str(doc.get("reason") or "the file says UNMEASURED")}
    return {"status": "MEASURED", "age_h": round(age_h, 2), "reason": "", "doc": doc}


def _code_fingerprint() -> tuple:
    """Bytes of this module and the fetch layer it calls: what a running copy is executing."""
    out = []
    for path in (Path(__file__), Path(getattr(ms, "__file__", "") or __file__)):
        try:
            out.append((str(path), path.read_bytes()))
        except OSError:
            out.append((str(path), None))
    return tuple(out)


def main() -> None:
    log("macro desk started (primary publishers: BLS keyed, EIA, ECB; FRED/ALFRED/Yahoo "
        "BLOCKED_ON_TERMS)")
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
            begin_cycle()      # one read of every route per pass, shared by the two writers
            anchors()          # first: hunt23 depends on the pkl
            build_state()
            pit_backfill()
        except Exception as e:
            log(f"cycle error: {e!r}")
        time.sleep(max(60, CYCLE_S - (time.time() - t0)))


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
