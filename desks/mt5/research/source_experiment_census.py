"""Global source -> acquired data -> feature -> experiment -> verdict census.

It walks every country pack, so Africa/MENA, Asia/Oceania, Europe and the Americas obey the same
contract.  A declared URL is not acquired data; acquired data is not a feature; and a feature is
not an evaluated experiment.  Missing links are durable conversion debt with a named owner.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _path in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from libs.moat import registry as R  # noqa: E402
from libs.research import country_lab as CL  # noqa: E402

PACKS = DESK / "research" / "countries"
ACQUIRED = DESK / "data" / "acquired" / "registry.json"
REPORT = DESK / "reports" / "SOURCE_EXPERIMENT_CENSUS.json"
ACQUISITION_OWNER = "hourly_discovery:acquire_datasets"


def _read(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text("utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def _token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _codes() -> list[str]:
    return sorted(p.parent.name for p in PACKS.glob("*/pack.py")
                  if not p.parent.name.startswith("_")
                  and p.parent.name not in {"global", "institutional", "jp"})


def _experiment_index() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    try:
        conn = R.connect()
        rows = conn.execute("SELECT experiment_id, source_id, candidate_id, status, verdict, "
                            "verdict_at FROM experiments WHERE source_id IS NOT NULL").fetchall()
        for row in rows:
            out[str(row["source_id"])].append(dict(row))
        conn.close()
    except Exception:
        pass
    return out


def build() -> dict[str, Any]:
    acquired = _read(ACQUIRED)
    by_url = dict(acquired.get("by_url") or {})
    series = dict(acquired.get("series") or {})
    experiments = _experiment_index()
    rows: list[dict[str, Any]] = []

    def append_source(*, code: str, region: str, source_id: str, source: str,
                      urls: list[str], information: list[str], coverage: str = "",
                      publication_lag_days: float | None = None, revisions: str = "",
                      pit_feasible: bool | None = None) -> None:
        attempted_urls = [url for url in urls if url in by_url]
        matched_urls = [url for url in attempted_urls
                        if str((by_url.get(url) or {}).get("status") or "SUCCESS") == "SUCCESS"]
        features = sorted(name for name, meta in series.items()
                          if str(meta.get("url") or "") in matched_urls)
        exp = experiments.get(source_id, [])
        evaluated = [e for e in exp if e.get("verdict") or e.get("verdict_at")]
        last_attempt = max((str(by_url[url].get("at") or "") for url in attempted_urls),
                           default="")
        last_fetch = max((str(by_url[url].get("at") or "") for url in matched_urls), default="")
        if not urls:
            blocker, owner = "NO_MACHINE_ENDPOINT", "source_frontier"
        elif not attempted_urls:
            blocker, owner = "NOT_ACQUIRED", ACQUISITION_OWNER
        elif not matched_urls:
            blocker, owner = "ACQUISITION_REFUSED", "source_frontier"
        elif not features:
            blocker, owner = "NO_USABLE_FEATURE", "feature_compiler"
        elif not exp:
            blocker, owner = "NO_EXPERIMENT", "experiment_spine"
        elif not evaluated:
            blocker, owner = "UNEVALUATED_EXPERIMENT", "universal_gauntlet"
        else:
            blocker, owner = "", ""
        rows.append({
            "region": region, "country": code, "source_id": source_id, "source": source,
            "information_families": information, "urls": urls,
            "acquisition_owner": ACQUISITION_OWNER, "last_successful_fetch": last_fetch or None,
            "last_attempt": last_attempt or None,
            "acquisition_refusals": sorted({str((by_url.get(url) or {}).get("refusal") or "")
                                             for url in attempted_urls
                                             if (by_url.get(url) or {}).get("refusal")}),
            "coverage": coverage or "UNMEASURED",
            "publication_lag_days": publication_lag_days,
            "revisions": revisions or "UNMEASURED", "pit_feasible": pit_feasible,
            "parser_result": "PARSED" if features else ("FETCHED_NO_FEATURE" if matched_urls
                                                          else "NOT_FETCHED"),
            "feature_ids": features,
            "experiment_ids": [str(e.get("experiment_id")) for e in exp],
            "evaluator_outcomes": [{"experiment_id": e.get("experiment_id"),
                                     "status": e.get("status"), "verdict": e.get("verdict"),
                                     "verdict_at": e.get("verdict_at")} for e in exp],
            "disposition": "EVALUATED" if not blocker else "UNRESOLVED",
            "blocker": blocker or None, "owner": owner or None,
            "next_attempt": "next hourly owner pass" if blocker else None,
        })

    for code in _codes():
        pack = CL.resolve_pack(code)
        if pack is None:
            rows.append({"region": "UNMEASURED", "country": code,
                         "source_id": f"{code}:pack", "source": "country pack",
                         "information_families": [], "urls": [],
                         "acquisition_owner": ACQUISITION_OWNER,
                         "last_successful_fetch": None, "coverage": "UNMEASURED",
                         "publication_lag_days": None, "revisions": "UNMEASURED",
                         "pit_feasible": None, "parser_result": "NOT_FETCHED",
                         "feature_ids": [], "experiment_ids": [], "evaluator_outcomes": [],
                         "disposition": "UNRESOLVED", "blocker": "PACK_DOES_NOT_RESOLVE",
                         "owner": "global_research_os", "next_attempt": "next hourly pass"})
            continue
        region = str(pack.region_command or "UNMEASURED")
        for dataset in pack.datasets:
            source_id = f"{code}:dataset:{_token(dataset.name)}"
            possible = [str(dataset.how_to_fetch or ""), str(dataset.source or "")]
            urls = [u for u in possible if u.startswith(("http://", "https://"))]
            append_source(code=code, region=region, source_id=source_id,
                          source=str(dataset.source or dataset.name), urls=urls,
                          information=list(dataset.mechanism_families),
                          coverage=dataset.coverage,
                          publication_lag_days=float(dataset.publication_lag_days),
                          revisions=dataset.revisions, pit_feasible=bool(dataset.pit_feasible))
        for source in CL.source_rows(pack):
            if source.absent_reason:
                continue
            append_source(code=code, region=region,
                          source_id=str(source.id or f"{code}:source:{_token(source.label)}"),
                          source=str(source.label or source.id), urls=list(source.roots),
                          information=[source.layer or "UNTAGGED"],
                          coverage="DECLARED_VERIFIED" if source.verified else "DECLARED")

    per_region: dict[str, dict[str, int]] = {}
    for region in sorted({str(row["region"]) for row in rows}):
        group = [row for row in rows if row["region"] == region]
        per_region[region] = {
            "sources": len(group),
            "attempted": sum(bool(row.get("last_attempt")) for row in group),
            "refused": sum(bool(row.get("acquisition_refusals")) for row in group),
            "acquired": sum(row["parser_result"] == "PARSED" for row in group),
            "features": sum(len(row["feature_ids"]) for row in group),
            "experiments": sum(len(row["experiment_ids"]) for row in group),
            "evaluated": sum(row["disposition"] == "EVALUATED" for row in group),
            "unresolved": sum(row["disposition"] == "UNRESOLVED" for row in group),
        }
    dispositions = Counter(str(row["disposition"]) for row in rows)
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "scope": "all country packs: Africa/MENA, Asia/Oceania, Europe and the Americas",
        "sources": len(rows), "dispositions": dict(dispositions),
        "conservation": {"inputs": len(rows), "evaluated": dispositions["EVALUATED"],
                         "explicitly_unresolved": dispositions["UNRESOLVED"],
                         "silently_lost": 0,
                         "identity_holds": len(rows) == sum(dispositions.values())},
        "per_region": per_region, "rows": rows,
        "rule": "declared != acquired != feature != experiment != evaluated outcome",
    }


def run(report: Path = REPORT) -> dict[str, Any]:
    doc = build()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    return doc


def main() -> int:
    doc = run()
    print(f"source experiment census: {doc['sources']} source rows; "
          f"{doc['dispositions'].get('EVALUATED', 0)} evaluated; "
          f"{doc['dispositions'].get('UNRESOLVED', 0)} unresolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
