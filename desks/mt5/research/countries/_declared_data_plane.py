"""Shared measured data plane for country packs without a bespoke collector.

The network owner is :mod:`research.acquire_datasets`, which runs on the hourly discovery clock.
Country miners consume its durable registry and report the exact declared datasets that did or
did not arrive.  This keeps one fetch implementation and makes ``no_fetch=True`` an explicit
ownership boundary rather than a silently stale lane.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research import country_lab as CL

DESK = Path(__file__).resolve().parents[2]
ACQUIRED = DESK / "data" / "acquired" / "registry.json"
REPORTS = DESK / "reports"
ACQUISITION_OWNER = "research/hourly_discovery.py:acquire_datasets"


def report_path(code: str) -> Path:
    return REPORTS / f"{code.upper()}_DATA_PLANE.json"


def declared_lanes(code: str) -> tuple[str, ...]:
    pack = CL.resolve_pack(code)
    return tuple(row.name for row in (pack.datasets if pack else ()) if row.name)


def _registry() -> dict[str, Any]:
    try:
        doc = json.loads(ACQUIRED.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def run(*, code: str, budget_s: float = 300.0, no_fetch: bool = True,
        dry_run: bool = False, registry: Any = None,
        report_default: Path | None = None) -> dict[str, Any]:
    """Measure every declared dataset against the canonical acquired-data registry."""
    del budget_s, registry
    pack = CL.resolve_pack(code)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    reg = _registry()
    by_url = dict(reg.get("by_url") or {})
    series = dict(reg.get("series") or {})
    lanes: list[dict[str, Any]] = []
    if pack is None:
        lanes.append({"dataset": code, "stored": 0, "vintages": 0,
                      "unmeasured": [{"what": f"{code}:pack", "verdict": "UNMEASURED",
                                      "why": "country pack does not resolve"}]})
    else:
        for dataset in pack.datasets:
            candidates = [str(dataset.how_to_fetch or ""), str(dataset.source or "")]
            urls = [u for u in candidates if u.startswith(("http://", "https://"))]
            matched_urls = [u for u in urls if u in by_url]
            matched_series = sorted({name for name, meta in series.items()
                                     if str(meta.get("url") or "") in matched_urls})
            successful_urls = [u for u in matched_urls
                               if by_url[u].get("status") == "SUCCESS"]
            last = max((str(by_url[u].get("at") or "") for u in successful_urls), default="")
            usable_series = [name for name in matched_series
                             if series[name].get("pit_authority") is True]
            blocking = []
            if not urls:
                blocking.append({"what": f"{code}:{dataset.name}", "verdict": "UNMEASURED",
                                 "why": "declared dataset has no machine-readable endpoint; "
                                        "source_frontier owns endpoint discovery"})
            elif not matched_urls:
                blocking.append({"what": f"{code}:{dataset.name}", "verdict": "UNMEASURED",
                                 "why": f"not yet acquired by {ACQUISITION_OWNER}"})
            else:
                for url in matched_urls:
                    if url not in successful_urls:
                        blocking.append({"what": url, "verdict": "UNMEASURED",
                                         "why": by_url[url].get("refusal") or
                                         "latest acquisition did not succeed"})
                if not matched_series:
                    blocking.append({"what": f"{code}:{dataset.name}", "verdict": "UNMEASURED",
                                     "why": "no persisted series in acquisition registry"})
                for name in matched_series:
                    if name not in usable_series:
                        blocking.append({"what": name, "verdict": "UNMEASURED",
                                         "why": "PIT authority absent or invalid",
                                         "details": series[name].get("pit_blocking") or []})
            lanes.append({
                "dataset": dataset.name, "source": dataset.source,
                "urls": urls, "acquisition_owner": ACQUISITION_OWNER,
                "fetch_requested_here": not no_fetch,
                "last_successful_fetch": last or None,
                "last_attempt": max((str(by_url[u].get("at") or "")
                                     for u in matched_urls), default="") or None,
                "attempted_endpoints": len(matched_urls),
                "successful_endpoints": len(successful_urls),
                "coverage": dataset.coverage, "frequency": dataset.frequency,
                "publication_lag_days": dataset.publication_lag_days,
                "revisions": dataset.revisions, "pit_feasible": dataset.pit_feasible,
                "stored": len(matched_series), "vintages": len(matched_series),
                "pit_usable": len(usable_series),
                "stored_feature_ids": matched_series,
                "feature_ids": usable_series, "unmeasured": blocking,
            })
    doc = {"at": now, "country": code, "acquisition_owner": ACQUISITION_OWNER,
           "no_fetch_is_owned": True, "lanes": lanes,
           "declared": len(lanes), "acquired": sum(bool(r.get("stored")) for r in lanes),
           "pit_usable": sum(bool(r.get("pit_usable")) for r in lanes),
           "unresolved": sum(bool(r.get("unmeasured")) for r in lanes),
           "rule": "declared coverage, acquired data and usable features are separate states"}
    target = report_default or report_path(code)
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    return doc
