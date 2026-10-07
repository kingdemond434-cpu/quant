"""PER SOURCE AND EVENT CLASS: how often a source is confirmed, revised, first, late, wrong, and
whether adding it makes the desk's forecast of the move better or only earlier (DATA-31).

WHAT EXISTED. `macro/attribution.report` counts confirmed / contradicted, median arrival lag and
median lead-to-move PER SOURCE; `research/source_registry.quality` measures a research ground's
revision rate off its refetched urls. Neither splits by EVENT CLASS, although a wire that is first
and right on central-bank headlines can be late and noisy on geopolitics. Neither says which share
of a source's events NO EARLIER SOURCE CARRIED, how often its claims never confirm, or whether it
adds predictive value once the others are known. This module is that table.

THE CLAIM. One row per (source, story): `source_id`, `event_class`, a `cluster` (the story's
identity across sources), `received_at`, optional `published_at`, `content_hash`, and whatever
the ledgers measured about it. Two ledgers feed it, and nothing is fetched:

  macro event ledger    (`data/macro/event_ledger.jsonl`, EventRecord rows) joined by event id
                        to `data/macro/event_attribution.jsonl` (move confirmation, lead to
                        move, the leading instrument's move and the desk's forecast sign).
                        Stories are clustered within an event class by title-token Jaccard
                        >= CLUSTER_JACCARD inside CONFIRM_WINDOW of the story's first receipt;
                        an explicit `cluster_id` / `story_id` on a row wins.
  sensor ledger         (`data/sensors/observations/<day>.jsonl`): an observation is a claim on
                        (entity, metric, event_time); a later vintage that names it in
                        `revision_of` marks it REVISED.

THE MEASURES, EACH WITH ITS n, AND UNMEASURED WITH ITS REASON BELOW ITS FLOOR (L1.28a).
  confirmation_rate     share of the source's stories another INDEPENDENT source (a different
                        source id, not a verbatim copy: a different content hash) carried within
                        +-CONFIRM_WINDOW; reported with its Wilson lower bound
  move_confirmation     share confirmed by the price (attribution's `move_confirmed`)
  false_positive_rate   among stories whose window has CLOSED: contradicted (a contradicting
                        source, or the move went the other way) or never confirmed by either
  revision_rate         share of the source's stories it later re-issued changed (a second
                        content hash on the same story) or that a later vintage revised
  unique_information    share of the source's stories (its own copies collapsed to one) that NO
                        EARLIER SOURCE carried; a story whose earlier carrier was a verbatim copy
                        is not unique either -- copies are discounted, never credited
  latency_s             median received - published
  lag_behind_first_s    median of (its receipt - the story's first receipt by anyone)
  lead_to_move_s        median arrival -> first material move (negative: the move came first)
  ipv_accuracy          does ADDING the source's forecast sign to the class base rate improve a
                        HELD-OUT probability of the move's sign? Its hit rate is learned only from
                        its earlier stories; Brier reduction judged by `sensor_engines.
                        forecast_gain` (block bootstrap), log-loss reduction beside it
  ipv_speed_s           median lead the source BUYS: the time from its receipt to the first
                        independent source's, over stories it carried first (0 when it was not
                        first); stories nobody else ever carried are counted as exclusive
Accuracy and speed are separate on purpose: a source can be early and add nothing, or late and
the only one that is right.
"""
from __future__ import annotations

import bisect
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

DESK = Path(__file__).resolve().parents[1]
MACRO_DIR = DESK / "data" / "macro"
EVENT_LEDGER = MACRO_DIR / "event_ledger.jsonl"
ATTRIBUTIONS = MACRO_DIR / "event_attribution.jsonl"
UNMEASURED = "UNMEASURED"
SCHEMA = "source_event_quality/1"
#: A story is confirmed / falsified inside this window of its receipt (attribution's horizon).
CONFIRM_WINDOW = timedelta(hours=24)
CLUSTER_JACCARD = 0.5
MIN_CLAIMS = 5
MIN_LEADS = 5
MIN_IPV = 30
SENSOR_DAYS = 14
SENSOR_MAX_ROWS = 200_000
WILSON_Z = 1.96
_TOKEN = re.compile(r"[^\W_]{3,}", re.UNICODE)
_STOP = frozenset({"the", "and", "for", "with", "from", "that", "this", "are", "was", "has",
                   "have", "will", "its", "after", "over", "into", "said", "says", "amid"})


# ============================================================================== small helpers
def _t(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    s = str(v or "").strip()
    if not s or s == UNMEASURED:
        return None
    try:
        got = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=UTC)


def _f(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
                if limit is not None and len(out) >= limit:
                    break
    return out


def wilson_lower(k: int, n: int, z: float = WILSON_Z) -> float | None:
    if n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(max(0.0, (centre - margin) / den), 4)


def _um(why: str) -> dict[str, str]:
    return {"value": UNMEASURED, "why": why}


def _rate(k: int, n: int, floor: int, what: str) -> dict[str, Any]:
    if n < floor:
        return {**_um(f"n={n} {what} < {floor}"), "n": n}
    return {"value": round(k / n, 4), "k": k, "n": n, "wilson_lower": wilson_lower(k, n)}


def _med(xs: Sequence[float], floor: int, what: str) -> dict[str, Any]:
    if len(xs) < floor:
        return {**_um(f"n={len(xs)} {what} < {floor}"), "n": len(xs)}
    return {"value": round(float(median(xs)), 3), "n": len(xs)}


def _tokens(text: str) -> frozenset[str]:
    return frozenset(w for w in (m.group(0).lower() for m in _TOKEN.finditer(text or ""))
                     if w not in _STOP)


# ============================================================================== the claims
def cluster(claims: list[dict[str, Any]]) -> None:
    """Give every claim a `cluster` in place: an explicit story id wins; otherwise the first
    earlier story of the same class, inside the window, whose title tokens overlap enough."""
    open_: dict[str, list[tuple[datetime, frozenset[str], str]]] = {}
    n = 0
    for c in sorted(claims, key=lambda r: r["received_at"]):
        if c.get("cluster"):
            continue
        toks = _tokens(str(c.get("title") or ""))
        cls = str(c["event_class"])
        live = [s for s in open_.get(cls, []) if c["received_at"] - s[0] <= CONFIRM_WINDOW]
        open_[cls] = live
        hit = None
        for _, stoks, sid in live:
            if toks and stoks and len(toks & stoks) / len(toks | stoks) >= CLUSTER_JACCARD:
                hit = sid
                break
        if hit is None:
            n += 1
            hit = f"{cls}#{n}"
            live.append((c["received_at"], toks, hit))
        c["cluster"] = hit


def from_event_ledger(rows: Iterable[Mapping[str, Any]],
                      attributions: Iterable[Mapping[str, Any]] = ()) -> list[dict[str, Any]]:
    """EventRecord rows (+ attribution rows by event id) as claims, clustered into stories."""
    att: dict[str, Mapping[str, Any]] = {}
    for a in attributions:
        if a.get("event_id"):
            att[str(a["event_id"])] = a                      # the latest marking wins
    claims: list[dict[str, Any]] = []
    for r in rows:
        rec = _t(r.get("received_at"))
        if rec is None or not r.get("source_id"):
            continue
        a = att.get(str(r.get("event_id") or ""), {})
        lead_sym = a.get("leading_instrument")
        signal = None
        for f in r.get("forecasts") or []:
            v = _f(f.get("expected_move_sigma")) if isinstance(f, Mapping) else None
            if v and str(f.get("symbol") or "") == str(lead_sym or ""):
                signal = 1 if v > 0 else -1
                break
        move = _f(a.get("leading_move_sigma"))
        mc = a.get("move_confirmed")
        claims.append({
            "source_id": str(r["source_id"]),
            "event_class": str(r.get("category") or "UNCLASSIFIED"),
            "cluster": str(r.get("cluster_id") or r.get("story_id") or ""),
            "title": str(r.get("title") or ""),
            "received_at": rec, "published_at": _t(r.get("published_at")),
            "content_hash": str(r.get("content_hash") or r.get("event_id") or ""),
            "contradicted": bool(r.get("contradicted_by")),
            "move_confirmed": mc if isinstance(mc, bool) else None,
            "lead_s": _f(a.get("lead_s")),
            "signal": signal,
            "outcome": (None if move is None or move == 0 else (1 if move > 0 else 0)),
            "attributed": bool(a)})
    cluster(claims)
    # a source re-issuing the same story with different content revised it
    hashes: dict[tuple[str, str], set[str]] = {}
    for c in claims:
        hashes.setdefault((c["source_id"], c["cluster"]), set()).add(c["content_hash"])
    for c in claims:
        c["revised"] = len(hashes[(c["source_id"], c["cluster"])]) > 1
    return claims


def from_sensor_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Sensor-ledger observations as claims on (entity, metric, event_time); a later vintage
    naming one in `revision_of` marks it revised."""
    rows = list(rows)
    revised = {str(r.get("revision_of")) for r in rows if r.get("revision_of")}
    claims = []
    for r in rows:
        if r.get("revision_of"):
            continue
        rec = _t(r.get("received_at"))
        if rec is None:
            continue
        oid = str(r.get("observation_id") or "")
        claims.append({
            "source_id": str(r.get("source_id") or r.get("sensor_id") or ""),
            "event_class": str(r.get("sensor_class") or "unclassified"),
            "cluster": f"{r.get('entity')}|{r.get('metric')}|{r.get('event_time')}",
            "received_at": rec,
            "published_at": _t(r.get("publication_time") or r.get("source_publication_time")),
            "content_hash": str(r.get("provenance_hash") or oid),
            "contradicted": False, "move_confirmed": None, "lead_s": None, "signal": None,
            "outcome": None, "attributed": False, "revised": oid in revised})
    return [c for c in claims if c["source_id"]]


# ============================================================================== the table
def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ipv_accuracy(cell: Sequence[Mapping[str, Any]], klass: Sequence[Mapping[str, Any]],
                 *, min_n: int = MIN_IPV) -> dict[str, Any]:
    """Held-out: the class base rate of an up move (Laplace, stories received before this one)
    against the same rate moved by this source's forecast sign at its own EARLIER hit rate."""
    from libs.research import sensor_engines as se
    outcomes = sorted(((c["received_at"], int(c["outcome"])) for c in klass
                       if c.get("outcome") is not None), key=lambda t: t[0])
    times = [t for t, _ in outcomes]
    ups = [0]
    for _, o in outcomes:
        ups.append(ups[-1] + o)
    mine = sorted((c for c in cell if c.get("outcome") is not None and c.get("signal")),
                  key=lambda c: c["received_at"])
    y: list[float] = []
    p_with: list[float] = []
    p_base: list[float] = []
    hits = 0
    for n_s, c in enumerate(mine):
        k = bisect.bisect_left(times, c["received_at"])
        pb = (ups[k] + 1) / (k + 2)
        h = (hits + 1) / (n_s + 2)
        pw = 1 / (1 + math.exp(-(_logit(pb) + (1 if c["signal"] > 0 else -1) * _logit(h))))
        y.append(float(c["outcome"]))
        p_with.append(pw)
        p_base.append(pb)
        hits += int((c["signal"] > 0) == bool(c["outcome"]))
    row = se.forecast_gain(y, p_with, p_base, engine="source_event_quality", cards=["DATA-31"],
                           falsifier="Adding the source's forecast sign does not lower the "
                                     "held-out Brier score of the move's sign.",
                           baseline="class base rate of an up move", block=5, min_n=min_n)

    def ll(ps: Sequence[float]) -> float:
        return -sum(math.log(p if o else 1 - p) for p, o in zip(ps, y, strict=True)) / len(y)

    row["brier_reduction"] = row.get("gain")
    row["logloss_reduction"] = round(ll(p_base) - ll(p_with), 6) if y else None
    if not y:
        row["why"] = ("no story from this source carries both a forecast sign and a measured "
                      "move (attribution)")
    return row


def table(claims: Sequence[dict[str, Any]], *, now: datetime,
          min_claims: int = MIN_CLAIMS, min_leads: int = MIN_LEADS,
          min_ipv: int = MIN_IPV) -> dict[str, Any]:
    """The per-(source, event class) table and a per-source roll-up of the same measures."""
    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        by_cluster.setdefault(c["cluster"], []).append(c)
    for grp in by_cluster.values():
        grp.sort(key=lambda r: r["received_at"])
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in claims:
        cells.setdefault((c["source_id"], c["event_class"]), []).append(c)
    by_class: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        by_class.setdefault(c["event_class"], []).append(c)

    def measure(rows: list[dict[str, Any]], klass: list[dict[str, Any]] | None
                ) -> dict[str, Any]:
        sid = rows[0]["source_id"]
        # this source's copies of one story collapse to its earliest claim
        first: dict[str, dict[str, Any]] = {}
        for c in sorted(rows, key=lambda r: r["received_at"]):
            first.setdefault(c["cluster"], c)
        stories = list(first.values())
        revised = {c["cluster"] for c in rows if c.get("revised")}
        n = len(stories)
        conf = uniq = closed = fp = rev = 0
        mc_k = mc_n = 0
        lag_first: list[float] = []
        speed: list[float] = []
        exclusive = 0
        for c in stories:
            grp = by_cluster[c["cluster"]]
            others = [o for o in grp if o["source_id"] != sid]
            indep = [o for o in others if o["content_hash"] != c["content_hash"]]
            near = [o for o in indep
                    if abs(o["received_at"] - c["received_at"]) <= CONFIRM_WINDOW]
            corroborated = bool(near)
            conf += int(corroborated)
            earlier = [o for o in others if o["received_at"] < c["received_at"]]
            uniq += int(not earlier)
            lag_first.append((c["received_at"] - grp[0]["received_at"]).total_seconds())
            later = [o for o in indep if o["received_at"] >= c["received_at"]]
            if not earlier:
                if later:
                    speed.append((later[0]["received_at"] - c["received_at"]).total_seconds())
                else:
                    exclusive += 1
            elif indep:
                speed.append(0.0)
            if c.get("move_confirmed") is not None:
                mc_n += 1
                mc_k += int(bool(c["move_confirmed"]))
            if now - c["received_at"] >= CONFIRM_WINDOW:
                closed += 1
                contradicted = c.get("contradicted") or c.get("move_confirmed") is False
                confirmed = corroborated or c.get("move_confirmed") is True
                fp += int(bool(contradicted) or not confirmed)
            rev += int(c["cluster"] in revised)
        lat = [(c["received_at"] - c["published_at"]).total_seconds() for c in stories
               if c.get("published_at") is not None]
        leads = [float(c["lead_s"]) for c in stories if c.get("lead_s") is not None]
        out: dict[str, Any] = {
            "n_claims": len(rows), "n_stories": n, "n_copies": len(rows) - n,
            "confirmation_rate": _rate(conf, n, min_claims, "stories"),
            "move_confirmation": _rate(mc_k, mc_n, min_claims,
                                       "stories with a price verdict (attribution)"),
            "false_positive_rate": _rate(fp, closed, min_claims,
                                         f"stories whose {CONFIRM_WINDOW} window has closed"),
            "revision_rate": _rate(rev, n, min_claims, "stories"),
            "unique_information": _rate(uniq, n, min_claims, "stories"),
            "latency_s": _med(lat, min_leads, "stories with a publication clock"),
            "lag_behind_first_s": _med(lag_first, min_leads, "stories"),
            "lead_to_move_s": _med(leads, min_leads, "stories with a measured move lead"),
            "ipv_speed_s": {**_med(speed, min_leads, "stories another source also carried"),
                            "n_exclusive": exclusive},
        }
        if klass is not None:
            out["ipv_accuracy"] = ipv_accuracy(rows, klass, min_n=min_ipv)
        return out

    rows_out = []
    for (sid, cls), rows in sorted(cells.items()):
        rows_out.append({"source_id": sid, "event_class": cls,
                         **measure(rows, by_class[cls])})
    by_source: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        by_source.setdefault(c["source_id"], []).append(c)
    sources = {sid: measure(rows, None) for sid, rows in sorted(by_source.items())}
    fields = ("confirmation_rate", "move_confirmation", "false_positive_rate", "revision_rate",
              "unique_information", "latency_s", "lag_behind_first_s", "lead_to_move_s",
              "ipv_speed_s")
    coverage = {f: sum(1 for r in rows_out if r[f].get("value") != UNMEASURED)
                for f in fields}
    coverage["ipv_accuracy"] = sum(1 for r in rows_out
                                   if r["ipv_accuracy"].get("verdict") != UNMEASURED)
    return {"schema": SCHEMA, "at": now.isoformat(timespec="seconds"),
            "n_claims": len(claims), "n_stories": len(by_cluster), "n_cells": len(rows_out),
            "cells": rows_out, "by_source": sources, "measured_cells": coverage,
            "confirm_window_h": CONFIRM_WINDOW.total_seconds() / 3600,
            "floors": {"rates": min_claims, "medians": min_leads, "ipv_accuracy": min_ipv},
            "rule": ("every measure carries its n and is UNMEASURED with its reason below its "
                     "floor; confirmation needs an INDEPENDENT source (a different id and a "
                     "different content hash), so a syndicated copy confirms nothing")}


# ============================================================================== the organ
def sensor_rows(root: Path | None = None, days: int = SENSOR_DAYS,
                max_rows: int = SENSOR_MAX_ROWS) -> list[dict[str, Any]]:
    from libs.research import sensor_contract as sc
    base = (root or sc.default_root()) / "observations"
    out: list[dict[str, Any]] = []
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*.jsonl"))[-days:]:
        out += _jsonl(path, limit=max(0, max_rows - len(out)))
        if len(out) >= max_rows:
            break
    return out


def build(*, now: datetime | None = None, ledger: Path = EVENT_LEDGER,
          attributions: Path = ATTRIBUTIONS, sensors: Path | None = None) -> dict[str, Any]:
    """Both ledgers, one table. Absent ledgers are named, never read as zero."""
    when = now or datetime.now(UTC)
    ev = _jsonl(ledger)
    att = _jsonl(attributions)
    sens = sensor_rows(sensors)
    claims = from_event_ledger(ev, att) + from_sensor_rows(sens)
    doc = table(claims, now=when)
    doc["inputs"] = {
        "event_ledger": {"path": str(ledger), "rows": len(ev)} if ev else
        _um(f"{ledger.name} absent or empty"),
        "attributions": {"path": str(attributions), "rows": len(att)} if att else
        _um(f"{attributions.name} absent or empty: move confirmation, lead to move and "
            "ipv_accuracy have no price verdict to read"),
        "sensor_ledger": {"rows": len(sens), "days": SENSOR_DAYS} if sens else
        _um("no sensor-ledger shard on this host")}
    if not claims:
        doc["status"] = UNMEASURED
        doc["why"] = "no claim in either ledger"
    return doc


__all__ = ["build", "cluster", "from_event_ledger", "from_sensor_rows", "ipv_accuracy",
           "table", "wilson_lower"]
