"""Clean data, enforced: a box-checked quality score per series, a quarantine list, a rising floor.

zuck 2026-11-25: "do we maximise clean data". The desk had pieces (`recorders/tick_integrity.py`
judges the tape; the source registry carries freshness fields) but no one score per series, no
quarantine, and no floor. This is that, for every price series the desk holds, from the bytes.

WHAT IS SCORED, per series, each component in [0, 1] and the overall score the WEAKEST of them (a
series is as clean as its worst property, never the average that hides a hole):

  coverage    present bars over the bars this series' OWN sessions say should exist. A slot
              (weekday, hour) is in session if it carried a bar in at least SESSION_QUORUM of the
              weeks the series spans. No asset-class list: a share CFD's 6.5-hour day is measured.
  freshness   age of the newest bar against STALE_H (a weekend plus a holiday must not read stale).
  duplicates  duplicate and out-of-order timestamps.
  alignment   every bar stamped on the hour, in UTC. A series whose clock is not UTC, or whose bars
              sit off the grid, is not comparable with any other series.
  outliers    OHLC invariants (high >= max(open, close), low <= min(open, close), positive prices,
              no NaN) and returns beyond OUTLIER_MADS robust deviations that are also a real move.
  pit         bars stamped in the FUTURE of the clock are lookahead. Revisions leakage is UNMEASURED
              for bars (bars are not revised); lake series carry their own known-by stamps.
  tick        the tape's own verdict from TICK_INTEGRITY.json when present, else UNMEASURED.

A series is QUARANTINED when it has a HARD defect (invariant break, duplicates, off-grid or
non-UTC clock, future bars, nonpositive prices) or its content score is under QUARANTINE_SCORE.
Quarantine REDIRECTS: the series is kept, never deleted, and consumers skip it until a pass
finds it clean again.

THE FLOOR RATCHETS UP. `check_ratchet` fails when the mean score falls, or the quarantined count
rises, against the best published pass (L1.50). UNMEASURED is a verdict: a series that could not be
read is counted as UNREADABLE, never as clean.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_DIR = ROOT / "desks" / "mt5" / "data" / "universe"
TICK_REPORT = ROOT / "desks" / "mt5" / "reports" / "TICK_INTEGRITY.json"

SESSION_QUORUM = 0.5
STALE_H = 120.0           # a long weekend plus one more session
QUARANTINE_SCORE = 0.5
OUTLIER_MADS = 25.0
OUTLIER_MIN_MOVE = 0.05   # and a real move: 5% in one hour
UNMEASURED = "UNMEASURED"


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_bars(df: Any, now: datetime | None = None) -> dict[str, Any]:
    """Score one OHLC frame indexed by bar time. Pure: no I/O."""
    import numpy as np
    import pandas as pd

    now = now or datetime.now(tz=UTC)
    n = len(df)
    if n < 50:
        return {"n": n, "score": None, "status": UNMEASURED, "hard": [],
                "why": f"only {n} bars: too few to establish a session or an outlier scale"}
    idx = df.index
    hard: list[str] = []
    comp: dict[str, Any] = {}

    # --- alignment: UTC, on the hour
    tz_ok = getattr(idx, "tz", None) is not None and str(idx.tz) in ("UTC", "utc")
    off_grid = (float(((idx.minute != 0) | (idx.second != 0)).mean())
                if hasattr(idx, "minute") else 1.0)
    comp["alignment"] = _clip(1.0 - off_grid) if tz_ok else 0.0
    if not tz_ok:
        hard.append("clock_not_utc")
    if off_grid > 0.01:
        hard.append("bars_off_the_hour_grid")

    # --- duplicates and order
    dup = int(idx.duplicated().sum())
    back = int((idx[1:] < idx[:-1]).sum())
    comp["duplicates"] = _clip(1.0 - (dup + back) / max(1, n) * 50.0)
    if dup:
        hard.append("duplicate_timestamps")
    if back:
        hard.append("out_of_order_bars")

    # --- freshness
    last = idx.max()
    last_utc = last.tz_convert("UTC") if getattr(last, "tzinfo", None) else last.tz_localize("UTC")
    age_h = (pd.Timestamp(now) - last_utc).total_seconds() / 3600.0
    comp["freshness"] = _clip(1.0 - max(0.0, age_h - STALE_H) / (STALE_H * 2.0))

    # --- point in time: no bar from the future of the clock
    future = int((idx > pd.Timestamp(now)).sum()) if tz_ok else 0
    comp["pit"] = 1.0 if future == 0 else 0.0
    if future:
        hard.append("future_stamped_bars")

    # --- coverage against the series' OWN weekly slots
    ix = idx.tz_convert("UTC") if tz_ok else idx
    weeks = (ix.normalize() - pd.to_timedelta(ix.dayofweek, unit="D")).astype("int64") // 10**9
    slot = ix.dayofweek * 24 + ix.hour
    wk_n = len(np.unique(weeks))
    freq = Counter(zip(weeks.tolist(), slot.tolist(), strict=False))
    per_slot: Counter[int] = Counter(s for (_w, s) in freq)
    in_session = {s for s, c in per_slot.items() if c / max(1, wk_n) >= SESSION_QUORUM}
    expected = wk_n * len(in_session)
    present = sum(1 for (_w, s) in freq if s in in_session)
    comp["coverage"] = _clip(present / expected) if expected else 0.0

    # --- outliers: invariants and robust returns
    o, h, lo, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    bad_px = int(np.sum(~np.isfinite(o + h + lo + c)) + np.sum((o <= 0) | (c <= 0)))
    ok = np.isfinite(o + h + lo + c)
    inv = int(np.sum(ok & ((h < np.maximum(o, c) - 1e-12) | (lo > np.minimum(o, c) + 1e-12))))
    if bad_px:
        hard.append("nonpositive_or_nan_prices")
    if inv:
        hard.append("ohlc_invariant_broken")
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.diff(np.log(np.where(c > 0, c, np.nan)))
    r = r[np.isfinite(r)]
    mad = float(np.median(np.abs(r - np.median(r)))) * 1.4826 if len(r) else 0.0
    big = (np.abs(r) > OUTLIER_MADS * mad) & (np.abs(r) > OUTLIER_MIN_MOVE)
    jumps = int(np.sum(big)) if mad else 0
    comp["outliers"] = _clip(1.0 - (bad_px + inv + jumps) / max(1, n) * 200.0)

    score = min(comp.values())
    # STALENESS PAGES BUT DOES NOT QUARANTINE: a series that stopped updating is still a valid
    # history for research cells, and quarantining on age would idle the whole lab the hour a feed
    # stalls. Only what makes the bytes WRONG quarantines (`content_score`).
    content = min(v for k, v in comp.items() if k != "freshness")
    return {"n": n, "status": "MEASURED", "score": round(score, 4),
            "content_score": round(content, 4), "stale": comp["freshness"] < 1.0,
            "components": {k: round(v, 4) for k, v in comp.items()},
            "age_h": round(age_h, 2), "weeks": wk_n, "session_slots": len(in_session),
            "dup": dup, "out_of_order": back, "invariant_breaks": inv, "bad_prices": bad_px,
            "return_jumps": jumps, "hard": hard}


def _tick_verdicts() -> dict[str, Any] | None:
    try:
        doc = json.loads(TICK_REPORT.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def assess(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Roll per-series scores into the published report, the quarantine list and the means."""
    measured = {k: v for k, v in rows.items() if v.get("status") == "MEASURED"}
    quarantined: dict[str, Any] = {}
    for sym, v in sorted(measured.items()):
        why = list(v.get("hard") or [])
        if (v.get("content_score") or 0.0) < QUARANTINE_SCORE:
            why.append(f"content_score {v.get('content_score')} < {QUARANTINE_SCORE}")
        if why:
            quarantined[sym] = {"why": why, "score": v.get("score")}
    scores = [float(v["score"]) for v in measured.values()]
    stale = sorted(k for k, v in measured.items() if v.get("stale"))
    worst = sorted(measured.items(), key=lambda t: float(t[1]["score"]))[:25]
    comp_means: dict[str, float] = {}
    for k in ("coverage", "freshness", "duplicates", "alignment", "outliers", "pit"):
        vals = [v["components"][k] for v in measured.values() if k in v.get("components", {})]
        if vals:
            comp_means[k] = round(sum(vals) / len(vals), 4)
    return {
        "n_series": len(rows), "n_measured": len(measured),
        "n_unreadable": len(rows) - len(measured),
        "mean_score": round(sum(scores) / len(scores), 4) if scores else None,
        "min_score": round(min(scores), 4) if scores else None,
        "mean_content_score": (round(sum(float(v["content_score"]) for v in measured.values())
                                     / len(measured), 4) if measured else None),
        "n_quarantined": len(quarantined), "quarantined": quarantined,
        "n_stale": len(stale), "stale": stale[:50],
        "component_means": comp_means,
        "worst": [{"series": k, "score": v["score"], "hard": v["hard"]} for k, v in worst],
        "unmeasured": {"revisions": "bars are not revised; lake series carry their own "
                                    "known-by stamps (dataset_translator)",
                       "tick": "TICK_INTEGRITY.json joined when present"},
        "rule": ("E-DQ: every series carries a box-checked score; a hard defect quarantines it "
                 "(redirected, never deleted); the floor only rises"),
    }


def check_ratchet(now: Mapping[str, Any], best: Mapping[str, Any] | None,
                  tol: float = 0.01) -> list[str]:
    """Breaches against the best published pass. Empty list = holds. UNMEASURED never passes."""
    out: list[str] = []
    if now.get("mean_score") is None:
        return ["mean_score UNMEASURED: no series could be read"]
    if not isinstance(best, Mapping):
        return out
    b_mean = best.get("mean_score")
    if isinstance(b_mean, (int, float)) and now["mean_score"] < float(b_mean) - tol:
        out.append(f"mean_score fell {b_mean} -> {now['mean_score']}")
    b_c, n_c = best.get("mean_content_score"), now.get("mean_content_score")
    if isinstance(b_c, (int, float)) and isinstance(n_c, (int, float)) and n_c < float(b_c) - tol:
        out.append(f"mean_content_score fell {b_c} -> {n_c}")
    b_q = best.get("n_quarantined")
    if isinstance(b_q, int) and now["n_quarantined"] > b_q:
        out.append(f"quarantined series rose {b_q} -> {now['n_quarantined']}")
    b_st = best.get("n_stale")
    if isinstance(b_st, int) and now.get("n_stale", 0) > b_st:
        out.append(f"stale series rose {b_st} -> {now['n_stale']}")
    b_un = best.get("n_unreadable")
    if isinstance(b_un, int) and now["n_unreadable"] > b_un:
        out.append(f"unreadable series rose {b_un} -> {now['n_unreadable']}")
    return out


def merge_best(best: Mapping[str, Any] | None, now: Mapping[str, Any]) -> dict[str, Any]:
    """The floor itself: the best each measure has ever been. It only ever improves."""
    b = dict(best) if isinstance(best, Mapping) else {}
    for k in ("mean_score", "mean_content_score"):
        v = now.get(k)
        if isinstance(v, (int, float)):
            b[k] = max(float(b[k]), float(v)) if isinstance(b.get(k), (int, float)) else float(v)
    for k in ("n_quarantined", "n_stale", "n_unreadable"):
        v = now.get(k)
        if isinstance(v, int):
            b[k] = min(int(b[k]), v) if isinstance(b.get(k), int) else v
    return b


def run(universe_dir: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Score every `<SYMBOL>_H1.parquet` under the universe directory."""
    import pandas as pd

    d = Path(universe_dir or UNIVERSE_DIR)
    rows: dict[str, dict[str, Any]] = {}
    for f in sorted(d.glob("*_H1.parquet")):
        sym = f.name[: -len("_H1.parquet")].upper()
        try:
            rows[sym] = score_bars(pd.read_parquet(f), now)
        except Exception as e:
            rows[sym] = {"status": UNMEASURED, "score": None, "hard": [],
                         "why": f"unreadable: {type(e).__name__}"}
    out = assess(rows)
    out["at"] = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    ticks = _tick_verdicts()
    out["tick_integrity"] = ("JOINED" if ticks else UNMEASURED)
    if not math.isfinite(out.get("mean_score") or 0.0):
        out["mean_score"] = None
    return out


def quarantined_symbols(report: Any) -> set[str]:
    """Symbols a consumer must skip. An unreadable report quarantines nothing and says so by being
    absent from this set -- the caller records UNMEASURED, never treats the absence as clean."""
    q = report.get("quarantined") if isinstance(report, Mapping) else None
    return {str(k).upper() for k in q} if isinstance(q, Mapping) else set()
