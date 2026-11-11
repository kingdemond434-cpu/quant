"""ALLOCATOR PROOF SUITE -- the incumbent's book against the challengers it never asks itself about.

ALLOC-10/16/20/21 (backlog 2026-10-07). Each pass, on the allocator's own daily R matrix:

  dro               ALLOC-20  a moment-ambiguity, distributionally robust log-growth book at the
                              allocator's total heat, scored next to the allocator's book
  disagreement      ALLOC-20  per booked sleeve, how far the sample / Bayesian / regime-conditional
                              / recent (EWMA) means disagree, and the shrink that disagreement
                              implies -- with the count of sleeves whose models disagree on SIGN
  release           ALLOC-21  for each calendar release inside the next 24h: hold through, go flat
                              before it, or wait -- priced from each booked sleeve's own
                              release-day excess variance
  no_trade_band     ALLOC-16  the rebalance band that maximised realised net growth on the
                              evidence, against the desk's single turnover constant
  attribution       ALLOC-10  PROSPECTIVE: the allocator's book and an equal-heat baseline are
                              appended to an append-only ledger at each evidence cutoff, BEFORE the
                              outcome exists, and scored when HORIZON_DAYS have been realised:
                              selection, sizing and cost, separately

SHADOW ONLY. Nothing here reaches sizing. A challenger that beats the incumbent prospectively is
evidence for a Rule-1 proof, not a licence.

    python desks/mt5/research/allocator_proof_suite.py [--json] [--no-write]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import robust_challengers as rc  # noqa: E402

DATA = DESK / "data"
REPORTS = DESK / "reports"
OUT = REPORTS / "ALLOCATOR_PROOF_SUITE.json"
LEDGER = DATA / "allocator_attribution_ledger.jsonl"
ALLOCATION = REPORTS / "pf_allocation.json"
VERSION = 1
#: Realised days before a prospective attribution row is scored: derived as four trading weeks
#: (4 x 5 = 20), long enough that one day's noise is a twentieth of the score.
HORIZON_DAYS = 20
#: Look-back for the in-sample challengers: one trading year (252 measured exchange days).
LOOKBACK_DAYS = 252
#: Widest sleeve set the challengers solve over: the allocator's funded sleeves plus the best
#: unfunded ones by t-stat, up to 40 columns, which keeps a pass under a few seconds measured on
#: the build box (a 252 x 40 projected ascent is ~0.1 s per solve).
MAX_COLUMNS = 40
#: Columns the causal band study re-solves daily; derived from the same budget: 12 columns x 500
#: days x 60 iterations is the largest study measured under 30 s on the build box.
BAND_COLUMNS = 12
#: Rebalance bands as fractions of total heat traded (L1). 0 is "always rebalance"; the grid
#: doubles from 0.5% so the curve is read on a log scale.
BAND_GRID = (0.0, 0.005, 0.01, 0.02, 0.04, 0.08, 0.16)
#: Bayesian prior strength in days for the shrunk mean, the same 250-day pseudo-sample the
#: `bayesian_kelly` challenger already uses (libs/portfolio/challengers.BAYES_K).
BAYES_K = 250.0
#: EWMA half-life for the "recent" mean, in trading days: derived as one quarter (63 days).
EWMA_HALFLIFE = 63.0


def _json(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _columns(daily: Any, book: dict[str, float]) -> list[str]:
    recent = daily.tail(LOOKBACK_DAYS)
    funded = [c for c in book if c in recent.columns]
    rest = [c for c in recent.columns if c not in book]
    x = recent[rest].fillna(0.0)
    sd = x.std(ddof=1).replace(0.0, np.nan)
    t = (x.mean() / sd * math.sqrt(max(len(x), 1))).fillna(-np.inf)
    extra = list(t.sort_values(ascending=False).index[:max(0, MAX_COLUMNS - len(funded))])
    return funded + [str(c) for c in extra]


def dro_section(r: np.ndarray, cols: list[str], book: dict[str, float]) -> dict[str, Any]:
    total = sum(book.values())
    if total <= 0 or r.shape[0] < 30:
        return {"status": "UNMEASURED", "why": "no funded book or < 30 days"}
    res = rc.dro_book(r, total)
    if res["status"] != "MEASURED":
        return res
    h_alloc = np.array([book.get(c, 0.0) for c in cols])
    mu, se = r.mean(axis=0), r.std(axis=0, ddof=1) / math.sqrt(r.shape[0])
    worst = (r - mu) * math.sqrt(1.0 + rc.DRO_Z ** 2 / r.shape[0]) + (mu - rc.DRO_Z * se)
    top = sorted(((cols[i], float(v)) for i, v in enumerate(res["heat"]) if v > 1e-6),
                 key=lambda kv: -kv[1])[:15]
    return {"status": "MEASURED", "basis": f"in-sample, last {r.shape[0]} days",
            "total_heat": total, "dro_book_top": dict(top),
            "growth_nominal": {"allocator": rc.log_growth(r, h_alloc),
                               "dro": res["growth_nominal"]},
            "growth_worst_case": {"allocator": rc.log_growth(worst, h_alloc),
                                  "dro": res["growth_worst_case"]},
            "overlap_l1": float(np.abs(res["heat"] - h_alloc).sum())}


def disagreement_section(daily: Any, cols: list[str], labels: list[str] | None,
                         current: str | None) -> dict[str, Any]:
    per: dict[str, Any] = {}
    recent = daily.tail(LOOKBACK_DAYS * 2)
    lab = labels[-len(recent):] if labels and len(labels) >= len(recent) else None
    for c in cols:
        x = recent[c].to_numpy(float)
        ok = np.isfinite(x)
        if ok.sum() < 30:
            continue
        xs = x[ok]
        n = xs.size
        w = 0.5 ** (np.arange(n)[::-1] / EWMA_HALFLIFE)
        means = {"sample": float(xs.mean()), "bayes": float(xs.mean() * n / (n + BAYES_K)),
                 "recent_ewma": float((w * xs).sum() / w.sum())}
        if lab is not None and current:
            m = np.array([str(v) == current for v in lab])[ok]
            if m.sum() >= 20:
                means["regime"] = float(xs[m].mean())
        se = float(xs.std(ddof=1) / math.sqrt(n))
        per[c] = {**rc.disagreement_shrink(means, se), "means": means}
    measured = [v for v in per.values() if v.get("status") == "MEASURED"]
    return {"status": "MEASURED" if measured else "UNMEASURED", "n_sleeves": len(measured),
            "n_sign_disagree": sum(1 for v in measured if not v["sign_agreement"]),
            "median_shrink_factor": (float(np.median([v["shrink_factor"] for v in measured]))
                                     if measured else None),
            "regime_label": current, "per_sleeve": per}


def _calendars(now: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from zoneinfo import ZoneInfo
    except ImportError:                                         # pragma: no cover
        return out
    for p in sorted((DATA / "calendars").glob("*.json")):
        doc = _json(p)
        dates = doc.get("dates")
        if not isinstance(dates, dict):
            continue
        try:
            tz = ZoneInfo(str(doc.get("tz") or "UTC"))
        except Exception:
            continue
        for day, hhmm in dates.items():
            try:
                loc = datetime.fromisoformat(f"{day}T{hhmm}").replace(tzinfo=tz)
            except ValueError:
                continue
            out.append({"name": doc.get("name") or p.stem, "date": str(day),
                        "at_utc": loc.astimezone(UTC)})
    return out


def release_section(daily: Any, book: dict[str, float], cost_r: float,
                    now: datetime) -> dict[str, Any]:
    events = _calendars(now)
    if not events:
        return {"status": "UNMEASURED", "why": "no release calendar on this host"}
    upcoming = [e for e in events if now <= e["at_utc"] <= now + timedelta(hours=24)]
    out: dict[str, Any] = {"status": "MEASURED", "n_calendars": len({e["name"] for e in events}),
                           "upcoming_24h": [], "per_release_history": {}}
    idx = [str(i)[:10] for i in daily.index]
    for name in sorted({e["name"] for e in events}):
        days = {e["date"] for e in events if e["name"] == name}
        mask = np.array([d in days for d in idx])
        out["per_release_history"][name] = {"n_release_days_in_matrix": int(mask.sum())}
        for e in (u for u in upcoming if u["name"] == name):
            hrs = (e["at_utc"] - now).total_seconds() / 3600.0
            per: dict[str, Any] = {}
            for s in book:
                if s not in daily.columns:
                    continue
                jv = rc.release_jump_var(daily[s].to_numpy(float), mask)
                if jv["status"] != "MEASURED":
                    per[s] = jv
                    continue
                per[s] = rc.release_decision(jv["mu_other"], jv["var_other"], jv["jump_var"],
                                             hrs, cost_r)
            out["upcoming_24h"].append({"release": name, "at_utc": e["at_utc"].isoformat(),
                                        "hours": round(hrs, 2), "per_sleeve": per})
    return out


def band_section(r: np.ndarray, cols: list[str], book: dict[str, float],
                 cost_r: float) -> dict[str, Any]:
    keep = [i for i, c in enumerate(cols) if c in book][:BAND_COLUMNS]
    total = sum(book.values())
    if len(keep) < 2 or r.shape[0] < 80 or total <= 0:
        return {"status": "UNMEASURED", "why": "fewer than 2 funded sleeves or < 80 days"}
    sub = r[:, keep]
    targets = rc.rolling_targets(sub, total)
    start = 60
    res = rc.no_trade_band(sub[start:], targets[start:], cost_r, [b * total for b in BAND_GRID])
    return {**res, "bands_as_fraction_of_heat": list(BAND_GRID), "n_columns": len(keep),
            "constant_cost_r": cost_r,
            "note": "causal targets: log-optimal on the trailing 60 days, refit every 5"}


def attribution_section(daily: Any, book: dict[str, float], cost_r: float,
                        write: bool) -> dict[str, Any]:
    idx = [str(i)[:10] for i in daily.index]
    cutoff = idx[-1] if idx else None
    rows: list[dict[str, Any]] = []
    try:
        for ln in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except ValueError:
                continue
    except OSError:
        pass
    appended = 0
    if cutoff and book and not any(r.get("cutoff") == cutoff for r in rows):
        prev = rows[-1].get("allocator") if rows else None
        eligible = [str(c) for c in daily.columns
                    if np.isfinite(daily[c].tail(LOOKBACK_DAYS).to_numpy(float)).sum() >= 60]
        row = {"cutoff": cutoff, "at": datetime.now(UTC).isoformat(timespec="seconds"),
               "allocator": book, "prev": prev, "eligible": eligible, "version": VERSION}
        rows.append(row)
        appended = 1
        if write:
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with LEDGER.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
    scored: list[dict[str, Any]] = []
    for row in rows:
        c = row.get("cutoff")
        if c not in idx:
            continue
        k = idx.index(c)
        if k + HORIZON_DAYS >= len(idx):
            continue
        window = daily.iloc[k + 1:k + 1 + HORIZON_DAYS]
        names = [str(n) for n in window.columns]
        res = rc.attribution(window.to_numpy(float), names, row.get("allocator") or {},
                             row.get("eligible") or [], cost_r, row.get("prev"))
        if res.get("status") == "MEASURED":
            scored.append({"cutoff": c, **res})
    agg: dict[str, Any] = {}
    if scored:
        for k in ("selection", "sizing", "cost", "net_vs_baseline"):
            v = np.array([s[k] for s in scored], dtype=float)
            agg[k] = {"mean_per_day": float(v.mean()),
                      "se": float(v.std(ddof=1) / math.sqrt(v.size)) if v.size > 1 else None,
                      "n": int(v.size)}
    return {"status": "MEASURED" if scored else "PENDING", "n_ledger": len(rows),
            "appended": appended, "n_scored": len(scored), "horizon_days": HORIZON_DAYS,
            "aggregate": agg, "recent": scored[-5:],
            "why": "" if scored else f"no ledger row has {HORIZON_DAYS} realised days yet"}


def run(*, write: bool = True, daily: Any = None, alloc: dict[str, Any] | None = None,
        now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or datetime.now(UTC)
    alloc = alloc if alloc is not None else _json(ALLOCATION)
    book = {str(k): float(v) for k, v in (alloc.get("book") or {}).items()
            if isinstance(v, (int, float)) and float(v) > 0}
    labels: list[str] | None = None
    current: str | None = None
    # The allocator's own turnover constant, read from it below; this literal only stands in
    # when the allocator cannot be imported (derived: TURNOVER_COST_R = 0.06 measured R/round trip).
    cost_r = 0.06
    why = "no evidence matrix"
    if daily is None:
        try:
            from research import pf_allocator as pa
            daily, _fwd = pa.build_evidence()
            cost_r = float(pa.TURNOVER_COST_R)
            try:
                lab, probs, _diag = pa.regime_state(daily)
                labels = [str(x) for x in lab] if lab else None
                current = max(probs, key=lambda kv: kv[1])[0] if probs else None
            except Exception:
                labels = None
        except (Exception, SystemExit) as exc:
            # `build_evidence` REFUSES with SystemExit when the hunt report is absent; that is
            # an UNMEASURED pass for this leg, published as such, never a crashed leg.
            daily = None
            why = f"no evidence matrix ({type(exc).__name__}: {str(exc)[:160]})"
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "version": VERSION,
                           "authority": "none -- shadow challengers; nothing here sizes",
                           "n_booked": len(book)}
    if daily is None or not len(daily.columns):
        doc.update(status="UNMEASURED", why=why, n_scored=0)
    else:
        cols = _columns(daily, book)
        r = daily[cols].tail(LOOKBACK_DAYS).to_numpy(float)
        r = np.nan_to_num(r, nan=0.0)
        doc.update(
            status="MEASURED", n_columns=len(cols),
            dro=dro_section(r, cols, book),
            disagreement=disagreement_section(daily, [c for c in cols if c in book] or cols[:10],
                                              labels, current),
            release=release_section(daily, book, cost_r, now),
            no_trade_band=band_section(
                np.nan_to_num(daily[cols].tail(560).to_numpy(float), nan=0.0), cols, book,
                cost_r),
            attribution=attribution_section(daily, book, cost_r, write))
        doc["n_scored"] = doc["attribution"]["n_scored"]
    doc["elapsed_s"] = round(time.monotonic() - t0, 2)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
        tmp.replace(OUT)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    doc = run(write=not args.no_write)
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"ALLOCATOR PROOF SUITE {doc.get('status')}: booked={doc.get('n_booked')} "
              f"scored={doc.get('n_scored')} {doc.get('why', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
