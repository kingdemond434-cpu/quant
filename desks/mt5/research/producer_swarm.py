"""THE PRODUCER SWARM: thousands of individual producers, one per (family x asset class x chart x
session x transform), each minting only cells the sealed gauntlet can build.

THE PRINCIPAL, 2026-09-30: "it must also daily ensure that all producers produce all broad as
possible testable cells not narrow all individual producers tons thousands of them and maximise
them all fr breadth". About fifty hand-written producers mint the desk's cells, each over the
ground its author thought of. This organ is the rest of the ground, as individual producers:

    INSTANTIATED FROM DATA. `data/producer_swarm_registry.json` names the asset classes, charts,
    sessions and transforms; the families are every family the sealed gauntlet builds from a
    cell's own params (`research/gauntlet_buildability`) minus the named exclusions. One producer
    per admitted combination, with its own id (`family.class.chart.session.transform`), its own
    lane (the class's symbols that have bars on its chart and that the two-lane law lets it hunt)
    and its own quota. Nothing about the axes is written in this file.

    BUILDABLE ONLY. A combination is instantiated only when `cell_verdict` says BUILDABLE for it
    (a chart the family declares inexpressible, a transform the family would receive unapplied,
    a class book without its `symbol` -- each is counted by reason in `not_instantiated`), and
    every cell is re-checked before it is minted.

    LEAST-JUDGED FIRST, NEVER A DUPLICATE. A producer walks its lane least-judged first
    (`breadth_rotation.orthogonal_ring`, per (symbol, family), from the judge's own seen-cells
    file) at the family's defaults, then one-axis parameter moves; a cell already judged, already
    in the docket, or already minted this pass is skipped by its executable identity
    (`frontier_identity.cell_id`, the judge's own naming). When every cell a producer can reach
    exists, it says EXHAUSTED instead of minting a copy.

    HOLES FIRST, THEN THE LAP. The hour's visits start with the producers aimed at what the last
    PRODUCER_BREADTH.json names as unfed -- clusters, asset classes, charts, sessions with no cell
    in 24h -- up to `hole_visit_share` of the ceiling; then the cursor walks the whole roster,
    ceil(N / visit_lap_hours) producers an hour, so every producer is visited every day.

    THROUGH THE REGISTRY DOOR, CHARGED. Cells are written with `libs.moat.registry.
    enqueue_candidate` (generator `producer_swarm`, source_id = the producer's id), from which
    `libs.moat.docket_feed` carries them into the judge's docket; every minted cell is charged to
    the trial census in `data/PRODUCER_SWARM_TRIALS.jsonl`, per family, which
    `libs.research.experiment_ledger` sums. Each visit's outcome (minted, EXHAUSTED, NO_LANE) is
    appended to `reports/swarm/producer_swarm_visits.jsonl`, which `producer_breadth` reads
    beside the registry to measure every producer individually.

NO PERFORMANCE IS CLAIMED on any minted cell; the gauntlet attaches the only numbers that attach.

    python desks/mt5/research/producer_swarm.py --once            # the hourly leg
    python desks/mt5/research/producer_swarm.py --roster          # print the roster census only
"""
from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = BASE / "data" / "producer_swarm_registry.json"
CURSOR = BASE / "data" / "producer_swarm_cursor.json"
TRIALS = BASE / "data" / "PRODUCER_SWARM_TRIALS.jsonl"
UNIVERSE = BASE / "data" / "universe"
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
REPORT = BASE / "reports" / "PRODUCER_SWARM.json"
VISITS = BASE / "reports" / "swarm" / "producer_swarm_visits.jsonl"
BREADTH = BASE / "reports" / "PRODUCER_BREADTH.json"
SOURCE = "producer_swarm"
UNMEASURED = "UNMEASURED"
#: A docket larger than this is not parsed for dedup (the registry's content hash still dedups);
#: the report says so. Sized far above today's 76 MB so it only guards a runaway file.
DOCKET_MAX_BYTES = 1024 * 1024 * 1024
#: Visit rows kept (the visits ledger is rewritten to the last 8 days when it passes this size).
VISITS_TRIM_BYTES = 64 * 1024 * 1024


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(p)


def _append(p: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")


def load_registry(path: Path | None = None) -> dict[str, Any]:
    doc = _read(path or REGISTRY, None)
    if not isinstance(doc, dict):
        raise SystemExit(f"producer swarm registry unreadable: {path or REGISTRY}")
    return doc


# ------------------------------------------------------------------ axes
def swarm_class(symbol: str, reg: dict[str, Any]) -> str | None:
    """The registry's asset class for `symbol`, from MetaTrader's own class string."""
    try:
        from research.universe_policy import asset_class_of
        raw = str(asset_class_of(symbol) or "").strip().lower()
    except Exception:
        return None
    for klass, names in (reg.get("asset_classes") or {}).items():
        if raw in {str(n).strip().lower() for n in names}:
            return str(klass)
    return None


def bars_by_chart(charts: list[str], universe: Path | None = None) -> dict[str, set[str]]:
    root = universe or UNIVERSE
    out: dict[str, set[str]] = {}
    for tf in charts:
        suffix = f"_{tf}.parquet"
        out[tf] = {p.name[: -len(suffix)] for p in root.glob(f"*{suffix}")}
    return out


def _family_fn(fam: str) -> Any:
    from research.gauntlet_buildability import _family_table
    return _family_table().get(fam)


def swarm_families(reg: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """(families, set aside with reason): every family the sealed gauntlet builds at the
    family's own defaults, minus the registry's named exclusions."""
    from research.breadth_sweep import default_families
    from research.gauntlet_buildability import BUILDABLE, family_verdict
    ok, blocked = default_families()
    excl = dict((reg.get("families") or {}).get("exclude") or {})
    fams: list[str] = []
    aside: dict[str, str] = {}
    for fam in sorted(ok):
        if fam in excl:
            aside[fam] = f"excluded by the registry: {excl[fam]}"
            continue
        v, why = family_verdict(fam)
        if v != BUILDABLE:
            aside[fam] = f"{v}: {why}"
            continue
        fams.append(fam)
    for fam, why in blocked.items():
        aside.setdefault(fam, why)
    return fams, aside


@lru_cache(maxsize=4096)
def _transform_ok(fam: str, mods_json: str) -> str | None:
    """None when the sealed call path applies `mods` to `fam`'s signals, else the reason."""
    mods = json.loads(mods_json)
    if not mods:
        return None
    from mt5desk import cell_modifiers
    fn = _family_fn(fam)
    if fn is None:
        return "family unresolvable"
    _kwargs, moved = cell_modifiers.split(fn, mods)
    if moved != mods:
        return ("the family takes these keys natively or takes **kwargs, so the transform would "
                "reach it as an argument rather than be applied")
    return cell_modifiers.refusal(moved)


def cluster_of(fam: str) -> str:
    try:
        from libs.research.alpha_clusters import classify_family
        return str(classify_family(fam))
    except Exception:
        return UNMEASURED


def _takes_symbol(fam: str) -> bool:
    try:
        from research.gauntlet_buildability import symbol_required
        return bool(symbol_required(fam))
    except Exception:
        return False


@dataclass(frozen=True)
class Producer:
    pid: str
    family: str
    klass: str
    chart: str
    session: str
    transform: str
    mods: tuple[tuple[str, Any], ...]
    lane: tuple[str, ...]
    cluster: str
    quota: int = 1
    base: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)


def base_params(chart: str, session: str, mods: dict[str, Any]) -> dict[str, Any]:
    p: dict[str, Any] = dict(mods)
    if chart != "H1":
        p["timeframe"] = chart
    if session != "all":
        p["session"] = session
    return p


def instantiate(reg: dict[str, Any] | None = None, *,
                bars: dict[str, set[str]] | None = None) -> tuple[list[Producer], dict[str, Any]]:
    """The roster: one Producer per admitted combination, and the census of what was not."""
    from mt5desk.families_orthogonal import timeframe_refusal

    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    from research.universe_policy import may_hypothesise
    reg = reg or load_registry()
    charts = [str(c).upper() for c in reg.get("charts") or []]
    sessions = [str(s) for s in reg.get("sessions") or ["all"]]
    free = {str(c).upper() for c in reg.get("session_free_charts") or []}
    transforms = {str(k): dict(v or {}) for k, v in (reg.get("transforms") or {}).items()}
    quota = max(1, int(reg.get("min_quota_per_visit") or 1))
    bars = bars if bars is not None else bars_by_chart(charts)
    fams, aside = swarm_families(reg)
    anywhere = set().union(*bars.values()) if bars else set()
    klass_of = {s: swarm_class(s, reg) for s in sorted(anywhere)}
    classes = list((reg.get("asset_classes") or {}).keys())
    out: list[Producer] = []
    skipped: Counter[str] = Counter()
    for fam in fams:
        cl = cluster_of(fam)
        for klass in classes:
            members = [s for s, k in klass_of.items() if k == klass and may_hypothesise(s, fam)]
            if not members:
                skipped["no_class_member_the_two_lane_law_admits"] += 1
                continue
            for tf in charts:
                if timeframe_refusal(fam, tf):
                    skipped["timeframe_refused_by_family"] += 1
                    continue
                lane = tuple(sorted(s for s in members if s in bars.get(tf, set())))
                if not lane:
                    skipped["no_bars_on_chart_for_class"] += 1
                    continue
                for sess in (["all"] if tf in free else sessions):
                    for tname, mods in transforms.items():
                        why = _transform_ok(fam, json.dumps(mods, sort_keys=True))
                        if why:
                            skipped["transform_not_applicable"] += 1
                            continue
                        p = base_params(tf, sess, mods)
                        probe = {**p, "symbol": lane[0]} if _takes_symbol(fam) else p
                        v, _w = cell_verdict(fam, probe)
                        if v != BUILDABLE:
                            skipped[f"verdict_{v}"] += 1
                            continue
                        out.append(Producer(
                            pid=f"{fam}.{klass}.{tf}.{sess}.{tname}", family=fam, klass=klass,
                            chart=tf, session=sess, transform=tname,
                            mods=tuple(sorted(mods.items())), lane=lane, cluster=cl,
                            quota=quota, base=p))
    census = {"producers": len(out), "families": len(fams),
              "families_set_aside": aside, "not_instantiated": dict(sorted(skipped.items())),
              "classes": {k: sum(1 for v in klass_of.values() if v == k) for k in classes},
              "unclassified_symbols": sorted(s for s, k in klass_of.items() if k is None)[:50]}
    return sorted(out, key=lap_key), census


def lap_key(p: Producer) -> str:
    """The lap order: a STABLE PERMUTATION of the ids (their digest), so each hour's slice of the
    ring spans every family, class, chart and session instead of two alphabetical families."""
    import hashlib
    return hashlib.sha1(p.pid.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ parameter variants
@lru_cache(maxsize=512)
def _variants_json(fam: str, pv_json: str) -> str:
    pv = json.loads(pv_json)
    fn = _family_fn(fam)
    out: list[dict[str, Any]] = [{}]
    if fn is None:
        return json.dumps(out)
    try:
        params = list(inspect.signature(fn).parameters.values())[1:]
    except (TypeError, ValueError):
        return json.dumps(out)
    scale = [str(x) for x in pv.get("scale") or []]
    never = [str(x) for x in pv.get("never") or []]
    for p in params:
        d = p.default
        if p.name in ("side", "symbol") or isinstance(d, bool) or not isinstance(d, (int, float)):
            continue
        if not any(t in p.name for t in scale) or any(t in p.name for t in never):
            continue
        for f in pv.get("scales") or []:
            if isinstance(d, int):
                v: Any = max(1, int(round(d * float(f))))
            else:
                v = round(float(d) * float(f), 6)
                if 0 < float(d) < 1 and not 0 < v < 1:
                    continue
            if v != d and v > 0:
                out.append({p.name: v})
    return json.dumps(out)


def variants(fam: str, reg: dict[str, Any]) -> list[dict[str, Any]]:
    """[{}] (the family's defaults) followed by every one-axis parameter move."""
    return json.loads(_variants_json(fam, json.dumps(reg.get("param_variants") or {},
                                                     sort_keys=True)))


# ------------------------------------------------------------------ dedup context
def known_cells(families: set[str]) -> tuple[set[str], dict[str, Any]]:
    """Executable ids of every cell already judged or in the docket, for `families`."""
    from research.frontier_identity import cell_id
    ids: set[str] = set()
    info: dict[str, Any] = {}
    seen = _read(BASE / "data" / "hypotheses" / "gauntlet_seen_cells.json", None)
    if isinstance(seen, dict):
        ids |= {str(k) for k in seen}
        info["judged"] = len(seen)
    else:
        info["judged"] = f"{UNMEASURED}: gauntlet_seen_cells.json unreadable"
    try:
        size = DOCKET.stat().st_size
    except OSError:
        size = -1
    if size < 0:
        info["docket"] = f"{UNMEASURED}: {DOCKET.name} absent"
    elif size > DOCKET_MAX_BYTES:
        info["docket"] = (f"{UNMEASURED}: {DOCKET.name} is {size >> 20} MB, over the parse "
                          "ceiling; the registry's content hash still dedups")
    else:
        rows = _read(DOCKET, [])
        n = 0
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or str(r.get("family")) not in families:
                continue
            sym = r.get("symbol") or r.get("sym")
            if not sym:
                continue
            params = dict(r.get("params") or {})
            if r.get("timeframe") and "timeframe" not in params and \
                    str(r["timeframe"]).upper() != "H1":
                params["timeframe"] = str(r["timeframe"]).upper()
            with contextlib.suppress(Exception):
                ids.add(cell_id({"sym": sym, "family": r["family"], "params": params}))
                n += 1
        info["docket_rows_in_swarm_families"] = n
        del rows
    return ids, info


# ------------------------------------------------------------------ the hour's plan
def holes(doc: dict[str, Any] | None) -> dict[str, list[str]]:
    """What the last PRODUCER_BREADTH.json names as unfed, by axis."""
    t = (doc or {}).get("totals") or {}
    h = t.get("coverage_holes") or {}
    clusters = {str(u.get("cluster")) for u in t.get("empty_clusters_unfed") or []
                if isinstance(u, dict) and str(u.get("why", "")).startswith("UNMINTED")}
    clusters |= {str(c) for c in h.get("clusters") or []}
    return {"clusters": sorted(clusters),
            "asset_classes": sorted(str(x) for x in h.get("asset_classes") or []),
            "charts": sorted(str(x) for x in h.get("charts") or []),
            "sessions": sorted(str(x) for x in h.get("sessions") or [])}


def in_hole(p: Producer, h: dict[str, list[str]]) -> bool:
    return (p.cluster in h["clusters"] or p.klass in h["asset_classes"]
            or p.chart in h["charts"] or (p.session in h["sessions"] and p.session != "all"))


def plan(roster: list[Producer], reg: dict[str, Any], cursor: dict[str, Any],
         hole_axes: dict[str, list[str]], turn: int) -> dict[str, Any]:
    """The hour's visits: hole producers first (rotating), then the lap from the cursor."""
    from research.breadth_rotation import rotating_window
    n = len(roster)
    lap_h = max(1, int(reg.get("visit_lap_hours") or 24))
    ceiling = max(1, int(reg.get("hourly_cell_ceiling") or 2000))
    ring_k = math.ceil(n / lap_h) if n else 0
    hole_cells = int(ceiling * float(reg.get("hole_visit_share") or 0.0))
    floor_q = max(1, int(reg.get("min_quota_per_visit") or 1))
    # THE CEILING IS SHARED, NOT LEFT ON THE TABLE: the lap's visits divide what the holes do not
    # take, every visit minting at least the floor; the hole producers are visited at the same
    # quota, as many as their share of the ceiling pays for.
    quota = max(floor_q, (ceiling - hole_cells) // max(1, ring_k))
    pos = int(cursor.get("pos") or 0) % n if n else 0
    ring = [roster[(pos + i) % n] for i in range(min(ring_k, n))]
    in_ring = {p.pid for p in ring}
    hole_pool = [p for p in roster if in_hole(p, hole_axes) and p.pid not in in_ring]
    hole_k = hole_cells // quota
    hole = rotating_window(hole_pool, hole_k, turn=turn) if hole_k else []
    return {"hole": hole, "ring": ring, "quota": quota, "ceiling": ceiling, "ring_k": ring_k,
            "pos": pos, "lap_hours_at_this_size": (round(n / ring_k, 2) if ring_k else None),
            "hole_pool": len(hole_pool)}


# ------------------------------------------------------------------ one visit
def visit(p: Producer, quota: int, reg: dict[str, Any], known: set[str],
          counts: tuple[dict[str, int], dict[tuple[str, str], int]]) -> tuple[list[dict], str]:
    """Mint up to `quota` new, buildable cells for `p`: defaults across the lane least-judged
    first, then one-axis parameter moves. Returns (cells, outcome)."""
    from research.breadth_rotation import orthogonal_ring
    from research.frontier_identity import cell_id
    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    if not p.lane:
        return [], "NO_LANE"
    ring = orthogonal_ring(p.lane, p.family, counts=counts)
    sym_param = _takes_symbol(p.family)
    out: list[dict] = []
    for var in variants(p.family, reg):
        for sym in ring:
            params = {**var, **p.base}
            if sym_param:
                params["symbol"] = sym
            cid = cell_id({"sym": sym, "family": p.family, "params": params})
            if cid in known:
                continue
            if cell_verdict(p.family, params)[0] != BUILDABLE:
                known.add(cid)
                continue
            known.add(cid)
            out.append({"cid": cid, "symbol": sym, "params": params,
                        "variant": next(iter(var), "defaults")})
            if len(out) >= quota:
                return out, "MINTED"
    return out, ("MINTED" if out else "EXHAUSTED")


def mechanism(p: Producer, cell: dict[str, Any]) -> str:
    return (f"{p.family} on {cell['symbol']} ({p.klass}, {p.chart}, session {p.session}, "
            f"transform {p.transform}, {cell['variant']}): a breadth cell minted by swarm "
            f"producer {p.pid} for cluster {p.cluster}. No performance is claimed -- the "
            f"gauntlet attaches the only numbers that attach.")


def write_cells(minted: list[tuple[Producer, dict[str, Any]]], *, conn=None) -> dict[str, Any]:
    """Through the registry's one door, one commit per chunk. Returns counts; never raises."""
    out: dict[str, Any] = {"attempted": 0, "created": 0, "already_present": 0, "failed": 0,
                           "why": None}
    if not minted:
        return out
    try:
        from libs.moat import registry as R
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: registry unimportable ({type(exc).__name__}: {exc})"
        out["failed"] = len(minted)
        return out
    own = conn is None
    try:
        con = conn or R.connect()
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"
        out["failed"] = len(minted)
        return out
    try:
        with R.batch(con, every=1000):
            for p, c in minted:
                out["attempted"] += 1
                try:
                    _id, made = R.enqueue_candidate(
                        family=p.family, symbol=c["symbol"], params=c["params"], origin="DESK",
                        mechanism=mechanism(p, c), conn=con, chart=p.chart, session=p.session,
                        asset_class=p.klass, generator=SOURCE, source_id=p.pid,
                        trial_family=p.family, transformation=p.transform,
                        producer="desks/mt5/research/producer_swarm.py")
                except Exception:
                    out["failed"] += 1
                    continue
                out["created" if made else "already_present"] += 1
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: registry write aborted ({type(exc).__name__}: {exc})"
    finally:
        if own:
            with contextlib.suppress(Exception):
                con.close()
    return out


def _trim_visits(path: Path, now: datetime) -> None:
    try:
        if path.stat().st_size < VISITS_TRIM_BYTES:
            return
        floor = (now - timedelta(days=8)).isoformat(timespec="seconds")
        keep = [ln for ln in path.read_text("utf-8").splitlines()
                if ln.strip() and json.loads(ln).get("t", "") >= floor]
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(keep) + ("\n" if keep else ""), "utf-8")
        tmp.replace(path)
    except (OSError, ValueError):
        return


# ------------------------------------------------------------------ the run
def run(*, dry_run: bool = False, now: datetime | None = None, reg: dict[str, Any] | None = None,
        bars: dict[str, set[str]] | None = None, conn=None, out_dir: Path | None = None,
        known: set[str] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or datetime.now(UTC)
    reg = reg or load_registry()
    report = (out_dir / "PRODUCER_SWARM.json") if out_dir else REPORT
    cursor_p = (out_dir / "producer_swarm_cursor.json") if out_dir else CURSOR
    trials_p = (out_dir / "PRODUCER_SWARM_TRIALS.jsonl") if out_dir else TRIALS
    visits_p = (out_dir / "producer_swarm_visits.jsonl") if out_dir else VISITS
    roster, census = instantiate(reg, bars=bars)
    if not roster:
        doc = {"generated_at": now.isoformat(timespec="seconds"), "status": UNMEASURED,
               "why": "no producer instantiated (no buildable family, class or bars)",
               "roster": census}
        _write(report, doc)
        return doc
    from research.breadth_rotation import hour_turn, judged_counts
    cursor = _read(cursor_p, {}) or {}
    hole_axes = holes(_read(BREADTH, {}) if out_dir is None else {})
    hplan = plan(roster, reg, cursor, hole_axes, hour_turn(now))
    fams = {p.family for p in roster}
    if known is None:
        known, kinfo = known_cells(fams)
    else:
        kinfo = {"judged": "supplied", "docket": "supplied"}
    counts = judged_counts()
    minted: list[tuple[Producer, dict[str, Any]]] = []
    outcomes: Counter[str] = Counter()
    visit_rows: list[dict[str, Any]] = []
    ts = now.isoformat(timespec="seconds")
    ring_done = 0
    for lane_name, plist in (("hole", hplan["hole"]), ("ring", hplan["ring"])):
        for p in plist:
            if len(minted) >= hplan["ceiling"]:
                break
            cells, outcome = visit(p, hplan["quota"], reg, known, counts)
            outcomes[outcome] += 1
            minted += [(p, c) for c in cells]
            visit_rows.append({"t": ts, "p": p.pid, "n": len(cells), "o": outcome,
                               "via": lane_name, "s": sorted({c["symbol"] for c in cells})})
            if lane_name == "ring":
                ring_done += 1
    wrote = ({"attempted": 0, "created": 0, "already_present": 0, "failed": 0,
              "why": "dry run: nothing written"} if dry_run else write_cells(minted, conn=conn))
    by_fam: Counter[str] = Counter(p.family for p, _c in minted)
    trial_rows = [{"ts": ts, "family": f, "cells_screened": n, "source": SOURCE,
                   "rule": "every minted swarm cell is a trial of its family",
                   "dry_run": bool(dry_run)} for f, n in sorted(by_fam.items())]
    if not dry_run or out_dir is not None:
        _append(trials_p, trial_rows)
        _append(visits_p, visit_rows)
        _trim_visits(visits_p, now)
        n = len(roster)
        new_pos = (hplan["pos"] + ring_done) % n
        laps = int(cursor.get("laps") or 0) + (1 if hplan["pos"] + ring_done >= n else 0)
        _write(cursor_p, {"pos": new_pos, "laps": laps, "roster": n, "updated": ts,
                          "rule": "the next ring visit starts at roster[pos] (roster sorted by "
                                  "producer id); advances by the producers actually visited"})
    cls_cells: Counter[str] = Counter(p.klass for p, _c in minted)
    chart_cells: Counter[str] = Counter(p.chart for p, _c in minted)
    clus_cells: Counter[str] = Counter(p.cluster for p, _c in minted)
    n = len(roster)
    doc = {
        "generated_at": ts, "status": "MEASURED", "dry_run": bool(dry_run),
        "rule": ("one producer per (family x asset class x chart x session x transform) from "
                 "data/producer_swarm_registry.json; buildable cells only; least-judged first; "
                 "judged/docketed/minted cells skipped by executable id; hole producers first, "
                 "then a cursor lap of ceil(N / visit_lap_hours) an hour; written through the "
                 "registry door and charged in PRODUCER_SWARM_TRIALS.jsonl"),
        "roster": census,
        "hour": {"visits": len(visit_rows), "hole_visits": len(hplan["hole"]),
                 "ring_visits": ring_done, "ring_planned": len(hplan["ring"]),
                 "hole_pool": hplan["hole_pool"], "quota_per_visit": hplan["quota"],
                 "ceiling": hplan["ceiling"], "cursor_from": hplan["pos"],
                 "outcomes": dict(outcomes), "cells_minted": len(minted),
                 "by_family": dict(sorted(by_fam.items())), "by_class": dict(cls_cells),
                 "by_chart": dict(chart_cells), "by_cluster": dict(clus_cells)},
        "holes_targeted": hole_axes,
        "dedup": kinfo,
        "write": wrote,
        "projection": {
            "producers": n,
            "visits_per_day": min(n, hplan["ring_k"] * 24) + len(hplan["hole"]) * 24,
            "lap_hours": hplan["lap_hours_at_this_size"],
            "cells_per_day_ceiling": hplan["ceiling"] * 24,
            "cells_per_day_at_this_quota": min(hplan["ceiling"],
                                               (hplan["ring_k"] + len(hplan["hole"]))
                                               * hplan["quota"]) * 24,
            "every_producer_visited_daily": bool(hplan["ring_k"] * 24 >= n),
            "note": ("an upper bound: a producer whose reachable cells all exist mints nothing "
                     "and says EXHAUSTED; the measured figure is PRODUCER_BREADTH.json's"),
        },
        "trials_recorded": trial_rows,
        "wall_s": round(time.monotonic() - t0, 2),
    }
    _write(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one hourly pass")
    ap.add_argument("--dry-run", action="store_true", help="plan and mint, write nothing")
    ap.add_argument("--roster", action="store_true", help="print the roster census only")
    a = ap.parse_args(argv)
    if a.roster:
        roster, census = instantiate()
        by_fam = Counter(p.family for p in roster)
        print(json.dumps({**census, "by_family": dict(by_fam)}, indent=1, default=str))
        return 0
    doc = run(dry_run=a.dry_run)
    h = doc.get("hour") or {}
    print(f"producer_swarm {doc.get('status')}: {doc.get('roster', {}).get('producers')} "
          f"producers; {h.get('visits')} visited ({h.get('hole_visits')} hole, "
          f"{h.get('ring_visits')} lap); {h.get('cells_minted')} cells minted; "
          f"outcomes {h.get('outcomes')}; write {doc.get('write')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
