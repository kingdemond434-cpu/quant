"""Where the book has no edge, said precisely enough that research can go and find one.

The allocator already reports an opportunity gap -- "x% of the heat target is unfundable" -- and
the crawler reads it. That sentence has no coordinates. This gives it some:

    global=bull/high_vol | session=ASIA_MID | event=NORMAL
        sleeves with positive conditional expectancy: 0 of 50
        -> research instruction: find an orthogonal mechanism for THIS state

HOW COVERAGE IS MEASURED. Every realised trade in the shadow ledgers is labelled with the state
it was taken in, using the SAME point-in-time labellers `state_admission` uses, so a bucket's
coverage is what the book actually did there, shrunk by k_state toward the sleeve's unconditional
mean exactly as the posterior would shrink it. A bucket covered by six lucky trades is not covered.

THE INSTRUCTION IS MACHINE-READABLE. Each uncovered bucket is written into the deepening queue as
a research task naming the state, the families already tried there and what they returned, and
the families structurally absent from it. Not "Asia is thin" but "Asia + low vol + no event has
nothing that pays; carry and cross-asset residual have never been tested there".

ONLY ADMITTED DIMENSIONS ARE USED, plus the global regime. A bucket built from a dimension the
admission test has buried would be asking research to fill a hole in a map that does not exist.

THE TIMEFRAME IS AN AXIS OF THE CELL (2026-09-08), read from each sleeve's certificate rather
than assumed. Until then every bucket was implicitly H1: a state "covered" by three hourly
sleeves read as covered for the M5 book too, and a family "never tried here" could not say on
which chart. The cell is now state x family x cluster x TIMEFRAME, and the label is explicit:
`M5` where the certificate's shadow_spec names the chart, `H1` where it carries params without
one (the desk's own declared default, shadow_forward.timeframe_of), `UNSTATED` where no
certificate matches the sleeve at all -- so the denominator names what it is built on.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.state_admission import Trade, build_labeller  # noqa: E402

OUT = BASE / "reports" / "REGIME_COVERAGE.json"
QUEUE = BASE / "data" / "hypotheses" / "miner_deepening_queue.json"
K_STATE = 40.0
MIN_N = 8
COVERED_R = 0.05
DIMENSIONS = ("session", "event", "weekday")


def _family_of(sleeve: str) -> str:
    parts = str(sleeve).split("_")
    return "_".join(parts[1:-1]) if len(parts) >= 3 else (parts[1] if len(parts) == 2 else sleeve)


def _admitted() -> set[str]:
    try:
        from research.state_admission_run import OUT as ADM
        return set(json.loads(ADM.read_text("utf-8")).get("admitted") or [])
    except Exception:
        return set()


GENOME = BASE / "reports" / "ALPHA_GENOME.json"


def _cluster_map() -> dict[tuple[str, str], str]:
    """(symbol, family) -> structural cluster, from the alpha genome. Empty when not built.

    The second definition of "never tried here": a bucket where three session-breakout sleeves
    all lose has NOT tried reversion, plumbing or carry -- by cluster, not by family name, so
    two families that are the same mechanism in disguise do not count as two attempts.
    """
    try:
        doc = json.loads(GENOME.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[tuple[str, str], str] = {}
    for name, members in (doc.get("clusters") or {}).items():
        for m in members:
            g = (doc.get("genome") or {}).get(m) or {}
            if g.get("symbol") and g.get("family"):
                out[(str(g["symbol"]).upper(), str(g["family"]))] = name
    return out


def _cluster_of(sleeve: str, cmap: dict[tuple[str, str], str]) -> str | None:
    sym = str(sleeve).split("_")[0].split("|")[0].upper()
    return cmap.get((sym, _family_of(sleeve)))


CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
TIMEFRAME_DIM = "timeframe"
UNSTATED_TF = "UNSTATED"


def _timeframe_of_cert(cert: dict) -> tuple[str, str]:
    """(chart, basis) for one certificate. `basis` says HOW the label was arrived at:
    `stated` when shadow_spec.params names a timeframe, `declared_default_H1` otherwise --
    the same rule shadow_forward.timeframe_of applies when it runs the sleeve."""
    spec = cert.get("shadow_spec") or {}
    params = spec.get("params") if isinstance(spec.get("params"), dict) else {}
    tf = params.get("timeframe") or spec.get("timeframe")
    if tf:
        return str(tf).upper(), "stated"
    return "H1", "declared_default_H1"


def _timeframe_map() -> tuple[dict[tuple[str, str], str], dict[str, str], dict[str, int]]:
    """From the canon: (symbol, family) -> chart, symbol -> chart when every certificate of the
    symbol agrees, and the basis census. All empty when the canon is absent."""
    try:
        doc = json.loads(CANON.read_text("utf-8"))
    except (OSError, ValueError):
        return {}, {}, {}
    by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_sym: dict[str, set[str]] = defaultdict(set)
    basis: dict[str, int] = defaultdict(int)
    for cert in (doc.get("survivors") or {}).values():
        if not isinstance(cert, dict):
            continue
        spec = cert.get("shadow_spec") or {}
        sym = str(cert.get("sym") or spec.get("symbol") or "").upper()
        fam = str(spec.get("family") or cert.get("family") or "")
        if not sym:
            continue
        tf, how = _timeframe_of_cert(cert)
        basis[how] += 1
        by_pair[(sym, fam)].add(tf)
        by_sym[sym].add(tf)
    pair = {k: next(iter(v)) if len(v) == 1 else "AMBIGUOUS" for k, v in by_pair.items()}
    sym_only = {k: next(iter(v)) for k, v in by_sym.items() if len(v) == 1}
    return pair, sym_only, dict(basis)


def _timeframe_labeller(pair: dict[tuple[str, str], str], sym_only: dict[str, str]):
    """Trade -> chart label. A chart written into the sleeve key (`@M5`) outranks the canon,
    because that key was minted from the certificate that runs the clock; a sleeve no
    certificate matches reads UNSTATED, never H1 -- a default here would rebuild the very
    implicit-H1 denominator this axis exists to remove."""
    def fn(t: Trade) -> str:
        sleeve = str(t.sleeve)
        if "@" in sleeve:
            tag = sleeve.split("@", 1)[1]
            for sep in ("#", ".", "_", "|"):
                tag = tag.split(sep)[0]
            if tag:
                return tag.upper()
        sym = sleeve.split("_")[0].split("|")[0].upper()
        return pair.get((sym, _family_of(sleeve))) or sym_only.get(sym) or UNSTATED_TF
    return fn


def _timeframe_of_key(key: str) -> str | None:
    for part in str(key).split("|"):
        if part.startswith(f"{TIMEFRAME_DIM}="):
            return part.split("=", 1)[1]
    return None


def _global_regime_labeller():
    """Day -> global regime label from the daily fit the allocator's worlds use.

    A DESCRIPTION OF THE PAST, NOT A FORECAST. The full-fit decode is used deliberately: the
    question is "what did the book do on days the engine labels bull/high_vol", not "could the
    engine have known that day". Stated so nobody mistakes this map for a prediction.
    """
    try:
        import pandas as pd

        from libs.regime.engine import RegimeEngine
        px = pd.read_parquet(BASE / "data" / "universe" / "XAUUSD_H1.parquet", columns=["close"])
        idx = pd.to_datetime(px.index, utc=True, errors="coerce")
        c = pd.Series(px["close"].to_numpy(float), index=idx).dropna()
        c = c.groupby(c.index.date).last().iloc[-2000:]
        eng = RegimeEngine().fit(c)
        lab = {j: str(ch["label"]) for j, ch in eng.hmm_char.items()}
        by_day = {str(d): lab[int(j)] for d, j in zip(c.index, eng.hmm_states, strict=False)}
        return lambda t: by_day.get(str(t.when)[:10], "")
    except Exception:
        return None


def coverage(trades: list[Trade], dims: tuple[str, ...],
             cmap: dict[tuple[str, str], str] | None = None) -> dict:
    by_sleeve_all: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        by_sleeve_all[t.sleeve].append(t.r)
    sleeve_mean = {k: float(np.mean(v)) for k, v in by_sleeve_all.items()}
    families_all = {_family_of(t.sleeve) for t in trades}
    cmap = cmap or {}
    clusters_all = {c for t in trades if (c := _cluster_of(t.sleeve, cmap))}

    cell: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for t in trades:
        if any(not t.buckets.get(d) for d in dims):
            continue
        cell["|".join(f"{d}={t.buckets[d]}" for d in dims)][t.sleeve].append(t.r)

    out = {}
    for key, per_sleeve in sorted(cell.items()):
        rows, fams_here, clusters_here = [], set(), set()
        for sleeve, rs in per_sleeve.items():
            n = len(rs)
            if n < MIN_N:
                continue
            fam = _family_of(sleeve)
            fams_here.add(fam)
            if (c := _cluster_of(sleeve, cmap)):
                clusters_here.add(c)
            lam = n / (n + K_STATE)
            cond = lam * float(np.mean(rs)) + (1.0 - lam) * sleeve_mean[sleeve]
            rows.append({"sleeve": sleeve, "family": fam, "n": n,
                         "raw_r": round(float(np.mean(rs)), 4),
                         "shrunk_r": round(cond, 4), "covers": bool(cond >= COVERED_R)})
        rows.sort(key=lambda r: -r["shrunk_r"])
        out[key] = {"n_trades": int(sum(len(v) for v in per_sleeve.values())),
                    "n_sleeves_measured": len(rows),
                    "n_covering": sum(1 for r in rows if r["covers"]),
                    "best": rows[0] if rows else None,
                    "families_tried": sorted(fams_here),
                    "families_never_tried_here": sorted(families_all - fams_here),
                    "clusters_tried": sorted(clusters_here),
                    "clusters_never_tried_here": sorted(clusters_all - clusters_here),
                    "sleeves": rows[:12]}
    return out


def instructions(cov: dict) -> list[dict]:
    """One research task per uncovered bucket with enough trades to know it is uncovered."""
    tasks = []
    for key, c in cov.items():
        if c["n_covering"] > 0 or c["n_trades"] < MIN_N * 2:
            continue
        tried = ", ".join(f"{r['family']} {r['shrunk_r']:+.2f}R (n={r['n']})"
                          for r in c["sleeves"][:5]) or "nothing measured"
        absent = ", ".join(c["families_never_tried_here"][:8]) or "none"
        absent_cl = ", ".join(c.get("clusters_never_tried_here", [])[:6]) or "none"
        tf = _timeframe_of_key(key)
        tasks.append({
            "source": "regime_coverage", "kind": "coverage_gap",
            "title": f"No positive-expectancy mechanism in state {key}",
            "description": (f"State {key}: {c['n_trades']} realised trades, "
                            f"{c['n_sleeves_measured']} sleeves measured, none with shrunk "
                            f"conditional expectancy >= {COVERED_R}R. Tried here: {tried}. "
                            f"Families never tested in this state: {absent}. Structural "
                            f"clusters (alpha genome) never tested here: {absent_cl}. "
                            + (f"Chart: {tf} (coverage on other timeframes does not count "
                               f"here). " if tf else "")
                            + "Find an orthogonal mechanism whose economic cause is specific "
                              "to this state -- not a re-parameterisation of what already "
                              "loses here."),
            "state": key, "timeframe": tf, "families_tried": c["families_tried"],
            "families_never_tried_here": c["families_never_tried_here"],
            "clusters_never_tried_here": c.get("clusters_never_tried_here", []), "status": None,
            "consumer": "hourly/daily research brains: propose a family + params for this "
                        "state or reject with a reason",
        })
    return tasks


def _label(trades: list[Trade], dims: tuple[str, ...],
           timeframes: tuple[dict[tuple[str, str], str], dict[str, str]] | None = None,
           ) -> tuple[list[Trade], dict[str, str]]:
    gaps: dict[str, str] = {}
    fns = {}
    g = _global_regime_labeller()
    if g is None:
        gaps["global"] = "regime engine could not fit XAUUSD daily here"
    else:
        fns["global"] = g
    for d in dims:
        fn = build_labeller(d)
        if fn is None:
            gaps[d] = "no point-in-time labeller on this host"
        else:
            fns[d] = fn
    if timeframes is not None:
        # The chart axis always labels: a sleeve without a certificate reads UNSTATED, which is
        # a bucket of its own rather than a trade dropped from the map.
        fns[TIMEFRAME_DIM] = _timeframe_labeller(*timeframes)
    out = []
    for t in trades:
        b = {d: v for d, fn in fns.items() if (v := fn(t))}
        out.append(Trade(t.sleeve, t.when, t.r, b))
    return out, gaps


def run(write_queue: bool = True) -> dict:
    from research.state_admission_run import load_trades

    admitted = _admitted()
    dims = tuple(d for d in DIMENSIONS if d in admitted)
    trades = load_trades("shadow")
    pair_tf, sym_tf, tf_basis = _timeframe_map()
    labelled, gaps = _label(trades, dims, (pair_tf, sym_tf))
    if not pair_tf:
        gaps["timeframe_certificates"] = (f"{CANON.name} absent or empty; every sleeve reads "
                                          f"timeframe={UNSTATED_TF}")
    # THE CHART IS ALWAYS AN AXIS. It is not an admitted state dimension (nothing about the
    # market is being conditioned on) but a property of the sleeve, so it joins the key after
    # the state dimensions and never goes through the admission gauntlet.
    used = (*(d for d in ("global", *dims) if d not in gaps), TIMEFRAME_DIM)
    cmap = _cluster_map()
    if not cmap:
        gaps["alpha_genome"] = "ALPHA_GENOME.json absent; cluster coverage not computed"
    cov = coverage(labelled, used, cmap)
    tasks = instructions(cov)
    tf_sleeves: dict[str, set[str]] = defaultdict(set)
    for t in labelled:
        tf_sleeves[t.buckets.get(TIMEFRAME_DIM, UNSTATED_TF)].add(t.sleeve)
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "dimensions": list(used),
           "n_clusters_known": len(set(cmap.values())),
           "admitted_dimensions": sorted(admitted), "gaps": gaps, "n_trades": len(trades),
           "n_buckets": len(cov), "n_uncovered": len(tasks),
           "uncovered": [t["state"] for t in tasks],
           # The denominator, stated: which charts the sleeves sit on and how each label was
           # reached (`stated` from the certificate, `declared_default_H1` by the desk's own
           # rule, UNSTATED where no certificate matches).
           "timeframes": {tf: len(s) for tf, s in sorted(tf_sleeves.items())},
           "timeframe_basis": {**tf_basis,
                               "sleeves_unstated": len(tf_sleeves.get(UNSTATED_TF, ()))},
           "coverage": cov}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    if write_queue and tasks:
        _merge_into_queue(tasks)
    doc["instructions"] = tasks
    return doc


def _merge_into_queue(tasks: list[dict], source: str = "regime_coverage") -> None:
    """Replace ONE source's tasks in the deepening queue; the worker already reads it hourly.

    Shared by every feedback engine that writes research instructions (coverage, excursions,
    opportunity curve): each owns exactly its own rows, keyed on `source`, so a rerun replaces
    rather than accumulates, and no engine can delete another's tasks.
    """
    try:
        doc = json.loads(QUEUE.read_text("utf-8"))
    except (OSError, ValueError):
        doc = {"tasks": []}
    rows = doc.get("tasks") if isinstance(doc, dict) else doc
    rows = [r for r in (rows if isinstance(rows, list) else [])
            if not (isinstance(r, dict) and r.get("source") == source)]
    rows.extend(tasks)
    if isinstance(doc, dict):
        doc["tasks"] = rows
        doc[f"{source}_tasks_at"] = datetime.now(tz=UTC).isoformat()
    else:
        doc = rows
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text(json.dumps(doc, indent=1, default=str), "utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args()
    doc = run(write_queue=not a.no_queue)
    print(f"REGIME COVERAGE  dims={doc['dimensions']}  {doc['n_trades']} trades, "
          f"{doc['n_buckets']} buckets, {doc['n_uncovered']} uncovered")
    for key, c in list(doc["coverage"].items())[:24]:
        b = c["best"]
        print(f"  {key:52s} n={c['n_trades']:4d} covering={c['n_covering']:2d} "
              + (f"best={b['sleeve'][:26]} {b['shrunk_r']:+.3f}R" if b else "best=-"))
    for g, why in doc["gaps"].items():
        print(f"  GAP {g}: {why}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
