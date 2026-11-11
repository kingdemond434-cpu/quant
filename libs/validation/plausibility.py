"""PLAUSIBILITY SCREEN + LEAK FORENSICS -- too good to be true is a QUESTION, never a verdict.

zuck, 2026-11-06, forwarding a transcript: an LLM strategy loop threw out an 11,000% PnL as a
look-ahead leak. None of the desk's ten gates asks "is this too good"; DSR, PBO and SPA are all
passed MORE easily by a leak. zuck, 2026-11-11: "the too good to be true one should know the
difference between a true mind blowing edge and the fake one ... only dismiss after proof not
assuming."

SO THE THRESHOLDS NEVER REJECT. They only raise a flag:

* annualised Sharpe above ``MAX_ANNUAL_SHARPE`` (6.0), or
* more than ``MAX_WIN_DAY_SHARE`` (95%) winning days on at least ``MIN_ACTIVE_DAYS`` active days.

A flagged cell goes to FORENSICS, each a test a leak fails and a real edge survives:

0. TRUNCATION (the look-ahead proof). The cell's own family is re-run on the bars cut at three
   points, with no future in hand. Every signal at or before the cut must come back IDENTICAL
   (time, side, stop, target). A signal that changes when the future is removed was computed
   from the future: that is a leak by construction, not by inference, and it is PROOF.
1. ENTRY DELAY (+1 bar). The same signals entered one bar later. A real edge degrades gracefully;
   an edge that is reading the bar it trades on collapses (<= ``DELAY_COLLAPSE_SHARE`` of its mean).
2. DIRECTION PERMUTATION (sides mirrored). A directional edge must LOSE when its sides are
   flipped; if it still prints an implausible Sharpe, the profit comes from the harness (fills,
   costs, bar geometry), not from the market.
3. TIME PERMUTATION (shuffled entry times, same count and bracket distances). The shuffled-label
   null: if random timing also prints an implausible Sharpe, the harness is the edge.
4. POINT-IN-TIME. Any input row the cell declares must have been available at the first
   decision time (``libs.data.pit.usable_at``); one that was not is a leak by definition.
5. LATER SLICE. The final 30% of the development window against the first 70%, recorded as
   robustness evidence (a leak usually holds everywhere, so it is evidence, not proof).

LEAK IS PROVEN, and only then is the cell refused, when: truncation changes a past signal; or a
PIT violation exists; or both
permutation nulls survive; or the delay collapse coincides with either permutation null
surviving. A delay collapse ALONE is not proof (a genuinely fast edge can die at one bar of
latency) -- it is labelled DELAY_FRAGILE and settled by forward paper, at real latency.

Everything else that was flagged is a MONSTER_CANDIDATE: it passes this stage, keeps every other
gate and every sizing rail, and is written to the fast-track list so forward shadow reads it
first. A flagged cell whose signals were not in hand (a cached series) is SUSPECT_UNFORENSICED:
it passes -- an unrun test is not proof -- and is queued for forensics on its next fresh build.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

MAX_ANNUAL_SHARPE = 6.0
MAX_WIN_DAY_SHARE = 0.95
MIN_ACTIVE_DAYS = 40
DAYS_PER_YEAR = 252
#: Entry-delayed mean R at or below this share of the original mean is a collapse.
DELAY_COLLAPSE_SHARE = 0.10
#: A permutation null "survives" when it still prints at least this annual Sharpe.
NULL_SURVIVES_SHARPE = MAX_ANNUAL_SHARPE / 2
LATER_SLICE = 0.30
N_TIME_SHUFFLES = 5


def annual_sharpe(daily: Any) -> float:
    r = np.asarray(daily if daily is not None else [], dtype="float64")
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    sd = float(r.std(ddof=1))
    return float(r.mean() / sd) * math.sqrt(DAYS_PER_YEAR) if sd > 0 else 0.0


def screen(daily: Any) -> dict[str, Any]:
    """The threshold flag. NEVER a rejection on its own."""
    r = np.asarray(daily if daily is not None else [], dtype="float64")
    r = r[np.isfinite(r)]
    active = r[r != 0.0]
    n_active = int(active.size)
    ann = annual_sharpe(r)
    win = float((active > 0).mean()) if n_active else 0.0
    reasons = []
    if ann > MAX_ANNUAL_SHARPE:
        reasons.append(f"annualised Sharpe {ann:.2f} > {MAX_ANNUAL_SHARPE}")
    if n_active >= MIN_ACTIVE_DAYS and win > MAX_WIN_DAY_SHARE:
        reasons.append(f"{win:.1%} winning days > {MAX_WIN_DAY_SHARE:.0%} on {n_active} days")
    return {"suspect": bool(reasons), "annual_sharpe": round(ann, 4),
            "win_day_share": round(win, 4), "active_days": n_active,
            "flags": reasons}


def _mean(x: Any) -> float | None:
    r = np.asarray(x if x is not None else [], dtype="float64")
    r = r[np.isfinite(r)]
    return float(r.mean()) if r.size else None


def forensics(daily: Any, *, delayed: Any = None, flipped: Any = None,
              shuffled: Sequence[Any] | None = None,
              pit_violations: Sequence[str] | None = None,
              truncation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the leak tests on whatever arms the caller could build. Missing arm = not run."""
    r = np.asarray(daily, dtype="float64")
    base_mean = _mean(r) or 0.0
    tests: dict[str, Any] = {}

    if delayed is not None:
        dm = _mean(delayed)
        collapse = bool(base_mean > 0 and (dm is None or dm <= DELAY_COLLAPSE_SHARE * base_mean))
        tests["entry_delay"] = {"ran": True, "mean_r": base_mean, "delayed_mean_r": dm,
                                "delayed_annual_sharpe": round(annual_sharpe(delayed), 4),
                                "collapse": collapse}
    else:
        tests["entry_delay"] = {"ran": False}

    if flipped is not None:
        fs = annual_sharpe(flipped)
        tests["direction_permutation"] = {"ran": True, "flipped_annual_sharpe": round(fs, 4),
                                          "survives": bool(fs >= NULL_SURVIVES_SHARPE)}
    else:
        tests["direction_permutation"] = {"ran": False}

    if shuffled:
        sh = [annual_sharpe(s) for s in shuffled if s is not None]
        med = float(np.median(sh)) if sh else 0.0
        tests["time_permutation"] = {"ran": bool(sh), "draws": len(sh),
                                     "median_annual_sharpe": round(med, 4),
                                     "survives": bool(sh and med >= NULL_SURVIVES_SHARPE)}
    else:
        tests["time_permutation"] = {"ran": False}

    pv = list(pit_violations or [])
    tests["point_in_time"] = {"ran": pit_violations is not None, "violations": pv[:20],
                              "violated": bool(pv)}

    tests["truncation"] = truncation if truncation is not None else {"ran": False}

    n = r.size
    cut = int(n * (1 - LATER_SLICE))
    if n >= 2 * MIN_ACTIVE_DAYS and cut > 1 and n - cut > 1:
        tests["later_slice"] = {"ran": True,
                                "early_annual_sharpe": round(annual_sharpe(r[:cut]), 4),
                                "late_annual_sharpe": round(annual_sharpe(r[cut:]), 4)}
    else:
        tests["later_slice"] = {"ran": False}

    delay_c = tests["entry_delay"].get("collapse", False)
    flip_s = tests["direction_permutation"].get("survives", False)
    time_s = tests["time_permutation"].get("survives", False)
    pit_v = tests["point_in_time"]["violated"]
    proof = []
    if tests["truncation"].get("leak"):
        proof.append(f"removing the future changed {tests['truncation'].get('changed')} past "
                     "signal(s): they were computed from bars not yet printed")
    if pit_v:
        proof.append("an input was not available at decision time")
    if flip_s and time_s:
        proof.append("both permutation nulls print an implausible Sharpe: the harness is the edge")
    if delay_c and (flip_s or time_s):
        proof.append("collapses at +1 bar AND a permutation null survives")
    ran_any = any(t.get("ran") for k, t in tests.items() if k != "later_slice")
    if proof:
        verdict = "LEAK_PROVEN"
    elif not ran_any:
        verdict = "SUSPECT_UNFORENSICED"
    elif delay_c:
        verdict = "DELAY_FRAGILE"
    else:
        verdict = "MONSTER_CANDIDATE"
    return {"verdict": verdict, "proof": proof, "tests": tests}


def plausibility_stage(daily: Any, forensic: dict[str, Any] | None = None) -> dict[str, Any]:
    """The gauntlet stage. Fails ONLY on proven leakage."""
    sc = screen(daily)
    if not sc["suspect"]:
        return {"passed": True, "verdict": "PLAUSIBLE", **sc,
                "why": "inside the plausibility screen"}
    fx = forensic or {"verdict": "SUSPECT_UNFORENSICED", "proof": [], "tests": {}}
    leak = fx["verdict"] == "LEAK_PROVEN"
    why = ("; ".join(fx["proof"]) if leak else
           {"MONSTER_CANDIDATE": "flagged and cleared every forensic test run: fast-track to "
                                 "forward shadow, normal sizing rails",
            "DELAY_FRAGILE": "dies at +1 bar of latency but no permutation null survives: not "
                             "proof of a leak; forward paper at real latency decides",
            "SUSPECT_UNFORENSICED": "flagged, forensics not run on this build: passes (an unrun "
                                    "test is not proof) and is queued for forensics"}
           .get(fx["verdict"], fx["verdict"]))
    return {"passed": not leak, **sc, "verdict": fx["verdict"],
            "fast_track": fx["verdict"] in ("MONSTER_CANDIDATE", "DELAY_FRAGILE"),
            "forensics": fx, "why": f"{'; '.join(sc['flags'])} -> {why}"}


# ------------------------------------------------------------------ signal-level arms
def build_arms(df: Any, sigs: list, series_of: Callable[[list], Any], *,
               seed: int = 0, n_shuffles: int = N_TIME_SHUFFLES) -> dict[str, Any]:
    """The delayed, mirrored and time-shuffled arms of one cell, from its own signals.

    ``series_of(signals)`` must return the cell's daily net-R series for a signal list (the
    gauntlet passes its own ``daily_series`` with the cell's frame and costs bound). Signals
    are dataclasses with ``time``, ``side``, ``stop`` and ``target``; arms are built with
    ``dataclasses.replace`` so every other field (ttl, trigger, banking) is carried unchanged.
    """
    import dataclasses

    import pandas as pd

    idx = df.index
    close = df["close"] if "close" in getattr(df, "columns", []) else None
    out: dict[str, Any] = {}

    def _next(t):
        pos = idx.searchsorted(pd.Timestamp(t), side="right")
        return idx[pos] if pos < len(idx) else None

    try:
        delayed = [dataclasses.replace(s, time=_next(s.time)) for s in sigs
                   if _next(s.time) is not None]
        out["delayed"] = series_of(delayed)
    except Exception as exc:  # an arm that cannot be built is reported, never assumed
        out["delayed_error"] = f"{type(exc).__name__}: {exc}"[:200]

    if close is not None:
        def _ref(t):
            pos = max(0, min(len(idx) - 1, idx.searchsorted(pd.Timestamp(t), side="right") - 1))
            return float(close.iloc[pos])
        try:
            flipped = [dataclasses.replace(s, side=-s.side, stop=2 * _ref(s.time) - s.stop,
                                           target=2 * _ref(s.time) - s.target,
                                           trigger=(None if getattr(s, "trigger", None) is None
                                                    else 2 * _ref(s.time) - s.trigger))
                       for s in sigs]
            out["flipped"] = series_of(flipped)
        except Exception as exc:
            out["flipped_error"] = f"{type(exc).__name__}: {exc}"[:200]
        try:
            rng = np.random.default_rng(seed)
            shuffled = []
            for _ in range(n_shuffles):
                picks = rng.choice(len(idx) - 1, size=len(sigs), replace=len(sigs) > len(idx) - 1)
                arm = []
                for s, p in zip(sigs, sorted(picks), strict=False):
                    t = idx[int(p)]
                    shift = float(close.iloc[int(p)]) - _ref(s.time)
                    arm.append(dataclasses.replace(
                        s, time=t, stop=s.stop + shift, target=s.target + shift,
                        trigger=(None if getattr(s, "trigger", None) is None
                                 else s.trigger + shift)))
                shuffled.append(series_of(arm))
            out["shuffled"] = shuffled
        except Exception as exc:
            out["shuffled_error"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def pit_violations(rows: Sequence[dict] | None, first_decision: Any) -> list[str] | None:
    """Declared input rows not usable at the first decision time; None when none declared."""
    if not rows:
        return None
    from datetime import datetime

    import pandas as pd

    from libs.data.pit import usable_at
    t = pd.Timestamp(first_decision).to_pydatetime() if first_decision is not None else None
    if not isinstance(t, datetime):
        return None
    return [str(r.get("id") or r.get("source_version") or i)
            for i, r in enumerate(rows) if isinstance(r, dict) and not usable_at(r, t)]


TRUNCATION_CUTS = (0.5, 0.7, 0.85)
#: Each cut is also tried a few bars later, so a leak that peeks k bars ahead lands a signal in
#: the window it cannot fill without the future, whatever the family's firing cadence.
TRUNCATION_OFFSETS = (0, 1, 2, 3, 5, 8)
#: Signals within this many bars of the cut may legitimately be absent (a family that needs one
#: confirmed bar after its trigger) -- recorded as edge_of_data, never counted as proof.
TRUNCATION_GRACE_BARS = 1


def _sig_key(s: Any) -> tuple:
    import pandas as pd

    def rnd(x):
        return None if x is None else round(float(x), 8)
    return (pd.Timestamp(s.time), int(s.side), rnd(s.stop), rnd(s.target),
            rnd(getattr(s, "trigger", None)))


def truncation_test(df: Any, sigs: list, regen: Callable[[Any], list],
                    cuts: Sequence[float] = TRUNCATION_CUTS,
                    offsets: Sequence[int] = TRUNCATION_OFFSETS) -> dict[str, Any]:
    """Re-run the family on bars cut short. A past signal that changes value, or appears or
    vanishes more than TRUNCATION_GRACE_BARS before the cut, was computed from the future."""
    import pandas as pd

    full = [_sig_key(s) for s in sigs]
    per_cut = []
    changed = edge = 0
    for frac in cuts:
        for off in offsets:
            k = int(len(df) * frac) + int(off)
            if k < 50 or k >= len(df):
                continue
            sub = df.iloc[:k]
            last = pd.Timestamp(sub.index[-1])
            grace_from = pd.Timestamp(sub.index[max(0, k - 1 - TRUNCATION_GRACE_BARS)])
            try:
                got = {g for g in (_sig_key(x) for x in (regen(sub) or [])) if g[0] <= last}
            except Exception as exc:  # a family that cannot run truncated is not a proof
                per_cut.append({"cut": str(last), "ran": False,
                                "error": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            want = {f for f in full if f[0] <= last}
            diff = want ^ got
            by_time_w = {f[0] for f in want}
            by_time_g = {g[0] for g in got}
            value_changed = [d for d in diff if d[0] in by_time_w and d[0] in by_time_g]
            presence = [d for d in diff if not (d[0] in by_time_w and d[0] in by_time_g)]
            hard = value_changed + [d for d in presence if d[0] <= grace_from]
            soft = [d for d in presence if d[0] > grace_from]
            changed += len(hard)
            edge += len(soft)
            per_cut.append({"cut": str(last), "ran": True, "past_signals": len(want),
                            "changed": len(hard), "edge_of_data": len(soft),
                            "examples": [str(d) for d in sorted(hard, key=lambda x: x[0])[:3]]})
    ran = any(c.get("ran") for c in per_cut)
    return {"ran": ran, "cuts": per_cut, "changed": changed, "edge_of_data": edge,
            "leak": bool(ran and changed)}
