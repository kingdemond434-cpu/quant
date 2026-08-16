#!/usr/bin/env python3
"""
AUTODISCOVERY SURVIVOR AGGREGATOR
=================================
Collects survivors from each autodiscovery run, deduplicates, ranks by quality,
and prepares a summary for Claude delivery.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
sys.path.insert(0, str(_ROOT))

REPORTS_DIR = _ROOT / "reports" / "crypto_research"
WEB_DIR = _ROOT / "web"
AGGREGATE_FILE = _ROOT / "data" / "autodiscovery_survivors_aggregate.json"
LEDGER_FILE = _ROOT / "data" / "autodiscovery_survivors_ledger.jsonl"
CLAUDE_DELIVERY_FILE = _ROOT / "data" / "claude_survivor_delivery.json"


def load_latest_survivor_report() -> dict | None:
    """Load the latest survivor report from crypto_research."""
    reports = sorted(REPORTS_DIR.glob("survivor_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        return None
    return json.loads(reports[0].read_text("utf-8"))


def load_web_payload() -> dict | None:
    """Load the web payload with latest results."""
    web_file = WEB_DIR / "autodiscovery_crypto.json"
    if not web_file.exists():
        return None
    return json.loads(web_file.read_text("utf-8"))


def load_aggregate() -> dict:
    """Load existing aggregate."""
    if AGGREGATE_FILE.exists():
        return json.loads(AGGREGATE_FILE.read_text("utf-8"))
    return {"survivors": {}, "last_updated": None, "total_unique": 0, "run_history": []}


def save_aggregate(agg: dict) -> None:
    """Save aggregate to file."""
    AGGREGATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    AGGREGATE_FILE.write_text(json.dumps(agg, indent=1, default=str) + "\n", "utf-8")


def append_ledger(entries: list[dict]) -> None:
    """Append to immutable ledger."""
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, default=str) + "\n")


def deduplicate_survivors(new_survivors: list[dict], existing: dict) -> dict:
    """Deduplicate survivors by content hash / family+symbol+params."""
    updated = dict(existing)
    for surv in new_survivors:
        key = surv.get("content_hash") or f"{surv.get('family','')}_{surv.get('symbol','')}_{surv.get('params','')}"
        if key in updated:
            # Update if better quality
            old_q = updated[key].get("quality_score", 0)
            new_q = surv.get("quality_score", 0)
            if new_q > old_q:
                updated[key] = surv
                updated[key]["last_seen"] = datetime.now(UTC).isoformat()
                updated[key]["times_seen"] = updated[key].get("times_seen", 1) + 1
        else:
            surv["first_seen"] = datetime.now(UTC).isoformat()
            surv["last_seen"] = datetime.now(UTC).isoformat()
            surv["times_seen"] = 1
            updated[key] = surv
    return updated


def quality_score(surv: dict) -> float:
    """Compute a quality score for ranking."""
    score = 0.0
    # Validation metrics
    if "validation" in surv:
        v = surv["validation"]
        if "dsr" in v:
            score += min(v["dsr"] * 10, 50)  # cap at 50
        if "pbo" in v:
            score += max(0, (1 - v["pbo"]) * 20)
        if "cpcv_sharpe" in v:
            score += max(0, v["cpcv_sharpe"] * 10)
    # Forward evidence
    if "forward_days" in surv:
        score += min(surv["forward_days"] * 0.5, 30)
    if "forward_sharpe" in surv:
        score += max(0, surv["forward_sharpe"] * 10)
    # Regime robustness
    if surv.get("regime_robust"):
        score += 15
    # Capacity
    if surv.get("capacity_usd"):
        score += min(surv["capacity_usd"] / 100000, 10)
    return round(score, 2)


def extract_survivors_from_report(report: dict) -> list[dict]:
    """Extract survivor list from report format."""
    survivors = []
    if "survivors" in report:
        for s in report["survivors"]:
            s["quality_score"] = quality_score(s)
            survivors.append(s)
    elif "survivors_list" in report:
        for s in report["survivors_list"]:
            s["quality_score"] = quality_score(s)
            survivors.append(s)
    elif "results" in report:
        for r in report["results"]:
            if r.get("status") in ("survivor", "promoted_to_paper", "promoted_to_registry"):
                r["quality_score"] = quality_score(r)
                survivors.append(r)
    return survivors


def extract_from_web_payload(payload: dict) -> list[dict]:
    """Extract survivors from web payload."""
    survivors = []
    if "cycles" in payload:
        for cycle in payload["cycles"]:
            if "survivors" in cycle:
                for s in cycle["survivors"]:
                    s["quality_score"] = quality_score(s)
                    s["cycle_time"] = cycle.get("timestamp")
                    survivors.append(s)
    return survivors


def main():
    print(f"[{datetime.now(UTC).isoformat()}] Starting survivor aggregation...")

    # Load sources
    report = load_latest_survivor_report()
    web = load_web_payload()
    agg = load_aggregate()

    # Extract survivors
    all_new = []
    if report:
        all_new.extend(extract_survivors_from_report(report))
    if web:
        all_new.extend(extract_from_web_payload(web))

    if not all_new:
        print("No new survivors found in this cycle")
        return

    print(f"Found {len(all_new)} survivor entries in this cycle")

    # Deduplicate
    existing = agg.get("survivors", {})
    updated = deduplicate_survivors(all_new, existing)

    # Sort by quality
    sorted_survivors = sorted(updated.values(), key=lambda x: x.get("quality_score", 0), reverse=True)

    # Update aggregate
    agg["survivors"] = {k: v for k, v in {f"surv_{i}": s for i, s in enumerate(sorted_survivors)}.items()}
    agg["total_unique"] = len(sorted_survivors)
    agg["last_updated"] = datetime.now(UTC).isoformat()
    agg["run_history"].append({
        "time": datetime.now(UTC).isoformat(),
        "new_this_run": len(all_new),
        "total_unique": len(sorted_survivors)
    })
    # Keep last 1000 runs
    if len(agg["run_history"]) > 1000:
        agg["run_history"] = agg["run_history"][-1000:]

    # Save
    save_aggregate(agg)
    append_ledger(all_new)

    # Prepare Claude delivery (top 20 by quality)
    top_20 = sorted_survivors[:20]
    delivery = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_survivors": len(sorted_survivors),
        "new_this_cycle": len(all_new),
        "top_survivors": [
            {
                "rank": i + 1,
                "family": s.get("family"),
                "subtype": s.get("subtype"),
                "symbol": s.get("symbol"),
                "params": s.get("params"),
                "quality_score": s.get("quality_score"),
                "validation": s.get("validation", {}),
                "forward_days": s.get("forward_days"),
                "forward_sharpe": s.get("forward_sharpe"),
                "regime_robust": s.get("regime_robust"),
                "capacity_usd": s.get("capacity_usd"),
                "content_hash": s.get("content_hash"),
                "mechanism": s.get("mechanism"),
            }
            for i, s in enumerate(top_20)
        ],
        "summary": {
            "total_unique_survivors": len(sorted_survivors),
            "avg_quality": round(sum(s.get("quality_score", 0) for s in sorted_survivors) / max(len(sorted_survivors), 1), 2),
            "families_represented": list(set(s.get("family") for s in sorted_survivors if s.get("family"))),
            "symbols_represented": list(set(s.get("symbol") for s in sorted_survivors if s.get("symbol"))),
        }
    }

    CLAUDE_DELIVERY_FILE.parent.mkdir(parents=True, exist_ok=True)
    CLAUDE_DELIVERY_FILE.write_text(json.dumps(delivery, indent=1, default=str) + "\n", "utf-8")

    print(f"Total unique survivors: {len(sorted_survivors)}")
    print(f"Top survivor quality: {sorted_survivors[0].get('quality_score', 0) if sorted_survivors else 0}")
    print(f"Claude delivery written to {CLAUDE_DELIVERY_FILE}")

    # Print top 5 for visibility
    for i, s in enumerate(top_20[:5]):
        print(f"  #{i+1}: {s.get('family','?')}/{s.get('subtype','?')} on {s.get('symbol','?')} | Q={s.get('quality_score',0)} | FwdSharpe={s.get('forward_sharpe','?')}")


if __name__ == "__main__":
    main()
