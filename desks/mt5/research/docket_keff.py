"""DOCKET ORDER BY MARGINAL k_eff -- judge first the cells that would add an INDEPENDENT bet.

    "837 certificates behave like about 2.5 independent bets ... Order the judging docket by
     marginal k_eff (each cell's expected contribution to the book's N_eff), not family balance."
                                       -- reports/tier1_breadth_gap_2026-09-30.md, gap 1

WHAT WAS WRONG. `judge_coverage` already orders the docket, and its family ranking already has a
breadth term -- `1/(1+occupancy)` of the family's cluster in the traded book. That term is
per-FAMILY and blind to the instrument: every cross_asset_residual cell on EURUSD ranked exactly
like one on a symbol the book holds nothing correlated with. Nominal sleeves doubled (220 -> 453)
while k_eff moved 2.50 -> 2.53 because the certificates kept landing on the same exposures.

WHAT THIS ADDS. A per-cell PRIORITY, in units of effective bets:

    priority = delta_N_eff(symbol) + EMPTY_CLUSTER_BONUS [cell's cluster empty in the book]
                                   + declared orthogonality [cell's census class vacant]

`delta_N_eff` is `libs/research/effective_breadth.exposure_neff` with the cell added as one unit
of standalone risk on its instrument, minus the book as it stands, on the desk's own daily panel.
The direction a docket cell will trade is unknown until it is judged, so the cell is charged the
WORSE of long and short -- the side that stacks onto what the book already holds. That is the
same conservative choice the breadth module makes everywhere (timing and sign can only add).

The two bonuses are the report's "6 empty risk clusters" (`libs/research/alpha_clusters`, read
from `reports/EFFECTIVE_BREADTH.json` `clusters.empty_in_both`) and "vacant high-orthogonality
classes" (`libs/research/mechanism_census` classes at or above
`libs/validation/family_multiplicity.ORTHOGONALITY_FLOOR` that no certified or traded family
occupies -- the same rule `scripts/report_breadth.py` publishes). A first sleeve in an empty
cluster is worth about one whole independent bet, which is why that bonus is 1.0.

IT REORDERS AND NOTHING ELSE. No row is removed, no quota is cut, no bar moves. The priority is
read (a) INSIDE each family's stream in `judge_coverage.coverage_order`, after the never-judged and
unseen-mechanism tests, and (b) as a one-sided family factor `1 + max(0, mean priority)` in
`judge_coverage.rank_by_value`, beside the orthogonality and certificate factors -- so it can lift
a family's share of the REMAINDER and can never touch the 25% floor every family is owed.

UNMEASURED IS NEVER A DEMOTION (L1.28a). No book artifact: every cell sits at par on the
instrument axis. A symbol with no usable bars takes the MEDIAN measured delta, not zero. An
unreadable cluster or class source pays no bonus to anyone and says so in the artifact.

PUBLISHED hourly (the docket is ordered by `merge_docket`, and `judge_coverage --once` re-reads it)
to `reports/DOCKET_KEFF_ORDER.json`: the term per (family, symbol) cell key, the per-symbol
instrument deltas, the cluster and class tables with their docket target counts, and what the
judge's measured capacity head holds under the shipped order against the legacy one.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.effective_breadth import MIN_PANEL_OBS, exposure_neff  # noqa: E402

REPORTS = BASE / "reports"
BREADTH = REPORTS / "EFFECTIVE_BREADTH.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNIVERSE = BASE / "data" / "universe"
REPORT = REPORTS / "DOCKET_KEFF_ORDER.json"

#: A first sleeve in a phenomenon the book holds nothing in is about ONE independent bet -- the
#: concavity of k_eff = n/(1+(n-1)rho) makes the first member of an uncorrelated cluster worth more
#: than the next five inside an occupied one. Units are effective bets, same as delta_N_eff.
EMPTY_CLUSTER_BONUS = 1.0

#: Cell keys published in full detail. The docket is ~1.4M rows but only a few thousand distinct
#: (family, symbol) keys, and the priority is a function of the key alone, so this is every cell's
#: term unless the key count itself explodes.
MAX_KEYS_PUBLISHED = 20000


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _sym(row: Mapping[str, Any]) -> str:
    s = row.get("symbol") or row.get("sym")
    if not s:
        syms = row.get("symbols")
        if isinstance(syms, list) and syms:
            s = syms[0]
    return str(s or "").strip().upper()


def _fam(row: Mapping[str, Any]) -> str:
    return str(row.get("family") or "").strip()


def cell_key(row: Mapping[str, Any]) -> str:
    return f"{_fam(row)}|{_sym(row)}"


# --------------------------------------------------------------------------- the instrument term
def daily_returns(sym: str, universe: Path | None = None) -> Any:
    """Daily log returns (a pandas Series indexed by day) from the desk's own H1 bars, or None
    when the file is absent, unreadable, or shorter than MIN_PANEL_OBS days."""
    base = universe or UNIVERSE
    f = base / f"{sym}_H1.parquet"
    if not f.exists():
        return None
    try:
        import pandas as pd
        d = pd.read_parquet(f, columns=["close"])
        r = np.log(d["close"]).diff().dropna().resample("1D").sum()
        r = r[r != 0]
    except Exception:
        return None
    return r if len(r) >= MIN_PANEL_OBS else None


def symbol_deltas(exposure: Mapping[str, float], nominal: float, symbols: Iterable[str],
                  loader: Callable[[str], Any] = daily_returns,
                  min_obs: int = MIN_PANEL_OBS) -> dict[str, dict[str, Any]]:
    """{symbol: {delta_k, status, ...}} -- what one more unit-risk sleeve on it adds to N_eff.

    Charged the WORSE sign: min over d in (+1, -1) of N_eff(book + d*e_s) - N_eff(book), both on
    the same complete-case panel (book instruments with bars, plus s). A book instrument without
    bars leaves the panel and takes its |exposure| out of the nominal, the conservative direction.
    """
    import pandas as pd
    series: dict[str, Any] = {}

    def get(s: str) -> Any:
        if s not in series:
            series[s] = loader(s)
        return series[s]

    book = {s: float(v) for s, v in exposure.items() if float(v) != 0.0}
    have = {s: v for s, v in book.items() if get(s) is not None}
    nom = max(0.0, float(nominal) - sum(abs(v) for s, v in book.items() if s not in have))
    book_df = pd.DataFrame({s: get(s) for s in sorted(have)}).dropna() if have else None
    out: dict[str, dict[str, Any]] = {}
    for sym in sorted(set(symbols)):
        if not sym:
            continue
        r = get(sym)
        if r is None:
            out[sym] = {"status": "UNMEASURED", "delta_k": None,
                        "why": f"no {min_obs}+ day H1-derived daily series for {sym}"}
            continue
        if not have or nom <= 0.0:
            out[sym] = {"status": "MEASURED", "delta_k": 1.0, "n_obs": len(r),
                        "why": "the measured book holds no exposure: any first sleeve is one bet"}
            continue
        assert book_df is not None
        frame = (book_df if sym in book_df.columns
                 else book_df.join(r.rename(sym), how="inner")).dropna()
        if len(frame) < min_obs:
            out[sym] = {"status": "UNMEASURED", "delta_k": None, "n_obs": len(frame),
                        "why": f"{len(frame)} aligned days with the book, below {min_obs}"}
            continue
        names = list(frame.columns)
        m = frame.to_numpy(dtype="float64")
        sd = m.std(axis=0)
        if not np.all(sd > 0):
            out[sym] = {"status": "UNMEASURED", "delta_k": None, "why": "a constant column"}
            continue
        corr = np.corrcoef(m / sd, rowvar=False)
        x0 = np.array([have.get(n, 0.0) for n in names], dtype="float64")
        j = names.index(sym)
        try:
            n0 = exposure_neff(nom, x0, corr)
            n1 = []
            for d in (1.0, -1.0):
                x1 = x0.copy()
                x1[j] += d
                n1.append(exposure_neff(nom + 1.0, x1, corr))
        except ValueError as exc:
            out[sym] = {"status": "UNMEASURED", "delta_k": None, "why": str(exc)[:160]}
            continue
        others = [i for i in range(len(names)) if i != j]
        rho = (float(np.mean(np.abs(corr[j, others]))) if others else None)
        out[sym] = {"status": "MEASURED", "delta_k": round(min(n1) - n0, 6),
                    "n_eff_book": round(n0, 4), "n_eff_with_cell": round(min(n1), 4),
                    "mean_abs_rho_to_book": None if rho is None else round(rho, 4),
                    "n_obs": len(frame), "in_book": sym in have}
    return out


# --------------------------------------------------------------------- the cluster / class terms
def empty_clusters(breadth: Any) -> tuple[set[str] | None, dict[str, Any]]:
    """(empty cluster keys, occupancy table) from EFFECTIVE_BREADTH; None when unreadable."""
    if not isinstance(breadth, dict) or not isinstance(breadth.get("clusters"), dict):
        return None, {}
    cl = breadth["clusters"]
    empty = cl.get("empty_in_both")
    if not isinstance(empty, list):
        return None, {}
    occ = {"traded": cl.get("counts_traded") or {}, "certified": cl.get("counts_certified") or {}}
    return {str(c) for c in empty}, occ


def held_book_names(breadth: Any, canon: Any) -> list[str]:
    """Names of what the book holds -- certified families and traded sleeve labels."""
    names: list[str] = []
    if isinstance(canon, dict):
        for key, cert in (canon.get("survivors") or {}).items():
            if isinstance(cert, dict):
                fam = (cert.get("shadow_spec") or {}).get("family") or cert.get("family")
                names.append(str(fam or cert.get("cell") or key))
    if isinstance(breadth, dict):
        names.extend(str(k) for k in (breadth.get("sleeve_clusters") or {}))
    return names


def vacant_classes(held: list[str]) -> tuple[dict[str, float] | None, str]:
    """{census class id: declared orthogonality} for high-orthogonality classes the book lacks."""
    if not held:
        return None, "no certified or traded family readable -- vacancy is UNMEASURED"
    try:
        from libs.research import mechanism_census as census
        from libs.validation import family_multiplicity as fm
    except Exception as exc:                                          # pragma: no cover
        return None, f"census unavailable: {type(exc).__name__}"
    occupied = {fm.family_of(n) for n in held}
    vac = {c.id: float(c.orthogonality) for c in census.TAXONOMY
           if c.id not in occupied and c.orthogonality >= fm.ORTHOGONALITY_FLOOR}
    return vac, (f"{len(vac)} census class(es) at orthogonality >= {fm.ORTHOGONALITY_FLOOR} hold "
                 f"none of {len(held)} certified/traded names")


def _cluster_of(fam: str) -> str:
    try:
        from libs.research.alpha_clusters import classify_family
        return str(classify_family(fam))
    except Exception:                                                # pragma: no cover
        return "UNCLASSIFIED"


def _class_of(fam: str) -> str:
    try:
        from libs.validation.family_multiplicity import family_of
        return str(family_of(fam))
    except Exception:                                                # pragma: no cover
        return "UNCLASSIFIED"


def culture_block(culture: Any = None, *, read_artifacts: bool = True) -> dict[str, Any]:
    """The survivor k_eff with every cross-culture SAME_EDGE merge group counted ONCE, and the
    (family|symbol) keys each group spans (research/culture_orthogonality.py). Two names of one
    edge are one bet: a JP and a CN survivor that lose on the same days add 1, not 2, to the
    count the CRO reads beside k_eff. An absent or stale artifact is UNMEASURED, never a merge."""
    try:
        try:
            from research import culture_orthogonality as co
        except ImportError:                                           # pragma: no cover
            import culture_orthogonality as co  # type: ignore[import-not-found,no-redef]
    except Exception as exc:                                          # pragma: no cover
        return {"status": "UNMEASURED", "why": f"culture module: {type(exc).__name__}",
                "key_groups": {}}
    why = "culture artifact supplied by caller"
    if culture is None:
        culture, why = co.load() if read_artifacts else (None, "artifacts not read")
    return co.docket_culture(culture, why)


# ------------------------------------------------------------------------------ the whole score
def score(rows: list[dict[str, Any]], *, breadth: Any = None, canon: Any = None,
          loader: Callable[[str], Any] | None = None, key: str = "_keff",
          read_artifacts: bool = True, culture: Any = None) -> dict[str, Any]:
    """Stamp `row[key]` = priority on every row and return the evidence. Removes nothing."""
    loader = loader or daily_returns
    if read_artifacts:
        breadth = breadth if breadth is not None else _read(BREADTH)
        canon = canon if canon is not None else _read(CANON)
    cult = culture_block(culture, read_artifacts=read_artifacts)
    key_groups: dict[str, str] = cult.get("key_groups") or {}
    at = datetime.now(tz=UTC).isoformat(timespec="seconds")
    fams = sorted({_fam(r) for r in rows})
    syms = sorted({_sym(r) for r in rows} - {""})

    # instrument term
    exp = (breadth or {}).get("exposure_by_instrument") if isinstance(breadth, dict) else None
    if isinstance(exp, dict):
        nominal_raw = ((breadth.get("nominal") or {}).get("sleeves_in_the_measurement")
                       if isinstance(breadth, dict) else None)
        exposure = {str(k): float(v) for k, v in exp.items()}
        nominal = float(nominal_raw) if nominal_raw else sum(abs(v) for v in exposure.values())
        deltas = symbol_deltas(exposure, nominal, syms, loader)
        inst_status = "MEASURED"
        inst_why = (f"book of {len(exposure)} instrument(s), nominal {nominal:g}; "
                    f"{sum(1 for d in deltas.values() if d['status'] == 'MEASURED')} of "
                    f"{len(deltas)} docket symbols measured")
    else:
        exposure, nominal, deltas = {}, 0.0, {}
        inst_status = "UNMEASURED"
        inst_why = ("reports/EFFECTIVE_BREADTH.json has no exposure_by_instrument -- every cell "
                    "sits at par on the instrument axis")
    measured = [float(d["delta_k"]) for d in deltas.values() if d.get("delta_k") is not None]
    par = statistics.median(measured) if measured else 0.0

    # cluster + class terms
    empty, occ = empty_clusters(breadth)
    vac, vac_why = vacant_classes(held_book_names(breadth, canon))
    cluster_of = {f: _cluster_of(f) for f in fams}
    class_of = {f: _class_of(f) for f in fams}

    terms: dict[str, dict[str, Any]] = {}
    cl_cells: dict[str, int] = {}
    cls_cells: dict[str, int] = {}
    for row in rows:
        f, s = _fam(row), _sym(row)
        k = f"{f}|{s}"
        t = terms.get(k)
        if t is None:
            d = deltas.get(s) or {}
            inst = d.get("delta_k")
            inst_v = float(inst) if inst is not None else par
            cb = EMPTY_CLUSTER_BONUS if (empty is not None and cluster_of[f] in empty) else 0.0
            ob = float(vac.get(class_of[f], 0.0)) if vac is not None else 0.0
            t = {"family": f, "symbol": s, "cluster": cluster_of[f], "census_class": class_of[f],
                 "delta_k": round(inst_v, 6),
                 "delta_k_status": "MEASURED" if inst is not None else "PAR",
                 "empty_cluster_bonus": cb, "vacant_class_bonus": ob,
                 "priority": round(inst_v + cb + ob, 6), "cells": 0,
                 "culture_merge_group": key_groups.get(k)}
            terms[k] = t
        t["cells"] += 1
        row[key] = t["priority"]
        cl_cells[t["cluster"]] = cl_cells.get(t["cluster"], 0) + 1
        cls_cells[t["census_class"]] = cls_cells.get(t["census_class"], 0) + 1

    try:
        from libs.research.alpha_clusters import CLUSTERS
        declared = [c.key for c in CLUSTERS]
    except Exception:                                                # pragma: no cover
        declared = sorted(cl_cells)
    clusters = {c: {"empty_in_book": (c in empty) if empty is not None else None,
                    "occupancy_traded": (occ.get("traded") or {}).get(c),
                    "occupancy_certified": (occ.get("certified") or {}).get(c),
                    "docket_cells": cl_cells.get(c, 0)}
                for c in sorted(set(declared) | set(cl_cells))}
    classes = {c: {"declared_orthogonality": o, "docket_cells": cls_cells.get(c, 0)}
               for c, o in sorted((vac or {}).items())}
    fam_mean: dict[str, float] = {}
    fam_n: dict[str, int] = {}
    for t in terms.values():
        fam_mean[t["family"]] = fam_mean.get(t["family"], 0.0) + t["priority"] * t["cells"]
        fam_n[t["family"]] = fam_n.get(t["family"], 0) + t["cells"]
    family_priority = {f: round(fam_mean[f] / fam_n[f], 6) for f in fam_mean if fam_n[f]}
    return {
        "at": at,
        "rule": ("priority = delta_N_eff(symbol; worse sign, exposure_neff on the desk's daily "
                 f"panel) + {EMPTY_CLUSTER_BONUS} if the cell's alpha cluster is empty in the book "
                 "+ declared orthogonality if its census class is vacant. REORDER ONLY: read "
                 "inside each family stream after never-judged and unseen-mechanism, and as a "
                 "one-sided family factor 1+max(0, mean) on the remainder; no row dropped"),
        "instrument": {"status": inst_status, "why": inst_why, "par_delta_k": round(par, 6),
                       "book_exposure": exposure, "nominal": nominal,
                       "symbols_measured": len(measured), "symbols": len(syms)},
        "clusters_status": "MEASURED" if empty is not None else "UNMEASURED",
        "empty_clusters": sorted(empty) if empty is not None else None,
        "vacant_classes_status": "MEASURED" if vac is not None else "UNMEASURED",
        "vacant_classes_why": vac_why,
        "cluster_targets": clusters,
        "vacant_class_targets": classes,
        "family_priority": family_priority,
        "culture": {**{k: v for k, v in cult.items() if k != "key_groups"},
                    "keys_in_merge_groups": len(key_groups)},
        "rows_scored": len(rows),
        "_terms": terms,
        "_deltas": deltas,
    }


def family_factor(rows: Iterable[Mapping[str, Any]], key: str = "_keff") -> dict[str, float]:
    """One-sided family factor 1 + max(0, mean cell priority); families with no stamp absent."""
    tot: dict[str, float] = {}
    n: dict[str, int] = {}
    for r in rows:
        v = r.get(key)
        if v is None:
            continue
        f = _fam(r)
        tot[f] = tot.get(f, 0.0) + float(v)
        n[f] = n.get(f, 0) + 1
    return {f: 1.0 + max(0.0, tot[f] / n[f]) for f in tot if n[f]}


def head_census(rows: list[dict[str, Any]], n: int, terms: Mapping[str, Mapping[str, Any]]
                ) -> dict[str, Any]:
    """What the judge's first `n` rows hold: cells per cluster, empty-cluster and vacant-class
    cells, and the summed priority -- the evidence that the order moved breadth into the head."""
    head = rows[:max(int(n), 0)]
    by_cluster: dict[str, int] = {}
    empty_cells = vacant_cells = 0
    total = 0.0
    for r in head:
        t = terms.get(cell_key(r)) or {}
        c = str(t.get("cluster") or "UNCLASSIFIED")
        by_cluster[c] = by_cluster.get(c, 0) + 1
        empty_cells += 1 if t.get("empty_cluster_bonus") else 0
        vacant_cells += 1 if t.get("vacant_class_bonus") else 0
        total += float(t.get("priority") or 0.0)
    return {"rows": len(head), "cells_by_cluster": dict(sorted(by_cluster.items())),
            "empty_cluster_cells": empty_cells, "vacant_class_cells": vacant_cells,
            "priority_sum": round(total, 4),
            "priority_mean": round(total / len(head), 6) if head else None}


def publish(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    """Write the full evidence: every (family, symbol) term, the symbol deltas, the targets."""
    target = path or REPORT
    terms = sorted((doc.get("_terms") or {}).values(),
                   key=lambda t: (-float(t["priority"]), t["family"], t["symbol"]))
    out = {k: v for k, v in doc.items() if not str(k).startswith("_")}
    out["cell_terms"] = terms[:MAX_KEYS_PUBLISHED]
    out["cell_terms_total"] = len(terms)
    out["symbol_deltas"] = doc.get("_deltas") or {}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    return target


def summary(doc: Mapping[str, Any]) -> dict[str, Any]:
    """The compact block JUDGE_COVERAGE.json carries; the detail lives in DOCKET_KEFF_ORDER.json."""
    keep = ("at", "rule", "clusters_status", "empty_clusters", "vacant_classes_status",
            "vacant_classes_why", "rows_scored", "head")
    out = {k: doc.get(k) for k in keep if k in doc}
    inst = dict(doc.get("instrument") or {})
    inst.pop("book_exposure", None)
    out["instrument"] = inst
    out["report"] = "desks/mt5/reports/DOCKET_KEFF_ORDER.json"
    return out


__all__ = [
    "EMPTY_CLUSTER_BONUS",
    "REPORT",
    "cell_key",
    "daily_returns",
    "empty_clusters",
    "family_factor",
    "head_census",
    "held_book_names",
    "publish",
    "score",
    "summary",
    "symbol_deltas",
    "vacant_classes",
]
