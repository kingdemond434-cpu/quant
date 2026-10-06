"""METHOD COMPETITION THAT MOVES THE SCHEDULER (Tier S audit rows AC13 and I12).

THE GAP, IN THE AUDIT'S OWN WORDS. AC13: *"adoption must change the real gauntlet or scheduler"* --
the arena (`libs/research/arena.py`) recorded LEADS / TRAILS per research arm and the Red Queen's
S33 scheduler champion beat the incumbent split on held-out days, and neither number reached the
thing that decides which leg runs next and for how long. I12: *"researcher_market and
meta_benchmark ... hold no budget authority"* -- they need "a scored tournament with a randomized
budget holdout", linked to realised P&L.

WHAT DECIDES COMPUTE. `desks/mt5/research/cycle_pricing.build_plan` -- every hourly leg's seconds
and the order the legs run in. This module produces the per-leg WEIGHTS it reads
(`reports/tier_s/SCHEDULER_STEER.json`, written by `tier_s.organ_steer`):

    contestants   arena            LEADS arms' legs up, TRAILS arms' legs down (bandit arms ->
                                   legs via `research_budget.LEG_ARMS`)
                  red_queen        the S33 scheduler champion's CURRENT split over producers, once
                                   it beat the incumbent on held-out days (its adoption)
                  researcher_market  the market's per-leg prices against their median (its ONLY
                                   route to compute: cycle_pricing no longer blends it as well)
                  meta_benchmark   validation legs up while the sealed immune score sits below its
                                   trailing mean, down while above
    tournament    every contestant's tilts are scored each hour against what the legs then
                  REALISED, on two channels: novelty-deflated unique births per CPU-hour (lost
                  runs scored as harm) and the change in the leg's FORWARD R (the forward clocks of
                  the certificates its producers bore -- the desk's realised-forward P&L per leg).
                  Each channel's hour score is standardised and mapped to a gain in [0, 1]; the
                  AUTHORITY is Hedge on the mean gain with eta = sqrt(8 ln K / T). A contestant
                  with fewer than MIN_HOURS scored hours has ZERO authority.
    experiment    two independent seeded random draws per hour among the legs the tournament wants
                  to move: the HOLDOUT (prior allocation, weight 1.0) and the TRIAL slice (the
                  holdout's size). The holdout-versus-treated test is a sequentially valid
                  e-process on HOURLY BLOCKS of APPLIED weights (`sequential_test`), and sets:
                    TRIAL     (UNMEASURED / UNDECIDED) only the trial slice runs on the weights;
                              every other leg is neutral; `authoritative: false`
                    ADMITTED  every non-holdout leg runs on the weights; authoritative
                    REJECTED  every leg neutral for COOLDOWN_H, then the trial resumes judged on
                              post-rejection evidence only

THE LAWS IT KEEPS, pinned by tests:

  * BACKPRESSURE GOES TO THE JUDGE ONLY. Only a leg in `down_ok` (the validation department) may
    sit below 1.0; every mining, information and generation leg is floored at 1.0 here AND in
    cycle_pricing, and cycle_pricing orders legs by their UNSTEERED price except to push a
    down-weighted judge leg later -- a steer can never move a generation leg back in a short pass.
  * ZERO-SUM IN WEIGHT SPACE, PAID BY THE JUDGE. The APPLIED weights average exactly 1.0: the
    steer's ups are paid for by judge-side downs -- the tournament's own, then an equal
    down-weight over the judge legs not otherwise steered -- and scaled to what those can pay.
    cycle_pricing's par floor and never-reduced total still hold.
  * A SUSPENDED ORGAN CARRIES NO AUTHORITY (`libs.tiers.authority.suspended`, the arena included
    through its own contract): its contestant is dropped before anything is combined.
  * INCONCLUSIVE IS NEUTRAL, except the seeded non-authoritative trial slice that produces the
    evidence; credit goes to the weights cycle_pricing actually APPLIED in that hour.

Research side only: nothing here sizes, admits, certifies or places.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

from libs.tiers import control_arm

CONTESTANTS: tuple[str, ...] = ("arena", "red_queen", "researcher_market", "meta_benchmark")
#: the organ whose `authority.suspended(...)` gates each contestant (meta_benchmark's verdicts are
#: published by the `immune` organ; the arena's contract is its leg_contracts row, `steers: arena`)
CONTESTANT_ORGAN: dict[str, str] = {"arena": "arena", "red_queen": "red_queen",
                                    "researcher_market": "market", "meta_benchmark": "immune"}
#: a weight never leaves [1 - MAX_TILT, 1 + MAX_TILT]
MAX_TILT = 0.5
#: the arena's step for a decisive verdict (LEADS up, TRAILS down)
ARENA_STEP = 0.25
#: share of the hour's movable legs held on the prior allocation
HOLDOUT_SHARE = 0.2
SALT = "scheduler_steer"
#: THE TRIAL SLICE. While the test is UNMEASURED or UNDECIDED, a second seeded random draw of the
#: SAME SIZE AS THE HOLDOUT runs on the weights; every other leg stays neutral. Equal arms minimise
#: the variance of the treated-minus-holdout difference for a given exposure. Speed at the hourly
#: cadence: each hour with at least one up-weighted leg in both arms is one block of the
#: e-process. With M movable legs, half up-weighted, P(an arm holds no up leg) = 0.8^(0.1 M), so
#: from M ~ 30 nearly every hour is a block. A steady treated-minus-holdout difference that is
#: half the recent range (x = 0.5) multiplies the lambda = 0.9 component by 1.45 an hour and
#: crosses 1/ALPHA in about 12 blocks (half a day); x = 0.2 needs about 30 (a day and a quarter);
#: x = 0.1 about 65 (under three days) -- all well inside WINDOW_H. A smaller slice yields fewer
#: blocks; a larger one exposes more legs to an unproven steer with the holdout still limiting.
TRIAL_SALT = "scheduler_steer_trial"
#: after a REJECTED test every leg is neutral this long; then the trial retries on fresh evidence
COOLDOWN_H = 72
#: scored hours below which a contestant has NO authority
MIN_HOURS = 3
#: the rolling window the test and the tournament scores are re-derived over
WINDOW_H = 14 * 24
#: the sequential test's level and its betting fractions (a fixed mixture: an average of
#: e-processes is an e-process, so no tuning is fitted on the data it judges)
ALPHA = 0.05
LAMBDAS: tuple[float, ...] = (0.1, 0.3, 0.6, 0.9)
MIN_BLOCKS = 3
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


#: the outcome channels a contestant is scored on, and where each lives on an assignment
CHANNELS: tuple[tuple[str, str], ...] = (("births", "outcomes"), ("forward_r", "pnl_outcomes"))


def hour_gains(history: Sequence[Mapping[str, Any]]) -> dict[str, list[float]]:
    """{contestant: [gain per scored hour]}. Each channel's raw scores are standardised by that
    channel's pooled spread, clipped to [-1, 1] and mapped to [0, 1]; an hour's gain is the mean
    over the channels that scored it. 0.5 is no skill."""
    raw: dict[str, list[tuple[int, str, float]]] = {}
    for h, a in enumerate(history):
        for ch, key in CHANNELS:
            out = a.get(key)
            if not isinstance(out, Mapping):
                continue
            for c, t in (a.get("tilts") or {}).items():
                sc = score_hour(t or {}, out)
                if sc is not None:
                    raw.setdefault(ch, []).append((h, str(c), sc))
    per: dict[str, dict[int, list[float]]] = {}
    for _ch, rows in raw.items():
        xs = [x for _h, _c, x in rows]
        mu = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0
        scale = sd if sd > EPS else (max(abs(x) for x in xs) or 1.0)
        for h, c, x in rows:
            per.setdefault(c, {}).setdefault(h, []).append(
                0.5 * (1.0 + max(-1.0, min(1.0, x / scale))))
    return {c: [sum(v) / len(v) for _h, v in sorted(hrs.items())] for c, hrs in per.items()}


def authorities(gains: Mapping[str, Sequence[float]], present: Sequence[str],
                min_hours: int = MIN_HOURS) -> dict[str, dict[str, Any]]:
    """HEDGE over the contestants that proposed this hour. Only a contestant with at least
    `min_hours` scored hours is eligible; the rest have authority 0. Among the K eligible, with T
    the largest number of scored hours, eta = sqrt(8 ln K / T) (the Hedge rate for losses in
    [0, 1]) and a_c is proportional to exp(-eta x T x mean loss_c), loss = 1 - gain."""
    rows: dict[str, dict[str, Any]] = {}
    elig = [c for c in present if len(gains.get(c) or ()) >= min_hours]
    for c in present:
        g = [float(x) for x in (gains.get(c) or ())]
        rows[c] = {"hours_scored": len(g),
                   "mean_gain": round(sum(g) / len(g), 6) if g else None,
                   "status": "MEASURED" if c in elig else "INSUFFICIENT_HOURS",
                   "authority": 0.0}
    if not elig:
        return rows
    k = len(elig)
    t = max(len(gains[c]) for c in elig)
    eta = math.sqrt(8.0 * math.log(k) / t) if k > 1 else 0.0
    loss = {c: 1.0 - float(rows[c]["mean_gain"]) for c in elig}
    lo = min(loss.values())
    raw = {c: math.exp(-eta * t * (loss[c] - lo)) for c in elig}
    tot = sum(raw.values())
    for c in elig:
        rows[c]["authority"] = round(raw[c] / tot, 6)
        rows[c]["eta"] = round(eta, 6)
    return rows


def combine(proposals: Mapping[str, Mapping[str, float]],
            auth: Mapping[str, float]) -> dict[str, float]:
    """w_leg = 1 + sum_c a_c (t_c,leg - 1), clipped. Zero authority everywhere is 1.0 everywhere."""
    legs = sorted({lg for p in proposals.values() for lg in p})
    return {lg: round(_clip(1.0 + sum(float(auth.get(c, 0.0)) * (float(p.get(lg, 1.0)) - 1.0)
                                      for c, p in proposals.items())), 6) for lg in legs}


def zero_sum(weights: Mapping[str, float], funders: Sequence[str] = ()) -> dict[str, float]:
    """Make the applied weights average exactly 1.0 -- BACKPRESSURE GOES TO THE JUDGE.

    The ups are paid for first by the downs among `weights` (only judge legs can be down), then by
    an equal down-weight spread over `funders` (the judge-side legs not otherwise steered this
    hour), each at most MAX_TILT below 1.0. If even that cannot pay for them, the ups are scaled
    to what it can; if the downs exceed the ups, the downs are scaled to the ups. Returns weights
    for `weights` AND for the funders that paid."""
    up = sum(w - 1.0 for w in weights.values() if w > 1.0)
    down = sum(1.0 - w for w in weights.values() if w < 1.0)
    fund = [f for f in sorted(set(funders)) if f not in weights]
    if up <= EPS and down <= EPS:
        return dict.fromkeys(weights, 1.0)
    if down >= up:
        k = up / down
        return {lg: round(1.0 + (w - 1.0) * (k if w < 1.0 else 1.0), 6)
                for lg, w in weights.items()}
    pay = min(up - down, MAX_TILT * len(fund))
    ku = (down + pay) / up
    res = {lg: round(1.0 + (w - 1.0) * (ku if w > 1.0 else 1.0), 6) for lg, w in weights.items()}
    if pay > EPS:
        res.update(dict.fromkeys(fund, round(1.0 - pay / len(fund), 6)))
    return res


def _draw(pool: Sequence[str], k: int, salt: str, hour_key: str) -> list[str]:
    pool = sorted(set(pool))
    k = min(int(k), len(pool))
    if k <= 0:
        return []
    seed = int(hashlib.sha256(f"{salt}|{hour_key}".encode()).hexdigest()[:16], 16)
    pick = np.random.default_rng(seed).choice(len(pool), size=k, replace=False)
    return sorted(pool[int(i)] for i in pick)


def holdout(legs: Iterable[str], hour_key: str, share: float = HOLDOUT_SHARE,
            salt: str = SALT) -> list[str]:
    """The seeded random slice held on the prior allocation this hour (seed sha256(salt|hour)).
    At least one leg whenever two or more are movable."""
    pool = sorted(set(legs))
    if len(pool) < 2:
        return []
    return _draw(pool, max(1, round(share * len(pool))), salt, hour_key)


def trial(candidates: Sequence[str], hour_key: str, k: int,
          salt: str = TRIAL_SALT) -> list[str]:
    """The seeded TRIAL slice: k non-holdout movable legs, an independent draw every hour."""
    return _draw(candidates, k, salt, hour_key)


def _t(x: Any) -> datetime | None:
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=UTC)
    if not x:
        return None
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _arm_of(row: Mapping[str, Any]) -> str | None:
    """By the APPLIED weight, never the intended one: held out (due a weight, ran at 1.0 by design)
    or treated (ran on a weight other than 1.0). Anything else is neither arm."""
    due = float(row.get("due") or 1.0)
    if abs(due - 1.0) <= EPS:
        return None
    raw = row.get("applied")
    applied = float(raw) if isinstance(raw, (int, float)) else 1.0
    if row.get("arm") == "holdout":
        return "holdout" if abs(applied - 1.0) <= EPS else None
    return "treated" if abs(applied - 1.0) > EPS else None


def blocks(assignments: Sequence[Mapping[str, Any]], key: str = "outcomes",
           side: str = "up") -> list[dict[str, Any]]:
    """One block per scored hour: mean treated outcome minus mean held-out outcome over the legs
    due a weight on `side` ("up" > 1, "down" < 1, "all"). Blocking by hour absorbs the dependence
    between legs that shared the hour's desk."""
    out = []
    for a in sorted(assignments, key=lambda r: str(r.get("at") or "")):
        o = a.get(key)
        if not isinstance(o, Mapping):
            continue
        arms: dict[str, list[float]] = {"treated": [], "holdout": []}
        for leg, row in (a.get("legs") or {}).items():
            if not isinstance(row, Mapping) or leg not in o:
                continue
            due = float(row.get("due") or 1.0)
            if (side == "up" and due <= 1.0) or (side == "down" and due >= 1.0):
                continue
            arm = _arm_of(row)
            if arm and isinstance(o[leg], (int, float)):
                arms[arm].append(float(o[leg]))
        if arms["treated"] and arms["holdout"]:
            out.append({"at": a.get("at"), "d": _mean(arms["treated"]) - _mean(arms["holdout"]),
                        "n_treated": len(arms["treated"]), "n_holdout": len(arms["holdout"])})
    return out


def sequential_test(diffs: Sequence[float], alpha: float = ALPHA) -> dict[str, Any]:
    """A sequentially valid, always-valid test on hourly block differences.

    Each block is scaled by a PREDICTABLE bound c_h = 2 x the largest |d| seen in EARLIER blocks
    and clipped to [-1, 1]; the first block only sets the scale. Two betting e-processes,
    E+ = mean over LAMBDAS of prod(1 + lambda x_h) (against H0: the clipped difference has mean
    <= 0) and E- with -x_h, are supermartingales under their nulls, so by Ville's inequality the
    running maximum crosses 1/alpha with probability at most alpha however often it is looked at.
    ADMITTED when max E+ >= 1/alpha, REJECTED when max E- >= 1/alpha, UNMEASURED below MIN_BLOCKS
    usable blocks, UNDECIDED otherwise."""
    xs: list[float] = []
    c = 0.0
    for d in diffs:
        if c > EPS:
            xs.append(max(-1.0, min(1.0, float(d) / c)))
        c = max(c, 2.0 * abs(float(d)))
    if len(xs) < MIN_BLOCKS:
        return {"verdict": "UNMEASURED", "blocks": len(xs), "e_up": None, "e_down": None,
                "why": f"{len(xs)} usable hourly block(s) < {MIN_BLOCKS}"}
    up = [1.0] * len(LAMBDAS)
    dn = [1.0] * len(LAMBDAS)
    best_up = best_dn = 1.0
    for x in xs:
        up = [u * (1.0 + lam * x) for u, lam in zip(up, LAMBDAS, strict=True)]
        dn = [v * (1.0 - lam * x) for v, lam in zip(dn, LAMBDAS, strict=True)]
        best_up = max(best_up, sum(up) / len(up))
        best_dn = max(best_dn, sum(dn) / len(dn))
    bar = 1.0 / alpha
    verdict = ("ADMITTED" if best_up >= bar else "REJECTED" if best_dn >= bar else "UNDECIDED")
    return {"verdict": verdict, "blocks": len(xs), "e_up": round(best_up, 4),
            "e_down": round(best_dn, 4), "bar": bar, "mean_x": round(sum(xs) / len(xs), 6)}


def holdout_comparison(assignments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The experiment's verdict and its evidence. `primary` is the sequential test on the
    up-weighted legs' births blocks (where a reallocation must pay); the down side, all steered
    legs and the forward-R (P&L) channel are published beside it, each with the same test, and the
    Welch comparison of the pooled leg-hours is kept for reference only (it is not sequentially
    valid and decides nothing)."""
    out: dict[str, Any] = {}
    for name, key, side in (("up", "outcomes", "up"), ("down", "outcomes", "down"),
                            ("all", "outcomes", "all"), ("forward_r", "pnl_outcomes", "all"),
                            ("elogw", "elogw_outcomes", "all")):
        bl = blocks(assignments, key, side)
        seq = sequential_test([b["d"] for b in bl])
        out[name] = {**seq, "n_treated": sum(b["n_treated"] for b in bl),
                     "n_control": sum(b["n_holdout"] for b in bl),
                     "mean_block_delta": _mean([b["d"] for b in bl]) if bl else None}
    pooled: dict[str, list[float]] = {"treated": [], "holdout": []}
    for a in assignments:
        o = a.get("outcomes")
        if isinstance(o, Mapping):
            for leg, row in (a.get("legs") or {}).items():
                arm = _arm_of(row) if isinstance(row, Mapping) else None
                if arm and leg in o and float(row.get("due") or 1.0) > 1.0:
                    pooled[arm].append(float(o[leg]))
    out["welch_reference"] = control_arm.compare(pooled["treated"], pooled["holdout"])
    return {**out, "primary": out["up"]["verdict"],
            "basis": "hourly blocks of (mean treated - mean held-out) outcome, arms by APPLIED "
                     "weight; outcome = novelty-deflated unique births per CPU-hour (a lost run "
                     "scores as harm); forward_r = change in the leg's forward R; elogw = change "
                     "in credited dE[log W]; mixture betting e-process, alpha "
                     f"{ALPHA}, always valid under repeated hourly looks"}


def _mean(xs: Sequence[float]) -> float:
    return round(sum(xs) / len(xs), 6) if xs else 0.0


def novelty_credit(local_count: int) -> float:
    """The breadth law's deflator: a (symbol, family) pair already born `local_count` times before
    is worth 1/sqrt(1 + local_count) of a new one."""
    return 1.0 / math.sqrt(1.0 + max(0, int(local_count)))


def steer(proposals: Mapping[str, Mapping[str, float]],
          suspended: Mapping[str, bool],
          history: Sequence[Mapping[str, Any]],
          hour_key: str, down_ok: Iterable[str] = (), rejected_at: Any = None,
          now: datetime | None = None) -> dict[str, Any]:
    """One hour's steer: drop suspended contestants, score the rest on `history` (past assignments
    carrying `tilts` and outcomes), weight them by Hedge, combine, floor every leg outside
    `down_ok` at 1.0, draw the holdout and the trial slice, pick the mode from the sequential test
    and make the APPLIED weights zero-sum. Returns the artifact body."""
    may_fall = set(down_ok)
    dropped = sorted(c for c in proposals if suspended.get(c))
    live = {c: dict(p) for c, p in proposals.items() if not suspended.get(c)}
    present = sorted(c for c, p in live.items() if p)
    gains = hour_gains(history)
    board = authorities(gains, present)
    # a SUSPENDED contestant keeps being SCORED (its tilts are still recorded) so its contract
    # can read ADMITTED again; it simply holds no authority meanwhile
    for c in dropped:
        g = gains.get(c) or []
        board[c] = {"hours_scored": len(g), "authority": 0.0, "status": "SUSPENDED",
                    "mean_gain": round(sum(g) / len(g), 6) if g else None}
    auth = {c: float(r["authority"]) for c, r in board.items()}
    due = {lg: (w if lg in may_fall else max(1.0, w))
           for lg, w in combine({c: live[c] for c in present}, auth).items()}
    movable = [lg for lg, w in due.items() if abs(w - 1.0) > EPS]
    held = holdout(movable, hour_key)
    trial_legs = trial(sorted(set(movable) - set(held)), hour_key, len(held))
    now = now or datetime.now(UTC)
    rejected = _t(rejected_at)
    fresh = [a for a in history if rejected is None or (_t(a.get("at")) or now) > rejected]
    comparison = holdout_comparison(fresh)
    v = comparison["primary"]
    if rejected is not None and now < rejected + timedelta(hours=COOLDOWN_H):
        mode = "COOLDOWN"
    elif v == "REJECTED":
        mode, rejected = "REJECTED", now
    elif v == "ADMITTED":
        mode = "ADMITTED"
    else:
        mode = "TRIAL"
    arm: dict[str, str] = {}
    for lg, w in due.items():
        if lg in held:
            arm[lg] = "holdout"
        elif abs(w - 1.0) <= EPS:
            arm[lg] = "neutral"
        elif mode == "ADMITTED":
            arm[lg] = "treated"
        elif mode == "TRIAL" and lg in trial_legs:
            arm[lg] = "trial"
        else:
            arm[lg] = "neutral"
    on = {lg: due[lg] for lg in due if arm[lg] in ("treated", "trial")}
    # the judge legs that are neither held out nor steered pay for the ups (backpressure to the
    # judge); they carry due 1.0 and are no arm of the experiment
    funders = sorted(lg for lg in may_fall if lg not in held and lg not in on)
    paid = zero_sum(on, funders)
    applied = {**dict.fromkeys(due, 1.0), **paid}
    for lg in paid:
        if lg not in due:
            due[lg] = 1.0
            arm[lg] = "funding"
    legs = {lg: {"due": due[lg], "applied": applied[lg], "arm": arm[lg],
                 "tilts": {c: live[c][lg] for c in present if lg in live[c]}}
            for lg in sorted(due)}
    moved = any(abs(w - 1.0) > EPS for w in applied.values())
    why = {
        "ADMITTED": "the sequential holdout test ADMITTED the steer: every non-holdout leg carries "
                    "the tournament's weights (zero-sum); the held-out slice runs at 1.0",
        "TRIAL": f"test {v}: only the seeded trial slice ({len(trial_legs)} leg(s), the "
                 "holdout's size) runs on the weights so the test can reach a verdict; every "
                 "other leg is neutral; authoritative: false",
        "REJECTED": "the sequential holdout test REJECTED the steer: every leg neutral, and the "
                    f"trial slice waits {COOLDOWN_H}h before retrying on fresh evidence",
        "COOLDOWN": f"cool-down after a REJECTED test at {rejected_at}: every leg neutral",
    }[mode]
    return {
        "hour": hour_key,
        "contestants": {c: {**board.get(c, {"authority": 0.0, "status": "NO_PROPOSAL"}),
                            "proposed_legs": len(live.get(c) or {}),
                            "suspended": bool(suspended.get(c))} for c in CONTESTANTS},
        "dropped_suspended": dropped,
        "weights": {lg: r["applied"] for lg, r in legs.items()},
        "applied_mean": round(sum(applied.values()) / len(applied), 6) if applied else 1.0,
        "legs": legs, "holdout": held, "trial": trial_legs, "mode": mode,
        "holdout_share": HOLDOUT_SHARE, "salt": SALT, "trial_salt": TRIAL_SALT,
        "comparison": comparison,
        "rejected_at": rejected.isoformat() if rejected else None,
        "authoritative": mode == "ADMITTED" and moved,
        "withdrawn": mode in ("REJECTED", "COOLDOWN"),
        "why": why,
        "parameters": {"max_tilt": MAX_TILT, "arena_step": ARENA_STEP, "min_hours": MIN_HOURS,
                       "window_h": WINDOW_H, "down_ok_legs": len(may_fall),
                       "cooldown_h": COOLDOWN_H, "alpha": ALPHA, "lambdas": list(LAMBDAS),
                       "trial_size": "equal to the holdout's",
                       "hedge_eta": "sqrt(8 ln K / T)"},
    }
