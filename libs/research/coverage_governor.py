"""Send the search where the book has no bet, not where the last backtest looked good.

THE MEASUREMENT THAT MAKES THIS NECESSARY, computed 2026-09-10 on the first run the coverage
modules had ever had:

    32 sleeves in the measurement, EFFECTIVE BREADTH 1.513, breadth ratio 0.047
    15 declared mechanism clusters, 4 occupied, largest cluster 52% of the traded book
    11 clusters EMPTY IN BOTH traded and certified

Thirty-two labels behaving like one and a half bets, with half the book in one cluster. N
uncorrelated edges of Sharpe s give s*sqrt(N), so the desk's stated lever -- "roughly twice as
many genuinely INDEPENDENT sources of P&L" -- is a claim about 1.513 and not about 32. Another
sleeve in `session_liquidity`, which already holds 26 of them, moves the first number and not the
second.

THAT IS THE ENTIRE ARGUMENT AGAINST BUYING MORE SCANNERS. A layer that finds more candidates along
axes already covered raises the label count and leaves growth where it is. Breadth is an
INDEPENDENCE property, and independence is measured -- so search budget has to be aimed at the
axes that are dark, which is what this file does.

THE INSTRUCTIONS WERE ALREADY WRITTEN. `alpha_breadth` publishes, for every empty cluster, a
`payer` (who pays this edge and why they must act) and a `hunt` (how to look for it). That is a
research brief per dark axis, sitting in an artifact that nothing read. This module ranks them and
turns them into owned queue tasks; it invents no mechanisms and proposes no parameters.

RANKING IS DERIVED, NOT JUDGED, so it can run unattended:

    EMPTINESS        a cluster empty in BOTH traded and certified is maximally orthogonal to the
                     current book -- there is nothing there to correlate with.
    RELIEF           a cluster whose absence lets one cluster hold 52% of the book is worth more
                     than one that would not change concentration.
    ACTIONABILITY    a cluster with a written `hunt` can be searched today; one without is a
                     naming exercise until someone writes the brief.

DELIBERATELY NOT INCLUDED: expected Sharpe, or anything read from a backtest. Ranking dark axes by
their past results is impossible -- they have none, which is what makes them dark -- and ranking
them by a NEIGHBOUR's results is how a search convinces itself the axis it already mined is the
promising one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Where `alpha_breadth` publishes the cluster map. Relative to the repo root.
BREADTH_REL = "desks/mt5/reports/EFFECTIVE_BREADTH.json"
#: Where `regime_coverage` publishes uncovered regime buckets.
REGIME_REL = "desks/mt5/reports/REGIME_COVERAGE.json"

#: Task kind for a dark-axis search. Owned by the `research` role in `libs.ops.org.DESK_ROLES`.
HUNT_KIND = "generate"

#: Dark axes queued per pass. The point is a short queue whose head is a real answer to "what is
#: being searched", not a backlog of every empty cluster at once.
BATCH = 4


@dataclass(frozen=True)
class DarkAxis:
    """One declared mechanism cluster the book has no bet in, and the brief for finding one."""

    cluster: str
    title: str
    payer: str
    hunt: str
    empty_in_both: bool
    priority: float
    components: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self)) | {"components": dict(self.components)}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def dark_axes(root: Path) -> list[DarkAxis]:
    """Every declared cluster with no bet in it, worst-covered first.

    Returns [] when the artifact is absent rather than guessing a map -- a governor that invented
    its own coverage picture would send the search wherever its default happened to point.
    """
    clusters = (_read(root / Path(*BREADTH_REL.split("/"))).get("clusters") or {})
    empty_detail = clusters.get("empty_detail") or []
    empty_both = set(clusters.get("empty_in_both") or [])
    counts = clusters.get("counts_traded") or {}
    share = float(clusters.get("largest_cluster_share_traded") or 0.0)

    out: list[DarkAxis] = []
    for row in empty_detail:
        if not isinstance(row, dict):
            continue
        name = str(row.get("cluster", ""))
        if not name:
            continue
        hunt = str(row.get("hunt", "") or "")
        comp = {
            # Empty in BOTH is the strongest form of orthogonality available: nothing is there to
            # correlate with. Empty in only one is weaker -- something already trades it.
            "emptiness": 1.0 if name in empty_both else 0.5,
            # A book with one cluster at 52% is fragile in a way a balanced one is not, so the
            # value of ANY new cluster rises with the concentration it would relieve.
            "relief": round(min(1.0, share), 4),
            # A written brief can be searched today. Without one this is a name, and queueing it
            # sends a worker to invent the mechanism it was supposed to look for.
            "actionable": 1.0 if hunt.strip() else 0.0,
        }
        out.append(DarkAxis(
            cluster=name, title=str(row.get("title", name)),
            payer=str(row.get("payer", "") or ""), hunt=hunt,
            empty_in_both=name in empty_both,
            priority=round(sum(comp.values()), 4), components=comp))
    # Ties break toward the cluster that is emptiest, then by name so the order is reproducible.
    out.sort(key=lambda a: (-a.priority, not a.empty_in_both, a.cluster))
    _ = counts
    return out


def census(root: Path) -> dict[str, Any]:
    """The coverage picture an operator reads, and the number that decides breadth."""
    breadth = _read(root / Path(*BREADTH_REL.split("/")))
    clusters = breadth.get("clusters") or {}
    eff = breadth.get("effective") or {}
    regime = _read(root / Path(*REGIME_REL.split("/")))
    axes = dark_axes(root)
    return {
        "effective_breadth": eff.get("effective_breadth"),
        "nominal_sleeves": eff.get("n_nominal"),
        "declared_clusters": clusters.get("declared"),
        "occupied": sorted(clusters.get("occupied_either") or []),
        "dark": [a.cluster for a in axes],
        "largest_cluster_share": clusters.get("largest_cluster_share_traded"),
        "meets_target": clusters.get("meets_target"),
        "regime_uncovered": regime.get("n_uncovered"),
        "regime_buckets": regime.get("n_buckets"),
        "why": ("search budget goes to clusters with no bet in them; adding another sleeve to a "
                "cluster that already holds half the book raises the label count and not the "
                "growth, because N uncorrelated edges of Sharpe s give s*sqrt(N)"),
    }


def enqueue(queue: Any, root: Path, *, org: Any = None, batch: int = BATCH) -> dict[str, Any]:
    """Queue a dark-axis hunt for the worst-covered clusters. Idempotent by cluster name.

    ONLY ACTIONABLE AXES. A cluster with no written brief is skipped and SAID, because queueing it
    sends a worker to invent the mechanism it was meant to search for -- which is how a hunt
    returns whatever the worker already believed.
    """
    from libs.ops.org import desk_org

    o = org or desk_org()
    queued, skipped = [], []
    for axis in dark_axes(root):
        if len(queued) >= batch:
            break
        if not axis.hunt.strip():
            skipped.append(f"{axis.cluster} (no written hunt brief)")
            continue
        task = o.delegate(
            queue, HUNT_KIND, frm="ops",
            payload={"cluster": axis.cluster, "title": axis.title, "payer": axis.payer,
                     "hunt": axis.hunt, "empty_in_both": axis.empty_in_both,
                     "components": axis.components},
            priority=axis.priority, dedupe_key=f"{HUNT_KIND}:cluster:{axis.cluster}")
        (queued.append(axis.cluster) if task is not None
         else skipped.append(f"{axis.cluster} (already being searched)"))
    return {"queued": queued, "skipped": skipped, "batch": batch,
            "why": ("a short queue whose head is a real answer to what is being searched, rather "
                    "than every empty cluster at once")}
