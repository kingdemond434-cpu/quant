"""MINE AROUND THE SURVIVORS: where each working edge is 2-3x stronger, and where it is not there.

    "Mine around survivors much harder than around random ideas. You already have evidence that
     XAU Asia works. Don't give it one experiment and spend 90% of compute randomly searching
     indicators. Decompose it. Ask: when does the existing edge become 2-3x stronger, and when
     does it disappear?"                                           -- the principal, 2026-09-05

WHAT THIS IS FOR, AND IT IS NOT NEW STRATEGIES. The desk already knows which sleeves work. What it
does not know is which STATES OF THOSE SLEEVES deserve capital. A sleeve with a 0.30R
unconditional expectancy that earns 0.9R on Tuesdays and -0.1R on Fridays is not one edge, it is
one edge and one liability sharing a name, and every unit of heat spent on the Friday half is
heat the Tuesday half could have used. Finding that costs no new hypothesis, no new instrument
and no new data -- only a decomposition of evidence the desk already owns.

THE TRAP THIS MODULE IS BUILT AROUND, in the principal's own words: "a 2-3x conditional edge found
across twenty slices with n=8 each is noise wearing a good number." Conditioning multiplies
hypotheses, and the maximum of twenty noisy slices is large by construction. Three things are
done about it and none of them is optional:

1. EVERY SLICE CARRIES ITS SAMPLE SIZE. Below MIN_SLICE_N observations there is no verdict at
   all -- UNMEASURED, which is not a weak finding but the absence of one.
2. EVERY SLICE CARRIES THE MULTIPLICITY OF EVERY SLICE TRIED, over all sleeves and all dimensions
   in one burden, deflated by `research/multiplicity.py`'s E[max_N Z] unmodified. Splitting the
   burden per sleeve or per dimension is the standard way to make a conditional slice look
   significant and it is not done here.
3. EVERY LIFT IS REPORTED TWICE -- on the raw conditional mean and on the SHRUNK one, where the
   slice is pulled toward the sleeve's own unconditional mean by the desk's k_state prior exactly
   as the allocator's posterior would pull it. The raw lift is what excites; the shrunk lift is
   what would actually be sized, and the gap between them at small n is the size of the illusion.

STRONGER means shrunk lift >= 2x, a deflated t above the line, AND a deflated CONTRAST against the
rest of the same group above it. The third condition is the one the first version lacked and the
one that makes the verdict mean what it says: `t_deflated` asks whether the slice's mean differs
from ZERO, which a slice can pass while being indistinguishable from its own sleeve's average.
Only the two-sample contrast can say the edge CHANGES in this state, and "reliably positive" read
as "reliably stronger" is how a decomposition manufactures states out of a sleeve that is simply
good everywhere. VANISHES means the shrunk conditional expectancy is at or below zero with the
sample behind it -- the finding with the most immediate value, because withdrawing heat from a
state that pays nothing needs no new edge and no new risk.

AND THE CONTRAST IS PUBLISHED SEPARATELY, because the verdict set alone throws away the best
evidence this module produces. Measured on this desk 2026-09-05: the `mean_reversion` cluster
earns +0.620R in the 01:00 UTC hour against +0.049R in every other hour, n=107, a Welch contrast
of t=5.1 and +2.88 after deflation against all 70 slices -- and it is NOT promoted to STRONGER,
because its shrunk lift is 1.90x against a 2.0x line. Both temptations are refused: the lift line
is not lowered to admit the result, and the result is not buried because it missed the line. The
`contrast` list carries it, with its sample and its burden, and a research task names it.

NOTHING HERE MOVES CAPITAL. It writes an artifact and research tasks. The allocator conditions on
the state dimensions `STATE_ADMISSION.json` has admitted, through its own shrinkage, and this
changes neither.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research.alpha_clusters import classify_sleeve  # noqa: E402

OUT = BASE / "reports" / "SURVIVOR_NEIGHBOURHOOD.json"
DRAWDOWN = BASE / "reports" / "DRAWDOWN_ALPHA.json"

#: A drawdown state must be over-represented by at least this much before a survivor's strength
#: inside it counts as an overlap. 1.0 is the base rate, so this asks for a real tilt rather than
#: any state that happened to appear once in the tail.
DRAWDOWN_LIFT_MIN = 1.25

#: Trades a group needs before it is worth decomposing at all. A sleeve with twelve trades cannot
#: be cut five ways and produce anything but noise, and cutting it anyway is how a research queue
#: fills with instructions nobody should follow.
MIN_SLEEVE_N = 20

#: THE TWO LEVELS THE DECOMPOSITION RUNS AT, and the second is not a convenience. On this desk's
#: forward history exactly ONE sleeve clears MIN_SLEEVE_N with a positive edge, so a sleeve-level
#: decomposition alone would report a single survivor and call the job done. The phenomenon
#: CLUSTER pools every sleeve that takes money from the same payer, which is where the sample is
#: -- and it is also the level at which "when is this edge stronger" is a question about a
#: mechanism rather than about one instrument's fortnight.
LEVELS: tuple[str, ...] = ("cluster", "sleeve")

#: Observations inside a slice before that slice has a verdict. Same floor as `regime_coverage`
#: and `opportunity_curve`; never lowered to make a slice speak.
MIN_SLICE_N = 8

#: The desk's conditional-expectancy prior strength, identical to `opportunity_curve.K_STATE` and
#: `regime_coverage.K_STATE`. A slice of n trades is worth n/(n+K_STATE) of its own mean and the
#: rest of the sleeve's unconditional one. At n=8 that is 17% -- which is exactly why an 8-trade
#: "3x edge" shrinks to almost nothing, and why the shrunk lift is the one to read.
K_STATE = 40.0

#: The lift the principal named. A state is only interesting if the edge there is at least this
#: multiple of the group's own unconditional expectancy, measured on the SHRUNK mean.
LIFT_STRONG = 2.0

#: THE UNCONDITIONAL EXPECTANCY A GROUP MUST CLEAR BEFORE A LIFT RATIO IS REPORTED AT ALL, and it
#: is `regime_coverage.COVERED_R` -- the desk's own line for "this bucket is covered". A ratio
#: against a base near zero is arithmetic, not a finding: `xau_m15_anti_momentum` earns +0.005R
#: unconditionally on this tree, and dividing a +0.060R slice by it produced a "6.1x edge" on a
#: sleeve with no edge to multiply. The floor is a TIGHTENING; nothing here is loosened by it.
COVERED_R = 0.05

#: |t| after multiplicity deflation before a slice is called STRONGER rather than watched.
T_LINE = 2.0

STRONGER, WATCH, VANISHES, NEUTRAL, UNMEASURED = (
    "STRONGER", "WATCH", "VANISHES", "NEUTRAL", "UNMEASURED")

#: Bucket labels that mean "the conditioner had no value here", not "the world was in this state".
#: Excluded from scoring so they cannot become a research target or carry multiplicity weight.
_BOOKKEEPING_BUCKETS: frozenset[str] = frozenset({"no_prior"})


def _trades() -> list[Any]:
    from research.state_admission_run import load_trades
    return list(load_trades("shadow"))


def _shrunk(rs: list[float], prior: float) -> float:
    """The slice's mean pulled toward the sleeve's own unconditional mean by the k_state prior."""
    n = len(rs)
    lam = n / (n + K_STATE)
    return lam * float(np.mean(rs)) + (1.0 - lam) * prior


def _t_stat(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    a = np.asarray(xs, dtype="float64")
    sd = float(a.std(ddof=1))
    if sd <= 0:
        return 0.0
    return float(a.mean() / (sd / math.sqrt(n)))


def _t_contrast(inside: list[float], outside: list[float]) -> float:
    """Welch t of the slice against THE REST OF ITS OWN GROUP -- the question actually being asked.

    `_t_stat` tests whether the slice's mean differs from ZERO, which is not what "the edge is
    stronger here" means: a slice can be reliably positive and be no different from the sleeve's
    average, and reporting the first as if it were the second is how a decomposition manufactures
    states. The contrast is the two-sample test, and it is the one that can say the edge CHANGES.

    Unequal variances are assumed (Welch, not pooled): a 107-trade slice and a 161-trade remainder
    of the same sleeve routinely have different dispersion, and the pooled test would understate
    the standard error in exactly the direction that makes a slice look special.
    """
    n1, n2 = len(inside), len(outside)
    if n1 < 2 or n2 < 2:
        return 0.0
    a = np.asarray(inside, dtype="float64")
    b = np.asarray(outside, dtype="float64")
    v1, v2 = float(a.var(ddof=1)), float(b.var(ddof=1))
    se = math.sqrt(v1 / n1 + v2 / n2)
    if se <= 0:
        return 0.0
    return float((a.mean() - b.mean()) / se)


def conditioners(trades: list[Any]) -> tuple[dict[str, dict[int, str]], dict[str, str]]:
    """dimension -> {trade index: bucket}, and the dimensions that could not be built.

    EVERY DIMENSION HERE IS RECONSTRUCTIBLE AT THE TRADE'S OWN MOMENT. That is the same rule
    `libs/regime/state_admission.build_labeller` enforces and for the same reason: labelling an
    August trade with today's regime fit would test whether the PRESENT predicts the past, which
    every dimension passes. `prior_outcome` uses only the sleeve's own PREVIOUS trade and
    `prior_day_book` only the book's PREVIOUS calendar day, so neither can see its own return.
    """
    from research.session_phase import phase_for_hour

    gaps: dict[str, str] = {}
    out: dict[str, dict[int, str]] = defaultdict(dict)
    stamps: list[datetime | None] = []
    for t in trades:
        try:
            stamps.append(datetime.fromisoformat(str(t.when)).astimezone(UTC))
        except (TypeError, ValueError):
            stamps.append(None)

    try:
        from research.session_phase import broker_utc_offset_h
        off, src = broker_utc_offset_h()
    except Exception:                                                     # noqa: BLE001
        off, src = None, "unavailable"
    if off is None:
        gaps["session_phase"] = (
            f"broker clock offset unknown ({src}); session phases are cut on the UTC hour, so a "
            "phase label here is the UTC phase and not the broker's")

    for i, dt in enumerate(stamps):
        if dt is None:
            continue
        h = (dt.hour + (off or 0)) % 24
        out["hour_utc"][i] = f"{dt.hour:02d}"
        out["session_phase"][i] = str(phase_for_hour(h))
        out["weekday"][i] = dt.strftime("%a")
        out["month_phase"][i] = ("month_end" if dt.day >= 25 else
                                 "month_start" if dt.day <= 5 else "month_middle")

    # THE SLEEVE'S OWN PREVIOUS TRADE. Strictly prior: index i sees only trades before it.
    order: dict[str, list[int]] = defaultdict(list)
    for i, dt in enumerate(stamps):
        if dt is not None:
            order[str(trades[i].sleeve)].append(i)
    for sleeve, idxs in order.items():
        idxs.sort(key=lambda j: stamps[j] or datetime.min.replace(tzinfo=UTC))
        for pos, i in enumerate(idxs):
            if pos == 0:
                out["prior_outcome"][i] = "no_prior"
                continue
            prev = float(trades[idxs[pos - 1]].r)
            out["prior_outcome"][i] = "after_win" if prev > 0 else "after_loss"
        del sleeve

    # THE BOOK'S PREVIOUS CALENDAR DAY. Also strictly prior.
    by_day: dict[str, float] = defaultdict(float)
    for i, dt in enumerate(stamps):
        if dt is not None:
            by_day[dt.strftime("%Y-%m-%d")] += float(trades[i].r)
    days = sorted(by_day)
    prev_of = {d: days[k - 1] for k, d in enumerate(days) if k > 0}
    for i, dt in enumerate(stamps):
        if dt is None:
            continue
        d = dt.strftime("%Y-%m-%d")
        p = prev_of.get(d)
        out["prior_day_book"][i] = ("no_prior" if p is None else
                                    "after_book_up" if by_day[p] > 0 else "after_book_down")

    try:
        from libs.regime.state_admission import build_labeller
        fn = build_labeller("event")
        if fn is None:
            gaps["event"] = "no event labeller on this tree; the calendar is unavailable"
        else:
            for i, t in enumerate(trades):
                lab = fn(t)
                if lab:
                    out["event"][i] = str(lab)
    except Exception as exc:                                              # noqa: BLE001
        gaps["event"] = f"{type(exc).__name__}: {exc}"
    return dict(out), gaps


def decompose(trades: list[Any]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    """Per (group, dimension, bucket): the conditional edge, its lift, its sample and its t.

    Run at both levels in `LEVELS`, into ONE row list carrying ONE multiplicity burden. Scoring
    the cluster level in a separate report with its own denominator would be the split-the-burden
    trick this module exists to avoid.
    """
    dims, gaps = conditioners(trades)
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, t in enumerate(trades):
        groups[("sleeve", str(t.sleeve))].append(i)
        groups[("cluster", classify_sleeve(str(t.sleeve)))].append(i)

    sleeves: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for (level, sleeve), idxs in sorted(groups.items()):
        rs = [float(trades[i].r) for i in idxs]
        base = float(np.mean(rs))
        ok = len(rs) >= MIN_SLEEVE_N and base >= COVERED_R
        key = f"{level}:{sleeve}"
        sleeves[key] = {
            "level": level, "name": sleeve,
            "n": len(rs), "mean_r": round(base, 4), "sum_r": round(float(np.sum(rs)), 4),
            "t": round(_t_stat(rs), 3),
            "cluster": sleeve if level == "cluster" else classify_sleeve(sleeve),
            "decomposed": ok,
            "why": ("decomposed" if ok else
                    f"not decomposed: {len(rs)} trades against the {MIN_SLEEVE_N} floor"
                    if len(rs) < MIN_SLEEVE_N else
                    f"not decomposed: {base:+.4f}R unconditional is below the {COVERED_R}R "
                    "coverage floor, so there is no surviving edge here to mine around and a "
                    "lift ratio against it would be arithmetic"),
        }
        if not ok:
            continue
        for dim, labels in sorted(dims.items()):
            buckets: dict[str, list[float]] = defaultdict(list)
            for i in idxs:
                lab = labels.get(i)
                if lab:
                    buckets[lab].append(float(trades[i].r))
            for bucket, vals in sorted(buckets.items()):
                if bucket in _BOOKKEEPING_BUCKETS:
                    # "no_prior" is not a state of the world -- it is the first trade in a
                    # series, where the conditioner does not exist yet. Scoring it would put a
                    # bookkeeping label in a research instruction and spend a hypothesis on it.
                    continue
                row: dict[str, Any] = {
                    "level": level, "sleeve": sleeve, "cluster": sleeves[key]["cluster"],
                    "dimension": dim, "bucket": bucket, "n": len(vals),
                    "sleeve_n": len(rs), "sleeve_mean_r": round(base, 4),
                }
                if len(vals) < MIN_SLICE_N:
                    row.update({
                        "verdict": UNMEASURED,
                        "why": (f"{len(vals)} trade(s) in this slice against the {MIN_SLICE_N} "
                                "floor -- UNMEASURED, not a weak edge"),
                    })
                    rows.append(row)
                    continue
                raw = float(np.mean(vals))
                shrunk = _shrunk(vals, base)
                # The complement is OTHER STATES, not "everything else": a `no_prior` trade is not
                # a trade in a different state, it is a trade the conditioner could not label, and
                # folding it in would contrast this state against a mixture of states and
                # non-observations.
                rest = [float(trades[i].r) for i in idxs
                        if labels.get(i) and labels.get(i) != bucket
                        and labels.get(i) not in _BOOKKEEPING_BUCKETS]
                row.update({
                    "mean_r_raw": round(raw, 4),
                    "mean_r_shrunk": round(shrunk, 4),
                    "mean_r_rest": round(float(np.mean(rest)), 4) if rest else None,
                    "n_rest": len(rest),
                    "lift_raw": round(raw / base, 3) if base != 0 else None,
                    "lift_shrunk": round(shrunk / base, 3) if base != 0 else None,
                    "shrinkage_lambda": round(len(vals) / (len(vals) + K_STATE), 3),
                    "t_raw": round(_t_stat(vals), 3),
                    # None, not zero, when the dimension has a single bucket: there is no
                    # complement to contrast against, and a zero would read as "measured, no
                    # difference" instead of "this question was not asked".
                    "t_vs_rest": (round(_t_contrast(vals, rest), 3) if len(rest) >= 2 else None),
                })
                rows.append(row)
    return rows, sleeves, gaps


def _verdicts(rows: list[dict[str, Any]]) -> int:
    """Attach the multiplicity burden and the verdict. Returns the number of tests it was over."""
    from research.multiplicity import deflate_t

    scored = [r for r in rows if r.get("verdict") != UNMEASURED]
    n_tests = len(scored)
    for r in rows:
        r["n_tests"] = n_tests
        if r.get("verdict") == UNMEASURED:
            continue
        r["t_deflated"] = round(deflate_t(float(r.get("t_raw") or 0.0), n_tests), 3)
        # THE CONTRAST CARRIES THE SAME BURDEN. It is one more test per slice, drawn from the same
        # sample, so deflating it against anything smaller than the whole set would be the
        # split-the-burden trick under another name.
        #
        # THE CONTRAST IS DEFLATED IN MAGNITUDE, WHICH `deflate_t` IS NOT, and the difference
        # matters here in a way it does not for `t_deflated`. The repo's convention is
        # `t - E[max_N Z]`, a ONE-SIDED haircut for "is this the best of N": correct where the bar
        # is a positive threshold, and wrong on a two-sided statistic, because it turns a contrast
        # of ZERO into -2.4 and a row with no evidence either way then reads as strongly negative.
        # Here the haircut is applied to |t| and floored at zero, so deflation can only ever move
        # a contrast TOWARD "no difference" and can never manufacture one, in either direction.
        t_c = r.get("t_vs_rest")
        if t_c is None:
            r["t_vs_rest_deflated"] = None
        else:
            mag = max(abs(float(t_c)) - (abs(float(t_c)) - deflate_t(abs(float(t_c)), n_tests)),
                      0.0)
            r["t_vs_rest_deflated"] = round(math.copysign(mag, float(t_c)), 3)
        shrunk = float(r.get("mean_r_shrunk") or 0.0)
        lift = r.get("lift_shrunk")
        if shrunk <= 0:
            r["verdict"] = VANISHES
        elif (lift is not None and lift >= LIFT_STRONG and r["t_deflated"] >= T_LINE
                and r["t_vs_rest_deflated"] is not None
                and r["t_vs_rest_deflated"] >= T_LINE):
            # STRICTLY THREE CONDITIONS, and the third was added because the first two can both
            # hold of a slice that is no different from its own sleeve: "reliably positive" is not
            # "reliably stronger", and only the contrast can tell them apart.
            r["verdict"] = STRONGER
        elif lift is not None and lift >= LIFT_STRONG:
            r["verdict"] = WATCH
        else:
            r["verdict"] = NEUTRAL
        r["why"] = (
            f"{r['verdict']}: raw {r['mean_r_raw']:+.3f}R shrinks to {shrunk:+.3f}R against the "
            f"sleeve's {r['sleeve_mean_r']:+.3f}R (lift {r['lift_raw']}x raw, {lift}x shrunk) on "
            f"n={r['n']}; t_raw {r['t_raw']}, t_deflated {r['t_deflated']}, contrast against the "
            f"rest of the group t={r['t_vs_rest']} (deflated {r['t_vs_rest_deflated']}) over "
            f"{n_tests} slices"
            + ("; the raw lift is what excites and the shrunk lift is what would be sized"
               if r["verdict"] == WATCH else ""))
    return n_tests


def drawdown_states() -> tuple[dict[tuple[str, str], float], str]:
    """(dimension, state) -> lift, for the states over-represented in the book's own drawdown.

    READ FROM `DRAWDOWN_ALPHA.json`, WHICH IS WHY THAT ARTIFACT IS NOT A DEAD END. On its own,
    "this survivor is 2.5x itself on Thursdays" is a sizing note. Crossed with the drawdown's own
    state signature it becomes something far more valuable: a state where an EXISTING edge is
    stronger AND the rest of the book is losing is drawdown alpha the desk already owns and is not
    sizing as such -- the cheapest possible version of the thing the factory is hunting for.

    Only the tightest band whose states reached the sample floor is used, and the lift floor is
    stated. An absent artifact returns nothing and says so; it never silently returns "no overlap",
    because "we did not look" and "we looked and there is none" are different sentences.
    """
    try:
        doc = json.loads(DRAWDOWN.read_text("utf-8"))
    except (OSError, ValueError):
        return {}, f"{DRAWDOWN.name} absent; no survivor state is cross-referenced against the " \
                   "book's own drawdown windows on this run"
    sig = doc.get("state_signature") or {}
    min_n = int(doc.get("min_n") or MIN_SLICE_N)
    out: dict[tuple[str, str], float] = {}
    for _gran, by_band in sorted(sig.items()):
        for band in ("worst_5pct", "worst_10pct", "worst_20pct"):
            rows = by_band.get(band) or []
            usable = [r for r in rows if int(r.get("n_in_drawdown") or 0) >= min_n
                      and float(r.get("lift") or 0.0) >= DRAWDOWN_LIFT_MIN]
            if usable:
                for r in usable:
                    key = (str(r["dimension"]), str(r["state"]))
                    out[key] = max(out.get(key, 0.0), float(r["lift"]))
                break
    if not out:
        return {}, (f"{DRAWDOWN.name} carries no drawdown state that reached its own sample floor "
                    f"at a lift of {DRAWDOWN_LIFT_MIN}x; there is nothing to cross-reference, "
                    "which is UNMEASURED rather than 'no overlap'")
    return out, ""


def _tasks(rows: list[dict[str, Any]]) -> list[dict]:
    """Research instructions, ONE PER CELL. A slice can qualify three ways -- it overlaps the
    book's drawdown, it clears the lift line, and it clears the contrast -- and queuing it three
    times spends three units of a bounded research budget on one question. The lists are walked
    most-specific first and a cell already spoken for is skipped, so the queue carries the
    strongest reason rather than every reason."""
    tasks: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def _claim(r: dict[str, Any]) -> bool:
        key = (str(r["sleeve"]), str(r["dimension"]), str(r["bucket"]))
        if key in seen:
            return False
        seen.add(key)
        return True

    overlap = [r for r in rows
               if r.get("verdict") in (STRONGER, WATCH) and r.get("in_book_drawdown_state")]
    for r in sorted(overlap, key=lambda x: -(x.get("lift_shrunk") or 0.0))[:4]:
        if not _claim(r):
            continue
        tasks.append({
            "source": "survivor_neighbourhood", "kind": "survivor_drawdown_overlap",
            "title": (f"{r['level']} {r['sleeve']} is {r['lift_shrunk']}x itself at "
                      f"{r['dimension']}={r['bucket']}, a state the book LOSES in "
                      f"(drawdown lift {r['drawdown_lift']}x)"),
            "description": (
                f"{r['sleeve']} earns {r['mean_r_shrunk']:+.3f}R shrunk at "
                f"{r['dimension']}={r['bucket']} against {r['sleeve_mean_r']:+.3f}R "
                f"unconditionally (n={r['n']}, t_deflated {r['t_deflated']} over "
                f"{r['n_tests']} slices), and that same state is {r['drawdown_lift']}x "
                "over-represented in the book's own worst periods (DRAWDOWN_ALPHA.json). "
                "This is drawdown alpha the desk ALREADY OWNS and is not sizing as such -- the "
                "cheapest version of the edge the factory is hunting. Confirm the overlap "
                "survives forward, then size this state rather than the sleeve's average."),
            "sleeve": r["sleeve"], "dimension": r["dimension"], "bucket": r["bucket"],
            "status": None, "consumer": "deepening_worker / pf_allocator research",
        })
    strong = [r for r in rows if r.get("verdict") in (STRONGER, WATCH)]
    for r in sorted(strong, key=lambda x: -(x.get("lift_shrunk") or 0.0))[:6]:
        if not _claim(r):
            continue
        tasks.append({
            "source": "survivor_neighbourhood", "kind": "survivor_state_strength",
            "title": (f"{r['level']} {r['sleeve']} is {r['lift_shrunk']}x itself at "
                      f"{r['dimension']}={r['bucket']} (n={r['n']}, {r['verdict']})"),
            "description": (
                f"{r['sleeve']} earns {r['sleeve_mean_r']:+.3f}R unconditionally over "
                f"{r['sleeve_n']} trades. At {r['dimension']}={r['bucket']} it earns "
                f"{r['mean_r_raw']:+.3f}R raw on n={r['n']}, which the k_state prior shrinks to "
                f"{r['mean_r_shrunk']:+.3f}R -- a shrunk lift of {r['lift_shrunk']}x. "
                f"t_deflated {r['t_deflated']} against {r['n_tests']} slices tried. "
                "Deepen THIS state rather than searching for a new sleeve: is there a mechanism "
                "that explains why this state is different, and does the lift survive the next "
                "block of forward trades? A lift with no mechanism is a slice of a small sample."),
            "sleeve": r["sleeve"], "dimension": r["dimension"], "bucket": r["bucket"],
            "status": None, "consumer": "deepening_worker / proposers",
        })
    contrast = [r for r in rows if r.get("verdict") != UNMEASURED
                and r.get("t_vs_rest_deflated") is not None
                and float(r["t_vs_rest_deflated"]) >= T_LINE]
    for r in sorted(contrast, key=lambda x: -(x.get("t_vs_rest_deflated") or 0.0))[:5]:
        if not _claim(r):
            continue
        tasks.append({
            "source": "survivor_neighbourhood", "kind": "survivor_state_strength",
            "title": (f"{r['level']} {r['sleeve']} earns {r['mean_r_raw']:+.2f}R at "
                      f"{r['dimension']}={r['bucket']} against {r['mean_r_rest']:+.2f}R "
                      f"elsewhere (n={r['n']}, contrast t_deflated {r['t_vs_rest_deflated']})"),
            "description": (
                f"{r['sleeve']} earns {r['mean_r_raw']:+.4f}R at {r['dimension']}="
                f"{r['bucket']} on n={r['n']} against {r['mean_r_rest']:+.4f}R on the other "
                f"n={r['n_rest']} trades of the same group -- a Welch contrast of "
                f"t={r['t_vs_rest']}, {r['t_vs_rest_deflated']} after deflation against "
                f"{r['n_tests']} slices. The shrunk lift is {r['lift_shrunk']}x, which is BELOW "
                f"the {LIFT_STRONG}x line, so this is not promoted as STRONGER; it is the "
                "best-powered evidence in the decomposition that the edge is genuinely different "
                "in this state. Find the mechanism that explains the state before any heat "
                "follows it, and confirm the contrast on the next block of forward trades."),
            "sleeve": r["sleeve"], "dimension": r["dimension"], "bucket": r["bucket"],
            "status": None, "consumer": "deepening_worker / state_admission",
        })
    dead = [r for r in rows if r.get("verdict") == VANISHES]
    for r in sorted(dead, key=lambda x: x.get("mean_r_shrunk") or 0.0)[:6]:
        if not _claim(r):
            continue
        tasks.append({
            "source": "survivor_neighbourhood", "kind": "survivor_state_dead",
            "title": (f"{r['level']} {r['sleeve']} earns nothing at "
                      f"{r['dimension']}={r['bucket']} "
                      f"({r['mean_r_shrunk']:+.3f}R shrunk, n={r['n']})"),
            "description": (
                f"{r['sleeve']} earns {r['sleeve_mean_r']:+.3f}R unconditionally but "
                f"{r['mean_r_shrunk']:+.3f}R (shrunk) at {r['dimension']}={r['bucket']} on "
                f"n={r['n']} trades, t_deflated {r['t_deflated']} over {r['n_tests']} slices. "
                "This is the cheapest kind of finding: withdrawing heat from a state that pays "
                "nothing needs no new edge and adds no new risk. Confirm the state is causal "
                "rather than incidental before it conditions capital -- the state-admission "
                "gauntlet, not this report, is what admits a dimension."),
            "sleeve": r["sleeve"], "dimension": r["dimension"], "bucket": r["bucket"],
            "status": None, "consumer": "deepening_worker / state_admission",
        })
    return tasks


def run(write_queue: bool = True) -> dict[str, Any]:
    trades = _trades()
    if not trades:
        doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "n_trades": 0, "rows": [],
               "sleeves": {}, "gaps": {"ledgers": "no shadow ledger on this tree"}}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        return doc
    rows, sleeves, gaps = decompose(trades)
    n_tests = _verdicts(rows)
    dd_states, dd_why = drawdown_states()
    if dd_why:
        gaps["drawdown_overlap"] = dd_why
    for r in rows:
        lift = dd_states.get((str(r.get("dimension")), str(r.get("bucket"))))
        r["in_book_drawdown_state"] = lift is not None
        if lift is not None:
            r["drawdown_lift"] = round(lift, 3)
    tasks = _tasks(rows)
    decomposed = [s for s, v in sleeves.items() if v["decomposed"]]
    only_sleeves = [s for s in decomposed if sleeves[s]["level"] == "sleeve"]
    best = max(only_sleeves, key=lambda s: sleeves[s]["sum_r"], default=None)
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "n_trades": len(trades), "gaps": gaps,
        "min_sleeve_n": MIN_SLEEVE_N, "min_slice_n": MIN_SLICE_N, "k_state": K_STATE,
        "lift_strong": LIFT_STRONG, "t_line": T_LINE, "covered_r": COVERED_R,
        "levels": list(LEVELS),
        "n_tests": n_tests,
        "n_groups": len(sleeves), "n_groups_decomposed": len(decomposed),
        "n_sleeves_decomposed": len(only_sleeves),
        "groups_decomposed": decomposed,
        "best_sleeve": best,
        "not_decomposed": {s: v["why"] for s, v in sorted(sleeves.items())
                           if not v["decomposed"]},
        "groups": sleeves,
        "stronger": sorted([r for r in rows if r.get("verdict") == STRONGER],
                           key=lambda r: -(r.get("lift_shrunk") or 0.0)),
        "watch": sorted([r for r in rows if r.get("verdict") == WATCH],
                        key=lambda r: -(r.get("lift_shrunk") or 0.0)),
        "vanishes": sorted([r for r in rows if r.get("verdict") == VANISHES],
                           key=lambda r: r.get("mean_r_shrunk") or 0.0),
        "n_unmeasured_slices": sum(1 for r in rows if r.get("verdict") == UNMEASURED),
        # THE CONTRAST LIST, WHICH THE VERDICT SET ON ITS OWN THROWS AWAY. A slice can differ from
        # the rest of its group at a deflated t of 4 and still fall under a 2x lift line, and on
        # this desk's own history the single best-powered conditional finding does exactly that:
        # `mean_reversion` in the Asia-open hour, n=107, +0.62R against +0.05R in every other
        # hour, at a 1.9x lift. Reporting only lift-passing rows would hide it, and lowering the
        # lift line to admit it would be loosening a bar to fit a result. Both are refused: the
        # bar stands and the contrast is published beside it, with its own sample and burden.
        "contrast": sorted(
            [r for r in rows if r.get("verdict") != UNMEASURED
             and r.get("t_vs_rest_deflated") is not None
             and abs(float(r["t_vs_rest_deflated"])) >= T_LINE],
            key=lambda r: -abs(float(r["t_vs_rest_deflated"]))),
        "drawdown_states": [{"dimension": d, "state": s, "lift": round(v, 3)}
                            for (d, s), v in sorted(dd_states.items())],
        # A state where a SURVIVING edge is stronger and the rest of the book is losing: drawdown
        # alpha the desk already owns and is not sizing as such.
        "drawdown_overlap": sorted(
            [r for r in rows
             if r.get("in_book_drawdown_state") and r.get("verdict") in (STRONGER, WATCH)],
            key=lambda r: -(r.get("lift_shrunk") or 0.0)),
        # And the other direction: a state where an edge VANISHES which is also over-represented
        # in the book's worst periods. NOT INDEPENDENT EVIDENCE, and the rule below says so --
        # the state signature is cut on the full book, so a cluster's own losses help make the
        # periods it loses in bad. It is a consistency check that names WHERE the drawdown is
        # made, which is a different and cheaper question than where new alpha would come from.
        "drawdown_cause": sorted(
            [r for r in rows
             if r.get("in_book_drawdown_state") and r.get("verdict") == VANISHES],
            key=lambda r: r.get("mean_r_shrunk") or 0.0),
        "rows": rows,
        "instruction": [t["title"] for t in tasks],
        "rule": (
            f"a slice speaks only at n >= {MIN_SLICE_N}; STRONGER needs a SHRUNK lift >= "
            f"{LIFT_STRONG}x AND t_deflated >= {T_LINE} against every slice tried across every "
            "sleeve in one burden. The raw lift is reported beside the shrunk one because the gap "
            "between them at small n is the size of the illusion. `drawdown_cause` is a "
            "CONSISTENCY CHECK and not independent evidence: the drawdown state signature it is "
            "crossed against was cut on the FULL book, so a cluster's own losses help make the "
            "periods it loses in bad -- it names where the drawdown is made, it does not prove "
            "the state caused it"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    if write_queue and tasks:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(tasks, source="survivor_neighbourhood")
        except Exception as exc:                                          # noqa: BLE001
            doc["queue_error"] = f"{type(exc).__name__}: {exc}"
    doc["tasks"] = tasks
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args()
    d = run(write_queue=not a.no_queue)
    print(f"SURVIVOR NEIGHBOURHOOD  {d['n_trades']} trades, {d.get('n_groups')} groups, "
          f"{d.get('n_groups_decomposed')} decomposed, {d.get('n_tests')} slices scored, "
          f"{d.get('n_unmeasured_slices')} below the sample floor")
    for s in d.get("groups_decomposed", []):
        v = d["groups"][s]
        print(f"  survivor {s[:38]:38s} n={v['n']:3d} mean={v['mean_r']:+.3f}R t={v['t']:+.2f}")
    for r in (d.get("contrast") or [])[:6]:
        print(f"  CONTRAST  {r['level']:7s} {r['sleeve'][:26]:26s} "
              f"{r['dimension']}={r['bucket']:14s} n={r['n']:3d} {r['mean_r_raw']:+.3f}R vs "
              f"{r['mean_r_rest']:+.3f}R elsewhere  t_def={r['t_vs_rest_deflated']:+.2f} "
              f"lift={r['lift_shrunk']}x [{r['verdict']}]")
    for r in (d.get("drawdown_cause") or [])[:4]:
        print(f"  DD-CAUSE  {r['level']:7s} {r['sleeve'][:26]:26s} "
              f"{r['dimension']}={r['bucket']:14s} shrunk={r['mean_r_shrunk']:+.3f}R n={r['n']} "
              f"in a state {r['drawdown_lift']}x over-represented in the book's worst periods")
    for r in (d.get("drawdown_overlap") or [])[:5]:
        print(f"  OVERLAP   {r['level']:7s} {r['sleeve'][:26]:26s} "
              f"{r['dimension']}={r['bucket']:14s} lift={r['lift_shrunk']}x in a drawdown state "
              f"({r['drawdown_lift']}x over-represented)")
    for label in ("stronger", "watch", "vanishes"):
        for r in (d.get(label) or [])[:8]:
            print(f"  {label.upper():9s} {r['level']:7s} {r['sleeve'][:26]:26s} "
                  f"{r['dimension']}={r['bucket']:14s} "
                  f"n={r['n']:3d} raw={r['mean_r_raw']:+.3f} shrunk={r['mean_r_shrunk']:+.3f} "
                  f"lift={r['lift_shrunk']}x t_def={r['t_deflated']}")
    for g, why in d.get("gaps", {}).items():
        print(f"  GAP {g}: {why}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
