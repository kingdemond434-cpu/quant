"""THE WORLD DATA OS (Tier S layers 2 and 35): bitemporal truth and active information
acquisition.

BITEMPORAL. Every datapoint carries two times -- when it was TRUE in the world (valid time) and
when the desk COULD HAVE KNOWN it (knowledge time) -- plus provenance, revision number, publication
latency, source reliability and licence. `as_of(knowledge_t)` answers with exactly what existed
at that moment, latest revision known then, so a backtest that asks for "GDP for Q2" in July gets
the flash estimate and not the September revision. `pit_audit()` measures any dataset against the
contract: rows whose knowledge time precedes their valid time are impossible, rows with no
knowledge time are UNMEASURED, and both are counted rather than silently fixed.

ACTIVE ACQUISITION. Four organs already rank what to acquire (`value_of_data`,
`data_acquisition_scientist`, `evig_acquisition`, `source_evig`). None checks afterwards whether
an acquisition delivered what it promised, so their predictions are never calibrated. The
acquisition LEDGER records each prediction (item, kind, predicted gain, cost, the metric it will
move and that metric's value now) and resolves it when the item lands: realised gain = the
metric's move. Each ranker's CALIBRATION (realised / predicted, shrunk toward 1) then scales its
future predictions, so a ranker that over-promises loses influence. Kinds cover datasets AND the
cheaper upgrades the principal named: better timestamps, higher-quality history, a broker feed,
depth, a new public source, a specific missing variable.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from libs.tiers.replay import parse_t

ACQUISITION_KINDS: tuple[str, ...] = ("dataset", "timestamps", "history_quality",
                                      "broker_feed", "depth", "public_source",
                                      "missing_variable")


@dataclass(frozen=True)
class Datum:
    entity: str
    attribute: str
    value: Any
    valid_time: str
    knowledge_time: str
    source: str = ""
    revision: int = 0
    latency_s: float | None = None
    reliability: float | None = None
    licence: str = ""


class BitemporalStore:
    def __init__(self, rows: Iterable[Datum] = ()) -> None:
        self.rows: list[Datum] = list(rows)

    def add(self, d: Datum) -> None:
        self.rows.append(d)

    def as_of(self, knowledge_t: str, *, entity: str | None = None,
              attribute: str | None = None) -> dict[tuple[str, str, str], Datum]:
        """(entity, attribute, valid_time) -> the latest revision KNOWN at knowledge_t."""
        kt = parse_t(knowledge_t)
        out: dict[tuple[str, str, str], Datum] = {}
        for d in self.rows:
            if entity is not None and d.entity != entity:
                continue
            if attribute is not None and d.attribute != attribute:
                continue
            dk = parse_t(d.knowledge_time)
            if dk is None or kt is None or dk > kt:
                continue
            key = (d.entity, d.attribute, d.valid_time)
            cur = out.get(key)
            if cur is None or (d.revision, d.knowledge_time) > (cur.revision, cur.knowledge_time):
                out[key] = d
        return out

    def revisions(self) -> dict[str, Any]:
        per: dict[tuple[str, str, str], int] = {}
        for d in self.rows:
            k = (d.entity, d.attribute, d.valid_time)
            per[k] = per.get(k, 0) + 1
        revised = sum(1 for v in per.values() if v > 1)
        return {"points": len(per), "revised": revised,
                "revised_share": (revised / len(per)) if per else None}


def pit_audit(rows: Iterable[Mapping[str, Any]], *, valid_keys: Sequence[str] = (
        "event_time", "valid_time", "period_end", "date", "time"),
        knowledge_keys: Sequence[str] = ("available_time", "knowledge_time", "published",
                                         "published_time", "found_at", "ingested_time")
        ) -> dict[str, Any]:
    n = impossible = unmeasured = ok = 0
    lat: list[float] = []
    for r in rows:
        n += 1
        vt = next((parse_t(r.get(k)) for k in valid_keys if r.get(k)), None)
        kt = next((parse_t(r.get(k)) for k in knowledge_keys if r.get(k)), None)
        if kt is None or vt is None:
            unmeasured += 1
            continue
        if kt < vt:
            impossible += 1
            continue
        ok += 1
        lat.append((kt - vt).total_seconds())
    lat.sort()
    return {"n": n, "pit_ok": ok, "impossible": impossible, "unmeasured": unmeasured,
            "pit_share": (ok / n) if n else None,
            "median_latency_s": lat[len(lat) // 2] if lat else None}


@dataclass
class Prediction:
    item: str
    kind: str
    ranker: str
    predicted_gain: float
    cost_eur: float
    cost_cpu_h: float
    metric: str
    metric_before: float | None
    at: str
    resolved: bool = False
    realised_gain: float | None = None
    resolved_at: str | None = None
    #: an action counter at registration (a source's ok count, a dataset's acquired flag), so
    #: an own-metric resolver can tell "acted on" from "re-listed" (acquisition_resolution.py)
    flag_before: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def rank(preds: Sequence[Prediction], calibration: Mapping[str, float] | None = None,
         eur_per_cpu_h: float = 0.05) -> list[dict[str, Any]]:
    cal = calibration or {}
    rows: list[dict[str, Any]] = []
    for p in preds:
        if p.resolved:
            continue
        adj = p.predicted_gain * cal.get(p.ranker, 1.0)
        cost = max(1e-6, p.cost_eur + eur_per_cpu_h * p.cost_cpu_h)
        rows.append({"item": p.item, "kind": p.kind, "ranker": p.ranker,
                     "adjusted_gain": round(adj, 6), "gain_per_eur": round(adj / cost, 6),
                     "calibration": cal.get(p.ranker, 1.0)})
    rows.sort(key=lambda r: (-float(r["gain_per_eur"]), str(r["item"])))
    return rows


def resolve(preds: Sequence[Prediction], acquired: Mapping[str, datetime],
            metric_now: Mapping[str, float], now: str) -> int:
    n = 0
    for p in preds:
        if p.resolved or p.item not in acquired:
            continue
        after = metric_now.get(p.metric)
        if after is None or p.metric_before is None:
            continue
        p.realised_gain = after - p.metric_before
        p.resolved = True
        p.resolved_at = now
        n += 1
    return n


def calibration(preds: Sequence[Prediction], prior_n: float = 5.0) -> dict[str, float]:
    """Per ranker: shrunk ratio of realised to predicted gain (1.0 with no evidence)."""
    by: dict[str, list[tuple[float, float]]] = {}
    for p in preds:
        if p.resolved and p.realised_gain is not None and p.predicted_gain > 0:
            by.setdefault(p.ranker, []).append((p.realised_gain, p.predicted_gain))
    out: dict[str, float] = {}
    for r, pairs in by.items():
        real = sum(a for a, _b in pairs)
        pred = sum(b for _a, b in pairs)
        ratio = real / pred if pred > 0 else 1.0
        n = len(pairs)
        shrunk = (n * ratio + prior_n * 1.0) / (n + prior_n)
        out[r] = round(max(0.0, min(3.0, shrunk)), 4) if math.isfinite(shrunk) else 1.0
    return out
