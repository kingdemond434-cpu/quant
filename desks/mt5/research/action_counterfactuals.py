"""The counterfactual ledger for the trades the desk TOOK: other exits, the other side, other sizes.

`counterfactual_markout` prices the trades the desk refused. This prices the ones it made, against
what else it could have done with the same signal on the same bars:

    hold        exit at the close of bar +1, +6, +12, +24, +48 after entry, keeping the sleeve's
                stop (1R adverse): a path that breached the stop before bar k is -1R at k, not
                the close. In R, with R = |entry - stop| when the row carries a stop price and
                |exit - entry| / |r_multiple| -- the realised R scale -- when it does not.
    opposite    the other side, closed at the realised exit: -r_multiple. Cost is not re-charged,
                so it is an upper bound on "the direction was wrong".
    sizing      0.5x, 1.0x, 1.5x, 2.0x of the sleeve's allocator fraction h (the book on the last
                `pf_forecast_log` line; h = 0.01 when the sleeve is unfunded, said so).

GROWTH IS NOT LINEAR IN SIZE, SO IT IS NOT COMPUTED AS IF IT WERE. A trade's fractional return
at normal size is R_scaled = h x r_multiple -- the sleeve risks h of equity per R -- and at
multiplier k it is k x R_scaled. The growth of a size is E[log(1 + k x R_scaled)] over the
sleeve's trades: doubling a sleeve with mean +0.3R and a -2R tail does not double its growth,
and the log says by how much less. Every sizing and hold verdict is the per-trade difference
log(1 + h k r_alt) - log(1 + h r_as_traded), averaged, with its t-statistic.

THIS IS THE SECOND GOVERNANCE RULE MADE MEASURABLE. "Every strong opportunity must be allowed to
increase capital above normal when the evidence supports it." SIZE_UP_EARNS is exactly that
evidence: growth at 1.5x or 2.0x exceeds growth at 1.0x with |t| >= 2 on at least 30 trades. And
"Every risk reduction mechanism must prove that it increases robust forward E[log W]." --
SIZE_DOWN_EARNS is that proof for a smaller size; a sleeve that cannot show it is not sized down
on prudence. Each verdict is a dE[log W] measurement with n and t attached, never a preference.

    SIZE_UP_EARNS        growth at 1.5x or 2.0x > growth at 1.0x, |t| >= 2, n >= 30
    SIZE_DOWN_EARNS      growth at 0.5x > growth at 1.0x, |t| >= 2, n >= 30
    HOLD_LONGER_EARNS    a horizon beyond the median bars held beats the realised exit, |t| >= 2
    EXIT_EARLIER_EARNS   a horizon short of the median bars held beats the realised exit, |t| >= 2
    AS_TRADED            n >= 30 and no alternative reaches |t| >= 2
    UNMEASURED           fewer than 30 measured trades

Where more than one alternative qualifies the sleeve's verdict is the largest dE[log W] and every
qualifying one is listed. MEASURES ONLY: nothing here sizes a lot, moves a stop, or edits a
certificate. SIZE_* verdicts become `sizing_hypothesis` tasks and HOLD/EXIT verdicts become
`exit_hypothesis` tasks for the deepening queue, each carrying the measured dE[log W] and n.

APPEND-ONLY, keyed on (sleeve, entry_time). A trade is measured once, when 48 bars after its
entry exist on this host; until then it is PENDING and re-tried next run. Sub-H1 sleeves (an
`_m5_` / `_m15_` token in the name) are skipped with the reason recorded: H1 bars cannot
measure a fifteen-minute path.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = _DESK / "data" / "action_counterfactuals.jsonl"
REPORT = _DESK / "reports" / "ACTION_COUNTERFACTUALS.json"
LIVE = _DESK / "data" / "live_ledger.jsonl"
FORECASTS = _DESK / "data" / "pf_forecast_log.jsonl"
LEDGER_DIRS = (_DESK / "reports" / "shadow", _ROOT / "backups" / "moat" / "shadow_ledgers")

HORIZONS: tuple[int, ...] = (1, 6, 12, 24, 48)
SIZES: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
MIN_TRADES = 30
T_MIN = 2.0
#: Risk fraction per R assumed for a sleeve the allocator does not fund. Stated on the row.
FALLBACK_H = 0.01
#: Sleeve-name tokens that mark a clock H1 bars cannot resolve.
SUB_H1_TOKENS = ("_m1_", "_m5_", "_m15_", "_m30_")
#: Ledger symbol prefixes that are not MT5 tickers. The MT5 / Fusion universe only.
SYMBOL_ALIASES = {"GOLD": "XAUUSD", "XAU": "XAUUSD", "SILVER": "XAGUSD", "XAG": "XAGUSD"}

SIZE_UP, SIZE_DOWN, HOLD_LONGER, EXIT_EARLIER, AS_TRADED, UNMEASURED = (
    "SIZE_UP_EARNS", "SIZE_DOWN_EARNS", "HOLD_LONGER_EARNS", "EXIT_EARLIER_EARNS",
    "AS_TRADED", "UNMEASURED")


def _rows(path: Path) -> list[dict]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def _load_bars(sym: str) -> pd.DataFrame | None:
    from research import proposer_common as pc
    return pc.bars(sym)


def _symbol_of(sleeve: str) -> str:
    from research.excursions import _symbol_of as sym
    raw = sym(sleeve)
    return SYMBOL_ALIASES.get(raw, raw)


def _ts(v: object) -> pd.Timestamp | None:
    try:
        t = pd.Timestamp(str(v))
    except (TypeError, ValueError):
        return None
    if t is pd.NaT:
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t


def counterfactual_path(bars: pd.DataFrame, entry_time: str, exit_time: str, side: int,
                        entry: float, risk: float) -> dict | None:
    """Hold alternatives in R on the bars after entry, with the 1R stop kept. None = PENDING."""
    t0, t1 = _ts(entry_time), _ts(exit_time)
    if t0 is None or risk <= 0 or not np.isfinite(risk):
        return None
    after = bars[bars.index > t0]
    if len(after) < max(HORIZONS):
        return None
    seg = after.iloc[:max(HORIZONS)]
    hi = seg["high"].to_numpy(float)
    lo = seg["low"].to_numpy(float)
    cl = seg["close"].to_numpy(float)
    adverse = (entry - lo) if side > 0 else (hi - entry)
    breached = adverse >= risk
    first_hit = int(np.argmax(breached)) if bool(breached.any()) else None
    hold: dict[str, float] = {}
    for k in HORIZONS:
        if first_hit is not None and first_hit < k:
            hold[str(k)] = -1.0
        else:
            hold[str(k)] = round(float(side * (cl[k - 1] - entry) / risk), 4)
    bars_held = int(((bars.index > t0) & (bars.index <= t1)).sum()) if t1 is not None else None
    return {"hold": hold, "bars_held": bars_held,
            "stop_hit_bar": (first_hit + 1 if first_hit is not None else None)}


def _trade(r: object, sleeve: str, basis: str) -> dict | None:
    if not isinstance(r, dict) or not sleeve:
        return None
    # A live row the gateway could not reconstruct an R for (no entry or stop price) carries a
    # fabricated zero; it is not a trade this ledger can replay.
    if basis == "live" and r.get("r_unreconstructible"):
        return None
    et = r.get("entry_time") or r.get("opened_at") or r.get("open_time")
    xt = r.get("exit_time") or r.get("close_time") or r.get("time")
    try:
        rm = float(r.get("r_multiple"))
        entry = float(r.get("entry") if r.get("entry") is not None else r.get("entry_price"))
        exit_ = float(r.get("exit") if r.get("exit") is not None else r.get("fill_price"))
    except (TypeError, ValueError):
        return None
    if not et or not all(np.isfinite(x) for x in (rm, entry, exit_)) or entry <= 0:
        return None
    s = str(r.get("side", 1)).lower()
    side = ((1 if s in ("0", "0.0", "buy", "long") else -1) if basis == "live"
            else (1 if s in ("long", "buy", "1", "1.0") else -1))
    stop = r.get("stop") if r.get("stop") is not None else r.get("sl")
    try:
        stop_f = float(stop) if stop is not None else None
    except (TypeError, ValueError):
        stop_f = None
    if stop_f is not None and np.isfinite(stop_f) and stop_f > 0 and stop_f != entry:
        risk, risk_source = abs(entry - stop_f), "stop_on_row"
    elif rm != 0.0 and exit_ != entry:
        risk, risk_source = abs(exit_ - entry) / abs(rm), "realised_r"
    else:
        risk, risk_source = 0.0, "none"
    return {"sleeve": sleeve, "symbol": _symbol_of(sleeve), "basis": basis,
            "entry_time": str(et), "exit_time": str(xt or ""), "side": side, "entry": entry,
            "exit": exit_, "r_multiple": rm, "reason": r.get("reason"), "risk_price": risk,
            "risk_source": risk_source}


def load_trades() -> tuple[list[dict], dict[str, str]]:
    gaps: dict[str, str] = {}
    out: list[dict] = []
    unparsed: dict[str, int] = {}
    for d in LEDGER_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            try:
                rows = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rows, list):
                continue
            sleeve = f.stem.removeprefix("ledger_")
            for r in rows:
                t = _trade(r, sleeve, "shadow")
                if t is not None:
                    out.append(t)
                else:
                    unparsed[sleeve] = unparsed.get(sleeve, 0) + 1
    if unparsed:
        gaps["unparsed_rows"] = (f"{sum(unparsed.values())} ledger rows carry no "
                                 "entry_time/entry/exit/r_multiple and cannot be replayed: "
                                 + ", ".join(f"{k}={v}" for k, v in sorted(unparsed.items())))
    if LIVE.exists():
        live = _rows(LIVE)
        kept = [t for r in live if (t := _trade(r, str(r.get("sleeve") or ""), "live"))]
        out.extend(kept)
        if len(kept) < len(live):
            gaps["live_ledger"] = (f"{len(live) - len(kept)} of {len(live)} live rows carry no "
                                   "entry_time / entry / exit and cannot be replayed")
    else:
        gaps["live_ledger"] = "absent on this host; shadow basis only"
    return out, gaps


def _done() -> set[str]:
    return {f"{r.get('sleeve')}|{r.get('entry_time')}" for r in _rows(OUT)}


def measure(trades: list[dict], done: set[str]) -> tuple[list[dict], Counter]:
    """Replay every not-yet-measured trade with bars on this host. Reasons for the rest."""
    skipped: Counter = Counter()
    cache: dict[str, pd.DataFrame | None] = {}
    new: list[dict] = []
    for t in trades:
        key = f"{t['sleeve']}|{t['entry_time']}"
        if key in done:
            continue
        if any(tok in t["sleeve"].lower() for tok in SUB_H1_TOKENS):
            skipped["sub_h1_sleeve"] += 1
            continue
        if t["risk_price"] <= 0:
            skipped["no_risk_scale"] += 1
            continue
        sym = t["symbol"]
        if sym not in cache:
            cache[sym] = _load_bars(sym)
        bars = cache[sym]
        if bars is None:
            skipped["no_bars"] += 1
            continue
        cf = counterfactual_path(bars, t["entry_time"], t["exit_time"], t["side"], t["entry"],
                                 t["risk_price"])
        if cf is None:
            skipped["pending"] += 1
            continue
        new.append({**t, **cf, "opposite_r": round(-t["r_multiple"], 4), "bar_clock": "H1",
                    "measured_at": datetime.now(tz=UTC).isoformat()})
        done.add(key)
    return new, skipped


def _book() -> tuple[dict[str, float], dict]:
    lines = _rows(FORECASTS)
    if not lines:
        return {}, {"source": f"pf_forecast_log absent on this host; h={FALLBACK_H} for every "
                              "sleeve"}
    last = lines[-1]
    book = {str(k): float(v) for k, v in (last.get("book") or {}).items()
            if isinstance(v, (int, float)) and float(v) > 0}
    return book, {"source": "pf_forecast_log (last line)", "t": last.get("t"),
                  "total_heat": last.get("total_heat"),
                  "expected_log_per_day": last.get("expected_log_per_day")}


def _tstat(x: np.ndarray) -> float | None:
    if x.size < 2:
        return None
    sd = float(x.std(ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return None
    return round(float(x.mean()) / (sd / float(np.sqrt(x.size))), 3)


def _log_growth(ret: np.ndarray) -> np.ndarray | None:
    """log(1 + ret) per trade, or None when any trade would have been ruin at that size."""
    x = 1.0 + ret
    if np.any(x <= 0) or not np.all(np.isfinite(x)):
        return None
    return np.log(x)


def _versus(alt: np.ndarray | None, base: np.ndarray) -> dict:
    if alt is None:
        return {"growth": None, "delta_elogw": None, "t": None, "why": "ruin at this size"}
    d = alt - base
    return {"growth": round(float(alt.mean()), 6), "delta_elogw": round(float(d.mean()), 6),
            "t": _tstat(d)}


def judge(rows: list[dict], h: float, h_source: str) -> dict:
    """Per-sleeve growth of every alternative against the trades as taken, and the verdict."""
    r = np.array([x["r_multiple"] for x in rows], dtype=float)
    n = int(r.size)
    base = _log_growth(h * r)
    out: dict = {"n": n, "h": h, "h_source": h_source, "mean_r": round(float(r.mean()), 4),
                 "t_r": _tstat(r), "trades_per_day": _trades_per_day(rows)}
    held = np.array([x["bars_held"] for x in rows if x.get("bars_held") is not None], dtype=float)
    med_held = float(np.median(held)) if held.size else None
    out["median_bars_held"] = med_held
    if base is None:
        out.update({"verdict": UNMEASURED, "verdicts_all": [],
                    "why": f"a trade at h={h} would have been ruin as traded; not priced"})
        return out
    out["as_traded"] = {"growth": round(float(base.mean()), 6)}
    out["sizing"] = {f"{k:.1f}x": _versus(_log_growth(k * h * r), base) for k in SIZES}
    holds: dict[str, dict] = {}
    for k in HORIZONS:
        hr = np.array([float(x["hold"][str(k)]) for x in rows], dtype=float)
        holds[str(k)] = {"mean_r": round(float(hr.mean()), 4),
                         **_versus(_log_growth(h * hr), base)}
    out["holds"] = holds
    out["opposite"] = {"mean_r": round(float(-r.mean()), 4),
                       **_versus(_log_growth(h * -r), base)}

    cands: list[dict] = []
    if n >= MIN_TRADES:
        for k in (1.5, 2.0):
            s = out["sizing"][f"{k:.1f}x"]
            if s["delta_elogw"] is not None and s["delta_elogw"] > 0 and (s["t"] or 0) >= T_MIN:
                cands.append({"verdict": SIZE_UP, "alternative": f"{k:.1f}x",
                              "delta_elogw": s["delta_elogw"], "t": s["t"]})
        s = out["sizing"]["0.5x"]
        if s["delta_elogw"] is not None and s["delta_elogw"] > 0 and (s["t"] or 0) >= T_MIN:
            cands.append({"verdict": SIZE_DOWN, "alternative": "0.5x",
                          "delta_elogw": s["delta_elogw"], "t": s["t"]})
        if med_held is not None:
            for k in HORIZONS:
                hd = holds[str(k)]
                if hd["delta_elogw"] is None or hd["delta_elogw"] <= 0 or (hd["t"] or 0) < T_MIN:
                    continue
                if k > med_held:
                    cands.append({"verdict": HOLD_LONGER, "alternative": f"+{k} bars",
                                  "delta_elogw": hd["delta_elogw"], "t": hd["t"]})
                elif k < med_held:
                    cands.append({"verdict": EXIT_EARLIER, "alternative": f"+{k} bars",
                                  "delta_elogw": hd["delta_elogw"], "t": hd["t"]})
    cands.sort(key=lambda c: -c["delta_elogw"])
    out["verdicts_all"] = cands
    if n < MIN_TRADES:
        out.update({"verdict": UNMEASURED, "why": f"{n} measured trades; {MIN_TRADES} needed"})
    elif not cands:
        out.update({"verdict": AS_TRADED,
                    "why": f"no alternative reaches |t| >= {T_MIN} on {n} trades"})
    else:
        best = cands[0]
        tpd = out["trades_per_day"]
        out.update({"verdict": best["verdict"], "best_alternative": best["alternative"],
                    "delta_elogw_per_trade": best["delta_elogw"],
                    "delta_elogw_per_day": (round(best["delta_elogw"] * tpd, 6) if tpd else None),
                    "why": (f"{best['alternative']} vs as traded: dE[log W] "
                            f"{best['delta_elogw']:+.6f} per trade, t={best['t']}, n={n}, "
                            f"h={h} ({h_source})")})
    return out


def _trades_per_day(rows: list[dict]) -> float | None:
    ts = [t for x in rows if (t := _ts(x.get("entry_time"))) is not None]
    if len(ts) < 2:
        return None
    days = max((max(ts) - min(ts)).total_seconds() / 86400.0, 1.0)
    return round(len(ts) / days, 4)


def _family_of(sleeve: str) -> str:
    from research.regime_coverage import _family_of as fam
    return fam(sleeve)


def tasks_for(per: dict[str, dict]) -> list[dict]:
    """One task per qualifying verdict CLASS per sleeve, each at its best alternative.

    A sleeve where holding longer AND sizing up both clear |t| >= 2 has two hypotheses, not
    one; the larger dE[log W] names the sleeve's verdict but does not hide the other.
    """
    tasks = []
    for sleeve, s in per.items():
        if s.get("verdict") in (UNMEASURED, AS_TRADED) or not s.get("verdicts_all"):
            continue
        best_by_verdict: dict[str, dict] = {}
        for c in s["verdicts_all"]:                       # sorted by dE[log W], best first
            best_by_verdict.setdefault(c["verdict"], c)
        tpd = s.get("trades_per_day")
        for v, c in best_by_verdict.items():
            kind = "sizing_hypothesis" if v in (SIZE_UP, SIZE_DOWN) else "exit_hypothesis"
            ask = ("Propose the sizing multiplier as a hypothesis for the allocator's evidence "
                   "-- the allocator, not this task, sizes; the second governance rule says a "
                   "strong opportunity must be allowed above normal when the evidence supports "
                   "it, and this is that evidence." if kind == "sizing_hypothesis" else
                   "Propose ONE exit rule (time stop at the named horizon, or a target it "
                   "implies) as exact parameters for a NEW cell with its own multiplicity "
                   "charge; the certified entry is not changed.")
            per_day = f" ({c['delta_elogw'] * tpd:+.6f} per day)" if tpd else ""
            tasks.append({
                "source": "action_counterfactuals", "kind": kind,
                "title": f"{sleeve}: {v} ({c['alternative']})",
                "description": (f"{s['n']} measured trades, mean R {s['mean_r']} "
                                f"(t={s['t_r']}), median bars held {s['median_bars_held']}. "
                                f"{c['alternative']} vs as traded: dE[log W] "
                                f"{c['delta_elogw']:+.6f} per trade{per_day} at h={s['h']} "
                                f"({s['h_source']}), t={c['t']}, n={s['n']}. Sleeve verdict "
                                f"{s['verdict']}; all qualifying: {s['verdicts_all']}. {ask}"),
                "symbols": [_symbol_of(sleeve)], "family": _family_of(sleeve), "params": {},
                "sleeve": sleeve, "verdict": v, "alternative": c["alternative"],
                "evidence": {"n": s["n"], "h": s["h"], "delta_elogw_per_trade": c["delta_elogw"],
                             "t": c["t"]},
                "status": None,
                "consumer": ("pf_allocator evidence / research brains"
                             if kind == "sizing_hypothesis" else "exit_sweep / research brains")})
    return tasks


def run() -> dict:
    trades, gaps = load_trades()
    done = _done()
    new, skipped = measure(trades, done)
    if new:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r) + "\n")
    allrows = [r for r in _rows(OUT) if isinstance(r.get("hold"), dict)]
    book, book_ctx = _book()
    by: dict[str, list[dict]] = defaultdict(list)
    for r in allrows:
        by[str(r["sleeve"])].append(r)
    per: dict[str, dict] = {}
    for sleeve, rows in by.items():
        h = book.get(sleeve)
        per[sleeve] = judge(rows, h if h else FALLBACK_H,
                            "pf_forecast_log book" if h else f"fallback {FALLBACK_H} (unfunded)")
    tasks = tasks_for(per)
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "n_trades": len(trades),
           "new_measured": len(new), "total_measured": len(allrows),
           "skipped": dict(skipped), "gaps": gaps, "allocator_book": book_ctx,
           "horizons": list(HORIZONS), "sizes": list(SIZES),
           "verdicts": {v: sum(1 for s in per.values() if s["verdict"] == v)
                        for v in (SIZE_UP, SIZE_DOWN, HOLD_LONGER, EXIT_EARLIER, AS_TRADED,
                                  UNMEASURED)},
           "sleeves": per, "tasks": tasks,
           "rule": ("growth(k) = E[log(1 + k h r)] over the sleeve's trades, never k x E[h r]; "
                    "verdict = largest dE[log W] alternative with |t| >= "
                    f"{T_MIN} on n >= {MIN_TRADES}; holds keep the 1R stop; MEASURES ONLY")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        from research.regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source="action_counterfactuals")
    except Exception as exc:
        doc["queue_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"ACTION COUNTERFACTUALS  {d['n_trades']} trades, {d['new_measured']} new, "
          f"{d['total_measured']} measured, skipped {d['skipped']}; verdicts {d['verdicts']}")
    for s, v in sorted(d["sleeves"].items(), key=lambda kv: -kv[1]["n"])[:14]:
        print(f"  {s[:38]:38s} n={v['n']:3d} h={v['h']:.4f} {v['verdict']:18s} "
              f"{str(v.get('why'))[:56]}")
    for g, why in d["gaps"].items():
        print(f"  GAP {g}: {why}")
    print(f"written: {OUT}  report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
