"""Factory status -- Information Advantage Score + dataset/sleeve registries -> web/factory.json.

Consolidates the governance view the mission asks for: how much information advantage we've
accumulated (datasets, mechanisms, orthogonal sleeves, forward-archive depth), the dataset registry
ranked by ROI, the free-data next priorities, and the portfolio-Sharpe milestone path. Rising IAS is
progress even when no deployable edge exists yet. Reads existing reports; recomputes nothing heavy.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.factory.registry import (
    DATASETS,
    best_dataset_priorities,
    free_next_priorities,
    information_advantage_score,
    milestone_path,
)

_WEB = Path("web/factory.json")
_CRYPTO = Path("reports/crypto_portfolio/report.json")
_METRICS = Path("data/crypto_metrics.parquet")


def main() -> None:
    cp = json.loads(_CRYPTO.read_text("utf-8")) if _CRYPTO.exists() else {}
    results = [r for r in cp.get("results", []) if not str(r.get("sleeve")).startswith("portfolio")]
    corr = pd.DataFrame(cp.get("correlations", {}))

    def sharpe(r: dict[str, object]) -> float:
        v = r.get("ann_sharpe")
        return float(v) if isinstance(v, (int, float)) else 0.0

    active = [r["sleeve"] for r in results if sharpe(r) > 0.4]
    orthogonal = []
    for s in active:
        if s in corr.columns:
            others = corr[s].drop(labels=[s], errors="ignore").abs()
            if others.empty or float(others.max()) < 0.3:
                orthogonal.append(s)
    validated = [r["sleeve"] for r in results if r.get("survived")]

    archive_days = 0
    if _METRICS.exists():
        archive_days = int(pd.read_parquet(_METRICS)["ts"].dt.date.nunique())

    datasets_in_use = sum(1 for d in DATASETS if d.status == "in_use")
    ias = information_advantage_score(
        datasets_in_use=datasets_in_use, mechanisms=len({r.get("sleeve") for r in results}),
        active_sleeves=len(active), validated_sleeves=len(validated),
        orthogonal_sleeves=len(orthogonal), archive_days=archive_days)

    counts: dict[str, int] = {}                          # family breadth from registry mapping
    from libs.factory.registry import SLEEVE_FAMILY
    for s in active:
        fam = SLEEVE_FAMILY.get(s)
        if fam:
            counts[fam] = counts.get(fam, 0) + 1
    ms = milestone_path(float(cp.get("headline_sharpe", 0.0) or 0.0), counts)

    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "information_advantage": ias,
        "milestone": {"current": ms.current, "next": ms.next_milestone, "gap": ms.gap,
                      "families_complete": ms.families_complete, "bottleneck": ms.bottleneck},
        "active_sleeves": active, "orthogonal_sleeves": orthogonal, "validated_sleeves": validated,
        "datasets": best_dataset_priorities(8),
        "free_next": free_next_priorities(6),
        "archive_days": archive_days,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    print(f"Information Advantage Score = {ias['score']}  "
          f"(active {len(active)}, orthogonal {len(orthogonal)}, validated {len(validated)}, "
          f"archive {archive_days}d)")
    print(f"milestone: at {ms.current} -> next {ms.next_milestone} (gap {ms.gap}); "
          f"bottleneck family = {ms.bottleneck}")
    print(f"wrote {_WEB}")


if __name__ == "__main__":
    main()
