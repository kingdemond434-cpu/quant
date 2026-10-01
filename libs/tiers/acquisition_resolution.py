"""EACH ACQUISITION RANKER RESOLVED ON ITS OWN METRIC, IN NORMALISED GAIN (Tier S layer 35).

`libs/tiers/bitemporal.py` records the four acquisition rankers' predictions and calibrates them
on arrival -- but it resolved all four against ONE desk metric (the intelligence pit_share),
which none of them predicts, and ranked their gains against each other in four different units.
A ranker that promised "0.03 R of posterior sd removed" was scored by a timestamp share, and its
0.03 was compared with another ranker's 12.7 nats.

HERE EACH RANKER IS HELD TO WHAT IT ACTUALLY PROMISED, read back from its OWN next report:

    value_of_data               need_id   R of posterior sd the observation would remove; the
                                          need's remaining value on a later report is what is
                                          still unremoved, so realised = value_then - value_now
    source_evig                 source id prior sd over the source's targets; resolved once the
                                          source was actually COLLECTED (its ok count rose):
                                          realised = u_then - u_now, predicted = evig x cost
                                          (= u x novelty x p_usable x lag weight)
    evig_acquisition            family:resource  the resource's remaining expected information
                                          in its own family's currency; realised = drop in it
    data_acquisition_scientist  dataset   the share of the observable the desk holds
                                          (1 - redundancy is what is missing); resolved when the
                                          ranker's own ROI ledger marks it ACQUIRED or its
                                          redundancy rises: realised = red_now - red_then,
                                          predicted = its information_gain term

An item that is simply no longer listed is NOT resolved: a ranker's top-N can drop an item for
reasons that are not the promise coming true, and absence is not evidence (UNMEASURED stays open).

NORMALISED GAIN. Every gain is divided by its ranker's SCALE -- the median |predicted gain| of
that ranker's registered predictions -- so one unit means "this ranker's typical promise" for all
four. Calibration is the shrunk ratio of normalised realised to normalised predicted (unit-free,
1.0 with no evidence), the Spearman agreement between the two is published beside it, and the
cross-ranker ranking multiplies NORMALISED predicted gain by calibration, never raw units.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from libs.tiers.bitemporal import Prediction
from libs.tiers.replay import parse_t

#: a prediction is not resolved before this many hours have passed since it was made
MIN_HOURS = 6.0


@dataclass(frozen=True)
class Spec:
    ranker: str
    report: str
    metric: str
    unit: str


SPECS: tuple[Spec, ...] = (
    Spec("value_of_data", "VALUE_OF_DATA.json", "vod.remaining_value", "R of posterior sd"),
    Spec("source_evig", "SOURCE_EVIG.json", "source.u_prior_sd", "prior sd over targets"),
    Spec("evig_acquisition", "EVIG_ACQUISITION.json", "evig.remaining", "family currency"),
    Spec("data_acquisition_scientist", "DATA_ACQUISITION.json", "dataset.held_share",
         "share of the observable held"),
)
BY_RANKER: dict[str, Spec] = {s.ranker: s for s in SPECS}


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def observe(ranker: str, doc: Any) -> dict[str, dict[str, Any]]:
    """item -> {predicted, value, flag, kind} from one ranker report, in its own metric.
    `value` is the own-metric reading now; `flag` a monotone action counter where one exists
    (source ok count; dataset acquired)."""
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(doc, Mapping):
        return out
    if ranker == "value_of_data":
        for r in doc.get("top") or []:
            v = _f((r or {}).get("value"))
            if isinstance(r, Mapping) and r.get("need_id") and v is not None:
                out[str(r["need_id"])] = {"predicted": v, "value": v, "flag": None,
                                          "kind": str(r.get("kind") or "missing_variable")}
    elif ranker == "source_evig":
        for r in doc.get("rows") or []:
            if not isinstance(r, Mapping) or not r.get("id"):
                continue
            u, ev, cost = _f(r.get("u_prior_sd")), _f(r.get("evig")), _f(r.get("cost_s"))
            if u is None or ev is None:
                continue
            out[str(r["id"])] = {"predicted": ev * (cost or 1.0), "value": u,
                                 "flag": _f(r.get("ok")), "kind": "public_source"}
    elif ranker == "evig_acquisition":
        for r in doc.get("ranked") or []:
            v = _f((r or {}).get("evig"))
            if isinstance(r, Mapping) and r.get("resource") is not None and v is not None:
                out[f"{r.get('family')}:{r['resource']}"] = {"predicted": v, "value": v,
                                                             "flag": None, "kind": "dataset"}
    elif ranker == "data_acquisition_scientist":
        acquired = {str(r.get("dataset")): bool(r.get("acquired"))
                    for r in ((doc.get("source_roi") or {}).get("rows") or [])
                    if isinstance(r, Mapping)}
        for r in doc.get("ranked") or []:
            if not isinstance(r, Mapping) or not r.get("dataset"):
                continue
            t = r.get("terms") or {}
            red, ig = _f(t.get("redundancy")), _f(t.get("information_gain"))
            if red is None or ig is None:
                continue
            ds = str(r["dataset"])
            out[ds] = {"predicted": ig, "value": red,
                       "flag": 1.0 if acquired.get(ds) else 0.0, "kind": "dataset"}
        for ds, acq in acquired.items():                  # held since: no longer ranked
            if acq and ds not in out:
                out[ds] = {"predicted": None, "value": 1.0, "flag": 1.0, "kind": "dataset"}
    return out


def register(preds: list[Prediction], ranker: str, obs: Mapping[str, Mapping[str, Any]],
             now: str, top: int = 20) -> int:
    """Register the ranker's top items not already open, in its own metric."""
    spec = BY_RANKER[ranker]
    open_items = {(p.ranker, p.item) for p in preds if not p.resolved}
    made = 0
    ranked = sorted(((k, v) for k, v in obs.items() if v.get("predicted") is not None),
                    key=lambda kv: -float(kv[1]["predicted"]))[:top]
    for item, o in ranked:
        if (ranker, item) in open_items:
            continue
        preds.append(Prediction(item=item, kind=str(o.get("kind") or "dataset"), ranker=ranker,
                                predicted_gain=float(o["predicted"]), cost_eur=0.0,
                                cost_cpu_h=0.1, metric=spec.metric,
                                metric_before=float(o["value"]), at=now,
                                flag_before=o.get("flag")))
        made += 1
    return made


def resolve(preds: Sequence[Prediction], obs_by: Mapping[str, Mapping[str, Mapping[str, Any]]],
            now: str) -> int:
    """Resolve open own-metric predictions whose promise the ranker's own report now shows
    acted on. Returns the number resolved this call."""
    t_now = parse_t(now)
    n = 0
    for p in preds:
        spec = BY_RANKER.get(p.ranker)
        if p.resolved or spec is None or p.metric != spec.metric or p.metric_before is None:
            continue
        t0 = parse_t(p.at)
        if t_now is None or t0 is None or t_now - t0 < timedelta(hours=MIN_HOURS):
            continue
        o = (obs_by.get(p.ranker) or {}).get(p.item)
        if o is None:
            continue                                        # not listed: not evidence
        now_v = _f(o.get("value"))
        if now_v is None:
            continue
        if p.ranker == "source_evig":
            if o.get("flag") is None or p.flag_before is None or \
                    float(o["flag"]) <= float(p.flag_before):
                continue                                    # not collected yet
            realised = p.metric_before - now_v
        elif p.ranker == "data_acquisition_scientist":
            acted = (o.get("flag") or 0.0) > (p.flag_before or 0.0) or now_v > p.metric_before
            if not acted:
                continue
            realised = now_v - p.metric_before
        else:
            realised = p.metric_before - now_v
        p.realised_gain = realised
        p.resolved = True
        p.resolved_at = now
        n += 1
    return n


def _spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    if len(a) < 3:
        return None

    def ranks(x: Sequence[float]) -> list[float]:
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den > 0 else None


def scales(preds: Sequence[Prediction]) -> dict[str, float]:
    """Per ranker: the median |predicted gain| of its own-metric predictions (its unit)."""
    by: dict[str, list[float]] = {}
    for p in preds:
        spec = BY_RANKER.get(p.ranker)
        if spec is not None and p.metric == spec.metric and p.predicted_gain != 0:
            by.setdefault(p.ranker, []).append(abs(p.predicted_gain))
    out: dict[str, float] = {}
    for r, xs in by.items():
        xs = sorted(xs)
        m = xs[len(xs) // 2] if len(xs) % 2 else 0.5 * (xs[len(xs) // 2 - 1] + xs[len(xs) // 2])
        if m > 0:
            out[r] = m
    return out


def calibration(preds: Sequence[Prediction], prior_n: float = 5.0) -> dict[str, dict[str, Any]]:
    """Per ranker, on NORMALISED gain: shrunk realised/predicted ratio, Spearman agreement,
    the resolved count and the unit. A ranker with nothing resolved is UNMEASURED (ratio 1.0)."""
    sc = scales(preds)
    out: dict[str, dict[str, Any]] = {}
    for spec in SPECS:
        s = sc.get(spec.ranker)
        done = [p for p in preds if p.ranker == spec.ranker and p.metric == spec.metric
                and p.resolved and p.realised_gain is not None and p.predicted_gain > 0]
        opened = sum(1 for p in preds if p.ranker == spec.ranker and p.metric == spec.metric
                     and not p.resolved)
        row: dict[str, Any] = {"metric": spec.metric, "unit": spec.unit, "scale": s,
                               "resolved": len(done), "open": opened}
        if not done or not s:
            out[spec.ranker] = {**row, "status": "UNMEASURED", "calibration": 1.0,
                                "spearman": None}
            continue
        pn = [p.predicted_gain / s for p in done]
        rn = [float(p.realised_gain or 0.0) / s for p in done]
        ratio = sum(rn) / sum(pn) if sum(pn) > 0 else 1.0
        n = len(done)
        shrunk = (n * ratio + prior_n) / (n + prior_n)
        out[spec.ranker] = {**row, "status": "MEASURED",
                            "calibration": round(max(0.0, min(3.0, shrunk)), 4),
                            "raw_ratio": round(ratio, 4),
                            "mean_normalised_predicted": round(sum(pn) / n, 4),
                            "mean_normalised_realised": round(sum(rn) / n, 4),
                            "spearman": (None if (sp := _spearman(pn, rn)) is None
                                         else round(sp, 4))}
    return out


def rank(preds: Sequence[Prediction], cal: Mapping[str, Mapping[str, Any]]
         ) -> list[dict[str, Any]]:
    """Open own-metric predictions across all rankers, by NORMALISED predicted gain x the
    ranker's calibration -- one currency, the ranker's typical promise."""
    sc = scales(preds)
    rows: list[dict[str, Any]] = []
    for p in preds:
        spec = BY_RANKER.get(p.ranker)
        if p.resolved or spec is None or p.metric != spec.metric or not sc.get(p.ranker):
            continue
        norm = p.predicted_gain / sc[p.ranker]
        c = float((cal.get(p.ranker) or {}).get("calibration") or 1.0)
        rows.append({"item": p.item, "ranker": p.ranker, "metric": p.metric,
                     "predicted": p.predicted_gain, "normalised_gain": round(norm, 4),
                     "calibration": c, "adjusted_gain": round(norm * c, 4), "since": p.at})
    rows.sort(key=lambda r: (-float(r["adjusted_gain"]), str(r["item"])))
    return rows
