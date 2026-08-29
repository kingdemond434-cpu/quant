"""Certify a MECHANISM from its whole panel, not one instrument at a time.

WHY THIS EXISTS (principal, 2026-08-29)

    "n >= 50 is throughput-bound, not calendar-bound. More instruments per sleeve family
     reaches 50 sooner."

Measured the same day: forward sleeves were accruing about 8 trades per 12 days. Against a floor
of 20 trades that is a month per sleeve, and against 50 it is three months -- while the calendar
floor of 14 days was already nearly satisfied. The desk was not waiting for time. It was waiting
for one instrument to produce evidence that twelve instruments were producing in parallel and
throwing away, because every sleeve counted only its own fills.

`overnight_gap_decay` runs on 12 symbols. Pooled, its panel reaches 20 observations in under two
days instead of a month. That is the entire speedup, and it costs nothing in rigour PROVIDED the
pooled count is honest about what is actually independent -- which is the hard part, and the
reason this is a module rather than a `sum()`.

WHY NAIVE POOLING WOULD BE FRAUD. `session_range_breakout` also shows 15 sleeves -- across 5
symbols. Those 15 are mostly rr-variants of the same symbol and session: the same trade, exited
at three different targets. Summing them reports 15x the evidence for something nearer 5x, and
would certify a mechanism on its own reflections. The two families look identical in a sleeve
count and are completely different panels.

    CLUSTER = (symbol, date). A trade is a fresh observation if it is a different instrument OR a
    different day. Three rr-variants of EURUSD on the same day collapse to one; EURUSD and AUDNZD
    on the same day stay two; EURUSD on Monday and Tuesday stay two. This is the granularity at
    which the panel is actually independent, and `forward_verdict.effective_n` already discounts
    exactly this way, so pooled and per-sleeve evidence are judged by one rule.

THE BAR DOES NOT MOVE. Pooled evidence faces the identical thresholds a single sleeve faces --
14 days, 50 trades or 20 with an always-valid significant bound, and 20 EFFECTIVE observations.
Nothing here is a lower standard; it is the same standard applied to evidence the desk already
had and was discarding.

WHAT A FAMILY VERDICT DOES NOT DO. It does not promote every member. A mechanism being real does
not make each instrument's implementation of it real, and the instrument that does NOT work is
precisely the one naive pooling would drag in on its siblings' backs. A member inherits family
evidence only if it also clears `MEMBER_MIN_TRADES` on its own, earns positive expectancy on its
own, and is not a statistical outlier against its own family. See `member_inherits`.
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import forward_verdict as fv

#: A member must show this much of its own evidence before inheriting the family's. Pooling
#: raises confidence that the MECHANISM is real; it says nothing about whether this instrument
#: implements it, and a member with almost no fills of its own has shown nothing to check.
MEMBER_MIN_TRADES = 5

#: A member whose own mean R sits this many standard errors BELOW its family's is treated as
#: heterogeneous and refused, however healthy the family looks. One-sided on purpose: a member
#: outperforming its family is not evidence of a problem, and refusing it would throw away the
#: best instrument in the panel for the crime of being good.
MEMBER_OUTLIER_Z = -2.0


def _cluster_key(symbol: str, entry_time: Any) -> tuple[str, str]:
    """(instrument, calendar day) -- the granularity at which this panel is independent."""
    return (str(symbol), str(entry_time)[:10])


def pool(members: dict[str, Sequence[tuple[Any, float]]]) -> dict:
    """Pool a family's members into one panel.

    `members` maps sleeve key -> sequence of (entry_time, r_multiple). Returns the pooled series
    with its cluster labels, ready for `forward_verdict.verdict`.
    """
    rs: list[float] = []
    clusters: list[tuple[str, str]] = []
    per_member: dict[str, list[float]] = {}
    for key, trades in members.items():
        # The instrument is the leading component of the sleeve key by construction
        # (`SYMBOL.selector#params`), and pooling must not depend on a params blob that varies.
        symbol = key.split(".", 1)[0]
        own: list[float] = []
        for entry_time, r in trades:
            rs.append(float(r))
            clusters.append(_cluster_key(symbol, entry_time))
            own.append(float(r))
        per_member[key] = own
    return {"rs": rs, "clusters": clusters, "per_member": per_member,
            "n_members": len(members), "n_symbols": len({k.split(".", 1)[0] for k in members})}


def family_verdict(members: dict[str, Sequence[tuple[Any, float]]],
                   days_active: int) -> dict:
    """The family's own verdict, on the same fixed bar every single sleeve faces.

    `days_active` is the span of the OLDEST member's clock: the panel has been observed for as
    long as its longest-running member, and taking the newest instead would restart the family
    clock every time an instrument joined.
    """
    p = pool(members)
    v = fv.verdict(p["rs"], days_active, clusters=p["clusters"])
    v.update({"n_members": p["n_members"], "n_symbols": p["n_symbols"],
              "pooled": True, "rule": "family_evidence.family_verdict/2026-08-29"})
    # A panel of near-duplicates is the failure this module exists to refuse, and it should say
    # so in words rather than leaving a bare number to be read as bad luck.
    if not v["independent"]:
        v["reason"] = (f"{p['n_members']} members across only {p['n_symbols']} symbols pooled to "
                       f"{v['n_eff']} independent observations ({v['n_eff_basis']}); the panel is "
                       f"mostly variants of the same trade, not a cross-section")
    return v


def member_inherits(member_rs: Sequence[float], fam: dict,
                    pooled_rs: Sequence[float]) -> tuple[bool, str]:
    """May this member stand on the family's evidence? Returns (allowed, why).

    THREE CONDITIONS, each blocking a different way pooling goes wrong:
      * the family itself must have passed -- nothing to inherit otherwise;
      * the member must have its own minimum evidence and its own positive expectancy, because a
        real mechanism can still be unimplementable on a given instrument (spread, session, tick
        size), and that instrument is exactly the one pooling would otherwise carry;
      * the member must not sit significantly BELOW its family, which is the same point measured
        against the panel rather than against zero.
    """
    if not fam.get("promote"):
        return False, "family has no verdict to inherit"

    n = len(member_rs)
    if n < MEMBER_MIN_TRADES:
        return False, (f"own evidence {n} < {MEMBER_MIN_TRADES} trades: the family says the "
                       f"mechanism is real, this member has not shown it works here")

    own_mean = sum(member_rs) / n
    if own_mean <= 0:
        return False, f"own expectancy {own_mean:+.4f}R is not positive despite a healthy family"

    pooled = list(pooled_rs)
    if len(pooled) >= 2:
        pm = sum(pooled) / len(pooled)
        var = sum((x - pm) ** 2 for x in pooled) / (len(pooled) - 1)
        se = math.sqrt(var / n) if var > 0 and n > 0 else 0.0
        if se > 0:
            z = (own_mean - pm) / se
            if z < MEMBER_OUTLIER_Z:
                return False, (f"own mean {own_mean:+.4f}R is {z:.1f} SE below the family's "
                               f"{pm:+.4f}R: heterogeneous, not a member of this panel")
    return True, (f"family verdict inherited: own n={n}, own exp {own_mean:+.4f}R, consistent "
                  f"with a panel of {fam.get('n_members')} members over {fam.get('n_symbols')} "
                  f"symbols ({fam.get('n_eff')} independent observations)")


def group_by_family(rows: dict[str, dict]) -> dict[str, dict[str, list]]:
    """Split ledger rows into families using the family each row records.

    Reads the row's own `family` field and never parses it out of the key: the key shape has
    already changed once on this desk (`SYM.selector` -> `SYM.selector#params`) and a parser
    would have silently regrouped every sleeve the day it did.
    """
    out: dict[str, dict[str, list]] = defaultdict(dict)
    for key, row in rows.items():
        if not isinstance(row, dict):
            continue
        fam = row.get("family") or (row.get("identity") or {}).get("family")
        if not fam:
            continue
        out[str(fam)][key] = row
    return dict(out)
