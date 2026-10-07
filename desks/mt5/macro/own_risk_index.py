"""Build the permitted risk state (`libs.data.own_risk`): the drop-in for VIXCLS and BAML credit.

    python desks/mt5/macro/own_risk_index.py            # write the archive, axes file, report
    python desks/mt5/macro/own_risk_index.py --dry-run  # measure and print, write nothing

Everything here is the desk's own MT5 data (`mt5:bars`, admitted by `libs.data.terms_hold`):

    risk     the broker's VIX CFD when listed (`vol_conditioner.BROKER_VOL_CFD`), else the
             Garman-Klass rv21 of US500 and NAS100 averaged; the term (log rv5/rv63) and its
             inversion flag on the same members
    credit   equity-implied credit stress from the US bank basket and US2000 against US500

Writes `data/own_risk_index.json` (the archive the allocator and gateway consumers read through
`libs.data.own_risk.load_pit`), `desks/mt5/data/axes/own_risk.json` (the world model's vol and
credit nodes, via the field catalogue) and `desks/mt5/reports/OWN_RISK_INDEX.json`.

THE COMPARISON WITH VIXCLS IS RESEARCH-ONLY EVIDENCE AND NEVER TRACKED. Where a held copy of
VIXCLS exists on the host (`data/fred_macro.json`, `data/fred_market_state.json`, or the vol
archive's reference), the level, rank and dlog correlations and an OLS map of VIXCLS on OWN_VIX_RV
go to `data/own_risk_vs_vixcls.json` (gitignored, box-local): they are derived from held data, so
they never enter the tracked report (audit #211 v3), the archive, a cell or a consumer. The report
carries only the comparison's status and where it was written.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import own_risk as orisk  # noqa: E402
from macro import vol_conditioner as vc  # noqa: E402

REPORT = DESK / "reports" / "OWN_RISK_INDEX.json"
AXES = DESK / "data" / "axes" / "own_risk.json"
UNIVERSE_DIR = DESK / "data" / "universe"
UNMEASURED = "UNMEASURED"
RISK_MEMBERS: dict[str, tuple[str, ...]] = {
    "US500": ("US500", "SPX500", "USA500", "SP500", "US500.cash"),
    "NAS100": ("NAS100", "USTEC", "NDX", "USTEC.cash", "NASDAQ"),
}
BANKS: tuple[tuple[str, ...], ...] = (
    ("JPMorganChase", "JPM"), ("BankofAmericaCorp", "BAC"), ("Citigroup", "C"),
    ("WellsFargo", "WFC"), ("GoldmanSachs", "GS"), ("MorganStanley", "MS"))
SMALL_CAP: tuple[str, ...] = ("US2000", "RUSSELL2000", "RTY", "US2000.cash")
MIN_BANKS = 3
CREDIT_WINDOW = 21
#: where a held VIXCLS copy may sit on a host -- read ONLY for the research comparison
HELD_VIX = (ROOT / "data" / "fred_macro.json", ROOT / "data" / "fred_market_state.json")
HELD_VIX_REFERENCE = DESK / "data" / "vol_archive" / "reference" / "VIX.json"
#: box-local, gitignored: numbers derived from the held VIXCLS copy never reach a tracked file
COMPARISON = ROOT / "data" / "own_risk_vs_vixcls.json"

Bars = Mapping[str, tuple[float, float, float, float, str]]


# ============================================================================== risk
def member_state(bars: Bars) -> dict[str, dict[str, Any]]:
    """day -> {rv5, rv21, rv63, avail} from one member's own bars (that day and earlier only)."""
    days = sorted(bars)
    gk: list[float] = []
    out: dict[str, dict[str, Any]] = {}
    for d in days:
        o, h, lo, c, avail = bars[d]
        gk.append(max(vc._gk(o, h, lo, c), 0.0))
        if len(gk) < 63:
            continue
        out[d] = {"rv5": vc._ann(float(np.mean(gk[-5:]))),
                  "rv21": vc._ann(float(np.mean(gk[-21:]))),
                  "rv63": vc._ann(float(np.mean(gk[-63:]))), "avail": avail}
    return out


def risk_series(members: Mapping[str, Bars]) -> dict[str, list[list[Any]]]:
    """OWN_VIX_RV / OWN_VIX_TERM / OWN_VIX_INVERTED points [[d, v, avail], ...] over members.
    A day carries the members that had a value; its availability is the LATEST of theirs."""
    states = {m: member_state(b) for m, b in members.items() if b}
    days = sorted({d for s in states.values() for d in s})
    rv: list[list[Any]] = []
    term: list[list[Any]] = []
    inv: list[list[Any]] = []
    for d in days:
        got = [s[d] for s in states.values() if d in s]
        if not got:
            continue
        avail = max(str(g["avail"]) for g in got)
        level = float(np.mean([g["rv21"] for g in got]))
        logs = [math.log(g["rv5"] / g["rv63"]) for g in got if g["rv5"] > 0 and g["rv63"] > 0]
        rv.append([d, round(level, 6), avail])
        if logs:
            t = float(np.mean(logs))
            term.append([d, round(t, 6), avail])
            inv.append([d, 1.0 if t > 0 else 0.0, avail])
    return {orisk.RISK_RV: rv, orisk.TERM: term, orisk.INVERTED: inv}


# ============================================================================== credit
def _logret(bars: Bars, window: int) -> dict[str, tuple[float, str]]:
    days = sorted(bars)
    out: dict[str, tuple[float, str]] = {}
    for i in range(window, len(days)):
        a, b = bars[days[i - window]][3], bars[days[i]][3]
        if a > 0 and b > 0:
            out[days[i]] = (math.log(b / a), bars[days[i]][4])
    return out


def credit_series(index: Bars, banks: Sequence[Bars], small: Bars | None,
                  window: int = CREDIT_WINDOW) -> list[list[Any]]:
    """Minus the mean of (bank basket - index) and (small cap - index) window log returns."""
    ix = _logret(index, window)
    bk = [_logret(b, window) for b in banks if b]
    sc = _logret(small, window) if small else {}
    out: list[list[Any]] = []
    for d in sorted(ix):
        parts: list[float] = []
        avail = [ix[d][1]]
        have = [b[d] for b in bk if d in b]
        if len(have) >= MIN_BANKS:
            parts.append(float(np.mean([h[0] for h in have])) - ix[d][0])
            avail += [h[1] for h in have]
        if d in sc:
            parts.append(sc[d][0] - ix[d][0])
            avail.append(sc[d][1])
        if parts:
            out.append([d, round(-float(np.mean(parts)), 8), max(avail)])
    return out


# ============================================================================== the comparison
def held_vix() -> tuple[dict[str, float], str]:
    """The held VIXCLS copy on this host, for the research comparison only."""
    for path in HELD_VIX:
        try:
            pts = (json.loads(path.read_text("utf-8")).get("series") or {}).get("VIXCLS")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(pts, list) and pts:
            got = {}
            for p in pts:
                try:
                    got[str(p[0])[:10]] = float(p[1])
                except (TypeError, ValueError, IndexError):
                    continue
            if got:
                return got, str(path.relative_to(ROOT))
    ref = vc.load_reference("^VIX", HELD_VIX_REFERENCE.parent)
    if ref:
        return ref, str(HELD_VIX_REFERENCE.relative_to(ROOT))
    return {}, ""


def _rank(xs: Any) -> np.ndarray:
    order = np.argsort(np.asarray(xs))
    r = np.empty(len(xs))
    r[order] = np.arange(len(xs))
    return r


def comparison(own: Sequence[Sequence[Any]], vix: Mapping[str, float], where: str
               ) -> dict[str, Any]:
    note = "research-only evidence: the held series never enters the archive or any consumer"
    if not vix:
        return {"status": UNMEASURED, "note": note,
                "why": "no held VIXCLS copy on this host (data/fred_macro.json, "
                       "data/fred_market_state.json, vol_archive reference): the cloud cannot "
                       "fetch FRED and the box holds the archive"}
    o = {str(p[0]): float(p[1]) for p in own}
    days = sorted(set(o) & set(vix))
    if len(days) < 60:
        return {"status": UNMEASURED, "note": note, "n": len(days), "source": where,
                "why": "fewer than 60 common days"}
    a = np.asarray([o[d] for d in days])
    b = np.asarray([vix[d] for d in days])
    level = float(np.corrcoef(a, b)[0, 1])
    rank = float(np.corrcoef(_rank(a), _rank(b))[0, 1])
    da, db = np.diff(np.log(np.maximum(a, 1e-9))), np.diff(np.log(np.maximum(b, 1e-9)))
    dlog = float(np.corrcoef(da, db)[0, 1]) if da.std() > 0 and db.std() > 0 else None
    slope, intercept = (float(x) for x in np.polyfit(a, b, 1))
    return {"status": "MEASURED", "note": note, "source": where, "n": len(days),
            "first": days[0], "last": days[-1], "corr_level": round(level, 4),
            "corr_rank": round(rank, 4),
            "corr_dlog": None if dlog is None else round(dlog, 4),
            "vix_over_own_mean": round(float(b.mean() / a.mean()), 4) if a.mean() else None,
            "ols_vix_on_own": {"slope": round(slope, 4), "intercept": round(intercept, 4)}}


# ============================================================================== the organ
def _resolve(cands: Sequence[str], universe_dir: Path) -> str | None:
    return vc.resolve_symbol(tuple(cands), universe_dir)


def build(universe_dir: Path = UNIVERSE_DIR, now: datetime | None = None) -> dict[str, Any]:
    when = now or datetime.now(UTC)
    members: dict[str, Bars] = {}
    used: dict[str, str] = {}
    for name, cands in RISK_MEMBERS.items():
        sym = _resolve(cands, universe_dir)
        if sym:
            b = vc.daily_bars(sym, universe_dir)
            if b:
                members[name], used[name] = b, sym
    series: dict[str, list[list[Any]]] = risk_series(members) if members else {}
    sources: dict[str, str] = {}
    cfd = vc.broker_vol_cfd("^VIX", universe_dir)
    cfd_bars = vc.daily_bars(cfd[0], universe_dir) if cfd else {}
    if cfd and cfd_bars:
        series[orisk.RISK] = [[d, round(v[3], 6), v[4]] for d, v in sorted(cfd_bars.items())]
        sources[orisk.RISK] = f"broker_cfd:{cfd[0]}"
    elif series.get(orisk.RISK_RV):
        series[orisk.RISK] = list(series[orisk.RISK_RV])
        sources[orisk.RISK] = f"{orisk.RISK_RV} ({'+'.join(sorted(used.values()))})"
    credit: dict[str, Any]
    idx_sym = used.get("US500")
    bank_syms = [s for s in (_resolve(c, universe_dir) for c in BANKS) if s]
    small_sym = _resolve(SMALL_CAP, universe_dir)
    if idx_sym and (len(bank_syms) >= MIN_BANKS or small_sym):
        banks = [vc.daily_bars(s, universe_dir) for s in bank_syms]
        small = vc.daily_bars(small_sym, universe_dir) if small_sym else None
        pts = credit_series(members["US500"], banks, small)
        if pts:
            series[orisk.CREDIT] = pts
            sources[orisk.CREDIT] = (f"-(banks[{','.join(bank_syms)}] & {small_sym or '-'} vs "
                                     f"{idx_sym}, {CREDIT_WINDOW}d log return)")
            credit = {"status": "MEASURED", "banks": bank_syms, "small_cap": small_sym,
                      "index": idx_sym, "points": len(pts)}
        else:
            credit = {"status": UNMEASURED, "why": "members listed but no common bar history"}
    else:
        credit = {"status": UNMEASURED,
                  "why": (f"needs US500 and either {MIN_BANKS}+ US bank share CFDs or US2000 with "
                          f"bars on this host; found index={idx_sym}, banks={bank_syms}, "
                          f"small_cap={small_sym}. The broker lists no credit index or credit "
                          "ETF CFD, so BAML has no direct permitted substitute")}
    vix, where = held_vix()
    rep: dict[str, Any] = {
        "at": when.isoformat(timespec="seconds"), "engine": "own_risk_index",
        "data_source": orisk.DATA_SOURCE, "archive": str(orisk.ARCHIVE.relative_to(ROOT)),
        "reader": "libs.data.own_risk.load_pit(as_of=...) / risk_series()",
        "replaces": orisk.REPLACES, "sources": sources, "members": used,
        "broker_vix_cfd": cfd[0] if cfd else None,
        "series": {k: {"points": len(v), "first": v[0][0] if v else None,
                       "last": v[-1][0] if v else None,
                       "last_value": v[-1][1] if v else None} for k, v in series.items()},
        "credit": credit,
        "status": "MEASURED" if series.get(orisk.RISK) else UNMEASURED,
        "scale": ("OWN_VIX_RV is annualised realised vol in percent (VIX units, realised not "
                  "implied: below VIX on average by the variance risk premium). Rank and dlog "
                  "consumers need no rescaling; absolute thresholds must be re-derived on "
                  "OWN_VIX's own history"),
    }
    if not series.get(orisk.RISK):
        rep["why"] = (f"no member bars: tried {sorted(RISK_MEMBERS)} and the broker VIX CFD "
                      f"under {universe_dir}")
    vs = comparison(series.get(orisk.RISK_RV, []), vix, where)
    rep["vs_vixcls"] = {"status": vs["status"], "note": vs["note"],
                        "written_to": f"{COMPARISON.parent.name}/{COMPARISON.name} (gitignored)",
                        **({"why": vs["why"]} if "why" in vs else {})}
    return {"report": rep, "series": series, "sources": sources, "vs_vixcls": vs}


def axes_doc(series: Mapping[str, Sequence[Sequence[Any]]], at: str) -> dict[str, Any]:
    """The world model's nodes: `own_vol_index` / `own_vol_term` (kind vol) and
    `own_credit_stress` (kind credit), causal through each point's available_time."""
    names = {orisk.RISK: "own_vol_index", orisk.TERM: "own_vol_term",
             orisk.CREDIT: "own_credit_stress"}
    out: dict[str, Any] = {}
    for sid, name in names.items():
        pts = series.get(sid) or []
        if pts:
            out[name] = {"what": f"{sid} (libs.data.own_risk), the desk's own MT5 data",
                         "n": len(pts), "first": pts[0][0], "last": pts[-1][0],
                         "points": [{"d": p[0], "v": p[1], "available_time": p[2]}
                                    for p in pts]}
    return {"axis": "macro", "id": "own_risk", "source": orisk.DATA_SOURCE, "at": at,
            "n_series": len(out), "shape": "series", "series": out}


def _write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    tmp.replace(path)


def run(*, dry_run: bool = False, universe_dir: Path = UNIVERSE_DIR,
        now: datetime | None = None, archive: Path | None = None,
        axes: Path | None = None, compare: Path | None = None) -> dict[str, Any]:
    got = build(universe_dir, now)
    rep: dict[str, Any] = got["report"]
    if dry_run:
        return rep
    if got["vs_vixcls"]["status"] == "MEASURED":
        _write(compare or COMPARISON, got["vs_vixcls"])
    if not got["series"]:
        return rep
    _write(archive or orisk.ARCHIVE, {"at": rep["at"], "source": orisk.DATA_SOURCE,
                                      "sources": got["sources"], "replaces": orisk.REPLACES,
                                      "series": got["series"]})
    _write(axes or AXES, axes_doc(got["series"], rep["at"]))
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the permitted risk state (VIXCLS/BAML drop-in)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    rep = run(dry_run=args.dry_run)
    if args.dry_run:
        print(json.dumps(rep, indent=1, default=str)[:4000])
        return 0
    _write(REPORT, rep)
    print(f"own_risk_index: {rep['status']} sources={rep['sources']} "
          f"credit={rep['credit']['status']} vs_vixcls={rep['vs_vixcls']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
