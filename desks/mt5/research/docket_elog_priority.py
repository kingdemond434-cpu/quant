"""THE JUDGE'S DOCKET, PRICED IN dE[log W] PER CPU-SECOND (idea 617, publisher side only).

    docket (data/hypotheses/external_survivors.json, the file the gauntlet streams)
      -> one row per gauntlet cell, keyed by `cell_id({"sym","family","params"})` -- the same
         string as the `cell` field of data/hypotheses/gate_verdict_ledger.jsonl
      -> d_elog_per_day, with its BASIS:
           MEASURED   the cell maps to a certified column of the allocator's worlds
                      (data/pf_allocator_cache/worlds.npz) AND pf_allocation.json publishes the
                      exact gradient dG/dh there: d_elog = dG/dh x STEP_HEAT (a 10bp heat step,
                      the allocator's own `next_10bp` question)
           PRIOR      family survival rate x posterior edge x (1 - |rho| to the live book); the
                      formula string rides in the row
           UNMEASURED any input missing -> null, never zero (L1.28a)
      -> cpu_s_est, with its BASIS:
           MEASURED   the sealed pre-warm cost meter's `by_family {n, s, max_s, warmed}` in
                      reports/WARM_GAUNTLET.json, s / n for the cell's family
           PRIOR      the meter exists but not for this family: median s/n across its families
           UNMEASURED no meter. compute_ledger is per LEG and is never divided down into cells.
      -> score = d_elog_per_day / cpu_s_est, null unless BOTH bases are MEASURED
      -> a per-family rollup {score_median, n_measured, basis}, complete over every cell, because
         the Judge's reader blends at family level inside allocate_by_yield

REPORT ONLY. `consumer` is null: the intended reader is the Judge's own sealed patch to
`external_gauntlet.allocate_by_yield`, reading MEASURED rows only. This organ never reorders,
trims or writes the docket; it changes nothing a sweep does until that patch lands.

Memory: the docket is streamed (it exceeded 1.5m rows once); the build box has 8 GB, so peak RSS
is measured with psutil and published.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.frontier_identity import cell_id  # noqa: E402  (the gauntlet's own import)

REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT = REPORTS / "DOCKET_ELOG_PRIORITY.json"
DOCKET = DATA / "hypotheses" / "external_survivors.json"
WORLDS = DATA / "pf_allocator_cache" / "worlds.npz"
PF_ALLOCATION = REPORTS / "pf_allocation.json"
POSTERIOR_ALPHA = REPORTS / "POSTERIOR_ALPHA.json"
WARM_REPORT = REPORTS / "WARM_GAUNTLET.json"
SLEEVES = DATA / "sleeves.json"
#: The PRIOR's inputs, by name. Survival rate is the gauntlet's own `_family_yield`, which reads
#: these two box files (survivors per RULED cell, shrunk to the house rate); posterior edge is
#: POSTERIOR_ALPHA `mu_mean`; rho is read from WORLDS.
GATES_EXTERNAL = REPORTS / "universal_gates_external.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
PRIOR_INPUTS: dict[str, tuple[Path, ...]] = {
    "survival_rate": (GATES_EXTERNAL, SURVIVORS),
    "posterior_edge": (POSTERIOR_ALPHA,),
    "rho_to_live_book": (WORLDS, SLEEVES),
}


def _input_name(key: str) -> str:
    return f"{key} ({'+'.join(p.name for p in PRIOR_INPUTS[key])})"

MEASURED, PRIOR, UNMEASURED = "MEASURED", "PRIOR", "UNMEASURED"
#: The heat step the marginal is priced at: the allocator's own `next_10bp` delta.
STEP_HEAT = 0.001
#: Per-cell rows kept (top-N by score); the family rollup is always complete.
DEFAULT_MAX_ROWS = 5000
INTENDED_CONSUMER = "external_gauntlet.allocate_by_yield (Judge sealed patch)"
PRIOR_FORMULA = "family_survival_rate x posterior_edge_R_per_day x (1 - |rho_to_live_book|)"


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _rss_mb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped]
        return float(round(psutil.Process().memory_info().rss / 1e6, 1))
    except Exception:
        return None


def _session_of(params: dict[str, Any], row: dict[str, Any]) -> str:
    for src in (params, row):
        for k in ("session", "selector", "window"):
            v = src.get(k)
            if isinstance(v, str) and v:
                return v
    return ""


# ---------------------------------------------------------------- inputs (each may be absent)

def iter_docket(path: Path) -> Iterator[Any]:
    """The docket rows, streamed with the gauntlet's own decoder when it imports."""
    try:
        from scripts.external_gauntlet import iter_json_array
    except Exception:
        pass
    else:
        yield from iter_json_array(path)
        return
    doc = json.loads(Path(path).read_text("utf-8"))
    yield from (doc if isinstance(doc, list) else [])


def docket_cells(path: Path) -> dict[str, dict[str, Any]]:
    """cell_id -> {sym, family, session}, grouped exactly as the gauntlet groups its cells."""
    out: dict[str, dict[str, Any]] = {}
    if not Path(path).exists():
        return out
    for h in iter_docket(path):
        if not isinstance(h, dict):
            continue
        sym, fam = h.get("symbol"), h.get("family")
        if not sym or not fam:
            continue
        params = dict(h.get("params") or {})
        row_tf = str(h.get("timeframe") or "").upper()
        if row_tf and row_tf != "H1" and "timeframe" not in params:
            params["timeframe"] = row_tf
        try:
            cid = cell_id({"sym": sym, "family": fam, "params": params})
        except Exception:
            continue
        if cid not in out:
            out[cid] = {"sym": str(sym), "family": str(fam), "session": _session_of(params, h)}
    return out


def load_worlds(path: Path) -> tuple[list[str], Any]:
    try:
        import numpy as np
        with np.load(path, allow_pickle=False) as z:
            names = [str(x) for x in z["names"]]
            r = np.asarray(z["r"], dtype="float64").reshape(-1, len(names))
        return names, r
    except Exception:
        return [], None


def column_for(cell: dict[str, Any], names: list[str]) -> str | None:
    """The certified worlds column this cell IS, or None. Exact `<sym>_<family>_<session>`; with no
    session on the cell, the single column carrying `<sym>_<family>_` (ambiguity maps nothing)."""
    stem = f"{cell['sym']}_{cell['family']}"
    if cell.get("session"):
        want = f"{stem}_{cell['session']}"
        return want if want in names else None
    hits = [n for n in names if n == stem or n.startswith(stem + "_")]
    return hits[0] if len(hits) == 1 else None


def family_columns(names: list[str], family: str) -> list[str]:
    return [n for n in names if f"_{family}_" in n or n.endswith(f"_{family}")]


def book_rho(names: list[str], r: Any, live: set[str]) -> dict[str, float]:
    """|corr| of each column to the live book (the sum of the OTHER live columns)."""
    out: dict[str, float] = {}
    if r is None or not names:
        return out
    import numpy as np
    book_idx = [i for i, n in enumerate(names) if n in live] or list(range(len(names)))
    total = r[:, book_idx].sum(axis=1)
    for i, n in enumerate(names):
        other = total - (r[:, i] if i in book_idx else 0.0)
        a, b = r[:, i], other
        ok = np.isfinite(a) & np.isfinite(b)
        if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
            continue
        out[n] = float(abs(np.corrcoef(a[ok], b[ok])[0, 1]))
    return out


def live_names() -> set[str]:
    rows = _json(SLEEVES).get("sleeves") or []
    return {str(r.get("name")) for r in rows
            if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"}


def gradient() -> dict[str, float]:
    gd = (_json(PF_ALLOCATION).get("growth_derivatives") or {})
    if str(gd.get("status") or "").upper() not in ("", "OK", MEASURED):
        return {}
    g = gd.get("gradient") or {}
    return {str(k): float(v) for k, v in g.items() if isinstance(v, (int, float))}


def posterior_edge() -> dict[str, float]:
    by: dict[str, list[float]] = {}
    for row in _json(POSTERIOR_ALPHA).get("sleeves") or []:
        if (isinstance(row, dict) and isinstance(row.get("mu_mean"), (int, float))
                and row.get("family")):
            by.setdefault(str(row["family"]), []).append(float(row["mu_mean"]))
    return {f: float(statistics.median(v)) for f, v in by.items()}


def survival_rate() -> dict[str, float]:
    """The gauntlet's own shrunk survivors-per-ruled-cell, by family (read, never re-derived)."""
    try:
        from scripts.external_gauntlet import _family_yield
        return {str(k): float(v) for k, v in (_family_yield() or {}).items()}
    except Exception:
        return {}


def cost_meter(path: Path) -> dict[str, dict[str, Any]]:
    """The sealed pre-warm meter's `by_family {n, s, max_s, warmed}`, wherever the report
    nests it (top level or one level down)."""
    doc = _json(path)
    cands = [doc] + [v for v in doc.values() if isinstance(v, dict)]
    for c in cands:
        bf = c.get("by_family")
        if isinstance(bf, dict) and bf:
            return {str(k): v for k, v in bf.items() if isinstance(v, dict)}
    return {}


# ---------------------------------------------------------------- the pricing

def price(cells: dict[str, dict[str, Any]], *, names: list[str], grad: dict[str, float],
          rho: dict[str, float], surv: dict[str, float], edge: dict[str, float],
          meter: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    per_cell_cpu: dict[str, float] = {}
    for fam, m in meter.items():
        n, s = m.get("n"), m.get("s")
        if isinstance(n, (int, float)) and isinstance(s, (int, float)) and n > 0:
            per_cell_cpu[fam] = float(s) / float(n)
    house_cpu = statistics.median(per_cell_cpu.values()) if per_cell_cpu else None
    fam_rho: dict[str, float | None] = {}
    rows: list[dict[str, Any]] = []
    for cid, c in cells.items():
        fam = c["family"]
        col = column_for(c, names) if grad else None
        if col is not None and col in grad:
            d, bd = grad[col] * STEP_HEAT, MEASURED
            formula = (f"dG/dh[{col}] x {STEP_HEAT} "
                       "(pf_allocation.json growth_derivatives, worlds.npz)")
        else:
            if fam not in fam_rho:
                rs = [rho[n] for n in family_columns(names, fam) if n in rho]
                fam_rho[fam] = statistics.median(rs) if rs else None
            sr, ed, rh = surv.get(fam), edge.get(fam), fam_rho[fam]
            if sr is None or ed is None or rh is None:
                d, bd = None, UNMEASURED
                missing = [_input_name(k) for k, v in (("survival_rate", sr),
                                                       ("posterior_edge", ed),
                                                       ("rho_to_live_book", rh)) if v is None]
                formula = f"{PRIOR_FORMULA}; missing: {', '.join(missing)}"
            else:
                d, bd = sr * ed * (1.0 - min(abs(rh), 1.0)), PRIOR
                formula = f"{PRIOR_FORMULA} = {sr:.6g} x {ed:.6g} x (1 - {rh:.4f})"
        if fam in per_cell_cpu:
            cpu, bc = per_cell_cpu[fam], MEASURED
        elif house_cpu is not None:
            cpu, bc = house_cpu, PRIOR
        else:
            cpu, bc = None, UNMEASURED
        # A score whenever the CPU side is MEASURED and the growth side is not UNMEASURED; its
        # basis is MEASURED only when both sides are (the Judge blends PRIOR at family level).
        score = (d / cpu if (bc == MEASURED and bd in (MEASURED, PRIOR) and d is not None
                             and cpu) else None)
        score_basis = (None if score is None else MEASURED if bd == MEASURED else PRIOR)
        rows.append({"cell": cid, "family": fam, "sym": c["sym"],
                     "d_elog_per_day": None if d is None else round(d, 10),
                     "cpu_s_est": None if cpu is None else round(cpu, 4),
                     "score": None if score is None else round(score, 12),
                     "score_basis": score_basis,
                     "basis_d_elog": bd, "basis_cpu": bc, "formula": formula})
    return rows


def rollup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by.setdefault(r["family"], []).append(r)
    out: dict[str, dict[str, Any]] = {}
    for fam, rs in sorted(by.items()):
        sc = [r["score"] for r in rs if r["score"] is not None]
        entry: dict[str, Any] = {"n_cells": len(rs), "n_scored": len(sc),
                                 "score_median": statistics.median(sc) if sc else None,
                                 "n_measured": sum(1 for r in rs
                                                   if r.get("score_basis") == MEASURED)}
        # basis_d_elog / basis_cpu are PLAIN STRINGS (the Judge's sealed reader pins them): the
        # dominant basis, a tie going to the better-evidenced one. Counts sit in basis_counts.
        entry["basis_counts"] = {}
        for key in ("basis_d_elog", "basis_cpu"):
            cnt = {b: sum(1 for r in rs if r[key] == b) for b in (MEASURED, PRIOR, UNMEASURED)}
            entry[key] = max((MEASURED, PRIOR, UNMEASURED), key=lambda b: cnt[b])
            entry["basis_counts"][key] = cnt
        out[fam] = entry
    return out


def _rank_key(r: dict[str, Any]) -> tuple[Any, ...]:
    s, d = r["score"], r["d_elog_per_day"]
    return (s is None, -(s or 0.0), d is None, -(d or 0.0), r["cell"])


def build(*, docket: Path = DOCKET, worlds: Path = WORLDS, warm: Path = WARM_REPORT,
          max_rows: int = DEFAULT_MAX_ROWS) -> dict[str, Any]:
    rss0 = _rss_mb()
    cells = docket_cells(docket)
    names, r = load_worlds(worlds)
    rho = book_rho(names, r, live_names())
    del r
    rows = price(cells, names=names, grad=gradient(), rho=rho, surv=survival_rate(),
                 edge=posterior_edge(), meter=cost_meter(warm))
    fams = rollup(rows)
    counts: dict[str, Any] = {
        k: {b: sum(1 for x in rows if x[k] == b) for b in (MEASURED, PRIOR, UNMEASURED)}
        for k in ("basis_d_elog", "basis_cpu")}
    counts["score_non_null"] = sum(1 for x in rows if x["score"] is not None)
    counts["score_basis"] = {b: sum(1 for x in rows if x["score_basis"] == b)
                             for b in (MEASURED, PRIOR)}
    rows.sort(key=_rank_key)
    kept = rows[:max_rows]
    try:
        import psutil
        total_mb = round(psutil.virtual_memory().total / 1e6, 1)
    except Exception:
        total_mb = None
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "report_only": True,
        "consumer": None,
        "intended_consumer": INTENDED_CONSUMER,
        "key": "cell_id({sym, family, params}) == gate_verdict_ledger.jsonl `cell`",
        "rule": ("score = d_elog_per_day / cpu_s_est when basis_cpu is MEASURED and basis_d_elog "
                 "is MEASURED or PRIOR, else null; score_basis is MEASURED only when both are"),
        "prior_inputs": {k: [str(p.relative_to(DESK)) for p in v]
                         for k, v in PRIOR_INPUTS.items()},
        "missing_inputs": sorted(_input_name(k) for k, v in PRIOR_INPUTS.items()
                                 if not all(p.exists() for p in v)),
        "step_heat": STEP_HEAT,
        "prior_formula": PRIOR_FORMULA,
        "inputs": {p.name: p.exists() for p in (docket, worlds, PF_ALLOCATION, POSTERIOR_ALPHA,
                                                 warm, SLEEVES)},
        "n_total": len(rows),
        "n_rows": len(kept),
        "max_rows": max_rows,
        "capped": len(rows) > len(kept),
        "basis_counts": counts,
        "families": fams,
        "rows": {x["cell"]: {k: v for k, v in x.items() if k != "cell"} for x in kept},
        "memory": {"rss_mb_start": rss0, "rss_mb_end": _rss_mb(), "total_phys_mb": total_mb},
    }


def write_atomic(doc: dict[str, Any], out: Path = OUT) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=False, default=str), "utf-8")
    os.replace(tmp, out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(max_rows=a.max_rows)
    write_atomic(doc, a.out)
    print(f"docket_elog_priority: {doc['n_total']} cells, {doc['n_rows']} rows kept, "
          f"{len(doc['families'])} families, bases {doc['basis_counts']}, "
          f"rss {doc['memory']['rss_mb_end']} MB -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
