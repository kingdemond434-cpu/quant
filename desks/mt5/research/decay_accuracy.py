"""DECAY ACCURACY -- how good is each decay DETECTOR, measured on the desk's own trade series.

Desk idea 249 ("fast decay retirement"), brief `reports/decay/DECAY_UPGRADE_BRIEF_2026-10-29.md`
item U5. A faster detector earns the right to act ONLY BY PROOF: growth governance Rule 1 says a
risk reduction must prove it increases robust forward E[log W], so a detector that alarms early
but alarms often is not an upgrade -- its false alarms are growth the book forgoes. This organ
replays every per-sleeve trade series causally, trade by trade, through each detector and scores
it on the same drawdown events.

IT ACTS ON NOTHING. It reads the shadow/forward ledgers, the live ledger, the roster (for names)
and the canon (for anchors), and writes `reports/DECAY_ACCURACY.json` and nothing else. No
gateway, allocator or roster file is touched; `decay_monitor` remains the only organ that moves a
sleeve. A detector the verdict calls PROMOTABLE still needs a human-reviewed change to
`decay_monitor` to act.

DETECTORS (each a causal function of the trades closed so far):

  CURRENT        `decay_monitor.stats` + `decay_monitor.verdict` on the trailing window (last
                 TRAIL_MAX_TRADES within TRAIL_DAYS of the trade being judged). Its alarm state is
                 FADE or RETIRE. Imported, never copied, so this measures the rule that trades.
  CUSUM          Page's lower CUSUM S = max(0, S + (mu0 - x)/sd - k), k = 0.5, h = 4 (declared,
                 never searched). mu0 is the series' certified per-trade expectancy (canon
                 `gates.expected_value.ev`) when a survivor matches, else the mean of its first
                 SELF_ANCHOR_N trades (and the series is then scored only after them). sd is the
                 declared unit risk (1R, a stop-defined trade's loss) on a certified anchor -- the
                 canon carries no per-trade dispersion -- and the self-anchor window's own sd
                 otherwise. Alarm when S > h; S resets to 0 after each alarm.
  FEATURE_DRIFT  The first-flag episodes `research/feature_drift.py` writes to
                 `data/feature_drift_state.json` ({sleeve: {episodes: [{first_flag_at, ...}]}}),
                 placed on a series at the last trade closed at or before the flag. Scored only
                 where an episode overlaps a series; UNMEASURED otherwise.

SCORING (identical for every detector):

  EVENT        a peak-to-trough fall of cumulative R of DD_EVENT_R (3R) or worse.
  LEAD R       R lost from the peak to the first trade at/after the peak at which the detector
               is in alarm (smaller is better). MISS: no alarm before the trough.
  FALSE ALARM  an alarm ONSET that is neither inside an event (peak..trough) nor followed by a
               >= 3R drawdown within the next FA_HORIZON (20) trades. An onset with fewer than 20
               trades after it and no drawdown yet is PENDING, not false.
  COST         (the missed_growth line) FADE_FACTOR x max(0, net R of the 20 trades after a false
               alarm): what a FADE at half risk would have forgone.

PROMOTION (CUSUM vs CURRENT): PROMOTABLE only if CUSUM's misses <= CURRENT's AND its median lead
R is smaller AND its false-alarm cost <= CURRENT's; NOT_PROMOTABLE with the reason otherwise;
UNMEASURED below MIN_EVENTS (5) events.

MISSED GROWTH. `missed_growth.py` is being rewritten in open PR #540, so this organ does not edit
it: it publishes its lines on its own report under `missed_growth` in the shape
`missed_growth.organ_published_lines` reads (`verdict`, `value`, `unit`, `at`). The carry line,
`"decay_accuracy": organ_published_lines(BASE / "reports" / "DECAY_ACCURACY.json")`, goes into
`missed_growth.py`'s organ block once #540 lands.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(ROOT), str(BASE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = BASE / "reports" / "DECAY_ACCURACY.json"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
DRIFT_STATE = BASE / "data" / "feature_drift_state.json"

# ---- the CURRENT rule, imported from the organ that trades it ---------------------------------
IMPORT_NOTE = "imported from research.decay_monitor"
try:
    from research import decay_monitor as _dm

    N_MIN_VERDICT: int = _dm.N_MIN_VERDICT
    EARLY_FADE_N: int = _dm.EARLY_FADE_N
    EARLY_FADE_R: float = _dm.EARLY_FADE_R
    DD_HARD_R: float = _dm.DD_HARD_R
    TRAIL_MAX_TRADES: int = _dm.TRAIL_MAX_TRADES
    T_PROMOTE: float = _dm.T_PROMOTE
    TRAIL_DAYS: int = _dm.TRAIL_DAYS
    LEDGER_NAME_MAX: int = _dm.LEDGER_NAME_MAX
    FADE_FACTOR: float = _dm.FADE_FACTOR
    SHADOW_LEDGER_DIRS: tuple[Path, ...] = tuple(_dm.SHADOW_LEDGER_DIRS)
    LEDGER: Path = _dm.LEDGER
    _stats: Callable[[list[float]], dict[str, Any]] = _dm.stats
    _verdict: Callable[[dict[str, Any]], tuple[str, str]] = _dm.verdict
    _row_time: Callable[[dict[str, Any]], datetime | None] = _dm._row_time
    _row_r: Callable[[dict[str, Any]], float | None] = _dm._row_r
except Exception as _e:  # pragma: no cover - the fallback is the declared degraded mode
    IMPORT_NOTE = (f"research.decay_monitor did not import ({type(_e).__name__}: {_e}); the "
                   f"CURRENT rule below is a FALLBACK copy of its 2026-11 thresholds and may "
                   f"lag the organ that trades")
    N_MIN_VERDICT, EARLY_FADE_N, EARLY_FADE_R, DD_HARD_R = 20, 5, 0.25, -25.0
    TRAIL_MAX_TRADES, T_PROMOTE, TRAIL_DAYS, LEDGER_NAME_MAX, FADE_FACTOR = 60, 2.5, 45, 27, 0.5
    SHADOW_LEDGER_DIRS = (BASE / "reports" / "shadow", ROOT / "backups" / "moat" / "shadow_ledgers")
    LEDGER = BASE / "data" / "live_ledger.jsonl"

    def _stats(rs: list[float]) -> dict[str, Any]:
        n = len(rs)
        out = {"n": n, "exp_r": 0.0, "t": 0.0, "max_dd_r": 0.0, "wins": 0}
        if not n:
            return out
        cum = peak = dd = 0.0
        for r in rs:
            cum += r
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
        mean = sum(rs) / n
        out.update({"exp_r": mean, "max_dd_r": dd, "wins": sum(1 for r in rs if r > 0)})
        if n >= 2:
            var = sum((x - mean) ** 2 for x in rs) / (n - 1)
            out["t"] = (mean / math.sqrt(var / n) if var > 0
                        else (99.0 if mean > 0 else -99.0 if mean < 0 else 0.0))
        return out

    def _verdict(s: dict[str, Any]) -> tuple[str, str]:
        if s["max_dd_r"] <= DD_HARD_R:
            return "RETIRE", "dd"
        if EARLY_FADE_N <= s["n"] < N_MIN_VERDICT and (
                int(s.get("wins", 0)) == 0 or s["exp_r"] <= -EARLY_FADE_R):
            return "FADE", "early"
        if s["n"] < N_MIN_VERDICT:
            return "HEALTHY", "n"
        if s["t"] <= -T_PROMOTE:
            return "RETIRE", "t"
        if s["t"] <= 0.0 or s["exp_r"] < 0.0:
            return "FADE", "t"
        return "HEALTHY", ""

    def _row_time(row: dict[str, Any]) -> datetime | None:
        for k in ("time", "close_time", "exit_time", "closed_at", "entry_time", "opened_at"):
            v = row.get(k)
            if isinstance(v, str) and v.strip():
                try:
                    ts = datetime.fromisoformat(v.replace("Z", "+00:00"))
                except ValueError:
                    continue
                return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        return None

    def _row_r(row: dict[str, Any]) -> float | None:
        for k in ("r_multiple", "r", "R"):
            v = row.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        return None

try:
    from libs.ops.live_ledger_view import ledger_path as _ledger_path
    LEDGER = _ledger_path(BASE / "data" / "live_ledger.jsonl")
except Exception:  # pragma: no cover
    pass

# ---- declared constants (never searched) -------------------------------------------------------
CUSUM_K = 0.5
CUSUM_H = 4.0
CERT_SD_R = 1.0
SELF_ANCHOR_N = 30
SELF_ANCHOR_SD_FLOOR = 0.1
DD_EVENT_R = 3.0
FA_HORIZON = 20
MIN_EVENTS = 5
DETECTORS = ("CURRENT", "CUSUM", "FEATURE_DRIFT")
SEED_CASES = {"USDNOK_carry": ("usdnok", "carry"), "AUDCHF": ("audchf",), "EURCHF": ("eurchf",)}
#: A ledger tag that names a sleeve (not a venue comment such as "[tp 4360.71]" or "#222 by #221").
_SLEEVE_ID = re.compile(r"^[a-z][a-z0-9_]+$")
UNMEASURED, COSTS, NOT_BINDING = "UNMEASURED", "COSTS", "NOT_BINDING"


def _read_json(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


# ---- series ------------------------------------------------------------------------------------
def _pairs(rows: Sequence[Mapping[str, Any]]) -> list[tuple[datetime, float]]:
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        ts, rv = _row_time(r), _row_r(r)
        if ts is None or rv is None or not math.isfinite(rv):
            continue
        out.append((ts, rv))
    out.sort(key=lambda p: p[0])
    return out


def shadow_series(dirs: Sequence[Path] = SHADOW_LEDGER_DIRS) -> list[dict[str, Any]]:
    """Every forward-clock ledger: `ledger_<cell>.json` lists (first directory wins per stem), and
    any dict-of-cells file whose values are row lists."""
    seen: dict[str, dict[str, Any]] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            stem = f.stem[len("ledger_"):]
            if stem in seen:
                continue
            doc = _read_json(f)
            groups: dict[str, list[Any]] = {}
            if isinstance(doc, list):
                groups[stem] = doc
            elif isinstance(doc, dict):
                groups = {str(k): v for k, v in doc.items() if isinstance(v, list)}
            for key, rows in groups.items():
                pts = _pairs(rows)
                if pts and key not in seen:
                    phases = {str(r.get("phase") or "") for r in rows if isinstance(r, dict)}
                    seen[key] = {"name": key, "source": f"shadow:{d.name}/{f.name}",
                                 "points": pts, "phases": sorted(p for p in phases if p)}
    return list(seen.values())


def roster_names(doc: Any) -> list[str]:
    sl = doc.get("sleeves", doc) if isinstance(doc, dict) else doc
    if isinstance(sl, dict):
        return [str(k) for k, v in sl.items() if isinstance(v, dict)]
    if isinstance(sl, list):
        return [str(r.get("name")) for r in sl if isinstance(r, dict) and r.get("name")]
    return []


def live_series(ledger: Path = LEDGER, roster: Sequence[str] = ()
                ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Per-sleeve live closes, joined to roster names by the venue's 27-char comment stem. Rows
    whose R was never measured are skipped exactly as decay_monitor skips them."""
    by_stem: dict[str, list[str]] = {}
    for n in roster:
        by_stem.setdefault(n[:LEDGER_NAME_MAX], []).append(n)
    groups: dict[str, list[dict[str, Any]]] = {}
    skipped = {"unreconstructible": 0, "unjoined": 0}
    try:
        lines = Path(ledger).read_text("utf-8").splitlines()
    except OSError:
        return [], {"why": f"no live ledger at {ledger}"}
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or not isinstance(r.get("r_multiple"), (int, float)):
            continue
        rq = r.get("risk_quote")
        if r.get("r_unreconstructible") is True or (isinstance(rq, (int, float)) and rq <= 0):
            skipped["unreconstructible"] += 1
            continue
        sl = str(r.get("sleeve") or "")
        names = by_stem.get(sl[:LEDGER_NAME_MAX]) or ([sl] if _SLEEVE_ID.match(sl) else [])
        if not names:
            skipped["unjoined"] += 1
            continue
        groups.setdefault(names[0], []).append(r)
    out = [{"name": n, "source": "live_ledger", "points": _pairs(rows), "phases": ["live"]}
           for n, rows in groups.items()]
    return [s for s in out if s["points"]], skipped


# ---- anchors -----------------------------------------------------------------------------------
def survivor_index(canon: Any) -> list[dict[str, Any]]:
    sv = canon.get("survivors") if isinstance(canon, dict) else None
    items = sv.values() if isinstance(sv, dict) else (sv if isinstance(sv, list) else [])
    out = []
    for s in items:
        if not isinstance(s, dict):
            continue
        ev = ((s.get("gates") or {}).get("expected_value") or {}).get("ev")
        spec = s.get("shadow_spec") or {}
        if not isinstance(ev, (int, float)) or not spec.get("symbol"):
            continue
        out.append({"cell": str(s.get("cell") or ""), "ev": float(ev),
                    "symbol": str(spec["symbol"]).upper(), "family": str(spec.get("family") or ""),
                    "selector": str(spec.get("selector") or "")})
    return out


def anchor_for(name: str, survivors: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Exact cell match first (selector token dropped), then a unique-or-pooled symbol x family x
    selector match. None means self-anchored."""
    nn = _norm(re.sub(r"^(external|qquant)\.", "", name))
    for s in survivors:
        sel = _norm(s["selector"])
        cand = nn.replace(f"_{sel}_", "_", 1) if sel else nn
        if _norm(s["cell"]) in (nn, cand):
            return {"basis": "certified_exact", "mu0": s["ev"], "cells": [s["cell"]]}
    m = [s for s in survivors
         if nn.startswith(s["symbol"].lower() + "_") and s["family"]
         and f"_{_norm(s['family'])}" in nn
         and (not s["selector"] or f"_{_norm(s['selector'])}" in nn
              or nn.endswith(_norm(s["family"])))]
    if not m:
        return None
    return {"basis": "certified_family" if len(m) == 1 else "certified_family_mean",
            "mu0": sum(s["ev"] for s in m) / len(m), "cells": [s["cell"] for s in m]}


# ---- detectors (causal) ------------------------------------------------------------------------
def current_states(points: Sequence[tuple[datetime, float]]) -> list[bool]:
    """In-alarm (FADE or RETIRE) after each trade, judged on the trailing window that trade sees."""
    out = []
    for j, (tj, _) in enumerate(points):
        lo = tj - timedelta(days=TRAIL_DAYS)
        win = [r for (t, r) in points[max(0, j - 10 * TRAIL_MAX_TRADES):j + 1] if t >= lo]
        v, _why = _verdict(_stats(win[-TRAIL_MAX_TRADES:]))
        out.append(v in ("FADE", "RETIRE"))
    return out


def cusum_alarms(rs: Sequence[float], mu0: float, sd: float, start: int = 0,
                 k: float = CUSUM_K, h: float = CUSUM_H) -> list[bool]:
    """Page's lower CUSUM; True at each trade where S crosses h (then S resets)."""
    out, s = [], 0.0
    sd = sd if sd > 0 else CERT_SD_R
    for j, x in enumerate(rs):
        if j < start:
            out.append(False)
            continue
        s = max(0.0, s + (mu0 - x) / sd - k)
        if s > h:
            out.append(True)
            s = 0.0
        else:
            out.append(False)
    return out


def drift_alarms(points: Sequence[tuple[datetime, float]],
                 episodes: Sequence[Mapping[str, Any]]) -> list[bool] | None:
    flags = []
    for e in episodes or []:
        try:
            ts = datetime.fromisoformat(str(e.get("first_flag_at")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        flags.append(ts if ts.tzinfo else ts.replace(tzinfo=UTC))
    if not points:
        return None
    t0, t1 = points[0][0], points[-1][0]
    flags = [f for f in flags if t0 <= f <= t1]
    if not flags:
        return None
    out = [False] * len(points)
    for f in flags:
        j = max(i for i, (t, _) in enumerate(points) if t <= f)
        out[j] = True
    return out


# ---- scoring -----------------------------------------------------------------------------------
def drawdown_events(rs: Sequence[float], start: int = 0,
                    bar: float = DD_EVENT_R) -> list[dict[str, Any]]:
    """Peak-to-trough falls of `bar` R or worse, on cumulative R from `start`."""
    events: list[dict[str, Any]] = []
    cum, peak, pk_i = 0.0, 0.0, start - 1          # the pre-series level is a peak at 0
    trough, tr_i, cums = 0.0, None, {start - 1: 0.0}
    for j in range(start, len(rs)):
        cum += rs[j]
        cums[j] = cum
        if cum > peak:
            if tr_i is not None and peak - trough >= bar:
                events.append({"peak_i": pk_i, "trough_i": tr_i,
                               "depth_r": round(peak - trough, 4)})
            peak, pk_i, trough, tr_i = cum, j, cum, None
        elif tr_i is None or cum < trough:
            trough, tr_i = cum, j
    if tr_i is not None and peak - trough >= bar:
        events.append({"peak_i": pk_i, "trough_i": tr_i, "depth_r": round(peak - trough, 4),
                       "open": True})
    for e in events:
        e["peak_cum"] = cums[e["peak_i"]]
    return events


def _onsets(state: Sequence[bool]) -> list[int]:
    return [j for j, v in enumerate(state) if v and (j == 0 or not state[j - 1])]


def score(rs: Sequence[float], alarm_state: Sequence[bool], onsets: Sequence[int],
          start: int = 0) -> dict[str, Any]:
    """Score one detector on one series. `alarm_state[j]` True = the detector is in alarm after
    trade j; `onsets` are the alarms counted for false-alarm purposes."""
    events = drawdown_events(rs, start)
    cum = [0.0] * len(rs)
    c = 0.0
    for j in range(len(rs)):
        c += rs[j] if j >= start else 0.0
        cum[j] = c
    ev_rows, leads, misses = [], [], 0
    for e in events:
        lo = max(e["peak_i"], start)
        hit = next((j for j in range(lo, e["trough_i"]) if alarm_state[j]), None)
        if hit is None:
            misses += 1
            ev_rows.append({**e, "alarm_i": None, "lead_r": None, "miss": True})
        else:
            lead = round(e["peak_cum"] - cum[hit], 4)
            leads.append(lead)
            ev_rows.append({**e, "alarm_i": hit, "lead_r": lead, "miss": False})
    false_alarms, pending, cost = 0, 0, 0.0
    for j in onsets:
        if j < start:
            continue
        if any(e["peak_i"] <= j <= e["trough_i"] for e in events):
            continue
        fut = rs[j + 1:j + 1 + FA_HORIZON]
        c, pk, dd = 0.0, 0.0, 0.0
        for x in fut:
            c += x
            pk = max(pk, c)
            dd = max(dd, pk - c)
        if dd >= DD_EVENT_R:
            continue
        if len(fut) < FA_HORIZON:
            pending += 1
            continue
        false_alarms += 1
        cost += FADE_FACTOR * max(0.0, sum(fut))
    return {"n_events": len(events), "misses": misses, "leads_r": leads,
            "false_alarms": false_alarms, "pending_alarms": pending,
            "false_alarm_cost_r": round(cost, 4), "n_alarms": sum(1 for j in onsets if j >= start),
            "events": ev_rows}


def _seed(name: str) -> str | None:
    nn = name.lower()
    for label, toks in SEED_CASES.items():
        if all(t in nn for t in toks):
            return label
    return None


def evaluate_series(s: Mapping[str, Any], survivors: Sequence[Mapping[str, Any]],
                    drift_state: Mapping[str, Any] | None) -> dict[str, Any]:
    pts = list(s["points"])
    rs = [r for _, r in pts]
    anc = anchor_for(str(s["name"]), survivors)
    row: dict[str, Any] = {"name": s["name"], "source": s["source"], "n": len(rs),
                           "phases": s.get("phases", []), "seed_case": _seed(str(s["name"])),
                           "first_at": pts[0][0].isoformat() if pts else None,
                           "last_at": pts[-1][0].isoformat() if pts else None}
    if anc:
        mu0, sd, start = anc["mu0"], CERT_SD_R, 0
        row["anchor"] = {**anc, "mu0": round(mu0, 4), "sd": sd,
                         "note": "certified ev; sd is the declared 1R unit "
                                 "(the canon carries no per-trade dispersion)"}
    else:
        if len(rs) <= SELF_ANCHOR_N:
            row["anchor"] = {"basis": "self", "note": f"no canon match and n <= {SELF_ANCHOR_N}: "
                                                      f"too short to self-anchor"}
            row["scored"] = False
            # Not in the aggregates (no anchor for CUSUM, so no like-for-like comparison), but the
            # CURRENT rule needs no anchor: its replay is published so a seed case is never silent.
            cur0 = current_states(pts)
            diag = score(rs, cur0, _onsets(cur0), 0)
            row["diagnostic_current"] = {
                **{k: v for k, v in diag.items() if k != "leads_r"},
                "note": "CURRENT replayed from trade 1 on an unanchored series; excluded from the "
                        "detector aggregates and the promotion verdict"}
            return row
        head = rs[:SELF_ANCHOR_N]
        mu0 = statistics.fmean(head)
        sd = max(statistics.stdev(head), SELF_ANCHOR_SD_FLOOR)
        start = SELF_ANCHOR_N
        row["anchor"] = {"basis": "self", "mu0": round(mu0, 4), "sd": round(sd, 4),
                         "note": f"no canon match: self-anchored on the first {SELF_ANCHOR_N} "
                                 f"trades, scored only after them"}
    row["scored"], row["scored_from"] = True, start
    cur = current_states(pts)
    cus = cusum_alarms(rs, mu0, sd, start)
    det: dict[str, Any] = {"CURRENT": score(rs, cur, _onsets(cur), start),
                           "CUSUM": score(rs, cus, [j for j, v in enumerate(cus) if v], start)}
    eps = ((drift_state or {}).get(str(s["name"])) or {}).get("episodes") if drift_state else None
    fd = drift_alarms(pts, eps or [])
    det["FEATURE_DRIFT"] = (score(rs, fd, [j for j, v in enumerate(fd) if v], start)
                            if fd is not None else {"verdict": UNMEASURED})
    row["detectors"] = det
    return row


def aggregate(rows: Sequence[Mapping[str, Any]], det: str) -> dict[str, Any]:
    sc = [r["detectors"][det] for r in rows
          if r.get("scored") and "n_events" in r["detectors"].get(det, {})]
    if not sc:
        return {"verdict": UNMEASURED, "n_series": 0,
                "why": "no series overlaps this detector's alarms"}
    leads = [x for s in sc for x in s["leads_r"]]
    return {"n_series": len(sc), "n_events": sum(s["n_events"] for s in sc),
            "misses": sum(s["misses"] for s in sc),
            "median_lead_r": round(statistics.median(leads), 4) if leads else None,
            "mean_lead_r": round(statistics.fmean(leads), 4) if leads else None,
            "n_alarms": sum(s["n_alarms"] for s in sc),
            "false_alarms": sum(s["false_alarms"] for s in sc),
            "pending_alarms": sum(s["pending_alarms"] for s in sc),
            "false_alarm_cost_r": round(sum(s["false_alarm_cost_r"] for s in sc), 4)}


def promotion_verdict(cur: Mapping[str, Any], new: Mapping[str, Any],
                      name: str = "CUSUM") -> dict[str, Any]:
    n_ev = int(cur.get("n_events") or 0)
    if n_ev < MIN_EVENTS or cur.get("verdict") == UNMEASURED or new.get("verdict") == UNMEASURED:
        return {"verdict": UNMEASURED,
                "why": f"{n_ev} drawdown event(s) < {MIN_EVENTS}: too few to judge a detector"}
    reasons = []
    if new["misses"] > cur["misses"]:
        reasons.append(f"misses {new['misses']} > CURRENT {cur['misses']}")
    nl, cl = new.get("median_lead_r"), cur.get("median_lead_r")
    if nl is None or (cl is not None and not nl < cl):
        reasons.append(f"median lead {nl}R not better than CURRENT {cl}R")
    if new["false_alarm_cost_r"] > cur["false_alarm_cost_r"]:
        reasons.append(f"false-alarm cost {new['false_alarm_cost_r']}R > CURRENT "
                       f"{cur['false_alarm_cost_r']}R")
    if reasons:
        return {"verdict": "NOT_PROMOTABLE", "why": f"{name} vs CURRENT: " + "; ".join(reasons)}
    return {"verdict": "PROMOTABLE",
            "why": f"{name} misses <= CURRENT, earlier median lead ({nl}R vs {cl}R), and costs "
                   f"no more in false alarms; acting on it still needs a reviewed "
                   f"decay_monitor change"}


def missed_growth_lines(agg: Mapping[str, Mapping[str, Any]], at: str) -> list[dict[str, Any]]:
    lines = []
    for det, a in agg.items():
        if a.get("verdict") == UNMEASURED:
            lines.append({"rail": f"decay_accuracy.{det}", "verdict": UNMEASURED, "value": None,
                          "unit": "R", "at": at, "why": a.get("why")})
            continue
        v = float(a["false_alarm_cost_r"])
        lines.append({"rail": f"decay_accuracy.{det}", "verdict": COSTS if v > 0 else NOT_BINDING,
                      "value": round(v, 4), "unit": "R", "at": at,
                      "false_alarms": a["false_alarms"],
                      "why": f"{a['false_alarms']} false alarm(s), each billed {FADE_FACTOR} x the "
                             f"positive net R of the {FA_HORIZON} trades after it (a FADE at half "
                             f"risk forgoes that much)"})
    return lines


def _event_row(e: Mapping[str, Any], dets: Mapping[str, Any]) -> dict[str, Any]:
    """One drawdown event with every scored detector's lead R beside it (None = missed)."""
    out: dict[str, Any] = {k: e[k] for k in ("peak_i", "trough_i", "depth_r")}
    for d in DETECTORS:
        evs = (dets.get(d) or {}).get("events")
        if evs is not None:
            out[f"{d}_lead_r"] = next((y["lead_r"] for y in evs if y["peak_i"] == e["peak_i"]),
                                      None)
    return out


def run(*, now: datetime | None = None, shadow: Sequence[dict[str, Any]] | None = None,
        live: Sequence[dict[str, Any]] | None = None, canon: Any = None, drift_state: Any = None,
        report_path: Path | None = REPORT) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    at = now.isoformat(timespec="seconds")
    live_skip: dict[str, Any] = {}
    if shadow is None:
        shadow = shadow_series(SHADOW_LEDGER_DIRS)
    if live is None:
        live, live_skip = live_series(LEDGER, roster_names(_read_json(SLEEVES_FILE, {})))
    if canon is None:
        canon = _read_json(CANON, {})
    drift_note = None
    if drift_state is None:
        drift_state = _read_json(DRIFT_STATE, None)
        if not isinstance(drift_state, dict):
            drift_note = (f"no {DRIFT_STATE.name} on this host (research/feature_drift.py, branch "
                          f"claude/feature-drift-monitor, has not written one): FEATURE_DRIFT "
                          f"UNMEASURED")
            drift_state = None
    survivors = survivor_index(canon)
    rows = [evaluate_series(s, survivors, drift_state) for s in [*shadow, *live]]
    agg = {d: aggregate(rows, d) for d in DETECTORS}
    if drift_note and agg["FEATURE_DRIFT"].get("verdict") == UNMEASURED:
        agg["FEATURE_DRIFT"]["why"] = drift_note
    per_series = []
    for r in rows:
        slim = {k: v for k, v in r.items() if k != "detectors"}
        if r.get("detectors"):
            slim["detectors"] = {d: ({k: v for k, v in x.items() if k not in ("events", "leads_r")}
                                     if "n_events" in x else x)
                                 for d, x in r["detectors"].items()}
            slim["events"] = [_event_row(e, r["detectors"])
                              for e in r["detectors"]["CURRENT"]["events"]]
        per_series.append(slim)
    doc = {"generated_at": at, "organ": "research/decay_accuracy.py",
           "acts_on": "nothing -- a report; decay_monitor alone moves a sleeve",
           "current_rule": IMPORT_NOTE,
           "constants": {"CUSUM_K": CUSUM_K, "CUSUM_H": CUSUM_H, "CERT_SD_R": CERT_SD_R,
                         "SELF_ANCHOR_N": SELF_ANCHOR_N, "DD_EVENT_R": DD_EVENT_R,
                         "FA_HORIZON": FA_HORIZON, "MIN_EVENTS": MIN_EVENTS,
                         "FADE_FACTOR": FADE_FACTOR, "N_MIN_VERDICT": N_MIN_VERDICT,
                         "EARLY_FADE_N": EARLY_FADE_N, "EARLY_FADE_R": EARLY_FADE_R,
                         "DD_HARD_R": DD_HARD_R, "TRAIL_MAX_TRADES": TRAIL_MAX_TRADES,
                         "TRAIL_DAYS": TRAIL_DAYS, "T_PROMOTE": T_PROMOTE},
           "inputs": {"shadow_series": len(shadow), "live_series": len(live),
                      "live_rows_skipped": live_skip, "canon_survivors": len(survivors),
                      "series_scored": sum(1 for r in rows if r.get("scored")),
                      "certified_anchor": sum(1 for r in rows if r.get("scored")
                                              and r["anchor"]["basis"] != "self"),
                      "self_anchor": sum(1 for r in rows if r.get("scored")
                                         and r["anchor"]["basis"] == "self")},
           "detectors": agg,
           "promotion": {"CUSUM": promotion_verdict(agg["CURRENT"], agg["CUSUM"]),
                         "FEATURE_DRIFT": promotion_verdict(agg["CURRENT"], agg["FEATURE_DRIFT"],
                                                            "FEATURE_DRIFT")},
           "seed_cases": [{k: r.get(k) for k in ("name", "source", "n", "seed_case", "scored")}
                          | {"anchor": (r.get("anchor") or {}).get("basis"),
                             "events": len(r.get("events") or []),
                             "detectors": r.get("detectors"),
                             "diagnostic_current": r.get("diagnostic_current")}
                          for r in per_series if r.get("seed_case")],
           "missed_growth": missed_growth_lines(agg, at),
           "missed_growth_note": ("published on this report in organ_published_lines' shape; the "
                                  "carry line in missed_growth.py lands after PR #540"),
           "series": per_series}
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = report_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8")
        tmp.replace(report_path)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.parse_args(argv)
    doc = run()
    d = doc["detectors"]
    print(f"decay_accuracy: {doc['inputs']['series_scored']} series scored; "
          + "; ".join(f"{k} events={v.get('n_events')} misses={v.get('misses')} "
                      f"lead={v.get('median_lead_r')} fa={v.get('false_alarms')} "
                      f"cost={v.get('false_alarm_cost_r')}" for k, v in d.items())
          + f"; CUSUM {doc['promotion']['CUSUM']['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
