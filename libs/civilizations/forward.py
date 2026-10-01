"""THE PUBLIC STRATEGY SURVIVORSHIP LABORATORY: QuantConnect Community Strategies forward-tracked.

    zuck, 2026-09-30: "snapshot today's published metrics -> record its claimed/OOS history ->
    revisit periodically -> measure subsequent performance -> classify decay/blow-up/stability ->
    infer phenotype -> generate mechanism hypothesis -> test independently on your MT5 universe.
    You shouldn't trust the leaderboard as evidence of transferable alpha; use it as a prior."

Each leaderboard / strategy-page vintage in the PIT store is parsed for the metrics the page
publishes (Sharpe, return, drawdown, OOS window) into a time series PER STRATEGY; the class is
decided on the series we recorded ourselves, never on the page's own claim:

    STABLE     latest Sharpe within 50% of the first recorded and > 0
    DECAY      latest Sharpe < 50% of first recorded, still > 0
    BLOW_UP    latest Sharpe <= 0 after a first recorded > 0.5, or drawdown doubled
    YOUNG      fewer than MIN_SNAPSHOTS spanning MIN_DAYS -- UNMEASURED, not stable
    UNPARSED   the page carried no metric this parser could read (named, never guessed)

The strategy's text (title/description) is independently routed through the ontology, so the
mechanism hypothesis goes to the gauntlet on MT5 bars whatever the leaderboard says.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

MIN_SNAPSHOTS = 3
MIN_DAYS = 14

_NUM = r"(-?\d+(?:\.\d+)?)"
_METRICS: dict[str, re.Pattern[str]] = {
    "sharpe": re.compile(r"sharpe(?:\s*ratio)?[^\d\-]{0,20}" + _NUM, re.I),
    "return_pct": re.compile(r"(?:return|cagr|annual return)[^\d\-]{0,20}" + _NUM + r"\s*%", re.I),
    "drawdown_pct": re.compile(r"drawdown[^\d\-]{0,20}" + _NUM + r"\s*%", re.I),
    "psr": re.compile(r"\bPSR\b[^\d\-]{0,10}" + _NUM, re.I),
}
_JSON_BLOB = re.compile(r"(\{[^{}]*\"(?:sharpe|Sharpe)[^{}]*\})")
_ID = re.compile(r"/strategies/(\d+)")


def parse_metrics(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for m in _JSON_BLOB.finditer(text or ""):
        try:
            blob = json.loads(m.group(1))
        except ValueError:
            continue
        for k, v in blob.items():
            if isinstance(v, (int, float)) and "sharpe" in k.lower():
                out.setdefault("sharpe", float(v))
    for k, rx in _METRICS.items():
        if k in out:
            continue
        hit = rx.search(text or "")
        if hit:
            try:
                out[k] = float(hit.group(1))
            except ValueError:
                continue
    return out


def strategy_id(uri: str, title: str = "") -> str:
    m = _ID.search(uri or "")
    return m.group(1) if m else (title or uri)[:120]


def snapshots(records: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """PIT records (every vintage) -> per-strategy metric series, oldest first."""
    series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        m = parse_metrics(f"{r.get('title') or ''}\n{r.get('body') or ''}")
        sid = strategy_id(str(r.get("source_uri") or ""), str(r.get("title") or ""))
        series[sid].append({"at": r.get("acquisition_time"), "metrics": m,
                            "record_id": r.get("record_id")})
    for v in series.values():
        v.sort(key=lambda x: str(x["at"]))
    return dict(series)


def _t(s: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def classify(series: list[dict[str, Any]]) -> dict[str, Any]:
    pts = [(p["at"], p["metrics"]) for p in series if p["metrics"].get("sharpe") is not None]
    if not pts:
        return {"class": "UNPARSED", "n": len(series),
                "why": "no Sharpe readable on any recorded vintage"}
    t0, t1 = _t(pts[0][0]), _t(pts[-1][0])
    days = (t1 - t0).days if t0 and t1 else 0
    s0, s1 = pts[0][1]["sharpe"], pts[-1][1]["sharpe"]
    base = {"n": len(pts), "days": days, "sharpe_first": s0, "sharpe_latest": s1}
    if len(pts) < MIN_SNAPSHOTS or days < MIN_DAYS:
        return {"class": "YOUNG", **base}
    dd0 = pts[0][1].get("drawdown_pct")
    dd1 = pts[-1][1].get("drawdown_pct")
    if (s0 > 0.5 and s1 <= 0) or (dd0 and dd1 and abs(dd1) >= 2 * abs(dd0)):
        return {"class": "BLOW_UP", **base}
    if s0 > 0 and s1 < 0.5 * s0:
        return {"class": "DECAY", **base}
    if s1 > 0:
        return {"class": "STABLE", **base}
    return {"class": "NEGATIVE", **base}


def laboratory(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    ser = snapshots(records)
    per = {sid: classify(s) for sid, s in ser.items()}
    counts: dict[str, int] = defaultdict(int)
    for v in per.values():
        counts[v["class"]] += 1
    return {"strategies": len(per), "by_class": dict(counts), "per_strategy": per}
