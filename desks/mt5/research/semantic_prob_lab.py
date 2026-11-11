"""LAB L: TYPED, CALIBRATED SEMANTIC PROBABILITIES FROM THE FREE MODEL CHAIN. Our own Jev.

    py -3 desks/mt5/research/semantic_prob_lab.py        # argless: one pass, rate-limited inside

WHAT IT REPLACES. The 2026-10-06 mandate named an external typed-probability API ("Jev") for
three jobs: Lab L semantic cells, semantic regimes, and AI tool calls over market state. It was
never wired (no key), and on 2026-11-11 the principal dropped it: "replicated without it". This
organ is the replication, on the free seat, with every number checked by Python.

THE LOOP, ONE READING EVERY MIN_INTERVAL_H:
  1. TEXT STATE. The newest text the desk's own intake holds (titles, claims, summaries under
     `data/intelligence/**`, written inside LOOKBACK_H), plus a MARKET STATE block Python computes
     from the H1 bars (the "get market state" tool of the mandate: the model is handed numbers,
     never asked to recall them).
  2. TYPED PROBABILITIES. The seat is asked for one JSON object: for every TOPIC, a probability
     over that topic's exclusive OUTCOMES for the next HORIZON_H hours.
  3. PYTHON CHECKS IT. Exact keys, finite numbers in [0, 1], a sum within SUM_TOL of 1
     (renormalised), else that topic is REJECTED for this reading and says why. A reply that does
     not parse is a rejected reading. Nothing unchecked reaches a file anyone reads.
  4. CALIBRATION, POINT IN TIME. Each topic's past readings are SETTLED against the bars once
     their horizon has passed. A one-parameter shrink towards the settled base rate
     (p_cal = w p + (1 - w) base), with w fitted on settled log loss, is applied AT READING TIME
     and stored on the row. A later fit never rewrites an earlier row, so the published series
     carries only what was knowable when each value was stamped.
  5. LAB L CELLS. Each directional topic publishes `<topic>__tilt` = p(up) - p(down) into the
     lake series `semantic_prob`, stamped `available_time`. Once that series holds
     MIN_OBSERVATIONS rows spanning MIN_SPAN_DAYS, one `exogenous_conditioner` cell per
     (topic, symbol), with the sign the topic implies, is enqueued in the canonical registry
     ONCE. The judge runs them through the same ten gates as everything else; that family lags
     the series a further publication day. The cells are LLM-derived through their source:
     `mt5desk.live_policy.LLM_DERIVED_SOURCES` keeps a certified one in forward shadow, never LIVE.

WHAT IT MAY NOT DO. LLMs propose only: nothing here sizes, promotes, vetoes or touches an order.
The probabilities are research features. The free tier is the default (llm_seat's own policy),
and the organ leaves FREE_RESERVE requests of the day's allowance for every other organ.

ARTIFACTS
  desks/mt5/data/semantic_lab/readings.jsonl     one row per reading (raw, checked, calibrated)
  desks/mt5/data/lake/series/semantic_prob.parquet   the PIT series the cells condition on
  desks/mt5/reports/SEMANTIC_PROB_LAB.json       skill per topic (Brier vs base rate), rejects,
                                                 cells minted -- the hourly report
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE = BASE / "data" / "semantic_lab"
READINGS = STATE / "readings.jsonl"
MINTED = STATE / "minted.json"
SERIES_ID = "semantic_prob"
SERIES = BASE / "data" / "lake" / "series" / f"{SERIES_ID}.parquet"
REPORT = BASE / "reports" / "SEMANTIC_PROB_LAB.json"
BARS_DIR = BASE / "data" / "universe"
INTEL_ROOTS = (BASE / "data" / "intelligence", ROOT / "data" / "intelligence")

MIN_INTERVAL_H = 6.0       # one reading per 6h: 4 free requests a day
HORIZON_H = 24             # what each probability is about
LOOKBACK_H = 24            # text written inside this window is the state
MAX_ITEMS = 60             # text items handed to the model
ITEM_CHARS = 240
MIN_ITEMS = 5              # fewer is UNMEASURED: no call is spent on an empty room
SUM_TOL = 0.05
FREE_RESERVE = 50          # requests left for every other organ
MIN_SETTLED_TO_CALIBRATE = 20
MIN_OBSERVATIONS = 30      # family_exogenous_conditioner's own floor; cells wait for it
#: Calendar span the published series must cover before a cell is minted. Thirty rows at the
#: six-hour interval is under eight days, and a cell minted then is a trial the judge counts in
#: its multiplicity charge while having almost nothing to judge it on (Auditor, #997).
MIN_SPAN_DAYS = 60
#: Bars sit on broker time under a UTC label (+2/+3). A reading is settled from the first bar at
#: least this far after its stamp, so the offset can never put a bar before the reading.
CLOCK_PAD_H = 3

#: topic -> (reference symbol, invert, outcomes [up, down, flat], cells {symbol: side_when_high}).
#: `invert` means the topic's asset rises when the reference symbol falls (USD vs EURUSD).
TOPICS: dict[str, dict[str, Any]] = {
    "usd": {"ref": "EURUSD", "invert": True,
            "question": "the US dollar broadly, against the major currencies",
            "cells": {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1, "USDCHF": 1,
                      "USDCAD": 1}},
    "gold": {"ref": "XAUUSD", "invert": False, "question": "spot gold (XAUUSD)",
             "cells": {"XAUUSD": 1, "XAGUSD": 1}},
    "jpy": {"ref": "USDJPY", "invert": True,
            "question": "the Japanese yen (safe-haven demand), against the US dollar",
            "cells": {"USDJPY": -1, "EURJPY": -1, "AUDJPY": -1}},
    "aud": {"ref": "AUDUSD", "invert": False,
            "question": "the Australian dollar (risk appetite and commodities), against USD",
            "cells": {"AUDUSD": 1, "NZDUSD": 1}},
}
OUTCOMES = ("up", "down", "flat")
TEXT_KEYS = ("title", "headline", "claim", "summary", "text", "description", "mechanism")
_UNMEASURED = "UNMEASURED"


# ------------------------------------------------------------------ small io
def _now() -> datetime:
    return datetime.now(UTC)


def _parse(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, p)


def readings(path: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = (path or READINGS).read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and _parse(r.get("available_time")):
            out.append(r)
    return out


# ------------------------------------------------------------------ 1. state
def text_state(now: datetime, roots: tuple[Path, ...] = INTEL_ROOTS) -> list[str]:
    """Newest distinct text items the desk's intake wrote inside LOOKBACK_H. Never raises."""
    cutoff = now.timestamp() - LOOKBACK_H * 3600
    files: list[tuple[float, Path]] = []
    for r in roots:
        if not r.is_dir():
            continue
        for f in r.rglob("*.json*"):
            try:
                m = f.stat().st_mtime
            except OSError:
                continue
            if cutoff <= m <= now.timestamp() + 60 and f.suffix in (".json", ".jsonl"):
                files.append((m, f))
    seen: set[str] = set()
    items: list[str] = []

    def take(obj: Any, depth: int = 0) -> None:
        if len(items) >= MAX_ITEMS or depth > 4:
            return
        if isinstance(obj, dict):
            for k in TEXT_KEYS:
                v = obj.get(k)
                if isinstance(v, str) and len(v.strip()) >= 20:
                    t = " ".join(v.split())[:ITEM_CHARS]
                    if t.lower() not in seen:
                        seen.add(t.lower())
                        items.append(t)
                    break
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    take(v, depth + 1)
        elif isinstance(obj, list):
            for v in obj[:200]:
                take(v, depth + 1)

    for _m, f in sorted(files, reverse=True):
        if len(items) >= MAX_ITEMS:
            break
        try:
            raw = f.read_text("utf-8", errors="ignore")[:2_000_000]
        except OSError:
            continue
        if f.suffix == ".jsonl":
            for ln in raw.splitlines()[-200:]:
                try:
                    take(json.loads(ln))
                except ValueError:
                    continue
        else:
            try:
                take(json.loads(raw))
            except ValueError:
                continue
    return items


def _bars(sym: str, bars_dir: Path) -> Any:
    try:
        import pandas as pd
        d = pd.read_parquet(bars_dir / f"{sym}_H1.parquet", columns=["close"])
        d.index = pd.DatetimeIndex(d.index)
        if d.index.tz is None:
            d.index = d.index.tz_localize("UTC")
        return d["close"].astype(float).dropna().sort_index()
    except Exception:
        return None


def market_state(now: datetime, bars_dir: Path = BARS_DIR) -> dict[str, Any]:
    """Python-computed returns the model is handed (it is never asked to recall a price)."""
    import pandas as pd
    out: dict[str, Any] = {}
    for t in TOPICS.values():
        s = _bars(t["ref"], bars_dir)
        if s is None or s.empty:
            continue
        s = s[s.index <= pd.Timestamp(now)]
        if len(s) < 130:
            continue
        last = float(s.iloc[-1])
        out[t["ref"]] = {"last_bar": str(s.index[-1]),
                         "ret_24h_pct": round(100 * math.log(last / float(s.iloc[-25])), 3),
                         "ret_5d_pct": round(100 * math.log(last / float(s.iloc[-121])), 3)}
    return out


# ------------------------------------------------------------------ 2-3. ask and check
def prompt(items: list[str], mkt: dict[str, Any], now: datetime) -> tuple[str, str]:
    system = ("You are a calibrated forecaster. You output probabilities, never advice. Use "
              "only the evidence given; when it says little, stay near the base rate. Reply "
              "with ONE JSON object and nothing else.")
    lines = [f"As of {now.isoformat(timespec='minutes')} UTC. Horizon: the next {HORIZON_H} "
             "hours.", "", "MARKET STATE (computed from bars):",
             json.dumps(mkt, sort_keys=True), "", "RECENT TEXT (newest first):"]
    lines += [f"[{i}] {t}" for i, t in enumerate(items)]
    lines += ["", "For each topic give P(up), P(down), P(flat) for the topic's asset over the "
              "horizon (flat = a move too small to matter). Each topic's three numbers sum to 1.",
              "Topics:"]
    lines += [f'- "{k}": {v["question"]}' for k, v in TOPICS.items()]
    lines += ["", 'Format: {"usd": {"up": 0.3, "down": 0.3, "flat": 0.4}, "gold": {...}, ...}']
    return system, "\n".join(lines)


def _object(text: str) -> dict[str, Any] | None:
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        doc = json.loads(t[i:j + 1])
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def check(doc: dict[str, Any] | None) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """(accepted topic -> outcome -> p, rejected topic -> why). Pure; the schema's only judge."""
    ok: dict[str, dict[str, float]] = {}
    bad: dict[str, str] = {}
    if not isinstance(doc, dict):
        return ok, dict.fromkeys(TOPICS, "reply was not a JSON object")
    low = {str(k).strip().lower(): v for k, v in doc.items()}
    for topic in TOPICS:
        v = low.get(topic)
        if not isinstance(v, dict):
            bad[topic] = "missing or not an object"
            continue
        vv = {str(k).strip().lower(): x for k, x in v.items()}
        if set(vv) != set(OUTCOMES):
            bad[topic] = f"outcomes {sorted(vv)} != {list(OUTCOMES)}"
            continue
        try:
            ps = {o: float(vv[o]) for o in OUTCOMES}
        except (TypeError, ValueError):
            bad[topic] = "a probability is not a number"
            continue
        if not all(math.isfinite(p) and 0.0 <= p <= 1.0 for p in ps.values()):
            bad[topic] = "a probability is outside [0, 1]"
            continue
        tot = sum(ps.values())
        if abs(tot - 1.0) > SUM_TOL:
            bad[topic] = f"probabilities sum to {tot:.3f}"
            continue
        ok[topic] = {o: p / tot for o, p in ps.items()}
    return ok, bad


# ------------------------------------------------------------------ 4. settle and calibrate
def settle(rows: list[dict[str, Any]], now: datetime,
           bars_dir: Path | None = None) -> dict[str, list[tuple[dict[str, float], str]]]:
    """Per topic: (raw probabilities, realised outcome) for every reading whose horizon passed.

    The flat band is a quarter of the median absolute 24h move over the 60 days BEFORE the
    reading, so what counts as "flat" is fixed before the outcome exists."""
    import numpy as np
    import pandas as pd
    bars_dir = bars_dir or BARS_DIR
    out: dict[str, list[tuple[dict[str, float], str]]] = {k: [] for k in TOPICS}
    cache: dict[str, Any] = {}
    for r in rows:
        at = _parse(r.get("available_time"))
        if at is None or at + timedelta(hours=HORIZON_H + CLOCK_PAD_H) > now:
            continue
        for topic, ps in (r.get("raw") or {}).items():
            spec = TOPICS.get(topic)
            if spec is None or not isinstance(ps, dict):
                continue
            s = cache.setdefault(spec["ref"], _bars(spec["ref"], bars_dir))
            if s is None or s.empty:
                continue
            t0 = pd.Timestamp(at + timedelta(hours=CLOCK_PAD_H))
            t1 = t0 + pd.Timedelta(hours=HORIZON_H)
            a, b = s[s.index >= t0], s[s.index >= t1]
            hist = s[(s.index < t0) & (s.index >= t0 - pd.Timedelta(days=60))]
            if a.empty or b.empty or len(hist) < 48:
                continue
            ret = math.log(float(b.iloc[0]) / float(a.iloc[0]))
            moves = np.abs(np.log(hist.to_numpy()[24:] / hist.to_numpy()[:-24]))
            band = 0.25 * float(np.median(moves)) if len(moves) else 0.0
            ret = -ret if spec["invert"] else ret
            o = "flat" if abs(ret) <= band else ("up" if ret > 0 else "down")
            out[topic].append(({k: float(ps.get(k, 0.0)) for k in OUTCOMES}, o))
    return out


def _base(pairs: list[tuple[dict[str, float], str]]) -> dict[str, float]:
    n = len(pairs)
    return {o: (sum(1 for _p, y in pairs if y == o) + 1) / (n + len(OUTCOMES)) for o in OUTCOMES}


def _logloss(pairs: list[tuple[dict[str, float], str]], w: float, base: dict[str, float]) -> float:
    eps = 1e-6
    return -sum(math.log(max(eps, w * p[y] + (1 - w) * base[y])) for p, y in pairs) / len(pairs)


def calibration(pairs: list[tuple[dict[str, float], str]]) -> dict[str, Any]:
    """Shrink weight w on settled log loss (w=1: trust the model; w=0: base rate)."""
    if len(pairs) < MIN_SETTLED_TO_CALIBRATE:
        return {"status": _UNMEASURED, "settled": len(pairs), "w": 1.0, "base": _base(pairs)}
    base = _base(pairs)
    grid = [i / 20 for i in range(21)]
    w = min(grid, key=lambda g: _logloss(pairs, g, base))
    brier = sum(sum((p[o] - (1.0 if y == o else 0.0)) ** 2 for o in OUTCOMES)
                for p, y in pairs) / len(pairs)
    brier_base = sum(sum((base[o] - (1.0 if y == o else 0.0)) ** 2 for o in OUTCOMES)
                     for _p, y in pairs) / len(pairs)
    return {"status": "MEASURED", "settled": len(pairs), "w": w, "base": base,
            "brier": round(brier, 4), "brier_base_rate": round(brier_base, 4),
            "skill": round(1 - brier / brier_base, 4) if brier_base else None,
            "logloss_model": round(_logloss(pairs, 1.0, base), 4),
            "logloss_calibrated": round(_logloss(pairs, w, base), 4)}


def calibrate(raw: dict[str, dict[str, float]],
              cal: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for topic, ps in raw.items():
        c = cal.get(topic) or {}
        w = float(c.get("w", 1.0))
        base = c.get("base") or {o: 1 / len(OUTCOMES) for o in OUTCOMES}
        out[topic] = {o: round(w * ps[o] + (1 - w) * float(base[o]), 6) for o in OUTCOMES}
    return out


# ------------------------------------------------------------------ 5. series and cells
def write_series(rows: list[dict[str, Any]], path: Path | None = None) -> int:
    import pandas as pd
    path = path or SERIES
    recs = []
    for r in rows:
        cal = r.get("calibrated") or {}
        if not cal:
            continue
        rec: dict[str, Any] = {"available_time": r["available_time"], "source_id": SERIES_ID}
        for topic, ps in cal.items():
            for o in OUTCOMES:
                rec[f"{topic}__{o}"] = ps.get(o)
            rec[f"{topic}__tilt"] = ps.get("up", 0.0) - ps.get("down", 0.0)
        recs.append(rec)
    if not recs:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    pd.DataFrame(recs).to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return len(recs)


def series_span_days(path: Path | None = None) -> float:
    """Days between the first and last `available_time` of the published series; 0 if absent."""
    import pandas as pd
    try:
        stamps = pd.to_datetime(pd.read_parquet(path or SERIES)["available_time"], utc=True,
                                errors="coerce").dropna()
    except Exception:
        return 0.0
    if stamps.empty:
        return 0.0
    return float((stamps.max() - stamps.min()) / pd.Timedelta(days=1))


def mint_cells(n_rows: int, span_days: float, *, minted_path: Path | None = None,
               enqueue: Any = None) -> dict[str, Any]:
    """One exogenous_conditioner cell per (topic, symbol), once, after MIN_OBSERVATIONS rows
    spanning MIN_SPAN_DAYS.

    THE CELLS ARE LLM-DERIVED AND SAY SO THROUGH THEIR SOURCE. `params.source` is SERIES_ID,
    which `mt5desk.live_policy.LLM_DERIVED_SOURCES` names: the promoter retires and the gateway
    refuses any LIVE row carrying it, so a certified cell keeps its forward-shadow clock and never
    holds capital without the principal's word. The marker is the source and not an extra param
    because params are the family's keyword arguments.
    """
    if n_rows < MIN_OBSERVATIONS or span_days < MIN_SPAN_DAYS:
        return {"status": "WAITING", "rows": n_rows, "needed": MIN_OBSERVATIONS,
                "span_days": round(float(span_days), 2), "needed_days": MIN_SPAN_DAYS,
                "minted": 0}
    minted_path = minted_path or MINTED
    done = set(_read_json(minted_path, []) or [])
    if enqueue is None:
        from libs.moat.registry import enqueue_candidate as enqueue
    made, errors = 0, []
    for topic, spec in TOPICS.items():
        for sym, side in spec["cells"].items():
            key = f"{topic}|{sym}|{side}"
            if key in done:
                continue
            try:
                enqueue(family="exogenous_conditioner", symbol=sym,
                        params={"source": SERIES_ID, "signal": f"{topic}__tilt",
                                "transform": "level_z", "side_when_high": int(side)},
                        origin="semantic_prob_lab", chart="H1", horizon="H1",
                        mechanism=(f"Lab L: the free model chain's calibrated tilt for "
                                   f"{spec['question']} is at an extreme"),
                        source_id=SERIES_ID, generator="semantic_prob_lab",
                        department="information", transformation="semantic_probability",
                        required_data=[f"desks/mt5/data/lake/series/{SERIES_ID}.parquet"],
                        pit_status="STAMPED",
                        falsifier=(f"the level_z of {SERIES_ID}.{topic}__tilt has no measurable "
                                   f"relation to {sym} out of sample"))
                done.add(key)
                made += 1
            except Exception as exc:
                errors.append(f"{key}: {type(exc).__name__}: {str(exc)[:60]}")
    _write_json(minted_path, sorted(done))
    return {"status": "MINTED" if not errors else "PARTIAL", "rows": n_rows,
            "span_days": round(float(span_days), 2), "minted": made, "llm_derived": True,
            "total": len(done), "errors": errors[:5]}


# ------------------------------------------------------------------ the pass
def _ask(system: str, user: str) -> tuple[str, str | None, str]:
    from libs.ops import llm_seat
    if llm_seat.free_tier_only() and llm_seat.free_budget_left() <= FREE_RESERVE:
        return "", "free allowance at its reserve: skipped so other organs keep theirs", ""
    seat = llm_seat.primary_seat()
    text, err = llm_seat.chat(user, system=system, max_tokens=4000, temperature=0.2,
                              effort="medium", response_format=llm_seat.JSON_OBJECT)
    return text, err, getattr(seat, "name", "") if seat else ""


def run(now: datetime | None = None, *, ask: Any = None, bars_dir: Path | None = None,
        roots: tuple[Path, ...] | None = None, enqueue: Any = None) -> dict[str, Any]:
    t = now or _now()
    bars_dir = bars_dir or BARS_DIR
    roots = roots or INTEL_ROOTS
    rows = readings()
    stamps = [d for d in (_parse(r["available_time"]) for r in rows) if d is not None]
    last = max(stamps, default=None)
    settled = settle(rows, t, bars_dir)
    cal = {k: calibration(v) for k, v in settled.items()}
    reading: dict[str, Any] = {"status": "SKIPPED"}
    if last is not None and (t - last).total_seconds() < MIN_INTERVAL_H * 3600:
        reading["why"] = f"last reading {last.isoformat()} is inside {MIN_INTERVAL_H}h"
    else:
        items = text_state(t, roots)
        if len(items) < MIN_ITEMS:
            reading = {"status": _UNMEASURED,
                       "why": f"{len(items)} text item(s) inside {LOOKBACK_H}h: no call spent"}
        else:
            system, user = prompt(items, market_state(t, bars_dir), t)
            started = time.monotonic()
            text, err, seat = (ask or _ask)(system, user)
            ok, bad = check(_object(text) if text and not err else None)
            row = {"available_time": t.isoformat(timespec="seconds"), "seat": seat,
                   "items": len(items), "wall_s": round(time.monotonic() - started, 1),
                   "error": err, "raw": ok, "rejected": bad,
                   "calibrated": calibrate(ok, cal),
                   "calibration_w": {k: cal[k]["w"] for k in ok}}
            # A rejected reading is kept too: it holds the interval (no retry storm on a model
            # that will not follow the schema) and it is what the reject rate counts.
            READINGS.parent.mkdir(parents=True, exist_ok=True)
            with READINGS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            rows.append(row)
            reading = {"status": "READ" if ok else "REJECTED", "accepted": sorted(ok),
                       "rejected": bad, "error": err}
    n = write_series(rows)
    cells = mint_cells(n, series_span_days(), enqueue=enqueue)
    return {"generated_utc": t.isoformat(timespec="seconds"),
            "status": "MEASURED" if rows else _UNMEASURED,
            "this_pass": reading, "readings": len(rows), "series_rows": n,
            "topics": {k: {"ref": v["ref"], "cells": v["cells"], "calibration": cal[k]}
                       for k, v in TOPICS.items()},
            "reject_rate": _reject_rate(rows), "cells": cells,
            "authority": "research features only: no sizing, promotion, veto or order"}


def _reject_rate(rows: list[dict[str, Any]]) -> float | None:
    tot = sum(len(r.get("raw") or {}) + len(r.get("rejected") or {}) for r in rows)
    bad = sum(len(r.get("rejected") or {}) for r in rows)
    return round(bad / tot, 4) if tot else None


def main(argv: list[str] | None = None) -> int:
    doc = run()
    _write_json(REPORT, doc)
    print(f"semantic_prob_lab: {doc['this_pass']['status']}; {doc['readings']} reading(s), "
          f"cells {doc['cells']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
