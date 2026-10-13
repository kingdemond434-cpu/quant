"""THE WORLD SENSOR'S TEN GAPS, RE-AUDITED FROM WHAT IS ON THE HOST (DATA-19).

The re-audit named ten gaps between the world sensor and a professional news/event desk:

    1 news_throughput           high-volume news throughput
    2 multilingual_firehose     a multilingual firehose
    3 gdelt_intake              GDELT intake
    4 pit_consensus_actual      point-in-time consensus AND actual per release
    5 low_latency_wire          a low-latency wire
    6 broad_m1_tick             broad M1 / tick coverage
    7 measured_reactions        measured reactions to events
    8 event_capital_authority   capital-authority evidence for events
    9 event_allocator_reaction  a resident event -> allocator reaction
   10 config_only_providers     providers that exist only as configuration

A gap that is described in prose cannot be tracked. This organ MEASURES each one from the
artifacts this host holds: counts, rates, freshness and latency percentiles. A gap whose evidence
is absent is UNMEASURED and NAMES the artifact it needed (L1.28a). Absence never reads as zero,
and zero never reads as absence: an artifact that is present and empty is a measured zero.

Each gap also gets `open`, judged against a DECLARED target (TARGETS). That is a reading aid with
the number beside it, not a verdict on the desk. Nothing here sizes, gates or writes to any
ledger. The clock is the hourly `sensor_ledger` leg (`research/sensor_ledger_digest.py`), which
writes reports/WORLD_SENSOR_GAPS.json right after SENSOR_LEDGER.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UNMEASURED = "UNMEASURED"
REPORT = DESK / "reports" / "WORLD_SENSOR_GAPS.json"
GAPS = ("news_throughput", "multilingual_firehose", "gdelt_intake", "pit_consensus_actual",
        "low_latency_wire", "broad_m1_tick", "measured_reactions", "event_capital_authority",
        "event_allocator_reaction", "config_only_providers")
#: The DECLARED target each gap is read against: a reading aid, not a fitted threshold.
TARGETS: dict[str, str] = {
    "news_throughput": "documents_24h >= 10000",
    "multilingual_firehose": "non_english_share >= 0.20 across >= 10 languages",
    "gdelt_intake": "rows_24h > 0 and newest row younger than 1 h",
    "pit_consensus_actual": "rows_30d > 0, newest younger than 7 d, every source terms-admitted",
    "low_latency_wire": "publication_to_receipt p50 <= 60 s",
    "broad_m1_tick": "M1 coverage >= 50% of the universe and ticks younger than 24 h",
    "measured_reactions": "atlas younger than 48 h with >= 1 cell clearing cost and Bonferroni",
    "event_capital_authority": ">= 1 LIVE sleeve or certified cell from an event family",
    "event_allocator_reaction": "the allocator watches the news re-solve request, and a 7 d "
                                "with requests has >= 1 event-triggered solve",
    "config_only_providers": "0 configured providers with no observed row",
}
EVENT_MARKERS = ("event", "news", "surprise", "earnings", "release", "exogenous_conditioner",
                 "announcement", "headline")


@dataclass
class Paths:
    desk: Path = DESK
    ledger_root: Path | None = None

    @property
    def intake(self) -> Path:
        return self.desk / "reports" / "WORLD_SENSOR_INTAKE.json"

    @property
    def consensus(self) -> Path:
        return self.desk / "data" / "macro" / "consensus_actuals.jsonl"

    @property
    def universe_dir(self) -> Path:
        return self.desk / "data" / "universe"

    @property
    def tape_state(self) -> Path:
        return self.desk / "data" / "tape" / "tape_state.json"

    @property
    def atlas(self) -> Path:
        return self.desk / "reports" / "EVENT_RESPONSE_ATLAS.json"

    @property
    def surprise(self) -> Path:
        return self.desk / "reports" / "EVENT_SURPRISE.json"

    @property
    def sleeves(self) -> Path:
        return self.desk / "data" / "sleeves.json"

    @property
    def survivors(self) -> Path:
        return self.desk / "reports" / "UNIVERSAL_SURVIVORS.json"

    @property
    def resolve_queue(self) -> Path:
        return self.desk / "data" / "allocator_resolve_queue.jsonl"

    @property
    def reactions(self) -> Path:
        return self.desk / "data" / "allocator_reactions.jsonl"

    @property
    def consensus_sources(self) -> Path:
        return self.desk / "data" / "event_consensus_sources.json"


@dataclass
class Ctx:
    now: datetime
    paths: Paths
    rows: list[dict[str, Any]] = field(default_factory=list)
    ledger_days: list[str] = field(default_factory=list)
    providers: Mapping[str, Sequence[str]] | None = None
    watched: Sequence[str] | None = None


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _t(v: Any) -> datetime | None:
    from libs.research import sensor_contract as sc
    return sc.parse_time(v)


def _age_s(now: datetime, t: datetime | None) -> float | None:
    return round((now - t).total_seconds(), 1) if t is not None else None


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _jsonl(p: Path, tail_bytes: int = 32 * 1024 * 1024) -> list[dict[str, Any]] | None:
    """Rows of a JSONL file (its tail), or None when the file is absent."""
    try:
        with p.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    out = []
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _un(why: str, *missing: str) -> dict[str, Any]:
    return {"status": UNMEASURED, "why": why, "missing": list(missing), "open": None}


def _measured(evidence: Sequence[str], metrics: Mapping[str, Any], open_: bool | None,
              **extra: Any) -> dict[str, Any]:
    return {"status": "MEASURED", "evidence": list(evidence), "metrics": dict(metrics),
            "open": open_, **extra}


def _docs(ctx: Ctx) -> list[dict[str, Any]]:
    return [r for r in ctx.rows if r.get("kind") == "document"]


def _ledger_missing(ctx: Ctx) -> str:
    root = ctx.paths.ledger_root or (ctx.paths.desk / "data" / "sensors")
    return f"{_rel(root)}/observations/<day>.jsonl (receipt days {', '.join(ctx.ledger_days)})"


# ============================================================================== the ten gaps
def news_throughput(ctx: Ctx) -> dict[str, Any]:
    docs = _docs(ctx)
    if not docs:
        return _un("the sensor ledger holds no document row in the read window",
                   _ledger_missing(ctx))
    since = ctx.now - timedelta(hours=24)
    recent = [r for r in docs if (t := _t(r.get("received_at"))) is not None and t >= since]
    hours = Counter(t.strftime("%Y-%m-%dT%H") for r in recent
                    if (t := _t(r.get("received_at"))) is not None)
    newest = max((t for r in docs if (t := _t(r.get("received_at"))) is not None), default=None)
    raw = sum(1 + int((r.get("attributes") or {}).get("copies") or 0) for r in recent)
    unique = len({str(r.get("provenance_hash") or r.get("observation_id")) for r in recent})
    intake = _json(ctx.paths.intake)
    m = {"documents_24h": len(recent), "raw_items_24h": raw, "unique_documents_24h": unique,
         "per_hour_mean": round(len(recent) / 24.0, 2),
         "peak_hour": max(hours.values()) if hours else 0,
         "hours_with_intake": len(hours), "newest_age_s": _age_s(ctx.now, newest),
         "news_day": (intake or {}).get("news_day") if isinstance(intake, dict) else None}
    return _measured([_ledger_missing(ctx), _rel(ctx.paths.intake)], m,
                     len(recent) < 10000)


def multilingual_firehose(ctx: Ctx) -> dict[str, Any]:
    docs = _docs(ctx)
    if not docs:
        return _un("no document row to read languages from", _ledger_missing(ctx))
    langs = Counter(str(r.get("language") or UNMEASURED) for r in docs)
    labelled = {k: v for k, v in langs.items() if k not in (UNMEASURED, "")}
    n_lab = sum(labelled.values())
    non_en = sum(v for k, v in labelled.items() if not k.lower().startswith("en"))
    share = round(non_en / n_lab, 4) if n_lab else None
    m = {"documents": len(docs), "labelled": n_lab,
         "unlabelled_share": round(1 - n_lab / len(docs), 4),
         "distinct_languages": len(labelled), "non_english_share": share,
         "top": dict(Counter(labelled).most_common(12))}
    return _measured([_ledger_missing(ctx)], m,
                     share is None or share < 0.20 or len(labelled) < 10)


def gdelt_intake(ctx: Ctx) -> dict[str, Any]:
    g = [r for r in ctx.rows if "gdelt" in f"{r.get('source_id')} {r.get('dataset_id')}".lower()]
    if not g:
        return _un("no GDELT row in the sensor ledger's read window (alt_proxies vaults the "
                   "15-minute exports; news_event_stream reads them into the ledger)",
                   f"{_ledger_missing(ctx)} rows with dataset_id gdelt_*")
    since = ctx.now - timedelta(hours=24)
    times = [t for r in g if (t := _t(r.get("received_at"))) is not None]
    slots = {str(r.get("source_publication_time") or r.get("knowable_at"))[:16] for r in g}
    newest = max(times, default=None)
    age = _age_s(ctx.now, newest)
    m: dict[str, Any] = {"rows": len(g), "rows_24h": sum(1 for t in times if t >= since),
         "distinct_publication_slots": len(slots), "newest_age_s": age,
         "datasets": dict(Counter(str(r.get("dataset_id")) for r in g).most_common(6))}
    return _measured([_ledger_missing(ctx)], m,
                     not (m["rows_24h"] > 0 and age is not None and age < 3600))


def pit_consensus_actual(ctx: Ctx) -> dict[str, Any]:
    rows = _jsonl(ctx.paths.consensus)
    if rows is None:
        return _un("the consensus+actual store is absent on this host",
                   _rel(ctx.paths.consensus))
    from libs.data.terms_hold import gauntlet_terms

    def num(v: Any) -> bool:
        return isinstance(v, int | float) and not isinstance(v, bool)

    both = [r for r in rows if num(r.get("actual")) and num(r.get("consensus"))
            and _t(r.get("at")) is not None]
    since = ctx.now - timedelta(days=30)
    recent = [r for r in both if (_t(r.get("at")) or ctx.now) >= since]
    srcs = Counter(str(r.get("source_id") or UNMEASURED) for r in both)
    admitted = {s: bool(gauntlet_terms(s)[0]) for s in srcs}
    newest = max((t for r in both if (t := _t(r.get("at"))) is not None), default=None)
    m: dict[str, Any] = {
         "rows": len(rows), "rows_with_both_and_stamp": len(both), "rows_30d": len(recent),
         "distinct_releases": len({str(r.get("release")) for r in both}),
         "newest_age_s": _age_s(ctx.now, newest),
         "sources": dict(srcs.most_common(10)),
         "terms_admitted_share": (round(sum(srcs[s] for s, ok in admitted.items() if ok)
                                        / len(both), 4) if both else None),
         "held_sources": sorted(s for s, ok in admitted.items() if not ok)}
    age = m["newest_age_s"]
    return _measured([_rel(ctx.paths.consensus)], m,
                     not (recent and age is not None and age < 7 * 86400
                          and not m["held_sources"]))


def low_latency_wire(ctx: Ctx) -> dict[str, Any]:
    from libs.research import sensor_contract as sc
    lat: list[float] = []
    by_ds: dict[str, list[float]] = {}
    for r in _docs(ctx):
        if r.get("knowable_basis") != "printed_stamp":
            continue                        # a receipt-bounded stamp has zero latency by design
        pub = r.get("source_publication_time")
        if pub in (None, UNMEASURED):
            pub = r.get("publication_time")
        v = sc.latency_s(pub, r.get("received_at"))
        if v is not None and v >= 0:
            lat.append(v)
            by_ds.setdefault(str(r.get("dataset_id") or UNMEASURED), []).append(v)
    if not lat:
        return _un("no document row carries an independent printed publication stamp",
                   f"{_ledger_missing(ctx)} rows with knowable_basis printed_stamp")
    pct = sc.percentiles(lat, (0.5, 0.9, 0.99))
    m = {"publication_to_receipt_s": pct,
         "share_within_60s": round(sum(1 for v in lat if v <= 60) / len(lat), 4),
         "by_dataset_p50_s": {k: sc.percentiles(v, (0.5,))["p50"]
                              for k, v in sorted(by_ds.items(), key=lambda kv: -len(kv[1]))[:8]}}
    p50 = pct.get("p50")
    return _measured([_ledger_missing(ctx)], m, not (isinstance(p50, float | int) and p50 <= 60))


def broad_m1_tick(ctx: Ctx) -> dict[str, Any]:
    reg = _json(ctx.paths.universe_dir / "universe.json")
    m1 = sorted(ctx.paths.universe_dir.glob("*_M1.parquet")) \
        if ctx.paths.universe_dir.is_dir() else []
    tape = _json(ctx.paths.tape_state)
    if not isinstance(reg, dict) and not m1 and not isinstance(tape, dict):
        return _un("neither the universe registry, M1 bars nor the tick tape state is on this "
                   "host", _rel(ctx.paths.universe_dir / "universe.json"),
                   _rel(ctx.paths.universe_dir) + "/*_M1.parquet", _rel(ctx.paths.tape_state))
    n_universe = len(reg) if isinstance(reg, dict) else None
    m1_new = max((p.stat().st_mtime for p in m1), default=None)
    m: dict[str, Any] = {
        "universe_symbols": n_universe, "m1_symbols": len(m1),
        "m1_coverage": (round(len(m1) / n_universe, 4) if n_universe else None),
        "m1_newest_file_age_s": (_age_s(ctx.now, datetime.fromtimestamp(m1_new, UTC))
                                 if m1_new else None)}
    tick_ok = False
    if isinstance(tape, dict):
        ages = [a for v in tape.values() if isinstance(v, dict)
                and (a := _age_s(ctx.now, _t(v.get("last_tick_utc")))) is not None]
        m.update(tick_symbols=len(ages),
                 tick_symbols_24h=sum(1 for a in ages if a <= 86400),
                 tick_newest_age_s=min(ages) if ages else None,
                 tick_age_s=_pct(ages))
        tick_ok = bool(ages) and min(ages) <= 86400
    else:
        m["ticks"] = _un("the tick tape state is absent", _rel(ctx.paths.tape_state))
    cov = m["m1_coverage"]
    return _measured([_rel(ctx.paths.universe_dir), _rel(ctx.paths.tape_state)], m,
                     not (isinstance(cov, float) and cov >= 0.5 and tick_ok))


def _pct(vals: Sequence[float]) -> dict[str, Any]:
    from libs.research import sensor_contract as sc
    return sc.percentiles(list(vals), (0.5, 0.9))


def measured_reactions(ctx: Ctx) -> dict[str, Any]:
    atlas = _json(ctx.paths.atlas)
    if not isinstance(atlas, dict):
        return _un("the event response atlas is absent on this host", _rel(ctx.paths.atlas))
    age = _age_s(ctx.now, _t(atlas.get("at")))
    cells = atlas.get("cells") or []
    m = {"n_events": atlas.get("n_events"), "n_cells": atlas.get("n_cells", len(cells)),
         "clearing": len(atlas.get("clearing") or []),
         "kinds": len(atlas.get("n_events_by_kind") or {}), "age_s": age,
         "surprise_z_events": (atlas.get("unmeasured") or {}).get("surprise_z_events")}
    sur = _json(ctx.paths.surprise)
    m["event_surprise_age_s"] = (_age_s(ctx.now, _t(sur.get("at")))
                                 if isinstance(sur, dict) else UNMEASURED)
    return _measured([_rel(ctx.paths.atlas), _rel(ctx.paths.surprise)], m,
                     not (m["clearing"] > 0 and age is not None and age < 48 * 3600))


def _is_event(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in EVENT_MARKERS)


def event_capital_authority(ctx: Ctx) -> dict[str, Any]:
    doc = _json(ctx.paths.sleeves)
    if doc is None:
        return _un("the sleeve roster is absent on this host", _rel(ctx.paths.sleeves))
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    live = [r for r in rows if str(r.get("status")).upper() == "LIVE"]
    ev_live = [r for r in live if _is_event(f"{r.get('family')} {r.get('name')}")]
    surv = _json(ctx.paths.survivors)
    cells: list[dict[str, Any]] | None = None          # None: absent or an unknown shape
    if isinstance(surv, dict):
        for key in ("survivors", "certified", "cells", "rows"):
            got = surv.get(key)
            if isinstance(got, list):
                cells = [c for c in got if isinstance(c, dict)]
                break
            if isinstance(got, dict):                  # keyed by cell id
                cells = [{**v, "_key": k} for k, v in got.items() if isinstance(v, dict)]
                break
    elif isinstance(surv, list):
        cells = [c for c in surv if isinstance(c, dict)]
    ev_cert = [c for c in cells or []
               if _is_event(f"{c.get('family')} {c.get('cell')} {c.get('name')} "
                            f"{c.get('_key')}")]
    m = {"sleeves": len(rows), "live": len(live), "event_live": len(ev_live),
         "event_live_names": [str(r.get("name")) for r in ev_live][:10],
         "certified_cells": len(cells) if cells is not None else UNMEASURED,
         "event_certified_cells": len(ev_cert) if cells is not None else UNMEASURED,
         "markers": list(EVENT_MARKERS)}
    return _measured([_rel(ctx.paths.sleeves), _rel(ctx.paths.survivors)], m,
                     not (ev_live or ev_cert))


def _watched_paths() -> list[str]:
    if str(DESK / "research") not in sys.path:
        sys.path.insert(0, str(DESK / "research"))
    try:
        import allocator_trigger as at  # type: ignore[import-not-found]
    except Exception:
        return []
    return [_rel(s.path) for s in at.sources()]


def event_allocator_reaction(ctx: Ctx) -> dict[str, Any]:
    queue = _jsonl(ctx.paths.resolve_queue)
    react = _jsonl(ctx.paths.reactions)
    if queue is None and react is None:
        return _un("neither the news re-solve queue nor the allocator's reaction log is on "
                   "this host", _rel(ctx.paths.resolve_queue), _rel(ctx.paths.reactions))
    watched = list(ctx.watched if ctx.watched is not None else _watched_paths())
    listens = any("resolve_request" in w or "resolve_queue" in w or "world_state" in w
                  for w in watched)
    since24, since7 = ctx.now - timedelta(hours=24), ctx.now - timedelta(days=7)
    q = queue or []
    q_times = [t for r in q if (t := _t(r.get("at") or r.get("enqueued_at"))) is not None]
    ev = [r for r in (react or []) if any(
        k in f"{r.get('kind')} {r.get('source')}".lower()
        for k in ("news", "event", "resolve_request", "world_state"))]
    ev7 = [r for r in ev if (_t(r.get("at")) or ctx.now - timedelta(days=30)) >= since7]
    lat = [float(r["latency_s"]) for r in ev7 if isinstance(r.get("latency_s"), int | float)]
    requests_7d = sum(1 for t in q_times if t >= since7) if queue is not None else None
    # OPEN when nothing watches the request (it is consumed by nothing), or when it is watched
    # and requests were lodged in the window with no event-triggered solve to show for them.
    # Watched with no request lodged in 7 d is closed: the wiring is there and there was nothing
    # to consume. Watched with the queue absent leans on the reaction log alone.
    if not listens:
        open_ = True
    elif requests_7d is None:
        open_ = not ev7
    else:
        open_ = requests_7d > 0 and not ev7
    m = {"requests_total": len(q) if queue is not None else UNMEASURED,
         "requests_24h": sum(1 for t in q_times if t >= since24) if queue is not None
         else UNMEASURED,
         "requests_7d": requests_7d if requests_7d is not None else UNMEASURED,
         "request_newest_age_s": _age_s(ctx.now, max(q_times, default=None)),
         "allocator_reactions_total": len(react) if react is not None else UNMEASURED,
         "event_triggered_solves_7d": len(ev7) if react is not None else UNMEASURED,
         "event_solve_latency_s": _pct(lat) if lat else UNMEASURED,
         "allocator_watches": watched,
         "allocator_listens_to_news": listens}
    return _measured([_rel(ctx.paths.resolve_queue), _rel(ctx.paths.reactions),
                      "desks/mt5/research/allocator_trigger.py:sources()"], m, open_)


def _declared_providers(paths: Paths) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    doc = _json(paths.consensus_sources)
    if isinstance(doc, dict):
        out["event_consensus_sources"] = [str(s.get("id")) for s in doc.get("sources") or []
                                          if isinstance(s, dict) and s.get("id")
                                          and not s.get("retired")]
    for p in (str(DESK), str(DESK / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from macro import sources as ms
        out["macro_official_feeds"] = [str(f[0]) for f in getattr(ms, "_OFFICIAL_FEEDS", ())]
    except Exception:
        out["macro_official_feeds"] = []
    try:
        import alt_proxies as ap  # type: ignore[import-not-found]
        out["gdelt"] = [str(x) for x in getattr(ap, "GDELT_IDS", ())]
    except Exception:
        out["gdelt"] = []
    return {k: v for k, v in out.items() if v}


def config_only_providers(ctx: Ctx) -> dict[str, Any]:
    declared = dict(ctx.providers if ctx.providers is not None
                    else _declared_providers(ctx.paths))
    if not declared:
        return _un("no provider configuration was readable on this host",
                   _rel(ctx.paths.consensus_sources), "desks/mt5/macro/sources.py")
    if not ctx.rows:
        return _un("the sensor ledger holds no row in the read window, so a configured "
                   "provider that never produced cannot be told from one not yet run",
                   _ledger_missing(ctx))
    seen = {f"{r.get('source_id')} {r.get('dataset_id')} {r.get('sensor_id')}".lower()
            for r in ctx.rows}
    store = _jsonl(ctx.paths.consensus) or []
    seen |= {str(r.get("source_id") or "").lower() for r in store}
    blob = " ".join(seen)
    norm = blob.replace("-", "_")
    only: dict[str, list[str]] = {}
    observed: dict[str, list[str]] = {}
    for group, ids in sorted(declared.items()):
        for pid in ids:
            key = pid.lower().replace("-", "_")
            (observed if key in norm else only).setdefault(group, []).append(pid)
    n_decl = sum(len(v) for v in declared.values())
    n_only = sum(len(v) for v in only.values())
    m = {"declared": n_decl, "observed": n_decl - n_only, "config_only": n_only,
         "config_only_by_group": only, "observed_by_group": observed,
         "match_rule": "a provider is observed when its id (case-insensitive) appears in a "
                       "ledger row's source_id, dataset_id or sensor_id, or in the consensus "
                       "store's source_id, inside the read window"}
    return _measured([_ledger_missing(ctx), _rel(ctx.paths.consensus_sources),
                      "desks/mt5/macro/sources.py", "desks/mt5/research/alt_proxies.py"], m,
                     n_only > 0)


AUDITS: dict[str, Callable[[Ctx], dict[str, Any]]] = {
    "news_throughput": news_throughput, "multilingual_firehose": multilingual_firehose,
    "gdelt_intake": gdelt_intake, "pit_consensus_actual": pit_consensus_actual,
    "low_latency_wire": low_latency_wire, "broad_m1_tick": broad_m1_tick,
    "measured_reactions": measured_reactions,
    "event_capital_authority": event_capital_authority,
    "event_allocator_reaction": event_allocator_reaction,
    "config_only_providers": config_only_providers,
}


def build(*, now: datetime | None = None, paths: Paths | None = None, ledger: Any = None,
          days: int = 2, providers: Mapping[str, Sequence[str]] | None = None,
          watched: Sequence[str] | None = None) -> dict[str, Any]:
    from libs.research import sensor_contract as sc
    when = now or datetime.now(UTC)
    p = paths or Paths()
    led = ledger if ledger is not None else sc.SensorLedger(p.ledger_root)
    if p.ledger_root is None:
        p.ledger_root = Path(getattr(led, "root", p.desk / "data" / "sensors"))
    day_list = [(when - timedelta(days=b)).date().isoformat() for b in range(max(1, days))]
    rows: list[dict[str, Any]] = []
    for d in day_list:
        try:
            rows.extend(led.rows(d))
        except Exception:                                # pragma: no cover - ledger guard
            continue
    ctx = Ctx(now=when, paths=p, rows=rows, ledger_days=day_list, providers=providers,
              watched=watched)
    gaps: dict[str, Any] = {}
    for name in GAPS:
        try:
            gaps[name] = {**AUDITS[name](ctx), "target": TARGETS[name]}
        except Exception as exc:
            gaps[name] = {**_un(f"the audit raised {type(exc).__name__}: {str(exc)[:160]}"),
                          "target": TARGETS[name]}
    st = Counter(g["status"] for g in gaps.values())
    return {"schema": "world_sensor_gaps/1", "at": when.isoformat(timespec="seconds"),
            "ledger_rows_read": len(rows), "ledger_days": day_list,
            "measured": st.get("MEASURED", 0), "unmeasured": st.get(UNMEASURED, 0),
            "open": sorted(k for k, g in gaps.items() if g.get("open") is True),
            "closed": sorted(k for k, g in gaps.items() if g.get("open") is False),
            "gaps": gaps,
            "rule": "each gap MEASURED from host artifacts or UNMEASURED naming what it needed; "
                    "`open` reads the number against a declared target, never sizes anything"}


def write(doc: Mapping[str, Any], out: Path = REPORT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    tmp.replace(out)
    return out
