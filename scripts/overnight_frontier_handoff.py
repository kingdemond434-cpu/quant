#!/usr/bin/env python3
"""Pre/post snapshot and machine-readable handoff for the renewable overnight frontier.

The script aggregates existing research artifacts; it does not invent counts, promote alphas,
alter validation, size risk, or place orders.  Missing evidence is UNMEASURED and is published via
the generic gap contract so the next max-push run can rank it without another bespoke reader.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.gap_contract import Gap, publish  # noqa: E402

CONTRACT = ROOT / "docs" / "research" / "OVERNIGHT_FRONTIER_CONTRACT.json"
BASELINE = ROOT / "data" / "overnight_frontier_baseline.json"
OUT = ROOT / "data" / "overnight_frontier_handoff.json"
HISTORY = ROOT / "data" / "overnight_frontier_history.jsonl"


def _read_path(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _read(rel: str, default: Any = None) -> Any:
    return _read_path(ROOT / rel, default)


def _nested(doc: Any, *path: str) -> Any:
    value = doc
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _metric(value: Any, source: str, *, unit: str = "count") -> dict[str, object]:
    number = float(value) if isinstance(value, (int, float)) else None
    if number is not None and number.is_integer():
        number = int(number)
    return {
        "status": "MEASURED" if number is not None else "UNMEASURED",
        "value": number,
        "unit": unit,
        "source": source,
    }


def _first_metric(candidates: list[tuple[Any, str]], *, unit: str = "count") -> dict[str, object]:
    for value, source in candidates:
        if isinstance(value, (int, float)):
            return _metric(value, source, unit=unit)
    return _metric(None, "no declared producer emitted this metric", unit=unit)


def _sum_source(rows: list[dict[str, Any]], *keys: str) -> int | None:
    if not rows:
        return None
    found = False
    total = 0
    for row in rows:
        for key in keys:
            value = row.get(key)
            if isinstance(value, (int, float)):
                total += int(value)
                found = True
                break
    return total if found else None


def conversion_metrics() -> dict[str, dict[str, object]]:
    sweep = _read("data/full_sweep.json", {})
    counts = sweep.get("counts", {}) if isinstance(sweep, dict) else {}
    source = _read("data/source_production.json", {})
    sources = source.get("sources", []) if isinstance(source, dict) else []
    sources = [row for row in sources if isinstance(row, dict)] if isinstance(sources, list) else []
    review = _read("data/research_review.json", {})
    ladder = _read("data/live_ladder.json", {})
    live_rows = ladder.get("rows", []) if isinstance(ladder, dict) else []
    live_rows = (
        [row for row in live_rows if isinstance(row, dict)] if isinstance(live_rows, list) else []
    )
    near = _first_metric(
        [
            (
                _nested(review, "near_survivor_bank", "count"),
                "data/research_review.json::near_survivor_bank.count",
            ),
            (
                _nested(review, "near_survivors", "count"),
                "data/research_review.json::near_survivors.count",
            ),
            (
                len(review.get("near_survivors", []))
                if isinstance(review, dict) and isinstance(review.get("near_survivors"), list)
                else None,
                "data/research_review.json::near_survivors",
            ),
        ]
    )
    killed = sweep.get("killed_cells") if isinstance(sweep, dict) else None
    formula = counts.get("FORMULA") if isinstance(counts, dict) else None
    dispositioned = (
        len(killed) + int(formula or 0)
        if isinstance(killed, list) and isinstance(formula, (int, float))
        else None
    )
    deployed_from_ladder = (
        sum(
            str(row.get("status", row.get("stage", ""))).upper() in {"LIVE", "DEPLOYED"}
            for row in live_rows
        )
        if live_rows
        else None
    )
    realised_values = [
        float(row.get("realised_pnl", row.get("realized_pnl")))
        for row in live_rows
        if isinstance(row.get("realised_pnl", row.get("realized_pnl")), (int, float))
    ]
    return {
        "discovered": _first_metric(
            [
                (
                    _sum_source(sources, "found", "discovered"),
                    "data/source_production.json::sources.found",
                ),
                (
                    counts.get("declared") if isinstance(counts, dict) else None,
                    "data/full_sweep.json::counts.declared",
                ),
            ]
        ),
        "distinct_mechanisms": _first_metric(
            [
                (
                    _sum_source(sources, "novel", "distinct_mechanisms"),
                    "data/source_production.json::sources.novel",
                ),
                (
                    counts.get("INDEPENDENT_MECHANISM") if isinstance(counts, dict) else None,
                    "data/full_sweep.json::counts.INDEPENDENT_MECHANISM",
                ),
            ]
        ),
        "hypotheses": _first_metric(
            [
                (
                    counts.get("declared") if isinstance(counts, dict) else None,
                    "data/full_sweep.json::counts.declared",
                ),
            ]
        ),
        "tested": _first_metric(
            [
                (_sum_source(sources, "tested"), "data/source_production.json::sources.tested"),
                (
                    counts.get("measurable") if isinstance(counts, dict) else None,
                    "data/full_sweep.json::counts.measurable",
                ),
            ]
        ),
        "dispositioned": _metric(dispositioned, "data/full_sweep.json::killed_cells+FORMULA"),
        "near_survivors": near,
        "survivors": _first_metric(
            [
                (formula, "data/full_sweep.json::counts.FORMULA"),
            ]
        ),
        "independent_survivors": _first_metric(
            [
                (
                    _sum_source(sources, "independent"),
                    "data/source_production.json::sources.independent",
                ),
                (
                    counts.get("INDEPENDENT_MECHANISM") if isinstance(counts, dict) else None,
                    "data/full_sweep.json::counts.INDEPENDENT_MECHANISM",
                ),
            ]
        ),
        "portfolio_tested": _first_metric(
            [
                (
                    _sum_source(sources, "portfolio_positive"),
                    "data/source_production.json::sources.portfolio_positive",
                ),
                (
                    counts.get("PORTFOLIO_CONTRIBUTING") if isinstance(counts, dict) else None,
                    "data/full_sweep.json::counts.PORTFOLIO_CONTRIBUTING",
                ),
            ]
        ),
        "deployed": _first_metric(
            [
                (
                    _sum_source(sources, "live_descendants"),
                    "data/source_production.json::sources.live_descendants",
                ),
                (deployed_from_ladder, "data/live_ladder.json::LIVE|DEPLOYED rows"),
            ]
        ),
        "realised_portfolio_contribution": _metric(
            sum(realised_values) if realised_values else None,
            "data/live_ladder.json::rows.realised_pnl",
            unit="pnl",
        ),
    }


def _artifact_state(contract: dict[str, Any], started_epoch: float | None) -> dict[str, object]:
    result = {}
    for rel in contract.get("required_artifacts", []):
        path = ROOT / str(rel)
        present = path.is_file()
        modified = path.stat().st_mtime if present else None
        result[str(rel)] = {
            "present": present,
            "modified_epoch": modified,
            "fresh_this_cycle": (
                bool(modified is not None and modified >= started_epoch)
                if started_epoch is not None
                else None
            ),
        }
    return result


def _git_state() -> dict[str, object]:
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args], cwd=ROOT, check=False, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    status = run("status", "--porcelain")
    return {
        "branch": run("branch", "--show-current"),
        "head": run("rev-parse", "HEAD"),
        "dirty_paths": status.splitlines() if isinstance(status, str) and status else [],
    }


def _risk_integrity() -> dict[str, object]:
    try:
        from scripts.check_risk_kernel import verify

        drifted, missing, unlocked = verify()
        return {
            "healthy": not (drifted or missing or unlocked),
            "drifted": drifted,
            "missing": missing,
            "unlocked": unlocked,
        }
    except (ImportError, OSError, ValueError) as exc:
        return {"healthy": None, "reason": str(exc)}


def _status(condition: bool | None, evidence: object, action: str) -> dict[str, object]:
    state = "HEALTHY" if condition is True else "DEGRADED" if condition is False else "UNMEASURED"
    return {"status": state, "evidence": evidence, "next_action": action}


def _all_measured(metrics: dict[str, dict[str, object]], names: tuple[str, ...]) -> bool | None:
    states = [metrics[name]["status"] == "MEASURED" for name in names]
    return all(states) if states else None


def maturity_scorecard(
    metrics: dict[str, dict[str, object]],
    artifacts: dict[str, object],
    *,
    pipeline_rc: int,
) -> dict[str, dict[str, object]]:
    risk = _risk_integrity()
    completion = _read("data/completion_program.json", {})
    validation = completion.get("validation", {}) if isinstance(completion, dict) else {}
    production = completion.get("production", {}) if isinstance(completion, dict) else {}
    research = completion.get("research", {}) if isinstance(completion, dict) else {}
    optimizer = _read("data/research_alpha_optimizer.json", {})
    external = _read("data/intelligence/external_frontier.json", {})
    controller_state = _read("data/controller_lease.json", {})
    controller_checkpoint = _read("data/controller_checkpoint.json", {})
    controller_status = _read("data/intelligence/midnight_codex_status.json", {})
    evolution = (
        optimizer.get("search_strategy_evolution", {}) if isinstance(optimizer, dict) else {}
    )
    coverage = evolution.get("coverage", {}) if isinstance(evolution, dict) else {}
    concentration = evolution.get("concentration", {}) if isinstance(evolution, dict) else {}
    serendipity = evolution.get("serendipity_channel", {}) if isinstance(evolution, dict) else {}
    present = [bool(row.get("present")) for row in artifacts.values() if isinstance(row, dict)]
    fresh = [
        bool(row.get("fresh_this_cycle")) for row in artifacts.values() if isinstance(row, dict)
    ]
    validation_values = [value for value in validation.values() if isinstance(value, dict)]
    validation_measured = bool(validation_values) and all(
        value.get("status") not in {"UNMEASURED", "INVALID_INPUT"} for value in validation_values
    )
    production_controls = (
        "deterministic_hot_path",
        "decision_ledger",
        "preflight",
        "venue_capability",
    )
    production_measured = bool(production) and all(
        isinstance(production.get(name), dict)
        and production[name].get("status") not in {"UNMEASURED", "INVALID_INPUT"}
        for name in production_controls
    )
    method_measured = isinstance(coverage.get("ratio"), (int, float))
    method_healthy = (
        method_measured
        and not bool(concentration.get("exploration_starvation"))
        and float(coverage.get("ratio", 0.0)) > 0
    )
    return {
        "survival_integrity": _status(
            risk.get("healthy") if isinstance(risk, dict) else None,
            risk,
            "restore/re-lock only through the principal-governed risk-kernel procedure",
        ),
        "data_freshness": _status(
            all(present) and all(fresh) if present else None,
            {"present": sum(present), "required": len(present), "fresh": sum(fresh)},
            "repair the earliest missing or stale producer before trusting downstream counts",
        ),
        "discovery_breadth": _status(
            _all_measured(metrics, ("discovered", "distinct_mechanisms")),
            {name: metrics[name] for name in ("discovered", "distinct_mechanisms")},
            "restore explicit discovery and mechanism provenance",
        ),
        "hypothesis_conversion": _status(
            _all_measured(metrics, ("hypotheses", "tested", "dispositioned", "near_survivors")),
            {
                name: metrics[name]
                for name in ("hypotheses", "tested", "dispositioned", "near_survivors")
            },
            "repair the first unmeasured conversion join; never infer a clean zero",
        ),
        "statistical_validation": _status(
            validation_measured if validation else None,
            {
                name: value.get("status")
                for name, value in validation.items()
                if isinstance(value, dict)
            },
            "supply powered, multiplicity-aware inputs; do not lower validation bars",
        ),
        "survivor_independence": _status(
            _all_measured(metrics, ("survivors", "independent_survivors")),
            {name: metrics[name] for name in ("survivors", "independent_survivors")},
            "measure mechanism independence rather than counting correlated variants",
        ),
        "portfolio_utilisation": _status(
            _all_measured(metrics, ("portfolio_tested", "deployed")),
            {name: metrics[name] for name in ("portfolio_tested", "deployed")},
            "close the survivor-to-portfolio-to-deployment join",
        ),
        "execution_reality": _status(
            production_measured if production else None,
            {name: production.get(name) for name in production_controls},
            "restore deterministic replay, decision, preflight and venue evidence before new opens",
        ),
        "unknown_unknown_renewal": _status(
            bool(_read("data/intelligence/daily_alpha_frontier.json", {})),
            {"frontier_artifact": "data/intelligence/daily_alpha_frontier.json"},
            "run the alpha frontier and convert blind spots into testable missions",
        ),
        "search_method_diversity": _status(
            method_healthy if method_measured else None,
            {"coverage": coverage, "concentration": concentration},
            "test missing discovery methodologies or mutate the search process when yield stagnates",
        ),
        "exploration_option_value": _status(
            serendipity.get("status") == "ACTIVE" if serendipity else None,
            serendipity,
            "activate exactly one bounded distant-domain mission with no promotion authority",
        ),
        "external_intelligence_transfer": _status(
            bool(external) and external.get("capability_graph", {}).get("status") == "MEASURED"
            if isinstance(external, dict)
            else None,
            {
                "capability_graph": external.get("capability_graph")
                if isinstance(external, dict)
                else None,
                "paper_transfer": external.get("paper_transfer")
                if isinstance(external, dict)
                else None,
                "route_coverage": external.get("discovery_route_coverage")
                if isinstance(external, dict)
                else None,
            },
            "restore elite-source acquisition and advance replication-to-internal-validation joins",
        ),
        "open_world_coverage": _status(
            research.get("open_world_coverage", {}).get("status") == "MEASURED"
            and research.get("open_world_coverage", {}).get("taxonomy_renewing") is True
            if isinstance(research.get("open_world_coverage"), dict)
            else None,
            research.get("open_world_coverage"),
            "rank known white spaces and run daily taxonomy-challenge searches",
        ),
        "meaningful_research_throughput": _status(
            research.get("meaningful_research_throughput", {}).get("status") == "MEASURED"
            if isinstance(research.get("meaningful_research_throughput"), dict)
            else None,
            research.get("meaningful_research_throughput"),
            "repair the first raw-to-independent-survivor bottleneck without trial quotas",
        ),
        "deep_forest_conversion": _status(
            external.get("deep_forest_intelligence", {}).get("status") == "MEASURED"
            if isinstance(external, dict)
            and isinstance(external.get("deep_forest_intelligence"), dict)
            else None,
            external.get("deep_forest_intelligence") if isinstance(external, dict) else None,
            "ingest lawful raw multilingual evidence and convert it into reproducible tests",
        ),
        "controller_continuity": _status(
            bool(controller_checkpoint)
            and controller_state.get("persistent_workers_controller_independent") is True,
            {
                "lease": controller_state,
                "checkpoint": controller_checkpoint,
                "midnight_status": controller_status,
            },
            "restore the fenced lease/checkpoint/handoff path without stopping persistent workers",
        ),
        "self_improvement": _status(
            pipeline_rc == 0 and bool(_read("data/max_push_queue.json", {})),
            {
                "pipeline_rc": pipeline_rc,
                "max_push_present": bool(_read("data/max_push_queue.json", {})),
            },
            "repair failed stages and execute the highest-ranked measured gap",
        ),
        "handoff_completeness": _status(
            bool(metrics) and bool(artifacts),
            {"metric_count": len(metrics), "artifact_count": len(artifacts)},
            "regenerate this handoff; never rely on session memory",
        ),
    }


def _deltas(
    before: dict[str, dict[str, object]], after: dict[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    out = {}
    for name, current in after.items():
        old = before.get(name, {})
        a, b = old.get("value"), current.get("value")
        delta = (
            float(b) - float(a)
            if isinstance(a, (int, float)) and isinstance(b, (int, float))
            else None
        )
        if isinstance(delta, float) and delta.is_integer():
            delta = int(delta)
        out[name] = {"before": a, "after": b, "delta": delta, "unit": current.get("unit")}
    return out


def _harvest() -> dict[str, object]:
    frontier = _read("data/intelligence/daily_alpha_frontier.json", {})
    practitioner = frontier.get("practitioner_frontier", {}) if isinstance(frontier, dict) else {}
    optimizer = _read("data/research_alpha_optimizer.json", {})
    evolution = (
        optimizer.get("search_strategy_evolution", {}) if isinstance(optimizer, dict) else {}
    )
    max_push = _read("data/max_push_queue.json", {})
    queue = max_push.get("queue", []) if isinstance(max_push, dict) else []
    ledger = _read("data/completion_ledger_status.json", {})
    return {
        "new_mechanisms": practitioner.get("new_mechanisms")
        if isinstance(practitioner, dict)
        else None,
        "factory_unmeasured_controls": frontier.get("high_priority_residuals")
        if isinstance(frontier, dict)
        else None,
        "search_method_mutations": evolution.get("mutations_and_combinations")
        if isinstance(evolution, dict)
        else None,
        "search_method_retirement_candidates": evolution.get("retirement_candidates")
        if isinstance(evolution, dict)
        else None,
        "serendipity_mission": evolution.get("serendipity_channel")
        if isinstance(evolution, dict)
        else None,
        "highest_value_next": queue[0] if isinstance(queue, list) and queue else None,
        "open_world_daily_priority": (
            _read("data/completion_program.json", {})
            .get("research", {})
            .get("open_world_coverage", {})
            .get("daily_priority")
        ),
        "deep_forest_hypotheses": (
            _read("data/intelligence/external_frontier.json", {})
            .get("deep_forest_intelligence", {})
            .get("hypothesis_candidates")
        ),
        "completion_headline": ledger.get("headline") if isinstance(ledger, dict) else None,
        "externally_blocked": ledger.get("externally_blocked")
        if isinstance(ledger, dict)
        else None,
    }


def snapshot() -> dict[str, object]:
    contract = _read_path(CONTRACT, {})
    now = datetime.now(tz=UTC)
    report = {
        "schema_version": 1,
        "run_id": now.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": now.isoformat(),
        "started_epoch": now.timestamp(),
        "contract": str(CONTRACT.relative_to(ROOT)),
        "git": _git_state(),
        "conversion_metrics": conversion_metrics(),
        "artifacts": _artifact_state(contract if isinstance(contract, dict) else {}, None),
    }
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    tmp = BASELINE.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=1), "utf-8")
    os.replace(tmp, BASELINE)
    return report


def finalize(*, pipeline_rc: int, sweep_rc: int | None, cycle_rc: int | None) -> dict[str, object]:
    contract = _read_path(CONTRACT, {})
    baseline = _read_path(BASELINE, {})
    if not isinstance(baseline, dict) or not isinstance(
        baseline.get("started_epoch"), (int, float)
    ):
        baseline = snapshot()
        baseline_status = "RECREATED_MISSING_BASELINE"
    else:
        baseline_status = "MEASURED"
    current = conversion_metrics()
    artifacts = _artifact_state(
        contract if isinstance(contract, dict) else {}, float(baseline["started_epoch"])
    )
    scorecard = maturity_scorecard(current, artifacts, pipeline_rc=pipeline_rc)
    status_counts: dict[str, int] = {}
    for row in scorecard.values():
        state = str(row["status"])
        status_counts[state] = status_counts.get(state, 0) + 1
    completed = datetime.now(tz=UTC)
    report = {
        "schema_version": 1,
        "run_id": baseline.get("run_id"),
        "started_at": baseline.get("started_at"),
        "completed_at": completed.isoformat(),
        "duration_seconds": max(0.0, completed.timestamp() - float(baseline["started_epoch"])),
        "baseline_status": baseline_status,
        "pipeline": {"rc": pipeline_rc, "sweep_rc": sweep_rc, "cycle_rc": cycle_rc},
        "authority": "MEASUREMENT/HANDOFF ONLY -- no promotion, sizing, order or rail-change authority",
        "renewal": "NEVER_TERMINAL -- each run must expand or improve the next frontier",
        "git": _git_state(),
        "conversion_metrics": current,
        "deltas": _deltas(baseline.get("conversion_metrics", {}), current),
        "artifacts": artifacts,
        "maturity_scorecard": scorecard,
        "maturity_status_counts": status_counts,
        "harvest": _harvest(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    os.replace(tmp, OUT)
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "run_id": report["run_id"],
                    "completed_at": report["completed_at"],
                    "pipeline": report["pipeline"],
                    "deltas": {name: row["delta"] for name, row in report["deltas"].items()},
                    "maturity": status_counts,
                },
                default=str,
            )
            + "\n"
        )
    gaps = []
    for name, row in scorecard.items():
        if row["status"] == "HEALTHY":
            continue
        current_value = (
            None if row["status"] == "UNMEASURED" else 0.5 if row["status"] == "DEGRADED" else 0.0
        )
        gaps.append(
            Gap(
                aspect=f"overnight::{name}",
                source="measurement_quality" if row["status"] == "UNMEASURED" else "open_defect",
                current=current_value,
                ceiling=1.0,
                detail=f"{row['status']}: {row['evidence']}",
                action=str(row["next_action"]),
                artifact=str(OUT.relative_to(ROOT)),
                tags=("overnight-frontier", name),
            )
        )
    publish("overnight_frontier", gaps, directory=ROOT / "data" / "published_gaps")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot")
    final = sub.add_parser("finalize")
    final.add_argument("--pipeline-rc", type=int, required=True)
    final.add_argument("--sweep-rc", type=int)
    final.add_argument("--cycle-rc", type=int)
    args = parser.parse_args()
    if args.command == "snapshot":
        report = snapshot()
        print(f"overnight-frontier: baseline {report['run_id']}")
    else:
        report = finalize(
            pipeline_rc=args.pipeline_rc, sweep_rc=args.sweep_rc, cycle_rc=args.cycle_rc
        )
        print(
            f"overnight-frontier: handoff {report['run_id']} | "
            f"maturity {report['maturity_status_counts']} -> {OUT.relative_to(ROOT)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
