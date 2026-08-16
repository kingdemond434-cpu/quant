#!/usr/bin/env python3
"""
MASTER SURVIVOR AGGREGATOR
==========================
Collects survivors from ALL research pipelines and prepares a unified
delivery for Claude. Runs after each research cycle.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
sys.path.insert(0, str(_ROOT))

DELIVERY_FILE = _ROOT / "data" / "claude_survivor_delivery.json"
AGGREGATE_FILE = _ROOT / "data" / "master_survivor_aggregate.json"
LEDGER_FILE = _ROOT / "data" / "master_survivor_ledger.jsonl"


def load_json(path: Path) -> dict | list | None:
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def extract_autodiscovery_survivors() -> list[dict]:
    """Extract survivors from autodiscovery crypto web payload."""
    web = load_json(_ROOT / "web" / "autodiscovery_crypto.json")
    if not web:
        return []
    survivors = []
    for s in web.get("survivors", []):
        s = dict(s)
        s["source"] = "autodiscovery_crypto"
        s["quality_score"] = s.get("quality_score", 0)
        survivors.append(s)
    return survivors


def extract_alpha_factory_recs() -> list[dict]:
    """Extract recommendations from alpha factory."""
    web = load_json(_ROOT / "web" / "alpha_factory.json")
    if not web:
        return []
    recs = []
    for r in web.get("recommendations", []):
        r = dict(r)
        r["source"] = "alpha_factory"
        r["quality_score"] = r.get("quality_score", 0)
        recs.append(r)
    return recs


def extract_paper_sleeve_forward() -> list[dict]:
    """Extract ACCRUING paper sleeves from forward runner."""
    web = load_json(_ROOT / "web" / "paper_sleeve_forward.json")
    if not web:
        return []
    sleeves = []
    for name, s in web.get("sleeves", {}).items():
        if s.get("evidence") == "ACCRUING":
            s = dict(s)
            s["name"] = name
            s["source"] = "paper_sleeve_forward"
            s["quality_score"] = s.get("progress_to_resolution", 0) * 100
            yield s


def extract_stage_a_screens() -> list[dict]:
    """Extract SCREEN-INTERESTING and SCREEN-WEAK from axis screens."""
    reports_dir = _ROOT / "reports" / "axis_screens"
    results = []
    for f in reports_dir.glob("*.json"):
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for cell in doc.get("screen_outputs", []):
            verdict = str(cell.get("verdict", ""))
            if verdict in ("SCREEN-INTERESTING", "SCREEN-WEAK"):
                cell = dict(cell)
                cell["source"] = f"stage_a_screen:{f.stem}"
                cell["quality_score"] = cell.get("quality_score", 0)
                yield cell


def extract_full_sweep_survivors() -> list[dict]:
    """Extract SCREEN-UNRATED survivors from full sweep."""
    path = _ROOT / "reports" / "axis_screens" / "conv_full_sweep__survivors.json"
    doc = load_json(_ROOT / path)
    if not doc:
        return []
    results = []
    for cell in doc.get("screen_outputs", []):
        if str(cell.get("verdict", "")) == "SCREEN-UNRATED":
            cell = dict(cell)
            cell["source"] = "full_sweep_survivors"
            cell["quality_score"] = cell.get("quality_score", 0)
            results.append(cell)
    return results


def extract_perpdex_survivors() -> list[dict]:
    """Extract SCREEN-INTERESTING and SCREEN-WEAK from perpdex funding screen."""
    path = _ROOT / "reports" / "axis_screens" / "perpdex_funding.json"
    doc = load_json(_ROOT / path)
    if not doc:
        return []
    results = []
    for cell in doc.get("screen_outputs", []):
        verdict = str(cell.get("verdict", ""))
        if verdict in ("SCREEN-INTERESTING", "SCREEN-WEAK"):
            cell = dict(cell)
            cell["source"] = "perpdex_funding"
            cell["quality_score"] = cell.get("quality_score", 0)
            results.append(cell)
    return results


def extract_paper_sleeve_queue() -> list[dict]:
    """Extract queued paper sleeves waiting for slot."""
    path = _ROOT / "data" / "paper_sleeve_queue.json"
    doc = load_json(_ROOT / path)
    if not doc:
        return []
    results = []
    for q in doc.get("queued", []):
        q = dict(q)
        q["source"] = "paper_sleeve_queue"
        q["quality_score"] = q.get("quality_score", 0)
        results.append(q)
    return results


def quality_score(s: dict) -> float:
    """Compute unified quality score."""
    score = 0.0
    # Validation metrics
    v = s.get("validation", {})
    if isinstance(v, dict):
        if "dsr" in v:
            score += min(v["dsr"] * 10, 50)
        if "pbo" in v:
            score += max(0, (1 - v["pbo"]) * 20)
        if "cpcv_sharpe" in v:
            score += max(0, v["cpcv_sharpe"] * 10)
    # Forward evidence
    if "forward_days" in s:
        score += min(s["forward_days"] * 0.5, 30)
    if "forward_sharpe" in s:
        score += max(0, s["forward_sharpe"] * 10)
    if "forward_ann_sharpe_8h" in s:
        score += max(0, s["forward_ann_sharpe_8h"] * 5)
    if "forward_ann_sharpe" in s:
        score += max(0, s["forward_ann_sharpe"] * 10)
    # Regime robustness
    if s.get("regime_robust"):
        score += 15
    # Capacity
    cap = s.get("capacity_usd")
    if cap:
        score += min(cap / 100000, 10)
    # Progress to resolution (paper sleeves)
    if "progress_to_resolution" in s:
        score += s["progress_to_resolution"] * 50
    # Forward sharpe (8h shadow)
    if "forward_ann_sharpe_8h" in s:
        score += max(0, s["forward_ann_sharpe_8h"] * 5)
    return round(score, 2)


def deduplicate(all_survivors: list[dict]) -> dict:
    """Deduplicate by content hash or family+symbol+params."""
    unique = {}
    for s in all_survivors:
        key = s.get("content_hash") or f"{s.get('family','')}_{s.get('symbol','')}_{s.get('params','')}_{s.get('subtype','')}"
        if key in unique:
            # Keep higher quality
            if s.get("quality_score", 0) > unique[key].get("quality_score", 0):
                unique[key] = s
                unique[key]["times_seen"] = unique[key].get("times_seen", 1) + 1
                unique[key]["last_seen"] = datetime.now(UTC).isoformat()
        else:
            s["first_seen"] = s.get("first_seen", datetime.now(UTC).isoformat())
            s["last_seen"] = datetime.now(UTC).isoformat()
            s["times_seen"] = 1
            unique[key] = s
    return unique


def main():
    print(f"[{datetime.now(UTC).isoformat()}] Starting MASTER survivor aggregation...")

    # Extract from all sources
    all_survivors = []
    all_survivors.extend(extract_autodiscovery_survivors())
    all_survivors.extend(extract_alpha_factory_recs())
    all_survivors.extend(list(extract_paper_sleeve_forward()))
    all_survivors.extend(list(extract_stage_a_screens()))
    all_survivors.extend(extract_full_sweep_survivors())
    all_survivors.extend(extract_perpdex_survivors())
    all_survivors.extend(extract_paper_sleeve_queue())

    print(f"Collected {len(all_survivors)} raw entries from all sources")

    if not all_survivors:
        print("No survivors found across all sources")
        return

    # Compute quality scores
    for s in all_survivors:
        s["quality_score"] = quality_score(s)

    # Deduplicate
    unique = deduplicate(all_survivors)
    sorted_survivors = sorted(unique.values(), key=lambda x: x.get("quality_score", 0), reverse=True)

    print(f"Total unique survivors: {len(sorted_survivors)}")

    # Load existing aggregate
    agg_path = _ROOT / "data" / "master_survivor_aggregate.json"
    agg = {"survivors": {}, "last_updated": None, "total_unique": 0, "run_history": []}
    if agg_path.exists():
        try:
            agg = json.loads(agg_path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    # Update with new data
    existing = agg.get("survivors", {})
    for k, v in unique.items():
        if k in existing:
            if v.get("quality_score", 0) > existing[k].get("quality_score", 0):
                existing[k] = v
                existing[k]["times_seen"] = existing[k].get("times_seen", 1) + 1
                existing[k]["last_seen"] = datetime.now(UTC).isoformat()
        else:
            v["first_seen"] = v.get("first_seen", datetime.now(UTC).isoformat())
            v["last_seen"] = datetime.now(UTC).isoformat()
            v["times_seen"] = 1
            existing[k] = v

    # Sort and update aggregate
    sorted_survivors = sorted(existing.values(), key=lambda x: x.get("quality_score", 0), reverse=True)
    agg["survivors"] = {f"surv_{i}": s for i, s in enumerate(sorted_survivors)}
    agg["total_unique"] = len(sorted_survivors)
    agg["last_updated"] = datetime.now(UTC).isoformat()
    agg["run_history"].append({
        "time": datetime.now(UTC).isoformat(),
        "total_unique": len(sorted_survivors),
        "sources_checked": 7
    })
    if len(agg["run_history"]) > 1000:
        agg["run_history"] = agg["run_history"][-1000:]

    # Save aggregate
    agg_path = _ROOT / "data" / "master_survivor_aggregate.json"
    agg_path.parent.mkdir(parents=True, exist_ok=True)
    agg_path.write_text(json.dumps(agg, indent=1, default=str) + "\n", "utf-8")

    # Append to ledger
    ledger_path = _ROOT / "data" / "master_survivor_ledger.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        for s in all_survivors:
            f.write(json.dumps(s, default=str) + "\n")

    # Prepare Claude delivery (top 30)
    top_30 = sorted_survivors[:30]
    delivery = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_survivors": len(sorted_survivors),
        "top_survivors": [
            {
                "rank": i + 1,
                "source": s.get("source"),
                "family": s.get("family"),
                "subtype": s.get("subtype"),
                "symbol": s.get("symbol"),
                "params": s.get("params"),
                "verdict": s.get("verdict") or s.get("status"),
                "quality_score": s.get("quality_score"),
                "validation": s.get("validation", {}),
                "forward_days": s.get("forward_days"),
                "forward_sharpe": s.get("forward_sharpe") or s.get("forward_ann_sharpe") or s.get("forward_ann_sharpe_8h"),
                "regime_robust": s.get("regime_robust"),
                "capacity_usd": s.get("capacity_usd"),
                "content_hash": s.get("content_hash"),
                "mechanism": s.get("mechanism"),
                "progress_to_resolution": s.get("progress_to_resolution"),
            }
            for i, s in enumerate(top_30)
        ],
        "summary": {
            "total_unique_survivors": len(sorted_survivors),
            "avg_quality": round(sum(s.get("quality_score", 0) for s in sorted_survivors) / max(len(sorted_survivors), 1), 2),
            "families_represented": list(set(s.get("family") for s in sorted_survivors if s.get("family"))),
            "symbols_represented": list(set(s.get("symbol") for s in sorted_survivors if s.get("symbol"))),
            "sources_represented": list(set(s.get("source") for s in sorted_survivors)),
            "by_source": {src: sum(1 for s in sorted_survivors if s.get("source") == src) for src in set(s.get("source") for s in sorted_survivors)},
        }
    }

    delivery_path = _ROOT / "data" / "claude_survivor_delivery.json"
    delivery_path.parent.mkdir(parents=True, exist_ok=True)
    delivery_path.write_text(json.dumps(delivery, indent=1, default=str) + "\n", "utf-8")

    print(f"Total unique survivors: {len(sorted_survivors)}")
    print(f"Claude delivery written to {delivery_path}")

    # Print top 10
    for i, s in enumerate(sorted_survivors[:10]):
        print(f"  #{i+1}: {s.get('source','?')} | {s.get('family','?')}/{s.get('subtype','?')} on {s.get('symbol','?')} | Q={s.get('quality_score',0)} | verdict={s.get('verdict','?')}")


if __name__ == "__main__":
    from datetime import UTC, datetime
    main()
