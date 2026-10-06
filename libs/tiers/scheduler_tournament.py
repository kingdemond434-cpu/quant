"""METHOD COMPETITION THAT MOVES THE SCHEDULER (Tier S audit rows AC13 and I12).

THE GAP, IN THE AUDIT'S OWN WORDS. AC13: *"adoption must change the real gauntlet or scheduler"* --
the arena (`libs/research/arena.py`) recorded LEADS / TRAILS per research arm and the Red Queen's
S33 scheduler champion beat the incumbent split on held-out days, and neither number reached the
thing that decides which leg runs next and for how long. I12: *"researcher_market and
meta_benchmark ... hold no budget authority"* -- they need "a scored tournament with a randomized
budget holdout".

WHAT DECIDES COMPUTE. `desks/mt5/research/cycle_pricing.build_plan` -- every hourly leg's seconds
and the order the legs run in. This module produces the per-leg WEIGHTS it now reads
(`reports/tier_s/SCHEDULER_STEER.json`, written by `tier_s.organ_steer`):

    contestants   arena            LEADS arms' legs up, TRAILS arms' legs down (bandit arms ->
                                   legs via `research_budget.LEG_ARMS`)
                  red_queen        the S33 scheduler champion's CURRENT split over producers, once
                                   it beat the incumbent on held-out days (its adoption), folded
                                   onto legs against the equal-share baseline
                  researcher_market  the market's per-leg prices against their median
                  meta_benchmark   the sealed immune benchmark: validation legs gain weight while
                                   the desk is getting easier to fool and give it back once it is
                                   not (immune score against its own trailing mean)
    tournament    each contestant's past tilts are scored against what the legs then REALISED
                  (novel hypotheses per CPU-hour, the hour after the tilt was published); its
                  AUTHORITY is a Hedge weight on that score -- a contestant whose tilts point at
                  the legs that went on to produce gains authority, one whose tilts point away
                  loses it. Unscored contestants sit at the prior (equal) authority.
    holdout       a SEEDED RANDOM slice (`HOLDOUT_SHARE`, re-drawn every hour from
                  sha256(salt|hour)) of the legs stays on the PRIOR allocation (weight 1.0) as a
                  control. The rest are treated. The holdout-versus-treated comparison
                  (`control_arm.compare`, Welch one-sided 5%) is published in the artifact. ONLY
                  an ADMITTED comparison lets the weights reach the scheduler: REJECTED,
                  UNDECIDED and UNMEASURED (too few legs) all default to NEUTRAL -- every weight
                  back to 1.0 -- authority earned, never assumed (verifier pre-check, #235).

THE LAWS IT KEEPS, by construction and pinned by tests:

  * TWO-SIDED, BUT BACKPRESSURE GOES TO THE JUDGE ONLY. A weight lives in
    [1 - MAX_TILT, 1 + MAX_TILT], and only a leg in `down_ok` (the judge / validation side, by the
    repo's own leg departments) may sit below 1.0. Every mining / research-generation leg is
    UP-ONLY: its weight is floored at 1.0, so a tournament can fund it more and never less.
  * NEVER A CUT. The weights are renormalised to mean 1.0 over the steered legs, and
    `cycle_pricing` applies them to the leg's PRICE SCORE, whose factor is floored at par (1.0x
    base) with a never-reduced total. A down-weighted leg runs later and wins less spare; it keeps
    its base seconds. Research generation is reallocated, never reduced.
  * A SUSPENDED ORGAN CARRIES NO AUTHORITY (`libs.tiers.authority.suspended`): its contestant is
    dropped from the tournament before anything is combined, and the artifact says so.
  * UNMEASURED IS NOT ZERO. A leg with no CPU in its window has no outcome; a contestant with no
    scored hours keeps the prior authority; an absent input proposes nothing (weight 1.0).

Research side only: nothing here sizes, admits, certifies or places.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from libs.tiers import control_arm

CONTESTANTS: tuple[str, ...] = ("arena", "red_queen", "researcher_market", "meta_benchmark")
#: the organ whose `authority.suspended(...)` gates each contestant (meta_benchmark's verdicts are
#: published by the `immune` organ, so its contract is the immune organ's)
CONTESTANT_ORGAN: dict[str, str] = {"arena": "arena", "red_queen": "red_queen",
                                    "researcher_market": "market", "meta_benchmark": "immune"}
#: a weight never leaves [1 - MAX_TILT, 1 + MAX_TILT]
MAX_TILT = 0.5
#: the arena's step for a decisive verdict (LEADS up, TRAILS down)
ARENA_STEP = 0.25
#: share of the hour's legs held on the prior allocation
HOLDOUT_SHARE = 0.2
SALT = "scheduler_steer"
#: Hedge learning rate on the standardised mean score
ETA = 1.0
#: scored hours below which a contestant keeps the prior authority
MIN_HOURS = 3
#: the rolling window the holdout comparison and the tournament scores are re-derived over
WINDOW_H = 14 * 24
EPS = 1e-9


def _clip(x: float) -> float:
    return max(1.0 - MAX_TILT, min(1.0 + MAX_TILT, float(x)))


# ------------------------------------------------------------------------------------------------
# contestants' proposals: {leg: tilt}, 1.0 = no opinion
# ------------------------------------------------------------------------------------------------

def arena_tilts(arms: Mapping[str, Mapping[str, Any]],
                leg_arms: Mapping[str, Sequence[str]]) -> dict[str, float]:
    """LEADS -> 1 + ARENA_STEP, TRAILS -> 1 - ARENA_STEP, anything else 1.0; a leg takes the mean
    over the arms it serves. An arm with no recorded verdict says nothing."""
    out: dict[str, float] = {}
    for leg, names in leg_arms.items():
        vals = []
        for a in names:
            v = str((arms.get(a) or {}).get("verdict") or "")
            vals.append(1.0 + ARENA_STEP if v == "LEADS" else
                        1.0 - ARENA_STEP if v == "TRAILS" else 1.0)
        if vals:
            t = _clip(sum(vals) / len(vals))
            if abs(t - 1.0) > EPS:
                out[str(leg)] = round(t, 6)
    return out


def red_queen_tilts(split: Mapping[str, float],
                    producer_leg: Mapping[str, str | None]) -> dict[str, float]:
    """The adopted scheduler champion's split over PRODUCERS, folded onto legs: a leg's tilt is the
    split its producers hold against the equal share they would hold (n_on_leg / n_producers)."""
    n = len(split)
    if n < 2:
        return {}
    held: dict[str, float] = {}
    count: dict[str, int] = {}
    for prod, w in split.items():
        leg = producer_leg.get(prod)
        if not leg:
            continue
        held[leg] = held.get(leg, 0.0) + max(0.0, float(w))
        count[leg] = count.get(leg, 0) + 1
    tot = sum(max(0.0, float(w)) for w in split.values()) or 1.0
    out: dict[str, float] = {}
    for leg, h in held.items():
        base = count[leg] / n
        t = _clip((h / tot) / base) if base > 0 else 1.0
        if abs(t - 1.0) > EPS:
            out[leg] = round(t, 6)
    return out


def market_tilts(leg_prices: Mapping[str, float]) -> dict[str, float]:
    """The researcher market's per-leg price against the median price, clipped."""
    vals = sorted(float(v) for v in leg_prices.values() if isinstance(v, (int, float))
                  and math.isfinite(float(v)))
    if len(vals) < 2:
        return {}
    k = len(vals)
    med = vals[k // 2] if k % 2 else 0.5 * (vals[k // 2 - 1] + vals[k // 2])
    if med <= 0:
        return {}
    out: dict[str, float] = {}
    for leg, v in leg_prices.items():
        if isinstance(v, (int, float)) and math.isfinite(float(v)):
            t = _clip(float(v) / med)
            if abs(t - 1.0) > EPS:
                out[str(leg)] = round(t, 6)
    return out


def meta_benchmark_tilts(history: Sequence[float], current: float | None,
                         validate_legs: Iterable[str]) -> dict[str, float]:
    """Validation legs tilt UP while the sealed benchmark's immune score sits below its trailing
    mean (the desk is getting easier to fool) and DOWN while it sits above it. Two-sided; at most
    MAX_TILT; nothing without three prior readings."""
    hist = [float(h) for h in history if isinstance(h, (int, float))]
    if current is None or len(hist) < 3:
        return {}
    mu = sum(hist) / len(hist)
    sd = math.sqrt(sum((h - mu) ** 2 for h in hist) / (len(hist) - 1)) if len(hist) > 1 else 0.0
    z = (mu - float(current)) / max(sd, 0.01)
    t = _clip(1.0 + MAX_TILT * max(-1.0, min(1.0, z / 2.0)))
    if abs(t - 1.0) <= EPS:
        return {}
    return {str(leg): round(t, 6) for leg in validate_legs}


# ------------------------------------------------------------------------------------------------
# the tournament
# ------------------------------------------------------------------------------------------------

def score_hour(tilts: Mapping[str, float], outcomes: Mapping[str, float]) -> float | None:
    """How well one contestant's tilts pointed at what the legs then realised: the tilt-weighted
    excess outcome, sum (t - 1)(y - ybar) / sum |t - 1| over the legs that have both. None when the
    contestant tilted none of the measured legs (no opinion is not a score)."""
    legs = [lg for lg in outcomes if lg in tilts and abs(float(tilts[lg]) - 1.0) > EPS]
    if not legs or len(outcomes) < 2:
        return None
    ybar = sum(float(v) for v in outcomes.values()) / len(outcomes)
    num = sum((float(tilts[lg]) - 1.0) * (float(outcomes[lg]) - ybar) for lg in legs)
    den = sum(abs(float(tilts[lg]) - 1.0) for lg in legs)
    return num / den if den > 0 else None


def authorities(scores: Mapping[str, Sequence[float]], present: Sequence[str],
                eta: float = ETA, min_hours: int = MIN_HOURS) -> dict[str, dict[str, Any]]:
    """Hedge over the contestants that proposed this hour: a_c proportional to
    exp(eta x mean_c / pooled sd). A contestant with fewer than `min_hours` scored hours keeps the
    prior (exponent 0). Two-sided: a positive record raises authority, a negative one lowers it."""
    pooled = [float(s) for c in present for s in (scores.get(c) or ())]
    sd = 0.0
    if len(pooled) > 1:
        mu = sum(pooled) / len(pooled)
        sd = math.sqrt(sum((x - mu) ** 2 for x in pooled) / (len(pooled) - 1))
    scale = sd if sd > EPS else (max((abs(x) for x in pooled), default=0.0) or 1.0)
    raw: dict[str, float] = {}
    rows: dict[str, dict[str, Any]] = {}
    for c in present:
        s = [float(x) for x in (scores.get(c) or ())]
        measured = len(s) >= min_hours
        mean = (sum(s) / len(s)) if s else None
        expo = eta * (mean or 0.0) / scale if measured else 0.0
        raw[c] = math.exp(max(-20.0, min(20.0, expo)))
        rows[c] = {"hours_scored": len(s), "mean_score": None if mean is None else round(mean, 6),
                   "status": "MEASURED" if measured else "PRIOR"}
    tot = sum(raw.values()) or 1.0
    for c in present:
        rows[c]["authority"] = round(raw[c] / tot, 6)
    return rows


def combine(proposals: Mapping[str, Mapping[str, float]],
            auth: Mapping[str, float]) -> dict[str, float]:
    """w_leg = 1 + sum_c a_c (t_c,leg - 1), clipped, then renormalised to mean 1.0 over the legs any
    contestant tilted -- a reallocation in weight space, never a net cut."""
    legs = sorted({lg for p in proposals.values() for lg in p})
    w: dict[str, float] = {}
    for lg in legs:
        x = 1.0 + sum(float(auth.get(c, 0.0)) * (float(p.get(lg, 1.0)) - 1.0)
                      for c, p in proposals.items())
        w[lg] = _clip(x)
    if not w:
        return {}
    mean = sum(w.values()) / len(w)
    return {lg: round(_clip(v / mean) if mean > 0 else 1.0, 6) for lg, v in w.items()}


def holdout(legs: Iterable[str], hour_key: str, share: float = HOLDOUT_SHARE,
            salt: str = SALT) -> list[str]:
    """The seeded random slice held on the prior allocation this hour: a fresh draw every hour
    (seed = sha256(salt|hour)), reproducible by anyone holding the hour key. At least one leg is
    held out whenever two or more are steered."""
    pool = sorted(set(legs))
    if len(pool) < 2:
        return []
    seed = int(hashlib.sha256(f"{salt}|{hour_key}".encode()).hexdigest()[:16], 16)
    k = max(1, round(share * len(pool)))
    pick = np.random.default_rng(seed).choice(len(pool), size=k, replace=False)
    return sorted(pool[int(i)] for i in pick)


def holdout_comparison(assignments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Treated versus held-out leg-hours, on the realised outcome, for the legs the tournament
    wanted to move UP (where a reallocation must pay) and DOWN (where it must not cost), plus all
    steered legs. `primary` is the up-weighted comparison; REJECTED there withdraws the steer."""
    arms: dict[str, dict[str, list[float]]] = {
        k: {"treated": [], "holdout": []} for k in ("up", "down", "all")}
    for a in assignments:
        outcomes = a.get("outcomes")
        if not isinstance(outcomes, dict):
            continue
        for leg, row in (a.get("legs") or {}).items():
            if leg not in outcomes or not isinstance(row, dict):
                continue
            due = float(row.get("due") or 1.0)
            if abs(due - 1.0) <= EPS:
                continue
            arm = "holdout" if row.get("arm") == "holdout" else "treated"
            y = float(outcomes[leg])
            arms["all"][arm].append(y)
            arms["up" if due > 1.0 else "down"][arm].append(y)
    out = {k: {**control_arm.compare(v["treated"], v["holdout"]),
               "mean_holdout": _mean(v["holdout"]), "mean_treated": _mean(v["treated"])}
           for k, v in arms.items()}
    return {**out, "primary": out["up"]["verdict"],
            "basis": "novel hypotheses born per CPU-hour of the leg in the hour after the weights "
                     "were published; treated legs ran on the tournament's weights, held-out "
                     "legs on the prior allocation (weight 1.0), same hours, same desk"}


def _mean(xs: Sequence[float]) -> float | None:
    return round(sum(xs) / len(xs), 6) if xs else None


def novelty_credit(local_count: int) -> float:
    """The breadth law's deflator: a birth whose (symbol, family) pair has already been born
    `local_count` times before it is worth 1/sqrt(1 + local_count) of a new one, so cheap
    near-duplicates cannot buy births per CPU-hour."""
    return 1.0 / math.sqrt(1.0 + max(0, int(local_count)))


def steer(proposals: Mapping[str, Mapping[str, float]],
          suspended: Mapping[str, bool],
          history: Sequence[Mapping[str, Any]],
          hour_key: str, down_ok: Iterable[str] = ()) -> dict[str, Any]:
    """One hour's steer: drop suspended contestants, score the rest on `history` (past assignments
    carrying `tilts` and `outcomes`), weight them, combine, draw the holdout, and withdraw
    everything unless the holdout comparison ADMITTED the steer. `down_ok` names the only legs
    (judge / validation) whose weight may fall below 1.0; every other leg is up-only. Returns the
    artifact body."""
    may_fall = set(down_ok)
    dropped = sorted(c for c in proposals if suspended.get(c))
    live = {c: dict(p) for c, p in proposals.items() if not suspended.get(c)}
    present = sorted(c for c, p in live.items() if p)
    scores: dict[str, list[float]] = {c: [] for c in CONTESTANTS}
    for a in history:
        outcomes = a.get("outcomes")
        if not isinstance(outcomes, dict):
            continue
        for c, t in (a.get("tilts") or {}).items():
            s = score_hour(t or {}, outcomes)
            if s is not None:
                scores.setdefault(c, []).append(s)
    board = authorities(scores, present)
    auth = {c: float(r["authority"]) for c, r in board.items()}
    due = {lg: (w if lg in may_fall else max(1.0, w))
           for lg, w in combine({c: live[c] for c in present}, auth).items()}
    held = holdout(due, hour_key)
    comparison = holdout_comparison(history)
    withdrawn = comparison["primary"] != "ADMITTED"
    legs: dict[str, dict[str, Any]] = {}
    for lg, w in sorted(due.items()):
        arm = "holdout" if lg in held else "treated"
        applied = 1.0 if (arm == "holdout" or withdrawn) else w
        legs[lg] = {"due": w, "applied": round(applied, 6), "arm": arm,
                    "tilts": {c: live[c][lg] for c in present if lg in live[c]}}
    return {
        "hour": hour_key,
        "contestants": {c: {**board.get(c, {"authority": 0.0, "status": "NO_PROPOSAL"}),
                            "proposed_legs": len(live.get(c) or {}),
                            "suspended": bool(suspended.get(c))} for c in CONTESTANTS},
        "dropped_suspended": dropped,
        "weights": {lg: r["applied"] for lg, r in legs.items()},
        "legs": legs, "holdout": held, "holdout_share": HOLDOUT_SHARE, "salt": SALT,
        "comparison": comparison,
        "authoritative": bool(legs) and not withdrawn and any(
            abs(r["applied"] - 1.0) > EPS for r in legs.values()),
        "withdrawn": withdrawn,
        "why": (f"holdout comparison is {comparison['primary']}, not ADMITTED: every leg runs on "
                "the prior allocation (neutral) until a held-out comparison admits the steer"
                if withdrawn else
                "treated legs carry the tournament's weights; the held-out slice runs on the prior "
                "allocation as the control"),
        "parameters": {"max_tilt": MAX_TILT, "arena_step": ARENA_STEP, "eta": ETA,
                       "min_hours": MIN_HOURS, "window_h": WINDOW_H,
                       "down_ok_legs": len(may_fall)},
    }
