"""STYLE NOVELTY: how much of each certificate is a textbook style, measured, per certificate.

THE PRINCIPAL, 2026-10-13: "we must use our machinery to hunt tons of unknown styles impressive
edges too this is a global quant desk right". The cert ranking of the same day found every live
edge was a textbook style -- carry, Asia breakout, Turtle Soup, Tokyo open, a formula fit. A desk
that only re-finds known styles on new symbols is a factor-replication shop, not a discovery
desk, and nothing on this tree measured the difference: `alpha_genome` names each family's
mechanism CLASS (structure, declared) and `residual_gate_mount` regresses a candidate on the
CURRENT BOOK, which is a different question -- a sleeve the book does not hold can still be
momentum.

WHAT IS MEASURED, PER CERTIFICATE, FROM ITS OWN SIGNALS:

    return novelty   every signal's directional window P&L, y = side * log(close[exit] /
                     close[entry]), projected onto what each KNOWN STYLE would have earned over
                     the SAME window on the SAME bars, decided only from bars at or before the
                     entry (point in time):
                         passive_window  long the window every time: carry and session/calendar
                                         drift, which take one side of a window by construction
                         abs_window      |window move|: the volatility / long-gamma style
                         reversal_1bar   against the last bar: short-term reversal / bounce
                         momentum_6bar   with the last six bars: intraday momentum
                         range_breakout_12bar  +1 at or above the prior 12-bar high, -1 at or
                                         below the low, else the side of the range midpoint:
                                         the session/opening-range breakout
                         trend_20d       sign of the trailing 20-day move
                         tsmom_60d       sign of the trailing 60-day move
                         reversal_1d     against the trailing 1-day move
                         breakout_20d    +1 above the trailing 20-day high, -1 below the low
                         value_250d      against the deviation from the 250-day mean (PPP-like)
                     novelty_return = 1 - adjusted uncentred R^2 of y on those columns: the share
                     of the certificate's P&L path, mean included, that no combination of known
                     styles reproduces. The intercept fit also gives the residual mean share and
                     its t, so "novel" and "novel AND still earning" are separate readings.
    genealogy        distance of the family's declared mechanism class from the textbook: 0.0
                     for breakout / trend / reversion / carry / calendar / volatility, 0.5 for
                     the adjacent classes (residual, microstructure, plumbing, positioning,
                     macro, event, regime, ensemble), 1.0 for a declared discovered, generic
                     or learned family, and a neutral 0.0 (UNMEASURED) for a family the
                     registry does not classify -- a registry gap never buys the tilt.
    novelty          novelty_return * (0.5 + 0.5 * genealogy) when the return projection is
                     measured: the returns decide and the declared class scales them, so a
                     "discovered" family that is one side of a fixed window reads as the textbook
                     style it is. UNMEASURED otherwise (genealogy alone is reported beside it,
                     never promoted to it).

NOT MEASURED, AND SAID SO: flow/positioning (no COT history on every host), and stops/targets
(the window P&L ignores them: the question is whether the DIRECTION CHOICE is a known style, and
two cells with the same direction choice and different exits are the same style).

WHAT IT CHANGES. `merge_hypotheses.breadth_order` divides each family's judgement spend by
(1 + its novelty), so a novel family is judged as though less of its docket had been spent. That
RE-ORDERS the docket and nothing else: no row is removed, no bar moves, no trial is added or
discounted, and the Tier S bar is the same bar for every row that reaches it.
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CERTS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
REPORT = BASE / "reports" / "STYLE_NOVELTY.json"
WEEKLY = BASE / "reports" / "NOVELTY_WEEKLY.json"

DEFAULT_BUDGET_S = 300.0
#: Re-measured at most this often; the certificates change on the judge's clock, not hourly.
REFRESH_S = 20 * 3600.0
WEEK_S = 7 * 86400.0
#: Measured 2026-10-13 in a cloud session container (not either desk box) on the 58-certificate
#: canon: peak 2,737 MB, the gauntlet's frame cache. The job lock re-learns it on each host.
NEED_MB = 2800
#: A certificate is NOVEL at or above this combined novelty, with its return novelty measured.
NOVEL_T = 0.5
MIN_TRADES = 30

STYLES: tuple[str, ...] = ("passive_window", "abs_window", "reversal_1bar", "momentum_6bar",
                           "range_breakout_12bar", "trend_20d", "tsmom_60d", "reversal_1d",
                           "breakout_20d", "value_250d")
#: Below this adjusted R^2 no style is named dominant: the betas of an unexplained fit are noise.
DOMINANT_MIN_R2 = 0.10
UNMEASURED_STYLES = {"flow_positioning": "no COT/positioning history is read on every host",
                     "exits": "stops and targets are ignored: the direction choice is the style"}

TEXTBOOK = frozenset({"breakout", "trend", "reversion", "carry", "calendar", "volatility"})
ADJACENT = frozenset({"residual", "microstructure", "plumbing", "positioning", "macro", "event",
                      "regime", "ensemble"})
NOVEL_CLASSES = frozenset({"discovered", "generic"})
#: The learned miners' families, DERIVED from research/learned_miners.MINERS so the set names
#: exactly the families that exist on this tree (audit of #377 v2). Empty when it cannot import:
#: the families then score as whatever MECHANISM_CLASS declares, never as novel by default.
@functools.lru_cache(maxsize=1)
def _learned_families() -> frozenset[str]:
    try:
        from research.learned_miners import MINERS
        return frozenset(str(m["family"]) for m in MINERS.values() if m.get("family"))
    except Exception:
        return frozenset()


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _mechanism_classes() -> dict[str, str]:
    try:
        from research.alpha_genome import MECHANISM_CLASS
        return dict(MECHANISM_CLASS)
    except Exception:
        return {}


def genealogy(family: str, classes: Mapping[str, str] | None = None) -> tuple[float, str]:
    """(distance from the textbook, the class it was read from).

    Only a DECLARED novel class scores 1.0 (discovered, generic, a learned miner's family). A
    family the registry does not classify is UNMEASURED and scores the neutral 0.0: a gap in
    MECHANISM_CLASS must never buy the largest tilt (L1.28a, audit of #377)."""
    if family in _learned_families():
        return 1.0, "learned"
    cls = (classes if classes is not None else _mechanism_classes()).get(family)
    if cls is None:
        return 0.0, "UNMEASURED"
    if cls in TEXTBOOK:
        return 0.0, cls
    if cls in ADJACENT:
        return 0.5, cls
    if cls in NOVEL_CLASSES:
        return 1.0, cls
    return 0.0, f"UNMEASURED: class {cls!r} has no declared distance"


def _bars_per_day(index: Any) -> float:
    try:
        import pandas as pd
        days = pd.DatetimeIndex(index).normalize()
        counts = pd.Series(1, index=days).groupby(level=0).sum()
        return max(float(counts.median()), 1.0)
    except Exception:
        return 24.0


def style_matrix(close: np.ndarray, index: Any, signals: Sequence[Any],
                 high: np.ndarray | None = None, low: np.ndarray | None = None,
                 open_: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(y, X): each signal's directional window P&L and each style's P&L on that window.

    THE ENGINE'S OWN WINDOW (mt5desk/engine.py backtest): a signal stamped on bar i0 enters at
    the OPEN of i0+1; a resting order (`trigger` set) fills at its trigger on the first of its
    `wait_bars` bars from i0+1 whose range CONTAINS it (high >= trigger >= low), else it never
    traded and is not a sample; the ttl exit is the OPEN of fill + ttl. Every style's position is
    decided from closes at or before bar i0, so nothing after the signal is read."""
    import pandas as pd
    idx = pd.DatetimeIndex(index)
    n = len(close)
    bpd = _bars_per_day(idx)
    lb = {k: max(int(round(d * bpd)), 1) for k, d in (("1d", 1), ("20d", 20), ("60d", 60),
                                                       ("250d", 250))}
    logc = np.log(np.asarray(close, dtype=float))
    logo = np.log(np.asarray(open_ if open_ is not None else close, dtype=float))
    last_exit = -1                       # the engine's single-position discipline
    hi_a = None if high is None else np.asarray(high, dtype=float)
    lo_a = None if low is None else np.asarray(low, dtype=float)
    ys: list[float] = []
    rows: list[list[float]] = []
    for s in signals:
        try:
            t = pd.Timestamp(s.time)
            if t.tzinfo is None and idx.tz is not None:
                t = t.tz_localize(idx.tz)
            i0 = int(idx.searchsorted(t, side="left"))
            side = int(np.sign(float(s.side)))
            ttl = max(int(getattr(s, "ttl_bars", 1) or 1), 1)
        except Exception:
            continue
        i = i0 + 1
        if side == 0 or i >= n - 1 or i0 < lb["250d"] or i <= last_exit:
            continue
        trig = getattr(s, "trigger", None)
        fill, e_log = i, float(logo[i])
        if trig is not None:
            if hi_a is None or lo_a is None:
                continue
            tgt = float(trig)
            wait = max(int(getattr(s, "wait_bars", 1) or 1), 1)
            hit = next((k for k in range(i, min(i + wait, n))
                        if hi_a[k] >= tgt >= lo_a[k]), -1)
            if hit < 0 or not (tgt > 0):
                continue
            fill, e_log = hit, math.log(tgt)
        x = fill + ttl
        if x > n - 1:
            continue
        last_exit = x
        w = float(logo[x] - e_log)
        if not math.isfinite(w):
            continue
        d_bar = i0
        past = logc[: d_bar + 1]
        r1 = past[-1] - past[-1 - lb["1d"]]
        r20 = past[-1] - past[-1 - lb["20d"]]
        r60 = past[-1] - past[-1 - lb["60d"]]
        hi = float(np.max(past[-1 - lb["20d"]:-1]))
        lo = float(np.min(past[-1 - lb["20d"]:-1]))
        brk = 1.0 if past[-1] > hi else (-1.0 if past[-1] < lo else 0.0)
        dev = past[-1] - float(np.mean(past[-1 - lb["250d"]:]))
        rb1 = past[-1] - past[-2]
        rb6 = past[-1] - past[-7]
        h12, l12 = float(np.max(past[-13:-1])), float(np.min(past[-13:-1]))
        rng = (1.0 if past[-1] >= h12 else -1.0 if past[-1] <= l12
               else float(np.sign(past[-1] - 0.5 * (h12 + l12))))
        ys.append(side * w)
        rows.append([w, abs(w), -np.sign(rb1) * w, np.sign(rb6) * w, rng * w,
                     np.sign(r20) * w, np.sign(r60) * w, -np.sign(r1) * w,
                     brk * w, -np.sign(dev) * w])
    return np.asarray(ys, dtype=float), np.asarray(rows, dtype=float).reshape(-1, len(STYLES))


def project(y: np.ndarray, X: np.ndarray) -> dict[str, Any]:
    """Uncentred adjusted R^2 of y on the styles, and the intercept fit's residual mean."""
    n = len(y)
    keep = [k for k in range(X.shape[1]) if np.std(X[:, k]) > 0] if n else []
    k = len(keep)
    if n < max(MIN_TRADES, 3 * max(k, 1)):
        return {"status": "UNMEASURED", "why": f"{n} usable signals, need "
                f"{max(MIN_TRADES, 3 * max(k, 1))}", "n": n}
    Xk = X[:, keep]
    beta, *_ = np.linalg.lstsq(Xk, y, rcond=None)
    ssr = float(np.sum((y - Xk @ beta) ** 2))
    sst = float(np.sum(y ** 2))
    r2 = 0.0 if sst <= 0 else 1.0 - ssr / sst
    r2_adj = 1.0 - (1.0 - r2) * n / max(n - k, 1)
    r2_adj = min(max(r2_adj, 0.0), 1.0)
    Xc = np.column_stack([np.ones(n), Xk])
    bc, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    res = y - Xc @ bc
    dof = max(n - Xc.shape[1], 1)
    try:
        cov = np.linalg.pinv(Xc.T @ Xc) * float(res @ res) / dof
        alpha_t = float(bc[0] / math.sqrt(cov[0, 0])) if cov[0, 0] > 0 else None
    except Exception:
        alpha_t = None
    mean_y = float(np.mean(y))
    return {"status": "MEASURED", "n": n, "style_r2_adj": round(r2_adj, 4),
            "novelty_return": round(1.0 - r2_adj, 4),
            "mean_window_pnl": round(mean_y, 7),
            "residual_mean": round(float(bc[0]), 7),
            "residual_mean_share": (round(float(bc[0]) / mean_y, 4) if mean_y != 0 else None),
            # A fit that reproduces the path leaves a residual of rounding error, and its t is
            # the ratio of two rounding errors: not a reading.
            "residual_t": (None if alpha_t is None or r2_adj > 0.999 else round(alpha_t, 3)),
            "betas": {STYLES[c]: round(float(b), 4) for c, b in zip(keep, beta, strict=True)},
            "dominant_style": (STYLES[keep[int(np.argmax(np.abs(beta)))]]
                               if k and r2_adj >= DOMINANT_MIN_R2 else None)}


def _builder() -> Callable[..., dict[str, Any] | None]:
    import external_gauntlet as eg  # type: ignore[import-not-found]
    fn: Callable[..., dict[str, Any] | None] = eg.build_cell
    return fn


def score_certificate(cert: Mapping[str, Any], meta: Mapping[str, Any],
                      build: Callable[..., dict[str, Any] | None] | None,
                      classes: Mapping[str, str]) -> dict[str, Any]:
    spec = cert.get("shadow_spec") or {}
    sym = str(spec.get("symbol") or cert.get("sym") or "")
    family = str(spec.get("family") or cert.get("family") or "")
    gen, cls = genealogy(family, classes)
    out: dict[str, Any] = {"symbol": sym, "family": family, "mechanism_class": cls,
                           "genealogy": gen}
    if build is None or not sym or not family:
        out.update({"status": "UNMEASURED", "novelty": None,
                    "why": "no builder or no symbol/family in shadow_spec"})
        return out
    try:
        obj = build(sym, family, dict(spec.get("params") or {}), dict(meta))
    except Exception as exc:
        obj, why = None, f"build_cell raised {type(exc).__name__}: {exc}"
    else:
        why = "build_cell returned no executable cell on this host"
    if not obj or obj.get("df") is None:
        out.update({"status": "UNMEASURED", "novelty": None, "why": why})
        return out
    df = obj["df"]
    hl = ((df["high"].to_numpy(dtype=float), df["low"].to_numpy(dtype=float))
          if {"high", "low"} <= set(df.columns) else (None, None))
    y, X = style_matrix(df["close"].to_numpy(dtype=float), df.index, obj.get("sigs") or [],
                        high=hl[0], low=hl[1],
                        open_=(df["open"].to_numpy(dtype=float) if "open" in df.columns
                               else None))
    proj = project(y, X)
    out["return_projection"] = proj
    if proj["status"] != "MEASURED":
        out.update({"status": "UNMEASURED", "novelty": None, "why": proj.get("why")})
        return out
    # THE RETURNS DECIDE, THE LABEL SCALES. A "discovered" family whose P&L is one side of a
    # fixed window every time IS the session-drift style whatever its family is called, so the
    # measured return novelty multiplies, and a textbook class halves what it measures.
    out.update({"status": "MEASURED",
                "novelty": round(float(proj["novelty_return"]) * (0.5 + 0.5 * gen), 4)})
    out["novel"] = bool(out["novelty"] >= NOVEL_T and float(proj["novelty_return"]) >= NOVEL_T)
    return out


def per_family(per: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """The SATURATION SIGNAL, per family (principal 2026-10-13: "saturated mechanisms families we
    have as certis dont get hunted"). A family is SATURATED when it already holds a certificate and
    none of its measured certificates is novel: another cell of it re-buys a style the desk owns.
    Nothing reads this block yet; this organ only publishes it. Breadth's enforcer is its intended
    reader, and when it lands it owes a missed-growth line and a floor for saturated families."""
    fams: dict[str, dict[str, Any]] = {}
    for e in per.values():
        if not isinstance(e, dict) or not e.get("family"):
            continue
        f = fams.setdefault(str(e["family"]), {"n_certificates": 0, "n_measured": 0,
                                               "n_novel": 0, "_nov": [], "_dom": {},
                                               "mechanism_class": e.get("mechanism_class"),
                                               "genealogy": e.get("genealogy")})
        f["n_certificates"] += 1
        if e.get("novelty") is not None:
            f["n_measured"] += 1
            f["_nov"].append(float(e["novelty"]))
            f["n_novel"] += int(bool(e.get("novel")))
            d = (e.get("return_projection") or {}).get("dominant_style")
            if d:
                f["_dom"][d] = f["_dom"].get(d, 0) + 1
    out: dict[str, dict[str, Any]] = {}
    for fam, f in sorted(fams.items()):
        nov = f.pop("_nov")
        dom = f.pop("_dom")
        f["mean_novelty"] = round(sum(nov) / len(nov), 4) if nov else None
        f["dominant_styles"] = dict(sorted(dom.items(), key=lambda kv: -kv[1]))
        f["saturation"] = ("UNMEASURED" if not nov else
                           "SATURATED" if f["n_novel"] == 0 else "OPEN")
        out[fam] = f
    return out


def family_values(path: Path = REPORT) -> dict[str, float]:
    """Per family, its measured mean novelty, else its genealogy: the docket's tilt input.

    Every family on the docket gets a value without the report (genealogy is declared), so an
    absent report tilts by structure alone rather than not at all."""
    doc = _json(path)
    measured: dict[str, list[float]] = {}
    for e in (doc.get("per_certificate") or {}).values():
        if isinstance(e, dict) and e.get("novelty") is not None:
            measured.setdefault(str(e.get("family")), []).append(float(e["novelty"]))
    return {f: sum(v) / len(v) for f, v in measured.items()}


def family_novelty(family: str, measured: Mapping[str, float],
                   classes: Mapping[str, str] | None = None) -> float:
    if family in measured:
        return float(measured[family])
    return genealogy(family, classes)[0]


def run(*, certs_path: Path = CERTS, fallback: Path = CANON, report_path: Path = REPORT,
        weekly_path: Path = WEEKLY, universe: Path = UNIVERSE,
        budget_s: float = DEFAULT_BUDGET_S, force: bool = False,
        build: Callable[..., dict[str, Any] | None] | None = None,
        now: float | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    clock = time.time() if now is None else now
    # FRESH MEANS A COMPLETE MEASUREMENT, DATED BY ITS OWN STAMP (audit of #377): a run the
    # budget cut short is never fresh, and the age is read from generated_utc, not the file's
    # mtime, which a clone or a copy resets.
    old = _json(report_path)
    age = float("inf")
    try:
        age = clock - datetime.fromisoformat(str(old.get("generated_utc"))).timestamp()
    except (TypeError, ValueError):
        pass
    # A stamp in the future is not fresh: it would hold measurement off until that date.
    if not force and old.get("complete") is True and 0.0 <= age < REFRESH_S:
        return {"status": "FRESH", "age_h": round(age / 3600.0, 1), "report": str(report_path)}
    deadline = t0 + float(budget_s)
    certs: dict[str, dict[str, Any]] = {}
    source = ""
    for p in (certs_path, fallback):
        surv = _json(p).get("survivors")
        if isinstance(surv, dict) and surv:
            certs, source = {str(k): v for k, v in surv.items() if isinstance(v, dict)}, str(p)
            break
    build_err = ""
    if build is None:
        try:
            build = _builder()
        except Exception as exc:
            build_err = f"gauntlet builder unavailable: {type(exc).__name__}: {exc}"
    meta = _json(universe)
    classes = _mechanism_classes()
    prior = old.get("per_certificate") or {}
    per: dict[str, Any] = {}
    # STALEST FIRST, so a budget that runs out skips a different tail each pass and the report
    # converges: never measured, then oldest measured_at.
    def _stamp(cid: str) -> str:
        e = prior.get(cid)
        return str(e.get("measured_at") or "") if isinstance(e, dict) else ""

    reached_all = True
    for cid in sorted(certs, key=lambda c: (_stamp(c), c)):
        cert = certs[cid]
        if time.monotonic() > deadline:
            reached_all = False
            prev = prior.get(cid) if isinstance(prior.get(cid), dict) else None
            per[cid] = {**(prev or {}), "status": (prev or {}).get("status", "NOT_REACHED"),
                        "carried_forward": prev is not None,
                        "why_not_reached": f"the {budget_s:.0f}s budget was spent first"}
            continue
        per[cid] = {**score_certificate(cert, meta, build, classes), "measured_at": _now()}
        if build_err and per[cid]["status"] == "UNMEASURED":
            per[cid]["why"] = build_err
    measured = [e for e in per.values() if e.get("novelty") is not None]
    novel = sorted((c for c, e in per.items() if e.get("novel")),
                   key=lambda c: -float(per[c]["novelty"]))
    dominant: dict[str, int] = {}
    for e in measured:
        d = (e.get("return_projection") or {}).get("dominant_style")
        if d:
            dominant[d] = dominant.get(d, 0) + 1
    doc = {
        "generated_utc": _now(), "source": source, "n_certificates": len(certs),
        "n_measured": len(measured), "n_novel": len(novel), "novel_threshold": NOVEL_T,
        "complete": reached_all,
        "status": ("NO_CERTIFICATES" if not certs else "MEASURED" if measured else "UNMEASURED"),
        "styles": list(STYLES), "styles_not_measured": UNMEASURED_STYLES,
        "dominant_style_counts": dict(sorted(dominant.items(), key=lambda kv: -kv[1])),
        "mean_novelty": (round(sum(float(e["novelty"]) for e in measured) / len(measured), 4)
                         if measured else None),
        "novel_certificates": novel,
        "per_family": per_family(per),
        "consumer": ("merge_hypotheses.breadth_order: spend / (1 + family novelty); re-orders "
                     "the docket only, no bar, trial count or row changes"),
        "per_certificate": per,
        "seconds": round(time.monotonic() - t0, 3),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        wage = clock - weekly_path.stat().st_mtime
    except OSError:
        wage = float("inf")
    if wage >= WEEK_S and reached_all:
        prev_w = _json(weekly_path)
        weekly_path.write_text(json.dumps({
            "generated_utc": doc["generated_utc"], "novel_threshold": NOVEL_T,
            "n_certificates": len(certs), "n_measured": len(measured), "n_novel": len(novel),
            "n_novel_last_week": prev_w.get("n_novel"), "mean_novelty": doc["mean_novelty"],
            "dominant_style_counts": doc["dominant_style_counts"],
            "top_novel": [{"cert": c, "novelty": per[c]["novelty"],
                           "residual_t": (per[c].get("return_projection") or {}).get(
                               "residual_t")} for c in novel[:10]],
        }, indent=1, default=str), "utf-8")
        doc["weekly_written"] = str(weekly_path)
    try:
        from libs.ops import events
        events.emit("style_novelty", leg="style_novelty", n_novel=len(novel),
                    n_measured=len(measured))
    except Exception:
        pass
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="measure each certificate's novelty against the "
                                 "known-style library")
    ap.add_argument("--once", action="store_true", help="one pass and exit (the default)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--force", action="store_true", help="re-measure even when fresh")
    args = ap.parse_args(argv)
    try:
        from job_lock import exclusive_job  # type: ignore[import-not-found]
    except Exception:
        exclusive_job = None
    if exclusive_job is not None:
        with exclusive_job("style_novelty", need_mb=NEED_MB) as go:
            if not go:
                print("style_novelty: stood down (duplicate writer or no room)")
                return 0
            doc = run(budget_s=args.budget_s, force=args.force)
    else:
        doc = run(budget_s=args.budget_s, force=args.force)
    print(f"style_novelty: {doc.get('status')} measured={doc.get('n_measured')} "
          f"novel={doc.get('n_novel')} of {doc.get('n_certificates')} "
          f"dominant={doc.get('dominant_style_counts')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
