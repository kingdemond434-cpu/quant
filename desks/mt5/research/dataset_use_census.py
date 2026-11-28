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
NOVELTY_MIN_OVERLAP = 24
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
    except Exception:                                                   # noqa: BLE001
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
    by_use: dict[str, int] = {u: 0 for u in U.USES}
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
    return {
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


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def main() -> int:
    doc = build()
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
    print("YIELD " + json.dumps({"targets": doc["unfed_datasets"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
