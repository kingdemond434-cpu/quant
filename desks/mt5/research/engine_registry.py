"""THE PER-(METHOD, DOMAIN) YIELD TABLE: which engine earns its hour, in which asset class.

Tier-1 W17 asks for the half of "exploit sources and methods" that the source registry does not
cover. `source_registry` prices WHERE a lead came from; this prices HOW it was made and WHAT it
was made about. They are different questions and the desk was answering only the first: the
bandit's arms are engines, but nothing measured P(certified | method, domain), so an engine that
has never certified anything in metals and one that certifies routinely in FX were priced by the
same arm.

WHAT IS MEASURED, and from where (every input is a `{"status", "why"}` row in the report):

  n_proposed   hypothesis_graph.jsonl -- every row, by its `source` (the proposer's own name)
               and its `symbol`'s asset class. This is the desk's lineage log and it is the only
               place where a hypothesis's ENGINE and its FATE sit on the same row.
  n_compiled   research_candidates in the ROOT alpha registry, by `generator` x `asset_class`:
               a proposal that became an executable candidate.
  n_tested     graph rows with a TERMINAL fate (FAILED or CERTIFIED). A BORN row is proposed and
               not yet judged -- counting it as a failure is how a young engine gets defunded
               for being young.
  n_certified  graph rows with fate CERTIFIED.
  cost         `generator_yield.compute_s / generated` where the registry has metered the
               generator, else the compute ledger's measured wall seconds for the leg(s) the
               method runs on, divided by the proposals that leg produced. UNMEASURED otherwise.

WHY A BETA-BINOMIAL AND NOT A RATIO. At n=1 a raw ratio says 100% and a raw ratio is what makes
compute chase the last lucky hit. Every cell's rate is the posterior mean of a Beta prior set to
`PRIOR_STRENGTH` pseudo-trials of the POOLED rate across all cells -- so a cell with no trials
reports the pooled rate and says PRIOR, not 0, and a one-hit cell at n=1 is shrunk hard enough
that it cannot outrank a measured 20-in-100. The credible interval is published beside the mean
with its own n, because a wide interval is the measurement saying it does not know yet (L1.28a).

WHAT THIS IS NOT. It caps nothing, vetoes nothing and defunds nothing. Every cell carries a
strictly positive weight -- the prior guarantees it -- and the exploration share is spread over
exactly the cells with NO trials, so a never-tried (method, domain) pair is funded BECAUSE it is
unmeasured rather than starved for it. The output is a normalised weight vector that
`research_budget` can read (`shares`, keyed by leg, the same shape it already reads from
RESEARCH_BANDIT.json); making compute follow measured yield is the whole point, and nothing here
is allowed to make the desk smaller (GROWTH GOVERNANCE Rule 1/Rule 2).

    python desks/mt5/research/engine_registry.py [--once] [--budget-s N] [--dry-run]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
COMPUTE = DESK / "data" / "compute_ledger.jsonl"
SOURCE_REG = DESK / "data" / "source_registry.json"
SEAT_ROOTS = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")
REGISTRY_DB = ROOT / "data" / "alpha_registry.sqlite"
REPORT = DESK / "reports" / "ENGINE_REGISTRY.json"

#: Pseudo-trials of the pooled rate that every cell starts from. TWENTY, and the number is
#: argued rather than tuned: at PRIOR_STRENGTH=4 a single certification at n=1 posts a posterior
#: mean above a measured 20-in-100, which is precisely the failure a raw ratio has and the whole
#: reason this table is not a ratio. Twenty pseudo-trials is the smallest round strength at which
#: the measured cell wins, and it is published so a later reader can argue it with evidence.
PRIOR_STRENGTH = 20.0
#: Central credible mass published beside every posterior mean.
CRED_MASS = 0.90
#: Share of the weight vector that never follows measured yield: it is spread over cells with NO
#: trials, in proportion to how many proposals are already waiting there. This is exploration,
#: not charity -- an unmeasured cell is the only kind that can still surprise the desk (L1.52).
EXPLORATION_SHARE = 0.25
#: Cells published in full. The rest are counted, never dropped silently.
MAX_CELLS = 400
#: Rows of lineage a pass will hold in memory. DERIVED from measured free memory at ~1 KB/row,
#: floored so an unreadable counter changes nothing. Never sized off a machine's nameplate.
MIN_ROWS = 200_000
ROW_BYTES = 1024
MEM_FRACTION = 0.25

RULE = ("compute follows measured yield per (method, domain); every cell keeps a positive "
        "weight from its prior, so this ranks and never vetoes")

#: Which hourly-cycle legs a method's compute is spent on, for the cost column and for the
#: leg-keyed share vector. Declared, auditable, and never a silent guess: a method that matches
#: nothing here has an UNMEASURED cost and says so.
METHOD_LEGS: dict[str, tuple[str, ...]] = {
    "external": ("search", "sweep", "merge_docket"),
    "orthogonal_sweep": ("sweep",),
    "edge_search": ("search",),
    "miner": ("mine", "maintain_miners"),
    "deep_forest": ("deep_forest",),
    "world": ("world_crawler",),
    "world_crawler": ("world_crawler",),
    "discovery_compiler": ("compile_candidates",),
    "execution_alpha_miner": ("moat_miner",),
    "moat_miner": ("moat_miner",),
    "alpha_evolution": ("deepen",),
    "event_graph": ("causal_graph",),
    "fund_playbook": ("mine",),
    "seat": ("deepen",),
}


# ------------------------------------------------------------------------------- io helpers
def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def row_budget() -> tuple[int, str]:
    """How many lineage rows this pass may hold, from MEASURED free memory."""
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        avail = int(psutil.virtual_memory().available)
    except Exception:
        return MIN_ROWS, f"psutil unavailable; floor {MIN_ROWS:,} rows"
    n = int(avail * MEM_FRACTION / ROW_BYTES)
    if n <= MIN_ROWS:
        return MIN_ROWS, (f"{avail / 1e6:.0f} MB available -> {n:,} rows, under the "
                          f"{MIN_ROWS:,} floor; floor used")
    return n, f"{avail / 1e6:.0f} MB available at {MEM_FRACTION:.0%} and {ROW_BYTES} B/row"


# ------------------------------------------------------------------------------- beta maths
def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (Lentz). Pure python on purpose: a research
    organ that needs scipy to state a credible interval is an organ that silently stops."""
    tiny, eps = 1e-30, 3e-12
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d, h = 1.0 / d, 1.0 / d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b) -- the Beta CDF."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_quantile(a: float, b: float, q: float) -> float:
    """The q-quantile of Beta(a, b) by bisection on the CDF. 80 halvings is 1e-24 of the unit
    interval -- far finer than the number is worth, and it always terminates."""
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def posterior(k: float, n: float, alpha0: float, beta0: float) -> dict[str, Any]:
    """Beta-Binomial posterior for k successes in n trials under a Beta(alpha0, beta0) prior."""
    a, b = alpha0 + max(0.0, k), beta0 + max(0.0, n - k)
    tail = (1.0 - CRED_MASS) / 2.0
    mean = a / (a + b)
    return {
        "k": round(float(k), 4), "n": round(float(n), 4),
        "p_mean": round(mean, 8),
        "ci": [round(beta_quantile(a, b, tail), 8), round(beta_quantile(a, b, 1.0 - tail), 8)],
        "ci_mass": CRED_MASS,
        "posterior": {"alpha": round(a, 6), "beta": round(b, 6)},
        "basis": "PRIOR" if n <= 0 else ("THIN" if n < PRIOR_STRENGTH else "MEASURED"),
        "raw_ratio": (round(k / n, 8) if n > 0 else None),
    }


# ------------------------------------------------------------------------------- domains
_AC_CACHE: dict[str, str] = {}


def asset_class(symbol: str) -> str:
    """The instrument's asset class from the broker's own registry (universe_policy)."""
    sym = str(symbol or "").strip().upper()
    if not sym:
        return "UNKNOWN"
    hit = _AC_CACHE.get(sym)
    if hit is not None:
        return hit
    klass = "UNCLASSIFIED"
    try:
        from research.universe_policy import asset_class_of
        klass = str(asset_class_of(sym) or "") or "UNCLASSIFIED"
    except Exception:
        klass = "UNCLASSIFIED"
    klass = " ".join(klass.lower().replace("_", " ").split()) or "UNCLASSIFIED"
    _AC_CACHE[sym] = klass
    return klass


def domain_of(symbol: str, region: str | None) -> str:
    """`<asset class>` or `<asset class>@<region>` when the row carries a region of its own."""
    base = asset_class(symbol)
    reg = str(region or "").strip().lower()
    return f"{base}@{reg}" if reg and reg not in {"none", "null", "global"} else base


def method_of(source: str, docket: dict[tuple[str, str], str],
              symbol: str, family: str) -> str:
    """The proposing engine's name. `external` is the external-backtest screen's own label for a
    whole family of sweeps; when the docket knows which sweep produced this (symbol, family) the
    finer name wins, because 30,256 rows under one label is not a measurement of any method."""
    name = str(source or "").strip() or "UNATTRIBUTED"
    if name in {"external", "src:external", "ext"}:
        fine = docket.get((str(symbol).upper(), str(family)))
        if fine:
            return fine
    return name


def _family(method: str) -> str:
    """The method's coarse family, for cost lookup: the part before the first ':'."""
    return str(method).split(":", 1)[0].strip().lower()


# ------------------------------------------------------------------------------- inputs
def read_docket() -> tuple[dict[tuple[str, str], str], dict[str, Any]]:
    """(symbol, family) -> the proposer name the docket recorded for it."""
    rows = _read_json(DOCKET, None)
    if not isinstance(rows, list):
        return {}, {"status": "absent", "why": f"{DOCKET.name} unreadable or not a list",
                    "rows": 0}
    out: dict[tuple[str, str], str] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        src = str(r.get("source") or r.get("producer") or "").strip()
        sym, fam = str(r.get("symbol") or "").upper(), str(r.get("family") or "")
        if src and sym and fam:
            out.setdefault((sym, fam), src)
    return out, {"status": "present", "why": f"{len(rows)} docket row(s)", "rows": len(out)}


def read_graph(limit: int, deadline: float,
               docket: dict[tuple[str, str], str]) -> tuple[dict[tuple[str, str], Counter[str]],
                                                            dict[str, Any]]:
    """Per (method, domain): proposed / tested / certified, from the lineage log."""
    cells: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    if not GRAPH.exists():
        return cells, {"status": "absent", "why": f"{GRAPH.name} not on disk", "rows": 0}
    n = bad = 0
    truncated = ""
    try:
        with GRAPH.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if n >= limit:
                    truncated = f"row budget {limit:,} reached"
                    break
                if n % 2048 == 0 and time.monotonic() > deadline:
                    truncated = "wall budget spent"
                    break
                try:
                    row = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if not isinstance(row, dict):
                    bad += 1
                    continue
                n += 1
                sym, fam = str(row.get("symbol") or ""), str(row.get("family") or "")
                method = method_of(row.get("source", ""), docket, sym, fam)
                cell = cells[(method, domain_of(sym, row.get("region_code")))]
                fate = str(row.get("fate") or "").upper()
                cell["proposed"] += 1
                if fate in {"FAILED", "CERTIFIED"}:
                    cell["tested"] += 1
                if fate == "CERTIFIED":
                    cell["certified"] += 1
    except OSError as exc:
        return cells, {"status": "absent", "why": f"{type(exc).__name__}: {exc}", "rows": n}
    why = f"{n:,} lineage row(s), {bad} unparseable"
    return cells, {"status": "present", "why": (why + f"; TRUNCATED: {truncated}" if truncated
                                                else why), "rows": n, "truncated": truncated}


def read_registry() -> tuple[dict[tuple[str, str], Counter[str]], dict[str, dict[str, float]],
                             dict[str, Any]]:
    """Compiled candidates per (generator, asset class), and metered compute per generator."""
    compiled: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    metered: dict[str, dict[str, float]] = {}
    if not REGISTRY_DB.exists():
        return compiled, metered, {"status": "absent",
                                   "why": f"{REGISTRY_DB} not on disk", "rows": 0}
    try:
        from libs.moat import registry as moat_registry
        conn = moat_registry.connect()
    except Exception:
        try:
            conn = sqlite3.connect(f"file:{REGISTRY_DB}?mode=ro", uri=True, timeout=20)
        except sqlite3.Error as exc:
            return compiled, metered, {"status": "absent", "why": f"sqlite: {exc}", "rows": 0}
    n = 0
    try:
        for gen, klass, sym, cnt in conn.execute(
                "SELECT COALESCE(generator, origin, 'UNATTRIBUTED'), COALESCE(asset_class, ''), "
                "COALESCE(symbol, ''), COUNT(*) FROM research_candidates GROUP BY 1, 2, 3"):
            dom = (" ".join(str(klass).lower().replace("_", " ").split())
                   or asset_class(str(sym)))
            compiled[(str(gen), dom or "UNCLASSIFIED")]["compiled"] += int(cnt)
            n += int(cnt)
        for gen, generated, compute_s in conn.execute(
                "SELECT generator, generated, compute_s FROM generator_yield"):
            metered[str(gen)] = {"generated": float(generated or 0.0),
                                 "compute_s": float(compute_s or 0.0)}
    except sqlite3.Error as exc:
        return compiled, metered, {"status": "absent", "why": f"sqlite: {exc}", "rows": n}
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()
    return compiled, metered, {"status": "present",
                               "why": f"{n:,} candidate(s), {len(metered)} metered generator(s)",
                               "rows": n}


def read_compute() -> tuple[dict[str, float], dict[str, Any]]:
    """Measured wall seconds per hourly-cycle leg."""
    legs: dict[str, float] = defaultdict(float)
    if not COMPUTE.exists():
        return dict(legs), {"status": "absent", "why": f"{COMPUTE.name} not on disk", "rows": 0}
    n = 0
    try:
        with COMPUTE.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                leg = str(row.get("run") or row.get("leg") or "")
                if leg:
                    legs[leg] += float(row.get("wall_s") or 0.0)
                    n += 1
    except OSError as exc:
        return dict(legs), {"status": "absent", "why": f"{type(exc).__name__}: {exc}", "rows": n}
    return dict(legs), {"status": "present",
                        "why": f"{n:,} ledger row(s) over {len(legs)} leg(s)", "rows": n}


def read_seats() -> tuple[dict[str, int], dict[str, Any]]:
    """Seat/producer names under data/intelligence/** and how many donation files each holds.

    STAT ONLY. Parsing every donation to learn a seat is alive would cost more than the rest of
    this organ; a seat that has donated nothing shows 0, which is the measurement."""
    seats: dict[str, int] = {}
    roots = [p for p in SEAT_ROOTS if p.is_dir()]
    if not roots:
        return seats, {"status": "absent", "why": "no data/intelligence root on disk", "rows": 0}
    for root in roots:
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for d in entries:
            if not d.is_dir():
                continue
            try:
                seats[d.name] = seats.get(d.name, 0) + sum(1 for _ in d.glob("*.json"))
            except OSError:
                seats.setdefault(d.name, 0)
    return seats, {"status": "present",
                   "why": f"{len(seats)} seat(s) across {len(roots)} intelligence root(s)",
                   "rows": len(seats)}


def read_regions() -> tuple[dict[str, str], dict[str, Any]]:
    """source_id -> region, so a cell can carry the region its ground declared."""
    doc = _read_json(SOURCE_REG, None)
    rows = doc.get("sources") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return {}, {"status": "absent", "why": f"{SOURCE_REG.name} unreadable", "rows": 0}
    out: dict[str, str] = {}
    for sid, r in rows.items():
        if isinstance(r, dict) and r.get("region"):
            out[str(sid)] = str(r["region"])
            for alias in r.get("aliases") or []:
                out.setdefault(str(alias), str(r["region"]))
    return out, {"status": "present", "why": f"{len(out)} source(s) declare a region",
                 "rows": len(out)}


# ------------------------------------------------------------------------------- cost
def cost_per_proposal(method: str, n_proposed: int, metered: dict[str, dict[str, float]],
                      legs: dict[str, float], leg_proposals: dict[str, int]
                      ) -> tuple[float | None, str]:
    """Compute seconds one proposal of this method cost, and how that was measured."""
    m = metered.get(method) or metered.get(_family(method))
    if m and m.get("generated", 0.0) > 0 and m.get("compute_s", 0.0) > 0:
        return (round(m["compute_s"] / m["generated"], 6),
                f"generator_yield: {m['compute_s']:.1f}s over {m['generated']:.0f} generated")
    names = METHOD_LEGS.get(method) or METHOD_LEGS.get(_family(method))
    if not names:
        return None, "UNMEASURED -- no metered generator and no declared leg for this method"
    total = sum(legs.get(leg, 0.0) for leg in names)
    made = sum(leg_proposals.get(leg, 0) for leg in names)
    if total <= 0.0:
        return None, f"UNMEASURED -- legs {'+'.join(names)} carry no seconds in the ledger"
    if made <= 0:
        return None, f"UNMEASURED -- legs {'+'.join(names)} produced no attributed proposal"
    return (round(total / made, 6),
            f"compute ledger: {total:.1f}s on {'+'.join(names)} over {made:,} proposal(s)")


# ------------------------------------------------------------------------------- the table
def build(budget_s: float = 300.0) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + max(5.0, float(budget_s))
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    limit, mem_why = row_budget()

    docket, s_docket = read_docket()
    cells, s_graph = read_graph(limit, deadline, docket)
    compiled, metered, s_reg = read_registry()
    legs, s_compute = read_compute()
    seats, s_seats = read_seats()
    regions, s_regions = read_regions()

    for (gen, dom), cnt in compiled.items():
        cells[(gen, dom)]["compiled"] += int(cnt["compiled"])
    for seat, files in seats.items():
        key = (f"seat:{seat}", "UNROUTED")
        if key not in cells and not any(m.endswith(seat) for m, _ in cells):
            cells[key]["donation_files"] += int(files)

    total_tested = sum(c["tested"] for c in cells.values())
    total_cert = sum(c["certified"] for c in cells.values())
    # JEFFREYS-SMOOTHED POOLED RATE. Never 0 and never 1, so a desk that has certified nothing
    # yet still has a prior it can state rather than a division it cannot do.
    p_pool = (total_cert + 0.5) / (total_tested + 1.0)
    alpha0, beta0 = PRIOR_STRENGTH * p_pool, PRIOR_STRENGTH * (1.0 - p_pool)

    leg_proposals: dict[str, int] = defaultdict(int)
    for (method, _dom), cnt in cells.items():
        for leg in METHOD_LEGS.get(method) or METHOD_LEGS.get(_family(method)) or ():
            leg_proposals[leg] += int(cnt["proposed"])

    rows: list[dict[str, Any]] = []
    for (method, dom), cnt in cells.items():
        post = posterior(cnt["certified"], cnt["tested"], alpha0, beta0)
        cost, cost_why = cost_per_proposal(method, int(cnt["proposed"]), metered,
                                           legs, dict(leg_proposals))
        yield_h = (round(post["p_mean"] * 3600.0 / cost, 6)
                   if cost and cost > 0 else None)
        rows.append({
            "cell": f"{method}|{dom}", "method": method, "domain": dom,
            "region": regions.get(method),
            "n_proposed": int(cnt["proposed"]), "n_compiled": int(cnt["compiled"]),
            "n_tested": int(cnt["tested"]), "n_certified": int(cnt["certified"]),
            "p_certified": post,
            "cost_s_per_proposal": cost, "cost_basis": cost_why,
            "expected_yield_per_compute_hour": yield_h,
            "yield_basis": ("MEASURED" if yield_h is not None and cnt["tested"] > 0 else
                            "PRIOR" if yield_h is not None else "UNMEASURED"),
            "verdict": ("UNMEASURED -- no trial in this cell; the rate shown is the pooled prior"
                        if cnt["tested"] == 0 else
                        f"{cnt['certified']}/{cnt['tested']} judged"),
        })

    weights, wmeta = weight_vector(rows)
    for r in rows:
        r["weight"] = weights.get(r["cell"], 0.0)
    rows.sort(key=lambda r: (-(r["expected_yield_per_compute_hour"] or -1.0),
                             -r["p_certified"]["p_mean"], -r["n_tested"]))

    by_method: dict[str, dict[str, Any]] = {}
    for r in rows:
        m = by_method.setdefault(r["method"], {"n_proposed": 0, "n_compiled": 0, "n_tested": 0,
                                               "n_certified": 0, "weight": 0.0, "domains": 0})
        for k in ("n_proposed", "n_compiled", "n_tested", "n_certified"):
            m[k] += r[k]
        m["weight"] = round(float(m["weight"]) + r["weight"], 8)
        m["domains"] += 1
    for name, agg in by_method.items():
        agg["p_certified"] = posterior(agg["n_certified"], agg["n_tested"], alpha0, beta0)
        agg["legs"] = list(METHOD_LEGS.get(name) or METHOD_LEGS.get(_family(name)) or ())

    by_domain: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = by_domain.setdefault(r["domain"], {"n_proposed": 0, "n_tested": 0, "n_certified": 0,
                                               "weight": 0.0, "methods": 0})
        for k in ("n_proposed", "n_tested", "n_certified"):
            d[k] += r[k]
        d["weight"] = round(float(d["weight"]) + r["weight"], 8)
        d["methods"] += 1

    shares = leg_shares(by_method)
    report = {
        "at": now, "organ": "engine_registry", "rule": RULE,
        "sources": {"hypothesis_graph": s_graph, "docket": s_docket, "alpha_registry": s_reg,
                    "compute_ledger": s_compute, "intelligence_seats": s_seats,
                    "source_registry": s_regions},
        "prior": {"strength_pseudo_trials": PRIOR_STRENGTH, "pooled_p": round(p_pool, 8),
                  "alpha": round(alpha0, 8), "beta": round(beta0, 8),
                  "pooled_basis": f"{total_cert} certified of {total_tested} judged, "
                                  "Jeffreys-smoothed",
                  "why": ("a cell with no trials reports THIS rate and is marked PRIOR; it is "
                          "never reported as 0 and never defunded for being young")},
        "n_cells": len(rows), "n_methods": len(by_method), "n_domains": len(by_domain),
        "totals": {"n_proposed": sum(r["n_proposed"] for r in rows),
                   "n_compiled": sum(r["n_compiled"] for r in rows),
                   "n_tested": total_tested, "n_certified": total_cert},
        "cells": rows[:MAX_CELLS],
        "n_cells_published": min(len(rows), MAX_CELLS),
        "cells_note": (f"ranked by expected yield per compute hour; {max(0, len(rows) - MAX_CELLS)}"
                       " lower-ranked cell(s) counted but not printed -- their weight is in "
                       "`weights`"),
        "methods": dict(sorted(by_method.items(), key=lambda t: -float(t[1]["weight"]))),
        "domains": dict(sorted(by_domain.items(), key=lambda t: -float(t[1]["weight"]))),
        "weights": dict(sorted(weights.items(), key=lambda t: -t[1])[:MAX_CELLS]),
        "engine_weights": {m: float(a["weight"])
                           for m, a in sorted(by_method.items(),
                                              key=lambda t: -float(t[1]["weight"]))},
        "shares": shares,
        "shares_note": ("normalised over the hourly-cycle legs the measured methods run on, in "
                        "the shape research_budget already reads from RESEARCH_BANDIT.json"),
        "exploration": wmeta,
        "unmeasured": {
            "cells_without_a_trial": sum(1 for r in rows if r["n_tested"] == 0),
            "cells_without_a_cost": sum(1 for r in rows
                                        if r["cost_s_per_proposal"] is None),
            "methods_without_a_leg": sorted(m for m in by_method
                                            if not by_method[m]["legs"])[:40],
            "why": ("an absent number is a verdict here: UNMEASURED cells keep the pooled prior "
                    "and the exploration share, and are never read as zero yield (L1.28a)"),
        },
        "budget": {"budget_s": float(budget_s), "elapsed_s": round(time.monotonic() - started, 3),
                   "row_limit": limit, "row_limit_basis": mem_why},
        "growth_governance": ("evidence only: no cap, no veto, no shrink. Every cell keeps a "
                              "strictly positive weight and the unmeasured are funded BECAUSE "
                              "they are unmeasured (Rule 1/Rule 2, LAWS)"),
        "artifacts": {"report": str(REPORT)},
    }
    return report


def weight_vector(rows: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, Any]]:
    """Normalised weight per cell: yield-proportional for the measured, an exploration floor for
    the cells with no trial at all. Sums to 1; every entry is strictly positive."""
    measured = {r["cell"]: float(r["expected_yield_per_compute_hour"])
                for r in rows
                if r["n_tested"] > 0 and (r["expected_yield_per_compute_hour"] or 0.0) > 0.0}
    unmeasured = {r["cell"]: float(r["n_proposed"]) + 1.0 for r in rows if r["n_tested"] == 0}
    out: dict[str, float] = dict.fromkeys((r["cell"] for r in rows), 0.0)
    if not out:
        return out, {"regime": "EMPTY", "why": "no cell on the table"}
    if not measured:
        total = sum(unmeasured.values()) or float(len(out))
        pool = unmeasured or dict.fromkeys(out, 1.0)
        for c, v in pool.items():
            out[c] = v / total
        meta = {"regime": "PRIOR_ONLY", "exploration_share": 1.0,
                "n_measured_cells": 0, "n_unmeasured_cells": len(unmeasured),
                "why": ("no cell has both a judged trial and a measured cost, so nothing follows "
                        "yield yet and the whole vector is exploration")}
    else:
        exp_share = EXPLORATION_SHARE if unmeasured else 0.0
        tm = sum(measured.values()) or 1.0
        for c, v in measured.items():
            out[c] += (1.0 - exp_share) * v / tm
        if unmeasured:
            tu = sum(unmeasured.values()) or 1.0
            for c, v in unmeasured.items():
                out[c] += exp_share * v / tu
        meta = {"regime": "YIELD_AND_EXPLORATION", "exploration_share": exp_share,
                "n_measured_cells": len(measured), "n_unmeasured_cells": len(unmeasured),
                "why": (f"{1.0 - exp_share:.0%} follows expected yield per compute hour; "
                        f"{exp_share:.0%} is spread over cells with no trial, by how many "
                        "proposals already wait there")}
    # A cell that is neither (judged but zero-yield, or costed but untested) keeps the floor its
    # prior earns it: silent zeros are how a table becomes a veto.
    floor = 1e-9
    for c in out:
        out[c] = max(out[c], floor)
    total = sum(out.values()) or 1.0
    out = {c: round(v / total, 10) for c, v in out.items()}
    drift = round(1.0 - sum(out.values()), 10)
    if abs(drift) > 1e-12:
        top = max(out, key=lambda c: out[c])
        out[top] = round(out[top] + drift, 10)
    return out, meta


def leg_shares(by_method: dict[str, dict[str, Any]]) -> dict[str, float]:
    """The engine weights folded onto the legs those engines run on, normalised to 1."""
    legs: dict[str, float] = defaultdict(float)
    for _method, agg in by_method.items():
        names = agg.get("legs") or []
        if not names:
            continue
        w = float(agg.get("weight") or 0.0) / max(1, len(names))
        for leg in names:
            legs[leg] += w
    total = sum(legs.values())
    if total <= 0:
        return {}
    return {leg: round(v / total, 8) for leg, v in sorted(legs.items(), key=lambda t: -t[1])}


# ------------------------------------------------------------------------------- cli
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="per-(method, domain) yield table")
    ap.add_argument("--once", action="store_true", help="one pass (this organ is single-shot)")
    ap.add_argument("--budget-s", type=float, default=300.0, help="wall-clock bound, seconds")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(argv)

    rep = build(a.budget_s)
    live = sum(1 for s in rep["sources"].values() if s["status"] == "present")
    top = rep["cells"][0] if rep["cells"] else {}
    print(f"engine-registry: {rep['n_methods']} method(s) x {rep['n_domains']} domain(s) = "
          f"{rep['n_cells']} cell(s) from {live}/{len(rep['sources'])} input(s)")
    t = rep["totals"]
    print(f"  proposed {t['n_proposed']:,}  compiled {t['n_compiled']:,}  "
          f"tested {t['n_tested']:,}  certified {t['n_certified']:,}")
    print(f"  prior     Beta({rep['prior']['alpha']:.4g}, {rep['prior']['beta']:.4g}) = "
          f"{rep['prior']['pooled_p']:.6f} over {PRIOR_STRENGTH:.0f} pseudo-trials")
    if top:
        p = top["p_certified"]
        print(f"  top       {top['cell']}  p={p['p_mean']:.6f} "
              f"[{p['ci'][0]:.6f}, {p['ci'][1]:.6f}] n={p['n']:.0f} "
              f"yield/h={top['expected_yield_per_compute_hour']}")
    print(f"  weights   {rep['exploration']['regime']}; "
          f"{rep['unmeasured']['cells_without_a_trial']} cell(s) with no trial keep the prior")
    print(f"  rule      {RULE}")
    if a.dry_run:
        print(f"  --dry-run: nothing written (would have written {REPORT.name})")
        return 0
    _atomic(REPORT, json.dumps(rep, indent=1, default=str))
    try:
        from libs.ops import events
        events.emit("ENGINE_REGISTRY", leg="engine_registry", n_cells=rep["n_cells"],
                    n_methods=rep["n_methods"], regime=rep["exploration"]["regime"])
    except Exception:
        pass
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
