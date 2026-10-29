"""CRO D18, MEASURED ON READS: how many datasets on this box no consumer actually read.

THE DUTY (docs/cro/CRO_CYCLE.md D18, "No unfed datasets", target 0) read MISSED every pass because
no organ published an `unfed_datasets` number. This organ publishes it every hour, and it counts
on the strictest evidence the desk has: a RECORDED READ (`libs/data/dataset_use`) by a consumer,
with the version it saw, inside the last `STALE_AFTER_S`. Listed, fetched, parsed and "cells
emitted" are all weaker states and none of them counts as fed here.

THE UNIVERSE, read from disk every pass (never a hand list):

    acquired:<series>   every series in `data/acquired/registry.json` (acquire_datasets)
    axis:<id>           every `data/axes/*.json` (the axis door: alt_proxies, macro, packs)
    lake:<stem>         every `data/lake/series/*.{csv,parquet}` (the lake's PIT envelope)

STATUS per dataset:

    FED          at least one consumer read it inside the window; its uses are listed
    STALE        it was read once, but not inside the window
    UNFED        no recorded read at all

`unfed_datasets` = UNFED + STALE. A dataset kind whose readers record nothing yet is not excused:
it reads UNFED, because "nobody can show they read it" is exactly the defect the duty names.
Before the readers that record (PR #192) reach the box, every dataset reads UNFED -- that is the
measurement, not an outage.

INFORMATION VALUE PER DATA COST (audit row ROMAN-1003, 2026-10-06). The same pass prices every
acquired series: does it carry information the desk does not already hold, what has it earned
downstream, and what did it cost to obtain?

    novelty        1 - max R^2 of its monthly changes against every other held acquired series
                   (pairwise-complete, >= NOVELTY_MIN_OVERLAP months). A series that is a copy
                   of one already held reads near 0; an orthogonal one near 1.
    outcome        gauntlet-credited survivors for the dataset from RESEARCH_ROI.json's
                   `dataset_roi`, or UNMEASURED by name. Never estimated here.
    cost           measured: bytes and fetch seconds per visit from the acquirer's registry.
    novelty_per_fetch_s   the ranking key. The acquirer's binding resource is its pass time.

NOVELTY NEVER LOOKS AT A RETURN. Whether information changes the conditional distribution of a
TRADED instrument is a test, every such look is a trial charged to the family-wise budget, and it
belongs to the gauntlet, whose verdicts come back as `outcome`. A pre-screen against returns here
would spend that budget off the books. So the value side is split honestly: novelty (free, no
trial) and credited outcome (paid for, by the gauntlet). The unfed list is ordered by novelty, so
a reader added to close D18 feeds the most informative series first.

THE SOURCE LEDGER (DATA-07, 2026-10-07). The same pass publishes one row per source / dataset /
version in `reports/DATASET_LEDGER.json` (+ a committed digest): access state, coverage, history
depth, the fields it cannot fill (by name), PIT status, latest release and ingestion, freshness
against its own cadence, consumers and last consumption, features minted from it, credited
outcomes, NON-CELL utility (reads in any use but `new_hypotheses`), cost, the first blocker, the
contract's acquisition method / licence / production eligibility / provenance (DATA-38), and
BASELINE vs BASELINE+DATA: where the one gauntlet judged a conditioned child AND its unconditioned
parent (`params.conditioner` naming the dataset), the verdict delta is published; everywhere else
it is UNMEASURED by name. The stage chain and PIT stamp of the registry sources are read from
`source_drain`'s own chain state, never re-derived.

THE TARGET IS 0 AND THE FIX IS A READER, NEVER A DELETION. Retiring a dataset to improve this
number is the museum the principal forbade in the other direction; the list is the work queue.

    python desks/mt5/research/dataset_use_census.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from libs.data import dataset_use as U  # noqa: E402

ACQUIRED = DESK / "data" / "acquired" / "registry.json"
AXES = DESK / "data" / "axes"
LAKE = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "DATASET_USE.json"
#: The small COMMITTED copy (reports/ is gitignored): counts plus the oldest unfed ids, so the
#: cloud and the CRO pass can read D18 without the box.
DIGEST = DESK / "data" / "digests" / "dataset_use_digest.json"
DIGEST_LIST = 200
RESEARCH_ROI = DESK / "reports" / "RESEARCH_ROI.json"
LEDGER_REPORT = DESK / "reports" / "DATASET_LEDGER.json"
LEDGER_DIGEST = DESK / "data" / "digests" / "dataset_ledger_digest.json"
CHAIN_STATE = DESK / "data" / "source_chain_state.json"
DRAIN_REPORT = DESK / "reports" / "SOURCE_DRAIN.json"
ASIA_SOURCES = DESK / "data" / "asia_sources.json"
GENOMES = DESK / "data" / "feature_genome" / "genomes.json"
CONTRACTS_STORE = DESK / "data" / "feature_genome" / "contracts.json"
GATE_VERDICTS = DESK / "reports" / "universal_gates_external.json"
#: The fields a ledger row owes, in order. One left UNMEASURED is named in `missing_fields`.
LEDGER_FIELDS: tuple[str, ...] = (
    "source", "version", "access_state", "coverage", "history_depth_days", "pit_status",
    "latest_release", "latest_ingestion", "freshness", "consumers", "last_consumption",
    "features", "outcomes", "non_cell_utility", "cost", "acquisition_method", "licence",
    "production_eligible", "provenance", "baseline_vs_data")
#: Hours a dataset may go unrefreshed: three times its own cadence (source_drain's rule).
CADENCE_WINDOW_H = {"realtime": 3.0, "intraday": 18.0, "daily": 144.0, "weekly": 1_008.0,
                    "monthly": 4_320.0, "quarterly": 12_960.0, "irregular": 6_480.0}
NON_CELL_USES = tuple(u for u in U.USES if u != "new_hypotheses")
NOVELTY_MIN_OVERLAP = 24
UNMEASURED = "UNMEASURED"
#: Bound on the pairwise novelty pass: series beyond it read UNMEASURED by name, never 1.0.
NOVELTY_MAX_SERIES = 4000


def universe(acquired: Path = ACQUIRED, axes: Path = AXES, lake: Path = LAKE) -> dict[str, str]:
    """dataset id -> kind, for everything on disk."""
    out: dict[str, str] = {}
    try:
        reg = json.loads(acquired.read_text("utf-8"))
        for name in (reg.get("series") or {}):
            out[f"acquired:{name}"] = "acquired"
    except (OSError, ValueError, AttributeError):
        pass
    for p in sorted(axes.glob("*.json")) if axes.exists() else []:
        out[f"axis:{p.stem}"] = "axis"
    if lake.exists():
        for p in sorted(lake.iterdir()):
            if p.suffix in (".csv", ".parquet") and not p.name.startswith("."):
                out[f"lake:{p.stem}"] = "lake"
    return out


def _monthly_changes(path: str) -> pd.Series | None:
    """Month-end first-seen values, differenced. Panels (repeated index) are not one series."""
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if "value" not in df.columns or not df.index.is_unique:
        return None
    v = pd.to_numeric(df["value"], errors="coerce")
    try:
        v.index = pd.to_datetime(v.index, utc=True)
    except (TypeError, ValueError):
        return None
    m = v.dropna().resample("ME").last().dropna()
    d = m.diff().dropna()
    return d if len(d) >= NOVELTY_MIN_OVERLAP and float(d.std()) > 0 else None


def novelty(changes: dict[str, pd.Series]) -> dict[str, dict[str, Any]]:
    """1 - max pairwise-complete R^2 against every other series, with the nearest twin named."""
    names = sorted(changes)
    if len(names) < 2:
        return {n: {"novelty": None, "status": "UNMEASURED",
                    "why": "fewer than two comparable series held"} for n in names}
    frame = pd.DataFrame({n: changes[n] for n in names})
    x = frame.to_numpy(dtype=float)
    mask = ~np.isnan(x)
    m = mask.astype(float)
    x0 = np.where(mask, x, 0.0)
    n_ij = m.T @ m
    sx = x0.T @ m                                    # sum of x_i over the overlap with j
    sxx = (x0 * x0).T @ m
    sxy = x0.T @ x0
    with np.errstate(divide="ignore", invalid="ignore"):
        cov = sxy - sx * sx.T / n_ij
        vx = sxx - sx * sx / n_ij
        r = cov / np.sqrt(vx * vx.T)
    r2 = np.where((n_ij >= NOVELTY_MIN_OVERLAP) & np.isfinite(r), r * r, np.nan)
    np.fill_diagonal(r2, np.nan)
    out: dict[str, dict[str, Any]] = {}
    for i, n in enumerate(names):
        row = r2[i]
        if np.all(np.isnan(row)):
            out[n] = {"novelty": None, "status": "UNMEASURED",
                      "why": f"no other series overlaps it by {NOVELTY_MIN_OVERLAP} months"}
            continue
        j = int(np.nanargmax(row))
        out[n] = {"novelty": round(1.0 - float(row[j]), 4), "status": "MEASURED",
                  "nearest": names[j], "nearest_r2": round(float(row[j]), 4),
                  "compared": int(np.sum(~np.isnan(row)))}
    return out


def _outcomes(path: Path) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    roi = doc.get("dataset_roi") if isinstance(doc, dict) else None
    return roi if isinstance(roi, dict) else {}


def information_value(acquired: Path = ACQUIRED,
                      research_roi: Path = RESEARCH_ROI) -> dict[str, dict[str, Any]]:
    """Per acquired dataset: novelty, credited outcome and measured cost (ROMAN-1003)."""
    try:
        reg = json.loads(acquired.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    series = reg.get("series") or {}
    by_url = reg.get("by_url") or {}
    eligible = sorted(series, key=lambda n: str((series[n] or {}).get("refreshed_at") or ""),
                      reverse=True)
    changes: dict[str, pd.Series] = {}
    for name in eligible[:NOVELTY_MAX_SERIES]:
        ch = _monthly_changes(str((series[name] or {}).get("path") or ""))
        if ch is not None:
            changes[name] = ch
    nov = novelty(changes)
    outcomes = _outcomes(research_roi)
    out: dict[str, dict[str, Any]] = {}
    for name, meta in series.items():
        meta = meta or {}
        url_row = by_url.get(str(meta.get("url") or "")) or {}
        n_series = max(len(url_row.get("series") or []), 1)
        visits = int(url_row.get("visits") or 0)
        fetch_s = (float(url_row["fetch_s_total"]) / visits / n_series
                   if visits and url_row.get("fetch_s_total") is not None else None)
        mb = (float(url_row["bytes"]) / 1e6 / n_series
              if url_row.get("bytes") is not None else None)
        nv = nov.get(name) or {"novelty": None, "status": "UNMEASURED",
                               "why": ("beyond the novelty bound" if name not in changes and
                                       name in eligible[NOVELTY_MAX_SERIES:] else
                                       "fewer than 24 monthly changes, or a panel")}
        oc = outcomes.get(name) or outcomes.get(str(meta.get("url") or ""))
        row: dict[str, Any] = {
            **nv,
            "outcome": ({"survivor_credit": oc.get("survivor_credit"),
                         "discoveries": oc.get("discoveries"), "status": "MEASURED"}
                        if isinstance(oc, dict) else
                        {"status": "UNMEASURED", "why": "no RESEARCH_ROI dataset row names it"}),
            "cost": {"mb_per_visit": round(mb, 6) if mb is not None else None,
                     "fetch_s_per_visit": round(fetch_s, 4) if fetch_s is not None else None,
                     "status": "MEASURED" if fetch_s is not None else "UNMEASURED"},
        }
        if nv.get("novelty") is not None and fetch_s is not None:
            row["novelty_per_fetch_s"] = round(float(nv["novelty"]) / max(fetch_s, 0.05), 4)
        out[f"acquired:{name}"] = row
    return out


def build(now: datetime | None = None, *, use_root: Path | None = None,
          acquired: Path = ACQUIRED, axes: Path = AXES, lake: Path = LAKE,
          research_roi: Path = RESEARCH_ROI) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    held = universe(acquired, axes, lake)
    value = information_value(acquired, research_roi)
    reads = U.census(use_root, now=now)
    rows: list[dict[str, Any]] = []
    for ds, kind in sorted(held.items()):
        e = reads.get(ds)
        if e and e["live_consumers"] > 0:
            status = "FED"
        elif e:
            status = "STALE"
        else:
            status = "UNFED"
        rows.append({"dataset": ds, "kind": kind, "status": status,
                     "uses": (e or {}).get("uses", []),
                     "consumers": sorted((e or {}).get("consumers", {}))})
    by_kind: dict[str, dict[str, int]] = {}
    for r in rows:
        k = by_kind.setdefault(r["kind"], {"held": 0, "fed": 0, "unfed": 0})
        k["held"] += 1
        k["fed" if r["status"] == "FED" else "unfed"] += 1
    by_use: dict[str, int] = dict.fromkeys(U.USES, 0)
    for r in rows:
        for u in r["uses"]:
            by_use[u] = by_use.get(u, 0) + 1
    def _nov(r: dict[str, Any]) -> float:
        v = (value.get(r["dataset"]) or {}).get("novelty")
        return -1.0 if v is None else float(v)
    # The work queue: the most novel unfed series first, unmeasured ones after the measured.
    unfed = sorted((r for r in rows if r["status"] != "FED"), key=lambda r: -_nov(r))
    measured = [v for v in value.values() if v.get("novelty") is not None]
    ranked = sorted(((k, v) for k, v in value.items() if "novelty_per_fetch_s" in v),
                    key=lambda kv: -float(kv[1]["novelty_per_fetch_s"]))
    orphan_reads = sorted(set(reads) - set(held))
    led = ledger(rows, value, reads, now, acquired=acquired, axes=axes, lake=lake)
    return {
        "ledger": led, "ledger_summary": ledger_summary(led),
        "measured_at": now.isoformat(timespec="seconds"),
        "duty": "CRO D18 -- no unfed datasets",
        "unfed_datasets": len(unfed),
        "target": 0,
        "datasets_held": len(rows),
        "fed": len(rows) - len(unfed),
        "by_kind": by_kind,
        "fed_by_use": by_use,
        "unfed": [{"dataset": r["dataset"], "kind": r["kind"], "status": r["status"],
                   "novelty": (value.get(r["dataset"]) or {}).get("novelty")}
                  for r in unfed],
        "information_value": {
            "row": "ROMAN-1003: incremental information per unit of data cost",
            "measured": len(measured), "unmeasured": len(value) - len(measured),
            "median_novelty": (round(float(np.median([v["novelty"] for v in measured])), 4)
                               if measured else None),
            "near_duplicates": sum(1 for v in measured if v["novelty"] < 0.05),
            "outcome_measured": sum(1 for v in value.values()
                                    if v["outcome"]["status"] == "MEASURED"),
            "top_per_cost": [{"dataset": k, **v} for k, v in ranked[:50]],
            "rule": ("novelty never reads a return: a conditional-distribution test on a traded "
                     "instrument is a trial and belongs to the gauntlet, whose credit returns "
                     "here as `outcome`"),
        },
        "information_value_by_dataset": value,
        "fed_rows": [r for r in rows if r["status"] == "FED"],
        "reads_of_datasets_not_on_disk": orphan_reads[:200],
        "evidence": ("a recorded consumer read (libs/data/dataset_use) inside "
                     f"{U.STALE_AFTER_S // 3600}h; listing, fetching, parsing and emitting cells "
                     "are weaker states and do not count as fed"),
    }


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _ts(value: Any) -> datetime | None:
    try:
        t = pd.Timestamp(str(value))
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    return (t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")).to_pydatetime()


def _feature_counts(path: Path = GENOMES) -> dict[str, int] | None:
    doc = _read(path, None)
    rows = doc.get("genomes") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return None
    out: dict[str, int] = {}
    for row in rows.values():
        if isinstance(row, dict) and row.get("dataset"):
            out[str(row["dataset"])] = out.get(str(row["dataset"]), 0) + 1
    return out


def _chain_rows() -> dict[str, dict[str, Any]]:
    """source_drain's per-source chain (its own report rows, else its committed chain state)."""
    rows = (_read(DRAIN_REPORT, {}) or {}).get("rows")
    if isinstance(rows, list) and rows:
        return {str(r.get("id")): r for r in rows if isinstance(r, dict) and r.get("id")}
    by = (_read(CHAIN_STATE, {}) or {}).get("by_source")
    return {str(k): dict(v) for k, v in by.items()} if isinstance(by, dict) else {}


def baseline_deltas(path: Path = GATE_VERDICTS) -> dict[str, list[dict[str, Any]]]:
    """dataset -> [child vs parent verdict pairs] where the gauntlet judged BOTH the cell
    conditioned on the dataset and the same cell without it. Pairs only on exact equality of
    family, symbol and every other parameter -- a delta against a different cell is not one."""
    doc = _read(path, {})
    verdicts = [v for v in (doc.get("verdicts") or []) if isinstance(v, dict)
                and not v.get("unmeasured")] if isinstance(doc, dict) else []
    def _key(v: dict[str, Any]) -> str:
        p = {k: x for k, x in (v.get("params") or {}).items() if k != "conditioner"} \
            if isinstance(v.get("params"), dict) else {}
        return json.dumps([v.get("family"), v.get("sym") or v.get("symbol"), p],
                          sort_keys=True, default=str)
    parents = {_key(v): v for v in verdicts
               if not (isinstance(v.get("params"), dict) and v["params"].get("conditioner"))}
    out: dict[str, list[dict[str, Any]]] = {}
    from research_only_fence import dataset_ids
    for v in verdicts:
        cond = v.get("params", {}).get("conditioner") if isinstance(v.get("params"), dict) \
            else None
        if not cond:
            continue
        par = parents.get(_key(v))
        if par is None:
            continue
        def _metric(x: dict[str, Any]) -> float | None:
            for k in ("sharpe", "exp_r", "mean_r", "expectancy"):
                if isinstance(x.get(k), (int, float)):
                    return float(x[k])
            return None
        mc, mp = _metric(v), _metric(par)
        row = {"child": v.get("cell"), "parent": par.get("cell"), "conditioner": cond,
               "child_passed": bool(v.get("passed")), "parent_passed": bool(par.get("passed")),
               "delta_passed": int(bool(v.get("passed"))) - int(bool(par.get("passed"))),
               "delta_metric": (round(mc - mp, 6) if mc is not None and mp is not None
                                else UNMEASURED)}
        for ds in dataset_ids(cond):
            out.setdefault(ds, []).append(row)
    return out


def _freshness(latest_ingestion: datetime | None, cadence: str | None,
               coverage: dict[str, Any], now: datetime) -> dict[str, Any]:
    if latest_ingestion is None:
        return {"status": UNMEASURED, "why": "no ingestion timestamp"}
    age_h = round((now - latest_ingestion).total_seconds() / 3600.0, 2)
    window, basis = None, ""
    if cadence and str(cadence).lower() in CADENCE_WINDOW_H:
        window, basis = CADENCE_WINDOW_H[str(cadence).lower()], f"declared cadence {cadence}"
    else:
        first, last, rows = coverage.get("first"), coverage.get("last"), coverage.get("rows")
        a, b = _ts(first), _ts(last)
        if a and b and isinstance(rows, int) and rows > 1:
            spacing_h = (b - a).total_seconds() / 3600.0 / (rows - 1)
            window, basis = max(24.0, 3.0 * spacing_h), "3x the observed spacing of its rows"
    if window is None:
        return {"status": UNMEASURED, "age_h": age_h, "why": "no cadence declared or inferable"}
    return {"status": "FRESH" if age_h <= window else "STALE", "age_h": age_h,
            "window_h": round(window, 1), "basis": basis}


def _blocker(row: dict[str, Any]) -> str:
    acc = str(row.get("access_state") or "")
    if acc.startswith(("REFUSED", "BLOCKED", "NEEDS_KEY", "TERMS")):
        return f"ACCESS: {acc}"
    stage = row.get("stage_reached")
    if stage not in (None, "cells_judged") and row.get("stops_at"):
        return f"CHAIN: stops at {row['stops_at']} ({row.get('chain_why') or 'source_drain'})"
    if str(row.get("pit_status") or "").startswith(("NO_AUTHORITY", "UNSTAMPED")):
        return f"PIT: {row['pit_status']}"
    if (row.get("freshness") or {}).get("status") == "STALE":
        return "FRESHNESS: older than three times its own cadence"
    if row.get("status") != "FED":
        return "CONSUMPTION: no recorded consumer read inside the window"
    if row.get("production_eligible") is False:
        return "PRODUCTION: research-only (no live_signal permission) -- research use only"
    return "NONE"


def ledger(rows: list[dict[str, Any]], value: dict[str, dict[str, Any]],
           reads: dict[str, dict[str, Any]], now: datetime, *, acquired: Path = ACQUIRED,
           axes: Path = AXES, lake: Path = LAKE) -> list[dict[str, Any]]:
    """DATA-07: one row per source / dataset / version, every field measured or named missing."""
    reg = _read(acquired, {}) or {}
    series_meta = reg.get("series") or {}
    by_url = reg.get("by_url") or {}
    keyed = reg.get("access") or {}
    chain = _chain_rows()
    asia = {str(r.get("id")): r for r in ((_read(ASIA_SOURCES, {}) or {}).get("sources") or [])
            if isinstance(r, dict) and r.get("id")}
    feats = _feature_counts(GENOMES)
    deltas = baseline_deltas(GATE_VERDICTS)
    try:
        from research_only_fence import eligibility_index
        elig = eligibility_index([r["dataset"] for r in rows], contracts_path=CONTRACTS_STORE,
                                 acquired_path=acquired)
    except Exception as exc:
        elig = {r["dataset"]: {"production_eligible": None,
                               "why": f"fence unavailable: {type(exc).__name__}"} for r in rows}
    out: list[dict[str, Any]] = []
    for r in rows:
        ds, kind = r["dataset"], r["kind"]
        name = ds.split(":", 1)[1]
        e: dict[str, Any] = {"dataset": ds, "kind": kind, "status": r["status"]}
        coverage: dict[str, Any] = {}
        ingest: datetime | None = None
        cadence: str | None = None
        if kind == "acquired":
            m = series_meta.get(name) or {}
            url = str(m.get("url") or "")
            u = by_url.get(url) or {}
            e["source"] = url or UNMEASURED
            seen = m.get("refreshed_at") or m.get("acquired_at")
            e["version"] = (f"{seen}#{str(m.get('schema_hash') or '')[:12]}".rstrip("#")
                            if seen else UNMEASURED)
            e["access_state"] = str((keyed.get(url) or {}).get("state") or u.get("status")
                                    or ("COLLECTED" if m.get("rows") else UNMEASURED))
            if u.get("refusal"):
                e["access_state"] = f"REFUSED: {u['refusal']}"
            coverage = {"first": m.get("first"), "last": m.get("last"), "rows": m.get("rows")}
            e["pit_status"] = ("AUTHORITY" if m.get("pit_authority") is True else
                               ("NO_AUTHORITY: " + (", ".join(str(b) for b in
                                                              (m.get("pit_blocking") or [])[:3])
                                                    or "the certifier withheld it")
                                if m.get("pit_authority") is False else UNMEASURED))
            e["latest_release"] = m.get("last") or UNMEASURED
            ingest = _ts(seen)
            e["history_status"] = m.get("history_status")
        elif kind == "axis":
            a = _read(axes / f"{name}.json", {}) or {}
            e["source"] = a.get("source") or UNMEASURED
            e["version"] = a.get("at") or UNMEASURED
            e["access_state"] = "COLLECTED" if a.get("n_rows") else UNMEASURED
            coverage = {"first": a.get("first"), "last": a.get("last"), "rows": a.get("n_rows")}
            e["pit_status"] = (f"KNOWABLE_LAG_{a['knowable_lag_days']}D"
                               if a.get("knowable_lag_days") is not None else UNMEASURED)
            e["latest_release"] = a.get("last") or UNMEASURED
            ingest = _ts(a.get("at"))
        else:                                            # lake series, often an asia source
            c = chain.get(name) or {}
            src = asia.get(name) or {}
            pit = _read(lake / f"{name}.pit.json", {}) or {}
            e["source"] = src.get("url") or c.get("url") or UNMEASURED
            cadence = src.get("cadence") or c.get("cadence")
            path = next((lake / f"{name}{x}" for x in (".parquet", ".csv")
                         if (lake / f"{name}{x}").exists()), None)
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, UTC) if path else None
            except OSError:
                mtime = None
            e["version"] = mtime.isoformat(timespec="seconds") if mtime else UNMEASURED
            e["access_state"] = str(c.get("last_status") or ("COLLECTED" if c.get("collected")
                                                             else UNMEASURED))
            frames = pit.get("frames") if isinstance(pit, dict) else None
            coverage = {"first": pit.get("first") if isinstance(pit, dict) else None,
                        "last": pit.get("last") if isinstance(pit, dict) else None,
                        "rows": c.get("n_rows") or (pit.get("n_rows") if isinstance(pit, dict)
                                                    else None)}
            e["pit_status"] = ("STAMPED" if c.get("pit_stamped") or any(
                isinstance(f, dict) and f.get("status") == "STAMPED" for f in frames or [])
                else (f"UNSTAMPED: {c.get('parse_error')}" if c.get("parse_error")
                      else UNMEASURED))
            e["latest_release"] = coverage.get("last") or UNMEASURED
            e["stage_reached"], e["stops_at"] = c.get("stage_reached"), c.get("stops_at")
            e["chain_why"] = c.get("why")
            ingest = mtime
        e["coverage"] = coverage if any(v is not None for v in coverage.values()) else UNMEASURED
        a, b = _ts(coverage.get("first")), _ts(coverage.get("last"))
        e["history_depth_days"] = round((b - a).total_seconds() / 86400.0, 1) if a and b \
            else UNMEASURED
        e["latest_ingestion"] = ingest.isoformat(timespec="seconds") if ingest else UNMEASURED
        e["freshness"] = _freshness(ingest, cadence, coverage, now)
        rd = reads.get(ds) or {}
        cons = rd.get("consumers") or {}
        e["consumers"] = sorted(cons) or UNMEASURED
        lasts = [str(v.get("last_read_at")) for v in cons.values() if v.get("last_read_at")]
        e["last_consumption"] = max(lasts) if lasts else UNMEASURED
        e["versions_read"] = sorted({str(v.get("version")) for v in cons.values()
                                     if v.get("version") is not None})
        if feats is None:
            e["features"] = UNMEASURED
        else:
            host = str((series_meta.get(name) or {}).get("host") or "") if kind == "acquired" \
                else ""
            e["features"] = feats.get(ds, 0) + (feats.get(f"acquired:{host}", 0) if host else 0)
        iv = value.get(ds) or {}
        e["outcomes"] = iv.get("outcome") or UNMEASURED
        e["cost"] = iv.get("cost") or UNMEASURED
        live_uses = set(rd.get("uses") or [])
        e["non_cell_utility"] = (sorted(live_uses & set(NON_CELL_USES)) if rd else UNMEASURED)
        el = elig.get(ds) or {}
        e["acquisition_method"] = el.get("acquisition_method", UNMEASURED)
        e["licence"] = el.get("licence", UNMEASURED)
        e["production_eligible"] = el.get("production_eligible")
        e["production_why"] = el.get("why")
        e["provenance"] = el.get("provenance", UNMEASURED)
        pairs = deltas.get(ds)
        e["baseline_vs_data"] = ({"status": "MEASURED", "pairs": pairs[:10], "n_pairs": len(pairs),
                                  "mean_delta_passed": round(sum(p["delta_passed"] for p in pairs)
                                                             / len(pairs), 4)}
                                 if pairs else
                                 {"status": UNMEASURED,
                                  "why": "no cell conditioned on this dataset was judged beside "
                                         "its unconditioned parent"})
        e["missing_fields"] = [f for f in LEDGER_FIELDS
                               if e.get(f) in (None, UNMEASURED, [], "")
                               or (isinstance(e.get(f), dict)
                                   and e[f].get("status") == UNMEASURED)]
        e["blocker"] = _blocker(e)
        out.append(e)
    return out


def ledger_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def count(pred: Any) -> int:
        return sum(1 for r in rows if pred(r))
    blockers: dict[str, int] = {}
    for r in rows:
        k = str(r["blocker"]).split(":", 1)[0]
        blockers[k] = blockers.get(k, 0) + 1
    missing: dict[str, int] = {}
    for r in rows:
        for f in r["missing_fields"]:
            missing[f] = missing.get(f, 0) + 1
    return {"datasets": len(rows), "blockers": blockers, "missing_field_counts": missing,
            "pit_authority": count(lambda r: str(r.get("pit_status")).startswith(
                ("AUTHORITY", "STAMPED", "KNOWABLE"))),
            "fresh": count(lambda r: (r.get("freshness") or {}).get("status") == "FRESH"),
            "stale": count(lambda r: (r.get("freshness") or {}).get("status") == "STALE"),
            "with_non_cell_use": count(lambda r: isinstance(r.get("non_cell_utility"), list)
                                       and r["non_cell_utility"]),
            "production_eligible": count(lambda r: r.get("production_eligible") is True),
            "research_only_or_uncontracted": count(lambda r: r.get("production_eligible")
                                                   is False),
            "baseline_measured": count(lambda r: r["baseline_vs_data"]["status"] == "MEASURED")}


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def main() -> int:
    doc = build()
    led = doc.pop("ledger")
    _atomic(LEDGER_REPORT, {"measured_at": doc["measured_at"],
                            "row": "DATA-07: per source / dataset / version ledger",
                            "fields": list(LEDGER_FIELDS), "summary": doc["ledger_summary"],
                            "rows": led})
    _atomic(LEDGER_DIGEST, {"measured_at": doc["measured_at"], "summary": doc["ledger_summary"],
                            "report": "desks/mt5/reports/DATASET_LEDGER.json",
                            "blocked_first": [{k: r.get(k) for k in ("dataset", "blocker",
                                                                       "missing_fields")}
                                              for r in led if r["blocker"] != "NONE"][:100]})
    _atomic(REPORT, doc)
    digest = {k: doc[k] for k in ("measured_at", "duty", "unfed_datasets", "target",
                                  "datasets_held", "fed", "by_kind", "fed_by_use", "evidence")}
    iv = dict(doc["information_value"])
    iv["top_per_cost"] = iv["top_per_cost"][:20]
    digest["information_value"] = iv
    digest["unfed_first"] = doc["unfed"][:DIGEST_LIST]
    digest["report"] = "desks/mt5/reports/DATASET_USE.json"
    _atomic(DIGEST, digest)
    print(f"dataset use: {doc['fed']}/{doc['datasets_held']} fed, unfed_datasets="
          f"{doc['unfed_datasets']} (target 0); by kind {doc['by_kind']}")
    print(f"source ledger: {doc['ledger_summary']['datasets']} row(s), blockers "
          f"{doc['ledger_summary']['blockers']} -> {LEDGER_REPORT}")
    print("YIELD " + json.dumps({"targets": doc["unfed_datasets"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
