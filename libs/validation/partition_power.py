"""PARTITION POWER (L1.63) -- can the partition behind a robustness certificate ever say NO?

WHAT THIS ASKS THAT NOTHING ELSE ON THE DESK DOES. Three wired gates certify that an edge is
"regime robust" -- ``libs/autodiscovery/regime.regime_robust`` (blocks REGISTRY promotion),
``libs/risk/sleeve_allocation`` min_regimes_positive (a sizing ceiling), and
``scripts/check_promotion_gate`` two_regimes (LIVE at 15% of book). All three implement the same
rule: split the return series into groups and require it to be net-positive in at least K of them.

Every existing instrument reads the OUTCOME of that rule. L1.43's ``check_fence_yield`` asks
whether a gate ever fired. L1.49's ``check_gate_reachability`` asks whether a gate ever RAN.
``gate_discrimination`` reads a per-gate accept/reject tally. NONE of them can see the case where
the gate runs on every candidate, is perfectly reachable, and returns True every single time
because THE PARTITION IT USES CANNOT PRODUCE A NEGATIVE GROUP for the edge in front of it. The
gate is not mis-calibrated and it is not dead; it is WELDED OPEN by its own choice of axis, and a
tally cannot distinguish "passed because the edge is robust" from "passed because this partition
was never able to fail".

THE PROVING INSTANCE IS THIS MODULE'S OWN FALSIFIER (capability hunt 2026-08-13 s0). The run was
built to test whether the desk's vol-tercile partition can see the state where funding carry dies.
Its FIRST version declared ``finds_dead_state`` the decisive criterion, then measured a carry proxy
that is non-positive on 3.0% of days -- so the criterion could not fire for EITHER axis, and the
verdict fell through to a spread comparison that answered a different question. The instrument
would have published REFUTED from a test that was structurally incapable of returning anything
else. That is the identical defect, one level up, and it was caught only because someone re-read
the instrument rather than its output.

MEASURED THE DAY THIS WAS BUILT, on 213 symbols x 2,384 days (2020-02-03 -> 2026-08-13) of the
desk's own D1 funding panel, carry sleeve = daily top-10 by trailing funding, net of 6bps/turn:
  vol terciles   : 3/3 groups positive  -> CANNOT FAIL
  funding state  : 2/2 groups positive  -> CANNOT FAIL
  funding breadth: 3/3 groups positive  -> CANNOT FAIL
Three different axes, 6.5 years, and not one of them can produce the failing group its certificate
claims to test for. The measured reason is that daily cross-sectional selection is itself the
hedge: unselected, the market's funding is non-positive on 40.6% of days; after top-10 selection,
3.0%. The certificate is not wrong -- it is EMPTY, and nothing on this desk could say so.

WHAT THIS IS NOT. It is a MEASUREMENT duty and a SCOPE EXPANSION. It lifts nothing, sizes nothing,
promotes nothing, opens no gate and loosens no statistical bar; it has no vocabulary for changing
any verdict it reads, and ``regime_robust`` behaves identically before and after. A WELDED reading
is never an argument to delete a gate -- L1.49's repair is UPWARD: make the partition capable of
failing (add an axis that can go negative), or record out loud that the certificate carries no
information for this edge. A smaller gauntlet that runs is not an improvement on a larger one that
does not.

UNMEASURED IS A REAL ANSWER (L1.28a). Below a usable group size the module refuses to grade rather
than manufacture a verdict, because "every group was positive" and "no group had enough
observations to tell" are different claims and only one of them is evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: A group smaller than this cannot support a mean/t-stat worth grading, so it is reported as
#: present-but-unusable rather than silently folded into the verdict (L1.60: skips are counted).
MIN_GROUP_OBS = 30

#: Below this many graded groups a partition is not a partition -- one group cannot discriminate.
MIN_GROUPS = 2

#: Label reserved for observations the partition could not place (warm-up, NaN, undefined).
UNLABELLED = "__none__"


@dataclass(frozen=True)
class GroupStat:
    """One group of a partition, graded on the same rule the wired gates use (net-positive?)."""

    name: str
    n: int
    mean: float
    t_stat: float
    positive: bool
    graded: bool


@dataclass(frozen=True)
class PartitionVerdict:
    """Whether a partition COULD have failed the edge it certified.

    ``can_fail`` is the whole point: it is True only when at least one graded group came out
    non-positive. A certificate issued by a partition with ``can_fail=False`` says nothing about
    the edge -- it would have passed anything.
    """

    name: str
    status: str                       # DISCRIMINATING | WELDED | UNMEASURED
    n_obs: int
    n_groups_graded: int
    n_groups_positive: int
    can_fail: bool
    min_group_mean: float | None
    why: str
    groups: list[GroupStat] = field(default_factory=list)
    attrition: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "status": self.status, "n_obs": self.n_obs,
            "n_groups_graded": self.n_groups_graded,
            "n_groups_positive": self.n_groups_positive,
            "can_fail": self.can_fail, "min_group_mean": self.min_group_mean,
            "why": self.why, "attrition": self.attrition,
            "groups": [
                {"name": g.name, "n": g.n, "mean": g.mean, "t_stat": g.t_stat,
                 "positive": g.positive, "graded": g.graded} for g in self.groups
            ],
        }


def _group_stat(name: str, r: np.ndarray, min_obs: int) -> GroupStat:
    n = len(r)
    if n < min_obs:
        # Present but unusable. Deliberately NOT dropped: an ungraded group is why a partition can
        # look welded when it is merely under-observed, and the caller must be able to see it.
        return GroupStat(name=name, n=n, mean=0.0, t_stat=0.0, positive=False, graded=False)
    mean = float(np.mean(r))
    sd = float(np.std(r, ddof=1))
    t = mean / (sd / np.sqrt(n)) if sd > 0 else 0.0
    return GroupStat(name=name, n=n, mean=round(mean, 10), t_stat=round(float(t), 4),
                     positive=bool(mean > 0.0), graded=True)


def partition_power(
    returns: np.ndarray,
    labels: np.ndarray,
    *,
    name: str,
    min_group_obs: int = MIN_GROUP_OBS,
) -> PartitionVerdict:
    """Grade one partition of one return series: could this axis have produced a failing group?

    ``labels`` must align with ``returns``; observations labelled :data:`UNLABELLED` are counted as
    attrition and excluded, never silently dropped (L1.60).
    """
    r = np.asarray(returns, dtype="float64")
    lab = np.asarray(labels).astype(str)
    attrition = {"observations": len(r), "unlabelled": 0, "ungraded_groups": 0}

    if len(r) != len(lab):
        return PartitionVerdict(
            name=name, status="UNMEASURED", n_obs=len(r), n_groups_graded=0,
            n_groups_positive=0, can_fail=False, min_group_mean=None,
            why=f"returns ({len(r)}) and labels ({len(lab)}) differ in length", attrition=attrition)

    keep = (lab != UNLABELLED) & np.isfinite(r)
    attrition["unlabelled"] = int((~keep).sum())
    r, lab = r[keep], lab[keep]

    stats = [_group_stat(g, r[lab == g], min_group_obs) for g in sorted(set(lab.tolist()))]
    graded = [g for g in stats if g.graded]
    attrition["ungraded_groups"] = len(stats) - len(graded)

    if len(graded) < MIN_GROUPS:
        return PartitionVerdict(
            name=name, status="UNMEASURED", n_obs=len(r), n_groups_graded=len(graded),
            n_groups_positive=sum(1 for g in graded if g.positive), can_fail=False,
            min_group_mean=None, groups=stats, attrition=attrition,
            why=(f"only {len(graded)} group(s) reached {min_group_obs} observations -- cannot "
                 "distinguish a welded partition from an under-observed one"))

    n_pos = sum(1 for g in graded if g.positive)
    can_fail = n_pos < len(graded)
    lo = min(g.mean for g in graded)
    if can_fail:
        status, why = "DISCRIMINATING", (
            f"{len(graded) - n_pos} of {len(graded)} graded groups are non-positive -- this "
            "partition is able to fail an edge, so a pass from it carries information")
    else:
        status, why = "WELDED", (
            f"all {len(graded)} graded groups are net-positive (min mean {lo:.3e}) over "
            f"{len(r)} observations -- this partition could not have failed this edge, so its "
            "certificate carries no information about it (L1.43)")
    return PartitionVerdict(
        name=name, status=status, n_obs=len(r), n_groups_graded=len(graded),
        n_groups_positive=n_pos, can_fail=can_fail, min_group_mean=round(lo, 10),
        groups=stats, attrition=attrition, why=why)


def summarise(verdicts: list[PartitionVerdict]) -> dict[str, Any]:
    """Roll up per-partition verdicts. An empty set reads UNMEASURED, never OK (L1.28a)."""
    if not verdicts:
        return {"status": "UNMEASURED", "n_partitions": 0, "n_welded": 0,
                "n_discriminating": 0, "n_unmeasured": 0,
                "why": "no partition was examined -- nothing here is evidence of health",
                "next_action": "wire at least one robustness partition into the fence's roster"}
    welded = [v for v in verdicts if v.status == "WELDED"]
    disc = [v for v in verdicts if v.status == "DISCRIMINATING"]
    unm = [v for v in verdicts if v.status == "UNMEASURED"]
    if welded:
        status = "WELDED"
        why = (f"{len(welded)} of {len(verdicts)} robustness partitions could not have failed the "
               f"edge they certify: {', '.join(v.name for v in welded)}")
        nxt = ("repair UPWARD (L1.49): give the certificate an axis able to produce a negative "
               "group, or record that it carries no information for this edge -- never delete it")
    elif not disc:
        status = "UNMEASURED"
        why = f"all {len(verdicts)} partitions are ungraded -- no verdict is available"
        nxt = "extend the panel or lower nothing: an under-observed partition is not a clean one"
    else:
        status = "OK"
        why = f"all {len(disc)} graded partitions are able to fail an edge"
        nxt = "none -- every certificate examined can say NO"
    return {"status": status, "n_partitions": len(verdicts), "n_welded": len(welded),
            "n_discriminating": len(disc), "n_unmeasured": len(unm),
            "why": why, "next_action": nxt,
            "partitions": [v.as_dict() for v in verdicts]}
