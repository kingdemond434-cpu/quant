"""Exit attribution: what every exit captured, left on the table and survived, by sleeve and reason.

THE EXCURSION LEDGER SAYS HOW FAR; THIS SAYS WHO GAVE IT BACK. `excursions` records, per trade,
the maximum favourable and adverse excursion in R. On its own that is a distribution. Joined to
the exit REASON on the ledger row it becomes an account:

    captured          = r_multiple                    what the exit rule banked
    left_on_table     = max(mfe_r - r_multiple, 0)    favourable excursion the exit did not keep
    adverse_survived  = mae_r                         how far against the trade went and lived

aggregated per sleeve and per exit reason (target / stop / ttl / other), so a target that fires
at 1R on trades whose median excursion is 2R, a time stop that closes winners still running, and
a stop that is touched and reversed each show up as a NUMBER on the reason that did it, not as a
feeling that "exits could be better".

VERDICTS ARE dE[log W] MEASUREMENTS, NEVER PRUDENCE. The desk's governance rules apply to exits as
they apply to sizing: "Every risk reduction mechanism must prove that it increases robust forward
E[log W]." and "Every strong opportunity must be allowed to increase capital above normal when
the evidence supports it." A target or time stop is a risk reduction mechanism -- it gives up
excursion in exchange for certainty -- and it must earn that trade in log-wealth. The
`growth_left_on_table` section prices the give-back with the allocator's own weight h for the
sleeve: dE[log W] per trade = E[log(1 + h(R + left)) - log(1 + hR)], the growth the book would
have had if the exit had kept the excursion. That number is an UPPER BOUND -- no exit rule keeps
the whole MFE -- and it is stated as one. Where the sleeve carries no allocator weight the
give-back is reported in R and the units are said.

    TARGET_TOO_NEAR   median MFE exceeds the target-R implied by the target exits' mean R by >50%
    TIME_STOP_BINDS   ttl exits carry positive mean R and a median MFE above twice what they kept
    STOP_TOO_TIGHT    most stop exits barely exceeded the stop AND had positive MFE in the window
    AS_IS             none of the above at n >= 20 joined trades
    UNMEASURED        fewer than 20 trades on the ledger
    UNMEASURED_PATH   enough trades, but the excursion ledger has no path for them on this host

WHAT THE PATH LEDGER CANNOT SAY. `excursions` stores the window extremes, not their ORDER, so
"MFE before the stop" is approximated by the window MFE (every bar in the window precedes the
exit). Stop distance is not on the ledger row; "barely exceeded" is measured against the realised
|R| of the stop exit, which is the stop plus slippage.

NEVER CHANGES A CERTIFIED ENTRY. A non-AS_IS verdict becomes an `exit_hypothesis` task for the
deepening queue carrying the numbers, to be answered as a NEW cell with its own multiplicity
charge. This module writes a report and research instructions; it moves no stop and no target.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

EXCURSIONS = _DESK / "data" / "excursions.jsonl"
LIVE = _DESK / "data" / "live_ledger.jsonl"
FORECASTS = _DESK / "data" / "pf_forecast_log.jsonl"
LEDGER_DIRS = (_DESK / "reports" / "shadow", _ROOT / "backups" / "moat" / "shadow_ledgers")
REPORT = _DESK / "reports" / "EXIT_ACCOUNTS.json"

#: Joined trades a sleeve needs before any verdict other than UNMEASURED is written.
MIN_TRADES = 20
#: Trades an exit REASON needs before its mean is used to imply a target or judge a rule.
MIN_REASON_N = 5
#: A stop exit "barely" exceeded its stop when MAE is within this many R of the realised |R|.
STOP_BARELY_R = 0.25
#: A stop exit "had positive MFE" when the window MFE reached at least this many R.
MFE_POSITIVE_R = 0.5

TARGET_TOO_NEAR, TIME_STOP_BINDS, STOP_TOO_TIGHT, AS_IS, UNMEASURED, UNMEASURED_PATH = (
    "TARGET_TOO_NEAR", "TIME_STOP_BINDS", "STOP_TOO_TIGHT", "AS_IS", "UNMEASURED",
    "UNMEASURED_PATH")
REASONS = ("target", "stop", "ttl", "other")


def _rows(path: Path) -> list[dict]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def _side(v: object, basis: str = "shadow") -> int:
    """+1 long / -1 short. Shadow rows write +-1 or a word; the live ledger writes the MT5
    position type, where 0 is BUY and 1 is SELL -- the same digit means the opposite side."""
    s = str(v).lower()
    if basis == "live":
        return 1 if s in ("0", "0.0", "buy", "long") else -1
    return 1 if s in ("long", "buy", "1", "1.0") else -1


def _reason_bucket(reason: object) -> str:
    r = str(reason or "").lower()
    return r if r in ("target", "stop", "ttl") else "other"


def _first(row: dict, *keys: str) -> object:
    for k in keys:
        v = row.get(k)
        if v is not None and v != "":
            return v
    return None


def load_trades() -> tuple[list[dict], dict[str, str]]:
    """Every taken trade the desk can account for, with the basis it was taken on and any gap.

    Shadow ledgers name the sleeve by file; the live ledger names it on the row. A live row
    without an entry timestamp cannot be joined to a path and is counted, not guessed.
    """
    gaps: dict[str, str] = {}
    out: list[dict] = []
    seen_dir = False
    unparsed: dict[str, int] = {}
    for d in LEDGER_DIRS:
        if not d.is_dir():
            continue
        seen_dir = True
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
    if not seen_dir:
        gaps["shadow_ledgers"] = "no shadow ledger directory on this host"
    if unparsed:
        # A row with only an R and no entry price (the sub-H1 scalp ledgers) has no path to
        # account for; it is counted here, never silently dropped.
        gaps["unparsed_rows"] = (f"{sum(unparsed.values())} ledger rows carry no "
                                 "entry_time/entry/r_multiple and cannot be joined to a path: "
                                 + ", ".join(f"{k}={v}" for k, v in sorted(unparsed.items())))
    if LIVE.exists():
        n_no_entry = 0
        for r in _rows(LIVE):
            t = _trade(r, str(r.get("sleeve") or ""), "live")
            if t is None:
                n_no_entry += 1
            else:
                out.append(t)
        if n_no_entry:
            gaps["live_ledger"] = (f"{n_no_entry} live rows carry no entry_time/entry/r_multiple "
                                   "and cannot be joined to a path")
    else:
        gaps["live_ledger"] = "absent on this host; shadow basis only"
    return out, gaps


def _trade(r: object, sleeve: str, basis: str) -> dict | None:
    if not isinstance(r, dict) or not sleeve:
        return None
    # A live row the gateway could not reconstruct an R for carries a fabricated zero, and a
    # row without a positive entry price has no path: neither is accounted, both are counted.
    if basis == "live" and r.get("r_unreconstructible"):
        return None
    et = _first(r, "entry_time", "opened_at", "open_time")
    xt = _first(r, "exit_time", "close_time", "time")
    try:
        rm = float(_first(r, "r_multiple", "r", "R"))
        entry = float(_first(r, "entry", "entry_price", "price_open"))
    except (TypeError, ValueError):
        return None
    if not et or not np.isfinite(rm) or not np.isfinite(entry) or entry <= 0:
        return None
    return {"sleeve": sleeve, "basis": basis, "entry_time": str(et), "exit_time": str(xt or ""),
            "side": _side(r.get("side", 1), basis), "entry": entry, "r_multiple": rm,
            "reason": _reason_bucket(r.get("reason")), "reason_raw": r.get("reason")}


def join_excursions(trades: list[dict], excursions: list[dict]) -> list[dict]:
    """Attach mfe_r / mae_r by (sleeve, entry_time); a trade without a path row stays unjoined."""
    path = {f"{e.get('sleeve')}|{e.get('entry_time')}": e for e in excursions
            if isinstance(e, dict)}
    out = []
    for t in trades:
        e = path.get(f"{t['sleeve']}|{t['entry_time']}")
        row = dict(t)
        if e is not None and e.get("mfe_r") is not None and e.get("mae_r") is not None:
            try:
                row["mfe_r"], row["mae_r"] = float(e["mfe_r"]), float(e["mae_r"])
                row["bars"] = int(e.get("bars") or 0)
                row.update(decompose(row))
                row["joined"] = True
            except (TypeError, ValueError):
                row["joined"] = False
        else:
            row["joined"] = False
        out.append(row)
    return out


def decompose(t: dict) -> dict:
    """captured / left_on_table / adverse_survived, all in R."""
    r, mfe, mae = float(t["r_multiple"]), float(t["mfe_r"]), float(t["mae_r"])
    return {"captured_r": round(r, 4), "left_on_table_r": round(max(mfe - r, 0.0), 4),
            "adverse_survived_r": round(mae, 4)}


def _tstat(x: np.ndarray) -> float | None:
    if x.size < 2:
        return None
    sd = float(x.std(ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return None
    return round(float(x.mean()) / (sd / float(np.sqrt(x.size))), 3)


def _group(rows: list[dict]) -> dict:
    r = np.array([x["r_multiple"] for x in rows], dtype=float)
    mfe = np.array([x["mfe_r"] for x in rows], dtype=float)
    mae = np.array([x["mae_r"] for x in rows], dtype=float)
    left = np.array([x["left_on_table_r"] for x in rows], dtype=float)
    mean_mfe = float(mfe.mean())
    return {"n": int(r.size), "mean_r": round(float(r.mean()), 4),
            "median_r": round(float(np.median(r)), 4), "t_r": _tstat(r),
            "median_mfe_r": round(float(np.median(mfe)), 4), "mean_mfe_r": round(mean_mfe, 4),
            "median_mae_r": round(float(np.median(mae)), 4),
            "capture_ratio": (round(float(r.mean()) / mean_mfe, 4) if mean_mfe > 0 else None),
            "mean_left_on_table_r": round(float(left.mean()), 4),
            "mean_adverse_survived_r": round(float(mae.mean()), 4)}


def aggregate(trades: list[dict]) -> dict[str, dict]:
    """Per sleeve: the whole account and the account per exit reason, from joined trades only."""
    by: dict[str, list[dict]] = defaultdict(list)
    n_all: dict[str, int] = defaultdict(int)
    basis: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    span: dict[str, list[str]] = defaultdict(list)
    for t in trades:
        n_all[t["sleeve"]] += 1
        basis[t["sleeve"]][t["basis"]] += 1
        span[t["sleeve"]].append(t["entry_time"])
        if t.get("joined"):
            by[t["sleeve"]].append(t)
    per: dict[str, dict] = {}
    for sleeve in n_all:
        rows = by.get(sleeve, [])
        stat: dict = {"n_trades": n_all[sleeve], "n_joined": len(rows),
                      "basis": dict(basis[sleeve]), "trades_per_day": _trades_per_day(span[sleeve])}
        if rows:
            stat.update(_group(rows))
            reasons: dict[str, dict] = {}
            for reason in REASONS:
                rs = [x for x in rows if x["reason"] == reason]
                if rs:
                    reasons[reason] = _group(rs)
            stat["by_reason"] = reasons
            tg = reasons.get("target")
            stat["implied_target_r"] = (tg["mean_r"] if tg and tg["n"] >= MIN_REASON_N
                                        and tg["mean_r"] > 0 else None)
            stat["stop_barely_and_positive_frac"] = _stop_barely_frac(rows)
        v, flags, why = verdict(stat)
        stat.update({"verdict": v, "flags": flags, "why": why})
        per[sleeve] = stat
    return per


def _trades_per_day(stamps: list[str]) -> float | None:
    ts = []
    for s in stamps:
        try:
            ts.append(datetime.fromisoformat(str(s).replace(" ", "T")))
        except ValueError:
            continue
    if len(ts) < 2:
        return None
    days = max((max(ts) - min(ts)).total_seconds() / 86400.0, 1.0)
    return round(len(ts) / days, 4)


def _stop_barely_frac(rows: list[dict]) -> float | None:
    stops = [x for x in rows if x["reason"] == "stop"]
    if not stops:
        return None
    hits = sum(1 for x in stops
               if x["mae_r"] <= max(1.0, abs(x["r_multiple"])) + STOP_BARELY_R
               and x["mfe_r"] >= MFE_POSITIVE_R)
    return round(hits / len(stops), 4)


def verdict(stat: dict) -> tuple[str, list[str], str]:
    """The sleeve's exit verdict, every flag that fired, and the measured reason in one line."""
    n_all, n = int(stat.get("n_trades", 0)), int(stat.get("n_joined", 0))
    if n_all < MIN_TRADES:
        return UNMEASURED, [], f"{n_all} trades on the ledger; {MIN_TRADES} needed"
    if n < MIN_TRADES:
        return UNMEASURED_PATH, [], (f"{n_all} trades but only {n} with an excursion path; "
                                     f"{MIN_TRADES} joined trades needed")
    flags: list[str] = []
    why: list[str] = []
    by = stat.get("by_reason") or {}
    tgt = stat.get("implied_target_r")
    if tgt is not None and stat["median_mfe_r"] > 1.5 * tgt:
        flags.append(TARGET_TOO_NEAR)
        why.append(f"median MFE {stat['median_mfe_r']}R vs implied target {tgt}R "
                   f"(+{100.0 * (stat['median_mfe_r'] / tgt - 1.0):.0f}%)")
    ttl = by.get("ttl")
    if (ttl and ttl["n"] >= MIN_REASON_N and ttl["mean_r"] > 0
            and ttl["median_mfe_r"] > 2.0 * ttl["mean_r"]):
        flags.append(TIME_STOP_BINDS)
        why.append(f"{ttl['n']} ttl exits keep {ttl['mean_r']}R of a median "
                   f"{ttl['median_mfe_r']}R excursion")
    stop = by.get("stop")
    frac = stat.get("stop_barely_and_positive_frac")
    if stop and stop["n"] >= MIN_REASON_N and frac is not None and frac > 0.5:
        flags.append(STOP_TOO_TIGHT)
        why.append(f"{100.0 * frac:.0f}% of {stop['n']} stop exits barely exceeded the stop "
                   f"(MAE within {STOP_BARELY_R}R of |R|) with MFE >= {MFE_POSITIVE_R}R")
    if not flags:
        return AS_IS, [], (f"{n} joined trades; capture ratio {stat.get('capture_ratio')}, "
                           f"mean left on table {stat['mean_left_on_table_r']}R")
    return flags[0], flags, "; ".join(why)


def _book() -> tuple[dict[str, float], dict]:
    """The allocator's last book: sleeve -> risk fraction per R, plus the line's context."""
    lines = _rows(FORECASTS)
    if not lines:
        return {}, {"source": "pf_forecast_log absent on this host; give-back stated in R"}
    last = lines[-1]
    book = {str(k): float(v) for k, v in (last.get("book") or {}).items()
            if isinstance(v, (int, float))}
    return book, {"source": "pf_forecast_log (last line)", "t": last.get("t"),
                  "total_heat": last.get("total_heat"),
                  "expected_log_per_day": last.get("expected_log_per_day")}


def growth_left_on_table(trades: list[dict], per: dict[str, dict],
                         book: dict[str, float]) -> dict[str, dict]:
    """dE[log W] the exits gave back, per sleeve, priced at the allocator's weight h.

    Growth is not linear in R, so the proxy is the mean over trades of
    log(1 + h(R + left)) - log(1 + hR) -- the exact log-wealth difference between what the exit
    kept and what the path offered -- with the linear h x mean(left) beside it for scale. A
    sleeve the allocator does not fund has no h; its give-back is in R and says so.
    """
    by: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        if t.get("joined"):
            by[t["sleeve"]].append(t)
    out: dict[str, dict] = {}
    for sleeve, stat in per.items():
        rows = by.get(sleeve, [])
        if not rows:
            out[sleeve] = {"n": 0, "units": "R", "mean_left_on_table_r": None,
                           "delta_elogw_per_trade": None, "why": "no excursion path joined"}
            continue
        r = np.array([x["r_multiple"] for x in rows], dtype=float)
        left = np.array([x["left_on_table_r"] for x in rows], dtype=float)
        h = book.get(sleeve)
        row: dict = {"n": int(r.size), "mean_left_on_table_r": round(float(left.mean()), 4),
                     "allocator_weight_h": h, "verdict": stat.get("verdict"),
                     "bound": "upper: no exit rule keeps the whole favourable excursion"}
        if h is None or h <= 0:
            row.update({"units": "R", "delta_elogw_per_trade": None,
                        "why": "sleeve carries no allocator weight; give-back stated in R"})
        else:
            kept, offered = 1.0 + h * r, 1.0 + h * (r + left)
            if np.any(kept <= 0) or np.any(offered <= 0):
                row.update({"units": "log-wealth", "delta_elogw_per_trade": None,
                            "why": "a trade at this weight would have been ruin; not priced"})
            else:
                d = np.log(offered) - np.log(kept)
                tpd = stat.get("trades_per_day")
                row.update({"units": "log-wealth per trade (x trades_per_day for per day)",
                            "delta_elogw_per_trade": round(float(d.mean()), 6),
                            "delta_elogw_linear": round(float(h * left.mean()), 6),
                            "trades_per_day": tpd,
                            "delta_elogw_per_day": (round(float(d.mean()) * tpd, 6)
                                                    if tpd else None)})
        out[sleeve] = row
    return out


def _symbol_of(sleeve: str) -> str:
    from research.excursions import _symbol_of as sym
    return sym(sleeve)


def _family_of(sleeve: str) -> str:
    from research.regime_coverage import _family_of as fam
    return fam(sleeve)


def tasks_for(per: dict[str, dict], growth: dict[str, dict]) -> list[dict]:
    """One exit_hypothesis per non-AS_IS sleeve, the numbers attached, the entry untouched."""
    tasks = []
    for sleeve, stat in per.items():
        v = stat.get("verdict")
        if v not in (TARGET_TOO_NEAR, TIME_STOP_BINDS, STOP_TOO_TIGHT):
            continue
        g = growth.get(sleeve, {})
        priced = (f"dE[log W] left on the table ~{g['delta_elogw_per_trade']:+.6f} per trade at "
                  f"allocator weight h={g['allocator_weight_h']} (upper bound)"
                  if g.get("delta_elogw_per_trade") is not None else
                  f"mean left on the table {stat['mean_left_on_table_r']}R per trade "
                  "(no allocator weight; R units)")
        tasks.append({
            "source": "exit_accounts", "kind": "exit_hypothesis",
            "title": f"{sleeve}: {v} -- {stat['why']}",
            "description": (f"{stat['n_joined']} joined trades ({stat['n_trades']} on the "
                            f"ledger). Verdict {v}; flags {stat['flags']}. mean R "
                            f"{stat['mean_r']} (t={stat['t_r']}), median MFE "
                            f"{stat['median_mfe_r']}R, median MAE {stat['median_mae_r']}R, "
                            f"capture ratio {stat['capture_ratio']}. By reason: "
                            + "; ".join(f"{k} n={x['n']} meanR={x['mean_r']} "
                                        f"medMFE={x['median_mfe_r']}R"
                                        for k, x in (stat.get("by_reason") or {}).items())
                            + f". {priced}. Propose ONE exit rule (target distance, time stop, "
                            "trail, partial) as exact parameters for a NEW cell with its own "
                            "multiplicity charge. The certified entry is not changed."),
            "symbols": [_symbol_of(sleeve)], "family": _family_of(sleeve), "params": {},
            "sleeve": sleeve, "verdict": v, "flags": stat["flags"],
            "evidence": {"n_joined": stat["n_joined"], "mean_r": stat["mean_r"],
                         "median_mfe_r": stat["median_mfe_r"],
                         "implied_target_r": stat.get("implied_target_r"),
                         "delta_elogw_per_trade": g.get("delta_elogw_per_trade")},
            "status": None, "consumer": "exit_sweep / research brains"})
    return tasks


def run() -> dict:
    trades, gaps = load_trades()
    exc = _rows(EXCURSIONS)
    if not exc:
        gaps["excursions"] = ("excursions.jsonl absent or empty on this host; every sleeve is "
                              "UNMEASURED_PATH until `excursions` has run")
    joined = join_excursions(trades, exc)
    per = aggregate(joined)
    book, book_ctx = _book()
    growth = growth_left_on_table(joined, per, book)
    tasks = tasks_for(per, growth)
    n_joined = sum(1 for t in joined if t.get("joined"))
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "n_trades": len(trades),
           "n_joined": n_joined, "n_sleeves": len(per),
           "verdicts": {v: sum(1 for s in per.values() if s["verdict"] == v)
                        for v in (TARGET_TOO_NEAR, TIME_STOP_BINDS, STOP_TOO_TIGHT, AS_IS,
                                  UNMEASURED, UNMEASURED_PATH)},
           "allocator_book": book_ctx, "gaps": gaps, "sleeves": per,
           "growth_left_on_table": growth, "exit_hypotheses": tasks,
           "rule": ("captured = R; left_on_table = max(MFE - R, 0); adverse_survived = MAE; "
                    "dE[log W] per trade = E[log(1 + h(R + left)) - log(1 + hR)] at the "
                    "allocator's h -- an upper bound, stated as one; verdicts need "
                    f"{MIN_TRADES} joined trades; no certified entry is changed")}
    # THE BOOK-LEVEL NUMBER the growth decomposition reads (allocator_attribution._exit_term):
    # capture ratio weighted by joined trades, and its median across sleeves, from the sleeves
    # that have one. Absent when no sleeve does, so the reader says UNMEASURED rather than 1.0.
    ratios = [(float(v["capture_ratio"]), int(v.get("n") or v.get("n_joined") or 0))
              for v in per.values() if isinstance(v, dict)
              and isinstance(v.get("capture_ratio"), (int, float))]
    if ratios:
        wsum = sum(n for _, n in ratios) or len(ratios)
        doc["summary"] = {
            "capture_ratio": round(sum(r * (n or 1) for r, n in ratios) / wsum, 4),
            "median_capture_ratio": round(sorted(r for r, _ in ratios)[len(ratios) // 2], 4),
            "n_sleeves_with_ratio": len(ratios)}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        from research.regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source="exit_accounts")
    except Exception as exc_:
        doc["queue_error"] = f"{type(exc_).__name__}: {exc_}"
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"EXIT ACCOUNTS  {d['n_trades']} trades, {d['n_joined']} with a path, "
          f"{d['n_sleeves']} sleeves; verdicts {d['verdicts']}")
    for s, v in sorted(d["sleeves"].items(), key=lambda kv: -kv[1]["n_joined"])[:14]:
        print(f"  {s[:38]:38s} n={v['n_joined']:3d}/{v['n_trades']:3d} "
              f"{v['verdict']:16s} {v['why'][:60]}")
    for g, why in d["gaps"].items():
        print(f"  GAP {g}: {why}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
